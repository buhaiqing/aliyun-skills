# Prompt Examples & Common Task Templates (Agent-Readable)

> This file collects **complete end-to-end flows** for the most common RAM
> requests, plus a **Chinese-language user-interaction quick reference** the
> agent uses to recognize and respond to natural-language triggers. Use this
> as a "task book" — match the user's request to a template, then dispatch
> the steps in order.
>
> Per-operation Pre-flight / Execution / Post-execution / Failure Recovery
> detail lives in [`operations/`](operations/) — these templates link out.

## 1. Common Task Templates (Step-by-Step)

Each template lists the **minimum viable step chain**. For each step, refer
to the linked reference for the full pre-flight + execution + validation.

#### Task: Create a RAM user and grant ECS read-only access

```
Step 1: CreateUser                                 → [user-operations.md §Create](operations/user-operations.md#operation-create-ram-user)
Step 2: AttachPolicyToUser (AliyunECSReadOnlyAccess) → [policy-operations.md §Attach to User](operations/policy-operations.md#operation-attach-policy-to-user)
Done
```

#### Task: Create a RAM role for ECS instances

```
Step 1: GetCallerIdentity                          → [role-operations.md §GetCallerIdentity](operations/role-operations.md#operation-get-caller-identity)
Step 2: CreateRole (with ECS service principal)     → [role-operations.md §Create](operations/role-operations.md#operation-create-ram-role)
Done
```

#### Task: Rotate an access key

```
Step 1: CreateAccessKey (new key shown once)        → [user-operations.md §Create AK](operations/user-operations.md#operation-create-access-key-for-ram-user)
Step 2: Display new key pair ONCE
Step 3: Wait for user confirmation
Step 4: UpdateAccessKey (old key → Inactive)        → [user-operations.md §Update AK](operations/user-operations.md#operation-update-access-key-status)
Step 5: Wait grace period (default 24h)
Step 6: DeleteAccessKey (old key)                   → [user-operations.md §Delete AK](operations/user-operations.md#operation-delete-access-key)
```

#### Task: Audit all permissions (least-privilege)

```
Step 1: ListUsers + ListRoles + ListGroups         → [audit-operations.md §Audit](operations/audit-operations.md#operation-least-privilege-audit)
Step 2: For each identity → ListPoliciesForX
Step 3: GetAccessKeyLastUsed for each AK
Step 4: Report findings (High / Medium / Low) + remediation
```

#### Task: Set up MFA for a user

```
Step 1: SetPasswordPolicy                          → [audit-operations.md §Set Password Policy](operations/audit-operations.md#operation-set-password-policy)
Step 2: CreateVirtualMFADevice                     → [user-operations.md §Create MFA](operations/user-operations.md#operation-create-virtual-mfa-device)
Step 3: Present QR code / base32 seed to user
Step 4: User provides 2 consecutive TOTP codes
Step 5: BindMFADevice (with TOTP code 1 + 2)        → [user-operations.md §Bind MFA](operations/user-operations.md#operation-bind-mfa-device)
Done
```

#### Task: Enable console login for a user

```
Step 1: CreateLoginProfile (password shown once)   → [user-operations.md §Create LoginProfile](operations/user-operations.md#operation-create-login-profile)
Step 2: Display initial password to user once
Step 3: Force reset on first login (PasswordResetRequired=true) — recommended
Done
```

#### Task: Create a custom policy for ECS management in cn-hangzhou

```
Step 1: CreatePolicy (with region-restricted policy document)
        → [policy-operations.md §Create](operations/policy-operations.md#operation-create-ram-policy)
Done
```

---

## 2. User Interaction Quick Reference (中文对话模板)

> When the user speaks Chinese, recognize the intent and execute the matching
> task template above. For each row, the agent **asks for the missing inputs
> first**, then runs the operation — never assume defaults for destructive
> actions.

| 用户说… | Agent 应做 | 对应操作 / 链接 |
|---------|-----------|----------------|
| "帮我创建一个子账号" | 询问用户名，再 `CreateUser` | [CreateUser](operations/user-operations.md#operation-create-ram-user) |
| "给这个用户授权" | 询问策略名 + 类型，再 `AttachPolicyToUser` | [AttachPolicyToUser](operations/policy-operations.md#operation-attach-policy-to-user) |
| "帮我生成一个AK" | 询问用户名，再 `CreateAccessKey`（仅展示一次） | [CreateAccessKey](operations/user-operations.md#operation-create-access-key-for-ram-user) |
| "我要轮换密钥" | 询问用户名，走密钥轮换 6 步流程 | [Key Rotation Flow](operations/user-operations.md#operation-access-key-rotation) |
| "检查一下权限" | 运行最小权限审计流程 | [Least-Privilege Audit](operations/audit-operations.md#operation-least-privilege-audit) |
| "设置密码策略" | 询问参数范围，再 `SetPasswordPolicy` | [SetPasswordPolicy](operations/audit-operations.md#operation-set-password-policy) |
| "帮我开个控制台登录" | 询问用户名 + 密码规则，再 `CreateLoginProfile` | [CreateLoginProfile](operations/user-operations.md#operation-create-login-profile) |
| "绑定MFA" | 询问用户名，走 MFA 创建 + 绑定流程 | [MFA Flow](operations/user-operations.md#operation-create-virtual-mfa-device) |
| "创建一个角色" | 询问角色名 + 受信策略，再 `CreateRole` | [CreateRole](operations/role-operations.md#operation-create-ram-role) |
| "删除这个用户" | 运行 Safety Gate + 5 步依赖清理 | [DeleteUser](operations/user-operations.md#operation-delete-ram-user) |
| "查看某个 AK 最近用过没" | 调用 `GetAccessKeyLastUsed` | [Audit §Check Last Used](operations/audit-operations.md#operation-least-privilege-audit) |
| "轮换角色临时凭证" | `AssumeRole` 取新凭证 | [AssumeRole](operations/role-operations.md#operation-sts-assumerole) |

---

## 3. User Interaction Norms (交互规范)

These rules apply to **all** RAM interactions, regardless of which task
template is selected.

- **Progressive disclosure (渐进式披露):** Ask only for the minimum needed
  information at each step. After completing a step, prompt for the next
  one — do not front-load the entire form.
- **Confirm before destruction (销毁前确认):** Any destructive action
  (delete user / role / policy / AK / login profile / MFA) MUST spell out
  the consequences and obtain explicit user assent before invoking the
  destructive API. For `DeleteUser`, the 5-step dependency cascade
  (detach policies / remove groups / delete AKs / delete login profile /
  unbind MFA) MUST complete first.
- **Suggest next step (建议下一步):** After completing an operation,
  proactively offer 1–2 logical follow-ups (e.g. after `CreateUser` →
  suggest `CreateLoginProfile` + `AttachPolicyToUser`).
- **Multi-step decomposition (多步骤分解):** For complex tasks (key
  rotation, MFA setup, full audit), break the work into discrete steps
  and confirm each before moving on.
- **示例对话模板:** 完整的多轮对话示例参见
  [Prompt Examples（与本文件同目录）](prompt-examples.md)。
- **Translation discipline:** When the user mixes Chinese + English
  (e.g. "帮我 create 一个 RAM user for dev team"), match the **intent**
  regardless of the language surface — do not require one language only.

---

## 4. Common Scenario Quick Reference

| Scenario | Steps |
|----------|-------|
| **Onboard Developer** | `CreateUser` → `CreateLoginProfile` (password shown once, `PasswordResetRequired=true`) → `AttachPolicyToUser` (`AliyunECSReadOnlyAccess`) → Optional `CreateAccessKey` |
| **Cross-Account Access** | `GetCallerIdentity` → `CreateRole` (trust policy scoping other account's `{{account_id}}:root`) → `CreatePolicy` → `AttachPolicyToRole` |
| **Key Rotation** | `CreateAccessKey` (new key shown once) → user updates apps → `UpdateAccessKey` (old → Inactive) → wait grace period → `DeleteAccessKey` |
| **Permission Audit** | `ListUsers` → per user: `ListPoliciesForUser` + `ListAccessKeys` + `GetAccessKeyLastUsed` → report High/Medium/Low |
| **Set Up MFA** | `SetPasswordPolicy` → per user: `CreateVirtualMFADevice` → user provides 2 TOTP codes → `BindMFADevice` |
