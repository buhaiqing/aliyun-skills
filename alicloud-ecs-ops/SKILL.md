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

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field value (including `ALIBABA_CLOUD_ACCESS_KEY_ID`) in console output, debug messages, error messages, or logs. If credential information must be displayed for debugging or troubleshooting purposes, use the masking format: show only the first 4 characters followed by `****` (e.g., `abcd****`). This masking rule applies to ALL output channels: stdout, stderr, log files, debug traces, error messages, and diagnostic reports.
>
> **Masking rules across all execution paths:**
> | Execution Path | Safe Pattern | Unsafe Pattern |
> |----------------|-------------|----------------|
> | Console output | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=abcd****` | Raw credential value in output |
> | Error messages | `Error: API call failed (credential omitted)` | Error containing raw credential value |
> | Log files | `[INFO] Credentials: Secret=abcd****` | `[INFO] AK Secret: LTAI5t...` |
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

### Operation: Security Group Compliance Check (安全组合规检查)

Detect high-risk security group configurations for security hardening and compliance audit.

#### High-Risk Patterns

| Pattern ID | Risk Type | Detection Rule | Severity | Remediation |
|------------|-----------|----------------|----------|-------------|
| 1 | **0.0.0.0/0开放高危端口** | `SourceCidrIp="0.0.0.0/0"` + 端口∈{22,3389,3306,1433,6379,27017} | 🔴 Critical | 限制源IP或删除规则 |
| 2 | **全通配规则** | `SourceCidrIp="0.0.0.0/0"` + `PortRange="-1/-1"` | 🔴 Critical | 立即删除或收紧 |
| 3 | **SSH全网开放** | TCP 22 端口对 `0.0.0.0/0` 开放 | 🔴 Critical | 改为固定IP或VPN |
| 4 | **RDP全网开放** | TCP 3389 端口对 `0.0.0.0/0` 开放 | 🔴 Critical | 改为固定IP或VPN |
| 5 | **数据库端口全网开放** | 3306/1433/6379/27017 对 `0.0.0.0/0` | 🔴 Critical | 仅允许应用服务器 |
| 6 | **规则过于宽松** | `Policy="accept"` + 无优先级限制 | 🟡 Medium | 添加优先级或收紧 |

#### Execution — CLI

```bash
# Step 1: Get all security groups
aliyun ecs DescribeSecurityGroups \
  --RegionId "{{user.region}}" \
  --output cols=SecurityGroupId,SecurityGroupName rows=SecurityGroups.SecurityGroup[]

# Step 2: Check each security group for high-risk rules
for sg_id in $(aliyun ecs DescribeSecurityGroups --RegionId "{{user.region}}" --output cols=SecurityGroupId rows=SecurityGroups.SecurityGroup[].SecurityGroupId | tail -n +2); do
  echo "Checking SecurityGroup: $sg_id"
  aliyun ecs DescribeSecurityGroupAttribute \
    --SecurityGroupId "$sg_id" \
    --RegionId "{{user.region}}" | \
  jq -r '.Permissions.Permission[] | 
    select(.SourceCidrIp == "0.0.0.0/0") | 
    select(.PortRange | test("^(22|3389|3306|1433|6379|27017|-1)/")) |
    "🔴 HIGH RISK: \(.IpProtocol) \(.PortRange) - \(.Policy)"
done
```

#### High-Risk Detection Script

```bash
#!/bin/bash
# check_sg_compliance.sh - Security Group Compliance Checker

REGION="{{user.region}}"
OUTPUT_FILE="sg-compliance-report.md"

echo "# 安全组合规检查报告" > "$OUTPUT_FILE"
echo "**检查时间:** $(date '+%Y-%m-%d %H:%M:%S')" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# High-risk ports
RISK_PORTS="22|3389|3306|1433|6379|27017"

# Get all security groups
SGs=$(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" --output json)

echo "## 合规检查结果" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo "| 安全组 | 规则ID | 协议 | 端口 | 源IP | 风险等级 | 建议 |" >> "$OUTPUT_FILE"
echo "|--------|--------|------|------|------|----------|------|" >> "$OUTPUT_FILE"

# Check each security group
for SG_ID in $(echo "$SGs" | jq -r '.SecurityGroups.SecurityGroup[].SecurityGroupId'); do
  SG_NAME=$(echo "$SGs" | jq -r ".SecurityGroups.SecurityGroup[] | select(.SecurityGroupId==\"$SG_ID\") | .SecurityGroupName")
  
  # Get security group rules
  RULES=$(aliyun ecs DescribeSecurityGroupAttribute \
    --RegionId "$REGION" \
    --SecurityGroupId "$SG_ID" \
    --output json)
  
  # Check for high-risk rules
  echo "$RULES" | jq -r --arg ports "$RISK_PORTS" '
    .Permissions.Permission[] | 
    select(.SourceCidrIp == "0.0.0.0/0") |
    select(.PortRange | test("^\($ports)(/|$)")) |
    [
      "'"$SG_ID"'",
      (.SecurityGroupRuleId // "N/A"),
      .IpProtocol,
      .PortRange,
      .SourceCidrIp,
      "🔴 Critical",
      "立即修复：限制源IP"
    ] | "| \(.[0]) | \(.[1]) | \(.[2]) | \(.[3]) | \(.[4]) | \(.[5]) | \(.[6]) |"
  ' >> "$OUTPUT_FILE"
done

echo "" >> "$OUTPUT_FILE"
echo "## 修复建议" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "1. **SSH(22)**: 只允许运维VPN IP或固定办公IP访问" >> "$OUTPUT_FILE"
echo "2. **RDP(3389)**: 只允许运维VPN IP或固定办公IP访问" >> "$OUTPUT_FILE"
echo "3. **数据库端口**: 只允许应用服务器安全组或VPC内网段" >> "$OUTPUT_FILE"
echo "4. **最佳实践**: 优先使用安全组Reference而非CIDR" >> "$OUTPUT_FILE"

cat "$OUTPUT_FILE"
```

#### SDK Implementation

```go
type SecurityGroupCompliance struct {
    ecsClient *ecs.Client
}

type ComplianceViolation struct {
    SecurityGroupID   string
    SecurityGroupName string
    RuleID            string
    Protocol          string
    PortRange         string
    SourceCidrIP      string
    RiskLevel         string  // "Critical", "High", "Medium", "Low"
    Description       string
    Remediation       string
}

func (s *SecurityGroupCompliance) CheckAll(regionID string) ([]ComplianceViolation, error) {
    var violations []ComplianceViolation

    // Get all security groups
    sgResp, err := s.ecsClient.DescribeSecurityGroups(&ecs.DescribeSecurityGroupsRequest{
        RegionId: tea.String(regionID),
    })
    if err != nil {
        return nil, err
    }

    // High-risk port patterns
    highRiskPorts := map[string]bool{
        "22": true, "3389": true,
        "3306": true, "1433": true,
        "6379": true, "27017": true,
    }

    for _, sg := range sgResp.Body.SecurityGroups.SecurityGroup {
        // Get security group rules
        attrResp, err := s.ecsClient.DescribeSecurityGroupAttribute(&ecs.DescribeSecurityGroupAttributeRequest{
            RegionId:        tea.String(regionID),
            SecurityGroupId: sg.SecurityGroupId,
        })
        if err != nil {
            continue
        }

        for _, perm := range attrResp.Body.Permissions.Permission {
            sourceIP := tea.ToString(perm.SourceCidrIp)
            portRange := tea.ToString(perm.PortRange)
            protocol := tea.ToString(perm.IpProtocol)

            // Check pattern 1: 0.0.0.0/0 + high-risk ports
            if sourceIP == "0.0.0.0/0" {
                // Parse port
                port := strings.Split(portRange, "/")[0]
                if highRiskPorts[port] || portRange == "-1/-1" {
                    violations = append(violations, ComplianceViolation{
                        SecurityGroupID:   tea.ToString(sg.SecurityGroupId),
                        SecurityGroupName: tea.ToString(sg.SecurityGroupName),
                        RuleID:            tea.ToString(perm.SecurityGroupRuleId),
                        Protocol:          protocol,
                        PortRange:         portRange,
                        SourceCidrIP:      sourceIP,
                        RiskLevel:         "Critical",
                        Description:       fmt.Sprintf("高危端口 %s 对全网开放", portRange),
                        Remediation:       "限制源IP到特定CIDR或安全组",
                    })
                }
            }
        }
    }

    return violations, nil
}
```

#### Compliance Report Format

```markdown
## 安全组合规检查报告

### 检查概览

| 指标 | 数量 |
|------|------|
| 安全组总数 | 45 |
| 高危规则 | 12 |
| 🔴 Critical | 8 |
| 🟡 Medium | 4 |

### 🔴 高危规则详情

| 安全组 | 规则ID | 协议 | 端口 | 风险 | 修复建议 |
|--------|--------|------|------|------|----------|
| sg-prod-web | sr-xxx1 | TCP | 22/22 | 全网SSH | 改为 10.0.0.0/8 |
| sg-prod-db | sr-xxx2 | TCP | 3306/3306 | 全网MySQL | 改为 sg-app 安全组引用 |

### 合规建议

1. **立即修复**: 全网开放22/3389端口的规则
2. **数据库访问**: 使用安全组引用而非CIDR
3. **审计**: 每月执行安全组合规检查
4. **告警**: 新增高危规则时自动告警
```

#### Auto-Remediation (Optional)

```bash
# 自动撤销高危规则 (需确认)
aliyun ecs RevokeSecurityGroup \
  --SecurityGroupId "{{sg_id}}" \
  --SecurityGroupRuleId "{{rule_id}}"
```

> **Security Note:** Always review before auto-remediation. Some rules may be intentionally open for specific use cases.

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

### Operation: Multi-Metric Anomaly Inspection

Detect composite anomaly patterns across multiple ECS metrics for proactive alerting and auto-remediation.

#### Supported Anomaly Patterns

| Pattern ID | Pattern Name | Detection Criteria | Severity | Auto-Action |
|------------|--------------|-------------------|----------|-------------|
| 1 | **CPU-Memory 双高模式** | CPU > 90% AND Memory > 85% for 5+ minutes | Critical | Auto-scale / Restart instance |
| 2 | **磁盘-IO 瓶颈模式** | DiskUsage > 90% AND IOPS > 80% of limit | High | Alert / Expand disk |
| 3 | **突变检测模式** | Metric change rate > threshold/minute | Medium | Alert / Log analysis |
| 4 | **Load-CPU 不匹配模式** | LoadAvg > CPU * 2 | High | Process analysis / Restart |
| 5 | **网络流量突增模式** | NetworkIn/Out > 3x baseline for 3+ minutes | Medium | Traffic analysis / DDoS check |
| 6 | **磁盘写入 Stall 模式** | DiskLatency > 100ms for 2+ minutes | Critical | IO optimization / Disk upgrade |

#### CLI Detection (Batch Collection)

```bash
# Collect multi-metric data for anomaly detection
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --StartTime "$(date -u -v-10M +%Y-%m-%dT%H:%MZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%MZ)" \
  --Period 60

aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName MemoryUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --StartTime "$(date -u -v-10M +%Y-%m-%dT%H:%MZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%MZ)" \
  --Period 60

aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName DiskUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}","device":"vda"}]' \
  --StartTime "$(date -u -v-10M +%Y-%m-%dT%H:%MZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%MZ)" \
  --Period 60
```

#### SDK Detection (Programmatic Pattern Analysis)

```go
// detectAnomalyPattern analyzes collected metrics for composite anomalies
func detectAnomalyPattern(metrics map[string][]float64) []string {
    var anomalies []string

    // Pattern 1: CPU-Memory 双高
    cpuValues := metrics["CPUUtilization"]
    memValues := metrics["MemoryUsage"]
    if len(cpuValues) >= 5 && len(memValues) >= 5 {
        recentCPU := cpuValues[len(cpuValues)-5:]
        recentMem := memValues[len(memValues)-5:]
        highCPU := true
        highMem := true
        for _, v := range recentCPU {
            if v < 90 { highCPU = false }
        }
        for _, v := range recentMem {
            if v < 85 { highMem = false }
        }
        if highCPU && highMem {
            anomalies = append(anomalies, "CPU-Memory-Double-High")
        }
    }

    // Pattern 2: Disk-IO 瓶颈 (simplified check)
    diskValues := metrics["DiskUsage"]
    if len(diskValues) >= 5 {
        recentDisk := diskValues[len(diskValues)-5:]
        allHigh := true
        for _, v := range recentDisk {
            if v < 90 { allHigh = false }
        }
        if allHigh {
            anomalies = append(anomalies, "Disk-IO-Bottleneck")
        }
    }

    // Pattern 3: 突变检测
    if len(cpuValues) >= 2 {
        changeRate := cpuValues[len(cpuValues)-1] - cpuValues[len(cpuValues)-2]
        if changeRate > 30 { // >30% change in 1 minute
            anomalies = append(anomalies, "Sudden-Change-Spike")
        }
    }

    // Pattern 4: Load-CPU 不匹配
    // Requires LoadAverage from CloudMonitor or instance agent
    // LoadAverage > CPU * 2 indicates process queue buildup

    return anomalies
}
```

#### Recovery Actions

| Anomaly Pattern | Auto-Recovery | Manual Recovery |
|-----------------|---------------|-----------------|
| CPU-Memory 双高 | Trigger Auto Scaling (if configured) | Restart instance / Optimize processes |
| 磁盘-IO 瓶颈 | Expand disk / Upgrade to SSD | Clean up / Archive old data |
| 突变检测 | Send alert notification | Analyze application logs |
| Load-CPU 不匹配 | Restart hung processes | Kill runaway processes |
| 网络流量突增 | Enable DDoS protection | Review traffic sources |
| 磁盘写入 Stall | Switch to higher IOPS disk | I/O scheduler tuning |

#### Integration with Monitoring

- **Alert Rules:** Create CMS alert rules for each pattern threshold
- **Action Park:** Configure auto-scaling, message notifications (MNS), or O&M callbacks (Function Compute)
- **Event Bridge:** Forward anomalies to Event Bridge for automated response workflows
- **Service Linked Role:** Use `AliyunECSAutoScalingRole` for automatic scaling operations

> **See also:** [Observability Integration](references/observability.md) for unified alerting and [Monitoring & Alerts](references/monitoring.md) for metric configuration.

---

### Operation: Idle Resource Detection (闲置资源智能识别)

Detect idle ECS instances based on multi-dimensional inactivity metrics for cost optimization and resource cleanup.

#### Idle Detection Dimensions

| Dimension | Metric Source | Threshold | Rationale |
|-----------|--------------|-----------|-----------|
| **无API调用** | ActionTrail事件 | 30天内无ECS API调用 | 排除自动化脚本管理的实例 |
| **无登录** | ActionTrail登录日志 | 30天内无SSH/RDP登录 | 排除运维登录的实例 |
| **无流量** | CloudMonitor `InternetOutRate` | 30天内平均出流量 < 1MB | 排除有定期任务的实例 |
| **无CPU活动** | CloudMonitor `CPUUtilization` | 30天内CPU使用率 < 1% | 排除后台任务的实例 |

#### Idle Classification

| Classification | Criteria | Action Recommendation |
|----------------|----------|------------------------|
| 🟢 **活跃实例** | 满足任一活跃条件 | 保留 |
| 🟡 **低频实例** | 30天无API但有登录 或 有流量 | 建议降配或检查用途 |
| 🔴 **疑似闲置** | 30天无登录 + 无流量 + 无API | 建议下线回收 |
| 🔴 **确定闲置** | 90天无任何活动 | 强制下线回收 |

#### Execution — CLI (Batch Detection)

```bash
# Step 1: Get all ECS instances in region
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --output cols=InstanceId,InstanceName,Status rows=Instances.Instance[]

# Step 2: Check network traffic (InternetOutRate) for each instance
# 30天平均出流量 < 1MB 视为无流量
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName InternetOutRate \
  --Dimensions '[{"instanceId":"{{instance_id}}"}]' \
  --StartTime "$(date -u -v-30D +%Y-%m-%dT%H:%MZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%MZ)" \
  --Period 86400 \
  --Aggregate Average

# Step 3: Check CPU utilization (30天内平均 < 1%)
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"{{instance_id}}"}]' \
  --StartTime "$(date -u -v-30D +%Y-%m-%dT%H:%MZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%MZ)" \
  --Period 86400 \
  --Aggregate Average

# Step 4: Check ActionTrail for API calls and logins
# 需要先启用ActionTrail并配置日志投递到SLS或OSS
aliyun actiontrail DescribeTrails --RegionId "{{user.region}}"

# 查询登录事件 (需要SLS查询)
# log: actiontrail:Audit事件中EventType=ConsoleLogin
```

#### SDK Detection (Programmatic)

```go
// IdleDetector checks multiple inactivity dimensions
type IdleDetector struct {
    cmsClient    *cms.Client
    ecsClient    *ecs.Client
    actionTrail  *actiontrail.Client
}

type IdleCheckResult struct {
    InstanceID       string
    InstanceName    string
    LastAPICall     time.Time
    LastLogin       time.Time
    AvgNetworkOut   float64  // MB/day
    AvgCPUUsage     float64  // %
    IdleScore       int      // 0-100, higher = more likely idle
    Classification  string   // "活跃/低频/疑似闲置/确定闲置"
}

func (d *IdleDetector) CheckIdle(instanceID string) (*IdleCheckResult, error) {
    result := &IdleDetector{InstanceID: instanceID}

    // 1. Check network traffic (30天平均)
    networkOut := d.checkNetworkTraffic(instanceID, 30)
    result.AvgNetworkOut = networkOut

    // 2. Check CPU usage (30天平均)
    cpuUsage := d.checkCPUUsage(instanceID, 30)
    result.AvgCPUUsage = cpuUsage

    // 3. Check ActionTrail for API calls
    lastAPICall := d.checkLastAPICall(instanceID)
    result.LastAPICall = lastAPICall

    // 4. Check ActionTrail for logins
    lastLogin := d.checkLastLogin(instanceID)
    result.LastLogin = lastLogin

    // Calculate idle score
    result.IdleScore = d.calculateIdleScore(result)

    // Classify
    result.Classification = d.classify(result)

    return result, nil
}

func (d *IdleDetector) calculateIdleScore(r *IdleCheckResult) int {
    score := 0
    daysSinceAPI := int(time.Since(r.LastAPICall).Hours() / 24)
    daysSinceLogin := int(time.Since(r.LastLogin).Hours() / 24)

    // 无API调用 (0-30分)
    if daysSinceAPI > 30 {
        score += 30
    } else if daysSinceAPI > 14 {
        score += 15
    }

    // 无登录 (0-25分)
    if daysSinceLogin > 30 {
        score += 25
    } else if daysSinceLogin > 14 {
        score += 10
    }

    // 无流量 (0-25分)
    if r.AvgNetworkOut < 1 {
        score += 25
    } else if r.AvgNetworkOut < 10 {
        score += 10
    }

    // 无CPU活动 (0-20分)
    if r.AvgCPUUsage < 1 {
        score += 20
    } else if r.AvgCPUUsage < 5 {
        score += 10
    }

    return score
}

func (d *IdleDetector) classify(r *IdleCheckResult) string {
    daysSinceAPI := int(time.Since(r.LastAPICall).Hours() / 24)
    daysSinceLogin := int(time.Since(r.LastLogin).Hours() / 24)

    // 确定闲置: 90天无任何活动
    if daysSinceAPI > 90 && daysSinceLogin > 90 && r.AvgNetworkOut < 1 {
        return "确定闲置"
    }

    // 疑似闲置: 30天无登录 + 无流量 + 无API
    if daysSinceLogin > 30 && r.AvgNetworkOut < 1 && daysSinceAPI > 30 {
        return "疑似闲置"
    }

    // 低频实例: 30天无API但有登录或有流量
    if daysSinceAPI > 30 && (daysSinceLogin <= 30 || r.AvgNetworkOut >= 1) {
        return "低频实例"
    }

    return "活跃实例"
}
```

#### Idle Resource Report

Generate a comprehensive idle resource report:

```markdown
## 闲置ECS资源分析报告

### 汇总统计

| 分类 | 数量 | 占比 |
|------|------|------|
| 活跃实例 | 45 | 60% |
| 低频实例 | 12 | 16% |
| 疑似闲置 | 10 | 13% |
| 确定闲置 | 8 | 11% |
| **总计** | **75** | 100% |

### 确定闲置实例 (建议立即回收)

| 实例ID | 实例名称 | 规格 | 30天流量 | 最后登录 | 建议操作 |
|--------|----------|------|----------|----------|----------|
| i-xxx1 | test-server-1 | ecs.t5-lc2m1.nano | 0 MB | 180天前 | 下线回收 |
| i-xxx2 | dev-old | ecs.s6-nano | 0 MB | 120天前 | 下线回收 |

### 疑似闲置实例 (需人工确认)

| 实例ID | 实例名称 | 最后API | 最后登录 | 流量 | 确认后操作 |
|--------|----------|---------|----------|------|------------|
| i-xxx3 | staging-app | 45天前 | 60天前 | 0.1 MB | 下线/归档 |

### 低频实例 (建议优化)

| 实例ID | 实例名称 | 规格 | 日均流量 | 用途 | 建议 |
|--------|----------|------|----------|------|------|
| i-xxx4 | backup-server | ecs.t6-nano | 5 MB | 备份 | 降配/改用按量 |
```

#### Auto-Resolution Workflow

| Classification | Auto-Action | Manual-Required |
|---------------|-------------|-----------------|
| 确定闲置 | 生成回收工单 | 确认后执行 |
| 疑似闲置 | 发送通知给Owner | 人工确认 |
| 低频实例 | 建议降配/转按量 | 人工确认 |

#### Integration Points

- **ActionTrail**: 必须启用并投递到SLS/OSS才能查询登录和API事件
- **CloudMonitor**: 查询网络流量和CPU指标
- **MNS**: 闲置告警通知
- **Auto Scaling**: 低频实例自动缩减

> **See also:** [Monitoring & Alerts](references/monitoring.md) for cost optimization workflows

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
   > **IMPORTANT:** When outputting the above commands to console or logs, the agent MUST replace `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` with the masking format `****` instead of the actual secret value (i.e., display as `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"`). Never resolve `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` to its actual value in any visible output.

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

### Operation: Cost Visualization Report (成本可视化报告)

Generate comprehensive cost analysis reports for ECS instances with hourly billing data.

#### Cost Metrics

| Metric | Source | Description |
|--------|--------|-------------|
| 实例运行时长 | ECS API | 按量付费实例运行时长 |
| 实例规格费用 | 阿里云价格API | 各规格每小时单价 |
| 磁盘存储费用 | Disk API | 云盘大小 × 单价 |
| 流量费用 | CloudMonitor | 出流量 × 单价 |
| 快照费用 | Snapshot API | 快照大小 × 单价 |

#### CLI Implementation

```bash
# Step 1: Get all instances with specs
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --output cols=InstanceId,InstanceName,InstanceType,Status rows=Instances.Instance[]

# Step 2: Get instance price (hourly rate)
aliyun ecs DescribeInstanceTypeFamilies --RegionId "{{user.region}}"

# Step 3: Get disk usage
aliyun ecs DescribeDisks \
  --RegionId "{{user.region}}" \
  --DiskType cloud \
  --output cols=InstanceId,DiskId,Size,Category rows=Disks.Disk[]

# Step 4: Query billing API (需要开通阿里云BSS)
aliyun bssapi QueryBill \
  --BillingCycle "2026-05" \
  --ProductCode ecs
```

#### Cost Report Format

```markdown
## ECS成本分析报告

### 总体概览

| 指标 | 数值 |
|------|------|
| 总实例数 | 75 |
| 月度总费用 | ¥12,450 |
| 日均费用 | ¥415 |
| 最高规格费用 | ecs.g7.2xlarge |

### 费用分布

| 费用类型 | 金额 | 占比 |
|----------|------|------|
| 实例费用 | ¥9,800 | 79% |
| 磁盘费用 | ¥1,500 | 12% |
| 流量费用 | ¥800 | 6% |
| 快照费用 | ¥350 | 3% |

### TOP 10 高费用实例

| 实例名称 | 规格 | 月费用 | 建议 |
|----------|------|--------|------|
| prod-app-1 | ecs.g7.2xlarge | ¥2,400 | 降配至g7.xlarge |
| prod-app-2 | ecs.g7.2xlarge | ¥2,400 | 降配至g7.xlarge |
| prod-db-1 | ecs.r7.4xlarge | ¥4,800 | 保留 |

### 成本优化建议

1. **降配建议**: 8台实例可降配，预计节省 ¥1,200/月
2. **预留实例**: 15台稳定实例建议购买RI，预节省 30%
3. **闲置实例**: 10台疑似闲置实例可回收，预节省 ¥800/月
4. **磁盘清理**: 清理过期快照可节省 ¥150/月
```

#### SDK Cost Calculator

```go
type CostCalculator struct {
    priceClient *bss.Client
    ecsClient   *ecs.Client
}

type InstanceCost struct {
    InstanceID     string
    InstanceName   string
    InstanceType   string
    Hours          float64
    HourlyPrice    float64
    DiskSizeGB     int
    DiskMonthlyFee float64
    TotalMonthly   float64
}

func (c *CostCalculator) CalculateAll(regionID string) ([]InstanceCost, error) {
    var costs []InstanceCost

    // Get all instances
    instances, err := c.getAllInstances(regionID)
    if err != nil {
        return nil, err
    }

    // Get hourly price for each instance type
    priceMap := c.getInstancePrices()

    // Get disk info
    diskMap := c.getDiskInfo(regionID)

    for _, inst := range instances {
        hours := c.calculateHours(inst)
        hourlyPrice := priceMap[inst.InstanceType]
        diskFee := float64(diskMap[inst.InstanceID]) * 0.0008 // 示例单价

        costs = append(costs, InstanceCost{
            InstanceID:     inst.InstanceID,
            InstanceName:   inst.InstanceName,
            InstanceType:   inst.InstanceType,
            Hours:          hours,
            HourlyPrice:    hourlyPrice,
            DiskSizeGB:     diskMap[inst.InstanceID],
            DiskMonthlyFee: diskFee,
            TotalMonthly:   hours * hourlyPrice * 24 * 30 + diskFee,
        })
    }

    return costs, nil
}
```

---

### Operation: Predictive Capacity Analysis (预测性容量分析)

Predict future resource utilization based on historical trends to prevent capacity issues.

#### Prediction Models

| Model | Input Data | Output | Use Case |
|-------|------------|--------|----------|
| **CPU趋势预测** | 30天CPU历史数据 | 未来7天CPU预测 | 提前扩容 |
| **内存趋势预测** | 30天内存历史数据 | 未来7天内存预测 | 防止OOM |
| **磁盘容量预测** | 磁盘使用率趋势 | 磁盘满预警 | 提前扩容 |
| **流量预测** | 网络流量历史 | 带宽扩容建议 | DDoS防护 |

#### CLI Implementation

```bash
# Step 1: Collect 30-day CPU data
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"{{instance_id}}"}]' \
  --StartTime "$(date -u -v-30D +%Y-%m-%dT%H:%MZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%MZ)" \
  --Period 3600 \
  --Aggregate Average

# Step 2: Linear regression for trend
# CPU增长趋势 = (最新值 - 30天前值) / 30天

# Step 3: 预测公式
# 预测值 = 当前值 + (日均增长 × 预测天数)
```

#### SDK Predictive Analysis

```go
type CapacityPredictor struct {
    cmsClient *cms.Client
}

type PredictionResult struct {
    InstanceID      string
    Metric          string
    CurrentValue    float64
    DailyGrowthRate float64
    PredictionDays  int
    PredictedValue  float64
    DaysToThreshold float64  // 到达阈值的天数
    RiskLevel       string    // "Safe", "Warning", "Critical"
    Recommendation  string
}

// predictCapacity uses linear regression for trend prediction
func (p *CapacityPredictor) predictCapacity(instanceID, metric string, daysToPredict int) (*PredictionResult, error) {
    // Fetch 30-day historical data
    dataPoints, err := p.fetchHistoricalData(instanceID, metric, 30)
    if err != nil {
        return nil, err
    }

    // Calculate daily growth rate (linear regression)
    growthRate := calculateLinearRegression(dataPoints)

    // Predict future value
    currentValue := dataPoints[len(dataPoints)-1]
    predictedValue := currentValue + (growthRate * float64(daysToPredict))

    // Calculate days to threshold (80% for CPU/Memory)
    threshold := 80.0
    daysToThreshold := 0
    if growthRate > 0 {
        daysToThreshold = int((threshold - currentValue) / growthRate)
    }

    // Determine risk level
    riskLevel := "Safe"
    recommendation := "正常运行"

    if daysToThreshold > 0 && daysToThreshold <= 7 {
        riskLevel = "Critical"
        recommendation = fmt.Sprintf("预计%d天达到阈值，建议立即扩容", daysToThreshold)
    } else if daysToThreshold > 7 && daysToThreshold <= 14 {
        riskLevel = "Warning"
        recommendation = fmt.Sprintf("预计%d天达到阈值，建议规划扩容", daysToThreshold)
    } else if predictedValue > threshold {
        riskLevel = "Warning"
        recommendation = "预测将超过阈值，建议监控"
    }

    return &PredictionResult{
        InstanceID:      instanceID,
        Metric:         metric,
        CurrentValue:    currentValue,
        DailyGrowthRate: growthRate,
        PredictionDays:  daysToPredict,
        PredictedValue:  predictedValue,
        DaysToThreshold: float64(daysToThreshold),
        RiskLevel:       riskLevel,
        Recommendation:  recommendation,
    }, nil
}

func calculateLinearRegression(values []float64) float64 {
    n := float64(len(values))
    if n < 2 {
        return 0
    }

    // Simple linear regression: y = mx + b
    // m = (nΣxy - ΣxΣy) / (nΣx² - (Σx)²)
    sumX, sumY, sumXY, sumX2 := 0.0, 0.0, 0.0, 0.0

    for i, v := range values {
        x := float64(i)
        sumX += x
        sumY += v
        sumXY += x * v
        sumX2 += x * x
    }

    m := (n*sumXY - sumX*sumY) / (n*sumX2 - sumX*sumX)
    return m
}
```

#### Prediction Report Format

```markdown
## 预测性容量分析报告

### 总体评估

| 指标 | Safe | Warning | Critical |
|------|------|---------|----------|
| CPU | 45 | 8 | 2 |
| 内存 | 40 | 10 | 5 |
| 磁盘 | 50 | 5 | 0 |

### 🔴 需立即关注 (Critical)

| 实例名称 | 指标 | 当前值 | 增长率/天 | 预测7天后 | 到达阈值 | 建议 |
|---------|------|--------|----------|----------|----------|------|
| prod-app-1 | CPU | 72% | +3.5% | 96% | 2天 | 立即扩容 |
| prod-cache-1 | 内存 | 85% | +2.1% | 99% | 3天 | 立即扩容 |

### 🟡 需规划关注 (Warning)

| 实例名称 | 指标 | 当前值 | 增长率/天 | 预测7天后 | 到达阈值 | 建议 |
|---------|------|--------|----------|----------|----------|------|
| prod-web-3 | CPU | 65% | +1.8% | 78% | 8天 | 本周规划扩容 |
| prod-batch-1 | 磁盘 | 70% | +2.5% | 87% | 8天 | 准备磁盘扩容 |

### 扩容建议

1. **立即执行**: prod-app-1 CPU扩容 (t5→t6或自动扩容)
2. **本周计划**: prod-cache-1 内存扩容
3. **下月规划**: 4台实例需要新增
```

#### Auto-Scaling Integration

```bash
# 基于预测结果触发扩容
aliyun ess CreateScalingRule \
  --ScalingGroupId "ess-xxx" \
  --ScalingRuleType "Predictive" \
  --MetricName cpu \
  --TargetValue 70 \
  --PredictionValue 80 \
  --PredictionTimeZone "Asia/Shanghai"
```

---

### Operation: LLM-Assisted Diagnosis (LLM辅助诊断)

Integrate Large Language Model for natural language diagnostic recommendations.

#### Diagnosis Workflow

```
用户报告问题
    ↓
提取关键信息 (实例ID、现象、错误信息)
    ↓
查询ECS状态 + 监控指标 + 日志
    ↓
构建诊断Prompt
    ↓
LLM分析 → 生成诊断建议
    ↓
返回结构化建议 + 修复步骤
```

#### CLI + LLM Integration

```bash
# Step 1: Gather diagnostic data
INSTANCE_ID="{{user.instance_id}}"

# Get instance status
STATUS=$(aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --InstanceIds "[\"$INSTANCE_ID\"]" \
  --output cols=Status rows=Instances.Instance[0].Status)

# Get recent alerts
ALERTS=$(aliyun cms DescribeAlertHistoryList \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%MZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%MZ)" \
  --InstanceId "$INSTANCE_ID" \
  --output json)

# Step 2: Build prompt for LLM
cat << 'EOF' > /tmp/diagnose_prompt.txt
你是阿里云ECS运维专家。请分析以下实例的诊断数据：

实例ID: $INSTANCE_ID
状态: $STATUS
最近告警: $ALERTS

用户报告: {{user.problem_description}}

请给出:
1. 可能的原因分析
2. 推荐的排查步骤
3. 修复建议
EOF

# Step 3: Call LLM (需要集成LLM API)
curl -X POST "https://api.llm.example.com/v1/chat" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -d "{\"prompt\": $(cat /tmp/diagnose_prompt.txt), \"model\": \"expert\"}"
```

#### Diagnosis Result Format

```markdown
## 诊断报告: i-xxx (prod-web-1)

### 问题概述
用户报告: "网站无法访问，SSH连接超时"

### 数据收集
- 实例状态: Running
- CPU: 95%
- 内存: 88%
- 磁盘: 72%
- 网络: 无出流量

### 🔍 根因分析

根据收集的数据，最可能的原因是:

**主要怀疑: 网络或应用异常**
1. CPU 95% 表明实例过载
2. 无出流量表明服务可能已崩溃
3. 内存 88% 接近瓶颈

### 📋 排查步骤

1. **检查VPC安全组** - 确认22端口开放
2. **查看控制台VNC** - 检查系统日志
3. **重启实例** - 紧急恢复服务
4. **检查应用日志** - 定位OOM原因

### 🛠️ 修复建议

**立即执行**:
```bash
# 重启实例
aliyun ecs RebootInstance --InstanceId i-xxx --ForceStop true

# 重启后检查
aliyun ecs DescribeInstances --InstanceIds '["i-xxx"]' \
  --output cols=Status,CPU,Memory
```

**长期优化**:
- 配置HPA自动扩容
- 优化应用内存使用
- 增加监控告警
```

#### Supported Problem Types

| 问题类型 | 关键数据 | LLM分析要点 |
|----------|----------|-------------|
| 无法连接 | 安全组、VPC、状态 | 网络路径分析 |
| 性能问题 | CPU、内存、IO | 资源瓶颈定位 |
| 磁盘满 | 磁盘使用率 | 清理建议 |
| 登录失败 | 安全组、ACL | 权限检查 |
| 应用崩溃 | 内存、OOM | 堆栈分析 |

> **Note:** LLM integration requires external LLM API (e.g., DashScope, OpenAI). Configure API endpoint in skill configuration.
