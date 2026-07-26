"""RDS and Redis resource collector."""
from __future__ import annotations

from typing import Any

from resource_model import Resource
from cli_utils import cli_call


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
    return Resource(
        resource_id=inst.get("DBInstanceId", ""),
        resource_type="rds",
        instance_name=inst.get("DBInstanceDescription", ""),
        instance_type=inst.get("DBInstanceType", ""),
        product="unknown",
        env="unknown",
        owner="unknown",
        cpu_cores=int(inst.get("DBInstanceCPU", 0)),
        memory_gb=float(inst.get("DBInstanceMemory", 0)) / 1024,
        disk_gb=float(inst.get("DBInstanceStorage", 0)),
        cpu_util_avg=0.0,
        mem_util_avg=0.0,
        disk_util_avg=0.0,
        iops_util_avg=0.0,
        net_in_avg=0.0,
        net_out_avg=0.0,
        monthly_cost=0.0,
        is_prepaid=1 if inst.get("PayType") == "Prepaid" else 0,
        days_until_expire=0,
    )


def _parse_redis(inst: dict[str, Any]) -> Resource:
    capacity = inst.get("Capacity", 0)
    try:
        cap_float = float(capacity)
    except (ValueError, TypeError):
        cap_float = 0.0
    return Resource(
        resource_id=inst.get("InstanceId", ""),
        resource_type="redis",
        instance_name=inst.get("InstanceName", ""),
        instance_type=inst.get("InstanceType", ""),
        product="unknown",
        env="unknown",
        owner="unknown",
        cpu_cores=0,
        memory_gb=cap_float,
        disk_gb=0.0,
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
