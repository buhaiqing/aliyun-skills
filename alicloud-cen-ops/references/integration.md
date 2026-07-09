<!-- markdownlint-disable MD013 MD060 MD024 MD022 MD032 -->

# Integration — CEN/CBN

## Execution Paths

| Path | Use When |
|------|----------|
| `aliyun cbn` CLI | Primary path for all supported CEN operations |
| Optional CBN CLI plugin | CLI suggests plugin or installed CLI lacks enhanced behavior |
| JIT Go SDK | CLI version/plugin lacks a needed parameter or automation requires typed SDK |

## Environment Variables

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
```

Do not print secrets. Validate with existence checks only:

```bash
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"
```

## CLI Setup

```bash
aliyun version
aliyun help cbn
aliyun plugin install --names aliyun-cli-cbn  # optional if available/needed
```

## JIT Go SDK Setup

```bash
mkdir -p /tmp/aliyun-cbn-sdk-workspace
cd /tmp/aliyun-cbn-sdk-workspace
go mod init cbn-sdk-script
export GOPROXY="https://goproxy.cn,direct"
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/cbn-20170912/v2/client
```

If Go is missing, use the repository JIT bootstrap script or download Go into a temporary workspace. Runtime artifacts must stay under `.runtime/` or `/tmp`, not committed.

## Minimal SDK Client

```go
cfg := &openapi.Config{
    AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
    AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
    Endpoint:        tea.String("cbn.aliyuncs.com"),
}
client, err := cbn.NewClient(cfg)
if err != nil { panic(err) }
```

Never log `cfg`.

## Cross-Skill Inputs

| From Skill | Input Needed by CEN |
|------------|---------------------|
| `alicloud-vpc-ops` | VPC ID, vSwitch IDs, zone IDs, CIDR blocks |
| `alicloud-vpc-ops` / VPN | VPN connection IDs and region |
| Express Connect/VBR skill when present | VBR ID, owner account, region |
| `alicloud-cms-ops` | Alarm creation and notification routing |

## Audit / Trace Paths

Runtime traces belong in gitignored paths:

```text
.runtime/audit/cen-ops/
audit-results/gcl-trace-*.json
```

Do not commit runtime JSON exports, flow log samples, or topology dumps unless the user explicitly reviews and approves.
