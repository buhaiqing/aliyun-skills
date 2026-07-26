"""RDS and Redis resource collector."""
from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from resource_model import Resource
from cli_utils import cli_call
from cost_model import estimate_monthly_cost, compute_days_until_expire

logger = logging.getLogger(__name__)

_RDS_CMS_METRICS = {
    "cpu_util_avg": "CpuUsage",
    "mem_util_avg": "MemoryUsage",
    "disk_util_avg": "DiskUsage",
    "iops_util_avg": "IOPSUsage",
    "net_in_avg": "SQLServer_NetworkInNew",
    "net_out_avg": "SQLServer_NetworkOutNew",
}

_REDIS_CMS_METRICS = {
    "cpu_util_avg": "CpuUsage",
    "mem_util_avg": "MemoryUsage",
    "net_in_avg": "IntranetIn",
    "net_out_avg": "IntranetOut",
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


def _fetch_rds_metrics(instance_id: str) -> dict[str, float]:
    namespace = "acs_rds_dashboard"
    metrics: dict[str, float] = {}
    for field, metric_name in _RDS_CMS_METRICS.items():
        metrics[field] = _fetch_cms_metric(metric_name, namespace, instance_id)
    return metrics


def _fetch_redis_metrics(instance_id: str) -> dict[str, float]:
    namespace = "acs_kvstore_dashboard"
    metrics: dict[str, float] = {}
    for field, metric_name in _REDIS_CMS_METRICS.items():
        metrics[field] = _fetch_cms_metric(metric_name, namespace, instance_id)
    return metrics


def collect_rds_resources(region: str) -> list[Resource]:
    """Collect RDS instances from a region."""
    cmd = f"aliyun rds DescribeDBInstances --RegionId {region} --output json"
    data = cli_call(cmd) or {}
    return [_parse_rds(i) for i in data.get("Items", {}).get("DBInstance", [])]


def collect_redis_resources(region: str) -> list[Resource]:
    """Collect Redis instances from a region."""
    cmd = f"aliyun r-kvstore DescribeInstances --RegionId {region} --output json"
    data = cli_call(cmd) or {}
    return [_parse_redis(i) for i in data.get("Instances", {}).get("KVStoreInstance", [])]


def _parse_rds(inst: dict[str, Any]) -> Resource:
    cpu_cores = int(inst.get("DBInstanceCPU", 0))
    memory_gb = float(inst.get("DBInstanceMemory", 0)) / 1024
    disk_gb = float(inst.get("DBInstanceStorage", 0))
    is_prepaid = inst.get("PayType") == "Prepaid"
    instance_id = inst.get("DBInstanceId", "")
    cms_metrics = _fetch_rds_metrics(instance_id)

    return Resource(
        resource_id=instance_id,
        resource_type="rds",
        instance_name=inst.get("DBInstanceDescription", ""),
        instance_type=inst.get("DBInstanceType", ""),
        product="unknown",
        env="unknown",
        owner="unknown",
        cpu_cores=cpu_cores,
        memory_gb=memory_gb,
        disk_gb=disk_gb,
        cpu_util_avg=cms_metrics.get("cpu_util_avg", 0.0),
        mem_util_avg=cms_metrics.get("mem_util_avg", 0.0),
        disk_util_avg=cms_metrics.get("disk_util_avg", 0.0),
        iops_util_avg=cms_metrics.get("iops_util_avg", 0.0),
        net_in_avg=cms_metrics.get("net_in_avg", 0.0),
        net_out_avg=cms_metrics.get("net_out_avg", 0.0),
        monthly_cost=estimate_monthly_cost("rds", "", cpu_cores, memory_gb, disk_gb, is_prepaid),
        is_prepaid=1 if is_prepaid else 0,
        days_until_expire=compute_days_until_expire(inst.get("ExpireTime")),
    )


def _parse_redis(inst: dict[str, Any]) -> Resource:
    capacity = inst.get("Capacity", 0)
    try:
        cap_float = float(capacity)
    except (ValueError, TypeError):
        cap_float = 0.0
    is_prepaid = inst.get("InstanceChargeType") == "PrePaid"
    instance_id = inst.get("InstanceId", "")
    cms_metrics = _fetch_redis_metrics(instance_id)

    return Resource(
        resource_id=instance_id,
        resource_type="redis",
        instance_name=inst.get("InstanceName", ""),
        instance_type=inst.get("InstanceType", ""),
        product="unknown",
        env="unknown",
        owner="unknown",
        cpu_cores=0,
        memory_gb=cap_float,
        disk_gb=0.0,
        cpu_util_avg=cms_metrics.get("cpu_util_avg", 0.0),
        mem_util_avg=cms_metrics.get("mem_util_avg", 0.0),
        disk_util_avg=0.0,
        iops_util_avg=0.0,
        net_in_avg=cms_metrics.get("net_in_avg", 0.0),
        net_out_avg=cms_metrics.get("net_out_avg", 0.0),
        monthly_cost=estimate_monthly_cost("redis", "", 0, cap_float, 0.0, is_prepaid),
        is_prepaid=1 if is_prepaid else 0,
        days_until_expire=compute_days_until_expire(inst.get("EndTime")),
    )
