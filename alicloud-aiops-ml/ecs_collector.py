"""ECS resource collector."""
from __future__ import annotations

from typing import Any

from resource_model import Resource
from cli_utils import cli_call


def collect_ecs_resources(region: str) -> list[Resource]:
    """Collect ECS instances from a region."""
    cmd = f"aliyun ecs DescribeInstances --RegionId {region} --output json"
    data = cli_call(cmd) or {}
    instances = data.get("Instances", {}).get("Instance", [])
    return [_parse_instance(i) for i in instances]


def _parse_instance(inst: dict[str, Any]) -> Resource:
    """Parse a single ECS instance into Resource."""
    return Resource(
        resource_id=inst.get("InstanceId", ""),
        resource_type="ecs",
        instance_name=inst.get("InstanceName", ""),
        instance_type=inst.get("InstanceType", ""),
        product=_get_tag(inst, "product"),
        env=_get_tag(inst, "env"),
        owner=_get_tag(inst, "owner"),
        cpu_cores=int(inst.get("Cpu", 0)),
        memory_gb=float(inst.get("Memory", 0)) / 1024,
        disk_gb=_sum_disk(inst),
        cpu_util_avg=0.0,
        mem_util_avg=0.0,
        disk_util_avg=0.0,
        iops_util_avg=0.0,
        net_in_avg=0.0,
        net_out_avg=0.0,
        monthly_cost=0.0,
        is_prepaid=1 if inst.get("InstanceChargeType") == "PrePaid" else 0,
        days_until_expire=0,
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
