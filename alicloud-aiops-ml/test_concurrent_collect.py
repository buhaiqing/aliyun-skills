"""RED tests for P0-#2 concurrent collection."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from resource_model import Resource
from pipeline import collect_all


def _stub_collectors(sleep_seconds: float = 0.05):
    """Build mock collectors each taking `sleep_seconds` to simulate API latency."""
    def make_collect(n: int, rtype: str):
        def _collect(region: str) -> list[Resource]:
            time.sleep(sleep_seconds)
            return [
                Resource(
                    resource_id=f"{rtype}-{i}", resource_type=rtype,
                    instance_name=f"{rtype}-{i}", instance_type="t",
                    product="p", env="e", owner="o",
                    cpu_cores=4, memory_gb=8.0, disk_gb=40.0,
                    cpu_util_avg=0.0, mem_util_avg=0.0, disk_util_avg=0.0,
                    iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
                    monthly_cost=100.0, is_prepaid=0, days_until_expire=0,
                )
                for i in range(n)
            ]
        return _collect
    return {
        "ecs": make_collect(3, "ecs"),
        "rds": make_collect(2, "rds"),
        "redis": make_collect(2, "redis"),
        "slb": make_collect(1, "slb"),
        "oss": make_collect(1, "oss"),
        "k8s": make_collect(2, "k8s_node"),
    }


def test_collect_all_returns_all_products() -> None:
    collectors = _stub_collectors()
    with patch.multiple(
        "pipeline",
        collect_ecs_resources=collectors["ecs"],
        collect_rds_resources=collectors["rds"],
        collect_redis_resources=collectors["redis"],
        collect_slb_resources=collectors["slb"],
        collect_oss_buckets=collectors["oss"],
        collect_k8s_nodes=collectors["k8s"],
    ):
        result = collect_all("cn-hangzhou", max_workers=6)

    assert len(result["ecs"]) == 3
    assert len(result["rds"]) == 2
    assert len(result["redis"]) == 2
    assert len(result["slb"]) == 1
    assert len(result["oss"]) == 1
    assert len(result["k8s"]) == 2


def test_collect_all_concurrent_faster_than_serial() -> None:
    """6 collectors × 0.1s = serial 0.6s; concurrent should be ~0.1-0.2s."""
    collectors = _stub_collectors(sleep_seconds=0.1)
    with patch.multiple(
        "pipeline",
        collect_ecs_resources=collectors["ecs"],
        collect_rds_resources=collectors["rds"],
        collect_redis_resources=collectors["redis"],
        collect_slb_resources=collectors["slb"],
        collect_oss_buckets=collectors["oss"],
        collect_k8s_nodes=collectors["k8s"],
    ):
        start = time.perf_counter()
        result = collect_all("cn-hangzhou", max_workers=6)
        concurrent_elapsed = time.perf_counter() - start

    total_resources = sum(len(v) for v in result.values())
    assert total_resources == 11
    assert concurrent_elapsed < 0.4, (
        f"Concurrent took {concurrent_elapsed:.2f}s; expected < 0.4s (6x0.1s = 0.6s serial)"
    )


def test_collect_all_respects_max_workers() -> None:
    """max_workers=1 falls back to serial."""
    collectors = _stub_collectors(sleep_seconds=0.05)
    with patch.multiple(
        "pipeline",
        collect_ecs_resources=collectors["ecs"],
        collect_rds_resources=collectors["rds"],
        collect_redis_resources=collectors["redis"],
        collect_slb_resources=collectors["slb"],
        collect_oss_buckets=collectors["oss"],
        collect_k8s_nodes=collectors["k8s"],
    ):
        result = collect_all("cn-hangzhou", max_workers=1)
    assert sum(len(v) for v in result.values()) == 11


def test_collect_all_partial_failure_does_not_crash() -> None:
    """If one collector raises, others still complete; failed one returns empty list."""
    collectors = _stub_collectors()

    def failing_collect(region: str) -> list[Resource]:
        raise RuntimeError("simulated API error")

    with patch.multiple(
        "pipeline",
        collect_ecs_resources=collectors["ecs"],
        collect_rds_resources=collectors["rds"],
        collect_redis_resources=collectors["redis"],
        collect_slb_resources=collectors["slb"],
        collect_oss_buckets=collectors["oss"],
        collect_k8s_nodes=failing_collect,
    ):
        result = collect_all("cn-hangzhou", max_workers=6)

    assert result["k8s"] == []
    assert len(result["ecs"]) == 3


def test_collect_all_default_max_workers() -> None:
    """Default max_workers must be sensible (>= 4, <= 10)."""
    from pipeline import DEFAULT_MAX_WORKERS
    assert 4 <= DEFAULT_MAX_WORKERS <= 10


# ─── M1: failed collectors must LOG, not silently swallow ───────────────

def test_collect_all_logs_failed_collectors(caplog) -> None:
    """Failed collectors must emit a warning log, not silently return []."""
    import logging
    collectors = _stub_collectors()

    def failing_collect(region: str) -> list[Resource]:
        raise RuntimeError("simulated API error: network timeout")

    with caplog.at_level(logging.WARNING, logger="pipeline"), patch.multiple(
        "pipeline",
        collect_ecs_resources=collectors["ecs"],
        collect_rds_resources=failing_collect,
        collect_redis_resources=collectors["redis"],
        collect_slb_resources=collectors["slb"],
        collect_oss_buckets=collectors["oss"],
        collect_k8s_nodes=collectors["k8s"],
    ):
        collect_all("cn-hangzhou", max_workers=6)

    assert any("rds" in record.message for record in caplog.records), \
        f"Expected warning log for 'rds' failure; got {[r.message for r in caplog.records]}"


def test_collect_all_does_not_swallow_keyboard_interrupt() -> None:
    """KeyboardInterrupt and SystemExit must NOT be swallowed."""
    collectors = _stub_collectors()

    def interrupt_collect(region: str) -> list[Resource]:
        raise KeyboardInterrupt()

    with patch.multiple(
        "pipeline",
        collect_ecs_resources=collectors["ecs"],
        collect_rds_resources=interrupt_collect,
        collect_redis_resources=collectors["redis"],
        collect_slb_resources=collectors["slb"],
        collect_oss_buckets=collectors["oss"],
        collect_k8s_nodes=collectors["k8s"],
    ):
        with pytest.raises(KeyboardInterrupt):
            collect_all("cn-hangzhou", max_workers=6)


# ─── M2: if ALL collectors fail, raise aggregate error ───────────────────

def test_collect_all_raises_if_all_collectors_fail() -> None:
    """If every collector raises, surface a single aggregate RuntimeError."""
    collectors = _stub_collectors()

    def all_fail(region: str) -> list[Resource]:
        raise RuntimeError(f"fail for {region}")

    with patch.multiple(
        "pipeline",
        collect_ecs_resources=all_fail,
        collect_rds_resources=all_fail,
        collect_redis_resources=all_fail,
        collect_slb_resources=all_fail,
        collect_oss_buckets=all_fail,
        collect_k8s_nodes=all_fail,
    ):
        with pytest.raises(RuntimeError, match="[Aa]ll.*collectors failed|0/6"):
            collect_all("cn-hangzhou", max_workers=6)


def test_collect_all_returns_partial_results_when_some_succeed() -> None:
    """If SOME collectors fail, return partial dict (no raise)."""
    collectors = _stub_collectors()

    def fail(region: str) -> list[Resource]:
        raise RuntimeError("fail")

    with patch.multiple(
        "pipeline",
        collect_ecs_resources=collectors["ecs"],
        collect_rds_resources=fail,
        collect_redis_resources=collectors["redis"],
        collect_slb_resources=fail,
        collect_oss_buckets=collectors["oss"],
        collect_k8s_nodes=fail,
    ):
        result = collect_all("cn-hangzhou", max_workers=6)

    assert len(result["ecs"]) == 3
    assert result["rds"] == []
    assert len(result["redis"]) == 2