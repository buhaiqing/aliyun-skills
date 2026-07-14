---
name: alicloud-dms-ops
description: >-
Use when the user needs to manage Alibaba Cloud DMS (Data Management Service) —
AI-powered data security
access gateway with NL2SQL, SQL audit, fine-grained permission control
(instance/DB/table/column/row level),
multi-source data governance, and DevOps workflow automation. User mentions DMS,
Data Management, data
security access, SQL review, intelligent query, NL2SQL, data governance, or
describes scenarios involving
database SQL execution, permission control, audit trails, or
natural-language-to-SQL queries even without
naming DMS directly. Not for billing, RAM, or specific database product
operations (RDS, PolarDB) that
  have their own ops skills.
license: MIT
compatibility: >-
Official Alibaba Cloud CLI (`aliyun`, with dms plugin), Go 1.21+ runtime (for
JIT SDK fallback),
  valid API credentials, network access to Alibaba Cloud endpoints.
metadata:
  author: alicloud
  version: "1.3.0"
  last_updated: "2026-07-14"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "DMS Enterprise 2024-04-14 — https://help.aliyun.com/zh/dms"
  cli_applicability: "dual-path"
  cli_support_evidence: >-
    DMS CLI requires plugin: `aliyun plugin install --names aliyun-cli-dms`.
Base CLI: `aliyun dms <ApiName>` API-style invocation. SDK path available as
fallback.
  environment:
 - ALIBABA_CLOUD_ACCESS_KEY_ID
 - ALIBABA_CLOUD_ACCESS_KEY_SECRET
 - ALIBABA_CLOUD_REGION_ID
 - ALIBABA_CLOUD_DMS_ENDPOINT
---

# Alibaba Cloud DMS (Data Management Service) Operations Skill

## Overview

DMS (Data Management Service) on Alibaba Cloud is an **AI-powered data security
access gateway** that provides:

- **Secure Access**: Credential security management, intranet-only data access,
  fine-grained permission control (instance/DB/table/column/row level),
  high-risk SQL identification and blocking, SQL audit trails
- **Intelligent Query (NL2SQL)**: Natural language to SQL conversion,
  personalized knowledge base, multi-source unified query
- **Multi-Source Support**: 40+ database and data warehouse types across Aliyun,
  AWS, and on-premise

> **UX Compliance:** This skill follows the [User Experience
  Specification](../references/user-experience-spec.md).

### CLI applicability

- **`cli_applicability: dual-path`:** DMS CLI requires plugin
  (`aliyun-cli-dms`). Both **CLI** (with plugin) and **SDK** paths are
  documented for each operation.

## Product Skill Mission

| Pillar | Mission | This skill |
| -------- | --------- | ------------ |
| **Domain colleague** | DMS data governance expertise + context for database teams | SQL approval flow, NL2SQL intelligent query, fine-grained permission runbook |
| **Harnessed delivery** | Explainable, observable outcomes | GCL rubric + wrapper-first CLI |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "DMS", "Data Management", "data security access",
  "SQL review", "intelligent query", "NL2SQL", or "data governance"
- Task involves SQL execution approval workflows, permission management,
  audit queries
- Task keywords: GetApproval, SubmitTask, ExecuteSql, GrantPermission,
  CreateUser, Query, AskQuestion, ListDatabase, CreateInstance,
  SensitiveColumn, AuditLog, SQL Review, HighRisk SQL
- User asks to execute SQL, manage permissions, query via natural language,
  or audit database activity
- User describes scenarios: "ask question about my data", "run SQL safely",
  "control who can access what data"

### SHOULD NOT Use This Skill When

- Task is about specific database products (RDS, PolarDB,
  Redis) → delegate to respective skills
- Task is billing / account management → delegate to: `alicloud-billing-ops`
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops`

### Delegation Rules

| Capability | Delegate To | Notes |
| ------------ | ------------- | ------- |
| RDS/PolarDB Instance Management | `alicloud-rds-ops` / `alicloud-polardb-ops` | DMS handles SQL governance only; instance lifecycle delegated |
| OSS File Operations | `alicloud-oss-ops` | Data import/export scenarios |
| Compute Nest Service | `alicloud-computenest-ops` | DMS deployment related |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
| ------------- | --------- | -------------- |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask user |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask user |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use default if skill allows |
| `{{env.ALIBABA_CLOUD_DMS_ENDPOINT}}` | DMS API endpoint | Default: `dms-enterprise.aliyuncs.com` |
| `{{user.database_id}}` | User-supplied database/DbId | Ask once; reuse |
| `{{user.user_id}}` | DMS user ID | Ask once; reuse |
| `{{user.sql_content}}` | SQL to execute/query | Ask once; reuse |
| `{{user.natural_question}}` | Natural language question for NL2SQL | Ask once; reuse |
| `{{output.task_id}}` | From API response | Parse from JSON |
| `{{output.request_id}}` | From API response | Log for audit |

> **Security:** NEVER log, print, or expose credential values. Verify existence
  only.

## Quick Start

### What This Skill Does

Enables secure SQL execution, fine-grained permission control,
natural-language-to-SQL queries, and audit trail management for DMS.

### Prerequisites

- DMS plugin: `aliyun plugin install --names aliyun-cli-dms`
- Credentials: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`

### Verify Setup

```bash
# Check DMS CLI (requires plugin)
aliyun dms --help

# Verify credentials
aliyun dms ListDatabases --PageSize 10
```

### Your First Command

```bash
# List databases accessible to current user
aliyun dms ListDatabases --PageSize 50
```

### Next Steps

- [Core Concepts](references/core-concepts.md) — Understand DMS architecture,
  data sources, permission model
- [Common Operations](#execution-flows-agent-readable) — SQL execution,
  permission management, NL2SQL
- [Troubleshooting](references/troubleshooting.md) — Fix common issues

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
| ----------- | ------------- | ------------ | ------------ |
| Submit SQL Task | Submit SQL execution task for approval | Medium | Medium |
| Approve/Reject Task | SQL review workflow (approve or reject) | Low | Medium |
| Get Approval | Query approval status for a task | Low | None |
| Execute SQL (CRUD/DDL) | Execute approved CRUD/DDL on target database | Medium | **High** |
| Call Stored Procedure | Call DB stored procedure (`CALL proc()`) | Medium | **High** |
| Call Function | Call DB function (`SELECT fn()`) | Low | Medium |
| Database User Mgmt | CREATE/ALTER/DROP USER + GRANT/REVOKE on DB | Medium | **High** |
| Batch SQL Transaction | Execute multi-statement SQL (transaction or batch) | Medium | **High** |
| Get Execution Detail | Retrieve SQL execution result/log | Low | None |
| List Databases | List databases registered in DMS | Low | None |
| Register Database | Register new DB instance into DMS | Medium | Medium |
| Unregister Database | Remove DB from DMS | Medium | **High** |
| Transfer Owner | Change database owner to another user | Low | Medium |
| NL2SQL Query | Convert natural language to SQL and execute | Medium | Low |
| Grant Permission | Grant fine-grained access (DB/table/column/row) | Medium | Medium |
| Revoke Permission | Revoke previously granted access | Medium | Medium |
| List Permissions | List all permissions for a user | Low | None |
| Sensitive Column Mgmt | Mark and protect sensitive columns | Low | Medium |
| SQL Audit Log | Query SQL execution audit trail | Low | None |
| Lock/Unlock Table | Exclusive lock for maintenance | Low | **High** |
| Create User | Create DMS user with role | Low | Medium |
| List Users | List all DMS users | Low | None |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI or SDK) → Validate → Recover**. Do
not skip phases.

### Operation: Submit SQL Task (SQL Approval Flow)

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
| ------- | -------- | ---------- | ------------ |
| Credentials | `test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID"` | Non-empty | HALT |
| DMS plugin/SDK | `aliyun dms --help` | Available | Fall back to SDK |
| Target database | `ListDatabases` confirms DbId exists | Found | HALT |
| High-risk SQL check | Rule engine scans | Pass or flag | Block; warn |

#### Execution — CLI (Primary Path)

```bash
# Submit SQL task for approval (creates ResourceLocker)
aliyun dms CreateResourceLocker \
 --ResourceList '[{"ResourceId":"{{user.database_id}}","ResourceType":"DATABASE"}]' \
 --Comment "{{user.sql_comment}}"
```

#### Execution — JIT Go SDK (Fallback Path)

```go
// Submit SQL task for approval
request := &dms.CreateResourceLockerRequest{
    ResourceList: []*dms.CreateResourceLockerRequestResourceList{
        {ResourceId: tea.String("{{user.database_id}}"), ResourceType: tea.String("DATABASE")},
    },
    Comment: tea.String("{{user.sql_comment}}"),
}
resp, err := client.CreateResourceLocker(request)
if err != nil {
    panic(err)
}
// resp.LockerId -> polling target
fmt.Println(tea.ToString(resp.Body))
```

#### Post-execution Validation (Submit)

1. Capture `{{output.locker_id}}` from `$.LockerId`
2. Poll `GetResourceLocker` until `Status == Approved` or timeout (max 300s,
   interval 10s)

#### Failure Recovery (Submit)

| Error pattern | Max retries | Agent Action | UX Feedback |
| --------------- | ------------- | -------------- | ------------- |
| InvalidParameter / SQL syntax error | 0–1 | Fix SQL; retry once | `[ERROR] InvalidParameter: SQL syntax error. Fix and retry.` |
| HighRiskSQL.Blocked | 0 | HALT; user modifies SQL | `[ERROR] High-risk SQL blocked by rule engine. Modify SQL or contact admin.` |
| QuotaExceeded | 0 | HALT; user raises quota | `[ERROR] QuotaExceeded: Daily task limit reached.` |
| Unauthorized | 0 | HALT; add `dms:*` RAM policy | `[ERROR] Unauthorized: Check RAM permissions.` |
| InternalError / 5xx | 3 | Retry with 2s, 4s, 8s backoff | `[ERROR] InternalError: Server error. Retrying...` |

### Operation: Execute SQL (CRUD + DDL)

> **Safety Gate:** MUST confirm target database and SQL content before
  execution.

#### Pre-flight (Safety Gate)

| Check | Method | Expected | On Failure |
| ------- | -------- | ---------- | ------------ |
| Confirmation | User confirms SQL intent | Explicit yes | HALT |
| Task approval (write) | `GetResourceLocker --LockerId "{{user.locker_id}}"` | Status == Approved | HALT — submit for approval first |
| Read-only (SELECT) | Check SQL starts with SELECT | SELECT intent | Skip approval check |
| High-risk SQL | SQL matches DROP/TRUNCATE/CREATE USER | Flagged | **HALT** — may need admin whitelist |

#### SQL Classification (Agent Decision Table)

| SQL Pattern | Execution Path | Approval Required |
| ------------- | ---------------- | ------------------- |
| `SELECT` (read-only) | ExecuteStatement directly | No |
| `INSERT` / `UPDATE` / `DELETE` | ExecuteStatement | **Yes** (via CreateResourceLocker) |
| `ALTER` / `CREATE` / `DROP` | ExecuteStatement | **Yes** + admin whitelist may apply |
| `CREATE USER` / `DROP USER` | ExecuteStatement | **HALT** — high-risk blocked by default |
| `CALL proc()` | ExecuteStatement | Depends on DB rules |
| `TRUNCATE` | ExecuteStatement | **HALT** — blocked without admin |

#### Execution — CLI (Execute)

```bash
# Read-only (no approval needed)
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "SELECT * FROM users WHERE id = {{user.user_id}}"

# Write operation (requires prior approval via CreateResourceLocker)
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "INSERT INTO orders (user_id, amount) VALUES (123, 99.9)"

# DDL (approval + admin whitelist may be required)
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "ALTER TABLE users ADD COLUMN phone VARCHAR(20)"
```

#### Execution — JIT Go SDK (Execute)

```go
request := &dms.ExecuteStatementRequest{
    DbId: tea.String("{{user.database_id}}"),
    Sql:  tea.String("{{user.sql_content}}"),
}
resp, err := client.ExecuteStatement(request)
if err != nil {
    panic(err)
}
// resp.Body.AffectedRows, resp.Body.RequestId
fmt.Println(tea.ToString(resp.Body))
```

#### Post-execution Validation (Execute SQL)

1. Capture `{{output.affected_rows}}` from `$.AffectedRows`
2. Capture `{{output.request_id}}` from `$.RequestId` for audit
3. Log execution with timestamp, user, database, SQL (masked), affected rows
4. For SELECT/query results: present rows in readable table format

#### Failure Recovery (Execute SQL)

| Error pattern | Agent Action |
| -------------- | -------------- |
| PermissionDenied | HALT; user needs GrantPermission first |
| SQLSyntaxError | Fix SQL; retry once |
| HighRiskSQL.Blocked | HALT; contact admin to whitelist; do NOT retry without approval |
| ConnectionFailed | Retry once; check database connectivity |
| SqlSyntaxError | Fix SQL; retry once |
| TableNotFound | Verify table name via Query; list tables first |

### Operation: Call Stored Procedure / Function

> **Safety Gate:** Stored procedure and function calls are subject to the
  high-risk SQL rule engine. Two confirmations are required before execution.

#### Pre-flight (Safety Gate — Two-Step Confirmation, Both Required)

| # | Check | Method | Expected | On Failure |
| --- | ------- | -------- | ---------- | ------------ |
| 1 | **User Confirmation** | Explicitly notify user: `CALL` / `SELECT fn()` will be scanned by DMS high-risk rule engine | User explicitly agrees to execute | HALT |
| 2 | **Admin Whitelist** | If user lacks privilege → instruct user to contact DMS admin to whitelist the current SQL | admin whitelisted | HALT — wait for admin |

#### OUT/INOUT Parameter Limitations

| Parameter Type | Supported | Description |
| ---------------- | ----------- | ------------- |
| IN Parameter | Yes | Normal parameter passing |
| OUT Parameter | With Caveat | DMS `ExecuteStatement` returns `AffectedRows`; OUT parameter values are NOT guaranteed to be returned. Recommend `SELECT fn()` instead of `CALL proc(?, @out)` |
| INOUT Parameter | With Caveat | Same as above; recommend writing to a temp table inside the procedure, then SELECT back |
| Return Value (RETURNS) | Yes | `SELECT fn(args)` returns scalar value normally |

#### Execution — CLI (Call Procedure)

```bash
# Call stored procedure (no OUT parameters)
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "CALL sp_monthly_report(2024, 12)"

# Call stored procedure (with OUT parameters — NOT recommended, OUT values may be lost)
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "CALL sp_with_out_param(100, @result)"

# Recommended: switch to function call or temp table pattern
# --Sql "SELECT fn_get_result(100)"           # Recommended
# --Sql "CALL sp_write_to_tmp(100); SELECT * FROM tmp_result"  # Batch execution
```

#### Execution — CLI (Call Function)

```bash
# Scalar function (recommended)
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "SELECT fn_get_user_balance(12345)"

# Table-valued function
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "SELECT * FROM fn_get_orders_by_date('2024-01-01', '2024-12-31')"

# Function in WHERE / VALUES clause
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "UPDATE orders SET status = fn_normalize(old_status) WHERE date > '2024-01-01'"
```

#### Post-execution Validation (Proc/Func)

1. Function call: parse `$.AffectedRows` or capture query results
2. Stored procedure: check `$.RequestId` + `$.AffectedRows`; OUT parameter
   values are NOT guaranteed to be returned
3. If high-risk SQL is blocked → go to Failure Recovery

#### Failure Recovery (Call Procedure/Function)

| Error pattern | Agent Action |
| -------------- | -------------- |
| HighRiskSQL.Blocked | **HALT** — inform user which SQL was blocked; advise contacting admin for whitelist; do NOT auto-retry |
| SQLSyntaxError (proc/fn not found) | Check procedure/function name spelling; retry once |
| PermissionDenied | HALT; grant via GrantPermission or execute via ExecuteStatement with appropriate privilege |

### Operation: Database User Management (Physical DB User)

> **Note:** Distinct from DMS logical users (`CreateUser`), this runbook
  operates on physical users in the target database instance (`CREATE USER` /
  `GRANT` / `REVOKE` / `DROP USER`).
>
> **Safety Gate:** `CREATE USER` and `DROP USER` are **high-risk SQL**, blocked
  by DMS rule engine by default. Admin whitelist + user explicit confirmation
  required.

#### Pre-flight (Safety Gate — Required Confirmation)

| # | Check | Method | Expected | On Failure |
| --- | ------- | -------- | ---------- | ------------ |
| 1 | Database registered in DMS | `ListDatabases` confirms DbId | Found | HALT; register database first |
| 2 | User has DDL privilege | `ListPermissions --UserId` | Includes DDL or ALL | HALT; grant permission first |
| 3 | **Admin Whitelist Confirmation** | Notify user that `CREATE USER` is blocked by default | User confirms contact with admin | HALT; wait for whitelist |
| 4 | **User Explicit Confirmation** | Display full `CREATE USER` SQL to user | User agrees to execute | HALT |

#### Execution — CLI (DB User)

```bash
# Create database user (high-risk SQL — admin whitelist required)
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "CREATE USER 'app_user'@'%' IDENTIFIED BY 'secure_pwd_123'"

# Grant user privileges
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "GRANT SELECT, INSERT, UPDATE ON mydb.* TO 'app_user'@'%'"

# View user privileges
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "SHOW GRANTS FOR 'app_user'@'%'"

# Change password
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "ALTER USER 'app_user'@'%' IDENTIFIED BY 'new_secure_pwd'"

# Revoke privileges
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "REVOKE INSERT, UPDATE ON mydb.* FROM 'app_user'@'%'"

# Drop database user (high-risk SQL — admin whitelist + user explicit confirmation required)
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "DROP USER 'app_user'@'%'"
```

#### Post-execution Validation (Database User Management)

1. `SHOW GRANTS FOR 'user'@'host'` to verify grant result
2. Log `{{output.request_id}}` for audit
3. Confirm `$.AffectedRows` matches expected value

#### Failure Recovery (Database User Management)

| Error pattern | Agent Action |
| -------------- | -------------- |
| HighRiskSQL.Blocked | **HALT** — advise contacting DMS admin for whitelist; do NOT auto-retry |
| AccessDeniedForUser | Current connection user lacks `CREATE USER` / `GRANT` privilege; execute as admin |
| UserAlreadyExists | User already exists; prompt to rename or use `ALTER USER` |
| SyntaxError (password) | Password does not meet policy; adjust password complexity |

### Operation: Batch SQL Transaction

> Applies to scenarios requiring multiple SQL statements in a single DMS call
  (data migration, batch writes, multi-step operations).

#### Pre-flight (Batch)

| Check | Method | Expected | On Failure |
| ------- | -------- | ---------- | ------------ |
| SQL list confirmation | Display each SQL statement to user | User confirms each | HALT |
| Transaction isolation requirement | Ask if transaction needed (multiple SQL treated as atomic) | User declares | Mark as non-transactional mode |
| High-risk SQL scan | Check each for DROP/TRUNCATE/CREATE USER | All pass | HALT; add to whitelist if needed |

#### Execution — Non-Transactional Mode (Batch SQL)

```bash
# Multiple SQL statements separated by semicolons
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "INSERT INTO logs (msg) VALUES ('step1'); \
          UPDATE counters SET val = val + 1 WHERE name = 'migrate'; \
          INSERT INTO logs (msg) VALUES ('step3')"
```

#### Execution — Transactional Mode (BEGIN/COMMIT)

```bash
# Explicit transaction begin
aliyun dms ExecuteStatement \
 --DbId "{{user.database_id}}" \
 --Sql "BEGIN; \
          INSERT INTO orders (user_id, amount) VALUES (1, 100); \
          UPDATE inventory SET qty = qty - 1 WHERE sku = 'A001'; \
          COMMIT"
```

#### Post-execution Validation (Batch SQL)

1. Check `$.AffectedRows` — in transaction mode should equal sum of all
   statement affected rows
2. For SELECT queries, parse returned results
3. Log `{{output.request_id}}` for audit

#### Failure Recovery (Batch SQL)

| Error pattern | Agent Action |
| -------------- | -------------- |
| Middle SQL fails | Transaction mode → ROLLBACK auto; non-transactional → executed SQL NOT rolled back |
| Partial SQL blocked by high-risk rules | **HALT** — contact admin for whitelist then retry |
| Timeout | Split into individual ExecuteStatement calls |
| Syntax error (some SQL) | Locate failing SQL via error message; fix and resubmit |

### Operation: NL2SQL Query (Intelligent Query)

#### Pre-flight (NL2SQL)

| Check | Method | Expected | On Failure |
| ------- | -------- | ---------- | ------------ |
| User question | Validate is a query (SELECT) not write | Query intent | Clarify scope |
| Target database | Confirm DbId is in ListDatabases | Found | List databases first |

#### Execution — CLI (NL2SQL)

```bash
# Natural language to SQL query (via IntelligentQuery or equivalent API)
aliyun dms IntelligentQuery \
 --DbId "{{user.database_id}}" \
 --Question "{{user.natural_question}}"
```

#### Execution — JIT Go SDK (NL2SQL)

```go
request := &dms.IntelligentQueryRequest{
    DbId:     tea.String("{{user.database_id}}"),
    Question: tea.String("{{user.natural_question}}"),
}
resp, err := client.IntelligentQuery(request)
if err != nil {
    panic(err)
}
// resp.Body.GeneratedSql, resp.Body.ResultData
fmt.Println(tea.ToString(resp.Body))
```

#### Post-execution Validation (NL2SQL)

1. Present `{{output.generated_sql}}` to user for confirmation
2. If auto-execute enabled, run the generated SQL via ExecuteStatement
3. Present query results in human-readable format

### Operation: Grant Permission (Fine-Grained Permission Control)

> Supports instance/DB/table/column/row level access control.

#### Pre-flight (Grant Permission)

- Confirm grantee user exists (via ListUsers)
- Confirm target database/table exists

#### Execution — CLI (Grant Permission)

```bash
# Grant table-level read permission
aliyun dms GrantPermission \
 --UserId "{{user.user_id}}" \
 --ResourceList '[{"ResourceId":"{{user.table_id}}","ResourceType":"TABLE"}]' \
 --PermissionType "READ"
```

#### Execution — JIT Go SDK (Grant)

```go
request := &dms.GrantPermissionRequest{
    UserId: tea.String("{{user.user_id}}"),
    ResourceList: []*dms.GrantPermissionRequestResourceList{
        {ResourceId: tea.String("{{user.table_id}}"), ResourceType: tea.String("TABLE")},
    },
    PermissionType: tea.String("READ"),
}
resp, err := client.GrantPermission(request)
```

#### Post-execution Validation (Grant Permission)

- Call `ListPermissions` with user ID filter; confirm new permission appears

### Operation: Query SQL Audit Log

#### Execution — CLI (Query Audit Log)

```bash
# Query audit logs (time range: last 24h)
aliyun dms ListAuditLogs \
 --StartTime "$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)" \
 --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
 --DbId "{{user.database_id}}"
```

#### Post-execution (Query Audit Log)

Parse `$.AuditLogList[].Sql, UserId, ExecuteTime, AffectedRows`; present as
audit table.

### Operation: List Databases

#### Execution — CLI (List Databases)

```bash
# List all databases accessible to current user
aliyun dms ListDatabases --PageSize 50

# Filter by owner
aliyun dms ListDatabases --OwnerUserId "{{user.user_id}}" --PageSize 50
```

#### Post-execution (List Databases)

Parse `$.DatabaseList[].DbId, DbName, DbType, OwnerUserId`; present to user.

### Operation: Revoke Permission

#### Pre-flight (Revoke Permission)

- Confirm permission exists via `ListPermissions`
- Confirm target user and resource IDs

#### Execution — CLI (Revoke Permission)

```bash
aliyun dms RevokePermission \
 --UserId "{{user.user_id}}" \
 --ResourceList '[{"ResourceId":"{{user.table_id}}","ResourceType":"TABLE"}]'
```

#### Post-execution Validation (Revoke Permission)

- Call `ListPermissions` with user ID filter; confirm permission absent

### Operation: List Users

#### Execution — CLI (List Users)

```bash
# List all DMS users
aliyun dms ListUsers --PageSize 50

# Filter by role
aliyun dms ListUsers --RoleType "Developer" --PageSize 50
```

#### Post-execution (List Users)

Parse `$.UserList[].UserId, NickName, Role, LastLoginTime`; present as user
table.

### Operation: Sensitive Column Management

#### Mark Column as Sensitive

##### Pre-flight

- Confirm table exists and user has admin/DBA role
- Confirm column is not already marked

##### Execution — CLI

```bash
aliyun dms CreateSensitiveColumn \
 --TableId "{{user.table_id}}" \
 --ColumnName "{{user.column_name}}" \
 --SensitiveLevel "HIGH" # LOW | MEDIUM | HIGH
```

##### Post-execution

- Call `ListSensitiveColumns --TableId "{{user.table_id}}"`; confirm column
  appears

#### List Sensitive Columns

##### Execution — CLI (List Sensitive Columns)

```bash
aliyun dms ListSensitiveColumns \
 --DbId "{{user.database_id}}" \
 --TableId "{{user.table_id}}"
```

##### Post-execution (List Sensitive Columns)

Parse `$.SensitiveColumns[].ColumnName, SensitiveLevel`; present to user.

### Operation: Database Owner Transfer

#### Pre-flight (Owner)

- Confirm new owner user exists via `ListUsers`
- Confirm database exists via `ListDatabases`
- Confirm current user has admin role

#### Execution — CLI (Owner)

```bash
aliyun dms ChangeDatabaseOwner \
 --DbId "{{user.database_id}}" \
 --OwnerUserId "{{user.new_owner_user_id}}"
```

#### Post-execution Validation (Owner)

- Call `ListDatabases --DbId "{{user.database_id}}"`; verify `OwnerUserId`
  changed

### Operation: SQL Review (Approve/Reject Task)

#### Pre-flight (Review)

- Confirm LockerId exists and is in `Approving` state
- Confirm reviewer has approval authority

#### Approve SQL Task

```bash
aliyun dms ApproveResourceLocker \
 --LockerId "{{user.locker_id}}" \
 --ApproveComment "LGTM"
```

#### Reject SQL Task

```bash
aliyun dms RejectResourceLocker \
 --LockerId "{{user.locker_id}}" \
 --RejectReason "Need WHERE clause for UPDATE"
```

#### Post-execution Validation (Review)

- Call `GetResourceLocker --LockerId "{{user.locker_id}}"`; verify `Status`
  changed

### Operation: Get Execution Detail

#### Pre-flight (Exec Detail)

- Provide RequestId from ExecuteStatement response
- Or provide TaskId for async task tracking

#### Execution — CLI (Exec Detail)

```bash
aliyun dms GetExecutionDetail \
 --RequestId "{{user.request_id}}"

# Or by TaskId
aliyun dms GetTaskDetail \
 --TaskId "{{user.task_id}}"
```

#### Post-execution (Exec Detail)

Parse `$.Sql, $.UserId, $.ExecuteTime, $.AffectedRows, $.Status,
$.ErrorMessage`; present as execution record.

### Operation: Lock/Unlock Table

#### Lock Table (for maintenance)

```bash
aliyun dms LockDatabaseObject \
 --ResourceList '[{"ResourceId":"{{user.table_id}}","ResourceType":"TABLE"}]' \
 --LockType "EXCLUSIVE" # SHARED | EXCLUSIVE
```

#### Unlock Table

```bash
aliyun dms UnlockDatabaseObject \
 --ResourceList '[{"ResourceId":"{{user.table_id}}","ResourceType":"TABLE"}]'
```

#### Post-execution Validation (Lock)

- Call `GetDatabaseObjectLockStatus --ResourceId "{{user.table_id}}"`; verify
  lock state

### Operation: Register Database Instance

#### Pre-flight (Register)

- Confirm instance credentials (host, port, database, username, password)
- Confirm network connectivity (VPC or internet)

#### Execution — CLI (Register)

```bash
aliyun dms RegisterDatabase \
 --InstanceType "MySQL" \
 --Host "rm-xxx.cn-hangzhou.rds.aliyuncs.com" \
 --Port 3306 \
 --Database "appdb" \
 --UserName "dms_user" \
 --Password "{{env.DMS_DB_PASSWORD}}" \
 --EnvType "DEV" # DEV | TEST | PRE | PROD
```

#### Post-execution Validation (Register)

- Call `ListDatabases`; verify new database appears
- Confirm ownership assigned to requesting user

### Operation: Unregister Database Instance

> **Safety Gate:** MUST confirm this is intentional and all data is backed up.

#### Pre-flight (Unregister)

- Explicit user confirmation required
- Verify no active locks or pending tasks

#### Execution — CLI (Unregister)

```bash
aliyun dms UnregisterDatabase \
 --DbId "{{user.database_id}}"
```

#### Post-execution Validation (Unregister)

- Call `ListDatabases --DbId "{{user.database_id}}"`; expect 404 or empty

## Failure Taxonomy

| Error Code | Meaning | Agent Action |
| ------------ | --------- | -------------- |
| InvalidParameter | SQL/param syntax error | Fix; retry once |
| HighRiskSQL.Blocked | SQL violates high-risk rule | HALT; user modifies SQL |
| QuotaExceeded | Task/user quota exceeded | HALT; request increase |
| Unauthorized | RAM permission insufficient | HALT; add `dms:*` policy |
| InternalError | Server error | Retry 3x with backoff; HALT |
| ResourceNotFound | Database/task/user not found | Verify ID; list first |
| OrderNotAllow | Approval not granted | Submit for approval first |
| PermissionDenied | No DMS permission on target | GrantPermission first |
| DbTypeNotSupported | Unsupported DB type | HALT; use compatible DB |

## Reference Directory

- [Core Concepts](references/core-concepts.md) — Architecture,
  40+ supported data sources, permission model, NL2SQL
- [API & SDK Usage](references/api-sdk-usage.md) — Operation map,
  request/response, SDK package
- [CLI Usage](references/cli-usage.md) — Plugin install, command map,
  JMESPath extraction
- [Troubleshooting](references/troubleshooting.md) — Error codes,
  diagnostic order, recovery patterns
- [Integration](references/integration.md) — Go JIT bootstrap, SDK workspace,
  env vars
- [Well-Architected Assessment](references/well-architected-assessment.md) —
  Security, stability, cost, efficiency, performance

## Operational Best Practices

- **Least privilege**: Grant minimum required permission (column/row level when
  possible)
- **Approval first**: All write SQL must go through CreateResourceLocker
  approval flow
- **Audit always**: Log all ExecuteStatement calls with RequestId for
  traceability
- **NL2SQL for read**: Use IntelligentQuery for read-only natural language
  queries
- **High-risk SQL blocking**: DMS rule engine blocks dangerous SQL
  automatically; respect its decision

## Changelog

| Version | Date | Changes |
| --------- | ------ | --------- |
| 1.0.0 | 2026-07-14 | Initial DMS Enterprise skill — NL2SQL, SQL approval flow, fine-grained permissions, SQL audit, 40+ data source support |
| 1.1.0 | 2026-07-14 | Add 8 runbooks: RevokePermission, ListUsers, SensitiveColumn, OwnerTransfer, SQLReview, ExecutionDetail, LockTable, Register/UnregisterDatabase |
| 1.2.0 | 2026-07-14 | Add 3 runbooks: CallStoredProcedure/Function (with OUT/INOUT limits + high-risk gate), DatabaseUserMgmt (CREATE USER/GRANT), BatchSQLTransaction; expand CRUD Pre-flight + SQL classification table |
| 1.3.0 | 2026-07-14 | Convert to English (all Chinese text removed) |
