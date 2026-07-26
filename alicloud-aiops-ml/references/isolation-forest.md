# Isolation Forest — alicloud-aiops-ml

Anomaly detection using the Isolation Forest algorithm for identifying underutilized or abnormally configured cloud resources.

## Algorithm Overview

Isolation Forest isolates anomalies by randomly partitioning the feature space. Anomalous points require fewer splits to isolate (shorter average path length), producing higher anomaly scores.

**Why Isolation Forest for FinOps**:
- No assumption about data distribution (resource utilization is often non-Gaussian)
- Handles high-dimensional data (multiple utilization + cost metrics)
- Efficient for medium datasets (100-10,000 resources)
- Provides anomaly scores (not just binary labels) for ranking

## Per-Product Modeling

Each product type has different utilization baselines. A 10% CPU ECS is normal for a dev instance; 10% CPU on a production RDS is suspicious.

```python
from sklearn.ensemble import IsolationForest

def detect_anomalies(df: pd.DataFrame, by_product: bool = True,
                      contamination: float = 0.1) -> pd.DataFrame:
    """
    Args:
        df: Feature DataFrame with normalized columns
        by_product: If True, fit one model per product line
        contamination: Expected fraction of anomalies (default 0.1 = 10%)

    Returns:
        DataFrame with added columns: anomaly_score, is_anomaly, top_features
    """
    feature_cols = [
        "cpu_util_norm", "mem_util_norm", "disk_util_norm",
        "iops_util_norm", "idle_ratio", "util_imbalance",
        "cost_per_cpu", "cost_per_gb",
    ]

    result = df.copy()
    result["anomaly_score"] = 0.0
    result["is_anomaly"] = False

    groups = [("all", result)] if not by_product else result.groupby("product")

    for product_name, group in groups:
        if len(group) < 5:
            continue  # too few samples to model

        model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100,
        )
        X = group[feature_cols].fillna(0)
        predictions = model.fit_predict(X)

        # -1 = anomaly, 1 = normal
        result.loc[group.index, "is_anomaly"] = predictions == -1
        result.loc[group.index, "anomaly_score"] = model.score_samples(X)

    return result
```

## Production-Only Filtering

Anomaly detection is only meaningful for production workloads. Non-prod resources naturally have irregular usage patterns.

```python
# Before calling detect_anomalies:
production_df = df[df["env"] == "production"].copy()
anomaly_df = detect_anomalies(production_df)
```

## Contamination Parameter Tuning

| Contamination | When to Use |
|--------------|-------------|
| `0.05` (5%) | Strict — only flag extreme outliers. Use when team has limited capacity for investigation |
| `0.10` (10%) | Default — balanced sensitivity. Recommended starting point |
| `0.15` (15%) | Relaxed — catch more candidates. Use for initial broad scan |

Auto-tuning strategy:

```python
def auto_tune_contamination(df: pd.DataFrame) -> float:
    """Adjust contamination based on resource count."""
    n = len(df)
    if n < 20:
        return 0.15  # small fleet, be more lenient
    if n < 100:
        return 0.10
    return 0.05  # large fleet, only flag true outliers
```

## Feature Contribution (Explainability)

For each flagged anomaly, identify which features contributed most to the anomaly score:

```python
def explain_anomaly(row: pd.Series, feature_cols: list[str],
                     group_median: pd.Series) -> list[str]:
    """
    Compare anomalous resource's features against its product group median.
    Returns top 3 features with largest deviation.
    """
    deviations = {}
    for col in feature_cols:
        if col in row and col in group_median:
            dev = abs(row[col] - group_median[col])
            deviations[col] = dev

    top_features = sorted(deviations, key=deviations.get, reverse=True)[:3]
    return top_features
```

## Output Format

| Column | Type | Description |
|--------|------|-------------|
| `anomaly_score` | float | Lower = more anomalous (path length based) |
| `is_anomaly` | bool | True if predicted as -1 by model |
| `top_features` | list[str] | Top 3 feature names contributing to anomaly |

## Model Validation

```python
def validate_isolation_forest(df: pd.DataFrame) -> dict:
    """Sanity checks for model output."""
    checks = {
        "all_scored": df["anomaly_score"].notna().all(),
        "anomaly_rate": df["is_anomaly"].mean(),
        "anomaly_rate_in_range": 0.02 <= df["is_anomaly"].mean() <= 0.25,
        "non_prod_excluded": len(df[df["env"] != "production"]) == 0,
    }
    checks["valid"] = all(checks.values())
    return checks
```

## Common Anomaly Patterns

| Pattern | Feature Signature | Interpretation |
|---------|------------------|----------------|
| Underutilized | `idle_ratio` > 0.9, `cpu_util_norm` < 0.1 | Idle resource, candidate for downsizing/termination |
| Over-provisioned | `cost_per_cpu` high, `cpu_util_norm` low | Expensive instance with low usage |
| Imbalanced | `util_imbalance` > 0.5 | CPU and memory usage mismatch (wrong spec family) |
| Cost outlier | `cost_per_gb` high, normal utilization | Overpriced instance for its workload |
