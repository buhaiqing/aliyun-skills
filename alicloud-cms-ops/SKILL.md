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
  version: "2.0.0"
  last_updated: "2026-05-14"
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

### Delegation Rules

- If alarm rule depends on a specific resource, verify the resource exists
  (via the resource's skill) before creating alarm rules.
- Multi-product monitoring: handle each product's metrics with its skill for
  resource verification; use this skill for alarm configuration.

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

## Enhanced Anomaly Detection & Self-Healing (Agent-Readable)

> This section defines the **4-layer anomaly detection framework** for CLI installation issues, **intelligent root cause analysis engine**, and **auto-healing capabilities**. Refer to [cli-install-diagnosis.md](references/cli-install-diagnosis.md) for complete diagnostic scripts.

### Anomaly Detection Architecture

```
 Level 1 (Env) → Level 2 (Dep) → Level 3 (Net) → Level 4 (Perm)
     │               │               │               │
     └───────────────┴───────────────┴───────────────┘
                         │
                    ┌────▼────────────────────────────┐
                    │  Root Cause Analysis Engine     │
                    │  (correlation → pattern → RCA)  │
                    └────┬────────────────────────────┘
                         │
                    ┌────▼────────────────────────────┐
                    │  Auto-Heal Engine               │
                    │  heal_cli / heal_go / heal_sdk  │
                    └────┬────────────────────────────┘
                         │
                    ┌────▼────────────────────────────┐
                    │  Degradation Matrix             │
                    │  FULL → NORMAL → DEGRADED → HALT│
                    └─────────────────────────────────┘
```

### Anomaly Detection Execution Protocol

When any CLI command fails, execute in order:

```
Step 1 — Quick Health Check: `command -v aliyun` → PASS proceed, FAIL → Step 2
Step 2 — Level 1 (Env): OS/shell/PATH/package manager/disk space
Step 3 — Level 2 (Dep): Go version ≥1.21, SDK resolution, proxy config
Step 4 — Level 3 (Net): DNS (metrics.aliyuncs.com), CMS endpoint, Go proxy
Step 5 — Level 4 (Perm): Env vars exist + dry-run DescribeProjectMeta
Step 6 — RCA: Cross-layer pattern matching + confidence scoring
Step 7 — Auto-Heal: heal_missing_cli|go|sdk_deps|proxy_config|env_vars
Step 8 — Degrade/Report: Heal succeeded → retry. Fail → degrade strategy
```

### Root Cause Analysis — Pattern Matching Rules

The anomaly analyzer correlates findings across all 4 layers. Below are the supported patterns:

| Pattern ID | Rule | Confidence | Impact | Auto-Fix Available |
|-----------|------|-----------|--------|-------------------|
| `NET_ROOT_DNS` | DNS failure + CMS endpoint unreachable | 0.95 | ALL_OPERATIONS | Partial (add DNS) |
| `NET_ROOT_ISOLATED` | CLI source + GitHub both unreachable | 0.90 | CLI_INSTALL_FAILED + SDK_DOWNLOAD_FAILED | Yes (proxy config) |
| `PERM_ROOT_RAM` | AK set + API returns Forbidden | 0.95 | API_CALLS_FORBIDDEN | No (manual RAM policy) |
| `DEP_ROOT_GO_MISSING` | Go not found + SDK resolve failed | 0.95 | JIT_SDK_FALLBACK_UNAVAILABLE | Yes (auto install Go) |
| `PERM_ROOT_AK_INVALID` | CMS endpoint reachable + AK invalid | 0.95 | ALL_API_CALLS_FAIL | No (manual AK rotation) |
| `ENV_ROOT_INSTALL_ENV` | Low disk + no download tool | 0.85 | CLI_INSTALL_FAILED | Yes (clean + install) |
| `NET_ROOT_SLOW_BANDWIDTH` | Server reachable but slow | 0.80 | INSTALL_TIMEOUT | Yes (proxy/mirror) |
| `ENV_ROOT_MULTI_WARN` | 3+ environment warnings | 0.70 | INSTALL_MAY_FAIL | Partial (sequential fix) |

### Degradation Strategy Application

After diagnosis, determine the execution mode:

| System Health | Execution Mode | Behavior | Agent Action |
|--------------|---------------|----------|-------------|
| CLI + SDK both available | **FULL** | Normal dual-path execution | Use CLI primary, SDK fallback |
| CLI only, SDK unavailable | **NORMAL_CLI** | CLI-only operations | Use CLI for covered ops; note SDK limitation |
| SDK only, CLI unavailable | **NORMAL_SDK** | SDK-only operations | Use JIT Go SDK for all operations |
| CLI install failed, Go available | **DEGRADED_SDK** | SDK with auto-install hint | Use SDK; suggest user install CLI |
| AK invalid/expired | **CRIPPLED** | All API calls fail | HALT; guide user to rotate AK |
| Network fully down | **BLOCKED** | No operation possible | HALT; report network diagnosis |
| Partial network (VPC only) | **DEGRADED_VPC** | Internal endpoint only | Use metrics-intra.aliyuncs.com |

Agent MUST log the degradation mode and notify the user when mode is not FULL.

### Quick Health Check Snippet

For any operation where the CLI is expected to be available:

```bash
# Quick health check — fast path before full diagnosis
if ! command -v aliyun &>/dev/null; then
  echo "[CMS-ENV] aliyun CLI not found. Running environment diagnosis..."
  # Reference: cli-install-diagnosis.md for full diagnostic scripts
  # Attempt auto-heal:
  if command -v curl &>/dev/null || command -v brew &>/dev/null; then
    echo "[CMS-HEAL] Attempting auto-install..."
    # macOS: brew install aliyun-cli
    # Linux/macOS: /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
  else
    echo "[CMS-HEAL] Cannot auto-install. Manual install required."
    echo "  See: https://aliyuncli.alicdn.com/install.sh"
    # Fall back to JIT Go SDK if Go is available
    if command -v go &>/dev/null; then
      echo "[CMS-DEGRADE] Falling back to JIT Go SDK..."
    else
      echo "[CMS-FATAL] Neither CLI nor Go runtime available."
      echo "  Install Go 1.21+: https://go.dev/dl/"
    fi
  fi
fi
```

### Reference Document

For complete diagnostic scripts, anomaly patterns, and auto-heal implementations, see:

- [CLI Install Diagnosis & Self-Healing](references/cli-install-diagnosis.md)

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
       curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
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

---

## Cross-Skill Anomaly Detection & Diagnosis (AIOps)

> This section defines **P0** capabilities for multi-metric correlation inspection, alarm-driven cross-skill root-cause diagnosis, and proactive monitoring workflows. These flows elevate `alicloud-cms-ops` from a metric-query tool to an **intelligent AIOps entrypoint**.

---

### Operation: Multi-Metric Anomaly Inspection

对指定资源执行多指标联合巡检，识别复合异常模式。当单一指标正常但多指标组合呈现风险特征时，此能力尤为关键。

#### Supported Anomaly Patterns

| Pattern | Metrics Involved | Detection Logic | Severity |
|---------|-----------------|-----------------|----------|
| CPU-Memory Pressure | CPUUtilization, MemoryUsage | Both >= 80% for >= 10min | Critical |
| Disk-IO Bottleneck | DiskUsage, IOPSUsage | DiskUsage >= 85% AND IOPSUsage >= 90% | Critical |
| Network Saturation | InternetInRate, InternetOutRate | Either > baseline + 3σ for >= 5min | Warning |
| Load-CPU Mismatch | LoadAverage, CPUUtilization | LoadAverage > vCPU*2 AND CPUUtilization < 50% (indicates IO wait) | Warning |
| Connection Exhaustion | ConnectionUsage, CpuUsage | ConnectionUsage >= 90% AND CPUUsage < 30% (sleeping connections) | Critical |
| Memory Leak Trend | MemoryUsage | Monotonic increase over 30min with slope > 5%/10min | Warning |
| CPU Spike | CPUUtilization | Sudden increase > 50 percentage points within 5min | Warning |

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Resource exists | Delegate to product skill (e.g., `alicloud-ecs-ops` DescribeInstances) | Resource found and Running | HALT |
| Metrics available | `DescribeMetricMetaList` for namespace | All pattern metrics exist | Reduce pattern scope |
| Time range valid | StartTime < EndTime, within retention | Valid range | Adjust range |
| Quota check | Track API call count | < 80% of 1M/month | Warn; proceed with caution |

#### Execution — CLI (Multi-Call Sequence)

```bash
#!/bin/bash
# multi-metric-inspection.sh

REGION="{{user.region}}"
NAMESPACE="{{user.namespace}}"
INSTANCE_ID="{{user.instance_id}}"
START_TIME="$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DIMENSIONS="[{\"instanceId\":\"${INSTANCE_ID}\"}]"

METRICS=()
case "$NAMESPACE" in
  acs_ecs_dashboard)
    METRICS=(CPUUtilization MemoryUsage DiskUsage LoadAverage InternetInRate InternetOutRate)
    ;;
  acs_rds_dashboard)
    METRICS=(CpuUsage MemoryUsage DiskUsage ConnectionUsage IOPSUsage)
    ;;
  acs_slb_dashboard)
    METRICS=(InstanceActiveConnection DropConnection DropPacketRX DropPacketTX)
    ;;
  *)
    echo "Unknown namespace: $NAMESPACE"
    exit 1
    ;;
esac

RESULTS_DIR="/tmp/cms-inspection-$(date +%s)"
mkdir -p "$RESULTS_DIR"

for metric in "${METRICS[@]}"; do
  echo "Querying $metric..."
  aliyun cms DescribeMetricList \
    --RegionId "$REGION" \
    --Namespace "$NAMESPACE" \
    --MetricName "$metric" \
    --Period 300 \
    --StartTime "$START_TIME" \
    --EndTime "$END_TIME" \
    --Dimensions "$DIMENSIONS" \
    > "$RESULTS_DIR/${metric}.json" 2>&1
done

echo "Results saved to $RESULTS_DIR"
```

#### Execution — JIT Go SDK (Advanced Correlation)

```go
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"time"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	cms20190101 "github.com/alibabacloud-go/cms-20190101/v7/client"
)

type DataPoint struct {
	Timestamp int64   `json:"timestamp"`
	Average   float64 `json:"Average"`
	Maximum   float64 `json:"Maximum"`
	Minimum   float64 `json:"Minimum"`
}

func queryMetric(client *cms20190101.Client, namespace, metricName, dimensions string, startTime, endTime string) ([]DataPoint, error) {
	request := &cms20190101.DescribeMetricListRequest{
		RegionId:   tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
		Namespace:  tea.String(namespace),
		MetricName: tea.String(metricName),
		Period:     tea.String("300"),
		StartTime:  tea.String(startTime),
		EndTime:    tea.String(endTime),
		Dimensions: tea.String(dimensions),
	}
	response, err := client.DescribeMetricList(request)
	if err != nil {
		return nil, err
	}

	var result struct {
		Datapoints string `json:"Datapoints"`
	}
	bodyStr := tea.ToString(response.Body)
	if err := json.Unmarshal([]byte(bodyStr), &result); err != nil {
		return nil, err
	}

	var datapoints []DataPoint
	if err := json.Unmarshal([]byte(result.Datapoints), &datapoints); err != nil {
		return nil, err
	}

	sort.Slice(datapoints, func(i, j int) bool {
		return datapoints[i].Timestamp < datapoints[j].Timestamp
	})
	return datapoints, nil
}

func detectAnomalyPattern(metrics map[string][]DataPoint, vCPU int) []string {
	var patterns []string

	cpu := metrics["CPUUtilization"]
	mem := metrics["MemoryUsage"]
	disk := metrics["DiskUsage"]
	iops := metrics["IOPSUsage"]
	load := metrics["LoadAverage"]
	conn := metrics["ConnectionUsage"]

	// Pattern: CPU-Memory Pressure
	if len(cpu) >= 2 && len(mem) >= 2 {
		cpuHigh, memHigh := true, true
		for i := len(cpu) - 2; i < len(cpu); i++ {
			if cpu[i].Average < 80 {
				cpuHigh = false
			}
			if mem[i].Average < 80 {
				memHigh = false
			}
		}
		if cpuHigh && memHigh {
			patterns = append(patterns, "CPU-Memory Pressure (Critical)")
		}
	}

	// Pattern: Disk-IO Bottleneck
	if len(disk) > 0 && len(iops) > 0 {
		latestDisk := disk[len(disk)-1].Average
		latestIOPS := iops[len(iops)-1].Average
		if latestDisk >= 85 && latestIOPS >= 90 {
			patterns = append(patterns, "Disk-IO Bottleneck (Critical)")
		}
	}

	// Pattern: Load-CPU Mismatch (IO wait)
	if len(load) > 0 && len(cpu) > 0 {
		latestLoad := load[len(load)-1].Average
		latestCPU := cpu[len(cpu)-1].Average
		if float64(vCPU)*2 < latestLoad && latestCPU < 50 {
			patterns = append(patterns, "Load-CPU Mismatch / IO Wait (Warning)")
		}
	}

	// Pattern: Connection Exhaustion
	if len(conn) > 0 && len(cpu) > 0 {
		latestConn := conn[len(conn)-1].Average
		latestCPU := cpu[len(cpu)-1].Average
		if latestConn >= 90 && latestCPU < 30 {
			patterns = append(patterns, "Connection Exhaustion (Critical)")
		}
	}

	// Pattern: Memory Leak Trend
	if len(mem) >= 6 {
		slope := (mem[len(mem)-1].Average - mem[len(mem)-6].Average) / 5
		if slope > 5 {
			patterns = append(patterns, "Memory Leak Trend (Warning)")
		}
	}

	// Pattern: CPU Spike
	if len(cpu) >= 2 {
		delta := cpu[len(cpu)-1].Average - cpu[len(cpu)-2].Average
		if delta > 50 {
			patterns = append(patterns, fmt.Sprintf("CPU Spike (+%.0f%%) (Warning)", delta))
		}
	}

	return patterns
}

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

	namespace := "{{user.namespace}}"
	instanceID := "{{user.instance_id}}"
	dimensions := fmt.Sprintf(`{"instanceId":"%s"}`, instanceID)

	metrics := map[string][]DataPoint{}
	metricNames := []string{"CPUUtilization", "MemoryUsage", "DiskUsage", "LoadAverage", "IOPSUsage", "ConnectionUsage", "InternetInRate", "InternetOutRate"}

	for _, name := range metricNames {
		dp, err := queryMetric(client, namespace, name, dimensions, startTime, endTime)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Warning: failed to query %s: %v\n", name, err)
			continue
		}
		metrics[name] = dp
	}

	patterns := detectAnomalyPattern(metrics, 4)
	if len(patterns) == 0 {
		fmt.Println("No anomaly patterns detected.")
		return
	}

	fmt.Println("=== Anomaly Patterns Detected ===")
	for _, p := range patterns {
		fmt.Printf("- %s\n", p)
	}
}
```

#### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Data completeness | All queried metrics return non-empty Datapoints | >= 2 data points per metric |
| Pattern match | Evaluate detection logic against collected data | Identify matched patterns with severity |
| Cross-skill trigger | If Critical pattern matched | Auto-delegate to corresponding product skill |

#### Recovery & Cross-Skill Delegation

| Pattern Detected | Primary Delegation | Secondary Delegation | DAS Delegation |
|-----------------|-------------------|---------------------|----------------|
| CPU-Memory Pressure | `alicloud-ecs-ops` | `alicloud-vpc-ops` | Optional |
| Disk-IO Bottleneck | `alicloud-ecs-ops` | — | Optional |
| Load-CPU Mismatch | `alicloud-ecs-ops` | — | Optional |
| Connection Exhaustion | `alicloud-rds-ops` | `alicloud-das-ops` | **Recommended** |
| Memory Leak Trend | `alicloud-ecs-ops` | — | Optional |
| CPU Spike | `alicloud-ecs-ops` | — | Optional |

> **Delegation Protocol:** When a pattern is detected, the agent MUST:
> 1. Record the pattern and severity in the inspection report
> 2. Invoke the primary skill to check resource status
> 3. If severity is Critical or resource status is abnormal, invoke DAS skill for AI diagnosis
> 4. Compile a unified report with findings from all delegated skills

---

### Alarm-Driven Cross-Skill Diagnosis

当 CMS 告警触发时，按以下决策树执行自动化跨 Skill 根因诊断。

#### Diagnosis Decision Tree

```
[CMS Alarm] → Step 1: Verify via DescribeMetricLast
  ├─ Normal → False positive; check rule config
  └─ Abnormal → Step 2: Check resource (delegate by namespace)
       ├─ acs_ecs_dashboard → alicloud-ecs-ops
       ├─ acs_rds_dashboard → alicloud-rds-ops
       ├─ acs_slb_dashboard → alicloud-slb-ops
       └─ acs_k8s_dashboard → alicloud-ack-ops

       → Step 3: Multi-metric correlation → Step 4: DAS deep diagnosis
       → Step 5: Unified report (findings + recommendations)
```

#### Unified Diagnosis Report Schema

| Field | Source | Example |
|-------|--------|---------|
| `report_id` | Generated | `rpt-uuid` |
| `timestamp` | CMS | `2026-05-14T10:30:00Z` |
| `alarm_source` | CMS | `ECS-CPU-Critical` |
| `resource_id` | CMS | `i-abcdefgh1234567890` |
| `resource_status` | Product Skill | `Running` |
| `metric_value` | CMS | `CPUUtilization: 96.5%` |
| `anomaly_patterns` | Inspection | `["CPU-Memory Pressure"]` |
| `root_cause` | Synthesized | `CPU saturation due to runaway process` |
| `delegated_skills` | Agent | `["alicloud-ecs-ops", "alicloud-das-ops"]` |
| `recommendation` | Synthesized | `Scale up instance or optimize query` |

#### Execution — CLI (Diagnosis Orchestration Script)

```bash
#!/bin/bash
# alarm-diagnosis-orchestrator.sh

REGION="{{user.region}}"
ALARM_NAME="{{user.alarm_name}}"
NAMESPACE="{{user.namespace}}"
METRIC_NAME="{{user.metric_name}}"
INSTANCE_ID="{{user.instance_id}}"
REPORT_DIR="/tmp/cms-diagnosis-$(date +%s)"
mkdir -p "$REPORT_DIR"

echo "=== CMS Alarm Diagnosis Started ==="
echo "Alarm: $ALARM_NAME | Metric: $METRIC_NAME | Resource: $INSTANCE_ID"

# Step 1: Verify alarm validity
echo -e "\n[Step 1] Verifying alarm validity..."
aliyun cms DescribeMetricLast \
  --RegionId "$REGION" \
  --Namespace "$NAMESPACE" \
  --MetricName "$METRIC_NAME" \
  --Dimensions "[{\"instanceId\":\"${INSTANCE_ID}\"}]" \
  > "$REPORT_DIR/step1_metric_last.json"

METRIC_VALUE=$(cat "$REPORT_DIR/step1_metric_last.json" | jq -r '.Datapoints | fromjson? | .[0].Average // "N/A"')
echo "Current metric value: $METRIC_VALUE"

# Step 2: Check resource status (namespace-specific)
echo -e "\n[Step 2] Checking resource status..."
case "$NAMESPACE" in
  acs_ecs_dashboard)
    aliyun ecs DescribeInstances --RegionId "$REGION" --InstanceIds "[\"${INSTANCE_ID}\"]" > "$REPORT_DIR/step2_resource.json"
    ;;
  acs_rds_dashboard)
    aliyun rds DescribeDBInstances --RegionId "$REGION" --DBInstanceId "$INSTANCE_ID" > "$REPORT_DIR/step2_resource.json"
    ;;
  acs_slb_dashboard)
    aliyun slb DescribeLoadBalancerAttribute --LoadBalancerId "$INSTANCE_ID" > "$REPORT_DIR/step2_resource.json"
    ;;
  *)
    echo "Unknown namespace: $NAMESPACE"
    ;;
esac

# Step 3: Multi-metric correlation
echo -e "\n[Step 3] Running multi-metric correlation..."
# (Invoke the multi-metric inspection logic above)

# Step 4: Check correlated alarms in last 1h
echo -e "\n[Step 4] Checking correlated alarms..."
START_TIME="$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

aliyun cms DescribeMetricAlarmList \
  --RegionId "$REGION" \
  --State ALARM \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  > "$REPORT_DIR/step4_correlated_alarms.json"

# Step 5: Compile report
echo -e "\n[Step 5] Compiling diagnosis report..."
cat > "$REPORT_DIR/diagnosis_report.md" << 'EOF'
# CMS Alarm Diagnosis Report

| Field | Value |
|-------|-------|
| Alarm | {{user.alarm_name}} |
| Metric | {{user.metric_name}} |
| Resource | {{user.instance_id}} |
| Current Value | (from step 1) |
| Resource Status | (from step 2) |
| Correlated Alarms | (from step 4) |

## Findings
(TODO: populate from delegated skills)

## Recommendations
(TODO: synthesize)
EOF

echo -e "\n=== Diagnosis Complete ==="
echo "Report saved to: $REPORT_DIR/diagnosis_report.md"
```

---

### Operation: Proactive Monitoring Inspection

定期执行多资源、多指标的主动巡检，发现潜在问题。

#### Execution Flow

1. **Discovery**: 列出监控组内所有资源
   ```bash
   aliyun cms DescribeMonitorGroupInstances \
     --RegionId {{user.region}} \
     --GroupId {{user.group_id}}
   ```

2. **Metric Collection**: 对每个资源采集关键指标
   ```bash
   aliyun cms DescribeMetricList \
     --RegionId {{user.region}} \
     --Namespace {{user.namespace}} \
     --MetricName {{user.metric_name}} \
     --Period 300 \
     --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
     --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
   ```

3. **Anomaly Detection**: 应用静态阈值 + 趋势分析
   - **静态阈值**: 与预定义阈值比较
   - **趋势分析**: 计算最近 N 个数据点的斜率；若斜率加速上升则标记
   - **同比环比**: 与昨天同时段、上周同时段比较（需要历史数据）

4. **Cross-Skill Diagnosis**: 对标记资源委托给产品 Skill

5. **Report Generation**: 生成巡检报告

   | Resource | Metric | Status | Severity | Pattern | Delegated Skill | Finding |
   |----------|--------|--------|----------|---------|-----------------|---------|
   | i-xxx | CPUUtilization | ALARM | Critical | CPU Spike | alicloud-ecs-ops | High load |
   | rm-yyy | ConnectionUsage | WARNING | Warning | Connection Exhaustion | alicloud-rds-ops | 85% used |

#### Anomaly Detection Algorithm (Trend)

```go
// Calculate linear regression slope for trend detection
func calculateSlope(points []DataPoint) float64 {
	n := float64(len(points))
	if n < 2 {
		return 0
	}
	var sumX, sumY, sumXY, sumX2 float64
	for i, p := range points {
		x := float64(i)
		y := p.Average
		sumX += x
		sumY += y
		sumXY += x * y
		sumX2 += x * x
	}
	slope := (n*sumXY - sumX*sumY) / (n*sumX2 - sumX*sumX)
	return slope
}

// Flag if slope indicates accelerating increase
func isAcceleratingIncrease(points []DataPoint) bool {
	if len(points) < 6 {
		return false
	}
	slope1 := calculateSlope(points[:len(points)/2])
	slope2 := calculateSlope(points[len(points)/2:])
	return slope2 > slope1 && slope2 > 2.0
}
```

---

### Alarm Storm Handling

当多个告警同时触发时，执行告警聚合与抑制策略。

#### Storm Detection Criteria

| Criteria | Threshold | Action |
|----------|-----------|--------|
| Alarm rate | > 10 alarms in 5 minutes | Enter storm mode |
| Same resource | > 3 alarms for same instance | Aggregate into single incident |
| Same namespace | > 50% of alarms from one namespace | Focus diagnosis on that product |
| Cascading pattern | Alarm A followed by Alarm B within 2min | Mark B as "likely caused by A" |

#### Storm Handling Workflow

1. **Detection**: Monitor DescribeMetricAlarmList with State=ALARM
2. **Aggregation**: Group alarms by resource_id, namespace, time window
3. **Suppression**: For aggregated alarms, suppress notifications except the primary
4. **Root Resource Identification**: Find the earliest alarm in the cascade
5. **Focused Diagnosis**: Delegate to the root resource's skill for deep diagnosis

```bash
#!/bin/bash
# alarm-storm-detector.sh

REGION="{{user.region}}"
START_TIME="$(date -u -v-5M +%Y-%m-%dT%H:%M:%SZ)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

aliyun cms DescribeMetricAlarmList \
  --RegionId "$REGION" \
  --State ALARM \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  --PageSize 100 \
  > /tmp/active_alarms.json

ALARM_COUNT=$(cat /tmp/active_alarms.json | jq '.AlarmList | length')
echo "Active alarms in last 5min: $ALARM_COUNT"

if [ "$ALARM_COUNT" -gt 10 ]; then
  echo "ALARM STORM DETECTED!"
  cat /tmp/active_alarms.json | jq '
    .AlarmList | group_by(.Dimensions) | 
    map({resource: .[0].Dimensions, count: length, alarms: map(.AlarmName)})
  '
fi
```

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to CMS.

### 安全 (Security)

| Area | Guidance |
|------|----------|
| **IAM** | Require: `cms:Describe*` for read-only. `cms:Put*`, `cms:Create*` for write ops. Scope to `acs:cms:*:*:*` |
| **Credentials** | `{{env.*}}` only. Never print secrets |
| **Alert Data** | Alert contact/phone numbers are sensitive — mask in output |

### 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | Multi-metric alerts reduce false positives. Use `EvaluationCount ≥ 3` for production. Set `Escalations` for tiered response |
| **面向精细的运维管控** | CMS IS the operational control layer for all other products. EffectiveInterval to suppress maintenance windows |
| **面向风险的应急快恢** | Alert-driven diagnosis via cross-skill delegation matrix. Escalation → DAS for DB, ECS for compute |

#### DR Runbook
```
Phase 1: Detect — CMS alert triggers on metric threshold
Phase 2: Diagnose — Cross-skill delegation (DAS for DB, ECS for compute, SLB for network)
Phase 3: Resolve — Auto-remediation or escalate to human with full diagnostic report
```

### 成本 (Cost)

| Item | Cost | Optimization |
|------|------|-------------|
| API Calls | 1,000,000/month free | Use Period=300s to reduce volume |
| Custom Metrics | Pay per datapoint | Consolidate metrics; reduce frequency |
| Alert Notifications | Free (SMS extra) | Use webhooks over SMS for cost control |

**Waste:** Unused alert rules (never triggered in 30d) → disable or delete. Over-frequent metric polling → increase Period.

### 效率 (Efficiency)

- **Multi-Metric Alarms:** Combine CPU, memory, disk into single alert to reduce noise
- **Alarm Templates:** Use alarm rule templates for consistent thresholds across resource groups
- **CI/CD:** JSON output by default. `DescribeMetricList` compatible with dashboards

### 性能 (Performance)

| Metric | CMS Namespace | Alert Threshold | Window |
|--------|--------------|-----------------|--------|
| Per-product metrics | `acs_{product}_dashboard` | Per product guidance | Period=300s |
| API Throttling | — | > 50 calls/second | Immediate |

**Key guidance:** Use longer Period values (300s vs 60s) to reduce API volume. Group resources using MonitorGroup for batch monitoring. Use DescribeMetricLast instead of DescribeMetricList for latest single value.

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
- [AIOps Prediction](references/aiops-prediction.md)
- [SecOps Monitoring](references/secops-monitoring.md)
- [FinOps Analysis](references/finops-analysis.md)

## Operational Best Practices

- **Least privilege:** Use `AliyunCloudMonitorReadOnlyAccess` for read-only operations; use `AliyunCloudMonitorFullAccess` only when creating or modifying resources.
- **Rate limiting:** Implement client-side rate limiting (max 50 calls/second). Use longer Period values (300s instead of 60s) to reduce API call volume.
- **Cost awareness:** Metric query APIs share a 1,000,000 calls/month free quota. Monitor usage to avoid unexpected charges.
- **Alarm tuning:** Set appropriate EvaluationCount (3+ for production) to avoid false positives. Use EffectiveInterval to suppress alarms during maintenance windows.
- **Data retention:** Choose Period based on retention needs — <60s (7 days), 60s (31 days), ≥300s (91 days).

## References

- [Alibaba Cloud CMS API Docs](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/api-reference-cms-2019-01-01/)
- [Alibaba Cloud CLI CMS Integration](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/cli-integration-example)
- [Agent Skill OpenSpec](https://agentskills.io/specification)
