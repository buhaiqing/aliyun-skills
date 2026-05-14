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

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field value in console output, debug messages, error messages, or logs.
>
> **Masking rules across all execution paths:**
> | Execution Path | Safe Pattern | Unsafe Pattern |
> |----------------|-------------|----------------|
> | Console output | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>` | Raw credential value in output |
> | Error messages | `Error: API call failed (credential omitted)` | Error containing raw credential value |
> | Log files | `[INFO] Credentials: Secret=***` | `[INFO] AK Secret: LTAI5t...` |
> | Verification | `test -n "$var" && echo "Secret is set"` (existence check only) | `echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET` |
> | JIT Go SDK | env read via `os.Getenv(...)` is safe; never print `Config` struct | `fmt.Printf("Config: %+v", config)` |
> | Debug/verbose | `Debug mode may expose credentials (use with caution)` | Un-masked credential in debug output |
>
> **Credential verification MUST check existence only**, never echo the value. This applies to ALL execution flows (SDK, CLI, and debugging scripts).

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

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-14 | Initial ECS skill with dual-path (CLI + SDK) support |
| 2.0.0 | 2026-05-14 | Added missing operations (RevokeSecurityGroup, Tag management, ResizeDisk, ReplaceSystemDisk), enhanced troubleshooting decision tree, added connectivity diagnostics, corrected DeleteInstance Force semantics, added recycle bin notes, added disk encryption and UserData docs |
| 2.1.0 | 2026-05-14 | Added Cloud Assistant operations (RunCommand, InvokeCommand, SendFile, StopInvocation, DescribeInvocationResults, DescribeSendFileResults, DescribeCloudAssistantStatus); added prompt-examples.md with 50+ natural language prompt examples |

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

#### Execution — JIT Go SDK (Fallback Path)

```go
package main

import (
	"fmt"
	"os"
	"time"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	ecs "github.com/alibabacloud-go/ecs-20140526/v4/client"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
		RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	}

	c, err := ecs.NewClient(config)
	if err != nil {
		panic(err)
	}

	req := &ecs.CreateInstanceRequest{
		RegionId:              tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
		ZoneId:                tea.String(os.Getenv("ZONE_ID")),
		ImageId:               tea.String(os.Getenv("IMAGE_ID")),
		InstanceType:          tea.String(os.Getenv("INSTANCE_TYPE")),
		SecurityGroupId:       tea.String(os.Getenv("SECURITY_GROUP_ID")),
		VSwitchId:             tea.String(os.Getenv("VSWITCH_ID")),
		InstanceName:          tea.String(os.Getenv("INSTANCE_NAME")),
		InternetMaxBandwidthOut: tea.Int(1),
		KeyPairName:           tea.String(os.Getenv("KEY_PAIR_NAME")),
	}

	resp, err := c.CreateInstance(req)
	if err != nil {
		panic(err)
	}

	instanceId := tea.ToString(resp.Body.InstanceId)
	fmt.Printf("Created instance: %s\n", instanceId)

	// Poll until Running
	for i := 0; i < 60; i++ {
		descReq := &ecs.DescribeInstancesRequest{
			RegionId:    tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
			InstanceIds: tea.String(`["` + instanceId + `"]`),
		}
		descResp, err := c.DescribeInstances(descReq)
		if err != nil {
			panic(err)
		}
		instances := descResp.Body.Instances.Instance
		if len(instances) > 0 && tea.ToString(instances[0].Status) == "Running" {
			fmt.Println("Instance is Running")
			break
		}
		time.Sleep(5 * time.Second)
	}
}
```

> **UserData Note:** To pass initialization scripts, add `UserData` field with base64-encoded content:
> ```go
> import "encoding/base64"
> userData := base64.StdEncoding.EncodeToString([]byte("#!/bin/bash\necho 'hello' > /tmp/setup.log"))
> req.UserData = tea.String(userData)
> ```

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

#### Execution — JIT Go SDK

```go
req := &ecs.DescribeInstancesRequest{
	RegionId:    tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InstanceIds: tea.String(`["` + os.Getenv("INSTANCE_ID") + `"]`),
}
resp, err := c.DescribeInstances(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.RunInstancesRequest{
	RegionId:              tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	ZoneId:                tea.String(os.Getenv("ZONE_ID")),
	ImageId:               tea.String(os.Getenv("IMAGE_ID")),
	InstanceType:          tea.String(os.Getenv("INSTANCE_TYPE")),
	SecurityGroupId:       tea.String(os.Getenv("SECURITY_GROUP_ID")),
	VSwitchId:             tea.String(os.Getenv("VSWITCH_ID")),
	InstanceName:          tea.String(os.Getenv("INSTANCE_NAME")),
	Amount:                tea.Int32(2),
	InternetMaxBandwidthOut: tea.Int(1),
	KeyPairName:           tea.String(os.Getenv("KEY_PAIR_NAME")),
}
resp, err := c.RunInstances(req)
// Parse InstanceIdSets.InstanceIdSet[] from response
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.ModifyInstanceAttributeRequest{
	InstanceId:   tea.String(os.Getenv("INSTANCE_ID")),
	InstanceName: tea.String(os.Getenv("NEW_INSTANCE_NAME")),
}
resp, err := c.ModifyInstanceAttribute(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.DescribeImagesRequest{
	RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	ImageOwnerAlias: tea.String("system"),
	OSType:          tea.String("Linux"),
}
resp, err := c.DescribeImages(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.StartInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.StartInstance(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.StopInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	ForceStop:  tea.Bool(false),
}
resp, err := c.StopInstance(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.RebootInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	ForceStop:  tea.Bool(false),
}
resp, err := c.RebootInstance(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.DeleteInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	Force:      tea.Bool(false),
}
resp, err := c.DeleteInstance(req)
```

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

#### Execution — JIT Go SDK

```go
size, _ := strconv.Atoi(os.Getenv("DISK_SIZE"))
req := &ecs.CreateDiskRequest{
	RegionId:     tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	ZoneId:       tea.String(os.Getenv("ZONE_ID")),
	DiskName:     tea.String(os.Getenv("DISK_NAME")),
	Size:         tea.Int32(int32(size)),
	DiskCategory: tea.String(os.Getenv("DISK_CATEGORY")),
}
resp, err := c.CreateDisk(req)
```

> **Disk Encryption:** For compliance, enable encryption with:
> ```bash
> aliyun ecs CreateDisk ... --Encrypted true --KMSKeyId "alias/acs/ecs"
> ```
> ```go
> req.Encrypted = tea.Bool(true)
> req.KMSKeyId = tea.String("alias/acs/ecs")
> ```

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

#### Execution — JIT Go SDK

```go
req := &ecs.AttachDiskRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	DiskId:     tea.String(os.Getenv("DISK_ID")),
}
resp, err := c.AttachDisk(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.DetachDiskRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	DiskId:     tea.String(os.Getenv("DISK_ID")),
}
resp, err := c.DetachDisk(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.DeleteDiskRequest{
	DiskId: tea.String(os.Getenv("DISK_ID")),
}
resp, err := c.DeleteDisk(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.CreateSnapshotRequest{
	DiskId:       tea.String(os.Getenv("DISK_ID")),
	SnapshotName: tea.String(os.Getenv("SNAPSHOT_NAME")),
}
resp, err := c.CreateSnapshot(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.DeleteSnapshotRequest{
	SnapshotId: tea.String(os.Getenv("SNAPSHOT_ID")),
}
resp, err := c.DeleteSnapshot(req)
```

---

### Operation: Create Security Group

#### Execution — CLI

```bash
aliyun ecs CreateSecurityGroup \
  --RegionId "{{user.region}}" \
  --SecurityGroupName "{{user.security_group_name}}" \
  --VpcId "{{user.vpc_id}}"
```

#### Execution — JIT Go SDK

```go
req := &ecs.CreateSecurityGroupRequest{
	RegionId:          tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	SecurityGroupName: tea.String(os.Getenv("SECURITY_GROUP_NAME")),
	VpcId:             tea.String(os.Getenv("VPC_ID")),
}
resp, err := c.CreateSecurityGroup(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.AuthorizeSecurityGroupRequest{
	SecurityGroupId: tea.String(os.Getenv("SECURITY_GROUP_ID")),
	RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	Permissions: []*ecs.AuthorizeSecurityGroupRequestPermissions{
		{
			IpProtocol:   tea.String("tcp"),
			PortRange:    tea.String("22/22"),
			SourceCidrIp: tea.String(os.Getenv("SOURCE_CIDR_IP")), // e.g., 203.0.113.10/32
			Policy:       tea.String("accept"),
			Priority:     tea.String("1"),
			Description:  tea.String("SSH access from admin IP"),
		},
	},
}
resp, err := c.AuthorizeSecurityGroup(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.RevokeSecurityGroupRequest{
	SecurityGroupId:       tea.String(os.Getenv("SECURITY_GROUP_ID")),
	RegionId:              tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	SecurityGroupRuleId: []*string{
		tea.String(os.Getenv("RULE_ID")),
	},
}
resp, err := c.RevokeSecurityGroup(req)
```

---

### Operation: Describe Security Group Attribute

#### Execution — CLI

```bash
aliyun ecs DescribeSecurityGroupAttribute \
  --SecurityGroupId "{{user.security_group_id}}" \
  --RegionId "{{user.region}}"
```

#### Execution — JIT Go SDK

```go
req := &ecs.DescribeSecurityGroupAttributeRequest{
	SecurityGroupId: tea.String(os.Getenv("SECURITY_GROUP_ID")),
	RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
}
resp, err := c.DescribeSecurityGroupAttribute(req)
```

---

### Operation: Add Tags to Resource

#### Execution — CLI

```bash
aliyun ecs AddTags \
  --ResourceType instance \
  --ResourceId "{{user.instance_id}}" \
  --Tags '[{"Key":"Environment","Value":"Production"},{"Key":"Owner","Value":"DevOps"}]'
```

#### Execution — JIT Go SDK

```go
req := &ecs.AddTagsRequest{
	ResourceType: tea.String("instance"),
	ResourceId:   tea.String(os.Getenv("INSTANCE_ID")),
	Tags: []*ecs.AddTagsRequestTags{
		{Key: tea.String("Environment"), Value: tea.String("Production")},
		{Key: tea.String("Owner"), Value: tea.String("DevOps")},
	},
}
resp, err := c.AddTags(req)
```

---

### Operation: Describe Tags

#### Execution — CLI

```bash
aliyun ecs DescribeTags \
  --RegionId "{{user.region}}" \
  --ResourceType instance \
  --ResourceId "{{user.instance_id}}"
```

#### Execution — JIT Go SDK

```go
req := &ecs.DescribeTagsRequest{
	RegionId:     tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	ResourceType: tea.String("instance"),
	ResourceId:   tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeTags(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.RemoveTagsRequest{
	ResourceType: tea.String("instance"),
	ResourceId:   tea.String(os.Getenv("INSTANCE_ID")),
	TagKey:       []*string{tea.String("Environment"), tea.String("Owner")},
}
resp, err := c.RemoveTags(req)
```

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

#### Execution — JIT Go SDK

```go
newSize, _ := strconv.Atoi(os.Getenv("NEW_SIZE"))
req := &ecs.ResizeDiskRequest{
	DiskId:  tea.String(os.Getenv("DISK_ID")),
	NewSize: tea.Int32(int32(newSize)),
}
resp, err := c.ResizeDisk(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.ReplaceSystemDiskRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	ImageId:    tea.String(os.Getenv("IMAGE_ID")),
}
resp, err := c.ReplaceSystemDisk(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.RunCommandRequest{
	RegionId:      tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InstanceIds:   tea.String(`["` + os.Getenv("INSTANCE_ID") + `"]`),
	CommandContent: tea.String(os.Getenv("COMMAND_CONTENT")),
	Type:          tea.String(os.Getenv("COMMAND_TYPE")), // RunShellScript, RunBatScript, RunPowerShellScript
	Name:          tea.String(os.Getenv("COMMAND_NAME")),
	Timeout:       tea.Int64(60),
}
resp, err := c.RunCommand(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.InvokeCommandRequest{
	RegionId:    tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	CommandId:   tea.String(os.Getenv("COMMAND_ID")),
	InstanceIds: tea.String(`["` + os.Getenv("INSTANCE_ID") + `"]`),
	Parameters:  tea.String(`{"var1":"value1"}`),
}
resp, err := c.InvokeCommand(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.DescribeInvocationResultsRequest{
	RegionId:   tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InvokeId:   tea.String(os.Getenv("INVOKE_ID")),
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeInvocationResults(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.StopInvocationRequest{
	RegionId:    tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InvokeId:    tea.String(os.Getenv("INVOKE_ID")),
	InstanceIds: tea.String(`["` + os.Getenv("INSTANCE_ID") + `"]`),
}
resp, err := c.StopInvocation(req)
```

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

#### Execution — JIT Go SDK

```go
import "encoding/base64"
import "os"

fileContent, err := os.ReadFile(os.Getenv("LOCAL_FILE"))
if err != nil {
	panic(err)
}
encodedContent := base64.StdEncoding.EncodeToString(fileContent)

req := &ecs.SendFileRequest{
	RegionId:    tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InstanceIds: tea.String(`["` + os.Getenv("INSTANCE_ID") + `"]`),
	Name:        tea.String(os.Getenv("FILE_NAME")),
	Description: tea.String(os.Getenv("FILE_DESCRIPTION")),
	TargetDir:   tea.String(os.Getenv("TARGET_DIR")),
	FileOwner:   tea.String(os.Getenv("FILE_OWNER")),
	FileGroup:   tea.String(os.Getenv("FILE_GROUP")),
	FileMode:    tea.String(os.Getenv("FILE_MODE")),
	Content:     tea.String(encodedContent),
	Overwrite:   tea.Bool(true),
}
resp, err := c.SendFile(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.DescribeSendFileResultsRequest{
	RegionId:   tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InvokeId:   tea.String(os.Getenv("INVOKE_ID")),
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeSendFileResults(req)
```

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

#### Execution — JIT Go SDK

```go
req := &ecs.DescribeCloudAssistantStatusRequest{
	RegionId:    tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InstanceIds: tea.String(`["` + os.Getenv("INSTANCE_ID") + `"]`),
}
resp, err := c.DescribeCloudAssistantStatus(req)
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Instance ID | `$.InstanceCloudAssistantStatusSet.InstanceCloudAssistantStatus[].InstanceId` | Instance identifier |
| Cloud Assistant Status | `$.InstanceCloudAssistantStatusSet.InstanceCloudAssistantStatus[].CloudAssistantStatus` | `true` = installed and running, `false` = not installed |
| Cloud Assistant Version | `$.InstanceCloudAssistantStatusSet.InstanceCloudAssistantStatus[].CloudAssistantVersion` | Agent version |
| OSType | `$.InstanceCloudAssistantStatusSet.InstanceCloudAssistantStatus[].OSType` | Linux / Windows |

> **If Cloud Assistant is not installed:** Use `aliyun ecs InstallCloudAssistant` or install manually via user-data / custom image.

---

## Prerequisites

1. **Install `aliyun` CLI** (primary execution path):

   ```bash
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   aliyun version
   ```

2. **Bootstrap Go runtime** (for JIT SDK fallback):

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

3. **Configure Credentials**:

   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```

4. **Verify Configuration**:

   ```bash
   aliyun ecs DescribeRegions
   ```

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)
- [Prompt Examples](references/prompt-examples.md) — 自然语言提示词示例，开箱即用

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
