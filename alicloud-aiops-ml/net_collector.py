"""SLB, OSS, and K8s resource collector."""
from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from resource_model import Resource
from cli_utils import cli_call
from cost_model import estimate_monthly_cost, compute_days_until_expire
from cms_client import fetch_metrics_parallel

logger = logging.getLogger(__name__)

# SLB: instanceActiveConnection for QPS-like, traffic for throughput
_SLB_CMS_METRICS = {
    "active_conn": "InstanceActiveConnection",
    "net_in_avg": "TrafficRXNew",
    "net_out_avg": "TrafficTXNew",
}


def _fetch_slb_metrics(instance_id: str) -> dict[str, float]:
    """Fetch all CMS metrics for an SLB instance in parallel."""
    namespace = "acs_slb_dashboard"
    tasks = [
        (metric_name, namespace, instance_id, 7, "instanceId")
        for metric_name in _SLB_CMS_METRICS.values()
    ]
    results = fetch_metrics_parallel(tasks, max_workers=len(tasks))
    return {
        field: results.get((metric_name, namespace), 0.0)
        for field, metric_name in _SLB_CMS_METRICS.items()
    }


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


def _parse_k8s_node(node: dict[str, Any]) -> Resource:
    cpu_cores = int(node.get("cpu", 0))
    # Memory in KiB → GiB: divide by 1024^2
    memory_gb = float(node.get("memory", 0)) / (1024 * 1024)
    disk_gb = float(node.get("disk", 0)) / (1024 * 1024)

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