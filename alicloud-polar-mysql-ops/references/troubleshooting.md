# Troubleshooting Guide — PolarDB MySQL

> Version: 1.0.0 | Last Updated: 2026-05-16

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| InvalidDBClusterId.NotFound | Cluster does not exist | Verify cluster ID; HALT |
| InvalidDBClusterId.Malform | Bad cluster ID format | Check format expected |
| InvalidParameter | Request parameter validation failed | Cross-check against OpenAPI spec |
| DBClusterQuotaExceeded | Cluster quota exceeded | HALT; raise quota request |
| InsufficientBalance | Insufficient account balance | HALT; user recharges |
| ResourceAlreadyExists | Resource already exists | Describe existing; reuse or rename |
| VPCIdNotFound | VPC not found | Delegate to `alicloud-vpc-ops` |
| VSwitchIdNotFound | VSwitch not found | Delegate to `alicloud-vpc-ops` |
| OperationDenied | Operation not permitted | Check cluster status; retry when valid |
| AccountNameAlreadyExists | Account already exists | Use different name |
| Throttling | Rate limit hit | Exponential backoff; max 3 retries |
| InternalError | Server-side error | Retry 3x; then HALT with RequestId |
| Forbidden.RAM | Insufficient IAM permissions | User adds RAM policy |

## Diagnostic Order

1. Verify cluster exists: `aliyun polardb DescribeDBClusterAttribute --DBClusterId <id>`
2. Check cluster status: `DBClusterStatus` field — must be `Running` for most operations
3. Verify region consistency: `RegionId` matches across all calls
4. Check VPC/VSwitch: Confirm network resources exist in target region
5. Review CLI coverage: `aliyun help polardb` for available commands
6. For performance issues: Use `DescribeDBClusterPerformance` + CMS metrics
7. For SQL issues: Delegate to `alicloud-das-ops` for diagnosis

## Common CLI Diagnostics

```bash
# Quick check — is the cluster running?
aliyun polardb DescribeDBClusterAttribute --DBClusterId "<id>" --output cols=DBClusterStatus,DBClusterDescription rows=DBClusterStatus,DBClusterDescription

# Check all nodes healthy
aliyun polardb DescribeDBNodes --DBClusterId "<id>" --output cols=DBNodeId,Role,HealthStatus rows=Items.DBDetail[].{DBNodeId,Role,HealthStatus}

# Check recent backups
aliyun polardb DescribeBackups --DBClusterId "<id>" --StartTime "<start>" --EndTime "<end>" --output cols=BackupId,BackupStatus rows=Items.Backup[].{BackupId,BackupStatus}
```
