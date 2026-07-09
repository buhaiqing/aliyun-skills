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

## Response Fields

> **Token Efficiency (TE-6):** SKILL.md lists only 3–5 most commonly used fields per operation.
> Complete response field lists are defined in the OpenAPI spec:
> - **OpenAPI Explorer:** https://api.aliyun.com/api/R-kvstore/2015-01-01
> - For each operation, see *Response Parameters* in the OpenAPI Explorer for the full field list.
>
> **Commonly used fields (SKILL.md)** focus on: `InstanceId`, `InstanceStatus`, `ConnectionDomain`, `Capacity`, `Bandwidth`, `Connections`, `RequestId`.

## Go SDK Examples

All examples assume a configured client:

```go
import rkvstore "github.com/alibabacloud-go/r-kvstore-20150101/v2/client"
import "github.com/alibabacloud-go/tea/tea"

c, err := rkvstore.NewClient(&openapi.Config{
	AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
	AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
	RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
})
```

### CreateInstance

```go
req := &rkvstore.CreateInstanceRequest{
	InstanceName:   tea.String(os.Getenv("INSTANCE_NAME")),
	InstanceClass:  tea.String(os.Getenv("INSTANCE_CLASS")),
	EngineVersion:  tea.String(os.Getenv("ENGINE_VERSION")),
	ZoneId:         tea.String(os.Getenv("ZONE_ID")),
	NetworkType:    tea.String(os.Getenv("NETWORK_TYPE")),
	VPCId:          tea.String(os.Getenv("VPC_ID")),
	VSwitchId:      tea.String(os.Getenv("VSWITCH_ID")),
	ChargeType:     tea.String(os.Getenv("CHARGE_TYPE")),
	Password:       tea.String(os.Getenv("PASSWORD")),
	Token:          tea.String(os.Getenv("TOKEN")),
}
resp, err := c.CreateInstance(req)
```

### DescribeInstances

```go
req := &rkvstore.DescribeInstancesRequest{
	RegionId:   tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeInstances(req)
```

### DescribeInstanceAttribute

```go
req := &rkvstore.DescribeInstanceAttributeRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeInstanceAttribute(req)
```

### RestartInstance

```go
req := &rkvstore.RestartInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.RestartInstance(req)
```

### DeleteInstance

```go
req := &rkvstore.DeleteInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DeleteInstance(req)
```

### ModifyInstanceSpec

```go
req := &rkvstore.ModifyInstanceSpecRequest{
	InstanceId:    tea.String(os.Getenv("INSTANCE_ID")),
	InstanceClass: tea.String(os.Getenv("INSTANCE_CLASS")),
}
resp, err := c.ModifyInstanceSpec(req)
```

### DescribeAccounts

```go
req := &rkvstore.DescribeAccountsRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeAccounts(req)
```

### CreateAccount

```go
req := &rkvstore.CreateAccountRequest{
	InstanceId:      tea.String(os.Getenv("INSTANCE_ID")),
	AccountName:     tea.String(os.Getenv("ACCOUNT_NAME")),
	AccountPassword: tea.String(os.Getenv("ACCOUNT_PASSWORD")),
	AccountType:     tea.String(os.Getenv("ACCOUNT_TYPE")),
}
resp, err := c.CreateAccount(req)
```

### DeleteAccount

```go
req := &rkvstore.DeleteAccountRequest{
	InstanceId:  tea.String(os.Getenv("INSTANCE_ID")),
	AccountName: tea.String(os.Getenv("ACCOUNT_NAME")),
}
resp, err := c.DeleteAccount(req)
```

### ResetAccountPassword

```go
req := &rkvstore.ResetAccountPasswordRequest{
	InstanceId:      tea.String(os.Getenv("INSTANCE_ID")),
	AccountName:     tea.String(os.Getenv("ACCOUNT_NAME")),
	AccountPassword: tea.String(os.Getenv("NEW_PASSWORD")),
}
resp, err := c.ResetAccountPassword(req)
```

### DescribeBackups

```go
req := &rkvstore.DescribeBackupsRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	StartTime:  tea.String(os.Getenv("START_TIME")),
	EndTime:    tea.String(os.Getenv("END_TIME")),
}
resp, err := c.DescribeBackups(req)
```

### CreateBackup

```go
req := &rkvstore.CreateBackupRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.CreateBackup(req)
```

### RestoreInstance

```go
req := &rkvstore.RestoreInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	BackupId:   tea.String(os.Getenv("BACKUP_ID")),
}
resp, err := c.RestoreInstance(req)
```

### DescribeSecurityIps

```go
req := &rkvstore.DescribeSecurityIpsRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeSecurityIps(req)
```

### ModifySecurityIps

```go
req := &rkvstore.ModifySecurityIpsRequest{
	InstanceId:          tea.String(os.Getenv("INSTANCE_ID")),
	SecurityIps:         tea.String(os.Getenv("SECURITY_IPS")),
	SecurityIpGroupName: tea.String(os.Getenv("SECURITY_IP_GROUP_NAME")),
}
resp, err := c.ModifySecurityIps(req)
```

### DescribeParameters

```go
req := &rkvstore.DescribeParametersRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeParameters(req)
```

### ModifyParameter

```go
req := &rkvstore.ModifyParameterRequest{
	InstanceId:     tea.String(os.Getenv("INSTANCE_ID")),
	ParameterName:  tea.String(os.Getenv("PARAMETER_NAME")),
	ParameterValue: tea.String(os.Getenv("PARAMETER_VALUE")),
}
resp, err := c.ModifyParameter(req)
```

### DescribeSlowLogs

```go
req := &rkvstore.DescribeSlowLogsRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	StartTime:  tea.String(os.Getenv("START_TIME")),
	EndTime:    tea.String(os.Getenv("END_TIME")),
}
resp, err := c.DescribeSlowLogs(req)
```

### DescribeHistoryMonitorValues

```go
req := &rkvstore.DescribeHistoryMonitorValuesRequest{
	InstanceId:  tea.String(os.Getenv("INSTANCE_ID")),
	MonitorKeys: tea.String(os.Getenv("MONITOR_KEYS")),
	StartTime:   tea.String(os.Getenv("START_TIME")),
	EndTime:     tea.String(os.Getenv("END_TIME")),
}
resp, err := c.DescribeHistoryMonitorValues(req)
```

### ModifyInstanceMaintainTime

```go
req := &rkvstore.ModifyInstanceMaintainTimeRequest{
	InstanceId:        tea.String(os.Getenv("INSTANCE_ID")),
	MaintainStartTime: tea.String(os.Getenv("MAINTAIN_START_TIME")),
	MaintainEndTime:   tea.String(os.Getenv("MAINTAIN_END_TIME")),
}
resp, err := c.ModifyInstanceMaintainTime(req)
```

### ModifyInstanceSSL

```go
req := &rkvstore.ModifyInstanceSSLRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	SSLEnabled: tea.String(os.Getenv("SSL_ENABLED")),
}
resp, err := c.ModifyInstanceSSL(req)
```

### ModifyIntranetBandwidth

```go
req := &rkvstore.ModifyIntranetBandwidthRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	Bandwidth:  tea.Int64(int64(os.Getenv("BANDWIDTH"))),
}
resp, err := c.ModifyIntranetBandwidth(req)
```

### MigrateToOtherZone

```go
req := &rkvstore.MigrateToOtherZoneRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	ZoneId:     tea.String(os.Getenv("ZONE_ID")),
}
resp, err := c.MigrateToOtherZone(req)
```

### UpgradeMinorVersion

```go
req := &rkvstore.UpgradeMinorVersionRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.UpgradeMinorVersion(req)
```

### FlushInstance

```go
req := &rkvstore.FlushInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.FlushInstance(req)
```
