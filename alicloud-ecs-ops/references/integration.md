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

### JIT SDK Script Template

```bash
# Initialize workspace
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script

# Get dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/tea-utils/v2/service
go get github.com/alibabacloud-go/ecs-20140526/v4/client
```

### SDK Script Example

```go
package main

import (
	"fmt"
	"os"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	ecs "github.com/alibabacloud-go/ecs-20140526/v4/client"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
		RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	}

	client, err := ecs.NewClient(config)
	if err != nil {
		panic(err)
	}

	req := &ecs.DescribeInstancesRequest{
		RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	}

	resp, err := client.DescribeInstances(req)
	if err != nil {
		panic(err)
	}

	fmt.Println(tea.ToString(resp.Body))
}
```

Execute:
```bash
go run ./main.go
```

## Cross-Product Dependencies

| This Skill Needs | From Skill | Verification Command |
|------------------|------------|---------------------|
| VPC/VSwitch | `alicloud-vpc-ops` | `aliyun vpc DescribeVpcs --RegionId ...` |
| RAM permissions | `alicloud-ram-ops` | `aliyun ram GetPolicy ...` |
| Security group rules | `alicloud-ecs-ops` (this skill) | `aliyun ecs DescribeSecurityGroups ...` |
| Monitoring/Alerts | `alicloud-cms-ops` | `aliyun cms DescribeMetricList ...` |
| Auto Scaling | `alicloud-ess-ops` | `aliyun ess DescribeScalingGroups ...` |

## Credential Sources (Priority Order)

| Priority | Source | Description |
|----------|--------|-------------|
| 1 (highest) | CLI flags | `--access-key-id`, `--access-key-secret`, `--region` |
| 2 | Shell environment | `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABA_CLOUD_REGION_ID` |
| 3 | `~/.aliyun/config.json` | Persistent profile config (JSON format) |
| 4 (lowest) | Default profile | `default` profile from config file |
