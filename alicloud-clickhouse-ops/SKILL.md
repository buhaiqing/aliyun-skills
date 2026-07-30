---
name: alicloud-clickhouse-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba
  Cloud ApsaraDB for ClickHouse — Enterprise Edition clusters (serverless,
  multi-AZ, Computing Groups) and Classic Edition clusters (legacy fixed-spec).
  User mentions ClickHouse, 云数据库ClickHouse, OLAP, 实时分析, 写入分析, or
  describes ClickHouse-specific scenarios (cluster lifecycle, account management,
  backup policy, slow query analysis, security IP whitelist, Computing Groups)
  even without naming the product directly. Not for billing, RAM, VPC (unless
  VPC endpoint configuration), or related products that have their own ops skills.
license: MIT
compatibility: >-
  Alibaba Cloud CLI (Enterprise Edition: `aliyun clickhouse` via plugin
  `aliyun-cli-clickhouse`; Classic Edition: Go SDK
  `github.com/alibabacloud-go/clickhouse-20191111`), valid API credentials,
  network access to Alibaba Cloud ClickHouse endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-07-29"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "clickhouse-2023-05-22 (Enterprise) / clickhouse-2019-11-11 (Classic)"
  cli_applicability: "dual-path"
  cli_support_evidence: >-
    Enterprise Edition operations are fully exposed via `aliyun clickhouse`
    CLI (plugin `aliyun-cli-clickhouse` v0.7.1+). Classic Edition operations
    are NOT exposed via the CLI plugin; use Go SDK directly. Path selection
    is determined by target instance edition.
  well_architected_compliance: "80% (Security: 90%, Stability: 85%, Cost: 70%, Performance: 75%, Efficiency: 80%)"
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud ApsaraDB for ClickHouse Operations Skill

## Overview

ApsaraDB for ClickHouse (云数据库 ClickHouse 版) is a fully managed real-time analytics database service based on the open-source ClickHouse. Alibaba Cloud offers two editions:

| Edition | Path | API Version | Best For |
|---------|------|-------------|----------|
| **Enterprise Edition** | `aliyun clickhouse` CLI (plugin) | `2023-05-22` | New deployments, serverless, multi-AZ, Computing Groups |
| **Classic Edition** | Go SDK `clickhouse-20191111` | `2019-11-11` | Legacy fixed-spec instances |

This skill is an **operational runbook** for agents: explicit scope, credential rules, pre-flight checks, **edition-aware path selection**, response validation, and failure recovery. **Do not use the web console as the primary agent execution path.**

> **UX Compliance:** This skill follows the [User Experience Specification](../alicloud-skill-generator/references/user-experience-spec.md). All operations include onboarding guidance, minimal prompts, smart defaults, clear feedback, and user-friendly error handling.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`** — Edition determines path:
  - **Enterprise Edition:** `aliyun clickhouse` (plugin `aliyun-cli-clickhouse`); CLI is the primary path.
  - **Classic Edition:** JIT Go SDK `github.com/alibabacloud-go/clickhouse-20191111`; CLI does NOT support Classic APIs.
  - **NEVER** send Enterprise-only operations (`StartDBInstance`, `StopDBInstance`, `NodeScaleMin/Max`, `ComputingGroupId`) to a Classic Edition instance.
  - **NEVER** send Classic-only operations (`ModifyDBCluster`, `CreateDatabase` legacy, `DescribeDBConfig`) to an Enterprise Edition instance.

### Path Selection Quick Check

```text
User request: operate on ClickHouse instance X
│
├─ Is X Enterprise Edition?
│  ├─ YES → Use `aliyun clickhouse` (Enterprise CLI)
│  │         Plugin required: aliyun-cli-clickhouse
│  │         Supports: Start/Stop/Restart, serverless, multi-AZ, Computing Groups
│  │
│  └─ NO (Classic) → Use Go SDK (clickhouse-20191111)
│                    Supports: fixed-spec only, no serverless
│
└─ For ambiguous operations (e.g., `CreateDBInstance`), use edition-appropriate API
   - Enterprise: `aliyun clickhouse CreateDBInstance --RegionId ...`
   - Classic:    `client.CreateDBInstance(req)` with RegionId field
```

## Five Core Standards (Quality Gates)

Every generated skill MUST satisfy these five standards. Use them as a design checklist:

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers and delegation rules |
| 2 | **Structured I/O** | Placeholder conventions (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) with type and source documented |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute → Validate → Recover, with numbered imperative steps |
| 4 | **Complete Failure Strategies** | Error taxonomy table with ≥ 10 ClickHouse-specific codes; HALT vs retry per error type |
| 5 | **Absolute Single Responsibility** | One product (ClickHouse), one primary resource model (DBInstance); cross-product delegation to other skills |

### Well-Architected Framework Integration (卓越架构)

In addition to the Five Core Standards, every generated skill MUST map its operations to Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html) five pillars:

| Pillar | Skill Integration | Reference |
|--------|-------------------|-----------|
| **安全 (Security)** | IAM permissions, credential masking, security IP whitelist, account authority levels | `references/well-architected-assessment.md` §2 |
| **稳定 (Stability)** | Multi-AZ (Enterprise), backup policy, restart/upgrade runbook, edition-specific HA patterns | `references/well-architected-assessment.md` §3 |
| **成本 (Cost)** | Serverless scaling, Stop vs Delete, storage tiering, NodeScaleMax guardrails | `references/well-architected-assessment.md` §4 |
| **效率 (Efficiency)** | Backup automation, slow query monitoring, batch restart, CI/CD integration | `references/well-architected-assessment.md` §5 |
| **性能 (Performance)** | CMS metrics, slow log analysis, Computing Groups (Enterprise), query optimization | `references/well-architected-assessment.md` §6 |

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/clickhouse-harness-wrapper.sh` for all ClickHouse CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun clickhouse` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. For runtime enforcement, source the shared shim: `source ../../alicloud-skill-generator/scripts/skillopt-shim/aliyun-shim.sh`. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md), [Shim](../alicloud-skill-generator/scripts/skillopt-shim/SHIM-README.md) |
| Plugin (Enterprise) | **MANDATORY**: Verify `aliyun-cli-clickhouse` plugin is installed before any `aliyun clickhouse` call | CLI Setup |
| SDK (Classic) | **MANDATORY**: Use Go SDK `github.com/alibabacloud-go/clickhouse-20191111/v3/client` for Classic Edition ops | `references/api-sdk-usage.md` |
| Path selection | **CRITICAL**: Always verify target instance edition BEFORE selecting CLI vs SDK | `references/rubric.md` §2 |
| Credentials | Read {{env.*}} from environment; never ask user to paste secrets | Integration |
| GCL | All write operations MUST pass GCL review before execution | GCL Rubric |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "ApsaraDB for ClickHouse" OR "云数据库ClickHouse" OR "OLAP" OR "实时分析" OR "ClickHouse实例"
- Task involves lifecycle operations on **DBInstance** (create, describe, modify, delete, restart, start, stop, upgrade)
- Task involves **account management** (create, delete, describe, reset password, modify authority)
- Task involves **backup** (describe backups, create/modify backup policy)
- Task involves **slow query analysis** (DescribeSlowLogRecords, DescribeSlowLogTrend)
- Task involves **security IP whitelist** (modify, describe)
- Task involves **Computing Group** operations (Enterprise Edition only)
- Task involves **endpoint/connection** management (create, describe, modify connection string)
- User keywords: 集群管理, 账户管理, 备份策略, 慢查询, 安全白名单, 计算组, 端点, 实时数仓
- User asks to deploy, configure, troubleshoot, or monitor ClickHouse **via API, SDK, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops`
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops`
- Task is VPC network creation only → delegate to: `alicloud-vpc-ops` (VPC endpoint config is within scope)
- Task is data-plane operation (INSERT/SELECT via JDBC/ClickHouse client) → NOT a skill task
- Task is cross-product orchestration → delegate to: `alicloud-aiops-cruise` or `alicloud-advisor-ops`
- User insists on **console-only** flows with no API → state limitation; do not invent undocumented HTTP steps

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |
| CMS 监控配置 | `alicloud-cms-ops` | ClickHouse 监控告警规则应通过 cms-ops 设置 |
| VPC 网络 | `alicloud-vpc-ops` | VPC、VSwitch 创建委托给 vpc-ops |
| 计费优化 | `alicloud-billing-ops` | 成本分析、月度账单 |

## Variable Convention (Agent-Readable)

Structured placeholders reduce injection ambiguity and unsafe prompts:

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.db_instance_id}}` | User-supplied ClickHouse instance ID | Ask once; reuse |
| `{{user.db_instance_description}}` | User-supplied instance name | Ask once; reuse |
| `{{user.node_count}}` | Node count (2-16 Fixed, or use NodeScaleMin/Max) | Ask once; reuse |
| `{{user.account_name}}` | ClickHouse account name | Ask once; reuse |
| `{{user.account_password}}` | Account password (NEVER log/trace) | Ask once; reuse |
| `{{output.db_instance_id}}` | From last API JSON response | Parse from response body |
| `{{output.edition}}` | Detected edition (Enterprise / Classic) | Parse from response |
| `{{output.backup_id}}` | From DescribeBackups response | Parse before DeleteDBInstance |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)。`{{user.account_password}}` MUST be masked in all trace/log output.

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes.
- **Endpoint (Enterprise):** `clickhouse.aliyuncs.com` (public) or VPC endpoint
- **Endpoint (Classic):** `clickhouse.aliyuncs.com`
- **API Version:**
  - Enterprise: `2023-05-22` (via CLI)
  - Classic: `2019-11-11` (via Go SDK)
- **SDK Package (Classic):** `github.com/alibabacloud-go/clickhouse-20191111/v3/client`

### Example Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateDBInstance (Enterprise) | `Body.DBInstanceId` | string | New ClickHouse instance ID |
| DescribeDBInstanceAttribute (Enterprise) | `Body.DBInstance.DBInstanceStatus` | string | Status (Running, Creating, Stopped, etc.) |
| DescribeDBInstanceAttribute (Enterprise) | `Body.DBInstance.NodeCount` | int | Number of nodes (Enterprise) |
| DescribeDBInstanceAttribute (Enterprise) | `Body.DBInstance.EngineVersion` | string | ClickHouse engine version |
| DescribeDBInstances (Enterprise) | `Body.DBInstances.DBInstance[*].DBInstanceId` | array | List of instance IDs |
| DescribeBackups (Enterprise) | `Body.Backups.Backup[*].BackupId` | array | List of backup IDs |
| DescribeBackups (Enterprise) | `Body.Backups.Backup[*].BackupStatus` | array | Backup status (Success / Failed) |
| DescribeAccounts (Enterprise) | `Body.Accounts.Account[*].AccountName` | array | List of account names |
| DescribeSecurityIPList (Enterprise) | `Body.SecurityIPList[*].SecurityIPList` | string | Current whitelist (CSV) |
| DescribeEndpoints (Enterprise) | `Body.Data.Endpoints[*].Address` | array | Endpoint addresses |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateDBInstance (Enterprise) | — | `Running` | 30s | 1800s (30min) |
| CreateDBInstance (Serverless) | — | `Running` | 30s | 1800s |
| RestartDBInstance | `Running` | `Running` | 10s | 300s |
| StartDBInstance | `Stopped` | `Running` | 10s | 300s |
| StopDBInstance | `Running` | `Stopped` | 10s | 300s |
| DeleteDBInstance | `Running` | absent | 10s | 600s |
| ModifyDBInstanceClass | `Running` | `Running` | 30s | 1800s |

## Quick Start

### What This Skill Does

This skill enables you to deploy, configure, troubleshoot, and monitor ApsaraDB for ClickHouse (Enterprise and Classic editions) on Alibaba Cloud using the appropriate edition path.

### Prerequisites

- [ ] `aliyun` CLI installed (v3.0.0+)
- [ ] For Enterprise Edition: `aliyun-cli-clickhouse` plugin installed
- [ ] For Classic Edition: Go runtime 1.21+ with ClickHouse SDK
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`

### Verify Setup

```bash
# Check aliyun CLI
aliyun version

# Install ClickHouse plugin (Enterprise Edition)
aliyun plugin install --names aliyun-cli-clickhouse

# Verify plugin
aliyun clickhouse DescribeRegions

# Quick SDK test for Classic Edition (in /tmp/aliyun-sdk-workspace)
mkdir -p /tmp/aliyun-sdk-workspace && cd /tmp/aliyun-sdk-workspace
go mod init ch-test
go get github.com/alibabacloud-go/clickhouse-20191111/v3/client
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
```

### Your First Command (Enterprise Edition)

```bash
# List ClickHouse instances
aliyun clickhouse DescribeDBInstances --RegionId cn-hangzhou

# Get instance detail
aliyun clickhouse DescribeDBInstanceAttribute \
  --RegionId cn-hangzhou \
  --DBInstanceId cc-bp1xxxxxxxxxx

# Output as table
aliyun clickhouse DescribeDBInstances --RegionId cn-hangzhou \
  --output cols=DBInstanceId,DBInstanceStatus,DBInstanceDescription \
  rows=Data.DBInstances[]
```

### Your First Command (Classic Edition — Go SDK)

```go
package main

import (
    "fmt"
    "os"
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    clickhouse "github.com/alibabacloud-go/clickhouse-20191111/v3/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("clickhouse.aliyuncs.com"),
    }
    client, _ := clickhouse.NewClient(config)
    req := &clickhouse.DescribeDBInstancesRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    resp, _ := client.DescribeDBInstances(req)
    fmt.Println(tea.ToString(resp.Body))
}
```

### Next Steps

- [Core Concepts](references/core-concepts.md) — Understand ClickHouse architecture and editions
- [CLI Usage](references/cli-usage.md) — Enterprise Edition command map
- [API/SDK Usage](references/api-sdk-usage.md) — Classic Edition SDK reference
- [Troubleshooting](references/troubleshooting.md) — Fix common issues
- [Well-Architected Assessment](references/well-architected-assessment.md) — Five-pillar review
- [GCL Rubric](references/rubric.md) — Quality gate for write operations

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| CreateDBInstance (Enterprise) | Create new Enterprise Edition cluster | High | Low |
| CreateDBInstance (Serverless) | Create serverless cluster with elastic scaling | High | Medium |
| DescribeDBInstances | List all ClickHouse instances | Low | None |
| DescribeDBInstanceAttribute | Get instance details | Low | None |
| ModifyDBInstanceClass | Scale node count / storage | Medium | Medium |
| RestartDBInstance | Reboot cluster | Medium | Medium |
| StartDBInstance | Resume stopped cluster (Enterprise only) | Low | Low |
| StopDBInstance | Pause cluster (Enterprise only) | Low | Low |
| DeleteDBInstance | Remove instance — **irreversible** | Low | **High** |
| CreateAccount | Create database user | Low | Low |
| ResetAccountPassword | Reset user password | Low | Medium |
| ModifyAccountAuthority | Change user permissions | Low | Medium |
| CreateBackupPolicy | Set automated backup schedule | Low | Low |
| ModifyBackupPolicy | Update backup policy | Low | Low |
| DescribeBackups | List recent backups | Low | None |
| DescribeSlowLogRecords | Review slow queries | Low | None |
| DescribeSlowLogTrend | Slow query trend analysis | Low | None |
| KillProcess | Terminate long-running query | Low | Medium |
| ModifySecurityIPList | Update whitelist | Low | **High** (overwrite mode) |
| DescribeEndpoints | List network endpoints | Low | None |
| CreateEndpoint | Provision new endpoint | Low | Low |
| ModifyDBInstanceConfig | Update cluster configuration | Medium | Medium |
| UpgradeMinorVersion | Upgrade engine version | High | High |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-07-29 | Initial ClickHouse skill (dual-path). Enterprise Edition CLI (2023-05-22) + Classic Edition SDK (2019-11-11). All P0/P1 items completed. |

## Execution Flows (Agent-Readable)

> **MANDATORY**: Edition determines execution path. Always verify edition BEFORE executing.

Every operation: **Pre-flight → Execute → Validate → Recover**. Do not skip phases.

> **EXECUTION MANDATORY RULE**: 所有 CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/clickhouse-harness-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun clickhouse ...` 命令在执行时应替换为 `./scripts/clickhouse-harness-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun clickhouse` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。

### Operation: Create ClickHouse Instance (Enterprise Edition)

#### Pre-flight Checks (Create ClickHouse Instance)

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Plugin installed | `aliyun plugin list \| grep aliyun-cli-clickhouse` | Plugin present | Install via `aliyun plugin install --names aliyun-cli-clickhouse` |
| Credentials | Env vars set; construct credential | Non-empty keys | HALT; user configures env |
| Region | `aliyun clickhouse DescribeRegions` | Region supported | Suggest valid region |
| Quota | `aliyun clickhouse DescribeDBInstances` count | < 10 per region | HALT; user raises quota |
| VPC exists | Validate VPC and VSwitch IDs | Found in region | HALT; create via vpc-ops |
| NodeCount valid | 2-16 (Fixed) or set NodeScaleMin/Max (Serverless) | Valid range | Adjust |
| Engine version | 23.x for Enterprise | Version available | Use supported version |

#### Execution (Enterprise Edition CLI)

```bash
# Minimal: fixed-spec cluster with 2 nodes
aliyun clickhouse CreateDBInstance \
  --RegionId cn-hangzhou \
  --DBInstanceDescription "my-clickhouse" \
  --NodeCount 2

# Serverless: elastic cluster (min 4 nodes, max 16)
aliyun clickhouse CreateDBInstance \
  --RegionId cn-hangzhou \
  --DBInstanceDescription "serverless-ch" \
  --NodeScaleMin 4 \
  --NodeScaleMax 16

# Multi-AZ
aliyun clickhouse CreateDBInstance \
  --RegionId cn-hangzhou \
  --DBInstanceDescription "prod-ch" \
  --NodeCount 6 \
  --MultiZone '{"zones":[{"zoneId":"cn-hangzhou-h","vswitchId":"vsw-xxx"},{"zoneId":"cn-hangzhou-i","vswitchId":"vsw-yyy"}]}'
```

#### Post-execution Validation

1. Capture `{{output.db_instance_id}}` from response: `Body.DBInstanceId`
2. Poll DescribeDBInstanceAttribute until terminal success state:

```bash
# Polling loop
for i in $(seq 1 60); do
  STATUS=$(aliyun clickhouse DescribeDBInstanceAttribute \
    --RegionId cn-hangzhou \
    --DBInstanceId cc-bp1xxxxxxxxxx \
    --output cols=DBInstanceStatus \
    rows=Data.DBInstance.DBInstanceStatus 2>/dev/null)
  if [ "$STATUS" = "Running" ]; then
    echo "✅ Instance created and running"
    break
  fi
  if [ "$STATUS" = "Creating" ] || [ "$STATUS" = "ConfigModifying" ]; then
    sleep 30
    continue
  fi
  echo "❌ Unexpected status: $STATUS"
  break
done
```

#### Failure Recovery

| Error pattern | Max retries | Agent Action | UX Feedback |
|--------------|-------------|--------------|-------------|
| `InvalidParameter.NodeCount` | 0 | Adjust to 2-16 (Fixed) or 4-32 (Serverless) | `[ERROR] InvalidParameter.NodeCount: Use 2-16 (Fixed) or 4-32 (Serverless).` |
| `InvalidParameter.StorageQuota` | 0 | Adjust to valid range | `[ERROR] InvalidParameter.StorageQuota: Max 32000GB per node.` |
| `QuotaExceeded` | 0 | HALT; user raises quota | `[ERROR] QuotaExceeded: Instance quota reached (10/region). Request increase.` |
| `VpcNotFound` | 0 | HALT; create VPC via vpc-ops | `[ERROR] VpcNotFound: Create VPC first using alicloud-vpc-ops.` |
| `EngineVersionNotSupported` | 0 | Use 23.x for Enterprise | `[ERROR] EngineVersionNotSupported: Use 23.x for Enterprise Edition.` |
| `Throttling` / 429 | 3 | Exponential backoff 2s → 4s → 8s | `⚠️ Rate limited. Retrying in {backoff}s...` |
| `InternalError` / 5xx | 3 | Retry with backoff; HALT if persists | `[ERROR] InternalError: Server error. RequestId: {id}. Retry or escalate.` |

### Operation: Describe ClickHouse Instances

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Path | Verify edition + corresponding tool | Tool available | Switch path |
| Region | Env var set | Non-empty | HALT |

#### Execution (Enterprise Edition CLI)

```bash
# List all instances in region
aliyun clickhouse DescribeDBInstances --RegionId cn-hangzhou

# Filter by status
aliyun clickhouse DescribeDBInstances \
  --RegionId cn-hangzhou \
  --DBInstanceStatus Running

# Output as compact table
aliyun clickhouse DescribeDBInstances --RegionId cn-hangzhou \
  --output cols=DBInstanceId,DBInstanceStatus,DBInstanceDescription,NodeCount \
  rows=Data.DBInstances[]
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| DBInstanceId | `Body.DBInstances.DBInstance[*].DBInstanceId` | Unique identifier |
| Status | `Body.DBInstances.DBInstance[*].DBInstanceStatus` | Running/Creating/Stopped |
| Description | `Body.DBInstances.DBInstance[*].DBInstanceDescription` | Display name |
| NodeCount | `Body.DBInstances.DBInstance[*].NodeCount` | Enterprise: number of nodes |
| Engine | `Body.DBInstances.DBInstance[*].Engine` | ClickHouse |
| EngineVersion | `Body.DBInstances.DBInstance[*].EngineVersion` | e.g., 23.8 |

### Operation: Restart ClickHouse Instance

#### Pre-flight (Safety Gate)

- **WARN** user: Restart causes temporary service interruption
- **MUST** confirm: instance ID and restart intent
- **VERIFY** status is `Running` (or `Stopped` for Start)
- **VERIFY** no pending operations

#### Execution (Enterprise Edition CLI)

```bash
aliyun clickhouse RestartDBInstance \
  --DBInstanceId cc-bp1xxxxxxxxxx \
  --RegionId cn-hangzhou
```

#### Execution (Classic Edition — Go SDK)

```go
client.RestartInstance(&clickhouse.RestartInstanceRequest{
    RegionId:     tea.String(regionId),
    DBInstanceId: tea.String(instanceId),
})
```

#### Post-execution Validation

Poll `DescribeDBInstanceAttribute` until status returns to `Running` (max 300s).

### Operation: Delete ClickHouse Instance (DESTRUCTIVE)

#### Pre-flight (Safety Gate — MANDATORY)

- **MUST** obtain explicit confirmation: irreversible delete of `{{user.db_instance_description}}` (`{{user.db_instance_id}}`)
- **MUST** warn user: all data, accounts, backups will be lost
- **MUST** verify recent backup exists (via `DescribeBackups`)
- **MUST NOT** proceed without clear user assent

#### Execution (Enterprise Edition CLI)

```bash
# Pre-check: confirm backup
aliyun clickhouse DescribeBackups \
  --DBInstanceId cc-bp1xxxxxxxxxx \
  --RegionId cn-hangzhou \
  --StartTime "$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# After user confirmation AND backup verification:
aliyun clickhouse DeleteDBInstance \
  --DBInstanceId cc-bp1xxxxxxxxxx \
  --RegionId cn-hangzhou
```

#### Post-execution Validation

Poll `DescribeDBInstanceAttribute` until `InvalidDBInstanceId.NotFound` (instance deleted).

### Operation: Modify Security IP Whitelist (DESTRUCTIVE if overwrite)

#### Pre-flight (Safety Gate)

- **WARN** user: `ModifyMode=0` (overwrite) can lock out all clients
- **RECOMMEND** `ModifyMode=1` (append) unless explicitly resetting
- **CONFIRM** IP format is valid (CIDR or single IP)

#### Execution (Enterprise Edition CLI)

```bash
# Append (safe, default)
aliyun clickhouse ModifySecurityIPList \
  --DBInstanceId cc-bp1xxxxxxxxxx \
  --RegionId cn-hangzhou \
  --SecurityIPList "10.0.0.0/8" \
  --GroupName default \
  --ModifyMode 1

# Overwrite (only when explicitly approved to reset)
aliyun clickhouse ModifySecurityIPList \
  --DBInstanceId cc-bp1xxxxxxxxxx \
  --RegionId cn-hangzhou \
  --SecurityIPList "127.0.0.1" \
  --GroupName default \
  --ModifyMode 0
```

#### Post-execution Validation

`DescribeSecurityIPList` to verify new whitelist; test connection from authorized client.

## Prerequisites

### 1. Install ClickHouse Plugin (Enterprise Edition)

```bash
# Install the ClickHouse plugin
aliyun plugin install --names aliyun-cli-clickhouse

# Verify installation
aliyun clickhouse DescribeRegions

# If plugin install fails (network issue):
# 1. Check `aliyun version` (must be v3.0.0+)
# 2. Manually download from https://github.com/aliyun/aliyun-cli-clickhouse/releases
```

### 2. Configure Credentials

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
```

> **IMPORTANT:** When outputting the above commands to console or logs, the agent MUST replace `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` with the masking format `****` instead of the actual secret value. Never resolve `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` to its actual value in any visible output.

### 3. Initialize SDK Workspace (Classic Edition — Optional)

```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init ch-sdk-script

# Core dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/tea-utils/v2/service

# ClickHouse Classic SDK
go get github.com/alibabacloud-go/clickhouse-20191111/v3/client
```

## Reference Directory

- [Core Concepts](references/core-concepts.md) — Editions, architecture, limits, quotas
- [CLI Usage](references/cli-usage.md) — Enterprise Edition command map
- [API & SDK Usage](references/api-sdk-usage.md) — Classic Edition SDK reference
- [Monitoring & Alerts](references/monitoring.md) — CMS metrics, alarm thresholds
- [Troubleshooting Guide](references/troubleshooting.md) — Error codes, diagnostic procedure
- [Well-Architected Assessment](references/well-architected-assessment.md) — Five-pillar review
- [GCL Rubric](references/rubric.md) — Quality gate for write operations
- [GCL Prompt Templates](references/prompt-templates.md) — Generator/Critic templates
- [User-Facing Prompt Examples](references/prompt-examples.md) — NL prompt examples
- [User Experience Specification](../alicloud-skill-generator/references/user-experience-spec.md)
- [Execution Environment Setup](../alicloud-skill-generator/references/execution-environment.md)

## Operational Best Practices

- **Path selection first:** Always verify edition BEFORE choosing CLI vs SDK.
- **Least privilege:** RAM policies scoped to `clickhouse:Describe*` for audit, `clickhouse:*` for operators.
- **Multi-zone:** Recommend distributing nodes across multiple zones for HA (Enterprise Edition only).
- **Backup:** Create backups before major changes (restart, upgrade, spec change).
- **Security IP:** Default to `ModifyMode=1` (append); never use `0.0.0.0/0` in production.
- **Serverless cost guard:** Always set explicit `NodeScaleMax` to prevent runaway billing.
- **Password handling:** Never log or trace `ResetAccountPassword` password value; mask in all output.

---

## Quality Gate (GCL)

Dual-path rollout of GCL per [`AGENTS.md` §12](../docs/gcl-spec.md#generator-critic-loop-gcl--implementation-spec). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 1, dual-path skill) |
| `max_iter` | 2 |
| `cli_applicability` | **dual-path** (Enterprise CLI + Classic SDK) |
| Most-scrutinized | **Path-edition mismatch** (LAYER 2 pre-flight); `DeleteDBInstance` without backup; `ModifySecurityIPList` with `ModifyMode=0` without justification; `ResetAccountPassword` password leak |
| Hard rule | Edition path MUST be selected BEFORE any other pre-flight; `DeleteDBInstance` requires verified backup; `ResetAccountPassword` MUST NOT log password |

### Changelog

1.0.0 | 2026-07-29 | Dual-path rollout. Enterprise Edition CLI (2023-05-22) primary; Classic Edition SDK (2019-11-11) fallback. Edition-aware path selection in rubric. 6 destructive op classes.

---

## Well-Architected Assessment

This skill's operations are evaluated against Alibaba Cloud's Well-Architected Framework (卓越架构). For detailed assessment patterns per pillar:

- Security Assessment — `references/well-architected-assessment.md` §2
- Stability Assessment — `references/well-architected-assessment.md` §3
- Cost Assessment — `references/well-architected-assessment.md` §4
- Efficiency Assessment — `references/well-architected-assessment.md` §5
- Performance Assessment — `references/well-architected-assessment.md` §6

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **Dual-Path Rule (NEW):** This skill is `cli_applicability: dual-path`. Both
  CLI (Enterprise) and SDK (Classic) execution paths are required. The skill
  MUST document path selection criteria explicitly in `SKILL.md` and
  `references/rubric.md`. Path mismatch is a first-class failure mode.
- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: dual-path`, the skill MUST provide runnable code
  snippets for BOTH paths (Enterprise CLI examples + Classic Go SDK examples).
  **APPLIES** — both paths documented in this skill.
