# API & SDK — ECI (VERIFIED 2026-06-02)

> **Status: ✅ Fields verified via meta JSON
> (`https://api.aliyun.com/meta/v1/products/ECI/versions/2018-08-08/api-docs.json`)
> and `aliyun eci <Op> --help`**

## OpenAPI

- Spec: **ECI-2018-08-08** (verified)
- Documentation: https://www.alibabacloud.com/help/en/eci
- **Product code:** `eci` (separate from `cs`)

## SDK Operations Map (verified from `aliyun help eci`)

| Goal | CLI command |
|------|-------------|
| Create ECI | `aliyun eci CreateContainerGroup` |
| List ECIs | `aliyun eci DescribeContainerGroups` |
| Describe single ECI | `aliyun eci DescribeContainerGroup` (note: singular) |
| Delete ECI | `aliyun eci DeleteContainerGroup` |
| Restart ECI | `aliyun eci RestartContainerGroup` |
| Update ECI | `aliyun eci UpdateContainerGroup` |
| Exec into container | `aliyun eci ExecContainerCommand` |
| Get container logs | `aliyun eci DescribeContainerLog` |
| ECI events | `aliyun eci DescribeContainerGroupEvents` |
| ECI status (batch) | `aliyun eci DescribeContainerGroupStatus` |
| ECI metrics | `aliyun eci DescribeContainerGroupMetric` / `DescribeMultiContainerGroupMetric` |
| **Quota** | `aliyun eci ListUsage` (not `DescribeContainerGroupQuota`!) |
| Price query | `aliyun eci DescribeContainerGroupPrice` |
| Available resources | `aliyun eci DescribeAvailableResource` |
| Image cache | `aliyun eci CreateImageCache` / `DescribeImageCaches` / `DeleteImageCache` / `UpdateImageCache` |
| Data cache | `aliyun eci CreateDataCache` / `DescribeDataCaches` / `UpdateDataCache` / `CopyDataCache` / `DeleteDataCache` |
| Virtual node | `aliyun eci CreateVirtualNode` / `DescribeVirtualNodes` / `UpdateVirtualNode` / `DeleteVirtualNode` |
| Tags | `aliyun eci TagResources` / `UntagResources` / `ListTagResources` |
| Resize volume | `aliyun eci ResizeContainerGroupVolume` |
| Commit container to image | `aliyun eci CommitContainer` / `DescribeCommitContainerTask` |
| Ops task | `aliyun eci CreateInstanceOpsTask` / `DescribeInstanceOpsRecords` |

## SDK Package

```
github.com/alibabacloud-go/eci-20180808/client
```

## CreateContainerGroup — VERIFIED Field Reference

> **CLI call style:** `aliyun eci CreateContainerGroup` uses `--Container.n.*` array
> parameters OR `--body '{...}'` for complex requests.

### Required (verified)

| Field | CLI param | Description |
|-------|-----------|-------------|
| `RegionId` | `--RegionId` | Required |
| `ContainerGroupName` | `--ContainerGroupName` | Required, 2-128 chars, lowercase letters/digits/`-` |
| `Container[].Name` | `--Container.1.Name` | Required, container name |
| `Container[].Image` | `--Container.1.Image` | Required, 1-255 chars |
| `SecurityGroupId` | `--SecurityGroupId` | Optional — uses default SG if not specified |
| `VSwitchId` | `--VSwitchId` | Optional — comma-separated, max 10 |

### Compute (verified)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `Cpu` | float | — | **Instance-level** vCPU (核) |
| `Memory` | float | — | **Instance-level** memory (GiB) |
| `Container[].Cpu` | float | — | Per-container vCPU |
| `Container[].Memory` | float | — | Per-container memory (GiB) |
| `InstanceType` | string | — | **ECS instance type** (e.g. `ecs.c5.xlarge`); supports multiple |
| `Gpu` | int | 0 | GPU count |
| `EphemeralStorage` | int (GiB) | 0-5000 | Extra ephemeral storage |
| `CpuOptionsCore` | int | — | CPU 物理核心数（部分规格支持） |
| `CpuOptionsThreadsPerCore` | int | — | 每核线程数（1 = 关闭超线程） |
| `CpuOptionsNuma` | string | — | 暂不支持 |
| `CpuArchitecture` | enum | `AMD64` | `AMD64` / `ARM64` |
| `OsType` | enum | `Linux` | `Linux` / `Windows` (邀测) |
| `ComputeCategory` | enum | — | `economy` / `general` (多值, max 100) |
| `GpuDriverVersion` | string | — | GPU driver version (部分规格支持) |

### Restart / Scheduling (verified)

| Field | Values | Default |
|-------|--------|---------|
| `RestartPolicy` | `Always` / `Never` / `OnFailure` | **`Always`** |
| `ActiveDeadlineSeconds` | int | — | ECI max lifetime (after which killed) |
| `ScheduleStrategy` | `VSwitchOrdered` / `VSwitchRandom` | — | Multi-AZ |
| `TerminationGracePeriodSeconds` | int | 30 | Shutdown grace period |

### Spot (verified)

| Field | Values | Default |
|-------|--------|---------|
| `SpotStrategy` | `NoSpot` / `SpotWithPriceLimit` / `SpotAsPriceGo` | `NoSpot` |
| `SpotPriceLimit` | float | Required with `SpotWithPriceLimit` |
| `SpotDuration` | int (hours) | 1; 0 = no protection |
| `StrictSpot` | boolean | false |

### Image (verified)

| Field | Description |
|-------|-------------|
| `Image` (per container) | Required; e.g. `registry-vpc.cn-hangzhou.aliyuncs.com/eci_open/nginx:latest` |
| `ImagePullPolicy` | `Always` / `IfNotPresent` / `Never` |
| `ImageRegistryCredential` | Array of `{Server, UserName, Password}`, max 11 |
| `ImageSnapshotId` | Bind image cache for fast startup |
| `ImageAccelerateMode` | `nydus` / `dadi` / `p2p` / `imc` |
| `AcrRegistryInfo` | ACR 企业版免密 (InstanceId, RegionId, ArnService, ArnUser, Domain) |
| `PlainHttpRegistry` | HTTP registry (self-hosted) |
| `InsecureRegistry` | Self-signed cert registry |
| `AutoMatchImageCache` | boolean (default false) |

### Container configuration (verified)

| Field | Type | Description |
|-------|------|-------------|
| `Arg` | array of string | Container args (max 10, 65535 chars each) |
| `Command` | array of string | Container cmd (max 20, 256 chars each) |
| `EnvironmentVar` | array of `{Key, Value, FieldRef.FieldPath}` | Env vars (max 241) |
| `EnvironmentVarHide` | boolean | Hide env vars in Describe response |
| `Port` | array of `{Protocol, Port}` | Container ports (max 101) |
| `VolumeMount` | array of `{MountPath, ReadOnly, SubPath, Name, MountPropagation}` | |
| `Tty` / `Stdin` / `StdinOnce` | boolean | TTY/STDIN config |
| `WorkingDir` | string | Working dir |
| `TerminationMessagePath` | string | Termination message file path |
| `TerminationMessagePolicy` | string | `FallbackToLogsOnError` |

### Probes (verified)

Both `LivenessProbe.*` and `ReadinessProbe.*` (with all same fields):

| Field | Type | Description |
|-------|------|-------------|
| `*.Exec.Command` | array of string | Cmd-style check (max 20) |
| `*.HttpGet.Path` | string | HTTP path |
| `*.HttpGet.Port` | int | HTTP port |
| `*.HttpGet.Scheme` | enum | `HTTP` / `HTTPS` |
| `*.TcpSocket.Port` | int | TCP port |
| `*.InitialDelaySeconds` | int | Delay after start |
| `*.PeriodSeconds` | int | Check period (default 10, min 1) |
| `*.TimeoutSeconds` | int | Timeout (default 1, min 1) |
| `*.SuccessThreshold` | int | Default 1; **currently must be 1** |
| `*.FailureThreshold` | int | Default 3 |

### Lifecycle hooks (verified)

Both `LifecyclePostStartHandler*` and `LifecyclePreStopHandler*` (same shape):

| Field | Description |
|-------|-------------|
| `*.Exec` | array of string (shell command) |
| `*.HttpGetHost` / `*.HttpGetPath` / `*.HttpGetPort` / `*.HttpGetScheme` / `*.HttpGetHttpHeader` | HTTP hook |
| `*.TcpSocketHost` / `*.TcpSocketPort` | TCP hook |

### Container SecurityContext (verified — LIMITED)

| Field | Allowed values | Notes |
|-------|-----------------|-------|
| `SecurityContext.Capability.Add` | only `NET_ADMIN`, `NET_RAW` | NET_RAW needs ticket |
| `SecurityContext.ReadOnlyRootFilesystem` | only `true` | |
| `SecurityContext.RunAsUser` | integer | |
| `SecurityContextRunAsGroup` | integer | (no `SecurityContext.` prefix!) |
| `SecurityContextRunAsNonRoot` | boolean | |
| `SecurityContextPrivileged` | boolean | **内测中**, needs ticket |
| `SecurityContext.Sysctl` | array | Safe sysctls only (`net.ipv4.ping_group_range`, `net.ipv4.ip_unprivileged_port_start`) |
| `HostSecurityContext.Sysctl` | array | Unsafe sysctls (`kernel.*`, `net.*`, `fs.mqueue.*`) |

### `Volume` types (verified)

```json
"Volume": [
  {
    "Name": "vol1",
    "Type": "EmptyDirVolume",
    "EmptyDirVolume": { "Medium": "memory", "SizeLimit": "2" }
  }
]
```

| Type | Sub-fields | Notes |
|------|-----------|-------|
| `EmptyDirVolume` | `Medium` (memory), `SizeLimit` (GiB) | |
| `NFSVolume` | `Path`, `Server`, `ReadOnly` | |
| `ConfigFileVolume` | `DefaultMode`, `ConfigFileToPath[]` (Path, Mode, Content base64) | Total content ≤ 60KB; each file ≤ 32KB |
| `FlexVolume` | `Driver` (`alicloud/disk` / `alicloud/nas` / `alicloud/oss`), `FsType`, `Options` (JSON) | **Preferred way to mount cloud disk** |
| `HostPathVolume` | `Type` (Directory/File), `Path` | **Whitelist only** |
| `DiskVolume` | `DiskId`, `DiskSize`, `FsType` | ⚠️ **Not recommended** — use FlexVolume |

### `InitContainer` (verified — supported)

Same shape as `Container` (minus probes). Standard K8s init pattern works.

### Network (verified)

| Field | Description |
|-------|-------------|
| `ZoneId` | AZ (optional, auto-selected) |
| `SecurityGroupId` | Default SG if not specified |
| `VSwitchId` | Comma-separated, max 10 |
| `EipInstanceId` | Bind existing EIP |
| `AutoCreateEip` | Auto-create EIP (boolean) |
| `EipBandwidth` | EIP bandwidth in Mbps (default 5) |
| `EipISP` | `BGP` (default) / `BGP_PRO` |
| `EipCommonBandwidthPackage` | Bind to existing shared bandwidth package |
| `IngressBandwidth` / `EgressBandwidth` | Per-direction bandwidth limit (Bps) |
| `Ipv6AddressCount` | int (fixed 1) | IPv6 address |
| `Ipv6GatewayBandwidthEnable` | boolean | IPv6 public gateway |
| `Ipv6GatewayBandwidth` | string | IPv6 public bandwidth (Mbps) |
| `PrivateIpAddress` | string | Specify private IPv4 |
| `FixedIp` | string (boolean) | Enable fixed IP |
| `FixedIpRetainHour` | int | Fixed IP retention (default 48h) |
| `HostAliase` | array of `{Ip, Hostname[]}` | Hostname aliases |
| `DnsPolicy` | `None` / `Default` |
| `DnsConfig.NameServer` / `Search` / `Option` | arrays | DNS config |

### Metadata (verified)

| Field | Type | Description |
|-------|------|-------------|
| `Tag` | array of `{Key, Value}` | Max 20 |
| `ResourceGroupId` | string | Resource group |
| `RamRoleName` | string | Instance RAM role |
| `ClientToken` | string | Idempotency (≤64 ASCII) |
| `HostName` | string | Hostname |
| `CorePattern` | string | Coredump path (not starting with `|`) |
| `ShareProcessNamespace` | boolean | Share PID namespace |
| `NtpServer` | array of string | NTP servers (max 21) |

### Data cache (verified)

`DataCacheBucket`, `DataCachePL`, `DataCacheProvisionedIops`,
`DataCacheBurstingEnabled` — for ECI tied to data cache.

### Dry run (verified)

`DryRun` (boolean) — pre-check only, returns `DryRun.Success` if OK.

### Verified response (CreateContainerGroup)

```json
{
  "RequestId": "89945DD3-9072-47D0-A318-353284CFC7B3",
  "ContainerGroupId": "eci-uf6fonnghi50u374****"
}
```

## DescribeContainerGroups — VERIFIED CLI Params

```
--RegionId                 Required, string
--ContainerGroupIds        JSON array, max 20
--ContainerGroupName       string
--Limit                    integer (default 20, max 20)
--NextToken                string (pagination)
--ResourceGroupId          string
--SecurityGroupId          string
--Status                   enum: Pending / Running (more values exist, verify)
--ComputeCategory          string
```

## ListUsage (Quota) — VERIFIED

```bash
aliyun eci ListUsage --RegionId cn-hangzhou
```

Returns region-level quota information. (Exact response field names
need first-use verification — see [openapi-verify-checklist.md](openapi-verify-checklist.md).)

## State Transitions

| Operation | Initial | Target | Poll Interval | Max Wait |
|-----------|---------|--------|---------------|----------|
| CreateContainerGroup | — | `Running` / `Succeeded` / `Failed` | 5s | 300s |
| DeleteContainerGroup | any | absent / 404 | 5s | 120s |
| UpdateContainerGroup | `Running` | `Running` | 5s | 120s |
| RestartContainerGroup | any | `Running` | 5s | 120s |

## JIT Go SDK Pattern

```go
// Pseudocode — adapt to exact SDK method signatures
package main

import (
    "fmt"
    "os"
    "github.com/alibabacloud-go/tea/tea"
    eci "github.com/alibabacloud-go/eci-20180808/client"
    "github.com/alibabacloud-go/tea-openapi/service"
)

func newClient() (*eci.Client, error) {
    config := &service.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    return eci.NewClient(config)
}

func createECI(c *eci.Client, name, image, sgId, vswId string, cpu, mem float32) (string, error) {
    body := map[string]interface{}{
        "RegionId":          os.Getenv("ALIBABA_CLOUD_REGION_ID"),
        "ContainerGroupName": name,
        "RestartPolicy":     "Never",  // <-- avoid infinite restart for batch jobs
        "SecurityGroupId":   sgId,
        "VSwitchId":         vswId,
        "Container": []map[string]interface{}{
            {
                "Name":  "app",
                "Image": image,
                "Cpu":   cpu,
                "Memory": mem,
            },
        },
        "Cpu":         cpu,
        "Memory":      mem,
        "ClientToken": fmt.Sprintf("%s-%d", name, os.Getpid()),
    }
    resp, err := c.CreateContainerGroup(body)
    if err != nil {
        return "", err
    }
    return *resp.Body.ContainerGroupId, nil
}
```

> **Never log the SK or print the full config struct.**

## Pagination

`DescribeContainerGroups` uses `Limit` (default 20, max 20) + `NextToken`.
`DescribeContainerGroupStatus` similar pattern.
