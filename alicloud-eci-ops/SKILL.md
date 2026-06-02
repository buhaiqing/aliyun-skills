---
name: alicloud-eci-ops
description: >-
  Use this skill when the user needs to create, manage, or troubleshoot Alibaba
  Cloud Elastic Container Instances (ECI) directly — tasks like "create an ECI",
  "run a batch job on ECI", "query ECI quota", "delete a ContainerGroup",
  "在 ECI 上跑任务", "弹性容器实例", "按 vCPU 秒计费容器" — even when the user
  doesn't name ECI explicitly but describes one-off containers or short-lived
  workloads. Catches lifecycle of ContainerGroups, ECI quota pre-flight
  (via `ListUsage`), exec into running containers, and ECI-level monitoring.
  Does NOT handle ASK cluster lifecycle — that is in
  `alicloud-ack-serverless-ops`. Does NOT handle ECS instances, ACK
  worker-node clusters, or container image building.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+
  runtime (for JIT SDK fallback), valid API credentials, network access to
  Alibaba Cloud ECI endpoints.
metadata:
  author: alicloud
  version: "1.1.0"
  last_updated: "2026-06-02"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "ECI-2018-08-08 / https://www.alibabacloud.com/help/en/eci"
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun help eci`. The `eci` product exposes 30+ operations
    including CreateContainerGroup, DescribeContainerGroups, DeleteContainerGroup,
    ExecContainerCommand, ListUsage (quota), DescribeContainerGroupMetric,
    RestartContainerGroup, DescribeAvailableResource, CreateImageCache,
    CreateDataCache, CreateVirtualNode. Most fields verified via
    `https://api.aliyun.com/meta/v1/products/ECI/versions/2018-08-08/api-docs.json`.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

# Alibaba Cloud ECI (Elastic Container Instance) Operations Skill

## ✅ OpenAPI 验证状态 (VERIFIED 2026-06-02)

> **Status: 已通过** `https://api.aliyun.com/meta/v1/products/ECI/versions/2018-08-08/api-docs.json`
> + `aliyun eci <Op> --help` + `aliyun help eci` 验证。
> 详见 [`references/openapi-verify-checklist.md`](references/openapi-verify-checklist.md)
> 和 [`references/api-sdk-usage.md`](references/api-sdk-usage.md)。
>
> **重大修正（修正训练知识错误）：**
> - ⚠️ **配额命令是 `ListUsage`**，不是 `DescribeContainerGroupQuota`（后者不存在）
> - **CPU pinning** 字段是 `CpuOptionsCore` + `CpuOptionsThreadsPerCore`（不是 `CpuOptions`）
> - **`ImageRegistryCredential`** 形状是 `{Server, UserName, Password}`（注意 `UserName` 不是 `Username`）
> - **`ExecContainerCommand`** 的 `--Command` 必须是 **JSON 数组**（不是字符串）
> - **`RestartPolicy` 默认是 `Always`**，**永远要确认**（误用 = 无限计费）
> - **支持 `InstanceType`**：可指定 ECS 规格（如 `ecs.c5.xlarge`）
> - **支持 `InitContainer`**（init 容器数组，K8s 风格）
> - **支持 Spot**（`SpotStrategy` / `SpotPriceLimit` / `SpotDuration` / `StrictSpot`）
> - **支持 EIP**（`EipInstanceId` / `AutoCreateEip` / `EipBandwidth` / `EipISP`）
> - **支持 IPv6**（`Ipv6AddressCount` / `Ipv6GatewayBandwidth`）
> - **支持镜像缓存**（`ImageSnapshotId` / `CreateImageCache` / `AutoMatchImageCache`）
> - **支持数据缓存**（`DataCacheBucket` / `DataCachePL` 等）
> - **Volume 类型完整**：`EmptyDirVolume` / `NFSVolume` / `ConfigFileVolume` / `FlexVolume` / `HostPathVolume`（白名单）/ `DiskVolume`（不推荐）
> - **Probes / Lifecycle hooks 完整支持**（HttpGet / TcpSocket / Exec / postStart / preStop）

---

## Overview

Alibaba Cloud **Elastic Container Instance (ECI)** is a **Serverless container
runtime**: each ECI (a.k.a. **ContainerGroup**) is a pod-equivalent unit that
runs in your VPC, billed per-second by vCPU + memory (and optional GPU), with
**no node to manage**.

This skill is an **operational runbook** for agents: explicit scope, credential
rules, pre-flight checks, **dual-path execution** (official **`aliyun` CLI**
primary, **JIT Go SDK** fallback), response validation, and failure recovery.

**Execution surface — CLI-primary with JIT Go SDK fallback:**
- **Primary:** `aliyun eci <Operation>` — static Go binary, covers
  ContainerGroup CRUD, exec, quota, image cache, data cache, virtual node.
- **Fallback:** JIT Go SDK
  (`github.com/alibabacloud-go/eci-20180808/client`)
  for advanced fields and any field not covered by the CLI.
- **Console click-paths** are not an agent execution surface in `SKILL.md`.

**Core resources managed by this skill:**
- **ContainerGroup** — the ECI unit (≡ K8s Pod). Identified by
  `ContainerGroupId`. Can contain 1..N containers sharing
  network/volume/lifecycle.
- **Container** — individual container inside a ContainerGroup.
- **ImageCache** — pre-pulled image data to accelerate ECI startup.
- **DataCache** — pre-staged data (model files, datasets) to accelerate ECI.
- **VirtualNode** — bridges non-ASK K8s clusters to ECI via virtual-kubelet.

**When to use this skill vs `alicloud-ack-serverless-ops`:**

| Need | Use |
|------|-----|
| Run a one-off batch job / short-lived container | `alicloud-eci-ops` (this) |
| Manage a K8s cluster of type `cluster_type=ManagedKubernetes` + `profile=Serverless` (ASK) | `alicloud-ack-serverless-ops` |
| Schedule long-lived workloads with HPA/CronHPA via K8s API | `alicloud-ack-serverless-ops` |
| Direct ECI management without K8s | `alicloud-eci-ops` (this) |
| Create a VirtualNode to bridge a self-managed K8s cluster to ECI | `alicloud-eci-ops` (this) |
| Create ImageCache / DataCache to accelerate cold start | `alicloud-eci-ops` (this) |

> **Relationship to ASK:** ASK's internal Pods **are** ECI ContainerGroups.
> This skill manages them directly; `alicloud-ack-serverless-ops` manages
> them through the K8s API. Don't run both on the same workload.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "ECI", "弹性容器实例", "ContainerGroup", "按 vCPU 秒计费容器",
  "跑个一次性任务", "在阿里云上跑个容器 Job"
- Task is ContainerGroup lifecycle: create, describe, list, update, delete,
  exec into
- Task is ECI quota pre-flight or quota change request
- User wants to run a **batch / CI / Spark / short-lived** workload on
  Alibaba Cloud **without** managing a K8s cluster
- User asks to attach GPU to a container on demand
- User asks for direct ECI exec (e.g. `docker exec`-like)
- User wants to create ImageCache or DataCache
- User wants to create a VirtualNode for their self-managed K8s cluster

### SHOULD NOT Use This Skill When

- Cluster is K8s-based (`cluster_type=ManagedKubernetes` + `profile=Serverless` for ASK, or `ManagedKubernetes` alone for managed) → delegate to
  [`alicloud-ack-serverless-ops`](../alicloud-ack-serverless-ops/SKILL.md)
  or [`alicloud-ack-ops`](../alicloud-ack-ops/SKILL.md)
- Task is about **bare ECS instances** → delegate to `alicloud-ecs-ops`
- Task is **container image build / registry** (ACR) → delegate to
  `alicloud-acr-ops` (when present)
- Task is **VPC / VSwitch / SecurityGroup** creation only →
  `alicloud-vpc-ops`
- Task is **K8s-level workload management on ASK** (Deployment, Service,
  HPA) → `alicloud-ack-serverless-ops` (kubectl through kubeconfig)
- Task is purely billing / account management → `alicloud-billing-ops`
- Task is RAM / permission model only → `alicloud-ram-ops`
- User insists on **console-only** flows with no API → state limitation;
  do not invent undocumented HTTP steps

### Delegation Rules

- Before `CreateContainerGroup`, ensure **VPC, VSwitch, SecurityGroup**
  exist (via `alicloud-vpc-ops`) and **ECI quota** is sufficient
  (via `aliyun eci ListUsage --RegionId <region>` in this skill).
- For container image from private registry (ACR), pre-configure
  `ImageRegistryCredential` (`Server` + `UserName` + `Password`) in
  the request; or delegate to `alicloud-acr-ops`.
- If a ContainerGroup is failing to schedule, the root cause is often
  ECI quota exhaustion, VSwitch IP shortage, or security group
  ingress — diagnose in this order before suspecting the image or
  command.

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.container_group_name}}` | User-supplied ContainerGroup name | Ask once; reuse |
| `{{user.container_group_id}}` | User-supplied or output ID | Ask if not from previous output |
| `{{user.image}}` | Container image (e.g. `nginx:1.25` or ACR URL) | Ask once |
| `{{user.vswitch_id}}` | VSwitch for ECI ENI | Ask; validate via VPC skill |
| `{{user.security_group_id}}` | SecurityGroup for ECI ENI | Ask; validate via VPC/ECS skill |
| `{{user.cpu}}` / `{{user.memory}}` | ECI spec | Ask; respect ECI min/max |
| `{{output.container_group_id}}` | From last CreateContainerGroup response | Parse from response |
| `{{output.container_group_ip}}` | ECI ENI IP | Parse from response |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`**
> MUST be collected interactively when missing.

> **凭据安全（强制）：** 参考
> [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, response
  shapes. ECI uses **`ECI-2018-08-08`** API version (verified).
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per
  spec. Common ECI errors: `QuotaExceeded`, `InvalidParameter.CPU.Memory`,
  `InvalidParameter.DuplicatedName`, `InvalidParameter.DuplicatedVolumeName`,
  `ImageSnapshot.NotFound`, `InvalidVSwitchId.IpNotEnough`,
  `OperationDenied.SecurityGroupMisMatch`, `OperationDenied.VswZoneMisMatch`.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** `ClientToken` can be used for CreateContainerGroup (≤64 ASCII).

### Response Field Table (ECI-Specific)

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateContainerGroup | `$.ContainerGroupId` | string | New ECI ID |
| CreateContainerGroup | `$.RequestId` | string | Request ID |
| DescribeContainerGroups | `$.ContainerGroups[].ContainerGroupId` | array | ECI IDs |
| DescribeContainerGroups | `$.ContainerGroups[].Status` | enum | ECI lifecycle state |
| DescribeContainerGroup | `$.Status` | string | ECI state |
| DescribeContainerGroup | `$.Containers[].Name` | string | Container names |
| DescribeContainerGroup | `$.Containers[].Image` | string | Container image |
| DescribeContainerGroup | `$.IntranetIp` | string | ECI ENI private IP |
| DescribeContainerGroup | `$.RegionId` / `$.VpcId` / `$.VSwitchId` | string | Network binding |
| ListUsage | (verify per region) | varies | Quota usage (CPU, memory, instance count) |

### Expected State Transitions (ContainerGroup)

| Operation | Initial | Target | Poll Interval | Max Wait |
|-----------|---------|--------|---------------|----------|
| CreateContainerGroup | — | `Running` / `Succeeded` / `Failed` | 5s | 300s |
| DeleteContainerGroup | any | absent / 404 | 5s | 120s |
| UpdateContainerGroup | `Running` | `Running` | 5s | 120s |
| RestartContainerGroup | any | `Running` | 5s | 120s |

### ContainerGroup Status Reference

| Status | Meaning | Actionable? |
|--------|---------|--------------|
| `Pending` | Provisioning ENI / pulling image | Wait; investigate if > 60s |
| `Scheduling` | Awaiting ECI quota / VSwitch IP | Check quota; raise if needed |
| `Running` | At least 1 container running | Yes — can Exec |
| `Succeeded` | All containers exited 0 (RestartPolicy=Never/OnFailure) | Yes — can delete |
| `Failed` | At least 1 container exited non-zero | Yes — read logs; consider recreate |
| `SchedulingFailed` | Quota exhausted, cannot schedule | Raise quota; retry |

## Quick Start

### What This Skill Does
This skill creates, describes, updates, deletes, and execs into Alibaba Cloud
Elastic Container Instances (ECI) via `aliyun eci ...` (primary) or JIT Go SDK
(fallback). It also handles ECI quota pre-flight checks via `ListUsage`.

### Prerequisites
- [ ] `aliyun` CLI installed (or Go runtime for JIT fallback)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`
- [ ] VPC + VSwitch + SecurityGroup exist in the target region
- [ ] **⚠️** Run the [OpenAPI verify status](#✅-openapi-验证状态-verified-2026-06-02)
      at the top of this file before first CreateContainerGroup

### Verify Setup
```bash
aliyun version
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo "✅ AK set"
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "✅ SK set (length only)"
aliyun eci ListUsage --body '{"RegionId":"'"$ALIBABA_CLOUD_REGION_ID"'"}' 2>&1 | head -30
```

### Your First Command
```bash
# Check ECI quota in region
aliyun eci ListUsage --body '{"RegionId":"'"$ALIBABA_CLOUD_REGION_ID"'"}'

# List current ContainerGroups
aliyun eci DescribeContainerGroups --RegionId $ALIBABA_CLOUD_REGION_ID \
  --output cols=ContainerGroupId,Status,Name \
  rows=ContainerGroups[].{ContainerGroupId:ContainerGroupId,Status:Status,Name:Name}
```

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| CreateContainerGroup | Create a new ECI (one or more containers) | Medium | Low (transient) |
| DescribeContainerGroup(s) | List / inspect ECIs | Low | None |
| UpdateContainerGroup | Update image / spec | Medium | Medium |
| ExecContainerCommand | Run a command inside a container | Low | Low |
| DeleteContainerGroup | Remove ECI (irreversible, kills workloads) | Low | **High** |
| RestartContainerGroup | Restart a ContainerGroup | Low | Medium |
| **ListUsage** | **Region-level quota usage (verified command)** | Low | None |
| DescribeContainerGroupPrice | ECI price query | Low | None |
| DescribeAvailableResource | ECS instance families available per region/zone | Low | None |
| CreateImageCache | Pre-pull images for fast startup | Medium | Low |
| CreateDataCache | Pre-stage data (models, datasets) | Medium | Low |
| CreateVirtualNode | Bridge self-managed K8s cluster to ECI | High | Medium |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-02 | Initial ECI skill. Covers ContainerGroup lifecycle, exec, quota, image cache, data cache, virtual node. |
| 1.1.0 | 2026-06-02 | **Major corrections after OpenAPI verification**: quota command is `ListUsage` (not `DescribeContainerGroupQuota`); `CpuOptions` is actually `CpuOptionsCore`+`CpuOptionsThreadsPerCore`; `ImageRegistryCredential` is `{Server,UserName,Password}`; `ExecContainerCommand` takes JSON array; added ImageCache/DataCache/VirtualNode/Spot/EIP/IPv6 sections. |

---

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI primary / SDK fallback) → Validate
→ Recover**. Do not skip phases.

### Operation: CreateContainerGroup

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI / deps | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys | HALT; user configures env |
| Region | `aliyun eci DescribeContainerGroups --RegionId {{user.region}}` | HTTP 200 | Suggest valid region |
| **ECI quota** | `aliyun eci ListUsage --body '{"RegionId":"{{user.region}}"}'` | Quota not exhausted | HALT; user raises quota in ECI console |
| VPC / VSwitch | Validate `{{user.vswitch_id}}` exists | Found | Delegate to VPC skill or ask |
| SecurityGroup | Validate `{{user.security_group_id}}` exists | Found | Delegate to VPC/ECS skill or ask |
| Image | If private registry, ensure `ImageRegistryCredential` ready | Set in request | Delegate to ACR or ask |
| **VSwitch free IPs** | `aliyun vpc DescribeVSwitches --VSwitchId {{user.vswitch_id}}` → check `AvailableIpAddress` | ≥ requested count | Expand VSwitch CIDR or pick another |

#### Execution — CLI (`aliyun eci`) (Primary Path)

> **CLI supports two styles**:
> 1. `--Container.N.*` array parameters (for simple cases)
> 2. `--body '{...}'` for complex requests

**Style 1: Simple array params (single container, no image cache)**
```bash
aliyun eci CreateContainerGroup \
  --RegionId "{{user.region}}" \
  --ContainerGroupName "{{user.container_group_name}}" \
  --Container.1.Name "app" \
  --Container.1.Image "{{user.image}}" \
  --Container.1.Cpu "1" \
  --Container.1.Memory "2" \
  --Cpu "{{user.cpu}}" \
  --Memory "{{user.memory}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --SecurityGroupId "{{user.security_group_id}}" \
  --RestartPolicy "Never"
```

**Style 2: JSON body (complex, multi-container, with private registry)**
```bash
aliyun eci CreateContainerGroup --body '{
  "RegionId": "{{user.region}}",
  "ContainerGroupName": "{{user.container_group_name}}",
  "RestartPolicy": "Never",
  "SecurityGroupId": "{{user.security_group_id}}",
  "VSwitchId": "{{user.vswitch_id}}",
  "Cpu": "{{user.cpu}}",
  "Memory": "{{user.memory}}",
  "Container": [
    {
      "Name": "app",
      "Image": "{{user.image}}",
      "Cpu": "{{user.cpu}}",
      "Memory": "{{user.memory}}"
    },
    {
      "Name": "sidecar",
      "Image": "logshipper:v1",
      "Cpu": "0.5",
      "Memory": "1"
    }
  ],
  "ImageRegistryCredential": [
    {
      "Server": "registry-vpc.cn-hangzhou.aliyuncs.com",
      "UserName": "{{user.acr_user}}",
      "Password": "{{user.acr_password}}"
    }
  ],
  "ClientToken": "{{user.container_group_name}}-$(date +%s)"
}'
```

> **For private registry:** Use `ImageRegistryCredential` array with
> `{Server, UserName, Password}` (note: `UserName`, not `Username`).
>
> **For EIP / internet access:** Use `AutoCreateEip=true` + `EipBandwidth`,
> OR bind existing `EipInstanceId`.
>
> **For image cache acceleration:** Set `ImageSnapshotId=<cache-id>`
> and/or `AutoMatchImageCache=true`.
>
> **Idempotency:** Pass `ClientToken` (unique string per request) to
> prevent duplicate creation on retry.

#### Execution — JIT Go SDK (Fallback Path)

When CLI does not support a specific field, or for advanced features:

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

1. Extract `{{output.container_group_id}}` from response (top-level `ContainerGroupId`).
2. Poll until `Status` is terminal:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun eci DescribeContainerGroups \
    --RegionId "{{user.region}}" \
    --ContainerGroupIds.1 "[\"{{output.container_group_id}}\"]" \
    --output cols=Status rows=ContainerGroups[].Status | tr -d '[:space:]')
  case "$STATUS" in
    Running|Succeeded|Failed) echo "Reached terminal status: $STATUS"; break ;;
    *) echo "Status: $STATUS, waiting..."; sleep 5 ;;
  esac
done
```

3. On success, report `ContainerGroupId`, `Status`, `IntranetIp`.
4. On terminal failure (`Failed`, timeout), go to **Failure Recovery**.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` / 400 | 0–1 | — | Fix args from OpenAPI verify status; retry once if safe |
| `QuotaExceeded` | 0 | — | HALT; user raises ECI quota in ECI console |
| `InvalidVSwitchId.IpNotEnough` | 0 | — | Expand VSwitch CIDR or use another VSwitch |
| `ImageSnapshot.NotFound` | 0 | — | Verify image cache ID or recreate |
| `ImagePullError` | 0 | — | Verify image name; verify `ImageRegistryCredential` |
| `InsufficientBalance` | 0 | — | HALT |
| `ErrorCheckAcl` / RAM | 0 | — | Delegate to RAM skill or user fixes policy |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 10s, 20s, 40s | Retry; then HALT with `RequestId` |

---

### Operation: ListUsage (Quota — Pre-flight Critical)

#### Execution — CLI

```bash
# ECI quota usage (region-level)
aliyun eci ListUsage --body '{"RegionId":"{{user.region}}"}'
```

> **Note:** Response field names for quota need first-use verification
> (see [openapi-verify-checklist.md](references/openapi-verify-checklist.md)).
> Expected fields likely include `CpuQuota` / `CpuUsed` / `MemoryQuota` /
> `MemoryUsed` and similar.

#### Gate Decision

- Compute `used + requested ≤ quota` for CPU and memory
- If over → HALT; user must raise quota in ECI console

> **Quota raises** are typically ticket-based or console-based; this skill
> does not auto-raise quota.

---

### Operation: DescribeContainerGroups

#### Execution — CLI

```bash
# List all ECIs in region
aliyun eci DescribeContainerGroups --RegionId {{user.region}}

# Filter by name
aliyun eci DescribeContainerGroups --RegionId {{user.region}} \
  --ContainerGroupName "{{user.container_group_name}}"

# Filter by status
aliyun eci DescribeContainerGroups --RegionId {{user.region}} \
  --Status "Running"

# Filter by security group
aliyun eci DescribeContainerGroups --RegionId {{user.region}} \
  --SecurityGroupId "{{user.security_group_id}}"

# Pagination
aliyun eci DescribeContainerGroups --RegionId {{user.region}} \
  --Limit 20 --NextToken "<token>"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| ContainerGroupId | `$.ContainerGroups[].ContainerGroupId` | Plain text |
| Name | `$.ContainerGroups[].ContainerGroupName` | Plain text |
| Status | `$.ContainerGroups[].Status` | `Pending` / `Running` / `Succeeded` / `Failed` / `Scheduling` / `SchedulingFailed` |
| Intranet IP | `$.ContainerGroups[].IntranetIp` | ENI private IP |
| VSwitch | `$.ContainerGroups[].VSwitchId` | Plain text |
| Created | `$.ContainerGroups[].CreatedTime` | ISO 8601 |

---

### Operation: DescribeContainerGroup (single)

```bash
aliyun eci DescribeContainerGroup --RegionId {{user.region}} \
  --ContainerGroupId "{{user.container_group_id}}"
```

Use this for full detail (container list, events, ENI, volumes).

---

### Operation: ExecContainerCommand

#### Pre-flight
- Confirm ContainerGroup is in `Running` status.
- Confirm the target container name exists in the response of
  `DescribeContainerGroup`.

#### Execution — CLI

> **⚠️** `--Command` must be a **JSON array**, not a plain string.

```bash
# Non-interactive, sync execution
aliyun eci ExecContainerCommand --RegionId {{user.region}} \
  --ContainerGroupId "{{user.container_group_id}}" \
  --ContainerName "app" \
  --Command '["/bin/sh", "-c", "ls -la /tmp"]' \
  --Sync true

# Interactive shell (TTY required)
aliyun eci ExecContainerCommand --RegionId {{user.region}} \
  --ContainerGroupId "{{user.container_group_id}}" \
  --ContainerName "app" \
  --Command '["/bin/bash"]' \
  --TTY true
```

> **Param notes (verified):**
> - `--Stdin` (default true) — read commands from stdin
> - `--Sync` (default false) — sync execution; if true, `TTY` must be false and `Command` cannot be `/bin/bash`
> - `--TTY` (default false) — enable interaction; required if `Command` is `/bin/bash`

#### Validation
- Output of the command is returned in the response. If the command
  returns non-zero, treat as failure and surface the stderr.

---

### Operation: UpdateContainerGroup

> **⚠️** Field support varies. Verify with
> `aliyun eci UpdateContainerGroup --help`. Common supported updates:
> image (rolling restart), resource limits (depending on state).

#### Pre-flight
- ContainerGroup must be in `Running` or terminal state (verify which).
- Some updates cause ECI restart; confirm user accepts.

#### Execution — CLI

```bash
# Update image (forces restart)
aliyun eci UpdateContainerGroup --RegionId {{user.region}} \
  --ContainerGroupId "{{user.container_group_id}}" \
  --Container.1.Name "app" \
  --Container.1.Image "nginx:1.26"
```

---

### Operation: DeleteContainerGroup

#### Pre-flight (Safety Gate)
- **MUST** obtain explicit confirmation.
- **MUST** warn user: deleting the ContainerGroup is irreversible;
  any in-flight workloads are killed; persistent volumes may survive
  but become orphan if no other CG uses them.
- Confirm ContainerGroup is in a terminal state or the user accepts
  forced kill.

#### Execution — CLI

```bash
# Single delete
aliyun eci DeleteContainerGroup --RegionId {{user.region}} \
  --ContainerGroupId "{{user.container_group_id}}"

# Batch delete (loop)
for CG_ID in $(...); do
  aliyun eci DeleteContainerGroup --RegionId {{user.region}} \
    --ContainerGroupId "$CG_ID"
done
```

#### Post-execution Validation

Poll `DescribeContainerGroup` until **404** or absent (max wait 120s).

#### Failure Recovery

| Error pattern | Action |
|---------------|--------|
| `ContainerGroupNotFound` | Already deleted; confirm to user |
| `ContainerGroupInTransition` (still Pending/Running) | Wait for terminal state, retry |
| `DependencyResourceExist` (e.g. attached volume busy) | Ask user to release |

---

## 跨 Skill 委托协议 (Cross-Skill Delegation)

| 委托场景 | 目标 Skill | 委托信息 |
|----------|------------|----------|
| **VPC / VSwitch / SG 未创建** | `alicloud-vpc-ops` | VPC ID、VSwitch ID、SecurityGroup ID 需求 |
| **VSwitch IP 不足** | `alicloud-vpc-ops` | VSwitch ID、需要扩大的 CIDR |
| **私有镜像拉取失败** | `alicloud-acr-ops` (when present) | Registry URL、镜像名、`ImageRegistryCredential` 形状 (Server/UserName/Password) |
| **底层 ENI / ECS 问题** | `alicloud-ecs-ops` | ENI ID、异常现象 |
| **K8s 集群内 ECI (ASK Pod)** | [`alicloud-ack-serverless-ops`](../alicloud-ack-serverless-ops/SKILL.md) | 集群 ID、Pod 名 — **不要同时用本 skill 管理同一个 Pod** |
| **日志聚合 (容器 stdout/stderr)** | `alicloud-sls-ops` (when present) | Project、Logstore |
| **监控告警 / Dashboard** | `alicloud-cms-ops` | 命名空间 `acs_eci_dashboard`、指标名 |
| **RAM 权限问题** | `alicloud-ram-ops` | Action、Resource |
| **成本核算** | `alicloud-billing-ops` | ECI 资源 ID、计费周期 |
| **ImageCache / DataCache 创建** | 本 skill (CreateImageCache / CreateDataCache) | 镜像列表、数据源、保留天数 |

---

## Prerequisites

1. **Install `aliyun` CLI** (primary):
   ```bash
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   ```

2. **Bootstrap Go runtime** (JIT SDK fallback): 参见
   [`../alicloud-ack-ops/references/integration.md`](../alicloud-ack-ops/references/integration.md)
   (复用相同的 self-healing 流程)

3. **Configure Credentials**:
   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```
   > **IMPORTANT:** Mask SK in console output:
   > `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"`.

4. **Verify**:
   ```bash
   aliyun eci ListUsage --body '{"RegionId":"'"$ALIBABA_CLOUD_REGION_ID"'"}'
   ```

> **Security:** Never commit credentials. All credentials use `{{env.*}}`
> placeholders — never real values.

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's
[Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).

### 安全 (Security)

| Area | Guidance |
|------|----------|
| **IAM** | Require: `eci:CreateContainerGroup`, `eci:Describe*`, `eci:DeleteContainerGroup`, `eci:ExecContainerCommand` scoped to user's VPC. **Avoid** `eci:*` wildcard. |
| **Credentials** | Use `{{env.*}}` only. Mask SK in all output. |
| **Network** | Place ECI in private subnets; use SecurityGroup to restrict ingress. Egress via NAT or EIP only. |
| **Image** | Prefer ACR (private, vulnerability-scanned) over public DockerHub. Always pin image digest. |
| **Exec** | `ExecContainerCommand` is equivalent to `docker exec` — treat as **privileged**. Log all exec invocations. |

### 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的设计** | `RestartPolicy=Never` for batch jobs (avoids infinite restart loop and infinite billing) |
| **幂等** | Always pass `ClientToken` for CreateContainerGroup to enable safe retry |
| **Quota headroom** | Always run `ListUsage` before `CreateContainerGroup`. Keep region usage < 80%. |
| **Volume cleanup** | ECI with cloud disk / NAS may leave orphan volumes; build a cleanup pass. |

#### DR Runbook
```
Phase 1: Verify — DescribeContainerGroup for target workload
Phase 2: Restore — Recreate ContainerGroup with same image + spec
Phase 3: Validate — Poll Status; if Failed, check Events / exec inspect
```

### 成本 (Cost)

| Billing | Best For | Savings |
|---------|----------|---------|
| **ECI on-demand (vCPU×sec, mem×sec)** | Variable workloads, batch | Baseline |
| **ECI Savings Plans** | Stable 24/7 baseline | Up to 60% |
| **ECI Spot (`SpotStrategy`)** | Fault-tolerant batch | Up to 90% |
| **GPU ECI** | ML inference, batch | Pay only for use |
| NAT Gateway (egress) | Internet-bound ECI | Flat hourly |
| EIP (if AutoCreateEip) | Internet-bound ECI | Flat hourly |

> **No idle cost** for ECI (unlike ECS nodes). This is the primary cost
> advantage.

**Waste detection:**
| Pattern | Detection | Action |
|---------|-----------|--------|
| `RestartPolicy=Always` + crash | `RestartCount` rising | Change to `Never` or `OnFailure` |
| Over-provisioned Cpu/Memory | `eci.cpu.usage` < 10% avg over 7d | Right-size |
| Long-running idle ECI | Running > 24h with no activity | Delete or set TTL |
| Cloud disk / NAS not cleaned up | ECI deleted but disk still exists | Build cleanup pass |

### 效率 (Efficiency)

- **Batch creation:** For many independent ECIs, parallelize CLI calls with
  `&` and `wait` — but respect API rate limits.
- **Image pre-pull:** Use `CreateImageCache` for latency-sensitive
  workloads.
- **Data pre-stage:** Use `CreateDataCache` for ML model / dataset
  workloads.
- **Right-sizing:** Match `Cpu` / `Memory` to actual workload; over-provisioned
  ECI wastes money per-second.

### 性能 (Performance)

| Metric | CMS Namespace | Target | Action |
|--------|---------------|--------|--------|
| Container CPU | `acs_eci_dashboard` | < 70% avg | Increase `Cpu` or scale out |
| Container Memory | `acs_eci_dashboard` | < 80% avg | Increase `Memory` |
| Cold start (image pull) | (via container log) | < 60s for 1GB image | Pre-pull via ImageCache; same-region ACR |
| ECI Pending (Scheduling) | (status) | < 5% of ECIs | Check quota, VSwitch IP |

**Key guidance:** Right-size `Cpu` / `Memory` to actual usage. ECI bills
per-spec, so over-provisioning is direct cost waste.

---

## FinOps Operations (成本优化运维)

### Operation: Cost Allocation by Tag

```bash
#!/bin/bash
# eci-cost-allocation-by-tag.sh <RegionId> <TagKey> <VcpuPerSec> <MemGbPerSec>
REGION="$1"
TAG_KEY="$2"
VCPU_COST="$3"
MEM_COST="$4"

# List ECIs with given tag
aliyun eci DescribeContainerGroups --RegionId "$REGION" \
  --output cols=ContainerGroupId,Name,Status,Cpu,Memory \
  rows=ContainerGroups[].{ContainerGroupId:ContainerGroupId,Name:ContainerGroupName,Status:Status,Cpu:Cpu,Memory:Memory}

echo ""
echo "Note: Real cost = (Cpu * vCPU_COST + Memory * Mem_COST) * seconds_running"
```

### Operation: Idle ECI Detection

ECIs are short-lived by design, so "idle" is unusual. Patterns:

| Pattern | Detection | Action |
|---------|-----------|--------|
| `Running` but no logs for > 1h | Log inspection | Investigate; consider delete |
| `Failed` > 1h | `DescribeContainerGroups` filter | Inspect + delete or restart |
| `Pending`/`Scheduling` > 5min | Status check | Check quota, VSwitch IP |

---

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [CLI Usage](references/cli-usage.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [Troubleshooting](references/troubleshooting.md)
- [Monitoring](references/monitoring.md)
- [Integration](references/integration.md)
- [OpenAPI Verify Checklist](references/openapi-verify-checklist.md) — **VERIFIED 2026-06-02**
- [Well-Architected Assessment](references/well-architected-assessment.md)

## Operational Best Practices

- **Least privilege:** RAM policies scoped to specific ECI actions; avoid
  `eci:*` wildcard. Use `eci:CreateContainerGroup` only when needed.
- **Quota awareness:** Always run `ListUsage` before
  `CreateContainerGroup`. If `Used / Total > 80%`, refuse and ask for
  quota raise.
- **VSwitch IP:** Pre-check `AvailableIpAddress` for the target VSwitch.
  Each ECI = 1 ENI = 1 IP from the VSwitch.
- **Image hygiene:** Pin image digest (`@sha256:...`); prefer ACR over
  public registries; scan with ACR vulnerability scanner before deploy.
- **Cost:** `RestartPolicy=Never` for batch (avoids infinite restart
  billing); use Spot for fault-tolerant work; use Savings Plans for
  24/7 baseline.
- **Cleanup:** Build a periodic cleanup pass to delete `Succeeded` /
  `Failed` ECIs older than N hours. Cloud disk / NAS volumes may
  survive — handle separately.
- **ImageCache / DataCache:** Pre-create for latency-sensitive or
  model-loading workloads to cut cold start by 60-90%.

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only`, the skill MUST provide
  `assets/code-snippets/`. **DOES NOT APPLY** — 本 skill 为 `dual-path`，
  CLI/SDK 已覆盖，无需 code snippets.
