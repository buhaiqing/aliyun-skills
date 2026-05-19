# Integration — KMS

## Environment Setup

**Primary path:** `aliyun` CLI (static Go binary, no runtime dependencies)

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
    export GOMODCACHE="/tmp/go-modcache"
    export GOPROXY="https://goproxy.cn,direct"
fi
go version
```

## JIT Go SDK Workflow

1. **Initialize workspace:**
   ```bash
   mkdir -p /tmp/aliyun-sdk-workspace
   cd /tmp/aliyun-sdk-workspace
   go mod init kms-jit
   export GOPROXY="https://goproxy.cn,direct"
   ```

2. **Get dependencies:**
   ```bash
   go get github.com/alibabacloud-go/darabonba-openapi/v2/client
   go get github.com/alibabacloud-go/kms-20160120/v3/client
   go get github.com/alibabacloud-go/tea
   go get github.com/alibabacloud-go/tea-utils/v2/service
   ```

3. **Generate script** (Agent dynamically creates operation-specific `.go` file)

4. **Execute:**
   ```bash
   go run ./main.go
   ```

## SDK Package Reference

| Product | Go SDK Package |
|---------|---------------|
| **KMS** | `github.com/alibabacloud-go/kms-20160120/v3/client` |

All SDK imports should use the `v3` major version. Latest release: v3.4.0.

## Cross-Skill Delegation Matrix

| Source Scenario | Target Skill | Delegation Data |
|-----------------|-------------|-----------------|
| Create KMS key for ECS disk encryption | `alicloud-ecs-ops` | `{{output.key_id}}`, region, key spec |
| Create KMS key for RDS TDE | `alicloud-rds-ops` | `{{output.key_id}}`, region |
| Create KMS key for OSS SSE-KMS | `alicloud-oss-ops` (when present) | `{{output.key_id}}`, region |
| RAM permission missing for KMS op | `alicloud-ram-ops` | Required action (e.g., `kms:CreateKey`), resource ARN |
| KMS instance VPC networking issues | `alicloud-vpc-ops` (when present) | VPC ID, VSwitch ID, region |

## Environment Variable Loading (`.env` support)

Credentials can be sourced from multiple locations:

```
Shell env (highest) > `.env` file > aliyun config.json > defaults (lowest)
```

### `.env` File Format

```ini
# Alibaba Cloud KMS credentials
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

- **Security**: `.env` MUST be in `.gitignore` — never commit credentials
- **Multiple clouds**: Use platform-specific prefixes

## Go SDK Script Template for KMS

```go
// main.go — KMS JIT SDK script template
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    kmssdk "github.com/alibabacloud-go/kms-20160120/v3/client"
    "github.com/alibabacloud-go/tea-utils/v2/service"
    "github.com/alibabacloud-go/tea/tea"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.Sprintf("kms.%s.aliyuncs.com", os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }

    client, err := kmssdk.NewClient(config)
    if err != nil {
        fmt.Printf("Error: failed to create KMS client\n")
        os.Exit(1)
    }

    runtime := &service.RuntimeOptions{
        ConnectTimeout: tea.Int(5000),
        ReadTimeout:    tea.Int(5000),
    }

    // === OPERATION-SPECIFIC CODE GOES HERE ===
    // Example: DescribeKey
    resp, err := client.DescribeKeyWithOptions(&kmssdk.DescribeKeyRequest{
        KeyId: tea.String(os.Getenv("KEY_ID")),
    }, runtime)
    if err != nil {
        fmt.Printf("Error: DescribeKey failed — %v\n", err)
        os.Exit(1)
    }

    fmt.Println(tea.ToString(resp.Body.Key.KeyId))
}
```

> Use `os.Getenv("KEY")` for all credentials. Never hardcode secrets in scripts.

## Credential Security

See main SKILL.md for credential masking rules. Key points for KMS:
- KMS handles sensitive cryptographic operations — credential leaks are especially dangerous
- JIT Go SDK scripts MUST NOT print Config structs to stdout or logs
- Debug mode should warn about potential credential exposure
