# CLI — DMS Enterprise (`aliyun dms`)

## Install DMS Plugin

```bash
aliyun plugin install --names aliyun-cli-dms
```

Verify:

```bash
aliyun dms --help
```

## Conventions

- Output is **JSON by default** — no `--output json` needed
- DMS CLI uses API-style invocation: `aliyun dms <ApiName> --Param value`
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- Use `--waiter` for polling (if supported)

## CLI vs API Coverage

| Operation | CLI Support | Notes |
| ----------- | ------------- | ------- |
| CreateResourceLocker | Yes | With plugin |
| GetResourceLocker | Yes | With plugin |
| ApproveResourceLocker | Yes | With plugin |
| RejectResourceLocker | Yes | With plugin |
| ExecuteStatement | Yes | With plugin |
| GetExecutionDetail | Yes | With plugin |
| GetTaskDetail | Yes | With plugin |
| Query | Yes | With plugin |
| IntelligentQuery | Yes | NL2SQL |
| ListDatabases | Yes | With plugin |
| RegisterDatabase | Yes | With plugin |
| UnregisterDatabase | Yes | With plugin |
| ChangeDatabaseOwner | Yes | With plugin |
| CreateUser | Yes | With plugin |
| ListUsers | Yes | With plugin |
| GrantPermission | Yes | With plugin |
| RevokePermission | Yes | With plugin |
| ListPermissions | Yes | With plugin |
| ListAuditLogs | Yes | With plugin |
| CreateSensitiveColumn | Yes | With plugin |
| ListSensitiveColumns | Yes | With plugin |
| LockDatabaseObject | Yes | With plugin |
| UnlockDatabaseObject | Yes | With plugin |
| GetDatabaseObjectLockStatus | Yes | With plugin |

## Command Examples

```bash
# === SQL Approval Workflow ===

# Submit SQL task for approval
aliyun dms CreateResourceLocker \
  --ResourceList '[{"ResourceId":"db-001","ResourceType":"DATABASE"}]' \
  --Comment "Update user status"

# Check approval status
aliyun dms GetResourceLocker --LockerId "locker-xxx"

# Approve SQL task
aliyun dms ApproveResourceLocker \
  --LockerId "locker-xxx" \
  --ApproveComment "LGTM, approved"

# Reject SQL task
aliyun dms RejectResourceLocker \
  --LockerId "locker-xxx" \
  --RejectReason "Need WHERE clause for UPDATE"

# === SQL Execution ===

# Execute SQL (after approval)
aliyun dms ExecuteStatement \
  --DbId "db-001" \
  --Sql "UPDATE users SET status=1 WHERE id=100"

# Query (read-only)
aliyun dms Query \
  --DbId "db-001" \
  --Sql "SELECT * FROM users LIMIT 10"

# Get execution detail by RequestId
aliyun dms GetExecutionDetail --RequestId "request-xxx"

# === NL2SQL ===

# Natural language to SQL query
aliyun dms IntelligentQuery \
  --DbId "db-001" \
  --Question "What are the top 10 users by order count?"

# === Database Management ===

# List databases
aliyun dms ListDatabases --PageSize 50

# Register new database instance
aliyun dms RegisterDatabase \
  --InstanceType "MySQL" \
  --Host "rm-xxx.cn-hangzhou.rds.aliyuncs.com" \
  --Port 3306 \
  --Database "appdb" \
  --UserName "dms_user" \
  --Password "${DMS_DB_PASSWORD}" \
  --EnvType "DEV"

# Change database owner
aliyun dms ChangeDatabaseOwner \
  --DbId "db-001" \
  --OwnerUserId "user-new-owner"

# === User & Permission Management ===

# List all users
aliyun dms ListUsers --PageSize 50

# Create DMS user
aliyun dms CreateUser \
  --UserId "user-xxx" \
  --Role "Developer" \
  --NickName "John Doe"

# Grant table-level read permission
aliyun dms GrantPermission \
  --UserId "user-xxx" \
  --ResourceList '[{"ResourceId":"table-xxx","ResourceType":"TABLE"}]' \
  --PermissionType "READ"

# Revoke permission
aliyun dms RevokePermission \
  --UserId "user-xxx" \
  --ResourceList '[{"ResourceId":"table-xxx","ResourceType":"TABLE"}]'

# List user permissions
aliyun dms ListPermissions --UserId "user-xxx"

# === Sensitive Column Management ===

# Mark column as sensitive
aliyun dms CreateSensitiveColumn \
  --TableId "table-xxx" \
  --ColumnName "phone_number" \
  --SensitiveLevel "HIGH"

# List sensitive columns in table
aliyun dms ListSensitiveColumns \
  --DbId "db-001" \
  --TableId "table-xxx"

# === Table Lock ===

# Lock table exclusively (maintenance)
aliyun dms LockDatabaseObject \
  --ResourceList '[{"ResourceId":"table-xxx","ResourceType":"TABLE"}]' \
  --LockType "EXCLUSIVE"

# Unlock table
aliyun dms UnlockDatabaseObject \
  --ResourceList '[{"ResourceId":"table-xxx","ResourceType":"TABLE"}]'

# Check lock status
aliyun dms GetDatabaseObjectLockStatus \
  --ResourceList '[{"ResourceId":"table-xxx","ResourceType":"TABLE"}]'

# === Audit & Security ===

# Query audit logs (last 24h)
aliyun dms ListAuditLogs \
  --StartTime "$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --DbId "db-001"

# === JMESPath Examples ===

# Extract database names
aliyun dms ListDatabases --PageSize 50 \
  --output cols=DbName,DbType rows=DatabaseList[].DbName,DatabaseList[].DbType

# Extract user IDs and roles
aliyun dms ListUsers --PageSize 50 \
  --output cols=UserId,Role rows=UserList[].UserId,UserList[].Role

# Extract audit SQL content
aliyun dms ListAuditLogs --DbId "db-001" \
  --output cols=Sql,UserId,ExecuteTime rows=AuditLogList[].Sql,AuditLogList[].UserId,AuditLogList[].ExecuteTime
```

## CRUD / Procedure / Function Examples

```bash
# SELECT (read-only, no approval)
aliyun dms ExecuteStatement --DbId "db-001" --Sql "SELECT * FROM users LIMIT 10"

# INSERT (write, requires approval)
aliyun dms ExecuteStatement --DbId "db-001" --Sql "INSERT INTO orders (user_id, amount) VALUES (1, 99.9)"

# UPDATE (with WHERE; without WHERE = blocked by rule engine)
aliyun dms ExecuteStatement --DbId "db-001" --Sql "UPDATE users SET status=1 WHERE id=100"

# DELETE (with WHERE)
aliyun dms ExecuteStatement --DbId "db-001" --Sql "DELETE FROM logs WHERE created_at < '2024-01-01'"

# DDL (ALTER TABLE — high-risk, admin whitelist may be required)
aliyun dms ExecuteStatement --DbId "db-001" --Sql "ALTER TABLE users ADD COLUMN phone VARCHAR(20)"

# Call stored procedure (no OUT params)
aliyun dms ExecuteStatement --DbId "db-001" --Sql "CALL sp_monthly_report(2024, 12)"

# Call function (recommended; returns value)
aliyun dms ExecuteStatement --DbId "db-001" --Sql "SELECT fn_get_user_balance(12345)"

# Call table-valued function
aliyun dms ExecuteStatement --DbId "db-001" --Sql "SELECT * FROM fn_get_orders_by_date('2024-01-01', '2024-12-31')"

# Database user (high-risk — needs admin whitelist + user confirmation)
aliyun dms ExecuteStatement --DbId "db-001" --Sql "CREATE USER 'app_user'@'%' IDENTIFIED BY 'secure_pwd'"

# GRANT privileges
aliyun dms ExecuteStatement --DbId "db-001" --Sql "GRANT SELECT, INSERT ON mydb.* TO 'app_user'@'%'"

# Show grants
aliyun dms ExecuteStatement --DbId "db-001" --Sql "SHOW GRANTS FOR 'app_user'@'%'"

# Batch SQL (non-transactional)
aliyun dms ExecuteStatement --DbId "db-001" \
  --Sql "INSERT INTO logs (msg) VALUES ('step1'); UPDATE counters SET val=val+1 WHERE name='migrate';"

# Batch SQL (transactional)
aliyun dms ExecuteStatement --DbId "db-001" \
  --Sql "BEGIN; INSERT INTO orders VALUES (1, 100); UPDATE inventory SET qty=qty-1 WHERE sku='A001'; COMMIT"
```

> **Important:** `CALL` and `CREATE USER` may be blocked by DMS high-risk rule
  engine. The agent must request explicit user confirmation and admin whitelist
  before executing.

## Waiter Pattern (Polling Approval)

```bash
# Poll until approved (max 300s, 10s interval)
for i in $(seq 1 30); do
  STATUS=$(aliyun dms GetResourceLocker --LockerId "locker-xxx" 2>/dev/null | \
    jq -r '.Status')
  if [ "$STATUS" = "Approved" ]; then
    echo "Approved"
    break
  elif [ "$STATUS" = "Rejected" ]; then
    echo "Rejected"
    exit 1
  fi
  sleep 10
done
```
