"""RDS and Redis resource collector."""
from __future__ import annotations

import logging
from typing import Any

from resource_model import Resource
from cli_utils import cli_call
from cost_model import estimate_monthly_cost, compute_days_until_expire
from cms_client import fetch_metrics_parallel

logger = logging.getLogger(__name__)

# RDS uses acs_rds_dashboard with dbInstanceId dimension
_RDS_CMS_METRICS = {
    "cpu_util_avg": "CpuUsage",
    "mem_util_avg": "MemoryUsage",
    "disk_util_avg": "DiskUsage",
    "iops_util_avg": "IOPSUsage",
    "net_in_avg": "Total_NetworkIn",
    "net_out_avg": "Total_NetworkOut",
}

# Redis/Tair uses acs_kvstore (no _dashboard suffix)
_REDIS_CMS_METRICS = {
    "cpu_util_avg": "CpuUsage",
    "mem_util_avg": "MemoryUsage",
    "connection_util_avg": "ConnectionUsage",
    "net_in_avg": "IntranetIn",
    "net_out_avg": "IntranetOut",
}


def _fetch_rds_metrics(instance_id: str) -> dict[str, float]:
    """Fetch all CMS metrics for an RDS instance in parallel."""
    namespace = "acs_rds_dashboard"
    tasks = [
        (metric_name, namespace, instance_id, 7, "dbInstanceId")
        for metric_name in _RDS_CMS_METRICS.values()
    ]
    results = fetch_metrics_parallel(tasks, max_workers=len(tasks))
    return {
        field: results.get((metric_name, namespace), 0.0)
        for field, metric_name in _RDS_CMS_METRICS.items()
    }


def _fetch_redis_metrics(instance_id: str) -> dict[str, float]:
    """Fetch all CMS metrics for a Redis/Tair instance in parallel."""
    namespace = "acs_kvstore"
    tasks = [
        (metric_name, namespace, instance_id, 7, "instanceId")
        for metric_name in _REDIS_CMS_METRICS.values()
    ]
    results = fetch_metrics_parallel(tasks, max_workers=len(tasks))
    return {
        field: results.get((metric_name, namespace), 0.0)
        for field, metric_name in _REDIS_CMS_METRICS.items()
    }


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
        monthly_cost=estimate_monthly_cost(
            "rds", "", cpu_cores, memory_gb, disk_gb, is_prepaid,
        ),
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
        monthly_cost=estimate_monthly_cost(
            "redis", "", 0, cap_float, 0, is_prepaid,
        ),
        is_prepaid=1 if is_prepaid else 0,
        days_until_expire=compute_days_until_expire(inst.get("EndTime")),
    )