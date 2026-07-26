# Report Template — alicloud-aiops-ml

Markdown report structure specification for FinOps analysis output.

## Report Sections (6 Required)

### 1. Executive Summary

Top-level overview with key metrics.

```markdown
# FinOps Analysis Report

**Generated**: {timestamp}
**Region**: {region}
**Analysis Period**: {start_date} to {end_date} (7 days)

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Resources | {n_resources} |
| Production Resources | {n_production} |
| Anomalies Detected | {n_anomalies} ({anomaly_pct}%) |
| Estimated Monthly Cost | ¥{total_cost:,.0f} |
| Potential Savings | ¥{potential_savings:,.0f} ({savings_pct}%) |
```

### 2. Anomaly TOP10

Top 10 anomalous resources ranked by anomaly score.

```markdown
## Anomaly Detection Results

| # | Resource | Product | Type | Env | Score | Top Contributing Features |
|---|----------|---------|------|-----|-------|--------------------------|
| 1 | i-xxx | app-order | ecs | production | -0.85 | idle_ratio(+0.92), cost_per_cpu(+0.78) |
| 2 | rm-xxx | platform-db | rds | production | -0.72 | util_imbalance(+0.65), mem_util_norm(+0.58) |
| ... | ... | ... | ... | ... | ... | ... |
```

**Score interpretation**: Lower (more negative) = more anomalous. Scores below -0.5 are flagged.

### 3. Cost Prediction

Monthly cost forecast with confidence intervals.

```markdown
## Monthly Cost Prediction

### By Product

| Product | Resources | Predicted Cost | Lower Bound | Upper Bound |
|---------|-----------|---------------|-------------|-------------|
| app-order | 15 | ¥12,500 | ¥10,000 | ¥15,000 |
| platform-infra | 8 | ¥8,200 | ¥6,560 | ¥9,840 |
| ... | ... | ... | ... | ... |
| **Total** | **{total}** | **¥{total_cost:,.0f}** | **¥{lower:,.0f}** | **¥{upper:,.0f}** |

*Confidence interval: ±20%. Model MAE: {mae_pct}%.*
```

### 4. Outliers (Cluster -1)

Resources that don't fit into any density cluster — spec outliers within their product line.

```markdown
## Resource Outliers (Cluster ID = -1)

| Resource | Product | Type | CPU | Memory | CPU Util | Cost/Core | Difference from Peers |
|----------|---------|------|-----|--------|----------|-----------|----------------------|
| i-abc | app-order | ecs | 32 | 64 GB | 12% | ¥156 | 3.2x peer median cost |
| rm-def | platform-db | rds | 8 | 32 GB | 95% | ¥240 | 1.8x peer median cost |

### Outlier Summary by Product

| Product | Total Resources | Outliers | Outlier % |
|---------|----------------|----------|-----------|
| app-order | 15 | 2 | 13.3% |
| platform-infra | 8 | 1 | 12.5% |
```

### 5. Cost Attribution

Breakdown by product, environment, and resource type.

```markdown
## Cost Attribution

### By Product

| Product | Monthly Cost | % of Total | Avg/Resource |
|---------|-------------|------------|-------------|
| app-order | ¥12,500 | 38.5% | ¥833 |
| platform-infra | ¥8,200 | 25.2% | ¥1,025 |
| ... | ... | ... | ... |

### By Environment

| Environment | Resources | Monthly Cost | % of Total |
|-------------|-----------|-------------|------------|
| production | 35 | ¥28,500 | 87.7% |
| int | 8 | ¥2,800 | 8.6% |
| test | 5 | ¥1,200 | 3.7% |

### By Resource Type

| Type | Resources | Monthly Cost | % of Total |
|------|-----------|-------------|------------|
| ecs | 20 | ¥15,000 | 46.2% |
| rds | 8 | ¥10,000 | 30.8% |
| redis | 5 | ¥4,500 | 13.8% |
| slb | 3 | ¥600 | 1.8% |
| oss | 2 | ¥200 | 0.6% |
| k8s_node | 10 | ¥2,200 | 6.8% |
```

### 6. Optimization Suggestions

Actionable recommendations with priority levels.

```markdown
## Optimization Suggestions

### P0 — High Priority (Immediate Action)

| # | Resource | Product | Issue | Suggestion | Est. Monthly Savings |
|---|----------|---------|-------|-----------|---------------------|
| 1 | i-xxx | app-order | 92% idle, g9i.4xlarge | Downgrade to g9i.2xlarge | ¥1,200 |
| 2 | rm-yyy | platform-db | 95% CPU, near capacity | Scale up or add read replica | ¥0 (risk mitigation) |

### P1 — Medium Priority (This Sprint)

| # | Resource | Product | Issue | Suggestion | Est. Monthly Savings |
|---|----------|---------|-------|-----------|---------------------|
| 3 | i-zzz | app-order | Imbalanced (32C/8G), 15% mem util | Switch to c9i family | ¥800 |

### P2 — Low Priority (Backlog)

| # | Resource | Product | Issue | Suggestion | Est. Monthly Savings |
|---|----------|---------|-------|-----------|---------------------|
| 4 | r-aaa | redis-cache | 5% memory usage, cluster mode | Downgrade to standard | ¥600 |

### Savings Summary

| Priority | Items | Est. Monthly Savings |
|----------|-------|---------------------|
| P0 | {n_p0} | ¥{savings_p0:,.0f} |
| P1 | {n_p1} | ¥{savings_p1:,.0f} |
| P2 | {n_p2} | ¥{savings_p2:,.0f} |
| **Total** | **{n_total}** | **¥{total_savings:,.0f}** |
```

## Priority Levels

| Priority | Criteria | Action Timeline |
|----------|----------|----------------|
| **P0** | >30% cost savings OR imminent capacity risk | Immediate (this week) |
| **P1** | 10-30% cost savings OR moderate risk | This sprint (1-2 weeks) |
| **P2** | <10% cost savings OR nice-to-have | Backlog |
| **P0 (Risk)** | Resource at capacity, risk of outage | Immediate — mitigate before optimizing cost |

## Formatting Guidelines

- **Tables**: Use markdown tables with aligned columns
- **Numbers**: Format costs as `¥12,500`, percentages as `38.5%`
- **Resource IDs**: Use short format (`i-xxx`, `rm-xxx`) for readability
- **Product names**: Use original product identifiers from tags/names
- **Anomaly scores**: Show 2 decimal places (`-0.85`)
- **Empty states**: If no anomalies/outliers found, show "None detected" row

## JSON Output

In addition to Markdown, a structured JSON report is generated for programmatic consumption:

```json
{
  "report_metadata": {
    "generated_at": "2026-07-27T10:00:00Z",
    "region": "cn-hangzhou",
    "period_days": 7
  },
  "executive_summary": {
    "total_resources": 50,
    "production_resources": 35,
    "anomalies_detected": 5,
    "estimated_monthly_cost": 32500,
    "potential_savings": 4800
  },
  "anomalies": [
    {
      "resource_id": "i-xxx",
      "product": "app-order",
      "anomaly_score": -0.85,
      "top_features": ["idle_ratio", "cost_per_cpu"]
    }
  ],
  "cost_prediction": {
    "total_predicted": 32500,
    "lower_bound": 26000,
    "upper_bound": 39000,
    "by_product": {}
  },
  "outliers": [],
  "cost_attribution": {
    "by_product": {},
    "by_env": {},
    "by_type": {}
  },
  "suggestions": [
    {
      "priority": "P0",
      "resource_id": "i-xxx",
      "suggestion": "Downgrade to g9i.2xlarge",
      "estimated_savings": 1200
    }
  ]
}
```
