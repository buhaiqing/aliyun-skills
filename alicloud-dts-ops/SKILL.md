---
name: alicloud-dts-ops
description: >-
  Use when deploying, configuring, troubleshooting, or monitoring Alibaba Cloud
  Data Transmission Service (DTS) — data migration, data synchronization, change
  tracking (订阅), and DTS instance lifecycle. User mentions 数据传输, DTS,
  data migration, data sync, change tracking, 数据迁移, 数据同步, 订阅, or
  describes scenarios like migrating databases between sources/targets,
  real-time data synchronization, cross-region replication, or
  zero-downtime migration. NOT for RDS, PolarDB, Redis, MongoDB, or
  billing/RAM-only tasks.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints. CLI plugin `aliyun-cli-dts` recommended for enhanced features.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-04"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "Dts 2020-01-01 / https://help.aliyun.com/zh/dts"
  cli_applicability: dual-path
  cli_support_evidence: "Confirmed via `aliyun help dts` — DTS (Data Transmission) is fully supported by the official aliyun CLI with 100+ APIs."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Data Transmission Service (DTS) Operations Skill

## Overview

Alibaba Cloud Data Transmission Service (DTS / 数据传输服务) provides managed
data migration, real-time data synchronization, and change tracking (CDC) between
various database sources and targets — including RDS, PolarDB, Redis, MongoDB,
Elasticsearch, AnalyticDB, self-managed databases (ECS/IDC), and third-party
cloud databases.

This skill is an **operational runbook** for agents: explicit scope, credential
rules, pre-flight checks, **dual-path execution** (official **SDK/API** and
**CLI** flows), response validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` fully supports `dts`.
  Each execution flow documents **both** the SDK step and the `aliyun` step
  for every operation.

### Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers and delegation rules |
| 2 | **Structured I/O** | Placeholder conventions (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) with type and source documented |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute → Validate → Recover, with numbered imperative steps |
| 4 | **Complete Failure Strategies** | Error taxonomy table with ≥ 12 product-specific codes; HALT vs retry per error type |
| 5 | **Absolute Single Responsibility** | One product (DTS), one primary resource model (DtsJob/DtsInstance); cross-product delegation to other skills |

### Well-Architected Framework Integration (卓越架构)

Operations map to Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html):
- **安全 (Security)**: IAM permissions, credential masking, network isolation
- **稳定 (Stability)**: Task monitoring, retry mechanisms, checkpoint recovery, DR runbook
- **成本 (Cost)**: Billing model comparison (pay-as-you-go vs subscription), DU optimization
- **效率 (Efficiency)**: Batch operations, CI/CD integration, structured migration runbook
- **性能 (Performance)**: DU metrics, latency monitoring, throughput baselines

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Data Transmission Service" OR "DTS" OR "数据传输" OR "数据传输服务"
- User mentions "数据迁移" OR "data migration" — migrating data from one database to another
- User mentions "数据同步" OR "data synchronization" — real-time syncing between databases
- User mentions "订阅" OR "change tracking" OR "CDC" — capturing data changes
- Task involves migrating databases from self-managed (ECS/IDC) to Alibaba Cloud
- Task involves cross-region or cross-account database replication
- Task involves creating, configuring, starting, stopping, or deleting DTS tasks
- Task involves testing database connectivity via DTS (DescribeConnectionStatus)
- Task involves monitoring DTS task status, latency, or data consistency
- Keywords: 迁移, 同步, 订阅, DTS任务, 迁移任务, 同步任务, 数据传输链路, 数据校验

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops`
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops`
- Task is about **RDS instance CRUD** (not migration/sync) → delegate to: `alicloud-rds-ops`
- Task is about **PolarDB cluster CRUD** → delegate to: `alicloud-polar-mysql-ops` / `alicloud-polar-postgresql-ops`
- Task is about **Redis/Tair CRUD** → delegate to: `alicloud-redis-ops`
- Task is about **MongoDB instance CRUD** → delegate to: `alicloud-mongodb-ops`
- User insists on **console-only** flows with no API → state limitation; do not invent undocumented HTTP steps

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
| `{{user.source_instance_id}}` | Source database instance ID | Ask once; reuse |
| `{{user.target_instance_id}}` | Target database instance ID | Ask once; reuse |
| `{{user.source_endpoint_type}}` | Source endpoint type (RDS, PolarDB, MongoDB, ECS, etc.) | Ask once; reuse |
| `{{user.target_endpoint_type}}` | Target endpoint type | Ask once; reuse |
| `{{user.dts_job_id}}` | DTS task ID | From API response or user |
| `{{user.dts_instance_id}}` | DTS instance ID | From API response or user |
| `{{output.dts_job_id}}` | From Create/Configure API response | `$.DtsJobId` / `$.Data[].DtsJobId` |
| `{{output.dts_instance_id}}` | From CreateDtsInstance response | `$.InstanceId` |
| `{{output.status}}` | Task status from DescribeDtsJobs | `$.Status` |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.

> **Security Warning (Credential Masking — MANDATORY):** NE log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`,
> database passwords (`SourceEndpointPassword` / `DestinationEndpointPassword`), or any credential field value.
> For DTS, especially sensitive: source/target database passwords in ConfigureDtsJob requests.

## Quick Start

### What This Skill Does
This skill enables you to deploy, configure, and manage data migration, synchronization, and change tracking tasks on Alibaba Cloud using the `aliyun` CLI (primary) or JIT Go SDK (fallback).

### Prerequisites
- [ ] `aliyun` CLI installed (or Go runtime for JIT fallback)
- [ ] DTS CLI plugin: `aliyun plugin install --names aliyun-cli-dts` (recommended for enhanced features)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`

### Verify Setup
```bash
# Check CLI and credentials
aliyun dts DescribeDtsJobs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}
```

### Your First Command
```bash
# Example: List DTS tasks
aliyun dts DescribeDtsJobs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}
```

### Next Steps
- [Core Concepts](references/core-concepts.md) — Understand DTS architecture and job types
- [Quick Migration Runbook](#operation-create-and-start-a-migration-task) — Create and start a migration task
- [Troubleshooting](references/troubleshooting.md) — Fix common DTS issues

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| CreateDtsInstance | Purchase a DTS instance | Medium | Low (paid) |
| ConfigureDtsJob | Configure migration/sync/change tracking task | High | Medium (data flow) |
| StartDtsJob | Start a configured task | Low | Medium (data starts flowing) |
| StopDtsJob | Stop a running task | Low | Medium (data halts) |
| SuspendDtsJob | Pause a task | Low | Low |
| DeleteDtsJob | Delete a task and release instance | Low | **High** — irreversible |
| DescribeDtsJobs | List all DTS tasks | Low | None |
| DescribeConnectionStatus | Test source/target connectivity | Medium | None |
| ResetDtsJob | Reset a failed task | Medium | Medium (clean slate) |
| ModifyDtsJob | Modify task configuration | High | Medium (misconfig risks) |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-04 | Initial DTS skill with migration, sync, change tracking, instance lifecycle, GCL integration |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (SDK/API and `aliyun`) → Validate → Recover**.

**Preference hint:** CLI is preferred for coverage and simplicity; Go SDK is used for operations CLI does not expose.

---

### Operation: Describe DTS Tasks

#### Pre-flight Checks
- [ ] Region is set in `{{env.ALIBABA_CLOUD_REGION_ID}}`
- [ ] `aliyun` CLI available (or Go SDK fallback)

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
# List all DTS tasks (any type: migration, sync, change tracking)
aliyun dts DescribeDtsJobs \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}

# Filter by type (migration)
aliyun dts DescribeDtsJobs \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --Type migration

# Filter by type (synchronization)
aliyun dts DescribeDtsJobs \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --Type synchronization

# Filter by type (subscribe for change tracking)
aliyun dts DescribeDtsJobs \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --Type subscribe

# Get specific task detail
aliyun dts DescribeDtsJobDetail \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"

# Legacy APIs (still supported)
aliyun dts DescribeMigrationJobs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}
aliyun dts DescribeSynchronizationJobs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}
aliyun dts DescribeSubscriptionInstances --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}
```

#### Post-execution Validation

- Parse `$.DtsJobList[].{DtsJobId,Status,JobType,DtsJobName}` from response
- Key states: `NotStarted`, `Prechecking`, `PrecheckFailed`, `Migrating`, `Synchronizing`, `Suspending`, `Suspended`, `Stopping`, `Stopped`, `Finished`, `Failed`

#### Failure Recovery

| Error pattern | Max retries | Agent Action |
|---------------|-------------|--------------|
| `InvalidRegionId` | 0 | HALT — verify region |
| Throttling (429) | 3, exponential | Retry with backoff |

---

### Operation: Create and Start a Migration Task

> DTS migration involves: (1) Purchase DTS instance → (2) Configure migration job → (3) Start migration job.
> For one-step simplified API, use `ConfigureDtsJob` with `JobType=MIGRATE` and `AutoStart=true`.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Source database reachable | `DescribeConnectionStatus` | `Success` | HALT — check network/DTS IP whitelist |
| Target database reachable | `DescribeConnectionStatus` | `Success` | HALT — check network/credentials |
| Source database instance exists | Describe via relevant skill | Running | HALT — source not available |
| Target database instance exists | Describe via relevant skill | Running | HALT — target not available |
| DTS quota | Describe DTS instances | Has capacity | CreateDtsInstance first |
| DTS white list CIDR | `DescribeDTSIP` | Whitelisted on source/target | Add CIDR to source/target SG |

#### Execution — CLI (`aliyun`) (Primary Path)

**Step 1: Purchase a DTS instance (if needed)**
```bash
aliyun dts CreateDtsInstance \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --Type migration \
  --PayType PostPaid \
  --SourceRegionId {{user.source_region}} \
  --DestinationRegionId {{user.target_region}} \
  --Quantity 1 \
  --AutoStart true
```

**Step 2: Configure migration job**
```bash
aliyun dts ConfigureDtsJob \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DataInitialization true \
  --DataSynchronization true \
  --JobType MIGRATE \
  --SourceEndpointInstanceType "{{user.source_endpoint_type}}" \
  --SourceEndpointInstanceID "{{user.source_instance_id}}" \
  --SourceEndpointRegion "{{user.source_region}}" \
  --SourceEndpointEngineName "{{user.source_engine}}" \
  --SourceEndpointUserName "{{user.source_username}}" \
  --SourceEndpointPassword "{{user.source_password}}" \
  --DestinationEndpointInstanceType "{{user.target_endpoint_type}}" \
  --DestinationEndpointInstanceID "{{user.target_instance_id}}" \
  --DestinationEndpointRegion "{{user.target_region}}" \
  --DestinationEndpointEngineName "{{user.target_engine}}" \
  --DestinationEndpointUserName "{{user.target_username}}" \
  --DestinationEndpointPassword "{{user.target_password}}" \
  --JobType MIGRATE \
  --DtsJobName "migrate-{{user.source_instance_id}}-to-{{user.target_instance_id}}"
```

> **Security:** Source and target database passwords are passed as CLI parameters. Ensure the execution environment does not log command lines with plaintext passwords. Consider using environment variables and JIT Go SDK for production.

**Step 3: Start migration (if AutoStart was false)**
```bash
aliyun dts StartDtsJob \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{output.dts_job_id}}"
```

**Step 4: Monitor migration progress**
```bash
# Check detailed status
aliyun dts DescribeDtsJobDetail \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{output.dts_job_id}}"

# Get migration progress (legacy)
aliyun dts DescribeMigrationJobStatus \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --MigrationJobId "{{output.dts_job_id}}"
```

#### Execution — JIT Go SDK (Fallback Path)

```go
// main.go — Configure a DTS migration job
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    dts "github.com/alibabacloud-go/dts-20200101/v1/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("dts.aliyuncs.com"),
    }

    client, err := dts.NewClient(config)
    if err != nil {
        panic(err)
    }

    request := &dts.ConfigureDtsJobRequest{
        // Source endpoint
        SourceEndpointInstanceType: tea.String(os.Getenv("SOURCE_ENDPOINT_TYPE")),
        SourceEndpointInstanceID:   tea.String(os.Getenv("SOURCE_INSTANCE_ID")),
        SourceEndpointRegion:       tea.String(os.Getenv("SOURCE_REGION")),
        SourceEndpointEngineName:   tea.String(os.Getenv("SOURCE_ENGINE")),
        SourceEndpointUserName:     tea.String(os.Getenv("SOURCE_USERNAME")),
        SourceEndpointPassword:     tea.String(os.Getenv("SOURCE_PASSWORD")),
        // Target endpoint
        DestinationEndpointInstanceType: tea.String(os.Getenv("TARGET_ENDPOINT_TYPE")),
        DestinationEndpointInstanceID:   tea.String(os.Getenv("TARGET_INSTANCE_ID")),
        DestinationEndpointRegion:       tea.String(os.Getenv("TARGET_REGION")),
        DestinationEndpointEngineName:   tea.String(os.Getenv("TARGET_ENGINE")),
        DestinationEndpointUserName:     tea.String(os.Getenv("TARGET_USERNAME")),
        DestinationEndpointPassword:     tea.String(os.Getenv("TARGET_PASSWORD")),
        // Job configuration
        DataInitialization:   tea.Bool(true),
        DataSynchronization:  tea.Bool(true),
        JobType:              tea.String("MIGRATE"),
        DtsJobName:           tea.String("migrate-job-" + os.Getenv("SOURCE_INSTANCE_ID")),
        RegionId:             tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }

    response, err := client.ConfigureDtsJob(request)
    if err != nil {
        panic(err)
    }

    fmt.Println(tea.ToString(response.Body))
    // Key output: $.DtsJobId -> migration job ID
}
```

Execute:
```bash
cd /tmp/aliyun-sdk-workspace
go run ./main.go
```

#### Post-execution Validation

1. Parse `{{output.dts_job_id}}` from response (path: `$.DtsJobId`)
2. Poll DescribeDtsJobDetail until status is `Migrating` / `Synchronizing` or terminal state:
```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun dts DescribeDtsJobDetail \
    --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
    --DtsJobId "{{output.dts_job_id}}" | jq -r '.Status')
  echo "Status: $STATUS"
  [ "$STATUS" = "Migrating" ] || [ "$STATUS" = "Synchronizing" ] && break
  [ "$STATUS" = "Finished" ] && { echo "✅ Migration completed"; break; }
  [ "$STATUS" = "Failed" ] && { echo "❌ Migration failed"; break; }
  sleep 10
done
```
3. On success, report DtsJobId and current status to the user
4. On failure (Failed / PrecheckFailed), go to Failure Recovery

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action | UX Feedback |
|---------------|-------------|---------|--------------|-------------|
| `InvalidParameter` / 400 | 0-1 | — | Fix args from OpenAPI; retry once if safe | `[ERROR] InvalidParameter: Check parameter values against OpenAPI docs` |
| `QuotaExceeded` | 0 | — | HALT | `[ERROR] QuotaExceeded: DTS instance quota reached. Purchase a new DTS instance first.` |
| `InsufficientBalance` | 0 | — | HALT | `[ERROR] InsufficientBalance: Account balance insufficient for DTS instance purchase.` |
| `PrecheckFailed` | 1 | — | DescribePreCheckStatus to find details; fix and retry | `[ERROR] PrecheckFailed: Check precheck details. Common: source/target connectivity or permissions.` |
| `JobExecutionException` | 3 | 10s, 30s, 60s | Retry with increasing backoff; if persists, HALT | `⚠️ Job execution exception. Retrying ({n}/3)...` |
| Throttling / 429 | 3 | exponential | Back off | `⚠️ Rate limit reached. Retrying in {backoff}s...` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId | `[ERROR] InternalError: Server error. Escalate with RequestId.` |
| `InvalidEndpointType` | 0 | — | HALT | `[ERROR] InvalidEndpointType: Unsupported source/target endpoint type. See allowed values in API doc.` |
| `InvalidConnectionString` | 0 | — | HALT | `[ERROR] InvalidConnectionString: Source or target connection string is invalid. Verify instance ID/region.` |
| `SubscriptionNotFound` | 0 | — | HALT | `[ERROR] SubscriptionNotFound: Change tracking instance not found. Verify instance ID.` |
| `InvalidJobName.Duplicate` | 0 | — | Use different job name | `[ERROR] InvalidJobName.Duplicate: A job with this name already exists. Use a unique name.` |
| `SourceOrDestinationNotAllowed` | 0 | — | HALT | `[ERROR] SourceOrDestinationNotAllowed: This source-target combo is not supported. Check official supported source/target matrix.` |
| `InvalidWhiteList` | 0 | — | Add DTS CIDR to source/target whitelist | `[ERROR] InvalidWhiteList: DTS server IP not in source/target whitelist. Use DescribeDTSIP to get CIDR blocks.` |

---

### Operation: Configure Data Synchronization

> Similar to migration but for ongoing real-time bidirectional or unidirectional sync.

#### Pre-flight Checks
- [ ] Source and target database connectivity verified via DescribeConnectionStatus
- [ ] DTS instance purchased (CreateDtsInstance with Type=synchronization) or reuse existing
- [ ] Source database has binlog enabled (for incremental sync) — check via relevant database skill
- [ ] DTS server CIDRs whitelisted on source/target (DescribeDTSIP)
- [ ] Source database account has replication privileges

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
aliyun dts ConfigureDtsJob \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DataInitialization true \
  --DataSynchronization true \
  --JobType SYNC \
  --SourceEndpointInstanceType "{{user.source_endpoint_type}}" \
  --SourceEndpointInstanceID "{{user.source_instance_id}}" \
  --SourceEndpointRegion "{{user.source_region}}" \
  --SourceEndpointEngineName "{{user.source_engine}}" \
  --SourceEndpointUserName "{{user.source_username}}" \
  --SourceEndpointPassword "{{user.source_password}}" \
  --DestinationEndpointInstanceType "{{user.target_endpoint_type}}" \
  --DestinationEndpointInstanceID "{{user.target_instance_id}}" \
  --DestinationEndpointRegion "{{user.target_region}}" \
  --DestinationEndpointEngineName "{{user.target_engine}}" \
  --DestinationEndpointUserName "{{user.target_username}}" \
  --DestinationEndpointPassword "{{user.target_password}}" \
  --DtsJobName "sync-{{user.source_instance_id}}-to-{{user.target_instance_id}}" \
  --StructureInitialization true
```

#### Post-execution Validation

- Poll DescribeDtsJobDetail until status `Synchronizing` or `Failed`
- Monitor sync latency: `$.SynchronizationDetails[].SynchronizationDelay` or `$.Delay`
- Data consistency: use DescribeCheckJobs or the data check feature

#### Failure Recovery

Same as migration error table above. Additional sync-specific errors:

| Error pattern | Agent Action |
|---------------|-------------|
| `DuplicateKey` | Check for conflict handling configuration; recommend conflict overwrite |
| `BinlogNotEnabled` | HALT — enable binlog on source database |
| `BinlogPurged` | Full re-sync needed; binlog retention period insufficient |

---

### Operation: Configure Change Tracking (订阅)

> Change tracking captures real-time data changes from a source database.
> Downstream consumers use `CreateConsumerChannel` to consume.

#### Pre-flight Checks
- [ ] CreateDtsInstance with Type=subscribe (or use legacy CreateSubscriptionInstance)
- [ ] Source database has binlog enabled
- [ ] DTS CIDRs whitelisted on source

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
# Step 1: Create change tracking instance (if needed)
aliyun dts CreateDtsInstance \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --Type subscribe \
  --PayType PostPaid \
  --SourceRegionId {{user.source_region}} \
  --Quantity 1

# Step 2: Configure change tracking task
aliyun dts ConfigureDtsJob \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --JobType SUBSCRIBE \
  --SourceEndpointInstanceType "{{user.source_endpoint_type}}" \
  --SourceEndpointInstanceID "{{user.source_instance_id}}" \
  --SourceEndpointRegion "{{user.source_region}}" \
  --SourceEndpointEngineName "{{user.source_engine}}" \
  --SourceEndpointUserName "{{user.source_username}}" \
  --SourceEndpointPassword "{{user.source_password}}" \
  --DtsJobName "subscribe-{{user.source_instance_id}}"

# Step 3: Create a consumer channel (for downstream consumption)
aliyun dts CreateConsumerChannel \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsInstanceId "{{output.dts_instance_id}}" \
  --ConsumerGroupName "my-consumer" \
  --ConsumerGroupUserName "consumer_user" \
  --ConsumerGroupPassword "consumer_password"
```

#### Post-execution Validation

- Verify consumer channel exists: `aliyun dts DescribeConsumerChannel --DtsInstanceId "{{output.dts_instance_id}}" --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}`
- Check tracking lag (delay between source change and capture)

---

### Operation: Stop / Suspend DTS Task

#### Pre-flight (Safety Gate)
- **MUST** confirm with user: stopping a DTS task halts data flow. For synchronization tasks, this may cause data lag.
- **MUST** verify the task is in a runnable state (`Migrating`, `Synchronizing`, `Suspended`)

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
# Stop task (hard stop — for migration or sync)
aliyun dts StopDtsJob \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"

# Suspend task (pause, can be resumed)
aliyun dts SuspendDtsJob \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"
```

#### Post-execution Validation
- Poll DescribeDtsJobDetail until status is `Stopped` or `Suspended`

---

### Operation: Delete DTS Task (Destructive)

#### Pre-flight (Safety Gate)
- **MUST** obtain explicit confirmation: `DELETE DTS task {{output.dts_job_name}} ({{output.dts_job_id}}) — this is IRREVERSIBLE and releases the DTS instance.`
- **MUST** check if the task is currently running — stop it first if so
- **MUST** inform user about data loss: any cached/unsynchronized data will be lost

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
# Step 1: Stop the task first (if running)
STATUS=$(aliyun dts DescribeDtsJobDetail --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --DtsJobId "{{user.dts_job_id}}" | jq -r '.Status')
if [ "$STATUS" = "Migrating" ] || [ "$STATUS" = "Synchronizing" ]; then
  aliyun dts StopDtsJob --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --DtsJobId "{{user.dts_job_id}}"
  sleep 5
fi

# Step 2: Delete the DTS job and release instance
aliyun dts DeleteDtsJob \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"
```

#### Post-execution Validation
- Verify task no longer exists: `aliyun dts DescribeDtsJobDetail --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --DtsJobId "{{user.dts_job_id}}"` should return empty or error

---

### Operation: Test Connectivity (DescribeConnectionStatus)

#### Pre-flight Checks
- [ ] Source endpoint parameters collected (type, instance ID, region, username, password)
- [ ] Target endpoint parameters collected

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
# Test source endpoint connectivity
aliyun dts DescribeConnectionStatus \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --SourceEndpointInstanceType "{{user.source_endpoint_type}}" \
  --SourceEndpointInstanceID "{{user.source_instance_id}}" \
  --SourceEndpointRegion "{{user.source_region}}" \
  --SourceEndpointEngineName "{{user.source_engine}}" \
  --SourceEndpointUserName "{{user.source_username}}" \
  --SourceEndpointPassword "{{user.source_password}}"
```

#### Post-execution Validation
- Parse `$.ConnectDetail[].Status` — each entry should be `Success`
- Common failures: wrong password, IP not whitelisted, network unreachable

---

### Operation: Modify DTS Task

#### Pre-flight Checks
- [ ] Task exists and is in a modifiable state (Suspended, Stopped)
- [ ] User confirms which parameters to change

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
# Modify task name
aliyun dts ModifyDtsJobName \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}" \
  --DtsJobName "{{user.new_job_name}}"

# Modify task password (if credentials changed)
aliyun dts ModifyDtsJobPassword \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}" \
  --Endpoint "src" \
  --UserName "{{user.source_username}}" \
  --Password "{{user.source_password}}"

# Modify DU limit (control task speed)
aliyun dts ModifyDtsJobDuLimit \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}" \
  --DuLimit "{{user.du_limit}}"
```

---

### Operation: Reset a Task

#### Pre-flight (Safety Gate)
- **MUST** warn user: resetting clears the current task progress; full re-sync required
- **MUST** confirm with explicit task ID

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
aliyun dts ResetDtsJob \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"
```

---

## Prerequisites

1. **Install `aliyun` CLI** (primary execution path — see [Enhanced Self-Healing Framework](references/enhanced-self-healing-framework.md) for pre-flight checks, error classification, multi-mirror retry, and health verification):
   ```bash
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   ```

2. **Install DTS CLI plugin** (recommended for enhanced features):
   ```bash
   aliyun plugin install --names aliyun-cli-dts
   ```

3. **Bootstrap Go runtime** (for JIT SDK fallback — see [Enhanced Self-Healing Framework](references/enhanced-self-healing-framework.md) for multi-version multi-mirror download, integrity check, and PATH setup):
   ```bash
   if ! command -v go &> /dev/null; then
       OS=$(uname -s | tr '[:upper:]' '[:lower:]')
       ARCH=$(uname -m)
       [ "$ARCH" = "x86_64" ] && ARCH="amd64"
       [ "$ARCH" = "aarch64" ] && ARCH="arm64"
       mkdir -p /tmp/go-runtime
       curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
       export PATH="/tmp/go-runtime/go/bin:$PATH"
   fi
   ```

4. **Configure Credentials** (credential masking rules per [execution-environment.md](references/integration.md#5-credential-security-mandatory)):
   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```

5. **Get DTS Server CIDR Blocks** (for whitelisting):
   ```bash
   aliyun dts DescribeDTSIP --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --SourceEndpointRegion {{user.source_region}} --DestinationEndpointRegion {{user.target_region}}
   ```

## Reference Directory

- [Core Concepts](references/core-concepts.md) — DTS architecture, job types, limits, supported source/target matrix
- [API & SDK Usage](references/api-sdk-usage.md) — Operation map, required fields, pagination, request/response
- [CLI Usage](references/cli-usage.md) — `aliyun dts` command map, coverage, invocation patterns
- [Troubleshooting Guide](references/troubleshooting.md) — Error codes (≥ 12), diagnostic order, multi-round diagnosis
- [Monitoring & Alerts](references/monitoring.md) — DTS metrics, dashboard, alarm configuration
- [Integration](references/integration.md) — Go SDK bootstrap, env vars, JIT workspace setup
- [Idempotency Checklist](references/idempotency-checklist.md) — Idempotent behavior for DTS operations
- [Well-Architected Assessment](references/well-architected-assessment.md) — Five-pillar assessment: Security, Stability, Cost, Efficiency, Performance
- [GCL Rubric](references/rubric.md) — **Phase 1 rollout** GCL rubric (5 core + 3 Aliyun dimensions, 8 per-op Safety sub-rules)
- [GCL Prompt Templates](references/prompt-templates.md) — **Phase 1 rollout** Generator & Critic prompt templates
- [Enhanced Self-Healing Framework](references/enhanced-self-healing-framework.md) — **MANDATORY** self-healing patterns for all installation flows (CLI install, Go JIT download, dependency download)

## Operational Best Practices

- **Least privilege:** DTS requires source/target database read/write access. Use dedicated DTS RAM roles (AliyunDTSPolicy).
- **Connectivity:** Always add DTS CIDR blocks (DescribeDTSIP) to source/target security groups before configuring tasks.
- **Prechecking:** Always run precheck (via ConfigureDtsJob with JobType=CHECK or separate precheck API) before full migration.
- **Monitoring:** Set up CMS alarms on DTS task status and sync delay for production workloads.
- **Cost:** Use subscription (包年包月) for long-running sync tasks; use pay-as-you-go for one-time migrations.
- **Data consistency:** Use data check feature (DescribeCheckJobs) after migration to verify completeness.

## Token Efficiency Guidelines (P0 — 强制)

### TE-1: API Query > Static Tables
Use `aliyun dts DescribeDTSIP` and `DescribeDtsJobs` instead of hardcoding IP ranges or task lists.
### TE-2: Compact error tables
Error codes in compact format with Agent Action column only.
### TE-3: Centralized JSON paths
Common JSON paths declared once in SKILL.md and references.
### TE-4: YAML anchors in example-config.yaml
### TE-5: Eliminate cross-file duplicate flows

---

## Quality Gate (GCL)

Phase 1 rollout of GCL per [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 1, 1st skill — DTS has destructive ops: DeleteDtsJob, ResetDtsJob, StopDtsJob) |
| `max_iter` | 2 |
| Most-scrutinized | `DeleteDtsJob` (irreversible), `ResetDtsJob` (clears progress), `ConfigureDtsJob` (password exposure) |
| Hard rule | Source/target database passwords in `ConfigureDtsJob` MUST NOT appear unmasked in any trace; Safety = 0 → ABORT |

### Changelog
1.0.0 | 2026-06-04 | Phase 1 rollout.

---

## See Also

- [Alibaba Cloud DTS Documentation](https://help.aliyun.com/zh/dts)
- [DTS Supported Source/Target Matrix](https://help.aliyun.com/zh/dts/supported-sources-and-targets)
- [DTS OpenAPI Reference](https://help.aliyun.com/zh/dts/developer-reference/api-dts-2020-01-01-overview)
- [RAM Permission Policies for DTS](https://help.aliyun.com/zh/dts/security/complianc/ram-based-access-management)