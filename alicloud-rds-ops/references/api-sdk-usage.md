# API & SDK — Alibaba Cloud RDS

## OpenAPI

- **Product**: RDS
- **API Version**: 2014-08-15
- **Base Endpoint**: `rds.aliyuncs.com`
- **Official Docs**: https://www.alibabacloud.com/help/en/rds
- **OpenAPI Explorer**: https://api.aliyun.com/api/Rds/2014-08-15

## SDK Operations Map

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Create Instance | CreateDBInstance | `CreateDBInstance` | `aliyun rds CreateDBInstance` |
| Describe Instances | DescribeDBInstances | `DescribeDBInstances` | `aliyun rds DescribeDBInstances` |
| Restart Instance | RestartDBInstance | `RestartDBInstance` | `aliyun rds RestartDBInstance` |
| Delete Instance | DeleteDBInstance | `DeleteDBInstance` | `aliyun rds DeleteDBInstance` |
| Describe Accounts | DescribeAccounts | `DescribeAccounts` | `aliyun rds DescribeAccounts` |
| Create Account | CreateAccount | `CreateAccount` | `aliyun rds CreateAccount` |
| Describe Databases | DescribeDatabases | `DescribeDatabases` | `aliyun rds DescribeDatabases` |
| Describe Backups | DescribeBackups | `DescribeBackups` | `aliyun rds DescribeBackups` |
| Describe Slow Logs | DescribeSlowLogs | `DescribeSlowLogs` | `aliyun rds DescribeSlowLogs` |
| Describe Resource Usage | DescribeResourceUsage | `DescribeResourceUsage` | `aliyun rds DescribeResourceUsage` |
| Describe Performance | DescribeDBInstancePerformance | `DescribeDBInstancePerformance` | `aliyun rds DescribeDBInstancePerformance` |
| Describe HA Config | DescribeDBInstanceHAConfig | `DescribeDBInstanceHAConfig` | `aliyun rds DescribeDBInstanceHAConfig` |
| Modify Security IPs | ModifySecurityIps | `ModifySecurityIps` | `aliyun rds ModifySecurityIps` |
| Describe Parameters | DescribeParameters | `DescribeParameters` | `aliyun rds DescribeParameters` |
| Modify Parameter | ModifyParameter | `ModifyParameter` | `aliyun rds ModifyParameter` |
| Describe Regions | DescribeRegions | `DescribeRegions` | `aliyun rds DescribeRegions` |
| Describe Available Classes | DescribeAvailableClasses | `DescribeAvailableClasses` | `aliyun rds DescribeAvailableClasses` |
| Describe Available Resource | DescribeAvailableResource | `DescribeAvailableResource` | `aliyun rds DescribeAvailableResource` |
| Describe Instance Attribute | DescribeDBInstanceAttribute | `DescribeDBInstanceAttribute` | `aliyun rds DescribeDBInstanceAttribute` |
| Describe Net Info | DescribeDBInstanceNetInfo | `DescribeDBInstanceNetInfo` | `aliyun rds DescribeDBInstanceNetInfo` |
| Describe IP Array List | DescribeDBInstanceIPArrayList | `DescribeDBInstanceIPArrayList` | `aliyun rds DescribeDBInstanceIPArrayList` |
| Describe Binlog Files | DescribeBinlogFiles | `DescribeBinlogFiles` | `aliyun rds DescribeBinlogFiles` |
| Describe Error Logs | DescribeErrorLogs | `DescribeErrorLogs` | `aliyun rds DescribeErrorLogs` |
| Describe SQL Log Records | DescribeSQLLogRecords | `DescribeSQLLogRecords` | `aliyun rds DescribeSQLLogRecords` |
| Modify Instance Spec | ModifyDBInstanceSpec | `ModifyDBInstanceSpec` | `aliyun rds ModifyDBInstanceSpec` |
| Upgrade Engine Version | UpgradeDBInstanceEngineVersion | `UpgradeDBInstanceEngineVersion` | `aliyun rds UpgradeDBInstanceEngineVersion` |
| Describe Available Zones | DescribeAvailableZones | `DescribeAvailableZones` | `aliyun rds DescribeAvailableZones` |
| Create Database | CreateDatabase | `CreateDatabase` | `aliyun rds CreateDatabase` |
| Delete Database | DeleteDatabase | `DeleteDatabase` | `aliyun rds DeleteDatabase` |
| Delete Account | DeleteAccount | `DeleteAccount` | `aliyun rds DeleteAccount` |
| Describe Read-only Instances | DescribeReadDBInstances | `DescribeReadDBInstances` | `aliyun rds DescribeReadDBInstances` |
| Create Backup | CreateBackup | `CreateBackup` | `aliyun rds CreateBackup` |
| Restore DB Instance | RestoreDBInstance | `RestoreDBInstance` | `aliyun rds RestoreDBInstance` |

## SDK Package

```bash
go get github.com/alibabacloud-go/rds-20140815/v2/client
```

## Request / Response Notes

- **Pagination**: Many list APIs support `PageSize` and `PageNumber` parameters.
- **Time Format**: APIs expect `YYYY-MM-DDTHH:mm:ssZ` (ISO 8601 UTC) for time parameters.
- **RegionId**: Required for most operations; must match the instance's region.
- **DBInstanceId**: The primary identifier for instance-scoped operations.

## Common Metric Keys (DescribeDBInstancePerformance)

| Metric Key | Description |
|------------|-------------|
| MySQL_Sessions | Total connections |
| MySQL_ActiveSessions | Active connections |
| MySQL_TPS | Transactions per second |
| MySQL_QPS | Queries per second |
| MySQL_IOPS | I/O operations per second |
| MySQL_CPUUsage | CPU utilization (%) |
| MySQL_MemoryUsage | Memory utilization (%) |
| MySQL_InnoDBBufferRatio | InnoDB buffer pool hit ratio |
| MySQL_DiskUsage | Disk space usage (%) |

> Note: Metric keys vary by engine. PostgreSQL and SQL Server use different key names.
> Refer to official documentation for engine-specific metrics.
