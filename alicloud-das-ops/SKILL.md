---
name: alicloud-das-ops
description: >-
  Use this skill when a user needs to diagnose why an Alibaba Cloud database
  is slow, investigate connection or session issues, analyze Redis/Tair memory
  usage, review disk space, find deadlocks, or set up automatic protections
  like SQL throttling and auto-scaling. Also covers registering databases for
  DAS monitoring, subscribing to event notifications, and reviewing
  DAS-triggered events. Trigger on any database performance problem —
  slowness, connection spikes, disk alerts, or unexplained degradation — even
  without mentioning DAS, 数据库自治服务, or HDM. Do NOT use for creating,
  deleting, or modifying database instances or their configurations (delegate
  to RDS, PolarDB, Redis, MongoDB, or other engine-specific skills) or for
  billing, account, or RAM permission tasks.
license: MIT
compatibility: >-
  Alibaba Cloud Go SDK (github.com/alibabacloud-go/das-20200116/v5/client),
  Go 1.21+ runtime (for JIT SDK fallback), valid AccessKey pair, network
  access to das.cn-shanghai.aliyuncs.com (DAS is single-region service).
metadata:
  author: alicloud
  version: "1.2.0"
  last_updated: "2026-06-11"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "DAS/2020-01-16"
  api_doc_url: "https://help.aliyun.com/zh/das/developer-reference/api-reference/"
  openapi_explorer: "https://next.api.aliyun.com/api/DAS/2020-01-16/overview"
  cli_applicability: sdk-only
  cli_support_evidence: >-
    DAS is NOT supported by aliyun CLI as of 2026-05-14.
    Verified via https://help.aliyun.com/zh/das/developer-reference/call-api-operations
    and `aliyun --help` product list (DAS absent).
    All operations require JIT Go SDK fallback.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
  notes: >-
    DAS endpoint is fixed to das.cn-shanghai.aliyuncs.com (public) or
    das.vpc-proxy.aliyuncs.com (VPC). Region parameter in SDK calls is
    still required (set to cn-shanghai) but service is logically global.
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud DAS (Database Autonomy Service) Operations Skill

## Overview

Database Autonomy Service (DAS, formerly HDM) is an AI-driven database
operations and maintenance platform on Alibaba Cloud. It provides
**full-lifecycle autonomous capabilities**: anomaly detection, root-cause
diagnosis, optimization recommendations, automatic SQL throttling, auto-scaling,
and intelligent O&M reports.

This skill is an **operational runbook** for agents: explicit scope, credential
rules, pre-flight checks, JIT Go SDK execution flows (CLI does not support
DAS), response validation, and failure recovery. **Do not use the web console
as the primary agent execution path** in `SKILL.md`.

### CLI applicability (repository policy)

- **`cli_applicability: sdk-only`**: Official `aliyun` CLI does **not** expose
  DAS. **Omit** `references/cli-usage.md`. All operations use **JIT Go SDK
  fallback** exclusively.
- The Go SDK package is `github.com/alibabacloud-go/das-20200116/v5/client`.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud DAS" OR "数据库自治服务" OR "HDM"
- Task involves CRUD or lifecycle operations on **DAS-managed database
  instances** (register, inspect, diagnose, optimize, throttle, scale)
- Task keywords:
  - instance registration / 接入实例 / AddHDMInstance
  - inspection / 巡检评分 / GetInstanceInspections
  - SQL diagnosis / SQL诊断 / CreateDiagnosticReport
  - cache analysis / 缓存分析 / CreateCacheAnalysisJob
  - deadlock analysis / 死锁分析 / CreateLatestDeadLockAnalysis
  - session management / 实例会话 / CreateKillInstanceSessionTask
  - space analysis / 空间分析 / GetSpaceSummary
  - SQL throttling / SQL限流 / CreateSqlLimitTask
  - SQL concurrency control / SQL并发控制 / EnableSqlConcurrencyControl, DisableSqlConcurrencyControl, DisableAllSqlConcurrencyControlRules
  - SQL concurrency control rules query / SQL限流规则查询 / GetRunningSqlConcurrencyControlRules, GetSqlConcurrencyControlRulesHistory
  - SQL concurrency control keywords / SQL限流关键词生成 / GetSqlConcurrencyControlKeywordsFromSqlText
  - auto-scaling / 自动弹性伸缩 / SetAutoScalingConfig
  - event subscription / 事件通知 / SetEventSubscription
  - autonomous event / 自治事件 / GetAutonomousNotifyEventsInRange
  - SQL insight / SQL洞察 / DescribeSqlLogStatistic
  - query governance / 查询治理 / GetQueryOptimizeData
  - index advice / 索引诊断 / GetQueryOptimizeExecErrorStats
  - performance insight / 性能洞察 / GetPfsSqlSamples
  - DAS Agent / DAS智能助手 / DAS Agent chat
- User asks to deploy, configure, troubleshoot, or monitor DAS **via API,
  SDK, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to:
  `alicloud-billing-ops` (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops`
  (when present)
- Task is about **creating or deleting the underlying database engine
  instances** (e.g., creating an RDS MySQL instance) → delegate to:
  `alicloud-rds-ops`, `alicloud-polar-mysql-ops`, `alicloud-polar-postgresql-ops`, `alicloud-polar-oracle-ops`, or the engine-specific skill
- Task is about **DAS Agent chat / LLM Q&A** → this skill covers API-level
  DAS Agent operations (e.g., querying usage); conversational LLM features
  are console-only and out of scope for API automation
- User insists on **console-only** flows with no API → state limitation;
  do not invent undocumented HTTP steps

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

## Variable Convention (Agent-Readable)

Structured placeholders reduce injection ambiguity and unsafe prompts:

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse. For DAS SDK calls, always pass `cn-shanghai` as the service region regardless of instance location |
| `{{user.instance_id}}` | User-supplied database instance ID | Ask once; reuse (e.g., `rm-2ze8g2am97624****`) |
| `{{user.engine}}` | Database engine type | Ask when required (e.g., `MySQL`, `PostgreSQL`, `Redis`, `MongoDB`, `SQLServer`, `PolarDB`) |
| `{{user.node_id}}` | Node ID for cluster instances | Ask when required (PolarDB, PolarDB-X) |
| `{{output.resource_id}}` | From last API JSON response | Parse per OpenAPI spec for this operation |
| `{{output.task_id}}` | Async task ID from create operations | Parse per OpenAPI spec; used for polling |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response
  shapes. DAS uses **RPC-style** APIs.
- **Endpoint:** `das.cn-shanghai.aliyuncs.com` (public) or
  `das.vpc-proxy.aliyuncs.com` (VPC). The SDK endpoint MUST be set explicitly
  because DAS is not in the default shared endpoint map of some SDK versions.
- **Region:** SDK calls MUST specify `RegionId: "cn-shanghai"` regardless of
  the target database instance's actual region.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / `message` fields per
  spec. Common DAS error codes:
  - `InvalidDBInstanceId.NotFound` — Instance not found or not registered in DAS
  - `InvalidParameter` — Missing or malformed parameter
  - `OperationDenied.InstanceStatus` — Instance status does not allow the operation
  - `Throttling` — Rate limit exceeded; implement exponential backoff
  - `InsufficientBalance` — Account balance insufficient for Pro features
- **Timestamps:** DAS returns Unix timestamps in **milliseconds** (e.g.,
  `expireTime: 1924963200000`). Convert to ISO 8601 when presenting to users.
- **Idempotency:** Most DAS create operations (e.g., `CreateDiagnosticReport`)
  generate new resources each time; document that duplicate calls produce
  distinct reports/tasks. `AddHDMInstance` is idempotent for the same
  `InstanceId` — repeated registration returns success without side effects.

### DAS Standard Response Structure

Nearly all DAS API responses follow this five-element envelope:

```json
{
  "Code": 200,
  "Message": "Successful",
  "RequestId": "B6D17591-B48B-4D31-9CD6-9B9796B2****",
  "Data": { ... },
  "Success": true
}
```

| Field | Type | Meaning | Agent Action |
|-------|------|---------|--------------|
| `Code` | integer (int64) | HTTP-like status code; `200` indicates success | Verify `Code == 200` before parsing `Data` |
| `Message` | string | Human-readable result; `"Successful"` on success | Log on failure; do not rely on for branching |
| `RequestId` | string | Unique request identifier for tracing | Include in error reports to Alibaba Cloud support |
| `Data` | any (object, array, boolean, string) | Payload; shape varies by operation | Parse per operation schema |
| `Success` | boolean | `true` when the business operation succeeded | Use as primary success gate |

> **Important:** `Code == 200` does **not** always mean business success.
> Always check `Success == true` before consuming `Data`.
> Some operations return `Code: 200` with `Success: false` and a descriptive
> `Message` (e.g., instance already in target state).

> **Response fields**: See [api-doc-mapping.md](references/api-doc-mapping.md) for operation-to-SDK-type mapping. Each operation section below documents the specific `$.Data` shape to parse.

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| AddHDMInstance | — | `registered` (implied) | N/A (sync) | 30s |
| CreateDiagnosticReport | — | `FINISHED` or `FAILED` | 5s | 300s |
| CreateCacheAnalysisJob | — | `SUCCESS` or `FAILED` | 10s | 600s |
| CreateLatestDeadLockAnalysis | — | `SUCCESS` or `FAILED` | 5s | 120s |
| CreateKillInstanceSessionTask | — | `completed` (implied) | N/A (async fire-and-forget) | 30s |
| CreateSqlLimitTask | — | `ACTIVE` or `EXPIRED` | 5s | 60s |
| EnableSqlConcurrencyControl | — | `Open` (implied) | N/A (sync) | 30s |
| DisableSqlConcurrencyControl | `Open` | `Closed` | N/A (sync) | 30s |
| DisableAllSqlConcurrencyControlRules | `Open` | `Closed` | N/A (sync) | 30s |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.2.0 | 2026-06-11 | Token efficiency optimization: consolidated operation sections to compact table format (TE-3/TE-6), moved prompt-templates.md to advanced/ (TE-7), removed Response Field Table (deduped via api-doc-mapping.md), compacted governance/adversarial-review.md and cross-skill-collaboration.md, removed redundant API doc links, condensed integration.md engine table |
| 1.1.0 | 2026-06-01 | Added SQL concurrency control operations: EnableSqlConcurrencyControl, DisableSqlConcurrencyControl, DisableAllSqlConcurrencyControlRules, GetRunningSqlConcurrencyControlRules, GetSqlConcurrencyControlRulesHistory, GetSqlConcurrencyControlKeywordsFromSqlText |
| 1.0.0 | 2026-05-14 | Initial DAS ops skill with SDK-only execution, covering instance registration, inspection, diagnosis, cache analysis, deadlock analysis, session management, space analysis, SQL throttling, event subscription, autonomous events, SQL insight, and query governance |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (JIT Go SDK) → Validate → Recover**.
Do not skip phases.

### Global Pre-flight Checks (Run Before Any DAS Operation)

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SDK / deps | `go version` | >= 1.21 | Document Go install; attempt JIT download of 1.24+ |
| SDK package | `go get github.com/alibabacloud-go/das-20200116/v5/client` | No import error | Document dependency resolution steps |
| Credentials | `os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")` and `SECRET` | Non-empty | HALT; user configures env |
| Region | Verify `ALIBABA_CLOUD_REGION_ID` is set | Non-empty | HALT; user configures env |
| Network | `curl -I https://das.cn-shanghai.aliyuncs.com` | HTTP 403 or 400 (not timeout) | Warn about network / proxy issues |

### Shared SDK Client Initialization Pattern

All JIT Go SDK examples below assume the following shared initialization.
Generate this once per workspace and reuse across operations:

```go
// /tmp/aliyun-sdk-workspace/das_client.go
package main
import (
    "encoding/json"; "fmt"; "os"; "strconv"
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    das "github.com/alibabacloud-go/das-20200116/v5/client"
    "github.com/alibabacloud-go/tea/tea"
)
func newDASClient() (*das.Client, error) {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String(os.Getenv("DAS_ENDPOINT")),
    }
    if config.Endpoint == nil || *config.Endpoint == "" {
        config.Endpoint = tea.String("das.cn-shanghai.aliyuncs.com")
    }
    return das.NewClient(config)
}
func printResponse(body interface{}) { b, _ := json.MarshalIndent(body, "", "  "); fmt.Println(string(b)) }
func main() {}
```

Execute (once per workspace):
```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script 2>/dev/null || true
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/das-20200116/v5/client
```

> **Note:** Set `DAS_ENDPOINT=das.vpc-proxy.aliyuncs.com` when running inside an Alibaba Cloud VPC.

> **Execution pattern:** Each operation below shows the Go request struct and its `client.{Operation}(request)` call. The `client, err := newDASClient()` and `printResponse(response.Body)` boilerplate is omitted for brevity — use the shared pattern above.

---

### Operation: Register Instance (AddHDMInstance)

> **Safety Note:** Registering a production instance enables DAS monitoring agents and may introduce minor performance overhead (< 1% CPU). Inform the user when acting on production instances.

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance exists (engine Describe API) → HALT if not found. Engine support check. Already registered via `GetInstanceInspections` → skip (idempotent) |
| **Go** | `request := &das.AddHDMInstanceRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID")), Engine: tea.String(os.Getenv("ENGINE"))}` → `client.AddHDMInstance(request)` |
| **Validate** | `$.Data` = `true`. If `false`, inspect `$.Message`. Cross-check via `GetInstanceInspections` |
| **Recover** | `InvalidDBInstanceId.NotFound` → verify ID; `OperationDenied.InstanceStatus` → wait; `Throttling` → backoff 1s,2s,4s,8s |

```bash
export INSTANCE_ID="{{user.instance_id}}" ENGINE="{{user.engine}}" DAS_ENDPOINT="das.cn-shanghai.aliyuncs.com"
cd /tmp/aliyun-sdk-workspace && go run ./main.go
```

---

### Operation: Get Inspection Score (GetInstanceInspections)

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered via trial call → not `NotFound` |
| **Go** | `request := &das.GetInstanceInspectionsRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.GetInstanceInspections(request)` |
| **Validate** | `$.Data.score` (0-100). `score < 60` → flag critical, suggest `CreateDiagnosticReport` |
| **Recover** | `InvalidDBInstanceId.NotFound` → run `AddHDMInstance` first |

---

### Operation: Create Diagnostic Report (CreateDiagnosticReport)

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered |
| **Go** | `request := &das.CreateDiagnosticReportRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.CreateDiagnosticReport(request)` |
| **Validate** | Parse `$.Data` for report ID. Poll `DescribeDiagnosticReportList` until `FINISHED` (5s interval, 300s max) |
| **Recover** | `OperationDenied.InstanceStatus` → wait; timeout >300s → suggest retry off-peak |

---

### Operation: Create Cache Analysis Job (CreateCacheAnalysisJob)

| Step | Detail |
|------|--------|
| **Pre-flight** | Engine = `Redis` or `Tair`. Instance registered |
| **Go** | `request := &das.CreateCacheAnalysisJobRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.CreateCacheAnalysisJob(request)` |
| **Validate** | `$.Data` = `true`. Poll `DescribeCacheAnalysisJob` until `SUCCESS` or `FAILED` (10s interval, 600s max) |
| **Recover** | Job fails → check `$.Data.errorMessage` |

---

### Operation: Create Deadlock Analysis (CreateLatestDeadLockAnalysis)

| Step | Detail |
|------|--------|
| **Pre-flight** | Engine = `MySQL`, `PolarDB`, `PolarDB-X`. Instance registered |
| **Go** | `request := &das.CreateLatestDeadLockAnalysisRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID")), NodeId: tea.String(os.Getenv("NODE_ID"))}` → `client.CreateLatestDeadLockAnalysis(request)` |
| **Validate** | `$.Data` = `true`. Poll `GetDeadLockHistory` to confirm new entry (5s interval, 120s max) |
| **Recover** | No recent deadlock → inform user |

---

### Operation: Kill Instance Session (CreateKillInstanceSessionTask)

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered. User provides session IDs. **Safety gate** — present target sessions, require confirmation |
| **Go** | `request := &das.CreateKillInstanceSessionTaskRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.CreateKillInstanceSessionTask(request)` |
| **Validate** | `$.Data` = `true`. Re-query `GetSessionList` to verify target sessions gone |
| **Recover** | Session already closed → inform; `OperationDenied.InstanceStatus` → wait |

---

### Operation: Get Space Summary (GetSpaceSummary)

| Step | Detail |
|------|--------|
| **Go** | `request := &das.GetSpaceSummaryRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.GetSpaceSummary(request)` |
| **Validate** | `$.Data.totalSize` (bytes). Breakdown: `dataSize`, `indexSize`, `freeSize`. Alert if usage >85% |

---

### Operation: Create SQL Limit Task (CreateSqlLimitTask)

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered. User provides SQL pattern. **Safety gate** — confirm limit params |
| **Go** | `request := &das.CreateSqlLimitTaskRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.CreateSqlLimitTask(request)` |
| **Validate** | `$.Data` = `true`. Query `DescribeSqlLimitTasks` to confirm `ACTIVE` status (5s interval, 60s max) |
| **Recover** | `InvalidParameter` → verify SQL pattern |

---

### Operation: Enable SQL Concurrency Control (EnableSqlConcurrencyControl)

> **Engine:** Only `MySQL`, `PolarDB`.

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered. Engine check. SQL keywords from user or `GetSqlConcurrencyControlKeywordsFromSqlText`. **Safety gate** — confirm `MaxConcurrency`, `ConcurrencyControlTime` |
| **Go** | `maxConcurrency, _ := strconv.ParseInt(os.Getenv("MAX_CONCURRENCY"), 10, 64); controlTime, _ := strconv.ParseInt(os.Getenv("CONTROL_TIME"), 10, 64)` → `request := &das.EnableSqlConcurrencyControlRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID")), SqlType: tea.String(os.Getenv("SQL_TYPE")), MaxConcurrency: tea.Int64(maxConcurrency), SqlKeywords: tea.String(os.Getenv("SQL_KEYWORDS")), ConcurrencyControlTime: tea.Int64(controlTime)}` → `client.EnableSqlConcurrencyControl(request)` |
| **Validate** | `$.Code`=200, `$.Success`=true. Confirm rule appears via `GetRunningSqlConcurrencyControlRules` with `Status=="Open"` |
| **Recover** | `InvalidParams` → verify format; `NoPermission` → check RAM policy |

```bash
export INSTANCE_ID="{{user.instance_id}}" SQL_TYPE="SELECT" SQL_KEYWORDS="call~open~api~test" MAX_CONCURRENCY=3 CONTROL_TIME=300 DAS_ENDPOINT="das.cn-shanghai.aliyuncs.com"
cd /tmp/aliyun-sdk-workspace && go run ./main.go
```

---

### Operation: Disable SQL Concurrency Control (DisableSqlConcurrencyControl)

| Step | Detail |
|------|--------|
| **Pre-flight** | Rule exists via `GetRunningSqlConcurrencyControlRules`. **Safety gate** — confirm `ItemId` with user |
| **Go** | `itemId, _ := strconv.ParseInt(os.Getenv("ITEM_ID"), 10, 64); request := &das.DisableSqlConcurrencyControlRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID")), ItemId: tea.Int64(itemId)}` → `client.DisableSqlConcurrencyControl(request)` |
| **Validate** | `$.Code`=200, `$.Success`=true. Confirm rule absent via `GetRunningSqlConcurrencyControlRules` |
| **Recover** | `InvalidParams` → verify `ItemId`; `NoPermission` → check RAM policy |

```bash
export INSTANCE_ID="{{user.instance_id}}" ITEM_ID="{{output.item_id}}" DAS_ENDPOINT="das.cn-shanghai.aliyuncs.com"
cd /tmp/aliyun-sdk-workspace && go run ./main.go
```

---

### Operation: Disable All SQL Concurrency Control Rules (DisableAllSqlConcurrencyControlRules)

> **Safety Gate:** Batch destructive action. Present all running rules from `GetRunningSqlConcurrencyControlRules`, require user confirmation.

| Step | Detail |
|------|--------|
| **Pre-flight** | `GetRunningSqlConcurrencyControlRules` → `Total > 0`. **Safety gate** — present summary, confirm |
| **Go** | `request := &das.DisableAllSqlConcurrencyControlRulesRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.DisableAllSqlConcurrencyControlRules(request)` |
| **Validate** | `$.Code`=200, `$.Success`=true. Confirm `Total==0` via `GetRunningSqlConcurrencyControlRules` |
| **Recover** | `InvalidParams` → verify ID; `NoPermission` → check RAM policy |

---

### Operation: Get Running SQL Concurrency Control Rules (GetRunningSqlConcurrencyControlRules)

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered |
| **Go** | `request := &das.GetRunningSqlConcurrencyControlRulesRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID")), PageNo: tea.Int32(1), PageSize: tea.Int32(10)}` → `client.GetRunningSqlConcurrencyControlRules(request)` |
| **Validate** | `$.Data.Total` (count). `$.Data.List.runningRules[]` — extract `ItemId`, `SqlType`, `SqlKeywords`, `MaxConcurrency`, `ConcurrencyControlTime`, `StartTime`, `Status`, `KeywordsHash` |
| **Recover** | `InvalidParams` → verify pagination; `NoPermission` → check RAM policy |

---

### Operation: Get SQL Concurrency Control Rules History (GetSqlConcurrencyControlRulesHistory)

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered |
| **Go** | `request := &das.GetSqlConcurrencyControlRulesHistoryRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID")), PageNo: tea.Int32(1), PageSize: tea.Int32(10)}` → `client.GetSqlConcurrencyControlRulesHistory(request)` |
| **Validate** | `$.Data.Total` (count). `$.Data.List.rules[]` — extract `ItemId`, `SqlType`, `SqlKeywords`, `MaxConcurrency`, `ConcurrencyControlTime`, `StartTime`, `Status` (Open/Closed), `KeywordsHash`, `UserId` |
| **Recover** | `InvalidParams` → verify pagination; `NoPermission` → check RAM policy |

---

### Operation: Get Keywords From SQL Text (GetSqlConcurrencyControlKeywordsFromSqlText)

> **Note:** Returned keywords are based on normalized SQL. To throttle a specific param value, append it with `~`. E.g., SQL `SELECT * FROM test WHERE name = 'das'` → API returns `SELECT~FROM~test~WHERE~name`; to throttle `name='das'` → `SELECT~FROM~test~WHERE~name~das`.

| Step | Detail |
|------|--------|
| **Pre-flight** | User provides SQL text. Instance registered |
| **Go** | `request := &das.GetSqlConcurrencyControlKeywordsFromSqlTextRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID")), SqlText: tea.String(os.Getenv("SQL_TEXT"))}` → `client.GetSqlConcurrencyControlKeywordsFromSqlText(request)` |
| **Validate** | `$.Data` = `~`-separated keyword string. Present to user for confirmation before `EnableSqlConcurrencyControl` |
| **Recover** | `InvalidParams` → verify SQL text; `NoPermission` → check RAM policy |

```bash
export INSTANCE_ID="{{user.instance_id}}" SQL_TEXT="SELECT * FROM orders WHERE status = 'pending'" DAS_ENDPOINT="das.cn-shanghai.aliyuncs.com"
cd /tmp/aliyun-sdk-workspace && go run ./main.go
```

---

### Operation: Configure Event Subscription (SetEventSubscription)

| Step | Detail |
|------|--------|
| **Go** | `request := &das.SetEventSubscriptionRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.SetEventSubscription(request)` |
| **Validate** | `$.Data` = `true`. Verify via `GetEventSubscription` |

---

### Operation: Query Autonomous Events (GetAutonomousNotifyEventsInRange)

| Step | Detail |
|------|--------|
| **Go** | `request := &das.GetAutonomousNotifyEventsInRangeRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID")), StartTime: tea.Int64(startTimeMs), EndTime: tea.Int64(endTimeMs)}` → `client.GetAutonomousNotifyEventsInRange(request)` |
| **Validate** | `$.Data[]` — parse `eventId`, `eventType`, `eventStatus`, `startTime` |

---

### Operation: Get Autonomous Event Content (GetAutonomousNotifyEventContent)

| Step | Detail |
|------|--------|
| **Go** | `request := &das.GetAutonomousNotifyEventContentRequest{RegionId: tea.String("cn-shanghai"), EventId: tea.String(os.Getenv("EVENT_ID"))}` → `client.GetAutonomousNotifyEventContent(request)` |
| **Validate** | `$.Data` — root cause, actions taken |

---

### Operation: Query SQL Insight Statistics (DescribeSqlLogStatistic)

| Step | Detail |
|------|--------|
| **Pre-flight** | DAS Pro enabled via `GetDasProServiceUsage` |
| **Go** | `request := &das.DescribeSqlLogStatisticRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.DescribeSqlLogStatistic(request)` |
| **Validate** | `$.Data` — SQL execution stats, slow query trends, error rates |

---

### Operation: Query DAS Pro Usage (GetDasProServiceUsage)

| Step | Detail |
|------|--------|
| **Go** | `request := &das.GetDasProServiceUsageRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.GetDasProServiceUsage(request)` |
| **Validate** | `$.Data.storageUsed` (bytes), `$.Data.storageFreeQuotaInMB` (MB). Alert if quota near limit. Parse `$.Data.expireTime` (Unix ms) |

---

### Operation: List Instance Sessions (GetSessionList)

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered |
| **Go** | `request := &das.GetSessionListRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.GetSessionList(request)` |
| **Validate** | `$.Data.sessionList[]` — `sessionId`, `user`, `host`, `db`, `command`, `time`, `state`, `info`. Present summary before kill |
| **Recover** | `InvalidDBInstanceId.NotFound` → register first; empty list → no active sessions |

---

### Operation: List SQL Limit Tasks (DescribeSqlLimitTasks)

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered |
| **Go** | `request := &das.DescribeSqlLimitTasksRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.DescribeSqlLimitTasks(request)` |
| **Validate** | `$.Data[]` — `taskId`, `sqlKeywords`, `maxConcurrency`, `status` (ACTIVE/EXPIRED), `createTime` |
| **Recover** | `InvalidDBInstanceId.NotFound` → register first |

---

### Operation: Get Auto-Scaling Config (GetAutoScalingConfig)

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered |
| **Go** | `request := &das.GetAutoScalingConfigRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.GetAutoScalingConfig(request)` |
| **Validate** | `$.Data` — `enableAutoScaling`, `maxStorage`, `maxSpecification`, `scalingPolicies` |
| **Recover** | Config not found → auto-scaling may not be enabled |

---

### Operation: Configure Auto-Scaling (SetAutoScalingConfig)

> **Safety Gate:** May trigger instance restart/connection flash. Confirm on production instances.

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered. Engine support (`MySQL`, `PostgreSQL`, `PolarDB`). DAS Pro enabled |
| **Go** | `request := &das.SetAutoScalingConfigRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.SetAutoScalingConfig(request)` |
| **Validate** | `$.Data` = `true`. Verify via `GetAutoScalingConfig` or autonomous events |
| **Recover** | `OperationDenied.InstanceStatus` → wait; `InvalidParameter` → verify limits |

---

### Operation: Query Governance Data (GetQueryOptimizeData)

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered. Engine support (`MySQL`, `PostgreSQL`, `PolarDB`) |
| **Go** | `request := &das.GetQueryOptimizeDataRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID"))}` → `client.GetQueryOptimizeData(request)` |
| **Validate** | `$.Data` — query stats, slow query list, execution plans |

---

### Operation: Query Performance Insight (GetPfsSqlSamples)

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered. DAS Pro enabled |
| **Go** | `request := &das.GetPfsSqlSamplesRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID")), StartTime: tea.Int64(startTimeMs), EndTime: tea.Int64(endTimeMs)}` → `client.GetPfsSqlSamples(request)` |
| **Validate** | `$.Data` — SQL samples, wait events, execution timelines |

---

### Operation: Network Connectivity Diagnosis (GetDBInstanceConnectivityDiagnosis)

> **Security:** If `DbPassword` is required, use a temp test account. NEVER use production admin credentials.

| Step | Detail |
|------|--------|
| **Pre-flight** | Instance registered. User provides source IP |
| **Go** | `request := &das.GetDBInstanceConnectivityDiagnosisRequest{RegionId: tea.String("cn-shanghai"), InstanceId: tea.String(os.Getenv("INSTANCE_ID")), SrcIp: tea.String(os.Getenv("SRC_IP"))}` → `client.GetDBInstanceConnectivityDiagnosis(request)` |
| **Validate** | `$.Data.connectivityResult` = `REACHABLE` or `UNREACHABLE`. If `UNREACHABLE` → parse `failureReason`, `suggestedActions` |
| **Recover** | `InvalidParameter.SrcIp` → verify IP; `OperationDenied.InstanceStatus` → wait |

---

### Operation: Intelligent Inspection（智能巡检）

一键执行数据库实例的DAS全面健康检查。Full Go SDK script at [references/intelligent-inspection.md](references/intelligent-inspection.md).

**6-step workflow:** GetInstanceInspections → CreateDiagnosticReport if < 60 → CMS metrics (CPU/conn/IOPS) via cms-ops → GetAutonomousNotifyEventsInRange → GetDasProServiceUsage → Scoring report.

**Scoring criteria:**

| 维度 | 评分依据 | 权重 |
|------|---------|------|
| DAS巡检评分 | DAS原生评分直接映射 | 30% |
| CPU使用率 | <70%=100, 70-85%=60, >85%=0 | 20% |
| 连接使用率 | <70%=100, 70-85%=60, >85%=0 | 15% |
| IOPS使用率 | <70%=100, 70-85%=60, >85%=0 | 15% |
| 自治事件 | 无严重=100, 有警告=60, 有严重=0 | 10% |
| DAS Pro状态 | 已激活=100, 未激活=60 | 10% |

**Confidence levels:** 0.9-1.0 auto-fix, 0.7-0.89 human review recommended, < 0.5 insufficient info.

---

## Well-Architected Assessment

| Pillar | Key Guidance |
|--------|-------------|
| **Security** | IAM: `das:*` for read, `das:Create*`, `das:Set*` for mutating. Mask SQL in output. Never use production creds for connectivity diagnosis |
| **Stability** | DAS inspection score + autonomous events for proactive fault detection. **Scenario:** Score < 60 → CreateDiagnosticReport → CMS metrics → resolve with auto-scaling/SQL throttling/session kill |
| **Cost** | DAS Basic: free (RDS instances). DAS Pro: paid per instance, enable only for production DBs. Waste: Pro on dev/test → disable |
| **Efficiency** | `SetAutoScalingConfig` for auto-scaling. `CreateSqlLimitTask`/`EnableSqlConcurrencyControl` for SQL throttling. Cross-skill delegation to ECS/VPC/SLB for network issues |
| **Performance** | CPU > 80% → alert. IOPS > 85% → alert. Active connections > 80% → alert. Slow queries > 10/min → investigate. Use `GetQueryOptimizeData` for deep analysis |

## Troubleshooting Capability Enhancement

This skill includes a comprehensive troubleshooting enhancement framework:

### Assessment & Optimization
- [Troubleshooting Capability Assessment](references/troubleshooting.md) — Root cause identification efficiency analysis, optimization proposals, and standardized evaluation metrics
- [Cross-Skill Collaboration Protocol](references/cross-skill-collaboration.md) — Trigger conditions, context passing format, and best practices for multi-skill diagnosis

### Prompt Templates (Advanced — Lazy-Loaded)
- [Troubleshooting Prompt Templates](references/advanced/prompt-templates.md) — Structured prompt templates categorized by fault type (connection_timeout, performance_degradation, data_anomaly) and diagnosis phase (symptom_collection, log_analysis, root_cause_identification, resolution)

### Configuration Assets
- [Fault Pattern Library](assets/das-fault-pattern-library.yaml) — 12 standardized fault patterns with symptoms, root causes, diagnostic APIs, and resolution APIs
- [Alert Thresholds](assets/das-alert-thresholds.yaml) — Static and dynamic baseline thresholds for 11 key metrics with special period adjustments
- [Log Analysis Patterns](assets/das-log-analysis-patterns.yaml) — 8 multi-source correlation analysis patterns for complex fault diagnosis

## References

- [DAS API Reference (Chinese)](https://help.aliyun.com/zh/das/developer-reference/api-reference/)
- [DAS OpenAPI Explorer](https://next.api.aliyun.com/api/DAS/2020-01-16/overview)
- [DAS Error Center](https://error-center.aliyun.com/product/DAS)
- [DAS Go SDK](https://github.com/alibabacloud-go/das-20200116)
- [Alibaba Cloud CLI (not applicable for DAS)](https://github.com/aliyun/aliyun-cli)
- [Agent Skill OpenSpec](https://agentskills.io/specification)
- [API Documentation Mapping](references/api-doc-mapping.md) — Canonical mapping of all skill operations to official API doc URLs and SDK types



