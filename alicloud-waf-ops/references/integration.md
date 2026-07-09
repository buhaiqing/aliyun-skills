# Integration — Alibaba Cloud WAF

## Environment Setup

**Primary path:** `aliyun waf-openapi` CLI (requires plugin installation)

**Fallback path:** JIT Go SDK (dynamic script generation + `go run`)

## CLI Plugin Installation

WAF 3.0 requires a CLI plugin. Install before first use:

```bash
# Install WAF plugin
aliyun plugin install --names aliyun-cli-waf-openapi

# Verify installation
aliyun plugin list | grep waf

# Expected output:
# waf-openapi   Web Application Firewall
```

## Go Runtime Bootstrap

If Agent Runtime lacks Go, JIT download from official source:

```bash
# Check Go runtime
if ! command -v go &> /dev/null; then
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    [ "$ARCH" = "x86_64" ] && ARCH="amd64"
    [ "$ARCH" = "aarch64" ] && ARCH="arm64"
    
    mkdir -p /tmp/go-runtime
    curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
    export PATH="/tmp/go-runtime/go/bin:$PATH"
    export GOPATH="/tmp/go-workspace"
    export GOCACHE="/tmp/go-cache"
fi

go version
```

> **Go version strategy:**
> - **JIT download:** Go 1.24+ (latest stable)
> - **Script compatibility:** Go 1.21+ (minimum)

## JIT Go SDK Workflow

### 1. Initialize workspace

```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script
```

### 2. Get dependencies

```bash
# Set proxy for China CDN mirror (faster download)
export GOPROXY="https://goproxy.cn,direct"

# Core dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/tea-utils/v2/service

# WAF SDK
go get github.com/alibabacloud-go/waf-openapi-20211001/v2/client
```

### 3. Generate script

Agent dynamically creates operation-specific .go file.

### 4. Execute

```bash
go run ./main.go
```

## SDK Package Reference

| Product | Go SDK Package |
|---------|---------------|
| WAF 3.0 | `github.com/alibabacloud-go/waf-openapi-20211001/v2/client` |

> Find package names at: https://github.com/alibabacloud-go

## Environment Variable Loading

Credentials can be sourced from multiple locations:

```
Shell env (highest) > `.env` file > aliyun config.json > defaults (lowest)
```

### `.env` File Format

```ini
# Alibaba Cloud credentials
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

- **Security**: `.env` MUST be in `.gitignore` — never commit credentials

## Go SDK Script Template

### DescribeInstanceInfo Example

```go
package main

import (
    "fmt"
    "os"
    
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    waf "github.com/alibabacloud-go/waf-openapi-20211001/v2/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("waf-openapi.cn-hangzhou.aliyuncs.com"),
    }
    
    client, err := waf.NewClient(config)
    if err != nil {
        panic(err)
    }
    
    request := &waf.DescribeInstanceInfoRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    
    response, err := client.DescribeInstanceInfo(request)
    if err != nil {
        panic(err)
    }
    
    fmt.Println(tea.ToString(response.Body))
}
```

### CreateDomain Example

```go
package main

import (
    "fmt"
    "os"
    
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    waf "github.com/alibabacloud-go/waf-openapi-20211001/v2/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("waf-openapi.cn-hangzhou.aliyuncs.com"),
    }
    
    client, err := waf.NewClient(config)
    if err != nil {
        panic(err)
    }
    
    request := &waf.CreateDomainRequest{
        RegionId:      tea.String("cn-hangzhou"),
        InstanceId:    tea.String("waf_xxx"),
        Domain:        tea.String("example.com"),
        OriginAddress: tea.String("1.2.3.4"),
    }
    
    response, err := client.CreateDomain(request)
    if err != nil {
        panic(err)
    }
    
    fmt.Println(tea.ToString(response.Body))
}
```

> Use `os.Getenv("KEY")` for all credentials. Never hardcode secrets in scripts.

## WAF Endpoint Reference

| Region | Endpoint |
|--------|----------|
| cn-hangzhou | waf-openapi.cn-hangzhou.aliyuncs.com |
| cn-shanghai | waf-openapi.cn-shanghai.aliyuncs.com |
| cn-beijing | waf-openapi.cn-beijing.aliyuncs.com |
| cn-shenzhen | waf-openapi.cn-shenzhen.aliyuncs.com |
| ap-southeast-1 | waf-openapi.ap-southeast-1.aliyuncs.com |

## Cross-Skill Integration

| Skill | Integration Point | Use Case |
|-------|-------------------|----------|
| `alicloud-ecs-ops` | Origin server health | Verify origin reachable |
| `alicloud-slb-ops` | Load balancer config | WAF + SLB layered defense |
| `alicloud-ram-ops` | WAF IAM permissions | Scope `waf:*` actions |
| `alicloud-actiontrail-ops` | API audit | Compliance, forensics |
| `alicloud-ddos-ops` | DDoS mitigation | Layer 3/4 protection |
