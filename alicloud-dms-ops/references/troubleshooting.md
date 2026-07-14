# Troubleshooting DMS

## Common Error Codes

| Code | Meaning | Agent Action |
| ------ | --------- | -------------- |
| InvalidParameter | SQL syntax or param error | Fix SQL syntax; retry once |
| HighRiskSQL.Blocked | SQL violates high-risk rule | HALT; user modifies SQL; contact admin |
| QuotaExceeded | Daily task or user quota exceeded | HALT; request quota increase |
| Unauthorized | RAM permission insufficient | HALT; add `dms:*` RAM policy |
| InternalError | Server error | Retry 3x (2s, 4s, 8s backoff); HALT |
| ResourceNotFound | Database/task/user/table not found | Verify ID via ListDatabases/Users |
| OrderNotAllow | Approval not granted | Submit for approval first via CreateResourceLocker |
| PermissionDenied | No DMS permission on target | GrantPermission first |
| DbTypeNotSupported | Unsupported DB type for this operation | HALT; use compatible DB type |
| ConnectionFailed | Cannot connect to target database | Check DB status; verify network/VPC |
| SqlSyntaxError | SQL has syntax errors | Fix SQL; retry once |
| SensitiveColumnAccessDenied | Accessing protected sensitive column | HALT; request admin to grant |
| LockConflict | Table already locked by another session | Wait or use UnlockDatabaseObject |
| OwnerNotAllowed | Cannot transfer to specified user | Verify user exists and has appropriate role |
| UserAlreadyExists | User with this ID already exists | Use existing user or specify different ID |
| DatabaseAlreadyRegistered | Database already registered in DMS | Use existing DbId or unregister first |
| LockNotFound | No active lock on specified object | Verify lock ID or table ID |
| ApproveNotAllowed | User not authorized to approve | HALT; request admin to approve |
| RejectNotAllowed | User not authorized to reject | HALT; request admin to reject |
| AccessDeniedForUser | Current DB user lacks CREATE USER/GRANT privilege | HALT; switch to admin account or grant privilege first |
| UserAlreadyExists (DB) | DB user already exists | Use ALTER USER or rename |
| ProcOrFuncNotFound | Procedure/function not found | Verify spelling; query information_schema first |
| OutParamNotReturned | OUT parameter value not in ExecuteStatement response | Switch to SELECT fn() or temp table pattern |

## Diagnostic Order

1. **Verify credentials**: `test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID"`
2. **Check DMS plugin**: `aliyun dms --help`
3. **List accessible databases**: `aliyun dms ListDatabases --PageSize 50`
4. **Check user permissions**: `aliyun dms ListPermissions --UserId "<user_id>"`
5. **Verify task status**: `aliyun dms GetResourceLocker --LockerId
   "<locker_id>"`
6. **Query audit logs**: `aliyun dms ListAuditLogs --DbId "<db_id>" --StartTime
   "..." --EndTime "..."`

## Recovery Patterns

### Approval Pending

- Poll GetResourceLocker every 10s, max 300s
- If timeout: report to user; suggest manual approval in console

### High-Risk SQL Blocked

- Show user which rule was triggered
- Suggest safer alternatives (add WHERE, use SELECT before DELETE, etc.)
- If truly needed: contact DMS admin to whitelist

### Permission Denied

- Guide user to request permission from database owner
- Or: use GrantPermission with admin credentials

### Execution Failed

- Log RequestId for audit
- Suggest GetExecutionDetail or ListAuditLogs for diagnosis
- Check if database is in maintenance window

## High-Risk SQL Rules

DMS rule engine blocks:

- `DROP TABLE` / `DROP DATABASE` without confirmation
- `TRUNCATE` without WHERE
- `DELETE` without WHERE clause
- `UPDATE` without WHERE clause
- `ALTER TABLE` adding columns with default
- Bulk DELETE affecting > 10,000 rows (configurable threshold)
