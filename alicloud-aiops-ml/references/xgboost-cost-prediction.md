# XGBoost Cost Prediction — alicloud-aiops-ml

Monthly cost prediction using XGBoost regression for FinOps budgeting and forecasting.

## Model Rationale

XGBoost is chosen for cost prediction because:
- Handles mixed feature types (numeric + categorical) natively
- Robust to outliers in cost data
- Provides feature importance for cost driver analysis
- Fast training on medium datasets (100-10,000 resources)

## Feature Selection

| Feature | Type | Importance | Description |
|---------|------|-----------|-------------|
| `cpu_cores` | int | High | Primary cost driver for compute |
| `memory_gb` | float | High | Primary cost driver for DB/cache |
| `disk_gb` | float | Medium | Storage cost contribution |
| `cpu_util_avg` | float | Low | Low utilization may indicate over-provisioning |
| `mem_util_avg` | float | Low | Similar to cpu_util |
| `product_encoded` | int | Medium | Product-line cost variation |
| `resource_type_encoded` | int | High | ECS vs RDS vs Redis cost baseline differs |
| `is_prepaid` | int | Medium | Subscription often has different unit cost |
| `days_until_expire` | int | Low | Near-expiry resources may have different pricing |
| `instance_family_encoded` | int | Medium | g9i vs c9i cost difference |

## Model Training

```python
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

def train_cost_predictor(df: pd.DataFrame) -> tuple[xgb.XGBRegressor, dict]:
    """Train XGBoost model for monthly cost prediction."""
    feature_cols = [
        "cpu_cores", "memory_gb", "disk_gb",
        "cpu_util_avg", "mem_util_avg",
        "product_encoded", "resource_type_encoded",
        "is_prepaid", "days_until_expire",
        "instance_family_encoded",
    ]
    target_col = "monthly_cost"

    X = df[feature_cols].fillna(0)
    y = df[target_col]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        objective="reg:squarederror",
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    mae_pct = mae / y_test.mean() * 100

    metrics = {
        "mae": round(mae, 2),
        "mae_pct": round(mae_pct, 1),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "pass": mae_pct < 20.0,
    }

    return model, metrics
```

## Confidence Intervals

Predictions include ±20% confidence bands to account for:
- Pricing variance across regions
- Discount/coupon effects not visible to API
- Spot instance and savings plan pricing

```python
def predict_with_confidence(model: xgb.XGBRegressor, df: pd.DataFrame,
                             confidence: float = 0.20) -> pd.DataFrame:
    """
    Returns predicted monthly cost with lower/upper bounds.

    Args:
        confidence: Width of interval (0.20 = ±20%)
    """
    feature_cols = [
        "cpu_cores", "memory_gb", "disk_gb",
        "cpu_util_avg", "mem_util_avg",
        "product_encoded", "resource_type_encoded",
        "is_prepaid", "days_until_expire",
        "instance_family_encoded",
    ]

    X = df[feature_cols].fillna(0)
    predicted = model.predict(X)

    result = df.copy()
    result["predicted_cost"] = predicted
    result["cost_lower"] = predicted * (1 - confidence)
    result["cost_upper"] = predicted * (1 + confidence)
    return result
```

## Model Evaluation

### Acceptance Criteria

| Metric | Target | Meaning |
|--------|--------|---------|
| MAE | < 20% of mean cost | Average prediction error under 20% |
| R² | > 0.85 | Model explains > 85% of cost variance |
| Feature coverage | All features have importance > 0 | Every feature contributes |

### Evaluation Function

```python
def evaluate_model(model: xgb.XGBRegressor, X_test: pd.DataFrame,
                    y_test: pd.Series) -> dict:
    """Full model evaluation report."""
    from sklearn.metrics import r2_score, mean_absolute_percentage_error

    y_pred = model.predict(X_test)

    return {
        "mae_cny": round(mean_absolute_error(y_test, y_pred), 2),
        "mape_pct": round(mean_absolute_percentage_error(y_test, y_pred) * 100, 1),
        "r2": round(r2_score(y_test, y_pred), 3),
        "feature_importance": dict(zip(
            X_test.columns,
            model.feature_importances_.round(4)
        )),
    }
```

## Prediction Workflow

```
1. Load enriched DataFrame with monthly_cost column
2. Train XGBoost model on 80% of data
3. Evaluate on 20% holdout → MAE < 20% → PASS
4. Predict cost for all resources
5. Add ±20% confidence intervals
6. Aggregate predictions by product for budget summary
```

## Per-Product Cost Aggregation

```python
def aggregate_cost_by_product(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize predicted costs by product line."""
    return df.groupby("product").agg(
        resource_count=("resource_id", "count"),
        total_predicted=("predicted_cost", "sum"),
        total_lower=("cost_lower", "sum"),
        total_upper=("cost_upper", "sum"),
        avg_per_resource=("predicted_cost", "mean"),
    ).sort_values("total_predicted", ascending=False)
```

## Limitations

- **Pricing staleness**: Prices change; model should be retrained monthly
- **Reserved instance pricing**: Not visible via API; actual cost may be lower
- **Small fleet**: < 50 resources may produce unreliable predictions
- **New instance families**: Prices for families not in training data use fallback estimates
