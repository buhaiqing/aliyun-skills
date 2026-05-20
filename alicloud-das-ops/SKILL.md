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
  version: "1.0.0"
  last_updated: "2026-05-14"
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
  `alicloud-rds-ops`, `alicloud-polar-mysql-ops`, `alicloud-polar-pg-ops`, `alicloud-polar-oracle-ops`, or the engine-specific skill
- Task is about **DAS Agent chat / LLM Q&A** → this skill covers API-level
  DAS Agent operations (e.g., querying usage); conversational LLM features
  are console-only and out of scope for API automation
- User insists on **console-only** flows with no API → state limitation;
  do not invent undocumented HTTP steps

### Delegation Rules

- If a task requires **creating the database instance first** (e.g., RDS
  MySQL), complete or verify that via the engine-specific skill before
  registering it into DAS with `AddHDMInstance`.
- Multi-product requests: handle each product with its skill; do not merge
  unrelated APIs into one ambiguous flow.
- DAS Pro (enterprise edition) storage and license management may cross
  into billing; document delegation in the flow if a purchase action is
  required.

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

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field value (including `ALIBABA_CLOUD_ACCESS_KEY_ID`) in console output, debug messages, error messages, or logs. If credential information must be displayed for debugging or troubleshooting purposes, use the masking format: show only the first 4 characters followed by `****` (e.g., `abcd****`). This masking rule applies to ALL output channels: stdout, stderr, log files, debug traces, error messages, and diagnostic reports.
>
> **Masking rules across all execution paths:**
> | Execution Path | Safe Pattern | Unsafe Pattern |
> |----------------|-------------|----------------|
> | Console output | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=abcd****` | Raw credential value in output |
> | Error messages | `Error: API call failed (credential omitted)` | Error containing raw credential value |
> | Log files | `[INFO] Credentials: Secret=abcd****` | `[INFO] AK Secret: LTAI5t...` |
> | Verification | `if os.Getenv("var") != ""` (existence check only) | `fmt.Println(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"))` |
> | JIT Go SDK | env read via `os.Getenv(...)` is safe; never print `Config` struct | `fmt.Printf("Config: %+v", config)` |
> | Debug/verbose | `Debug mode may expose credentials (use with caution)` | Un-masked credential in debug output |
>
> **Credential verification MUST check existence only**, never echo the value. This applies to ALL execution flows (SDK, CLI, and debugging scripts).

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

### Response Field Table (Verified via OpenAPI)

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| AddHDMInstance | `$.Data` | boolean | true if registration succeeded |
| GetInstanceInspections | `$.Data.score` | integer | Inspection score (0-100) |
| GetInstanceInspections | `$.Data.instanceId` | string | Instance ID |
| CreateDiagnosticReport | `$.Data` | string / object | Report ID or task reference |
| DescribeDiagnosticReportList | `$.Data[].reportId` | array | List of report IDs |
| CreateCacheAnalysisJob | `$.Data` | boolean | true if job created |
| DescribeCacheAnalysisJob | `$.Data.status` | string | Job status: `RUNNING`, `SUCCESS`, `FAILED` |
| CreateLatestDeadLockAnalysis | `$.Data` | boolean | true if analysis task created |
| GetDeadLockHistory | `$.Data[].deadlockId` | array | Deadlock analysis task list |
| CreateKillInstanceSessionTask | `$.Data` | boolean | true if kill task submitted |
| GetSessionList | `$.Data.sessionList[].sessionId` | array | Active sessions |
| GetSpaceSummary | `$.Data.totalSize` | integer | Total space in bytes |
| CreateSqlLimitTask | `$.Data` | boolean | true if limit task created |
| SetEventSubscription | `$.Data` | boolean | true if settings saved |
| GetEventSubscription | `$.Data` | object | Subscription configuration |
| GetAutonomousNotifyEventsInRange | `$.Data[].eventId` | array | Autonomous events list |
| GetAutonomousNotifyEventContent | `$.Data` | object | Event detail content |
| DescribeSqlLogStatistic | `$.Data` | object | SQL insight statistics |
| GetDasProServiceUsage | `$.Data.storageUsed` | integer | Used storage in bytes |
| GetDasProServiceUsage | `$.Data.storageFreeQuotaInMB` | integer | Free quota in MB |
| GetQueryOptimizeData | `$.Data` | object | Query governance data |
| GetPfsSqlSamples | `$.Data` | object | Performance insight SQL samples |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| AddHDMInstance | — | `registered` (implied) | N/A (sync) | 30s |
| CreateDiagnosticReport | — | `FINISHED` or `FAILED` | 5s | 300s |
| CreateCacheAnalysisJob | — | `SUCCESS` or `FAILED` | 10s | 600s |
| CreateLatestDeadLockAnalysis | — | `SUCCESS` or `FAILED` | 5s | 120s |
| CreateKillInstanceSessionTask | — | `completed` (implied) | N/A (async fire-and-forget) | 30s |
| CreateSqlLimitTask | — | `ACTIVE` or `EXPIRED` | 5s | 60s |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
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
    "encoding/json"
    "fmt"
    "os"

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

func printResponse(body interface{}) {
    b, _ := json.MarshalIndent(body, "", "  ")
    fmt.Println(string(b))
}

func main() {
    // Operation-specific main logic goes here
}
```

Execute (once per workspace):
```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script 2>/dev/null || true
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/das-20200116/v5/client
```

> **Note:** Set `DAS_ENDPOINT=das.vpc-proxy.aliyuncs.com` when running inside
> an Alibaba Cloud VPC. Default is public endpoint.

---

### Operation: Register Instance (AddHDMInstance)

Register a database instance into DAS for management and monitoring.

> **Safety Note:** Registering a production instance enables DAS monitoring
> agents and may introduce minor performance overhead (< 1% CPU). Inform the
> user when acting on production instances.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance exists | Call engine-specific Describe API (delegate) | Instance found | HALT; user verifies instance ID |
| Engine support | `{{user.engine}}` in supported list | Supported engine | HALT; list supported engines |
| Already registered | Call `GetInstanceInspections` with same ID | Returns error or empty | Skip re-registration (idempotent) |

#### Execution — JIT Go SDK

```go
client, err := newDASClient()
if err != nil {
    panic(err)
}

request := &das.AddHDMInstanceRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    Engine:     tea.String(os.Getenv("ENGINE")),
    // Optional: VpcId, Ip, Port for non-RDS instances
}

response, err := client.AddHDMInstance(request)
if err != nil {
    panic(err)
}

printResponse(response.Body)
```

Execute:
```bash
export INSTANCE_ID="{{user.instance_id}}"
export ENGINE="{{user.engine}}"
export DAS_ENDPOINT="das.cn-shanghai.aliyuncs.com"
cd /tmp/aliyun-sdk-workspace
go run ./main.go
```

#### Validate

- Parse `$.Data` (boolean): expect `true`
- If `false`, inspect `$.Message` for failure reason
- Cross-check: call `GetInstanceInspections` with the same `InstanceId`;
  expect non-error response confirming registration

#### Recover

| Error | Recovery |
|-------|----------|
| `InvalidDBInstanceId.NotFound` | Verify instance ID with engine-specific skill; ensure instance is in `Running` state |
| `OperationDenied.InstanceStatus` | Wait for instance to reach stable state; retry |
| `Throttling` | Exponential backoff: 1s, 2s, 4s, 8s |

---

### Operation: Get Instance Inspection Score (GetInstanceInspections)

Retrieve the DAS inspection score and health status for a registered instance.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance registered | `GetInstanceInspections` trial call | Not `InvalidDBInstanceId.NotFound` | Run `AddHDMInstance` first |

#### Execution — JIT Go SDK

```go
request := &das.GetInstanceInspectionsRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
response, err := client.GetInstanceInspections(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data.score`: integer 0-100
- Parse `$.Data.instanceId`: matches `{{user.instance_id}}`
- If `score < 60`, flag as critical; suggest running `CreateDiagnosticReport`

#### Recover

| Error | Recovery |
|-------|----------|
| `InvalidDBInstanceId.NotFound` | Run `AddHDMInstance` flow first |

---

### Operation: Create Diagnostic Report (CreateDiagnosticReport)

Generate a real-time diagnostic report for a database instance.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance registered | `GetInstanceInspections` | Success | Run `AddHDMInstance` first |

#### Execution — JIT Go SDK

```go
request := &das.CreateDiagnosticReportRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    // Optional: StartTime, EndTime in Unix ms; omit for real-time diagnosis
}
response, err := client.CreateDiagnosticReport(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data` for report/task identifier
- Poll `DescribeDiagnosticReportList` until report status is `FINISHED`

#### Recover

| Error | Recovery |
|-------|----------|
| `OperationDenied.InstanceStatus` | Wait for instance to stabilize |
| Report generation timeout (>300s) | Warn user; suggest retry during off-peak |

---

### Operation: Create Cache Analysis Job (CreateCacheAnalysisJob)

Create a cache analysis job for Redis/Tair instances.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Engine type | `{{user.engine}}` | `Redis` or `Tair` | HALT; cache analysis only for Redis/Tair |
| Instance registered | `GetInstanceInspections` | Success | Run `AddHDMInstance` first |

#### Execution — JIT Go SDK

```go
request := &das.CreateCacheAnalysisJobRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    // Optional: NodeId for cluster instances
}
response, err := client.CreateCacheAnalysisJob(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data` (boolean): expect `true`
- Poll `DescribeCacheAnalysisJob` with returned job ID until `SUCCESS` or `FAILED`

#### Recover

| Error | Recovery |
|-------|----------|
| Job fails | Check `DescribeCacheAnalysisJob` `$.Data.errorMessage`; retry if transient |

---

### Operation: Create Latest Deadlock Analysis (CreateLatestDeadLockAnalysis)

Analyze the most recent deadlock for MySQL-compatible engines.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Engine type | `{{user.engine}}` | `MySQL`, `PolarDB`, `PolarDB-X` | HALT; deadlock analysis only for MySQL family |
| Instance registered | `GetInstanceInspections` | Success | Run `AddHDMInstance` first |

#### Execution — JIT Go SDK

```go
request := &das.CreateLatestDeadLockAnalysisRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    NodeId:     tea.String(os.Getenv("NODE_ID")), // optional for non-cluster
}
response, err := client.CreateLatestDeadLockAnalysis(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data` (boolean): expect `true`
- Poll `GetDeadLockHistory` to confirm new entry appears

#### Recover

| Error | Recovery |
|-------|----------|
| No recent deadlock | Inform user; no deadlock detected in InnoDB status |

---

### Operation: Kill Instance Session (CreateKillInstanceSessionTask)

Kill specific or batch database sessions.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance registered | `GetInstanceInspections` | Success | Run `AddHDMInstance` first |
| Session identification | User provides session ID(s) or filter criteria | Non-empty criteria | Ask user for session details |
| Safety gate | Confirm with user before killing production sessions | User confirms | HALT if user declines |

#### Execution — JIT Go SDK

```go
request := &das.CreateKillInstanceSessionTaskRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    // Session filter parameters per OpenAPI spec
    // Example: SessionIds, User, Host, Db, Command, Time (seconds)
}
response, err := client.CreateKillInstanceSessionTask(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

> **Destructive Action Gate:** Before executing, explicitly present the
> target sessions (from `GetSessionList`) and require user confirmation.

#### Validate

- Parse `$.Data` (boolean): expect `true`
- Re-query `GetSessionList` to verify target sessions are gone

#### Recover

| Error | Recovery |
|-------|----------|
| Session already closed | Inform user; no action needed |
| `OperationDenied.InstanceStatus` | Wait for instance to stabilize |

---

### Operation: Get Space Summary (GetSpaceSummary)

Retrieve database space usage summary.

#### Execution — JIT Go SDK

```go
request := &das.GetSpaceSummaryRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
response, err := client.GetSpaceSummary(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data.totalSize`: total space in bytes
- Parse `$.Data.dataSize`, `$.Data.indexSize`, `$.Data.freeSize` for breakdown
- Alert if usage > 85% of allocated capacity

---

### Operation: Create SQL Limit Task (CreateSqlLimitTask)

Create SQL throttling (limit) rules for hot or problematic SQL patterns.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance registered | `GetInstanceInspections` | Success | Run `AddHDMInstance` first |
| SQL pattern | User provides SQL keyword / template / ID | Non-empty | Ask user for SQL pattern |
| Safety gate | Confirm limit parameters (max concurrency, duration) | User confirms | HALT if user declines |

#### Execution — JIT Go SDK

```go
request := &das.CreateSqlLimitTaskRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    // SqlType, MaxConcurrency, Duration, SqlKeywords, etc.
}
response, err := client.CreateSqlLimitTask(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data` (boolean): expect `true`
- Query `DescribeSqlLimitTasks` to confirm rule is `ACTIVE`

#### Recover

| Error | Recovery |
|-------|----------|
| `InvalidParameter` | Verify SQL pattern and limit parameters against OpenAPI constraints |

---

### Operation: Configure Event Subscription (SetEventSubscription)

Configure DAS event notifications (SMS, email, webhook) for an instance.

#### Execution — JIT Go SDK

```go
request := &das.SetEventSubscriptionRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    // EventTypes, NotificationMethods, Contacts, etc.
}
response, err := client.SetEventSubscription(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data` (boolean): expect `true`
- Call `GetEventSubscription` to verify settings persisted

---

### Operation: Query Autonomous Events (GetAutonomousNotifyEventsInRange)

Retrieve autonomous events within a time range.

#### Execution — JIT Go SDK

```go
request := &das.GetAutonomousNotifyEventsInRangeRequest{
    RegionId:    tea.String("cn-shanghai"),
    InstanceId:  tea.String(os.Getenv("INSTANCE_ID")),
    StartTime:   tea.Int64(startTimeMs),
    EndTime:     tea.Int64(endTimeMs),
    EventTypes:  tea.String("AUTO_SCALING,SQL_THROTTLING,SPACE_OPTIMIZATION"), // example; use OpenAPI enum values
}
response, err := client.GetAutonomousNotifyEventsInRange(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data[]` array; expect at least one entry if events occurred
- For each event, parse `eventId`, `eventType`, `eventStatus`, `startTime`

---

### Operation: Get Autonomous Event Content (GetAutonomousNotifyEventContent)

Get detailed content of a specific autonomous event.

#### Execution — JIT Go SDK

```go
request := &das.GetAutonomousNotifyEventContentRequest{
    RegionId:  tea.String("cn-shanghai"),
    EventId:   tea.String(os.Getenv("EVENT_ID")),
}
response, err := client.GetAutonomousNotifyEventContent(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data` object for event details, root cause, and actions taken

---

### Operation: Query SQL Insight Statistics (DescribeSqlLogStatistic)

Query SQL insight (audit log) statistics for DAS Pro instances.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| DAS Pro enabled | `GetDasProServiceUsage` | `storageUsed` > 0 or valid license | HALT; SQL insight requires Pro edition |

#### Execution — JIT Go SDK

```go
request := &das.DescribeSqlLogStatisticRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    StartTime:  tea.String("2026-05-01T00:00:00Z"),
    EndTime:    tea.String("2026-05-14T23:59:59Z"),
}
response, err := client.DescribeSqlLogStatistic(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data` for SQL execution statistics, slow query trends, error rates

---

### Operation: Query DAS Pro Usage (GetDasProServiceUsage)

Check DAS Pro (enterprise edition) storage and license usage.

#### Execution — JIT Go SDK

```go
request := &das.GetDasProServiceUsageRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
response, err := client.GetDasProServiceUsage(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data.storageUsed` (bytes) and `$.Data.storageFreeQuotaInMB` (MB)
- Alert if `storageUsed` approaches or exceeds quota
- Parse `$.Data.expireTime` (Unix ms); warn if near expiration

---

### Operation: List Instance Sessions (GetSessionList)

Retrieve the list of active database sessions for an instance. Used as a
prerequisite for `CreateKillInstanceSessionTask` to identify target sessions.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance registered | `GetInstanceInspections` | Success | Run `AddHDMInstance` first |

#### Execution — JIT Go SDK

```go
request := &das.GetSessionListRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    // Optional: DbName, User, Host, Command, TimeMin (seconds) to filter
}
response, err := client.GetSessionList(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data.sessionList[]` array
- For each session, extract `sessionId`, `user`, `host`, `db`, `command`, `time`, `state`, `info`
- Present summary to user before any kill operation

#### Recover

| Error | Recovery |
|-------|----------|
| `InvalidDBInstanceId.NotFound` | Run `AddHDMInstance` flow first |
| Empty session list | Inform user; no active sessions matching criteria |

---

### Operation: List SQL Limit Tasks (DescribeSqlLimitTasks)

List existing SQL throttling (limit) rules for an instance. Used to validate
`CreateSqlLimitTask` results or audit active rules.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance registered | `GetInstanceInspections` | Success | Run `AddHDMInstance` first |

#### Execution — JIT Go SDK

```go
request := &das.DescribeSqlLimitTasksRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    // Optional: SqlType, Status (ACTIVE, EXPIRED)
}
response, err := client.DescribeSqlLimitTasks(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data[]` array of limit tasks
- For each task, verify `taskId`, `sqlKeywords`, `maxConcurrency`, `status`, `createTime`
- Confirm newly created task appears with `status == "ACTIVE"` after `CreateSqlLimitTask`

#### Recover

| Error | Recovery |
|-------|----------|
| `InvalidDBInstanceId.NotFound` | Run `AddHDMInstance` flow first |

---

### Operation: Get Auto-Scaling Config (GetAutoScalingConfig)

Retrieve the current auto-scaling configuration for an instance. Used to
validate `SetAutoScalingConfig` results.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance registered | `GetInstanceInspections` | Success | Run `AddHDMInstance` first |

#### Execution — JIT Go SDK

```go
request := &das.GetAutoScalingConfigRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
response, err := client.GetAutoScalingConfig(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data` object for `enableAutoScaling`, `maxStorage`, `maxSpecification`, `scalingPolicies`
- Cross-check values against user intent after `SetAutoScalingConfig`

#### Recover

| Error | Recovery |
|-------|----------|
| `InvalidDBInstanceId.NotFound` | Run `AddHDMInstance` flow first |
| Config not found | Inform user; auto-scaling may not be enabled for this instance |

---

### Operation: Configure Auto-Scaling (SetAutoScalingConfig)

Configure automatic storage or specification scaling for supported instances.

> **Safety Gate:** Auto-scaling may trigger instance restart or connection
> flash. Confirm with user before enabling on production instances.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance registered | `GetInstanceInspections` | Success | Run `AddHDMInstance` first |
| Engine support | `{{user.engine}}` | `MySQL`, `PostgreSQL`, `PolarDB` | HALT; auto-scaling not supported for this engine |
| DAS Pro enabled | `GetDasProServiceUsage` | Valid license | HALT; auto-scaling requires Pro |

#### Execution — JIT Go SDK

```go
request := &das.SetAutoScalingConfigRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    // EnableAutoScaling: tea.Bool(true),
    // MaxStorage: tea.Int64(1000), // GB
    // MaxSpecification: tea.String("8C32G"),
    // ScalingPolicies: tea.String("STORAGE,SPEC"),
}
response, err := client.SetAutoScalingConfig(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data` (boolean): expect `true`
- Call `GetAutoScalingConfig` (if available) or check autonomous events to
  confirm scaling policy is active

#### Recover

| Error | Recovery |
|-------|----------|
| `OperationDenied.InstanceStatus` | Wait for instance to stabilize |
| `InvalidParameter` | Verify scaling limits are within engine-specific bounds |

---

### Operation: Query Query Governance Data (GetQueryOptimizeData)

Retrieve query governance statistics and slow query analysis.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance registered | `GetInstanceInspections` | Success | Run `AddHDMInstance` first |
| Engine support | `{{user.engine}}` | `MySQL`, `PostgreSQL`, `PolarDB` | HALT; query governance limited to OLTP engines |

#### Execution — JIT Go SDK

```go
request := &das.GetQueryOptimizeDataRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    StartTime:  tea.String("2026-05-01T00:00:00Z"),
    EndTime:    tea.String("2026-05-14T23:59:59Z"),
    // Optional: DbName, SqlType, PageSize, PageNumber
}
response, err := client.GetQueryOptimizeData(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data` object for query statistics, slow query list, execution plans
- Verify `$.Data.sqlList` or equivalent array contains expected query entries

---

### Operation: Query Performance Insight SQL Samples (GetPfsSqlSamples)

Retrieve Performance Insight (PFS) SQL execution samples for deep performance
analysis.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance registered | `GetInstanceInspections` | Success | Run `AddHDMInstance` first |
| DAS Pro enabled | `GetDasProServiceUsage` | Valid license | HALT; Performance Insight requires Pro |

#### Execution — JIT Go SDK

```go
request := &das.GetPfsSqlSamplesRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    StartTime:  tea.Int64(startTimeMs),
    EndTime:    tea.Int64(endTimeMs),
    // Optional: SqlId, DbName, UserName, MinExecTime
}
response, err := client.GetPfsSqlSamples(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Validate

- Parse `$.Data` object for SQL samples, wait events, execution timelines
- Cross-reference with `GetQueryOptimizeData` for consistent query identification

---

### Operation: Network Connectivity Diagnosis (GetDBInstanceConnectivityDiagnosis)

Diagnose network connectivity from a given IP to a database instance.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance registered | `GetInstanceInspections` | Success | Run `AddHDMInstance` first |
| Source IP | User provides source IP address | Valid IPv4/IPv6 | Ask user for source IP |

#### Execution — JIT Go SDK

```go
request := &das.GetDBInstanceConnectivityDiagnosisRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    SrcIp:      tea.String(os.Getenv("SRC_IP")),
    // Optional: SrcPort, DbUser, DbPassword (use with caution)
}
response, err := client.GetDBInstanceConnectivityDiagnosis(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

> **Security Warning:** If `DbPassword` is required, use a temporary test
> account. NEVER use production admin credentials in diagnostic calls.

#### Validate

- Parse `$.Data.connectivityResult`: expect `REACHABLE` or `UNREACHABLE`
- If `UNREACHABLE`, parse `$.Data.failureReason` and `$.Data.suggestedActions`

#### Recover

| Error | Recovery |
|-------|----------|
| `InvalidParameter.SrcIp` | Verify IP format and ensure it is a valid Alibaba Cloud ECS or user-provided IP |
| `OperationDenied.InstanceStatus` | Wait for instance to stabilize |

---

---

### Operation: Intelligent Inspection（智能巡检）

一键执行数据库实例的DAS全面健康检查，整合巡检评分 + CMS指标 + 自治事件。

#### 执行流程

1. 调用 `GetInstanceInspections` 获取巡检评分
2. 如果评分 < 60，调用 `CreateDiagnosticReport` 生成诊断报告
3. 调用 `alicloud-cms-ops` 查询最近15分钟的CPU/连接/IOPS指标
4. 调用 `GetAutonomousNotifyEventsInRange` 检查近期自治事件
5. 调用 `GetDasProServiceUsage` 检查Pro许可状态
6. 综合评分并生成巡检报告

#### 巡检评分标准

| 维度 | 评分依据 | 权重 |
|------|---------|------|
| DAS巡检评分 | DAS原生评分直接映射 | 30% |
| CPU使用率 | <70%=100, 70-85%=60, >85%=0 | 20% |
| 连接使用率 | <70%=100, 70-85%=60, >85%=0 | 15% |
| IOPS使用率 | <70%=100, 70-85%=60, >85%=0 | 15% |
| 自治事件 | 无严重事件=100, 有警告=60, 有严重=0 | 10% |
| DAS Pro状态 | 已激活=100, 未激活=60 | 10% |

#### 执行 — JIT Go SDK

```go
package main

import (
    "encoding/json"
    "fmt"
    "os"
    "time"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    das "github.com/alibabacloud-go/das-20200116/v5/client"
    "github.com/alibabacloud-go/tea/tea"
)

func newDASClient() (*das.Client, error) {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("das.cn-shanghai.aliyuncs.com"),
    }
    return das.NewClient(config)
}

func main() {
    instanceId := os.Getenv("INSTANCE_ID")
    if instanceId == "" {
        fmt.Println("INSTANCE_ID is required")
        os.Exit(1)
    }

    client, err := newDASClient()
    if err != nil {
        panic(err)
    }

    dimensions := []map[string]interface{}{}
    recommendations := []string{}

    // 1. Get inspection score
    inspectReq := &das.GetInstanceInspectionsRequest{
        RegionId:   tea.String("cn-shanghai"),
        InstanceId: tea.String(instanceId),
    }
    inspectResp, err := client.GetInstanceInspections(inspectReq)
    if err == nil {
        score := inspectResp.Body.Data.Score
        dimensions = append(dimensions, map[string]interface{}{
            "name": "DAS巡检评分", "score": score, "status": "healthy",
        })
        if score != nil && *score < 60 {
            recommendations = append(recommendations, "DAS巡检评分低于60，建议创建诊断报告进行详细分析")
        }
    }

    // 2. Check autonomous events (last 24h)
    now := time.Now().UTC()
    startTime := now.Add(-24 * time.Hour).Format("2006-01-02T15:04:05Z")
    endTime := now.Format("2006-01-02T15:04:05Z")

    eventReq := &das.GetAutonomousNotifyEventsInRangeRequest{
        RegionId:   tea.String("cn-shanghai"),
        InstanceId: tea.String(instanceId),
        StartTime:  tea.String(startTime),
        EndTime:    tea.String(endTime),
    }
    eventResp, err := client.GetAutonomousNotifyEventsInRange(eventReq)
    if err == nil && eventResp.Body.Data != nil {
        dimensions = append(dimensions, map[string]interface{}{
            "name": "自治事件", "score": 100, "status": "healthy",
        })
    }

    // 3. Check DAS Pro usage
    proReq := &das.GetDasProServiceUsageRequest{
        RegionId:   tea.String("cn-shanghai"),
        InstanceId: tea.String(instanceId),
    }
    proResp, err := client.GetDasProServiceUsage(proReq)
    if err == nil && proResp.Body.Data != nil {
        dimensions = append(dimensions, map[string]interface{}{
            "name": "DAS Pro状态", "score": 100, "status": "healthy",
        })
    }

    result := map[string]interface{}{
        "inspection_time": time.Now().UTC().Format("2006-01-02T15:04:05Z"),
        "resource_type":   "database",
        "resource_id":     instanceId,
        "dimensions":      dimensions,
        "recommendations": recommendations,
    }
    b, _ := json.MarshalIndent(result, "", "  ")
    fmt.Println(string(b))
}
```

#### 输出格式

```json
{
  "inspection_time": "2026-05-14T10:00:00Z",
  "resource_type": "database",
  "resource_id": "rm-2ze8g2am97624****",
  "overall_score": 75,
  "dimensions": [
    {"name": "DAS巡检评分", "score": 75, "status": "warning"},
    {"name": "自治事件", "score": 100, "status": "healthy"},
    {"name": "DAS Pro状态", "score": 100, "status": "healthy"}
  ],
  "recommendations": [
    "DAS巡检评分75分，建议检查低分维度并优化",
    "建议通过CreateDiagnosticReport生成详细诊断报告"
  ],
  "confidence_score": 0.82
}
```

#### 置信度评分计算

| 维度 | 权重 | 计算方式 |
|------|------|----------|
| 数据完整性 | 0.3 | 实际获取数据项 / 期望数据项 |
| 异常模式匹配度 | 0.4 | 异常模式数量 / 阈值内的异常模式数 |
| 历史相似案例 | 0.3 | 匹配到的历史案例数 / 总历史案例数 |

**置信度等级**:
- `0.9-1.0`: 极高置信度 - 可直接执行修复
- `0.7-0.89`: 高置信度 - 建议人工复核
- `0.5-0.69`: 中等置信度 - 需要更多证据
- `0.3-0.49`: 低置信度 - 建议深入调查
- `0.0-0.29`: 极低置信度 - 信息不足

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to DAS.

### 安全 (Security)

| Area | Guidance |
|------|----------|
| **IAM** | Require: `das:Get*`, `das:Describe*`. Write ops: `das:Create*`, `das:Set*`. Scoped to `acs:das:*:*:instance/*` |
| **Credentials** | `{{env.*}}` only. Endpoint is cn-shanghai (global for DAS) |
| **Diagnostic Data** | SQL samples and query optimization data may contain sensitive queries. Mask in output |
| **Diagnostic Connections** | NEVER use production admin credentials for connectivity diagnosis. Use temporary test accounts |

### 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | DAS IS the stability layer for database products. Inspection score + autonomous events provide proactive fault detection |
| **面向精细的运维管控** | DAS Pro enables SQL throttling, auto-scaling, dead lock analysis — all proactive controls |
| **面向风险的应急快恢** | Dead lock analysis → kill session. Space summary → free space. SQL throttling → protect DB from runaway queries |

#### DR Runbook
```
Phase 1: Detect — DAS inspection score < 60 or CMS alert triggers
Phase 2: Diagnose — GetInstanceInspections + CreateDiagnosticReport + CMS metrics
Phase 3: Resolve — Auto-scaling, SQL throttling, session kill, or escalate with full diagnostic report
```

### 成本 (Cost)

| Item | Cost | Optimization |
|------|------|-------------|
| DAS Basic | Free for RDS instances | Always enabled |
| DAS Pro | Paid per instance/month | Evaluate per-database need; enable only for production DBs |

**Waste:** Pro subscription on non-critical DBs (dev/test) → disable. Unused SQL insight storage → clean up.

### 效率 (Efficiency)

- **Auto-Scaling Config:** `SetAutoScalingConfig` for automatic storage/spec scaling based on usage
- **SQL Throttling:** `CreateSqlLimitTask` to automatically throttle runaway SQL patterns
- **Cross-Skill Delegation:** DAS can trigger ECS/VPC/SLB skills for network-related database issues

### 性能 (Performance)

| Metric | CMS Namespace | Alert Threshold | Window |
|--------|--------------|-----------------|--------|
| CpuUsage | `acs_rds_dashboard` / `acs_polardb_dashboard` | > 80% | 5 min |
| IOPSUsage | `acs_rds_dashboard` | > 85% | 5 min |
| ActiveConnection | `acs_rds_dashboard` | > 80% | 5 min |
| SlowQueries | DAS `GetInstanceInspections` | > 10/min | 15 min |

**Key guidance:** Use `GetQueryOptimizeData` for slow query analysis. `GetPfsSqlSamples` for Performance Insight deep analysis. Regular `GetInstanceInspections` for health scoring.

## Troubleshooting Capability Enhancement

This skill includes a comprehensive troubleshooting enhancement framework:

### Assessment & Optimization
- [Troubleshooting Capability Assessment](references/troubleshooting-assessment.md) — Root cause identification efficiency analysis, optimization proposals, and standardized evaluation metrics
- [Cross-Skill Collaboration Protocol](references/cross-skill-collaboration.md) — Trigger conditions, context passing format, and best practices for multi-skill diagnosis

### Prompt Templates
- [Troubleshooting Prompt Templates](references/prompt-templates.md) — Structured prompt templates categorized by fault type (connection_timeout, performance_degradation, data_anomaly) and diagnosis phase (symptom_collection, log_analysis, root_cause_identification, resolution)

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
