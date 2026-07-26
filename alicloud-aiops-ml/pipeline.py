"""Unified collection pipeline with concurrent execution.

Provides a single entry point to collect resources across all products in
a region, parallelized via ThreadPoolExecutor (subprocess-bound I/O).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from ecs_collector import collect_ecs_resources
from db_collector import collect_rds_resources, collect_redis_resources
from net_collector import collect_slb_resources, collect_oss_buckets, collect_k8s_nodes
from resource_model import Resource


DEFAULT_MAX_WORKERS = 6


def collect_all(
    region: str,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> dict[str, list[Resource]]:
    """Collect resources from all products in `region` concurrently.

    Returns dict keyed by product: {"ecs": [...], "rds": [...], ...}.
    Failed collectors are omitted from the result (caller should check keys).

    Threading (not multiprocessing) is used because the bottleneck is
    subprocess.wait() I/O, not CPU. ThreadPoolExecutor releases the GIL
    during blocking I/O.
    """
    collectors: dict[str, Callable[[str], list[Resource]]] = {
        "ecs": collect_ecs_resources,
        "rds": collect_rds_resources,
        "redis": collect_redis_resources,
        "slb": collect_slb_resources,
        "oss": collect_oss_buckets,
        "k8s": collect_k8s_nodes,
    }

    results: dict[str, list[Resource]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_name = {
            executor.submit(fn, region): name
            for name, fn in collectors.items()
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results[name] = future.result()
            except Exception:
                results[name] = []

    return results


def collect_all_flat(
    region: str,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> list[Resource]:
    """Collect from all products and return as a single flat list."""
    grouped = collect_all(region, max_workers=max_workers)
    flat: list[Resource] = []
    for resources in grouped.values():
        flat.extend(resources)
    return flat