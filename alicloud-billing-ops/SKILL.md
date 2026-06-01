---
name: alicloud-billing-ops
description: >-
  Use when the user needs to query, analyze, or manage Alibaba Cloud billing, costs, orders, or account finances — account balance, bill overview/details, instance-level bills, settlement bills, orders, reservations (RI/SCU), savings plans, resource packages, transactions, prepaid cards, vouchers, cost optimization, budget alerts, resource expiration warnings. User mentions "账单", "费用", "账单明细", "账户余额", "订单", "预留实例", "RI", "存储容量包", "SCU", "储蓄计划", "Savings Plan", "资源包", "代金券", "发票", "月账单", "成本优化", "费用分析", "bssopenapi", "billing", "cost", "bill" — even without naming the product explicitly. Not for resource CRUD (delegate to product-specific skills), permissions (delegate to alicloud-ram-ops), account/resource-group management (delegate to alicloud-resourcemanager-ops), or monitoring/alerts (delegate to alicloud-cms-ops).
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-05-30"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "BSSOpenApi 2017-12-14 / https://help.aliyun.com/zh/billing/developer-reference/api-bssopenapi-2017-12-14-overview"
  cli_applicability: "dual-path"
  cli_support_evidence: >-
    Confirmed via `aliyun bssopenapi help` — 70+ operations including QueryAccountBalance, QueryBill, QueryBillOverview, QueryInstanceBill, QuerySettleBill, QueryAccountBill, QuerySplitItemBill, QueryOrders, GetOrderDetail, QueryRIUtilizationDetail, QuerySavingsPlansInstance, QuerySavingsPlansDeductLog, QueryResourcePackageInstances, QueryAccountTransactions, QueryPrepaidCards, QueryCashCoupons are all fully supported by the official aliyun CLI (v3.3.14+).
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Billing Operations Skill

## Overview

BSSOpenApi (Billing Support System Open API) is Alibaba Cloud's unified billing management service. This skill is an **operational runbook** for agents: explicit scope, credential rules, pre-flight checks, **dual-path execution** (official `aliyun` CLI primary, JIT Go SDK fallback), response validation, and failure recovery. **All operations are read-only** — this skill does not perform resource CRUD or billing modifications.

> **UX Compliance:** This skill follows the [User Experience Specification](../alicloud-skill-generator/references/user-experience-spec.md). All operations include onboarding guidance, minimal prompts, smart defaults, clear feedback, and user-friendly error handling.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` fully supports BSSOpenApi. CLI is the **primary** execution path for all billing queries. JIT Go SDK is the **fallback** for edge cases or when Go-based data processing pipelines are needed. Both paths are documented for each operation below.

## Five Core Standards (Quality Gates)

Every generated skill MUST satisfy these five standards. Use them as a design checklist during population:

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT use with billing trigger keywords (CN/EN), explicit delegation to RAM, resource-manager, CMS, and product-specific skills |
| 2 | **Structured I/O** | `{{env.*}}` for credentials, `{{user.*}}` for billing cycle filters, `{{output.*}}` for API response capture per OpenAPI JSON paths |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight (credential + param check) → Execute (CLI primary + SDK fallback) → Validate (response code + data presence) → Recover (error taxonomy) |
| 4 | **Complete Failure Strategies** | 14 error codes with retry/HALT distinction; throttling backoff; pagination recovery; credential validation |
| 5 | **Absolute Single Responsibility** | One product (BSSOpenApi), one domain (billing/financial). Cross-product delegation: RAM for permissions, CMS for alarms, product skills for resource CRUD |

Refer to the [meta-skill](../alicloud-skill-generator/SKILL.md#five-core-standards-quality-gates) for detailed descriptions of each standard.

### Well-Architected Framework Integration (卓越架构)

In addition to the Five Core Standards, every generated skill MUST map its operations to Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html) five pillars:

| Pillar | Skill Integration | Reference |
|--------|-------------------|-----------|
| **安全 (Security)** | IAM permissions with least privilege; credential masking MANDATORY; RAM policy templates | `references/well-architected-assessment.md` §1 |
| **稳定 (Stability)** | Retry/backoff for throttling; pagination recovery; data freshness awareness | `references/well-architected-assessment.md` §2 |
| **成本 (Cost)** | Cost anomaly detection; RI/SCU coverage analysis; waste detection patterns; FinOps runbook | `references/well-architected-assessment.md` §3 |
| **效率 (Efficiency)** | Batch pagination; pipeline-friendly JSON output; CI/CD cost tracking | `references/well-architected-assessment.md` §4 |
| **性能 (Performance)** | API latency characteristics; filter-first strategy; cache guidelines | `references/well-architected-assessment.md` §5 |

See [references/well-architected-assessment.md](references/well-architected-assessment.md) for the complete specification.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud BSSOpenApi" OR "BSS" OR "Billing" OR "账单" OR "费用"
- Task involves querying **account balance** (QueryAccountBalance)
- Task involves **bill queries** — overview, detail, instance-level, settlement, account, or split billing
- Task involves **order queries** and **order details**
- Task involves **RI/SCU/SP** — reserved instances utilization, savings plans, storage capacity units
- Task involves **resource packages** — listing, status check, remaining amount
- Task involves **financial tools** — transactions, prepaid cards, cash coupons
- Task involves **FinOps** — cost anomaly detection, budget tracking, expiration warnings, coverage analysis
- Task keywords: bill, invoice, balance, order, RI, SCU, savings plan, resource package, coupon, prepaid, transaction, 账单, 费用, 订单, 预留实例, 储蓄计划, 资源包, 代金券, 储值卡, cost optimization, FinOps, bssopenapi, QueryBill, QueryAccountBalance
- User asks to analyze, monitor, or optimize costs **via API, CLI, or automation**
- **Even without naming BSSOpenApi explicitly:** user says "查一下账户余额", "这个月花多少钱了", "ECS费用明细", "代金券还有多少"

### SHOULD NOT Use This Skill When

- Task is **resource CRUD** (create/modify/delete ECS, RDS, SLB, etc.) → delegate to: `alicloud-ecs-ops`, `alicloud-rds-ops`, `alicloud-slb-ops`, etc.
- Task is **RAM / permission management** → delegate to: `alicloud-ram-ops`
- Task is **account / resource group management** → delegate to: `alicloud-resourcemanager-ops`
- Task is **monitoring / alert configuration** → delegate to: `alicloud-cms-ops`
- Task is **network / VPC / NAT** → delegate to: `alicloud-nat-ops`, `alicloud-vpc-ops`
- User insists on **console-only** flows with no API → state limitation; do not invent undocumented HTTP steps

### Delegation Rules

- Billing operations are **self-contained** — no dependencies on other cloud resources
- **From other skills:** When a product skill (ECS, RDS, etc.) needs cost attribution, delegate to this skill's `QueryInstanceBill` with `ProductCode` filter
- **To other skills:** When billing query reveals a resource issue (e.g., orphaned instance), delegate investigation to the appropriate product skill
- Multi-product cost analysis: use this skill's product-level billing APIs; do not merge unrelated product APIs

## Variable Convention (Agent-Readable)

Structured placeholders reduce injection ambiguity and unsafe prompts:

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Default to `cn-hangzhou` (billing is region-independent) |
| `{{user.billing_cycle}}` | Billing cycle (YYYY-MM) | Ask once; default to current month |
| `{{user.product_code}}` | Product code filter (e.g., ecs, rds) | Ask once; optional filter |
| `{{user.order_id}}` | Order ID for detail query | Ask once |
| `{{user.sp_instance_id}}` | Savings Plan instance ID | Ask once |
| `{{output.balance}}` | From QueryAccountBalance response | Parse per `$.Data.AvailableAmount` |
| `{{output.bill_items}}` | From QueryBill response | Parse per `$.Data.Items.Item[]` |
| `{{output.total_count}}` | Pagination counter | Parse per `$.Data.TotalCount` |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field value in console output, debug messages, error messages, or logs.
>
> **Masking rules across all execution paths:**
> | Execution Path | Safe Pattern | Unsafe Pattern |
> |----------------|-------------|----------------|
> | Console output | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>` | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=LTAI5t...` |
> | Error messages | `Error: API call failed (credential omitted)` | `Error: InvalidAccessKeySecret.XXX ... actual secret...` |
> | Verification | `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "Secret is set"` | `echo "Secret=$ALIBABA_CLOUD_ACCESS_KEY_SECRET"` |
> | JIT Go SDK | `AccessKeySecret: tea.String(os.Getenv("..."))` (env read is safe) | `fmt.Printf("Config: %+v", config)` |
>
> **If any execution flow violates this rule, the skill SHALL be blocked from merge as a security incident.**

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes
- **BillingCycle format:** `YYYY-MM` (e.g., `2026-05`)
- **Timezone:** All timestamps are UTC+8 (Asia/Shanghai)
- **Endpoint:** `business.aliyuncs.com` (region-independent)
- **API version:** `2017-12-14`

### Response Field Table (Key Operations)

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| QueryAccountBalance | `$.Data.AvailableAmount` | string | Available cash balance |
| QueryBillOverview | `$.Data.Items.Item[]` | array | Product-level bill summary |
| QueryBill | `$.Data.Items.Item[]` | array | Bill detail records |
| QueryInstanceBill | `$.Data.Items.Item[]` | array | Instance-level bill records |
| QueryOrders | `$.Data.OrderList.Order[]` | array | Order list |
| GetOrderDetail | `$.Data` | object | Single order detail |
| QueryRIUtilizationDetail | `$.Data.Items[]` | array | RI utilization records |
| QuerySavingsPlansInstance | `$.Data.Items[]` | array | Savings plans list |
| QueryResourcePackageInstances | `$.Data.Instances.Instance[]` | array | Resource packages list |
| QueryAccountTransactions | `$.Data.AccountTransactionsList` | object | Transaction records |
| QueryPrepaidCards | `$.Data.PrepaidCard[]` | array | Prepaid card list |
| QueryCashCoupons | `$.Data.CashCoupon[]` | array | Cash coupon list |

All bill/item arrays support pagination via `$.Data.TotalCount`, `$.Data.PageNum`, `$.Data.PageSize`.

## Quick Start

### What This Skill Does
This skill enables you to query and analyze Alibaba Cloud billing data — account balance, bills, orders, reservations, savings plans, resource packages, transactions, coupons — using the `aliyun` CLI (primary) or JIT Go SDK (fallback).

### Prerequisites
- [ ] `aliyun` CLI installed (or Go runtime for JIT fallback)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] RAM policy includes `bssapi:Query*` permissions

### Verify Setup
```bash
# Check CLI and billing permissions
aliyun bssopenapi QueryAccountBalance
```

### Your First Command
```bash
# Check account balance
aliyun bssopenapi QueryAccountBalance

# Monthly bill overview
aliyun bssopenapi QueryBillOverview --BillingCycle "2026-05"
```

### Next Steps
- [Core Concepts](references/core-concepts.md) — Understand billing architecture
- [Common Operations](#execution-flows-agent-readable) — Query bills, orders, savings
- [CLI Usage](references/cli-usage.md) — Complete CLI command map with JSON paths
- [Troubleshooting](references/troubleshooting.md) — Fix common errors
- [FinOps Best Practices](references/finops-best-practices.md) — Cost optimization runbooks

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| QueryAccountBalance | Check account balance | Low | None |
| QueryBillOverview | Monthly bill by product | Low | None |
| QueryBill | Bill details with filters | Low | None |
| QueryInstanceBill | Instance-level billing | Low | None |
| QuerySettleBill | Post-settlement bills (large datasets) | Low | None |
| QueryAccountBill | Bill by account/resource owner | Low | None |
| QuerySplitItemBill | Split/shared billing items | Low | None |
| QueryOrders + GetOrderDetail | Order list and details | Low | None |
| QueryRIUtilizationDetail | RI utilization analysis | Medium | None |
| QuerySavingsPlans* | Savings plans info and deduct logs | Medium | None |
| QueryResourcePackageInstances | Resource package status | Low | None |
| QueryAccountTransactions | Transaction history | Low | None |
| QueryPrepaidCards | Prepaid card inventory | Low | None |
| QueryCashCoupons | Voucher inventory and balance | Low | None |
| Cost Anomaly Detection | MoM cost comparison | Medium | None |
| Resource Expiry Warning | 30-day expiration check | Medium | None |
| FinOps Optimization | RI/SP coverage analysis | High | None |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-30 | Initial billing skill: 14 APIs + 3 FinOps patterns, dual-path execution, 14 error codes, Well-Architected five-pillar integration |

---

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI primary + SDK fallback) → Validate → Recover**. Do not skip phases.

**Preference hint:** CLI is the primary path for all billing queries. JIT Go SDK is used when Go-based data processing is needed or for complex multi-API pipelines.

### Common Pre-flight Checks (All Operations)

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI availability | `aliyun version 2>&1` | Exit code 0 | Document CLI install; redirect to [Prerequisites](#prerequisites) |
| Credentials | `test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"` | Both set | HALT; user configures env |
| Billing permission | `aliyun bssopenapi QueryAccountBalance 2>&1` | Valid JSON response (no NotAuthorized) | HALT; check RAM policy includes `bssapi:QueryAccountBalance` |

---

### Operation 1: QueryAccountBalance — 账户余额查询

**When to use:**
- Check available account balance
- Verify billing account health
- Pre-operation balance check before any cost-incurring activity

**What to expect:** Returns AvailableAmount, CreditAmount, Currency in one API call.

#### Execution — CLI (Primary Path)

```bash
# JSON output by default
BALANCE=$(aliyun bssopenapi QueryAccountBalance)
AVAILABLE=$(echo "$BALANCE" | jq -r '.Data.AvailableAmount')
CREDIT=$(echo "$BALANCE" | jq -r '.Data.CreditAmount')
CURRENCY=$(echo "$BALANCE" | jq -r '.Data.Currency')
echo "Balance: $AVAILABLE $CURRENCY (Credit: $CREDIT $CURRENCY)"
```

#### Execution — JIT Go SDK (Fallback)

See [references/api-sdk-usage.md](references/api-sdk-usage.md) for complete Go SDK client initialization.

```go
response, err := client.QueryAccountBalance()
if err != nil {
    panic(err)
}
available := tea.StringValue(response.Body.Data.AvailableAmount)
credit := tea.StringValue(response.Body.Data.CreditAmount)
currency := tea.StringValue(response.Body.Data.Currency)
fmt.Printf("Balance: %s %s (Credit: %s %s)\n", available, currency, credit, currency)
```

#### Post-execution Validation

1. Verify response contains `$.Data.AvailableAmount`
2. Validate Currency is expected (typically `CNY`)
3. Report balance to user in human-readable format

#### Failure Recovery

| Error pattern | Max retries | Agent Action | UX Feedback |
|--------------|-------------|--------------|-------------|
| `NotAuthorized` | 0 | HALT | `[ERROR] NotAuthorized: Verify RAM policy includes bssapi:QueryAccountBalance` |
| `Throttling.User` | 3, exponential | Retry with backoff | `Rate limited. Retrying in {backoff}s... (Attempt {current}/{max})` |
| `InternalError` | 3, 2s/4s/8s | Retry then HALT with RequestId | `[ERROR] InternalError: Server error. Retry or escalate with RequestId: {RequestId}` |

---

### Operation 2: QueryBillOverview — 账单总览

Gets monthly bill overview grouped by product. **Required parameter:** `BillingCycle` (YYYY-MM format).

#### Execution — CLI

```bash
# Monthly bill overview (default: all products)
aliyun bssopenapi QueryBillOverview --BillingCycle "{{user.billing_cycle}}"

# With product filter
# aliyun bssopenapi QueryBillOverview --BillingCycle "2026-05" --ProductCode "ecs"
```

#### Execution — SDK Fallback

```go
request := &bssopenapi.QueryBillOverviewRequest{
    BillingCycle: tea.String("2026-05"),
    ProductCode:  tea.String("ecs"), // optional
}
response, err := client.QueryBillOverview(request)
```

#### Post-execution Validation

1. Check `$.Data.Items.Item[]` exists and is non-empty
2. List top products sorted by `PretaxAmount` (desc)
3. Report total: sum of all `PretaxAmount`

#### Present to User

| Field | JSON Path | Notes |
|-------|-----------|-------|
| Product | `$.Data.Items.Item[].ProductCode` | Product identifier |
| Name | `$.Data.Items.Item[].ProductName` | Chinese name |
| Amount | `$.Data.Items.Item[].PretaxAmount` | Pre-tax amount (CNY) |
| BillingCycle | `$.Data.BillingCycle` | Confirmation of queried period |

#### Failure Recovery

| Error pattern | Agent Action |
|--------------|-------------|
| `InvalidParameter.BillingCycle` | FIX — use YYYY-MM format |
| `MissingParameter.BillingCycle` | FIX — add BillingCycle parameter |
| `NotAuthorized` | HALT — verify `bssapi:QueryBillOverview` permission |

---

### Operation 3: QueryBill — 账单明细

Gets detailed bill items with pagination. Supports ProductCode and SubscriptionType filters.

**Optional filters:** `ProductCode` (e.g., ecs, rds), `SubscriptionType` (Subscription/PayAsYouGo), `IsHideZeroCharge` (true/false).

**What to expect:** Paginated list with UsageStartTime, UsageEndTime, PretaxAmount, and resource identifiers.

#### Execution — CLI

```bash
# Bill details (paginated)
aliyun bssopenapi QueryBill \
  --BillingCycle "{{user.billing_cycle}}" \
  --PageNum 1 \
  --PageSize 100 \
  --ProductCode "{{user.product_code}}"

# Filter: PayAsYouGo ECS only
# aliyun bssopenapi QueryBill \
#   --BillingCycle "2026-05" \
#   --ProductCode "ecs" \
#   --SubscriptionType "PayAsYouGo" \
#   --IsHideZeroCharge true \
#   --PageNum 1 --PageSize 100
```

#### Execution — SDK Fallback

```go
request := &bssopenapi.QueryBillRequest{
    BillingCycle:     tea.String(billingCycle),
    PageNum:          tea.Int32(1),
    PageSize:         tea.Int32(100),
    ProductCode:      tea.String("ecs"),
    SubscriptionType: tea.String("PayAsYouGo"),
    IsHideZeroCharge: tea.Bool(true),
}
response, err := client.QueryBill(request)
```

#### Post-execution Validation

1. Verify `$.Data.TotalCount` for total records
2. Check `$.Data.BillingCycle` matches requested period
3. Paginate if `TotalCount > PageSize`
4. Present key billing fields in a table

#### Pagination

```bash
# Auto-paginate to fetch all records
TOTAL=$(echo "$RESPONSE" | jq '.Data.TotalCount')
TOTAL_PAGES=$(( (TOTAL + 99) / 100 ))
# Loop pages 1..TOTAL_PAGES
```

#### Failure Recovery

| Error pattern | Agent Action |
|--------------|-------------|
| `InvalidParameter.BillingCycle` | FIX — use YYYY-MM format |
| `InvalidParameter.PageSize` | FIX — reduce to ≤ 100 |
| `InvalidParameter.PageNum` | FIX — PageNum must be ≥ 1 |
| `Throttling.User` | RETRY — 3 attempts with exponential backoff |

---

### Operation 4: QueryInstanceBill — 实例账单

Instance-level billing grouped by `InstanceID`. Supports `IsBillingItem` (include sub-items).

#### Execution — CLI

```bash
aliyun bssopenapi QueryInstanceBill \
  --BillingCycle "2026-05" \
  --PageNum 1 \
  --PageSize 100 \
  --IsBillingItem false
```

#### Output Fields

| Field | JSON Path | Description |
|-------|-----------|-------------|
| Instance ID | `$.Data.Items.Item[].InstanceID` | Resource instance identifier |
| Product | `$.Data.Items.Item[].ProductCode` | Product code (ecs, rds, etc.) |
| Cost | `$.Data.Items.Item[].PretaxAmount` | Pre-tax amount |
| Billing Type | `$.Data.Items.Item[].BillingType` | SubscriptionType/UsageType |

---

### Operation 5: QuerySettleBill — 结算账单

Post-settlement bills for accounts with large billing data (> 50,000 entries). Same structure as QueryBill.

```bash
aliyun bssopenapi QuerySettleBill \
  --BillingCycle "2026-05" \
  --PageNum 1 \
  --PageSize 100
```

---

### Operation 6: QueryAccountBill — 账号账单

Bill grouped by resource owner account (useful for multi-account financial management).

```bash
aliyun bssopenapi QueryAccountBill \
  --BillingCycle "2026-05" \
  --PageNum 1 \
  --PageSize 20
```

---

### Operation 7: QuerySplitItemBill — 分账账单

Split/shared billing items with tag-based filtering. Supports `TagFilter`.

```bash
aliyun bssopenapi QuerySplitItemBill \
  --BillingCycle "2026-05" \
  --PageNum 1 \
  --PageSize 20
```

**Output:** `$.Data.Items.Item[]` with `SplitItemID`, `SplitItemName`, `Tag`, `PretaxAmount`.

---

### Operation 8: QueryOrders + GetOrderDetail

Query orders in a time range, then drill down to order detail.

**Timing note:** QueryOrders defaults to last 1 hour. Specify `CreateTimeStart`/`CreateTimeEnd` for broader ranges.

```bash
# Step 1: List orders
aliyun bssopenapi QueryOrders \
  --CreateTimeStart "2026-05-01T00:00:00Z" \
  --CreateTimeEnd "2026-05-31T23:59:59Z" \
  --PageNum 1 \
  --PageSize 20

# Step 2: Get order detail
ORDER_ID=$(echo "$ORDERS" | jq -r '.Data.OrderList.Order[0].OrderId')
aliyun bssopenapi GetOrderDetail --OrderId "$ORDER_ID"
```

**Output (OrderList):** `$.Data.OrderList.Order[]` with `OrderId`, `ProductCode`, `PaymentStatus`, `PaymentTime`, `PretaxAmount`.
**Output (Detail):** `$.Data` with full order configuration including `OriginalConfig` and `NewConfig`.

---

### Operation 9: QueryRIUtilizationDetail — RI预留实例利用率

Check Reserved Instance utilization to detect under-utilization or waste.

```bash
aliyun bssopenapi QueryRIUtilizationDetail \
  --PageNum 1 \
  --PageSize 20 \
  --DeductedCommodityCode "ecs"
```

**Output:** `$.Data.Items[]` with `RIInstanceId`, `InstanceSpec`, `DeductedInstanceId`, `RIUtilizationRatio`.

**FinOps trigger:** If `RIUtilizationRatio < 0.5` (50%), flag as under-utilized. Suggest modifying RI or releasing.

---

### Operation 10: QuerySavingsPlansInstance + QuerySavingsPlansDeductLog

List savings plans and view deduction logs.

```bash
# Step 1: List savings plans
aliyun bssopenapi QuerySavingsPlansInstance \
  --PageNum 1 \
  --PageSize 100

# Step 2: Deduction log for specific SP
SP_ID="{{output.sp_instance_id}}"
aliyun bssopenapi QuerySavingsPlansDeductLog \
  --InstanceId "$SP_ID" \
  --StartTime "2026-05-01T00:00:00Z" \
  --EndTime "2026-05-31T23:59:59Z"
```

**Output (Instance):** `$.Data.Items[]` with `InstanceId`, `SavingsType`, `CurrentPoolValue`, `Status`, `StartTime`, `EndTime`.
**FinOps trigger:** If `CurrentPoolValue < 100` → alert SP pool nearly depleted. Top up to avoid pay-as-you-go charges.

---

### Operation 11: QueryResourcePackageInstances — 资源包查询

List all resource packages with status, remaining amounts, and expiration.

```bash
aliyun bssopenapi QueryResourcePackageInstances \
  --PageNum 1 \
  --PageSize 100
```

**Output:** `$.Data.Instances.Instance[]` with `InstanceId`, `PackageType`, `Status`, `TotalAmount`, `RemainingAmount`, `ExpiryTime`.

**FinOps trigger:** If `ExpiryTime` within 30 days → alert user to renew or evaluate decommissioning.

---

### Operation 12: QueryAccountTransactions — 交易流水

Transaction history including payments, refunds, deductions.

```bash
aliyun bssopenapi QueryAccountTransactions \
  --PageNum 1 \
  --PageSize 20
```

**Output:** `$.Data.AccountTransactionsList` with `TransactionNumber`, `Amount`, `Balance`, `TransactionChannel`, `TransactionTime`.

---

### Operation 13: QueryPrepaidCards — 储值卡

List prepaid cards with balance and expiration.

```bash
aliyun bssopenapi QueryPrepaidCards
```

**Output:** `$.Data.PrepaidCard[]` with `PrepaidCardId`, `NominalValue`, `Balance`, `Status`, `ExpiryTime`.

---

### Operation 14: QueryCashCoupons — 代金券

List available vouchers/coupons.

```bash
aliyun bssopenapi QueryCashCoupons
```

**Output:** `$.Data.CashCoupon[]` with `CashCouponId`, `NominalValue`, `Balance`, `Status`, `EffectiveTime`, `ExpiryTime`.

---

### FinOps Operation 15: Cost Anomaly Detection — 费用异常检测

Compare current month vs last month; flag >30% increase.

#### Execution

```bash
#!/bin/bash
CURRENT_MONTH=$(date +%Y-%m)
LAST_MONTH=$(date -v-1m +%Y-%m 2>/dev/null || date -d '1 month ago' +%Y-%m)

CURRENT_TOTAL=$(aliyun bssopenapi QueryBillOverview --BillingCycle "$CURRENT_MONTH" | jq '[.Data.Items.Item[] | select(.PretaxAmount != null) | .PretaxAmount | tonumber] | add // 0')
LAST_TOTAL=$(aliyun bssopenapi QueryBillOverview --BillingCycle "$LAST_MONTH" | jq '[.Data.Items.Item[] | select(.PretaxAmount != null) | .PretaxAmount | tonumber] | add // 0')

if [ "$LAST_TOTAL" != "0" ]; then
  CHANGE_PCT=$(python3 -c "print(f'{($CURRENT_TOTAL/$LAST_TOTAL - 1) * 100:.1f}'){")
  if (( $(echo "$CHANGE_PCT > 30" | bc -l) )); then
    echo "[ALERT] Cost anomaly: ${CHANGE_PCT}% MoM change"
    aliyun bssopenapi QueryBillOverview --BillingCycle "$CURRENT_MONTH" | jq -r '.Data.Items.Item[] | [.ProductCode, .PretaxAmount] | @tsv' | sort -t$'\t' -k2 -rn | head -10
  fi
fi
```

**Alert levels:**
- > 30% increase → P1 Alert (review product breakdown)
- > 50% increase → P0 Alert (immediate investigation)
- New product with > 1000 CNY → P1 Alert

---

### FinOps Operation 16: Resource Expiration Warning — 资源到期预警

Check resources (packages, SP, RI) expiring within 30 days.

```bash
#!/bin/bash
# Resource packages expiring within 30 days
aliyun bssopenapi QueryResourcePackageInstances --PageNum 1 --PageSize 100 | jq -r '
  .Data.Instances.Instance[] |
  select(.Status == "Valid") |
  select(
    (((.ExpiryTime | strptime("%Y-%m-%dT%H:%M:%SZ") | mktime) - now) / 86400) <= 30
  ) |
  "\\(.InstanceId) (\\(.PackageType)): \\(.RemainingAmount)/\\(.TotalAmount) remaining, expires \\(.ExpiryTime)"
'
```

**Alert:** Any resource expiring within 30 days → P1 Alert. Within 7 days → P0 Alert.

---

### FinOps Operation 17: RI/SCU Coverage Gap Detection

Check if pay-as-you-go spend could be covered by RI or SCU.

```bash
# Coverage check
COVERAGE=$(aliyun bssopenapi DescribeResourceCoverageTotal)
COV_PCT=$(echo "$COVERAGE" | jq -r '.Data.TotalCoverage.CoveragePercentage // "0"')
if (( $(echo "$COV_PCT < 70" | bc -l) )); then
  echo "[WARN] RI/SCU coverage: ${COV_PCT}% — below 70% threshold"
fi
```

**Recommendation flow:**
1. Coverage < 70% → Check `DescribeResourceCoverageDetail` per product
2. Identify uncovered RI-eligible services (ECS, RDS, etc.)
3. Match instance families and regions
4. Purchase RI via BSSOpenApi `CreateInstance` or console

---

## Prerequisites

1. **Install `aliyun` CLI** (primary execution path — static Go binary, no runtime dependencies):

   ```bash
   # Official installer (auto-detects OS and architecture)
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"

   # Or Homebrew (macOS)
   brew install aliyun-cli
   ```

2. **Bootstrap Go runtime** (for JIT SDK fallback — only needed if CLI does not support operation):

   ```bash
   if ! command -v go &> /dev/null; then
       OS=$(uname -s | tr '[:upper:]' '[:lower:]')
       ARCH=$(uname -m)
       [ "$ARCH" = "x86_64" ] && ARCH="amd64"
       [ "$ARCH" = "aarch64" ] && ARCH="arm64"
       mkdir -p /tmp/go-runtime
       curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
       export PATH="/tmp/go-runtime/go/bin:$PATH"
       export GOPATH="/tmp/go-workspace"
       export GOCACHE="/tmp/go-cache"
       export GOMODCACHE="/tmp/go-modcache"
       export GOPROXY="https://goproxy.cn,direct"
   fi
   go version
   ```

3. **Configure Credentials** — Environment variables (recommended for Agent execution):

   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"  # billing default
   ```

> **Security:** Never commit `.env` to version control (already in `.gitignore`). All credentials use `{{env.*}}` placeholders in generated Skills — never real values.

## Reference Directory

- [Core Concepts](references/core-concepts.md) — Billing architecture, limits, data freshness
- [CLI Usage](references/cli-usage.md) — Complete command map, JSON paths, pagination, cost anomaly scripts
- [API & SDK Usage](references/api-sdk-usage.md) — Go SDK initialization, request/response patterns, JIT workflow
- [Troubleshooting Guide](references/troubleshooting.md) — Error taxonomy (14 codes), diagnostic order, recovery patterns
- [Monitoring & Alerts](references/monitoring.md) — Cost anomaly detection, expiry monitoring, RI/SP alerts
- [Integration](references/integration.md) — Cross-skill delegation matrix, RAM policy templates, environment setup
- [Well-Architected Assessment](references/well-architected-assessment.md) — Five-pillar assessment: Security, Stability, Cost, Efficiency, Performance
- [FinOps Best Practices](references/finops-best-practices.md) — Executable FinOps patterns: anomaly detection, expiry warning, RI/SP optimization, budget alerts, account health checks

## Operational Best Practices

- **Least privilege:** RAM policies scoped to `bssapi:Query*` for read-only billing access. NEVER use `AdministratorAccess`.
- **Credential rotation:** Rotate AccessKey pairs every 90 days.
- **Data freshness:** Current month bills are preliminary; finalized by day 3-5 of the following month. RI data has ~2h delay.
- **Pagination:** Always check `TotalCount` against `PageSize`; implement automatic pagination loops.
- **Cost optimization:** Run FinOps patterns (anomaly detection, expiry warning, coverage check) on a schedule.

## Token Efficiency Guidelines (P0)

Generated skills MUST follow these 6 rules. See meta-skill SKILL.md for detailed examples.

### TE-1: API Query > Static Tables
Use API commands instead of hardcoding version/port/quota tables.
### TE-2: No docstrings in code
Inline comments only. No function-level docstring.
### TE-3: Compact error tables
`| Error Code | Agent Action |`
### TE-4: Centralized JSON paths
File-top comment block; one per resource type (see cli-usage.md).
### TE-5: YAML anchors in example-config.yaml
Use `&env` to eliminate repeated environment fields.
### TE-6: Eliminate cross-file duplicate flows
SKILL.md already has full flow, no Complete Workflow in config or SDK files.
