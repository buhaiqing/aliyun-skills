# Troubleshooting Guide — PolarDB MySQL

> Version: 1.1.0 | Last Updated: 2026-05-26

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

### Slow Query Specific Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| InvalidStartTime.Malformed | Invalid start time format | Use ISO 8601 format: `yyyy-MM-ddTHH:mmZ` |
| InvalidEndTime.Malformed | Invalid end time format | Use ISO 8601 format: `yyyy-MM-ddTHH:mmZ` |
| TimeRangeExceeded | Time range > 7 days | Split into multiple queries or reduce range |
| NoDataAvailable | No slow logs in time range | INFO: No slow queries found; check if audit log collector enabled |
| InvalidDBNodeId.NotFound | Node ID does not exist | Verify node ID via `DescribeDBNodes` |
| DBNodeId.Malformed | Invalid node ID format | Check node ID format |

## Diagnostic Order

1. Verify cluster exists: `aliyun polardb DescribeDBClusterAttribute --DBClusterId <id>`
2. Check cluster status: `DBClusterStatus` field — must be `Running` for most operations
3. Verify region consistency: `RegionId` matches across all calls
4. Check VPC/VSwitch: Confirm network resources exist in target region
5. Review CLI coverage: `aliyun help polardb` for available commands
6. For performance issues: Use `DescribeDBClusterPerformance` + CMS metrics
7. For SQL issues: Delegate to `alicloud-das-ops` for diagnosis
8. **For slow queries:** Verify audit log collector is enabled

## Common CLI Diagnostics

```bash
# Quick check — is the cluster running?
aliyun polardb DescribeDBClusterAttribute --DBClusterId "<id>" --output cols=DBClusterStatus,DBClusterDescription rows=DBClusterStatus,DBClusterDescription

# Check all nodes healthy
aliyun polardb DescribeDBNodes --DBClusterId "<id>" --output cols=DBNodeId,Role,HealthStatus rows=Items.DBDetail[].{DBNodeId,Role,HealthStatus}

# Check recent backups
aliyun polardb DescribeBackups --DBClusterId "<id>" --StartTime "<start>" --EndTime "<end>" --output cols=BackupId,BackupStatus rows=Items.Backup[].{BackupId,BackupStatus}

# Check if audit log collector enabled (required for slow query logging)
aliyun polardb DescribeDBClusterAuditLogCollector --DBClusterId "<id>"
```

## Slow Query Analysis Diagnostics

### 1. Verify Slow Query Logging is Enabled

```bash
# Check audit log collector status
aliyun polardb DescribeDBClusterAuditLogCollector \
  --DBClusterId "<cluster_id>" \
  --output cols=AuditLogStatus rows=AuditLogStatus

# Expected: AuditLogStatus = "Enable"
# If "Disable", slow query logging is not active
```

### 2. Test Slow Query Retrieval

```bash
# Quick test with 1-hour window
START_TIME=$(date -u -v-1H +"%Y-%m-%dT%H:%MZ")
END_TIME=$(date -u +"%Y-%m-%dT%H:%MZ")

aliyun polardb DescribeSlowLogs \
  --DBClusterId "<cluster_id>" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"
```

### 3. Troubleshoot Empty Results

| Symptom | Possible Cause | Solution |
|---------|---------------|----------|
| No data returned | Time range too narrow | Expand to at least 1 hour |
| No data returned | Audit log collector disabled | Enable via `ModifyDBClusterAuditLogCollector` |
| No data returned | No slow queries in range | Normal — no slow queries detected |
| Partial data | Pagination not handled | Iterate through all pages |
| Time format error | Wrong timestamp format | Use ISO 8601 UTC format |
| Range exceeded | > 7 days | Split into multiple queries |

### 4. Performance Considerations

```bash
# For large datasets, use smaller page sizes and longer intervals
aliyun polardb DescribeSlowLogRecords \
  --DBClusterId "<cluster_id>" \
  --StartTime "2024-11-20T00:00Z" \
  --EndTime "2024-11-21T00:00Z" \
  --PageSize 50 \
  --PageNumber 1

# Use specific node filtering to reduce data volume
aliyun polardb DescribeSlowLogRecords \
  --DBClusterId "<cluster_id>" \
  --DBNodeId "<node_id>" \
  --StartTime "<start>" \
  --EndTime "<end>"
```
