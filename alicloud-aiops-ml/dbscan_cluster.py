"""DBSCAN-style clustering for resource grouping."""
from __future__ import annotations

from collections import deque

import numpy as np
from resource_model import Resource


def cluster_resources(resources: list[Resource], features: list[dict[str, float]], eps: float = 0.5) -> list[dict]:
    """Cluster resources using simple distance-based grouping.

    Args:
        eps: Maximum distance between samples in NORMALIZED feature space (0-1).
             Default 0.5 works well for z-score-normalized [cpu, mem, cost] features.
    """
    if not features:
        return []

    X = np.array([[f["cpu_cores"], f["memory_gb"], f["monthly_cost"]] for f in features])
    X_norm = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-8)

    labels = _vectorized_dbscan(X_norm, eps=eps)

    results = []
    for res, label in zip(resources, labels):
        results.append({
            "resource_id": res.resource_id,
            "resource_type": res.resource_type,
            "cluster_id": int(label),
        })
    return results


def _pairwise_distances(X: np.ndarray) -> np.ndarray:
    """Vectorized pairwise Euclidean distance matrix.

    Uses the ||a-b||^2 = ||a||^2 + ||b||^2 - 2*a.b identity to avoid
    materializing an O(n^2d) intermediate. Memory: O(n^2) (just the result).
    """
    sq_norm = (X * X).sum(axis=1)
    dot_product = X @ X.T
    sq_distances = sq_norm[:, None] + sq_norm[None, :] - 2.0 * dot_product
    sq_distances -= np.diag(sq_distances)
    np.maximum(sq_distances, 0.0, out=sq_distances)
    np.fill_diagonal(sq_distances, 0.0)
    return np.sqrt(sq_distances)


def _vectorized_dbscan(X: np.ndarray, eps: float = 0.5, min_samples: int = 1) -> list[int]:
    """DBSCAN with vectorized neighbor lookup.

    Complexity:
    - Distance matrix: O(n²d) compute via numpy (no n²d intermediate)
    - BFS expansion: O(n) Python loop with precomputed neighbors
    - Memory: O(n²) for dist_matrix + is_neighbor
    """
    n = len(X)
    if n == 0:
        return []

    dist_matrix = _pairwise_distances(X)
    is_neighbor = dist_matrix <= eps

    labels = np.full(n, -1, dtype=np.int64)
    cluster_id = 0

    for i in range(n):
        if labels[i] != -1:
            continue

        neighbors = np.flatnonzero(is_neighbor[i])
        if len(neighbors) < min_samples:
            continue

        labels[i] = cluster_id
        queue = deque(neighbors.tolist())
        while queue:
            j = queue.popleft()
            if labels[j] == -1:
                labels[j] = cluster_id
                j_neighbors = np.flatnonzero(is_neighbor[j])
                if len(j_neighbors) >= min_samples:
                    queue.extend(j_neighbors.tolist())
        cluster_id += 1

    return labels.tolist()