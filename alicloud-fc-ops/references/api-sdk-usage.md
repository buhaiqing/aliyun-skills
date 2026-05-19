# API & SDK — Function Compute (FC 3.0)

## OpenAPI Specification

- **API Version**: `FC/2023-03-30`
- **Style**: ROA (RESTful, not RPC)
- **Base Endpoint**: `https://fcv3.<region_id>.aliyuncs.com`
- **Authentication**: Alibaba Cloud Signature v1.0
- **Content-Type**: `application/json`
- **Reference**: [API Overview](https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-fc-2023-03-30-overview)

## SDK Operations Map

| Goal | API OperationId | SDK Method | HTTP Method | Path |
|------|----------------|------------|-------------|------|
| Create function | CreateFunction | `client.CreateFunction` | POST | `/2023-03-30/functions` |
| Get function | GetFunction | `client.GetFunction` | GET | `/2023-03-30/functions/{functionName}` |
| List functions | ListFunctions | `client.ListFunctions` | GET | `/2023-03-30/functions` |
| Update function | UpdateFunction | `client.UpdateFunction` | PUT | `/2023-03-30/functions/{functionName}` |
| Delete function | DeleteFunction | `client.DeleteFunction` | DELETE | `/2023-03-30/functions/{functionName}` |
| Invoke (sync) | InvokeFunction | `client.InvokeFunction` | POST | `/2023-03-30/functions/{functionName}/invocations` |
| Create trigger | CreateTrigger | `client.CreateTrigger` | POST | `/2023-03-30/functions/{functionName}/triggers` |
| Get trigger | GetTrigger | `client.GetTrigger` | GET | `/2023-03-30/functions/{functionName}/triggers/{triggerName}` |
| List triggers | ListTriggers | `client.ListTriggers` | GET | `/2023-03-30/functions/{functionName}/triggers` |
| Update trigger | UpdateTrigger | `client.UpdateTrigger` | PUT | `/2023-03-30/functions/{functionName}/triggers/{triggerName}` |
| Delete trigger | DeleteTrigger | `client.DeleteTrigger` | DELETE | `/2023-03-30/functions/{functionName}/triggers/{triggerName}` |
| Set provision config | PutProvisionConfig | `client.PutProvisionConfig` | PUT | `/2023-03-30/functions/{functionName}/provision-config` |
| Get provision config | GetProvisionConfig | `client.GetProvisionConfig` | GET | `/2023-03-30/functions/{functionName}/provision-config` |
| List provision configs | ListProvisionConfigs | `client.ListProvisionConfigs` | GET | `/2023-03-30/provision-configs` |
| Set concurrency config | PutConcurrencyConfig | `client.PutConcurrencyConfig` | PUT | `/2023-03-30/functions/{functionName}/concurrency-config` |
| Get concurrency config | GetConcurrencyConfig | `client.GetConcurrencyConfig` | GET | `/2023-03-30/functions/{functionName}/concurrency-config` |
| List concurrency configs | ListConcurrencyConfigs | `client.ListConcurrencyConfigs` | GET | `/2023-03-30/concurrency-configs` |
| Set async invoke config | PutAsyncInvokeConfig | `client.PutAsyncInvokeConfig` | PUT | `/2023-03-30/functions/{functionName}/async-invoke-config` |
| Get async invoke config | GetAsyncInvokeConfig | `client.GetAsyncInvokeConfig` | GET | `/2023-03-30/functions/{functionName}/async-invoke-config` |
| List async invoke configs | ListAsyncInvokeConfigs | `client.ListAsyncInvokeConfigs` | GET | `/2023-03-30/async-invoke-configs` |
| Delete async invoke config | DeleteAsyncInvokeConfig | `client.DeleteAsyncInvokeConfig` | DELETE | `/2023-03-30/functions/{functionName}/async-invoke-config` |
| Create session | CreateSession | `client.CreateSession` | POST | `/2023-03-30/sessions` |
| Get session | GetSession | `client.GetSession` | GET | `/2023-03-30/sessions/{sessionId}` |
| List sessions | ListSessions | `client.ListSessions` | GET | `/2023-03-30/sessions` |
| Delete session | DeleteSession | `client.DeleteSession` | DELETE | `/2023-03-30/sessions/{sessionId}` |
| Set scaling config | PutScalingConfig | `client.PutScalingConfig` | PUT | `/2023-03-30/functions/{functionName}/scaling-config` |
| Get scaling config | GetScalingConfig | `client.GetScalingConfig` | GET | `/2023-03-30/functions/{functionName}/scaling-config` |
| Delete scaling config | DeleteScalingConfig | `client.DeleteScalingConfig` | DELETE | `/2023-03-30/functions/{functionName}/scaling-config` |

## GPU Functions

GPU workloads reuse the operations above. Additional request-body fields on **CreateFunction** / **UpdateFunction**:

| Field | Type | Purpose |
|-------|------|---------|
| `gpuConfig.gpuType` | string | e.g. `fc.gpu.ada.1`, `fc.gpu.ampere.1`, `fc.gpu.tesla.1` |
| `gpuConfig.gpuMemorySize` | integer | VRAM in MB (multiple of 1024) |
| `customContainerConfig` | object | `image`, `port`, `command`, `entrypoint` — **required** for GPU |
| `instanceConcurrency` | integer | Use **1** for vLLM continuous batching |
| `instanceLifecycleConfig.initializer` | object | Model warmup before traffic |
| `nasConfig` / `ossMountConfig` | object | Model weights / batch I/O |
| `logConfig.enableLlmMetrics` | boolean | vLLM/SGLang metrics (custom log config only) |

| Scenario | Key SDK calls |
|----------|---------------|
| Online vLLM | `CreateFunction` → `PutScalingConfig` → `CreateTrigger` (http) |
| Quasi-real-time | `PutScalingConfig` with `minInstances: 0` |
| Offline batch | `CreateFunction` → `PutAsyncInvokeConfig` → `InvokeFunction` (Async header) or OSS `CreateTrigger` |
| Resident pool | `PutScalingConfig` with `residentPoolId` |

CLI/SDK examples: [gpu-inference.md §10](gpu-inference.md#10-cli--api--sdk-by-scenario). Struct reference: [GpuConfig](https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-fc-2023-03-30-struct-gpuconfig), [CreateFunctionInput](https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-fc-2023-03-30-struct-createfunctioninput).

**Out of scope:** Function AI managed model services (separate control plane, not `fc-20230330` client).

## Go SDK Usage

```go
// main.go — FC SDK client initialization
package main

import (
    "fmt"
    "os"
    
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    fc "github.com/alibabacloud-go/fc-20230330/v4/client"
    "github.com/alibabacloud-go/tea/tea"
)

func CreateFCClient(region string) (*fc.Client, error) {
    endpoint := fmt.Sprintf("https://fcv3.%s.aliyuncs.com", region)
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String(endpoint),
    }
    return fc.NewClient(config)
}
```

## Pagination Pattern

All List operations use `nextToken` + `limit` pagination:

```bash
# First page
aliyun fc-open GET "/2023-03-30/functions?limit=50"
# Parse nextToken from response
# Subsequent pages
aliyun fc-open GET "/2023-03-30/functions?limit=50&nextToken={token}"
```

## Request / Response Notes

- **Request body**: JSON, optional fields may be omitted
- **Response format**: Standard FC envelope with `Body` containing the actual response object
- **Required headers**: Authorization, Date, x-fc-account-id (for some endpoints)
- **Invocation types**: `Sync` (default) or `Async` via `x-fc-invocation-type` header
