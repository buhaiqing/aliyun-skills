# Feature Engineering — alicloud-aiops-ml

Feature extraction, normalization, and encoding methodology for the AIOps ML pipeline.

## Feature Categories

### 1. Raw Features (from collectors)

| Feature | Type | Source | Description |
|---------|------|--------|-------------|
| `cpu_cores` | int | Instance spec | vCPU count |
| `memory_gb` | float | Instance spec | Memory in GB (normalized from MB/kB) |
| `disk_gb` | float | DescribeDisks / RDS props | Total disk/storage in GB |
| `cpu_util_avg` | float | CMS | 7-day avg CPU utilization (%) |
| `mem_util_avg` | float | CMS | 7-day avg memory utilization (%) |
| `disk_util_avg` | float | CMS | Disk usage (%) |
| `iops_util_avg` | float | CMS | IOPS usage (%) |
| `net_in_avg` | float | CMS | Inbound bandwidth (Mbps) |
| `net_out_avg` | float | CMS | Outbound bandwidth (Mbps) |
| `monthly_cost` | float | Cost model | Estimated monthly cost (CNY) |
| `is_prepaid` | int | Instance props | 1=subscription, 0=pay-as-you-go |
| `days_until_expire` | int | ExpireTime calc | Days remaining on subscription |

### 2. Normalized Features (MinMax Scaling)

All scalar features scaled to [0, 1] range per resource type:

```python
from sklearn.preprocessing import MinMaxScaler

def normalize_scalar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize per resource_type to avoid cross-product scaling bias."""
    scalar_cols = [
        "cpu_cores", "memory_gb", "disk_gb",
        "cpu_util_avg", "mem_util_avg", "disk_util_avg",
        "iops_util_avg", "net_in_avg", "net_out_avg",
        "monthly_cost", "days_until_expire",
    ]
    result = df.copy()
    for rtype, group in df.groupby("resource_type"):
        scaler = MinMaxScaler()
        idx = group.index
        result.loc[idx, [f"{c}_norm" for c in scalar_cols]] = scaler.fit_transform(
            group[scalar_cols].fillna(0)
        )
    return result
```

**Why per-type normalization**: An 8-core ECS and an 8-core RDS have very different cost/utilization profiles. Global normalization would distort the signal.

### 3. Derived Features

| Feature | Formula | Purpose |
|---------|---------|---------|
| `cpu_mem_ratio` | `cpu_cores / max(memory_gb, 1)` | Detect imbalanced specs (e.g. 32 vCPU + 4 GB) |
| `cost_per_cpu` | `monthly_cost / max(cpu_cores, 1)` | CPU cost efficiency |
| `cost_per_gb` | `monthly_cost / max(memory_gb, 0.1)` | Memory cost efficiency |
| `idle_ratio` | `1 - max(cpu_util_avg, mem_util_avg) / 100` | 0=fully utilized, 1=completely idle |
| `util_imbalance` | `abs(cpu_util_avg - mem_util_avg) / 100` | CPU vs memory utilization gap |

```python
def compute_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["cpu_mem_ratio"] = result["cpu_cores"] / result["memory_gb"].clip(lower=1)
    result["cost_per_cpu"] = result["monthly_cost"] / result["cpu_cores"].clip(lower=1)
    result["cost_per_gb"] = result["monthly_cost"] / result["memory_gb"].clip(lower=0.1)
    result["idle_ratio"] = 1 - result[["cpu_util_avg", "mem_util_avg"]].max(axis=1) / 100
    result["util_imbalance"] = abs(
        result["cpu_util_avg"] - result["mem_util_avg"]
    ) / 100
    return result
```

### 4. Categorical Encoding

| Feature | Encoding | Values |
|---------|----------|--------|
| `product` | LabelEncoder | App/product line names |
| `env` | LabelEncoder | production, int, test, staging, dev, unknown |
| `resource_type` | LabelEncoder | ecs, rds, redis, slb, oss, k8s_node |
| `owner` | LabelEncoder | Usernames / team names |
| `instance_family` | LabelEncoder | g9i, c9i, r9i, etc. |

```python
from sklearn.preprocessing import LabelEncoder

def encode_categorical(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    categorical_cols = ["product", "env", "resource_type", "owner", "instance_family"]
    for col in categorical_cols:
        if col in result.columns:
            le = LabelEncoder()
            result[f"{col}_encoded"] = le.fit_transform(result[col].fillna("unknown"))
    return result
```

## Feature Selection for Each Model

| Model | Features Used | Rationale |
|-------|--------------|-----------|
| **Isolation Forest** | `cpu_util_norm`, `mem_util_norm`, `disk_util_norm`, `iops_util_norm`, `idle_ratio`, `util_imbalance`, `cost_per_cpu`, `cost_per_gb` | Anomaly detection on utilization + cost patterns |
| **XGBoost** | `cpu_cores`, `memory_gb`, `disk_gb`, `cpu_util_avg`, `mem_util_avg`, `product_encoded`, `is_prepaid`, `days_until_expire`, `resource_type_encoded` | Cost prediction from spec + utilization |
| **DBSCAN** | `cpu_util_norm`, `mem_util_norm`, `disk_util_norm`, `cost_per_cpu`, `cost_per_gb`, `idle_ratio`, `cpu_mem_ratio` | Resource grouping by spec/utilization profile |

## Feature Importance Analysis

After model training, feature importance is logged for audit:

```python
def log_feature_importance(model, feature_names: list[str]) -> dict[str, float]:
    """Extract and log feature importance for transparency."""
    if hasattr(model, "feature_importances_"):
        importances = dict(zip(feature_names, model.feature_importances_))
        return dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))
    return {}
```

## Full Pipeline

```python
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Complete feature engineering pipeline."""
    df = normalize_scalar_features(df)
    df = compute_derived_features(df)
    df = encode_categorical(df)
    return df
```
