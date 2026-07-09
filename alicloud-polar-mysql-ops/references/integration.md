# Integration — PolarDB MySQL

> Version: 1.0.0 | Last Updated: 2026-05-16

## Environment Setup

**Primary path:** `aliyun polardb` CLI (static Go binary)

**Fallback path:** JIT Go SDK via `polardb-20220530/v3/client`

## Go SDK Package

```
github.com/alibabacloud-go/polardb-20220530/v3/client
```

## JIT Go SDK Workflow

```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script
export GOPROXY="https://goproxy.cn,direct"
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/tea-utils/v2/service
go get github.com/alibabacloud-go/polardb-20220530/v3/client
go run ./main.go
```

## Go SDK Script Template

```go
package main

import (
	"fmt"
	"os"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	polardb "github.com/alibabacloud-go/polardb-20220530/v3/client"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
	}

	client, err := polardb.NewClient(config)
	if err != nil {
		panic(err)
	}

	req := &polardb.DescribeDBClustersRequest{
		DBType:   tea.String("MySQL"),
		RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	}

	resp, err := client.DescribeDBClusters(req)
	if err != nil {
		panic(err)
	}

	fmt.Println(tea.ToString(resp.Body))
}
```

## Self-Healing Framework

See [alicloud-skill-generator/references/enhanced-self-healing-framework.md](../../alicloud-skill-generator/references/enhanced-self-healing-framework.md) for complete self-healing installation procedures.

## Credential Configuration

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=***
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=***
export ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

> **SECURITY:** Never echo secret values. Verify existence only: `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"`
