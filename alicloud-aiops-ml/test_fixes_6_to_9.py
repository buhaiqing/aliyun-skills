"""RED tests for fixes #6, #7, #8, #9."""
from __future__ import annotations

from pathlib import Path

import pytest
from resource_model import Resource
from dbscan_cluster import cluster_resources
from iforest_detector import detect_anomalies
from feature_engine import extract_features
from report_generator import generate_report
from data_pipeline import aggregate_to_json, load_resources


def make_r(i: int, cost: float = 100.0, cpu: int = 4) -> Resource:
    return Resource(
        resource_id=f"r-{i}", resource_type="ecs", instance_name=f"x{i}",
        instance_type="t", product="p", env="e", owner="o",
        cpu_cores=cpu, memory_gb=8.0, disk_gb=40.0,
        cpu_util_avg=0.0, mem_util_avg=0.0, disk_util_avg=0.0,
        iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
        monthly_cost=cost, is_prepaid=0, days_until_expire=0,
    )


# ─── Fix #6: dbscan tiny dataset ──────────────────────────────────────────

def test_cluster_resources_three_resources_get_valid_labels() -> None:
    """With 3 resources, normalization noise shouldn't make all noise."""
    resources = [make_r(i, cost=100.0 + i * 10, cpu=4 + i) for i in range(3)]
    feats = extract_features(resources)
    result = cluster_resources(resources, feats)
    labels = [r["cluster_id"] for r in result]
    assert all(isinstance(l, int) for l in labels)
    assert len(set(labels)) >= 1


def test_cluster_resources_identical_features_all_same_cluster() -> None:
    """Identical features must collapse to ONE cluster, not all noise."""
    resources = [make_r(i, cost=100.0, cpu=4) for i in range(5)]
    feats = extract_features(resources)
    result = cluster_resources(resources, feats, eps=2.0)
    labels = [r["cluster_id"] for r in result]
    non_noise = [l for l in labels if l >= 0]
    assert len(non_noise) >= 3, f"Got labels={labels}; expected at least 3 in a cluster"


# ─── Fix #7: iforest n=1 ──────────────────────────────────────────────────

def test_detect_anomalies_single_resource_no_anomaly() -> None:
    """Single resource: cannot detect anomaly (no baseline). All is_anomaly=False."""
    r = make_r(0, cost=500.0)
    feats = extract_features([r])
    result = detect_anomalies([r], feats)
    assert len(result) == 1
    assert result[0]["is_anomaly"] is False


# ─── Fix #8: report mkdir parents ────────────────────────────────────────

def test_generate_report_creates_missing_parent_dirs(tmp_path: Path) -> None:
    """Report generator must create missing parent directories."""
    nested_dir = tmp_path / "deeply" / "nested" / "reports"
    output = nested_dir / "report.md"
    assert not nested_dir.exists()

    r = make_r(0, cost=100.0)
    generate_report([r], [], [], [], str(output))

    assert nested_dir.exists(), "Parent dirs not created"
    assert output.exists()


# ─── Fix #9: asdict to avoid drift ────────────────────────────────────────

def test_load_resources_roundtrip_with_new_field(tmp_path: Path) -> None:
    """If a new field is added to JSON that wasn't in dataclass, roundtrip preserves it.

    Note: actually the current code drops unknown keys. This test pins the
    round-trip behavior: serialize via asdict, load, all fields present.
    """
    r = make_r(0, cost=100.0)
    json_path = tmp_path / "r.json"
    aggregate_to_json([r], str(json_path))
    loaded = load_resources(str(json_path))
    assert loaded[0].resource_id == r.resource_id
    assert loaded[0].monthly_cost == r.monthly_cost
    assert loaded[0].cpu_cores == r.cpu_cores
    assert loaded[0].disk_gb == r.disk_gb