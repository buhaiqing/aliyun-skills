# OpenAPI Verify Checklist — ECI (VERIFIED 2026-06-02)

> **Status: ✅ VERIFIED via `aliyun help eci` + `aliyun eci <Op> --help` +
> `https://api.aliyun.com/meta/v1/products/ECI/versions/2018-08-08/api-docs.json`**

## ✅ Verified Findings (real OpenAPI, training knowledge was partially wrong)

### Major correction 1: Quota command is `ListUsage`, NOT `DescribeContainerGroupQuota`

The CLI exposes **`aliyun eci ListUsage`** (and **`DescribeContainerGroupPrice`**, **`DescribeAvailableResource`**).
**There is no `DescribeContainerGroupQuota` operation** — earlier training
knowledge was wrong.

Verified operation list (from `aliyun help eci`):

```
CommitContainer, CopyDataCache, CreateContainerGroup, CreateDataCache,
CreateImageCache, CreateInstanceOpsTask, CreateVirtualNode,
DeleteContainerGroup, DeleteDataCache, DeleteImageCache, DeleteVirtualNode,
DescribeAvailableResource, DescribeCommitContainerTask,
DescribeContainerGroupEvents, DescribeContainerGroupMetric,
DescribeContainerGroupPrice, DescribeContainerGroupStatus,
DescribeContainerGroups, DescribeContainerLog, DescribeDataCaches,
DescribeImageCaches, DescribeInstanceOpsRecords,
DescribeMultiContainerGroupMetric, DescribeRegions, DescribeVirtualNodes,
ExecContainerCommand, ListTagResources, ListUsage,
ResizeContainerGroupVolume, RestartContainerGroup, TagResources,
UntagResources, UpdateContainerGroup, UpdateDataCache, UpdateImageCache,
UpdateVirtualNode
```

### Major correction 2: `CpuOptions` is actually `CpuOptionsCore` + `CpuOptionsThreadsPerCore`

The OpenAPI does **not** have a single `CpuOptions` object. Instead it has:

| Field | Type | Description |
|-------|------|-------------|
| `CpuOptionsCore` | integer | CPU 物理核心数。仅部分规格支持 |
| `CpuOptionsThreadsPerCore` | integer | 每核线程数。1 = 关闭超线程 |
| `CpuOptionsNuma` | string | 暂不支持设置 |

### Major correction 3: `ImageRegistryCredential` shape is `Server` + `UserName` + `Password`

```json
"ImageRegistryCredential": [
  {
    "Server": "registry-vpc.cn-shanghai.aliyuncs.com",
    "UserName": "yourusername",
    "Password": "yourpassword"
  }
]
```

(Note: `UserName`, not `Username`; no `Registry` field — `Server` is the
registry address.)

### Major correction 4: `ExecContainerCommand` CLI takes JSON array, not string

```bash
# ✅ Correct — Command is JSON array
aliyun eci ExecContainerCommand \
  --RegionId cn-hangzhou \
  --ContainerGroupId eci-xxx \
  --ContainerName app \
  --Command '["/bin/sh", "-c", "ls -la /tmp"]'

# ❌ Wrong — do NOT pass a plain string
# --Command "ls -la /tmp"
```

Other params (verified): `Stdin` (default true), `Sync` (default false;
if true, TTY must be false), `TTY` (default false; if Command is
`/bin/bash`, must be true).

### `RestartPolicy` (verified, 3 values)

| Value | Default | Behavior |
|-------|---------|----------|
| `Always` | ✅ default | Always restart |
| `Never` | — | Never restart (recommended for batch jobs to avoid infinite billing) |
| `OnFailure` | — | Restart only on non-zero exit |

### `InstanceType` for ECS spec-based creation (verified)

You can create ECI by **specifying vCPU+memory** OR **specifying an ECS
instance type**. The latter (`InstanceType` field) lets you pin to a
specific ECS spec like `ecs.c5.xlarge`.

| Creation mode | Required fields |
|---------------|-----------------|
| vCPU + memory mode | `Cpu` (instance-level), `Memory` (instance-level), per-container `Cpu`/`Memory` |
| ECS spec mode | `InstanceType` (e.g. `ecs.c5.xlarge`) |
| Both (multi-spec) | `InstanceType` accepts multiple specs comma-separated |

### Spot instances (verified)

| Field | Values | Default |
|-------|--------|---------|
| `SpotStrategy` | `NoSpot` / `SpotWithPriceLimit` / `SpotAsPriceGo` | `NoSpot` |
| `SpotPriceLimit` | float (0.001-1000) | Required when `SpotWithPriceLimit` |
| `SpotDuration` | integer hours | 1 default; 0 = no protection |
| `StrictSpot` | boolean | false default |

### `ComputeCategory` (verified)

| Value | Description |
|-------|-------------|
| `economy` | 经济型 |
| `general` | 通用型 |

Multiple values can be passed (max 100) to set creation order.

### `Volume.Type` full support matrix (verified)

| Type | Description |
|------|-------------|
| `EmptyDirVolume` | EmptyDir (with `Medium=memory` for RAM, `SizeLimit` for cap) |
| `NFSVolume` | NFS (with `Path`, `ReadOnly`, `Server`) |
| `ConfigFileVolume` | ConfigFile (with `DefaultMode`, `ConfigFileToPath` array; total ≤ 60KB) |
| `FlexVolume` | FlexVolume plugin (`alicloud/disk` / `alicloud/nas` / `alicloud/oss`) |
| `HostPathVolume` | HostPath (Type: `Directory` or `File`; **whitelist only**) |
| `DiskVolume` | Cloud disk (⚠️ **not recommended**; use FlexVolume) |

### `InitContainer` (verified — supported)

Init container fields mirror `Container` minus a few (no `LivenessProbe`,
etc.). Standard K8s init pattern works.

### Container `SecurityContext` (verified — limited support)

| Field | Values | Notes |
|-------|--------|-------|
| `SecurityContext.Capability.Add` | only `NET_ADMIN` and `NET_RAW` | NET_RAW needs ticket |
| `SecurityContext.ReadOnlyRootFilesystem` | only `true` | |
| `SecurityContext.RunAsUser` | integer | |
| `SecurityContextRunAsGroup` | integer | (note: no `SecurityContext.` prefix here) |
| `SecurityContextRunAsNonRoot` | boolean | |
| `SecurityContextPrivileged` | boolean | **内测中**, needs ticket |

### EIP (verified — multiple modes)

| Field | Description |
|-------|-------------|
| `EipInstanceId` | Bind existing EIP |
| `AutoCreateEip` | Auto-create EIP (boolean) |
| `EipBandwidth` | EIP bandwidth in Mbps (default 5) |
| `EipISP` | `BGP` (default) / `BGP_PRO` |
| `EipCommonBandwidthPackage` | Bind to existing shared bandwidth package |
| `IngressBandwidth` / `EgressBandwidth` | Bandwidth limit per direction (Bps) |

### Other verified fields (CreateContainerGroup)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `RegionId` | string | — | **Required** |
| `ZoneId` | string | auto | AZ |
| `SecurityGroupId` | string | auto | Default SG if not specified |
| `VSwitchId` | string | auto | **Supports multiple, comma-separated, max 10** |
| `ContainerGroupName` | string | — | **Required**, 2-128 chars, lowercase letters/digits/`-` |
| `EphemeralStorage` | int (GiB) | 0-5000 | Extra ephemeral storage |
| `ActiveDeadlineSeconds` | int | — | ECI max lifetime; after which it's killed |
| `TerminationGracePeriodSeconds` | int | 30 | Grace period for shutdown |
| `Ipv6AddressCount` | int (fixed 1) | — | IPv6 address count |
| `FixedIp` | string (boolean) | false | Enable fixed IP for instance |
| `FixedIpRetainHour` | int | 48 | Fixed IP retention hours |
| `AutoMatchImageCache` | boolean | false | Auto match image cache |
| `ImageSnapshotId` | string | — | Bind image cache for fast startup |
| `ResourceGroupId` | string | — | Resource group |
| `RamRoleName` | string | — | Instance RAM role |
| `HostName` | string | — | Hostname |
| `CorePattern` | string | — | Custom coredump path |
| `ShareProcessNamespace` | boolean | false | Share PID namespace |
| `ScheduleStrategy` | enum | — | `VSwitchOrdered` / `VSwitchRandom` |
| `Tag` | array of {Key,Value} | — | Max 20 |
| `ImageRegistryCredential` | array of {Server, UserName, Password} | — | Max 11 |
| `DnsPolicy` | enum | — | `None` / `Default` |
| `DnsConfig.NameServer` / `Search` / `Option` | arrays | — | DNS config |
| `NtpServer` | array | — | NTP servers (max 21) |
| `HostAliase` | array of {Ip, Hostname} | — | Hostname aliases (note typo in API) |
| `SecurityContext.Sysctl` | array of {Name,Value} | — | Safe sysctls only |
| `HostSecurityContext.Sysctl` | array of {Name,Value} | — | Unsafe sysctls (kernel.*, net.*, etc.) |
| `AcrRegistryInfo` | array of {InstanceId, RegionId, ArnService, ArnUser, Domain, InstanceName} | — | ACR 企业版免密 |
| `PlainHttpRegistry` | string | — | HTTP registry addresses (comma-separated) |
| `InsecureRegistry` | string | — | Self-signed cert registry |
| `ImageAccelerateMode` | enum | — | `nydus` / `dadi` / `p2p` / `imc` |
| `Ipv6GatewayBandwidthEnable` | boolean | false | Enable IPv6 gateway |
| `Ipv6GatewayBandwidth` | string | — | IPv6 gateway bandwidth (Mbps) |
| `ContainerResourceView` | boolean | false | Container sees spec as request |
| `DataCacheBucket` / `DataCachePL` / `DataCacheProvisionedIops` / `DataCacheBurstingEnabled` | various | — | Data cache params |
| `DryRun` | boolean | false | Pre-check only |
| `PrivateIpAddress` | string | — | Specify IPv4 private IP |
| `OsType` | enum | Linux | `Linux` / `Windows` (Windows 邀测) |
| `CpuArchitecture` | enum | AMD64 | `AMD64` / `ARM64` |
| `GpuDriverVersion` | string | — | GPU driver version |
| `MaxPendingMinute` | int | — | Max pending minutes |

### Verified response (CreateContainerGroup)

```json
{
  "RequestId": "89945DD3-9072-47D0-A318-353284CFC7B3",
  "ContainerGroupId": "eci-uf6fonnghi50u374****"
}
```

### Verified error codes (sampled)

400: `Account.Arrearage`, `DryRunOperation`, `InvalidParameter.CPU.Memory`,
`InvalidParameter.DuplicatedName`, `InvalidParameter.DuplicatedVolumeName`,
`IncorrectStatus`, `ServiceNotEnabled`, `ImageSnapshot.IncorrectStatus`,
`ImageSnapshot.NotSupport`, `DiskVolume.NotSupport`, `RamRole.NotSupport`,
`DiskNumber.LimitExceed`, `InvalidPaymentMethod.InsufficientBalance`,
`DiskVolume.NotInSameZone`, `NoPermission`, `HighCpuMemConfigRequired`,
`RecommendEmpty.InstanceTypeFamilyNotMatched`, `LocalDiskAmountNotMatch`,
`Payfor.CreditPayInsufficientBalance`, `InvalidOperation.KMS.InstanceTypeNotSupport`,
`InvalidParameter.Encrypted.KmsNotEnabled`, `InvalidParameter.KMS.EncryptedIllegal`,
`InvalidSpotCpuMemorySpec`, `Ipv6AddressNotSupportVsw`, `Ipv6AddressNotSupport`,
`Ipv6AddressNotSupportInstanceType`, `EipPayInsufficientBalance`,
`EipPurchaseFlowControl`, `Throttling`, `JobInstance*` series,
`InvalidInstanceTypeForEciSpotDurationBuy`, `InvalidInstanceTypeForEciBuy`,
`InstanceTypeNotMatchCpuArch`, `PrivateIpAddress.Already.InUse`,
`IncorrectOperation`, `FeatureBasedConstraintConflict`,
`OperationFailed.RiskControl`, `RISK.RISK_CONTROL_REJECTION`,
`InvalidInstanceTypeForRaid`, `RegionDissolved`,
`MultiAttachedCloudDiskNotSupport`

403: `OperationDenied.VswZoneMisMatch`, `QuotaExceeded`, `Zone.NotOnSale`,
`Forbidden.RiskControl`, `Forbidden.SubUser`, `Forbidden.OnlyForInvitedTest`,
`OperationDenied.SecurityGroupMisMatch`, `InvalidVSwitchId.IpNotEnough`,
`Forbidden.UserBussinessStatus`, `Forbidden.UserNotRealNameAuthentication`,
`InvalidUser.PassRoleForbidden`, `NoPermission`, `OperationDenied.NoStock`,
`InvalidParameter.KMS.KeyId.Forbidden`, `Forbidden.AccountClosed`,
`InvalidOperation.ResourceManagedByCloudProduct`, `Spot.NotMatched`,
`SecurityRisk.3DVerification`, `CreateServiceLinkedRole.Denied`,
`Throttling.Vcpu.PerDay`, `FeatureAccessRestricted`

404: `ImageSnapshot.NotFound`, `InvalidDiskId.NotFound`,
`InvalidParameter.KMS.KeyId.NotFound`

## When to Re-Verify

| Trigger | Action |
|---------|--------|
| OpenAPI version change | Re-fetch meta JSON |
| New ECI feature needed | Re-verify specific field |
| CLI version upgrade | Re-run `aliyun eci <Op> --help` |

## Commands Re-Run

```bash
# All ECI operations
aliyun help eci

# Specific operation parameters
aliyun eci CreateContainerGroup --help
aliyun eci ExecContainerCommand --help
aliyun eci DescribeContainerGroups --help
aliyun eci ListUsage --body '{"RegionId":"cn-hangzhou"}'   # quota

# Meta JSON (canonical schema)
curl -s https://api.aliyun.com/meta/v1/products/ECI/versions/2018-08-08/api-docs.json | jq '.apis.CreateContainerGroup'
```
