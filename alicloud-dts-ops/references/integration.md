# Integration — DTS (Data Transmission Service)

## Environment Setup

**Primary path:** `aliyun dts` CLI (static Go binary, no runtime dependencies)

**Recommended:** Install DTS CLI plugin
```bash
aliyun plugin install --names aliyun-cli-dts
```

**Fallback path:** JIT Go SDK (dynamic script generation + `go run`)

### Go Runtime Bootstrap

```bash
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

### JIT Go SDK Workflow

```bash
# Initialize workspace
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script

# Set China CDN proxy (faster download)
export GOPROXY="https://goproxy.cn,direct"

# Core dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea

# DTS SDK
go get github.com/alibabacloud-go/dts-20200101/v1/client
```

### Go SDK Script Template

```go
// main.go — DTS SDK template
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    dts "github.com/alibabacloud-go/dts-20200101/v1/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("dts.aliyuncs.com"),
    }

    client, err := dts.NewClient(config)
    if err != nil {
        panic(err)
    }

    // Describe DTS Jobs example
    request := &dts.DescribeDtsJobsRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }

    response, err := client.DescribeDtsJobs(request)
    if err != nil {
        panic(err)
    }

    fmt.Println(tea.ToString(response.Body))
}
```

## SDK Package Naming

| Product | Go SDK Package |
|---------|---------------|
| DTS | `github.com/alibabacloud-go/dts-20200101/v1/client` |

> Find package at: https://github.com/alibabacloud-go/dts-20200101

## Environment Variables

```ini
# Required
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou

# Operation-specific (set as needed)
SOURCE_ENDPOINT_TYPE=RDS
SOURCE_INSTANCE_ID=rm-xxxx
SOURCE_REGION=cn-hangzhou
SOURCE_ENGINE=mysql
SOURCE_USERNAME=dts_user
SOURCE_PASSWORD=your_password
TARGET_ENDPOINT_TYPE=RDS
TARGET_INSTANCE_ID=rm-yyyy
TARGET_REGION=cn-hangzhou
TARGET_ENGINE=mysql
TARGET_USERNAME=dts_user
TARGET_PASSWORD=your_password
```

> **Security:** All credential values (AK, SK, database passwords) MUST use environment variables. Never hardcode secrets in scripts. Never echo or log credential values.

## Cross-Skill Delegation Matrix

| Operation | Delegates to | Notes |
|-----------|-------------|-------|
| Source DB status check | `alicloud-rds-ops`, `alicloud-polar-mysql-ops`, `alicloud-redis-ops`, `alicloud-mongodb-ops` | Verify source instance is Running before configuring DTS |
| Target DB status check | `alicloud-rds-ops`, `alicloud-polar-mysql-ops`, `alicloud-redis-ops`, `alicloud-mongodb-ops` | Verify target instance is Running |
| VPC/Network verification | `alicloud-vpc-ops` | Ensure VPC/routing allows DTS connectivity |
| Security group whitelisting | `alicloud-ecs-ops` (for ECS-based DBs) | Add DTS CIDR to ECS security group |
| CMS alarm setup | `alicloud-cms-ops` | Create DTS monitoring dashboard and alerts |
| RAM permission setup | `alicloud-ram-ops` | Create DTS-specific RAM user/policy |

## Credential Security

| Rule | Description |
|------|-------------|
| AK/SK | Use `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` / `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` — never collect from user |
| DB passwords | Passwords in ConfigureDtsJob MUST be `<masked>` in logs; use JIT Go SDK with env vars for production |
| Log output | Never echo `SourceEndpointPassword` or `DestinationEndpointPassword` values |
| PS output | On Linux, `ps aux` can expose command-line passwords — prefer JIT Go SDK for sensitive operations |

### Safe Password Handling (JIT Go SDK)

```go
// SAFE: password from environment variable
SourceEndpointPassword: tea.String(os.Getenv("SOURCE_PASSWORD")),

// UNSAFE: password on command line
// aliyun dts ConfigureDtsJob --SourceEndpointPassword "mypassword"
```