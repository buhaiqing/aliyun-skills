# Well-Architected Assessment — DMS

## Security Pillar

| Control | Implementation |
| --------- | --------------- |
| Least privilege | RAM policy: `dms:CreateResourceLocker,dms:ExecuteStatement,dms:ListDatabases` only; avoid `dms:*` |
| Credential masking | Never echo AK/SK; verify existence only |
| Fine-grained access | Use column/row level permissions for sensitive data |
| High-risk SQL blocking | DMS rule engine auto-blocks dangerous SQL (DROP, TRUNCATE, DELETE without WHERE, CREATE/DROP USER) |
| SQL audit trail | Log all ExecuteStatement calls with RequestId |
| Intranet access | Data never leaves VPC via DMS agent |
| Sensitive column protection | Mark columns via CreateSensitiveColumn; enforce masking |
| Table lock | Use LockDatabaseObject before maintenance; prevent concurrent writes |
| Owner transfer | Verify new owner has appropriate role before ChangeDatabaseOwner |
| Stored procedure/function | Verify `CALL` against high-risk rules; admin whitelist required for sensitive procs |
| Database user ops | Always require explicit user confirmation + admin whitelist for `CREATE USER` / `DROP USER` |
| Batch SQL transaction | Prefer transaction mode for atomicity; log each batch's RequestId |

## Stability Pillar

| Control | Implementation |
| --------- | --------------- |
| Approval workflow | All write SQL must go through CreateResourceLocker → approval |
| Backup before execution | Recommend checking recent backup via ListBackupPolicy before destructive SQL |
| Idempotency | Use LockerId for polling; handle OrderNotAllow gracefully |
| DR runbook | ListAuditLogs for last 24h; know which DBs are critical |
| Maintenance window | Check DescribeInstanceLifeCycle before production changes |
| Table lock pattern | Lock before schema changes; unlock after; handle LockConflict errors |
| Register/Unregister | Verify instance connectivity before register; confirm no active tasks before unregister |

## Cost Pillar

| Control | Implementation |
| --------- | --------------- |
| Task quota | Default 100/day; configure per user to avoid runaway automation |
| Concurrent execution | 10 per instance; use semaphore pattern for batch |
| Read vs write | Use Query (read-only) vs ExecuteStatement; appropriate cost allocation |
| NL2SQL for ad-hoc | Use IntelligentQuery instead of manual SQL for exploration |

## Efficiency Pillar

| Control | Implementation |
| --------- | --------------- |
| Batch operations | ListDatabases/ListUsers with pagination |
| Approval polling | 10s interval, max 300s; don't poll faster |
| Automation | Script repeated approvals via GetResourceLocker polling |
| Multi-source query | Single NL2SQL query across multiple DBs via DMS |

## Performance Pillar

| Metric | Threshold |
| -------- | ----------- |
| Approval polling interval | 10s |
| Execution check interval | 5s |
| Max wait for approval | 300s |
| Max concurrent executions | 10 per instance |
| Query timeout | 300s for read, 60s for write |
