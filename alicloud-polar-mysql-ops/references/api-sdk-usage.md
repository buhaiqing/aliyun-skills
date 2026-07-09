# API & SDK Usage — PolarDB MySQL

> Version: 1.1.0 | Last Updated: 2026-05-26

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
| **Slow Query Analysis** |
| Statistics | `DescribeSlowLogs` | Query slow SQL statistics overview |
| Details | `DescribeSlowLogRecords` | Query detailed slow SQL records |
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
| **DescribeSlowLogs** | `DBClusterId`, `StartTime`, `EndTime` |
| **DescribeSlowLogRecords** | `DBClusterId`, `StartTime`, `EndTime` |

### Slow Query API Parameters

**DescribeSlowLogs Request:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `DBClusterId` | string | Yes | PolarDB cluster ID |
| `StartTime` | string | Yes | Start time in ISO 8601 format (UTC), e.g., `2024-11-22T02:22Z` |
| `EndTime` | string | Yes | End time in ISO 8601 format (UTC), e.g., `2024-11-22T02:22Z` |
| `DBName` | string | No | Filter by database name |
| `PageSize` | int32 | No | Records per page (default: 30, max: 100) |
| `PageNumber` | int32 | No | Page number (default: 1) |

**DescribeSlowLogRecords Request:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `DBClusterId` | string | Yes | PolarDB cluster ID |
| `StartTime` | string | Yes | Start time in ISO 8601 format (UTC) |
| `EndTime` | string | Yes | End time in ISO 8601 format (UTC) |
| `DBNodeId` | string | No | Filter by specific node ID |
| `DBName` | string | No | Filter by database name |
| `PageSize` | int32 | No | Records per page (default: 30, max: 100) |
| `PageNumber` | int32 | No | Page number (default: 1) |
| `SQLText` | string | No | Filter by SQL text pattern |

### Slow Query Response Fields

**DescribeSlowLogs Response:**

| Field | Path | Type | Description |
|-------|------|------|-------------|
| SQL Text | `$.Items.SQLSlowLog[].SQLText` | string | SQL statement pattern |
| DB Name | `$.Items.SQLSlowLog[].DBName` | string | Database name |
| Slow Log Count | `$.Items.SQLSlowLog[].SlowLogCounts` | int64 | Number of occurrences |
| Total Count | `$.Items.SQLSlowLog[].TotalCounts` | int64 | Total execution count |
| Max Query Time | `$.Items.SQLSlowLog[].MaxQueryTime` | float64 | Maximum execution time (s) |
| Avg Query Time | `$.Items.SQLSlowLog[].AvgQueryTime` | float64 | Average execution time (s) |
| Min Query Time | `$.Items.SQLSlowLog[].MinQueryTime` | float64 | Minimum execution time (s) |

**DescribeSlowLogRecords Response:**

| Field | Path | Type | Description |
|-------|------|------|-------------|
| SQL Text | `$.Items.SQLSlowRecord[].SQLText` | string | Complete SQL statement |
| Query Start Time | `$.Items.SQLSlowRecord[].QueryStartTime` | string | Execution start timestamp (ISO 8601) |
| Query Time | `$.Items.SQLSlowRecord[].QueryTime` | float64 | Execution time in seconds |
| Query Time (ms) | `$.Items.SQLSlowRecord[].QueryTimeMS` | float64 | Execution time in milliseconds |
| Lock Time (ms) | `$.Items.SQLSlowRecord[].LockTimeMS` | int64 | Lock wait time in milliseconds |
| Parse Row Counts | `$.Items.SQLSlowRecord[].ParseRowCounts` | int64 | Rows examined/scanned |
| Return Row Counts | `$.Items.SQLSlowRecord[].ReturnRowCounts` | int64 | Rows returned |
| DB Name | `$.Items.SQLSlowRecord[].DBName` | string | Database name |
| Host Address | `$.Items.SQLSlowRecord[].HostAddress` | string | Client IP address |
| Execution Plan | `$.Items.SQLSlowRecord[].ExecutionPlan` | string | Execution plan (if available) |

### Pagination

- Use `PageNumber` (default 1) and `PageSize` (default 30, max 100).
- Total count returned in `TotalRecordCount`.
- For slow query analysis, fetch all pages to get complete dataset:

```go
// Paginated slow log retrieval
pageNumber := int32(1)
allRecords := []polardb.DescribeSlowLogRecordsResponseBodyItemsSQLSlowRecord{}

for {
    req := &polardb.DescribeSlowLogRecordsRequest{
        DBClusterId: tea.String(clusterId),
        StartTime:   tea.String(startTime),
        EndTime:     tea.String(endTime),
        PageSize:    tea.Int32(100),
        PageNumber:  tea.Int32(pageNumber),
    }
    resp, _ := client.DescribeSlowLogRecords(req)
    
    items := resp.Body.Items.SQLSlowRecord
    allRecords = append(allRecords, items...)
    
    // Check if we've fetched all records
    if len(allRecords) >= int(tea.Int32Value(resp.Body.TotalRecordCount)) {
        break
    }
    pageNumber++
}
```

### Timestamps

All time parameters use `yyyy-MM-ddTHH:mmZ` format (UTC). Time range constraints:

- Maximum range: 7 days
- Format: ISO 8601 with UTC timezone
- Example: `2024-11-22T02:22Z`

## Error Code Reference

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| InvalidDBClusterId.NotFound | 404 | Cluster does not exist |
| InvalidDBClusterId.Malform | 400 | Malformed cluster ID |
| InvalidParameter | 400 | Parameter validation failed |
| InvalidStartTime.Malformed | 400 | Invalid start time format |
| InvalidEndTime.Malformed | 400 | Invalid end time format |
| TimeRangeExceeded | 400 | Time range exceeds 7 days |
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
