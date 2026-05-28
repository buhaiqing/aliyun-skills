<!-- markdownlint-disable MD003 MD013 MD022 MD024 MD034 MD041 MD060 -->

# Integration — Alibaba Cloud Security Center (SAS)

## Environment Setup

**Primary path:** `aliyun` CLI (`aliyun sas ...`)

**Fallback path:** JIT Go SDK (`github.com/alibabacloud-go/sas-20181203/v4/client`)

### Go Runtime Bootstrap

See [alicloud-skill-generator/references/execution-environment.md](../../alicloud-skill-generator/references/execution-environment.md) for JIT Go 1.24+ download.

```bash
if ! command -v go &> /dev/null; then
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m); [ "$ARCH" = "x86_64" ] && ARCH="amd64"
    mkdir -p /tmp/go-runtime
    curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
    export PATH="/tmp/go-runtime/go/bin:$PATH"
    export GOPROXY="https://goproxy.cn,direct"
fi
```

### JIT Workspace

```bash
mkdir -p /tmp/aliyun-sdk-workspace && cd /tmp/aliyun-sdk-workspace
go mod init sas-script
export GOPROXY="https://goproxy.cn,direct"
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/sas-20181203/v4/client
go get github.com/alibabacloud-go/tea-utils/v2/service
```

### Client Initialization

```go
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    sas "github.com/alibabacloud-go/sas-20181203/v4/client"
    "github.com/alibabacloud-go/tea/tea"
)

func main() {
    region := os.Getenv("ALIBABA_CLOUD_REGION_ID")
    if region == "" {
        region = "cn-shanghai"
    }
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        RegionId:        tea.String(region),
        Endpoint:        tea.String("tds." + region + ".aliyuncs.com"),
    }
    client, err := sas.NewClient(config)
    if err != nil {
        panic(err)
    }
    resp, err := client.DescribeAllRegionsStatistics(&sas.DescribeAllRegionsStatisticsRequest{})
    if err != nil {
        panic(err)
    }
    fmt.Println(tea.ToString(resp.Body))
}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | AccessKey ID |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | AccessKey Secret (never log) |
| `ALIBABA_CLOUD_REGION_ID` | Yes | Region for `tds.{region}.aliyuncs.com` |
| `ALIBABA_CLOUD_SECURITY_TOKEN` | No | STS token when using assume-role |

## Endpoints

| Type | Endpoint |
|------|----------|
| China (common) | `tds.cn-shanghai.aliyuncs.com` |
| Regional | `tds.{regionId}.aliyuncs.com` |
| VPC | `tds.vpc-proxy.aliyuncs.com` (region-specific) |
| Intl VPC | `tds-intl.vpc-proxy.aliyuncs.com` |

Reference: <https://www.alibabacloud.com/help/en/security-center/developer-reference/api-sas-2018-12-03-endpoint>

## Cross-Skill Delegation Matrix

| Need | Delegate To | When |
|------|-------------|------|
| API audit / who changed resource | `alicloud-actiontrail-ops` | Forensics, compliance |
| RAM policy / disable AK | `alicloud-ram-ops` | Permission fix, AK leak response |
| ECS network / instance state | `alicloud-ecs-ops` | Agent install, isolation at compute layer |
| ACK cluster security context | `alicloud-ack-ops` | Container cluster assets |
| KMS encryption keys | `alicloud-kms-ops` | Key rotation separate from SAS |
| CMS alarms on metrics | `alicloud-cms-ops` | External alerting |
| WAF web attacks | `waf-openapi` skill (if present) | Layer-7 web protection |

## Service-Linked Role

Security Center may require a service-linked role for cross-product access:

```bash
aliyun sas CreateServiceLinkedRole
```

Run once per account when APIs return role-related errors (verify message text).

## Multi-Account / Resource Directory

```bash
aliyun sas DescribeMonitorAccounts
aliyun sas CreateRdDefaultSyncList
```

Pass `ResourceDirectoryAccountId` on `DescribeCloudCenterInstances` when querying member accounts.

## Optional CLI Plugin

```bash
aliyun plugin install --names aliyun-cli-sas
```

## Pinned API Profile

| Field | Value |
|-------|-------|
| Product | Sas |
| Version | 2018-12-03 |
| SDK module | `github.com/alibabacloud-go/sas-20181203/v4/client` |

Re-verify operation signatures when upgrading SDK major versions.
