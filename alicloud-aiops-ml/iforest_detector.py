"""Cost-based threshold anomaly detector."""
from __future__ import annotations

import numpy as np
from resource_model import Resource


def detect_anomalies(resources: list[Resource], features: list[dict[str, float]], contamination: float = 0.1) -> list[dict]:
    """Detect cost anomalies using Z-score threshold method."""
    results = []
    costs = [f["monthly_cost"] for f in features]
    if not costs:
        return results

    mean_cost = np.mean(costs)
    std_cost = np.std(costs) if len(costs) > 1 else mean_cost * 0.1
    threshold = mean_cost + 2 * max(std_cost, 1)

    for res, feat in zip(resources, features):
        is_anomaly = feat["monthly_cost"] > threshold
        score = feat["monthly_cost"] / max(threshold, 1)
        results.append({
            "resource_id": res.resource_id,
            "resource_type": res.resource_type,
            "monthly_cost": feat["monthly_cost"],
            "threshold": round(threshold, 2),
            "anomaly_score": round(score, 3),
            "is_anomaly": is_anomaly,
        })
    return results
