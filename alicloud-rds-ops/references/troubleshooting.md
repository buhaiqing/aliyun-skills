# Troubleshooting Alibaba Cloud RDS

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `InvalidParameter` / 400 | Request failed validation | Align body with OpenAPI; check parameter types and ranges |
| `InvalidDBInstanceId.NotFound` / 404 | DB instance does not exist | Verify DBInstanceId; check region |
| `Forbidden.RAM` / 403 | Insufficient RAM permissions | User adds RAM policy with required RDS permissions |
| `DBInstanceLocked` / 400 | Instance is locked (e.g., expired) | Check instance status; renew if expired |
| `QuotaExceeded.DBInstance` / 400 | DB instance quota exceeded | HALT; user raises quota or deletes unused instances |
| `InsufficientBalance` / 400 | Account balance insufficient | HALT; user adds funds |
| `DBInstanceAlreadyExists` / 400 | Instance with same name exists | Ask reuse vs new name |
| `InvalidAccountName.Duplicate` / 400 | Account name already exists | Choose different account name |
| `InvalidSecurityIPList.Duplicate` / 400 | IP already in whitelist | Skip or remove existing entry first |
| `InternalError` / 500 | Server-side error | Retry with backoff; then HALT with RequestId |
| `Throttling` / 429 | Rate limit exceeded | Back off exponentially; respect Retry-After header |
| `InvalidEngineVersion.NotSupported` / 400 | Engine version not supported | Check available versions via DescribeAvailableClasses |
| `InvalidVPCId.NotFound` / 404 | VPC does not exist | Verify VPCId; delegate to `alicloud-vpc-ops` |
| `InvalidVSwitchId.NotFound` / 404 | VSwitch does not exist | Verify VSwitchId; delegate to `alicloud-vpc-ops` |
| `InvalidBackupId.NotFound` / 404 | Backup does not exist | Verify BackupId; check time range in DescribeBackups |
| `DBInstanceStatus.NotSupported` / 400 | Operation not supported in current status | Wait for instance to reach Running status |
| `InvalidParameter.ResourceNotFound` / 400 | Resource not found | Verify resource ID and region |
| `BackupFailed` / 500 | Backup creation failed | Retry; check instance status and storage space |

## Diagnostic Order

1. **Verify instance exists**: `aliyun rds DescribeDBInstances --DBInstanceId {{user.db_instance_id}}`
2. **Check instance status**: Look for `DBInstanceStatus` in response
3. **Check region consistency**: Ensure `RegionId` matches instance region
4. **Verify credentials**: `aliyun rds DescribeRegions` should succeed
5. **Check RAM permissions**: Ensure policy includes required RDS actions
6. **Check network access**: Verify SecurityIPList includes client IP
7. **Check quota**: `aliyun rds DescribeAvailableResource --RegionId {{user.region}}`
8. **Review error RequestId**: Include in support tickets for server-side errors

## Connection Issues

| Symptom | Possible Cause | Resolution |
|---------|---------------|------------|
| Connection timeout | SecurityIPList blocks client IP | Add client IP to whitelist |
| Connection refused | Instance not in `Running` status | Wait for instance to become Running |
| Authentication failed | Wrong account/password | Reset password or verify credentials |
| SSL required | SSL enforcement enabled | Use SSL connection or disable SSL requirement |

## Performance Issues

| Symptom | Diagnostic Steps |
|---------|-----------------|
| High CPU | Check `MySQL_CPUUsage` metric; analyze slow queries |
| High Memory | Check `MySQL_MemoryUsage` metric; review buffer pool settings |
| High Connections | Check `MySQL_Sessions` vs max_connections parameter |
| Slow Queries | Run `DescribeSlowLogs` for the affected time range |
| Disk Full | Check `DescribeResourceUsage`; expand storage or clean up |
| Replication Lag | Check `DescribeDBInstanceHAConfig` for sync mode and lag |

## Backup Issues

| Symptom | Possible Cause | Resolution |
|---------|---------------|------------|
| Backup failed | Insufficient storage | Free up space or expand storage |
| Backup not found | Wrong time range | Adjust StartTime/EndTime in DescribeBackups |
| Restore failed | Incompatible engine version | Verify target instance supports backup version |
