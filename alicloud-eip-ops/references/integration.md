# EIP Integration

> **Purpose:** SDK setup, JIT Go SDK workflow, and cross-skill delegation matrix.

## Go SDK Package

```
github.com/alibabacloud-go/vpc-20160428/v3/client
```

## JIT Go SDK Workflow

```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init eip-sdk-script
export GOPROXY="https://goproxy.cn,direct"
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/vpc-20160428/v3/client
```

```go
package main

import (
    "fmt"
    "os"
    
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    vpc "github.com/alibabacloud-go/vpc-20160428/v3/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    
    client, err := vpc.NewClient(config)
    if err != nil {
        fmt.Fprintf(os.Stderr, "NewClient error: %v\n", err)
        os.Exit(1)
    }
    
    request := &vpc.DescribeEipAddressesRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    
    resp, err := client.DescribeEipAddresses(request)
    if err != nil {
        fmt.Fprintf(os.Stderr, "DescribeEipAddresses error: %v\n", err)
        os.Exit(1)
    }
    
    fmt.Println(tea.Prettify(resp))
}
```

```bash
go run ./main.go
```

## Cross-Skill Delegation Matrix

| Alarm/Error Type | Primary Skill | Delegated Skill | Delegation Trigger |
|-----------------|--------------|-----------------|--------------------|
| EIP 绑定 ECS 失败 | `alicloud-eip-ops` | `alicloud-ecs-ops` | ECS 实例状态异常或不在同 Region |
| EIP 绑定 NAT 失败 | `alicloud-eip-ops` | `alicloud-nat-ops` | NAT Gateway 状态异常 |
| EIP 绑定 SLB 失败 | `alicloud-eip-ops` | `alicloud-slb-ops` | SLB 实例状态异常 |
| 带宽包管理 | `alicloud-eip-ops` | — | 共享带宽操作无跨 Skill 委托 |
| EIP 流量异常 | `alicloud-eip-ops` | `alicloud-ecs-ops` / `alicloud-nat-ops` | 排查绑定目标资源健康状态 |
| Blackhole DDoS | `alicloud-eip-ops` | `alicloud-cms-ops` | 联动云监控告警和 DDoS 高防 |

## Delegation Workflow

```
[EIP 告警触发]
    │
    ├── 1. 识别告警类型（带宽/连接/黑hole/解绑失败）
    ├── 2. 检查当前 EIP 状态和绑定目标
    ├── 3. 若绑定目标异常 → 调用目标 Skill（ECS/NAT/SLB）
    ├── 4. 汇总结果生成诊断报告
    └── 5. 提供可执行的修复建议
```

## Environment Variable Loading

```ini
ALIBABA_CLOUD_ACCESS_KEY_ID=<your_ak>
ALIBABA_CLOUD_ACCESS_KEY_SECRET=<your_secret>
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

**Security:** Credential masking is MANDATORY. Never echo `ALIBABA_CLOUD_ACCESS_KEY_SECRET`.
