"""Tests + benchmark for vectorized DBSCAN (P0-#3)."""
from __future__ import annotations

import time

import numpy as np
import pytest
from resource_model import Resource
from feature_engine import extract_features
from dbscan_cluster import cluster_resources, _pairwise_distances, _vectorized_dbscan


def make_r(i: int, cost: float, cpu: int) -> Resource:
    return Resource(
        resource_id=f"r-{i}", resource_type="ecs", instance_name=f"x{i}",
        instance_type="t", product="p", env="e", owner="o",
        cpu_cores=cpu, memory_gb=8.0, disk_gb=40.0,
        cpu_util_avg=0.0, mem_util_avg=0.0, disk_util_avg=0.0,
        iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
        monthly_cost=cost, is_prepaid=0, days_until_expire=0,
    )


# ─── Behavioral tests ───────────────────────────────────────────────────

def test_vectorized_dbscan_produces_valid_labels() -> None:
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
    resources = [make_r(i, cost=100.0, cpu=4) for i in range(5)]
    feats = extract_features(resources)
    result = cluster_resources(resources, feats, eps=2.0)
    labels = [r["cluster_id"] for r in result]
    non_noise = [l for l in labels if l >= 0]
    assert len(non_noise) >= 3, f"Got labels={labels}"


def test_vectorized_dbscan_two_well_separated_clusters() -> None:
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


# ─── Distance matrix correctness (H2 fix) ───────────────────────────────

def test_pairwise_distances_matches_naive_implementation() -> None:
    """_pairwise_distances must produce same matrix as naive O(n^2) loop.

    Critical: identity-trick refactor must preserve numerical correctness.
    """
    np.random.seed(0)
    n = 50
    d = 3
    X = np.random.randn(n, d)

    actual = _pairwise_distances(X)

    naive = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            naive[i, j] = np.linalg.norm(X[i] - X[j])

    np.testing.assert_allclose(actual, naive, atol=1e-10)


def test_pairwise_distances_diagonal_is_zero() -> None:
    np.random.seed(1)
    X = np.random.randn(10, 3)
    actual = _pairwise_distances(X)
    np.testing.assert_allclose(np.diag(actual), 0.0, atol=1e-10)


def test_pairwise_distances_symmetric() -> None:
    np.random.seed(2)
    X = np.random.randn(10, 3)
    actual = _pairwise_distances(X)
    np.testing.assert_allclose(actual, actual.T, atol=1e-10)


# ─── Performance regression guard (H2: smaller peak memory) ────────────

def test_vectorized_dbscan_scales_sub_linearly_in_python_loop() -> None:
    """n=500 should complete in <2s (sanity bound, not strict)."""
    np.random.seed(0)
    n = 500
    resources = [
        make_r(i, cost=100.0 + np.random.randn() * 50, cpu=4 + i % 16)
        for i in range(n)
    ]
    feats = extract_features(resources)

    start = time.perf_counter()
    cluster_resources(resources, feats)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"n={n} took {elapsed:.2f}s; expected <2s"