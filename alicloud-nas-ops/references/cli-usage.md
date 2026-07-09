# NAS CLI Usage

## Install

```bash
# Official installer
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"

# Verify
aliyun version
```

**NAS-specific plugin** (optional — adds NFS/SMB ACL, LDAP/AD, protocol
service, dataflow subtasks):

```bash
aliyun plugin install --names aliyun-cli-nas
aliyun plugin list
```

## Conventions (agent execution)

- **Output is JSON by default** — NO `--output json` needed for plain JSON.
- **Use `--output cols=...,rows=...`** for JMESPath tabular extraction:

  ```bash
  aliyun nas DescribeFileSystems --PageSize 5 \
    --output cols=FileSystemId,Status,StorageType,MeteredSize \
           rows=FileSystems.FileSystem[].[FileSystemId,Status,StorageType,MeteredSize]
  ```

- **`--no-interactive` does NOT exist** in `aliyun` CLI — all commands are
  non-interactive by default.
- **Credentials are read from** `ALIBABA_CLOUD_ACCESS_KEY_ID` /
  `ALIBABA_CLOUD_ACCESS_KEY_SECRET` env vars, or `~/.aliyun/config.json`.
- **Region** is read from `ALIBABA_CLOUD_REGION_ID` env var; alternatively
  pass `--RegionId <region>` per command.

## Command Map (Quick Reference)

### Activation & Discovery

| Goal | Command |
|------|---------|
| Activate NAS in region | `aliyun nas OpenNASService --RegionId <region>` |
| List supported regions | `aliyun nas DescribeRegions` |
| List zones (per region) | `aliyun nas DescribeZones --RegionId <region>` |
| Check storage plans | `aliyun nas DescribeStoragePackages` |
| List FS statistics | `aliyun nas DescribeFileSystemStatistics` |

### File System

| Goal | Command |
|------|---------|
| Create standard NAS | `aliyun nas CreateFileSystem --FileSystemType standard --ProtocolType NFS --StorageType Performance --ClientToken "$(uuidgen)"` |
| Create Extreme NAS | `aliyun nas CreateFileSystem --FileSystemType extreme --ProtocolType NFS --StorageType advance --Capacity 2048 --ClientToken "$(uuidgen)"` |
| Create CPFS | `aliyun nas CreateFileSystem --FileSystemType cpfs --ProtocolType cpfs --StorageType advance_200 --Capacity 4096 --Bandwidth 2048 --ClientToken "$(uuidgen)"` |
| List file systems | `aliyun nas DescribeFileSystems --PageSize 50` |
| List by type | `aliyun nas DescribeFileSystems --FileSystemType standard` |
| Get one FS | `aliyun nas DescribeFileSystems --FileSystemId <id>` |
| Modify description | `aliyun nas ModifyFileSystem --FileSystemId <id> --Description "new desc"` |
| Upgrade FS | `aliyun nas UpgradeFileSystem --FileSystemId <id> --<upgrade-params>` |
| Delete FS | `aliyun nas DeleteFileSystem --FileSystemId <id>` |
| Roll back to snapshot | `aliyun nas ResetFileSystem --FileSystemId <id> --SnapshotId <snap-id>` |
| Change resource group | `aliyun nas ChangeResourceGroup --ResourceId <id> --ResourceType FileSystem --NewResourceGroupId <rg-id>` |

### Mount Target

| Goal | Command |
|------|---------|
| Create mount target | `aliyun nas CreateMountTarget --FileSystemId <id> --AccessGroupName <name> --VpcId <vpc> --VswId <vsw> --NetworkType Vpc` |
| List mount targets | `aliyun nas DescribeMountTargets --FileSystemId <id>` |
| Get one mount target | `aliyun nas DescribeMountTargets --FileSystemId <id> --MountTargetId <mt-id>` |
| Modify mount target | `aliyun nas ModifyMountTarget --FileSystemId <id> --MountTargetId <mt-id> --AccessGroupName <name>` |
| Delete mount target | `aliyun nas DeleteMountTarget --FileSystemId <id> --MountTargetId <mt-id>` |
| List mounted clients | `aliyun nas DescribeMountedClients --FileSystemId <id>` |

### Permission (AccessGroup / Rule)

| Goal | Command |
|------|---------|
| Create access group | `aliyun nas CreateAccessGroup --AccessGroupName <name> --AccessGroupType Vpc` |
| List access groups | `aliyun nas DescribeAccessGroups` |
| Modify access group | `aliyun nas ModifyAccessGroup --AccessGroupName <name> --Description "..."` |
| Delete access group | `aliyun nas DeleteAccessGroup --AccessGroupName <name>` |
| Add access rule | `aliyun nas CreateAccessRule --AccessGroupName <name> --SourceCidrIp "10.0.0.0/8" --RWAccessType RDWR --UserAccessType root_squash --Priority 1` |
| List access rules | `aliyun nas DescribeAccessRules --AccessGroupName <name>` |
| Modify access rule | `aliyun nas ModifyAccessRule --AccessGroupName <name> --AccessRuleId <id> --SourceCidrIp "10.0.0.0/8"` |
| Delete access rule | `aliyun nas DeleteAccessRule --AccessGroupName <name> --AccessRuleId <id>` |

### Access Point

| Goal | Command |
|------|---------|
| Create access point | `aliyun nas CreateAccessPoint --FileSystemId <id> --AccessGroupName <name> --VpcId <vpc> --VswId <vsw> --Path "/data"` |
| List access points | `aliyun nas DescribeAccessPoints --FileSystemId <id>` |
| Get access point | `aliyun nas DescribeAccessPoint --AccessPointId <ap-id>` |
| Modify access point | `aliyun nas ModifyAccessPoint --AccessPointId <ap-id> --Path "/newpath"` |
| Delete access point | `aliyun nas DeleteAccessPoint --AccessPointId <ap-id>` |

### Snapshot

| Goal | Command |
|------|---------|
| Create snapshot | `aliyun nas CreateSnapshot --FileSystemId <id> --SnapshotName "name" --RetentionDays 30` |
| List snapshots | `aliyun nas DescribeSnapshots --FileSystemId <id>` |
| Delete snapshot | `aliyun nas DeleteSnapshot --SnapshotId <id>` |
| Create auto-snapshot policy | `aliyun nas CreateAutoSnapshotPolicy --PolicyName "name" --RepeatWeekdays "1,2,3,4,5,6,7" --TimePoints "3" --RetentionDays 7` |
| List auto-snapshot policies | `aliyun nas DescribeAutoSnapshotPolicies` |
| Modify auto-snapshot policy | `aliyun nas ModifyAutoSnapshotPolicy --AutoSnapshotPolicyId <id> --<param> <value>` |
| Delete auto-snapshot policy | `aliyun nas DeleteAutoSnapshotPolicy --AutoSnapshotPolicyId <id>` |
| Apply policy to FS | `aliyun nas ApplyAutoSnapshotPolicy --AutoSnapshotPolicyId <id> --FileSystemIds "[\"<id>\"]"` |
| Cancel policy on FS | `aliyun nas CancelAutoSnapshotPolicy --AutoSnapshotPolicyId <id> --FileSystemIds "[\"<id>\"]"` |
| List auto-snapshot tasks | `aliyun nas DescribeAutoSnapshotTasks --FileSystemId <id>` |

### Lifecycle Policy

| Goal | Command |
|------|---------|
| Create lifecycle policy | `aliyun nas CreateLifecyclePolicy --FileSystemId <id> --LifecyclePolicyName "name" --LifecycleRuleConfig '<json>'` |
| List lifecycle policies | `aliyun nas DescribeLifecyclePolicies --FileSystemId <id>` |
| Modify lifecycle policy | `aliyun nas ModifyLifecyclePolicy --FileSystemId <id> --LifecyclePolicyName "name" --LifecycleRuleConfig '<json>'` |
| Update lifecycle policy | `aliyun nas UpdateLifecyclePolicy --FileSystemId <id> --LifecyclePolicyName "name"` |
| Delete lifecycle policy | `aliyun nas DeleteLifecyclePolicy --FileSystemId <id> --LifecyclePolicyName "name"` |
| Start execution | `aliyun nas StartLifecyclePolicyExecution --FileSystemId <id> --LifecyclePolicyName "name"` |
| Stop execution | `aliyun nas StopLifecyclePolicyExecution --FileSystemId <id> --LifecyclePolicyName "name"` |
| Create retrieve job | `aliyun nas CreateLifecycleRetrieveJob --FileSystemId <id> --Path "/archive/oldfile"` |
| List retrieve jobs | `aliyun nas ListLifecycleRetrieveJobs --FileSystemId <id>` |
| Cancel retrieve job | `aliyun nas CancelLifecycleRetrieveJob --JobId <job-id>` |
| Retry retrieve job | `aliyun nas RetryLifecycleRetrieveJob --JobId <job-id>` |

### Recycle Bin (standard NAS only)

| Goal | Command |
|------|---------|
| Enable recycle bin | `aliyun nas EnableRecycleBin --FileSystemId <id> --RetentionDays 14` |
| Get attribute | `aliyun nas GetRecycleBinAttribute --FileSystemId <id>` |
| Update retention | `aliyun nas UpdateRecycleBinAttribute --FileSystemId <id> --RetentionDays 30` |
| Disable + clean | `aliyun nas DisableAndCleanRecycleBin --FileSystemId <id>` |
| List recently recycled dirs | `aliyun nas ListRecentlyRecycledDirectories --FileSystemId <id>` |
| List recycled files | `aliyun nas ListRecycledDirectoriesAndFiles --FileSystemId <id> --Path "/old"` |
| Create restore job | `aliyun nas CreateRecycleBinRestoreJob --FileSystemId <id> --SourcePath "/old" --TargetPath "/new"` |
| Create delete job | `aliyun nas CreateRecycleBinDeleteJob --FileSystemId <id> --SourcePath "/old"` |
| List recycle jobs | `aliyun nas ListRecycleBinJobs --FileSystemId <id>` |
| Cancel recycle job | `aliyun nas CancelRecycleBinJob --JobId <job-id>` |

### ACL (NFS / SMB) — Plugin Required

| Goal | Command |
|------|---------|
| Enable NFS ACL | `aliyun nas EnableNfsAcl --FileSystemId <id>` |
| Disable NFS ACL | `aliyun nas DisableNfsAcl --FileSystemId <id>` |
| Describe NFS ACL | `aliyun nas DescribeNfsAcl --FileSystemId <id>` |
| Enable SMB ACL | `aliyun nas EnableSmbAcl --FileSystemId <id>` |
| Disable SMB ACL | `aliyun nas DisableSmbAcl --FileSystemId <id>` |
| Describe SMB ACL | `aliyun nas DescribeSmbAcl --FileSystemId <id>` |
| Modify SMB ACL | `aliyun nas ModifySmbAcl --FileSystemId <id> --<smb-acl-params>` |
| Create LDAP config | `aliyun nas CreateLDAPConfig --FileSystemId <id> --<ldap-params>` |
| Modify LDAP config | `aliyun nas ModifyLDAPConfig --FileSystemId <id> --<ldap-params>` |
| Delete LDAP config | `aliyun nas DeleteLDAPConfig --FileSystemId <id>` |

### SMB Protocol Service (Plugin Required)

| Goal | Command |
|------|---------|
| Create protocol service | `aliyun nas CreateProtocolService --FileSystemId <id> --ProtocolType SMB --<smb-params>` |
| Describe protocol service | `aliyun nas DescribeProtocolService --FileSystemId <id>` |
| Modify protocol service | `aliyun nas ModifyProtocolService --FileSystemId <id> --Description "..."` |
| Delete protocol service | `aliyun nas DeleteProtocolService --FileSystemId <id>` |
| Create protocol mount target | `aliyun nas CreateProtocolMountTarget --FileSystemId <id> --VpcId <vpc> --VswId <vsw> --<protocol-mt-params>` |
| Describe protocol mount target | `aliyun nas DescribeProtocolMountTarget --FileSystemId <id>` |
| Get protocol mount target | `aliyun nas GetProtocolMountTarget --FileSystemId <id>` |
| Modify protocol mount target | `aliyun nas ModifyProtocolMountTarget --FileSystemId <id> --Description "..."` |
| Delete protocol mount target | `aliyun nas DeleteProtocolMountTarget --FileSystemId <id>` |

### Filesets (CPFS / CPFS SE only)

| Goal | Command |
|------|---------|
| Create fileset | `aliyun nas CreateFileset --FileSystemId <id> --FilesetName "name" --Path "/data"` |
| Get fileset | `aliyun nas GetFileset --FileSystemId <id> --FilesetId <id>` |
| List filesets | `aliyun nas DescribeFilesets --FileSystemId <id>` |
| Modify fileset | `aliyun nas ModifyFileset --FileSystemId <id> --FilesetId <id> --<param> <value>` |
| Delete fileset | `aliyun nas DeleteFileset --FileSystemId <id> --FilesetId <id>` |
| Set fileset quota | `aliyun nas SetFilesetQuota --FileSystemId <id> --FilesetId <id> --<quota-params>` |
| Cancel fileset quota | `aliyun nas CancelFilesetQuota --FileSystemId <id> --FilesetId <id>` |

### Data Flow (CPFS only)

| Goal | Command |
|------|---------|
| Create dataflow | `aliyun nas CreateDataFlow --FileSystemId <id> --<dataflow-params>` |
| List dataflows | `aliyun nas DescribeDataFlows --FileSystemId <id>` |
| Modify dataflow | `aliyun nas ModifyDataFlow --FileSystemId <id> --DataFlowId <id> --<param> <value>` |
| Delete dataflow | `aliyun nas DeleteDataFlow --FileSystemId <id> --DataFlowId <id>` |
| Start dataflow | `aliyun nas StartDataFlow --FileSystemId <id> --DataFlowId <id>` |
| Stop dataflow | `aliyun nas StopDataFlow --FileSystemId <id> --DataFlowId <id>` |
| Create dataflow task | `aliyun nas CreateDataFlowTask --FileSystemId <id> --<task-params>` |
| List dataflow tasks | `aliyun nas DescribeDataFlowTasks --FileSystemId <id>` |
| Cancel dataflow task | `aliyun nas CancelDataFlowTask --FileSystemId <id> --TaskId <id>` |

### Directory Quota (standard NAS)

| Goal | Command |
|------|---------|
| Set dir quota | `aliyun nas SetDirQuota --FileSystemId <id> --Path "/data" --<quota-params>` |
| List dir quotas | `aliyun nas DescribeDirQuotas --FileSystemId <id>` |
| Cancel dir quota | `aliyun nas CancelDirQuota --FileSystemId <id> --Path "/data"` |

### Tagging

| Goal | Command |
|------|---------|
| Add tag (legacy) | `aliyun nas AddTags --FileSystemId <id> --Tag.1.Key env --Tag.1.Value prod` |
| Remove tag (legacy) | `aliyun nas RemoveTags --FileSystemId <id> --Tag.1.Key env` |
| Tag resources | `aliyun nas TagResources --ResourceId.1 <id> --ResourceType FileSystem --Tag.1.Key env --Tag.1.Value prod` |
| Untag resources | `aliyun nas UntagResources --ResourceId.1 <id> --ResourceType FileSystem --TagKey.1 env` |
| List tag resources | `aliyun nas ListTagResources --ResourceId.1 <id> --ResourceType FileSystem` |

## CLI vs API Coverage

| Operation Category | CLI Coverage | Plugin-Required? | Notes |
|--------------------|--------------|------------------|-------|
| Service activation, regions, zones | ✅ Full | No | |
| File system CRUD | ✅ Full | No | |
| Mount targets | ✅ Full | No | |
| Access groups & rules | ✅ Full | No | |
| Access points | ✅ Full | No | |
| Snapshots & policies | ✅ Full | No | |
| Lifecycle | ✅ Full | No | |
| Recycle bin | ✅ Full | No | |
| Tagging | ✅ Full | No | |
| **NFS ACL** | ✅ Full | **Yes** | |
| **SMB ACL** | ✅ Full | **Yes** | |
| **LDAP/AD** | ✅ Full | **Yes** | |
| **SMB protocol service** | ✅ Full | **Yes** | |
| Filesets (CPFS) | ✅ Full | No | |
| Data flows (CPFS) | ✅ Full | **Yes** | Dataflow subtasks |
| Directory quotas | ✅ Full | No | |
| File-level data plane | ⚠️ Partial | No | `CreateDir`, `ListDirectoriesAndFiles` exposed; full data plane via NFS/SMB protocol |
| Cross-region replication | ❌ No | — | Use HBR (`alicloud-hbr-ops`) for DR |

> **Bottom line:** ~95% of NAS control-plane operations are available via
> `aliyun` CLI. **The agent rarely needs the JIT Go SDK fallback.** The few
> gaps are covered by the dedicated `aliyun-cli-nas` plugin.

## Polling Patterns

### Wait for File System `Running`

```bash
# Bash polling loop
for i in $(seq 1 60); do
  STATUS=$(aliyun nas DescribeFileSystems --FileSystemId <id> --PageSize 1 | jq -r '.FileSystems.FileSystem[0].Status')
  echo "[$i] status=$STATUS"
  [ "$STATUS" = "Running" ] && break
  sleep 10
done
```

### Wait for Mount Target `Active`

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun nas DescribeMountTargets --FileSystemId <id> --MountTargetId <mt-id> | jq -r '.MountTargets.MountTarget[0].Status')
  echo "[$i] status=$STATUS"
  [ "$STATUS" = "Active" ] && break
  sleep 5
done
```

### Wait for Snapshot `Accomplished`

```bash
for i in $(seq 1 180); do
  STATUS=$(aliyun nas DescribeSnapshots --SnapshotId <id> | jq -r '.Snapshots.Snapshot[0].Status')
  PROGRESS=$(aliyun nas DescribeSnapshots --SnapshotId <id> | jq -r '.Snapshots.Snapshot[0].Progress')
  echo "[$i] status=$STATUS progress=$PROGRESS"
  [ "$STATUS" = "Accomplished" ] && break
  [ "$STATUS" = "Failed" ] && { echo "snapshot failed"; exit 1; }
  sleep 10
done
```
