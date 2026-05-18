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

```go
config := &openapi.Config{
    AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
    AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
    RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
}
c, err := dds.NewClient(config)
// See api-sdk-usage.md for full request/response handling
```

## Critical Rules

### Credential Security (MANDATORY)

**NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field value (including `ALIBABA_CLOUD_ACCESS_KEY_ID`). If credential information must be displayed for debugging or troubleshooting purposes, use the masking format: show only the first 4 characters followed by `****` (e.g., `abcd****`). This masking rule applies to ALL output channels: stdout, stderr, log files, debug traces, error messages, and diagnostic reports.

| Execution Path | Safe Pattern | Unsafe Pattern |
|----------------|-------------|----------------|
| Console output | `Secret=abcd****` | Raw credential value |
| Error messages | `credential omitted` | Error containing credential |
| Verification | `test -n "$var"` (existence check) | `echo $SECRET` |

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

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2026-05-19 | Security & FinOps enhancements: credential safety (chmod 600), network security checklist, cost awareness (billing models, backup costs), password policy & least privilege, audit log guidance, cross-skill delegation examples |
| 1.0.0 | 2026-05-18 | Initial MongoDB/ApsaraDB skill with dual-path (CLI + SDK) support |