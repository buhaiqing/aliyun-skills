# Advisor — API & SDK Usage

> **Fallback path.** Use the `aliyun advisor` CLI for all operations.
> This document is for users who need to embed Advisor calls in a
> larger Go program (e.g. CI pipeline, automated cost report, integration
> with internal observability).

## When to Use SDK

Use the SDK only when:

- You need to embed the inspection call in a Go program that already
  has Alibaba Cloud SDK integration.
- You need fine-grained control over retry, throttling, or
  observability that the CLI doesn't expose.
- You're building a service that consumes Advisor output programmatically
  (e.g. monthly cost report generator, alerting pipeline).

For one-off queries, always prefer the CLI.

## Go SDK Package

| Item | Value |
|------|-------|
| Module | `github.com/alibabacloud-go/advisor-20180120` |
| API version | 2018-01-20 |
| Service endpoint | `advisor.aliyuncs.com` (regional endpoints also exist) |
| Client class | `*advisor.Client` |

## Quick Bootstrap

```go
package main

import (
    "fmt"
    "os"
    "time"

    advisor "github.com/alibabacloud-go/advisor-20180120/v3/client"
    "github.com/alibabacloud-go/tea/tea"
    "github.com/alibabacloud-go/tea-openapi/service"
)

func newClient() (*advisor.Client, error) {
    cfg := &service.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
        Endpoint:        tea.String("advisor.aliyuncs.com"),
        ReadTimeout:     tea.Int(30 * 1000),
        ConnectTimeout:  tea.Int(10 * 1000),
    }
    return advisor.NewClient(cfg)
}

func main() {
    client, err := newClient()
    if err != nil {
        fmt.Fprintf(os.Stderr, "[ERROR] client init: %v\n", err)
        os.Exit(1)
    }

    resp, err := client.DescribeAdvices(&advisor.DescribeAdvicesRequest{})
    if err != nil {
        fmt.Fprintf(os.Stderr, "[ERROR] describe: %v\n", err)
        os.Exit(2)
    }
    if resp.Body == nil {
        fmt.Fprintln(os.Stderr, "[WARN] empty body")
        os.Exit(0)
    }
    fmt.Printf("RequestId: %s, Advices: %d\n",
        tea.StringValue(resp.Body.RequestId),
        len(resp.Body.Advices),
    )
}
```

> **安全提醒：** 严禁将 `AccessKeySecret` 写入日志、fmt 输出或 panic message。
> 任何 SK 出现于日志都会被审计系统告警。

## Operation Reference

The SDK has a 1-to-1 mapping with the CLI operations. Below are the
most common ones; for the full list, run `aliyun advisor --help`.

### DescribeAdvices

```go
req := &advisor.DescribeAdvicesRequest{
    Product:     tea.String("Ecs"),
    BizLanguage: tea.String("en"),
}
resp, err := client.DescribeAdvices(req)
if err != nil { /* handle */ }

for _, a := range resp.Body.Advices {
    fmt.Printf("[%s] %s on %s — %s\n",
        tea.StringValue(a.Severity),
        tea.StringValue(a.CheckId),
        tea.StringValue(a.ResourceId),
        tea.StringValue(a.AdviceName),
    )
}
```

### DescribeAdvicesPage (paginated)

```go
pageNum := 1
pageSize := 50
for {
    req := &advisor.DescribeAdvicesPageRequest{
        PageNumber: tea.Int32(int32(pageNum)),
        PageSize:   tea.Int32(int32(pageSize)),
    }
    resp, err := client.DescribeAdvicesPage(req)
    if err != nil { break }

    for _, a := range resp.Body.Advices {
        // process
    }
    if int(tea.Int32Value(resp.Body.TotalCount)) <= pageNum*pageSize {
        break
    }
    pageNum++
}
```

### DescribeAdvisorChecks

```go
req := &advisor.DescribeAdvisorChecksRequest{
    Product: tea.String("Ecs"),
}
resp, _ := client.DescribeAdvisorChecks(req)
for _, c := range resp.Body.Checks {
    fmt.Printf("%s [%s] — %s\n",
        tea.StringValue(c.CheckId),
        tea.StringValue(c.Severity),
        tea.StringValue(c.CheckName),
    )
}
```

### DescribeCostOptimizationOverview

```go
req := &advisor.DescribeCostOptimizationOverviewRequest{}
resp, _ := client.DescribeCostOptimizationOverview(req)
if resp.Body.Overview != nil {
    fmt.Printf("Total monthly savings: %s\n",
        tea.StringValue(resp.Body.Overview.TotalSavings),
    )
}
```

### GetInspectProgress (polling)

```go
// RefreshAdvisorCheck returned a TaskId
taskId := int32(12345)
for i := 0; i < 20; i++ {
    resp, _ := client.GetInspectProgress(&advisor.GetInspectProgressRequest{
        TaskId: tea.Int32(taskId),
    })
    status := tea.StringValue(resp.Body.Status)
    fmt.Printf("[%d/20] Status: %s\n", i+1, status)
    if status == "Finished" || status == "Failed" {
        break
    }
    time.Sleep(30 * time.Second)
}
```

### RefreshAdvisorCheck (side effect)

```go
// ALWAYS require explicit user confirmation before calling this
resp, err := client.RefreshAdvisorCheck(&advisor.RefreshAdvisorCheckRequest{
    Product: tea.String("Ecs"),
})
if err != nil { /* handle */ }
taskId := resp.Body.TaskId
// poll via GetInspectProgress
```

## Throttling and Retry

The SDK has built-in throttling via the `tea` library. Recommended
pattern for high-frequency callers:

```go
import "github.com/alibabacloud-go/tea/tea/oss"

retryer := oss.NewRetryer(
    tea.Int(3),                  // max attempts
    tea.Bool(false),             // no jitter
    tea.Int(1000),               // initial backoff ms
    tea.Int(8000),               // max backoff ms
)
// pass retryer to config
```

For 429/Throttling errors, the SDK auto-retries with exponential
backoff up to the configured maximum. For business errors
(`InvalidParameter`, `Forbidden`), no retry is performed.

## Error Handling Pattern

```go
resp, err := client.DescribeAdvices(req)
if err != nil {
    // SDK error: includes HTTP/SDK-level issues
    if tea.IsServiceError(err) {
        se := err.(*tea.ServiceError)
        fmt.Printf("[ERROR] %s: %s (status=%d)\n",
            se.Code, se.Message, se.StatusCode)
    } else {
        fmt.Printf("[ERROR] network: %v\n", err)
    }
    return
}
// business error (in response body)
if resp.Body.Code != nil && *resp.Body.Code != "" {
    fmt.Printf("[BUSINESS-ERROR] %s: %s\n",
        *resp.Body.Code, *resp.Body.Message)
    return
}
```

## Multi-Account Support

Use `--assume-aliyun-id` in CLI, or in SDK, the
`AssumeAliyunId` request field:

```go
resp, _ := client.DescribeAdvices(&advisor.DescribeAdvicesRequest{
    AssumeAliyunId: tea.Int64(12345),
})
```

The RAM role used must have `advisor:Describe*` permissions on the
target account.

## Limitations

- **No streaming** — the OpenAPI does not support streaming responses;
  for very large accounts, paginate and process in chunks.
- **No webhooks** — the service does not push events; you must poll
  `DescribeAdvices` or trigger via `RefreshAdvisorCheck` + poll.
- **Region parameter** — most operations accept no region; the service
  is global. Specifying `--region cn-hangzhou` is optional and may be
  ignored.

## Sandbox Verification

```bash
# Verify SDK compiles
cd assets/code-snippets
go mod tidy
go vet ./...
go build ./...
```

(For this `cli-first` skill, snippets are not bundled in
`assets/code-snippets/`. The above is for users who create their own
SDK wrapper.)

## Reference Links

- [Alibaba Cloud Advisor OpenAPI](https://help.aliyun.com/zh/advisor/developer-reference/api-advisor-2018-01-20-overview)
- [Go SDK source](https://github.com/alibabacloud-go/advisor-20180120)
- [Tea SDK retry/credentials](https://github.com/alibabacloud-go/tea)
