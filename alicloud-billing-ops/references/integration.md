# Integration — BSSOpenApi

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

### JIT Go SDK Workflow

```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script
export GOPROXY="https://goproxy.cn,direct"

go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/bssopenapi-20171214/v3/client

go run ./main.go
```

## Cross-Skill Delegation

BSSOpenApi (billing) is the foundation skill for financial operations. Other skills delegate billing queries here.

### Delegation Matrix

| Caller Skill | Delegates | Operation |
|-------------|-----------|-----------|
| `alicloud-ecs-ops` | Instance cost attribution | `QueryInstanceBill` with `ProductCode=ecs` |
| `alicloud-rds-ops` | Database billing | `QueryBill` with `ProductCode=rds` |
| `alicloud-slb-ops` | Load balancer costs | `QueryInstanceBill` with `ProductCode=slb` |
| `alicloud-ack-ops` | Cluster cost breakdown | `QuerySplitItemBill` with tag filter |
| `alicloud-oss-ops` | Storage billing | `QueryBill` with `ProductCode=oss` |
| Cost optimization | Budget analysis | `QueryBillOverview` + `QueryAccountBalance` |
| FinOps reporting | Consolidated costs | All `Query*` operations as needed |

### Inbound Delegations

This skill does not delegate to other skills for core billing queries. Billing operations are self-contained.

### Outbound Delegations

| Scenario | Delegate To |
|----------|-----------|
| Resource CRUD (instance management) | `alicloud-ecs-ops`, `alicloud-rds-ops`, etc. |
| RAM permissions for billing | `alicloud-ram-ops` |
| Account/resource group management | `alicloud-resourcemanager-ops` |
| Monitoring / CMS alarms | `alicloud-cms-ops` |

## Environment Variables

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"  # billing default
export GOPROXY="https://goproxy.cn,direct"     # China CDN mirror
```

## API Version Pinning

| Component | Version | Date |
|-----------|---------|------|
| BSSOpenApi API | 2017-12-14 | — |
| Go SDK | v3 | Latest stable |
| aliyun CLI | 3.3.14+ | Verified 2026-05 |

## Security Integration

### RAM Policy Template

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bssapi:QueryAccountBalance",
        "bssapi:QueryBill",
        "bssapi:QueryBillOverview",
        "bssapi:QueryInstanceBill",
        "bssapi:QuerySettleBill",
        "bssapi:QueryAccountBill",
        "bssapi:QuerySplitItemBill",
        "bssapi:QueryOrders",
        "bssapi:GetOrderDetail",
        "bssapi:QueryRIUtilizationDetail",
        "bssapi:QuerySavingsPlansInstance",
        "bssapi:QuerySavingsPlansDeductLog",
        "bssapi:QueryResourcePackageInstances",
        "bssapi:QueryAccountTransactions",
        "bssapi:QueryPrepaidCards",
        "bssapi:QueryCashCoupons"
      ],
      "Resource": "*"
    }
  ]
}
```

### Credential Security

- MANDATORY masking: NEVER log or echo `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- Verification uses existence checks only: `test -n "$var"`
- JIT Go SDK: `os.Getenv()` is safe; never `fmt.Printf("%+v", config)`
