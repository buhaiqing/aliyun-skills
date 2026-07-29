# API/SDK Usage: ClickHouse Classic Edition (2019-11-11)

> This documents the **Classic Edition** SDK (`clickhouse-2019-11-11`). For the Enterprise Edition CLI (`2023-05-22`), see `cli-usage.md`.

## Go SDK Setup

```go
import (
    "github.com/alibabacloud-go/clickhouse-20191111/v3/client"
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
)
```

Use `alicloud-jit-setup.sh` for JIT SDK setup, then build as needed.

## Operation Map

### Instance Lifecycle (Classic Edition)

| Operation | SDK Method | Notes |
|-----------|-----------|-------|
| CreateDBInstance | `client.CreateDBInstance()` | Creates a ClickHouse Classic instance |
| DescribeDBInstances | `client.DescribeDBInstances()` | List instances |
| DescribeDBInstanceAttribute | `client.DescribeDBInstanceAttribute()` | Get instance details |
| ModifyDBCluster | `client.ModifyDBCluster()` | Scale instance spec |
| DeleteDBCluster | `client.DeleteDBCluster()` | ⚠️ Destructive |
| RestartInstance | `client.RestartInstance()` | Reboot |
| UpgradeMinorVersion | `client.UpgradeMinorVersion()` | Minor version upgrade |

### Account Management

| Operation | SDK Method |
|-----------|-----------|
| CreateAccount | `client.CreateAccount()` |
| DeleteAccount | `client.DeleteAccount()` |
| DescribeAccounts | `client.DescribeAccounts()` |
| ResetAccountPassword | `client.ResetAccountPassword()` |
| ModifyAccountAuthority | `client.ModifyAccountAuthority()` |

### Security

| Operation | SDK Method |
|-----------|-----------|
| DescribeDBClusterAccessWhiteList | `client.DescribeDBClusterAccessWhiteList()` |
| ModifyDBClusterAccessWhiteList | `client.ModifyDBClusterAccessWhiteList()` |
| DescribeDBClusterNetInfoItems | `client.DescribeDBClusterNetInfoItems()` |
| AllocateClusterPublicConnection | `client.AllocateClusterPublicConnection()` |
| ReleaseClusterPublicConnection | `client.ReleaseClusterPublicConnection()` |

### Backup

| Operation | SDK Method |
|-----------|-----------|
| DescribeBackups | `client.DescribeBackups()` |
| DescribeBackupPolicy | `client.DescribeBackupPolicy()` |
| ModifyBackupPolicy | `client.ModifyBackupPolicy()` |

### Monitoring

| Operation | SDK Method |
|-----------|-----------|
| DescribeSlowLogRecords | `client.DescribeSlowLogRecords()` |
| DescribeSlowLogTrend | `client.DescribeSlowLogTrend()` |
| DescribeProcessList | `client.DescribeProcessList()` |

### Database & Table

| Operation | SDK Method |
|-----------|-----------|
| CreateDatabase | `client.CreateDatabase()` |
| DeleteDatabase | `client.DeleteDatabase()` |
| DescribeTables | `client.DescribeTables()` |
| DescribeAllDataSource | `client.DescribeAllDataSource()` |
| DescribeColumns | `client.DescribeColumns()` |

### Configuration

| Operation | SDK Method |
|-----------|-----------|
| DescribeDBConfig | `client.DescribeDBConfig()` |
| ModifyDBConfig | `client.ModifyDBConfig()` |

### Resource Management

| Operation | SDK Method |
|-----------|-----------|
| DescribeRegions | `client.DescribeRegions()` |

## Pagination

Classic Edition APIs follow standard Alibaba Cloud pagination:

```go
func ListAllInstances(client *client.Client, regionId string) ([]*client.DescribeDBInstancesResponseBodyDataDBInstancesDBInstance, error) {
    var all []*client.DescribeDBInstancesResponseBodyDataDBInstancesDBInstance
    pageNumber := int32(1)
    pageSize := int32(100)

    for {
        req := &client.DescribeDBInstancesRequest{
            RegionId:   tea.String(regionId),
            PageNumber: tea.Int32(pageNumber),
            PageSize:   tea.Int32(pageSize),
        }
        resp, err := client.DescribeDBInstances(req)
        if err != nil {
            return nil, err
        }
        all = append(all, resp.Body.Data.DBInstances...)
        if len(resp.Body.Data.DBInstances) < int(pageSize) {
            break
        }
        pageNumber++
    }
    return all, nil
}
```

## Error Handling

```go
// SDK errors are typed — check for specific error codes
resp, err := client.DescribeDBInstances(req)
if err != nil {
    if strings.Contains(err.Error(), "InvalidDBInstanceId.NotFound") {
        // Instance not found — may have been deleted
    }
    return err
}
```

## Coverage Gap

The Classic Edition SDK (`2019-11-11`) does NOT support:
- Serverless scaling (NodeScaleMin/Max)
- Computing Groups
- Multi-AZ deployment
- Enterprise-specific features (StartDBInstance, StopDBInstance, etc.)

For these features, use the Enterprise Edition CLI (`cli-usage.md`).
