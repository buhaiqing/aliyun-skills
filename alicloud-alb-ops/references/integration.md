# Integration — ALB

> Version: 1.0.0 | Last Updated: 2026-06-07

## Environment Setup

**Primary path:** `aliyun alb` CLI (static Go binary, no runtime dependencies)

**Fallback path:** JIT Go SDK via `alb-20200616/v2/client`

## Go SDK Package

```
github.com/alibabacloud-go/alb-20200616/v2/client
```

## JIT Go SDK Workflow

```bash
# Initialize workspace
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script

# Set proxy for China CDN mirror
export GOPROXY="https://goproxy.cn,direct"

# Install dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/tea-utils/v2/service
go get github.com/alibabacloud-go/alb-20200616/v2/client

# Run script
go run ./main.go
```

## Go SDK Script Template

```go
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    alb "github.com/alibabacloud-go/alb-20200616/v2/client"
)

func main() {
    config := &openapi.Config{
        // ALB endpoint: alb.aliyuncs.com (or VPC endpoint for private access)
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
    }
    // Option 1: default public endpoint
    // config.Endpoint = tea.String("alb.aliyuncs.com")

    client, err := alb.NewClient(config)
    if err != nil {
        panic(err)
    }

    // Operation-specific code (replace with target operation)
    listReq := &alb.ListLoadBalancersRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    response, err := client.ListLoadBalancers(listReq)
    if err != nil {
        panic(err)
    }
    fmt.Println(tea.ToString(response.Body))
}
```

## SDK Package Naming Reference

| Product | Go SDK Package |
|---------|---------------|
| ALB | `github.com/alibabacloud-go/alb-20200616/v2/client` |
| ECS | `github.com/alibabacloud-go/ecs-20140526/v4/client` |
| VPC | `github.com/alibabacloud-go/vpc-20160428/v3/client` |
| CMS | `github.com/alibabacloud-go/cms-20190101/v2/client` |

Find package names at: https://github.com/alibabacloud-go

## Security

- **ALB credentials:** Use `os.Getenv("...")` in Go scripts — never hardcode secrets
- **Endpoint:** Public endpoint `alb.aliyuncs.com` or VPC endpoint for private subnets (`.vpc.aliyuncs.com`)
- **IAM:** Minimum RAM policies: `alb:*` for full management, or individual action permissions

## Cross-Skill Delegation Matrix

| Scenario | Delegate To | Action |
|----------|-------------|--------|
| VPC/VSwitch verification | `alicloud-vpc-ops` | Verify VPC/VSwitch exist before ALB creation |
| EIP/bandwidth package | `alicloud-eip-ops` | Associate EIP or shared bandwidth with ALB |
| Security group | `alicloud-ecs-ops` / `alicloud-vpc-ops` | Verify/modify security group rules |
| ECS backend health | `alicloud-ecs-ops` | Check ECS instance status and health when backend unhealthy |
| WAF attachment | `alicloud-waf-ops` | Configure WAF protection for ALB |
| Monitoring alerts | `alicloud-cms-ops` | Set up CloudMonitor alarm rules for ALB metrics |
| DNS configuration | `alicloud-dns-ops` | Configure DNS CNAME to ALB DNSName |
| Certificate management | `alicloud-cas-ops` | Upload and manage SSL certificates |
| Access logs (SLS) | `alicloud-sls-ops` | Create and manage SLS projects/logstores for ALB access logs |
| Tags | `alicloud-resourcemanager-ops` | Resource group and tag management |