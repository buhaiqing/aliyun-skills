---
name: alicloud-rds-ops
description: >-
  Use this skill to manage Alibaba Cloud RDS instances
  (MySQL/PostgreSQL/SQL Server/MariaDB) — create, modify, describe, delete,
  restart, or monitor them, along with accounts, databases, backups, restores,
  parameter groups, binlog files, read replicas, and security whitelists.
  Diagnose slow queries, analyze performance metrics
  (CPU/memory/IOPS/connections/TPS/QPS), check disk and resource usage, and
  inspect HA or network configuration, or run SQL / execute a `.sql` script file
  against a MySQL instance (via `mysql` client or RDS Data API — see
  references/advanced/sql-execution.md; `aliyun rds` alone cannot run SQL files). Also
  reach for this skill when the user reports a slow or unreachable database,
  wants to upgrade an instance, migrate from self-hosted to RDS, plan a backup
  strategy, or automate any RDS operation — even if they just say "my Alibaba
  database" without naming RDS explicitly. Match against keywords: RDS, 云数据库,
  关系型数据库, 数据库, 实例, 备份, 慢查询, 白名单, 监控, 参数, 只读, binlog,
  performance, connection, migration, failover, upgrade, SQL, 执行SQL, sql文件,
  导入脚本, schema, migration script. Do NOT use for PolarDB, Redis/Tair,
  MongoDB, or billing/accounting/RAM-only tasks.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "2.1.0"
  last_updated: "2026-06-04"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "RDS 2014-08-15 / https://www.alibabacloud.com/help/en/rds"
  cli_applicability: dual-path
  cli_support_evidence: "Confirmed via `aliyun help rds` — RDS is fully supported by the official aliyun CLI."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud RDS Operations Skill

## Common JSON Paths (Centralized)

```
# Create DB Instance:         $.DBInstanceId
# Describe DB Instances:      $.Items.DBInstance[].{DBInstanceId,DBInstanceStatus,Engine,EngineVersion,RegionId,ZoneId}
# Describe Accounts:          $.Accounts.DBInstanceAccount[].AccountName
# Describe Databases:         $.Databases.Database[].DBName
# Describe Backups:           $.Items.Backup[].BackupId
# Describe ResourceUsage:     $.{DiskUsed,LogSize,DataSize}
# Create Backup:              $.BackupJobId
# Create Database:            $.DBName
# Create/Restore/Delete/etc:  $.RequestId
```

## Overview

Alibaba Cloud RDS (Relational Database Service) provides managed relational databases
including MySQL, PostgreSQL, SQL Server, and MariaDB. This skill is an **operational
runbook** for agents: explicit scope, credential rules, pre-flight checks,
**dual-path execution** (official **SDK/API** and **CLI** flows), response validation,
and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` fully supports RDS. Each
  execution flow documents **both** the SDK step and the `aliyun` step for every
  operation.

### Quick Start

不知道从哪里开始？按需选一个：

- **"怎么把 SQL 文件跑进 RDS"** → [SQL Execution Runbook](references/advanced/sql-execution.md)（含 `mysql` 客户端和 RDS Data API 两种路径）
- **"我需要 1 条自然语言提示词"** → [Prompts Handbook](references/prompts.md)（34 条分类示例）
- **"实例有异常，帮我巡检一下"** → [RDS Cruise 巡检工作流](references/cruise.md) + [Alert Diagnosis](references/alert-diagnosis.md)
- **"我想看核心概念/术语"** → [Core Concepts](references/core-concepts.md)
- **"出错码对应什么"** → [Troubleshooting Guide](references/troubleshooting.md)
- **"我要写自定义 Go SDK 脚本"** → [API & SDK Usage](references/api-sdk-usage.md)

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud RDS" OR "云数据库" OR "关系型数据库" OR "RDS实例"
- User mentions "MySQL" OR "PostgreSQL" OR "SQL Server" OR "MariaDB" in the
  context of Alibaba Cloud managed databases
- Task involves CRUD or lifecycle operations on **RDS DB instances** (create,
  describe, modify, delete, list, restart, upgrade)
- Task involves **database accounts** (create, describe, delete, grant privileges)
- Task involves **databases** (create, describe, delete)
- Task involves **backups** (create, describe, restore, delete)
- Task involves **performance monitoring** (CPU, memory, IOPS, connections, TPS/QPS)
- Task involves **slow query logs** (describe, analyze)
- Task involves **executing SQL** or running a **`.sql` file** on RDS MySQL (use
  `mysql` client or `aliyun rds-data` — see [SQL Execution](references/advanced/sql-execution.md);
  **not** `aliyun rds` alone)
- Task involves **parameter groups** (describe, modify)
- Task involves **security groups / whitelists** (describe, modify)
- Task keywords: 数据库, 实例, 备份, 慢查询, 参数, 白名单, 监控, SQL, sql文件,
  执行SQL, 导入脚本, database, instance, backup, slow log, parameter, whitelist,
  monitor, execute sql, sql file, schema
- User asks to deploy, configure, troubleshoot, or monitor RDS **via API, SDK,
  CLI, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops`
  (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when present)
- Task is about **PolarDB MySQL** → delegate to: `alicloud-polar-mysql-ops`
- Task is about **PolarDB PostgreSQL** → delegate to: `alicloud-polar-pg-ops`
- Task is about **PolarDB Oracle-compatible** → delegate to: `alicloud-polar-oracle-ops`
- Task is about **Redis / NoSQL** → delegate to: `alicloud-redis-ops` (when present)
- Task is about **MongoDB** → delegate to: `alicloud-mongodb-ops` (when present)
- User insists on **console-only** flows with no API → state limitation; do not
  invent undocumented HTTP steps

### Delegation Rules

- If creating an RDS instance in a VPC, verify VPC and VSwitch exist (via
  `alicloud-vpc-ops`) before RDS creation.
- If restoring from backup, verify the backup exists via DescribeBackups before
  initiating RestoreDBInstance.
- Multi-product requests: handle each product with its skill; do not merge
  unrelated APIs into one ambiguous flow.

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.db_instance_id}}` | User-supplied RDS DBInstanceId | Ask once; reuse |
| `{{user.db_instance_name}}` | User-supplied RDS instance name | Ask once; reuse |
| `{{user.engine}}` | Database engine (MySQL, PostgreSQL, SQLServer, MariaDB) | Ask once; reuse |
| `{{user.engine_version}}` | Engine version (e.g., 8.0, 13.0) | Ask once; reuse |
| `{{user.account_name}}` | Database account name | Ask once; reuse |
| `{{user.db_name}}` | Database name | Ask once; reuse |
| `{{user.backup_id}}` | Backup ID | Ask once; reuse |
| `{{output.db_instance_id}}` | From last API or CLI JSON response | Parse per OpenAPI or verified CLI path |
| `{{output.request_id}}` | From API response | For support / correlation |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** Document client request tokens, duplicate names, and
  `DBInstanceAlreadyExists` behavior per API.
- **ClientToken:** For write operations (CreateDBInstance, CreateAccount, etc.),
  generate a unique `ClientToken` (UUID v4) per logical request. If the same
  operation is retried due to network timeout, reuse the same `ClientToken` to
  ensure idempotency. The API returns the same result for duplicate requests
  with the same `ClientToken` within 24 hours.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateDBInstance | `$.DBInstanceId` | string | New DB instance ID |
| DescribeDBInstances | `$.Items.DBInstance[].DBInstanceId` | array | Instance IDs |
| DescribeDBInstances | `$.Items.DBInstance[].DBInstanceStatus` | string | Instance status |
| DescribeDBInstances | `$.Items.DBInstance[].Engine` | string | Engine type |
| DescribeDBInstances | `$.Items.DBInstance[].EngineVersion` | string | Engine version |
| DescribeDBInstances | `$.Items.DBInstance[].DBInstanceClass` | string | Instance class |
| DescribeDBInstances | `$.Items.DBInstance[].RegionId` | string | Region ID |
| DescribeDBInstances | `$.Items.DBInstance[].ZoneId` | string | Zone ID |
| DescribeDBInstances | `$.Items.DBInstance[].CreationTime` | string | ISO 8601 timestamp |
| DescribeDBInstances | `$.Items.DBInstance[].ExpireTime` | string | ISO 8601 expiration |
| DescribeDBInstances | `$.Items.DBInstance[].DBInstanceStorage` | string | Storage size (GB) |
| RestartDBInstance | `$.RequestId` | string | Request ID |
| DeleteDBInstance | `$.RequestId` | string | Request ID |
| DescribeAccounts | `$.Accounts.DBInstanceAccount[].AccountName` | array | Account names |
| DescribeDatabases | `$.Databases.Database[].DBName` | array | Database names |
| DescribeBackups | `$.Items.Backup[].BackupId` | array | Backup IDs |
| DescribeSlowLogs | `$.Items.SQLSlowLog[].SQLText` | array | Slow query SQL text |
| DescribeResourceUsage | `$.DiskUsed` | int | Disk used (MB) |
| DescribeResourceUsage | `$.LogSize` | int | Log size (MB) |
| DescribeResourceUsage | `$.DataSize` | int | Data size (MB) |
| DescribeDBInstancePerformance | `$.PerformanceKeys.PerformanceKey[].Key` | array | Metric keys |
| DescribeDBInstancePerformance | `$.PerformanceKeys.PerformanceKey[].ValueFormat` | string | Value format |
| DescribeDBInstanceHAConfig | `$.SyncMode` | string | Sync mode (Sync/Async) |
| DescribeDBInstanceHAConfig | `$.HAMode` | string | HA mode (RPO/RTO) |
| DescribeDBInstanceHAConfig | `$.HostInstanceInfos.NodeInfo[].NodeType` | array | Master/Slave node types |
| CreateDatabase | `$.DBName` | string | Created database name |
| DeleteDatabase | `$.RequestId` | string | Request ID |
| DeleteAccount | `$.RequestId` | string | Request ID |
| CreateBackup | `$.BackupJobId` | string | Backup job ID |
| RestoreDBInstance | `$.DBInstanceId` | string | Restored instance ID |
| DescribeReadDBInstances | `$.Items.ReadOnlyDBInstance[].DBInstanceId` | array | Read-only instance IDs |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateDBInstance | — | `Running` | 10s | 600s |
| RestartDBInstance | `Running` | `Running` | 10s | 300s |
| DeleteDBInstance | any stable state | absent | 10s | 300s |
| CreateAccount | — | `Available` | 5s | 120s |
| CreateDatabase | — | `Running` | 5s | 120s |
| RestoreDBInstance | — | `Running` | 10s | 600s |
| CreateBackup | — | `Success` | 10s | 600s |

### Polling Strategy

RDS 大多数写入操作（创建实例/账号/库、备份、恢复、规格变更等）是 **异步** 的：API
立即返回 `RequestId` 或资源 ID，但资源状态需要时间才能达到终态。所有 Operation 统一遵循
以下轮询模式（CLI 原生 waiter 尚未覆盖 RDS 全部场景，故采用通用 shell 轮询）：

```bash
# 通用轮询模板 — 适用于任意 Operation
for i in $(seq 1 60); do            # 60 次 × 10s = 600s（按 Operation 调整次数/间隔）
  STATUS=$(aliyun rds <DescribeXxx> \
    --DBInstanceId "{{user.db_instance_id}}" \
    --output cols=<StatusField> rows=<JsonPath>)
  [ "$STATUS" = "<TargetState>" ] && break
  sleep <PollInterval>
done
[ "$STATUS" = "<TargetState>" ] || { echo "TIMEOUT"; exit 1; }
```

| 轮询参数 | 含义 | 适用场景 |
|---------|------|---------|
| **Poll Interval** | 两次查询间隔 | 重操作 10s（实例/恢复），轻操作 5s（账号/库） |
| **Max Wait** | 最长等待时间 | 写入完成 = 600s，恢复 = 600s，删 = 300s，账号/库 = 120s |
| **Target State** | 终态判定值 | `Running` / `Available` / `Success` / absent（`TotalRecordCount=0`） |

> **未达到 Target State 但接近 Max Wait** → 进入 [Failure Recovery](#failure-recovery)
> 流程，记录 `RequestId` 提交工单。
>
> **JIT Go SDK 端**用 `DescribeXxx` 同步轮询即可，模式相同。

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (SDK/API and `aliyun`) → Validate → Recover**.

---

### Operation: Create DB Instance

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SDK / deps | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys | HALT; user configures env |
| Region | `aliyun rds DescribeRegions` | `{{user.region}}` supported | Suggest valid region |
| Engine / Version | `aliyun rds DescribeAvailableClasses` | `{{user.engine}}` `{{user.engine_version}}` supported | Suggest valid combo |
| VPC/VSwitch | `aliyun vpc DescribeVpcs` / `DescribeVSwitches` | VPC and VSwitch exist | Delegate to `alicloud-vpc-ops` |
| Quota | `aliyun rds DescribeAvailableResource` | Sufficient quota | HALT; user raises quota |

#### Execution — CLI (Primary Path)

```bash
aliyun rds CreateDBInstance \
  --RegionId "{{user.region}}" \
  --Engine "{{user.engine}}" \
  --EngineVersion "{{user.engine_version}}" \
  --DBInstanceClass "{{user.db_instance_class}}" \
  --DBInstanceStorage "{{user.db_instance_storage}}" \
  --DBInstanceNetType "{{user.net_type|Intranet}}" \
  --VPCId "{{user.vpc_id}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --SecurityIPList "{{user.security_ip_list|10.0.0.0/8}}" \
  --PayType "{{user.pay_type|Postpaid}}"
```

> **Note:** Output is JSON by default. Parse `DBInstanceId` from response.

#### Execution — JIT Go SDK (Fallback Path)

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

1. Read `{{output.db_instance_id}}` from `$.DBInstanceId`.
2. Poll **DescribeDBInstances** until `DBInstanceStatus` is `Running`:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun rds DescribeDBInstances \
    --RegionId "{{user.region}}" \
    --DBInstanceId "{{output.db_instance_id}}" \
    --output cols=DBInstanceStatus rows=Items.DBInstance[0].DBInstanceStatus)
  [ "$STATUS" = "Running" ] && break
  sleep 10
done
```

3. On success, report `{{output.db_instance_id}}`, connection string, and key fields.
4. On terminal failure, go to **Failure Recovery**.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` / 400 | 0–1 | — | Fix args from OpenAPI; retry once if safe |
| `QuotaExceeded` / `DBInstanceQuotaExceeded` | 0 | — | HALT |
| `InsufficientBalance` | 0 | — | HALT |
| `DBInstanceAlreadyExists` | 0 | — | Ask reuse vs new name |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Describe DB Instances

#### Execution — CLI

```bash
# Describe all instances in region
aliyun rds DescribeDBInstances --RegionId "{{user.region}}"

# Describe specific instance
aliyun rds DescribeDBInstances \
  --RegionId "{{user.region}}" \
  --DBInstanceId "{{user.db_instance_id}}"

# Extract specific fields with JMESPath
aliyun rds DescribeDBInstances --RegionId "{{user.region}}" \
  --output cols=DBInstanceId,DBInstanceStatus,Engine,DBInstanceClass rows=Items.DBInstance[].{DBInstanceId,DBInstanceStatus,Engine,DBInstanceClass}
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| DB Instance ID | `$.Items.DBInstance[].DBInstanceId` | Plain text |
| Name | `$.Items.DBInstance[].DBInstanceDescription` | Plain text |
| Status | `$.Items.DBInstance[].DBInstanceStatus` | Running, Creating, Deleting, Rebooting, etc. |
| Engine | `$.Items.DBInstance[].Engine` | MySQL, PostgreSQL, SQLServer, MariaDB |
| Version | `$.Items.DBInstance[].EngineVersion` | e.g., 8.0, 13.0 |
| Instance Class | `$.Items.DBInstance[].DBInstanceClass` | e.g., rds.mysql.s1.large |
| Storage | `$.Items.DBInstance[].DBInstanceStorage` | GB |
| Region | `$.Items.DBInstance[].RegionId` | Plain text |
| Zone | `$.Items.DBInstance[].ZoneId` | Plain text |
| Network Type | `$.Items.DBInstance[].DBInstanceNetType` | Internet / Intranet |
| VPC ID | `$.Items.DBInstance[].VPCId` | Plain text |
| VSwitch ID | `$.Items.DBInstance[].VSwitchId` | Plain text |
| Security IPs | `$.Items.DBInstance[].SecurityIPList` | Comma-separated |
| Creation Time | `$.Items.DBInstance[].CreationTime` | ISO 8601 |
| Expire Time | `$.Items.DBInstance[].ExpireTime` | ISO 8601 |
| Pay Type | `$.Items.DBInstance[].PayType` | Postpaid / Prepaid |

---

### Operation: Restart DB Instance

#### Pre-flight

- Verify instance exists and status is `Running`.
- **MUST** obtain explicit confirmation: restart causes brief downtime.

#### Execution — CLI

```bash
aliyun rds RestartDBInstance --DBInstanceId "{{user.db_instance_id}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until `DBInstanceStatus` returns to `Running`:

```bash
for i in $(seq 1 30); do
  STATUS=$(aliyun rds DescribeDBInstances \
    --RegionId "{{user.region}}" \
    --DBInstanceId "{{user.db_instance_id}}" \
    --output cols=DBInstanceStatus rows=Items.DBInstance[0].DBInstanceStatus)
  [ "$STATUS" = "Running" ] && break
  sleep 10
done
```

---

### Operation: Delete DB Instance

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of instance
  `{{user.db_instance_id}}` (`{{user.db_instance_name}}`).
- **MUST NOT** proceed without clear user assent.
- Verify instance is in `Running` status. If not, warn user.
- **Recommendation:** Create final backup before deletion (optional, user decides).

#### Execution — CLI

```bash
aliyun rds DeleteDBInstance --DBInstanceId "{{user.db_instance_id}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll **DescribeDBInstances** until instance is absent (returns empty list or
`DBInstanceNotFound`) within **300s**.

```bash
for i in $(seq 1 30); do
  RESULT=$(aliyun rds DescribeDBInstances \
    --RegionId "{{user.region}}" \
    --DBInstanceId "{{user.db_instance_id}}" \
    --output cols=TotalRecordCount rows=TotalRecordCount)
  [ "$RESULT" = "0" ] && break
  sleep 10
done
```

---

### Operation: Describe Accounts

#### Execution — CLI

```bash
aliyun rds DescribeAccounts \
  --DBInstanceId "{{user.db_instance_id}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Account Name | `$.Accounts.DBInstanceAccount[].AccountName` | Plain text |
| Account Status | `$.Accounts.DBInstanceAccount[].AccountStatus` | Available, Unavailable |
| Account Type | `$.Accounts.DBInstanceAccount[].AccountType` | Normal, Super |
| DB Privileges | `$.Accounts.DBInstanceAccount[].DatabasePrivilege[].DBName` | Associated databases |

---

### Operation: Create Account

#### Pre-flight

- Verify instance exists and status is `Running`.
- Verify account name does not already exist (call DescribeAccounts first).

#### Execution — CLI

```bash
aliyun rds CreateAccount \
  --DBInstanceId "{{user.db_instance_id}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPassword "{{user.account_password}}" \
  --AccountType "{{user.account_type|Normal}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until account status is `Available`:

```bash
for i in $(seq 1 24); do
  STATUS=$(aliyun rds DescribeAccounts \
    --DBInstanceId "{{user.db_instance_id}}" \
    --AccountName "{{user.account_name}}" \
    --output cols=AccountStatus rows=Accounts.DBInstanceAccount[0].AccountStatus)
  [ "$STATUS" = "Available" ] && break
  sleep 5
done
```

---

### Operation: Delete Account

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation before deleting account.
- Warn user that deleted accounts cannot be recovered.
- Verify account exists (call DescribeAccounts first).

#### Execution — CLI

```bash
aliyun rds DeleteAccount \
  --DBInstanceId "{{user.db_instance_id}}" \
  --AccountName "{{user.account_name}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Verify account no longer appears in DescribeAccounts:

```bash
for i in $(seq 1 12); do
  RESULT=$(aliyun rds DescribeAccounts \
    --DBInstanceId "{{user.db_instance_id}}" \
    --AccountName "{{user.account_name}}" \
    --output cols=TotalRecordCount rows=TotalRecordCount)
  [ "$RESULT" = "0" ] && break
  sleep 5
done
```

> Note: `TotalRecordCount` is at the root level of the response.

---

### Operation: Create Database

#### Pre-flight

- Verify instance exists and status is `Running`.
- Verify database name does not already exist (call DescribeDatabases first).

#### Execution — CLI

```bash
aliyun rds CreateDatabase \
  --DBInstanceId "{{user.db_instance_id}}" \
  --DBName "{{user.db_name}}" \
  --CharacterSetName "{{user.character_set_name|utf8mb4}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until database status is `Running`:

```bash
for i in $(seq 1 24); do
  STATUS=$(aliyun rds DescribeDatabases \
    --DBInstanceId "{{user.db_instance_id}}" \
    --DBName "{{user.db_name}}" \
    --output cols=DBStatus rows=Databases.Database[0].DBStatus)
  [ "$STATUS" = "Running" ] && break
  sleep 5
done
```

---

### Operation: Delete Database

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of database `{{user.db_name}}`.
- **MUST NOT** proceed without clear user assent.
- Verify database exists (call DescribeDatabases first).

#### Execution — CLI

```bash
aliyun rds DeleteDatabase \
  --DBInstanceId "{{user.db_instance_id}}" \
  --DBName "{{user.db_name}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Verify database no longer appears in DescribeDatabases:

```bash
for i in $(seq 1 12); do
  RESULT=$(aliyun rds DescribeDatabases \
    --DBInstanceId "{{user.db_instance_id}}" \
    --DBName "{{user.db_name}}" \
    --output cols=TotalRecordCount rows=TotalRecordCount)
  [ "$RESULT" = "0" ] && break
  sleep 5
done
```

> Note: `TotalRecordCount` is at the root level of the response.

---

### Operation: Describe Databases

#### Execution — CLI

```bash
aliyun rds DescribeDatabases \
  --DBInstanceId "{{user.db_instance_id}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| DB Name | `$.Databases.Database[].DBName` | Plain text |
| DB Status | `$.Databases.Database[].DBStatus` | Creating, Running, Deleting |
| Engine | `$.Databases.Database[].Engine` | Engine type |
| Character Set | `$.Databases.Database[].CharacterSetName` | e.g., utf8mb4 |

---

### Operation: Create Backup

#### Pre-flight

- Verify instance exists and status is `Running`.
- Warn user that backup creation may take several minutes.

#### Execution — CLI

```bash
aliyun rds CreateBackup \
  --DBInstanceId "{{user.db_instance_id}}" \
  --BackupMethod "{{user.backup_method|Physical}}" \
  --BackupType "{{user.backup_type|FullBackup}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll **DescribeBackups** until backup status is `Success`:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun rds DescribeBackups \
    --DBInstanceId "{{user.db_instance_id}}" \
    --StartTime "{{user.start_time}}" \
    --EndTime "{{user.end_time}}" \
    --output cols=BackupStatus rows=Items.Backup[0].BackupStatus)
  [ "$STATUS" = "Success" ] && break
  sleep 10
done
```

---

### Operation: Restore DB Instance

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation before restoring instance.
- Warn user that restore will overwrite current data.
- Verify backup exists and status is `Success` (call DescribeBackups first).
- Check if instance is in `Running` status.

#### Execution — CLI

```bash
aliyun rds RestoreDBInstance \
  --DBInstanceId "{{user.db_instance_id}}" \
  --BackupId "{{user.backup_id}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until `DBInstanceStatus` returns to `Running`:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun rds DescribeDBInstances \
    --RegionId "{{user.region}}" \
    --DBInstanceId "{{user.db_instance_id}}" \
    --output cols=DBInstanceStatus rows=Items.DBInstance[0].DBInstanceStatus)
  [ "$STATUS" = "Running" ] && break
  sleep 10
done
```

---

### Operation: Describe Backups

#### Execution — CLI

```bash
# List backups for an instance
aliyun rds DescribeBackups \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"

# Extract backup IDs and status
aliyun rds DescribeBackups \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --output cols=BackupId,BackupStatus,BackupSize rows=Items.Backup[].{BackupId,BackupStatus,BackupSize}
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Backup ID | `$.Items.Backup[].BackupId` | Plain text |
| Backup Status | `$.Items.Backup[].BackupStatus` | Success, Failed |
| Backup Type | `$.Items.Backup[].BackupType` | FullBackup, IncrementalBackup |
| Backup Size | `$.Items.Backup[].BackupSize` | Bytes |
| Backup Start Time | `$.Items.Backup[].BackupStartTime` | ISO 8601 |
| Backup End Time | `$.Items.Backup[].BackupEndTime` | ISO 8601 |
| Backup Mode | `$.Items.Backup[].BackupMode` | Automated, Manual |

---

### Operation: Describe Slow Logs

#### Execution — CLI

```bash
aliyun rds DescribeSlowLogs \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --DBName "{{user.db_name}}"

# Extract top slow queries
aliyun rds DescribeSlowLogs \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --output cols=SQLText,MySQLTotalExecutionCounts,MySQLTotalExecutionTimes rows=Items.SQLSlowLog[].{SQLText,MySQLTotalExecutionCounts,MySQLTotalExecutionTimes}
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| SQL Text | `$.Items.SQLSlowLog[].SQLText` | Query text (truncated) |
| Execution Count | `$.Items.SQLSlowLog[].MySQLTotalExecutionCounts` | Total executions |
| Execution Time | `$.Items.SQLSlowLog[].MySQLTotalExecutionTimes` | Total execution time (ms) |
| Max Execution Time | `$.Items.SQLSlowLog[].MySQLMaxExecutionTime` | Max single execution (ms) |
| Return Row Count | `$.Items.SQLSlowLog[].ReturnTotalRowCounts` | Total rows returned |
| Parse Row Count | `$.Items.SQLSlowLog[].ParseTotalRowCounts` | Total rows parsed |
| DB Name | `$.Items.SQLSlowLog[].DBName` | Database name |

---

### Operation: Describe Resource Usage

#### Execution — CLI

```bash
aliyun rds DescribeResourceUsage \
  --DBInstanceId "{{user.db_instance_id}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Disk Used | `$.DiskUsed` | MB |
| Data Size | `$.DataSize` | MB |
| Log Size | `$.LogSize` | MB |
| Backup Size | `$.BackupSize` | MB |

---

### Operation: Describe DB Instance Performance

#### Execution — CLI

```bash
aliyun rds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.db_instance_id}}" \
  --Key "{{user.metric_key}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"

# Common metric keys: MySQL_Sessions, MySQL_ActiveSessions, MySQL_TPS,
# MySQL_IOPS, MySQL_CPUUsage, MySQL_MemoryUsage
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Metric Key | `$.PerformanceKeys.PerformanceKey[].Key` | Metric identifier |
| Value Format | `$.PerformanceKeys.PerformanceKey[].ValueFormat` | Value format description |
| Values | `$.PerformanceKeys.PerformanceKey[].Values.PerformanceValue[]` | Time-series data points |

---

### Operation: Describe DB Instance HA Config

#### Execution — CLI

```bash
aliyun rds DescribeDBInstanceHAConfig \
  --DBInstanceId "{{user.db_instance_id}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Sync Mode | `$.SyncMode` | Sync / Async |
| HA Mode | `$.HAMode` | RPO / RTO |
| Master Instance ID | `$.HostInstanceInfos.NodeInfo[].NodeId` (NodeType=Master) | Master node ID |
| Slave Instance ID | `$.HostInstanceInfos.NodeInfo[].NodeId` (NodeType=Slave) | Slave node ID(s) |

---

### Operation: Modify Security IPs

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation before modifying whitelist.
- Warn user that incorrect IPs may block access.

#### Execution — CLI

```bash
aliyun rds ModifySecurityIps \
  --DBInstanceId "{{user.db_instance_id}}" \
  --SecurityIps "{{user.security_ips}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Verify via DescribeDBInstanceIPArrayList:

```bash
aliyun rds DescribeDBInstanceIPArrayList \
  --DBInstanceId "{{user.db_instance_id}}"
```

---

### Operation: Describe Parameters

#### Execution — CLI

```bash
aliyun rds DescribeParameters \
  --DBInstanceId "{{user.db_instance_id}}"

# Extract specific parameter
aliyun rds DescribeParameters \
  --DBInstanceId "{{user.db_instance_id}}" \
  --output cols=ParameterName,ParameterValue,ParameterDescription rows=RunningParameters.DBInstanceParameter[].{ParameterName,ParameterValue,ParameterDescription}
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Parameter Name | `$.RunningParameters.DBInstanceParameter[].ParameterName` | Plain text |
| Parameter Value | `$.RunningParameters.DBInstanceParameter[].ParameterValue` | Current value |
| Default Value | `$.RunningParameters.DBInstanceParameter[].DefaultParameterValue` | Default value |
| Modifiable | `$.RunningParameters.DBInstanceParameter[].IsModifiable` | true / false |
| Description | `$.RunningParameters.DBInstanceParameter[].ParameterDescription` | Plain text |

---

### Operation: Modify Parameter

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation before modifying parameters.
- Warn user that incorrect parameters may affect stability or performance.
- Verify parameter is modifiable (`IsModifiable` is true).
- Check if restart is required for the parameter change.

#### Execution — CLI

```bash
aliyun rds ModifyParameter \
  --DBInstanceId "{{user.db_instance_id}}" \
  --Parameters "{\"{{user.parameter_name}}\":\"{{user.parameter_value}}\"}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

1. Poll **DescribeParameters** to verify the new value is applied.
2. If restart is required, prompt user for confirmation before restarting.

---

### Operation: Describe DB Instance Attribute

#### Execution — CLI

```bash
aliyun rds DescribeDBInstanceAttribute \
  --DBInstanceId "{{user.db_instance_id}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| DB Instance ID | `$.Items.DBInstanceAttribute[].DBInstanceId` | Plain text |
| Status | `$.Items.DBInstanceAttribute[].DBInstanceStatus` | Lifecycle state |
| Engine | `$.Items.DBInstanceAttribute[].Engine` | Engine type |
| Version | `$.Items.DBInstanceAttribute[].EngineVersion` | Engine version |
| Class | `$.Items.DBInstanceAttribute[].DBInstanceClass` | Instance class |
| Storage | `$.Items.DBInstanceAttribute[].DBInstanceStorage` | GB |
| Max Connections | `$.Items.DBInstanceAttribute[].MaxConnections` | Max allowed connections |
| Max IOPS | `$.Items.DBInstanceAttribute[].MaxIOPS` | Max IOPS |
| Connection Mode | `$.Items.DBInstanceAttribute[].ConnectionMode` | Standard / Safe |
| Connection String | `$.Items.DBInstanceAttribute[].ConnectionString` | Primary endpoint |
| Port | `$.Items.DBInstanceAttribute[].Port` | Database port |
| VPC ID | `$.Items.DBInstanceAttribute[].VPCId` | Plain text |
| VSwitch ID | `$.Items.DBInstanceAttribute[].VSwitchId` | Plain text |
| Security IPs | `$.Items.DBInstanceAttribute[].SecurityIPList` | Comma-separated |
| Creation Time | `$.Items.DBInstanceAttribute[].CreationTime` | ISO 8601 |
| Expire Time | `$.Items.DBInstanceAttribute[].ExpireTime` | ISO 8601 |
| Lock Mode | `$.Items.DBInstanceAttribute[].LockMode` | Lock state (0=normal) |
| Lock Reason | `$.Items.DBInstanceAttribute[].LockReason` | Reason if locked |

---

### Operation: Describe DB Instance Net Info

#### Execution — CLI

```bash
aliyun rds DescribeDBInstanceNetInfo \
  --DBInstanceId "{{user.db_instance_id}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Connection String | `$.DBInstanceNetInfos.DBInstanceNetInfo[].ConnectionString` | Endpoint address |
| IP Address | `$.DBInstanceNetInfos.DBInstanceNetInfo[].IPAddress` | IP address |
| Port | `$.DBInstanceNetInfos.DBInstanceNetInfo[].Port` | Port number |
| Network Type | `$.DBInstanceNetInfos.DBInstanceNetInfo[].IPType` | Inner / Public |
| VPC ID | `$.DBInstanceNetInfos.DBInstanceNetInfo[].VPCId` | Plain text |
| VSwitch ID | `$.DBInstanceNetInfos.DBInstanceNetInfo[].VSwitchId` | Plain text |

---

### Operation: Describe DB Instance IP Array List

#### Execution — CLI

```bash
aliyun rds DescribeDBInstanceIPArrayList \
  --DBInstanceId "{{user.db_instance_id}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Array Name | `$.Items.DBInstanceIPArray[].DBInstanceIPArrayName` | Whitelist group name |
| Security IPs | `$.Items.DBInstanceIPArray[].SecurityIPList` | Comma-separated IPs |
| Array Attribute | `$.Items.DBInstanceIPArray[].DBInstanceIPArrayAttribute` | hidden / empty |

---

### Operation: Describe Binlog Files

#### Execution — CLI

```bash
aliyun rds DescribeBinlogFiles \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| File Name | `$.Items.BinLogFile[].LogFileName` | Binlog file name |
| File Size | `$.Items.BinLogFile[].FileSize` | Bytes |
| Start Time | `$.Items.BinLogFile[].StartTime` | ISO 8601 |
| End Time | `$.Items.BinLogFile[].EndTime` | ISO 8601 |
| Download Link | `$.Items.BinLogFile[].DownloadLink` | Temporary URL |

---

### Operation: Describe Error Logs

#### Execution — CLI

```bash
aliyun rds DescribeErrorLogs \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Error Info | `$.Items.ErrorLog[].ErrorInfo` | Error message |
| Create Time | `$.Items.ErrorLog[].CreateTime` | ISO 8601 |

---

### Operation: Describe SQL Log Records

#### Execution — CLI

```bash
aliyun rds DescribeSQLLogRecords \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| SQL Text | `$.Items.SQLRecord[].SQLText` | Executed SQL |
| Execute Time | `$.Items.SQLRecord[].ExecuteTime` | ISO 8601 |
| Latency | `$.Items.SQLRecord[].Latency` | Execution time (us) |
| Account | `$.Items.SQLRecord[].AccountName` | Executing account |
| DB Name | `$.Items.SQLRecord[].DBName` | Target database |
| Client IP | `$.Items.SQLRecord[].ClientHostIp` | Client IP address |
| Return Rows | `$.Items.SQLRecord[].ReturnRowCounts` | Rows returned |

---

### Operation: Modify DB Instance Spec

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation before modifying instance specification.
- Warn user that specification change may cause brief downtime.
- Verify target instance class and storage are supported for the engine/version.
- Check if instance is in `Running` status.

#### Execution — CLI

```bash
aliyun rds ModifyDBInstanceSpec \
  --DBInstanceId "{{user.db_instance_id}}" \
  --DBInstanceClass "{{user.db_instance_class}}" \
  --DBInstanceStorage "{{user.db_instance_storage}}" \
  --PayType "{{user.pay_type}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until `DBInstanceStatus` returns to `Running`:

```bash
for i in $(seq 1 30); do
  STATUS=$(aliyun rds DescribeDBInstances \
    --RegionId "{{user.region}}" \
    --DBInstanceId "{{user.db_instance_id}}" \
    --output cols=DBInstanceStatus rows=Items.DBInstance[0].DBInstanceStatus)
  [ "$STATUS" = "Running" ] && break
  sleep 10
done
```

---

### Operation: Upgrade DB Instance Engine Version

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation before upgrading engine version.
- Warn user that upgrade is irreversible and may cause downtime.
- Verify target version is supported via `DescribeAvailableClasses`.
- Check if instance is in `Running` status.
- **Recommendation:** Create manual backup before upgrade.

#### Execution — CLI

```bash
aliyun rds UpgradeDBInstanceEngineVersion \
  --DBInstanceId "{{user.db_instance_id}}" \
  --EngineVersion "{{user.engine_version}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until `DBInstanceStatus` returns to `Running` and `EngineVersion` matches target:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun rds DescribeDBInstances \
    --RegionId "{{user.region}}" \
    --DBInstanceId "{{user.db_instance_id}}" \
    --output cols=DBInstanceStatus,EngineVersion rows=Items.DBInstance[0].{DBInstanceStatus,EngineVersion})
  echo "$STATUS" | grep -q "Running" && echo "$STATUS" | grep -q "{{user.engine_version}}" && break
  sleep 10
done
```

---

### Operation: Describe Available Zones

#### Execution — CLI

```bash
aliyun rds DescribeAvailableZones \
  --RegionId "{{user.region}}" \
  --Engine "{{user.engine}}" \
  --EngineVersion "{{user.engine_version}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Zone ID | `$.AvailableZones.AvailableZone[].ZoneId` | Zone identifier |
| Zone Name | `$.AvailableZones.AvailableZone[].ZoneName` | Human-readable name |
| Region ID | `$.AvailableZones.AvailableZone[].RegionId` | Region identifier |

### Operation: Describe Read-only Instances

#### Execution — CLI

```bash
aliyun rds DescribeReadDBInstances \
  --DBInstanceId "{{user.db_instance_id}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| DB Instance ID | `$.Items.ReadOnlyDBInstance[].DBInstanceId` | Read-only instance ID |
| Status | `$.Items.ReadOnlyDBInstance[].DBInstanceStatus` | Lifecycle state |
| Class | `$.Items.ReadOnlyDBInstance[].DBInstanceClass` | Instance class |
| Storage | `$.Items.ReadOnlyDBInstance[].DBInstanceStorage` | GB |
| Connection String | `$.Items.ReadOnlyDBInstance[].ConnectionString` | Read endpoint |
| Port | `$.Items.ReadOnlyDBInstance[].Port` | Database port |

---

## RDS Cruise (巡检工作流)

详见 [RDS Cruise 巡检工作流](references/cruise.md)

## Prerequisites

见 [执行环境配置](../alicloud-skill-generator/references/execution-environment.md)

详见 [SQL Execution](references/advanced/sql-execution.md) 了解 `mysql` 客户端和 RDS Data API 用法。

## Intelligent Diagnosis Workflow (Agent-Readable)

When the user reports an alert or performance issue (e.g., "RDS CPU 告警",
"数据库连接超时", "复制延迟"), the Agent MUST execute the **Smart Alert
Response Workflow** documented in [Alert Diagnosis & Root Cause Analysis](references/alert-diagnosis.md).

### Trigger Keywords for Diagnosis Mode

| User Input Pattern | Diagnosis Type | Entry Point |
|-------------------|----------------|-------------|
| "CPU 告警" / "CPU 高" / "CPU 100%" | CPU Performance | Section 1.1 + 6.1 Playbook |
| "磁盘告警" / "磁盘满" / "空间不足" | Disk Capacity | Section 1.4 + 6.2 Playbook |
| "连接数告警" / "Too many connections" | Connection Exhaustion | Section 1.3 |
| "复制延迟" / "只读实例延迟" / "主从延迟" | Replication Lag | Section 1.6 + 6.3 Playbook |
| "慢查询" / "查询慢" / "SQL 慢" | Query Performance | Section 8.1 |
| "数据库宕机" / "连不上" / "连接超时" | Availability | Section 7 P0-Critical |
| "巡检异常" / "健康检查失败" / "有异常" | General Health | RDS Cruise + Diagnosis |
| "内存告警" / "OOM" / "内存不足" | Memory Pressure | Section 1.2 |
| "IO 高" / "IOPS 告警" / "磁盘 IO 慢" | IO Bottleneck | Section 1.5 |

### Diagnosis Execution Rules

1. **NEVER jump to conclusions** — Agent MUST collect at least 3 data points
   before declaring a root cause.
2. **Always correlate** — Single-metric alerts are rarely the full picture.
   Use the Multi-Dimensional Correlation Matrix (Section 2.1).
3. **Engine-aware** — Apply MySQL / PostgreSQL / SQL Server specific diagnostic
   trees (Section 3) based on `Engine` field.
4. **Pattern-aware** — Identify time-series patterns (Section 4) to distinguish
   between sudden spikes, gradual ramps, and periodic waves.
5. **Severity-aware** — Use the Alert Severity Escalation Matrix (Section 7)
   to determine response urgency and notification level.
6. **Evidence-based** — Every root cause claim MUST be backed by specific
   API response data (JSON path + value).
7. **Actionable** — Recommendations MUST be prioritized and include risk assessment.

### Quick Diagnosis CLI (All-in-One)

详见 [RDS Cruise 巡检工作流](references/cruise.md)

---

## Advanced Analytics

以下深度分析文档仅在用户明确需要时加载，**不要在常规操作中读取**：

| 场景 | 文档 |
|------|------|
| 性能预测、容量规划 | [advanced/aiops-prediction.md](references/advanced/aiops-prediction.md) |
| 成本分析、资源优化 | [advanced/finops-analysis.md](references/advanced/finops-analysis.md) |

### ⚠️ Security-Sensitive Operations

以下操作涉及数据变更，**执行前必须获得用户显式确认**：

| 场景 | 文档 | 风险等级 |
|------|------|---------|
| SQL 文件执行 | [advanced/sql-execution.md](references/advanced/sql-execution.md) | 🔴 高（可执行 DROP/TRUNCATE） |

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to RDS.

### 安全 (Security)

| Assessment Area | Guidance |
|-----------------|----------|
| **IAM** | Never use `AdministratorAccess`. Require: `rds:Describe*`, `rds:Create*` scoped to `acs:rds:*:*:dbinstance/*` |
| **Credentials** | Use `{{env.*}}` only. Never print secrets |
| **Network** | VPC-only deployment. White-list application IPs — never `0.0.0.0/0` |
| **Data at Rest** | Enable TDE for compliance. SSL for in-transit encryption |
| **SQL Security** | Use parameterized queries. Review slow logs for suspicious patterns |

### 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | HighAvailability edition with primary+standby. Cross-AZ. Auto-failover < 30s |
| **面向精细的运维管控** | Daily backup + binlog incremental. Monitor CPU/Memory/IOPS/Disk at 80% |
| **面向风险的应急快恢** | Point-in-time restore via `RestoreDBInstance`. **RTO:** < 30 min. **RPO:** 0 (binlog streaming) |

#### DR Runbook
```
Phase 1: Verify — Check status, recent backups, binlog retention
Phase 2: Restore — Restore to NEW instance (never overwrite production)
Phase 3: Validate — Data integrity, application smoke tests, traffic switch
```

### 成本 (Cost) — 扩展版

#### 成本可见性

| 维度 | API/方法 | 输出 | 用途 |
|------|----------|------|------|
| 实例月成本 | Billing API | 规格 × 单价 × 天数 | 成本追踪 |
| 存储成本 | DescribeResourceUsage | 存量 × 存储单价 | 存储优化 |
| 备份成本 | DescribeBackups | 备份量 × 备份单价 | 备份策略优化 |
| 跨地域成本 | DescribeCrossRegionBackup | 跨地域量 × 单价 | 跨地域评估 |

#### FinOps 工作流

| 工作流 | 触发频率 | 输出 | 参考 |
|--------|----------|------|------|
| 利用率审计 | 每周 | 低利用率实例列表 + 节省金额 | [FinOps §1](references/advanced/finops-analysis.md#1-实例利用率评估) |
| 成本审计 | 每月 | 成本趋势 + 异常实例 | [FinOps §5](references/advanced/finops-analysis.md#5-成本预警规则) |
| 预留审计 | 每季度 | 预留覆盖率 + 建议购买 | [FinOps §3](references/advanced/finops-analysis.md#3-预留实例优化) |

#### Right-sizing 建议

| Pattern | Condition | Recommendation | Savings |
|---------|-----------|----------------|---------|
| CPU浪费 | avg < 10% 7d | 降级 2档规格 | 60-80% |
| CPU轻度浪费 | avg 10-30% 7d | 降级 1档规格 | 30-50% |
| 内存浪费 | avg < 30% 7d | 降级规格 | 30-50% |
| 存储浪费 | 使用率 < 30% | 缩容存储至 2倍实际 | 按实际节省 |
| IOPS浪费 | avg < 20% 7d | 存储类型降级 | 20-30% |

#### 预留实例优化

| Running Duration | Recommendation | Savings |
|------------------|----------------|---------|
| 30-180 days | 包月 | 30-40% |
| > 180 days | 包年 | 60-80% |
| > 365 days | 包3年 | 70-85% |

#### 节省计算

```bash
# 降级节省公式
downgrade_savings = (current_rate - target_rate) × 24 × 30

# 预留节省公式
reserved_savings = (on_demand_annual - reserved_annual)

# 合计节省潜力
total_savings = Σ downgrade_savings + Σ reserved_savings + Σ storage_savings
```

> **详细 FinOps 分析**: 参考 [FinOps Cost Optimization](references/advanced/finops-analysis.md)

| Billing | Best For | Savings |
|---------|----------|---------|
| 按量付费 | Dev/test | N/A |
| 包年包月 | Production | Up to 80% |
| Serverless | Unpredictable workloads | Pay per request |

**Waste Detection (FinOps §4):** CPU < 10% AND IOPS < 50 for 7d → downgrade. Unused databases → consolidate. Idle instances (Connections = 0) → archive or delete.

### 效率 (Efficiency)

- **Automated Backups:** Set `BackupPeriod` for scheduled daily backups
- **Parameter Groups:** `ModifyParameter` with scheduled apply to avoid interruption
- **CI/CD:** JSON output by default, compatible with pipelines

### 性能 (Performance)

| Metric | CMS Namespace | Scale Up | Scale Down | Window |
|--------|--------------|----------|------------|--------|
| CpuUsage | `acs_rds_dashboard` | > 80% | < 40% | 5 min |
| IOPSUsage | `acs_rds_dashboard` | > 80% | < 50% | 5 min |
| MemoryUsage | `acs_rds_dashboard` | > 85% | < 60% | 5 min |
| ActiveSession | `acs_rds_dashboard` | > 20 | < 5 | 5 min |

**Key guidance:** Use `DescribeDBInstancePerformance` for baselines. `DescribeSlowLogRecords` for > 1s queries. Distribute reads across RO nodes if connection limits reached.

## SQL Execution (Agent Quick Reference)

> **Full runbook:** [references/advanced/sql-execution.md](references/advanced/sql-execution.md)

| User intent | Agent action |
|-------------|--------------|
| Run multi-statement `.sql` file | **Path A:** `mysql -h ... < file.sql` after `DescribeDBInstanceNetInfo` + whitelist |
| "用阿里云 CLI 执行 SQL 文件" | Clarify: `aliyun rds` **cannot**; use `mysql` (Path A) or `rds-data` plugin (Path B, no native file flag) |
| Single SQL without port 3306 | Install `aliyun-cli-rds-data`; `CreateSecret`/`DescribeSecrets`; `execute-statement --sql "..."` |
| Bulk parameterized INSERT | `batch-execute-statement` — not a general SQL file runner |

```bash
aliyun plugin install --names aliyun-cli-rds-data   # required for rds-data subcommands
```

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [SQL Execution (mysql client & RDS Data API)](references/advanced/sql-execution.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Alert Diagnosis & Root Cause Analysis](references/alert-diagnosis.md)
- [AIOps Prediction & Anomaly Detection](references/advanced/aiops-prediction.md)
- [FinOps Cost Optimization](references/advanced/finops-analysis.md)
- [Observability (Metrics/Logs/Traces 联动)](references/observability.md)
- [RDS Cruise (巡检工作流)](references/cruise.md)
- [Fault Pattern Knowledge Base](references/knowledge-base.md)
- [Prompts Handbook (提示词示例)](references/prompts.md)
- [Integration](references/integration.md)
- [GCL Rubric](references/rubric.md) — **Phase 1 rollout** GCL rubric (5 core + 3 Aliyun dimensions, per-op Safety sub-rules, 6-class / 12-regex SQL classification, 4 worked examples)
- [GCL Prompt Templates](references/prompt-templates.md) — **Phase 1 rollout** Generator & Critic prompt templates (3-path: control-plane CLI / SDK / data-plane SQL aware)

## See Also

- [Proactive Inspection Workflow Template](../alicloud-skill-generator/templates/proactive-inspection.md)
- [API Call Counter Pattern](../alicloud-skill-generator/templates/api-call-counter.md)

## Operational Best Practices

- **Least privilege:** RAM policies scoped to required APIs only.
- **Availability:** Use multi-AZ deployments for production workloads.
- **Cost:** Right-size instance class and storage; use prepaid for long-term workloads.
- **Security:** Restrict SecurityIPList to minimum required CIDRs; rotate account passwords regularly.
- **Backup:** Enable automated backups and test restore procedures periodically.
- **Monitoring:** Set up CloudMonitor alerts for CPU, memory, connections, and disk usage.

---

## Quality Gate (GCL)

This skill is the **third rollout** of the Generator-Critic-Loop (GCL)
adversarial quality gate defined in [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate).
Every runtime execution of an `alicloud-rds-ops` operation MUST be wrapped
in a GCL loop before the result is returned to the user.

> **Two references in this directory carry the GCL contract:**
>
> | File | Purpose |
> |---|---|
> | [`references/rubric.md`](references/rubric.md) | The 5 core + 3 Aliyun-specific rubric dimensions, per-op Safety sub-rules, the 6-class / 12-regex SQL classification, and 4 worked examples |
> | [`references/prompt-templates.md`](references/prompt-templates.md) | The Generator and Critic prompt templates (with `{{env.*}}` / `{{user.*}}` / `{{output.*}}` placeholders) |
> | [`references/advanced/sql-execution.md`](references/advanced/sql-execution.md) | Path A (`mysql`) / Path B (`rds-data`) / Path C (DMS) decision tree — referenced by both rubric and prompt templates for SQL Execution ops |
>
> The full rationale, termination rules, anti-patterns, and rollout roadmap
> live in `AGENTS.md` §12. This section is only a pointer + per-skill override.

### GCL Scope for RDS

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 1 rollout, third skill) |
| Default `max_iter` | **2** (inherited from `AGENTS.md` §12.8) |
| Operations covered | ALL operations in this SKILL.md (CRUD + accounts + databases + backups + whitelists + parameters + SQL Execution) |
| Operations most scrutinized | `DeleteDBInstance`, `DeleteAccount`, `DeleteDatabase`, `RestoreDBInstance`, `ResetAccountPassword`, `CreateAccount` (password hygiene), `ModifySecurityIps` (especially `0.0.0.0/0`), `ModifyParameter` (high-risk params), `UpgradeDBInstanceEngineVersion`, **all SQL Execution ops** (data-plane) |

### Per-Op Safety Sub-Rules (Quick Reference)

For the **full** sub-rule table, see [`references/rubric.md` §1.2](../alicloud-rds-ops/references/rubric.md).
Highlights:

| Operation | Hard Safety condition (Score 1 requires) |
|---|---|
| `DeleteDBInstance` | Explicit user confirmation of `{{user.db_instance_id}}` AND `{{user.db_instance_name}}`; `DBInstanceStatus == Running`; final backup created OR user explicitly waived |
| `DeleteDatabase` | Explicit user confirmation of `{{user.db_name}}`; **final DB-level backup created (no waiver — databases cannot be snapshot-restored)** |
| `RestoreDBInstance` | Explicit user confirmation; `BackupId` verified via `DescribeBackups` with `BackupStatus == Success`; target instance is the original owner |
| `ResetAccountPassword` | Explicit user confirmation; `AccountPassword` NOT in any trace field; password complexity 8-32 chars |
| `CreateAccount` | `AccountName` is not `root` / `admin` / `mysql` / `postgres`; password delivered via env var, not CLI flag |
| `ModifySecurityIps` | **No `0.0.0.0/0` entry** in `{{user.security_ips}}` unless user explicitly justified |
| `ModifyParameter` | Parameter is not in the high-risk list (`innodb_flush_log_at_trx_commit`, `sync_binlog`, `max_connections`, `lower_case_table_names`, `default_storage_engine`, `log_bin`) unless user explicitly justified |
| `UpgradeDBInstanceEngineVersion` | Explicit user confirmation; **final backup created (no waiver)**; maintenance window confirmed |
| **SQL Execution (data-plane)** | See `rubric.md` §1.2.1 — 6 risk classes (READ-ONLY / WRITE-LIMITED / DESTRUCTIVE-LIMITED / DESTRUCTIVE-MASS / SCHEMA-MUTATION / FATAL); 12 regex hot-spots incl. `DELETE` / `UPDATE` without `WHERE`, `DROP DATABASE`, `SHUTDOWN` |

### The WHERE-Clause Rule (data-plane, hard gate)

For multi-statement SQL files (`mysql < file.sql`) or single SQL statements
(`aliyun rds-data execute-statement`):

- **`DELETE` / `UPDATE` without `WHERE`** → Safety = 0 (full-table mutation)
- **`DELETE FROM x WHERE 1=1`** → Safety = 0 (treated as full-table)
- **Multi-statement files** must be scanned in their entirety; the
  worst-case classification across all statements is the file's Safety
  score. Sampling is allowed for very large files (> 1000 statements) but
  must be recorded in `statement_count` / `statements_scanned` /
  `sampling_strategy`.

### RDS-Specific Additions (beyond the 5 core dimensions)

| Dimension | Threshold | Why it matters for RDS |
|---|---|---|
| **Region Compliance** | ≥ 0.5 | `--RegionId` must match `{{user.region}}` to avoid cross-region cost leakage |
| **Credential Hygiene** | = 1 (**absolute**) | RDS has the **richest password surface in the skill farm** — `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `MYSQL_PWD`, `RDS_NEW_PASSWORD`, `AccountPassword`, RDS Data API `ResourceArn`, `SecretStore` credentials. Any one in a trace → ABORT. |
| **Well-Architected** | ≥ 0.5 | The 5 WA pillars from `references/well-architected-assessment.md`. Security is the **primary pillar** for DDL/DML/data-plane ops. |

### Three-Path Trace Convention (control-plane vs. data-plane)

Unlike ECS (cli-first), RDS supports THREE execution paths:

```json
{
  "generator": {
    "path": "control-plane-cli",  // or "control-plane-sdk" | "data-plane-mysql" | "data-plane-rds-data"
    "command": "aliyun rds ...",  // or "mysql -h ... -e ..." for data-plane
    "affected_rows": null,  // int for DML only
    "command_classification": "DESTRUCTIVE-MASS",  // for SQL Execution only
    ...
  }
}
```

Path selection rules (inherited from `prompt-templates.md` §1):

1. **Default to control-plane CLI** — `aliyun rds <action> --DBInstanceId ...`.
2. **Use data-plane SQL** only when: (a) user explicitly asks to run SQL, (b) user provided a `.sql` file, (c) requested op is `SELECT` / `SHOW` / `DESCRIBE` requiring live data read.
3. **NEVER route** `DROP DATABASE` / full-table `TRUNCATE` to data plane when a control-plane alternative exists (e.g. `DeleteDatabase` is softer than `DROP DATABASE`; consider proposing it first).

### Termination (inherited from `AGENTS.md` §12.5)

| Condition | Behavior |
|---|---|
| All dimensions ≥ threshold | **PASS** — return Generator's result |
| Safety = 0 **or** Credential Hygiene = 0 | **ABORT** — never return partial output |
| Other dimension < threshold AND iter < 2 | **RETRY** — inject Critic suggestions into next Generator prompt |
| Other dimension < threshold AND iter = 2 | **MAX_ITER** — return best-so-far + unresolved rubric items |

### Trace Persistence (mandatory)

Every GCL run MUST write `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json`
with the schema defined in `AGENTS.md` §12.6. Apply the RDS-specific
sanitization regex helpers in `rubric.md` §2.2 to scrub all 8 RDS-specific
secret patterns before persisting.

### Changelog (this section only)

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-04 | Third rollout: added `## Quality Gate (GCL)` section + `references/rubric.md` + `references/prompt-templates.md`. Default `max_iter=2`. Aligned with `AGENTS.md` §12 and the ECS / Redis pilots. RDS-specific additions: three-path (control-plane CLI / control-plane SDK / data-plane SQL) trace convention; SQL statement classification (6 risk classes, 12 regex hot-spots); hard WHERE-clause rule (no `WHERE` on `DELETE` / `UPDATE` → Safety = 0); 8 RDS-specific secret patterns with sanitization helper. |

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `dual-path`，CLI/SDK 已覆盖，无需 code snippets.
