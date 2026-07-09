---
name: alicloud-fc-ops
description: >-
  Use when the user needs to inspect, diagnose, optimize, or monitor Alibaba Cloud
  Function Compute (FC) — function lifecycle, triggers, provisioned instances,
  concurrency configs, VPC bindings, and AIOps-driven diagnostics. User mentions
  "函数计算", "Function Compute", "FC 3.0", "Serverless函数", "冷启动", or
  describes product-specific scenarios (e.g., cold start latency, memory
  right-sizing, invocation throttling, timeout errors, idle function detection,
  provisioned instance cost waste, GPU function, vLLM inference, LLM batch
  scoring) even without naming the product directly.
  Not for billing-only, RAM-only, or related products that have their own ops
  skills. For FC code deployment from source, delegate to CI/CD or deployment skills.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints. FC 3.0 uses ROA-style API (`aliyun fc-open <METHOD> /2023-03-30/path`).
metadata:
  author: alicloud
  version: "3.2.0"
  last_updated: "2026-06-04"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "FC/2023-03-30 (Function Compute 3.0), ROA-style API"
  cli_applicability: "dual-path"
  cli_support_evidence: >-
    FC 3.0 uses ROA-style API. Confirmed CLI path: `aliyun fc-open POST /2023-03-30/functions`.
    SDK path: github.com/alibabacloud-go/fc-20230330/v4
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Function Compute (FC 3.0) Operations Skill

## Overview

Alibaba Cloud Function Compute (FC) is a fully managed, event-driven serverless compute platform. FC 3.0 simplifies the resource model: functions are top-level resources with qualifiers (versions/aliases) instead of the FC 2.0 service-based hierarchy. This skill is an **operational runbook** for agents: function inspection, trigger management, provisioned instance optimization, concurrency analysis, VPC binding verification, and **AIOps-driven multi-metric diagnostics** (cold start analysis, memory right-sizing, idle detection, throttle cascade diagnosis).

**Execution paths:** Dual-path — ROA-style CLI (`aliyun fc-open`) as primary, JIT Go SDK (`github.com/alibabacloud-go/fc-20230330/v4`) as fallback for operations CLI doesn't cover.

> **UX Compliance:** This skill follows the [User Experience Specification](../alicloud-skill-generator/../alicloud-skill-generator/references/user-experience-spec.md). All operations include onboarding guidance, minimal prompts, smart defaults, clear feedback, and user-friendly error handling.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`**: Both `aliyun fc-open` (ROA CLI) and Go SDK paths are documented. CLI covers all CRUD operations; SDK provides strongly-typed alternatives for complex body payloads.

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with specific keywords and delegation rules |
| 2 | **Structured I/O** | `{{env.*}}` for credentials; `{{user.*}}` for interactive input; `{{output.*}}` from API responses |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute (ROA CLI + SDK) → Validate → Recover |
| 4 | **Complete Failure Strategies** | 20+ FC error codes; HALT vs retry per error category |
| 5 | **Absolute Single Responsibility** | FC functions only; cross-product delegation documented |

### Well-Architected Framework Integration (卓越架构)

| Pillar | FC-Specific Integration | Reference |
|--------|------------------------|-----------|
| **安全** | RAM execution roles, VPC networking, code encryption, secret management | `references/well-architected-assessment.md` §2.1 |
| **稳定** | Reserved capacity for always-on, async retry config, provisioned instances, multi-region DR | `references/well-architected-assessment.md` §2.2 |
| **成本** | Memory right-sizing, idle function detection, provisioned vs on-demand, reserved instance optimization | `references/well-architected-assessment.md` §2.3 |
| **效率** | Batch function operations, tag-based filtering, CI/CD patterns, concurrent invocation | `references/well-architected-assessment.md` §2.4 |
| **性能** | Cold start optimization, memory-performance mapping, provisioned instance warm-up, p99 duration | `references/well-architected-assessment.md` §2.5 |

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper ./scripts/fc-skillopt-wrapper.sh to enable automated self-repair; fallback to native aliyun only when wrapper unavailable. | SkillOpt |
| Credentials | Read {{env.*}} from environment; never ask user to paste secrets | Integration |
| GCL | All write operations MUST pass GCL review before execution | GCL Rubric |


## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "函数计算", "Function Compute", "FC", "FC 3.0", "阿里云函数计算", "Serverless函数"
- Task involves CRUD/lifecycle operations on FC functions (create, describe, invoke, modify, delete, list)
- Task involves FC triggers (HTTP, timer, OSS, MNS, Log Service, EventBridge)
- Task involves FC configuration: provisioned instances, concurrency limits, async invocation, VPC bindings
- User asks to analyze FC optimization: memory right-sizing, cold start reduction, idle function detection, provisioned instance tuning, cost analysis
- User asks to diagnose FC issues: invocation failures, timeout errors, throttling, memory OOM, cold start latency, VPC connectivity failures
- User asks for FC monitoring/AIOps: multi-metric anomaly inspection, alert-driven diagnosis, proactive inspection
- User asks about **FC GPU functions**, **vLLM** / **SGLang** deployment, **LLM metrics**, or **batch / quasi-real-time inference** on Function Compute

### SHOULD NOT Use This Skill When

- Task is purely billing/account management → delegate to billing ops skill (when present)
- Task is RAM/permission model only → delegate to: `alicloud-ram-ops`
- Task is VPC/subnet/security-group configuration → delegate to: `alicloud-vpc-ops` (when present)
- Task is SLB health check/backend config → delegate to: `alicloud-slb-ops`
- Task is ECS/container compute → delegate to: `alicloud-ecs-ops` or `alicloud-ack-ops`
- Task is CMS alert rule management (non-FC) → delegate to: `alicloud-cms-ops`
- Task is DAS database diagnosis → delegate to: `alicloud-das-ops`
- User wants SLS log analysis → delegate to: `alicloud-sls-ops` (when present)
- User asks about API Gateway configuration → delegate to: API Gateway skill (when present)

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment (e.g., cn-hangzhou) | Use configured default |
| `{{user.function_name}}` | User-supplied function name | Ask once; reuse |
| `{{user.qualifier}}` | Version or alias (e.g., LATEST, prod, v1) | Default: `LATEST` |
| `{{user.time_range}}` | Time window for metric query | Default: last 1 hour |
| `{{output.function_name}}` | From ListFunctions or GetFunction response | Parse from API |
| `{{output.function_arn}}` | From API response | Parse from API |
| `{{output.cold_start_ms}}` | Derived from InitialDuration metric | Calculated |
| `{{output.request_id}}` | From API response `.RequestId` | For escalation |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **FC 3.0 uses ROA-style API** (`FC/2023-03-30`). CLI: `aliyun fc-open <METHOD> /2023-03-30/<path> [--body "..."] [--header "..."]`
- **Endpoint**: `fcv3.<region_id>.aliyuncs.com` (e.g., `fcv3.cn-hangzhou.aliyuncs.com`)
- **Errors**: HTTP status code with error body (`.code`, `.message`, `.requestId`)
- **Timestamps**: ISO 8601 format
- **Pagination**: `limit` (max 100) + `nextToken`
- **Code package**: Must be uploaded to OSS first, then reference via `ossBucketName`/`ossObjectName` (CLI cannot upload code directly)

### Key Response Fields

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| GetFunction | `$.functionName` | string | Function name |
| GetFunction | `$.runtime` | string | Runtime (python3.10, go1, nodejs18, java21, etc.) |
| GetFunction | `$.memorySize` | integer | Memory in MB |
| GetFunction | `$.timeout` | integer | Timeout in seconds |
| GetFunction | `$.state` | string | PENDING / ACTIVE / FAILED |
| GetFunction | `$.lastUpdateStatus` | string | SUCCESSFUL / FAILED / IN_PROGRESS |
| GetFunction | `$.vpcConfig` | object | VPC, vSwitches, securityGroupId |
| GetFunction | `$.role` | string | RAM execution role ARN |
| GetProvisionConfig | `$.current` | integer | Actual running provisioned instances |
| GetProvisionConfig | `$.target` | integer | Target provisioned instance count |
| GetAsyncInvokeConfig | `$.maxAsyncEventAgeInSeconds` | integer | Max async event retention |
| GetAsyncInvokeConfig | `$.maximumRetryAttempts` | integer | Max retry attempts |

### FC Resource State Machine

```
[CreateFunction] → PENDING → ACTIVE → [Invoke/Trigger]
                                      ↓
                    [UpdateFunction] → IN_PROGRESS → ACTIVE
                    [UpdateFunction] → FAILED → [Retry] → ACTIVE
                                      ↓
                    [DisableFunctionInvocation] → DISABLED
                    [EnableFunctionInvocation] → ACTIVE
```

## Quick Start

### What This Skill Does
Manage Alibaba Cloud Function Compute (FC 3.0) functions — lifecycle, triggers, provisioned instances, concurrency, VPC bindings, and AIOps diagnostics.

### Prerequisites
- [ ] `aliyun` CLI installed
- [ ] Credentials: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region: `ALIBABA_CLOUD_REGION_ID`

### Verify Setup
```bash
aliyun fc-open GET /2023-03-30/functions
```

### Your First Command
```bash
aliyun fc-open GET /2023-03-30/functions/{{user.function_name}}
```

### Next Steps
- [Core Concepts](references/core-concepts.md) — FC 3.0 architecture, limits, dependency graph
- [GPU Inference (vLLM & Batch)](references/gpu-inference.md) — GPU function paths, batching, warmup, LLM metrics
- [Execution Flows](#execution-flows) — CRUD operations, CLI + SDK paths
- [Monitoring](references/monitoring.md) — Multi-metric anomaly inspection, AIOps patterns
- [Troubleshooting](references/troubleshooting.md) — FC error codes, 5-step diagnosis

---

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| CreateFunction | Create FC function with code from OSS | Medium | Low |
| DeployFromSource | Package local code → upload OSS → create/update → invoke | High | Low |
| Update Function Code | Hot-update function code (via UpdateFunction API) | Medium | Medium |
| GetFunction | Inspect function configuration | Low | None |
| ListFunctions | List functions with filters | Low | None |
| InvokeFunction | Synchronous or asynchronous invocation | Medium | Medium |
| UpdateFunction | Update function config/code via UpdateFunction API | Medium | Medium |
| DeleteFunction | Delete function | Low | **High** |
| ManageTrigger | Create/update/delete triggers | Medium | Medium |
| ProvisionConfig | Inspect/configure provisioned instances | Medium | Medium |
| ConcurrencyConfig | Set concurrency limits | Medium | Low |
| AsyncInvokeConfig | Configure async retry policy | Medium | Low |
| VpcBinding | Configure VPC network access | Medium | Medium |
| MultiMetricAnomaly | AIOps multi-metric anomaly inspection | High | None |
| AlertDiagnosis | 5-step alert-driven diagnosis | High | None |
| IdleDetection | Detect idle/underutilized functions | Low | None |
| CreateGpuFunction | Create GPU custom-container function (vLLM image, gpuConfig) | High | Medium |
| GpuScalingConfig | Set minInstances / resident pool for GPU elastic or warm capacity | Medium | Medium |
| GpuHttpInference | HTTP trigger + OpenAI-compatible curl to vLLM endpoint | Medium | Low |
| GpuBatchAsync | Async invoke + DLQ or OSS trigger for offline batch scoring | High | Medium |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 3.1.0 | 2026-05-19 | Add gpu-inference.md (vLLM/batch scenarios); CLI/API/SDK per scenario (§10); GPU ops in SKILL, cli-usage, api-sdk-usage; GPU fault patterns |
| 1.0.0 | 2026-05-18 | Initial FC 3.0 skill: dual-path CLI/SDK, AIOps monitoring, Well-Architected 5-pillar, self-healing framework |

---

> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/fc-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun fc ...` 命令在执行时应替换为 `./scripts/fc-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun fc` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI + SDK) → Validate → Recover**. Do not skip phases.

**Preference:** ROA CLI (`aliyun fc-open`) is primary for its simplicity. JIT Go SDK is fallback when CLI body construction is too complex.

### Operation: Create FC Function

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI available | `aliyun version` | Exit code 0 | HALT; install CLI |
| Credentials | env check non-empty | AK + Secret set | HALT; configure |
| Region | env region valid | Valid FC region | HALT; set region |
| Code package | OSS bucket + object exists | Accessible code.zip | Ask user to upload code to OSS first |
| Execution role | RAM role ARN provided | Valid role with `fc:InvokeFunction` | Delegate to `alicloud-ram-ops` |
| Quota | Check account function limit | Within quota | HALT; request quota increase |

#### Execution — CLI (ROA Primary Path)

```bash
# Create function (code from OSS)
aliyun fc-open POST /2023-03-30/functions --body "$(cat <<EOF
{
  "functionName": "{{user.function_name}}",
  "runtime": "{{user.runtime}}",
  "handler": "{{user.handler}}",
  "memorySize": {{user.memory_mb|default:512}},
  "timeout": {{user.timeout|default:60}},
  "code": {
    "ossBucketName": "{{user.oss_bucket}}",
    "ossObjectName": "{{user.oss_object}}"
  },
  "role": "{{user.ram_role_arn}}"
}
EOF
)"
```

#### Execution — JIT Go SDK (Fallback)

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

1. Parse `{{output.function_name}}` and `{{output.function_id}}` from response
2. Poll `GetFunction` until `$.state == "ACTIVE"` (interval 5s, max 300s):

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)（60×5s → ACTIVE）
```

3. If state == "FAILED": check `$.stateReason` and `$.stateReasonCode` for root cause
4. Verify code is accessible: `aliyun fc-open GET /2023-03-30/functions/{{user.function_name}}/code`
5. **Test invocation** (optional): `aliyun fc-open POST /2023-03-30/functions/{{user.function_name}}/invocations`

#### Failure Recovery

| Error | Max Retries | Agent Action | UX Feedback |
|-------|-------------|--------------|-------------|
| `ResourceLimitExceeded` | 0 | HALT; account quota reached | `[ERROR] Quota exceeded for this region. Request increase or delete unused functions.` |
| `RoleAccessDenied` | 0 | HALT; RAM role issue | `[ERROR] Execution role inaccessible. Verify RAM role trust policy allows fc.aliyuncs.com.` |
| `InvalidArgument` | 0 | Check body field types | `[ERROR] Invalid parameter. Validate runtime, handler memorySize, timeout values.` |
| `ServiceNotFound` | 0 | HALT | `[ERROR] FC service not activated. Enable Function Compute in console first.` |
| `BucketAccessDenied` | 0 | HALT; OSS permission | `[ERROR] Cannot access OSS code package. Check bucket ACL and RAM policy.` |
| `Throttling` | 3, exponential | Back off | `⚠️ Rate limited, retrying...` |
| `InternalError` | 3, 2s→4s→8s | Retry | `[ERROR] FC internal error. Retrying... If persists, escalate with RequestId.` |
| `Forbidden.RAM` | 0 | HALT | `[ERROR] RAM permission denied. Add fc:* or specific fc:CreateFunction policy.` |

### Operation: GPU Function (vLLM & Batch)

**Scope:** Path **B** — self-managed GPU function via `fc-open` / Go SDK. Path **A** (Function AI Model Service) is console/Serverless Devs — see [gpu-inference.md §10.1](references/gpu-inference.md#101-path-a--function-ai-model-service-vllm).

| Scenario | APIs (in order) | Detail |
|----------|-----------------|--------|
| Online vLLM API | CreateFunction → PutScalingConfig (`minInstances≥1`) → CreateTrigger (http) | [gpu-inference.md §10.2–10.4](references/gpu-inference.md#102-create-gpu-function-custom-container--vllm) |
| Quasi-real-time | CreateFunction → PutScalingConfig (`minInstances: 0`) | [§10.3](references/gpu-inference.md#103-elastic-scaling--mininstances-online-vs-quasi-real-time) |
| Offline batch | CreateFunction → PutAsyncInvokeConfig → InvokeFunction (Async) or OSS CreateTrigger | [§10.5–10.6](references/gpu-inference.md#105-offline-batch--async-invoke--dlq) |
| Resident GPU | CreateFunction (console pool at create) → PutScalingConfig (`residentPoolId`) | [§10.3](references/gpu-inference.md#103-elastic-scaling--mininstances-online-vs-quasi-real-time) |

#### Pre-flight (GPU-specific)

完整 GPU 操作步骤见 [references/gpu-inference.md](references/gpu-inference.md)

#### Execution — Create GPU function (CLI excerpt)

完整 CLI 命令见 [references/gpu-inference.md](references/gpu-inference.md)

#### Execution — Scaling + HTTP inference

完整 CLI 命令见 [references/gpu-inference.md](references/gpu-inference.md)

#### Execution — Async batch job

完整 CLI 命令见 [references/gpu-inference.md](references/gpu-inference.md)

#### Post-execution Validation

完整验证步骤见 [references/gpu-inference.md](references/gpu-inference.md)

#### Failure Recovery (GPU)

完整错误处理见 [references/gpu-inference.md](references/gpu-inference.md)

### Operation: List Functions

#### Execution — CLI

```bash
# All functions
aliyun fc-open GET /2023-03-30/functions

# Filter by name prefix
aliyun fc-open GET "/2023-03-30/functions?prefix={{user.prefix}}"

# Paginate (limit + nextToken)
aliyun fc-open GET "/2023-03-30/functions?limit=100"

# Filter by runtime
aliyun fc-open GET "/2023-03-30/functions?runtime=python3.10"

# Filter by FC version (fcv2 vs fcv3)
aliyun fc-open GET "/2023-03-30/functions?fcVersion=fcv3"

# Filter by tag
aliyun fc-open GET "/2023-03-30/functions?tag.filter.1.key=env&tag.filter.1.value=production"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Name | `$.functions[].functionName` | Function identifier |
| Runtime | `$.functions[].runtime` | Language runtime |
| Memory | `$.functions[].memorySize` | MB |
| Timeout | `$.functions[].timeout` | Seconds |
| State | `$.functions[].state` | ACTIVE / FAILED / PENDING |

### Operation: Describe Function

#### Execution — CLI

```bash
aliyun fc-open GET /2023-03-30/functions/{{user.function_name}}

# Specific version
aliyun fc-open GET "/2023-03-30/functions/{{user.function_name}}?qualifier={{user.qualifier}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Name | `$.functionName` | |
| ID | `$.functionId` | Unique identifier |
| ARN | `$.arn` (constructed) | Full resource ARN |
| Runtime | `$.runtime` | |
| Memory | `$.memorySize` MB | |
| Timeout | `$.timeout` s | |
| Handler | `$.handler` | |
| State | `$.state` | PENDING/ACTIVE/FAILED |
| LastUpdateStatus | `$.lastUpdateStatus` | |
| StateReason | `$.stateReason` | If FAILED, explains why |
| StateReasonCode | `$.stateReasonCode` | Error code if FAILED |
| DiskSize | `$.diskSize` MB | 512 (default) or 10240 |
| Role | `$.role` | Execution role ARN |
| VPC Config | `$.vpcConfig` | Network isolation |

### Operation: Invoke Function

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Function ACTIVE | GetFunction `$.state` | `ACTIVE` | HALT; fix function first |
| Handler valid | Check `$.handler` | Non-empty string | HALT; fix handler |
| Timeout sufficient | Review `$.timeout` | Adequate for operation | Warn user |

#### Execution — CLI (Synchronous)

```bash
aliyun fc-open POST /2023-03-30/functions/{{user.function_name}}/invocations \
  --body '{{user.payload|default:"{}"}}' \
  --header "x-fc-invocation-type=Sync"
```

#### Execution — CLI (Asynchronous)

```bash
aliyun fc-open POST /2023-03-30/functions/{{user.function_name}}/invocations \
  --body '{{user.payload|default:"{}"}}' \
  --header "x-fc-invocation-type=Async"
```

#### Post-execution Validation

- Sync: Check response body for function output
- Async: Request accepted immediately, check async task status:

```bash
aliyun fc-open GET "/2023-03-30/functions/{{user.function_name}}/async-invocations"
```

### Operation: Invoke Function — SDK Path

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

### Operation: End-to-End Deploy (Package → Upload OSS → Deploy → Invoke)

完整部署流程（Pre-flight → Phase 1-5 → Failure Recovery）见 [references/deploy-from-source.md](references/deploy-from-source.md)

### Operation: Update Function Code (Hot Update)

**When to use:** Update existing function's code package without changing runtime, memory, or other config.

**Note:** FC 3.0 does not have a separate `UpdateFunctionCode` API. Code is updated via `UpdateFunction` by including the `code` field in the request body.

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Function exists | `GetFunction` | State = ACTIVE | HALT; function not found |
| New package ready | OSS object uploaded | Object accessible | Upload new code to OSS first |

#### Execution — CLI

```bash
# Update function code via UpdateFunction (include only code field)
aliyun fc-open PUT /2023-03-30/functions/{{user.function_name}} --body "$(cat <<EOF
{
  "code": {
    "ossBucketName": "{{user.oss_bucket}}",
    "ossObjectName": "{{user.oss_prefix}}/{{user.function_name}}-v2-code.zip"
  }
}
EOF
)"
```

#### Post-execution Validation
1. Poll `GetFunction` until `$.state == "ACTIVE"` or `$.lastUpdateStatus == "SUCCESSFUL"`
2. Test invocation with known payload to verify new code works
3. If rollback needed: restore from previous OSS package and update again

### Operation: Update Function

#### Safety Gate
- **Non-destructive**: Updates config, does NOT stop running instances
- **Qualifiers**: Unpublished (LATEST) only — cannot update published versions
- **Backup**: Get current config before update

```bash
# Backup current config
aliyun fc-open GET /2023-03-30/functions/{{user.function_name}} > /tmp/{{user.function_name}}-config-backup.json

# Update (partial body, only changed fields)
aliyun fc-open PUT /2023-03-30/functions/{{user.function_name}} --body "$(cat <<EOF
{
  "description": "{{user.description}}",
  "memorySize": {{user.memory_mb}},
  "timeout": {{user.timeout}}
}
EOF
)"
```

### Operation: Delete Function

#### Safety Gate

- **MUST** obtain explicit confirmation: `Confirm deletion of function "{{user.function_name}}"?`
- **MUST** warn: irreversible, all triggers, provisioned instances, and async configs removed
- **MUST NOT** proceed without clear assent

#### Execution

```bash
aliyun fc-open DELETE /2023-03-30/functions/{{user.function_name}}

# SDK path
// fcClient.DeleteFunction(tea.String(functionName))
```

#### Post-execution Validation
- Poll GetFunction until 404 ResourceNotFound (interval 5s, max 120s)

#### Failure Recovery
| Error | Agent Action | UX |
|-------|-------------|-----|
| `ResourceInUse` | HALT; function being invoked | `[ERROR] Function in use. Wait for invocations to complete.` |
| `ResourceNotFound` | Already deleted | `Function already deleted — nothing to do.` |

### Operation: Manage Triggers

#### Execution — CLI

```bash
# Create trigger
aliyun fc-open POST /2023-03-30/functions/{{user.function_name}}/triggers --body "$(cat <<EOF
{
  "triggerName": "{{user.trigger_name}}",
  "triggerType": "{{user.trigger_type}}",
  "triggerConfig": {"your": "config"},
  "invocationRole": "{{user.ram_role_arn}}"
}
EOF
)"

# List triggers
aliyun fc-open GET /2023-03-30/functions/{{user.function_name}}/triggers

# Get trigger
aliyun fc-open GET /2023-03-30/functions/{{user.function_name}}/triggers/{{user.trigger_name}}

# Delete trigger (safety gate: confirm)
aliyun fc-open DELETE /2023-03-30/functions/{{user.function_name}}/triggers/{{user.trigger_name}}
```

#### Supported Trigger Types

| Type | Use Case | Key Config |
|------|----------|------------|
| `http` | REST API endpoint | Auth type, methods |
| `timer` | Scheduled/cron | Cron expression |
| `oss` | Object upload event | Bucket, event types |
| `log` | Log Service trigger | Logstore, filter |
| `mns` | Message queue | Queue URL |
| `eventbridge` | EventBridge events | Event pattern |

### Operation: Inspect/Configure Provisioned Instances

#### Execution — CLI

```bash
# List all provisioned configs
aliyun fc-open GET /2023-03-30/provision-configs

# Get specific provisioned config
aliyun fc-open GET "/2023-03-30/functions/{{user.function_name}}/provision-config?qualifier={{user.qualifier}}"

# Create provisioned instance (pre-warm)
aliyun fc-open PUT /2023-03-30/functions/{{user.function_name}}/provision-config \
  --body "$(cat <<EOF
{
  "qualifier": "{{user.qualifier}}",
  "target": 1
}
EOF
)"
```

#### Post-execution Validation

1. `current` vs `target`: if `current < target`, still warming up
2. `current > 0` but invocation ≈ 0 → cost waste (idle provisioned)
3. Cost impact: provisioned = billed per instance-hour regardless of invocations

### Operation: Inspect Async Invocation Config

```bash
aliyun fc-open GET "/2023-03-30/functions/{{user.function_name}}/async-invoke-config?qualifier={{user.qualifier}}"
```

| Field | Description |
|-------|-------------|
| `maxAsyncEventAgeInSeconds` | Max async event retention (0-259200) |
| `maximumRetryAttempts` | Max delivery retries (0-3) |
| `destination.onSuccess` | ARN for success callback |
| `destination.onFailure` | ARN for failure destination |

---

### Operation: Multi-Metric Anomaly Inspection (AIOps)

#### Supported Anomaly Patterns

| Pattern | Metrics | Detection Logic | Severity | Interpretation |
|---------|---------|-----------------|----------|----------------|
| **ColdStartBurst** | InitialDuration, InvocationCount | Cold start >500ms during traffic spike | Warning | Capacity scaling causing cold starts |
| **MemoryPressure** | MemoryUsage, Errors, Duration | Memory ~limit + exit code 137 | Critical | OOM — function killed by platform |
| **ThrottleCascade** | InvocationThrottled, InvocationCount | Throttled >10% of total invocations | Critical | Concurrency limit too low for load |
| **DurationCreep** | FunctionDuration (p50/p95) | p95 > 2x p50 or sustained upward trend | Warning | Performance degradation |
| **IdleResourceWaste** | InvocationCount, ProvisionConfig | 0 invocations in 24h with provisioned instances | Warning | Paying for unused provisioned capacity |
| **ErrorRateSpike** | ErrorCount, InvocationCount | Error rate >5% in 15min window | Critical | Function code or dependency failure |
| **MemoryLeakTrend** | MemoryUsage over time | Steady increase across invocations (not reset) | Warning | Potential memory leak in runtime |
| **TimeoutApproach** | Duration vs configured timeout | Duration approaching 80%+ of timeout | Warning | Risk of timeout errors under load |

#### Pre-flight

| Check | Expected | On Failure |
|-------|----------|------------|
| Function(s) identified | ≥1 via ListFunctions | Ask user |
| CMS metrics available | Namespace `acs_fc` accessible | Delegate to `alicloud-cms-ops` |
| Time window | Default: last 1h | Accept `{{user.time_range}}` |

#### Execution — Multi-Metric CLI

完整 CLI 查询命令见 [references/monitoring.md#cli-monitoring-integration--multi-metric-queries](references/monitoring.md#cli-monitoring-integration--multi-metric-queries)

---

### Operation: Alert-Driven Diagnosis (AIOps 5-Step Decision Tree)

完整诊断流程见 [references/monitoring.md](references/monitoring.md)

---

## Prerequisites

1. **Install `aliyun` CLI**
2. **Bootstrap Go runtime** (JIT SDK fallback)
3. **Configure credentials** (`{{env.*}}`)
4. **Verify**: `aliyun fc-open GET /2023-03-30/functions`

See [../alicloud-skill-generator/references/execution-environment.md](../alicloud-skill-generator/references/execution-environment.md) for detailed setup with self-healing framework.

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Deploy from Source](references/deploy-from-source.md)
- [Polling Patterns](references/polling-patterns.md) — FC 函数状态轮询模板
- [Monitoring & AIOps](references/monitoring.md)
- [Troubleshooting](references/troubleshooting.md)
- [Integration](references/integration.md)
- [Well-Architected Assessment](references/well-architected-assessment.md)
- [Knowledge Base](references/knowledge-base.md)
- [GPU Inference (vLLM & Batch)](references/gpu-inference.md)
- [Observability](references/observability.md)
- [Self-Healing Framework](references/enhanced-self-healing-framework.md)
- [Enhanced Self-Healing](references/enhanced-self-healing-framework.md)
- [User Experience Specification](../alicloud-skill-generator/references/user-experience-spec.md)
- [Optimization Analysis](../alicloud-rds-ops/references/advanced/finops-analysis.md)

## Operational Best Practices

- **Least privilege RAM**: `fc:GetFunction`, `fc:ListFunctions`, etc. — not `AdministratorAccess`
- **Cold start optimization**: Provisioned instances for latency-critical, optimize code/memory for cost-sensitive
- **Memory right-sizing**: Monitor actual usage → adjust memorySize → better performance + lower cost
- **Async with retry**: Set `maximumRetryAttempts` ≥ 2 for reliability, + failure destination
- **Concurrency guardrails**: Set per-function limits to prevent noisy neighbor
- **VPC for data access**: Use VPC binding for RDS/Redis, but note cold start penalty (~200ms)
- **Tag everything**: `env`, `team`, `costCenter` for cost attribution

---

## Quality Gate (GCL)

Phase 5 rollout for `recommended` skills per [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Recommended** (Phase 5, `max_iter=3`) |
| Most-scrutinized | `DeleteFunction` (no active triggers; backup function config), `DeleteService` (no functions inside; cascade warning) |

### Changelog
1.0.0 | 2026-06-04 | Phase 5 `recommended` rollout for fc-ops.

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `dual-path`，CLI/SDK 已覆盖，无需 code snippets.
