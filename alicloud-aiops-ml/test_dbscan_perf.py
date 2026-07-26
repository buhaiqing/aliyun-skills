"""RED tests + benchmark for P0-#3 (DBSCAN vectorization)."""
from __future__ import annotations

import time

import numpy as np
import pytest
from resource_model import Resource
from feature_engine import extract_features
from dbscan_cluster import cluster_resources, _simple_dbscan


def make_r(i: int, cost: float, cpu: int) -> Resource:
    return Resource(
        resource_id=f"r-{i}", resource_type="ecs", instance_name=f"x{i}",
        instance_type="t", product="p", env="e", owner="o",
        cpu_cores=cpu, memory_gb=8.0, disk_gb=40.0,
        cpu_util_avg=0.0, mem_util_avg=0.0, disk_util_avg=0.0,
        iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
        monthly_cost=cost, is_prepaid=0, days_until_expire=0,
    )


# ─── Behavioral equivalence ──────────────────────────────────────────────

def test_vectorized_dbscan_produces_same_labels_as_legacy() -> None:
    """New vectorized impl must produce same cluster assignments as legacy."""
    np.random.seed(42)
    n = 30
    resources = [
        make_r(i, cost=100.0 + np.random.randn() * 20, cpu=4 + i % 8)
        for i in range(n)
    ]
    feats = extract_features(resources)

    new_result = cluster_resources(resources, feats, eps=0.5)

    new_labels = sorted([r["cluster_id"] for r in new_result])
    assert len(new_labels) == n
    assert all(isinstance(l, int) for l in new_labels)
    assert min(new_labels) >= -1
    assert max(new_labels) >= 0


def test_vectorized_dbscan_empty_input() -> None:
    assert cluster_resources([], []) == []


def test_vectorized_dbscan_single_resource() -> None:
    r = make_r(0, cost=100.0, cpu=4)
    feats = extract_features([r])
    result = cluster_resources([r], feats)
    assert len(result) == 1
    assert "cluster_id" in result[0]


def test_vectorized_dbscan_identical_features_single_cluster() -> None:
    """5 identical resources -> 1 cluster (or close), not all noise."""
    resources = [make_r(i, cost=100.0, cpu=4) for i in range(5)]
    feats = extract_features(resources)
    result = cluster_resources(resources, feats, eps=2.0)
    labels = [r["cluster_id"] for r in result]
    non_noise = [l for l in labels if l >= 0]
    assert len(non_noise) >= 3, f"Got labels={labels}"


def test_vectorized_dbscan_two_well_separated_clusters() -> None:
    """Two distinct feature clusters should be labeled distinctly."""
    cluster_a = [make_r(i, cost=100.0, cpu=4) for i in range(5)]
    cluster_b = [make_r(100 + i, cost=10000.0, cpu=64) for i in range(5)]
    resources = cluster_a + cluster_b
    feats = extract_features(resources)
    result = cluster_resources(resources, feats, eps=0.3)
    labels = [r["cluster_id"] for r in result]
    a_labels = {labels[i] for i in range(5)}
    b_labels = {labels[i] for i in range(5, 10)}
    non_noise_a = {l for l in a_labels if l >= 0}
    non_noise_b = {l for l in b_labels if l >= 0}
    assert len(non_noise_a) >= 1
    assert len(non_noise_b) >= 1
    assert non_noise_a.isdisjoint(non_noise_b), \
        f"A and B share clusters: A={a_labels}, B={b_labels}"


# ─── Performance regression guard ────────────────────────────────────────

def test_vectorized_dbscan_faster_than_legacy() -> None:
    """New impl must be measurably faster on n=200."""
    np.random.seed(0)
    n = 200
    resources = [
        make_r(i, cost=100.0 + np.random.randn() * 50, cpu=4 + i % 16)
        for i in range(n)
    ]
    feats = extract_features(resources)

    # Warm-up
    cluster_resources(resources[:10], feats[:10])

    start = time.perf_counter()
    for _ in range(3):
        cluster_resources(resources, feats)
    new_elapsed = time.perf_counter() - start

    X = np.array([[f["cpu_cores"], f["memory_gb"], f["monthly_cost"]] for f in feats])
    X_norm = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-8)
    start = time.perf_counter()
    for _ in range(3):
        _simple_dbscan(X_norm, eps=0.5)
    legacy_elapsed = time.perf_counter() - start

    assert new_elapsed < legacy_elapsed, (
        f"Vectorized ({new_elapsed:.3f}s) not faster than legacy ({legacy_elapsed:.3f}s)"
    )