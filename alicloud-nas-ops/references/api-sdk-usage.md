# NAS API & SDK Reference

## OpenAPI Profile

- **Product code:** `nas`
- **API version:** `2017-06-26`
- **Style:** RPC-style (parameter-style)
- **Endpoint pattern:** `nas.<region>.aliyuncs.com` (e.g., `nas.cn-hangzhou.aliyuncs.com`)
- **OpenAPI Explorer:** <https://api.aliyun.com/api/NAS/2017-06-26>
- **Documentation:** <https://help.aliyun.com/zh/nas/developer-reference/api-nas-2017-06-26-overview>

## Go SDK

- **Package:** `github.com/alibabacloud-go/nas-20170626/v3/client`
- **Required Go version:** 1.21+ (JIT download 1.24+)
- **OpenAPI base:** `github.com/alibabacloud-go/darabonba-openapi/v2/client`
- **Tea utils:** `github.com/alibabacloud-go/tea/tea`

### Install

```bash
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/nas-20170626/v3/client
```

### Client Factory

```go
// /tmp/aliyun-sdk-workspace/main.go
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

## Operation Map (Aliyun-Native Categories)

### Service Activation & Discovery

| Goal | API operationId | SDK method | Notes |
|------|-----------------|------------|-------|
| Activate NAS | `OpenNASService` | `OpenNASService` | One-time per region |
| List regions | `DescribeRegions` | `DescribeRegions` | |
| List zones | `DescribeZones` | `DescribeZones` | Per zone lists supported FS types |

### File System Lifecycle

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| Create FS | `CreateFileSystem` | `CreateFileSystem` |
| List FS | `DescribeFileSystems` | `DescribeFileSystems` |
| Modify FS description | `ModifyFileSystem` | `ModifyFileSystem` |
| Upgrade FS (Extreme/CPFS) | `UpgradeFileSystem` | `UpgradeFileSystem` |
| Delete FS | `DeleteFileSystem` | `DeleteFileSystem` |
| Roll back to snapshot | `ResetFileSystem` | `ResetFileSystem` |
| Change resource group | `ChangeResourceGroup` | `ChangeResourceGroup` |

### Mount Target

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| Create mount target | `CreateMountTarget` | `CreateMountTarget` |
| List mount targets | `DescribeMountTargets` | `DescribeMountTargets` |
| Modify mount target | `ModifyMountTarget` | `ModifyMountTarget` |
| Delete mount target | `DeleteMountTarget` | `DeleteMountTarget` |
| List mounted clients | `DescribeMountedClients` | `DescribeMountedClients` |

### Permission (Access Group / Rule)

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| Create access group | `CreateAccessGroup` | `CreateAccessGroup` |
| List access groups | `DescribeAccessGroups` | `DescribeAccessGroups` |
| Modify access group | `ModifyAccessGroup` | `ModifyAccessGroup` |
| Delete access group | `DeleteAccessGroup` | `DeleteAccessGroup` |
| Create access rule | `CreateAccessRule` | `CreateAccessRule` |
| List access rules | `DescribeAccessRules` | `DescribeAccessRules` |
| Modify access rule | `ModifyAccessRule` | `ModifyAccessRule` |
| Delete access rule | `DeleteAccessRule` | `DeleteAccessRule` |

### Access Points (NAS 2020+ feature)

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| Create access point | `CreateAccessPoint` | `CreateAccessPoint` |
| List access points | `DescribeAccessPoints` | `DescribeAccessPoints` |
| Get access point | `DescribeAccessPoint` | `DescribeAccessPoint` |
| Modify access point | `ModifyAccessPoint` | `ModifyAccessPoint` |
| Delete access point | `DeleteAccessPoint` | `DeleteAccessPoint` |

### Snapshots

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| Create snapshot | `CreateSnapshot` | `CreateSnapshot` |
| List snapshots | `DescribeSnapshots` | `DescribeSnapshots` |
| Delete snapshot | `DeleteSnapshot` | `DeleteSnapshot` |
| Create auto-snapshot policy | `CreateAutoSnapshotPolicy` | `CreateAutoSnapshotPolicy` |
| List auto-snapshot policies | `DescribeAutoSnapshotPolicies` | `DescribeAutoSnapshotPolicies` |
| Modify auto-snapshot policy | `ModifyAutoSnapshotPolicy` | `ModifyAutoSnapshotPolicy` |
| Delete auto-snapshot policy | `DeleteAutoSnapshotPolicy` | `DeleteAutoSnapshotPolicy` |
| Apply policy to FS | `ApplyAutoSnapshotPolicy` | `ApplyAutoSnapshotPolicy` |
| Cancel policy on FS | `CancelAutoSnapshotPolicy` | `CancelAutoSnapshotPolicy` |
| List auto-snapshot tasks | `DescribeAutoSnapshotTasks` | `DescribeAutoSnapshotTasks` |

### Lifecycle / Tier-Down

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| Create lifecycle policy | `CreateLifecyclePolicy` | `CreateLifecyclePolicy` |
| List lifecycle policies | `DescribeLifecyclePolicies` | `DescribeLifecyclePolicies` |
| Modify lifecycle policy | `ModifyLifecyclePolicy` | `ModifyLifecyclePolicy` |
| Update lifecycle policy | `UpdateLifecyclePolicy` | `UpdateLifecyclePolicy` |
| Delete lifecycle policy | `DeleteLifecyclePolicy` | `DeleteLifecyclePolicy` |
| Start policy execution | `StartLifecyclePolicyExecution` | `StartLifecyclePolicyExecution` |
| Stop policy execution | `StopLifecyclePolicyExecution` | `StopLifecyclePolicyExecution` |
| List retrieve jobs | `ListLifecycleRetrieveJobs` | `ListLifecycleRetrieveJobs` |
| Cancel retrieve job | `CancelLifecycleRetrieveJob` | `CancelLifecycleRetrieveJob` |
| Retry retrieve job | `RetryLifecycleRetrieveJob` | `RetryLifecycleRetrieveJob` |
| Create retrieve job | `CreateLifecycleRetrieveJob` | `CreateLifecycleRetrieveJob` |

### Recycle Bin

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| Enable recycle bin | `EnableRecycleBin` | `EnableRecycleBin` |
| Get attribute | `GetRecycleBinAttribute` | `GetRecycleBinAttribute` |
| Update attribute (retention) | `UpdateRecycleBinAttribute` | `UpdateRecycleBinAttribute` |
| Disable + clean | `DisableAndCleanRecycleBin` | `DisableAndCleanRecycleBin` |
| List recently recycled dirs | `ListRecentlyRecycledDirectories` | `ListRecentlyRecycledDirectories` |
| List recycled files | `ListRecycledDirectoriesAndFiles` | `ListRecycledDirectoriesAndFiles` |
| Create restore job | `CreateRecycleBinRestoreJob` | `CreateRecycleBinRestoreJob` |
| Create delete job | `CreateRecycleBinDeleteJob` | `CreateRecycleBinDeleteJob` |
| List recycle jobs | `ListRecycleBinJobs` | `ListRecycleBinJobs` |
| Cancel recycle job | `CancelRecycleBinJob` | `CancelRecycleBinJob` |

### ACL (NFS / SMB)

| Goal | API operationId | SDK method | Plugin-Required |
|------|-----------------|------------|-----------------|
| Enable NFS ACL | `EnableNfsAcl` | `EnableNfsAcl` | yes (aliyun-cli-nas) |
| Disable NFS ACL | `DisableNfsAcl` | `DisableNfsAcl` | yes |
| Describe NFS ACL | `DescribeNfsAcl` | `DescribeNfsAcl` | yes |
| Enable SMB ACL | `EnableSmbAcl` | `EnableSmbAcl` | yes |
| Disable SMB ACL | `DisableSmbAcl` | `DisableSmbAcl` | yes |
| Describe SMB ACL | `DescribeSmbAcl` | `DescribeSmbAcl` | yes |
| Modify SMB ACL | `ModifySmbAcl` | `ModifySmbAcl` | yes |
| Create LDAP config | `CreateLDAPConfig` | `CreateLDAPConfig` | yes |
| Modify LDAP config | `ModifyLDAPConfig` | `ModifyLDAPConfig` | yes |
| Delete LDAP config | `DeleteLDAPConfig` | `DeleteLDAPConfig` | yes |

### SMB Protocol Service (alternative to classic SMB)

| Goal | API operationId | SDK method | Plugin-Required |
|------|-----------------|------------|-----------------|
| Create protocol service | `CreateProtocolService` | `CreateProtocolService` | yes |
| Describe protocol service | `DescribeProtocolService` | `DescribeProtocolService` | yes |
| Modify protocol service | `ModifyProtocolService` | `ModifyProtocolService` | yes |
| Delete protocol service | `DeleteProtocolService` | `DeleteProtocolService` | yes |
| Create protocol mount target | `CreateProtocolMountTarget` | `CreateProtocolMountTarget` | yes |
| Describe protocol mount target | `DescribeProtocolMountTarget` / `GetProtocolMountTarget` | same | yes |
| Modify protocol mount target | `ModifyProtocolMountTarget` | `ModifyProtocolMountTarget` | yes |
| Delete protocol mount target | `DeleteProtocolMountTarget` | `DeleteProtocolMountTarget` | yes |

### Filesets (CPFS / CPFS SE only)

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| Create fileset | `CreateFileset` | `CreateFileset` |
| Get fileset | `GetFileset` | `GetFileset` |
| List filesets | `DescribeFilesets` | `DescribeFilesets` |
| Modify fileset | `ModifyFileset` | `ModifyFileset` |
| Delete fileset | `DeleteFileset` | `DeleteFileset` |

### Data Flow (CPFS only)

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| Create dataflow | `CreateDataFlow` | `CreateDataFlow` |
| List dataflows | `DescribeDataFlows` | `DescribeDataFlows` |
| Modify dataflow | `ModifyDataFlow` | `ModifyDataFlow` |
| Delete dataflow | `DeleteDataFlow` | `DeleteDataFlow` |
| Start dataflow | `StartDataFlow` | `StartDataFlow` |
| Stop dataflow | `StopDataFlow` | `StopDataFlow` |
| Create dataflow task | `CreateDataFlowTask` | `CreateDataFlowTask` |
| List dataflow tasks | `DescribeDataFlowTasks` | `DescribeDataFlowTasks` |
| Cancel dataflow task | `CancelDataFlowTask` | `CancelDataFlowTask` |
| Create dataflow subtask | `CreateDataFlowSubTask` | `CreateDataFlowSubTask` |
| List dataflow subtasks | `DescribeDataFlowSubTasks` | `DescribeDataFlowSubTasks` |
| Cancel dataflow subtask | `CancelDataFlowSubTask` | `CancelDataFlowSubTask` |
| Auto-refresh | `ApplyDataFlowAutoRefresh` / `CancelDataFlowAutoRefresh` / `ModifyDataFlowAutoRefresh` | same |

### Directory Quota

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| Set dir quota | `SetDirQuota` | `SetDirQuota` |
| List dir quotas | `DescribeDirQuotas` | `DescribeDirQuotas` |
| Cancel dir quota | `CancelDirQuota` | `CancelDirQuota` |
| Set fileset quota | `SetFilesetQuota` | `SetFilesetQuota` |
| Cancel fileset quota | `CancelFilesetQuota` | `CancelFilesetQuota` |

### File-Level Operations (data plane)

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| Create dir | `CreateDir` | `CreateDir` |
| Create file | `CreateFile` | `CreateFile` |
| List directory | `ListDirectoriesAndFiles` | `ListDirectoriesAndFiles` |
| Get properties | `GetDirectoryOrFileProperties` | `GetDirectoryOrFileProperties` |

### Tagging

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| Add tag | `AddTags` | `AddTags` |
| Remove tag | `RemoveTags` | `RemoveTags` |
| Tag resources | `TagResources` | `TagResources` |
| Untag resources | `UntagResources` | `UntagResources` |
| List tag resources | `ListTagResources` | `ListTagResources` |

### Storage Plan

| Goal | API operationId | SDK method |
|------|-----------------|------------|
| List storage plans | `DescribeStoragePackages` | `DescribeStoragePackages` |
| List FS statistics | `DescribeFileSystemStatistics` | `DescribeFileSystemStatistics` |

## Common Request Patterns

### Pagination

Most list operations support `PageNumber` (1-based) and `PageSize` (max 100):

```go
req := &nas.DescribeFileSystemsRequest{
    PageNumber: tea.Int32(1),
    PageSize:   tea.Int32(50),
}
```

### ClientToken (Idempotency)

`CreateFileSystem` accepts a `ClientToken` (≤ 64 ASCII chars) to make retries
safe. The NAS backend deduplicates requests with the same token:

```go
req := &nas.CreateFileSystemRequest{
    // ... other params
    ClientToken: tea.String("my-create-fs-2026-06-04-001"),
}
```

### Mount Target Domain Format

The `MountTargetDomain` follows the pattern:

```
<FileSystemId-without-prefix>.<region>.nas.aliyuncs.com
```

Example: `31a8e42551a44ad496adf****.cn-hangzhou.nas.aliyuncs.com`

Mount commands:

```bash
# NFSv3
mount -t nfs -o vers=3,proto=tcp,nolock,noacl 31a8e4****.cn-hangzhou.nas.aliyuncs.com:/ /mnt/nas

# NFSv4
mount -t nfs -o vers=4,minorversion=1,rsize=1048576,wsize=1048576 31a8e4****.cn-hangzhou.nas.aliyuncs.com:/ /mnt/nas

# SMB
mount -t cifs //31a8e4****.cn-hangzhou.nas.aliyuncs.com/myshare /mnt/smb -o username=myuser,password=***
```

> **Security:** Never put NAS credentials in `ps` history. Use
> `REDISCLI_AUTH`-style env vars or `~/.smbcredentials`.

## Response Envelope

All NAS responses follow the Alibaba Cloud OpenAPI standard envelope:

```json
{
  "RequestId": "B6D17591-B48B-4D31-9CD6-9B9796B2****",
  "HostId": "nas.cn-hangzhou.aliyuncs.com",
  "Code": "Success",
  "Message": "Successful",
  "<OperationSpecificData>": { ... }
}
```

For list operations, `<OperationSpecificData>` is typically an object
containing `TotalCount`, `PageSize`, `PageNumber`, and a list (e.g.,
`FileSystems.FileSystem[]`, `MountTargets.MountTarget[]`,
`AccessGroups.AccessGroup[]`).
