# API & SDK Usage — PolarDB MySQL

> Version: 1.0.0 | Last Updated: 2026-05-16

## OpenAPI

- **Service Endpoint:** `polardb.aliyuncs.com`
- **API Version:** 2022-05-30

## Go SDK Package

```
github.com/alibabacloud-go/polardb-20220530/v3/client
```

## SDK Operations Map

| Goal | API operationId | Description |
|------|-----------------|-------------|
| **Cluster Lifecycle** |
| Create | `CreateDBCluster` | Create PolarDB MySQL cluster |
| List | `DescribeDBClusters` | List all clusters in region |
| Describe | `DescribeDBClusterAttribute` | Get detailed cluster info |
| Modify | `ModifyDBCluster` | Modify cluster configuration |
| Delete | `DeleteDBCluster` | Delete cluster |
| Start | `StartDBCluster` | Start stopped cluster |
| Stop | `StopDBCluster` | Stop running cluster |
| Pause | `PauseDBCluster` | Pause serverless cluster |
| Resume | `ResumeDBCluster` | Resume paused cluster |
| Upgrade | `UpgradeDBCluster` | Upgrade cluster class/version |
| Clone | `CloneDBCluster` | Clone from existing cluster |
| **Node Management** |
| Add | `AddDBNodes` | Add read-only nodes |
| Remove | `RemoveDBNodes` | Remove nodes |
| Describe | `DescribeDBNodes` | List nodes in cluster |
| Restart | `RestartDBNode` | Restart a specific node |
| **Account Management** |
| Create | `CreateAccount` | Create database account |
| Describe | `DescribeAccounts` | List accounts |
| Set Privilege | `GrantAccountPrivilege` | Grant database privileges |
| Revoke Privilege | `RevokeAccountPrivilege` | Revoke privileges |
| Reset Password | `ResetAccountPassword` | Reset account password |
| Delete | `DeleteAccount` | Delete account |
| **Database Management** |
| Create | `CreateDatabase` | Create database |
| Describe | `DescribeDatabases` | List databases |
| Modify | `ModifyDatabaseDescription` | Modify database description |
| Delete | `DeleteDatabase` | Delete database |
| **Backup Management** |
| Create | `CreateBackup` | Manual backup |
| Describe | `DescribeBackups` | List backup sets |
| Policy | `DescribeBackupPolicy` | Get backup policy |
| Modify Policy | `ModifyBackupPolicy` | Change backup policy |
| Delete | `DeleteBackupFile` | Delete backup set |
| Restore | `RestoreDBCluster` | Restore from backup |
| **Endpoint Management** |
| Describe | `DescribeDBClusterEndpoints` | List cluster endpoints |
| Create | `CreateDBEndpoint` | Create custom endpoint |
| Modify | `ModifyDBClusterEndpoint` | Modify endpoint config |
| Delete | `DeleteDBEndpoint` | Delete custom endpoint |
| **Monitoring** |
| Performance | `DescribeDBClusterPerformance` | Get performance metrics |
| Metrics | `DescribeDBNodePerformance` | Get node-level metrics |
| **Other** |
| Regions | `DescribeRegions` | List supported regions |
| Available Classes | `DescribeDBClusterAvailableClasses` | List available instance classes |
| Global GDN | `DescribeGlobalDatabaseNetwork` | Describe GDN |

## Request / Response Notes

### Required Fields for Common Operations

| Operation | Required Fields |
|-----------|----------------|
| CreateDBCluster | `DBType`, `DBVersion`, `DBNodeClass`, `DBNodeNumber`, `RegionId`, `VPCId`, `VSwitchId`, `PayType` |
| DescribeDBClusters | `RegionId` or `DBClusterId` |
| DescribeDBClusterAttribute | `DBClusterId` |
| CreateAccount | `DBClusterId`, `AccountName`, `AccountPassword` |
| CreateDatabase | `DBClusterId`, `DBName` |
| CreateBackup | `DBClusterId` |
| DescribeBackups | `DBClusterId`, `StartTime`, `EndTime` |

### Pagination

- Use `PageNumber` (default 1) and `PageSize` (default 30, max 100).
- Total count returned in `TotalRecordCount`.

### Timestamps

All time parameters use `yyy-MM-ddTHH:mmZ` format (UTC).

## Error Code Reference

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| InvalidDBClusterId.NotFound | 404 | Cluster does not exist |
| InvalidDBClusterId.Malform | 400 | Malformed cluster ID |
| InvalidParameter | 400 | Parameter validation failed |
| DBClusterQuotaExceeded | 403 | Cluster quota exceeded |
| InsufficientBalance | 403 | Account balance insufficient |
| ResourceAlreadyExists | 409 | Resource name already exists |
| VPCIdNotFound | 404 | VPC does not exist |
| VSwitchIdNotFound | 404 | VSwitch does not exist |
| OperationDenied | 400 | Operation not permitted |
| OperationDenied.InstanceStatus | 400 | Action not allowed for current status |
| AccountNameAlreadyExists | 409 | Account already exists |
| AccountNameInvalid | 400 | Invalid account name format |
| DBNameAlreadyExists | 409 | Database already exists |
| Throttling | 429 | API throttled |
| InternalError | 500 | Server-side error |
