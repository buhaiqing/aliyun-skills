# FinOps Data Pipeline — alicloud-aiops-ml

End-to-end data collection and processing pipeline for FinOps analysis.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATA COLLECTION LAYER                       │
│                                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ ECS      │ │ RDS/Redis│ │ SLB/OSS  │ │ Tag      │            │
│  │ Collector│ │ Collector│ │ K8s Col. │ │ Collector│            │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘            │
│       │             │            │            │                   │
└───────┼─────────────┼────────────┼────────────┼───────────────────┘
        │             │            │            │
        ▼             ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATA AGGREGATION LAYER                       │
│                                                                   │
│                    ┌──────────────────┐                          │
│                    │   data_pipeline  │                          │
│                    │   collect_all()  │                          │
│                    └────────┬─────────┘                          │
│                             │  unified DataFrame                  │
└─────────────────────────────┼───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FEATURE ENGINEERING LAYER                      │
│                                                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ Normalize    │ │ Derived      │ │ Categorical  │             │
│  │ (MinMax)     │ │ Features     │ │ Encoding     │             │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘             │
│         └────────────────┼────────────────┘                      │
│                           ▼                                       │
│                    ┌──────────────┐                              │
│                    │ Feature DF   │                              │
│                    └──────┬───────┘                              │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       ML MODEL LAYER                              │
│                                                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ Isolation    │ │ XGBoost      │ │ DBSCAN       │             │
│  │ Forest       │ │ Cost Predict │ │ Clustering   │             │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘             │
│         └────────────────┼────────────────┘                      │
│                           ▼                                       │
│                    ┌──────────────┐                              │
│                    │ Report Gen.  │                              │
│                    └──────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Step 1: Parallel Collection

Each collector fetches resource metadata + 7-day CMS metrics concurrently:

```
collect_all(region, days=7)
  ├── fetch_ecs_instances()    → ecs_df
  ├── fetch_rds_instances()    → rds_df
  ├── fetch_redis_instances()  → redis_df
  ├── fetch_slb_loadbalancers()→ slb_df
  ├── fetch_oss_buckets()      → oss_df
  ├── fetch_k8s_clusters()     → k8s_df
  └── fetch_all_tags()         → tags_df
```

### Step 2: Tag Enrichment

```
enrich_with_tags(unified_df, tags_df)
  ├── Level 1: ResourceManager ListResources (authoritative)
  ├── Level 2: Instance name regex parsing (fallback)
  └── Level 3: "unknown" (final fallback)
```

### Step 3: Feature Engineering

```
build_features(enriched_df)
  ├── normalize_scalar_features()   → cpu_util_norm, mem_util_norm, disk_util_norm
  ├── compute_derived_features()    → idle_ratio, cost_per_core, cost_per_gb, cpu_mem_ratio
  └── encode_categorical()          → product_encoded, env_encoded, resource_type_encoded
```

### Step 4: ML Analysis (parallel)

```
├── detect_anomalies(features_df)   → anomaly_score, is_anomaly, top_features
├── predict_cost(features_df)       → predicted_cost, cost_lower, cost_upper
└── cluster_resources(features_df)  → cluster_id
```

### Step 5: Report Generation

```
generate_report(anomaly_df, cost_df, cluster_df)
  ├── Executive Summary
  ├── Anomaly TOP10
  ├── Cost Prediction
  ├── Outliers
  ├── Cost Attribution
  └── Optimization Suggestions
```

## Error Handling Strategy

| Error Type | Strategy | Retry | Fallback |
|-----------|----------|-------|----------|
| API Throttling | Exponential backoff: 1s → 2s → 4s | 3 | Skip resource, log WARN |
| Credential Invalid | Abort immediately | 0 | Prompt user to check AK/SK |
| Network Timeout | Linear retry: 2s → 2s | 2 | Skip resource, log WARN |
| Resource Not Found | Continue | 0 | Skip, log WARN |
| CMS Data Missing | Continue | 0 | Fill metric with 0, log WARN |
| Tag Missing | Fallback chain | N/A | Level 2 → Level 3 → "unknown" |

## Data Quality Guarantees

| Guarantee | Method |
|-----------|--------|
| Memory unit consistency | All memory converted to GB (ECS: MB÷1024, RDS: kB÷1024², Redis: MB÷1024) |
| Timezone consistency | All timestamps in UTC |
| Null handling | CMS metrics default to 0 when unavailable |
| Duplicate prevention | `resource_id` deduplication at aggregation layer |
| env filtering | Only `env=production` resources enter anomaly/outlier analysis |
