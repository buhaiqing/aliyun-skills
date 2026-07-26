"""DBSCAN-style clustering for resource grouping."""
from __future__ import annotations

import numpy as np
from resource_model import Resource


def cluster_resources(resources: list[Resource], features: list[dict[str, float]], eps: float = 50.0) -> list[dict]:
    """Cluster resources using simple distance-based grouping."""
    if not features:
        return []

    X = np.array([[f["cpu_cores"], f["memory_gb"], f["monthly_cost"]] for f in features])
    X_norm = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-8)

    labels = _simple_dbscan(X_norm, eps=eps / 100)

    results = []
    for res, label in zip(resources, labels):
        results.append({
            "resource_id": res.resource_id,
            "resource_type": res.resource_type,
            "cluster_id": int(label),
        })
    return results


def _simple_dbscan(X: np.ndarray, eps: float = 0.5, min_samples: int = 1) -> list[int]:
    """Simplified DBSCAN without sklearn dependency."""
    n = len(X)
    labels = [-1] * n
    cluster_id = 0

    for i in range(n):
        if labels[i] != -1:
            continue

        neighbors = [j for j in range(n) if np.linalg.norm(X[i] - X[j]) <= eps]
        if len(neighbors) < min_samples:
            continue

        labels[i] = cluster_id
        queue = list(neighbors)
        while queue:
            j = queue.pop(0)
            if labels[j] == -1:
                labels[j] = cluster_id
                new_neighbors = [k for k in range(n) if np.linalg.norm(X[j] - X[k]) <= eps]
                if len(new_neighbors) >= min_samples:
                    queue.extend(new_neighbors)
        cluster_id += 1

    return labels
