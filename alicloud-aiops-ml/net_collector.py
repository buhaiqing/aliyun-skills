"""SLB, OSS, and K8s resource collector."""
from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from resource_model import Resource
from cli_utils import cli_call
from cost_model import estimate_monthly_cost, compute_days_until_expire

logger = logging.getLogger(__name__)

_SLB_CMS_METRICS = {
    "net_in_avg": "TrafficRXNew",
    "net_out_avg": "TrafficTXNew",
}


def _fetch_cms_metric(
    metric_name: str,
    namespace: str,
    instance_id: str,
    days: int = 7,
) -> float:
    """Fetch a single CMS metric average over `days` days. Returns 0.0 on failure."""
    start = (
        f"$(date -u -d '{days} days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null "
        f"|| date -u -v-{days}d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
    )
    end = "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
    dimensions = f'[{{"instanceId":"{instance_id}"}}]'
    cmd = (
        f"aliyun cms DescribeMetricList"
        f" --MetricName {metric_name}"
        f" --Namespace {namespace}"
        f" --Dimensions '{dimensions}'"
        f" --StartTime {start}"
        f" --EndTime {end}"
        f" --Period 86400"
        f" --api-version 2019-05-01"
        f" --output json"
    )
    try:
        result = subprocess.run(cmd.replace(" --output json", ""), shell=True, capture_output=True, text=True, timeout=30)  # aliyun CLI v3 compat
        if result.returncode != 0:
            logger.debug("CMS %s/%s returned non-zero: %s", namespace, metric_name, result.stderr)
            return 0.0
        data = json.loads(result.stdout)
        dps = data.get("Datapoints", {})
        values: list[float] = []
        if isinstance(dps, str) and dps:
            try:
                parsed = json.loads(dps)
                if isinstance(parsed, dict):
                    values = [float(v) for v in parsed.values() if v is not None]
                elif isinstance(parsed, list):
                    values = [float(v) for v in parsed if v is not None]
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        if not values:
            return 0.0
        return sum(values) / len(values)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        logger.debug("CMS fetch %s/%s failed: %s", namespace, metric_name, e)
        return 0.0


def _fetch_slb_metrics(instance_id: str) -> dict[str, float]:
    namespace = "acs_slb_dashboard"
    metrics: dict[str, float] = {}
    for field, metric_name in _SLB_CMS_METRICS.items():
        metrics[field] = _fetch_cms_metric(metric_name, namespace, instance_id)
    return metrics


def _fetch_oss_bucket_stat(bucket_name: str) -> dict[str, float]:
    """Fetch OSS bucket storage size via ossutil. Returns {"disk_gb": N} or {"disk_gb": 0}."""
    cmd = f"ossutil stat oss://{bucket_name} --format json"
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            logger.debug("ossutil stat for %s failed: %s", bucket_name, result.stderr)
            return {"disk_gb": 0.0}
        data = json.loads(result.stdout)
        storage = float(data.get("Storage", 0)) / (1024 ** 3)
        return {"disk_gb": round(storage, 2)}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError, Exception) as e:
        logger.debug("ossutil stat for %s failed: %s", bucket_name, e)
        return {"disk_gb": 0.0}


def collect_slb_resources(region: str) -> list[Resource]:
    """Collect SLB instances from a region."""
    cmd = f"aliyun slb DescribeLoadBalancers --RegionId {region} --output json"
    data = cli_call(cmd) or {}
    return [_parse_slb(i) for i in data.get("LoadBalancers", {}).get("LoadBalancer", [])]


def collect_oss_buckets(region: str) -> list[Resource]:
    """Collect OSS buckets (region-filtered)."""
    cmd = f"aliyun oss ls --region {region}"
    result = cli_call(cmd, parse_json=False)
    if result is None:
        return []
    return [_parse_oss_line(line) for line in result.splitlines() if line.strip().startswith("oss://")]


def _parse_oss_line(line: str) -> Resource:
    """Parse a single oss ls output line."""
    parts = line.split()
    bucket_name = parts[0].replace("oss://", "") if parts else ""
    stat = _fetch_oss_bucket_stat(bucket_name)
    disk_gb = stat.get("disk_gb", 0.0)

    return Resource(
        resource_id=bucket_name,
        resource_type="oss",
        instance_name=bucket_name,
        instance_type="bucket",
        product="unknown",
        env="unknown",
        owner="unknown",
        cpu_cores=0,
        memory_gb=0.0,
        disk_gb=disk_gb,
        cpu_util_avg=0.0,
        mem_util_avg=0.0,
        disk_util_avg=0.0,
        iops_util_avg=0.0,
        net_in_avg=0.0,
        net_out_avg=0.0,
        monthly_cost=estimate_monthly_cost("oss", "", 0, 0.0, disk_gb, False),
        is_prepaid=0,
        days_until_expire=0,
    )


def collect_k8s_nodes(region: str) -> list[Resource]:
    """Collect ACK cluster nodes."""
    cmd = f"aliyun cs DescribeClusters --RegionId {region} --output json"
    data = cli_call(cmd) or {}
    # CS API may return a list (aliyun CLI v3) or dict with "clusters" key
    if isinstance(data, list):
        clusters = data
    else:
        clusters = data.get("clusters", [])
    nodes = []
    for cluster in clusters:
        cid = cluster.get("cluster_id")
        if cid:
            nodes.extend(_fetch_cluster_nodes(region, cid))
    return nodes


def _fetch_cluster_nodes(region: str, cluster_id: str) -> list[Resource]:
    cmd = f"aliyun cs DescribeClusterNodes --RegionId {region} --ClusterId {cluster_id} --output json"
    data = cli_call(cmd) or {}
    return [_parse_k8s_node(n) for n in data.get("nodes", [])]


def _parse_slb(inst: dict[str, Any]) -> Resource:
    instance_id = inst.get("LoadBalancerId", "")
    instance_type = inst.get("AddressType", "")
    cms_metrics = _fetch_slb_metrics(instance_id)

    return Resource(
        resource_id=instance_id,
        resource_type="slb",
        instance_name=inst.get("LoadBalancerName", ""),
        instance_type=instance_type,
        product="unknown",
        env="unknown",
        owner="unknown",
        cpu_cores=0,
        memory_gb=0.0,
        disk_gb=0.0,
        cpu_util_avg=0.0,
        mem_util_avg=0.0,
        disk_util_avg=0.0,
        iops_util_avg=0.0,
        net_in_avg=cms_metrics.get("net_in_avg", 0.0),
        net_out_avg=cms_metrics.get("net_out_avg", 0.0),
        monthly_cost=estimate_monthly_cost("slb", instance_type, 0, 0.0, 0.0, False),
        is_prepaid=0,
        days_until_expire=0,
    )


def _parse_oss(bucket: dict[str, Any]) -> Resource:
    return Resource(
        resource_id=bucket.get("Name", ""),
        resource_type="oss",
        instance_name=bucket.get("Name", ""),
        instance_type="bucket",
        product="unknown",
        env="unknown",
        owner="unknown",
        cpu_cores=0,
        memory_gb=0.0,
        disk_gb=0.0,
        cpu_util_avg=0.0,
        mem_util_avg=0.0,
        disk_util_avg=0.0,
        iops_util_avg=0.0,
        net_in_avg=0.0,
        net_out_avg=0.0,
        monthly_cost=0.0,
        is_prepaid=0,
        days_until_expire=0,
    )


def _parse_k8s_node(node: dict[str, Any]) -> Resource:
    cpu_cores = int(node.get("cpu", 0))
    memory_gb = float(node.get("memory", 0)) / 1024 / 1024 / 1024
    disk_gb = float(node.get("disk", 0)) / 1024 / 1024 / 1024

    return Resource(
        resource_id=node.get("node_id", ""),
        resource_type="k8s_node",
        instance_name=node.get("name", ""),
        instance_type=node.get("instance_type", ""),
        product="unknown",
        env="unknown",
        owner="unknown",
        cpu_cores=cpu_cores,
        memory_gb=memory_gb,
        disk_gb=disk_gb,
        cpu_util_avg=0.0,
        mem_util_avg=0.0,
        disk_util_avg=0.0,
        iops_util_avg=0.0,
        net_in_avg=0.0,
        net_out_avg=0.0,
        monthly_cost=estimate_monthly_cost("k8s_node", "", cpu_cores, memory_gb, disk_gb, False),
        is_prepaid=0,
        days_until_expire=0,
    )
