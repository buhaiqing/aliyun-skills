---
name: alicloud-ram-ops
description: >-
  Use when the user wants to manage who can access their Alibaba Cloud account
  and what they can do — including access keys, MFA, console login, password
  policies, roles (cross-account or service-linked), custom/system policies,
  STS temporary credentials, and least-privilege audits. Trigger on: RAM, IAM,
  access control, permissions, authorization, security audit, key rotation,
  compliance, 子账号, 授权, 权限管理, 密钥管理, AK轮换, 安全审计, 角色扮演,
  合规检查, 密码策略, 登录设置. Also trigger when the user asks to create or
  manage users/roles/keys, grant permissions, rotate keys, check access, set up
  MFA, audit security, assign or switch roles, or configure password rules —
  even without saying "RAM". Do NOT use for billing, CloudSSO, or non-RAM
  resource management (ECS, RDS, OSS, etc.).
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints. RAM is a global service; most APIs use `cn-hangzhou` as the
  default region regardless of resource location.
metadata:
  author: alicloud
  version: "2.3.0"
  last_updated: "2026-06-07"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "Ram/2015-05-01"
  api_doc: "https://help.aliyun.com/zh/ram/developer-reference/api-ram-2015-05-01-overview"
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun ram --help` and official docs at
    https://help.aliyun.com/zh/ram/developer-reference/cli-reference-ram.
    The `aliyun` CLI exposes the full Ram/2015-05-01 API surface including
    CreateUser, GetUser, ListUsers, CreateRole, GetRole, ListRoles,
    CreatePolicy, GetPolicy, ListPolicies, AttachPolicyToUser,
    AttachPolicyToRole, CreateAccessKey, ListAccessKeys, CreateLoginProfile,
    CreateVirtualMFADevice, and STS AssumeRole.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

# Alibaba Cloud RAM Operations Skill

> **SKILL.md** describes **what** to do (triggers, pre-flight, variables,
> execution overview, links to references/). **references/** describes
> **how** to do it (full commands, JSON paths, error taxonomy, failure
> recovery). Per AGENTS.md §2 Content Separation Rule, do **not** embed
> full execution blocks here — link to the operation file.

## Common JSON Paths (Pointer)

For centralized JSON response paths (`$.User.UserId`, `$.Role.Arn`,
`$.Credentials.SecurityToken`, etc.) and the full per-operation response
field table, see
[`references/api-response-reference.md`](references/api-response-reference.md).

## Overview

Resource Access Management (RAM) is Alibaba Cloud's identity and access
management (IAM) service. This skill is an **operational runbook** for agents:
explicit scope, credential rules, pre-flight checks, **dual-path execution**
(official **SDK/API** and **`aliyun` CLI**), response validation, and failure
recovery for RAM identities, permissions, and security credentials.

**RAM is a global service.** Most RAM APIs use `cn-hangzhou` as the default
region regardless of where your cloud resources are located. Some APIs (e.g.
STS AssumeRole) may accept a regional endpoint, but identity management APIs
are typically global.

**Security-first principle:** RAM operations directly affect account security.
Every destructive action (delete user, delete access key, delete role, detach
policy) MUST have an explicit safety gate. Policy changes MUST be validated
before and after application.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` supports RAM fully.
  You **MUST** ship [`references/cli-usage.md`](references/cli-usage.md) and
  document **both** the SDK step **and** the `aliyun` step for every
  operation (full script blocks live in `references/operations/*.md`).

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "RAM", "访问控制", "IAM", "权限管理", "access control",
  "Resource Access Management", "子账号", "授权", "角色扮演", "密钥管理",
  "安全凭证", "登录设置", "密码策略", "多因素认证"
- Task involves CRUD or lifecycle operations on **RAM users** (create,
  describe, modify, delete, list, enable/disable)
- Task involves **RAM user groups** (create, add/remove users, attach/detach
  policies, delete)
- Task involves **RAM roles** (create, describe, modify trust policy, delete,
  assume role via STS)
- Task involves **RAM policies** (create custom policy, describe, list,
  attach/detach to user/group/role, delete)
- Task involves **access keys** (create, list, update status, delete, rotate,
  audit last used)
- Task involves **login profiles** (enable console login, set password policy,
  reset password, delete)
- Task involves **MFA / virtual MFA devices** (create, bind, unbind, delete)
- Task involves **STS temporary credentials** (AssumeRole, GetCallerIdentity)
- Task involves **least-privilege audits** (analyze attached policies,
  identify over-permissioned identities, unused access keys)
- Task keywords: user, group, role, policy, permission, AK, AccessKey,
  MFA, login profile, STS, AssumeRole, trust policy, principal, action,
  resource, effect, condition, least privilege, audit, rotation,
  子账号, 授权, 角色, 策略, 密钥, 登录, 密码, MFA, 权限审计

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to:
  `alicloud-billing-ops` (when present)
- Task is about creating or managing non-RAM cloud resources (ECS, RDS, etc.)
  → delegate to the product-specific `alicloud-[product]-ops` skill
- Task is about configuring CloudSSO → delegate to:
  `alicloud-cloudsso-ops` (when present)
- User insists on **console-only** flows with no API → state limitation;
  do not invent undocumented HTTP steps

## Variable Convention (Pointer)

For the full placeholder table (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`),
collection constraints, and credential-hygiene rules, see
[`references/variable-convention.md`](references/variable-convention.md).
All operations in `references/operations/*.md` and the prompt templates
in `references/prompt-templates.md` reference these placeholders.

## Quick Start (Agent-Readable)

Use this section to quickly understand what the skill can do and how to get
started. Each common task below links to the full operation documentation.

### Operation Index (by Resource)

| Resource | Operations | Reference |
|----------|-----------|-----------|
| **RAM User** | Create / Describe / Update / Delete | [user-operations.md](references/operations/user-operations.md) |
| **Login Profile** | Create / Get / Update / Delete | [user-operations.md §LoginProfile](references/operations/user-operations.md#operation-create-login-profile) |
| **Access Key** | Create / List / Update / Delete / Rotate | [user-operations.md §AccessKey](references/operations/user-operations.md) |
| **Virtual MFA** | Create / Bind / Unbind / Delete | [user-operations.md §MFA](references/operations/user-operations.md) |
| **User Group** | Create / Describe / Add/Remove User / Delete | [group-operations.md](references/operations/group-operations.md) |
| **RAM Role** | Create / Describe / Update / Delete | [role-operations.md](references/operations/role-operations.md) |
| **STS** | AssumeRole / GetCallerIdentity | [role-operations.md §STS](references/operations/role-operations.md#operation-sts-assumerole) |
| **Policy** | Create / CreateVersion / Get / Attach / Detach / Delete | [policy-operations.md](references/operations/policy-operations.md) |
| **Password Policy** | Set / Get | [audit-operations.md](references/operations/audit-operations.md) |
| **Audit** | Least-Privilege Audit (multi-step) | [audit-operations.md §Audit](references/operations/audit-operations.md#operation-least-privilege-audit) |
| **Key Rotation** | Multi-step supervised flow | [user-operations.md §Rotation](references/operations/user-operations.md#operation-access-key-rotation) |

### Common Task Templates (high-level)

For step-by-step recipes with one-line dispatch per step, see
[`references/prompt-examples.md`](references/prompt-examples.md). The most
common:

- "Create a RAM user and grant ECS read-only access" → `CreateUser` →
  `AttachPolicyToUser`
- "Create a RAM role for ECS instances" → `GetCallerIdentity` → `CreateRole`
  (ECS service principal)
- "Rotate an access key" → 6-step supervised flow (see
  [`user-operations.md`](references/operations/user-operations.md#operation-access-key-rotation))
- "Audit all permissions" → `ListUsers` → per-user `ListPoliciesForUser` +
  `ListAccessKeys` + `GetAccessKeyLastUsed` → report (see
  [`audit-operations.md`](references/operations/audit-operations.md#operation-least-privilege-audit))
- "Set up MFA for a user" → `CreateVirtualMFADevice` → user provides 2 TOTP
  codes → `BindMFADevice`
- "Enable console login for a user" → `CreateLoginProfile` (password shown
  once, `PasswordResetRequired=true`)

For a Chinese-language user-interaction quick reference (intent → action),
see [`references/prompt-examples.md` §2](references/prompt-examples.md#2-user-interaction-quick-reference-中文对话模板).

## Execution Pattern (recap)

Every operation follows: **Pre-flight → Execute (SDK/API and `aliyun`) →
Validate → Recover**. Do not skip phases. Full Pre-flight tables, command
blocks, validation queries, and Failure Recovery tables live in
[`references/operations/`](references/operations/) — this SKILL.md only
links to them.

For API/SDK request field requirements and pagination rules, see
[`references/api-sdk-usage.md`](references/api-sdk-usage.md). For CLI
output conventions (JSON by default, `--output cols=`, URL-encoded
`PolicyDocument`), see [`references/cli-usage.md`](references/cli-usage.md).

## Prerequisites

见 [执行环境配置](../alicloud-skill-generator/references/execution-environment.md)

RAM 是全局服务，默认 Region `cn-hangzhou`。

---

## Well-Architected Assessment (卓越架构)

See [references/well-architected.md](references/well-architected.md) for
RAM-specific WAF guidance (security/stability/cost/efficiency/performance
pillars) and [references/operational-best-practices.md](references/operational-best-practices.md)
for 7 RAM best practice guidelines.

## Quality Gate (GCL)

This skill is the **fourth rollout** of the Generator-Critic-Loop (GCL)
adversarial quality gate defined in
[`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate).
Every runtime execution of an `alicloud-ram-ops` operation MUST be wrapped
in a GCL loop before the result is returned to the user.

For the full GCL scope (`max_iter=2`, 4th rollout, all 18 RAM ops covered),
the 9-row Per-Op Safety Sub-Rules table, RAM-specific dimensions
(Region/Well-Architected/Credential Hygiene = 1 absolute), termination
conditions, trace persistence, and the changelog, see
[`references/gcl-quality-gate.md`](references/gcl-quality-gate.md). The
underlying rubric and prompt templates live in
[`references/rubric.md`](references/rubric.md) and
[`references/prompt-templates.md`](references/prompt-templates.md).

> **Why RAM warrants stricter GCL rules (summary):** RAM is the
> credential-management meta-layer — a bug here is a bug in *every*
> downstream skill. Three consequences: (1) Credential Hygiene is
> double-strict (also covers `CreateAccessKey` / `CreateLoginProfile`
> outputs), (2) `DeleteUser` requires a 5-step dependency cascade,
> (3) Privilege-escalation detection runs across all RAM ops.
> Full discussion: [`gcl-quality-gate.md` §2](references/gcl-quality-gate.md).

## Reference Directory

| File | Purpose |
|------|---------|
| [core-concepts.md](references/core-concepts.md) | RAM architecture, limits, dependencies |
| [api-sdk-usage.md](references/api-sdk-usage.md) | OpenAPI spec + SDK Operations Map + Request/Response notes |
| [cli-usage.md](references/cli-usage.md) | `aliyun ram` / `aliyun sts` CLI conventions |
| [api-response-reference.md](references/api-response-reference.md) | **JSON paths + Response Field Table + error taxonomy** |
| [variable-convention.md](references/variable-convention.md) | **Placeholder table + collection constraints + credential hygiene** |
| [prompt-examples.md](references/prompt-examples.md) | **Common task templates + Chinese interaction quick reference** |
| [troubleshooting.md](references/troubleshooting.md) | Error code diagnostics, recovery |
| [policy-examples.md](references/policy-examples.md) | Ready-to-use policy JSON |
| [integration.md](references/integration.md) | Go bootstrap, env vars, credential rules |
| [operations/user-operations.md](references/operations/user-operations.md) | User + LoginProfile + AccessKey + MFA + Key Rotation |
| [operations/group-operations.md](references/operations/group-operations.md) | Group CRUD + Add/Remove User |
| [operations/role-operations.md](references/operations/role-operations.md) | Role + STS AssumeRole + GetCallerIdentity + Trust Policy |
| [operations/policy-operations.md](references/operations/policy-operations.md) | Policy + Version + Attach/Detach |
| [operations/audit-operations.md](references/operations/audit-operations.md) | Password Policy + Least-Privilege Audit + Key Rotation |
| [well-architected.md](references/well-architected.md) | WAF security/stability/cost/efficiency/performance |
| [operational-best-practices.md](references/operational-best-practices.md) | 7 best practice guidelines |
| [diagnostic-quick-reference.md](references/diagnostic-quick-reference.md) | 20 error patterns + diagnostic commands |
| [intelligent-inspection.md](references/intelligent-inspection.md) | 智能巡检 (security audit flow) |
| [gcl-quality-gate.md](references/gcl-quality-gate.md) | **GCL scope / Per-Op Safety / Termination / Trace / Changelog** |
| [rubric.md](references/rubric.md) | 5 core + 3 Aliyun dimensions, 18 per-op Safety sub-rules, 7-pattern privilege-escalation |
| [prompt-templates.md](references/prompt-templates.md) | Generator & Critic templates with one-shot delivery + 5-step cascade |

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `dual-path`，CLI/SDK 已覆盖，无需 code snippets.
