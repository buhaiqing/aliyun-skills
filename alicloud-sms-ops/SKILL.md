---
name: alicloud-sms-ops
description: >-
  Use when the user needs to manage Alibaba Cloud SMS Service (dysmsapi) — send
  single or batch SMS, manage SMS signatures and templates, query delivery
  reports, and configure SMS verification codes. Triggers when the user mentions
  "短信服务", "SMS", "短消息", "验证码", "短信签名", "短信模板", "发送短信",
  "群发短信", "短信发送记录", "短信统计", or describes SMS-related scenarios
  (e.g., verification code not received, SMS delivery failure, template audit)
  even without naming the product directly. Not for billing, RAM, or related
  messaging products (email, push notifications, IM).
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.1.0"
  last_updated: "2026-06-21"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "Dysmsapi 2017-05-25 / https://www.alibabacloud.com/help/en/sms"
  cli_applicability: cli-first
  cli_support_evidence: >-
    Confirmed via `aliyun help dysmsapi` — dysmsapi is fully supported by the
    official aliyun CLI. All core operations (SendSms, SendBatchSms,
    QuerySendDetails, QuerySendStatistics, AddSmsSign, QuerySmsSign,
    DeleteSmsSign, AddSmsTemplate, QuerySmsTemplate, DeleteSmsTemplate) have
    matching CLI commands.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud SMS Service Operations Skill

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/sms-skillopt-wrapper.sh` for all SMS CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun sms` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md) |
| GCL | All write operations MUST pass GCL review before execution | [GCL Rubric](references/rubric.md) |

## Common JSON Paths (Centralized)

```
# SendSms:                $.Code, $.Message, $.RequestId, $.BizId
# SendBatchSms:           $.Code, $.Message, $.RequestId, $.BizId
# QuerySendDetails:       $.SmsSendDetailDTOs.SmsSendDetailDTO[].{SendStatus,SendTime,Receiver,TemplateCode,Content}
# QuerySendStatistics:    $.SmsSendStatDTOs.SmsSendStatDTO[].{SmsSendCount,SmsSuccessCount,SmsSpeed}
# QuerySmsSign:           $.SignName, $.SignStatus, $.AuditStatus, $.CreateDate
# QuerySmsTemplate:       $.TemplateCode, $.TemplateName, $.TemplateStatus, $.AuditStatus, $.TemplateContent
# AddSmsSign:             $.SignName, $.RequestId
# AddSmsTemplate:         $.TemplateCode, $.RequestId
# DeleteSmsSign:          $.RequestId
# DeleteSmsTemplate:      $.RequestId
# ModifySmsSign:          $.RequestId
# ModifySmsTemplate:      $.RequestId
```

## Overview

Alibaba Cloud SMS Service (短信服务, dysmsapi) provides short message service
capabilities including single/batch SMS sending, signature and template management,
delivery reports, and verification codes. This skill is an **operational runbook**
for agents: explicit scope, credential rules, pre-flight checks,
**cli-first execution** (official **`aliyun` CLI** as primary path, **JIT Go SDK**
as fallback), response validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: cli-first`:** Official `aliyun` fully supports dysmsapi.
  CLI is the **primary** execution path for all operations. JIT Go SDK is the
  **fallback** only when CLI lacks support for a specific edge-case operation.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud SMS" OR "短信服务" OR "dysmsapi" OR "短消息"
- Task involves **sending SMS** — single or batch (SendSms, SendBatchSms)
- Task involves **SMS signatures** — add, describe, modify, delete, query audit status
- Task involves **SMS templates** — add, describe, modify, delete, query audit status
- Task involves **delivery reports** — query send details, send statistics
- Task involves **verification codes** — send and verify SMS verification codes
- Task involves **SMS packages/billing** — query SMS package details and usage
- Task keywords: 短信, SMS, 验证码, 签名, 模板, 群发, 发送记录, 统计, 短信服务, 短信包, 短信套餐, 套餐余额, 包用量, 套餐使用统计, 批量短信包,
  verification code, signature, template, batch, send, delivery, report
- User asks to deploy, configure, troubleshoot, or monitor SMS **via API, SDK, CLI,
  or automation**
- User reports "验证码没收到", "短信发送失败", "签名审核不通过", "模板审核失败"

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops`
  (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when present)
- Task is about **email service (DirectMail)** → delegate to: `alicloud-directmail-ops`
  (when present)
- Task is about **push notifications (Cloud Push)** → delegate to: `alicloud-push-ops`
  (when present)
- Task is about **instant messaging (IM)** → delegate to: `alicloud-im-ops` (when present)
- User insists on **console-only** flows with no API → state limitation; do not
  invent undocumented HTTP steps

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.phone_numbers}}` | Recipient phone number(s) | Ask once; reuse |
| `{{user.sign_name}}` | SMS signature name | Ask once; reuse |
| `{{user.template_code}}` | SMS template code | Ask once; reuse |
| `{{user.template_content}}` | SMS template content | Ask once; reuse |
| `{{user.template_param}}` | Template parameters (JSON) | Ask once; reuse |
| `{{user.sms_code}}` | Verification code | Ask once; reuse |
| `{{user.out_id}}` | External ID for tracking | Ask once; reuse |
| `{{user.phone_numbers_json}}` | JSON array of recipient phone numbers (batch send) | Ask once; reuse |
| `{{user.sign_names_json}}` | JSON array of SMS signature names (batch send, single element for all recipients) | Ask once; reuse |
| `{{user.template_params_json}}` | JSON array of template parameters (batch send, one per recipient) | Ask once; reuse |
| `{{output.biz_id}}` | From last API or CLI JSON response | Parse per OpenAPI or verified CLI path |
| `{{output.request_id}}` | From API response | For support / correlation |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** Document client request tokens, duplicate names, and
  `ResourceAlreadyExists` behavior per API.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| SendSms | `$.Code` | string | Result code (OK = success) |
| SendSms | `$.Message` | string | Result message |
| SendSms | `$.RequestId` | string | Request ID for correlation |
| SendSms | `$.BizId` | string | Business ID for tracking |
| SendBatchSms | `$.Code` | string | Result code |
| SendBatchSms | `$.Message` | string | Result message |
| SendBatchSms | `$.RequestId` | string | Request ID |
| SendBatchSms | `$.BizId` | string | Business ID |
| QuerySendDetails | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].SendStatus` | int | 3=success, 2=fail, 6=unknown |
| QuerySendDetails | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].SendTime` | string | Send timestamp |
| QuerySendDetails | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].Receiver` | string | Phone number |
| QuerySendDetails | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].TemplateCode` | string | Template code |
| QuerySendDetails | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].Content` | string | SMS content |
| QuerySendStatistics | `$.SmsSendStatDTOs.SmsSendStatDTO[].SmsSendCount` | int | Total sent |
| QuerySendStatistics | `$.SmsSendStatDTOs.SmsSendStatDTO[].SmsSuccessCount` | int | Successful count |
| QuerySendStatistics | `$.SmsSendStatDTOs.SmsSendStatDTO[].SmsSpeed` | long | Speed (SMS/second) |
| QuerySmsSign | `$.SignName` | string | Signature name |
| QuerySmsSign | `$.SignStatus` | int | 0=under review, 1=approved, 2=rejected |
| QuerySmsSign | `$.AuditStatus` | string | Audit status |
| QuerySmsTemplate | `$.TemplateCode` | string | Template code |
| QuerySmsTemplate | `$.TemplateName` | string | Template name |
| QuerySmsTemplate | `$.TemplateStatus` | int | 0=under review, 1=approved, 2=rejected |
| QuerySmsTemplate | `$.TemplateContent` | string | Template content |
| AddSmsSign | `$.SignName` | string | Signature name |
| AddSmsTemplate | `$.TemplateCode` | string | Template code |

### Send Status Codes

| Code | Status | Description |
|------|--------|-------------|
| 0 | 发送中 | Sending in progress |
| 1 | 发送失败 | Send failed |
| 2 | 发送成功 | Send successful |
| 3 | 已接受 | Accepted by carrier |
| 4 | 未知状态 | Unknown status |
| 5 | 等待发送 | Pending send |
| 6 | 发送失败(运营商) | Carrier rejection |

### Signature Status Codes

| Status | Meaning |
|--------|---------|
| 0 | 审核中 (Under review) |
| 1 | 审核通过 (Approved) |
| 2 | 审核失败 (Rejected) |

## Quick Start

### What This Skill Does
This skill enables you to send, manage, and monitor Alibaba Cloud SMS Service
using the `aliyun` CLI (primary) or JIT Go SDK (fallback).

### Prerequisites
- [ ] `aliyun` CLI installed (or Go runtime for JIT fallback)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`
- [ ] SMS signature approved (for sending SMS)
- [ ] SMS template approved (for sending SMS)

### Verify Setup
```bash
# Check CLI and credentials
aliyun dysmsapi QuerySendStatistics --RegionId cn-hangzhou --StartDate "$(date -d "7 days ago" +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d)" --EndDate "$(date +%Y-%m-%d)"
```

### Your First Command
```bash
# Example: Send a single SMS
aliyun dysmsapi SendSms \
  --PhoneNumbers "13800138000" \
  --SignName "阿里云" \
  --TemplateCode "SMS_123456789" \
  --TemplateParam '{"code":"1234"}'
```

### Next Steps
- [Core Concepts](references/core-concepts.md) — Understand SMS Service architecture
- [Common Operations](#execution-flows) — Send, manage signatures/templates, query reports
- [Troubleshooting](references/troubleshooting.md) — Fix common issues

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| SendSms | Send single SMS | Low | Low |
| SendBatchSms | Send batch SMS (up to 100) | Medium | Medium |
| QuerySendDetails | Query delivery reports | Low | None |
| QuerySendStatistics | Query sending statistics | Low | None |
| AddSmsSign | Add SMS signature | Medium | Low |
| QuerySmsSign | Query signature status | Low | None |
| DeleteSmsSign | Delete SMS signature | Low | **Medium** — reversible if re-created |
| ModifySmsSign | Modify SMS signature | Medium | Low |
| AddSmsTemplate | Add SMS template | Medium | Low |
| QuerySmsTemplate | Query template status | Low | None |
| DeleteSmsTemplate | Delete SMS template | Low | **Medium** — reversible if re-created |
| ModifySmsTemplate | Modify SMS template | Medium | Low |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-15 | Initial release with CLI-first execution |

> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/sms-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun sms ...` 命令在执行时应替换为 `./scripts/sms-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun sms` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (SDK/API and `aliyun`) → Validate → Recover**.

> All operations include a JIT Go SDK fallback; see [API & SDK Usage](references/api-sdk-usage.md) for detailed SDK implementation steps.

### Operation: Send Single SMS

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI / deps | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys | HALT; user configures env |
| Region | Region is valid | `cn-hangzhou` or supported region | Suggest valid region |
| Signature | `aliyun dysmsapi QuerySmsSign --SignName {{user.sign_name}}` | SignStatus == 1 (approved) | HALT; user must add/approve signature first |
| Template | `aliyun dysmsapi QuerySmsTemplate --TemplateCode {{user.template_code}}` | TemplateStatus == 1 (approved) | HALT; user must add/approve template first |
| Phone numbers | Validate format | 11-digit mobile number | HALT; invalid phone number format |
| GCL Quality Gate | Delegate to `alicloud-gcl-runner-ops` | Validation passed | Proceed with execution |

#### Execution — CLI (Primary Path)

```bash
# Single SMS send
aliyun dysmsapi SendSms \
  --PhoneNumbers "{{user.phone_numbers}}" \
  --SignName "{{user.sign_name}}" \
  --TemplateCode "{{user.template_code}}" \
  --TemplateParam "{{user.template_param}}" \
  --OutId "{{user.out_id}}"
```

> **Note:** Output is JSON by default. Parse `BizId` and `Code` from response.
> `Code` should be "OK" for success.



#### Post-execution Validation

1. Read `{{output.biz_id}}` from `$.BizId`.
2. Verify `$.Code` == "OK". If not, check `$.Message` for error details.
3. Optionally query delivery status via `QuerySendDetails`.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` / "参数错误" | 0–1 | — | Fix phone number, signature, or template code; retry once if safe |
| `isv.BUSINESS_LIMIT_CONTROL` / "业务限流" | 3 | exponential | Back off 1s, 2s, 4s; respect rate limits |
| `isv.SMS_SIGNATURE_ILLEGAL` / "签名不合法" | 0 | — | HALT; user must fix signature |
| `isv.SMS_TEMPLATE_ILLEGAL` / "模板不合法" | 0 | — | HALT; user must fix template |
| `SignatureDoesNotMatch` / "签名不匹配" | 0 | — | HALT; verify signature name and template belong together |
| `isv.AMOUNT_NOT_ENOUGH` / "余额不足" | 0 | — | HALT; user must recharge |
| `isv.DAY_AMOUNT_LIMIT` / "日发送量限制" | 0 | — | HALT; daily quota exceeded |
| `isv.TEMPLATE_MISSING` / "模板不存在" | 0 | — | HALT; verify template code |
| `isv.SMS_TEMPLATE_UNAPPROVED` / "模板未审核通过" | 0 | — | HALT; user must wait for template approval |
| `isv.SMS_SIGNATURE_UNAPPROVED` / "签名未审核通过" | 0 | — | HALT; user must wait for signature approval |
| `InvalidAccessKey` / 403 | 0 | — | HALT; check credentials |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

> **RequestId Extraction:** On any API error, extract `RequestId` from the response
> for support correlation.

---

### Operation: Send Batch SMS

#### Pre-flight Checks

Same as **Send Single SMS** above, plus:
- Verify phone number list is valid (max 100 numbers)
- Verify template parameters are compatible with batch sending

#### Execution — CLI (Primary Path)

```bash
# Batch SMS send (up to 100 numbers)
aliyun dysmsapi SendBatchSms \
  --PhoneNumberJson "{{user.phone_numbers_json}}" \
  --SignNameJson "{{user.sign_names_json}}" \
  --TemplateCode "{{user.template_code}}" \
  --TemplateParamJson "{{user.template_params_json}}"
```

> **Note:** `SignNameJson` can be a single-element array (same signature for all)
> or per-number array. `TemplateParamJson` must match phone count.



#### Post-execution Validation

1. Read `{{output.biz_id}}` from `$.BizId`.
2. Verify `$.Code` == "OK".
3. Optionally query delivery status via `QuerySendDetails`.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `isv.BUSINESS_LIMIT_CONTROL` | 3 | exponential | Back off; respect rate limits |
| `InvalidParameter.JsonArray` | 0 | — | Fix JSON array format; verify counts match |
| `isv.AMOUNT_NOT_ENOUGH` | 0 | — | HALT; recharge |

---

### Operation: Query Delivery Details

#### Execution — CLI (Primary Path)

```bash
# Query send details for a specific date
aliyun dysmsapi QuerySendDetails \
  --PhoneNumbers "{{user.phone_numbers}}" \
  --SendDate "$(date +%Y-%m-%d)" \
  --PageSize 10 \
  --Page 1
```



#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Send Status | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].SendStatus` | 3=success, 2=fail |
| Send Time | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].SendTime` | ISO 8601 |
| Receiver | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].Receiver` | Phone number |
| Template Code | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].TemplateCode` | Template used |
| Content | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].Content` | SMS content |
| Out ID | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].OutId` | External tracking ID |
| Err Code | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].ErrCode` | Error code if failed |
| Err Msg | `$.SmsSendDetailDTOs.SmsSendDetailDTO[].ErrMsg` | Error message if failed |

---

### Operation: Query Send Statistics

#### Execution — CLI (Primary Path)

```bash
# Query daily statistics for last 7 days
aliyun dysmsapi QuerySendStatistics \
  --StartDate "$(date -d "7 days ago" +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d)" \
  --EndDate "$(date +%Y-%m-%d)"
```



#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Date | `$.SmsSendStatDTOs.SmsSendStatDTO[].SmsDate` | Date |
| Send Count | `$.SmsSendStatDTOs.SmsSendStatDTO[].SmsSendCount` | Total sent |
| Success Count | `$.SmsSendStatDTOs.SmsSendStatDTO[].SmsSuccessCount` | Successful |
| Send Speed | `$.SmsSendStatDTOs.SmsSendStatDTO[].SmsSpeed` | SMS/second |
| Success Rate | `$.SmsSendStatDTOs.SmsSendStatDTO[].SmsSuccessRate` | Success percentage |

---

### Operation: Add SMS Signature

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Sign name format | Validate | Chinese/English, 2-12 chars | HALT; invalid format |
| Sign source | Validate | 0=verification, 1=marketing, 2=notification, 3=utility | HALT; select valid source |
| Sign file | File path valid | Image file for review | HALT; upload sign image |
| GCL Quality Gate | Delegate to `alicloud-gcl-runner-ops` | Validation passed | Proceed with execution |

#### Execution — CLI (Primary Path)

```bash
# Add SMS signature
aliyun dysmsapi AddSmsSign \
  --SignName "{{user.sign_name}}" \
  --SignSource "{{user.sign_source}}" \
  --MoreData '["file://{{user.sign_file}}"]'
```



#### Post-execution Validation

1. Verify `$.Code` == "OK".
2. Signature enters review status (SignStatus == 0).
3. Poll `QuerySmsSign` until status changes (approved/rejected).

#### Failure Recovery

| Error pattern | Max retries | Agent Action |
|---------------|-------------|--------------|
| `isv.SMS_SIGN_NAME_ILLEGAL` | 0 | HALT; fix sign name format |
| `isv.SMS_SIGN_USED_BEFORE` | 0 | HALT; sign already exists |
| `isv.SMS_SIGN_FILE_INVALID` | 0 | HALT; upload valid sign image |

---

### Operation: Query SMS Signature

#### Execution — CLI (Primary Path)

```bash
# Query signature status
aliyun dysmsapi QuerySmsSign --SignName "{{user.sign_name}}"
```



#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Sign Name | `$.SignName` | Signature name |
| Sign Status | `$.SignStatus` | 0=review, 1=approved, 2=rejected |
| Audit Status | `$.AuditStatus` | Detailed audit status |
| Create Date | `$.CreateDate` | Creation timestamp |
| Reason | `$.Reason` | Rejection reason (if rejected) |

---

### Operation: Delete SMS Signature

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: delete signature `{{user.sign_name}}`.
- **MUST NOT** proceed without clear user assent.
- **GCL Quality Gate**: Delegate to `alicloud-gcl-runner-ops` to perform adversarial review before execution.

#### Execution — CLI (Primary Path)

```bash
aliyun dysmsapi DeleteSmsSign --SignName "{{user.sign_name}}"
```



#### Post-execution Validation

1. Verify `$.Code` == "OK".
2. Verify signature no longer exists via `QuerySmsSign`.

---

### Operation: Modify SMS Signature

#### Pre-flight Checks

Same as **Add SMS Signature** above.

#### Execution — CLI (Primary Path)

```bash
aliyun dysmsapi ModifySmsSign \
  --SignName "{{user.sign_name}}" \
  --SignSource "{{user.sign_source}}" \
  --MoreData '["file://{{user.sign_file}}"]'
```



#### Post-execution Validation

1. Verify `$.Code` == "OK".
2. Modified signature enters review status.

#### Failure Recovery
| Error pattern | Max retries | Agent Action |
|---------------|-------------|--------------|
| `isv.SMS_SIGN_NAME_ILLEGAL` | 0 | HALT; fix sign name format |
| `isv.SMS_SIGN_USED_BEFORE` | 0 | HALT; sign already exists |
| `isv.SMS_SIGN_FILE_INVALID` | 0 | HALT; upload valid sign image |
| `InvalidParameter` | 0 | HALT; fix parameters |
| `InternalError` | 3 | 2s, 4s, 8s backoff; retry then HALT |

---

### Operation: Add SMS Template

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Template name | Validate | 2-20 chars | HALT; invalid format |
| Template type | Validate | 0=verification, 1=marketing, 2=notification, 3=utility | HALT; select valid type |
| Template content | Validate | Must contain `${variable}` placeholders | HALT; fix template content |
| Template content format | Validate | ≤500 chars, no forbidden words | HALT; fix content |
| GCL Quality Gate | Delegate to `alicloud-gcl-runner-ops` | Validation passed | Proceed with execution |

#### Execution — CLI (Primary Path)

```bash
# Add SMS template
aliyun dysmsapi AddSmsTemplate \
  --TemplateName "{{user.template_name}}" \
  --TemplateType "{{user.template_type}}" \
  --TemplateContent "{{user.template_content}}" \
  --Remark "{{user.remark}}"
```



#### Post-execution Validation

1. Verify `$.Code` == "OK".
2. Template enters review status (TemplateStatus == 0).
3. Poll `QuerySmsTemplate` until status changes (approved/rejected).

#### Failure Recovery

| Error pattern | Max retries | Agent Action |
|---------------|-------------|--------------|
| `isv.SMS_TEMPLATE_ILLEGAL` | 0 | HALT; fix template content |
| `isv.SMS_TEMPLATE_USED_BEFORE` | 0 | HALT; template already exists |
| `isv.TEMPLATE_CONTENT_LIMIT` | 0 | HALT; template content too long |

---

### Operation: Query SMS Template

#### Execution — CLI (Primary Path)

```bash
# Query template status
aliyun dysmsapi QuerySmsTemplate --TemplateCode "{{user.template_code}}"
```



#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Template Code | `$.TemplateCode` | Template code |
| Template Name | `$.TemplateName` | Template name |
| Template Status | `$.TemplateStatus` | 0=review, 1=approved, 2=rejected |
| Audit Status | `$.AuditStatus` | Detailed audit status |
| Template Content | `$.TemplateContent` | Template content |
| Create Date | `$.CreateDate` | Creation timestamp |
| Reason | `$.Reason` | Rejection reason (if rejected) |

---

### Operation: Delete SMS Template

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: delete template `{{user.template_code}}`.
- **MUST NOT** proceed without clear user assent.
- **GCL Quality Gate**: Delegate to `alicloud-gcl-runner-ops` to perform adversarial review before execution.

#### Execution — CLI (Primary Path)

```bash
aliyun dysmsapi DeleteSmsTemplate --TemplateCode "{{user.template_code}}"
```



#### Post-execution Validation

1. Verify `$.Code` == "OK".
2. Verify template no longer exists via `QuerySmsTemplate`.

---

### Operation: Modify SMS Template

#### Pre-flight Checks

Same as **Add SMS Template** above.

#### Execution — CLI (Primary Path)

```bash
aliyun dysmsapi ModifySmsTemplate \
  --TemplateCode "{{user.template_code}}" \
  --TemplateName "{{user.template_name}}" \
  --TemplateType "{{user.template_type}}" \
  --TemplateContent "{{user.template_content}}" \
  --Remark "{{user.remark}}"
```



#### Post-execution Validation

1. Verify `$.Code` == "OK".
2. Modified template enters review status.

#### Failure Recovery
| Error pattern | Max retries | Agent Action |
|---------------|-------------|--------------|
| `isv.SMS_TEMPLATE_ILLEGAL` | 0 | HALT; fix template content |
| `isv.TEMPLATE_CONTENT_LIMIT` | 0 | HALT; template content too long |
| `InvalidParameter` | 0 | HALT; fix parameters |
| `InternalError` | 3 | 2s, 4s, 8s backoff; retry then HALT |

---

### Operation: Send Verification Code SMS

This is a specialized operation for sending verification codes (common use case).

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Phone number | Validate format | 11-digit mobile | HALT; invalid phone |
| Verification code | Generate or user-provided | 4-6 digit code | HALT; invalid code format |
| Template | Must be verification type (TemplateType=0) | Approved verification template | HALT; use verification template |
| GCL Quality Gate | Delegate to `alicloud-gcl-runner-ops` | Validation passed | Proceed with execution |

#### Execution — CLI (Primary Path)

```bash
# Generate verification code (if not provided)
CODE=$(printf "%06d" $((RANDOM % 1000000)))

# Send verification code SMS
aliyun dysmsapi SendSms \
  --PhoneNumbers "{{user.phone_numbers}}" \
  --SignName "{{user.sign_name}}" \
  --TemplateCode "{{user.template_code}}" \
  --TemplateParam "{\"code\":\"${CODE}\"}"
```



#### Post-execution Validation

1. Verify `$.Code` == "OK".
2. Store verification code and timestamp for later verification.
3. Return `{{output.biz_id}}` for tracking.

#### Verification Code Best Practices

- **Length:** 4-6 digits recommended
- **Validity:** 5-10 minutes typical
- **Rate limit:** Max 1 SMS per phone per minute
- **Retry limit:** Max 3 attempts per verification session

---

### Operation: Cost Optimization Analysis

| Trigger | Purpose | CLI | Key Dimensions |
|---------|---------|-----|----------------|
| "短信成本", "费用分析" | 分析短信发送成本和效率 | `QuerySendStatistics` + `QuerySendDetails` | 发送量 / 成功率 / 模板效率 |

**Optimization:** 分析发送成功率，优化模板内容，减少无效发送。

---

## Well-Architected Framework Integration (卓越架构)

| Pillar | Integration | Reference |
|--------|-------------|-----------|
| 安全 | Phone validation, template review, credential masking | `references/well-architected-assessment.md` §2.1 |
| 稳定 | Retry/backoff, rate limits, delivery tracking | `references/well-architected-assessment.md` §2.2 |
| 成本 | SMS optimization, delivery monitoring, batch sending | `references/well-architected-assessment.md` §2.3 |
| 效率 | Batch sends, template reuse, auto verification codes | `references/well-architected-assessment.md` §2.4 |
| 性能 | Rate management, concurrent optimization | `references/well-architected-assessment.md` §2.5 |

See [references/well-architected-assessment.md](references/well-architected-assessment.md) for the complete specification.

## Token Efficiency Guidelines (P0 — 强制)

Generated skills MUST follow these 6 rules. See meta-skill SKILL.md for detailed examples.

### TE-1: API Query > Static Tables
Use API commands instead of hardcoding version/port/quota tables.
```markdown
aliyun dysmsapi QuerySendStatistics
| Date | Send Count | Success Count |
```

### TE-2: No docstrings in code
Inline comments only. No function-level docstring.
```go
// DO: inline comment only
func sendSms() { ... }
```

### TE-3: Compact error tables
| Error Code | Agent Action |
|------------|-------------|

### TE-4: Centralized JSON paths
File-top comment block; one per resource type.

### TE-5: YAML anchors in example-config.yaml
Use `&dev` / `&prod` to eliminate repeated fields.

### TE-6: Eliminate cross-file duplicate flows
SKILL.md already has full flow, no Complete Workflow in config or SDK files.

---

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Integration](references/integration.md)
- [Well-Architected Assessment](references/well-architected-assessment.md)
- [GCL Rubric](references/rubric.md) — Phase 5 extension GCL rubric (batch send, sign/template delete)
- [GCL Prompt Templates](references/prompt-templates.md) — Generator & Critic prompt templates for GCL delegation

## Quality Gate (GCL)

Phase 5 extension rollout for `recommended` skills per [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Recommended** (Phase 5 extension, `max_iter=3`) |
| Most-scrutinized | `SendBatchSms` (recipient count, template audit, quota), `DeleteSmsSign` / `DeleteSmsTemplate` |

### Changelog

1.0.0 | 2026-06-21 | GCL rollout (rubric + prompt-templates + Quality Gate section).

## Operational Best Practices

- **Least privilege:** RAM policies scoped to SMS APIs only (dysmsapi:*).
- **Template approval:** Submit templates 24-48 hours before campaign launch.
- **Signature consistency:** Use the same signature for related templates.
- **Batch optimization:** Use SendBatchSms for >5 messages to reduce API calls.
- **Rate limiting:** Respect per-second and per-day quotas to avoid throttling.
- **Delivery monitoring:** Use QuerySendDetails to track delivery rates.
- **Cost control:** Set daily/monthly budget alerts via CloudMonitor.

## RAM Policy Examples

### Minimal Least-Privilege Policy
This policy grants full access to all SMS Service APIs for a specific RAM user:
```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dysmsapi:SendSms",
        "dysmsapi:SendBatchSms",
        "dysmsapi:QuerySendDetails",
        "dysmsapi:QuerySendStatistics",
        "dysmsapi:AddSmsSign",
        "dysmsapi:QuerySmsSign",
        "dysmsapi:DeleteSmsSign",
        "dysmsapi:ModifySmsSign",
        "dysmsapi:AddSmsTemplate",
        "dysmsapi:QuerySmsTemplate",
        "dysmsapi:DeleteSmsTemplate",
        "dysmsapi:ModifySmsTemplate"
      ],
      "Resource": "*"
    }
  ]
}
```

### Restricted Least-Privilege Policy
This policy grants only the minimum permissions required for sending SMS and querying reports:
```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dysmsapi:SendSms",
        "dysmsapi:SendBatchSms",
        "dysmsapi:QuerySendDetails",
        "dysmsapi:QuerySendStatistics"
      ],
      "Resource": "*"
    }
  ]
}
```

### Resource-Level Restriction Policy
This policy restricts access to specific SMS signatures and templates:
```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dysmsapi:SendSms",
        "dysmsapi:SendBatchSms"
      ],
      "Resource": [
        "acs:dysmsapi:*:*:signName/MyApprovedSign",
        "acs:dysmsapi:*:*:template/SMS_123456789"
      ]
    }
  ]
}
```
