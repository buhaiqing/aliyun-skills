<!-- markdownlint-disable MD013 MD060 MD024 MD022 MD032 -->

# Idempotency Checklist — Advisor

## Read Operations (Idempotent)

All 13 read-only operations are inherently idempotent:

| Operation | Idempotency Note |
|-----------|------------------|
| `DescribeAdvices` | Same window returns same advices |
| `DescribeAdvicesPage` | Paginated, same page_number + page_size = same result |
| `DescribeAdvicesFlatPage` | Paginated flat list |
| `DescribeAdvisorChecks` | List of check definitions (static) |
| `DescribeAdvisorChecksFoPages` | Paginated check list |
| `DescribeAdvisorResources` | Resources currently under advisory |
| `DescribeCostCheckAdvices` | Cost check result detail |
| `DescribeCostCheckResults` | Aggregated cost check results |
| `DescribeCostOptimizationOverview` | Cost overview snapshot |
| `GetHistoryAdvices` | Same date range = same historical data |
| `GetInspectProgress` | Same task_id = same progress |
| `GetProductList` | Static product list |
| `GetTaskStatusById` | Same task_id = same status |

## Side-Effect Operations (NOT Idempotent)

| Operation | Idempotency Rule |
|-----------|------------------|
| `RefreshAdvisorCheck` | **Not idempotent**. Each call creates a new `$.TaskId`. To avoid duplicate inspections: call once, poll `GetInspectProgress` to completion, then check `DescribeAdvices` for new results. Do not re-trigger unless explicitly requested. |
| `RefreshAdvisorCostCheck` | **Not idempotent**. Same as above — creates a new `$.TaskId` each time. Call once, poll to completion. |
| `RefreshAdvisorResource` | **Not idempotent**. Single-resource refresh. Call once per resource. |

## Retry Policy

| Error | Retry? |
|-------|--------|
| `Throttling.User` | Yes, max 3, exponential backoff |
| `Throttling.Api` | Yes, max 3, exponential backoff |
| `ServiceUnavailable` | Yes, max 3, exponential backoff |
| `InspectFailed` | Yes, max 1 retry (10s backoff) |
| `InternalError` | Yes, max 2, exponential backoff |
| `InvalidParameter` | Retry once only after deterministic fix (strip RegionId, etc.) |
| `UnknownProduct` / `PluginNotInstalled` | Retry once after plugin install |
| `Forbidden.RAM` | No; HALT (requires RAM policy change) |
| `QuotaExceeded.Inspection` | No; HALT (wait until next day) |
| `QuotaExceeded.Api` | Yes, max 3, exponential backoff |
| `TaskNotFound` | No; HALT (stale task ID, re-trigger) |

## Automation Requirements

- For `RefreshAdvisor*` operations: generate a unique operation fingerprint (product + timestamp) to detect duplicate triggers at the agent layer.
- Log `$.TaskId` and `$.RequestId` for every side-effect call, never credentials.
- Persist GCL traces for `RefreshAdvisorCheck` and `RefreshAdvisorCostCheck` (classified as `recommended` level).
- Re-run `DescribeAdvices` after inspection completes to confirm new advices appeared.
