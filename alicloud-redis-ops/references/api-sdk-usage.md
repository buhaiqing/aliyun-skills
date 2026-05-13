# API & SDK — Alibaba Cloud Redis / Tair (KVStore)

## OpenAPI

- **Product**: R-kvstore (Redis / Tair / KVStore)
- **API Version**: 2015-01-01
- **Base Endpoint**: `r-kvstore.aliyuncs.com`
- **Official Docs**: https://www.alibabacloud.com/help/en/redis
- **OpenAPI Explorer**: https://api.aliyun.com/api/R-kvstore/2015-01-01

## SDK Operations Map

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Create Instance | CreateInstance | `CreateInstance` | `aliyun r-kvstore create-instance` |
| Describe Instances | DescribeInstances | `DescribeInstances` | `aliyun r-kvstore describe-instances` |
| Describe Instance Attribute | DescribeInstanceAttribute | `DescribeInstanceAttribute` | `aliyun r-kvstore describe-instance-attribute` |
| Restart Instance | RestartInstance | `RestartInstance` | `aliyun r-kvstore restart-instance` |
| Delete Instance | DeleteInstance | `DeleteInstance` | `aliyun r-kvstore delete-instance` |
| Modify Instance Spec | ModifyInstanceSpec | `ModifyInstanceSpec` | `aliyun r-kvstore modify-instance-spec` |
| Describe Accounts | DescribeAccounts | `DescribeAccounts` | `aliyun r-kvstore describe-accounts` |
| Create Account | CreateAccount | `CreateAccount` | `aliyun r-kvstore create-account` |
| Delete Account | DeleteAccount | `DeleteAccount` | `aliyun r-kvstore delete-account` |
| Reset Account Password | ResetAccountPassword | `ResetAccountPassword` | `aliyun r-kvstore reset-account-password` |
| Describe Backups | DescribeBackups | `DescribeBackups` | `aliyun r-kvstore describe-backups` |
| Create Backup | CreateBackup | `CreateBackup` | `aliyun r-kvstore create-backup` |
| Restore Instance | RestoreInstance | `RestoreInstance` | `aliyun r-kvstore restore-instance` |
| Describe Security IPs | DescribeSecurityIps | `DescribeSecurityIps` | `aliyun r-kvstore describe-security-ips` |
| Modify Security IPs | ModifySecurityIps | `ModifySecurityIps` | `aliyun r-kvstore modify-security-ips` |
| Describe Parameters | DescribeParameters | `DescribeParameters` | `aliyun r-kvstore describe-parameters` |
| Modify Parameter | ModifyParameter | `ModifyParameter` | `aliyun r-kvstore modify-parameter` |
| Describe Slow Logs | DescribeSlowLogs | `DescribeSlowLogs` | `aliyun r-kvstore describe-slow-logs` |
| Describe History Monitor Values | DescribeHistoryMonitorValues | `DescribeHistoryMonitorValues` | `aliyun r-kvstore describe-history-monitor-values` |
| Describe Monitor Items | DescribeMonitorItems | `DescribeMonitorItems` | `aliyun r-kvstore describe-monitor-items` |
| Describe Intranet Attribute | DescribeIntranetAttribute | `DescribeIntranetAttribute` | `aliyun r-kvstore describe-intranet-attribute` |
| Modify Intranet Bandwidth | ModifyIntranetBandwidth | `ModifyIntranetBandwidth` | `aliyun r-kvstore modify-intranet-bandwidth` |
| Describe Regions | DescribeRegions | `DescribeRegions` | `aliyun r-kvstore describe-regions` |
| Describe Zones | DescribeZones | `DescribeZones` | `aliyun r-kvstore describe-zones` |
| Describe Available Resource | DescribeAvailableResource | `DescribeAvailableResource` | `aliyun r-kvstore describe-available-resource` |
| Migrate To Other Zone | MigrateToOtherZone | `MigrateToOtherZone` | `aliyun r-kvstore migrate-to-other-zone` |
| Modify Instance Maintain Time | ModifyInstanceMaintainTime | `ModifyInstanceMaintainTime` | `aliyun r-kvstore modify-instance-maintain-time` |
| Modify Instance SSL | ModifyInstanceSSL | `ModifyInstanceSSL` | `aliyun r-kvstore modify-instance-ssl` |
| Describe Engine Version | DescribeEngineVersion | `DescribeEngineVersion` | `aliyun r-kvstore describe-engine-version` |
| Upgrade Minor Version | UpgradeMinorVersion | `UpgradeMinorVersion` | `aliyun r-kvstore upgrade-minor-version` |
| Flush Instance | FlushInstance | `FlushInstance` | `aliyun r-kvstore flush-instance` |

## SDK Package

```bash
go get github.com/alibabacloud-go/r-kvstore-20150101/v2/client
```

## Request / Response Notes

- **Pagination**: Many list APIs support `PageSize` and `PageNumber` parameters.
- **Time Format**: APIs expect `YYYY-MM-DDTHH:mm:ssZ` (ISO 8601 UTC) for time parameters.
- **RegionId**: Required for most operations; must match the instance's region.
- **InstanceId**: The primary identifier for instance-scoped operations.
- **Token**: Use UUID v4 for idempotency on write operations; reuse within 24 hours for retries.

## Common Metric Keys (DescribeHistoryMonitorValues)

| Metric Key | Description |
|------------|-------------|
| `UsedMemory` | Used memory (bytes) |
| `UsedConnection` | Used connections (count) |
| `UsedQPS` | Queries per second |
| `CpuUsage` | CPU utilization (%) |
| `MemoryUsage` | Memory utilization (%) |
| `IntranetIn` | Intranet inbound traffic (bytes/s) |
| `IntranetOut` | Intranet outbound traffic (bytes/s) |
| `IntranetInRatio` | Intranet inbound bandwidth usage (%) |
| `IntranetOutRatio` | Intranet outbound bandwidth usage (%) |
| `FailedCount` | Failed command count |
| `AvgRt` | Average response time (microseconds) |
| `MaxRt` | Max response time (microseconds) |
| `Keys` | Total key count |
| `ExpiredKeys` | Expired key count |
| `EvictedKeys` | Evicted key count |
| `HitRate` | Cache hit rate (%) |
| `InFlow` | Inbound flow (bytes/s) |
| `OutFlow` | Outbound flow (bytes/s) |
| `ConnectionUsage` | Connection usage (%) |
| `DataDelay` | Data replication delay (seconds) |

> Note: Available metrics vary by instance type (Redis vs Tair) and architecture (standard vs cluster). Use `DescribeMonitorItems` to query available metrics for a specific instance.
