# NAT Integration

> **Purpose:** SDK setup, JIT Go SDK workflow, and cross-skill delegation matrix.

## Go SDK Package

```
github.com/alibabacloud-go/vpc-20160428/v3/client
```

## JIT Go SDK Workflow

```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init nat-sdk-script
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
    
    request := &vpc.DescribeNatGatewaysRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    
    resp, err := client.DescribeNatGateways(request)
    if err != nil {
        fmt.Fprintf(os.Stderr, "DescribeNatGateways error: %v\n", err)
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
| NAT 网关创建失败 | `alicloud-nat-ops` | `alicloud-vpc-ops` | VPC 不存在或 vSwitch 异常 |
| SNAT/DNAT 配置失败 | `alicloud-nat-ops` | `alicloud-eip-ops` | EIP 不存在、未绑定、或状态异常 |
| NAT 带宽饱和 | `alicloud-nat-ops` | `alicloud-eip-ops` | 需要添加更多 EIP 扩容 SNAT |
| DNAT 端口映射不通 | `alicloud-nat-ops` | `alicloud-ecs-ops` | 目标 ECS 服务异常或安全组阻止 |
| NAT 删除失败 | `alicloud-nat-ops` | `alicloud-vpc-ops` | SNAT/DNAT/EIP 依赖未清理 |
| NAT 流量异常突增 | `alicloud-nat-ops` | `alicloud-ecs-ops` | 排查内网实例是否发起异常请求 |

## Delegation Workflow

```
[NAT 告警触发]
    │
    ├── 1. 识别告警类型（创建/配置/带宽/连通性/删除）
    ├── 2. 检查 NAT 网关状态和配置
    ├── 3. 若 SNAT/DNAT 异常 → 检查 EIP 状态 (`alicloud-eip-ops`)
    ├── 4. 若 DNAT 不通 → 检查目标 ECS (`alicloud-ecs-ops`)
    ├── 5. 汇总结果生成诊断报告
    └── 6. 提供可执行的修复建议
```

## Environment Variable Loading

```ini
ALIBABA_CLOUD_ACCESS_KEY_ID=<your_ak>
ALIBABA_CLOUD_ACCESS_KEY_SECRET=<your_secret>
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

**Security:** Credential masking is MANDATORY. Never echo `ALIBABA_CLOUD_ACCESS_KEY_SECRET`.
