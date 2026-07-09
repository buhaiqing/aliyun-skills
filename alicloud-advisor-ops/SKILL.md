---
name: alicloud-advisor-ops
description: >-
  Use when the user needs Alibaba Cloud Intelligent Advisor (智能顾问) —
  cross-product health inspection results, optimization recommendations, cost
  analysis, or to trigger refresh inspection on demand. User mentions
  Advisor, 智能顾问, advisor, 巡检, 巡检结果, 风险检查, 健康检查, 健康报告,
  成本优化, 成本分析, 优化建议, or asks "what should I optimize on my account",
  "show me the latest inspection report", "how to reduce cost", "is my
  account healthy" — even without naming the product. Not for live
  monitoring metrics (use alicloud-cms-ops), single-resource troubleshooting
  (use the specific product skill), or real-time alerting.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+
  runtime (for JIT SDK fallback), valid API credentials, network access to
  Alibaba Cloud endpoints. Plugin `aliyun-cli-advisor` must be installed:
  `aliyun plugin install --names aliyun-cli-advisor`.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-06"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "Advisor 2018-01-20 / https://help.aliyun.com/zh/advisor/developer-reference/api-advisor-2018-01-20-overview"
  cli_applicability: cli-first
  cli_support_evidence: >-
    Confirmed via `aliyun help advisor` and `aliyun plugin install
    --names aliyun-cli-advisor` (v0.4.0). All 16 operations
    (DescribeAdvices, DescribeAdvicesPage, DescribeAdvicesFlatPage,
    DescribeAdvisorChecks, DescribeAdvisorChecksFoPages,
    DescribeAdvisorResources, DescribeCostCheckAdvices,
    DescribeCostCheckResults, DescribeCostOptimizationOverview,
    GetHistoryAdvices, GetInspectProgress, GetProductList,
    GetTaskStatusById, RefreshAdvisorCheck, RefreshAdvisorCostCheck,
    RefreshAdvisorResource) have matching CLI commands, but the
    `aliyun-cli-advisor` plugin ONLY accepts kebab-case forms
    (e.g. `get-product-list`, NOT `GetProductList`). PascalCase CLI
    invocations fail with exit code 2 and a "Did you mean" hint.
    RAM action names remain PascalCase (e.g. `advisor:GetProductList`)
    — only the CLI subcommand spelling differs. CLI is the primary
    path; SDK fallback is used only when the user needs to embed
    inspection in a larger Go program.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Intelligent Advisor Operations Skill

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Prefer `./scripts/advisor-harness-wrapper.sh`; legacy `advisor-skillopt-wrapper.sh` shim supported. Fallback to native `aliyun advisor` only when wrapper missing. | [CLI](references/cli-usage.md), [Harness](references/skillopt-integration.md) |

## Overview

Alibaba Cloud Intelligent Advisor (智能顾问) is a managed cross-product
health inspection and cost optimization service. It continuously scans the
resources in your account and surfaces:

- **Health advices (风险检查/巡检结果):** Security, stability, performance,
  and best-practice violations across all cloud products.
- **Cost optimization (成本优化):** Idle, oversized, or underutilized
  resources with savings estimates and recommended actions.
- **Inspection tasks (巡检):** On-demand and scheduled scans, with progress
  tracking and history.

This skill is an **operational runbook** for agents: explicit scope,
credential rules, pre-flight checks, **CLI-first execution** with **JIT
Go SDK fallback**, response validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: cli-first`:** The `aliyun` CLI (with
  `aliyun-cli-advisor` plugin) covers **all 16 operations**. You **MUST**
  use the `aliyun advisor <Operation>` commands documented in
  [`references/cli-usage.md`](references/cli-usage.md) as the primary
  path. The Go SDK is documented as a fallback in
  [`references/api-sdk-usage.md`](references/api-sdk-usage.md) and is
  only needed when the inspection call must be embedded in a larger Go
  program (e.g., a CI pipeline) rather than run interactively.

### Read-Only by Default

The skill is **read-only by default**. The two `RefreshAdvisor*` and
`RefreshAdvisorCostCheck` operations trigger an inspection task but **do
not modify resources**. They are safe to call with explicit user
confirmation, but agents should treat any inspection-trigger call as a
moderately-risky side effect (charges API quota and may take minutes).

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT use conditions with precise triggers and explicit delegation to `alicloud-cms-ops`, `alicloud-billing-ops`, and per-product skills |
| 2 | **Structured I/O** | Placeholder conventions (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) with type and source documented |
| 3 | **Explicit Actionable Steps** | Each operation: Pre-flight → Execute → Validate → Recover, with numbered imperative steps |
| 4 | **Complete Failure Strategies** | Error taxonomy table with 10+ product-specific codes; HALT vs retry per error type |
| 5 | **Absolute Single Responsibility** | One product (Advisor), one primary resource model (Advice / Check); cross-product delegation documented |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

User mentions any of: Advisor, 智能顾问, 巡检, 巡检结果, 健康报告,
风险检查, 成本优化, 优化建议, 闲置资源, 缩配建议. Or asks to:

- **View health advices** — "What's wrong with my account?", "Show me
  the latest inspection results", "Any high-severity risks?".
- **View check definitions** — "What checks does Advisor run?",
  "List available inspection items".
- **Drill into a resource** — "What resources did Advisor scan?",
  "Show advices for instance i-xxx".
- **Cost optimization** — "How can I reduce my bill?", "Show idle or
  oversized resources", "Cost optimization overview".
- **Historical advices** — "Show last week's inspection results",
  "Trend on past advice".
- **Trigger or monitor inspection** — "Run inspection now", "Refresh
  cost check", "Is the inspection done?", "What's the inspection
  progress?".
- **List supported products** — "Which products does Advisor cover?".

CLI keyword hints: `DescribeAdvices`, `RefreshAdvisorCheck`,
`GetInspectProgress`, `CostCheck`.

### SHOULD NOT Use This Skill When

- Task is **real-time monitoring metrics / time-series data** → delegate
  to: `alicloud-cms-ops` (Cloud Monitor for raw metric points)
- Task is **historical billing invoices / cost explorer spend breakdown**
  → delegate to: `alicloud-billing-ops` (Billing API for invoices,
  orders, balances)
- Task is **a single resource's health** (one ECS, one RDS) → delegate
  to: the per-product skill (`alicloud-ecs-ops`, `alicloud-rds-ops`,
  etc.) — Advisor gives cross-product aggregated view, not per-resource
  deep diagnosis
- Task is **DAS database slow-query analysis** → delegate to:
  `alicloud-das-ops`
- Task is **active troubleshooting on a specific alert** → Advisor is
  a batch report, not a real-time diagnosis engine
- Task is **triggering a fix / remediation** → Advisor only reports;
  remediation is delegated to per-product ops skills
- User wants **console-only flows with no API** → state the limitation;
  do not invent undocumented HTTP steps

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime env | NEVER ask; HALT if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime env | NEVER ask; HALT if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Default region; Advisor is global | Use `cn-hangzhou` default |
| `{{user.product}}` | Cloud product code (`Ecs`, `Rds`, ...) | Ask once; reuse |
| `{{user.severity}}` | `Critical` / `Warning` / `Info` | Ask once; reuse |
| `{{user.check_id}}` | Specific check ID | Ask once; reuse |
| `{{user.resource_id}}` | Resource ID | Ask once; reuse |
| `{{user.start_date}}` / `{{user.end_date}}` | History range (`YYYY-MM-DD`, ≤90d) | Ask once; reuse |
| `{{user.page_size}}` | Page size (default 50) | Use default unless user overrides |
| `{{output.task_id}}` | From `$.TaskId` (refresh ops) | Parse from response |
| `{{output.advice_id}}` / `{{output.check_id}}` | From response body | Parse from response |
| `{{output.request_id}}` | API request ID for audit | Parse from response |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing. Reference: [Credential Masking
> Rules](../alicloud-skill-generator/references/credential-masking.md).

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and
  response shapes.
- **Advisor is region-agnostic:** most operations accept no `--region`
  (the service runs centrally); omit region parameter for global calls
  unless `--region` is documented as required.
- **Pagination:** Two styles are used.
  - `*Page` APIs use `--page-number` / `--page-size` (1-indexed).
  - Some advanced APIs use `NextToken` cursor style — check the
    individual operation in [`references/cli-usage.md`](references/cli-usage.md).
- **Idempotency:** Read operations are idempotent (same window returns
  same advices). Side-effect operations (`RefreshAdvisor*`) are NOT
  idempotent: re-running creates a new `$.TaskId`.
- **Timestamps:** ISO 8601 in UTC, e.g. `2026-06-06T10:00:00Z`.
- **Severity values:** `Critical`, `Warning`, `Info` (advisory).

> **MR-8 维护规范**: 文档与代码注释中使用纯文本标识
> (`Critical` / `Warning` / `Info`)，不在报告中使用 emoji。表格或日志中
> 如需视觉区分，依赖 markdown 表格列或前缀标记 (`[CRIT]`, `[WARN]`,
> `[INFO]`)。

### Common JSON Paths (Quick Reference)

For the full JSON path table (all operations), see
[`references/cli-usage.md#json-path-reference`](references/cli-usage.md#json-path-reference-centralized).
Quick reference for the four most-common operations:

| Operation | Primary Path | Type |
|-----------|--------------|------|
| `DescribeAdvices` | `$.Advices[]` | array of advice objects |
| `DescribeAdvicesPage` | `$.Advices`, `$.TotalCount` | array + int |
| `DescribeCostOptimizationOverview` | `$.Overview.TotalSavings`, `$.Overview.Items[]` | number + array |
| `GetInspectProgress` | `$.Status` (Pending/Running/Finished/Failed), `$.Progress` (0-100) | string + int |

### Expected State Transitions (inspection tasks)

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| RefreshAdvisorCheck | — | TaskId returned | 30s | 600s |
| GetInspectProgress | Pending | Running → Finished | 30s | 600s |
| RefreshAdvisorCostCheck | — | TaskId returned | 30s | 600s |

## Quick Start

### What This Skill Does

This skill enables you to query Alibaba Cloud Advisor's cross-product
inspection results, cost optimization recommendations, and on-demand
refresh tasks, using the `aliyun advisor` CLI (primary) or JIT Go SDK
(fallback).

### Prerequisites

See [Execution Environment](../alicloud-skill-generator/references/execution-environment.md).

```bash
# Install the Advisor CLI plugin (one-time)
aliyun plugin install --names aliyun-cli-advisor

# Verify
aliyun advisor version
```

### Verify Setup

```bash
# Quick connectivity check (region-agnostic)
# NOTE: aliyun-cli-advisor plugin requires kebab-case CLI subcommand
aliyun advisor get-product-list
```

### Your First Command

```bash
# List all current health advices
aliyun advisor describe-advices

# Filter by product and severity
aliyun advisor describe-advices --product Ecs --biz-language zh
```

### Next Steps

- [Core Concepts](references/core-concepts.md) — Understand Advisor's
  inspection model and advice structure
- [CLI Usage](references/cli-usage.md) — All 16 CLI commands with
  parameters and JSON paths
- [Cost Optimization](references/cli-usage.md#cost-optimization) —
  Dedicated subsection for cost reduction workflows
- [Troubleshooting](references/troubleshooting.md) — Fix common errors

> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/advisor-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun advisor ...` 命令在执行时应替换为 `./scripts/advisor-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun advisor` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。

## Execution Flows (Agent-Readable)

Every operation follows: **Pre-flight → Execute → Validate → Recover**.
Do not skip phases. The 14 read operations share the same
`Pre-flight → Execute → Validate` skeleton; only the `Execute` command
differs. For brevity, full flows for the most common operations are
shown below; the full command map is in
[`references/cli-usage.md`](references/cli-usage.md).

**Preference hint:** CLI is preferred for all operations. The Go SDK
fallback is only used when embedding inspection calls in a Go-based CI
pipeline.

### Operation: Get Latest Health Advices (Most Common)

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI / plugin | `aliyun advisor version` | Version printed | Install plugin: `aliyun plugin install --names aliyun-cli-advisor` |
| Credentials | `env \| grep ALIBABA_CLOUD_ACCESS_KEY` | Non-empty | HALT; user configures env |
| Connectivity | `aliyun advisor get-product-list` | Non-empty product list | HALT; check network / credentials / Advisor service activation |

#### CLI Execution

```bash
# All advices (unpaginated)
aliyun advisor describe-advices

# Filter by product
aliyun advisor describe-advices --product Ecs

# Filter by severity (Critical / Warning / Info)
aliyun advisor describe-advices --product Ecs

# Get a single advice by ID
aliyun advisor describe-advices --advice-id {{user.advice_id}}

# Get a single check's results
aliyun advisor describe-advices --check-id {{user.check_id}
```

#### SDK Execution (JIT Go Fallback)

The CLI is the primary path. The JIT Go SDK is used only when the
inspection call must be embedded in a Go program (e.g. CI pipeline).
See [API & SDK Usage](references/api-sdk-usage.md) for the canonical
SDK snippet.

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Response received | `$.RequestId` | Non-empty |
| Advices array | `$.Advices` | Array (may be empty if account is clean) |
| Severity distribution | Sum of `Critical` + `Warning` + `Info` across `$.Advices[].Severity` | Non-negative count |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Plugin not installed | `UnknownProduct` or `ProductNotFound` | Run `aliyun plugin install --names aliyun-cli-advisor` |
| Permission denied | `Forbidden.RAM` | HALT; grant `advisor:DescribeAdvices` RAM permission |
| Throttling | `Throttling.User` | Retry with exponential backoff (max 3 attempts) |
| Network error | `RequestError` | Retry with backoff |

## Safety Gates (硬约束)

> **本 Skill 是只读 + 触发型。任何调用 `RefreshAdvisor*` 之前必须
> 取得用户明确确认。**

| 红线 | 要求 | 违反后果 |
|------|------|----------|
| `RefreshAdvisorCheck` / `RefreshAdvisorCostCheck` 无用户确认 | 必须先 Ask，再 Execute | GCL Safety = 0，立即 ABORT |
| `RefreshAdvisorResource` 缺少 `--product` | `--product` 必填 (SAF-RAR-01) | API 拒绝 |
| AK/SK 出现在日志/JSON 输出 | 仅使用 `{{env.*}}`，禁止回显 | 严重违规 |
| 在循环中反复触发 `RefreshAdvisor*` | 必须有用户授权 (避免配额耗尽) | 配额耗尽 → HALT |
| 凭据/权限问题未修复就继续 | `Forbidden.RAM` / `InvalidAccessKeyId` | HALT |

### Operation: Trigger Inspection Refresh (Side Effect)

> **[SIDE EFFECT] Requires explicit user confirmation before execution.**
> Triggers an inspection task (may take several minutes, consumes API
> quota, may produce new advices the user is then expected to act on).

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Plugin / creds | Same as above | All pass | HALT |
| User intent | User has asked to "run inspection" or "refresh" | Explicit intent | HALT; ask user to confirm |
| Scope | Determine: full account vs single product vs single resource | Clear scope | Ask user for scope |

#### CLI Execution

```bash
# Full inspection (no product filter)
aliyun advisor refresh-advisor-check

# Single product
aliyun advisor refresh-advisor-check --product Ecs

# Single resource
aliyun advisor refresh-advisor-check \
  --product Ecs \
  --resource-id {{user.resource_id}

# With cost dimension
aliyun advisor refresh-advisor-check \
  --product Ecs \
  --resource-dimension-list "Cost=e" "Performance=f"
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Task ID returned | `$.TaskId` | Positive integer |
| Task progresses | `GetInspectProgress --task-id {{output.task_id}}` | `Status: Finished` (within 600s) |
| New advices visible | `DescribeAdvices` after status `Finished` | New entries appear |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Throttling | `Throttling.User` | Retry with backoff |
| Quota exceeded | `QuotaExceeded.Inspection` | HALT; check inspection quota |
| Task stays Pending > 600s | `Status: Pending` after 10 min | Report; suggest user check console |

### Operation: Get Cost Optimization Overview

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Plugin / creds | Same as above | All pass | HALT |

#### CLI Execution

```bash
# Full account overview
aliyun advisor describe-cost-optimization-overview

# Specific check plan
aliyun advisor describe-cost-optimization-overview --check-plan-id {{user.check_plan_id}
```

#### SDK Execution (JIT Go Fallback)

See [API & SDK Usage](references/api-sdk-usage.md). CLI is the primary
path; SDK is only for embedding in Go programs.

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Overview object | `$.Overview` | Object with at least `TotalSavings`, `Items` |
| Item count | `$.Overview.Items` | Non-negative integer |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Empty result | `$.Overview.Items == []` | Inform user: no cost optimization opportunities currently |
| Permission denied | `Forbidden.RAM` | HALT; grant `advisor:DescribeCostOptimizationOverview` |

### Operation: Get Cost Check Advices (Detail) and Aggregated Results

See [`references/cli-usage.md#describecostcheckadvices`](references/cli-usage.md) for full parameters and JSON paths.
Same `Pre-flight → Execute → Validate → Recover` skeleton as the
`DescribeAdvices` flow above. Key flag: `--group-by Check|Product|Region`
for `DescribeCostCheckResults`.

### Operation: Get Historical Advices

See [`references/cli-usage.md#gethistoryadvices`](references/cli-usage.md).
Date range constraint: `end - start <= 90 days`; `YYYY-MM-DD` format.
Use `--reverse true` for newest-first ordering.

### Operation: Poll Inspection Progress / Get Task Status

See [`references/cli-usage.md#getinspectprogress`](references/cli-usage.md).
Recommended polling: 30s interval, max 20 attempts. After `Finished`,
re-run `DescribeAdvices` to see new findings.

### Operation: Get Product List

See [`references/cli-usage.md#getproductlist`](references/cli-usage.md).
Use this to enumerate valid product codes before filtering.

### Operation: Refresh Advisor Resource (Single Resource)

> **[SIDE EFFECT] Single-resource refresh; less expensive than full
> account refresh but still consumes quota.** Implicit confirmation if
> user has named the resource; require explicit confirmation if not.

See [`references/cli-usage.md#refreshadvisorresource`](references/cli-usage.md).
`--product` is required (SAF-RAR-01).

### Operation: Refresh Advisor Cost Check (Side Effect)

> **[SIDE EFFECT] Triggers cost optimization scan. Requires explicit
> user confirmation (SAF-RCC-01).**

See [`references/cli-usage.md#refreshadvisorcostcheck`](references/cli-usage.md).
Returns `$.TaskId`; poll with `GetInspectProgress` (30s interval, max 20 attempts).

## Failure Recovery Reference

### Error Taxonomy

| Error Code | Description | Retryable | Max Retries | Backoff | Agent Action |
|------------|-------------|-----------|-------------|---------|--------------|
| `UnknownProduct` | `advisor` product not recognized by CLI | No | 0 | — | Run `aliyun plugin install --names aliyun-cli-advisor` |
| `PluginNotInstalled` | `aliyun-cli-advisor` plugin missing | No | 0 | — | Install plugin, then retry |
| `InvalidParameter` | Parameter value invalid (e.g. malformed date) | No | 0 | — | HALT; validate input against API spec |
| `MissingParameter` | Required parameter missing | No | 0 | — | HALT; add required parameter |
| `InvalidParameter.CheckId` | `CheckId` does not exist | No | 0 | — | HALT; list valid IDs with DescribeAdvisorChecks |
| `InvalidParameter.Product` | `Product` not in supported list | No | 0 | — | HALT; use `get-product-list` to enumerate |
| `InvalidParameter.Severity` | Severity value not in enum | No | 0 | — | HALT; use `Critical` / `Warning` / `Info` |
| `InvalidParameter.DateRange` | `start-date` > `end-date` or range > 90 days | No | 0 | — | HALT; adjust date range |
| `Forbidden.RAM` | RAM policy missing required permission | No | 0 | — | HALT; grant `advisor:*` policy (read or write) |
| `Throttling.User` | User-level API rate limit exceeded | Yes | 3 | Exponential (2s, 4s, 8s) | Wait and retry; reduce request rate |
| `Throttling.Api` | API-level throttling | Yes | 3 | Exponential (1s, 2s, 4s) | Wait and retry |
| `QuotaExceeded.Inspection` | Daily inspection quota exceeded | No | 0 | — | HALT; wait until next day or upgrade plan |
| `QuotaExceeded.Api` | API call quota exceeded | Yes | 3 | Exponential (5s, 10s, 20s) | Wait and retry |
| `TaskNotFound` | `TaskId` not found / expired | No | 0 | — | HALT; verify task ID with `RefreshAdvisorCheck` |
| `InspectFailed` | Inspection task failed (server-side) | Yes | 1 | Exponential (10s) | Retry once; if persists, report to user |
| `ServiceUnavailable` | Service temporarily unavailable | Yes | 3 | Exponential (2s, 4s, 8s) | Wait and retry |
| `InternalError` | Internal server error | Yes | 2 | Exponential (2s, 4s) | Retry; if persists, escalate |
| `RequestError` | Network/connection error | Yes | 3 | Exponential (1s, 2s, 4s) | Check network; retry |

### HALT vs Retry Decision Matrix

| Condition | Decision | Rationale |
|-----------|----------|-----------|
| Business error (InvalidParameter, Forbidden, QuotaExceeded) | **HALT** | User or configuration action required |
| Throttling (Throttling.User, Throttling.Api) | **Retry** | Temporary; backoff resolves |
| Network error (RequestError, ServiceUnavailable) | **Retry** | Temporary infrastructure issue |
| Credential / permission (Forbidden.RAM) | **HALT** | Requires RAM policy fix |
| Task not found (TaskNotFound) | **HALT** | Stale task ID; re-trigger with RefreshAdvisorCheck |
| Inspection failure (InspectFailed) | **Retry once** then **HALT** | Server-side issue; report to user if persists |

### RAM Permission Reference

Read-only operations:

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "advisor:DescribeAdvices",
        "advisor:DescribeAdvicesPage",
        "advisor:DescribeAdvicesFlatPage",
        "advisor:DescribeAdvisorChecks",
        "advisor:DescribeAdvisorChecksFoPages",
        "advisor:DescribeAdvisorResources",
        "advisor:DescribeCostCheckAdvices",
        "advisor:DescribeCostCheckResults",
        "advisor:DescribeCostOptimizationOverview",
        "advisor:GetHistoryAdvices",
        "advisor:GetInspectProgress",
        "advisor:GetProductList",
        "advisor:GetTaskStatusById"
      ],
      "Resource": "*"
    }
  ]
}
```

Inspection-trigger operations (add to the above):

```json
{
  "Effect": "Allow",
  "Action": [
    "advisor:RefreshAdvisorCheck",
    "advisor:RefreshAdvisorCostCheck",
    "advisor:RefreshAdvisorResource"
  ],
  "Resource": "*"
}
```

---

## Well-Architected Assessment (卓越架构)

Reference: [`references/well-architected-assessment.md`](references/well-architected-assessment.md)
for the full five-pillar assessment.

| Pillar | Core Principle for Advisor |
|--------|----------------------------|
| **Security** | Read-only inspection does not expose data. Use dedicated RAM sub-accounts with `advisor:Describe*` only; grant `advisor:Refresh*` only when user explicitly opts in to inspection triggers |
| **Stability** | Advisor is a managed service. Failure modes are documented per-error-code; throttling is the main stability concern for high-frequency callers |
| **Cost** | Inspection triggers consume API quota but no monetary cost. Cost optimization **savings** in `$.Overview.TotalSavings` are the main economic value of this skill |
| **Efficiency** | Use `DescribeAdvicesPage` over `DescribeAdvices` for large accounts (the unpaginated API may return thousands of entries). Use `group-by` parameters in `DescribeCostCheckResults` to aggregate before reading details |
| **Performance** | Single `DescribeAdvices` call returns in < 5s for typical accounts. Inspection refresh tasks may take 5-10 min; use `GetInspectProgress` polling at 30s intervals |

---

## Quality Gate (GCL)

This skill participates in the Generator-Critic-Loop (GCL) defined in
[`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate).
Per `AGENTS.md` §12.8, this skill is classified as **`recommended`** (it
has 3 inspection-trigger side effects: `RefreshAdvisorCheck`,
`RefreshAdvisorCostCheck`, `RefreshAdvisorResource`; no destructive
resource operations).

| Aspect | Setting |
|---|---|
| Required? | **Yes** (`recommended`) |
| `max_iter` | 3 |
| Most-scrutinized ops | `RefreshAdvisorCheck`, `RefreshAdvisorCostCheck`, `RefreshAdvisorResource` |
| Rubric | [`references/rubric.md`](references/rubric.md) |
| Prompt templates | [`references/prompt-templates.md`](references/prompt-templates.md) |

### Changelog
1.0.0 | 2026-06-06 | Initial release. 16 operations covered; CLI-first
path with JIT Go SDK fallback; full read+side-effect flow documentation;
GCL rubric and prompt templates.

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only`, the skill MUST provide
  `assets/code-snippets/` with runnable Go SDK code. **DOES NOT APPLY** —
  this skill is `cli-first`, the `aliyun advisor` CLI covers all 16
  operations, and SDK fallback is documented but not the primary path.
- **[User Experience Spec](../alicloud-skill-generator/references/user-experience-spec.md)** —
  Standardized interaction patterns and error message format.
- **[AIOps Best Practices](../alicloud-skill-generator/references/aiops-best-practices.md)** —
  Multi-metric correlation, cross-skill diagnosis, delegation matrix.
