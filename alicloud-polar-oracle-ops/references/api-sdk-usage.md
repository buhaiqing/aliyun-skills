# API & SDK Usage — PolarDB Oracle-compatible (IO)

> Version: 1.0.0 | Last Updated: 2026-05-16

## OpenAPI

- **Service Endpoint:** `polardb-io.aliyuncs.com`
- **API Version:** 2021-11-26

## Go SDK Package

```
github.com/alibabacloud-go/polardb-io-20211126/v3/client
```

## Operations Map

| Goal | API operationId | Description |
|------|-----------------|-------------|
| CreateDBCluster | Create cluster | Create PolarDB-O cluster |
| DescribeDBClusters | List clusters | List clusters in region |
| DescribeDBClusterAttribute | Describe cluster | Get detailed info |
| ModifyDBCluster | Modify cluster | Change configuration |
| DeleteDBCluster | Delete cluster | Delete cluster |
| AddDBNodes | Add nodes | Scale out compute nodes |
| RemoveDBNodes | Remove nodes | Scale in compute nodes |
| DescribeDBNodes | Describe nodes | List nodes |
| StartDBCluster | Start cluster | Start stopped cluster |
| StopDBCluster | Stop cluster | Stop running cluster |
| UpgradeDBCluster | Upgrade cluster | Upgrade specification |
| CreateAccount | Create account | Create database account |
| DescribeAccounts | Describe accounts | List accounts |
| CreateDatabase | Create database | Create database |
| DescribeDatabases | Describe databases | List databases |
| CreateBackup | Create backup | Manual backup |
| DescribeBackups | Describe backups | List backup sets |
| ModifyBackupPolicy | Modify backup policy | Change backup policy |
| DescribeDBClusterEndpoints | Describe endpoints | List endpoints |
| DescribeRegions | List regions | Available regions |

## Common Required Fields

| Operation | Required Fields |
|-----------|----------------|
| CreateDBCluster | `DBNodeClass`, `DBNodeNumber`, `RegionId`, `VPCId`, `VSwitchId`, `PayType` |
| DescribeDBClusters | `RegionId` or `DBClusterId` |

## Error Code Reference

| Error Code | Meaning | Action |
|------------|---------|--------|
| InvalidDBClusterId.NotFound | Cluster not found | Verify ID |
| InvalidParameter | Parameter invalid | Check OpenAPI spec |
| DBClusterQuotaExceeded | Quota exceeded | Raise quota |
| InsufficientBalance | No funds | Recharge |
| Throttling | Rate limited | Exponential backoff |
| InternalError | Server error | Retry 3x; HALT |
| OperationDenied | Operation not permitted | Check cluster status |
| AccountNameInvalid | Invalid account name | Fix format |
| DBNameAlreadyExists | Database exists | Reuse or rename |
