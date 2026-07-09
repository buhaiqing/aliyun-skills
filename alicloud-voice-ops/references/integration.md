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
   # Set proxy for China CDN mirror (faster download)
   export GOPROXY="https://goproxy.cn,direct"
   
   # Core dependencies
   go get github.com/alibabacloud-go/darabonba-openapi/v2/client
   go get github.com/alibabacloud-go/tea
   go get github.com/alibabacloud-go/tea-utils/v2/service
   
   # Voice Service SDK
   go get github.com/alibabacloud-go/dyvmsapi-20170525/v3/client
   ```

3. **Generate script** (Agent dynamically creates operation-specific .go file)

4. **Execute:**
   ```bash
   go run ./main.go
   ```

### SDK Package

```bash
go get github.com/alibabacloud-go/dyvmsapi-20170525/v3/client
```

### SDK Script Example

```go
package main

import (
	"fmt"
	"os"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/dyvmsapi-20170525/v3/client"
	"github.com/alibabacloud-go/tea/tea"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
		Endpoint:        tea.String("dyvmsapi.aliyuncs.com"),
	}

	client, err := dyvmsapi.NewClient(config)
	if err != nil {
		panic(err)
	}

	// SingleCallByVoice example (pre-recorded audio)
	request := &dyvmsapi.SingleCallByVoiceRequest{
		CalledNumber: tea.String("13800138000"),
		VoiceCode:    tea.String("123456"),
		ShowNumber:   tea.String("4008123123"),
	}

	response, err := client.SingleCallByVoice(request)
	if err != nil {
		panic(err)
	}

	fmt.Println(tea.ToString(response.Body))
}
```

## Environment Variable Loading (`.env` support)

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

## Credential Management

- Credentials MUST use `{{env.*}}` placeholders — NEVER ask user for secrets
- AccessKey rotation: recommend 90-day cycle
- Prefer MFA-enabled RAM users for interactive operations
