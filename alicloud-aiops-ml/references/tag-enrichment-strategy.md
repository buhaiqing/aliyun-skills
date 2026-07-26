# Tag Enrichment Strategy — alicloud-aiops-ml

Multi-level tag enrichment pipeline for resource identification and cost attribution.

## Priority Levels

```
Level 1 (Most Authoritative)
  │  ResourceManager ListResources → direct Tag key-value pairs
  │
  ├── Level 2 (Fallback)
  │    Instance name regex parsing → product / env / owner extraction
  │
  └── Level 3 (Final Fallback)
       "unknown" → unidentifiable resources
```

## Level 1: ResourceManager ListResources

Most authoritative source. Tags are explicitly set by users/automation on resources.

**API**: `aliyun resourcemanager ListResources --ResourceType ACS::{Product}::{ResourceType}`

**Tag keys expected**:

| Tag Key | Purpose | Required | Example Values |
|---------|---------|----------|---------------|
| `product` | Product line / application | Yes | `app-user-service`, `app-order`, `platform-infra` |
| `env` | Environment | Yes | `production`, `int`, `test`, `staging` |
| `owner` | Responsible person/team | Yes | `zhangsan`, `platform-team` |
| `business_line` | Business domain | No | `ecommerce`, `logistics`, `payment` |
| `cost_center` | Cost accounting center | No | `CC-001`, `CC-002` |

**Tag to DataFrame mapping**:

```python
def tags_to_dataframe(tags: list[dict]) -> pd.DataFrame:
    """
    tags = [
      {"ResourceId": "i-xxx", "Tags": [
        {"Key": "product", "Value": "app-order"},
        {"Key": "env", "Value": "production"},
      ]}
    ]
    → DataFrame columns: resource_id, product, env, owner, business_line, cost_center
    """
```

## Level 2: Instance Name Regex Parsing

Fallback when ResourceManager tags are absent. Parses naming conventions from `instance_name`.

### Naming Convention Patterns

| Pattern | Regex | Extracted | Example |
|---------|-------|-----------|---------|
| Hyphen-delimited | `^([a-z]+)-([a-z]+)-([a-z0-9]+)` | product, env, index | `app-order-prod-01` → product=`app-order`, env=`production` |
| Env prefix | `^(prod\|int\|test\|stg)-(.+)` | env, rest | `prod-api-gateway` → env=`production`, product=`api-gateway` |
| Product prefix | `^([a-z-]+)-(prod\|int\|test\|stg)` | product, env | `user-service-prod` → product=`user-service`, env=`production` |
| K8s pod style | `^([a-z-]+)-([a-z0-9]+)-([a-z0-9]+)` | product, replica, hash | `order-svc-7d4f8b9c-x2k` → product=`order-svc` |

### Env Name Normalization

| Raw Value | Normalized |
|-----------|-----------|
| `prod`, `production`, `prd`, `live` | `production` |
| `int`, `integration`, `sit` | `int` |
| `test`, `tst`, `uat`, `qa` | `test` |
| `stg`, `staging`, `pre` | `staging` |
| `dev`, `development` | `dev` |

### Owner Extraction

- Check for common owner patterns in name: `-<username>-`, `-<team>-`
- If name contains a known username from team roster → assign
- Otherwise → leave for Level 3

## Level 3: "unknown" Fallback

When neither Level 1 nor Level 2 can determine a value:

| Field | Fallback Value | Impact |
|-------|---------------|--------|
| `product` | `"unknown"` | Excluded from per-product cost attribution |
| `env` | `"unknown"` | **NOT** included in anomaly detection (production-only filter) |
| `owner` | `"unknown"` | Flagged in report as unowned resources |
| `business_line` | `"unknown"` | Excluded from per-business-line breakdown |

## Enrichment Pipeline

```python
def enrich_resources(resources_df: pd.DataFrame, tags_df: pd.DataFrame, account_id: str = None) -> pd.DataFrame:
    """
    1. Left join resources_df with tags_df on resource_id
    2. For rows where product/env/owner is NaN after join:
       a. Try Level 2 regex parsing on instance_name
       b. If still NaN: set to "unknown"
    3. Return enriched DataFrame
    """
```

## Example

### Input

```
resource_id | instance_name           | Tags (from ResourceManager)
------------|------------------------|---------------------------
i-001       | app-order-prod-01      | {product: app-order, env: production}
i-002       | user-svc-staging-master | (none)
i-003       | legacy-box             | (none)
```

### Output

```
resource_id | product     | env        | owner    | source
------------|-------------|------------|----------|--------
i-001       | app-order   | production | zhangsan | Level 1 (Tag)
i-002       | user-svc    | staging    | unknown  | Level 2 (Name)
i-003       | unknown     | unknown    | unknown  | Level 3 (Fallback)
```
