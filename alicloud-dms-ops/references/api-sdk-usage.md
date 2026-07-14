# API & SDK — DMS Enterprise

## OpenAPI

- Spec: DMS Enterprise API 2024-04-14
- Base path: `dms-enterprise.aliyuncs.com`
- Version: v1

## Go SDK Package

`github.com/alibabacloud-go/dms-enterprise-2024-04-14/v1/client`

## SDK Install

```bash
mkdir -p /tmp/aliyun-sdk-workspace && cd /tmp/aliyun-sdk-workspace
go mod init sdk-script
export GOPROXY="https://goproxy.cn,direct"
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/dms-enterprise-2024-04-14/v1/client
```

## Operations Map

| Goal | API Operation | SDK Method | Notes |
| ------ | -------------- | ------------ | ------- |
| Submit SQL task | CreateResourceLocker | CreateResourceLocker | Approval workflow |
| Check approval | GetResourceLocker | GetResourceLocker | Poll until Approved |
| Approve task | ApproveResourceLocker | ApproveResourceLocker | SQL review |
| Reject task | RejectResourceLocker | RejectResourceLocker | With reason |
| Execute SQL | ExecuteStatement | ExecuteStatement | Write operations |
| Query SQL | Query | Query | Read-only queries |
| Get execution detail | GetExecutionDetail | GetExecutionDetail | By RequestId |
| Get task detail | GetTaskDetail | GetTaskDetail | By TaskId |
| NL2SQL | IntelligentQuery | IntelligentQuery | Natural language |
| List databases | ListDatabases | ListDatabases | Pagination support |
| Register database | RegisterDatabase | RegisterDatabase | With credentials |
| Unregister database | UnregisterDatabase | UnregisterDatabase | Remove from DMS |
| Change owner | ChangeDatabaseOwner | ChangeDatabaseOwner | Transfer DB |
| Create user | CreateUser | CreateUser | With role |
| List users | ListUsers | ListUsers | Pagination |
| Grant permission | GrantPermission | GrantPermission | Fine-grained |
| Revoke permission | RevokePermission | RevokePermission | By ID |
| List permissions | ListPermissions | ListPermissions | Filter by user/DB |
| Query audit logs | ListAuditLogs | ListAuditLogs | Time-range filter |
| Mark sensitive column | CreateSensitiveColumn | CreateSensitiveColumn | Column-level |
| List sensitive columns | ListSensitiveColumns | ListSensitiveColumns | By DB |
| Lock table | LockDatabaseObject | LockDatabaseObject | Exclusive/SHARED |
| Unlock table | UnlockDatabaseObject | UnlockDatabaseObject | Release lock |
| Lock status | GetDatabaseObjectLockStatus | GetDatabaseObjectLockStatus | Check lock state |
| Call procedure | ExecuteStatement | ExecuteStatement | `CALL proc()` via Sql param |
| Call function | ExecuteStatement | ExecuteStatement | `SELECT fn()` via Sql param |
| CREATE USER | ExecuteStatement | ExecuteStatement | `CREATE USER ...` via Sql param (high-risk) |
| GRANT / REVOKE | ExecuteStatement | ExecuteStatement | Via Sql param |
| Batch SQL | ExecuteStatement | ExecuteStatement | Multi-statement via `;` or transaction |

## Common JSON Paths

```json
// CreateResourceLocker response
$.LockerId     → string, polling target
$.Status       → "Approving" | "Approved" | "Rejected"
$.CreateTime   → timestamp

// ExecuteStatement response
$.AffectedRows → int64
$.RequestId    → string, audit key

// ListDatabases response
$.DatabaseList[].DbId     → string
$.DatabaseList[].DbName   → string
$.DatabaseList[].DbType   → string (MySQL, PostgreSQL, etc.)
$.DatabaseList[].OwnerUserId → string

// IntelligentQuery response
$.GeneratedSql  → string, generated SQL (confirm before exec)
$.ResultData    → array, query results
$.Headers       → array, column names

// ListAuditLogs response
$.AuditLogList[].Sql          → string
$.AuditLogList[].UserId       → string
$.AuditLogList[].ExecuteTime  → timestamp
$.AuditLogList[].AffectedRows → int64
```

## Pagination

- PageSize: max 100 (default 20)
- PageNumber: 1-based
- TotalCount in response header

```go
request := &dms.ListDatabasesRequest{
    PageSize:   tea.Int32(50),
    PageNumber: tea.Int32(1),
}
```

## Idempotency

- CreateResourceLocker: Use Comment as idempotency key
- ExecuteStatement: Not idempotent; use TaskId for tracking
