# NAS Integration Reference

## Execution Environment

### Primary Path: `aliyun` CLI

Static Go binary, no runtime dependencies. Install once per host:

```bash
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"

# Optional: install the dedicated NAS plugin for ACL/AD/SMB protocol
aliyun plugin install --names aliyun-cli-nas
```

### Fallback Path: JIT Go SDK

When the agent prefers a programmatic flow, or for any operation the CLI
does not cover (rare; CLI covers ~95% of NAS), JIT-generate a Go script.

#### Go Runtime Bootstrap

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

> **Version strategy:** JIT downloads Go 1.24+; scripts target Go 1.21+
> compatibility (use `slices`, `maps` from `golang.org/x/exp` if you need
> 1.21-compatible newer features).

#### Workspace Bootstrap

```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script 2>/dev/null || true
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/nas-20170626/v3/client
```

#### Shared Client Factory

```go
// /tmp/aliyun-sdk-workspace/main.go (operation-agnostic header)
package main

import (
    "encoding/json"
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    nas "github.com/alibabacloud-go/nas-20170626/v3/client"
    "github.com/alibabacloud-go/tea/tea"
)

func newNASClient() (*nas.Client, error) {
    return nas.NewClient(&openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("nas." + os.Getenv("ALIBABA_CLOUD_REGION_ID") + ".aliyuncs.com"),
    })
}

func printResponse(b interface{}) {
    out, _ := json.MarshalIndent(b, "", "  ")
    fmt.Println(string(out))
}
```

Execute:

```bash
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
cd /tmp/aliyun-sdk-workspace
go run ./main.go
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | AccessKey ID |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | AccessKey Secret — **never echo in logs** |
| `ALIBABA_CLOUD_REGION_ID` | Yes | Region code (e.g., `cn-hangzhou`) |
| `ALIBABA_CLOUD_NAS_ENDPOINT` | Optional | Override default endpoint (for VPC-proxy) |
| `ALIBABA_CLOUD_STS_TOKEN` | Optional | For STS-based temporary credentials |

### `.env` File Format

```ini
# Alibaba Cloud credentials
ALIBABA_CLOUD_ACCESS_KEY_ID=LTAI5t***************
ALIBABA_CLOUD_ACCESS_KEY_SECRET=********************************
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

> **Security:** `.env` MUST be in `.gitignore` — never commit credentials.

## Required RAM Permissions

The following minimal RAM policy covers the core control-plane operations:

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "nas:OpenNASService",
        "nas:DescribeRegions",
        "nas:DescribeZones",
        "nas:DescribeFileSystems",
        "nas:CreateFileSystem",
        "nas:ModifyFileSystem",
        "nas:DeleteFileSystem",
        "nas:ResetFileSystem",
        "nas:DescribeMountTargets",
        "nas:CreateMountTarget",
        "nas:DeleteMountTarget",
        "nas:ModifyMountTarget",
        "nas:DescribeAccessGroups",
        "nas:CreateAccessGroup",
        "nas:DeleteAccessGroup",
        "nas:ModifyAccessGroup",
        "nas:DescribeAccessRules",
        "nas:CreateAccessRule",
        "nas:DeleteAccessRule",
        "nas:ModifyAccessRule",
        "nas:DescribeAccessPoints",
        "nas:CreateAccessPoint",
        "nas:DeleteAccessPoint",
        "nas:DescribeSnapshots",
        "nas:CreateSnapshot",
        "nas:DeleteSnapshot",
        "nas:DescribeAutoSnapshotPolicies",
        "nas:CreateAutoSnapshotPolicy",
        "nas:ApplyAutoSnapshotPolicy",
        "nas:CancelAutoSnapshotPolicy",
        "nas:DescribeLifecyclePolicies",
        "nas:CreateLifecyclePolicy",
        "nas:EnableRecycleBin",
        "nas:DisableAndCleanRecycleBin",
        "nas:GetRecycleBinAttribute",
        "nas:ListRecentlyRecycledDirectories",
        "nas:ListRecycledDirectoriesAndFiles",
        "nas:CreateRecycleBinRestoreJob",
        "nas:TagResources",
        "nas:UntagResources",
        "nas:ListTagResources"
      ],
      "Resource": "*"
    }
  ]
}
```

> **For resource-scoped (least-privilege) policies**, replace `"Resource": "*"`
> with explicit ARNs:
> `acs:nas:<region>:<account-id>:filesystem/*` and `acs:nas:<region>:<account-id>:accessgroup/*`.

## Cross-Skill Delegation Matrix

| Task | Delegate To |
|------|-------------|
| Create VPC / vSwitch for mount targets | `alicloud-vpc-ops` |
| Verify ECS instance / cluster can reach NAS MT | `alicloud-ecs-ops` |
| Add NAS permission to RAM role | `alicloud-ram-ops` |
| KMS CMK for NAS server-side encryption | `alicloud-kms-ops` |
| Cross-region snapshot DR | `alicloud-hbr-ops` |
| SLB / traffic control in front of NAS clients | `alicloud-slb-ops` |
| NAS billing / invoice queries | `alicloud-billing-ops` |
| ECI / ACK pods mounting NAS via CSI | `alicloud-ack-ops` / `alicloud-eci-ops` |
| PolarDB / RDS backup to NAS via DBS | `alicloud-dbs-ops` (when present) |

## Mount Target Workflow End-to-End

The most common NAS workflow is **create FS → create MT → mount from ECS**.
Cross-skill coordination:

```
1. alicloud-nas-ops:      OpenNASService (one-time)
2. alicloud-nas-ops:      CreateFileSystem
3. alicloud-vpc-ops:      DescribeVSwitches (verify vSwitch exists)
4. alicloud-nas-ops:      CreateAccessGroup + CreateAccessRule
5. alicloud-nas-ops:      CreateMountTarget (binds FS + VPC + vSwitch + group)
6. alicloud-ecs-ops:      AuthorizeSecurityGroup (allow TCP/2049 or 445)
7. (Operator)             mount on ECS, verify with df -h
```

For ACK clusters, the workflow uses the
[alicloud-storage-alicloudnas-csi](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-alibaba-cloud-nas-volumes)
driver. **Do not** manually mount NAS inside pods when using the CSI driver —
the driver handles mount / unmount lifecycle per pod.

## Endpoint Patterns

| Environment | Endpoint pattern |
|-------------|------------------|
| Public | `nas.<region>.aliyuncs.com` |
| VPC | `nas-vpc.<region>.aliyuncs.com` (or set `Endpoint` explicitly in SDK config) |
| Finance Cloud | `nas.<region>.aliyuncs.com` (different region prefix) |

For VPC access, set the SDK `Endpoint` to the VPC endpoint:

```go
config.Endpoint = tea.String("nas-vpc.cn-hangzhou.aliyuncs.com")
```

## Connection Pooling and Timeouts

For high-throughput mounts (e.g., AI training on CPFS):

- **NFS:** increase `rsize` and `wsize` to 1 MB:
  ```bash
  mount -t nfs -o rsize=1048576,wsize=1048576,vers=4.1 ...
  ```
- **SMB:** enable SMB Multichannel and large MTU on the client.
- **CPFS:** use the parallel data access pattern; consult Alibaba Cloud HPC
  best practices.

## NFS vs SMB Decision

| Factor | Choose NFS | Choose SMB |
|--------|------------|------------|
| Clients are Linux/Unix | ✅ | possible via `cifs-utils` |
| Clients are Windows | ❌ | ✅ native |
| AD / LDAP integration | Optional (NFSv4 with Kerberos) | ✅ first-class |
| POSIX ACLs (chmod/chown) | ✅ exact match | simulated (no real POSIX ACL) |
| Application compatibility | Linux native | Windows native |
| Performance tuning | `rsize/wsize` | SMB Multichannel |
| Recycle bin | `rm` → recycle bin (NAS-side) | Recycle Bin (Windows native) |
