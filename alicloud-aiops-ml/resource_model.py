"""Unified resource data model for FinOps analysis."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Resource:
    """Unified resource representation across all cloud products."""

    # Identity
    resource_id: str
    resource_type: str
    instance_name: str
    instance_type: str

    # Organization (from Tag enrichment)
    product: str
    env: str
    owner: str

    # Capacity (from Describe APIs)
    cpu_cores: int
    memory_gb: float
    disk_gb: float

    # Utilization (from CMS metrics, 7-day average)
    cpu_util_avg: float
    mem_util_avg: float
    disk_util_avg: float
    iops_util_avg: float
    net_in_avg: float
    net_out_avg: float

    # Cost
    monthly_cost: float
    is_prepaid: int
    days_until_expire: int
