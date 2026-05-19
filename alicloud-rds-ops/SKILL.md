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
  references/sql-execution.md; `aliyun rds` alone cannot run SQL files). Also
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
  version: "2.0.0"
  last_updated: "2026-05-19"
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
  `mysql` client or `aliyun rds-data` — see [SQL Execution](references/sql-execution.md);
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

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field value (including `ALIBABA_CLOUD_ACCESS_KEY_ID`) in console output, debug messages, error messages, or logs. If credential information must be displayed for debugging or troubleshooting purposes, use the masking format: show only the first 4 characters followed by `****` (e.g., `abcd****`). This masking rule applies to ALL output channels: stdout, stderr, log files, debug traces, error messages, and diagnostic reports.
>
> **Masking rules across all execution paths:**
> | Execution Path | Safe Pattern | Unsafe Pattern |
> |----------------|-------------|----------------|
> | Console output | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=abcd****` | Raw credential value in output |
> | Error messages | `Error: API call failed (credential omitted)` | Error containing raw credential value |
> | Log files | `[INFO] Credentials: Secret=abcd****` | `[INFO] AK Secret: LTAI5t...` |
> | Verification | `test -n "$var" && echo "Secret is set"` (existence check only) | `echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET` |
> | JIT Go SDK | env read via `os.Getenv(...)` is safe; never print `Config` struct | `fmt.Printf("Config: %+v", config)` |
> | Debug/verbose | `Debug mode may expose credentials (use with caution)` | Un-masked credential in debug output |
>
> **Credential verification MUST check existence only**, never echo the value. This applies to ALL execution flows (SDK, CLI, and debugging scripts).

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

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-14 | Initial RDS skill with dual-path (CLI + SDK) support |

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

```go
package main

import (
	"fmt"
	"os"
	"strconv"
	"time"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	rds "github.com/alibabacloud-go/rds-20140815/v2/client"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
		RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	}

	c, err := rds.NewClient(config)
	if err != nil {
		panic(err)
	}

	storageInt, _ := strconv.Atoi(os.Getenv("DB_INSTANCE_STORAGE"))

	req := &rds.CreateDBInstanceRequest{
		RegionId:          tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
		Engine:            tea.String(os.Getenv("ENGINE")),
		EngineVersion:     tea.String(os.Getenv("ENGINE_VERSION")),
		DBInstanceClass:   tea.String(os.Getenv("DB_INSTANCE_CLASS")),
		DBInstanceStorage: tea.Int32(int32(storageInt)),
		DBInstanceNetType: tea.String(os.Getenv("DB_INSTANCE_NET_TYPE")),
		VPCId:             tea.String(os.Getenv("VPC_ID")),
		VSwitchId:         tea.String(os.Getenv("VSWITCH_ID")),
		SecurityIPList:    tea.String(os.Getenv("SECURITY_IP_LIST")),
		PayType:           tea.String(os.Getenv("PAY_TYPE")),
		ClientToken:       tea.String(os.Getenv("CLIENT_TOKEN")),
	}

	resp, err := c.CreateDBInstance(req)
	if err != nil {
		panic(err)
	}

	instanceId := tea.ToString(resp.Body.DBInstanceId)
	fmt.Printf("Created RDS instance: %s\n", instanceId)

	// Poll until Running
	for i := 0; i < 60; i++ {
		descReq := &rds.DescribeDBInstancesRequest{
			RegionId:     tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
			DBInstanceId: tea.String(instanceId),
		}
		descResp, err := c.DescribeDBInstances(descReq)
		if err != nil {
			panic(err)
		}
		items := descResp.Body.Items.DBInstance
		if len(items) > 0 && tea.ToString(items[0].DBInstanceStatus) == "Running" {
			fmt.Println("RDS instance is Running")
			break
		}
		time.Sleep(10 * time.Second)
	}
}
```

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

```go
req := &rds.DescribeDBInstancesRequest{
	RegionId:     tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
}
resp, err := c.DescribeDBInstances(req)
```

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

```go
req := &rds.RestartDBInstanceRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
}
resp, err := c.RestartDBInstance(req)
```

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

```go
req := &rds.DeleteDBInstanceRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
}
resp, err := c.DeleteDBInstance(req)
```

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

```go
req := &rds.DescribeAccountsRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
}
resp, err := c.DescribeAccounts(req)
```

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

```go
req := &rds.CreateAccountRequest{
	DBInstanceId:    tea.String(os.Getenv("DB_INSTANCE_ID")),
	AccountName:     tea.String(os.Getenv("ACCOUNT_NAME")),
	AccountPassword: tea.String(os.Getenv("ACCOUNT_PASSWORD")),
	AccountType:     tea.String(os.Getenv("ACCOUNT_TYPE")),
}
resp, err := c.CreateAccount(req)
```

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

```go
req := &rds.DeleteAccountRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
	AccountName:  tea.String(os.Getenv("ACCOUNT_NAME")),
}
resp, err := c.DeleteAccount(req)
```

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

```go
req := &rds.CreateDatabaseRequest{
	DBInstanceId:     tea.String(os.Getenv("DB_INSTANCE_ID")),
	DBName:           tea.String(os.Getenv("DB_NAME")),
	CharacterSetName: tea.String(os.Getenv("CHARACTER_SET_NAME")),
}
resp, err := c.CreateDatabase(req)
```

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

```go
req := &rds.DeleteDatabaseRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
	DBName:       tea.String(os.Getenv("DB_NAME")),
}
resp, err := c.DeleteDatabase(req)
```

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

```go
req := &rds.DescribeDatabasesRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
}
resp, err := c.DescribeDatabases(req)
```

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

```go
req := &rds.CreateBackupRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
	BackupMethod: tea.String(os.Getenv("BACKUP_METHOD")),
	BackupType:   tea.String(os.Getenv("BACKUP_TYPE")),
}
resp, err := c.CreateBackup(req)
```

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

```go
req := &rds.RestoreDBInstanceRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
	BackupId:     tea.String(os.Getenv("BACKUP_ID")),
}
resp, err := c.RestoreDBInstance(req)
```

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

```go
req := &rds.DescribeBackupsRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
	StartTime:    tea.String(os.Getenv("START_TIME")),
	EndTime:      tea.String(os.Getenv("END_TIME")),
}
resp, err := c.DescribeBackups(req)
```

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

```go
req := &rds.DescribeSlowLogsRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
	StartTime:    tea.String(os.Getenv("START_TIME")),
	EndTime:      tea.String(os.Getenv("END_TIME")),
	DBName:       tea.String(os.Getenv("DB_NAME")),
}
resp, err := c.DescribeSlowLogs(req)
```

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

```go
req := &rds.DescribeResourceUsageRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
}
resp, err := c.DescribeResourceUsage(req)
```

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

```go
req := &rds.DescribeDBInstancePerformanceRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
	Key:          tea.String(os.Getenv("METRIC_KEY")),
	StartTime:    tea.String(os.Getenv("START_TIME")),
	EndTime:      tea.String(os.Getenv("END_TIME")),
}
resp, err := c.DescribeDBInstancePerformance(req)
```

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

```go
req := &rds.DescribeDBInstanceHAConfigRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
}
resp, err := c.DescribeDBInstanceHAConfig(req)
```

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

```go
req := &rds.ModifySecurityIpsRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
	SecurityIps:  tea.String(os.Getenv("SECURITY_IPS")),
}
resp, err := c.ModifySecurityIps(req)
```

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

```go
req := &rds.DescribeParametersRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
}
resp, err := c.DescribeParameters(req)
```

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

```go
req := &rds.ModifyParameterRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
	Parameters:   tea.String(os.Getenv("PARAMETERS")),
}
resp, err := c.ModifyParameter(req)
```

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

```go
req := &rds.DescribeDBInstanceAttributeRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
}
resp, err := c.DescribeDBInstanceAttribute(req)
```

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

```go
req := &rds.DescribeDBInstanceNetInfoRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
}
resp, err := c.DescribeDBInstanceNetInfo(req)
```

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

```go
req := &rds.DescribeDBInstanceIPArrayListRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
}
resp, err := c.DescribeDBInstanceIPArrayList(req)
```

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

```go
req := &rds.DescribeBinlogFilesRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
	StartTime:    tea.String(os.Getenv("START_TIME")),
	EndTime:      tea.String(os.Getenv("END_TIME")),
}
resp, err := c.DescribeBinlogFiles(req)
```

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

```go
req := &rds.DescribeErrorLogsRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
	StartTime:    tea.String(os.Getenv("START_TIME")),
	EndTime:      tea.String(os.Getenv("END_TIME")),
}
resp, err := c.DescribeErrorLogs(req)
```

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

```go
req := &rds.DescribeSQLLogRecordsRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
	StartTime:    tea.String(os.Getenv("START_TIME")),
	EndTime:      tea.String(os.Getenv("END_TIME")),
}
resp, err := c.DescribeSQLLogRecords(req)
```

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

```go
storageInt, _ := strconv.Atoi(os.Getenv("DB_INSTANCE_STORAGE"))

req := &rds.ModifyDBInstanceSpecRequest{
	DBInstanceId:      tea.String(os.Getenv("DB_INSTANCE_ID")),
	DBInstanceClass:   tea.String(os.Getenv("DB_INSTANCE_CLASS")),
	DBInstanceStorage: tea.Int32(int32(storageInt)),
	PayType:           tea.String(os.Getenv("PAY_TYPE")),
}
resp, err := c.ModifyDBInstanceSpec(req)
```

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

```go
req := &rds.UpgradeDBInstanceEngineVersionRequest{
	DBInstanceId:  tea.String(os.Getenv("DB_INSTANCE_ID")),
	EngineVersion: tea.String(os.Getenv("ENGINE_VERSION")),
}
resp, err := c.UpgradeDBInstanceEngineVersion(req)
```

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

```go
req := &rds.DescribeAvailableZonesRequest{
	RegionId:      tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	Engine:        tea.String(os.Getenv("ENGINE")),
	EngineVersion: tea.String(os.Getenv("ENGINE_VERSION")),
}
resp, err := c.DescribeAvailableZones(req)
```

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

```go
req := &rds.DescribeReadDBInstancesRequest{
	DBInstanceId: tea.String(os.Getenv("DB_INSTANCE_ID")),
}
resp, err := c.DescribeReadDBInstances(req)
```

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

The **RDS Cruise** is a composite workflow that runs multiple checks in sequence
for comprehensive instance health assessment. Use this when the user asks to
"巡检", "检查", "健康检查", "health check", "cruise", or "inspect" an RDS instance.

### Cruise Execution Order

| Step | Operation | Purpose | On Failure |
|------|-----------|---------|------------|
| 1 | **DescribeDBInstanceAttribute** | Verify instance exists and get full status | HALT if not found |
| 2 | **DescribeDBInstanceNetInfo** | Check connection endpoints and network config | Log warning |
| 3 | **DescribeDBInstanceHAConfig** | Verify HA status and sync mode | Log warning if single-AZ |
| 4 | **DescribeResourceUsage** | Check disk, data, log, backup usage | Alert if > 80% |
| 5 | **DescribeDBInstancePerformance** | Check CPU, memory, connections, IOPS | Alert if thresholds exceeded |
| 6 | **DescribeSlowLogs** | Identify top slow queries | Log top 5 |
| 7 | **DescribeBackups** | Verify recent backup success | Alert if no successful backup in 24h |
| 8 | **DescribeParameters** | Check critical parameter values | Log non-default values |
| 9 | **DescribeErrorLogs** | Check recent errors | Log if errors found |
| 10 | **DescribeAccounts** | Audit accounts and privileges | Log if Super accounts exist |
| 11 | **DescribeDBInstanceIPArrayList** | Verify whitelist configuration | Log if too permissive (0.0.0.0/0) |

### Cruise CLI Script

```bash
#!/bin/bash
# RDS Cruise — Comprehensive Health Check
DB_INSTANCE_ID="{{user.db_instance_id}}"
REGION="{{user.region}}"
# Cross-platform date calculation (macOS and Linux)
if date -v-1d +%Y-%m-%dT%H:%M:%SZ >/dev/null 2>&1; then
  START_TIME="$(date -u -v-1d +%Y-%m-%dT%H:%M:%SZ)"
else
  START_TIME="$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ)"
fi
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "=== RDS Cruise: $DB_INSTANCE_ID ==="
echo ""

# 1. Instance Attribute
echo "[1/11] Instance Attribute"
aliyun rds DescribeDBInstanceAttribute --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 2. Net Info
echo "[2/11] Network Info"
aliyun rds DescribeDBInstanceNetInfo --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 3. HA Config
echo "[3/11] HA Configuration"
aliyun rds DescribeDBInstanceHAConfig --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 4. Resource Usage
echo "[4/11] Resource Usage"
aliyun rds DescribeResourceUsage --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 5. Performance — CPU
echo "[5/11] Performance (CPU)"
aliyun rds DescribeDBInstancePerformance \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --Key MySQL_CPUUsage --StartTime "$START_TIME" --EndTime "$END_TIME"
echo ""

# 6. Slow Logs
echo "[6/11] Slow Queries (Top 5)"
aliyun rds DescribeSlowLogs \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  --output cols=SQLText,MySQLTotalExecutionCounts,MySQLTotalExecutionTimes rows=Items.SQLSlowLog[0:5].{SQLText,MySQLTotalExecutionCounts,MySQLTotalExecutionTimes}
echo ""

# 7. Backups
echo "[7/11] Backups (Last 24h)"
aliyun rds DescribeBackups \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --StartTime "$START_TIME" --EndTime "$END_TIME"
echo ""

# 8. Parameters — Critical
echo "[8/11] Critical Parameters"
aliyun rds DescribeParameters --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 9. Error Logs
echo "[9/11] Error Logs"
aliyun rds DescribeErrorLogs \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --StartTime "$START_TIME" --EndTime "$END_TIME"
echo ""

# 10. Accounts
echo "[10/11] Accounts"
aliyun rds DescribeAccounts --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 11. IP Whitelist
echo "[11/11] IP Whitelist"
aliyun rds DescribeDBInstanceIPArrayList --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

echo "=== RDS Cruise Complete ==="
```

### Cruise Thresholds & Alerts

| Check | Warning Threshold | Critical Threshold | Agent Action |
|-------|-------------------|-------------------|--------------|
| Disk Usage | > 80% | > 90% | Alert; suggest storage expansion. Note: Calculate from `DiskUsed/DBInstanceStorage*100` |
| CPU Usage | > 80% | > 95% | Alert; suggest instance upgrade or query optimization |
| Memory Usage | > 80% | > 95% | Alert; suggest instance upgrade |
| Connections | > 80% of max_connections | > 95% | Alert; suggest connection pooling |
| Slow Queries | > 10 in 1h | > 50 in 1h | Alert; suggest index optimization |
| Backup Age | > 24h | > 48h | Alert; verify backup policy |
| Error Logs | Any errors | Repeated errors | Log; investigate root cause |
| IP Whitelist | 0.0.0.0/0 present | — | Security alert; restrict access |
| HA Sync Mode | Async | — | Warning; suggest Sync for critical workloads |

---

## Prerequisites

1. **Install `aliyun` CLI** (primary execution path — static Go binary, no runtime
   dependencies):

   ```bash
   # Official installer (auto-detects OS and architecture)
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"

   # Or Homebrew (macOS)
   brew install aliyun-cli
   ```

2. **Bootstrap Go runtime** (for JIT SDK fallback — only needed if CLI does not
   support operation):

   ```bash
   # Check if Go exists
   if ! command -v go &> /dev/null; then
       # JIT download Go 1.24 (auto-detects OS and architecture)
       OS=$(uname -s | tr '[:upper:]' '[:lower:]')
       ARCH=$(uname -m)
       [ "$ARCH" = "x86_64" ] && ARCH="amd64"
       [ "$ARCH" = "aarch64" ] && ARCH="arm64"

       mkdir -p /tmp/go-runtime
       curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime

       # Set environment variables
       export PATH="/tmp/go-runtime/go/bin:$PATH"
       export GOPATH="/tmp/go-workspace"
       export GOCACHE="/tmp/go-cache"
       export GOMODCACHE="/tmp/go-modcache"
       export GOPROXY="https://goproxy.cn,direct"  # China CDN mirror
   fi

   go version
   ```

   > Go version strategy: **JIT download Go 1.24+**, **Script compatibility Go 1.21+**
   > (minimum).

3. **Configure Credentials** — Environment variables (recommended for Agent execution):

   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```
   > **IMPORTANT:** When outputting the above commands to console or logs, the agent MUST replace `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` with the masking format `****` instead of the actual secret value (i.e., display as `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"`). Never resolve `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` to its actual value in any visible output.

   **Alternative — Interactive CLI Configuration:**
   ```bash
   aliyun configure
   ```

   **Alternative — Config File (`~/.aliyun/config.json`):**
   ```bash
   mkdir -p ~/.aliyun
   cat > ~/.aliyun/config.json << 'CONFIGEOF'
   {
     "current": "default",
     "profiles": [
       {
         "name": "default",
         "mode": "AK",
         "access_key_id": "{{user.access_key_id}}",
         "access_key_secret": "{{user.access_key_secret}}",
         "region_id": "{{user.region}}"
       }
     ]
   }
   CONFIGEOF
   ```

4. **Verify Configuration**:
   ```bash
   # Quick validation (JSON output by default)
   aliyun rds DescribeRegions
   ```

> **Security:** Never commit `.env` to version control (already in `.gitignore`).
> All credentials use `{{env.*}}` placeholders in generated Skills — never real values.

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

For rapid triage, execute this composite command:

```bash
#!/bin/bash
# RDS Smart Diagnosis — Rapid Triage
DB_INSTANCE_ID="{{user.db_instance_id}}"
REGION="{{user.region}}"

# Cross-platform date
if date -v-1H +%Y-%m-%dT%H:%M:%SZ >/dev/null 2>&1; then
  START_TIME="$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"
else
  START_TIME="$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)"
fi
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "=== RDS Smart Diagnosis: $DB_INSTANCE_ID ==="
echo ""

# 1. Instance status and spec
echo "[1/6] Instance Attribute"
aliyun rds DescribeDBInstanceAttribute --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --output cols=DBInstanceId,DBInstanceStatus,Engine,EngineVersion,DBInstanceClass,DBInstanceStorage,MaxConnections rows=Items.DBInstanceAttribute[0].{DBInstanceId,DBInstanceStatus,Engine,EngineVersion,DBInstanceClass,DBInstanceStorage,MaxConnections}
echo ""

# 2. Resource usage
echo "[2/6] Resource Usage"
aliyun rds DescribeResourceUsage --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 3. Performance snapshot
echo "[3/6] Performance Snapshot"
aliyun rds DescribeDBInstancePerformance \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --Key MySQL_CPUUsage,MySQL_MemoryUsage,MySQL_Sessions,MySQL_ActiveSessions,MySQL_IOPS,MySQL_TPS,MySQL_QPS \
  --StartTime "$START_TIME" --EndTime "$END_TIME"
echo ""

# 4. HA status
echo "[4/6] HA Configuration"
aliyun rds DescribeDBInstanceHAConfig --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 5. Top slow queries
echo "[5/6] Top 5 Slow Queries"
aliyun rds DescribeSlowLogs \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  --output cols=SQLText,MySQLTotalExecutionCounts,MySQLTotalExecutionTimes,MySQLMaxExecutionTime rows=Items.SQLSlowLog[0:5].{SQLText,MySQLTotalExecutionCounts,MySQLTotalExecutionTimes,MySQLMaxExecutionTime}
echo ""

# 6. Recent errors
echo "[6/6] Recent Errors"
aliyun rds DescribeErrorLogs \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  --output cols=ErrorInfo,CreateTime rows=Items.ErrorLog[0:5].{ErrorInfo,CreateTime}
echo ""

echo "=== Diagnosis Data Collection Complete ==="
echo "Apply correlation matrix and engine-specific diagnostic tree to identify root cause."
```

> **Note:** Replace `MySQL_*` metric keys with `Pg_*` or `MSSQL_*` prefixes
> for PostgreSQL or SQL Server instances.

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

### 成本 (Cost)

| Billing | Best For | Savings |
|---------|----------|---------|
| 按量付费 | Dev/test | N/A |
| 包年包月 | Production | Up to 80% |
| Serverless | Unpredictable workloads | Pay per request |

**Waste:** CPU < 10% AND IOPS < 50 for 7d → downgrade. Unused databases → consolidate.

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

> **Full runbook:** [references/sql-execution.md](references/sql-execution.md)

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
- [SQL Execution (mysql client & RDS Data API)](references/sql-execution.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Alert Diagnosis & Root Cause Analysis](references/alert-diagnosis.md)
- [Integration](references/integration.md)

## Operational Best Practices

- **Least privilege:** RAM policies scoped to required APIs only.
- **Availability:** Use multi-AZ deployments for production workloads.
- **Cost:** Right-size instance class and storage; use prepaid for long-term workloads.
- **Security:** Restrict SecurityIPList to minimum required CIDRs; rotate account passwords regularly.
- **Backup:** Enable automated backups and test restore procedures periodically.
- **Monitoring:** Set up CloudMonitor alerts for CPU, memory, connections, and disk usage.
