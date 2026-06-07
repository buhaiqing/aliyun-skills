---
name: alicloud-cms-ops
description: >-
  Use this skill when users need to monitor Alibaba Cloud resource health,
  investigate why a resource is performing poorly, set up monitoring alerts,
  troubleshoot alarm triggers, export monitoring data, or run proactive
  inspections — even if they don't explicitly name CloudMonitor, CMS,
  monitoring, or any specific metric names. Covers metric queries (CPU,
  memory, disk, network, IOPS, connections), alarm rule CRUD, custom/event
  monitoring, dashboards, anomaly pattern detection (CPU spikes, memory leaks,
  disk bottlenecks), alarm storm handling, and cross-resource correlation
  analysis. Also triggers on Chinese terms (云监控, 告警, 指标, 监控大盘,
  性能巡检, 主动巡检, 异常检测), vague health questions ("is my server OK?",
  "any anomalies?", "check metrics"), and monitoring data analysis requests.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "2.2.0"
  last_updated: "2026-06-04"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "Cms/2019-01-01 (RPC style)"
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun cms --help` and official CLI integration docs.
    CLI supports core CMS operations including DescribeMetricList,
    PutMetricAlarm, DescribeMetricAlarmList, DeleteMetricAlarm.
    Some advanced operations may require JIT Go SDK fallback.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud CloudMonitor (CMS) Operations Skill

## Overview

Alibaba Cloud CloudMonitor (CMS, 云监控) is the unified monitoring and alerting
service for Alibaba Cloud resources. It provides metrics collection, alarm
configuration, dashboard management, and custom monitoring capabilities. This
skill is an **operational runbook** for agents: explicit scope, credential rules,
pre-flight checks, **dual-path execution** (official **SDK/API** and **`aliyun`**
CLI), response validation, and failure recovery.

**Execution surface:** CLI-first with JIT Go SDK fallback. The `aliyun` CLI
supports CMS core operations. For operations not covered by CLI or requiring
complex request structures, JIT build a Go SDK script.

**API Versions:**
- **Cms/2019-01-01** (RPC style): Primary API version for metric queries and
  alarm management. Used by CLI.
- **Cms/2024-03-30** (ROA style): CloudMonitor 2.0 APIs for advanced features
  like context stores, memory stores, and ExecuteQuery. SDK-only.

### CLI applicability

- **`cli_applicability: dual-path`:** Official `aliyun` supports CMS core
  operations. Each execution flow documents both CLI and SDK paths.
- CLI coverage gaps: CloudMonitor 2.0 advanced features (context stores,
  memory stores, ExecuteQuery) are SDK-only.

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| DescribeMetricList | Query time-series metric data | Low | None |
| DescribeMetricLast | Query latest metric value | Low | None |
| PutMetricAlarm | Create or update alarm rule | Medium | Low |
| DescribeMetricAlarmList | List alarm rules | Low | None |
| DeleteMetricAlarm | Delete alarm rule | Medium | Medium |
| DescribeAnomalyConfidence | Anomaly confidence scoring for detected issues | Medium | Low |
| DescribeMetricPrediction | Predictive metric alerting with ML | Medium | Low |
| DescribeComplianceAlarms | Security compliance monitoring alarms | Low | None |
| DescribeIdleResources | Idle/underutilized resource detection | Low | None |
| DescribeCostOptimization | Cost optimization suggestions | Medium | Low |

## Phase 3-H: Dynamic Instance-Level Alert Management

> Dynamic instance discovery, confidence-scored auto-processing vs HITL, alarm blacklist, threshold tuning, event alerts, and composite expressions. Full GCL templates at [references/prompt-templates.md](references/prompt-templates.md), CLI commands at [references/cli-usage.md](references/cli-usage.md).

| Capability | CLI Command | Confidence | Rollback |
|------------|-------------|-----------|----------|
| Dynamic Instance Discovery | Cross-skill delegation | Auto if ≥80 | Delete rule |
| Alarm Blacklist | `CreateMetricRuleBlackList` | Auto if ≥80 | DeleteMetricRuleBlackList |
| Threshold Tuning | `PutResourceMetricRule` | Auto | Revert via PutResourceMetricRule |
| Event-Based Alerts | `PutEventRule` | Auto | DeleteEventRule |
| Composite Expressions | `PutResourceMetricRule + ExpressionRaw` | HITL | DeleteMetricRule |

**HITL triggers:** instance count = 0 or > 100, critical production env, permanent silence, first execution of filter pattern, complex composite filters.

**Safety protocol:** Auto-diagnose empty instance lists (case mismatch, status filter), validate tag existence before execution, verify all instances post-creation, each operation has a rollback delete/disable.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "CloudMonitor", "CMS", "云监控", "监控", "alarm", "告警",
  "metric", "指标", "dashboard", "监控大盘", "异常检测", "主动巡检"
- Task involves monitoring resource health, investigating performance issues
  (high CPU, memory pressure, disk bottlenecks, network saturation)
- Task involves querying metrics (CPU, memory, disk, network, IOPS, connections)
- Task involves creating, modifying, listing, or deleting alarm rules
- Task involves configuring alarm contacts or contact groups
- Task involves custom monitoring (PutCustomMetric, custom metrics)
- Task involves monitoring data export or analysis
- Task involves anomaly pattern detection or multi-metric correlation analysis
- Task involves alarm storm handling or cross-resource incident aggregation
- Task involves proactive monitoring inspection across resources

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to:
  `alicloud-billing-ops` (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops`
  (when present)
- Task is about creating/modifying the monitored resources themselves
  (e.g., creating ECS instances) → delegate to the respective product skill
  (e.g., `alicloud-ecs-ops`)
- Task requires CloudMonitor 2.0 advanced features not yet covered → note
  limitation; do not invent undocumented APIs

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.namespace}}` | Cloud product namespace (e.g., acs_ecs_dashboard) | Ask once; reuse |
| `{{user.metric_name}}` | Metric name (e.g., CPUUtilization) | Ask once; reuse |
| `{{user.instance_id}}` | Resource instance ID | Ask once; reuse |
| `{{user.alarm_name}}` | Alarm rule name | Ask once; reuse |
| `{{user.contact_group}}` | Contact group name for alarm notifications | Ask once; reuse |
| `{{user.group_name}}` | Monitor group name | Ask once; reuse |
| `{{user.account_id}}` | Alibaba Cloud account ID (for MNS topic ARN) | Ask once; reuse |
| `{{user.topic_name}}` | MNS topic name for alarm actions | Ask once; reuse |
| `{{output.metric_data}}` | Metric query result | Parse per OpenAPI spec |
| `{{output.alarm_id}}` | Alarm rule ID from API response | Parse per OpenAPI spec |
| `{{user.prediction_period}}` | Prediction time window (seconds) | Ask once; reuse |
| `{{user.confidence_threshold}}` | Minimum confidence for action | Ask once; reuse |
| `{{user.cost_threshold}}` | Cost anomaly threshold ($) | Ask once; reuse |
| `{{output.confidence_score}}` | Anomaly confidence score | Parse from prediction API |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response
  shapes.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** `PutMetricAlarm` is idempotent (same alarm name overwrites).
  `CreateMonitorGroup` may fail with `ResourceAlreadyExists`.

### Common Namespaces (Use `DescribeProjectMeta` for latest)

```
aliyun cms DescribeProjectMeta --RegionId {{user.region}}
```

| Product | Namespace |
|---------|-----------|
| ECS | acs_ecs_dashboard |
| RDS | acs_rds_dashboard |
| SLB | acs_slb_dashboard |
| Redis | acs_kvstore_dashboard |
| Kubernetes | acs_k8s_dashboard |

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| DescribeMetricList | `$.Datapoints` | array | Metric data points |
| DescribeMetricList | `$.Period` | string | Aggregation period |
| PutMetricAlarm | `$.Success` | boolean | Operation success |
| PutMetricAlarm | `$.Code` | string | Response code |
| DescribeMetricAlarmList | `$.AlarmList` | array | List of alarm rules |
| DeleteMetricAlarm | `$.Success` | boolean | Operation success |

### Rate Limits

- **Free quota:** 1M calls/month for DescribeMetric APIs
- **Throttle:** 50 calls/second per account
- **Error:** `Throttling.User` / `Request was denied due to user flow control`

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.1.0 | 2026-05-14 | Enhanced anomaly detection framework: CLI install diagnosis, 4-layer environment checks, intelligent root cause analysis, auto-heal engine, degradation strategies |
| 2.0.0 | 2026-05-14 | Initial CMS skill with dual-path execution, metric queries, alarm management |

## Enhanced Anomaly Detection & Self-Healing

> 4-layer framework (Env → Dep → Net → Perm) for CLI/SDK diagnosis, RCA pattern matching, and auto-healing. Full scripts and patterns at [references/cli-install-diagnosis.md](references/cli-install-diagnosis.md).

**Execution protocol on failure:**
```
Step 1: Quick Health Check (`command -v aliyun`) → PASS? proceed. FAIL → Step 2
Step 2: Level 1 (Env): OS/shell/PATH/package manager/disk space
Step 3: Level 2 (Dep): Go version, SDK resolution, proxy config
Step 4: Level 3 (Net): DNS (metrics.aliyuncs.com), CMS endpoint, Go proxy
Step 5: Level 4 (Perm): Env vars exist + dry-run DescribeProjectMeta
Step 6: RCA: Cross-layer pattern matching + confidence scoring
Step 7: Auto-Heal: heal_missing_cli|go|sdk_deps|proxy_config|env_vars
Step 8: Degrade/Report: Heal succeeded → retry. Fail → degrade strategy
```

**Degradation modes:** FULL (CLI+SDK) → NORMAL_CLI → NORMAL_SDK → DEGRADED_SDK → CRIPPLED (AK invalid → HALT) → BLOCKED (network → HALT). Agent MUST log mode and notify if not FULL.

**Quick check snippet:**
```bash
if ! command -v aliyun &>/dev/null; then
  echo "[CMS-ENV] CLI not found. Running env diagnosis..."
  command -v curl &>/dev/null && /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
  command -v go &>/dev/null && echo "[CMS-DEGRADE] Falling back to JIT Go SDK..."
fi
```

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI preferred, SDK fallback) →
Validate → Recover**.

---

### Operation: Query Metric Data (DescribeMetricList)

Query time-series metric data for a specific cloud product and metric.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI / deps | `aliyun version` | Exit code 0 | Run **Enhanced Anomaly Detection** (see above): Level 1-2-3-4 checks → auto-heal → degrade |
| Credentials | Env vars set | Non-empty keys | HALT; run **Level 4 Permission Check** → auto-heal env vars or user configures env |
| CLI credential validity | `aliyun cms DescribeProjectMeta` dry-run | `"Code":"200"` | Run **Root Cause Analysis**: if Forbidden → RAM policy; if InvalidAK → rotate AK |
| Namespace validity | Check against known namespaces table | Valid namespace | Suggest valid namespace |
| Metric validity | Call DescribeMetricMetaList | Metric exists | Suggest valid metrics |
| Time range | StartTime < EndTime, within retention | Valid range | Adjust range |

#### Execution — CLI (Primary Path)

```bash
aliyun cms DescribeMetricList \
  --RegionId "{{user.region}}" \
  --Namespace "{{user.namespace}}" \
  --MetricName "{{user.metric_name}}" \
  --Period 60 \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
```

**Critical CLI Notes:**
- `--Period` values: 15, 60, 300, 900, 3600 (seconds).
- `--Dimensions` is a JSON array string; must be properly escaped.
- Time format: ISO 8601 (e.g., `2026-05-14T10:00:00Z`).
- Time command: `date -u -v-1H` works on macOS; on Linux use `date -u -d '1 hour ago'`.
- Storage duration depends on Period: <60s → 7 days, 60s → 31 days, ≥300s → 91 days.

#### Execution — JIT Go SDK (Fallback Path)

```go
package main

import (
    "fmt"
    "os"
    "time"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    cms20190101 "github.com/alibabacloud-go/cms-20190101/v7/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("metrics.aliyuncs.com"),
    }

    client, err := cms20190101.NewClient(config)
    if err != nil {
        panic(err)
    }

    now := time.Now().UTC()
    startTime := now.Add(-1 * time.Hour).Format("2006-01-02T15:04:05Z")
    endTime := now.Format("2006-01-02T15:04:05Z")

    request := &cms20190101.DescribeMetricListRequest{
        RegionId:  tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
        Namespace: tea.String("{{user.namespace}}"),
        MetricName: tea.String("{{user.metric_name}}"),
        Period:    tea.String("60"),
        StartTime: tea.String(startTime),
        EndTime:   tea.String(endTime),
        Dimensions: tea.String(fmt.Sprintf(`{"instanceId":"%s"}`, "{{user.instance_id}}")),
    }

    response, err := client.DescribeMetricList(request)
    if err != nil {
        panic(err)
    }

    fmt.Println(tea.ToString(response.Body))
}
```

Execute:
```bash
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/cms-20190101/v7/client
go run ./main.go
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Response success | `$.Success` == true | true |
| Data presence | `$.Datapoints` non-empty | At least 1 data point |
| Data freshness | Last timestamp within Period | Recent data |

#### Recovery

| Error | Action | Auto-Heal |
|-------|--------|-----------|
| `Throttling.User` | Backoff 5s, retry up to 3 times | Built-in retry with exponential backoff |
| `Request was denied due to user flow control` | Backoff 5s, retry up to 3 times | Built-in retry |
| `InvalidParameter` | Verify Namespace, MetricName, Dimensions | Check against metric metadata |
| `InvalidAccessKeyId` / `SignatureDoesNotMatch` | AK invalid or expired | Run **Level 4 Permission Check** → guide user to rotate AK |
| `ResourceNotFound` | Verify instance exists in target region | Check via product-specific skill |
| `Forbidden` | Check RAM policy for `AliyunCloudMonitorReadOnlyAccess` | Run **Root Cause Analysis** → `PERM_ROOT_RAM` pattern |
| CLI not found | CLI unavailable | Run **Quick Health Check** → auto-heal `heal_missing_cli` → degrade to JIT SDK |
| Network timeout | CMS endpoint unreachable | Run **Level 3 Network Check** → auto-heal proxy/DNS → degrade to VPC endpoint |

---

### Operation: Create or Update Alarm Rule (PutMetricAlarm)

Create or update a metric-based alarm rule.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI / deps | `aliyun version` | Exit code 0 | Run **Enhanced Anomaly Detection**: Level 1-2-3-4 → auto-heal → degrade |
| Credentials | Env vars set | Non-empty keys | HALT; run **Level 4 Permission Check** |
| CLI credential validity | `aliyun cms DescribeProjectMeta` dry-run | `"Code":"200"` | Run **Root Cause Analysis** → auto-heal or report |
| Resource exists | Describe resource via product skill | Resource found | HALT; create resource first |
| Contact group | DescribeContactGroupList | Group exists | Create contact group first |
| Alarm name | DescribeMetricAlarmList | Name not conflict | Proceed (PutMetricAlarm overwrites) |

#### Execution — CLI (Primary Path)

```bash
aliyun cms PutMetricAlarm \
  --RegionId "{{user.region}}" \
  --AlarmName "{{user.alarm_name}}" \
  --Namespace "{{user.namespace}}" \
  --MetricName "{{user.metric_name}}" \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Statistics "Average" \
  --ComparisonOperator ">=" \
  --Threshold 80 \
  --Period 300 \
  --EvaluationCount 3 \
  --ContactGroups '["{{user.contact_group}}"]' \
  --AlarmActions '["acs:mns:{{user.region}}:{{user.account_id}}:topics/{{user.topic_name}}"]' \
  --EffectiveInterval "00:00-23:59"
```

**Critical CLI Notes:**
- `--Statistics`: Average, Minimum, Maximum, Value (default: Average).
- `--ComparisonOperator`: `>`, `>=`, `<`, `<=`, `==`, `!=`.
- `--Period`: Must match metric's supported periods (typically 60 or 300).
- `--EvaluationCount`: Consecutive periods before triggering (default: 3).
- `--AlarmActions`: JSON array of MNS topic ARNs or other action endpoints.
- `--EffectiveInterval`: Time window format "HH:MM-HH:MM".
- This operation is **idempotent** — same AlarmName overwrites existing rule.

#### Execution — JIT Go SDK (Fallback Path)

```go
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    cms20190101 "github.com/alibabacloud-go/cms-20190101/v7/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("metrics.aliyuncs.com"),
    }

    client, err := cms20190101.NewClient(config)
    if err != nil {
        panic(err)
    }

    request := &cms20190101.PutMetricAlarmRequest{
        RegionId:          tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
        AlarmName:         tea.String("{{user.alarm_name}}"),
        Namespace:         tea.String("{{user.namespace}}"),
        MetricName:        tea.String("{{user.metric_name}}"),
        Dimensions:        tea.String(fmt.Sprintf(`{"instanceId":"%s"}`, "{{user.instance_id}}")),
        Statistics:        tea.String("Average"),
        ComparisonOperator: tea.String(">="),
        Threshold:         tea.String("80"),
        Period:            tea.String("300"),
        EvaluationCount:   tea.String("3"),
        ContactGroups:     tea.String(`["{{user.contact_group}}"]`),
        EffectiveInterval: tea.String("00:00-23:59"),
    }

    response, err := client.PutMetricAlarm(request)
    if err != nil {
        panic(err)
    }

    fmt.Println(tea.ToString(response.Body))
}
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Response success | `$.Success` == true | true |
| Alarm created | DescribeMetricAlarmList with AlarmName | Rule found with matching config |

#### Recovery

| Error | Action | Auto-Heal |
|-------|--------|-----------|
| `InvalidParameter` | Verify Statistics, ComparisonOperator, Threshold values | Check against metric metadata |
| `ResourceNotFound` | Verify Namespace, MetricName, or Dimensions | Check via product-specific skill |
| `ContactGroupNotFound` | Create contact group via PutContactGroup | Auto-create via PutContactGroup if user confirms |
| `QuotaExceeded` | Check alarm rule quota; delete unused rules | List and identify stale rules for cleanup |
| `Forbidden` | Check RAM policy for write permissions | Run **Root Cause Analysis** → `PERM_ROOT_RAM` → suggest `AliyunCloudMonitorFullAccess` |
| CLI not found | CLI unavailable | Run **Quick Health Check** → auto-heal → degrade to JIT SDK |

---

### Operation: List Alarm Rules (DescribeMetricAlarmList)

List metric alarm rules with optional filtering.

#### Execution — CLI (Primary Path)

```bash
aliyun cms DescribeMetricAlarmList \
  --RegionId "{{user.region}}" \
  --Namespace "{{user.namespace}}" \
  --MetricName "{{user.metric_name}}" \
  --PageSize 50 \
  --PageNumber 1
```

**Optional filters:**
- `--AlarmName`: Filter by alarm name (supports wildcard).
- `--State`: Filter by state (OK, ALARM, INSUFFICIENT_DATA).
- `--EnableState`: true or false.

#### Execution — JIT Go SDK (Fallback Path)

```go
// Similar pattern to DescribeMetricList
// Use cms20190101.DescribeMetricAlarmListRequest
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Response success | `$.Success` == true | true |
| Data presence | `$.AlarmList` non-empty | Rules returned |

---

### Operation: Delete Alarm Rule (DeleteMetricAlarm)

Delete one or more metric alarm rules.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI / deps | `aliyun version` | Exit code 0 | Run **Enhanced Anomaly Detection** → auto-heal → degrade |
| Credentials | Env vars set | Non-empty keys | HALT; run **Level 4 Permission Check** |
| Alarm exists | DescribeMetricAlarmList | Alarm found | HALT; alarm not found |
| User confirmation | Prompt user | Confirmed | HALT |

#### Execution — CLI (Primary Path)

```bash
aliyun cms DeleteMetricAlarm \
  --RegionId "{{user.region}}" \
  --Id "{{user.alarm_id}}"
```

**Batch delete:**
```bash
aliyun cms DeleteMetricAlarm \
  --RegionId "{{user.region}}" \
  --Id "id1,id2,id3"
```

#### Execution — JIT Go SDK (Fallback Path)

```go
// Use cms20190101.DeleteMetricAlarmRequest with Id field
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Response success | `$.Success` == true | true |
| Alarm deleted | DescribeMetricAlarmList with Id | Empty result |

#### Recovery

| Error | Action | Auto-Heal |
|-------|--------|-----------|
| `ResourceNotFound` | Alarm already deleted or ID invalid | Verify via DescribeMetricAlarmList |
| `Forbidden` | Check RAM policy for delete permissions | Run **Root Cause Analysis** → `PERM_ROOT_RAM` → suggest delete permission |
| CLI not found | CLI unavailable | Run **Quick Health Check** → auto-heal → degrade to JIT SDK |

---

### Operation: Query Latest Metric Data (DescribeMetricLast)

Query the most recent data point for a metric.

#### Execution — CLI (Primary Path)

```bash
aliyun cms DescribeMetricLast \
  --RegionId "{{user.region}}" \
  --Namespace "{{user.namespace}}" \
  --MetricName "{{user.metric_name}}" \
  --Period 60 \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
```

**Note:** Shares the 1M/month free quota with DescribeMetricList.

---

### Operation: Query Metric Metadata (DescribeMetricMetaList)

List available metrics for a namespace.

#### Execution — CLI (Primary Path)

```bash
aliyun cms DescribeMetricMetaList \
  --RegionId "{{user.region}}" \
  --Namespace "{{user.namespace}}"
```

---

### Operation: Create Monitor Group (CreateMonitorGroup)

Create an application monitor group.

#### Execution — CLI (Primary Path)

```bash
aliyun cms CreateMonitorGroup \
  --RegionId "{{user.region}}" \
  --GroupName "{{user.group_name}}" \
  --ContactGroups '["{{user.contact_group}}"]'
```

---

### Operation: Delete Monitor Group (DeleteMonitorGroup)

Delete a monitor group. **Requires user confirmation.**

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI / deps | `aliyun version` | Exit code 0 | Run **Enhanced Anomaly Detection** → auto-heal → degrade |
| Credentials | Env vars set | Non-empty keys | HALT; run **Level 4 Permission Check** |
| Group exists | DescribeMonitorGroups | Group found | HALT; group not found |
| No active alarms | DescribeMetricAlarmList with group filter | No alarms reference group | Warn user; proceed with caution |
| User confirmation | Prompt user | Confirmed | HALT |

#### Execution — CLI (Primary Path)

```bash
aliyun cms DeleteMonitorGroup \
  --RegionId "{{user.region}}" \
  --GroupId "{{user.group_id}}"
```

#### Execution — JIT Go SDK (Fallback Path)

```go
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    cms20190101 "github.com/alibabacloud-go/cms-20190101/v7/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("metrics.aliyuncs.com"),
    }

    client, err := cms20190101.NewClient(config)
    if err != nil {
        panic(err)
    }

    request := &cms20190101.DeleteMonitorGroupRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
        GroupId:  tea.String("{{user.group_id}}"),
    }

    response, err := client.DeleteMonitorGroup(request)
    if err != nil {
        panic(err)
    }

    fmt.Println(tea.ToString(response.Body))
}
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Response success | `$.Success` == true | true |
| Group deleted | DescribeMonitorGroups with GroupId | Empty result |

#### Recovery

| Error | Action | Auto-Heal |
|-------|--------|-----------|
| `InvalidParameter` | Verify GroupId | Check via DescribeMonitorGroups |
| `ResourceNotFound` | Group already deleted or ID invalid | Verify via DescribeMonitorGroups |
| `Forbidden` | Check RAM policy for delete permissions | Run **Root Cause Analysis** → `PERM_ROOT_RAM` pattern |
| CLI not found | CLI unavailable | Run **Quick Health Check** → auto-heal → degrade to JIT SDK |

---

## Safety Gates

### Destructive Operations

| Operation | Confirmation Required | Safety Check |
|-----------|----------------------|--------------|
| DeleteMetricAlarm | YES — prompt user | Verify alarm ID exists |
| DeleteMonitorGroup | YES — prompt user | Verify group has no active alarms |
| DeleteContactGroup | YES — prompt user | Verify group not used by active alarms |

### Credential Handling

- **NEVER** log `ALIBABA_CLOUD_ACCESS_KEY_SECRET`.
- Mask in all output: `ALIBABA_CLOUD_ACCESS_KEY_SECRET=abcd****` (first 4 chars + `****`).
- Verify env vars exist before execution; HALT if missing.

## Error Handling Reference

| Error Code | Meaning | Action |
|------------|---------|--------|
| `Throttling.User` | Rate limit exceeded | Exponential backoff (1s, 2s, 4s), max 3 retries |
| `InvalidParameter` | Invalid request parameter | Verify parameter values against API docs |
| `ResourceNotFound` | Resource does not exist | Verify resource ID, region, namespace |
| `Forbidden` | Permission denied | Check RAM policy; require `AliyunCloudMonitorFullAccess` or `AliyunCloudMonitorReadOnlyAccess` |
| `QuotaExceeded` | Quota limit reached | Check quota; request increase if needed |
| `InsufficientBalance` | Account balance insufficient | HALT; user must top up account |
| `InternalError` | Service internal error | Retry after 5s; escalate if persistent |

## Prerequisites

1. **Install `aliyun` CLI** (primary):
   ```bash
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   ```

2. **Bootstrap Go runtime** (JIT SDK fallback): See [integration.md](references/integration.md) for full self-healing install. Quick start:
   ```bash
   if ! command -v go &> /dev/null; then
       OS=$(uname -s | tr '[:upper:]' '[:lower:]'); ARCH=$(uname -m)
       [ "$ARCH" = "x86_64" ] && ARCH="amd64"; [ "$ARCH" = "aarch64" ] && ARCH="arm64"
       GO_VERSION=$(curl -sL "https://go.dev/dl/?mode=json" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['version'])" 2>/dev/null)
       curl -fsSL "https://go.dev/dl/${GO_VERSION}.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
       export PATH="/tmp/go-runtime/go/bin:$PATH" GOMODCACHE="/tmp/go-modcache"
       export GOPROXY="https://goproxy.cn,direct"
   fi
   ```

3. **Configure Credentials** — Environment variables (recommended for Agent execution):
   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```
   > **IMPORTANT:** When outputting to console, use masking: `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"`.

4. **Verify**:
   ```bash
   aliyun cms DescribeProjectMeta --RegionId {{user.region}}
   ```

> **Security:** Never commit `.env` to version control. All credentials use `{{env.*}}` placeholders — never real values.

## Cross-Skill Anomaly Detection & Diagnosis (AIOps)

> P0 capabilities for multi-metric correlation inspection, alarm-driven cross-skill root-cause diagnosis, and proactive monitoring workflows. Full reference at [references/aiops-inspection.md](references/aiops-inspection.md).

| Operation | Purpose | Key CLI Commands | Reference |
|-----------|---------|-----------------|-----------|
| Multi-Metric Inspection | Joint metric inspection for composite anomaly patterns | `DescribeMetricList` across 4+ metrics | [Full spec](references/aiops-inspection.md#multi-metric-anomaly-inspection) |
| Alarm-Driven Diagnosis | 5-step cross-skill root-cause diagnosis triggered by CMS alarms | `DescribeMetricLast` → product DescribeInstances → multi-metric | [Full spec](references/aiops-inspection.md#alarm-driven-cross-skill-diagnosis) |
| Proactive Inspection | Periodic multi-resource inspection to find issues before incidents | `DescribeMonitorGroupInstances` → `DescribeMetricList` per resource | [Full spec](references/aiops-inspection.md#proactive-monitoring-inspection) |
| Alarm Storm Handling | Aggregation and suppression when >10 alarms in 5min | `DescribeMetricAlarmList` with State=ALARM | [Full spec](references/aiops-inspection.md#alarm-storm-handling) |

**Diagnosis decision tree:**
```
[CMS Alarm] → Verify via DescribeMetricLast
  ├─ Normal → False positive; check rule config
  └─ Abnormal → Check resource (delegate by namespace)
       → Multi-metric correlation → DAS deep diagnosis → Unified report
```

## Advanced Analytics

以下深度分析文档仅在用户明确需要时加载，**不要在常规操作中读取**：

| 场景 | 文档 |
|------|------|
| 性能预测、容量规划 | [advanced/aiops-prediction.md](references/advanced/aiops-prediction.md) |
| 成本分析、资源优化 | [advanced/finops-analysis.md](references/advanced/finops-analysis.md) |

---

## Well-Architected Assessment

Evaluated per Alibaba Cloud [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).

| Pillar | Key Guidance |
|--------|-------------|
| **Security** | IAM: `cms:Describe*` read-only, `cms:Put*` write. `{{env.*}}` only — never print secrets. Mask contact info in output |
| **Stability** | `EvaluationCount ≥ 3` for production. EffectiveInterval for maintenance windows. Cross-skill delegation for DR (DAS→DB, ECS→compute, SLB→network) |
| **Cost** | 1M calls/month free. Use Period=300s to reduce volume. Webhooks > SMS. Disable 30d-unused rules |
| **Efficiency** | Multi-metric alarms reduce noise. Use alarm templates for consistency. JSON output for CI/CD |
| **Performance** | Longer Period (300s > 60s). Group via MonitorGroup. Use DescribeMetricLast for latest value

## Reference Directory

- [CLI Usage Guide](references/cli-usage.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [Core Concepts](references/core-concepts.md)
- [Troubleshooting Guide](references/troubleshooting.md) — 含根因定位决策树（AIOps）
- [Monitoring & Alerts](references/monitoring.md)
- [Integration Guide](references/integration.md) — 含跨 Skill 委托矩阵
- [Knowledge Base](references/knowledge-base.md) — 常见故障模式库
- [Observability Integration](references/observability.md) — Metrics/Logs/Traces 联动
- [Prompts Handbook](references/prompts.md) — 常用提示词手册
- [AIOps Inspection](references/aiops-inspection.md) — Multi-metric anomaly detection, alarm-driven cross-skill diagnosis, proactive inspection, alarm storm handling
- [AIOps Prediction](references/advanced/aiops-prediction.md)
- [SecOps Monitoring](references/secops-monitoring.md)
- [FinOps Analysis](references/advanced/finops-analysis.md)

## Operational Best Practices

- **Least privilege:** Use `AliyunCloudMonitorReadOnlyAccess` for read-only operations; use `AliyunCloudMonitorFullAccess` only when creating or modifying resources.
- **Rate limiting:** Implement client-side rate limiting (max 50 calls/second). Use longer Period values (300s instead of 60s) to reduce API call volume.
- **Cost awareness:** Metric query APIs share a 1,000,000 calls/month free quota. Monitor usage to avoid unexpected charges.
- **Alarm tuning:** Set appropriate EvaluationCount (3+ for production) to avoid false positives. Use EffectiveInterval to suppress alarms during maintenance windows.
- **Data retention:** Choose Period based on retention needs — <60s (7 days), 60s (31 days), ≥300s (91 days).

---

## Quality Gate (GCL)

Phase 5 rollout for `recommended` skills per [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Recommended** (Phase 5, `max_iter=3`) |
| Most-scrutinized | `DeleteMetricAlarm` (backup alarm rule JSON; monitoring coverage lost), `DeleteMonitorGroup` (group alarms + contacts detached) |

### Changelog
1.0.0 | 2026-06-04 | Phase 5 `recommended` rollout for cms-ops.

---

## References

- [Alibaba Cloud CMS API Docs](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/api-reference-cms-2019-01-01/)
- [Alibaba Cloud CLI CMS Integration](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/cli-integration-example)
- [Agent Skill OpenSpec](https://agentskills.io/specification)


## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `dual-path`，CLI/SDK 已覆盖，无需 code snippets.
