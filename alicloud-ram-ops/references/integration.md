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

> **Go version strategy:**
> - **JIT download:** Go 1.24+ (latest stable)
> - **Script compatibility:** Go 1.21+ (minimum)

### JIT Go SDK Workflow

1. **Initialize workspace:**
   ```bash
   mkdir -p /tmp/aliyun-sdk-workspace
   cd /tmp/aliyun-sdk-workspace
   go mod init sdk-script
   ```

2. **Get dependencies:**
   ```bash
   export GOPROXY="https://goproxy.cn,direct"

   # Core dependencies
   go get github.com/alibabacloud-go/darabonba-openapi/v2/client
   go get github.com/alibabacloud-go/tea
   go get github.com/alibabacloud-go/tea-utils/v2/service

   # RAM SDK
   go get github.com/alibabacloud-go/ram-20150501/v2/client

   # STS SDK
   go get github.com/alibabacloud-go/sts-20150401/v2/client
   ```

3. **Generate script** (Agent dynamically creates operation-specific .go file)

4. **Execute:**
   ```bash
   go run ./main.go
   ```

### SDK Package Naming

| Product | Go SDK Package |
|---------|---------------|
| RAM | `github.com/alibabacloud-go/ram-20150501/v2/client` |
| STS | `github.com/alibabacloud-go/sts-20150401/v2/client` |

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
- **RAM note:** RAM is global; `cn-hangzhou` is the typical default even if
  resources are in other regions.

### Go `.env` Loading (optional)

```go
package main

import (
    "os"
    "github.com/joho/godotenv"
)

func init() {
    godotenv.Load(".env")
}

func main() {
    ak := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
    sk := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    region := os.Getenv("ALIBABA_CLOUD_REGION_ID")
}
```

## Credential Verification

```bash
# Primary: aliyun CLI validation
aliyun ram ListUsers --MaxItems 5
aliyun sts GetCallerIdentity
```

If `aliyun` validation fails, attempt retries per retry logic. After 3 failures,
proceed to JIT Go SDK and verify:

```bash
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
    fmt.Println("Credentials OK (JIT Go SDK mode)")
}
EOF
go run /tmp/aliyun-sdk-workspace/verify.go
```

> **SECURITY WARNING:** Verification code ONLY checks for existence. NEVER log
> the actual secret value.

## Cross-Product Delegation

When a RAM operation is part of a multi-product workflow:

1. **RAM setup first:** Create users, roles, policies
2. **Attach resource policies:** Use the target product's skill to attach
   resource-level policies (e.g., OSS bucket policy, ECS resource group policy)
3. **Verify end-to-end:** Use the target product's skill to verify the RAM
   identity can access the resource

Example: ECS instance access via RAM role
1. Create RAM role with ECS service principal (this skill)
2. Attach `AliyunECSFullAccess` to role (this skill)
3. Create ECS instance and attach instance role (`alicloud-ecs-ops` skill)
4. Verify instance metadata can retrieve STS credentials (`alicloud-ecs-ops` skill)
