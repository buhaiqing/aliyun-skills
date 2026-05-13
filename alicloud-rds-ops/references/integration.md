# Integration

## Environment Setup

**Primary path:** `aliyun` CLI (static Go binary, no runtime dependencies)

**Fallback path:** JIT Go SDK (dynamic script generation + `go run`)

### Go Runtime Bootstrap

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
    export GOMODCACHE="/tmp/go-modcache"
    export GOPROXY="https://goproxy.cn,direct"
fi

go version
```

### SDK Dependencies

```bash
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script

# Core dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/tea-utils/v2/service

# RDS-specific SDK
go get github.com/alibabacloud-go/rds-20140815/v2/client
```

### Credential Verification

```bash
# Primary: aliyun CLI validation
aliyun rds DescribeRegions

# Fallback: Go SDK credential check
cat > /tmp/aliyun-sdk-workspace/verify.go << 'EOF'
package main

import (
    "fmt"
    "os"
)

func main() {
    ak := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
    sk := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    if ak == "" || sk == "" {
        fmt.Println("Missing ALIBABA_CLOUD_ACCESS_KEY_ID or ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        os.Exit(1)
    }
    fmt.Println("Credentials OK")
}
EOF
go run /tmp/aliyun-sdk-workspace/verify.go
```

> **SECURITY WARNING:** The verification code above **ONLY checks for existence**
> of credentials. **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
> in console output.

## Cross-Product Integration

| Scenario | Primary Skill | Delegated Skill | Integration Point |
|----------|--------------|-----------------|-------------------|
| Create RDS in VPC | `alicloud-rds-ops` | `alicloud-vpc-ops` | Verify VPC/VSwitch before CreateDBInstance |
| RDS with ECS access | `alicloud-rds-ops` | `alicloud-ecs-ops` | Add ECS security group IPs to RDS whitelist |
| RDS backup to OSS | `alicloud-rds-ops` | `alicloud-oss-ops` | Configure cross-region backup storage |
| RDS monitoring | `alicloud-rds-ops` | `alicloud-cms-ops` | Set up CloudMonitor alerts |
| RDS with RAM | `alicloud-rds-ops` | `alicloud-ram-ops` | Configure service-linked roles |

## API Profile

- **Service Code**: `rds`
- **API Version**: `2014-08-15`
- **Endpoint Pattern**: `rds.aliyuncs.com` (global), `rds.{{region}}.aliyuncs.com` (regional)
- **Protocol**: HTTPS (RPC-style)
- **SDK Package**: `github.com/alibabacloud-go/rds-20140815/v2/client`
