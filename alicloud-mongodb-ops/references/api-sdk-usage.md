# API & SDK — Alibaba Cloud MongoDB (DDS)

## OpenAPI

- **Product**: DDS (Document Database Service)
- **API Version**: 2015-12-01
- **Base Endpoint**: `mongodb.aliyuncs.com`
- **Official Docs**: https://www.alibabacloud.com/help/en/mongodb
- **OpenAPI Explorer**: https://api.aliyun.com/api/Mongodb/2015-12-01

## CLI Path (aliyun dds)

Core commands for MongoDB instance operations:

| Operation | CLI Command | Key Parameters |
|-----------|-------------|----------------|
| List Instances | `aliyun dds DescribeInstances` | RegionId, InstanceStatus |
| Get Instance | `aliyun dds DescribeInstances --InstanceId` | InstanceId |
| Create Instance | `aliyun dds CreateInstance` | EngineVersion, InstanceClass, Storage |
| Modify Instance | `aliyun dds ModifyDBInstanceSpec` | InstanceId, InstanceClass |
| Delete Instance | `aliyun dds DeleteInstance` | InstanceId |
| Restart Instance | `aliyun dds RestartInstance` | InstanceId |
| Describe Accounts | `aliyun dds DescribeAccounts` | InstanceId |
| Create Account | `aliyun dds CreateAccount` | AccountName, AccountPassword |
| Describe Backups | `aliyun dds DescribeBackups` | InstanceId |
| Create Backup | `aliyun dds CreateBackup` | InstanceId, BackupType |
| Describe SlowLogs | `aliyun dds DescribeSlowLogs` | InstanceId, StartTime, EndTime |
| Describe Parameters | `aliyun dds DescribeParameters` | InstanceId |
| Modify Parameters | `aliyun dds ModifyParameters` | InstanceId, Parameters |
| Describe SecurityIPs | `aliyun dds DescribeSecurityIPs` | InstanceId |
| Modify SecurityIPs | `aliyun dds ModifySecurityIPs` | InstanceId, SecurityIps |

## SDK Operations Map

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Create Instance | CreateInstance | `CreateInstance` | `aliyun dds CreateInstance` |
| Describe Instances | DescribeInstances | `DescribeInstances` | `aliyun dds DescribeInstances` |
| Describe Instance Attribute | DescribeInstanceAttribute | `DescribeInstanceAttribute` | `aliyun dds DescribeInstanceAttribute` |
| Modify Instance Spec | ModifyDBInstanceSpec | `ModifyDBInstanceSpec` | `aliyun dds ModifyDBInstanceSpec` |
| Restart Instance | RestartInstance | `RestartInstance` | `aliyun dds RestartInstance` |
| Delete Instance | DeleteInstance | `DeleteInstance` | `aliyun dds DeleteInstance` |
| Describe Accounts | DescribeAccounts | `DescribeAccounts` | `aliyun dds DescribeAccounts` |
| Create Account | CreateAccount | `CreateAccount` | `aliyun dds CreateAccount` |
| Delete Account | DeleteAccount | `DeleteAccount` | `aliyun dds DeleteAccount` |
| Reset Account Password | ResetAccountPassword | `ResetAccountPassword` | `aliyun dds ResetAccountPassword` |
| Describe Backups | DescribeBackups | `DescribeBackups` | `aliyun dds DescribeBackups` |
| Create Backup | CreateBackup | `CreateBackup` | `aliyun dds CreateBackup` |
| Restore Instance | RestoreInstance | `RestoreInstance` | `aliyun dds RestoreInstance` |
| Describe Security IPs | DescribeSecurityIPs | `DescribeSecurityIPs` | `aliyun dds DescribeSecurityIPs` |
| Modify Security IPs | ModifySecurityIPs | `ModifySecurityIPs` | `aliyun dds ModifySecurityIPs` |
| Describe Parameters | DescribeParameters | `DescribeParameters` | `aliyun dds DescribeParameters` |
| Modify Parameters | ModifyParameters | `ModifyParameters` | `aliyun dds ModifyParameters` |
| Describe Slow Logs | DescribeSlowLogs | `DescribeSlowLogs` | `aliyun dds DescribeSlowLogs` |
| Describe Regions | DescribeRegions | `DescribeRegions` | `aliyun dds DescribeRegions` |
| Describe Available Resource | DescribeAvailableResource | `DescribeAvailableResource` | `aliyun dds DescribeAvailableResource` |
| Upgrade Engine Version | UpgradeDBInstanceEngineVersion | `UpgradeDBInstanceEngineVersion` | `aliyun dds UpgradeDBInstanceEngineVersion` |
| Describe Performance | DescribeDBInstancePerformance | `DescribeDBInstancePerformance` | `aliyun dds DescribeDBInstancePerformance` |
| Describe Resource Usage | DescribeResourceUsage | `DescribeResourceUsage` | `aliyun dds DescribeResourceUsage` |

## SDK Path (Go)

### Package Installation

```bash
go get github.com/alibabacloud-go/dds-20151201/v3/client
```

### Client Creation

```go
package main

import (
    "os"
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    dds "github.com/alibabacloud-go/dds-20151201/v3/client"
)

func createClient() (*dds.Client, error) {
    config := &openapi.Config{
        AccessKeyId:     os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        AccessKeySecret: os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        RegionId:        os.Getenv("ALIBABA_CLOUD_REGION_ID"),
    }
    // Endpoint defaults to mongodb.aliyuncs.com based on RegionId
    return dds.NewClient(config)
}
```

### Key SDK Operations

#### CreateInstance

```go
func createMongoDBInstance(client *dds.Client) error {
    request := &dds.CreateInstanceRequest{
        RegionId:        tea.String("cn-hangzhou"),
        EngineVersion:   tea.String("4.2"),
        DBInstanceClass: tea.String("dds.mongo.mid"),
        DBInstanceStorage: tea.Int32(20),
        AccountPassword: tea.String("YourPassword123!"),
        SecurityToken:   tea.String(uuid.New().String()), // Idempotency
    }
    
    response, err := client.CreateInstance(request)
    if err != nil {
        return fmt.Errorf("CreateInstance failed: %v", err)
    }
    
    fmt.Printf("Instance created: %s\n", *response.Body.DBInstanceId)
    return nil
}
```

#### DescribeInstances

```go
func listMongoDBInstances(client *dds.Client, regionId string) ([]*dds.DescribeInstancesResponseBodyDBInstancesDBInstance, error) {
    request := &dds.DescribeInstancesRequest{
        RegionId:      tea.String(regionId),
        PageSize:      tea.Int32(30),
        PageNumber:    tea.Int32(1),
    }
    
    response, err := client.DescribeInstances(request)
    if err != nil {
        return nil, fmt.Errorf("DescribeInstances failed: %v", err)
    }
    
    return response.Body.DBInstances.DBInstance, nil
}
```

#### ModifyDBInstanceSpec

```go
func modifyInstanceSpec(client *dds.Client, instanceId, newClass string) error {
    request := &dds.ModifyDBInstanceSpecRequest{
        DBInstanceId:     tea.String(instanceId),
        DBInstanceClass:  tea.String(newClass),
        EffectiveTime:    tea.String("Immediately"), // or "MaintainTime"
    }
    
    response, err := client.ModifyDBInstanceSpec(request)
    if err != nil {
        return fmt.Errorf("ModifyDBInstanceSpec failed: %v", err)
    }
    
    fmt.Printf("Order ID: %s\n", *response.Body.OrderId)
    return nil
}
```

#### DescribeAccounts

```go
func describeAccounts(client *dds.Client, instanceId string) ([]*dds.DescribeAccountsResponseBodyAccountsAccount, error) {
    request := &dds.DescribeAccountsRequest{
        DBInstanceId: tea.String(instanceId),
    }
    
    response, err := client.DescribeAccounts(request)
    if err != nil {
        return nil, fmt.Errorf("DescribeAccounts failed: %v", err)
    }
    
    return response.Body.Accounts.Account, nil
}
```

#### CreateBackup

```go
func createBackup(client *dds.Client, instanceId string) error {
    request := &dds.CreateBackupRequest{
        DBInstanceId: tea.String(instanceId),
        BackupType:   tea.String("Full"), // or "Snapshot"
    }
    
    response, err := client.CreateBackup(request)
    if err != nil {
        return fmt.Errorf("CreateBackup failed: %v", err)
    }
    
    fmt.Printf("Backup ID: %s\n", *response.Body.BackupId)
    return nil
}
```

## Dual-Path Execution Pattern

### When to Use CLI

| Scenario | Reason |
|----------|--------|
| Quick operations | Single command execution without code overhead |
| Manual debugging | Direct API invocation with immediate response |
| Ad-hoc scripts | Shell script integration for automation |
| Testing endpoints | Rapid API validation before SDK implementation |
| CI/CD pipelines | Simplified pipeline steps for common operations |

### When to Use SDK

| Scenario | Reason |
|----------|--------|
| Production code | Integrated Go applications with proper error handling |
| Complex workflows | Multi-step operations with dependency chains |
| Batch processing | Bulk operations across multiple instances |
| Error recovery | Structured retry logic and graceful degradation |
| State management | Persistent client with connection pooling |

### CLI Output Formatting

```bash
# List instances with specific columns
aliyun dds DescribeInstances \
  --RegionId cn-hangzhou \
  --output cols=InstanceId,InstanceStatus,InstanceType,EngineVersion \
           rows=DBInstances.DBInstance[]

# Query instance by status
aliyun dds DescribeInstances \
  --RegionId cn-hangzhou \
  --InstanceStatus Running \
  --output cols=InstanceId,DBInstanceClass,Storage rows=DBInstances.DBInstance[]

# Describe backups with JMESPath
aliyun dds DescribeBackups \
  --DBInstanceId dds-bp123xxx \
  --output cols=BackupId,BackupStatus,BackupSize,BackupStartTime \
           rows=Backups.Backup[]

# Get instance performance metrics
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId dds-bp123xxx \
  --Key MongoDB_CPUUsage,MongoDB_MemoryUsage \
  --StartTime 2025-01-01T00:00:00Z \
  --EndTime 2025-01-01T01:00:00Z \
  --output cols=Key,Value,Unit rows=PerformanceKeys.PerformanceKey[].Values.Value[]
```

## Error Handling Patterns

### Common Error Codes

| Code | HTTP Status | Handling |
|------|-------------|----------|
| `Throttling` | 400 | Retry with exponential backoff (max 3 retries) |
| `InvalidInstanceId.NotFound` | 404 | Verify ID, check region, confirm instance exists |
| `InvalidInstanceStatus` | 400 | Wait for Normal status, check transition state |
| `InvalidDBInstanceClass.NotFound` | 400 | Verify spec with DescribeAvailableResource |
| `InsufficientBalance` | 400 | Check account balance, add credits |
| `OperationDenied.QuotaExceeded` | 400 | Check quota limits, request increase |
| `BackupJobExists` | 400 | Wait for current backup to complete |
| `ParameterInvalid` | 400 | Validate parameter format and value range |

### Retry Pattern (Go SDK)

```go
import (
    "time"
    "github.com/alibabacloud-go/tea/tea"
)

func withRetry(fn func() error, maxRetries int) error {
    backoff := []time.Duration{1, 2, 5} // seconds
    
    for i := 0; i < maxRetries; i++ {
        err := fn()
        if err == nil {
            return nil
        }
        
        // Check for retryable errors
        if tea.IsRetryableError(err) || isThrottling(err) {
            if i < len(backoff) {
                time.Sleep(backoff[i] * time.Second)
                continue
            }
            time.Sleep(10 * time.Second)
            continue
        }
        
        return err
    }
    return fmt.Errorf("max retries exceeded")
}

func isThrottling(err error) bool {
    if teaError, ok := err.(*tea.TeaError); ok {
        return teaError.Code == "Throttling"
    }
    return false
}
```

### Instance Status Validation

```go
func waitForInstanceStatus(client *dds.Client, instanceId, targetStatus string, timeout time.Duration) error {
    deadline := time.Now().Add(timeout)
    
    for time.Now().Before(deadline) {
        resp, err := client.DescribeInstances(&dds.DescribeInstancesRequest{
            DBInstanceId: tea.String(instanceId),
        })
        if err != nil {
            return err
        }
        
        if len(resp.Body.DBInstances.DBInstance) > 0 {
            status := *resp.Body.DBInstances.DBInstance[0].DBInstanceStatus
            if status == targetStatus {
                return nil
            }
            if status == "Creating" || status == "Changing" {
                time.Sleep(5 * time.Second)
                continue
            }
            return fmt.Errorf("unexpected status: %s", status)
        }
        
        time.Sleep(5 * time.Second)
    }
    
    return fmt.Errorf("timeout waiting for status: %s", targetStatus)
}
```

## Request / Response Notes

- **Pagination**: List APIs support `PageSize` (max 100) and `PageNumber` (default 1).
- **Time Format**: APIs expect `YYYY-MM-DDTHH:mm:ssZ` (ISO 8601 UTC) for time parameters.
- **RegionId**: Required for most operations; must match the instance's region.
- **DBInstanceId**: Primary identifier for instance-scoped operations.
- **SecurityToken**: Use UUID v4 for idempotency on write operations; reuse within 24 hours for retries.
- **EngineVersion**: Supports 4.0, 4.2, 4.4, 5.0, 6.0, 7.0 depending on instance type.

## Common Metric Keys (DescribeDBInstancePerformance)

| Metric Key | Description |
|------------|-------------|
| `MongoDB_CPUUsage` | CPU utilization (%) |
| `MongoDB_MemoryUsage` | Memory utilization (%) |
| `MongoDB_IOPS` | I/O operations per second |
| `MongoDB_Connections` | Active connections |
| `MongoDB_ConnectionsUsage` | Connection usage (%) |
| `MongoDB_DataSize` | Data size (bytes) |
| `MongoDB_StorageUsage` | Storage usage (%) |
| `MongoDB_Opcounters` | Operation counters (query/insert/update/delete) |
| `MongoDB_NetworkIn` | Network inbound traffic (bytes/s) |
| `MongoDB_NetworkOut` | Network outbound traffic (bytes/s) |
| `MongoDB_CursorOpen` | Open cursors count |
| `MongoDB_CursorTimeout` | Cursor timeouts count |
| `MongoDB_WiredTigerCache` | WiredTiger cache usage (bytes) |

> Note: Available metrics vary by MongoDB version and instance architecture (standalone vs replica set vs sharded cluster). Use instance-specific monitoring endpoints for comprehensive metrics.

## Instance Architecture Types

| Type | CLI Value | Description |
|------|-----------|-------------|
| Standalone | `standalone` | Single-node deployment |
| Replica Set | `replicate` | 3-node replica set with automatic failover |
| Sharding | `sharding` | Sharded cluster for horizontal scaling |

> Note: Architecture type is specified during creation via `ArchitectureType` parameter.