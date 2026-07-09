# Advisor — CLI Usage Reference

> **Primary path for this skill.** All 16 operations are covered by the
> `aliyun advisor <Operation>` CLI after installing the
> `aliyun-cli-advisor` plugin.

## Setup

```bash
# One-time plugin install
aliyun plugin install --names aliyun-cli-advisor

# Verify
aliyun advisor version
```

The plugin exposes the same operations as the OpenAPI (2018-01-20
version) with English operation names. Parameter names use camelCase
(kebab-case in CLI flags: `--check-id`, `--page-number`).

## Operation Map (16 operations)

| CLI command | OpenAPI Operation | Type | Purpose |
|------------|------------------|------|---------|
| `describe-advices` | DescribeAdvices | Read | All current health advices (no pagination) |
| `describe-advices-page` | DescribeAdvicesPage | Read | Paginated health advices |
| `describe-advices-flat-page` | DescribeAdvicesFlatPage | Read | Paginated flat advice list |
| `describe-advisor-checks` | DescribeAdvisorChecks | Read | List all check definitions |
| `describe-advisor-checks-fo-pages` | DescribeAdvisorChecksFoPages | Read | Paginated check definitions |
| `describe-advisor-resources` | DescribeAdvisorResources | Read | Resources scanned by Advisor |
| `describe-cost-check-advices` | DescribeCostCheckAdvices | Read | Cost optimization advices (paginated) |
| `describe-cost-check-results` | DescribeCostCheckResults | Read | Aggregated cost results |
| `describe-cost-optimization-overview` | DescribeCostOptimizationOverview | Read | Cost optimization summary |
| `get-history-advices` | GetHistoryAdvices | Read | Historical advices |
| `get-inspect-progress` | GetInspectProgress | Read | Poll inspection task progress |
| `get-product-list` | GetProductList | Read | Supported products |
| `get-task-status-by-id` | GetTaskStatusById | Read | Inspection task status by ID |
| `refresh-advisor-check` | RefreshAdvisorCheck | Side effect | Trigger inspection |
| `refresh-advisor-cost-check` | RefreshAdvisorCostCheck | Side effect | Trigger cost check |
| `refresh-advisor-resource` | RefreshAdvisorResource | Side effect | Refresh a single resource |

---

## Read Operations (13)

### DescribeAdvices

Get latest health advices. **No pagination** — for large accounts use
`DescribeAdvicesPage`.

```bash
# All advices
aliyun advisor describe-advices

# Filter by product
aliyun advisor describe-advices --product Ecs

# Filter by check ID
aliyun advisor describe-advices --check-id "Ecs.SecurityGroup.OpenPort22"

# Filter by resource ID
aliyun advisor describe-advices --resource-id {{user.resource_id}}

# Filter by advice ID (single advice)
aliyun advisor describe-advices --advice-id 12345

# Exclude a specific advice
aliyun advisor describe-advices --exclude-advice-id 12345

# Filter by check plan
aliyun advisor describe-advices --check-plan-id 1

# English vs Chinese labels
aliyun advisor describe-advices --biz-language en   # default
aliyun advisor describe-advices --biz-language zh   # Chinese
```

**Parameters:**

| Flag | Type | Description |
|------|------|-------------|
| `--advice-id` | int | Single advice ID |
| `--check-id` | string | Filter by check ID |
| `--check-plan-id` | int | Filter by check plan |
| `--exclude-advice-id` | int | Exclude this advice |
| `--biz-language` | string | `en` (default) / `zh` |
| `--product` | string | Cloud product code (Ecs, Rds, Slb, ...) |
| `--resource-id` | string | Resource ID |

**Response JSON paths:**

| Path | Type | Description |
|------|------|-------------|
| `$.RequestId` | string | API request ID |
| `$.Advices[]` | array | All matching advices |
| `$.Advices[].AdviceId` | int | Advice ID |
| `$.Advices[].CheckId` | string | Rule that fired |
| `$.Advices[].Severity` | string | Critical / Warning / Info |
| `$.Advices[].Product` | string | Cloud product code |
| `$.Advices[].ResourceId` | string | Affected resource ID |
| `$.Advices[].AdviceDescription` | string | Human-readable description |
| `$.Advices[].AdviceName` | string | Short title |
| `$.Advices[].FixAdvice` | string | Remediation hint |
| `$.Advices[].Url` | string | Console link for more details |
| `$.Advices[].GmtModified` | string | Last update time (ISO 8601) |

---

### DescribeAdvicesPage

Paginated health advices. Prefer this for accounts with many advices.

```bash
# Page 1, 50 per page
aliyun advisor describe-advices-page --page-number 1 --page-size 50

# With product filter
aliyun advisor describe-advices-page --product Ecs --page-number 1 --page-size 100
```

**Parameters:** all from `DescribeAdvices` plus:

| Flag | Type | Description |
|------|------|-------------|
| `--page-number` | int | Page number (1-indexed) |
| `--page-size` | int | Page size (default 50, max varies) |

**Response JSON paths:**

| Path | Type | Description |
|------|------|-------------|
| `$.Advices` | array | Page of advices |
| `$.PageNumber` | int | Current page |
| `$.PageSize` | int | Items per page |
| `$.TotalCount` | int | Total matching advices |

---

### DescribeAdvicesFlatPage

Flat (non-hierarchical) paginated advice list. Useful for simple
export-to-CSV workflows.

```bash
aliyun advisor describe-advices-flat-page --page-number 1 --page-size 100
```

**Response:** same as `DescribeAdvicesPage` but `$.Advices` items are
flat dictionaries without nested groups.

---

### DescribeAdvisorChecks

List all check definitions Advisor can run. **No pagination.**

```bash
# All checks
aliyun advisor describe-advisor-checks

# Filter by product
aliyun advisor describe-advisor-checks --product Ecs
```

**Parameters:**

| Flag | Type | Description |
|------|------|-------------|
| `--product` | string | Cloud product code |
| `--biz-language` | string | `en` / `zh` |

**Response JSON paths:**

| Path | Type | Description |
|------|------|-------------|
| `$.Checks[]` | array | All check definitions |
| `$.Checks[].CheckId` | string | Rule ID (e.g. `Ecs.SecurityGroup.OpenPort22`) |
| `$.Checks[].CheckName` | string | Display name |
| `$.Checks[].Severity` | string | Default severity |
| `$.Checks[].Product` | string | Cloud product |
| `$.Checks[].Description` | string | What the check does |
| `$.Checks[].Category` | string | Security / Stability / Cost / Performance |

---

### DescribeAdvisorChecksFoPages

Paginated check definitions with additional filters.

```bash
# By category
aliyun advisor describe-advisor-checks-fo-pages --category Security

# By product + status
aliyun advisor describe-advisor-checks-fo-pages --product Ecs --status Enabled

# By check type list
aliyun advisor describe-advisor-checks-fo-pages \
  --check-types "Ecs.SecurityGroup.OpenPort22" "Ecs.Disk.NoSnapshot"
```

**Parameters:**

| Flag | Type | Description |
|------|------|-------------|
| `--assume-aliyun-id` | int | Assume another account |
| `--biz-category` | string | Business category |
| `--category` | string | Security / Stability / Cost / Performance |
| `--check-types` | list | Specific check IDs |
| `--name` | string | Name filter (substring) |
| `--page-number` | int | Page number |
| `--page-size` | int | Page size |
| `--product` | string | Cloud product |
| `--source` | string | Source filter |
| `--status` | string | `Enabled` / `Disabled` |
| `--token` | string | Pagination token |

---

### DescribeAdvisorResources

List resources that Advisor has scanned.

```bash
# All resources for a product
aliyun advisor describe-advisor-resources --product Ecs

# By resource ID
aliyun advisor describe-advisor-resources --resource-id {{user.resource_id}}

# By keyword
aliyun advisor describe-advisor-resources --product Ecs --keyword "web"

# Paginated
aliyun advisor describe-advisor-resources --product Ecs --page-number 1 --page-size 50
```

**Parameters:**

| Flag | Type | Description |
|------|------|-------------|
| `--keyword` | string | Substring search |
| `--biz-language` | string | `en` / `zh` |
| `--page-number` | int | Page number |
| `--page-size` | int | Page size |
| `--product` | string | Cloud product |
| `--resource-id` | string | Resource ID |

**Response JSON paths:**

| Path | Type | Description |
|------|------|-------------|
| `$.Resources[]` | array | Resources |
| `$.Resources[].ResourceId` | string | Resource ID |
| `$.Resources[].ResourceName` | string | Display name |
| `$.Resources[].Product` | string | Cloud product |
| `$.Resources[].Region` | string | Region |
| `$.TotalCount` | int | Total resources |

---

### DescribeCostCheckAdvices

Cost optimization advices (paginated, with extensive filters).

```bash
# All cost advices
aliyun advisor describe-cost-check-advices --page-number 1 --page-size 50

# Filter by severity
aliyun advisor describe-cost-check-advices --severity Critical

# Filter by product / region
aliyun advisor describe-cost-check-advices \
  --product Ecs \
  --region-ids cn-hangzhou

# Filter by tag
aliyun advisor describe-cost-check-advices \
  --tag-keys env \
  --tag-values prod

# Multi-account
aliyun advisor describe-cost-check-advices \
  --assume-aliyun-id-list 12345 67890
```

**Parameters:**

| Flag | Type | Description |
|------|------|-------------|
| `--assume-aliyun-id-list` | list | Account IDs to assume |
| `--check-id` | string | Specific check |
| `--check-plan-id` | int | Check plan |
| `--biz-language` | string | `en` / `zh` |
| `--page-number` | int | Page number |
| `--page-size` | int | Page size |
| `--region-ids` | list | Region filter |
| `--resource-group-id-list` | list | Resource group filter |
| `--resource-id` | string | Single resource |
| `--resource-ids` | list | Multiple resources |
| `--resource-name` | string | Resource name (substring) |
| `--severity` | string | `Critical` / `Warning` / `Info` |
| `--tag-keys` | list | Tag keys |
| `--tag-list` | list | Tag list (compound) |
| `--tag-values` | list | Tag values |

**Response JSON paths:**

| Path | Type | Description |
|------|------|-------------|
| `$.Advices` | array | Cost advices |
| `$.PageNumber`, `$.PageSize`, `$.TotalCount` | int | Pagination |
| `$.Advices[].EstimatedSavings` | number | Monthly savings estimate |
| `$.Advices[].CurrentSpec` | string | Current configuration |
| `$.Advices[].RecommendedSpec` | string | Recommended configuration |

---

### DescribeCostCheckResults

Aggregated cost results, grouped by a chosen dimension.

```bash
# Group by check item
aliyun advisor describe-cost-check-results --group-by Check

# Group by product
aliyun advisor describe-cost-check-results --group-by Product

# Group by region
aliyun advisor describe-cost-check-results --group-by Region

# With severity filter (integer: 1=Critical, 2=Warning, 3=Info)
aliyun advisor describe-cost-check-results --group-by Check --severity 1
```

**Parameters:**

| Flag | Type | Description |
|------|------|-------------|
| `--assume-aliyun-id-list` | list | Account IDs |
| `--check-ids` | list | Check IDs |
| `--check-plan-id` | int | Check plan |
| `--group-by` | string | `Check` / `Product` / `Region` |
| `--product` | string | Cloud product |
| `--region-ids` | list | Region filter |
| `--resource-group-id-list` | list | Resource group |
| `--resource-id`, `--resource-ids`, `--resource-name` | varies | Resource filters |
| `--severity` | int | 1/2/3 (note: integer) |
| `--tag-keys`, `--tag-list`, `--tag-values` | list | Tag filters |

**Response JSON paths:**

| Path | Type | Description |
|------|------|-------------|
| `$.Results` | array | Aggregated groups |
| `$.Results[].GroupKey` | string | Group dimension value |
| `$.Results[].TotalSavings` | number | Sum of savings in this group |
| `$.Results[].ResourceCount` | int | Number of resources in this group |

---

### DescribeCostOptimizationOverview

Top-level cost optimization summary.

```bash
aliyun advisor describe-cost-optimization-overview

# Specific check plan
aliyun advisor describe-cost-optimization-overview --check-plan-id 1
```

**Parameters:**

| Flag | Type | Description |
|------|------|-------------|
| `--assume-aliyun-id` | int | Single account to assume |
| `--assume-aliyun-id-list` | list | Multiple accounts |
| `--check-plan-id` | int | Check plan |
| `--token` | string | Pagination token |

**Response JSON paths:**

| Path | Type | Description |
|------|------|-------------|
| `$.Overview` | object | Summary object |
| `$.Overview.TotalSavings` | number | Total estimated monthly savings |
| `$.Overview.Items[]` | array | Per-item breakdown |
| `$.Overview.Items[].Category` | string | Ecs.Idle / Rds.Oversized / ... |
| `$.Overview.Items[].Savings` | number | Per-item savings |
| `$.Overview.Items[].ResourceCount` | int | Number of resources affected |

---

### GetHistoryAdvices

Historical advices (snapshot from past inspections).

```bash
# 7-day history
aliyun advisor get-history-advices \
  --start-date 2026-05-30 \
  --end-date 2026-06-06 \
  --page-num 1 \
  --page-size 50

# Newest first
aliyun advisor get-history-advices \
  --start-date 2026-05-30 \
  --end-date 2026-06-06 \
  --reverse true

# Filter by severity
aliyun advisor get-history-advices \
  --start-date 2026-05-30 \
  --end-date 2026-06-06 \
  --severity Critical
```

**Parameters:**

| Flag | Type | Description |
|------|------|-------------|
| `--end-date` | string | End date (YYYY-MM-DD) |
| `--biz-language` | string | `en` / `zh` |
| `--page-num` | int | Page number |
| `--page-size` | int | Page size |
| `--product` | string | Cloud product |
| `--reverse` | bool | Newest first if `true` |
| `--severity` | string | `Critical` / `Warning` / `Info` |
| `--start-date` | string | Start date (YYYY-MM-DD) |

**Constraints:**

- Date range must be ≤ 90 days.
- Both dates required; `end-date >= start-date`.

---

### GetInspectProgress

Poll inspection task progress.

```bash
# After RefreshAdvisorCheck
aliyun advisor get-inspect-progress --task-id 12345

# With multi-account
aliyun advisor get-inspect-progress --task-id 12345 --assume-aliyun-id 12345
```

**Parameters:**

| Flag | Type | Description |
|------|------|-------------|
| `--assume-aliyun-id` | int | Account to assume |
| `--task-id` | int | Task ID from RefreshAdvisorCheck |
| `--token` | string | Pagination token |

**Response JSON paths:**

| Path | Type | Description |
|------|------|-------------|
| `$.Status` | string | `Pending` / `Running` / `Finished` / `Failed` |
| `$.Progress` | int | 0-100 (when present) |
| `$.AdviceCount` | int | Number of advices generated (when finished) |

**Recommended polling pattern:**

```bash
# Poll every 30s, max 10 min
for i in {1..20}; do
  status=$(aliyun advisor get-inspect-progress --task-id $TASK_ID \
    | jq -r '.Status')
  echo "[$i] Status: $status"
  if [ "$status" = "Finished" ] || [ "$status" = "Failed" ]; then
    break
  fi
  sleep 30
done
```

---

### GetProductList

List products covered by Advisor.

```bash
# CLI subcommand uses kebab-case (PascalCase is rejected by the plugin).
aliyun advisor get-product-list
```

**Response JSON paths:**

| Path | Type | Description |
|------|------|-------------|
| `$.Products[]` | array | Product list |
| `$.Products[].Code` | string | Product code (Ecs, Rds, ...) |
| `$.Products[].Name` | string | Display name |

---

### GetTaskStatusById

Get task status (different from `GetInspectProgress`; simpler, no
progress detail).

```bash
aliyun advisor get-task-status-by-id --task-id "12345"
```

**Parameters:**

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--task-id` | string | Yes | Task ID |

---

## Side-Effect Operations (3)

### RefreshAdvisorCheck

> **[SIDE EFFECT]** Triggers an inspection scan. Does not modify
> resources but consumes API quota and may take minutes.

```bash
# Full account scan (no filter)
aliyun advisor refresh-advisor-check

# Single product
aliyun advisor refresh-advisor-check --product Ecs

# Single resource
aliyun advisor refresh-advisor-check \
  --product Ecs \
  --resource-id i-bp1xxxxxxxxxx

# With dimension filter (cost-only or performance-only)
aliyun advisor refresh-advisor-check \
  --product Ecs \
  --resource-dimension-list "Cost=e" "Performance=f"

# Multi-account
aliyun advisor refresh-advisor-check --assume-aliyun-id 12345
```

**Parameters:**

| Flag | Type | Description |
|------|------|-------------|
| `--assume-aliyun-id` | int | Account to assume |
| `--check-id` | string | Specific check to re-run |
| `--check-plan-id` | int | Specific check plan |
| `--biz-language` | string | `en` / `zh` |
| `--product` | string | Cloud product |
| `--resource-dimension-list` | list | `Cost=e`, `Performance=f`, `Security=e`, `Stability=f` |
| `--resource-id` | string | Resource ID |
| `--token` | string | Pagination token |

**Response JSON paths:**

| Path | Type | Description |
|------|------|-------------|
| `$.TaskId` | int | Use with `GetInspectProgress` |

**Polling:** see `GetInspectProgress` pattern above.

---

### RefreshAdvisorCostCheck

> **[SIDE EFFECT]** Triggers a cost optimization check.

```bash
# Full cost check
aliyun advisor refresh-advisor-cost-check

# Specific check IDs
aliyun advisor refresh-advisor-cost-check \
  --check-ids "Ecs.Idle" "Rds.Oversized"

# Force resource refresh
aliyun advisor refresh-advisor-cost-check --refresh-resource true
```

**Parameters:**

| Flag | Type | Description |
|------|------|-------------|
| `--assume-aliyun-id-list` | list | Account IDs |
| `--check-ids` | list | Specific check IDs |
| `--check-plan-id` | int | Check plan |
| `--product` | string | Cloud product |
| `--refresh-resource` | bool | Re-collect resource data first |
| `--resource-ids` | list | Specific resources |

**Response:** `$.TaskId` — poll with `GetInspectProgress`.

---

### RefreshAdvisorResource

> **[SIDE EFFECT]** Refresh a single resource's data. Cheaper than
> full inspection; useful after a resource modification.

```bash
aliyun advisor refresh-advisor-resource \
  --product Ecs \
  --resource-id i-bp1xxxxxxxxxx
```

**Parameters:**

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--product` | string | Yes | Cloud product |
| `--resource-id` | string | No | Specific resource |

**Response:** standard `RequestId`-only; no `TaskId` — operation is
synchronous.

---

## JSON Path Reference (centralized)

```text
# Common paths
$.RequestId                                       # API request ID
$.TotalCount                                      # Pagination total

# Advices (most operations)
$.Advices[]                                       # Array of advices
$.Advices[].AdviceId                              # int
$.Advices[].CheckId                               # string
$.Advices[].Severity                              # Critical / Warning / Info
$.Advices[].Product                               # Ecs / Rds / ...
$.Advices[].ResourceId                            # string
$.Advices[].AdviceDescription                     # string (en/zh)
$.Advices[].AdviceName                            # string
$.Advices[].FixAdvice                             # string
$.Advices[].Url                                   # console URL
$.Advices[].GmtModified                           # ISO 8601
$.Advices[].EstimatedSavings                      # cost-only
$.Advices[].CurrentSpec                           # cost-only
$.Advices[].RecommendedSpec                       # cost-only

# Checks
$.Checks[]                                        # Array of check defs
$.Checks[].CheckId
$.Checks[].CheckName
$.Checks[].Severity
$.Checks[].Category                               # Security / Stability / Cost / Performance

# Resources
$.Resources[]
$.Resources[].ResourceId
$.Resources[].ResourceName
$.Resources[].Product
$.Resources[].Region

# Cost overview
$.Overview.TotalSavings
$.Overview.Items[]
$.Overview.Items[].Category
$.Overview.Items[].Savings
$.Overview.Items[].ResourceCount

# Cost results (grouped)
$.Results[]
$.Results[].GroupKey
$.Results[].TotalSavings
$.Results[].ResourceCount

# Task progress
$.Status                                          # Pending / Running / Finished / Failed
$.Progress                                        # 0-100
$.AdviceCount

# Products
$.Products[]
$.Products[].Code
$.Products[].Name
```

## Coverage Gap Table

| Operation | CLI Support | Notes |
|-----------|-------------|-------|
| All 16 operations | YES | Plugin `aliyun-cli-advisor` covers 100% |
| `code-snippets` required? | NO | This skill is `cli-first`; SDK fallback is documented but not the primary path |
