# API/SDK Usage Reference

> Go SDK 完整使用参考 for PolarDB PostgreSQL

## Overview

本文档提供 PolarDB PostgreSQL 的 Go SDK 完整使用参考，包括所有核心 API 的操作示例。

## SDK Installation

```bash
# 初始化 Go 模块
cd /tmp/aliyun-sdk-workspace
go mod init polardb-ops

# 安装依赖
go get github.com/alibabacloud-go/darabonba-openapi/v2
go get github.com/alibabacloud-go/polardb-20220530/v3
go get github.com/alibabacloud-go/tea
go get github.com/google/uuid
```

## Client Initialization

```go
package main

import (
    "fmt"
    "os"
    
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    polardb "github.com/alibabacloud-go/polardb-20220530/v3/client"
    "github.com/alibabacloud-go/tea/tea"
)

// createClient - 创建 PolarDB 客户端
func createClient() (*polardb.Client, error) {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    
    return polardb.NewClient(config)
}

func main() {
    client, err := createClient()
    if err != nil {
        panic(err)
    }
    
    // Use client...
    fmt.Println("Client created successfully")
}
```

## Cluster Operations

### Create DB Cluster

```go
package main

import (
    "fmt"
    "os"
    
    "github.com/google/uuid"
    polardb "github.com/alibabacloud-go/polardb-20220530/v3/client"
    "github.com/alibabacloud-go/tea/tea"
)

func createCluster(client *polardb.Client) (*string, error) {
    request := &polardb.CreateDBClusterRequest{
        RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
        DBType:          tea.String("PostgreSQL"),
        DBVersion:       tea.String("14"),
        DBClusterClass:  tea.String("polar.pg.g2.xlarge"),
        DBNodeClass:     tea.String("polar.pg.g2.xlarge"),
        ZoneId:          tea.String("cn-hangzhou-h"),
        VPCId:           tea.String(os.Getenv("VPC_ID")),
        VSwitchId:       tea.String(os.Getenv("VSWITCH_ID")),
        PayType:         tea.String("Postpaid"),
        ClientToken:     tea.String(uuid.New().String()),
    }
    
    response, err := client.CreateDBCluster(request)
    if err != nil {
        return nil, err
    }
    
    clusterId := tea.StringValue(response.Body.DBClusterId)
    fmt.Printf("Created cluster: %s\n", clusterId)
    return &clusterId, nil
}
```

### Describe DB Clusters

```go
func describeClusters(client *polardb.Client) error {
    request := &polardb.DescribeDBClustersRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
        DBType:   tea.String("PostgreSQL"),
    }
    
    response, err := client.DescribeDBClusters(request)
    if err != nil {
        return err
    }
    
    for _, cluster := range response.Body.Items.DBCluster {
        fmt.Printf("Cluster: %s, Status: %s, Version: %s\n",
            tea.StringValue(cluster.DBClusterId),
            tea.StringValue(cluster.DBClusterStatus),
            tea.StringValue(cluster.DBVersion),
        )
    }
    
    return nil
}
```

### Describe Cluster Attribute

```go
func describeClusterAttribute(client *polardb.Client, clusterId string) error {
    request := &polardb.DescribeDBClusterAttributeRequest{
        DBClusterId: tea.String(clusterId),
    }
    
    response, err := client.DescribeDBClusterAttribute(request)
    if err != nil {
        return err
    }
    
    fmt.Printf("Cluster: %s\n", tea.StringValue(response.Body.DBClusterId))
    fmt.Printf("Status: %s\n", tea.StringValue(response.Body.DBClusterStatus))
    fmt.Printf("Class: %s\n", tea.StringValue(response.Body.DBClusterClass))
    
    return nil
}
```

### Cluster Lifecycle

```go
// Start cluster
func startCluster(client *polardb.Client, clusterId string) error {
    request := &polardb.StartDBClusterRequest{
        DBClusterId: tea.String(clusterId),
    }
    
    _, err := client.StartDBCluster(request)
    return err
}

// Stop cluster
func stopCluster(client *polardb.Client, clusterId string) error {
    request := &polardb.StopDBClusterRequest{
        DBClusterId: tea.String(clusterId),
    }
    
    _, err := client.StopDBCluster(request)
    return err
}

// Delete cluster
func deleteCluster(client *polardb.Client, clusterId string) error {
    request := &polardb.DeleteDBClusterRequest{
        DBClusterId: tea.String(clusterId),
    }
    
    _, err := client.DeleteDBCluster(request)
    return err
}
```

## Node Operations

```go
// Describe DB Nodes
func describeDBNodes(client *polardb.Client, clusterId string) error {
    request := &polardb.DescribeDBNodesRequest{
        DBClusterId: tea.String(clusterId),
    }
    
    response, err := client.DescribeDBNodes(request)
    if err != nil {
        return err
    }
    
    for _, node := range response.Body.DBNodes {
        fmt.Printf("Node: %s, Class: %s, Role: %s\n",
            tea.StringValue(node.DBNodeId),
            tea.StringValue(node.DBNodeClass),
            tea.StringValue(node.DBNodeRole),
        )
    }
    
    return nil
}

// Add read-only node
func addDBNode(client *polardb.Client, clusterId, nodeClass string) (*string, error) {
    request := &polardb.AddDBNodesRequest{
        DBClusterId:   tea.String(clusterId),
        DBNodeClass:   tea.String(nodeClass),
        ClientToken:   tea.String(uuid.New().String()),
    }
    
    response, err := client.AddDBNodes(request)
    if err != nil {
        return nil, err
    }
    
    return tea.String(response.Body.DBNodeId), nil
}
```

## Account Operations

```go
// Create account
func createAccount(client *polardb.Client, clusterId, accountName, password string) error {
    request := &polardb.CreateAccountRequest{
        DBClusterId:     tea.String(clusterId),
        AccountName:     tea.String(accountName),
        AccountPassword: tea.String(password),
        AccountType:     tea.String("Super"),
    }
    
    _, err := client.CreateAccount(request)
    return err
}

// Describe accounts
func describeAccounts(client *polardb.Client, clusterId string) error {
    request := &polardb.DescribeAccountsRequest{
        DBClusterId: tea.String(clusterId),
    }
    
    response, err := client.DescribeAccounts(request)
    if err != nil {
        return err
    }
    
    for _, account := range response.Body.Accounts.Account {
        fmt.Printf("Account: %s, Status: %s, Type: %s\n",
            tea.StringValue(account.AccountName),
            tea.StringValue(account.AccountStatus),
            tea.StringValue(account.AccountType),
        )
    }
    
    return nil
}
```

## Database Operations

```go
// Create database
func createDatabase(client *polardb.Client, clusterId, dbName string) error {
    request := &polardb.CreateDatabaseRequest{
        DBClusterId:     tea.String(clusterId),
        DBName:          tea.String(dbName),
        CharacterSetName: tea.String("UTF8"),
    }
    
    _, err := client.CreateDatabase(request)
    return err
}

// Describe databases
func describeDatabases(client *polardb.Client, clusterId string) error {
    request := &polardb.DescribeDatabasesRequest{
        DBClusterId: tea.String(clusterId),
    }
    
    response, err := client.DescribeDatabases(request)
    if err != nil {
        return err
    }
    
    for _, db := range response.Body.Databases.Database {
        fmt.Printf("Database: %s, Status: %s\n",
            tea.StringValue(db.DBName),
            tea.StringValue(db.DBStatus),
        )
    }
    
    return nil
}
```

## Backup Operations

```go
// Create backup
func createBackup(client *polardb.Client, clusterId string) (*string, error) {
    request := &polardb.CreateBackupRequest{
        DBClusterId: tea.String(clusterId),
        BackupType:  tea.String("FullBackup"),
    }
    
    response, err := client.CreateBackup(request)
    if err != nil {
        return nil, err
    }
    
    return tea.String(response.Body.BackupJobId), nil
}

// Describe backups
func describeBackups(client *polardb.Client, clusterId, startTime, endTime string) error {
    request := &polardb.DescribeBackupsRequest{
        DBClusterId: tea.String(clusterId),
        StartTime:   tea.String(startTime),
        EndTime:     tea.String(endTime),
    }
    
    response, err := client.DescribeBackups(request)
    if err != nil {
        return err
    }
    
    for _, backup := range response.Body.Items.Backup {
        fmt.Printf("Backup: %s, Size: %s, Status: %s\n",
            tea.StringValue(backup.BackupId),
            tea.StringValue(backup.BackupSize),
            tea.StringValue(backup.BackupStatus),
        )
    }
    
    return nil
}
```

## Error Handling

```go
package main

import (
    "errors"
    "fmt"
    "time"
    
    "github.com/alibabacloud-go/tea/tea"
)

// SDKError - SDK错误处理
type SDKError struct {
    Code    string
    Message string
    RequestId string
}

func (e *SDKError) Error() string {
    return fmt.Sprintf("SDK Error [%s]: %s (RequestId: %s)", e.Code, e.Message, e.RequestId)
}

// parseError - 解析 SDK 错误
func parseError(err error) *SDKError {
    if err == nil {
        return nil
    }
    
    var sdkErr *tea.SDKError
    if errors.As(err, &sdkErr) {
        return &SDKError{
            Code:    tea.StringValue(sdkErr.Code),
            Message: tea.StringValue(sdkErr.Message),
            RequestId: tea.StringValue(sdkErr.RequestId),
        }
    }
    
    return &SDKError{
        Code:    "Unknown",
        Message: err.Error(),
    }
}

// RetryConfig - 重试配置
type RetryConfig struct {
    MaxRetries  int
    RetryDelay  time.Duration
    RetryableCodes []string
}

// DefaultRetryConfig - 默认重试配置
var DefaultRetryConfig = &RetryConfig{
    MaxRetries:  3,
    RetryDelay:  5 * time.Second,
    RetryableCodes: []string{"Throttling", "ServiceUnavailable", "InternalError"},
}

// isRetryable - 检查错误是否可重试
func isRetryable(err *SDKError, config *RetryConfig) bool {
    for _, code := range config.RetryableCodes {
        if err.Code == code {
            return true
        }
    }
    return false
}

// executeWithRetry - 带重试的执行
func executeWithRetry(operation func() error, config *RetryConfig) error {
    if config == nil {
        config = DefaultRetryConfig
    }
    
    var lastErr error
    
    for i := 0; i <= config.MaxRetries; i++ {
        err := operation()
        if err == nil {
            return nil
        }
        
        sdkErr := parseError(err)
        lastErr = sdkErr
        
        if !isRetryable(sdkErr, config) {
            return err
        }
        
        if i < config.MaxRetries {
            fmt.Printf("Retry %d/%d after %v: %s\n", i+1, config.MaxRetries, config.RetryDelay, sdkErr.Code)
            time.Sleep(config.RetryDelay)
        }
    }
    
    return lastErr
}
```

## Polling Helpers

```go
package main

import (
    "fmt"
    "time"
    
    polardb "github.com/alibabacloud-go/polardb-20220530/v3/client"
    "github.com/alibabacloud-go/tea/tea"
)

// WaitForClusterState - 等待集群达到目标状态
func WaitForClusterState(client *polardb.Client, clusterId, targetState string, timeout time.Duration) error {
    deadline := time.Now().Add(timeout)
    interval := 10 * time.Second
    
    for time.Now().Before(deadline) {
        request := &polardb.DescribeDBClusterAttributeRequest{
            DBClusterId: tea.String(clusterId),
        }
        
        response, err := client.DescribeDBClusterAttribute(request)
        if err != nil {
            return err
        }
        
        currentState := tea.StringValue(response.Body.DBClusterStatus)
        fmt.Printf("Cluster state: %s (waiting for %s)\n", currentState, targetState)
        
        if currentState == targetState {
            return nil
        }
        
        time.Sleep(interval)
    }
    
    return fmt.Errorf("timeout waiting for cluster %s to reach state %s", clusterId, targetState)
}

// WaitForAccountAvailable - 等待账户可用
func WaitForAccountAvailable(client *polardb.Client, clusterId, accountName string, timeout time.Duration) error {
    deadline := time.Now().Add(timeout)
    interval := 5 * time.Second
    
    for time.Now().Before(deadline) {
        request := &polardb.DescribeAccountsRequest{
            DBClusterId: tea.String(clusterId),
        }
        
        response, err := client.DescribeAccounts(request)
        if err != nil {
            return err
        }
        
        for _, account := range response.Body.Accounts.Account {
            if tea.StringValue(account.AccountName) == accountName {
                status := tea.StringValue(account.AccountStatus)
                fmt.Printf("Account %s status: %s\n", accountName, status)
                
                if status == "Available" {
                    return nil
                }
            }
        }
        
        time.Sleep(interval)
    }
    
    return fmt.Errorf("timeout waiting for account %s to become available", accountName)
}
```

## Complete Example

```go
package main

import (
    "fmt"
    "os"
    "time"
    
    "github.com/google/uuid"
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    polardb "github.com/alibabacloud-go/polardb-20220530/v3/client"
    "github.com/alibabacloud-go/tea/tea"
)

func main() {
    // Create client
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    
    client, err := polardb.NewClient(config)
    if err != nil {
        panic(err)
    }
    
    // Create cluster
    createReq := &polardb.CreateDBClusterRequest{
        RegionId:       tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
        DBType:         tea.String("PostgreSQL"),
        DBVersion:      tea.String("14"),
        DBClusterClass: tea.String("polar.pg.g2.xlarge"),
        DBNodeClass:    tea.String("polar.pg.g2.xlarge"),
        ZoneId:         tea.String(os.Getenv("ZONE_ID")),
        VPCId:          tea.String(os.Getenv("VPC_ID")),
        VSwitchId:      tea.String(os.Getenv("VSWITCH_ID")),
        PayType:        tea.String("Postpaid"),
        ClientToken:    tea.String(uuid.New().String()),
    }
    
    createResp, err := client.CreateDBCluster(createReq)
    if err != nil {
        panic(err)
    }
    
    clusterId := tea.StringValue(createResp.Body.DBClusterId)
    fmt.Printf("Created cluster: %s\n", clusterId)
    
    // Wait for cluster running
    fmt.Println("Waiting for cluster to be running...")
    err = WaitForClusterState(client, clusterId, "Running", 10*time.Minute)
    if err != nil {
        panic(err)
    }
    
    // Create account
    accountReq := &polardb.CreateAccountRequest{
        DBClusterId:     tea.String(clusterId),
        AccountName:     tea.String("admin"),
        AccountPassword: tea.String("Password123!"),
        AccountType:     tea.String("Super"),
    }
    
    _, err = client.CreateAccount(accountReq)
    if err != nil {
        panic(err)
    }
    
    fmt.Println("Account created")
    
    // Wait for account available
    err = WaitForAccountAvailable(client, clusterId, "admin", 2*time.Minute)
    if err != nil {
        panic(err)
    }
    
    fmt.Println("Account is available")
    
    // Create database
    dbReq := &polardb.CreateDatabaseRequest{
        DBClusterId:      tea.String(clusterId),
        DBName:           tea.String("mydb"),
        CharacterSetName: tea.String("UTF8"),
    }
    
    _, err = client.CreateDatabase(dbReq)
    if err != nil {
        panic(err)
    }
    
    fmt.Println("Database created")
    fmt.Println("Setup complete!")
}
```
