"""Shared CMS metric fetching helpers.

Centralizes the subprocess + JSON parsing logic so that ECS, RDS, Redis, SLB,
and other collectors all use the same battle-tested implementation.

Key differences between products:
- Most use namespace `acs_<product>_dashboard` with `instanceId` dimension
- RDS uses `acs_rds_dashboard` namespace with `dbInstanceId` dimension
- Redis/Tair uses `acs_kvstore` (no `_dashboard` suffix) namespace with `instanceId`

For SLB and other multi-port/multi-protocol metrics, datapoints have multiple
entries per timestamp (one per port+protocol). The parser groups by timestamp
and sums before averaging, giving total throughput per timestamp.
"""
from __future__ import annotations

import json
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)


def fetch_cms_metric(
    metric_name: str,
    namespace: str,
    instance_id: str,
    days: int = 7,
    dimension_key: str = "instanceId",
    timeout: int = 30,
) -> float:
    """Fetch a single CMS metric average over `days` days.

    Returns 0.0 on any failure (network, parse, missing data).

    Args:
        metric_name: CMS MetricName (e.g. "CPUUtilization", "CpuUsage")
        namespace: CMS Namespace (e.g. "acs_ecs_dashboard")
        instance_id: Resource ID
        days: Number of days back from now to query
        dimension_key: Dimension key — defaults to "instanceId", RDS uses "dbInstanceId"
        timeout: Subprocess timeout in seconds
    """
    start = (
        f"$(date -u -d '{days} days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null "
        f"|| date -u -v-{days}d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
    )
    end = "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
    dimensions = f'[{{"{dimension_key}":"{instance_id}"}}]'
    cmd = (
        f"aliyun cms DescribeMetricList"
        f" --MetricName {metric_name}"
        f" --Namespace {namespace}"
        f" --Dimensions '{dimensions}'"
        f" --StartTime {start}"
        f" --EndTime {end}"
        f" --Period 86400"
    )
    try:
        result = subprocess.run(
            cmd.replace(" --output json", ""),  # aliyun CLI v3 compat
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logger.debug("CMS %s/%s for %s returned non-zero: %s",
                          namespace, metric_name, instance_id, result.stderr)
            return 0.0
        data = json.loads(result.stdout)
        return _parse_cms_datapoints(data)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        logger.debug("CMS fetch for %s/%s failed: %s", namespace, metric_name, e)
        return 0.0


def _parse_cms_datapoints(data: dict[str, Any]) -> float:
    """Parse CMS DescribeMetricList response and return average value.

    Returns 0.0 if no valid data.

    For SLB and other multi-port/multi-protocol metrics, datapoints have
    multiple entries per timestamp. We sum across ports per timestamp, then
    average across timestamps — giving total throughput per timestamp.
    """
    dps = data.get("Datapoints", "")
    if not dps:
        return 0.0

    # Datapoints can be a JSON string or already-parsed list
    if isinstance(dps, str):
        try:
            dps = json.loads(dps)
        except (json.JSONDecodeError, TypeError):
            return 0.0

    # Group by timestamp (handles multi-port/multi-protocol datapoints)
    if isinstance(dps, list):
        per_timestamp: dict[int, float] = {}
        for dp in dps:
            if isinstance(dp, dict):
                avg = dp.get("Average")
                ts = dp.get("timestamp")
                if avg is None or ts is None:
                    continue
                try:
                    per_timestamp[ts] = per_timestamp.get(ts, 0.0) + float(avg)
                except (ValueError, TypeError):
                    pass
        if not per_timestamp:
            return 0.0
        return sum(per_timestamp.values()) / len(per_timestamp)

    # Dict-type fallback (rare)
    if isinstance(dps, dict):
        values: list[float] = []
        for v in dps.values():
            try:
                values.append(float(v))
            except (ValueError, TypeError):
                pass
        if not values:
            return 0.0
        return sum(values) / len(values)

    return 0.0


def fetch_metrics_parallel(
    tasks: list[tuple[str, str, str, int, str]],
    max_workers: int = 10,
) -> dict[tuple[str, str], float]:
    """Fetch multiple CMS metrics in parallel using ThreadPoolExecutor.

    Args:
        tasks: List of (metric_name, namespace, instance_id, days, dimension_key) tuples
        max_workers: ThreadPoolExecutor max_workers

    Returns:
        Dict keyed by (metric_name, namespace) -> average value
    """
    results: dict[tuple[str, str], float] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_key = {
            executor.submit(
                fetch_cms_metric,
                metric_name, namespace, instance_id, days, dimension_key,
            ): (metric_name, namespace)
            for metric_name, namespace, instance_id, days, dimension_key in tasks
        }
        for future in future_to_key:
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception as e:
                logger.debug("Parallel CMS fetch failed for %s: %s", key, e)
                results[key] = 0.0
    return results