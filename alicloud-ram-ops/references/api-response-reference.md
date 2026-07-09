# RAM API — Response Reference (Agent-Readable)

> This file is the **canonical dictionary** of JSON response paths, field
> semantics, and error code taxonomy for RAM operations. Agent parsers SHOULD
> reference these paths directly when interpreting `aliyun ram` / `aliyun sts`
> output.
>
> For request/response field requirements, see
> [`api-sdk-usage.md`](api-sdk-usage.md). For CLI conventions, see
> [`cli-usage.md`](cli-usage.md).

## 1. Common JSON Paths (Centralized, Top-of-File)

```text
# Create User:   $.User.{UserId,UserName,CreateDate}
# Get User:      $.User.{UserId,LastLoginDate}
# List Users:    $.Users.User[]
# Create Role:   $.Role.{RoleId,RoleName,Arn}
# List Roles:    $.Roles.Role[]
# Create Policy: $.Policy.{PolicyName,PolicyType,DefaultVersion}
# List Policies: $.Policies.Policy[]
# Create AK:     $.AccessKey.{AccessKeyId,AccessKeySecret,Status}
# AssumeRole:    $.Credentials.{AccessKeyId,AccessKeySecret,SecurityToken,Expiration}
# Delete/etc:    $.RequestId
```

> **Tip:** When parsing with `jq` or JMESPath, always check the response root
> first — most RAM API responses are wrapped in a `User` / `Role` / `Policy` /
> `AccessKey` / `Credentials` / `Roles` (plural for lists) envelope.

---

## 2. Response Field Table (Per-Operation)

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
| ListAccessKeys | `$.AccessKeys.AccessKey[].AccessKeyId` | string | AK identifier |
| ListAccessKeys | `$.AccessKeys.AccessKey[].Status` | string | `Active` or `Inactive` |
| ListAccessKeys | `$.AccessKeys.AccessKey[].CreateDate` | string | ISO 8601 |
| AssumeRole | `$.Credentials.AccessKeyId` | string | Temporary AK |
| AssumeRole | `$.Credentials.AccessKeySecret` | string | Temporary secret |
| AssumeRole | `$.Credentials.SecurityToken` | string | STS token |
| AssumeRole | `$.Credentials.Expiration` | string | ISO 8601 expiration |
| AssumeRole | `$.AssumedRoleId` | string | Format `{{role_id}}:{{session_name}}` |
| AssumeRole | `$.AssumedRoleArn` | string | Format `acs:ram::{{account_id}}:role/{{role_name}}/{{session_name}}` |
| GetCallerIdentity | `$.AccountId` | string | Current Alibaba Cloud account ID — use to construct ARNs |
| GetCallerIdentity | `$.Arn` | string | Identity ARN (user or role) |
| GetCallerIdentity | `$.UserId` | string | Principal ID |
| GetLoginProfile | `$.LoginProfile.UserName` | string | User with console login enabled |
| GetLoginProfile | `$.LoginProfile.PasswordResetRequired` | bool | Force password change on next login |
| GetLoginProfile | `$.LoginProfile.MFABindRequired` | bool | Require MFA setup before console access |
| GetPasswordPolicy | `$.PasswordPolicy.MinimumPasswordLength` | int | 8–32 |
| GetPasswordPolicy | `$.PasswordPolicy.RequireLowercaseCharacters` | bool | Require a–z |
| GetPasswordPolicy | `$.PasswordPolicy.RequireUppercaseCharacters` | bool | Require A–Z |
| GetPasswordPolicy | `$.PasswordPolicy.RequireNumbers` | bool | Require 0–9 |
| GetPasswordPolicy | `$.PasswordPolicy.RequireSymbols` | bool | Require special chars |
| GetPasswordPolicy | `$.PasswordPolicy.MaxLoginAttempts` | int | 3–32 |
| GetPasswordPolicy | `$.PasswordPolicy.PasswordReusePrevention` | int | 1–24 (number of last passwords blocked) |
| GetPasswordPolicy | `$.PasswordPolicy.MaxPasswordAge` | int | 0–180 days (0 = no expiration) |
| GetPasswordPolicy | `$.PasswordPolicy.HardExpiry` | bool | Hard block when expired (vs. soft warning) |
| CreateVirtualMFADevice | `$.VirtualMFADevice.SerialNumber` | string | MFA device serial — required for `BindMFADevice` |
| CreateVirtualMFADevice | `$.VirtualMFADevice.Base32StringSeed` | string | Base32 seed for manual enrollment (no QR) |
| CreateVirtualMFADevice | `$.VirtualMFADevice.QRCodePNG` | string | Base64-encoded PNG of QR code |
| GetUserMFAInfo | `$.UserMFAInfo.MFADevice` | string | "acs:ram::{{account_id}}:mfa/{{device_name}}" — absent if none |
| ListGroupsForUser | `$.Groups.Group[]` | array | Groups the user belongs to |

---

## 3. API & Response Conventions

- **OpenAPI is canonical** for path, query, body fields, enums, and response
  shapes. RAM uses **RPC-style** APIs with version `2015-05-01`.
- **Errors:** Map SDK/HTTP errors to `code` / `message` / `requestId` fields.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** RAM APIs are generally NOT idempotent for create
  operations. Creating a user/role/policy with the same name returns
  `EntityAlreadyExists`. Always probe with `Get*` / `List*` first, or ask the
  user to confirm reuse vs new name.
- **Global service:** Most RAM APIs do not require `RegionId` or use
  `cn-hangzhou` as default. STS AssumeRole may require a regional endpoint.

---

## 4. Common Error Codes (RAM-Specific)

The following error patterns are the most common; full per-operation
tables live in each `operations/*.md` file.

| Error Code Pattern | Meaning | Agent Action |
|--------------------|---------|--------------|
| `EntityAlreadyExists.User` | User name already taken | Ask reuse vs new name |
| `EntityAlreadyExists.Role` | Role name already taken | Ask reuse vs new name |
| `EntityAlreadyExists.Policy` | Policy name already taken | Ask reuse vs new name |
| `EntityAlreadyExists.MFADevice` | MFA device name collision | Pick a unique device name |
| `EntityNotExist.User` | User does not exist | HALT; create user first |
| `EntityNotExist.Role` | Role does not exist | HALT; create role first |
| `EntityNotExist.Policy` | Policy does not exist | HALT; create policy first |
| `EntityNotExist.LoginProfile` | Login profile missing | Create profile first |
| `EntityNotExist.MFADevice` | No MFA device bound | HALT; nothing to unbind/delete |
| `InvalidParameter.UserName` | Name format wrong | Enforce `^[a-zA-Z0-9_.@-]{1,64}$` |
| `InvalidParameter.PolicyName` | Policy name format wrong | Enforce `^[a-zA-Z0-9_-]{1,128}$` |
| `InvalidParameter.PolicyDocument` | Policy JSON invalid | Validate JSON, retry once |
| `InvalidParameter.AssumeRolePolicyDocument` | Trust policy JSON invalid | Validate JSON, retry once |
| `InvalidParameter.DisplayName` | Display name invalid | Fix format; retry once |
| `InvalidParameter.MaxSessionDuration` | Out of range (900–43200) | Fix value; retry once |
| `LimitExceeded.Policy` | Policy doc > 6144 chars | Split or reduce scope |
| `LimitExceeded.Policy.Version` | ≥ 5 versions on one policy | Delete old non-default versions first |
| `DeleteConflict.User.Group` | User still in groups | `ListGroupsForUser` → `RemoveUserFromGroup` |
| `DeleteConflict.User.AccessKey` | User still has AKs | `ListAccessKeys` → `DeleteAccessKey` |
| `DeleteConflict.User.Policy` | User still has policies | `ListPoliciesForUser` → `DetachPolicyFromUser` |
| `DeleteConflict.User.LoginProfile` | User has login profile | `GetLoginProfile` → `DeleteLoginProfile` |
| `DeleteConflict.Role.Policy` | Role still has policies | `ListPoliciesForRole` → `DetachPolicyFromRole` |
| `NoPermission` | Caller lacks required permission | HALT; need `AliyunRAMFullAccess` or scope-specific grant |
| Throttling / 429 | Rate limit | Back off; respect `Retry-After` |
| `InternalError` / 5xx | Server error | Retry with exponential backoff (2s, 4s, 8s); HALT with `RequestId` after |

> **Sanitization note (GCL):** When persisting GCL traces, scrub the 11
> RAM-specific secret patterns listed in
> [`rubric.md` §2.2](rubric.md) — `AccessKeySecret`, `Password`,
> `SecurityToken`, `Base32StringSeed`, etc.

---

## 5. CLI / SDK Output Notes

- **Output format:** The `aliyun` CLI emits **JSON by default** — no
  `--output json` flag is required for plain JSON extraction.
- **Tabular extraction:** Use `--output cols=<fields> rows=<root>` to
  extract a flat table.
- **CRITICAL for `CreateAccessKey`:** Use `--output json` (NOT `cols=`) so
  the agent can parse and display `AccessKeyId` + `AccessKeySecret` exactly
  once. Tabular output may be captured by shell history, process monitors,
  or logging systems.
- **URL-encoded responses:** `PolicyDocument` (in `GetPolicy`) and
  `AssumeRolePolicyDocument` (in `GetRole` / `CreateRole`) are
  URL-encoded. Decode before parsing as JSON.
