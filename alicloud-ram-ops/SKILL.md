---
name: alicloud-ram-ops
description: >-
  Use when you need to manage Alibaba Cloud RAM (Resource Access Management)
  identities, permissions, and access policies. Covers RAM users, user groups,
  roles, policies, access keys, MFA, and login profiles. Invoke when the user
  mentions RAM, access control, IAM, permissions, users, groups, roles,
  policies, AK rotation, MFA setup, or least-privilege audits.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints. RAM is a global service; most APIs use `cn-hangzhou` as the
  default region regardless of resource location.
metadata:
  author: alicloud
  version: "2.0.0"
  last_updated: "2026-05-14"
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
  You **MUST** ship **`references/cli-usage.md`** and document **both** the
  SDK step **and** the `aliyun` step for every operation.

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

### Delegation Rules

- If a RAM role needs to access ECS/RDS/OSS, the role itself is managed here,
  but resource-level policies on those services are managed in their respective
  skills.
- Multi-product requests: handle RAM identity/permission setup first, then
  delegate resource provisioning to the appropriate product skill.

## Variable Convention (Agent-Readable)

Structured placeholders reduce injection ambiguity and unsafe prompts:

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | RAM global default: `cn-hangzhou` |
| `{{user.user_name}}` | User-supplied RAM user name | Ask once; reuse; validate format |
| `{{user.group_name}}` | User-supplied RAM group name | Ask once; reuse; validate format |
| `{{user.role_name}}` | User-supplied RAM role name | Ask once; reuse; validate format |
| `{{user.policy_name}}` | User-supplied policy name | Ask once; reuse; validate format |
| `{{user.policy_document}}` | User-supplied or generated policy JSON | Validate JSON structure before use |
| `{{user.access_key_id}}` | Specific access key to act on | Ask when operation targets a key |
| `{{output.user_id}}` | From CreateUser / GetUser response | Parse per OpenAPI |
| `{{output.role_arn}}` | From CreateRole / GetRole response | Parse per OpenAPI: `acs:ram::{{account_id}}:role/{{role_name}}` |
| `{{output.policy_type}}` | `Custom` or `System` | Parse per OpenAPI |
| `{{output.access_key_id}}` | From CreateAccessKey response | Parse per OpenAPI; SECRET shown ONLY once |
| `{{output.access_key_secret}}` | From CreateAccessKey response | Parse per OpenAPI; show ONCE, then NEVER log again |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing.

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `{{output.access_key_secret}}`, `AccessKeySecret`, or any credential/secret field value in console output, debug messages, error messages, or logs. `{{output.access_key_secret}}` from CreateAccessKey MUST be shown to the user **ONCE** and NEVER logged or stored.
>
> **Masking rules across all execution paths:**
> | Execution Path | Safe Pattern | Unsafe Pattern |
> |----------------|-------------|----------------|
> | Console output | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>` | Raw credential value in output |
> | Error messages | `Error: API call failed (credential omitted)` | Error containing raw credential value |
> | Log files | `[INFO] Credentials: Secret=***` | `[INFO] AK Secret: LTAI5t...` |
> | Verification | `if os.Getenv("var") != ""` (existence check only) | `echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET` |
> | JIT Go SDK | env read via `os.Getenv(...)` is safe; never print `Config` struct | `fmt.Printf("Config: %+v", config)` |
> | Debug/verbose | `Debug mode may expose credentials (use with caution)` | Un-masked credential in debug output |
>
> **Credential verification MUST check existence only**, never echo the value. This applies to ALL execution flows (SDK, CLI, and debugging scripts).

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response
  shapes. RAM uses **RPC-style** APIs with version `2015-05-01`.
- **Errors:** Map SDK/HTTP errors to `code` / `message` / `requestId` fields.
  Common RAM errors: `EntityAlreadyExists`, `EntityNotExist`,
  `InvalidParameter`, `NoPermission`, `DeleteConflict`.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** RAM APIs are generally NOT idempotent for create
  operations. Creating a user/role/policy with the same name returns
  `EntityAlreadyExists`. Document this behavior and ask reuse vs new name.
- **Global service:** Most RAM APIs do not require `RegionId` or use
  `cn-hangzhou` as default. STS AssumeRole may require a regional endpoint.

### Response Field Table (RAM-Specific)

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateUser | `$.User.UserId` | string | Unique RAM user ID |
| CreateUser | `$.User.UserName` | string | Requested user name |
| CreateUser | `$.User.CreateDate` | string | ISO 8601 timestamp |
| GetUser | `$.User.UserId` | string | User ID |
| GetUser | `$.User.LastLoginDate` | string | Last console login (may be absent) |
| ListUsers | `$.Users.User[]` | array | List of user objects |
| CreateRole | `$.Role.RoleId` | string | Unique role ID |
| CreateRole | `$.Role.RoleName` | string | Requested role name |
| CreateRole | `$.Role.Arn` | string | Full ARN for AssumeRole |
| CreateRole | `$.Role.AssumeRolePolicyDocument` | string | URL-encoded trust policy |
| GetRole | `$.Role.Arn` | string | Role ARN |
| ListRoles | `$.Roles.Role[]` | array | List of role objects |
| CreatePolicy | `$.Policy.PolicyName` | string | Policy name |
| CreatePolicy | `$.Policy.PolicyType` | string | `Custom` or `System` |
| CreatePolicy | `$.Policy.DefaultVersion` | string | Version ID (e.g. `v1`) |
| GetPolicy | `$.Policy.PolicyDocument` | string | URL-encoded policy JSON |
| ListPolicies | `$.Policies.Policy[]` | array | List of policy objects |
| CreateAccessKey | `$.AccessKey.AccessKeyId` | string | New AK ID (show once) |
| CreateAccessKey | `$.AccessKey.AccessKeySecret` | string | New AK secret (show ONCE) |
| CreateAccessKey | `$.AccessKey.Status` | string | `Active` |
| ListAccessKeys | `$.AccessKeys.AccessKey[]` | array | List of access keys |
| AssumeRole | `$.Credentials.AccessKeyId` | string | Temporary AK |
| AssumeRole | `$.Credentials.AccessKeySecret` | string | Temporary secret |
| AssumeRole | `$.Credentials.SecurityToken` | string | STS token |
| AssumeRole | `$.Credentials.Expiration` | string | ISO 8601 expiration |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.1.0 | 2026-05-14 | UX optimization: added Quick Start, Common Scenarios, User Interaction Patterns, Diagnostic Quick Reference, and expanded Chinese trigger keywords |
| 2.0.0 | 2026-05-14 | Initial RAM skill with dual-path execution, full identity lifecycle, policy management, STS, and security gates |

## Quick Start (Agent-Readable)

Use this section to quickly understand what the skill can do and how to get
started. Each common task below links to the full operation documentation.

### Common Task Templates

#### Task: "Create a RAM user and grant ECS read-only access"

```
Step 1: CreateUser → Step 2: AttachPolicyToUser (AliyunECSReadOnlyAccess) → Done
```

#### Task: "Create a RAM role for ECS instances"

```
Step 1: GetCallerIdentity → Step 2: CreateRole (with ECS service principal) → Done
```

#### Task: "Rotate an access key"

```
Step 1: CreateAccessKey → Step 2: Display new key → Step 3: Wait for user confirmation
→ Step 4: UpdateAccessKey (old key → Inactive) → Step 5: Wait grace period
→ Step 6: DeleteAccessKey (old key)
```

#### Task: "Audit all permissions"

```
Step 1: ListUsers → Step 2: For each user → ListPoliciesForUser + ListAccessKeys
→ Step 3: GetAccessKeyLastUsed → Step 4: Report findings
```

#### Task: "Set up MFA for a user"

```
Step 1: CreateVirtualMFADevice → Step 2: Present QR code to user
→ Step 3: BindMFADevice (with two TOTP codes from user) → Done
```

#### Task: "Enable console login for a user"

```
Step 1: CreateLoginProfile → Step 2: Display password to user once → Done
```

#### Task: "Create a custom policy for ECS management in cn-hangzhou"

```
Step 1: CreatePolicy (with region-restricted policy document) → Done
```

### User Interaction Quick Reference

| User says... | Agent should... | Operation |
|-------------|----------------|-----------|
| "帮我创建一个子账号" | Ask for user name, then CreateUser | Create RAM User |
| "给这个用户授权" | Ask for policy name and type, then AttachPolicyToUser | Attach Policy to User |
| "帮我生成一个AK" | Ask for user name, then CreateAccessKey | Create Access Key |
| "我要轮换密钥" | Ask for user name, then follow rotation flow | Access Key Rotation |
| "检查一下权限" | Run Least-Privilege Audit flow | Least-Privilege Audit |
| "设置密码策略" | Ask for policy parameters, then SetPasswordPolicy | Set Password Policy |
| "帮我开个控制台登录" | Ask for user name, then CreateLoginProfile | Create Login Profile |
| "绑定MFA" | Ask for user name, then CreateVirtualMFADevice + BindMFADevice | Bind MFA Device |
| "创建一个角色" | Ask for role name and trust policy, then CreateRole | Create RAM Role |
| "删除这个用户" | Run Safety Gate, then DeleteUser with dependency cleanup | Delete RAM User |

## Common Scenarios (Agent-Readable)

Real-world scenarios with step-by-step flows. Use these as templates when the
user's request matches a common pattern.

### Scenario 1: Onboard a New Developer

**Goal:** Create a RAM user with console access and ECS read-only permissions.

```
1. CreateUser --UserName "dev-zhangsan" --DisplayName "张三"
2. CreateLoginProfile --UserName "dev-zhangsan" --PasswordResetRequired true
   → Display password to user ONCE
3. AttachPolicyToUser --PolicyName "AliyunECSReadOnlyAccess" --PolicyType System
4. (Optional) CreateAccessKey --UserName "dev-zhangsan"
   → Display AccessKeyId and AccessKeySecret ONCE
5. Report: "User dev-zhangsan created. Console login enabled. ECS read-only access granted."
```

### Scenario 2: Grant Cross-Account Access

**Goal:** Allow another Alibaba Cloud account to assume a role in this account.

```
1. GetCallerIdentity → Get {{output.account_id}}
2. CreateRole --RoleName "cross-account-admin" \
     --AssumeRolePolicyDocument '{"Statement":[{"Action":"sts:AssumeRole","Effect":"Allow",\
       "Principal":{"RAM":["acs:ram::{{other_account_id}}:root"]},"Version":"1"}]}'
3. CreatePolicy --PolicyName "CrossAccountAdminPolicy" --PolicyDocument '...'
4. AttachPolicyToRole --PolicyName "CrossAccountAdminPolicy" --PolicyType Custom
5. Report: "Role cross-account-admin created. Other account can assume it via STS."
```

### Scenario 3: Emergency Access Key Rotation

**Goal:** Rotate a compromised or expiring access key with minimal downtime.

```
1. ListAccessKeys --UserName "{{user.user_name}}" → Identify old key
2. CreateAccessKey --UserName "{{user.user_name}}"
   → Display new key pair ONCE
3. Instruct user: "Update your applications with the new access key."
4. Wait for user confirmation.
5. UpdateAccessKey --UserName "{{user.user_name}}" --AccessKeyId "{{old_key}}" --Status Inactive
6. Monitor for errors during grace period (default 24h).
7. After user confirms: DeleteAccessKey --UserName "{{user.user_name}}" --AccessKeyId "{{old_key}}"
```

### Scenario 4: Full Permission Audit

**Goal:** Identify over-permissioned users and unused access keys.

```
1. ListUsers → For each user:
   a. ListPoliciesForUser → Check for wildcard actions
   b. ListAccessKeys → For each key:
      - GetAccessKeyLastUsed → Check if unused > 90 days
   c. GetLoginProfile → Check if console login is enabled but unused
2. ListRoles → For each role:
   a. ListPoliciesForRole → Check for over-permission
3. Report with risk levels:
   - HIGH: Action "*" or Resource "*" without Condition
   - MEDIUM: Key unused > 90 days
   - LOW: Console login enabled but never used
```

### Scenario 5: Set Up MFA for All Users

**Goal:** Enforce MFA for all RAM users with console access.

```
1. SetPasswordPolicy --RequireSymbols true --MinimumPasswordLength 12 --MaxPasswordAge 90
2. ListUsers → For each user:
   a. GetUserMFAInfo → If no MFA:
      - CreateVirtualMFADevice → Present QR code
      - Ask user for two consecutive TOTP codes
      - BindMFADevice
3. UpdateLoginProfile --MFABindRequired true (for each user with login profile)
4. Report: "MFA enforced for all users with console access."
```

### User Interaction Patterns

The agent SHOULD follow these interaction patterns to provide a consistent
user experience:

#### Pattern 1: Progressive Disclosure

Do NOT dump all information at once. Instead, reveal information step by step:

```
User: "帮我创建一个子账号"
Agent: "好的，请提供以下信息：
  1. 用户名（必填，1-64个字符，支持字母、数字、.、@、-、_）
  2. 显示名称（可选）
  3. 手机号（可选）
  4. 邮箱（可选）"
User: "用户名 dev-zhangsan，显示名称 张三"
Agent: "好的，正在创建用户 dev-zhangsan..."
Agent: "✅ 用户创建成功！
  - 用户名: dev-zhangsan
  - 显示名称: 张三
  - 用户ID: 123456789
  是否需要为此用户开启控制台登录或生成AccessKey？"
```

#### Pattern 2: Confirmation Before Destruction

For any destructive operation, ALWAYS:

1. State exactly what will happen
2. List the consequences
3. Ask for explicit confirmation
4. Wait for user's clear assent before proceeding

```
Agent: "⚠️ 即将执行删除操作：
  - 删除RAM用户: dev-zhangsan
  - 此操作不可逆
  - 该用户的所有AccessKey、登录配置、MFA设备将被一并删除
  - 该用户从所有用户组中移除
  确认继续？(yes/no)"
```

#### Pattern 3: Suggest Next Steps

After completing an operation, proactively suggest what the user might want
to do next:

```
Agent: "✅ 用户 dev-zhangsan 已创建。
  接下来您可以：
  - 开启控制台登录（CreateLoginProfile）
  - 生成AccessKey（CreateAccessKey）
  - 授权（AttachPolicyToUser）
  - 添加到用户组（AddUserToGroup）
  请问需要继续哪一项？"
```

#### Pattern 4: Handle Multi-Step Requests

When a user asks for a complex task, break it down and confirm each step:

```
User: "帮我创建一个有ECS管理权限的子账号"
Agent: "好的，这个任务需要以下步骤：
  1. 创建RAM用户
  2. 授权ECS管理权限
  3. （可选）开启控制台登录
  4. （可选）生成AccessKey
  请提供用户名，我先创建用户。"
```

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (SDK/API and `aliyun`) → Validate →
Recover**. Do not skip phases.

---

### Operation: Create RAM User

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SDK / deps | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys / valid config | HALT; user configures env |
| User name format | Regex: `^[a-zA-Z0-9_.@-]{1,64}$` | Valid | Ask for valid name |
| Duplicate | `aliyun ram GetUser --UserName {{user.user_name}}` | `EntityNotExist` | Ask reuse vs new name |

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
aliyun ram CreateUser \
  --UserName "{{user.user_name}}" \
  --DisplayName "{{user.display_name}}" \
  --MobilePhone "{{user.mobile_phone}}" \
  --Email "{{user.email}}"
```

> Optional parameters: `DisplayName`, `MobilePhone`, `Email`, `Comments`.
> All are optional; only `UserName` is required.

#### Execution — JIT Go SDK (Fallback Path)

```go
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    ram "github.com/alibabacloud-go/ram-20150501/v2/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("ram.aliyuncs.com"),
    }

    client, err := ram.NewClient(config)
    if err != nil {
        panic(err)
    }

    request := &ram.CreateUserRequest{
        UserName: tea.String(os.Getenv("RAM_USER_NAME")),
    }

    response, err := client.CreateUser(request)
    if err != nil {
        panic(err)
    }

    fmt.Println(tea.ToString(response.Body))
}
```

> SDK package: `github.com/alibabacloud-go/ram-20150501/v2/client`

#### Post-execution Validation

1. Read `{{output.user_id}}` from `$.User.UserId`.
2. Call `GetUser` to confirm existence:
   ```bash
   aliyun ram GetUser --UserName "{{user.user_name}}"
   ```
3. Report `UserName`, `UserId`, and `CreateDate` to the user.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityAlreadyExists.User` | 0 | — | Ask reuse vs new name |
| `InvalidParameter.UserName` | 0 | — | Fix name format; retry once |
| `InvalidParameter.DisplayName` | 0 | — | Fix display name; retry once |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Describe RAM User

#### Execution — CLI

```bash
# Get single user
aliyun ram GetUser --UserName "{{user.user_name}}"

# List all users (paginated)
aliyun ram ListUsers --MaxItems 100

# Extract specific fields
aliyun ram GetUser --UserName "{{user.user_name}}" \
  --output cols=UserName,UserId,CreateDate,LastLoginDate rows=User
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| UserName | `$.User.UserName` | Plain text |
| UserId | `$.User.UserId` | Plain text |
| CreateDate | `$.User.CreateDate` | ISO 8601 |
| LastLoginDate | `$.User.LastLoginDate` | May be absent if never logged in |
| DisplayName | `$.User.DisplayName` | May be absent |
| Email | `$.User.Email` | May be absent |
| MobilePhone | `$.User.MobilePhone` | May be absent |

---

### Operation: Update RAM User

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `aliyun ram GetUser --UserName {{user.user_name}}` | Success | HALT; create user first |
| New user name format | If renaming, regex `^[a-zA-Z0-9_.@-]{1,64}$` | Valid | Ask for valid name |
| Duplicate new name | If renaming, `GetUser` with new name | `EntityNotExist` | Ask different name |

#### Execution — CLI

```bash
aliyun ram UpdateUser \
  --UserName "{{user.user_name}}" \
  --NewUserName "{{user.new_user_name}}" \
  --NewDisplayName "{{user.new_display_name}}" \
  --NewMobilePhone "{{user.new_mobile_phone}}" \
  --NewEmail "{{user.new_email}}"
```

> At least one of `NewUserName`, `NewDisplayName`, `NewMobilePhone`, `NewEmail` must be provided.
> `NewUserName` renames the user; all other fields update existing attributes.

#### Post-execution Validation

```bash
aliyun ram GetUser --UserName "{{user.new_user_name}}"
```

Report updated fields to user.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.User` | 0 | — | HALT; user does not exist |
| `EntityAlreadyExists.User` | 0 | — | New name already taken; ask different name |
| `InvalidParameter.NewUserName` | 0 | — | Fix format; retry once |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |

---

### Operation: Delete RAM User

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: "This will permanently delete RAM
  user `{{user.user_name}}` and all associated access keys, login profiles,
  MFA devices, and group memberships. This action is irreversible."
- **MUST NOT** proceed without clear user assent.
- **MUST** check for attached policies and group memberships; warn user that
  these will be implicitly detached.
- **MUST** verify and optionally clean up dependencies in this order:
  1. **Detach policies:** `ListPoliciesForUser` → `DetachPolicyFromUser` for each
  2. **Remove from groups:** `ListGroupsForUser` → `RemoveUserFromGroup` for each
  3. **Delete access keys:** `ListAccessKeys` → `DeleteAccessKey` for each
  4. **Delete login profile:** `GetLoginProfile` → `DeleteLoginProfile`
  5. **Unbind MFA:** `GetUserMFAInfo` → `UnbindMFADevice` → `DeleteVirtualMFADevice`

> **Note:** Some dependencies can be implicitly deleted with the user, but
> explicit cleanup prevents `DeleteConflict` errors and ensures audit clarity.

#### Execution — CLI

```bash
aliyun ram DeleteUser --UserName "{{user.user_name}}"
```

#### Post-execution Validation

1. Call `GetUser` — expect `EntityNotExist.User` or equivalent 404.
2. Call `ListAccessKeys` — should return empty for this user.
3. Report success to user.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.User` | 0 | — | HALT; user does not exist |
| `DeleteConflict.User.Group` | 0 | — | Remove from all groups first |
| `DeleteConflict.User.AccessKey` | 0 | — | Delete all access keys first |
| `DeleteConflict.User.Policy` | 0 | — | Detach all policies first |
| `DeleteConflict.User.LoginProfile` | 0 | — | Delete login profile first |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Create RAM User Group

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Group name format | Regex: `^[a-zA-Z0-9_.@-]{1,64}$` | Valid | Ask for valid name |
| Duplicate | `aliyun ram GetGroup --GroupName {{user.group_name}}` | `EntityNotExist` | Ask reuse vs new name |

#### Execution — CLI

```bash
aliyun ram CreateGroup \
  --GroupName "{{user.group_name}}" \
  --Comments "{{user.comments}}"
```

#### Post-execution Validation

```bash
aliyun ram GetGroup --GroupName "{{user.group_name}}"
```

---

### Operation: Add User to Group

#### Execution — CLI

```bash
aliyun ram AddUserToGroup \
  --GroupName "{{user.group_name}}" \
  --UserName "{{user.user_name}}"
```

#### Post-execution Validation

```bash
aliyun ram ListUsersForGroup --GroupName "{{user.group_name}}"
```

---

### Operation: Remove User from Group

#### Execution — CLI

```bash
aliyun ram RemoveUserFromGroup \
  --GroupName "{{user.group_name}}" \
  --UserName "{{user.user_name}}"
```

---

### Operation: Delete RAM User Group

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- **MUST** warn that all users will be removed from the group and all attached
  policies will be detached.

#### Execution — CLI

```bash
aliyun ram DeleteGroup --GroupName "{{user.group_name}}"
```

---

### Operation: Create RAM Role

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Role name format | Regex: `^[a-zA-Z0-9_.@-]{1,64}$` | Valid | Ask for valid name |
| Trust policy JSON | Validate JSON structure | Valid JSON | Fix syntax; retry |
| Duplicate | `aliyun ram GetRole --RoleName {{user.role_name}}` | `EntityNotExist` | Ask reuse vs new name |

#### Trust Policy Document Structure

The `AssumeRolePolicyDocument` (trust policy) is a JSON string that defines
which principals can assume the role:

```json
{
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Effect": "Allow",
      "Principal": {
        "RAM": ["acs:ram::{{account_id}}:root"]
      }
    }
  ],
  "Version": "1"
}
```

Common principal types:
- **Alibaba Cloud account:** `{"RAM": ["acs:ram::{{account_id}}:root"]}`
- **Specific RAM user:** `{"RAM": ["acs:ram::{{account_id}}:user/{{user_name}}"]}`
- **Service principal:** `{"Service": ["ecs.aliyuncs.com"]}`
- **Identity provider (SAML/OIDC):** `{"Federated": ["acs:ram::{{account_id}}:saml-provider/{{provider_name}}"]}`

#### Execution — CLI

```bash
# Trust policy must be a properly escaped JSON string
aliyun ram CreateRole \
  --RoleName "{{user.role_name}}" \
  --AssumeRolePolicyDocument '{{user.assume_role_policy_document}}' \
  --Description "{{user.description}}" \
  --MaxSessionDuration {{user.max_session_duration}}
```

> `MaxSessionDuration` is optional (default 3600 seconds, max 43200).

#### Execution — JIT Go SDK

```go
request := &ram.CreateRoleRequest{
    RoleName:                 tea.String(os.Getenv("RAM_ROLE_NAME")),
    AssumeRolePolicyDocument: tea.String(os.Getenv("RAM_TRUST_POLICY")),
    Description:              tea.String(os.Getenv("RAM_ROLE_DESCRIPTION")),
}
response, err := client.CreateRole(request)
```

#### Post-execution Validation

1. Read `{{output.role_arn}}` from `$.Role.Arn`.
2. Call `GetRole` to confirm:
   ```bash
   aliyun ram GetRole --RoleName "{{user.role_name}}"
   ```
3. Report `RoleName`, `RoleId`, `Arn`, and `MaxSessionDuration`.

---

### Operation: Describe RAM Role

#### Execution — CLI

```bash
# Get single role
aliyun ram GetRole --RoleName "{{user.role_name}}"

# List all roles (paginated)
aliyun ram ListRoles --MaxItems 100

# Extract ARN
aliyun ram GetRole --RoleName "{{user.role_name}}" \
  --output cols=RoleName,RoleId,Arn,MaxSessionDuration rows=Role
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| RoleName | `$.Role.RoleName` | Plain text |
| RoleId | `$.Role.RoleId` | Plain text |
| Arn | `$.Role.Arn` | Full ARN for AssumeRole |
| MaxSessionDuration | `$.Role.MaxSessionDuration` | Seconds |
| CreateDate | `$.Role.CreateDate` | ISO 8601 |
| AssumeRolePolicyDocument | `$.Role.AssumeRolePolicyDocument` | URL-encoded JSON |

---

### Operation: Update RAM Role

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Role exists | `aliyun ram GetRole --RoleName {{user.role_name}}` | Success | HALT; create role first |
| New role name format | If renaming, regex `^[a-zA-Z0-9_.@-]{1,64}$` | Valid | Ask for valid name |
| Trust policy JSON | If updating, validate JSON | Valid JSON | Fix syntax; retry |
| MaxSessionDuration | If provided, 900–43200 | In range | Fix value; retry |

#### Execution — CLI

```bash
aliyun ram UpdateRole \
  --RoleName "{{user.role_name}}" \
  --NewRoleName "{{user.new_role_name}}" \
  --AssumeRolePolicyDocument '{{user.new_assume_role_policy_document}}' \
  --Description "{{user.new_description}}" \
  --MaxSessionDuration {{user.new_max_session_duration}}
```

> At least one of `NewRoleName`, `AssumeRolePolicyDocument`, `Description`,
> `MaxSessionDuration` must be provided.
> `AssumeRolePolicyDocument` replaces the entire trust policy.

#### Post-execution Validation

```bash
aliyun ram GetRole --RoleName "{{user.new_role_name}}"
```

Report updated fields to user.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.Role` | 0 | — | HALT; role does not exist |
| `EntityAlreadyExists.Role` | 0 | — | New name already taken; ask different name |
| `InvalidParameter.AssumeRolePolicyDocument` | 0 | — | Fix trust policy JSON; retry once |
| `InvalidParameter.MaxSessionDuration` | 0 | — | Fix to 900–43200; retry once |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |

---

### Operation: Delete RAM Role

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- **MUST** check for attached policies (`ListPoliciesForRole`) and warn that
  they will be implicitly detached.
- **MUST** warn that any running STS sessions are not affected, but new
  AssumeRole calls will fail.

#### Execution — CLI

```bash
aliyun ram DeleteRole --RoleName "{{user.role_name}}"
```

#### Post-execution Validation

1. Call `GetRole` — expect `EntityNotExist.Role`.
2. Report success.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.Role` | 0 | — | HALT; role does not exist |
| `DeleteConflict.Role.Policy` | 0 | — | Detach all policies first |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Create RAM Policy

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Policy name format | Regex: `^[a-zA-Z0-9_-]{1,128}$` | Valid | Ask for valid name |
| Policy document JSON | Validate JSON structure | Valid JSON with Version, Statement | Fix syntax; retry |
| Policy document size | Length ≤ 6144 characters | Within limit | Split into multiple policies or reduce scope |
| Duplicate | `aliyun ram GetPolicy --PolicyName {{user.policy_name}} --PolicyType Custom` | `EntityNotExist` | Ask reuse vs new name |

#### Policy Document Structure

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeInstances",
        "ecs:StartInstance",
        "ecs:StopInstance"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "acs:RegionId": "cn-hangzhou"
        }
      }
    }
  ]
}
```

Policy document rules:
- `Version` MUST be `"1"`
- `Statement` is an array of objects
- Each statement has `Effect` (`Allow` or `Deny`), `Action` (array or string),
  `Resource` (array or string), and optional `Condition`
- `Action` supports wildcards: `ecs:*`, `ecs:Describe*`
- `Resource` supports ARNs: `acs:ecs:*:*:instance/i-*`

#### Execution — CLI

```bash
aliyun ram CreatePolicy \
  --PolicyName "{{user.policy_name}}" \
  --PolicyDocument '{{user.policy_document}}' \
  --Description "{{user.policy_description}}"
```

#### Post-execution Validation

```bash
aliyun ram GetPolicy \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType Custom
```

Report `PolicyName`, `PolicyType`, `DefaultVersion`, and `Description`.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityAlreadyExists.Policy` | 0 | — | Ask reuse vs new name |
| `InvalidParameter.PolicyName` | 0 | — | Fix name format; retry once |
| `InvalidParameter.PolicyDocument` | 0 | — | Fix JSON syntax; retry once |
| `LimitExceeded.Policy` | 0 | — | Document size > 6144 chars; split policy |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Create Policy Version

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Policy exists | `aliyun ram GetPolicy --PolicyName {{user.policy_name}} --PolicyType Custom` | Success | HALT; create policy first |
| Version limit | `aliyun ram ListPolicyVersions --PolicyName {{user.policy_name}} --PolicyType Custom` | < 5 versions | Delete old versions first |
| Policy document JSON | Validate JSON structure | Valid JSON with Version, Statement | Fix syntax; retry |
| Document size | Length ≤ 6144 characters | Within limit | Split or reduce scope |

#### Execution — CLI

```bash
aliyun ram CreatePolicyVersion \
  --PolicyName "{{user.policy_name}}" \
  --PolicyDocument '{{user.policy_document}}' \
  --SetAsDefault {{user.set_as_default}}
```

> `SetAsDefault`: `true` or `false`. If `true`, the new version becomes the
> default version used for all attachments.

#### Post-execution Validation

```bash
aliyun ram GetPolicy \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType Custom
```

Report `PolicyName`, `DefaultVersion`, and version count.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.Policy` | 0 | — | HALT; policy does not exist |
| `LimitExceeded.Policy.Version` | 0 | — | Delete old non-default versions first |
| `InvalidParameter.PolicyDocument` | 0 | — | Fix JSON syntax; retry once |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |

---

### Operation: Attach Policy to User

#### Execution — CLI

```bash
aliyun ram AttachPolicyToUser \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType "{{user.policy_type}}" \
  --UserName "{{user.user_name}}"
```

> `PolicyType` is `Custom` or `System`.

#### Post-execution Validation

```bash
aliyun ram ListPoliciesForUser --UserName "{{user.user_name}}"
```

---

### Operation: Attach Policy to Role

#### Execution — CLI

```bash
aliyun ram AttachPolicyToRole \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType "{{user.policy_type}}" \
  --RoleName "{{user.role_name}}"
```

#### Post-execution Validation

```bash
aliyun ram ListPoliciesForRole --RoleName "{{user.role_name}}"
```

---

### Operation: Attach Policy to Group

#### Execution — CLI

```bash
aliyun ram AttachPolicyToGroup \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType "{{user.policy_type}}" \
  --GroupName "{{user.group_name}}"
```

#### Post-execution Validation

```bash
aliyun ram ListPoliciesForGroup --GroupName "{{user.group_name}}"
```

---

### Operation: Detach Policy

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation when detaching from a production
  identity.
- **MUST** warn about potential access loss.

#### Execution — CLI

```bash
# From user
aliyun ram DetachPolicyFromUser \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType "{{user.policy_type}}" \
  --UserName "{{user.user_name}}"

# From role
aliyun ram DetachPolicyFromRole \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType "{{user.policy_type}}" \
  --RoleName "{{user.role_name}}"

# From group
aliyun ram DetachPolicyFromGroup \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType "{{user.policy_type}}" \
  --GroupName "{{user.group_name}}"
```

---

### Operation: Delete RAM Policy

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- **MUST** check if policy is attached to any user, group, or role using
  `ListEntitiesForPolicy`.
- **MUST** warn that attached entities will lose permissions.
- **MUST NOT** allow deletion of System policies.

#### Execution — CLI

```bash
aliyun ram DeletePolicy \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType "Custom"
```

> Only `Custom` policies can be deleted. System policies are managed by Alibaba
> Cloud and cannot be deleted.

---

### Operation: Create Access Key for RAM User

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `aliyun ram GetUser --UserName {{user.user_name}}` | Success | HALT; create user first |
| Key limit | `aliyun ram ListAccessKeys --UserName {{user.user_name}}` | < 2 keys | HALT; delete old key first |

#### Execution — CLI

```bash
aliyun ram CreateAccessKey --UserName "{{user.user_name}}"
```

#### Post-execution Validation

1. Read `{{output.access_key_id}}` and `{{output.access_key_secret}}` from
   response.
2. **CRITICAL:** Display `AccessKeyId` and `AccessKeySecret` to the user
   **exactly once**. After this, the secret is irretrievable.
3. Call `ListAccessKeys` to confirm the new key is `Active`.

#### Security Handling

```bash
# Use JSON output — agent parses and controls exactly what is displayed
aliyun ram CreateAccessKey --UserName "{{user.user_name}}" --output json
```

> **CRITICAL SECURITY:** The agent MUST parse the JSON response and ONLY
> display `AccessKeyId` and `AccessKeySecret` to the user once. The agent MUST
> NOT use `--output cols=` for this operation because tabular output may be
> captured by shell history, process monitors, or logging systems. JSON output
> allows the agent to extract fields programmatically and control display.
>
> **NEVER** log `AccessKeySecret` to files, logs, or chat history after the
> initial display. If the user loses it, they must create a new access key.

---

### Operation: List Access Keys

#### Execution — CLI

```bash
aliyun ram ListAccessKeys --UserName "{{user.user_name}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| AccessKeyId | `$.AccessKeys.AccessKey[].AccessKeyId` | Plain text |
| Status | `$.AccessKeys.AccessKey[].Status` | `Active` or `Inactive` |
| CreateDate | `$.AccessKeys.AccessKey[].CreateDate` | ISO 8601 |

---

### Operation: Update Access Key Status

#### Execution — CLI

```bash
aliyun ram UpdateAccessKey \
  --UserName "{{user.user_name}}" \
  --AccessKeyId "{{user.access_key_id}}" \
  --Status "Inactive"
```

> `Status` values: `Active` or `Inactive`.

---

### Operation: Delete Access Key

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- **MUST** warn that any application using this key will immediately lose access.
- **MUST** check `GetAccessKeyLastUsed` to see if the key was recently used.

#### Execution — CLI

```bash
aliyun ram DeleteAccessKey \
  --UserName "{{user.user_name}}" \
  --AccessKeyId "{{user.access_key_id}}"
```

---

### Operation: Access Key Rotation

#### Flow

1. **Create new access key** (`CreateAccessKey`).
2. **Display new key pair ONCE** to user.
3. **Instruct user** to update applications with the new key.
4. **Wait for user confirmation** that applications are updated.
5. **Update old key status to `Inactive`** (`UpdateAccessKey`).
6. **Monitor for errors** for a grace period (user-defined, default 24h).
7. **Delete old access key** (`DeleteAccessKey`).

> This is a **user-supervised** operation. The agent MUST NOT automatically
> delete the old key without explicit user confirmation after the grace period.

---

### Operation: Create Login Profile

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `GetUser` | Success | HALT; create user first |
| No existing profile | `GetLoginProfile` | `EntityNotExist` | Ask update vs skip |

#### Execution — CLI

```bash
aliyun ram CreateLoginProfile \
  --UserName "{{user.user_name}}" \
  --Password '{{user.password}}' \
  --PasswordResetRequired true \
  --MFABindRequired false
```

> `PasswordResetRequired`: force password change on next login.
> `MFABindRequired`: require MFA setup before console access.
>
> **CRITICAL SECURITY:** Passwords passed via CLI command line may be visible
> in shell history (`~/.bash_history`), process lists (`ps aux`), and system
> logs. ALWAYS wrap passwords in single quotes to prevent shell interpolation.
> Prefer generating random passwords and forcing reset on first login
> (`PasswordResetRequired true`).

---

### Operation: Delete Login Profile

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- **MUST** warn that the user will lose console access.

#### Execution — CLI

```bash
aliyun ram DeleteLoginProfile --UserName "{{user.user_name}}"
```

---

### Operation: Update Login Profile

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `GetUser` | Success | HALT; create user first |
| Profile exists | `GetLoginProfile` | Success | HALT; create profile first |

#### Execution — CLI

```bash
aliyun ram UpdateLoginProfile \
  --UserName "{{user.user_name}}" \
  --Password "{{user.new_password}}" \
  --PasswordResetRequired true \
  --MFABindRequired false
```

> **SECURITY WARNING:** Passwords passed via CLI may be visible in process
> lists (`ps aux`). Where possible, use environment variables or secure input
> methods. At minimum, wrap passwords in single quotes to prevent shell
> interpolation.

#### Post-execution Validation

```bash
aliyun ram GetLoginProfile --UserName "{{user.user_name}}"
```

Report `PasswordResetRequired` and `MFABindRequired` status.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.User` | 0 | — | HALT; user does not exist |
| `EntityNotExist.LoginProfile` | 0 | — | HALT; create login profile first |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |

---

### Operation: Unbind MFA Device

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `GetUser` | Success | HALT; create user first |
| MFA bound | `GetUserMFAInfo` | Has MFA device | HALT; no MFA to unbind |

#### Execution — CLI

```bash
aliyun ram UnbindMFADevice --UserName "{{user.user_name}}"
```

> After unbinding, the virtual MFA device still exists and can be re-bound or
> deleted separately.

#### Post-execution Validation

```bash
aliyun ram GetUserMFAInfo --UserName "{{user.user_name}}"
```

Expect no MFA device attached.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.User` | 0 | — | HALT; user does not exist |
| `EntityNotExist.MFADevice` | 0 | — | HALT; no MFA device bound |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |

---

### Operation: Create Virtual MFA Device

#### Execution — CLI

```bash
aliyun ram CreateVirtualMFADevice \
  --VirtualMFADeviceName "{{user.mfa_device_name}}"
```

#### Post-execution Validation

1. Read `$.VirtualMFADevice.SerialNumber` and `$.VirtualMFADevice.Base32StringSeed`
   or `$.VirtualMFADevice.QRCodePNG` from response.
2. Present QR code or base32 seed to user for device enrollment.
3. After user enrolls device, call `BindMFADevice` with two consecutive TOTP codes.

---

### Operation: Bind MFA Device

#### Execution — CLI

```bash
aliyun ram BindMFADevice \
  --SerialNumber "{{output.mfa_serial_number}}" \
  --UserName "{{user.user_name}}" \
  --AuthenticationCode1 "{{user.totp_code_1}}" \
  --AuthenticationCode2 "{{user.totp_code_2}}"
```

> `AuthenticationCode1` and `AuthenticationCode2` must be two consecutive
> TOTP codes from the user's MFA device.

---

### Operation: Delete Virtual MFA Device

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- **MUST** warn that the user will lose MFA protection.

#### Execution — CLI

```bash
aliyun ram DeleteVirtualMFADevice \
  --SerialNumber "{{output.mfa_serial_number}}"
```

---

### Operation: STS AssumeRole

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Role exists | `aliyun ram GetRole --RoleName {{user.role_name}}` | Success | HALT; create role first |
| Role ARN | Parse from `GetRole` | Valid ARN | HALT |

#### Execution — CLI

```bash
aliyun sts AssumeRole \
  --RoleArn "{{output.role_arn}}" \
  --RoleSessionName "{{user.session_name}}" \
  --DurationSeconds 3600 \
  --Policy '{{user.session_policy}}'
```

> `DurationSeconds`: 900–43200 (default 3600).
> `Policy`: optional inline session policy (JSON string) for further restriction.
> `RoleSessionName`: 2–64 chars, `[a-zA-Z0-9_.@-]`.

#### Execution — JIT Go SDK

```go
import (
    sts "github.com/alibabacloud-go/sts-20150401/v2/client"
)

request := &sts.AssumeRoleRequest{
    RoleArn:         tea.String(os.Getenv("RAM_ROLE_ARN")),
    RoleSessionName: tea.String(os.Getenv("RAM_SESSION_NAME")),
    DurationSeconds: tea.Int64(3600),
}
response, err := stsClient.AssumeRole(request)
```

> SDK package: `github.com/alibabacloud-go/sts-20150401/v2/client`

#### Post-execution Validation

1. Read `$.Credentials.AccessKeyId`, `$.Credentials.AccessKeySecret`,
   `$.Credentials.SecurityToken`, `$.Credentials.Expiration`.
2. Display temporary credentials to user (these expire; no need for one-time
   restriction like permanent AKs, but still treat as sensitive).
3. Report `Expiration` timestamp.

---

### Operation: Get Caller Identity

#### Execution — CLI

```bash
aliyun sts GetCallerIdentity
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| AccountId | `$.AccountId` | Current Alibaba Cloud account ID — use this to construct ARNs |
| Arn | `$.Arn` | Identity ARN (user or role) |
| UserId | `$.UserId` | Principal ID |

> **Usage for trust policies:** When creating a role trust policy that references
> the current account, FIRST call `GetCallerIdentity` to obtain `AccountId`,
> THEN substitute it into the trust policy JSON:
> ```json
> {"Principal": {"RAM": ["acs:ram::{{output.account_id}}:root"]}}
> ```

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `NoPermission` | 0 | — | HALT; caller lacks STS permissions |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Set Password Policy

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Min length | 8–32 | In range | Fix to 8–32 |
| Max login attempts | 3–32 | In range | Fix to 3–32 |
| Password reuse | 1–24 | In range | Fix to 1–24 |
| Max password age | 0–180 | In range | Fix to 0–180 (0 = no expiration) |

#### Execution — CLI

```bash
aliyun ram SetPasswordPolicy \
  --MinimumPasswordLength 12 \
  --RequireLowercaseCharacters true \
  --RequireUppercaseCharacters true \
  --RequireNumbers true \
  --RequireSymbols true \
  --MaxLoginAttempts 5 \
  --PasswordReusePrevention 5 \
  --MaxPasswordAge 90 \
  --HardExpiry false
```

> All parameters are optional; omitted parameters retain their current values.

#### Post-execution Validation

```bash
aliyun ram GetPasswordPolicy
```

Report all policy settings to user.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` | 0 | — | Fix out-of-range value; retry once |
| `NoPermission` | 0 | — | HALT; need `AliyunRAMFullAccess` |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |

---

### Operation: Get Password Policy

#### Execution — CLI

```bash
aliyun ram GetPasswordPolicy
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| MinimumPasswordLength | `$.PasswordPolicy.MinimumPasswordLength` | 8–32 |
| RequireLowercaseCharacters | `$.PasswordPolicy.RequireLowercaseCharacters` | true/false |
| RequireUppercaseCharacters | `$.PasswordPolicy.RequireUppercaseCharacters` | true/false |
| RequireNumbers | `$.PasswordPolicy.RequireNumbers` | true/false |
| RequireSymbols | `$.PasswordPolicy.RequireSymbols` | true/false |
| MaxLoginAttempts | `$.PasswordPolicy.MaxLoginAttempts` | 3–32 |
| PasswordReusePrevention | `$.PasswordPolicy.PasswordReusePrevention` | 1–24 |
| MaxPasswordAge | `$.PasswordPolicy.MaxPasswordAge` | 0–180 days |
| HardExpiry | `$.PasswordPolicy.HardExpiry` | true/false |

---

### Operation: Least-Privilege Audit

#### Flow

1. **List all identities:**
   ```bash
   aliyun ram ListUsers --MaxItems 1000
   aliyun ram ListRoles --MaxItems 1000
   aliyun ram ListGroups --MaxItems 1000
   ```

2. **For each identity, list attached policies:**
   ```bash
   aliyun ram ListPoliciesForUser --UserName "{{user.user_name}}"
   aliyun ram ListPoliciesForRole --RoleName "{{user.role_name}}"
   aliyun ram ListPoliciesForGroup --GroupName "{{user.group_name}}"
   ```

3. **For each policy, get document:**
   ```bash
   aliyun ram GetPolicy \
     --PolicyName "{{user.policy_name}}" \
     --PolicyType "{{user.policy_type}}"
   # Then get specific version:
   aliyun ram GetPolicyVersion \
     --PolicyName "{{user.policy_name}}" \
     --PolicyType "{{user.policy_type}}" \
     --VersionId "{{user.version_id}}"
   ```

4. **Analyze for over-permission:**
   - `Action: "*"` or `Resource: "*"` without `Condition`
   - Wildcards on sensitive actions (e.g., `ram:*`, `ecs:Delete*`)
   - `Effect: Deny` missing for high-risk operations
   - Unused policies (attached but no recent usage)

5. **List access keys and check last used:**
   ```bash
   aliyun ram ListAccessKeys --UserName "{{user.user_name}}"
   aliyun ram GetAccessKeyLastUsed --AccessKeyId "{{user.access_key_id}}"
   ```

6. **Report findings** with risk level (High / Medium / Low) and remediation
   suggestions.

---

---

### Operation: Intelligent Inspection（安全巡检）

一键执行RAM安全巡检，检查用户权限、AccessKey状态、密码策略、MFA绑定等安全配置。

#### 执行流程

1. 调用 `GetPasswordPolicy` 检查密码策略强度
2. 调用 `ListUsers` 遍历所有用户
3. 对每个用户检查：AccessKey数量及最后使用时间、MFA绑定状态、登录配置
4. 调用 `ListRoles` 检查角色信任策略
5. 综合评分并生成安全巡检报告

#### 巡检评分标准

| 维度 | 评分依据 | 权重 |
|------|---------|------|
| 密码策略 | 最小长度≥12且包含各类字符=100, 否则=60 | 20% |
| 用户MFA覆盖率 | 100%=100, >50%=60, <50%=0 | 20% |
| 未使用AK比例 | 0%=100, <50%=60, >50%=0 | 20% |
| 过度授权策略 | 无Action:*且Resource:*=100, 有=0 | 20% |
| 密码有效期 | ≤90天=100, >90天=60, 永不过期=0 | 20% |

#### 执行 — CLI

```bash
#!/bin/bash
# ram-security-inspection.sh
# Usage: ./ram-security-inspection.sh

SCORE=0
echo "=== RAM Security Inspection ==="
echo ""

# 1. Password policy check
echo "[1/5] Password Policy:"
POLICY=$(aliyun ram GetPasswordPolicy --output json 2>/dev/null)
MIN_LEN=$(echo "$POLICY" | jq -r '.PasswordPolicy.MinimumPasswordLength // 0')
HAS_SYMBOLS=$(echo "$POLICY" | jq -r '.PasswordPolicy.RequireSymbols // false')
MAX_AGE=$(echo "$POLICY" | jq -r '.PasswordPolicy.MaxPasswordAge // 0')
echo "  Min Length: $MIN_LEN, Symbols: $HAS_SYMBOLS, Max Age: $MAX_AGE days"
if [ "$MIN_LEN" -ge 12 ] && [ "$HAS_SYMBOLS" = "true" ]; then
  SCORE=$((SCORE + 20))
  echo "  ✅ Password policy: Strong"
else
  echo "  ⚠️ Password policy: Needs improvement"
fi

# 2. User MFA coverage
echo ""
echo "[2/5] User MFA Coverage:"
USERS=$(aliyun ram ListUsers --MaxItems 100 --output json | jq -r '.Users.User[].UserName')
TOTAL_USERS=$(echo "$USERS" | grep -c . || true)
MFA_USERS=0
for user in $USERS; do
  MFA=$(aliyun ram GetUserMFAInfo --UserName "$user" --output json 2>/dev/null | jq -r '.MFADevice.SerialNumber // ""')
  [ -n "$MFA" ] && MFA_USERS=$((MFA_USERS + 1))
done
echo "  Users: $TOTAL_USERS, MFA enabled: $MFA_USERS"
if [ "$TOTAL_USERS" -gt 0 ]; then
  MFA_RATIO=$((MFA_USERS * 100 / TOTAL_USERS))
  [ "$MFA_RATIO" -eq 100 ] && SCORE=$((SCORE + 20))
  [ "$MFA_RATIO" -ge 50 ] && [ "$MFA_RATIO" -lt 100 ] && SCORE=$((SCORE + 12))
fi

# 3. Unused access keys
echo ""
echo "[3/5] Access Key Audit:"
UNUSED_KEYS=0
TOTAL_KEYS=0
for user in $USERS; do
  KEYS=$(aliyun ram ListAccessKeys --UserName "$user" --output json 2>/dev/null | jq -r '.AccessKeys.AccessKey[].AccessKeyId')
  for key in $KEYS; do
    TOTAL_KEYS=$((TOTAL_KEYS + 1))
    LAST_USED=$(aliyun ram GetAccessKeyLastUsed --UserName "$user" --UserAccessKeyId "$key" --output json 2>/dev/null | jq -r '.AccessKeyLastUsed.LastUsedDate // "Never"')
    [ "$LAST_USED" = "Never" ] && UNUSED_KEYS=$((UNUSED_KEYS + 1))
  done
done
echo "  Total keys: $TOTAL_KEYS, Unused: $UNUSED_KEYS"
[ "$UNUSED_KEYS" -eq 0 ] && SCORE=$((SCORE + 20))
[ "$UNUSED_KEYS" -gt 0 ] && [ "$UNUSED_KEYS" -le "$((TOTAL_KEYS / 2))" ] && SCORE=$((SCORE + 12))

# 4. Over-permissioned policies check
echo ""
echo "[4/5] Policy Audit:"
POLICIES=$(aliyun ram ListPolicies --Scope All --MaxItems 100 --output json | jq -r '.Policies.Policy[] | select(.PolicyType=="Custom") | .PolicyName')
OVER_PERM=0
for policy in $POLICIES; do
  DOC=$(aliyun ram GetPolicy --PolicyName "$policy" --PolicyType Custom --output json 2>/dev/null | jq -r '.DefaultPolicyVersion.PolicyDocument // ""')
  if echo "$DOC" | jq -e '.Statement[] | select(.Action=="*" and .Resource=="*")' > /dev/null 2>&1; then
    OVER_PERM=$((OVER_PERM + 1))
  fi
done
echo "  Custom policies with Action:* + Resource:*: $OVER_PERM"
[ "$OVER_PERM" -eq 0 ] && SCORE=$((SCORE + 20))

# 5. Password expiry check
echo ""
echo "[5/5] Password Expiry:"
if [ "$MAX_AGE" -gt 0 ] && [ "$MAX_AGE" -le 90 ]; then
  SCORE=$((SCORE + 20))
  echo "  ✅ Password expires in $MAX_AGE days"
elif [ "$MAX_AGE" -gt 90 ]; then
  SCORE=$((SCORE + 12))
  echo "  ⚠️ Password expiry > 90 days ($MAX_AGE)"
else
  echo "  ⚠️ Password never expires"
fi

echo ""
echo "=== Inspection Score: $SCORE/100 ==="
if [ "$SCORE" -ge 80 ]; then
  echo "Status: HEALTHY"
elif [ "$SCORE" -ge 60 ]; then
  echo "Status: WARNING - Review recommended"
else
  echo "Status: CRITICAL - Immediate action required"
fi
```

#### 输出格式

```json
{
  "inspection_time": "2026-05-14T10:00:00Z",
  "resource_type": "ram",
  "resource_id": "account",
  "overall_score": 75,
  "dimensions": [
    {"name": "密码策略", "score": 100, "status": "healthy"},
    {"name": "用户MFA覆盖率", "score": 60, "status": "warning", "value": "3/5"},
    {"name": "未使用AK比例", "score": 100, "status": "healthy", "value": "0/10"},
    {"name": "过度授权策略", "score": 0, "status": "critical", "value": "2个"},
    {"name": "密码有效期", "score": 100, "status": "healthy", "value": "90天"}
  ],
  "recommendations": [
    "发现2个自定义策略包含Action:*和Resource:*，建议缩小权限范围",
    "MFA覆盖率60%，建议为所有用户启用MFA"
  ]
}
```

## Prerequisites

1. **Install `aliyun` CLI** (primary execution path):

   ```bash
   # Download installer
   curl -fsSL -o /tmp/aliyun-install.sh https://aliyuncli.alicdn.com/install.sh

   # Optional: verify checksum if published by Alibaba Cloud
   # sha256sum /tmp/aliyun-install.sh

   # Execute installer
   /bin/bash /tmp/aliyun-install.sh
   aliyun version
   ```

   > **Security note:** `curl | bash` patterns bypass integrity verification.
   > Prefer downloading first, inspecting the script, then executing.

2. **Configure Credentials** (environment variables preferred):

   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
   ```

3. **Verify RAM access:**

   ```bash
   aliyun ram ListUsers --MaxItems 10
   aliyun sts GetCallerIdentity
   ```

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Policy Examples](references/policy-examples.md)
- [Integration](references/integration.md)

## Operational Best Practices

- **Least privilege:** Scope policies to specific actions, resources, and
  conditions. Avoid `Action: "*"` and `Resource: "*"`.
- **Rotate access keys:** Rotate access keys every 90 days. Use the rotation
  flow documented above.
- **Enable MFA:** Require MFA for console access, especially for privileged
  users.
- **Use roles for applications:** Prefer STS AssumeRole over long-term access
  keys for applications and services.
- **Monitor unused identities:** Regularly audit and delete unused users, roles,
  and access keys.
- **Password policy:** Enforce strong password policies via
  `SetPasswordPolicy`.
- **No root account for daily ops:** Create dedicated RAM users with minimal
  permissions for all operational tasks.

## Diagnostic Quick Reference

Quick error lookup for common RAM operation failures. For detailed
troubleshooting, see [Troubleshooting Guide](references/troubleshooting.md).

### Common Error Patterns

| Error Code | Meaning | Most Likely Cause | Quick Fix |
|-----------|---------|-------------------|-----------|
| `EntityAlreadyExists.User` | User already exists | Duplicate create | Ask reuse vs new name |
| `EntityNotExist.User` | User not found | Wrong name or already deleted | Verify name with `ListUsers` |
| `EntityAlreadyExists.Group` | Group already exists | Duplicate create | Ask reuse vs new name |
| `EntityNotExist.Group` | Group not found | Wrong name or already deleted | Verify name with `ListGroups` |
| `EntityAlreadyExists.Role` | Role already exists | Duplicate create | Ask reuse vs new name |
| `EntityNotExist.Role` | Role not found | Wrong name or already deleted | Verify name with `ListRoles` |
| `EntityAlreadyExists.Policy` | Policy already exists | Duplicate create | Ask reuse vs new name |
| `EntityNotExist.Policy` | Policy not found | Wrong name or already deleted | Verify name with `ListPolicies` |
| `DeleteConflict.User.Group` | User still in groups | Dependency not cleaned | Remove from groups first |
| `DeleteConflict.User.AccessKey` | User has active keys | Dependency not cleaned | Delete keys first |
| `DeleteConflict.User.Policy` | User has attached policies | Dependency not cleaned | Detach policies first |
| `DeleteConflict.User.LoginProfile` | User has login profile | Dependency not cleaned | Delete profile first |
| `DeleteConflict.Role.Policy` | Role has attached policies | Dependency not cleaned | Detach policies first |
| `InvalidParameter.UserName` | Bad user name format | Regex violation | Fix to `^[a-zA-Z0-9_.@-]{1,64}$` |
| `InvalidParameter.PolicyDocument` | Bad policy JSON | JSON syntax error | Validate with `jq` |
| `LimitExceeded.Policy` | Policy too large | > 6144 characters | Split into multiple policies |
| `LimitExceeded.Policy.Version` | Too many versions | > 5 versions | Delete old non-default versions |
| `NoPermission` | Access denied | Missing RAM permissions | Grant `AliyunRAMFullAccess` |
| Throttling / 429 | Rate limited | Too many requests | Retry with exponential backoff |
| `InternalError` / 5xx | Server error | Transient | Retry 3 times; then HALT with RequestId |

### Quick Diagnostic Commands

| Symptom | Diagnostic Command | Expected Output |
|---------|-------------------|-----------------|
| "User not found" | `aliyun ram ListUsers --MaxItems 1000` | List all users; check spelling |
| "Role not found" | `aliyun ram ListRoles --MaxItems 1000` | List all roles; check spelling |
| "Policy not found" | `aliyun ram ListPolicies --Scope All --MaxItems 1000` | List all policies; check type |
| "Access denied" | `aliyun sts GetCallerIdentity` | Verify credentials are valid |
| "Can't delete" | `aliyun ram ListPoliciesForUser --UserName X` | Check attached policies |
| "Key limit reached" | `aliyun ram ListAccessKeys --UserName X` | Max 2 keys per user |
| "Throttling" | Check `Retry-After` header | Wait and retry |
| "JSON parse error" | `echo '{{policy}}' \| jq .` | Validate JSON syntax |

### When to Escalate

- `InternalError` persists after 3 retries → HALT; provide RequestId to user
- `NoPermission` on RAM itself → User needs `AliyunRAMFullAccess` or equivalent
- Unexpected error not in this table → HALT; ask user to check Alibaba Cloud
  status page: https://status.aliyun.com
