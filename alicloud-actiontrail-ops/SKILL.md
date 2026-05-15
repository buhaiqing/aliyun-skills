---
name: alicloud-actiontrail-ops
description: >-
  Investigate Alibaba Cloud account activity — find who deleted or modified a
  resource, when an API was called, what changed, and from where. Use for
  security incident response, compliance auditing, troubleshooting unexpected
  changes, and keeping operation logs beyond the default 90-day retention. User
  mentions ActionTrail, 操作审计, audit trail, 审计日志, 操作日志, 事件查询,
  审计, 合规, 安全, or asks to trace API calls, check AccessKey usage, export
  operation logs, investigate failed access, or set up long-term log storage —
  even without naming the product. Not for billing, RAM permissions, or managing
  OSS/SLS/MaxCompute directly.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-05-15"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "Actiontrail 2020-07-06 / https://help.aliyun.com/zh/actiontrail/developer-reference/api-actiontrail-2020-07-06-overview"
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun help actiontrail` — ActionTrail is fully supported by
    the official aliyun CLI. All core operations (CreateTrail, DeleteTrail,
    StartLogging, StopLogging, UpdateTrail, GetTrailStatus, DescribeTrails,
    LookupEvents) have matching CLI commands.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud ActionTrail Operations Skill

## Overview

Alibaba Cloud ActionTrail (操作审计) monitors and records API calls and user activities
across Alibaba Cloud services, including operations performed via the console, OpenAPI,
and developer tools. This skill is an **operational runbook** for agents: explicit scope,
credential rules, pre-flight checks, **dual-path execution** (official **`aliyun` CLI**
as primary path, **JIT Go SDK** as fallback), response validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` supports ActionTrail. You
**MUST** use **`references/cli-usage.md`** and, in **each** execution flow below,
document **both** the SDK step **and** the `aliyun` step for every operation the CLI
exposes. If the CLI covers **only part** of the API, add a **coverage gap** table
(SDK-only operations) in `references/cli-usage.md`.

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers and delegation rules |
| 2 | **Structured I/O** | Placeholder conventions (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) with type and source documented |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute → Validate → Recover, with numbered imperative steps |
| 4 | **Complete Failure Strategies** | Error taxonomy table with 10+ product-specific codes; HALT vs retry per error type |
| 5 | **Absolute Single Responsibility** | One product (ActionTrail), one primary resource model (Trail); cross-product delegation to other skills |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "ActionTrail" OR "操作审计" OR "actiontrail" OR "trail" OR "跟踪"
- User mentions "审计日志" OR "操作日志" OR "事件查询" OR "审计事件"
- Task involves **trail lifecycle** (create, describe, update, delete, enable/disable logging)
- Task involves **event lookup/query** (search historical events, filter by time/user/resource)
- Task involves **delivery configuration** (OSS/SLS/MaxCompute delivery setup)
- Task involves **AccessKey audit** (last used info, events, IPs, products, resources)
- Task involves **data event selectors** (configure data-level event collection)
- Task involves **insight events** (enable/disable/query insight analysis)
- Task involves **advanced query** (scenes, templates, SQL-based event search)
- Task involves **data replenishment** (backfill historical events to delivery destinations)
- Task keywords: 操作审计, actiontrail, trail, 跟踪, 审计, audit, 事件, event, 日志, log,
  LookupEvents, CreateTrail, StartLogging, StopLogging, AccessKey审计
- User asks to audit, trace, or investigate API calls, resource changes, or user activities
  **via API, SDK, CLI, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops` (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when present)
- Task is about **SLS (Log Service)** log analysis or dashboard creation → delegate to:
  `alicloud-sls-ops` (when present)
- Task is about **OSS** bucket configuration or data management → delegate to:
  `alicloud-oss-ops` (when present)
- Task is about **MaxCompute** project management → delegate to:
  `alicloud-maxcompute-ops` (when present)
- User insists on **console-only** flows with no API → state limitation; do not invent
  undocumented HTTP steps

### Delegation Rules

- If creating a trail with OSS delivery, verify OSS bucket exists (via `alicloud-oss-ops`
  when present) before trail creation.
- If creating a trail with SLS delivery, verify SLS project exists (via `alicloud-sls-ops`
  when present) before trail creation.
- If investigating a specific resource change (e.g., ECS instance deletion), use
  LookupEvents to find the event, then delegate to the relevant product skill for
  remediation.
- Multi-product audit requests: handle ActionTrail event lookup first, then delegate
  to specific product skills for further investigation.

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.trail_name}}` | User-supplied trail name | Ask once; reuse |
| `{{user.oss_bucket_name}}` | User-supplied OSS bucket name | Ask once; reuse |
| `{{user.sls_project_arn}}` | User-supplied SLS project ARN | Ask once; reuse |
| `{{user.access_key_id}}` | User-supplied AccessKey ID to audit | Ask once; reuse |
| `{{user.start_time}}` | Event lookup start time (ISO 8601 UTC) | Ask once; reuse |
| `{{user.end_time}}` | Event lookup end time (ISO 8601 UTC) | Ask once; reuse |
| `{{user.event_type}}` | Event type filter | Ask once; reuse |
| `{{user.service_name}}` | Cloud service name filter | Ask once; reuse |
| `{{user.event_name}}` | Event name filter | Ask once; reuse |
| `{{output.trail_name}}` | From last API or CLI JSON response | Parse per OpenAPI or verified CLI path |
| `{{output.trail_status}}` | Trail logging status (Enable/Disable) | Parse per OpenAPI or verified CLI path |
| `{{output.request_id}}` | API request ID for tracking | Parse per OpenAPI or verified CLI path |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected
> interactively when missing.

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose
> `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any
> credential field value in console output, debug messages, error messages, or logs.
> Credential verification MUST check existence only, never echo the value.

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec.
- **Timestamps:** ISO 8601 with timezone when the API returns strings (e.g.
  `2026-04-28T10:00:00+08:00`).
- **Pagination:** LookupEvents uses `NextToken` for pagination. MaxResults range: 0-50.

### Example Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateTrail | `$.TrailName` | string | Created trail name |
| DescribeTrails | `$.TrailList[].TrailName` | array | Trail names |
| GetTrailStatus | `$.IsLogging` | boolean | Whether logging is enabled |
| LookupEvents | `$.Events[]` | array | Event records |
| LookupEvents | `$.NextToken` | string | Pagination token |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateTrail | — | created (disabled) | 5s | 60s |
| StartLogging | disabled | enabled | 5s | 60s |
| StopLogging | enabled | disabled | 5s | 60s |
| DeleteTrail | any | deleted | 5s | 60s |

## Quick Start

### What This Skill Does
This skill enables you to configure, query, and manage ActionTrail audit logging on
Alibaba Cloud using the `aliyun` CLI (primary) or JIT Go SDK (fallback).

### Prerequisites
- [ ] `aliyun` CLI installed (or Go runtime for JIT fallback)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`

### Verify Setup
```bash
# Check CLI and credentials
aliyun actiontrail DescribeRegions
```

### Your First Command
```bash
# List all trails
aliyun actiontrail DescribeTrails
```

### Next Steps
- [Core Concepts](references/core-concepts.md) — Understand ActionTrail architecture
- [Common Operations](#execution-flows) — Create, manage, and query trails and events
- [Troubleshooting](references/troubleshooting.md) — Fix common issues

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| CreateTrail | Create a new trail for event delivery | Medium | Low |
| DescribeTrails | List all trails | Low | None |
| GetTrailStatus | Query trail logging status | Low | None |
| StartLogging | Enable trail logging | Low | Low |
| StopLogging | Disable trail logging | Low | Low |
| UpdateTrail | Modify trail configuration | Medium | Medium |
| DeleteTrail | Remove a trail | Low | **High** — irreversible |
| LookupEvents | Search historical events | Medium | None |
| GetAccessKeyLastUsedInfo | Query AccessKey last usage | Low | None |
| EnableInsight | Enable insight analysis | Low | Low |
| DisableInsight | Disable insight analysis | Low | Low |
| LookupInsightEvents | Query insight events | Medium | None |
| CreateDeliveryHistoryJob | Backfill historical events | Medium | Low |
| CreateComplianceTrail | Create a compliance-grade trail (all regions, all events) | Medium | Low |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2026-05-15 | Added 5 new InsightTypes (IpInsight, AkInsight, PolicyChangeInsight, PasswordChangeInsight, TrailConcealmentInsight), LookupInsightEvents flow, CreateComplianceTrail flow with compliance checklist, InsightTypeNotAvailable error code |
| 1.0.0 | 2026-05-15 | Initial ActionTrail skill with CLI and SDK support |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (SDK/API and `aliyun`) → Validate → Recover**.
Do not skip phases.

**Preference hint:** CLI is preferred for coverage and simplicity; Go SDK is used for
operations CLI does not expose.

### Operation: Create Trail

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SDK / deps | Import client; version matches `metadata.api_profile` | No import error | Document install pin |
| CLI / deps | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Construct credential from env | Non-empty keys | HALT; user configures env |
| Region | `aliyun actiontrail DescribeRegions` | Region supported | Suggest valid region |
| Trail name | Validate name: 6-36 chars, lowercase start, alphanumeric/hyphen/underscore | Valid name | Ask user for valid name |
| Delivery target | At least one of OssBucketName, SlsProjectArn, MaxComputeProjectArn specified | At least one set | Ask user for delivery target |

#### CLI Execution

```bash
aliyun actiontrail CreateTrail \
  --Name {{user.trail_name}} \
  --OssBucketName {{user.oss_bucket_name}} \
  --OssKeyPrefix {{user.oss_key_prefix}} \
  --EventRW All \
  --IsOrganizationTrail false
```

**Note:** By default, the created trail is in **disabled** state. You must call
`StartLogging` to enable it.

#### SDK Execution (JIT Go Fallback)

```go
package main

import (
    "fmt"
    "os"
    "encoding/json"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    actiontrail "github.com/alibabacloud-go/actiontrail-20200706/v4/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("actiontrail.aliyuncs.com"),
    }

    client, err := actiontrail.NewClient(config)
    if err != nil {
        panic(err)
    }

    request := &actiontrail.CreateTrailRequest{
        Name:          tea.String(os.Args[1]),
        OssBucketName: tea.String(os.Args[2]),
        EventRW:       tea.String("All"),
    }

    response, err := client.CreateTrail(request)
    if err != nil {
        panic(err)
    }

    body, _ := json.Marshal(response.Body)
    fmt.Println(string(body))
}
```

```bash
go run main.go {{user.trail_name}} {{user.oss_bucket_name}}
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Trail created | `aliyun actiontrail DescribeTrails` | Trail appears in list |
| Trail name matches | `$.TrailList[0].TrailName` | Matches `{{user.trail_name}}` |
| Delivery target set | `$.TrailList[0].OssBucketName` | Matches `{{user.oss_bucket_name}}` |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Trail name exists | `TrailAlreadyExistsException` | HALT; suggest different name |
| Invalid parameter | `InvalidParameter` | HALT; check parameter values |
| Network error | `RequestError` | Retry with exponential backoff (3 attempts) |

### Operation: Describe Trails

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Credentials | Env vars set | Non-empty | HALT |

#### CLI Execution

```bash
# List all trails
aliyun actiontrail DescribeTrails

# List trails with name filter
aliyun actiontrail DescribeTrails --NameList '["{{user.trail_name}}"]'

# Include organization trails
aliyun actiontrail DescribeTrails --IncludeOrganizationTrail true
```

#### SDK Execution (JIT Go Fallback)

```go
request := &actiontrail.DescribeTrailsRequest{}
response, err := client.DescribeTrails(request)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Response received | `$.RequestId` | Non-empty |
| Trail list | `$.TrailList` | Array (may be empty) |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Network error | `RequestError` | Retry with backoff |

### Operation: Get Trail Status

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Trail exists | `aliyun actiontrail DescribeTrails` | Trail in list | HALT; trail not found |

#### CLI Execution

```bash
aliyun actiontrail GetTrailStatus --Name {{user.trail_name}}
```

#### SDK Execution (JIT Go Fallback)

```go
request := &actiontrail.GetTrailStatusRequest{
    Name: tea.String("{{user.trail_name}}"),
}
response, err := client.GetTrailStatus(request)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Status received | `$.IsLogging` | Boolean value |
| Latest delivery time | `$.LatestDeliveryTime` | ISO 8601 timestamp |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Trail not found | `TrailNotFoundException` | HALT; suggest listing trails first |

### Operation: Start Logging

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Trail exists | `DescribeTrails` | Trail in list | HALT |
| Trail is disabled | `GetTrailStatus` | `IsLogging: false` | Already enabled; no action needed |

#### CLI Execution

```bash
aliyun actiontrail StartLogging --Name {{user.trail_name}}
```

#### SDK Execution (JIT Go Fallback)

```go
request := &actiontrail.StartLoggingRequest{
    Name: tea.String("{{user.trail_name}}"),
}
response, err := client.StartLogging(request)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Logging enabled | `aliyun actiontrail GetTrailStatus --Name {{user.trail_name}}` | `IsLogging: true` |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Trail not found | `TrailNotFoundException` | HALT |
| Already logging | `IsLogging: true` | Inform user; no action needed |

### Operation: Stop Logging

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Trail exists | `DescribeTrails` | Trail in list | HALT |
| Trail is enabled | `GetTrailStatus` | `IsLogging: true` | Already disabled; no action needed |

#### CLI Execution

```bash
aliyun actiontrail StopLogging --Name {{user.trail_name}}
```

#### SDK Execution (JIT Go Fallback)

```go
request := &actiontrail.StopLoggingRequest{
    Name: tea.String("{{user.trail_name}}"),
}
response, err := client.StopLogging(request)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Logging disabled | `aliyun actiontrail GetTrailStatus --Name {{user.trail_name}}` | `IsLogging: false` |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Trail not found | `TrailNotFoundException` | HALT |

### Operation: Update Trail

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Trail exists | `DescribeTrails` | Trail in list | HALT |

#### CLI Execution

```bash
aliyun actiontrail UpdateTrail \
  --Name {{user.trail_name}} \
  --OssBucketName {{user.oss_bucket_name}} \
  --EventRW All
```

#### SDK Execution (JIT Go Fallback)

```go
request := &actiontrail.UpdateTrailRequest{
    Name:          tea.String("{{user.trail_name}}"),
    OssBucketName: tea.String("{{user.oss_bucket_name}}"),
}
response, err := client.UpdateTrail(request)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Trail updated | `aliyun actiontrail DescribeTrails` | Updated configuration reflected |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Trail not found | `TrailNotFoundException` | HALT |
| Invalid parameter | `InvalidParameter` | HALT; check parameter values |

### Operation: Delete Trail

> **⚠️ DESTRUCTIVE — Requires explicit user confirmation before execution.**

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Trail exists | `DescribeTrails` | Trail in list | HALT; trail not found |
| User confirmation | Ask user: "Are you sure you want to delete trail `{{user.trail_name}}`?" | Explicit "yes" | HALT |

#### CLI Execution

```bash
aliyun actiontrail DeleteTrail --Name {{user.trail_name}}
```

#### SDK Execution (JIT Go Fallback)

```go
request := &actiontrail.DeleteTrailRequest{
    Name: tea.String("{{user.trail_name}}"),
}
response, err := client.DeleteTrail(request)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Trail deleted | `aliyun actiontrail DescribeTrails` | Trail no longer in list |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Trail not found | `TrailNotFoundException` | Already deleted; inform user |
| Dependency error | `DependencyViolation` | HALT; check if trail has active dependencies |

### Operation: Lookup Events

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Credentials | Env vars set | Non-empty | HALT |

#### CLI Execution

```bash
# Basic event lookup (last 7 days by default)
aliyun actiontrail LookupEvents

# Lookup with filters
aliyun actiontrail LookupEvents \
  --StartTime {{user.start_time}} \
  --EndTime {{user.end_time}} \
  --EventType ApiCall \
  --ServiceName Ecs \
  --MaxResults 50

# Lookup by specific event name
aliyun actiontrail LookupEvents \
  --EventName DeleteInstances \
  --ServiceName Ecs

# Lookup by AccessKey ID
aliyun actiontrail LookupEvents \
  --EventAccessKeyId {{user.access_key_id}}

# Paginated lookup
aliyun actiontrail LookupEvents \
  --MaxResults 50 \
  --NextToken {{output.next_token}}
```

#### SDK Execution (JIT Go Fallback)

```go
request := &actiontrail.LookupEventsRequest{
    StartTime: tea.String("{{user.start_time}}"),
    EndTime:   tea.String("{{user.end_time}}"),
    MaxResults: tea.Int32(50),
}
response, err := client.LookupEvents(request)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Events received | `$.Events` | Array of event records |
| Pagination | `$.NextToken` | Present if more results |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Throttling | `Throttling` | Retry with exponential backoff (max 3 attempts) |
| Invalid time range | `InvalidParameter` | HALT; ensure time range ≤ 30 days and within 90 days |
| Network error | `RequestError` | Retry with backoff |

### Operation: Get AccessKey Last Used Info

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Credentials | Env vars set | Non-empty | HALT |

#### CLI Execution

```bash
aliyun actiontrail GetAccessKeyLastUsedInfo --AccessKeyId {{user.access_key_id}}
```

#### SDK Execution (JIT Go Fallback)

```go
request := &actiontrail.GetAccessKeyLastUsedInfoRequest{
    AccessKeyId: tea.String("{{user.access_key_id}}"),
}
response, err := client.GetAccessKeyLastUsedInfo(request)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Info received | `$.AccountId` | Non-empty |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| AccessKey not found | `AccessKeyNotFoundException` | HALT; verify AccessKey ID |
| Throttling | `Throttling` | Retry with backoff |

### Operation: Enable Insight

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Credentials | Env vars set | Non-empty | HALT |

#### CLI Execution

```bash
# Enable IP insight — detect operations from unfamiliar IP addresses
aliyun actiontrail EnableInsight --InsightType IpInsight

# Enable API call rate insight — detect unusual API call volume
aliyun actiontrail EnableInsight --InsightType ApiCallRateInsight

# Enable API error rate insight — detect unusual API error spikes
aliyun actiontrail EnableInsight --InsightType ApiErrorRateInsight

# Enable AccessKey insight — detect unusual AccessKey call patterns
aliyun actiontrail EnableInsight --InsightType AkInsight

# Enable policy change insight — detect permission changes
aliyun actiontrail EnableInsight --InsightType PolicyChangeInsight

# Enable password change insight — detect password changes
aliyun actiontrail EnableInsight --InsightType PasswordChangeInsight

# Enable trail concealment insight — detect trail disable/deletion attempts
aliyun actiontrail EnableInsight --InsightType TrailConcealmentInsight
```

**Supported InsightType values (7 types):**

| InsightType | Detection Scenario | Best Practice Use Case |
|-------------|-------------------|----------------------|
| `IpInsight` | Operations from unfamiliar IP addresses | Detect AccessKey theft — hacker uses stolen AK from new region |
| `ApiCallRateInsight` | Unusual API call volume changes | Detect employee offboarding — bulk resource deletion spikes |
| `ApiErrorRateInsight` | Unusual API error rate spikes | Detect resource dependency breakage — deleted resource causes cascading failures |
| `AkInsight` | Unusual AccessKey call patterns | Detect AK misuse — abnormal call frequency or time pattern |
| `PolicyChangeInsight` | Permission/ policy changes | Detect unauthorized privilege escalation |
| `PasswordChangeInsight` | Password change events | Detect account compromise — unexpected password reset |
| `TrailConcealmentInsight` | Trail disable/deletion attempts | Detect audit evasion — attacker tries to cover tracks by disabling trails |

#### SDK Execution (JIT Go Fallback)

```go
request := &actiontrail.EnableInsightRequest{
    InsightType: tea.String("IpInsight"),
}
response, err := client.EnableInsight(request)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Insight enabled | `aliyun actiontrail GetInsightTypes` | InsightType appears in list |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Invalid type | `InsightTypeNotAvailable` | HALT; use one of: IpInsight, ApiCallRateInsight, ApiErrorRateInsight, AkInsight, PolicyChangeInsight, PasswordChangeInsight, TrailConcealmentInsight |

### Operation: Lookup Insight Events

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Credentials | Env vars set | Non-empty | HALT |
| Insight enabled | `aliyun actiontrail GetInsightTypes` | At least one InsightType enabled | HALT; enable insight first |

#### CLI Execution

```bash
# Query all insight events for a specific type
aliyun actiontrail LookupInsightEvents --InsightType IpInsight

# Query with time range
aliyun actiontrail LookupInsightEvents \
  --InsightType ApiCallRateInsight \
  --StartTime "2026-05-01T00:00:00Z" \
  --EndTime "2026-05-15T23:59:59Z" \
  --MaxResults 50
```

#### SDK Execution (JIT Go Fallback)

```go
request := &actiontrail.LookupInsightEventsRequest{
    InsightType: tea.String("IpInsight"),
    MaxResults:  tea.Int32(50),
}
response, err := client.LookupInsightEvents(request)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Events received | `$.InsightEvents` | Array of insight event records |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| No insight enabled | `InsightTypeNotAvailable` | HALT; enable the InsightType first |
| No events found | Empty array | Inform user: insight events may take up to 24 hours to generate after enabling |

### Operation: Disable Insight

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Credentials | Env vars set | Non-empty | HALT |
| Insight enabled | `aliyun actiontrail GetInsightTypes` | InsightType in list | HALT; insight already disabled |

#### CLI Execution

```bash
aliyun actiontrail DisableInsight --InsightType IpInsight
```

#### SDK Execution (JIT Go Fallback)

```go
request := &actiontrail.DisableInsightRequest{
    InsightType: tea.String("IpInsight"),
}
response, err := client.DisableInsight(request)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Insight disabled | `aliyun actiontrail GetInsightTypes` | InsightType no longer in list |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Insight not enabled | `InsightTypeNotAvailable` | HALT; insight type was not enabled |
| Invalid type | `InsightTypeNotAvailable` | HALT; use one of the valid types |

### Operation: Get Insight Types

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Credentials | Env vars set | Non-empty | HALT |

#### CLI Execution

```bash
aliyun actiontrail GetInsightTypes
```

#### SDK Execution (JIT Go Fallback)

```go
request := &actiontrail.GetInsightTypesRequest{}
response, err := client.GetInsightTypes(request)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Response received | `$.RequestId` | Non-empty |
| Insight types list | `$.InsightTypes` | Array of enabled insight type strings |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Network error | `RequestError` | Retry with backoff |

### Operation: Create Compliance Trail (Best Practice)

Creates a trail that meets compliance requirements: all regions, all event types,
OSS delivery with encryption, and immediate logging activation.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Credentials | Env vars set | Non-empty | HALT |
| OSS bucket | Verify bucket exists and supports SSE-KMS | Bucket accessible | HALT; create or configure OSS bucket first |
| Trail name | Validate: 6-36 chars, lowercase start | Valid name | Ask user for valid name |

#### CLI Execution

```bash
# Step 1: Create trail with all-region, all-event coverage
aliyun actiontrail CreateTrail \
  --Name {{user.trail_name}} \
  --OssBucketName {{user.oss_bucket_name}} \
  --OssKeyPrefix compliance-audit \
  --EventRW All \
  --TrailRegion All \
  --IsOrganizationTrail false

# Step 2: Enable logging immediately
aliyun actiontrail StartLogging --Name {{user.trail_name}}

# Step 3: Verify trail status
aliyun actiontrail GetTrailStatus --Name {{user.trail_name}}
```

**Compliance checklist:**
- [ ] Trail covers **all regions** (`--TrailRegion All`)
- [ ] Trail captures **all event types** (`--EventRW All`)
- [ ] Logging is **enabled** (`StartLogging`)
- [ ] OSS bucket uses **SSE-KMS** or **SSE-OSS** encryption (configure on OSS side)
- [ ] OSS bucket has **WORM policy** for data immutability (configure on OSS side)
- [ ] RAM permissions follow **least-privilege** principle

#### SDK Execution (JIT Go Fallback)

```go
// Step 1: Create compliance trail
createReq := &actiontrail.CreateTrailRequest{
    Name:          tea.String("{{user.trail_name}}"),
    OssBucketName: tea.String("{{user.oss_bucket_name}}"),
    EventRW:       tea.String("All"),
    TrailRegion:   tea.String("All"),
}
createResp, err := client.CreateTrail(createReq)

// Step 2: Enable logging
startReq := &actiontrail.StartLoggingRequest{
    Name: tea.String("{{user.trail_name}}"),
}
client.StartLogging(startReq)
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Trail created | `aliyun actiontrail DescribeTrails` | Trail in list with `TrailRegion: All` |
| All events | `$.TrailList[0].EventRW` | `All` |
| Logging enabled | `aliyun actiontrail GetTrailStatus --Name {{user.trail_name}}` | `IsLogging: true` |

#### Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| Trail exists | `TrailAlreadyExistsException` | HALT; use different name or update existing trail |
| Quota exceeded | `QuotaExceeded` | HALT; max 5 trails per region, delete unused ones first |

## Failure Recovery Reference

### Error Taxonomy

| Error Code | Description | Retryable | Max Retries | Backoff | Agent Action |
|------------|-------------|-----------|-------------|---------|--------------|
| `TrailNotFoundException` | Specified trail does not exist | No | 0 | — | HALT; suggest listing trails with DescribeTrails |
| `TrailAlreadyExistsException` | Trail name already in use | No | 0 | — | HALT; suggest a different trail name |
| `InvalidParameter` | Invalid parameter value | No | 0 | — | HALT; check parameter values against API docs |
| `InvalidParameterValue` | Parameter value out of range | No | 0 | — | HALT; check parameter constraints |
| `Throttling` | Request throttled | Yes | 3 | Exponential (1s, 2s, 4s) | Wait and retry; reduce request rate |
| `RequestError` | Network/connection error | Yes | 3 | Exponential (1s, 2s, 4s) | Check network connectivity; retry |
| `ServiceUnavailable` | Service temporarily unavailable | Yes | 3 | Exponential (2s, 4s, 8s) | Wait and retry; check service status |
| `InternalError` | Internal server error | Yes | 2 | Exponential (2s, 4s) | Retry; if persists, escalate |
| `AccessDenied` | Insufficient permissions | No | 0 | — | HALT; check RAM policy permissions |
| `InvalidAccessKeyId` | AccessKey ID not found | No | 0 | — | HALT; verify AccessKey ID |
| `SignatureDoesNotMatch` | Request signature mismatch | No | 0 | — | HALT; check credential configuration |
| `MissingParameter` | Required parameter missing | No | 0 | — | HALT; add required parameter |
| `DependencyViolation` | Resource has dependencies | No | 0 | — | HALT; resolve dependencies first |
| `QuotaExceeded` | Trail quota exceeded (max 5 per region) | No | 0 | — | HALT; delete unused trails or use different region |
| `AccessKeyNotFoundException` | AccessKey ID not found for audit | No | 0 | — | HALT; verify AccessKey ID |
| `InvalidEventType` | Invalid event type specified | No | 0 | — | HALT; use valid event types: ApiCall, ConsoleOperation, AliyunServiceEvent, PasswordReset, ConsoleSignin, ConsoleSignout |
| `InsightTypeNotAvailable` | Invalid or not-yet-enabled InsightType | No | 0 | — | HALT; use valid types: IpInsight, ApiCallRateInsight, ApiErrorRateInsight, AkInsight, PolicyChangeInsight, PasswordChangeInsight, TrailConcealmentInsight |
| `TimeRangeExceeded` | Time range exceeds 30 days or 90-day limit | No | 0 | — | HALT; adjust time range (max 30 days span, within 90 days) |

### HALT vs Retry Decision Matrix

| Condition | Decision | Rationale |
|-----------|----------|-----------|
| Business error (TrailNotFound, InvalidParameter, AccessDenied) | **HALT** | User or configuration action required |
| Throttling (Throttling) | **Retry** | Temporary; backoff resolves |
| Network error (RequestError, ServiceUnavailable) | **Retry** | Temporary infrastructure issue |
| Quota error (QuotaExceeded) | **HALT** | Requires resource cleanup or quota increase |
| Credential error (InvalidAccessKeyId, SignatureDoesNotMatch) | **HALT** | Requires credential fix |
| Missing parameter (MissingParameter) | **HALT** | Requires user input |