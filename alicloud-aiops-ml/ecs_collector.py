"""ECS resource collector."""
from __future__ import annotations

import logging
from typing import Any

from resource_model import Resource
from cli_utils import cli_call
from cost_model import estimate_monthly_cost, compute_days_until_expire
from cms_client import fetch_cms_metric, fetch_metrics_parallel

logger = logging.getLogger(__name__)

# CMS metric names and their Resource field names.
_CMS_METRICS = {
    "cpu_util_avg": "CPUUtilization",
    "mem_util_avg": "MemoryUtilization",
    "disk_util_avg": "DiskUtilization",
    "iops_util_avg": "DiskReadIOPS",
    "net_in_avg": "InternetInRate",
    "net_out_avg": "InternetOutRate",
}


def _fetch_ecs_metrics(instance_id: str, region: str, days: int = 7) -> dict[str, float]:
    """Fetch all CMS metrics for an ECS instance in parallel.

    Uses ThreadPoolExecutor to issue concurrent CMS calls (one per metric).
    """
    namespace = "acs_ecs_dashboard"
    tasks = [
        (metric_name, namespace, instance_id, days, "instanceId")
        for metric_name in _CMS_METRICS.values()
    ]
    results = fetch_metrics_parallel(tasks, max_workers=len(tasks))
    # Map results back to resource field names
    return {
        field: results.get((metric_name, namespace), 0.0)
        for field, metric_name in _CMS_METRICS.items()
    }


def collect_ecs_resources(region: str) -> list[Resource]:
    """Collect ECS instances from a region."""
    cmd = f"aliyun ecs DescribeInstances --RegionId {region} --output json"
    data = cli_call(cmd) or {}
    instances = data.get("Instances", {}).get("Instance", [])
    return [_parse_instance(i, region) for i in instances]


def _parse_instance(inst: dict[str, Any], region: str) -> Resource:
    """Parse a single ECS instance into Resource."""
    instance_id = inst.get("InstanceId", "")
    instance_type = inst.get("InstanceType", "")
    cpu_cores = int(inst.get("Cpu", 0))
    memory_gb = float(inst.get("Memory", 0)) / 1024
    disk_gb = _sum_disk(inst)
    is_prepaid = inst.get("InstanceChargeType") == "PrePaid"

    # CMS metrics — graceful degradation
    cms_metrics = _fetch_ecs_metrics(instance_id, region)

    return Resource(
        resource_id=instance_id,
        resource_type="ecs",
        instance_name=inst.get("InstanceName", ""),
        instance_type=instance_type,
        product=_get_tag(inst, "product"),
        env=_get_tag(inst, "env"),
        owner=_get_tag(inst, "owner"),
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
            "ecs", instance_type, cpu_cores, memory_gb, disk_gb, is_prepaid,
        ),
        is_prepaid=1 if is_prepaid else 0,
        days_until_expire=compute_days_until_expire(inst.get("ExpiredTime")),
    )


def _get_tag(instance: dict[str, Any], key: str) -> str:
    for tag in instance.get("Tags", {}).get("Tag", []):
        if tag.get("Key") == key:
            return tag.get("Value", "unknown")
    return "unknown"


def _sum_disk(instance: dict[str, Any]) -> float:
    total = 0.0
    for disk in instance.get("Disks", {}).get("Disk", []):
        try:
            total += float(str(disk.get("Size", 0)).replace("GiB", "").strip())
        except (ValueError, TypeError):
            pass
    return total
