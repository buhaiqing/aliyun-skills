"""Simplified cost estimation and expiration utilities for Alibaba Cloud resources."""
from __future__ import annotations

import datetime
import logging
import math

logger = logging.getLogger(__name__)

# Monthly instance-type prices (CNY). These are approximate list prices.
# Real prices depend on region, billing type, and discounts — use the billing
# API for exact values.  This table serves as a reasonable fallback.
PRICE_MAP: dict[str, float] = {
    # ECS general-purpose g9i
    "ecs.g9i.large": 250.0,
    "ecs.g9i.xlarge": 500.0,
    "ecs.g9i.2xlarge": 1000.0,
    "ecs.g9i.4xlarge": 2000.0,
    "ecs.g9i.8xlarge": 4000.0,
    "ecs.g9i.16xlarge": 8000.0,
    # ECS general-purpose g8i
    "ecs.g8i.large": 240.0,
    "ecs.g8i.xlarge": 480.0,
    "ecs.g8i.2xlarge": 960.0,
    "ecs.g8i.4xlarge": 1920.0,
    "ecs.g8i.8xlarge": 3840.0,
    "ecs.g8i.16xlarge": 7680.0,
    # ECS compute-optimised c8i
    "ecs.c8i.large": 280.0,
    "ecs.c8i.xlarge": 560.0,
    "ecs.c8i.2xlarge": 1120.0,
    "ecs.c8i.4xlarge": 2240.0,
    "ecs.c8i.8xlarge": 4480.0,
    # ECS memory-optimised r8i
    "ecs.r8i.large": 350.0,
    "ecs.r8i.xlarge": 700.0,
    "ecs.r8i.2xlarge": 1400.0,
    "ecs.r8i.4xlarge": 2800.0,
    "ecs.r8i.8xlarge": 5600.0,
    # SLB
    "internet": 100.0,
    "intranet": 0.0,
    # K8s (ACK managed cluster base fee, nodes priced separately)
    "ack.standard": 900.0,
    "ack.pro": 2800.0,
}


def _parse_date_safe(date_str: str) -> datetime.datetime | None:
    """Parse a date string with fallback formats."""
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%MZ",       # e.g. 2029-03-31T16:00Z
        "%Y-%m-%dT%H:%M:%S+08:00",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def compute_days_until_expire(expired_time_str: str | None) -> int:
    """Return days remaining until the resource expires.

    Returns 0 if expired_time_str is None, empty, or already expired.
    Returns a large sentinel (36500) for pay-as-you-go (no expiration).
    """
    if not expired_time_str or not expired_time_str.strip():
        return 0
    expiry = _parse_date_safe(expired_time_str)
    if expiry is None:
        logger.warning("Could not parse expiration date: %s", expired_time_str)
        return 0
    delta = (expiry - datetime.datetime.now()).days
    return max(0, delta)


def estimate_monthly_cost(
    resource_type: str,
    instance_type: str,
    cpu_cores: int,
    memory_gb: float,
    disk_gb: float,
    is_prepaid: bool,
) -> float:
    """Estimate monthly cost (CNY) for a cloud resource.

    Uses PRICE_MAP for known instance types, falls back to a heuristic
    based on CPU cores and memory.

    Args:
        resource_type: One of "ecs", "rds", "redis", "slb", "oss", "k8s_node".
        instance_type: The aliyun instance type string (e.g. "ecs.g9i.2xlarge").
        cpu_cores: Number of vCPUs.
        memory_gb: Memory in GiB.
        disk_gb: Disk/storage in GiB.
        is_prepaid: True for subscription (PrePaid), False for pay-as-you-go.

    Returns:
        Estimated monthly cost in CNY.
    """
    rtype = resource_type.lower()

    if rtype == "ecs":
        return _estimate_ecs(instance_type, cpu_cores, memory_gb, disk_gb, is_prepaid)
    if rtype in ("rds", "rds_mysql", "rds_postgresql"):
        return _estimate_rds(cpu_cores, memory_gb, disk_gb, is_prepaid)
    if rtype == "redis":
        return _estimate_redis(memory_gb, is_prepaid)
    if rtype == "slb":
        return _estimate_slb(instance_type)
    if rtype == "oss":
        return disk_gb * 0.12
    if rtype in ("k8s_node", "k8s"):
        return cpu_cores * 100.0 + memory_gb * 25.0
    return 0.0


def _estimate_ecs(
    instance_type: str,
    cpu_cores: int,
    memory_gb: float,
    disk_gb: float,
    is_prepaid: bool,
) -> float:
    if instance_type and instance_type in PRICE_MAP:
        base = PRICE_MAP[instance_type]
    else:
        base = cpu_cores * 100.0 + memory_gb * 25.0
    # Disk cost (simplified: efficient cloud disk ~0.35 CNY/GiB/month)
    disk_cost = disk_gb * 0.35
    total = base + disk_cost
    if is_prepaid:
        # Prepaid is typically ~15% cheaper than pay-as-you-go
        total *= 0.85
    return math.ceil(total * 100) / 100


def _estimate_rds(cpu_cores: int, memory_gb: float, disk_gb: float, is_prepaid: bool) -> float:
    base = cpu_cores * 200.0 + memory_gb * 50.0 + disk_gb * 1.0
    if is_prepaid:
        base *= 0.85
    return math.ceil(base * 100) / 100


def _estimate_redis(memory_gb: float, is_prepaid: bool) -> float:
    base = memory_gb * 80.0
    if is_prepaid:
        base *= 0.85
    return math.ceil(base * 100) / 100


def _estimate_slb(instance_type: str) -> float:
    """SLB cost: public (internet) ~100 CNY, private (intranet) ~0 CNY."""
    return PRICE_MAP.get(instance_type, 100.0)
