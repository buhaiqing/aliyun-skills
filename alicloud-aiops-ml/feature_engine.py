"""Feature engineering - extract features for ML models."""
from __future__ import annotations

from resource_model import Resource


def extract_features(resources: list[Resource]) -> list[dict[str, float]]:
    """Extract feature vectors from resources for ML models."""
    return [_extract_single(r) for r in resources]


def _extract_single(r: Resource) -> dict[str, float]:
    return {
        "cpu_cores": float(r.cpu_cores),
        "memory_gb": r.memory_gb,
        "disk_gb": r.disk_gb,
        "cpu_util_avg": r.cpu_util_avg,
        "mem_util_avg": r.mem_util_avg,
        "disk_util_avg": r.disk_util_avg,
        "iops_util_avg": r.iops_util_avg,
        "net_in_avg": r.net_in_avg,
        "net_out_avg": r.net_out_avg,
        "monthly_cost": r.monthly_cost,
        "is_prepaid": float(r.is_prepaid),
        "days_until_expire": float(r.days_until_expire),
        "cpu_mem_ratio": r.cpu_util_avg / r.mem_util_avg if r.mem_util_avg > 0 else 0.0,
        "cost_per_cpu": r.monthly_cost / r.cpu_cores if r.cpu_cores > 0 else 0.0,
        "cost_per_gb": r.monthly_cost / r.memory_gb if r.memory_gb > 0 else 0.0,
    }
