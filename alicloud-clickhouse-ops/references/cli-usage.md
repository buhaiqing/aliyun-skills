# CLI Usage: ClickHouse Enterprise Edition (2023-05-22)

> **CLI Applicability**: `dual-path` — Enterprise Edition is CLI-supported via `aliyun clickhouse` (plugin `aliyun-cli-clickhouse` v0.7.1). The Classic Edition (2019-11-11) is SDK-only — see `api-sdk-usage.md`.

## CLI Setup

```bash
# Install the ClickHouse plugin (required for Enterprise Edition)
aliyun plugin install --names aliyun-cli-clickhouse

# Verify
aliyun clickhouse DescribeDBInstances --RegionId cn-hangzhou
```

## Operation Map

### Instance Lifecycle

| Operation | CLI Command | Key Parameters | Notes |
|-----------|------------|---------------|-------|
| **List instances** | `aliyun clickhouse DescribeDBInstances` | `--RegionId`, `--DBInstanceStatus`, `--PageNumber`, `--PageSize` | Optional filters |
| **Get instance detail** | `aliyun clickhouse DescribeDBInstanceAttribute` | `--RegionId` (Required), `--DBInstanceId` | Single instance detail |
| **Create instance** | `aliyun clickhouse CreateDBInstance` | `--RegionId` (Required), `--DBInstanceDescription`, `--Engine`, `--EngineVersion`, `--Category`, `--NodeCount`, `--NodeScaleMin`, `--NodeScaleMax`, `--DeploySchema`, `--MultiZone`, `--DBTimeZone`, `--StorageQuota`, `--ClientToken`, `--ResourceGroupId` | See [Creation Details](#creation-details) |
| **Modify instance class** | `aliyun clickhouse ModifyDBInstanceClass` | `--DBInstanceId` (Required), `--RegionId`, `--NodeCount`, `--NodeScaleMin`, `--NodeScaleMax`, `--ScaleMin`, `--ScaleMax`, `--StorageQuota`, `--ComputingGroupId` | Scale up/down |
| **Start instance** | `aliyun clickhouse StartDBInstance` | `--DBInstanceId` (Required), `--RegionId` | Resume a stopped instance |
| **Stop instance** | `aliyun clickhouse StopDBInstance` | `--DBInstanceId` (Required), `--RegionId` | Pause billing |
| **Restart instance** | `aliyun clickhouse RestartDBInstance` | `--DBInstanceId` (Required), `--RegionId` | Reboot |
| **Delete instance** | `aliyun clickhouse DeleteDBInstance` | `--DBInstanceId` (Required), `--RegionId` | ⚠️ Destructive |
| **Upgrade minor version** | `aliyun clickhouse UpgradeMinorVersion` | `--DBInstanceId` (Required), `--RegionId`, `--TargetMinorVersion`, `--SwitchTime`, `--SwitchTimeMode` | |

### Creation Details

```bash
# Minimal: fixed-spec cluster with 2 nodes
aliyun clickhouse CreateDBInstance \
  --RegionId cn-hangzhou \
  --DBInstanceDescription "my-clickhouse" \
  --NodeCount 2

# Serverless: elastic cluster (min 4 nodes, max 16)
aliyun clickhouse CreateDBInstance \
  --RegionId cn-hangzhou \
  --DBInstanceDescription "serverless-ch" \
  --NodeScaleMin 4 \
  --NodeScaleMax 16

# Multi-AZ
aliyun clickhouse CreateDBInstance \
  --RegionId cn-hangzhou \
  --MultiZone '{"zones":[{"zoneId":"cn-hangzhou-h","vswitchId":"vsw-xxx"},{"zoneId":"cn-hangzhou-i","vswitchId":"vsw-yyy"}]}'
```

### Account Management

| Operation | CLI Command | Key Parameters |
|-----------|------------|---------------|
| **List accounts** | `aliyun clickhouse DescribeAccounts` | `--DBInstanceId` (Required), `--RegionId`, `--PageNumber`, `--PageSize` |
| **Create account** | `aliyun clickhouse CreateAccount` | `--DBInstanceId` (Required), `--Account` (Required), `--AccountType` (Required: `Normal`/`Super`), `--Password` (Required), `--RegionId` (Required) |
| **Modify account authority** | `aliyun clickhouse ModifyAccountAuthority` | `--DBInstanceId` (Required), `--Account` (Required), `--DmlAuthSetting` (Required), `--RegionId` (Required) |
| **Reset password** | `aliyun clickhouse ResetAccountPassword` | `--DBInstanceId` (Required), `--Account` (Required), `--Password` (Required), `--RegionId` (Required) |
| **Delete account** | `aliyun clickhouse DeleteAccount` | `--DBInstanceId` (Required), `--Account` (Required), `--RegionId` (Required) |

### Database Management

| Operation | CLI Command | Key Parameters |
|-----------|------------|---------------|
| **Create database** | `aliyun clickhouse CreateDB` | `--DBInstanceId` (Required), `--DBName` (Required), `--RegionId` (Required), `--Comment` |
| **Delete database** | `aliyun clickhouse DeleteDB` | `--DBInstanceId` (Required), `--DBName` (Required), `--RegionId` (Required) |
| **Describe data sources** | `aliyun clickhouse DescribeDBInstanceDataSources` | `--DBInstanceId` (Required), `--RegionId`, `--DBName`, `--TableName` |

### Network & Security

| Operation | CLI Command | Key Parameters |
|-----------|------------|---------------|
| **List endpoints** | `aliyun clickhouse DescribeEndpoints` | `--DBInstanceId` (Required), `--RegionId`, `--ComputingGroupId` |
| **Create endpoint** | `aliyun clickhouse CreateEndpoint` | `--DBInstanceId` (Required), `--RegionId` (Required), `--ConnectionPrefix`, `--DBInstanceNetType`, `--ComputingGroupId` |
| **Delete endpoint** | `aliyun clickhouse DeleteEndpoint` | `--DBInstanceId` (Required), `--ConnectionString`, `--DBInstanceNetType`, `--RegionId`, `--ComputingGroupId` |
| **Modify connection string** | `aliyun clickhouse ModifyDBInstanceConnectionString` | `--DBInstanceId`, `--ConnectionString`, `--RegionId` |
| **Describe security IP list** | `aliyun clickhouse DescribeSecurityIPList` | `--DBInstanceId` (Required), `--RegionId` |
| **Modify security IP list** | `aliyun clickhouse ModifySecurityIPList` | `--DBInstanceId` (Required), `--SecurityIPList`, `--GroupName`, `--ModifyMode`, `--RegionId` |

### Backup & Recovery

| Operation | CLI Command | Key Parameters |
|-----------|------------|---------------|
| **Describe backups** | `aliyun clickhouse DescribeBackups` | `--DBInstanceId` (Required), `--StartTime` (Required), `--EndTime` (Required), `--RegionId` (Required), `--BackupId` |
| **Create backup policy** | `aliyun clickhouse CreateBackupPolicy` | `--DBInstanceId` (Required), `--PreferredBackupPeriod` (Required), `--PreferredBackupTime` (Required), `--RegionId` (Required), `--BackupRetentionPeriod` |
| **Modify backup policy** | `aliyun clickhouse ModifyBackupPolicy` | `--DBInstanceId` (Required), `--PreferredBackupPeriod` (Required), `--PreferredBackupTime` (Required), `--RegionId` (Required), `--BackupRetentionPeriod` |
| **Describe backup policy** | `aliyun clickhouse DescribeBackupPolicy` | `--DBInstanceId` (Required), `--RegionId` (Required) |
| **Delete backup policy** | `aliyun clickhouse DeleteBackupPolicy` | `--DBInstanceId` (Required), `--RegionId` (Required) |

### Monitoring & Diagnostics

| Operation | CLI Command | Key Parameters |
|-----------|------------|---------------|
| **Describe slow log records** | `aliyun clickhouse DescribeSlowLogRecords` | `--DBInstanceId` (Required), `--EndTime`, `--PageNumber`, `--PageSize`, `--ComputingGroupId` |
| **Describe slow log trend** | `aliyun clickhouse DescribeSlowLogTrend` | `--DBInstanceId` (Required), `--EndTime`, `--QueryDurationMs`, `--ComputingGroupId` |
| **Describe process list** | `aliyun clickhouse DescribeProcessList` | `--DBInstanceId` (Required), `--RegionId`, `--ComputingGroupId` |
| **Kill process** | `aliyun clickhouse KillProcess` | `--DBInstanceId` (Required), `--RegionId`, `--ComputingGroupId` |

### Configuration

| Operation | CLI Command | Key Parameters |
|-----------|------------|---------------|
| **Describe config** | `aliyun clickhouse DescribeDBInstanceConfig` | `--DBInstanceId` (Required), `--RegionId` (Required) |
| **Modify config** | `aliyun clickhouse ModifyDBInstanceConfig` | `--DBInstanceId` (Required), `--RegionId` (Required), `--Parameters` |
| **Describe config change log** | `aliyun clickhouse DescribeDBInstanceConfigChangeLog` | `--DBInstanceId` (Required), `--RegionId` (Required) |

### Resource Management

| Operation | CLI Command | Key Parameters |
|-----------|------------|---------------|
| **Change resource group** | `aliyun clickhouse ChangeResourceGroup` | `--DBInstanceId` (Required), `--ResourceGroupId` (Required), `--RegionId` |
| **Describe regions** | `aliyun clickhouse DescribeRegions` | (No parameters) |

## JSON Output Processing

```bash
# Query instances with JMESPath
aliyun clickhouse DescribeDBInstances --RegionId cn-hangzhou \
  --output cols=DBInstanceId,DBInstanceStatus,DBInstanceDescription \
  rows=Data.DBInstances[]

# Get single instance detail
aliyun clickhouse DescribeDBInstanceAttribute --RegionId cn-hangzhou --DBInstanceId ch-xxx \
  --output json
```

## Coverage Gap

The Enterprise Edition CLI (`2023-05-22`) covers all major operations for the Enterprise Edition. The **Classic Edition** (`2019-11-11`) is not exposed via this CLI plugin — use the Go SDK (`api-sdk-usage.md`) for Classic Edition operations.
