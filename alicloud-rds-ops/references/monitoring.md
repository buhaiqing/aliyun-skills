# Monitoring Alibaba Cloud RDS

## Key Metrics

### Performance Metrics (via DescribeDBInstancePerformance)

#### MySQL Metrics

| Metric | Key | Unit | Threshold Suggestion |
|--------|-----|------|---------------------|
| CPU Usage | `MySQL_CPUUsage` | % | > 80% warning, > 95% critical |
| Memory Usage | `MySQL_MemoryUsage` | % | > 80% warning, > 95% critical |
| Total Sessions | `MySQL_Sessions` | count | > 80% of max_connections warning |
| Active Sessions | `MySQL_ActiveSessions` | count | Baseline + 50% warning |
| TPS | `MySQL_TPS` | count/sec | Baseline deviation |
| QPS | `MySQL_QPS` | count/sec | Baseline deviation |
| IOPS | `MySQL_IOPS` | count/sec | > 80% of max IOPS warning |
| InnoDB Buffer Hit Ratio | `MySQL_InnoDBBufferRatio` | % | < 95% warning |
| Disk Usage | `MySQL_DiskUsage` | % | > 80% warning, > 90% critical |
| InnoDB Data Reads | `MySQL_InnoDBDataRead` | bytes/sec | Baseline deviation |
| InnoDB Data Writes | `MySQL_InnoDBDataWritten` | bytes/sec | Baseline deviation |
| InnoDB Row Lock Waits | `MySQL_InnoDBRowLockWaits` | count/sec | > 10/sec warning |
| Threads Running | `MySQL_ThreadsRunning` | count | > 80% of max_connections warning |
| Threads Connected | `MySQL_ThreadsConnected` | count | > 80% of max_connections warning |

#### PostgreSQL Metrics

| Metric | Key | Unit | Threshold Suggestion |
|--------|-----|------|---------------------|
| CPU Usage | `Pg_CPUUsage` | % | > 80% warning, > 95% critical |
| Memory Usage | `Pg_MemoryUsage` | % | > 80% warning, > 95% critical |
| Total Connections | `Pg_Sessions` | count | > 80% of max_connections warning |
| Active Connections | `Pg_ActiveSessions` | count | Baseline + 50% warning |
| TPS | `Pg_TPS` | count/sec | Baseline deviation |
| QPS | `Pg_QPS` | count/sec | Baseline deviation |
| IOPS | `Pg_IOPS` | count/sec | > 80% of max IOPS warning |
| Buffer Cache Hit Ratio | `Pg_BufferHitRatio` | % | < 95% warning |
| Disk Usage | `Pg_DiskUsage` | % | > 80% warning, > 90% critical |
| Checkpoint Count | `Pg_CheckpointCount` | count/sec | > baseline + 50% warning |
| Deadlock Count | `Pg_DeadlockCount` | count | > 0 warning |
| Temp File Size | `Pg_TempFileSize` | bytes | > 100MB warning |
| Replication Lag | `Pg_ReplicationLag` | seconds | > 30s warning, > 300s critical |

#### SQL Server Metrics

| Metric | Key | Unit | Threshold Suggestion |
|--------|-----|------|---------------------|
| CPU Usage | `MSSQL_CPUUsage` | % | > 80% warning, > 95% critical |
| Memory Usage | `MSSQL_MemoryUsage` | % | > 80% warning, > 95% critical |
| Total Connections | `MSSQL_Sessions` | count | > 80% of max_connections warning |
| Active Connections | `MSSQL_ActiveSessions` | count | Baseline + 50% warning |
| Transactions/sec | `MSSQL_Transactions` | count/sec | Baseline deviation |
| Batch Requests/sec | `MSSQL_BatchRequests` | count/sec | Baseline deviation |
| IOPS | `MSSQL_IOPS` | count/sec | > 80% of max IOPS warning |
| Buffer Cache Hit Ratio | `MSSQL_BufferCacheHitRatio` | % | < 95% warning |
| Disk Usage | `MSSQL_DiskUsage` | % | > 80% warning, > 90% critical |
| Page Life Expectancy | `MSSQL_PageLifeExpectancy` | seconds | < 300s warning |
| Lock Waits/sec | `MSSQL_LockWaits` | count/sec | > 10/sec warning |
| Blocked Processes | `MSSQL_BlockedProcesses` | count | > 5 warning |
| TempDB Usage | `MSSQL_TempDBUsage` | % | > 80% warning |

### Error Logs (via DescribeErrorLogs)

| Metric | Path | Unit | Threshold Suggestion |
|--------|------|------|---------------------|
| Error Count | `$.Items.ErrorLog[]` | count | > 0 warning (investigate) |
| Error Rate | — | count/hour | > 10/hour critical |
| Lock Wait Timeout | `$.Items.ErrorLog[].ErrorInfo` | count | > 5/hour warning |
| Deadlock | `$.Items.ErrorLog[].ErrorInfo` | count | > 0 critical |
| Replication Error | `$.Items.ErrorLog[].ErrorInfo` | count | > 0 critical |

### SQL Audit (via DescribeSQLLogRecords)

| Metric | Path | Unit | Threshold Suggestion |
|--------|------|------|---------------------|
| Slow SQL Count | `$.Items.SQLRecord[]` | count | > 100/hour warning |
| High Latency SQL | `$.Items.SQLRecord[].Latency` | us | > 1000000us (1s) warning |
| Error SQL Count | `$.Items.SQLRecord[].ReturnStatus` | count | > 10/hour warning |
| Full Table Scan SQL | `$.Items.SQLRecord[].SQLText` | count | > 50/hour warning |

### Resource Usage (via DescribeResourceUsage)

| Metric | Path | Unit | Threshold Suggestion |
|--------|------|------|---------------------|
| Disk Used | `$.DiskUsed` | MB | Monitor growth rate |
| Data Size | `$.DataSize` | MB | Monitor growth rate |
| Log Size | `$.LogSize` | MB | Monitor growth rate |
| Backup Size | `$.BackupSize` | MB | Monitor backup storage costs |
| Disk Usage % | `DiskUsed / DBInstanceStorage * 100` | % | > 80% warning, > 90% critical |

## Alert Example (CloudMonitor)

```json
{
  "RuleName": "RDS-CPU-High",
  "MetricName": "MySQL_CPUUsage",
  "Namespace": "acs_rds_dashboard",
  "Dimensions": [
    {
      "DBInstanceId": "{{user.db_instance_id}}"
    }
  ],
  "ComparisonOperator": "GreaterThanThreshold",
  "Threshold": 80,
  "EvaluationCount": 3,
  "ContactGroups": ["dba-team"]
}
```

## Multi-Dimensional Alert Rules

### Composite Alert: CPU + Connections + Slow Queries

```json
{
  "RuleName": "RDS-Performance-Degradation",
  "Conditions": [
    {
      "MetricName": "MySQL_CPUUsage",
      "Threshold": 80,
      "Duration": 300
    },
    {
      "MetricName": "MySQL_Sessions",
      "Threshold": 80,
      "Duration": 300
    }
  ],
  "Logic": "AND",
  "Action": "TriggerDiagnosisWorkflow"
}
```

### Composite Alert: Disk + Backup Failure

```json
{
  "RuleName": "RDS-Capacity-Risk",
  "Conditions": [
    {
      "MetricName": "MySQL_DiskUsage",
      "Threshold": 85,
      "Duration": 600
    }
  ],
  "AdditionalCheck": "DescribeBackups status in last 24h",
  "Action": "TriggerCapacityDiagnosis"
}
```

## Monitoring Best Practices

1. **Baseline establishment**: Collect metrics for 1-2 weeks to establish normal patterns.
2. **Multi-dimensional alerts**: Combine CPU + connections + disk for comprehensive coverage.
3. **Slow query monitoring**: Schedule regular `DescribeSlowLogs` analysis.
4. **Backup monitoring**: Verify automated backups succeed daily via `DescribeBackups`.
5. **Replication monitoring**: For HA instances, monitor sync mode and replication lag.
6. **Capacity planning**: Track disk growth rate and project when expansion is needed.
7. **Engine-specific monitoring**: Use engine-specific metric keys for accurate alerting.
8. **Correlation analysis**: When multiple alerts fire, use the correlation matrix in alert-diagnosis.md.
