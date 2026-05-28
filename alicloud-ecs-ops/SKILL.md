---
name: alicloud-ecs-ops
description: >-
  Use this skill to manage the full lifecycle of Alibaba Cloud ECS instances
  (Elastic Compute Service) — create, start, stop, restart, delete, resize,
  replace system disks, and manage disks (attach, detach, resize, delete).
  Manage images, snapshots, security groups and rules, and resource tags.
  Run commands, scripts, and send files via Cloud Assistant. Diagnose
  connectivity issues. Reach for this skill when the user needs a VM, reports
  "my server won't start", "disk is full", "can't connect", "help me migrate",
  "change the OS", "expand storage", or wants to deploy, monitor, troubleshoot,
  or automate Alibaba Cloud compute resources — even if they just say "云服务器",
  "主机", "虚拟机", "弹性计算" without naming ECS explicitly. Keywords: ECS,
  云服务器, 弹性计算, 主机, 虚拟机, 实例, 磁盘, 快照, 镜像, 安全组, 云助手,
  VM, instance, disk, snapshot, image. Do NOT use for databases (RDS),
  networking/load balancing (VPC/SLB/ALB), containers (ACK/ASK),
  billing/accounting, or RAM-only tasks.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "2.1.0"
  last_updated: "2026-05-14"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "ECS 2014-05-26 / https://www.alibabacloud.com/help/en/ecs"
  cli_applicability: cli-first
  cli_support_evidence: "Confirmed via `aliyun help ecs` — ECS is fully supported by the official aliyun CLI. All core operations (CRUD, lifecycle, disks, snapshots, security groups) have matching CLI commands."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud ECS Operations Skill

## Common JSON Paths (Centralized)

```
# Create/Describe Instance: $.Instances.Instance[].{InstanceId,Status,RegionId,ZoneId,InstanceName}
# Create Disk:              $.DiskId
# Describe Disks:           $.Disks.Disk[].{DiskId,Status}
# Create Snapshot:          $.SnapshotId
# Describe Snapshots:       $.Snapshots.Snapshot[].SnapshotId
# Create SecurityGroup:     $.SecurityGroupId
# AuthorizeSG/Delete/etc:   $.RequestId
# RunInstances:             $.InstanceIdSets.InstanceIdSet[]
# RunCommand:               $.InvokeId
# Describe Images:          $.Images.Image[].ImageId
```

## Overview

Alibaba Cloud ECS (Elastic Compute Service) provides scalable virtual servers in the cloud. This skill is an **operational runbook** for agents: explicit scope, credential rules, pre-flight checks, **cli-first execution** (official **`aliyun` CLI** as primary path, **JIT Go SDK** as fallback), response validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: cli-first`:** Official `aliyun` fully supports ECS. CLI is the **primary** execution path for all operations. JIT Go SDK is the **fallback** only when CLI lacks support for a specific edge-case operation.

### Quick Start

不知道从哪里开始？直接看 [Prompt Examples](references/prompt-examples.md)，里面有 50+ 条自然语言提示词示例，覆盖实例管理、云盘操作、安全组配置、云助手远程执行、故障诊断等场景，复制即用。

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud ECS" OR "云服务器" OR "Elastic Compute Service" OR "ECS实例"
- Task involves CRUD or lifecycle operations on **ECS instances** (create, start, stop, restart, delete, describe, list)
- Task involves **disks** (create, attach, detach, delete, describe, resize)
- Task involves **images** (create, describe, delete, copy, share)
- Task involves **snapshots** (create, describe, delete, rollback)
- Task involves **security groups** (create, describe, delete, authorize, revoke rules)
- Task involves **batch operations** (RunInstances)
- Task involves **instance attribute modifications** (rename, reset password)
- Task involves **Cloud Assistant** operations (run commands on instances, send files, query execution results)
- Task keywords: 实例, 云盘, 镜像, 快照, 安全组, 云助手, instance, disk, image, snapshot, security group, batch, run-instances, cloud assistant, run command, send file
- User asks to deploy, configure, troubleshoot, or monitor ECS **via API, SDK, CLI, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops` (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when present)
- Task is about **VPC / networking only** → delegate to: `alicloud-vpc-ops` (when present)
- Task is about **RDS / databases** → delegate to: `alicloud-rds-ops` (when present)
- User insists on **console-only** flows with no API → state limitation; do not invent undocumented HTTP steps

### Delegation Rules

- If creating an ECS instance in a VPC, verify VPC and VSwitch exist (via `alicloud-vpc-ops`) before ECS creation.
- If attaching a disk, verify the disk and instance are in the same zone and region.
- Multi-product requests: handle each product with its skill; do not merge unrelated APIs into one ambiguous flow.

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.instance_id}}` | User-supplied ECS instance ID | Ask once; reuse |
| `{{user.instance_name}}` | User-supplied ECS instance name | Ask once; reuse |
| `{{user.disk_id}}` | User-supplied disk ID | Ask once; reuse |
| `{{user.image_id}}` | User-supplied image ID | Ask once; reuse |
| `{{user.security_group_id}}` | User-supplied security group ID | Ask once; reuse |
| `{{user.zone_id}}` | User-supplied zone ID | Ask once; reuse |
| `{{user.instance_type}}` | User-supplied instance type | Ask once; reuse |
| `{{user.vswitch_id}}` | User-supplied VSwitch ID | Ask once; reuse |
| `{{user.vpc_id}}` | User-supplied VPC ID | Ask once; reuse |
| `{{user.key_pair_name}}` | User-supplied SSH key pair name | Ask once; reuse |
| `{{output.instance_id}}` | From last API or CLI JSON response | Parse per OpenAPI or verified CLI path |
| `{{output.disk_id}}` | From last API or CLI JSON response | Parse per OpenAPI or verified CLI path |
| `{{output.snapshot_id}}` | From last API or CLI JSON response | Parse per OpenAPI or verified CLI path |
| `{{output.security_group_id}}` | From last API or CLI JSON response | Parse per OpenAPI or verified CLI path |
| `{{output.request_id}}` | From API response | For support / correlation |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** Document client request tokens, duplicate names, and `InstanceAlreadyExists` behavior per API.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateInstance | `$.InstanceId` | string | New instance ID |
| DescribeInstances | `$.Instances.Instance[].InstanceId` | array | Instance IDs |
| DescribeInstances | `$.Instances.Instance[].Status` | string | Instance status |
| DescribeInstances | `$.Instances.Instance[].RegionId` | string | Region ID |
| DescribeInstances | `$.Instances.Instance[].ZoneId` | string | Zone ID |
| DescribeInstances | `$.Instances.Instance[].InstanceName` | string | Instance name |
| DescribeInstances | `$.Instances.Instance[].Cpu` | int | vCPU count |
| DescribeInstances | `$.Instances.Instance[].Memory` | int | Memory (MB) |
| DescribeInstances | `$.Instances.Instance[].CreationTime` | string | ISO 8601 timestamp |
| StartInstance | `$.RequestId` | string | Request ID |
| StopInstance | `$.RequestId` | string | Request ID |
| DeleteInstance | `$.RequestId` | string | Request ID |
| CreateDisk | `$.DiskId` | string | New disk ID |
| DescribeDisks | `$.Disks.Disk[].DiskId` | array | Disk IDs |
| DescribeDisks | `$.Disks.Disk[].Status` | string | Disk status |
| AttachDisk | `$.RequestId` | string | Request ID |
| DetachDisk | `$.RequestId` | string | Request ID |
| CreateSnapshot | `$.SnapshotId` | string | New snapshot ID |
| DescribeSnapshots | `$.Snapshots.Snapshot[].SnapshotId` | array | Snapshot IDs |
| DeleteSnapshot | `$.RequestId` | string | Request ID |
| CreateSecurityGroup | `$.SecurityGroupId` | string | New security group ID |
| DescribeSecurityGroups | `$.SecurityGroups.SecurityGroup[].SecurityGroupId` | array | Security group IDs |
| AuthorizeSecurityGroup | `$.RequestId` | string | Request ID |
| RunInstances | `$.InstanceIdSets.InstanceIdSet[]` | array | Instance IDs |
| ModifyInstanceAttribute | `$.RequestId` | string | Request ID |
| DescribeImages | `$.Images.Image[].ImageId` | array | Image IDs |
| RunCommand | `$.InvokeId` | string | Invocation ID |
| DescribeInvocationResults | `$.Invocation.InvocationResults.InvocationResult[].InvokeId` | array | Invocation IDs |
| DescribeInvocationResults | `$.Invocation.InvocationResults.InvocationResult[].Output` | string | Command output (base64) |
| DescribeInvocationResults | `$.Invocation.InvocationResults.InvocationResult[].ExitCode` | int | Exit code |
| DescribeInvocationResults | `$.Invocation.InvocationResults.InvocationResult[].InvocationStatus` | string | Status: Pending, Running, Success, Failed, Timeout, Cancelled |
| SendFile | `$.InvokeId` | string | File transfer invocation ID |
| DescribeSendFileResults | `$.SendFileResults.SendFileResult[].InvokeId` | array | Invocation IDs |
| DescribeSendFileResults | `$.SendFileResults.SendFileResult[].FileStatus` | string | Status: Pending, Running, Success, Failed, PartialFailed |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateInstance | — | `Running` | 5s | 300s |
| StartInstance | `Stopped` | `Running` | 5s | 120s |
| StopInstance | `Running` | `Stopped` | 5s | 120s |
| RebootInstance | `Running` | `Running` | 5s | 120s |
| DeleteInstance | any stable state | absent / `Deleted` | 5s | 300s |
| CreateDisk | — | `Available` | 5s | 120s |
| AttachDisk | `Available` | `In_use` | 5s | 120s |
| DetachDisk | `In_use` | `Available` | 5s | 120s |
| DeleteDisk | `Available` | absent | 5s | 60s |
| ResizeDisk | `Available` or `In_use` | same | 5s | 120s |
| ReplaceSystemDisk | `Stopped` | `Stopped` | 5s | 300s |
| CreateSnapshot | — | `accomplished` | 10s | 600s |
| CreateSecurityGroup | — | `Available` | 5s | 60s |
| DeleteSnapshot | any stable state | absent | 5s | 60s |
| RunInstances | — | `Running` | 5s | 300s |
| ModifyInstanceAttribute | any | — | — | — |

> **Note on DeleteInstance:** Deleted instances enter the **Recycle Bin** by default (retention: 15 days for pay-as-you-go, varies for subscription). Use `--Force true` to bypass the recycle bin and permanently delete immediately. The `--Force` parameter does NOT mean "force stop"; it means "force permanent deletion without recycle bin." To delete a Running instance safely, first call `StopInstance`, then `DeleteInstance --Force false`.

### Polling Strategy

| Scenario | Preferred Method | Fallback |
|----------|-----------------|----------|
| CLI supports `--waiter` | `aliyun ... --waiter expr=... to=... timeout=... interval=...` | Manual loop |
| CLI lacks `--waiter` | Manual `for` loop with `sleep` | JIT Go SDK polling |
| Complex multi-resource wait | JIT Go SDK with concurrent polling | Sequential CLI calls |

> Always prefer `--waiter` when available; it reduces shell script complexity. Document which method is used in each operation.



## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (SDK/API and `aliyun`) → Validate → Recover**.

### Operation: Create Instance

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SDK / deps | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys | HALT; user configures env |
| Region | `aliyun ecs DescribeRegions` | `{{user.region}}` supported | Suggest valid region |
| Zone | `aliyun ecs DescribeZones --RegionId {{user.region}}` | `{{user.zone_id}}` supported | Suggest valid zone |
| Image | `aliyun ecs DescribeImages --RegionId {{user.region}}` | `{{user.image_id}}` exists | Suggest valid image |
| VPC/VSwitch | `aliyun vpc DescribeVpcs` / `DescribeVSwitches` | VPC and VSwitch exist | Delegate to `alicloud-vpc-ops` |
| Quota | `aliyun ecs DescribeAccountAttributes` | Sufficient quota | HALT; user raises quota |

#### Execution — CLI (Primary Path)

```bash
aliyun ecs CreateInstance \
  --RegionId "{{user.region}}" \
  --ZoneId "{{user.zone_id}}" \
  --ImageId "{{user.image_id}}" \
  --InstanceType "{{user.instance_type}}" \
  --SecurityGroupId "{{user.security_group_id}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --InstanceName "{{user.instance_name}}" \
  --InternetMaxBandwidthOut 1 \
  --KeyPairName "{{user.key_pair_name}}"
```

> **Security Note:** Prefer `KeyPairName` over `Password` for SSH authentication. If `Password` is used, ensure it meets complexity requirements (8-30 chars, mixed case + digits).

> **Note:** Output is JSON by default. Parse `InstanceId` from response.

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

1. Read `{{output.instance_id}}` from `$.InstanceId`.
2. Poll **DescribeInstances** until `Status` is `Running`:

```bash
# Using waiter (if supported by CLI version)
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{output.instance_id}}"]' \
  --waiter expr='Instances.Instance[0].Status' to=Running timeout=300 interval=5

# Alternative: manual polling loop (universal compatibility)
for i in $(seq 1 60); do
  STATUS=$(aliyun ecs DescribeInstances \
    --RegionId "{{user.region}}" \
    --InstanceIds '["{{output.instance_id}}"]' \
    --output cols=Status rows=Instances.Instance[0].Status)
  [ "$STATUS" = "Running" ] && break
  sleep 5
done
```

3. On success, report `{{output.instance_id}}`, public IP, and key fields.
4. On terminal failure, go to **Failure Recovery**.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` / 400 | 0–1 | — | Fix args from OpenAPI; retry once if safe |
| `QuotaExceeded` / `InstanceQuotaExceed` | 0 | — | HALT |
| `InsufficientBalance` | 0 | — | HALT |
| `ResourceAlreadyExists` / `InstanceAlreadyExists` | 0 | — | Ask reuse vs new name |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

> **RequestId Extraction:** On any API error, extract `RequestId` from the response for support correlation:
> ```bash
> # CLI: RequestId is in the JSON error response
> aliyun ecs DescribeInstances ... 2>&1 | jq -r '.RequestId // .requestId // "unknown"'
> ```
> ```go
> // SDK: RequestId is in the error response
> if err != nil {
>     if sdkErr, ok := err.(*tea.SDKError); ok {
>         requestId := tea.ToString(sdkErr.Data)
>         fmt.Printf("RequestId: %s\n", requestId)
>     }
> }
> ```

---

### Operation: Describe Instances

#### Execution — CLI

```bash
# Describe all instances in region
aliyun ecs DescribeInstances --RegionId "{{user.region}}"

# Describe specific instance
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]'

# Extract specific fields with JMESPath
aliyun ecs DescribeInstances --RegionId "{{user.region}}" \
  --output cols=InstanceId,Status,InstanceName rows=Instances.Instance[].{InstanceId,Status,InstanceName}
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Instance ID | `$.Instances.Instance[].InstanceId` | Plain text |
| Name | `$.Instances.Instance[].InstanceName` | Plain text |
| Status | `$.Instances.Instance[].Status` | Running, Stopped, Starting, Stopping |
| Region | `$.Instances.Instance[].RegionId` | Plain text |
| Zone | `$.Instances.Instance[].ZoneId` | Plain text |
| Instance Type | `$.Instances.Instance[].InstanceType` | e.g., ecs.g7.large |
| CPU | `$.Instances.Instance[].Cpu` | vCPU count |
| Memory | `$.Instances.Instance[].Memory` | MB |
| Public IP (Classic) | `$.Instances.Instance[].PublicIpAddress.IpAddress[]` | Array |
| Public IP (VPC + EIP) | `$.Instances.Instance[].EipAddress.IpAddress` | String |
| Private IP (VPC) | `$.Instances.Instance[].VpcAttributes.PrivateIpAddress.IpAddress[]` | Array |
| Private IP (Classic) | `$.Instances.Instance[].InnerIpAddress.IpAddress[]` | Array |
| Creation Time | `$.Instances.Instance[].CreationTime` | ISO 8601 |
| Expired Time | `$.Instances.Instance[].ExpiredTime` | ISO 8601 |

---

### Operation: Run Instances (Batch Create)

#### Pre-flight Checks

Same as **Create Instance** above.

#### Execution — CLI

```bash
aliyun ecs RunInstances \
  --RegionId "{{user.region}}" \
  --ZoneId "{{user.zone_id}}" \
  --ImageId "{{user.image_id}}" \
  --InstanceType "{{user.instance_type}}" \
  --SecurityGroupId "{{user.security_group_id}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --InstanceName "{{user.instance_name}}" \
  --Amount 2 \
  --InternetMaxBandwidthOut 1 \
  --KeyPairName "{{user.key_pair_name}}"
```

> **Note:** `Amount` supports 1-100. Returns `InstanceIdSets` array.

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll **DescribeInstances** with `InstanceIds` filter until all instances reach `Running`.

---

### Operation: Modify Instance Attribute

#### Pre-flight

- Verify instance exists.

#### Execution — CLI

```bash
# Rename instance
aliyun ecs ModifyInstanceAttribute \
  --InstanceId "{{user.instance_id}}" \
  --InstanceName "{{user.new_instance_name}}"

# Reset password (instance must be Stopped)
aliyun ecs ModifyInstanceAttribute \
  --InstanceId "{{user.instance_id}}" \
  --Password "{{user.new_password}}"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

---

### Operation: Describe Images

#### Execution — CLI

```bash
# List all images in region
aliyun ecs DescribeImages --RegionId "{{user.region}}"

# Filter by image type (system, custom, shared, marketplace)
aliyun ecs DescribeImages \
  --RegionId "{{user.region}}" \
  --ImageOwnerAlias system \
  --OSType Linux

# Search by name pattern
aliyun ecs DescribeImages \
  --RegionId "{{user.region}}" \
  --ImageName "CentOS*"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Image ID | `$.Images.Image[].ImageId` | e.g., centos_7_9_x64_20G_alibase_20230718.vhd |
| Image Name | `$.Images.Image[].ImageName` | Plain text |
| OS Type | `$.Images.Image[].OSType` | Linux / Windows |
| Platform | `$.Images.Image[].Platform` | CentOS, Ubuntu, etc. |
| Size | `$.Images.Image[].Size` | GB |

---

### Operation: Start Instance

#### Pre-flight

- Verify instance exists and status is `Stopped`.

#### Execution — CLI

```bash
aliyun ecs StartInstance --InstanceId "{{user.instance_id}}"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until `Status` is `Running`:

```bash
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --waiter expr='Instances.Instance[0].Status' to=Running timeout=120 interval=5
```

---

### Operation: Stop Instance

#### Pre-flight

- Verify instance exists and status is `Running`.

#### Execution — CLI

```bash
aliyun ecs StopInstance --InstanceId "{{user.instance_id}}" --ForceStop false
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until `Status` is `Stopped`:

```bash
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --waiter expr='Instances.Instance[0].Status' to=Stopped timeout=120 interval=5
```

---

### Operation: Reboot Instance

#### Pre-flight

- Verify instance exists and status is `Running`.

#### Execution — CLI

```bash
aliyun ecs RebootInstance --InstanceId "{{user.instance_id}}" --ForceStop false
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until `Status` returns to `Running`:

```bash
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --waiter expr='Instances.Instance[0].Status' to=Running timeout=120 interval=5
```

---

### Operation: Delete Instance

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of instance `{{user.instance_id}}` (`{{user.instance_name}}`).
- **MUST NOT** proceed without clear user assent.
- Verify instance is in `Stopped` status (required by API). If running, **stop first** (safer) or use `--Force true` (forces stop then delete).

#### Execution — CLI

```bash
# Safe: instance must already be Stopped; goes to Recycle Bin
aliyun ecs DeleteInstance --InstanceId "{{user.instance_id}}" --Force false

# Force: permanently delete without Recycle Bin (use with caution)
aliyun ecs DeleteInstance --InstanceId "{{user.instance_id}}" --Force true
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll **DescribeInstances** until instance is absent (returns empty list or `InstanceNotFound`) within **300s**.

```bash
for i in $(seq 1 60); do
  RESULT=$(aliyun ecs DescribeInstances \
    --RegionId "{{user.region}}" \
    --InstanceIds '["{{user.instance_id}}"]' \
    --output cols=TotalCount rows=TotalCount)
  [ "$RESULT" = "0" ] && break
  sleep 5
done
```

---

### Operation: Create Disk

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Region/Zone | `aliyun ecs DescribeZones --RegionId {{user.region}}` | Zone valid | Suggest valid zone |
| Disk Category | OpenAPI spec | `cloud`, `cloud_efficiency`, `cloud_ssd`, `cloud_essd`, `cloud_auto` | Validate input |
| Quota | `aliyun ecs DescribeAccountAttributes` | Sufficient quota | HALT |

#### Execution — CLI

```bash
aliyun ecs CreateDisk \
  --RegionId "{{user.region}}" \
  --ZoneId "{{user.zone_id}}" \
  --DiskName "{{user.disk_name}}" \
  --Size "{{user.disk_size}}" \
  --DiskCategory "{{user.disk_category}}"
```

> **Note:** `ZoneId` is optional if `InstanceId` is specified (creates and attaches in one step).

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until `Status` is `Available`:

```bash
aliyun ecs DescribeDisks \
  --RegionId "{{user.region}}" \
  --DiskIds '["{{output.disk_id}}"]' \
  --waiter expr='Disks.Disk[0].Status' to=Available timeout=120 interval=5
```

---

### Operation: Attach Disk

#### Pre-flight

- Verify disk status is `Available`.
- Verify instance and disk are in the same zone.

#### Execution — CLI

```bash
aliyun ecs AttachDisk \
  --InstanceId "{{user.instance_id}}" \
  --DiskId "{{user.disk_id}}"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until disk `Status` is `In_use`:

```bash
aliyun ecs DescribeDisks \
  --RegionId "{{user.region}}" \
  --DiskIds '["{{user.disk_id}}"]' \
  --waiter expr='Disks.Disk[0].Status' to=In_use timeout=120 interval=5
```

---

### Operation: Detach Disk

#### Pre-flight

- Verify disk status is `In_use`.

#### Execution — CLI

```bash
aliyun ecs DetachDisk \
  --InstanceId "{{user.instance_id}}" \
  --DiskId "{{user.disk_id}}"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until disk `Status` is `Available`:

```bash
aliyun ecs DescribeDisks \
  --RegionId "{{user.region}}" \
  --DiskIds '["{{user.disk_id}}"]' \
  --waiter expr='Disks.Disk[0].Status' to=Available timeout=120 interval=5
```

---

### Operation: Delete Disk

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of disk `{{user.disk_id}}`.
- **MUST** verify disk is detached (`Status` is `Available`).

#### Execution — CLI

```bash
aliyun ecs DeleteDisk --DiskId "{{user.disk_id}}"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

---

### Operation: Create Snapshot

#### Pre-flight

- Verify disk exists and is attached (recommended for consistency).

#### Execution — CLI

```bash
aliyun ecs CreateSnapshot \
  --DiskId "{{user.disk_id}}" \
  --SnapshotName "{{user.snapshot_name}}"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until `Status` is `accomplished`:

```bash
aliyun ecs DescribeSnapshots \
  --RegionId "{{user.region}}" \
  --SnapshotIds '["{{output.snapshot_id}}"]' \
  --waiter expr='Snapshots.Snapshot[0].Status' to=accomplished timeout=600 interval=10
```

---

### Operation: Delete Snapshot

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of snapshot `{{user.snapshot_id}}`.

#### Execution — CLI

```bash
aliyun ecs DeleteSnapshot --SnapshotId "{{user.snapshot_id}}"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

---

### Operation: Create Security Group

#### Execution — CLI

```bash
aliyun ecs CreateSecurityGroup \
  --RegionId "{{user.region}}" \
  --SecurityGroupName "{{user.security_group_name}}" \
  --VpcId "{{user.vpc_id}}"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until security group exists:

```bash
aliyun ecs DescribeSecurityGroups \
  --RegionId "{{user.region}}" \
  --SecurityGroupIds '["{{output.security_group_id}}"]' \
  --waiter expr='SecurityGroups.SecurityGroup[0].SecurityGroupId' to={{output.security_group_id}} timeout=60 interval=5
```

---

### Operation: Authorize Security Group Rule

#### Pre-flight

- Verify security group exists and is in the correct VPC.
- **Security Warning:** Avoid `SourceCidrIp: 0.0.0.0/0` for production. Restrict to specific IPs or security groups.

#### Execution — CLI

> **Note:** The old flat parameters (`--IpProtocol`, `--PortRange`, etc.) are deprecated. Use `--Permissions` array format.

```bash
# Example: Allow SSH from a specific IP (recommended)
aliyun ecs AuthorizeSecurityGroup \
  --SecurityGroupId "{{user.security_group_id}}" \
  --RegionId "{{user.region}}" \
  --Permissions '[{"IpProtocol":"tcp","PortRange":"22/22","SourceCidrIp":"203.0.113.10/32","Policy":"accept","Priority":"1"}]'

# Example: Allow HTTP from anywhere (use with caution)
aliyun ecs AuthorizeSecurityGroup \
  --SecurityGroupId "{{user.security_group_id}}" \
  --RegionId "{{user.region}}" \
  --Permissions '[{"IpProtocol":"tcp","PortRange":"80/80","SourceCidrIp":"0.0.0.0/0","Policy":"accept","Priority":"2"}]'
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

---

### Operation: Revoke Security Group Rule

#### Pre-flight

- Verify security group exists.
- Obtain the `SecurityGroupRuleId` from `DescribeSecurityGroupAttribute` or from the `AuthorizeSecurityGroup` response.

#### Execution — CLI

```bash
# Revoke by rule ID (recommended)
aliyun ecs RevokeSecurityGroup \
  --SecurityGroupId "{{user.security_group_id}}" \
  --RegionId "{{user.region}}" \
  --SecurityGroupRuleId.1 "{{user.rule_id}}"

# Revoke by Permissions array (fallback)
aliyun ecs RevokeSecurityGroup \
  --SecurityGroupId "{{user.security_group_id}}" \
  --RegionId "{{user.region}}" \
  --Permissions '[{"IpProtocol":"tcp","PortRange":"22/22","SourceCidrIp":"0.0.0.0/0","Policy":"accept"}]'
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

---

### Operation: Describe Security Group Attribute

#### Execution — CLI

```bash
aliyun ecs DescribeSecurityGroupAttribute \
  --SecurityGroupId "{{user.security_group_id}}" \
  --RegionId "{{user.region}}"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

---

### Operation: Security Group Compliance Check (安全组合规检查)

| Trigger | Purpose | CLI | Key Check |
|---------|---------|-----|-----------|
| "安全组检查", "合规审计" | 检测 `0.0.0.0/0` 开放的高危端口 | `aliyun ecs DescribeSecurityGroupAttribute` | `SourceCidrIp` + `PortRange` ∈ {22,3389,3306,1433,6379,27017} |

**Severity:** Critical rules → `SourceCidrIp="0.0.0.0/0"` + high-risk port; Immediate remediation.  
**Full runbook:** [安全组合规检查](references/sg-compliance-check.md)

---

### Operation: Multi-Metric Anomaly Inspection

| Trigger | Purpose | CLI | Key Thresholds |
|---------|---------|-----|----------------|
| "异常检测", "告警分析" | 跨指标复合异常（CPU+Memory, Disk+IOPS） | `aliyun cms DescribeMetricList` — `CPUUtilization`, `MemoryUsage`, `DiskUsage` | CPU>90% AND Mem>85% 5min → Critical |

**Auto-Actions:** CPU-Memory 双高 → Auto-scale; 磁盘-IO 瓶颈 → 扩容 SSD.  
**Full runbook:** [多指标异常巡检](references/multi-metric-anomaly.md)

---

### Operation: Idle Resource Detection (闲置资源智能识别)

| Trigger | Purpose | CLI | Key Dimensions |
|---------|---------|-----|----------------|
| "闲置实例", "成本优化" | 识别 30天无活动实例 | `aliyun cms DescribeMetricList` — `InternetOutRate`, `CPUUtilization` + ActionTrail | 30d 无流量 + 无CPU + 无API → 疑似闲置 |

**Classification:** 活跃 / 低频 / 疑似闲置 / 确定闲置 → 保留 / 降配 / 回收.  
**Full runbook:** [闲置资源检测](references/idle-resource-detection.md)

---

### Operation: Cost Visualization Report (成本可视化报告)

| Trigger | Purpose | CLI | Key Metrics |
|---------|---------|-----|-------------|
| "成本分析", "费用报告" | ECS 实例+磁盘+快照月度费用 | `aliyun ecs DescribeInstances` + `DescribeDisks` + `bssapi QueryBill` | 实例费 / 磁盘费 / 流量费 / 快照费 |

**Optimization:** Right-size 低利用率实例 → 节省 60-80%; RI 长期实例 → 节省 30-85%.  
**Full runbook:** [成本可视化报告](references/cost-visualization.md)

---

### Operation: Predictive Capacity Analysis (预测性容量分析)

| Trigger | Purpose | CLI | Prediction |
|---------|---------|-----|------------|
| "容量预警", "趋势分析" | 基于30天历史预测未来7天容量 | `aliyun cms DescribeMetricList` — `CPUUtilization` (30d, Period=3600) | 线性回归: `current + daily_growth × days` |

**Risk Levels:** ≤7d to threshold → Critical; ≤14d → Warning.  
**Full runbook:** [预测性容量分析](references/predictive-capacity.md)

---

### Operation: LLM-Assisted Diagnosis (LLM辅助诊断)

| Trigger | Purpose | Workflow | Data Inputs |
|---------|---------|----------|-------------|
| "诊断", "故障排查" | LLM 分析 ECS 状态+监控+日志生成修复建议 | 收集数据 → 构建 Prompt → LLM 分析 → 输出报告 | `DescribeInstances` (Status), `cms` (CPU/Mem), 用户描述 |

**Problem Types:** 无法连接 / 性能问题 / 磁盘满 / 登录失败 / 应用崩溃.  
**Full runbook:** [LLM辅助诊断](references/llm-diagnosis.md)

---

### Operation: Add Tags to Resource

#### Execution — CLI

```bash
aliyun ecs AddTags \
  --ResourceType instance \
  --ResourceId "{{user.instance_id}}" \
  --Tags '[{"Key":"Environment","Value":"Production"},{"Key":"Owner","Value":"DevOps"}]'
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

---

### Operation: Describe Tags

#### Execution — CLI

```bash
aliyun ecs DescribeTags \
  --RegionId "{{user.region}}" \
  --ResourceType instance \
  --ResourceId "{{user.instance_id}}"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

---

### Operation: Remove Tags from Resource

#### Execution — CLI

```bash
aliyun ecs RemoveTags \
  --ResourceType instance \
  --ResourceId "{{user.instance_id}}" \
  --TagKey.1 "Environment" \
  --TagKey.2 "Owner"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

---

### Operation: Resize Disk

#### Pre-flight

- Verify disk exists.
- For system disks, instance must be `Stopped`.
- For data disks, can resize while `In_use` (online expansion) or `Available`.
- New size must be larger than current size.

#### Execution — CLI

```bash
aliyun ecs ResizeDisk \
  --DiskId "{{user.disk_id}}" \
  --NewSize "{{user.new_size}}"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

> **Post-resize:** After resizing the cloud disk, you must extend the file system inside the OS. This is an OS-level operation, not an ECS API operation.

---

### Operation: Replace System Disk

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: replacing the system disk will erase all data on it.
- Instance must be in `Stopped` state.
- Create a snapshot of the current system disk as backup before proceeding.

#### Execution — CLI

```bash
aliyun ecs ReplaceSystemDisk \
  --InstanceId "{{user.instance_id}}" \
  --ImageId "{{user.image_id}}"
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until instance status returns to `Stopped` (then user must start it):

```bash
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --waiter expr='Instances.Instance[0].Status' to=Stopped timeout=300 interval=5
```

---

### Operation: Connectivity Diagnostics

When a user reports "cannot connect to ECS", follow this decision tree:

#### Step 1: Verify Instance State

```bash
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --output cols=Status,InstanceName rows=Instances.Instance[0].{Status,InstanceName}
```

- If `Status` != `Running` → Instance is not running. Start it or investigate why it stopped.

#### Step 2: Verify Network Configuration

```bash
# Check public IP / EIP
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --output cols=PublicIp,Eip,PrivateIp \
  rows='Instances.Instance[0].{PublicIp:PublicIpAddress.IpAddress[0],Eip:EipAddress.IpAddress,PrivateIp:VpcAttributes.PrivateIpAddress.IpAddress[0]}'
```

- No public IP and no EIP → Instance is not accessible from the internet. Need to bind EIP or use a jump server.

#### Step 3: Verify Security Group Rules

```bash
# Get security group IDs attached to instance
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --output cols=SecurityGroupIds rows=Instances.Instance[0].SecurityGroupIds

# Check inbound rules for the security group
aliyun ecs DescribeSecurityGroupAttribute \
  --SecurityGroupId "{{user.security_group_id}}" \
  --RegionId "{{user.region}}"
```

- Verify the required port (22 for SSH, 3389 for RDP) is allowed from the source IP.
- Verify no `drop` rule with higher priority is blocking the traffic.

#### Step 4: Verify VPC / VSwitch Configuration

```bash
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --output cols=VpcId,VSwitchId rows=Instances.Instance[0].{VpcId,VSwitchId}
```

- Delegate to `alicloud-vpc-ops` if VPC/VSwitch configuration is suspect.

#### Step 5: Check CloudMonitor Metrics

```bash
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

- High CPU / memory may indicate the OS is unresponsive, not a network issue.

#### Step 6: Escalation

If all above checks pass but connectivity still fails:
- Collect `RequestId` from all API calls.
- Check instance system logs via ECS console (VNC) if available.
- Contact Alibaba Cloud support with `RequestId`, instance ID, and timestamp.

---



---

### Operation: Run Command (Cloud Assistant)

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance exists | `aliyun ecs DescribeInstances` | `{{user.instance_id}}` found | HALT |
| Instance status | Status == `Running` | Cloud Assistant requires Running instance | Start instance first |
| Cloud Assistant installed | `aliyun ecs DescribeCloudAssistantStatus --RegionId {{user.region}} --InstanceIds '["{{user.instance_id}}"]'` | `CloudAssistantStatus` == `true` | Install Cloud Assistant agent |
| Command type | `{{user.command_type}}` | `RunShellScript`, `RunBatScript`, `RunPowerShellScript` | Default to `RunShellScript` |

#### Execution — CLI

```bash
# Run a shell command on a Linux instance
aliyun ecs RunCommand \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --CommandContent "echo 'Hello from Cloud Assistant' && uname -a" \
  --Type "RunShellScript" \
  --Name "diagnostic-check"

# Run a PowerShell command on a Windows instance
aliyun ecs RunCommand \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --CommandContent "Get-Process | Sort-Object CPU -Descending | Select-Object -First 5" \
  --Type "RunPowerShellScript" \
  --Name "cpu-top-processes"

# Run with timeout (seconds) and working directory
aliyun ecs RunCommand \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --CommandContent "cd /var/log && tar czf /tmp/logs.tar.gz ." \
  --Type "RunShellScript" \
  --Name "collect-logs" \
  --Timeout 300 \
  --WorkingDir "/var/log"
```

> **Security Note:** Commands run with root/Administrator privileges. Validate command content to prevent accidental damage. Avoid commands that expose secrets in output.

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

1. Read `{{output.invoke_id}}` from `$.InvokeId`.
2. Poll **DescribeInvocationResults** until status is terminal (`Success`, `Failed`, `Timeout`, `Cancelled`):

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun ecs DescribeInvocationResults \
    --RegionId "{{user.region}}" \
    --InvokeId "{{output.invoke_id}}" \
    --InstanceId "{{user.instance_id}}" \
    --output cols=InvocationStatus rows=Invocation.InvocationResults.InvocationResult[0].InvocationStatus)
  echo "Attempt $i: Status=$STATUS"
  case "$STATUS" in
    Success) echo "Command executed successfully"; break ;;
    Failed|Timeout|Cancelled) echo "Command failed with status: $STATUS"; break ;;
  esac
  sleep 5
done
```

3. Extract output (base64-decoded):

```bash
# Get command output (base64 encoded)
aliyun ecs DescribeInvocationResults \
  --RegionId "{{user.region}}" \
  --InvokeId "{{output.invoke_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --output cols=Output,ExitCode rows=Invocation.InvocationResults.InvocationResult[0].{Output,ExitCode}

# Decode base64 output
OUTPUT=$(aliyun ecs DescribeInvocationResults \
  --RegionId "{{user.region}}" \
  --InvokeId "{{output.invoke_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --output cols=Output rows=Invocation.InvocationResults.InvocationResult[0].Output)
echo "$OUTPUT" | base64 -d
```

#### Failure Recovery

| Error pattern | Agent Action |
|---------------|--------------|
| `InvalidInstanceId.NotFound` | Verify instance ID and region |
| `InvalidParameter.CommandContent` | Command exceeds 16KB limit or contains invalid characters |
| `CloudAssistantNotInstalled` | Install Cloud Assistant agent on the instance |
| `InvocationStatus` = `Failed` | Check `Output` (base64 decode) and `ExitCode` for OS-level errors |
| `InvocationStatus` = `Timeout` | Increase `--Timeout` value; check if command is stuck |

---

### Operation: Invoke Command (Cloud Assistant)

Use this when you have a **pre-created command** (via `CreateCommand`) and want to invoke it on instances.

#### Execution — CLI

```bash
aliyun ecs InvokeCommand \
  --RegionId "{{user.region}}" \
  --CommandId "{{user.command_id}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --Parameters '{"var1":"value1","var2":"value2"}'
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Same as **RunCommand** — poll `DescribeInvocationResults` with the returned `InvokeId`.

---

### Operation: Describe Invocation Results

#### Execution — CLI

```bash
# Query results for a specific invocation and instance
aliyun ecs DescribeInvocationResults \
  --RegionId "{{user.region}}" \
  --InvokeId "{{user.invoke_id}}" \
  --InstanceId "{{user.instance_id}}"

# Query all results for an invocation across multiple instances
aliyun ecs DescribeInvocationResults \
  --RegionId "{{user.region}}" \
  --InvokeId "{{user.invoke_id}}"

# Extract specific fields
aliyun ecs DescribeInvocationResults \
  --RegionId "{{user.region}}" \
  --InvokeId "{{user.invoke_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --output cols=InvokeId,InvocationStatus,ExitCode,StartTime,EndTime \
  rows=Invocation.InvocationResults.InvocationResult[0].{InvokeId,InvocationStatus,ExitCode,StartTime,EndTime}
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Invoke ID | `$.Invocation.InvocationResults.InvocationResult[].InvokeId` | Invocation identifier |
| Instance ID | `$.Invocation.InvocationResults.InvocationResult[].InstanceId` | Target instance |
| Status | `$.Invocation.InvocationResults.InvocationResult[].InvocationStatus` | Pending, Running, Success, Failed, Timeout, Cancelled |
| Exit Code | `$.Invocation.InvocationResults.InvocationResult[].ExitCode` | OS exit code (0 = success) |
| Output | `$.Invocation.InvocationResults.InvocationResult[].Output` | Base64-encoded stdout/stderr |
| Start Time | `$.Invocation.InvocationResults.InvocationResult[].StartTime` | ISO 8601 |
| End Time | `$.Invocation.InvocationResults.InvocationResult[].EndTime` | ISO 8601 |
| Error Info | `$.Invocation.InvocationResults.InvocationResult[].ErrorInfo` | Error details if failed |

> **Output Decoding:** The `Output` field is base64-encoded. Decode before presenting to user:
> ```bash
> echo "$OUTPUT" | base64 -d
> ```

---

### Operation: Stop Invocation

#### Execution — CLI

```bash
aliyun ecs StopInvocation \
  --RegionId "{{user.region}}" \
  --InvokeId "{{user.invoke_id}}" \
  --InstanceIds '["{{user.instance_id}}"]'
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

> **Note:** Only invocations in `Pending` or `Running` status can be stopped.

---

### Operation: Send File (Cloud Assistant)

Send a local file to one or more ECS instances via Cloud Assistant.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance exists and Running | `aliyun ecs DescribeInstances` | Status == `Running` | Start instance |
| Cloud Assistant installed | `aliyun ecs DescribeCloudAssistantStatus` | `CloudAssistantStatus` == `true` | Install agent |
| File exists locally | `test -f {{user.local_file}}` | File exists | HALT |
| File size | `stat -f%z {{user.local_file}}` | < 32MB | Split file or use alternative method |

#### Execution — CLI

```bash
# Send a file to an instance
aliyun ecs SendFile \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --Name "deploy-script" \
  --Description "Deployment script for app v2.0" \
  --TargetDir "/tmp" \
  --FileOwner "root" \
  --FileGroup "root" \
  --FileMode "0755" \
  --Content "$(base64 -i /path/to/local/script.sh)" \
  --Overwrite true

# Send a configuration file
aliyun ecs SendFile \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --Name "app-config" \
  --TargetDir "/etc/myapp" \
  --FileOwner "myapp" \
  --FileGroup "myapp" \
  --FileMode "0644" \
  --Content "$(base64 -i /path/to/local/config.yaml)" \
  --Overwrite true
```

> **Note:** The `Content` field must be base64-encoded file content.

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

1. Read `{{output.invoke_id}}` from `$.InvokeId`.
2. Poll **DescribeSendFileResults** until status is terminal:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun ecs DescribeSendFileResults \
    --RegionId "{{user.region}}" \
    --InvokeId "{{output.invoke_id}}" \
    --InstanceId "{{user.instance_id}}" \
    --output cols=FileStatus rows=SendFileResults.SendFileResult[0].FileStatus)
  echo "Attempt $i: Status=$STATUS"
  case "$STATUS" in
    Success) echo "File sent successfully"; break ;;
    Failed|PartialFailed) echo "File transfer failed: $STATUS"; break ;;
  esac
  sleep 5
done
```

#### Failure Recovery

| Error pattern | Agent Action |
|---------------|--------------|
| `InvalidParameter.Content` | Content exceeds 32MB or is not valid base64 |
| `InvalidParameter.FileMode` | File mode must be valid octal (e.g., `0755`, `0644`) |
| `FileStatus` = `Failed` | Check target directory permissions and disk space |
| `FileStatus` = `PartialFailed` | Some instances succeeded, some failed. Retry on failed instances |

---

### Operation: Describe Send File Results

#### Execution — CLI

```bash
# Query file transfer results
aliyun ecs DescribeSendFileResults \
  --RegionId "{{user.region}}" \
  --InvokeId "{{user.invoke_id}}" \
  --InstanceId "{{user.instance_id}}"

# Extract specific fields
aliyun ecs DescribeSendFileResults \
  --RegionId "{{user.region}}" \
  --InvokeId "{{user.invoke_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --output cols=FileStatus,TargetDir,FileOwner,FileMode \
  rows=SendFileResults.SendFileResult[0].{FileStatus,TargetDir,FileOwner,FileMode}
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Invoke ID | `$.SendFileResults.SendFileResult[].InvokeId` | File transfer invocation ID |
| Instance ID | `$.SendFileResults.SendFileResult[].InstanceId` | Target instance |
| File Status | `$.SendFileResults.SendFileResult[].FileStatus` | Pending, Running, Success, Failed, PartialFailed |
| Target Dir | `$.SendFileResults.SendFileResult[].TargetDir` | Destination directory |
| File Owner | `$.SendFileResults.SendFileResult[].FileOwner` | Owner on target |
| File Group | `$.SendFileResults.SendFileResult[].FileGroup` | Group on target |
| File Mode | `$.SendFileResults.SendFileResult[].FileMode` | Permissions on target |
| Start Time | `$.SendFileResults.SendFileResult[].StartTime` | ISO 8601 |
| End Time | `$.SendFileResults.SendFileResult[].EndTime` | ISO 8601 |

---

### Operation: Describe Cloud Assistant Status

Check whether Cloud Assistant agent is installed and running on instances.

#### Execution — CLI

```bash
aliyun ecs DescribeCloudAssistantStatus \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]'

# Extract status
aliyun ecs DescribeCloudAssistantStatus \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --output cols=InstanceId,CloudAssistantStatus \
  rows=InstanceCloudAssistantStatusSet.InstanceCloudAssistantStatus[].{InstanceId,CloudAssistantStatus}
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Instance ID | `$.InstanceCloudAssistantStatusSet.InstanceCloudAssistantStatus[].InstanceId` | Instance identifier |
| Cloud Assistant Status | `$.InstanceCloudAssistantStatusSet.InstanceCloudAssistantStatus[].CloudAssistantStatus` | `true` = installed and running, `false` = not installed |
| Cloud Assistant Version | `$.InstanceCloudAssistantStatusSet.InstanceCloudAssistantStatus[].CloudAssistantVersion` | Agent version |
| OSType | `$.InstanceCloudAssistantStatusSet.InstanceCloudAssistantStatus[].OSType` | Linux / Windows |

> **If Cloud Assistant is not installed:** Use `aliyun ecs InstallCloudAssistant` or install manually via user-data / custom image.

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to ECS.

### 安全 (Security)

| Assessment Area | Guidance | CLI Verification |
|-----------------|----------|-----------------|
| **IAM Permissions** | Never use `AdministratorAccess`. Required minimum: `ecs:Describe*`, `ecs:Create*`, `ecs:Delete*` scoped to `acs:ecs:*:*:instance/*` | Review RAM policies attached to the executing user/role |
| **Credential Security** | Use `{{env.*}}` placeholders only. Must mask credentials to `****` (first 4 chars + `****`) when outputting to console, logs, or error messages. Never print or log credentials. Rotate AccessKeys every 90 days. | `test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" \|\| echo "MISSING"` |
| **Network Isolation** | Use VPC endpoints for API calls. Avoid public endpoints. Restrict security group inbound rules to minimum CIDRs. | `aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId <sg-id>` — scan for `0.0.0.0/0` |
| **Data at Rest** | Enable disk encryption (`Encrypted=true`) for all data disks. Use `KMSKeyId` for custom keys. | `aliyun ecs DescribeDisks` → check `Encrypted` and `KMSKeyId` fields |
| **Instance Security** | Restrict SSH/RDP access to specific source IPs via security group rules. Avoid `0.0.0.0/0` on ports 22/3389. | `aliyun ecs DescribeSecurityGroupAttribute` → verify no `0.0.0.0/0` on sensitive ports |

### 稳定 (Stability)

| Assessment Area | Guidance | Implementation |
|-----------------|----------|----------------|
| **面向失败的架构设计** | Deploy instances across multiple Availability Zones. Use Auto Scaling groups with health checks. Load balance with SLB. | Create instances in `≥ 2` zones. Use `RunInstances` with `MultiAzPolicy` parameter. |
| **面向精细的运维管控** | Tag all instances (`Environment`, `Owner`, `Project`). Monitor CPU, memory, disk I/O via CMS. Set alert thresholds. | `aliyun ecs AddTags` on creation. CMS `DescribeMetricAlarmList` for alerting. |
| **面向风险的应急快恢** | Backup via `CreateSnapshot` before any destructive operation. Test restore periodically. Document RTO/RPO targets. | **RTO:** < 15 min for single instance restart. **RPO:** < 4 hours (snapshot frequency). |
| **Multi-AZ Deployment** | Distribute instances across zones to mitigate single-zone failure. Use SLB to distribute traffic. | `aliyun ecs DescribeZones` → create instances in `cn-hangzhou-a` AND `cn-hangzhou-b`. |

#### 应急快恢 Runbook

```
Phase 1: Verify — Check instance status, public IP, security group, VPC config
Phase 2: Restore — Replace system disk from snapshot OR restore from backup
Phase 3: Validate — Confirm connectivity, application health, data integrity
```

### 成本 (Cost)

| Billing Model | Best For | Savings vs Pay-As-You-Go |
|--------------|----------|-------------------------|
| **按量付费** | Dev/test, short-term, unpredictable workloads | N/A |
| **包年包月** | Production, stable workloads (≥ 1 month) | Up to 85% |
| **抢占式实例 (Spot)** | Fault-tolerant batch/spot workloads | Up to 90% |
| **预留实例** | Predictable 24/7 workloads (1yr/3yr) | Up to 74% |

#### Waste Detection
- **Idle instances:** CPU < 10% AND network I/O < 1 MB/s for 7+ consecutive days → recommend downgrade or stop
- **Orphaned snapshots:** Snapshots without active images/disks referencing them → recommend deletion
- **Unattached disks:** Disks with `Status: Available` for 30+ days → recommend attach or delete
- **Oversized instances:** Actual memory < 50% of provisioned for 14+ days → recommend right-sizing

### 效率 (Efficiency)

| Pattern | Guidance |
|---------|----------|
| **Batch Operations** | Use `RunInstances` for ≥ 3 instances. Avoid serial `CreateInstance` calls. |
| **CI/CD Integration** | All SKILL.md outputs are JSON by default. Compatible with jq/yq for pipeline parsing. Store in CI artifacts. |
| **Cloud Assistant** | Use `SendFile` + `RunCommand` for remote execution. Eliminates SSH key management overhead. |
| **Automation** | Tag-based lifecycle: tag instances with `AutoShutdown=true` for scheduled stop actions. |

### 性能 (Performance)

| Metric | CMS Namespace | Scale Up Threshold | Scale Down Threshold | Monitoring Window |
|--------|--------------|-------------------|---------------------|-------------------|
| CPUUtilization | `acs_ecs_dashboard` | > 80% | < 30% | 5 min avg |
| MemoryUsage | `acs_ecs_dashboard` | > 85% | < 50% | 5 min avg |
| InternalBandwidth | `acs_ecs_dashboard` | > 70% | < 40% | 5 min avg |
| DiskUsage | `acs_ecs_dashboard` | > 90% | < 70% | 5 min avg |

**Key guidance:**
- Use `cloud_essd` PL1+ disks for I/O-intensive workloads; benchmark expected IOPS per disk category.
- Enable Auto Scaling with `min`, `max`, `desired` capacity. Test scale-out by simulating traffic spikes.
- Monitor `InternalBandwidthRX`/`InternalBandwidthTX` for inter-zone bottlenecks.

## Prerequisites

见 [执行环境配置](../alicloud-skill-generator/references/execution-environment.md)

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)
- [Prompt Examples](references/prompt-examples.md) — 自然语言提示词示例，开箱即用
- [Batch Operations](references/batch-operations.md) — 批量并行操作模板
- [Observability](references/observability.md) — 可观测性联动规则
- [API Call Counter](https://github.com/aliyun-skill-runner/alicloud-skill-generator/templates/api-call-counter.md) — API 调用计数集成

## Operational Best Practices

- **Least privilege:** RAM policies scoped to required ECS APIs only.
- **Availability:** Deploy across multiple zones for HA; use Auto Scaling groups.
- **Cost:** Use spot instances for non-critical workloads; right-size instance types.
- **Security:** Restrict security group rules to minimum required ports/CIDRs.
- **Backup:** Create regular snapshots for critical disks.
- **Tagging:** Enforce mandatory tags (`Environment`, `Owner`, `Project`) on all resources for cost allocation and access control.
- **Naming:** Use consistent naming conventions (e.g., `{{project}}-{{env}}-{{role}}-{{seq}}`).
- **Encryption:** Enable disk encryption (`Encrypted=true`) for all data disks containing sensitive data.
- **DryRun:** Use `DryRun=true` on `CreateInstance` and `RunInstances` to validate parameters before actual creation:
  ```bash
  aliyun ecs CreateInstance ... --DryRun true
  ```
- **Recycle Bin Awareness:** Deleted instances enter Recycle Bin by default. Set `--Force true` only when permanent deletion is explicitly required.
- **UserData Validation:** Always base64-encode UserData. Test initialization scripts in a staging environment before production deployment.

---



---



---


