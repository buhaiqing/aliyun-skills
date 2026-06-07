---
name: alicloud-nas-ops
description: >-
  Use when the user needs to manage Alibaba Cloud File Storage NAS — create,
  configure, list, mount, and delete file systems (General-purpose / Extreme /
  CPFS / CPFS SE); manage mount targets, permission groups and rules, access
  points, snapshots and snapshot policies, lifecycle policies, recycle bin,
  LDAP/AD, NFS/SMB ACL, SMB protocol services, filesets, directory quotas,
  data flow tasks, and tags. User mentions NAS, 文件存储, 文件系统, 挂载点,
  权限组, 快照, CPFS, NFS, SMB, 回收站, 访问点, 极速型, 通用型, 容量型,
  性能型 — even without naming the product directly. Not for OSS object storage,
  block storage / EBS disks, HDFS, Content Delivery Network (CDN), or data
  lake analytics.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to
  nas.aliyuncs.com regional endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-04"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: >-
    NAS 2017-06-26 (RPC-style).
    https://help.aliyun.com/zh/nas/developer-reference/api-nas-2017-06-26-overview
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun help nas` — Product NAS (File Storage NAS), Version
    2017-06-26. ~95 core operations are exposed natively, including
    CreateFileSystem / DescribeFileSystems / DeleteFileSystem / CreateMountTarget
    / DescribeMountTargets / CreateAccessGroup / DescribeAccessGroups /
    CreateAccessRule / CreateSnapshot / DescribeSnapshots / CreateLifecyclePolicy
    / DescribeLifecyclePolicies / EnableRecycleBin / DisableAndCleanRecycleBin /
    OpenNASService / DescribeRegions / DescribeZones. Optional dedicated plugin
    `aliyun plugin install --names aliyun-cli-nas` adds NFS/SMB ACL and
    advanced data-flow operations; the agent falls back to JIT Go SDK for any
    gap.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud File Storage NAS Operations Skill

## Overview

**Alibaba Cloud File Storage NAS** is a fully managed, shared, scalable, and
distributed file system accessible over the standard NFS (v3 / v4.1) and SMB
(2.x / 3.x) protocols. It supports four file system families — **General-purpose
NAS (standard)**, **Extreme NAS (extreme)**, **CPFS** (Cloud Parallel File
Storage), and **CPFS SE** — covering everything from web application hot
storage to high-throughput HPC and AI workloads.

This skill is an **operational runbook** for agents: explicit scope, credential
rules, pre-flight checks, **dual-path execution** (official **`aliyun` CLI** as
the primary path, **JIT Go SDK** as the fallback for plugin-required or
advanced operations), response validation, and failure recovery. **Do not use
the web console as the primary agent execution path** in `SKILL.md` or
[阿里云 NAS 控制台](https://nas.console.aliyun.com).

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:**
  - **Primary path:** `aliyun nas <ApiName>` covers ~95 control-plane
    operations (file systems, mount targets, permission groups/rules, snapshots,
    lifecycle policies, recycle bin, filesets, tags, etc.).
  - **Fallback path:** JIT Go SDK (`github.com/alibabacloud-go/nas-20170626/v3/client`)
    for the small set of operations gated by the dedicated
    `aliyun-cli-nas` plugin, or for callers that prefer a programmatic flow.

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT use conditions with precise triggers; explicit delegation to OSS / EBS / RAM / VPC skills |
| 2 | **Structured I/O** | `{{env.*}}` / `{{user.*}}` / `{{output.*}}` placeholders; central JSON-path table |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute (CLI / SDK) → Validate → Recover |
| 4 | **Complete Failure Strategies** | Error taxonomy ≥ 10 product-specific codes (InvalidFileSystem.NotFound, QuotaExceeded, Forbidden.RAM, etc.); HALT vs retry per type |
| 5 | **Absolute Single Responsibility** | One product (NAS), one primary resource (FileSystem + MountTarget + AccessGroup); VPC / RAM / billing delegated |

### Well-Architected Framework Integration

| Pillar | Skill Integration | Reference |
|--------|-------------------|-----------|
| **安全 (Security)** | RAM permission groups (AccessGroup/AccessRule), NFS ACL, SMB ACL/AD, VPC-only mount targets, encryption | `references/well-architected-assessment.md` §2.1 |
| **稳定 (Stability)** | Cross-AZ mount targets, snapshot policies, recycle bin, lifecycle tier-down to IA/Archive, DR via cross-region replication | `references/well-architected-assessment.md` §2.2 |
| **成本 (Cost)** | Storage class (Performance / Capacity / Premium / standard / advance), StoragePackage plans, lifecycle tier-down, directory quota | `references/well-architected-assessment.md` §2.3 |
| **效率 (Efficiency)** | Batch mount-target creation, snapshot policy re-use, fileset operations for CPFS | `references/well-architected-assessment.md` §2.4 |
| **性能 (Performance)** | Extreme NAS tier (100 MB/s/TiB → 1000 MB/s/TiB), CPFS throughput, monitor IOPS/latency via CMS namespace | `references/well-architected-assessment.md` §2.5 |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud NAS" OR "File Storage NAS" OR "文件存储" OR
  "NAS" OR "文件系统" OR "挂载点" OR "权限组" OR "CPFS" OR "通用型NAS" OR
  "容量型NAS" OR "性能型NAS" OR "极速型NAS" OR "NFS" OR "SMB" OR "访问点" OR
  "快照策略" OR "回收站" OR "生命周期策略" OR "Fileset"
- Task involves CRUD or lifecycle operations on **NAS file systems** (create,
  describe, modify, delete, list)
- Task involves **mount targets**: `CreateMountTarget`, `DescribeMountTargets`,
  `DeleteMountTarget`, `ModifyMountTarget`
- Task involves **permission groups and rules**: `CreateAccessGroup`,
  `DescribeAccessGroups`, `ModifyAccessGroup`, `DeleteAccessGroup`,
  `CreateAccessRule`, `DescribeAccessRules`, `ModifyAccessRule`,
  `DeleteAccessRule`
- Task involves **access points**: `CreateAccessPoint`, `DescribeAccessPoints`,
  `ModifyAccessPoint`, `DeleteAccessPoint`
- Task involves **snapshots and policies**: `CreateAutoSnapshotPolicy`,
  `DescribeAutoSnapshotPolicies`, `ApplyAutoSnapshotPolicy`,
  `CreateSnapshot`, `DescribeSnapshots`, `DeleteSnapshot`,
  `ResetFileSystem` (rollback)
- Task involves **lifecycle / data tiering**: `CreateLifecyclePolicy`,
  `DescribeLifecyclePolicies`, `ModifyLifecyclePolicy`,
  `StartLifecyclePolicyExecution`, `StopLifecyclePolicyExecution`
- Task involves **recycle bin**: `EnableRecycleBin`, `GetRecycleBinAttribute`,
  `UpdateRecycleBinAttribute`, `DisableAndCleanRecycleBin`,
  `ListRecentlyRecycledDirectories`, `ListRecycledDirectoriesAndFiles`,
  `CreateRecycleBinRestoreJob`, `CreateRecycleBinDeleteJob`
- Task involves **NFS / SMB ACL**, **SMB protocol services**,
  **LDAP/AD integration** (`EnableNfsAcl`, `DescribeNfsAcl`,
  `EnableSmbAcl`, `DescribeSmbAcl`, `CreateLDAPConfig`,
  `ModifyLDAPConfig`, `CreateProtocolService`, `DescribeProtocolService`,
  `CreateProtocolMountTarget`)
- Task involves **CPFS filesets and data flows**:
  `CreateFileset`, `DescribeFilesets`, `ModifyFileset`, `DeleteFileset`,
  `CreateDataFlow`, `DescribeDataFlows`, `ModifyDataFlow`,
  `StartDataFlow`, `StopDataFlow`
- Task involves **directory quotas** (`SetDirQuota`, `DescribeDirQuotas`,
  `CancelDirQuota`, `SetFilesetQuota`, `CancelFilesetQuota`)
- Task involves **NAS service activation** (`OpenNASService`),
  **region/zone discovery** (`DescribeRegions`, `DescribeZones`), **tag
  management** (`AddTags`, `RemoveTags`, `ListTagResources`,
  `TagResources`, `UntagResources`), **resource group changes**
  (`ChangeResourceGroup`)
- User mentions: mount, 挂载, 文件存储, 快照, 跨可用区, 权限组规则, 目录配额,
  回收站恢复, 文件级快照, IA 存储, 归档存储, lifecycle policy
- User asks to deploy, configure, troubleshoot, or monitor NAS **via API, SDK,
  CLI, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops`
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops`
- Task is about **OSS object storage** (buckets + objects) → delegate to:
  `alicloud-oss-ops`
- Task is about **block storage / EBS disks** (for ECS) → delegate to:
  `alicloud-ecs-ops`
- Task is about **HDFS / Data Lake Analytics** storage backend → use the data
  analytics skill, not raw NAS
- Task is about **CDN edge delivery** (NAS is not a CDN origin by default;
  use OSS + CDN)
- User wants to mount NAS from inside an ApsaraMQ / EMR cluster — those
  clusters mount NAS through their own CSI drivers; this skill exposes the
  control plane only
- User insists on **console-only** flows with no API → state limitation

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Alibaba Cloud AK | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Alibaba Cloud SK | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Default region | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region (e.g., `cn-hangzhou`) | Ask once; reuse |
| `{{user.zone_id}}` | Zone (e.g., `cn-hangzhou-h`) | Ask when creating capacity-bound FS |
| `{{user.protocol_type}}` | `NFS` / `SMB` / `cpfs` | Ask once; validate against `FileSystemType` |
| `{{user.storage_type}}` | `Performance` / `Capacity` / `Premium` / `standard` / `advance` / `advance_100` / `advance_200` / `economic` | Ask once; validate |
| `{{user.file_system_type}}` | `standard` / `extreme` / `cpfs` / `cpfsse` | Ask once; default `standard` |
| `{{user.file_system_id}}` | File system ID (`31a8e4****`, `extreme-****`, `cpfs-****`, `cpfsse-****`) | Ask once; reuse |
| `{{user.mount_target_id}}` | Mount target ID (e.g., `mt-****`) | Ask once; reuse |
| `{{user.access_group_name}}` | Permission group name | Ask once; reuse |
| `{{user.vpc_id}}` | VPC ID | Ask once; cross-check via `alicloud-vpc-ops` |
| `{{user.vswitch_id}}` | vSwitch ID | Ask once; must be in same VPC and zone |
| `{{user.network_type}}` | `Vpc` (only supported value in most regions) | Default `Vpc`; do not invent |
| `{{output.file_system_id}}` | From `CreateFileSystem` response | Parse from `$.FileSystemId` |
| `{{output.mount_target_id}}` | From `CreateMountTarget` response | Parse from `$.MountTargetId` |
| `{{output.mount_target_domain}}` | From `CreateMountTarget` response | Parse from `$.MountTargetDomain` |
| `{{output.snapshot_id}}` | From `CreateSnapshot` response | Parse from `$.SnapshotId` |
| `{{output.request_id}}` | Request ID for support / correlation | Parse from `$.RequestId` |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing.

> **凭据安全（强制）：** 参考
> [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)


## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response
  shapes. Reference:
  `https://help.aliyun.com/zh/nas/developer-reference/api-nas-2017-06-26-overview`
- **Errors:** Map errors to `Code` and `Message` per spec. Common NAS codes:
  - `InvalidFileSystem.NotFound` — File system ID does not exist
  - `InvalidMountTarget.NotFound` — Mount target ID does not exist
  - `InvalidAccessGroup.NotFound` — Permission group does not exist
  - `InvalidParameter` — Missing or malformed parameter
  - `QuotaExceeded` / `FileSystem.QuotaFull` — Account- or instance-level quota exhausted
  - `OperationDenied.FileSystemStatus` — File system is not in a state that allows the operation
  - `Forbidden.RAM` — Caller lacks `nas:*` RAM permission
  - `Throttling` — Rate limit exceeded; exponential backoff required
  - `InsufficientBalance` — Pay-as-you-go NAS requires a positive balance
  - `ServiceNotOpened` — NAS not activated in the region (run `OpenNASService` first)
- **Timestamps:** ISO 8601 strings (e.g., `2026-04-28T10:00:00+08:00`).
- **Idempotency:** `CreateFileSystem` accepts `ClientToken` (≤ 64 ASCII chars)
  for safe retry; `CreateMountTarget` is **non-idempotent** — duplicates return
  `OperationDenied.MountTargetDomainAlreadyExists`. `DeleteFileSystem` and
  `DeleteMountTarget` are idempotent on already-deleted resources.
- **Async behavior:** `CreateFileSystem`, `DeleteFileSystem`,
  `CreateMountTarget`, `DeleteMountTarget` are async. Poll `DescribeFileSystems`
  / `DescribeMountTargets` until terminal state (`Running` / `Stopped` / absent).

### Common Response Field Table (JSON paths verified against OpenAPI 2017-06-26)

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| OpenNASService | `$.OrderId` | string | Order ID for service activation |
| CreateFileSystem | `$.FileSystemId` | string | New file system ID |
| DescribeFileSystems | `$.FileSystems.FileSystem[].FileSystemId` | array | File system IDs |
| DescribeFileSystems | `$.FileSystems.FileSystem[].FileSystemType` | string | `standard` / `extreme` / `cpfs` / `cpfsse` |
| DescribeFileSystems | `$.FileSystems.FileSystem[].Status` | string | `Pending` / `Running` / `Stopped` |
| DescribeFileSystems | `$.FileSystems.FileSystem[].ProtocolType` | string | `NFS` / `SMB` / `cpfs` |
| DescribeFileSystems | `$.FileSystems.FileSystem[].StorageType` | string | `Performance` / `Capacity` / `Premium` / `standard` / `advance` |
| DescribeFileSystems | `$.FileSystems.FileSystem[].MeteredSize` | integer | Used capacity in bytes |
| DescribeFileSystems | `$.TotalCount` / `$.PageSize` / `$.PageNumber` | integer | Pagination metadata |
| DeleteFileSystem | `$.RequestId` | string | Request ID |
| CreateMountTarget | `$.MountTargetDomain` | string | Mount domain (e.g., `31a8e4****.cn-hangzhou.nas.aliyuncs.com`) |
| CreateMountTarget | `$.MountTargetId` | string | Mount target ID (e.g., `mt-****`) |
| DescribeMountTargets | `$.MountTargets.MountTarget[].MountTargetId` | array | Mount target IDs |
| DescribeMountTargets | `$.MountTargets.MountTarget[].MountTargetDomain` | array | Mount domains |
| DescribeMountTargets | `$.MountTargets.MountTarget[].Status` | string | `Pending` / `Active` / `Inactive` / `Deleted` |
| DescribeMountTargets | `$.MountTargets.MountTarget[].VpcId` / `$.MountTargets.MountTarget[].VswId` | string | Bound VPC / vSwitch |
| DeleteMountTarget | `$.RequestId` | string | Request ID |
| CreateAccessGroup | `$.AccessGroupName` | string | New permission group name |
| DescribeAccessGroups | `$.AccessGroups.AccessGroup[].AccessGroupName` | array | Group names |
| CreateAccessRule | `$.AccessRuleId` | string | New rule ID |
| DescribeAccessRules | `$.AccessRules.AccessRule[].AccessRuleId` | array | Rule IDs |
| DescribeAccessRules | `$.AccessRules.AccessRule[].SourceCidrIp` | array | Authorized source CIDR |
| DescribeAccessRules | `$.AccessRules.AccessRule[].RWAccessType` | string | `RDWR` / `RDONLY` |
| DescribeAccessRules | `$.AccessRules.AccessRule[].UserAccessType` | string | `no_squash` / `root_squash` / `all_squash` |
| DescribeAccessRules | `$.AccessRules.AccessRule[].Priority` | integer | 1–100, 1 = highest |
| CreateSnapshot | `$.SnapshotId` | string | New snapshot ID (e.g., `s-****`) |
| DescribeSnapshots | `$.Snapshots.Snapshot[].SnapshotId` | array | Snapshot IDs |
| DescribeSnapshots | `$.Snapshots.Snapshot[].Status` | string | `Progressing` / `Accomplished` / `Failed` |
| CreateAutoSnapshotPolicy | `$.AutoSnapshotPolicyId` | string | New policy ID |
| CreateAccessPoint | `$.AccessPointId` | string | New access point ID |
| DescribeAccessPoints | `$.AccessPoints.AccessPoint[].AccessPointId` | array | Access point IDs |
| CreateLifecyclePolicy | `$.LifecyclePolicyName` | string | New policy name |
| DescribeLifecyclePolicies | `$.LifecyclePolicies.LifecyclePolicy[].LifecyclePolicyName` | array | Policy names |
| GetRecycleBinAttribute | `$.RecycleBinAttribute.RetentionDays` | integer | Retention period (1–180 days) |
| DescribeRegions | `$.Regions.Region[].RegionId` | array | Region IDs |
| DescribeZones | `$.Zones.Zone[].ZoneId` | array | Zone IDs |
| DescribeZones | `$.Zones.Zone[].SupportedFileSystemType` | array | Supported FS types per zone |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateFileSystem | — | `Running` | 10s | 600s |
| DeleteFileSystem | `Running` / `Stopped` | absent | 10s | 300s |
| CreateMountTarget | — | `Active` | 5s | 300s |
| DeleteMountTarget | `Active` | `Deleted` / absent | 5s | 300s |
| CreateSnapshot | — | `Accomplished` | 10s | 1800s |
| ResetFileSystem (rollback) | `Running` | `Running` (rolled back) | 10s | 3600s |
| CreateRecycleBinRestoreJob | — | `Running` → `Success` | 10s | 86400s |

## Quick Start

### What This Skill Does
Manage the full NAS lifecycle: create file systems (4 families), mount targets,
permission groups, access points, snapshots, lifecycle policies, recycle bin,
and CPFS filesets — via `aliyun` CLI (primary) or JIT Go SDK (fallback).

### Prerequisites
- [ ] `aliyun` CLI installed
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`
- [ ] NAS activated in the target region (run `OpenNASService` once if not)

### Verify Setup
```bash
# Check CLI and credentials
aliyun nas DescribeRegions

# Check service activation
aliyun nas DescribeFileSystems --PageSize 1
```

### Your First Command
```bash
# List existing file systems in the current region
aliyun nas DescribeFileSystems --FileSystemType standard --PageSize 10
```

### Next Steps
- [Core Concepts](references/core-concepts.md) — NAS architecture, FS types, mount topology
- [API & SDK Usage](references/api-sdk-usage.md) — All operations, request/response snippets
- [CLI Usage](references/cli-usage.md) — `aliyun nas` command map, coverage table
- [Troubleshooting](references/troubleshooting.md) — Error codes, diagnosis, recovery

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| OpenNASService | Activate NAS in the current region | Low | Low (one-time) |
| CreateFileSystem | Create a new file system | Medium | Medium (creates billed resource) |
| DescribeFileSystems | List / page file systems | Low | None |
| ModifyFileSystem | Update FS description | Low | Low |
| DeleteFileSystem | Delete a file system (irreversible) | Low | **High** |
| CreateMountTarget | Add a mount target (one per zone per FS) | Medium | Medium |
| DescribeMountTargets | List mount targets for a file system | Low | None |
| DeleteMountTarget | Remove a mount target | Low | Medium |
| CreateAccessGroup | Create a permission group | Low | Low |
| CreateAccessRule | Authorize a CIDR for NFS/SMB | Low | Low (security) |
| CreateSnapshot | Create a manual snapshot | Low | Low |
| ResetFileSystem | Roll back a file system to a snapshot | Medium | **High** (data overwrite) |
| CreateAutoSnapshotPolicy | Create a recurring snapshot policy | Low | Low |
| CreateLifecyclePolicy | Create an IA/Archive tiering policy | Low | Low |
| EnableRecycleBin | Enable recycle bin on a file system | Low | Low |
| CreateRecycleBinRestoreJob | Restore deleted data from recycle bin | Low | Low (time-window limited) |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-04 | Initial NAS ops skill: dual-path execution, covering all 4 file system families (General-purpose / Extreme / CPFS / CPFS SE), mount targets, permission groups/rules, access points, snapshots and snapshot policies, lifecycle policies, recycle bin, LDAP/AD, NFS/SMB ACL, SMB protocol services, filesets, directory quotas, data flow tasks, and tags |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI / SDK) → Validate → Recover**. Do
not skip phases.

### Global Pre-flight Checks (Run Before Any NAS Operation)

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI installed | `aliyun version` | Exit code 0 | Document install (`/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"`) |
| Credentials | `test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"` | Both non-empty | HALT; user configures env |
| Region set | `test -n "$ALIBABA_CLOUD_REGION_ID"` | Non-empty | HALT; user sets env |
| NAS service active | `aliyun nas DescribeFileSystems --PageSize 1` | Non-error response | Run `OpenNASService` first |
| Network | `curl -I https://nas.aliyuncs.com` | HTTP 4xx (not timeout) | Warn about network / proxy issues |

### Shared SDK Client Initialization Pattern

All JIT Go SDK examples below assume this shared initialization. Generate this
once per workspace and reuse across operations:

```go
// /tmp/aliyun-sdk-workspace/nas_client.go
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
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("nas." + os.Getenv("ALIBABA_CLOUD_REGION_ID") + ".aliyuncs.com"),
    }
    return nas.NewClient(config)
}

func printResponse(body interface{}) {
    b, _ := json.MarshalIndent(body, "", "  ")
    fmt.Println(string(b))
}

func main() {
    // Operation-specific main logic goes here
}
```

Execute (once per workspace):
```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script 2>/dev/null || true
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/nas-20170626/v3/client
```

> **Note:** `nas-20170626/v3` is the canonical Go SDK package for OpenAPI
> `2017-06-26`. Pin to `v3` in `go.mod` for compatibility.

---

### Operation: Activate NAS Service (OpenNASService)

> **Required first step in any new region.** Calling `CreateFileSystem` in a
> region where NAS has not been activated returns `ServiceNotOpened`.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Region supported | `aliyun nas DescribeRegions` | Current region in `$.Regions.Region[].RegionId` | HALT; user picks a supported region |
| Account active | Caller AK is enabled | — | HALT; user enables AK |

#### Execution — CLI (`aliyun`)

```bash
aliyun nas OpenNASService --RegionId "{{user.region}}"
```

#### Execution — JIT Go SDK

```go
request := &nas.OpenNASServiceRequest{
    RegionId: tea.String("cn-shanghai"),
}
response, err := client.OpenNASService(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Post-execution Validation

- Parse `$.OrderId` — save for support escalation if subsequent operations fail
- Wait 30s, then run `DescribeFileSystems --PageSize 1` to confirm service is ready

#### Failure Recovery

| Error | Recovery |
|-------|----------|
| `Forbidden.RAM` | Add `nas:OpenNASService` to caller RAM policy |
| `InsufficientBalance` | Defer to `alicloud-billing-ops` to recharge |
| `ServiceAlreadyOpened` | Idempotent — proceed with the next operation |

---

### Operation: Create File System (CreateFileSystem)

> **Creates a billed resource.** Confirm with user before execution. Required
> parameters vary by `FileSystemType` — see the parameter matrix below.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| NAS active | `OpenNASService` | Order ID returned | Run `OpenNASService` first |
| Region has zone | `DescribeZones --RegionId {{user.region}}` | Target zone in list | HALT; user picks supported zone |
| Quota | `DescribeFileSystems` → `$.TotalCount` | Less than account quota | HALT; user requests quota raise |
| VPC / vSwitch | `alicloud vpc DescribeVSwitches --VpcId {{user.vpc_id}}` (delegate) | vSwitch exists in target zone | HALT; user creates vSwitch |

#### Parameter Matrix (verified against `aliyun nas CreateFileSystem --help`)

| FileSystemType | Required `ProtocolType` | Required `StorageType` | Notes |
|----------------|-------------------------|------------------------|-------|
| `standard` | `NFS` or `SMB` | `Performance` / `Capacity` / `Premium` | Bandwidth/Capacity auto-selected by tier |
| `extreme` | `NFS` | `standard` or `advance` | Must also pass `Capacity` (GiB) |
| `cpfs` | `cpfs` | `advance_100` / `advance_200` / `economic` | Must also pass `Capacity` (GiB) and `Bandwidth` (MB/s) |
| `cpfsse` | `cpfs` | `advance_100` | Must also pass `Capacity` (GiB) and `Bandwidth` (MB/s) |

#### Execution — CLI (`aliyun`)

```bash
# General-purpose (standard) Performance NAS with NFS
aliyun nas CreateFileSystem \
  --RegionId "{{user.region}}" \
  --FileSystemType "standard" \
  --ProtocolType "NFS" \
  --StorageType "Performance" \
  --Description "My web app shared storage" \
  --ClientToken "$(uuidgen)"

# Extreme NAS (capacity-bound)
aliyun nas CreateFileSystem \
  --RegionId "{{user.region}}" \
  --FileSystemType "extreme" \
  --ProtocolType "NFS" \
  --StorageType "standard" \
  --Capacity 2048 \
  --ClientToken "$(uuidgen)"

# CPFS (high-throughput, HPC/AI)
aliyun nas CreateFileSystem \
  --RegionId "{{user.region}}" \
  --FileSystemType "cpfs" \
  --ProtocolType "cpfs" \
  --StorageType "advance_200" \
  --Capacity 4096 \
  --Bandwidth 2048 \
  --ClientToken "$(uuidgen)"
```

#### Execution — JIT Go SDK

```go
request := &nas.CreateFileSystemRequest{
    RegionId:       tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    FileSystemType: tea.String("standard"),
    ProtocolType:   tea.String("NFS"),
    StorageType:    tea.String("Performance"),
    Description:    tea.String("My web app shared storage"),
    ClientToken:    tea.String(uuid.New().String()),
}
response, err := client.CreateFileSystem(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Post-execution Validation

1. Parse `$.FileSystemId` → `{{output.file_system_id}}`
2. Poll `DescribeFileSystems --FileSystemId <id>` until `$.FileSystems.FileSystem[0].Status == "Running"`:

```bash
# CLI polling
aliyun nas DescribeFileSystems \
  --FileSystemId "{{output.file_system_id}}" \
  --PageSize 1 \
  --output cols=FileSystemId,Status rows=FileSystems.FileSystem[].[FileSystemId,Status]
```

3. Verify `MeteredSize` is present (proves data path is initialized)
4. **Mount target creation is a separate operation** — see next section

#### Failure Recovery

| Error | Recovery |
|-------|----------|
| `InvalidParameter.ProtocolType` / `InvalidParameter.StorageType` | Re-check matrix above; ensure `ProtocolType` matches `FileSystemType` |
| `QuotaExceeded` | HALT; user requests quota raise via console / ticket |
| `ServiceNotOpened` | Run `OpenNASService` first |
| `OperationDenied.FileSystemStatus` | Wait 30s; re-check |
| `Throttling` | Exponential backoff: 1s, 2s, 4s, 8s |

---

### Operation: Create Mount Target (CreateMountTarget)

> Mount targets bind a file system to a specific VPC + vSwitch + access group.
> A file system can have multiple mount targets (e.g., one per VPC).

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| File system exists and `Running` | `DescribeFileSystems` | `Status == "Running"` | HALT; wait or check `OperationDenied` |
| VPC / vSwitch exist | Delegate to `alicloud-vpc-ops` | VpcId and VswId exist in same region and zone | HALT; user creates them |
| Access group exists | `DescribeAccessGroups --AccessGroupName {{user.access_group_name}}` | Group found | Run `CreateAccessGroup` first |
| No duplicate | `DescribeMountTargets --FileSystemId {{user.file_system_id}} --VpcId {{user.vpc_id}} --VswId {{user.vswitch_id}}` | Empty / not `Active` | Skip or delete existing first |

#### Execution — CLI (`aliyun`)

```bash
aliyun nas CreateMountTarget \
  --FileSystemId "{{user.file_system_id}}" \
  --AccessGroupName "{{user.access_group_name}}" \
  --VpcId "{{user.vpc_id}}" \
  --VswId "{{user.vswitch_id}}" \
  --NetworkType "Vpc" \
  --Description "Mount for web app VPC"
```

#### Execution — JIT Go SDK

```go
request := &nas.CreateMountTargetRequest{
    FileSystemId:    tea.String(os.Getenv("FILE_SYSTEM_ID")),
    AccessGroupName: tea.String(os.Getenv("ACCESS_GROUP_NAME")),
    VpcId:           tea.String(os.Getenv("VPC_ID")),
    VswId:           tea.String(os.Getenv("VSWITCH_ID")),
    NetworkType:     tea.String("Vpc"),
}
response, err := client.CreateMountTarget(request)
if err != nil {
    panic(err)
}
printResponse(response.Body)
```

#### Post-execution Validation

1. Parse `$.MountTargetDomain` → mount address (e.g., `31a8e4****.cn-hangzhou.nas.aliyuncs.com`)
2. Parse `$.MountTargetId` → `{{output.mount_target_id}}`
3. Poll `DescribeMountTargets` until `$.MountTargets.MountTarget[0].Status == "Active"`
4. Present the mount command to the user (Linux):
   ```bash
   sudo mount -t nfs <MountTargetDomain>:/ /mnt/nas
   ```

#### Failure Recovery

| Error | Recovery |
|-------|----------|
| `InvalidFileSystem.NotFound` | Verify `FileSystemId`; rerun `DescribeFileSystems` to list |
| `InvalidVSwitchId.NotFound` | Delegate to `alicloud-vpc-ops` to verify vSwitch |
| `OperationDenied.MountTargetDomainAlreadyExists` | Mount target already exists for this FS+VPC+vSwitch; **non-idempotent** — re-use existing |
| `OperationDenied.FileSystemStatus` | Wait for `Running` |
| `Forbidden.RAM` | Add `nas:CreateMountTarget` to caller RAM policy |

---

### Operation: Create Access Group & Rule

> The default `DEFAULT_VPC_GROUP_NAME` allows `0.0.0.0/0` with `RDWR` and
> `root_squash`. **Always create a dedicated group with restricted CIDR for
> production file systems.**

#### CLI — Create Group

```bash
aliyun nas CreateAccessGroup \
  --AccessGroupName "{{user.access_group_name}}" \
  --AccessGroupType "Vpc" \
  --Description "Web app NFS access group"
```

#### CLI — Add Rule (authorize CIDR)

```bash
aliyun nas CreateAccessRule \
  --AccessGroupName "{{user.access_group_name}}" \
  --SourceCidrIp "10.0.0.0/8" \
  --RWAccessType "RDWR" \
  --UserAccessType "root_squash" \
  --Priority 1
```

> **Quota:** 20 access groups per region; 300 rules per group. `CreateAccessRule`
> priorities 1–100 (1 = highest). Newer rules override older ones at the same
> priority. See [references/cli-usage.md](references/cli-usage.md) for batch
> patterns.

#### Failure Recovery

| Error | Recovery |
|-------|----------|
| `InvalidAccessGroup.Duplicate` | Pick a different group name |
| `QuotaExceeded.AccessGroup` | Delete unused groups or request raise |
| `InvalidParameter.Priority` | Use 1–100 |
| `InvalidParameter.UserAccessType` | Valid: `no_squash`, `root_squash`, `all_squash` |
| `InvalidParameter.RWAccessType` | Valid: `RDONLY`, `RDWR` |

---

### Operation: Create Snapshot (CreateSnapshot)

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| File system exists | `DescribeFileSystems` | Found and `Running` | HALT |
| Snapshot quota | `DescribeSnapshots --FileSystemId <id>` → count | < quota | HALT; user deletes old snapshots |
| Retention understood | Snapshots are billable; user confirmed | Yes | HALT if user declines |

#### Execution — CLI (`aliyun`)

```bash
aliyun nas CreateSnapshot \
  --FileSystemId "{{user.file_system_id}}" \
  --SnapshotName "pre-upgrade-$(date +%Y%m%d-%H%M%S)" \
  --Description "Snapshot before ECS upgrade" \
  --RetentionDays 30
```

#### Post-execution Validation

1. Parse `$.SnapshotId` → `{{output.snapshot_id}}`
2. Poll `DescribeSnapshots --SnapshotId <id>` until
   `$.Snapshots.Snapshot[0].Status == "Accomplished"`:

```bash
aliyun nas DescribeSnapshots \
  --SnapshotId "{{output.snapshot_id}}" \
  --output cols=SnapshotId,Status,SourceFileSystemId,Progress \
         rows=Snapshots.Snapshot[].[SnapshotId,Status,SourceFileSystemId,Progress]
```

#### Failure Recovery

| Error | Recovery |
|-------|----------|
| `OperationDenied.FileSystemStatus` | Wait for `Running`; retry |
| `QuotaExceeded.Snapshot` | Delete old snapshots; raise quota via ticket |
| `Throttling` | Exponential backoff |

---

### Operation: Rollback File System to Snapshot (ResetFileSystem)

> **CRITICAL — DESTRUCTIVE.** Resets the file system to the state of an
> existing snapshot. **All data written after the snapshot is lost.**

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: `Reset file system {{user.file_system_id}} to snapshot {{user.snapshot_id}}`
- **MUST** warn user: post-snapshot data is unrecoverable unless in recycle bin
- **SHOULD** create a fresh snapshot of the current state first (best practice)

#### Execution — CLI (`aliyun`)

```bash
aliyun nas ResetFileSystem \
  --FileSystemId "{{user.file_system_id}}" \
  --SnapshotId "{{user.snapshot_id}}"
```

#### Post-execution Validation

1. Poll `DescribeFileSystems --FileSystemId <id>` until `Status == "Running"`
2. Mount via the existing mount target and verify data integrity (manual / app-level)

#### Failure Recovery

| Error | Recovery |
|-------|----------|
| `InvalidSnapshot.NotFound` | Verify `SnapshotId` with `DescribeSnapshots` |
| `OperationDenied.FileSystemStatus` | File system mid-state; wait |
| `OperationDenied.ResetDuringWrite` | Stop app traffic, retry |

---

### Operation: Enable Recycle Bin (EnableRecycleBin)

> Recycle bin retains deleted data for 1–180 days, allowing recovery via
> `CreateRecycleBinRestoreJob`. **Strongly recommended before any destructive
> operation.** Only supported on `standard` (General-purpose) NAS.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| File system type | `DescribeFileSystems` | `FileSystemType == "standard"` | HALT; recycle bin is General-purpose NAS only |
| File system exists | `DescribeFileSystems` | Found | HALT |

#### Execution — CLI (`aliyun`)

```bash
aliyun nas EnableRecycleBin \
  --FileSystemId "{{user.file_system_id}}" \
  --RetentionDays 14
```

#### Post-execution Validation

- Call `GetRecycleBinAttribute --FileSystemId <id>` to confirm `Enabled == true`
  and `RetentionDays` is set

---

### Operation: Restore from Recycle Bin (CreateRecycleBinRestoreJob)

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Recycle bin enabled | `GetRecycleBinAttribute` | `Enabled == true` | Run `EnableRecycleBin` first |
| Item in recycle bin | `ListRecentlyRecycledDirectories --FileSystemId <id>` | Target path found | HALT; not in bin or expired |

#### Execution — CLI (`aliyun`)

```bash
aliyun nas CreateRecycleBinRestoreJob \
  --FileSystemId "{{user.file_system_id}}" \
  --SourcePath "/old/deleted/path" \
  --TargetPath "/restored/path"
```

#### Post-execution Validation

- Poll `ListRecycleBinJobs` until job status is `Success`
- Verify the restored path is mountable and contains the expected data

---

### Operation: Delete File System (DeleteFileSystem)

> **CRITICAL — IRREVERSIBLE.** Deletes the file system and all mount targets.
> Data written via `rm` is recoverable from the recycle bin if enabled;
> data deleted via `DeleteFileSystem` itself is **NOT** recoverable.

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation with the file system ID
- **MUST** verify no production traffic is using any mount targets
- **SHOULD** create a final snapshot before deletion
- **SHOULD** delete all mount targets first (or after — they auto-delete with the FS)
- **MUST** remove the file system from any cross-region DR / HBR replication
  plan via `alicloud-hbr-ops` first

#### Execution — CLI (`aliyun`)

```bash
# Optional: list current mount targets
aliyun nas DescribeMountTargets --FileSystemId "{{user.file_system_id}}"

# Delete the file system
aliyun nas DeleteFileSystem --FileSystemId "{{user.file_system_id}}"
```

#### Post-execution Validation

- Poll `DescribeFileSystems --FileSystemId <id>` until the API returns
  `InvalidFileSystem.NotFound` (gone) within 300s
- Re-list with `DescribeFileSystems --PageSize 100` and confirm absence

#### Failure Recovery

| Error | Recovery |
|-------|----------|
| `InvalidFileSystem.NotFound` | Already deleted; idempotent success |
| `OperationDenied.FileSystemStatus` | File system is mid-state (e.g., creating); wait |
| `OperationDenied.HasMountTargets` | List mount targets; delete them first, then retry |
| `OperationDenied.HasActiveBackupPlan` | Remove from HBR/SMS plan via `alicloud-hbr-ops` first |
| `Throttling` | Exponential backoff |

---

## Prerequisites

1. **Install `aliyun` CLI** (primary execution path — static Go binary, no runtime dependencies):

   ```bash
   # Official installer (auto-detects OS and architecture)
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"

   # Or Homebrew (macOS)
   brew install aliyun-cli
   ```

2. **(Optional) Install the dedicated NAS plugin** for advanced operations
   (NFS ACL, SMB ACL, AD integration, data flow subtasks):

   ```bash
   aliyun plugin install --names aliyun-cli-nas
   ```

3. **Bootstrap Go runtime** (for JIT SDK fallback — only needed if CLI does not support operation):

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

4. **Configure Credentials** — Environment variables (recommended for Agent execution):

   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```

5. **Activate NAS** in the target region (one-time per region):

   ```bash
   aliyun nas OpenNASService --RegionId "{{user.region}}"
   ```

6. **Verify Configuration**:

   ```bash
   aliyun nas DescribeRegions
   ```

> **Security:** Never commit `.env` to version control (already in `.gitignore`).
> All credentials use `{{env.*}}` placeholders in generated Skills — never real
> values.

## Reference Directory

- [Core Concepts](references/core-concepts.md) — NAS architecture, FS types, mount topology
- [API & SDK Usage](references/api-sdk-usage.md) — All operations, request/response snippets
- [CLI Usage](references/cli-usage.md) — `aliyun nas` command map, coverage table
- [Troubleshooting Guide](references/troubleshooting.md) — Error codes, diagnosis, recovery
- [Monitoring & Alerts](references/monitoring.md) — CMS metrics, dashboards
- [Integration](references/integration.md) — JIT SDK setup, env vars, cross-skill delegation
- [Well-Architected Assessment](references/well-architected-assessment.md) — five-pillar integration
- [User Experience Specification](../alicloud-skill-generator/references/user-experience-spec.md) — mandatory UX compliance

## Operational Best Practices

- **Least privilege:** RAM policies scoped to `nas:*` only; access groups
  restrict by source CIDR; SMB ACL further restricts by AD user.
- **Availability:** Multi-AZ via separate mount targets per zone; HA on the
  application side via NFS round-robin DNS or SMB witness.
- **Cost:** Use `Capacity` storage for cold data; enable lifecycle policies
  to tier down to IA/Archive automatically; purchase `StoragePackage` for
  steady-state workloads.
- **Backup:** Always enable a snapshot policy and recycle bin BEFORE any
  destructive operation.
- **Security:** Replace the default `DEFAULT_VPC_GROUP_NAME` permission
  group with a dedicated, CIDR-restricted group in production.

## Token Efficiency Guidelines (P0 — 强制)

This skill follows the six TE rules defined in
`alicloud-skill-generator/SKILL.md` §Token Efficiency Requirements:

- **TE-1:** Use `DescribeZones` and `DescribeRegions` to discover
  supported types instead of hardcoding.
- **TE-2:** No docstrings in code snippets; inline comments only.
- **TE-3:** Compact error tables (one row per error code).
- **TE-4:** JSON paths centralized in the `Common Response Field Table`
  near the top of this file.
- **TE-5:** YAML anchors in `assets/example-config.yaml`.
- **TE-6:** No duplication between SKILL.md and reference files; references
  add depth, not repetition.

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.
