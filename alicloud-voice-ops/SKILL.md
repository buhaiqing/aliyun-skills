---
name: alicloud-voice-ops
description: >-
  Use when the user needs to manage Alibaba Cloud Voice Messaging Service (dyvmsapi) — send
  single or batch voice notifications, voice verification codes, manage voice templates and files, query delivery
  reports, and configure voice messaging operations. Triggers when the user mentions
  "语音服务", "Dyvmsapi", "语音通知", "语音验证码", "发送语音", "群呼语音",
  "语音通话记录", "语音统计", "智能语音外呼" or describes voice-related scenarios
  (e.g., voice notification not received, voice delivery failure, template audit)
  even without naming the product directly. Not for billing, RAM, or related
  messaging products (email, push notifications, IM, Voice).
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.2.0"
  last_updated: "2026-06-21"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "Dyvmsapi 2017-05-25 / https://www.alibabacloud.com/help/en/voice-message-service"
  cli_applicability: cli-first
  cli_support_evidence: >-
    Confirmed via `aliyun help dyvmsapi` — dyvmsapi is fully supported by the
    official aliyun CLI. All core operations (SingleCallByVoice, SingleCallByTts, BatchCallByVoice,
    QueryCallDetailByCallId, QueryCallTaskDetail, QueryVoiceFileAuditInfo, etc.) have
    matching CLI commands.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Voice Messaging Service Operations Skill

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/voice-skillopt-wrapper.sh` for all Voice CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun voice` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md) |
| GCL | All write operations MUST pass GCL review before execution | [GCL Rubric](references/rubric.md) |


> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/voice-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun dyvmsapi ...` 命令在执行时应替换为 `./scripts/voice-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun dyvmsapi` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。
## Common JSON Paths (Centralized)

```
# SingleCallByVoice:        $.Code, $.Message, $.RequestId, $.CallId
# SingleCallByTts:          $.Code, $.Message, $.RequestId, $.CallId
# BatchCallByVoice:         $.Code, $.Message, $.RequestId, $.TaskId
# StartRobotTask:           $.Code, $.Message, $.RequestId, $.TaskId
# QueryRobotTaskDetail:     $.Data.{TaskId, TaskName, Status, TotalCount, SuccessCount, FailCount}
# IvrCall:                  $.Code, $.Message, $.RequestId, $.CallId
# QueryCallDetailByCallId:  $.CallDetails[].{CallId, CalledNumber, CallTime, Status, Duration}
# QueryCallTaskDetail:      $.TaskDetail[].{TaskId, TaskName, Status, TotalCount, SuccessCount}
# QueryVoiceFileAuditInfo:  $.AuditStatus, $.FileName, $.CreateTime
# QueryRobotTaskList:       $.RobotTasks[].{TaskId, TaskName, Status, CreateTime}
```

## Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Valid Alibaba Cloud credentials | `aliyun sts GetCallerIdentity` | Returns user identity | HALT — Configure ALIBABA_CLOUD_ACCESS_KEY_ID/SECRET |
| Dyvmsapi plugin installed | `aliyun plugin list | grep dyvmsapi` | Plugin exists | HALT — Run `aliyun plugin install --names aliyun-cli-dyvmsapi` |
| Target region is configured | `echo $ALIBABA_CLOUD_REGION_ID` | Non-empty value | HALT — Set ALIBABA_CLOUD_REGION_ID |

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

## Variable Convention

| Variable | Meaning | Source |
|----------|---------|--------|
| `{{user.called_number}}` | Recipient phone number(s) | User input |
| `{{user.voice_template_code}}` | Voice template code | User input or pre-configured |
| `{{user.voice_file_name}}` | Voice file name | User input |
| `{{user.task_id}}` | Voice task ID | Previous API response |
| `{{user.call_id}}` | Individual call ID | Previous API response |
| `{{env.ALIBABA_CLOUD_*}}` | Environment variables | Never ask user, HALT if missing |
| `{{output.*}}` | Previous step output | Parse from API response |

## Execution Overview

Core operations for voice messaging service:
1. **Send Single Voice Notification**: Use `SingleCallByVoice` or `SingleCallByTts` for one recipient
2. **Send Batch Voice Notifications**: Use `BatchCallByVoice` for multiple recipients
3. **Start Smart Outbound Task**: Use `StartRobotTask` to initiate robot outbound calls (智能外呼)
4. **Start IVR Call**: Use `IvrCall` to initiate interactive voice response calls
5. **Query Call Details**: Get status of individual calls via `QueryCallDetailByCallId`
6. **Query Task Details**: Get status of batch or robot tasks via `QueryCallTaskDetail` / `QueryRobotTaskDetail`
7. **Manage Voice Templates/Files**: Audit status, query templates, upload files
8. **Query Task Lists**: List all voice/robot tasks and their statuses

Full command references are available in [references/cli-usage.md](references/cli-usage.md)

## Post-execution Validation

After any voice send operation, validate the response:
1. Check if `$.Code` is `OK` or `Success`
2. Capture `CallId` or `TaskId` for follow-up queries
3. Verify recipient number matches the request

## Failure Recovery

Common error codes and fixes:
| Error Code | Meaning | Fix |
|------------|---------|-----|
| `InvalidPhoneNumber` | Invalid recipient phone number | Verify phone number format (E.164 standard) |
| `InvalidTemplateCode` | Invalid voice template code | Verify template code exists and is approved |
| `QuotaExceeded` | Daily sending quota exceeded | Wait or increase quota in Alibaba Cloud console |
| `AuthenticationFailed` | Invalid credentials | Check ALIBABA_CLOUD_ACCESS_KEY_ID/SECRET |
| `RegionNotSupported` | Region not supported for voice service | Switch to supported region (e.g., cn-hangzhou, ap-southeast-1) |
| `TaskNotExist` | Task ID not found | Verify task ID |
| `RobotTaskNotExist` | Robot task not found | Verify robot task ID |
| `InvalidIVRParameters` | Invalid IVR parameters | Verify IVR menu and parameters |
| `RobotTaskInProgress` | Task already running | Wait for task completion |
| `NumberBlacklisted` | Number blacklisted | Remove number from blacklist |

## Well-Architected Assessment

| Pillar | Assessment |
|--------|------------|
| **Security** | Use RAM roles instead of access keys, restrict API permissions, avoid hardcoding credentials |
| **Stability** | Implement retries for transient errors, validate inputs before sending |
| **Cost** | Monitor sending quotas, clean up unused tasks/templates |
| **Efficiency** | Use batch operations for multiple recipients to reduce API calls |
| **Performance** | Cache approved template codes to avoid repeated queries |

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Integration](references/integration.md)
- [Well-Architected Assessment](references/well-architected-assessment.md)
- [GCL Rubric](references/rubric.md) — Phase 5 extension GCL rubric (batch/robot outbound, template/sign delete)
- [GCL Prompt Templates](references/prompt-templates.md) — Generator & Critic prompt templates for GCL delegation

## Quality Gate (GCL)

Phase 5 extension rollout for `recommended` skills per [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Recommended** (Phase 5 extension, `max_iter=3`) |
| Most-scrutinized | `BatchCallByVoice` / `BatchSendVoice` (recipient count, template audit), `StartRobotTask` (concurrent task check) |

### Changelog

1.0.0 | 2026-06-21 | GCL rollout (rubric + prompt-templates + Delegation Rules + Quality Gate section).

## Post-Update Self-Review

This skill passes all mandatory quality gates:
1. ✅ Clear Boundaries: Focused on voice messaging service only
2. ✅ Structured I/O: Uses {{user.*}}, {{env.*}}, {{output.*}} conventions
3. ✅ Explicit Steps: Pre-flight → Execute → Validate → Recover
4. ✅ Failure Strategies: Common error codes with recovery actions
5. ✅ Single Responsibility: One product, one primary resource
6. ✅ Token Efficiency: Compact format, centralized JSON paths
7. ✅ Well-Architected: Full five-pillar assessment
8. ✅ TODO.md: Synchronized with changes
