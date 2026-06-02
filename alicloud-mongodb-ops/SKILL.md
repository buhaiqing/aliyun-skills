---
name: alicloud-mongodb-ops
description: >-
  Use when deploying, configuring, troubleshooting, or monitoring Alibaba Cloud
  MongoDB / ApsaraDB for MongoDB instances — create, modify, delete, restart,
  scale, migrate, upgrade, or manage instances; manage accounts, databases,
  backups, whitelists, SSL, parameters, and maintenance windows; monitor CPU,
  memory, connections, IOPS, and operation metrics; analyze slow queries, and
  diagnose connection timeouts, high latency, OOM, CPU spikes, and replication
  lag. Trigger even without explicit "MongoDB" — Chinese terms: 云数据库MongoDB,
  文档数据库, 实例, 备份, 白名单, 参数, 监控, 慢查询, 连接超时, 延迟高,
  ApsaraDB for MongoDB, DDS. NOT for RDS, PolarDB, Redis/Tair, or billing/RAM-only
  tasks.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.1.0"
  last_updated: "2026-05-19"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "Dds 2015-12-01 / https://help.aliyun.com/zh/apsaradb-for-mongodb"
  cli_applicability: dual-path
  cli_support_evidence: "Confirmed via `aliyun help dds` — MongoDB (Dds) is fully supported by the official aliyun CLI."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud MongoDB / ApsaraDB for MongoDB Operations Skill

## Overview

Alibaba Cloud MongoDB (ApsaraDB for MongoDB / DDS) provides managed MongoDB-compatible
document database services supporting standalone, replica set, and sharded cluster
architectures. This skill is an **operational runbook** for agents: explicit scope,
credential rules, pre-flight checks, **dual-path execution** (official **SDK/API**
and **CLI** flows), response validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` fully supports `dds` (MongoDB).
  Each execution flow documents **both** the SDK step and the `aliyun` step for
  every operation.

### Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers and delegation rules |
| 2 | **Structured I/O** | Placeholder conventions (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) with type and source documented |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute → Validate → Recover, with numbered imperative steps |
| 4 | **Complete Failure Strategies** | Error taxonomy table with ≥ 10 product-specific codes; HALT vs retry per error type |
| 5 | **Absolute Single Responsibility** | One product, one primary resource model; cross-product delegation to other skills |

### Well-Architected Framework Integration (卓越架构)

Operations map to Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html):
- **安全 (Security)**: IAM permissions, credential masking, network isolation
- **稳定 (Stability)**: Backup/restore, multi-AZ, DR runbook, failure-oriented design
- **成本 (Cost)**: Billing model comparison, waste detection, right-sizing
- **效率 (Efficiency)**: Batch operations, CI/CD integration, automation patterns
- **性能 (Performance)**: Metrics, auto-scaling, performance baselines

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud MongoDB" OR "ApsaraDB for MongoDB" OR "DDS" OR "云数据库MongoDB" OR "文档数据库"
- Task involves CRUD or lifecycle operations on **MongoDB instances** (create, describe, modify, delete, list, restart, upgrade)
- Task involves **instance accounts** (create, describe, delete, reset password)
- Task involves **databases** (create, describe, delete)
- Task involves **backups** (create, describe, restore, delete)
- Task involves **whitelists / security groups** (describe, modify)
- Task involves **parameters** (describe, modify)
- Task involves **performance monitoring** (CPU, memory, connections, IOPS, operation counts)
- Task involves **slow query logs** (describe, analyze)
- Task involves **instance migration, scaling, or architecture changes**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops`
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops`
- Task is about **RDS (relational database)** → delegate to: `alicloud-rds-ops`
- Task is about **PolarDB MySQL** → delegate to: `alicloud-polar-mysql-ops`
- Task is about **PolarDB PostgreSQL** → delegate to: `alicloud-polar-pg-ops`
- Task is about **Redis / Tair** → delegate to: `alicloud-redis-ops`
- User insists on **console-only** flows with no API → state limitation; do not invent undocumented HTTP steps

### Delegation Rules

- If creating a MongoDB instance in a VPC, verify VPC and VSwitch exist (via `alicloud-vpc-ops`) before instance creation.
- If restoring from backup, verify the backup exists via DescribeBackups before initiating RestoreDBInstance.
- Multi-product requests: handle each product with its skill; do not merge unrelated APIs into one ambiguous flow.

**Cross-Skill Verification Examples:**

```bash
# Verify VPC exists before creating MongoDB instance (delegate to alicloud-vpc-ops)
aliyun vpc DescribeVpcs \
  --RegionId "{{user.region}}" \
  --VpcId "{{user.vpc_id}}" \
  --output cols=VpcId,Status,VSwitchIds rows=Vpcs.Vpc[]

# Verify VSwitch exists
aliyun vpc DescribeVSwitches \
  --RegionId "{{user.region}}" \
  --VpcId "{{user.vpc_id}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --output cols=VSwitchId,Status,CidrBlock rows=VSwitches.VSwitch[]

# For cost analysis, delegate to alicloud-billing-ops
# aliyun bssopenapi QueryAccountBalance
# aliyun bssopenapi QueryBillOverview --BillingCycle 2026-05
```

## Key Concepts

### Instance Types

| Type | Architecture | Use Case | HA Support |
|------|--------------|----------|------------|
| **standalone** | Single node | Dev/test, low-criticality | No HA |
| **replicaset** | 3/5/7 nodes | Production workloads | Multi-AZ HA, automatic failover |
| **sharding** | Mongos + Shard + Config | Large-scale, high-throughput | Horizontal scaling |

**Details:** See `references/sharding-ops.md` for sharding architecture and `references/replicaset-ops.md` for replica set operations.

### Engine Versions

| Version | Status | Notes |
|---------|--------|-------|
| 4.0 | Legacy | Extended support |
| 4.2 | Stable | Recommended for compatibility |
| 4.4 | Stable | Most common production version |
| 5.0 | Active | New features, improved performance |
| 6.0 | Active | Latest LTS, enhanced sharding |
| 7.0 | Active | Newest, advanced features |

### Storage Types

| Type | Performance | Use Case |
|------|-------------|----------|
| **cloud_ssd** | Standard SSD | General workloads |
| **cloud_essd** | Enhanced SSD | High IOPS, latency-sensitive |

## Core Actions

### Instance Lifecycle

| Operation | API | CLI | Complexity | Risk |
|-----------|-----|-----|------------|------|
| Create | `CreateDBInstance` | `aliyun dds CreateDBInstance` | High | Low |
| Describe | `DescribeDBInstances` | `aliyun dds DescribeDBInstances` | Low | None |
| Describe Attribute | `DescribeDBInstanceAttribute` | `aliyun dds DescribeDBInstanceAttribute` | Low | None |
| Modify Spec | `ModifyDBInstanceSpec` | `aliyun dds ModifyDBInstanceSpec` | Medium | Medium |
| Restart | `RestartDBInstance` | `aliyun dds RestartDBInstance` | Low | Medium |
| Delete | `DeleteDBInstance` | `aliyun dds DeleteDBInstance` | Low | **High** — irreversible |

**Pre-flight pattern (all operations):**
1. Verify SDK/CLI availability: `aliyun version`
2. Verify credentials exist (non-empty check only, never expose values)
3. Verify region: `aliyun dds DescribeRegions`
4. Verify instance exists (for modify/restart/delete): `DescribeDBInstances`

**State Transitions:**

| Operation | Initial → Target | Poll Interval | Max Wait |
|-----------|------------------|---------------|----------|
| CreateDBInstance | — → `Running` | 10s | 600s |
| RestartDBInstance | `Running` → `Running` | 10s | 300s |
| DeleteDBInstance | any → absent | 10s | 300s |
| ModifyDBInstanceSpec | `Running` → `Running` | 10s | 600s |

### Account Management

| Operation | API | CLI |
|-----------|-----|-----|
| Describe Accounts | `DescribeAccounts` | `aliyun dds DescribeAccounts` |
| Create Account | `CreateAccount` | `aliyun dds CreateAccount` |
| Delete Account | `DeleteAccount` | `aliyun dds DeleteAccount` |
| Reset Password | `ResetAccountPassword` | `aliyun dds ResetAccountPassword` |

**Account Types:** `root` (system admin) / `normal` (application accounts)

**Password Policy:**
- Minimum 8 characters; recommend 16+ for production
- Must contain uppercase, lowercase, digit, and special character
- Avoid common passwords and dictionary words
- Rotate passwords every 90 days for production accounts

**Least Privilege Best Practices:**

| Practice | Recommendation | Risk if Ignored |
|----------|----------------|-----------------|
| **Application accounts** | Create dedicated `normal` accounts per application | Root compromise = full database access |
| **Database scope** | Grant account access to only required databases | Over-permissioned accounts increase blast radius |
| **Role assignment** | Use built-in roles: `read`, `readWrite`, `dbAdmin` | Custom roles may have excessive permissions |
| **Root usage** | Reserve `root` for DBA operations only | Application bugs can destroy all data |

**Example: Create Least-Privilege Application Account**
```bash
# Create a normal account with readWrite on a single database
aliyun dds CreateAccount \
  --DBInstanceId "{{user.db_instance_id}}" \
  --AccountName "app_user" \
  --AccountPassword "{{user.app_password}}" \
  --AccountType "Normal"

# After creation, grant specific database permissions via MongoDB shell
# (Alibaba Cloud MongoDB may require console or additional API for role assignment)
```

### Database Operations

| Operation | API | CLI |
|-----------|-----|-----|
| Describe Databases | `DescribeDatabases` | `aliyun dds DescribeDatabases` |
| Create Database | `CreateDatabase` | `aliyun dds CreateDatabase` |
| Delete Database | `DeleteDatabase` | `aliyun dds DeleteDatabase` |

### Backup Operations

| Operation | API | CLI |
|-----------|-----|-----|
| Describe Backups | `DescribeBackups` | `aliyun dds DescribeBackups` |
| Create Backup | `CreateBackup` | `aliyun dds CreateBackup` |
| Restore Instance | `RestoreDBInstance` | `aliyun dds RestoreDBInstance` |

**Backup Types:** `Automated` (scheduled) / `Manual` (user-initiated)
**Backup Modes:** `Physical` / `Logical`

**Backup Cost Considerations:**
- Backup storage is billed separately from instance storage
- Physical backups are typically larger than logical backups
- Automated backups follow the instance retention policy (default 7 days)
- Long-term retention increases storage costs; evaluate necessity

**Cost-Efficient Backup Strategy:**
```bash
# Review backup sizes and retention
aliyun dds DescribeBackups \
  --DBInstanceId "{{user.db_instance_id}}" \
  --output cols=BackupId,BackupSize,BackupType,BackupMode,BackupStartTime \
  rows=Backups.Backup[]

# Estimate: total backup storage cost ≈ Σ(BackupSize) × backup_storage_unit_price
# Delegate to alicloud-billing-ops for precise cost breakdown
```

### Monitoring & Diagnostics

| Operation | API | CLI | Purpose |
|-----------|-----|-----|---------|
| Performance Metrics | `DescribeDBInstancePerformance` | `aliyun dds DescribeDBInstancePerformance` | CPU/Memory/Connections/IOPS |
| Slow Logs | `DescribeSlowLogRecords` | `aliyun dds DescribeSlowLogRecords` | Query analysis |
| Parameters | `DescribeParameters` | `aliyun dds DescribeParameters` | Config inspection |

**Key Metrics:** `CPUUsage`, `MemoryUsage`, `ConnectionUsage`, `IOPSUsage` (CMS namespace: `acs_mongodb_dashboard`)

### DAS Integration (Database Autonomy Service)

For advanced performance analysis, connect to DAS console or use DAS APIs:

```bash
# Query DAS for performance insights
# Note: DAS provides additional AI-powered diagnostics beyond basic metrics
```

**Supported Anomaly Patterns:**

| # | Pattern | Detection Criteria | Action |
|---|---------|-------------------|--------|
| 1 | **Memory-Connection双高** | MemoryUsage > 85% AND ConnectionUsage高 | Check connection leaks, query optimization |
| 2 | **查询延迟异常** | QueryLatency突增 (>3x baseline) | Analyze slow queries, check indexes |
| 3 | **索引缺失预警** | 慢查询 + 无索引覆盖 | Create covering indexes |
| 4 | **存储空间预警** | StorageUsage > 85% | Archive/cleanup or scale storage |

**DAS Diagnostic Commands:**
```bash
# For detailed slow query analysis, delegate to alicloud-das-ops
# aliyun das DescribeSlowLogRecords
```

### Operation: Intelligent Inspection（MongoDB 智能巡检）

**Purpose**: 主动发现 MongoDB 实例性能瓶颈、安全风险和容量问题

**Five-Step Workflow**:
1. **Discovery**: `aliyun dds DescribeDBInstances` 列出所有实例
2. **Collection**: 批量采集 CPU/Memory/IOPS/Connections/Storage 指标
3. **Detection**: 应用异常模式检测 (4种已定义模式)
4. **Diagnosis**: 深度分析慢查询、索引缺失、连接池状态
5. **Report**: 生成巡检报告 (Markdown格式)

**CLI Script Template**:
```bash
#!/bin/bash
# mongodb-intelligent-inspection.sh
# Usage: ./mongodb-intelligent-inspection.sh <InstanceId> <RegionId>

InstanceId=${1}
RegionId=${2:-cn-hangzhou}

# 采集指标
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId $InstanceId \
  --RegionId $RegionId \
  --Key "CPUUsage_MemoryUsage_IOPS_Connections"

# 检查索引缺失
aliyun dds DescribeIndexRecommendation \
  --DBInstanceId $InstanceId

# 生成报告
echo "## MongoDB 巡检报告 - ${InstanceId}"
echo "| 指标 | 当前值 | 状态 |"
echo "|------|--------|------|"
```

**Inspection Scoring**:
- CPU使用率 < 70%: 10分
- 内存使用率 < 80%: 10分  
- 连接数 < 80%上限: 10分
- 慢查询 < 10/hour: 10分
- 索引覆盖率 > 90%: 10分
- 总分 < 40分 → Critical, 需立即优化

**巡检触发条件**:
- 定时任务: 每日/每周自动执行
- 事件触发: 实例规格变更、告警阈值触发
- 手动触发: 用户主动发起巡检请求

**巡检报告内容**:
- 实例概览: 规格、版本、架构、运行时间
- 性能指标: CPU/内存/IOPS/连接数/存储使用趋势
- 异常检测: 4种模式检测结果及风险等级
- 诊断建议: 针对每个问题的优化方案
- 历史对比: 与上次巡检结果对比分析

**Delegation**:
- 详细慢查询分析 → `alicloud-das-ops`
- 索引优化建议 → `alicloud-mongodb-ops` (索引管理)
- 容量规划 → `alicloud-billing-ops`

## CLI/SDK Dual-Path

### Primary Path: CLI (aliyun)

```bash
# Verify setup
aliyun dds DescribeRegions

# List instances
aliyun dds DescribeDBInstances --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}

# Create instance
aliyun dds CreateDBInstance \
  --RegionId "{{user.region}}" \
  --Engine "MongoDB" \
  --EngineVersion "{{user.engine_version}}" \
  --DBInstanceClass "{{user.db_instance_class}}" \
  --DBInstanceStorage "{{user.db_instance_storage}}" \
  --NetworkType "VPC" \
  --VPCId "{{user.vpc_id}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --ReplicationFactor "{{user.replication_factor|3}}"
```

### Fallback Path: JIT Go SDK

Use when CLI lacks operation or complex programmatic control needed. See `references/api-sdk-usage.md` for complete SDK patterns.

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## Critical Rules

### Pre-flight Checks

| Check | Method | On Failure |
|-------|--------|------------|
| Credentials | Env vars non-empty | HALT; user configures |
| Region | `DescribeRegions` | Suggest valid region |
| VPC/VSwitch | `alicloud-vpc-ops` | Delegate to VPC skill |
| Quota | `DescribeAvailableResource` | HALT; user raises quota |

### Safety Gates (Require User Confirmation)

- **DeleteDBInstance** — irreversible deletion
- **DeleteDatabase** — data loss
- **DeleteAccount** — access removal
- **RestoreDBInstance** — data overwrite
- **RestartDBInstance** — brief downtime
- **ModifyDBInstanceSpec** — potential interruption

### Cost Awareness (FinOps)

> For comprehensive cost analysis and optimization, delegate to `alicloud-billing-ops` or `finops-analysis-aliyun`.

**Billing Model Quick Reference:**

| Model | Best For | Cost Characteristic |
|-------|----------|---------------------|
| **Subscription** (包年包月) | Long-running production | Lower unit cost; upfront commitment |
| **Pay-As-You-Go** (按量付费) | Dev/test, short-term | Higher unit cost; no commitment |

**Cost-Impacting Parameters on Create/Modify:**

| Parameter | Cost Impact | Recommendation |
|-----------|-------------|----------------|
| `DBInstanceClass` | Primary driver | Start small, scale based on metrics |
| `DBInstanceStorage` | Linear with size | Use ESSD PL1 for most workloads |
| `ReplicationFactor` | Multiplies node cost | 3 for production, 1 for dev/test |
| `NetworkType` | Cross-region traffic billed | Keep app and DB in same region/VPC |

**Pre-creation Cost Check:**
```bash
# Query price before creating (reference only — actual billing varies)
aliyun dds DescribePrice \
  --RegionId "{{user.region}}" \
  --DBInstanceClass "{{user.db_instance_class}}" \
  --DBInstanceStorage "{{user.db_instance_storage}}" \
  --PayType "{{user.pay_type|PrePaid}}"
```

**Resource Efficiency Check:**
```bash
# Identify underutilized instances for potential downsizing
aliyun dds DescribeDBInstances \
  --RegionId "{{user.region}}" \
  --output cols=DBInstanceId,DBInstanceClass,DBInstanceStatus,CreationTime \
  rows=DBInstances.DBInstance[]

# For detailed utilization analysis (CPU < 5% for 7 days), delegate to:
# - `finops-analysis-aliyun` for cross-resource cost optimization
# - `alicloud-billing-ops` for billing and usage breakdown
```

## Escalation Rules

### HALT Conditions (No Retry)

| Error Code | Action |
|------------|--------|
| `InvalidParameter` / 400 | Fix args from OpenAPI spec |
| `QuotaExceeded` | HALT; user raises quota |
| `InsufficientBalance` | HALT; user resolves billing |
| `DBInstanceAlreadyExists` | Ask reuse vs new name |
| `DBInstanceNotFound` | HALT; verify instance ID |

### Retry Conditions

| Error Pattern | Max Retries | Backoff | Action |
|---------------|-------------|---------|--------|
| Throttling / 429 | 3 | exponential | Respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |
| Network timeout | 3 | exponential | Retry with backoff |

### Ask User Before Proceeding

- Multiple instances match query — ask which to target
- Operation affects production instance — ask confirmation
- Insufficient permissions — ask user to verify RAM policy
- Unknown error with no recovery path — escalate with RequestId

## References

Detailed documentation for specialized operations:

| Document | Purpose |
|----------|---------|
| [sharding-ops.md](references/sharding-ops.md) | Sharded cluster architecture, shard management, balancing |
| [replicaset-ops.md](references/replicaset-ops.md) | Replica set operations, failover, election monitoring |
| [index-strategy.md](references/index-strategy.md) | Index design, optimization, slow query analysis |
| [troubleshooting.md](references/troubleshooting.md) | Error codes, diagnostic playbooks, root cause analysis |
| [monitoring.md](references/monitoring.md) | CloudWatch metrics, alert thresholds, dashboard setup |
| [api-sdk-usage.md](references/api-sdk-usage.md) | Complete API operation mapping, SDK request/response patterns |
| **See:** `../alicloud-skill-generator/templates/batch-operations.md` | Instance, collection, index batch queries |
| **See:** `../alicloud-skill-generator/templates/api-call-counter.md` | API call counting for rate limiting |

## Capabilities at a Glance

| Operation | Description | Risk Level |
|-----------|-------------|------------|
| Create | New instance (standalone/replica/sharded) | Low |
| Describe | View instance details | None |
| Modify | Change configuration | Medium |
| Delete | Remove instance | **High** — irreversible |
| Restart | Restart instance | Medium |
| Scale | Storage or spec scaling | Medium |
| Backup | Create snapshot | Low |
| Restore | Restore from backup | **High** — data overwrite |



## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `dual-path`，CLI/SDK 已覆盖，无需 code snippets.
