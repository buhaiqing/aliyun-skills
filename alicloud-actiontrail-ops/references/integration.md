# Integration — Alibaba Cloud ActionTrail (操作审计)

## Go SDK Setup (JIT Fallback)

### SDK Package

```bash
go get github.com/alibabacloud-go/actiontrail-20200706/v4/client
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
```

### Basic Client Initialization

```go
package main

import (
    "fmt"
    "os"
    "encoding/json"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    actiontrail "github.com/alibabacloud-go/actiontrail-20200706/v4/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("actiontrail.aliyuncs.com"),
    }

    client, err := actiontrail.NewClient(config)
    if err != nil {
        panic(err)
    }

    // Example: DescribeTrails
    response, err := client.DescribeTrails(&actiontrail.DescribeTrailsRequest{})
    if err != nil {
        panic(err)
    }

    body, _ := json.Marshal(response.Body)
    fmt.Println(string(body))
}
```

### Common SDK Usage Patterns

#### Create Trail

```go
request := &actiontrail.CreateTrailRequest{
    Name:          tea.String("my-trail"),
    OssBucketName: tea.String("my-bucket"),
    EventRW:       tea.String("All"),
}
response, err := client.CreateTrail(request)
```

#### Lookup Events

```go
request := &actiontrail.LookupEventsRequest{
    StartTime:  tea.String("2026-05-01T00:00:00Z"),
    EndTime:    tea.String("2026-05-15T23:59:59Z"),
    MaxResults: tea.Int32(50),
}
response, err := client.LookupEvents(request)
```

#### Get AccessKey Last Used Info

```go
request := &actiontrail.GetAccessKeyLastUsedInfoRequest{
    AccessKeyId: tea.String("LTAI5t****"),
}
response, err := client.GetAccessKeyLastUsedInfo(request)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | Alibaba Cloud AccessKey ID |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | Alibaba Cloud AccessKey Secret |
| `ALIBABA_CLOUD_REGION_ID` | Yes | Default region for API calls |
| `ALIBABA_CLOUD_SECURITY_TOKEN` | No | STS token (when using RAM role) |

## Endpoints

| Type | Endpoint |
|------|----------|
| Global | `actiontrail.aliyuncs.com` |
| Regional | `actiontrail.[region_id].aliyuncs.com` |
| VPC | `actiontrail-vpc.[region_id].aliyuncs.com` |

## JIT Go SDK Bootstrap

When the `aliyun` CLI is unavailable, use the JIT Go SDK fallback:

```bash
# Step 1: Check/install Go runtime
if ! command -v go &> /dev/null; then
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    [ "$ARCH" = "x86_64" ] && ARCH="amd64"
    [ "$ARCH" = "aarch64" ] && ARCH="arm64"
    curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
    export PATH="/tmp/go-runtime/go/bin:$PATH"
fi

# Step 2: Create workspace
mkdir -p /tmp/actiontrail-sdk && cd /tmp/actiontrail-sdk
go mod init actiontrail-sdk

# Step 3: Install SDK
go get github.com/alibabacloud-go/actiontrail-20200706/v4/client
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea

# Step 4: Run SDK script
go run main.go
```

## Multi-GOPROXY Strategy

```bash
GOPROXY_MIRRORS=(
    "https://goproxy.cn,direct"
    "https://goproxy.io,direct"
    "https://proxy.golang.org,direct"
    "direct"
)

for proxy in "${GOPROXY_MIRRORS[@]}"; do
    GOPROXY="$proxy" go get github.com/alibabacloud-go/actiontrail-20200706/v4/client && break
done
```