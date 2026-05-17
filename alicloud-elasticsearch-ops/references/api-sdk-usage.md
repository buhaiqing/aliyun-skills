# API & SDK Usage — Alibaba Cloud Elasticsearch

> **Purpose:** Operation map, request/response fields, pagination patterns, SDK code examples.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-17
> **SDK Package:** `github.com/alibabacloud-go/elasticsearch-20170613/v6/client`
> **API Version:** `2017-06-13`

---

## 1. SDK Package Information

| Property | Value |
|----------|-------|
| **Go SDK** | `github.com/alibabacloud-go/elasticsearch-20170613/v6/client` |
| **API Version** | `2017-06-13` |
| **Endpoint** | `elasticsearch.aliyuncs.com` (public) |
| **VPC Endpoint** | `<region>.elasticsearch-vpc.aliyuncs.com` |
| **Documentation** | [OpenAPI Portal](https://api.aliyun.com/product/Elasticsearch) |

---

## 2. Client Initialization

```go
package main

import (
    "fmt"
    "os"
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    elasticsearch "github.com/alibabacloud-go/elasticsearch-20170613/v6/client"
)

func main() {
    // Create configuration
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("elasticsearch.aliyuncs.com"),
    }
    
    // Create client
    client, err := elasticsearch.NewClient(config)
    if err != nil {
        panic(err)
    }
    
    // Client is ready for operations
    fmt.Println("✅ Elasticsearch client initialized")
}
```

---

## 3. Operations Map

### Instance Lifecycle Operations

| Goal | API Method | SDK Function | Notes |
|------|------------|--------------|-------|
| Create instance | CreateInstance | `client.CreateInstance(request)` | Requires VPC, VSwitch |
| Describe instance | DescribeInstance | `client.DescribeInstance(request)` | Get detailed info |
| List instances | ListInstance | `client.ListInstance(request)` | Pagination supported |
| Update instance | UpdateInstance | `client.UpdateInstance(request)` | Modify configuration |
| Delete instance | DeleteInstance | `client.DeleteInstance(request)` | Irreversible |
| Restart instance | RestartInstance | `client.RestartInstance(request)` | Service interruption |

### Snapshot Operations

| Goal | API Method | SDK Function | Notes |
|------|------------|--------------|-------|
| Create snapshot | CreateSnapshot | `client.CreateSnapshot(request)` | Backup operation |
| Describe snapshot | DescribeSnapshot | `client.DescribeSnapshot(request)` | Get snapshot details |
| List snapshots | ListSnapshots | `client.ListSnapshots(request)` | Pagination |
| Delete snapshot | DeleteSnapshot | `client.DeleteSnapshot(request)` | Remove backup |

### Plugin Operations

| Goal | API Method | SDK Function | Notes |
|------|------------|--------------|-------|
| Install plugin | InstallSystemPlugin | `client.InstallSystemPlugin(request)` | System plugin |
| Install user plugin | InstallUserPlugins | `client.InstallUserPlugins(request)` | Custom plugin |
| List plugins | ListPlugins | `client.ListPlugins(request)` | Installed plugins |
| Uninstall plugin | UninstallPlugin | `client.UninstallPlugin(request)` | Remove plugin |

### Version & Upgrade Operations

| Goal | API Method | SDK Function | Notes |
|------|------------|--------------|-------|
| Get region config | GetRegionConfiguration | `client.GetRegionConfiguration(request)` | Available versions |
| Upgrade version | UpgradeEngineVersion | `client.UpgradeEngineVersion(request)` | Version upgrade |
| Get upgrade info | UpgradeInfo | `client.UpgradeInfo(request)` | Upgrade status |

### Network & Security Operations

| Goal | API Method | SDK Function | Notes |
|------|------------|--------------|-------|
| Modify whitelist | ModifyWhiteIps | `client.ModifyWhiteIps(request)` | IP whitelist |
| Update public network | UpdatePublicNetwork | `client.UpdatePublicNetwork(request)` | Public access |
| Open HTTPS | OpenHttps | `client.OpenHttps(request)` | Enable TLS |
| Close HTTPS | CloseHttps | `client.CloseHttps(request)` | Disable TLS |
| Update password | UpdateAdminPassword | `client.UpdateAdminPassword(request)` | Admin password |

### Diagnostic Operations

| Goal | API Method | SDK Function | Notes |
|------|------------|--------------|-------|
| Diagnose instance | DiagnoseInstance | `client.DiagnoseInstance(request)` | Health check |
| List diagnose reports | ListDiagnoseReport | `client.ListDiagnoseReport(request)` | Report history |
| Describe health | DescribeElasticsearchHealth | `client.DescribeElasticsearchHealth(request)` | Cluster health |

---

## 4. Request/Response Examples

### CreateInstance

**Request:**
```go
request := &elasticsearch.CreateInstanceRequest{
    RegionId:          tea.String("cn-hangzhou"),
    InstanceName:      tea.String("my-es-cluster"),
    EsVersion:         tea.String("7.10_aliyun"),
    NodeSpec:          tea.String("elasticsearch.sn2ne.large"),
    DataNodeAmount:    tea.Int32(3),
    DiskType:          tea.String("cloud_ssd"),
    DiskSize:          tea.Int32(100),
    VpcId:             tea.String("vpc-xxx"),
    VswitchId:         tea.String("vsw-xxx"),
    Password:          tea.String("MyPassword123!"),
    ChargeType:        tea.String("PostPaid"),  // Pay-as-you-go
}
```

**Response:**
```json
{
  "RequestId": "XXX-XXX-XXX",
  "Result": {
    "InstanceId": "es-cn-xxx",
    "InstanceName": "my-es-cluster",
    "Status": "Activating"
  }
}
```

**Key Fields:**

| Path | Type | Description |
|------|------|-------------|
| `Body.Result.InstanceId` | string | New instance ID |
| `Body.Result.InstanceName` | string | Instance name |
| `Body.Result.Status` | string | Initial status |

### DescribeInstance

**Request:**
```go
request := &elasticsearch.DescribeInstanceRequest{
    InstanceId: tea.String("es-cn-xxx"),
}
```

**Response:**
```json
{
  "RequestId": "XXX",
  "Result": {
    "InstanceId": "es-cn-xxx",
    "InstanceName": "my-es-cluster",
    "RegionId": "cn-hangzhou",
    "Status": "Normal",
    "EsVersion": "7.10_aliyun",
    "NodeAmount": 3,
    "NodeSpec": "elasticsearch.sn2ne.large",
    "DiskType": "cloud_ssd",
    "DiskSize": 100,
    "Endpoints": [
      {
        "EndpointType": "Public",
        "Endpoint": "es-cn-xxx.elasticsearch.aliyuncs.com"
      }
    ],
    "KibanaEndpoint": "https://es-cn-xxx.kibana.elasticsearch.aliyuncs.com",
    "CreatedAt": "2026-05-17T10:00:00Z"
  }
}
```

**Key Fields:**

| Path | Type | Description |
|------|------|-------------|
| `Body.Result.InstanceId` | string | Instance identifier |
| `Body.Result.Status` | string | Lifecycle state |
| `Body.Result.EsVersion` | string | Elasticsearch version |
| `Body.Result.NodeAmount` | int32 | Number of data nodes |
| `Body.Result.Endpoints` | array | Connection endpoints |

### ListInstance

**Request:**
```go
request := &elasticsearch.ListInstanceRequest{
    RegionId: tea.String("cn-hangzhou"),
    PageNumber: tea.Int32(1),
    PageSize:   tea.Int32(20),
    // Optional filters:
    Status:     tea.String("Normal"),
    InstanceName: tea.String("prefix-"),
}
```

**Response:**
```json
{
  "RequestId": "XXX",
  "Result": {
    "Instances": [
      {
        "InstanceId": "es-cn-xxx1",
        "InstanceName": "my-cluster-1",
        "Status": "Normal",
        "EsVersion": "7.10_aliyun"
      },
      {
        "InstanceId": "es-cn-xxx2",
        "InstanceName": "my-cluster-2",
        "Status": "Normal",
        "EsVersion": "8.9_aliyun"
      }
    ],
    "TotalCount": 45,
    "PageNumber": 1,
    "PageSize": 20
  }
}
```

**Pagination Pattern:**

| Field | Type | Usage |
|-------|------|-------|
| `PageNumber` | int32 | Current page (starts at 1) |
| `PageSize` | int32 | Items per page (default 20, max 100) |
| `TotalCount` | int32 | Total instances |
| `Body.Result.Instances` | array | Instance list |

---

## 5. Error Handling

### SDK Error Structure

```go
response, err := client.CreateInstance(request)
if err != nil {
    // Parse error
    if sdkErr, ok := err.(*tea.SDKError); ok {
        fmt.Printf("Error Code: %s\n", tea.ToString(sdkErr.Code))
        fmt.Printf("Error Message: %s\n", tea.ToString(sdkErr.Message))
        fmt.Printf("Request ID: %s\n", tea.ToString(sdkErr.RequestId))
    }
    panic(err)
}
```

### Common Error Codes

| Code | HTTP Status | Description | Recovery |
|------|-------------|-------------|----------|
| `InvalidParameter` | 400 | Invalid request parameter | Fix parameter per API spec |
| `InvalidParameter.Value` | 400 | Parameter value out of range | Use valid value |
| `MissingParameter` | 400 | Required parameter missing | Add required field |
| `InstanceNotFound` | 404 | Instance does not exist | Verify instance ID |
| `RegionNotSupported` | 400 | Region not supported | Use supported region |
| `QuotaExceeded` | 400 | Resource quota exceeded | Request quota increase |
| `VpcNotFound` | 404 | VPC not found | Create VPC first |
| `VswitchNotFound` | 404 | VSwitch not found | Create VSwitch first |
| `Forbidden.RAM` | 403 | RAM permission denied | Add RAM policy |
| `OperationDenied` | 403 | Operation not allowed | Check instance status |
| `Throttling` | 429 | Rate limit exceeded | Retry with backoff |
| `InternalError` | 500 | Server internal error | Retry; escalate with RequestId |
| `ServiceUnavailable` | 503 | Service temporarily unavailable | Retry later |

---

## 6. Pagination Pattern

### Iterate All Instances

```go
func listAllInstances(client *elasticsearch.Client, regionId string) ([]*elasticsearch.Instance, error) {
    var allInstances []*elasticsearch.Instance
    pageNum := int32(1)
    pageSize := int32(50)
    
    for {
        request := &elasticsearch.ListInstanceRequest{
            RegionId:   tea.String(regionId),
            PageNumber: tea.Int32(pageNum),
            PageSize:   tea.Int32(pageSize),
        }
        
        response, err := client.ListInstance(request)
        if err != nil {
            return nil, err
        }
        
        instances := response.Body.Result.Instance
        allInstances = append(allInstances, instances...)
        
        totalCount := tea.ToInt32(response.Body.Result.TotalCount)
        if len(allInstances) >= totalCount {
            break
        }
        pageNum++
    }
    
    return allInstances, nil
}
```

---

## 7. Async Operation Polling

### Poll Until Stable State

```go
import "time"

func waitForInstanceReady(client *elasticsearch.Client, instanceId string, maxWaitSeconds int) error {
    for i := 0; i < maxWaitSeconds/10; i++ {
        response, err := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
            InstanceId: tea.String(instanceId),
        })
        if err != nil {
            return err
        }
        
        status := tea.ToString(response.Body.Result.Status)
        if status == "Normal" {
            return nil // Ready
        }
        if status == "Failed" {
            return fmt.Errorf("instance creation failed")
        }
        
        time.Sleep(10 * time.Second)
    }
    return fmt.Errorf("timeout waiting for instance")
}
```

---

## 8. Complete SDK Script Template

```go
// main.go — Full template for JIT execution
package main

import (
    "fmt"
    "os"
    "time"
    
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    elasticsearch "github.com/alibabacloud-go/elasticsearch-20170613/v6/client"
)

func main() {
    // Validate environment
    if os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID") == "" {
        panic("ALIBABA_CLOUD_ACCESS_KEY_ID not set")
    }
    if os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET") == "" {
        panic("ALIBABA_CLOUD_ACCESS_KEY_SECRET not set")
    }
    if os.Getenv("ALIBABA_CLOUD_REGION_ID") == "" {
        panic("ALIBABA_CLOUD_REGION_ID not set")
    }
    
    // Create client
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("elasticsearch.aliyuncs.com"),
    }
    
    client, err := elasticsearch.NewClient(config)
    if err != nil {
        panic(err)
    }
    
    // Execute operation (example: list instances)
    response, err := client.ListInstance(&elasticsearch.ListInstanceRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    })
    if err != nil {
        panic(err)
    }
    
    // Print results
    for _, inst := range response.Body.Result.Instance {
        fmt.Printf("Instance: %s | Status: %s | Version: %s\n",
            tea.ToString(inst.InstanceId),
            tea.ToString(inst.Status),
            tea.ToString(inst.EsVersion))
    }
}
```

---

*For troubleshooting common API errors, see [troubleshooting.md](troubleshooting.md).*