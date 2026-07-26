"""Linear cost predictor using OLS regression."""
from __future__ import annotations

import numpy as np
from resource_model import Resource


def predict_cost(resources: list[Resource], features: list[dict[str, float]]) -> list[dict]:
    """Predict cost using OLS linear regression on CPU and Memory."""
    X = np.array([[f["cpu_cores"], f["memory_gb"]] for f in features])
    y = np.array([f["monthly_cost"] for f in features])

    if len(X) < 2:
        return [{"resource_id": r.resource_id, "predicted_cost": r.monthly_cost, "diff": 0.0} for r in resources]

    X_b = np.c_[np.ones(len(X)), X]
    try:
        theta = np.linalg.lstsq(X_b, y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return [{"resource_id": r.resource_id, "predicted_cost": r.monthly_cost, "diff": 0.0} for r in resources]

    results = []
    for res, feat in zip(resources, features):
        x = np.array([1, feat["cpu_cores"], feat["memory_gb"]])
        predicted = float(x @ theta)
        diff = predicted - feat["monthly_cost"]
        results.append({
            "resource_id": res.resource_id,
            "predicted_cost": round(predicted, 2),
            "actual_cost": feat["monthly_cost"],
            "diff": round(diff, 2),
        })
    return results
