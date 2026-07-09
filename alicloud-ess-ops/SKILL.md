---
name: alicloud-ess-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba
  Cloud Auto Scaling (ESS, 弹性伸缩) — scaling group lifecycle, scaling
  configurations/rules, scheduled tasks, lifecycle hooks, instance refresh,
  alarm-based scaling, notification configurations, and load balancer
  association. User mentions Auto Scaling, ESS, 弹性伸缩, elastic scaling,
  scaling group, scaling configuration, 伸缩组, 伸缩配置, or describes
  scenarios (automatic instance scaling, scheduled scaling, health check
  replacement, load balancing with scaling, instance refresh, elasticity
  strategy) even without naming the product explicitly. CLI: `aliyun ess`,
  SDK: `ess-2014-08-28`. NOT for ECS/ECI instance management without scaling,
  SLB/ALB configuration without scaling integration, billing/RAM-only tasks, or
  other products that have their own ops skills.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-07"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "Auto Scaling (ESS) 2014-08-28 / https://help.aliyun.com/zh/auto-scaling/"
  cli_applicability: dual-path
  cli_support_evidence: "Confirmed via `aliyun help ess` — Auto Scaling (ESS) is supported by the official aliyun CLI with full coverage of CRUD operations for scaling groups, configurations, rules, scheduled tasks, lifecycle hooks, alarms, notifications, instance management, and load balancer association."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
  gcl_classification: required
  gcl_max_iter: 2
  token_budget_estimate: "~3500 tokens (SKILL.md only)"
  references_index:
    - path: "references/execution-flows.md"
      load_condition: "当用户需要执行具体操作时"
    - path: "references/core-concepts.md"
      load_condition: "当用户需要了解架构或配额时"
    - path: "references/api-sdk-usage.md"
      load_condition: "当用户需要 SDK 操作或 API 详情时"
    - path: "references/cli-usage.md"
      load_condition: "当用户需要 CLI 快速参考时"
    - path: "references/troubleshooting.md"
      load_condition: "当用户需要排查错误时"
    - path: "references/monitoring.md"
      load_condition: "当用户需要监控指标时"
    - path: "references/integration.md"
      load_condition: "当用户需要 JIT SDK 引导时"
    - path: "references/well-architected-assessment.md"
      load_condition: "当用户需要架构评估时"
    - path: "references/idempotency-checklist.md"
      load_condition: "当用户需要幂等重试指导时"
    - path: "references/rubric.md"
      load_condition: "当用户需要 GCL 评分规则时"
    - path: "references/prompt-templates.md"
      load_condition: "当用户需要 GCL 提示模板时"
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Auto Scaling (ESS) Operations Skill

## Common JSON Paths (Centralized)

```
# CreateScalingGroup:              $.ScalingGroupId
# DescribeScalingGroups:           $.ScalingGroups[].{ScalingGroupId,ScalingGroupName,ActiveScalingConfigurationId,LifecycleState,MinSize,MaxSize,DesiredCapacity}
# CreateScalingConfiguration:      $.ScalingConfigurationId
# DescribeScalingConfigurations:   $.ScalingConfigurations[].{ScalingConfigurationId,ScalingConfigurationName,ImageId,InstanceType,LifecycleState}
# CreateScalingRule:               $.ScalingRuleId
# DescribeScalingRules:            $.ScalingRules[].{ScalingRuleId,ScalingRuleName,ScalingRuleAri,Cooldown,MinAdjustmentMagnitude,ScalingRuleType}
# CreateScheduledTask:             $.ScheduledTaskId
# DescribeScheduledTasks:          $.ScheduledTasks[].{ScheduledTaskId,ScheduledTaskName,Description,ScheduleExpression,RecurrenceValue}
# CreateLifecycleHook:             $.LifecycleHookId
# DescribeLifecycleHooks:          $.LifecycleHooks[].{LifecycleHookId,LifecycleHookName,LifecycleTransition,HeartbeatTimeout,DefaultResult}
# CreateAlarm:                     $.AlarmTaskId
# DescribeAlarms:                  $.AlarmList[].{AlarmTaskId,AlarmTaskName,MetricName,ComparisonOperator,Threshold,State}
# DescribeScalingActivities:       $.ScalingActivities[].{ScalingActivityId,Description,Cause,StartTime,EndTime,StatusCode,StatusMessage}
# DescribeScalingInstances:        $.ScalingInstances[].{InstanceId,ScalingConfigurationId,ScalingGroupId,HealthStatus,LifecycleState}
# DescribeRegions:                 $.Regions[].{RegionId,RegionEndpoint,LocalName}
# EnableScalingGroup:              $.RequestId
# DisableScalingGroup:             $.RequestId
# DeleteScalingGroup:              $.RequestId
# AttachInstances:                 $.RequestId
# DetachInstances:                 $.RequestId
# RemoveInstances:                 $.RequestId
# SetInstancesProtection:          $.RequestId
# ExecuteScalingRule:              $.ScalingActivityId
```

## Overview

Auto Scaling (ESS) is Alibaba Cloud's elastic scaling service that automatically adjusts compute resources based on policies. This skill is an **operational runbook** for agents: Pre-flight → Execute (CLI primary + SDK fallback) → Validate → Recover.

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/ess-skillopt-wrapper.sh` for all ESS CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun ess` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md) |

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers and delegation rules |
| 2 | **Structured I/O** | Placeholders (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) with type and source |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute → Validate → Recover |
| 4 | **Complete Failure Strategies** | Error taxonomy with ≥ 10 product-specific codes; HALT vs retry |
| 5 | **Absolute Single Responsibility** | Auto Scaling groups, configurations, rules, scheduled tasks, lifecycle hooks; delegates ECS/ALB/RDS |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Auto Scaling" OR "ESS" OR "弹性伸缩" OR "伸缩组" OR "伸缩配置"
- Task involves CRUD on **scaling groups** (create, describe, modify, enable, disable, delete)
- Task involves **scaling configurations** (create, describe, modify, set as default, delete)
- Task involves **scaling rules** (create, describe, modify, delete, execute)
- Task involves **scheduled tasks** (create, describe, modify, delete)
- Task involves **lifecycle hooks** (create, describe, modify, complete heartbeat, delete)
- Task involves **alarm-based scaling** (create/describe/modify/delete alarm-based rules)
- Task involves **instance management** (attach, detach, remove, enter/exit standby, set health status)
- Task involves **load balancer association** (attach/detach CLB, ALB, VServerGroup, ServerGroup)
- Task involves **notification configurations** (create, describe, modify, delete)
- Task involves **instance refresh** (start, cancel, resume, rollback, query)
- Task involves **tag management** (tag/untag scaling groups)
- Task involves **monitoring scaling activities or diagnostics**
- User asks about elasticity strategy, capacity planning, or automatic scaling

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops`
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops`
- Task is about **ECS instance lifecycle** without scaling → delegate to: `alicloud-ecs-ops`
- Task is about **SLB/ALB configuration** without scaling integration → delegate to: `alicloud-slb-ops` / `alicloud-alb-ops`
- Task is about **RDS instance** without scaling → delegate to: `alicloud-rds-ops`
- User insists on **console-only** flows → state limitation; do not invent undocumented HTTP steps

### Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |
| ECS 实例管理 | `alicloud-ecs-ops` | 创建/修改非伸缩组管理的 ECS 实例 |
| ALB/SLB 配置 | `alicloud-alb-ops` / `alicloud-slb-ops` | 独立配置负载均衡器 |
| RDS 实例管理 | `alicloud-rds-ops` | 独立管理 RDS 实例 |
| VPC 网络 | `alicloud-vpc-ops` | VPC 和交换机管理 |

## Variable Convention (Agent-Readable)

| Var | Category | Items |
|-----|----------|-------|
| `{{env.*}}` | Environment (NEVER ask; HALT if unset) | `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABA_CLOUD_REGION_ID` |
| `{{user.*}}` | User input (ask once, reuse) | `region`, `scaling_group_id/name`, `min/max/desired_size`, `vpc_id`, `vswitch_ids`, `removal_policies`, `scaling_configuration_id/name`, `image_id`, `instance_type`, `security_group_id`, `scaling_rule_id/name/type`, `adjustment_value`, `cooldown`, `scheduled_task_id/name`, `recurrence`, `launch_time`, `lifecycle_hook_id/name`, `transition`, `heartbeat_timeout`, `alarm_task_id/name`, `metric_name`, `threshold`, `comparison_operator`, `instance_ids`, `load_balancer_ids`, `db_instance_ids`, `alb_sg_id`, `notification_arn`, `tag_key/value` |
| `{{output.*}}` | API response (parse per OpenAPI path) | `scaling_group_id`, `scaling_configuration_id`, `scaling_rule_id`, `scheduled_task_id`, `lifecycle_hook_id`, `alarm_task_id`, `scaling_activity_id`, `request_id`, `client_token` |

### Credential Security (Mandatory — 凭据安全)

> **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, or any credential field value in console output, debug messages, error messages, or logs.

| Pattern | Safe (✅) | Unsafe (❌) |
|---------|-----------|-------------|
| Console output | `Secret=<masked>` | `Secret=LTAI5t...` |
| Error messages | `Error: API call failed (credential omitted)` | `Error: InvalidAccessKeySecret.XXX` |
| Env verification | `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"` | `echo "Secret=$ALIBABA_CLOUD_ACCESS_KEY_SECRET"` |
| JIT Go SDK | `AccessKeySecret: tea.String(os.Getenv("..."))` (env read safe) | `fmt.Printf("Config: %+v", config)` or `log.Printf("%+v", ...)` |
| Debug mode | Warning message only | Unmasked credential output |

**Credential verification MUST check existence only, never echo the value.**
- ✅ Bash: `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"`
- ❌ Bash: `echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- ✅ Go: `if os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET") == ""`
- ❌ Go: `fmt.Println(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"))`

> **If any execution flow violates this rule, the skill SHALL be blocked from merge as a security incident.**

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for all paths, fields, enums, and response shapes.
- **ClientToken:** ESS supports `ClientToken` for write operations — always generate UUID v4 for idempotency.
- **Pagination:** Most Describe* operations support `PageNumber` + `PageSize` (default 10, max 50). Use `TotalCount` to paginate.
- **Timestamps:** ISO 8601 format (e.g., `2026-06-07T10:00:00Z`).
- **Async operations:** Scaling group creation, instance attach/detach, scaling rule execution trigger `ScalingActivityId`. Poll with `DescribeScalingActivities`.
- **Quota limits:** Use `DescribeLimitation` to check resource limits per region.

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateScalingGroup | — | `Active` | 5s | 120s |
| EnableScalingGroup | `Inactive` | `Active` | 5s | 60s |
| DisableScalingGroup | `Active` | `Inactive` | 5s | 60s |
| DeleteScalingGroup | any | absent | 5s | 300s |
| AttachInstances | — | attached | 5s | 120s |
| DetachInstances | — | detached | 5s | 120s |
| RemoveInstances | — | removed | 5s | 120s |
| ExecuteScalingRule | — | activity complete | 10s | 300s |
| StartInstanceRefresh | — | refreshed | 10s | 600s |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-07 | Initial ESS skill with dual-path (CLI + SDK) support, GCL required |

## Quick Start

### Prerequisites
- [ ] `aliyun` CLI installed
- [ ] Credentials: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region: `ALIBABA_CLOUD_REGION_ID`

### First Command
```bash
# List all scaling groups in region
aliyun ess DescribeScalingGroups --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Capabilities at a Glance

| Operation | Description | Risk |
|-----------|-------------|------|
| CreateScalingGroup | Create scaling group | Low |
| ModifyScalingGroup | Modify scaling group attributes | Medium |
| DeleteScalingGroup | Delete scaling group | **High** |
| EnableScalingGroup | Enable a scaling group | Medium |
| DisableScalingGroup | Disable a scaling group | Medium |
| CreateScalingConfiguration | Create scaling configuration | Low |
| DeleteScalingConfiguration | Delete scaling configuration | Medium |
| CreateScalingRule | Create scaling rule | Low |
| DeleteScalingRule | Delete scaling rule | Medium |
| ExecuteScalingRule | Execute a scaling rule (trigger scaling) | Medium |
| CreateScheduledTask | Create scheduled task | Low |
| DeleteScheduledTask | Delete scheduled task | Low |
| CreateLifecycleHook | Create lifecycle hook | Low |
| DeleteLifecycleHook | Delete lifecycle hook | Low |
| AttachInstances | Attach ECS/ECI instances to scaling group | Medium |
| DetachInstances | Detach instances from scaling group | Medium |
| RemoveInstances | Remove instances from scaling group | **High** |
| EnterStandby / ExitStandby | Toggle standby mode for instances | Low |
| AttachLoadBalancers | Attach CLB to scaling group | Medium |
| DetachLoadBalancers | Detach CLB from scaling group | Medium |
| StartInstanceRefresh | Start instance refresh | **High** |
| CreateAlarm | Create alarm-based scaling rule | Low |
| DeleteAlarm | Delete alarm-based scaling rule | Medium |
| SetGroupDeletionProtection | Enable/disable group deletion protection | Low |
| TagResources / UntagResources | Manage tags | Low |

> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/ess-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun ess ...` 命令在执行时应替换为 `./scripts/ess-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun ess` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。

## Execution Flows (Agent-Readable)

每项操作遵循 **Pre-flight → Execute → Validate → Recover**。完整 CLI/SDK 命令见 [references/execution-flows.md](references/execution-flows.md).

---

### Operation: Create Scaling Group

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys | HALT; user configures |
| Region | `aliyun ess DescribeRegions` | `{{user.region}}` supported | Suggest valid region |
| VPC/VSwitch | `aliyun vpc DescribeVpcs/DescribeVSwitches` | Exist in region | Delegate to `alicloud-vpc-ops` |
| Quota | `aliyun ess DescribeLimitation` | Below group limit | HALT; request quota increase |

#### Execution

Full CLI command in [references/execution-flows.md §1](references/execution-flows.md#1-create-scaling-group)

#### Post-execution Validation

1. Capture `{{output.scaling_group_id}}` from `$.ScalingGroupId`.
2. Poll `DescribeScalingGroups` until `LifecycleState == Active`.
3. On success, report ID, name, and state.
4. On failure, check status message.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| InvalidParameter | 0-1 | — | Fix args from OpenAPI; retry once |
| QuotaExceeded.ScalingGroup | 0 | — | HALT — request quota increase |
| InsufficientBalance | 0 | — | HALT — recharge account |
| VSwitchId.NotAvailable | 0 | — | Suggest valid VSwitch in same VPC |
| Throttling / 429 | 3 | exponential | Back off; respect Retry-After header |
| InternalError / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Describe/List Scaling Groups

#### Execution — CLI

```bash
aliyun ess DescribeScalingGroups --RegionId "{{user.region}}"
aliyun ess DescribeScalingGroups --ScalingGroupId.1 "{{user.scaling_group_id}}"
```

#### Present to User

| Field | Path |
|-------|------|
| Scaling Group ID | `$.ScalingGroups[].ScalingGroupId` |
| Name | `$.ScalingGroups[].ScalingGroupName` |
| Lifecycle State | `$.ScalingGroups[].LifecycleState` |
| Min/Max/Desired | `$.ScalingGroups[].{MinSize,MaxSize,DesiredCapacity}` |
| Active Config ID | `$.ScalingGroups[].ActiveScalingConfigurationId` |
| VPC / VSwitches | `$.ScalingGroups[].{VpcId,VSwitchIds}` |
| Total Count | `$.TotalCount` |

---

### Operation: Modify Scaling Group

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Scaling group exists | `DescribeScalingGroups` | LifecycleState Active/Inactive | HALT — group not found |
| Capacity validation | Check MinSize ≤ DesiredCapacity ≤ MaxSize | Valid range | HALT — adjust capacity bounds |

#### Execution

Full CLI command in [references/execution-flows.md §2](references/execution-flows.md#2-modify-scaling-group)

#### Post-execution Validation
```bash
aliyun ess DescribeScalingGroups --ScalingGroupId.1 "{{user.scaling_group_id}}"
```

---

### Operation: Delete Scaling Group

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation with `{{user.scaling_group_id}}` and name.
- **MUST** check group has **no instances** (`DescribeScalingInstances`). If instances exist, advise user to `RemoveInstances` first or use `ForceDelete=true`.
- **MUST** verify no scaling activities in progress.
- **RECOMMEND** disabling the scaling group first (`DisableScalingGroup`).
- **RECOMMEND** checking associated resources — deletion cascades.

#### Execution

Full CLI command in [references/execution-flows.md §3](references/execution-flows.md#3-delete-scaling-group)

#### Post-execution Validation

Poll `DescribeScalingGroups` until the group ID is absent. Max wait: 300s. Warn if `ForceDelete=true` was used.

---

### Operation: Scaling Configuration

#### Execution

Full CLI commands in [references/execution-flows.md §4](references/execution-flows.md#4-scaling-configuration)

#### Post-execution Validation

Capture `$.ScalingConfigurationId`. Verify:
```bash
aliyun ess DescribeScalingConfigurations --ScalingConfigurationId.1 "{{output.scaling_configuration_id}}"
```

---

### Operation: Scaling Rules

#### Execution

Full CLI commands in [references/execution-flows.md §5](references/execution-flows.md#5-scaling-rules)

> **ScalingRuleType:** `SimpleScalingRule`, `StepScalingRule`, `TargetTrackingScalingRule`, `PredictiveScalingRule`.
> **AdjustmentType:** `QuantityChangeInCapacity`, `PercentChangeInCapacity`, `TotalCapacity`.
> `ExecuteScalingRule` returns `$.ScalingActivityId`.

---

### Operation: Scheduled Tasks

#### Execution

Full CLI commands in [references/execution-flows.md §6](references/execution-flows.md#6-scheduled-tasks)

> **ScheduledAction:** The `ScalingRuleAri` of the rule to execute.
> **RecurrenceType:** `Daily`, `Weekly`, `Monthly`, `Cron`.

---

### Operation: Lifecycle Hooks

#### Execution

Full CLI commands in [references/execution-flows.md §7](references/execution-flows.md#7-lifecycle-hooks)

> **LifecycleTransition:** `Autoscaling:EC2Instance-Launching`, `Autoscaling:EC2Instance-Terminating`.
> **DefaultResult / LifecycleActionResult:** `CONTINUE`, `ABANDON`.

---

### Operation: Instance Management

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instances exist | `aliyun ecs DescribeInstances` | Instances in region | HALT — verify instance IDs |
| Scaling group active | `DescribeScalingGroups` | Active | HALT — enable group first |

#### Execution

Full CLI commands in [references/execution-flows.md §8](references/execution-flows.md#8-instance-management)

> **RemoveInstances (Destructive):** Must obtain explicit confirmation. Permanently removes instances.

---

### Operation: Load Balancer Association

#### Execution

Full CLI commands in [references/execution-flows.md §9](references/execution-flows.md#9-load-balancer-association)

---

### Operation: Enable/Disable Scaling Group

#### Execution

Full CLI commands in [references/execution-flows.md §10](references/execution-flows.md#10-enabledisable-scaling-group)

#### Post-execution Validation
```bash
aliyun ess DescribeScalingGroups --ScalingGroupId.1 "{{user.scaling_group_id}}"
```

---

### Operation: Alarm-Based Scaling Rules

#### Execution

Full CLI commands in [references/execution-flows.md §11](references/execution-flows.md#11-alarm-based-scaling-rules)

> **Alarm state:** `ALARM` (triggering), `OK` (normal), `INSUFFICIENT_DATA`.

---

### Operation: Instance Refresh

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Scaling group active | `DescribeScalingGroups` | Active | HALT |
| No ongoing refresh | `DescribeInstanceRefreshes` | No active refresh in progress | HALT |

#### Execution

Full CLI commands in [references/execution-flows.md §12](references/execution-flows.md#12-instance-refresh)

> **Instance Refresh (Destructive):** Replaces all existing instances. Must obtain explicit confirmation.

---

### Operation: Notification Configuration

#### Execution

Full CLI commands in [references/execution-flows.md §13](references/execution-flows.md#13-notification-configuration)

> **NotificationType:** `autoscaling:SCALE_OUT_SUCCESS`, `autoscaling:SCALE_IN_SUCCESS`, `autoscaling:SCALE_OUT_ERROR`, `autoscaling:SCALE_IN_ERROR`, `autoscaling:SCALE_REJECT`, etc.

---

### Operation: Tag Management

#### Execution

Full CLI commands in [references/execution-flows.md §14](references/execution-flows.md#14-tag-management)

---

### Operation: Set Group Deletion Protection

```bash
aliyun ess SetGroupDeletionProtection \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --GroupDeletionProtection true
```

---

### Operation: Query Scaling Activities

```bash
aliyun ess DescribeScalingActivities --ScalingGroupId "{{user.scaling_group_id}}" --PageNumber 1 --PageSize 20
aliyun ess DescribeScalingActivityDetail --ScalingActivityId "{{user.scaling_activity_id}}"
```

> Key fields: `StatusCode` (Success/Fail/Rejected), `StatusMessage` (error details).

---

## Operational Best Practices

### Capacity Management
- **MinSize == DesiredCapacity:** Prevents scale-in below desired level.
- **PredictiveScalingRule:** For proactive scaling based on historical patterns.
- **MultiAZPolicy:** Use `BALANCE` for even AZ distribution; `PRIORITY` for cost optimization.

### Health Check Integration
- ESS automatically replaces unhealthy instances when health check enabled.
- Use lifecycle hooks for custom health check logic.
- `SetInstanceHealth` for manual health status override.

### Scaling Configuration Management
- **Keep only active configs:** Periodically delete unused configurations.
- **Use `ModifyScalingGroup --ActiveScalingConfigurationId`** to switch configurations during instance refresh.

### Instance Refresh Best Practices
- Use `MinHealthyPercentage=100` for zero-downtime refresh.
- Use batch mode for controlled rollout.
- Test with canary batch before full rollout.

## Well-Architected Framework Assessment

See [`references/well-architected-assessment.md`](references/well-architected-assessment.md) for detailed five-pillar assessment patterns:

| Pillar | Key Considerations |
|--------|--------------------|
| **Security** | RAM policy for ESS operations; network isolation via VPC; credential masking |
| **Stability** | Multi-AZ group distribution; health check replacement; lifecycle hooks; deletion protection |
| **Cost** | Right-sizing instance types; scheduling scale-in during off-peak; predictive scaling |
| **Efficiency** | Automation via scheduled tasks/alarms; infrastructure-as-code templates |
| **Performance** | Proper scaling thresholds; cooldown tuning; step scaling vs simple scaling |

## Quality Gate (GCL)

This skill uses the Generator-Critic-Loop adversarial quality gate per `AGENTS.md` §12.

| Property | Value |
|----------|-------|
| Classification | `required` |
| max_iter | 2 |
| Most-scrutinized ops | DeleteScalingGroup, RemoveInstances, DetachInstances, StartInstanceRefresh |

See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md) for full GCL configuration.

## See Also — Meta-Skill Rules

| Document | Description |
|----------|-------------|
| [alicloud-skill-generator](../alicloud-skill-generator/) | Meta-skill rules for generating/updating agent skills (monorepo-only) |
| [AGENTS.md](../AGENTS.md) | Full agent guide — post-update self-review, GCL, token efficiency (monorepo-only) |

## Reference Directory

| File | Purpose | Load Condition |
|------|---------|----------------|
| [references/execution-flows.md](references/execution-flows.md) | Full CLI/SDK commands for all operations | 执行操作时 |
| [references/core-concepts.md](references/core-concepts.md) | ESS architecture, limits, quotas, resource relationships | 了解架构时 |
| [references/api-sdk-usage.md](references/api-sdk-usage.md) | Operation map, required fields, request/response, pagination | SDK 开发时 |
| [references/cli-usage.md](references/cli-usage.md) | `aliyun ess` command map, invocation patterns | CLI 参考时 |
| [references/troubleshooting.md](references/troubleshooting.md) | Error codes (≥ 22), ordered diagnostics, recovery | 排查错误时 |
| [references/monitoring.md](references/monitoring.md) | CMS metrics, dashboards, alarms | 配置监控时 |
| [references/integration.md](references/integration.md) | Go bootstrap, env vars, cross-skill delegation | JIT SDK 集成时 |
| [references/well-architected-assessment.md](references/well-architected-assessment.md) | Five-pillar assessment | 架构评估时 |
| [references/rubric.md](references/rubric.md) | GCL rubric — scoring dimensions, sub-rules, termination | GCL 评审时 |
| [references/prompt-templates.md](references/prompt-templates.md) | GCL Generator/Critic prompt templates | GCL 评审时 |
| [references/idempotency-checklist.md](references/idempotency-checklist.md) | Idempotent behavior for retries/automation | 重试逻辑时 |
| [assets/eval_queries.json](assets/eval_queries.json) | Trigger accuracy eval queries | 评测触发准确性时 |
| [assets/example-config.yaml](assets/example-config.yaml) | Example configuration with anchors | 配置参考时 |