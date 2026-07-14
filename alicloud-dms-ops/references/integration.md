# Integration

## Environment Setup

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
fi
```

### DMS Plugin Install

```bash
aliyun plugin install --names aliyun-cli-dms
```

## JIT Go SDK Workflow

1. **Initialize workspace:**

   ```bash
   mkdir -p /tmp/aliyun-sdk-workspace
   cd /tmp/aliyun-sdk-workspace
   go mod init sdk-script
   ```

2. **Get dependencies:**

   ```bash
   export GOPROXY="https://goproxy.cn,direct"
   go get github.com/alibabacloud-go/darabonba-openapi/v2/client
   go get github.com/alibabacloud-go/tea
   go get github.com/alibabacloud-go/dms-enterprise-2024-04-14/v1/client
   ```

3. **Generate operation-specific .go file**

4. **Execute:**

   ```bash
   go run ./main.go
   ```

## SDK Script Template

```go
// main.go
package main

import (
    "fmt"
    "os"
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea"
    dms "github.com/alibabacloud-go/dms-enterprise-2024-04-14/v1/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String(os.Getenv("ALIBABA_CLOUD_DMS_ENDPOINT")),
    }
    client, err := dms.NewClient(config)
    if err != nil {
        panic(err)
    }
    // Operation-specific code here
    _ = client
}
```

## Environment Variables

| Variable | Default | Notes |
| ---------- | --------- | ------- |
| ALIBABA_CLOUD_DMS_ENDPOINT | dms-enterprise.aliyuncs.com | API endpoint |
| ALIBABA_CLOUD_ACCESS_KEY_ID | — | Required |
| ALIBABA_CLOUD_ACCESS_KEY_SECRET | — | Required |
| ALIBABA_CLOUD_REGION_ID | cn-hangzhou | Region |

## Credential Masking (MANDATORY)

- NEVER echo AK/SK values: `echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET` is **banned**
- Verify existence only: `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo
  "OK"`
- Go SDK: `os.Getenv()` is safe; `fmt.Printf("%+v", config)` is **banned**
