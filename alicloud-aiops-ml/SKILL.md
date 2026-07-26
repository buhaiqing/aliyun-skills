---
name: alicloud-aiops-ml
description: >-
  Use this skill for AIOps + FinOps ML analysis of Alibaba Cloud resources.
  Collect resources across ECS, RDS, Redis, SLB, OSS, and K8s nodes
  concurrently, extract ML features, detect cost anomalies via Z-score
  thresholding, cluster resources with vectorized DBSCAN, predict costs via OLS
  linear regression, enrich resources with Tag-based organization metadata
  (product/env/owner), and generate Markdown FinOps inspection reports. Reach
  for this skill when the user asks for "FinOps analysis", "cost optimization",
  "resource anomaly detection", "cloud resource clustering", "cost prediction",
  "idle resource detection", "标签补全", or "巡检分析报告" — even if they just say
  "帮我看下云资源成本" or "哪些资源有异常". Do NOT use for single-product CRUD
  operations (delegate to product-specific skills), billing-only tasks
  (delegate to alicloud-billing-ops), or non-analytics operational tasks.
keywords:
  zh:
    - surface: "FinOps分析"
      maps_to: AIOps-ML
      note: "成本优化分析"
    - surface: "成本优化"
      maps_to: AIOps-ML
      note: "cost optimization intent"
    - surface: "资源异常检测"
      maps_to: AIOps-ML
      note: "anomaly detection for cloud resources"
    - surface: "资源聚类"
      maps_to: AIOps-ML
      note: "DBSCAN clustering of resources"
    - surface: "成本预测"
      maps_to: AIOps-ML
      note: "cost prediction via linear regression"
    - surface: "巡检分析报告"
      maps_to: AIOps-ML
      note: "FinOps inspection report generation"
    - surface: "标签补全"
      maps_to: AIOps-ML
      note: "Tag enrichment for organization metadata"
    - surface: "闲置资源检测"
      maps_to: AIOps-ML
      note: "idle resource identification"
  en:
    - surface: "FinOps analysis"
      maps_to: AIOps-ML
      note: "cloud financial operations analysis"
    - surface: "cost optimization"
      maps_to: AIOps-ML
      note: "cost optimization intent"
    - surface: "anomaly detection"
      maps_to: AIOps-ML
      note: "resource anomaly detection"
    - surface: "resource clustering"
      maps_to: AIOps-ML
      note: "DBSCAN clustering"
    - surface: "cost prediction"
      maps_to: AIOps-ML
      note: "cost forecasting"
    - surface: "inspection report"
      maps_to: AIOps-ML
      note: "FinOps inspection report"
    - surface: "tag enrichment"
      maps_to: AIOps-ML
      note: "tag-based organization metadata"
negative_keywords:
  - surface: "RDS"
    delegate_to: "alicloud-rds-ops"
    note: "single-product RDS operations"
  - surface: "ECS"
    delegate_to: "alicloud-ecs-ops"
    note: "single-product ECS operations"
  - surface: "Redis"
    delegate_to: "alicloud-redis-ops"
    note: "single-product Redis operations"
  - surface: "SLB"
    delegate_to: "alicloud-slb-ops"
    note: "single-product SLB operations"
  - surface: "OSS"
    delegate_to: "alicloud-oss-ops"
    note: "single-product OSS operations"
  - surface: "账单"
    delegate_to: "alicloud-billing-ops"
    note: "billing-only tasks"
license: MIT
compatibility: >-
  Python 3.10+, Official Alibaba Cloud CLI (`aliyun`, Go binary), numpy>=1.26.0,
  pytest>=8.0.0, valid API credentials, network access to Alibaba Cloud endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-07-26"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  python_version_minimum: "3.10"
  cli_applicability: read-only
  cli_support_evidence: "Confirmed via `aliyun help` — all collectors use read-only Describe*/List*/Get* API actions only."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_ACCOUNT_ID
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud AIOps + FinOps ML Analysis Skill

## Overview

Alibaba Cloud AIOps-ML is a **read-only analytics skill** that provides
cross-product resource collection, ML-powered anomaly detection, clustering,
and cost prediction for FinOps and AIOps use cases. It collects resources
from ECS, RDS, Redis, SLB, OSS, and K8s nodes concurrently, enriches them
with Tag-based organization metadata, runs ML analysis, and generates
structured Markdown reports.

### Architecture

```text
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐
│  Collectors  │───▶│  Tag Enrich  │───▶│  Feature Eng  │───▶│  ML Models │
│  (parallel)  │    │  (batched)   │    │  (15-dim)    │    │  (3 models)│
└─────────────┘    └──────────────┘    └──────────────┘    └────────────┘
                                                                  │
                                                                  ▼
                                                          ┌────────────┐
                                                          │   Report   │
                                                          │  Generator │
                                                          └────────────┘
```

### ML Models

| Model | File | Algorithm | Purpose |
|-------|------|-----------|---------|
| Anomaly Detector | `iforest_detector.py` | Z-score thresholding | Detect cost outliers |
| Clusterer | `dbscan_cluster.py` | Vectorized DBSCAN (O(n²) via numpy) | Group similar resources |
| Cost Predictor | `xgboost_predictor.py` | OLS linear regression | Predict cost from CPU/Mem |

### Safety

**All operations are read-only.** The `cli_utils.py` wrapper enforces this at
the API call level — only `Describe*`, `List*`, and `Get*` actions are allowed.
Shell metacharacters in commands are rejected at the boundary. No write,
delete, or modify operations are ever executed.

## Runtime Rules

| Area | Rule | Reference |
|------|------|-----------|
| Credentials | Read `{{env.*}}` only from environment; never ask user to paste or print secrets | [Integration](references/integration.md) |
| Read-only | All API calls are enforced read-only via `cli_utils.py` safety gate | `cli_utils.py` |
| Python | Python 3.10+ with `from __future__ import annotations` | `requirements.txt` |
| Concurrency | Collectors run in parallel via `ThreadPoolExecutor` (max 6 workers) | `pipeline.py` |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User asks for cross-product FinOps analysis or cost optimization
- User wants to detect cost anomalies across cloud resources
- User asks to cluster resources by similarity (CPU/Mem/Cost)
- User requests cost prediction based on resource specs
- User wants to generate a FinOps inspection report
- User asks to enrich resources with Tag metadata
- Task keywords: FinOps, 成本优化, 异常检测, 资源聚类, 成本预测, 巡检报告,
  标签补全, anomaly detection, cost prediction, resource clustering

### SHOULD NOT Use This Skill When

- Task is single-product CRUD → delegate to product-specific skill
  (`alicloud-ecs-ops`, `alicloud-rds-ops`, etc.)
- Task is billing-only (bills, invoices) → delegate to `alicloud-billing-ops`
- Task is RAM/permission management → delegate to `alicloud-ram-ops`
- Task requires write/delete/modify operations → this skill is read-only

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCOUNT_ID}}` | Alibaba Cloud account ID | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use as default region |
| `{{user.region}}` | User-supplied region for analysis | Ask once; reuse |
| `{{user.output_dir}}` | Output directory for reports | Default: `.runtime/reports` |
| `{{user.days}}` | Analysis time window in days | Default: 30 |
| `{{output.report_path}}` | Path to generated report | Parse from report_generator output |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing.

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute → Validate → Recover**.

### Operation: Full FinOps Analysis Pipeline

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Python deps | `python3 -c "import numpy"` | Exit code 0 | `pip install -r requirements.txt` |
| CLI available | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars | Non-empty keys | HALT; user configures env |
| Account ID | `{{env.ALIBABA_CLOUD_ACCOUNT_ID}}` | Non-empty | HALT; user configures env |
| Region | `aliyun ecs DescribeRegions` | `{{user.region}}` supported | Suggest valid region |
| Output dir | `mkdir -p {{user.output_dir}}` | Directory writable | HALT; fix permissions |
| Trace dir | `mkdir -p .runtime/traces` | Directory writable | WARN; trace disabled |

> **Trace Output**: Every pipeline run produces a structured JSON trace at
> `.runtime/traces/trace_{run_id}.json` containing:
> - Per-step timing (started_at, ended_at, duration_ms)
> - Input/output summaries for each pipeline step
> - Model parameters (thresholds, hyperparameters, formulas)
> - Data quality metrics (CMS availability, null counts, edge cases)
> - Provenance (Python version, platform, timestamps)
> - This trace serves as a **data source for AI self-analysis** of the pipeline:
>   identify bottlenecks, detect data quality issues, compare runs, and optimize model parameters.

#### Step 1: Collect Resources

```bash
python3 -c "
from pipeline import collect_all_flat
from data_pipeline import aggregate_to_json
resources = collect_all_flat('{{user.region}}')
aggregate_to_json(resources, '{{user.output_dir}}/resources.json')
print(f'Collected {len(resources)} resources')
"
```

Collects from 6 products in parallel: ECS, RDS, Redis, SLB, OSS, K8s nodes.

#### Step 2: Enrich Tags

```bash
python3 -c "
from data_pipeline import load_resources
from tag_collector import enrich_tags
resources = load_resources('{{user.output_dir}}/resources.json')
resources = enrich_tags(resources, '{{user.region}}', '{{env.ALIBABA_CLOUD_ACCOUNT_ID}}')
from data_pipeline import aggregate_to_json
aggregate_to_json(resources, '{{user.output_dir}}/resources_enriched.json')
print(f'Enriched {len(resources)} resources')
"
```

Batch-enriches with `product`, `env`, `owner` tags (50 per API call).

#### Step 3: Feature Engineering

```bash
python3 -c "
from data_pipeline import load_resources
from feature_engine import extract_features
resources = load_resources('{{user.output_dir}}/resources_enriched.json')
features = extract_features(resources)
print(f'Extracted {len(features)} feature vectors ({len(features[0]) if features else 0} dimensions)')
"
```

Extracts 15-dimensional feature vectors: capacity, utilization, cost, derived ratios.

#### Step 4: Run ML Models

```bash
python3 -c "
from data_pipeline import load_resources
from feature_engine import extract_features
from iforest_detector import detect_anomalies
from dbscan_cluster import cluster_resources
from xgboost_predictor import predict_cost
import json

resources = load_resources('{{user.output_dir}}/resources_enriched.json')
features = extract_features(resources)

anomalies = detect_anomalies(resources, features)
clusters = cluster_resources(resources, features)
predictions = predict_cost(resources, features)

json.dump(anomalies, open('{{user.output_dir}}/anomalies.json', 'w'), ensure_ascii=False)
json.dump(clusters, open('{{user.output_dir}}/clusters.json', 'w'), ensure_ascii=False)
json.dump(predictions, open('{{user.output_dir}}/predictions.json', 'w'), ensure_ascii=False)

print(f'Anomalies: {sum(1 for a in anomalies if a[\"is_anomaly\"])}/{len(anomalies)}')
print(f'Clusters: {len(set(c[\"cluster_id\"] for c in clusters))}')
print(f'Predictions: {len(predictions)}')
"
```

#### Step 5: Generate Report

```bash
python3 -c "
from data_pipeline import load_resources
import json
from report_generator import generate_report

resources = load_resources('{{user.output_dir}}/resources_enriched.json')
anomalies = json.load(open('{{user.output_dir}}/anomalies.json'))
predictions = json.load(open('{{user.output_dir}}/predictions.json'))
clusters = json.load(open('{{user.output_dir}}/clusters.json'))

report = generate_report(resources, anomalies, predictions, clusters, '{{user.output_dir}}/report.md')
print(f'Report: {{user.output_dir}}/report.md')
"
```

#### Post-execution Validation

1. Verify `{{user.output_dir}}/report.md` exists and has content
2. Check anomaly count — if > 50% of resources, verify threshold is appropriate
3. Check cluster count — if 0, verify eps parameter (default 0.5 may need tuning)
4. Check prediction coverage — all resources should have predictions

#### Failure Recovery

| Error pattern | Agent Action |
|---------------|--------------|
| `InvalidParameter` from CLI | Fix parameter format; retry once |
| `MissingCredential` | HALT; user configures env vars |
| Collector partial failure | Logged as WARNING; pipeline continues with remaining products |
| All collectors fail | RuntimeError raised; check credentials and region |
| `numpy.linalg.LinAlgError` | Predictions fall back to identity (diff=0) |
| Single-resource edge case | All models handle n=1 gracefully |

---

### Operation: Anomaly Detection Only

Run just the anomaly detection step on pre-collected resources.

```bash
python3 -c "
from data_pipeline import load_resources
from feature_engine import extract_features
from iforest_detector import detect_anomalies

resources = load_resources('{{user.output_dir}}/resources_enriched.json')
features = extract_features(resources)
results = detect_anomalies(resources, features)
for r in results:
    if r['is_anomaly']:
        print(f'{r[\"resource_id\"]} ({r[\"resource_type\"]}): cost={r[\"monthly_cost\"]:.2f}, threshold={r[\"threshold\"]:.2f}')
"
```

### Operation: Resource Clustering Only

Run just the DBSCAN clustering on pre-collected resources.

```bash
python3 -c "
from data_pipeline import load_resources
from feature_engine import extract_features
from dbscan_cluster import cluster_resources

resources = load_resources('{{user.output_dir}}/resources_enriched.json')
features = extract_features(resources)
results = cluster_resources(resources, features, eps=0.5)
for r in results:
    print(f'{r[\"resource_id\"]} ({r[\"resource_type\"]}) -> cluster {r[\"cluster_id\"]}')
"
```

### Operation: Cost Prediction Only

Run just the cost prediction on pre-collected resources.

```bash
python3 -c "
from data_pipeline import load_resources
from feature_engine import extract_features
from xgboost_predictor import predict_cost

resources = load_resources('{{user.output_dir}}/resources_enriched.json')
features = extract_features(resources)
results = predict_cost(resources, features)
for r in results:
    if abs(r['diff']) > 100:
        print(f'{r[\"resource_id\"]}: actual={r[\"actual_cost\"]:.2f}, predicted={r[\"predicted_cost\"]:.2f}, diff={r[\"diff\"]:.2f}')
"
```

### Operation: Tag Enrichment Only

Enrich resources with Tag metadata without running ML models.

```bash
python3 -c "
from data_pipeline import load_resources, aggregate_to_json
from tag_collector import enrich_tags

resources = load_resources('{{user.output_dir}}/resources.json')
resources = enrich_tags(resources, '{{user.region}}', '{{env.ALIBABA_CLOUD_ACCOUNT_ID}}')
aggregate_to_json(resources, '{{user.output_dir}}/resources_enriched.json')
print(f'Enriched {len(resources)} resources')
"
```

---

## Output Format

### Report Structure

The generated Markdown report contains 4 sections:

1. **资源概览** — Resource count by type, total monthly cost
2. **异常检测** — Cost anomalies above Z-score threshold
3. **成本预测** — Actual vs predicted cost with deviation
4. **资源聚类** — DBSCAN cluster assignments

### Intermediate Files

| File | Format | Content |
|------|--------|---------|
| `resources.json` | JSON array | Raw collected resources |
| `resources_enriched.json` | JSON array | Tag-enriched resources |
| `anomalies.json` | JSON array | Anomaly detection results |
| `clusters.json` | JSON array | DBSCAN cluster assignments |
| `predictions.json` | JSON array | Cost predictions |
| `report.md` | Markdown | Human-readable analysis report |

---

## Component Reference

| Component | File | Description |
|-----------|------|-------------|
| **Data Model** | `resource_model.py` | `Resource` dataclass with 18 fields |
| **CLI Utils** | `cli_utils.py` | Read-only enforced `aliyun` CLI wrapper |
| **Trace Logger** | `trace_logger.py` | Structured JSON trace for AI self-analysis |
| **Pipeline** | `pipeline.py` | Parallel resource collection (6 collectors) |
| **Data Pipeline** | `data_pipeline.py` | JSON serialization/deserialization |
| **Feature Engine** | `feature_engine.py` | 15-dim feature extraction |
| **Anomaly Detector** | `iforest_detector.py` | Z-score threshold anomaly detection |
| **Clusterer** | `dbscan_cluster.py` | Vectorized DBSCAN (numpy) |
| **Cost Predictor** | `xgboost_predictor.py` | OLS linear regression |
| **Tag Enricher** | `tag_collector.py` | Batch Tag API enrichment |
| **Report Generator** | `report_generator.py` | Markdown report generation |
| **ECS Collector** | `ecs_collector.py` | ECS instance collection |
| **DB Collector** | `db_collector.py` | RDS + Redis instance collection |
| **Network Collector** | `net_collector.py` | SLB + OSS + K8s node collection |

## Collected Products

| Product | Collector | Resource Type | API Actions |
|---------|-----------|---------------|-------------|
| ECS | `ecs_collector.py` | `ecs` | `DescribeInstances` |
| RDS | `db_collector.py` | `rds` | `DescribeDBInstances` |
| Redis | `db_collector.py` | `redis` | `DescribeInstances` |
| SLB | `net_collector.py` | `slb` | `DescribeLoadBalancers` |
| OSS | `net_collector.py` | `oss` | `ListBuckets` |
| K8s | `net_collector.py` | `k8s_node` | `DescribeClusterNodes` |

## Well-Architected Assessment

| Pillar | Key Guidance |
|--------|-------------|
| **Security** | Read-only only; credential masking in all outputs; shell metacharacter rejection |
| **Stability** | Partial collector failure does not block pipeline; n=1 edge cases handled gracefully |
| **Cost** | FinOps-first: cost anomaly detection, prediction, idle resource identification |
| **Efficiency** | Parallel collection via ThreadPoolExecutor (6 workers); batch Tag API (50/request); vectorized DBSCAN |
| **Performance** | DBSCAN: 52x speedup via vectorization; distance matrix memory: 25% reduction; O(n²d) compute, O(n²) memory |

## Prerequisites

- Python 3.10+
- Alibaba Cloud CLI (`aliyun`) installed and configured
- Environment variables: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABA_CLOUD_ACCOUNT_ID`
- Python packages: `numpy>=1.26.0`, `pytest>=8.0.0`

## Testing

```bash
cd alicloud-aiops-ml
python3 -m pytest -v
```

Test files cover:
- `test_integration.py` — end-to-end pipeline
- `test_edge_cases.py` — empty inputs, single resource, invalid data
- `test_dbscan_perf.py` — DBSCAN performance benchmarks
- `test_concurrent_collect.py` — concurrent collection
- `test_cli_hardening.py` — CLI security hardening
- `test_tag_batch.py` — batch tag enrichment
- `test_round3_fixes.py` — regression tests
- `test_fixes_6_to_9.py` — edge case fixes

## Operational Best Practices

- **Run in batch**: Use the full pipeline for comprehensive analysis; individual operations for targeted queries
- **Tag resources**: Ensure `product`, `env`, `owner` tags on all resources for accurate enrichment
- **Check output**: Review `report.md` for actionable insights; verify anomaly counts are reasonable
- **Tune parameters**: Adjust `eps` (DBSCAN) and `contamination` (anomaly) for your cost profile
- **Monitor collectors**: If a product collector consistently fails, check API permissions

---

## Quality Gate (GCL)

This skill participates in the Generator-Critic-Loop (GCL) adversarial quality
gate defined in [`AGENTS.md` §12](../docs/gcl-spec.md).

### GCL Scope

| Aspect | Setting |
|--------|---------|
| Required? | **Yes** (Phase 1) |
| Default `max_iter` | **2** |
| Operations covered | All read-only analysis operations |
| Risk profile | **Low** — read-only, no destructive ops, enforced at CLI boundary |

### Per-Op Safety Sub-Rules

| Operation | Safety condition (Score 1 requires) |
|-----------|-------------------------------------|
| Full pipeline | All collectors return valid data OR partial failures logged; no credential leakage in output |
| Tag enrichment | `account_id` validated before ARN construction; batch API calls respect rate limits |
| Anomaly detection | Threshold derived from actual data distribution; edge cases (n=1, n=0) handled |
| DBSCAN clustering | Vectorized implementation verified against reference; diagonal distances = 0 |
| Cost prediction | Linear regression handles singular matrix; predictions fall back to identity |
| Report generation | All sections populated; empty sections render as "无数据" not blank |

### Termination

| Condition | Behavior |
|-----------|----------|
| All dimensions >= threshold | **PASS** |
| Safety = 0 **or** Credential Hygiene = 0 | **ABORT** |
| Other dimension < threshold AND iter < 2 | **RETRY** |
| Other dimension < threshold AND iter = 2 | **MAX_ITER** |

---

## See Also

- [AGENTS.md §18.7 FinOps/ML 模块开发复盘](../AGENTS.md) — 6-round iteration lessons learned
- [alicloud-ecs-ops](../alicloud-ecs-ops/SKILL.md) — ECS operations (single-product)
- [alicloud-rds-ops](../alicloud-rds-ops/SKILL.md) — RDS operations (single-product)
- [alicloud-billing-ops](../alicloud-billing-ops/SKILL.md) — Billing operations
