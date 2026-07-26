# Cost Model Reference — alicloud-aiops-ml

Cost estimation methodology for FinOps analysis. All prices are estimates based on Alibaba Cloud official pricing pages and may vary by region and commitment term.

## General Approach

Monthly cost = `instance_hourly_price × 730 hours` (average hours/month) for pay-as-you-go.
For subscription (包年包月): cost = `monthly price from billing API or plan`.

**Limitations**: Actual cost depends on discounts, coupons, reserved instances, and Savings Plans not visible via resource APIs. This model provides **estimation** suitable for relative comparison and anomaly detection, not billing reconciliation.

## ECS Pricing

### Instance Families (Simplified)

| Family | Type | vCPU:Mem Ratio | Use Case | Hourly (estimate, CNY) |
|--------|------|---------------|----------|------------------------|
| g9i | General Purpose | 1:4 | Web/App servers | vCPU × 0.35 |
| c9i | Compute Optimized | 1:2 | Batch processing | vCPU × 0.30 |
| r9i | Memory Optimized | 1:8 | In-memory DB, cache | vCPU × 0.50 |
| g8i | General Purpose | 1:4 | Standard workloads | vCPU × 0.30 |
| g7 | General Purpose | 1:4 | Previous gen | vCPU × 0.25 |

### Cost Calculation

```python
def estimate_ecs_monthly_cost(instance_type: str, cpu_cores: int, memory_gb: int,
                               disk_gb: float, is_prepaid: bool) -> float:
    # Base compute cost
    family = instance_type.split('.')[0]  # e.g., "g9i" from "g9i.2xlarge"
    hourly = CPU_PRICE_MAP.get(family, 0.30) * cpu_cores

    # Disk cost (assume ESSD PL0, 0.001 CNY/GB/hour)
    disk_hourly = disk_gb * 0.001

    monthly = (hourly + disk_hourly) * 730
    return round(monthly, 2)
```

### Price Map

```python
CPU_PRICE_MAP = {
    "g9i": 0.35, "c9i": 0.30, "r9i": 0.50,
    "g8i": 0.30, "g7":  0.25, "c7":  0.22,
    "r7":  0.42, "g6":  0.20, "DEFAULT": 0.30,
}
```

## RDS Pricing

| DB Engine | Spec Type | Monthly Estimate (CNY) |
|-----------|-----------|------------------------|
| MySQL | General Purpose | `memory_gb × 100 + storage_gb × 0.8` |
| PostgreSQL | General Purpose | `memory_gb × 120 + storage_gb × 0.8` |
| SQL Server | General Purpose | `memory_gb × 200 + storage_gb × 1.0` |

```python
def estimate_rds_monthly_cost(engine: str, memory_gb: float, storage_gb: float) -> float:
    engine_multiplier = {"MySQL": 100, "PostgreSQL": 120, "SQLServer": 200}
    multiplier = engine_multiplier.get(engine, 100)
    return round(memory_gb * multiplier + storage_gb * 0.8, 2)
```

## Redis Pricing

| Architecture | Memory Tier | Monthly (CNY/GB) |
|-------------|-------------|------------------|
| Standard | ≤ 1 GB | 64 |
| Standard | 1-32 GB | 56 |
| Cluster | Any | 80 |
| Read/Write Splitting | Any | 70 |

```python
def estimate_redis_monthly_cost(capacity_gb: float, architecture: str) -> float:
    if architecture == "cluster":
        return round(capacity_gb * 80, 2)
    if architecture == "rwsplit":
        return round(capacity_gb * 70, 2)
    if capacity_gb <= 1:
        return round(capacity_gb * 64, 2)
    return round(capacity_gb * 56, 2)
```

## SLB Pricing

| Type | Monthly Estimate (CNY) |
|------|------------------------|
| CLB (Classic, shared) | 0 (free tier) |
| CLB (Standard spec) | 100-500 (depends on spec) |
| ALB | LCU-based, estimate: `traffic_gb × 0.05` |
| NLB | LCU-based, estimate: `traffic_gb × 0.06` |

```python
def estimate_slb_monthly_cost(lb_type: str, spec: str = "", traffic_gb: float = 0) -> float:
    if lb_type == "clb" and not spec:
        return 0.0
    if lb_type == "clb":
        return 200.0  # default spec estimate
    if lb_type == "alb":
        return round(traffic_gb * 0.05, 2)
    if lb_type == "nlb":
        return round(traffic_gb * 0.06, 2)
    return 0.0
```

## OSS Storage Pricing

| Storage Class | Monthly (CNY/GB) |
|--------------|------------------|
| Standard | 0.12 |
| Infrequent Access (IA) | 0.08 |
| Archive | 0.033 |
| Cold Archive | 0.015 |

```python
def estimate_oss_monthly_cost(storage_gb: float, storage_class: str = "Standard") -> float:
    rates = {"Standard": 0.12, "IA": 0.08, "Archive": 0.033, "ColdArchive": 0.015}
    return round(storage_gb * rates.get(storage_class, 0.12), 2)
```

## K8s Node Cost Approximation

K8s nodes are ECS instances. Cost = sum of all node ECS costs:

```python
def estimate_k8s_monthly_cost(nodes_df: pd.DataFrame) -> float:
    return nodes_df.apply(
        lambda row: estimate_ecs_monthly_cost(
            row["instance_type"], row["cpu_cores"],
            row["memory_gb"], row.get("disk_gb", 0),
            row.get("is_prepaid", False)
        ), axis=1
    ).sum()
```

## Total Cost Aggregation

```python
def compute_monthly_cost(df: pd.DataFrame) -> pd.Series:
    costs = pd.Series(0.0, index=df.index)
    for resource_type, group in df.groupby("resource_type"):
        if resource_type == "ecs":
            costs[group.index] = group.apply(lambda r: estimate_ecs_monthly_cost(...), axis=1)
        elif resource_type == "rds":
            costs[group.index] = group.apply(lambda r: estimate_rds_monthly_cost(...), axis=1)
        # ... etc
    return costs
```
