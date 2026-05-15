# VPC Integration

> **Purpose:** SDK setup, JIT Go SDK workflow, and environment integration.

## Go SDK Package

```
github.com/alibabacloud-go/vpc-20160428/v3/client
```

## JIT Go SDK Workflow

When CLI doesn't support a specific VPC operation, use the JIT Go SDK approach:

### 1. Initialize workspace

```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init vpc-sdk-script
export GOPROXY="https://goproxy.cn,direct"
```

### 2. Get dependencies

```bash
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/vpc-20160428/v3/client
```

### 3. Create operation-specific script

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
    
    // Operation-specific call
    request := &vpc.DescribeVpcsRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    
    resp, err := client.DescribeVpcs(request)
    if err != nil {
        fmt.Fprintf(os.Stderr, "DescribeVpcs error: %v\n", err)
        os.Exit(1)
    }
    
    fmt.Println(tea.Prettify(resp))
}
```

### 4. Execute

```bash
go run ./main.go
```

## Credential Handling

```bash
# Shell environment (highest priority)
export ALIBABA_CLOUD_ACCESS_KEY_ID="..."
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="..."
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"

# .env file (loaded by shell if present)
# ALIBABA_CLOUD_ACCESS_KEY_ID=...
# ALIBABA_CLOUD_ACCESS_KEY_SECRET=...
# ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

**Security:** Never log, print, or echo credential values. Use `test -n "$VAR"` for existence checks.

## Cross-Skill Delegation Matrix

| Alarm/Error Type | Primary Skill | Delegated Skill | Delegation Trigger |
|-----------------|--------------|-----------------|--------------------|
| VPC 创建失败（配额） | `alicloud-vpc-ops` | — | 用户手动申请配额 |
| VPC 关联 ECS 资源失败 | `alicloud-vpc-ops` | `alicloud-ecs-ops` | ECS 不在目标 VPC 中 |
| NAT Gateway 带宽饱和 | `alicloud-vpc-ops` | `alicloud-eip-ops` | 需要添加更多 EIP 扩容 SNAT |
| EIP 绑定失败 | `alicloud-vpc-ops` | `alicloud-eip-ops` | EIP 不存在或状态异常 |
| VPN 连接断开 | `alicloud-vpc-ops` | `alicloud-cms-ops` (告警) | 需要排查网络连通性 |
| FlowLog 数据异常 | `alicloud-vpc-ops` | `alicloud-slb-ops` / `alicloud-ecs-ops` | 根据 FlowLog 源/目标定位资源 |
| 路由冲突 | `alicloud-vpc-ops` | — | 检查路由表配置，无跨 Skill 委托 |
| 安全组/EIP 连通性问题 | `alicloud-vpc-ops` | `alicloud-ecs-ops` + `alicloud-eip-ops` | 联合排查网络链路 |

## Delegation Workflow

```
[VPC 告警触发]
    │
    ├── 1. 识别告警类型（VPC/NAT/EIP/FlowLog）
    ├── 2. 查矩阵确定主诊断 Skill
    ├── 3. 调用 VPC Skill 检查资源状态
    ├── 4. 若涉及 ECS/EIP/SLB → 调用对应 Skill
    ├── 5. 汇总所有输出生成统一报告
    └── 6. 提供可执行的修复建议
```

## Environment Variable Loading

```ini
# Alibaba Cloud credentials (for all VPC-related operations)
ALIBABA_CLOUD_ACCESS_KEY_ID=<your_ak>
ALIBABA_CLOUD_ACCESS_KEY_SECRET=<your_secret>
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

**Note:** These credentials are used by both the `aliyun` CLI and the JIT Go SDK for VPC API calls.
