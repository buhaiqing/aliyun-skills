# CLI — RAM (`aliyun ram` / `aliyun sts`)

## Install and Config

- Install: see [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- **CRITICAL Credentials:** The `aliyun` CLI reads from env vars
  `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR
  `~/.aliyun/config.json` (JSON format).
- For sandbox environments, set env vars directly (preferred) or use
  `--config-path`.

## Conventions (Agent Execution)

- Output is **JSON by default** — NO `--output json` needed for plain JSON
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- `--no-interactive` does NOT exist in `aliyun` CLI — all commands are
  non-interactive by default
- Document **exact** JSON paths after verifying with a real invocation
- RAM is a **global service**; most commands do not require `--RegionId`
- STS commands (`AssumeRole`, `GetCallerIdentity`) use `aliyun sts`, not
  `aliyun ram`

## CLI vs API Coverage Gap

| Operation (API / SDK) | Available via `aliyun`? | Notes |
|-----------------------|------------------------|-------|
| CreateUser | yes | Full support |
| GetUser | yes | Full support |
| UpdateUser | yes | Full support |
| DeleteUser | yes | Full support |
| ListUsers | yes | Full support |
| CreateGroup | yes | Full support |
| GetGroup | yes | Full support |
| DeleteGroup | yes | Full support |
| ListGroups | yes | Full support |
| AddUserToGroup | yes | Full support |
| RemoveUserFromGroup | yes | Full support |
| ListUsersForGroup | yes | Full support |
| CreateRole | yes | Full support |
| GetRole | yes | Full support |
| UpdateRole | yes | Full support |
| DeleteRole | yes | Full support |
| ListRoles | yes | Full support |
| CreatePolicy | yes | Full support |
| GetPolicy | yes | Full support |
| DeletePolicy | yes | Full support |
| ListPolicies | yes | Full support |
| CreatePolicyVersion | yes | Full support |
| GetPolicyVersion | yes | Full support |
| DeletePolicyVersion | yes | Full support |
| ListPolicyVersions | yes | Full support |
| AttachPolicyToUser | yes | Full support |
| AttachPolicyToRole | yes | Full support |
| AttachPolicyToGroup | yes | Full support |
| DetachPolicyFromUser | yes | Full support |
| DetachPolicyFromRole | yes | Full support |
| DetachPolicyFromGroup | yes | Full support |
| ListPoliciesForUser | yes | Full support |
| ListPoliciesForRole | yes | Full support |
| ListPoliciesForGroup | yes | Full support |
| ListEntitiesForPolicy | yes | Full support |
| CreateAccessKey | yes | Full support |
| UpdateAccessKey | yes | Full support |
| DeleteAccessKey | yes | Full support |
| ListAccessKeys | yes | Full support |
| GetAccessKeyLastUsed | yes | Full support |
| CreateLoginProfile | yes | Full support |
| GetLoginProfile | yes | Full support |
| UpdateLoginProfile | yes | Full support |
| DeleteLoginProfile | yes | Full support |
| CreateVirtualMFADevice | yes | Full support |
| BindMFADevice | yes | Full support |
| UnbindMFADevice | yes | Full support |
| DeleteVirtualMFADevice | yes | Full support |
| GetUserMFAInfo | yes | Full support |
| SetPasswordPolicy | yes | Full support |
| GetPasswordPolicy | yes | Full support |
| AssumeRole (STS) | yes | Via `aliyun sts AssumeRole` |
| GetCallerIdentity (STS) | yes | Via `aliyun sts GetCallerIdentity` |

> **Coverage status:** `dual-path` — CLI covers 100% of documented RAM API
> surface. JIT Go SDK fallback is available for edge cases or when CLI
> metadata is stale.

## Command Map

### Users

| Goal | Example `aliyun` invocation | Notes |
|------|---------------------------|-------|
| Create | `aliyun ram CreateUser --UserName alice --DisplayName "Alice L"` | JSON output by default |
| Describe | `aliyun ram GetUser --UserName alice` | JSON output by default |
| Update | `aliyun ram UpdateUser --UserName alice --NewUserName alice2` | Rename or update fields |
| Delete | `aliyun ram DeleteUser --UserName alice` | Irreversible |
| List | `aliyun ram ListUsers --MaxItems 100` | Paginated |

### Groups

| Goal | Example `aliyun` invocation | Notes |
|------|---------------------------|-------|
| Create | `aliyun ram CreateGroup --GroupName developers` | |
| Describe | `aliyun ram GetGroup --GroupName developers` | |
| Delete | `aliyun ram DeleteGroup --GroupName developers` | |
| List | `aliyun ram ListGroups --MaxItems 100` | |
| Add user | `aliyun ram AddUserToGroup --GroupName developers --UserName alice` | |
| Remove user | `aliyun ram RemoveUserFromGroup --GroupName developers --UserName alice` | |
| List users | `aliyun ram ListUsersForGroup --GroupName developers` | |

### Roles

| Goal | Example `aliyun` invocation | Notes |
|------|---------------------------|-------|
| Create | `aliyun ram CreateRole --RoleName MyRole --AssumeRolePolicyDocument '{...}'` | Trust policy as JSON string |
| Describe | `aliyun ram GetRole --RoleName MyRole` | |
| Update | `aliyun ram UpdateRole --RoleName MyRole --AssumeRolePolicyDocument '{...}'` | Update trust policy |
| Delete | `aliyun ram DeleteRole --RoleName MyRole` | |
| List | `aliyun ram ListRoles --MaxItems 100` | |

### Policies

| Goal | Example `aliyun` invocation | Notes |
|------|---------------------------|-------|
| Create | `aliyun ram CreatePolicy --PolicyName my-policy --PolicyDocument '{...}'` | Custom policy only |
| Describe | `aliyun ram GetPolicy --PolicyName my-policy --PolicyType Custom` | |
| Delete | `aliyun ram DeletePolicy --PolicyName my-policy --PolicyType Custom` | Only Custom |
| List | `aliyun ram ListPolicies --PolicyType Custom` | |
| Create version | `aliyun ram CreatePolicyVersion --PolicyName my-policy --PolicyDocument '{...}' --SetAsDefault true` | |
| Attach to user | `aliyun ram AttachPolicyToUser --PolicyName my-policy --PolicyType Custom --UserName alice` | |
| Attach to role | `aliyun ram AttachPolicyToRole --PolicyName my-policy --PolicyType Custom --RoleName MyRole` | |
| Attach to group | `aliyun ram AttachPolicyToGroup --PolicyName my-policy --PolicyType Custom --GroupName developers` | |
| Detach from user | `aliyun ram DetachPolicyFromUser --PolicyName my-policy --PolicyType Custom --UserName alice` | |
| List for user | `aliyun ram ListPoliciesForUser --UserName alice` | |
| List entities | `aliyun ram ListEntitiesForPolicy --PolicyName my-policy --PolicyType Custom` | Who has this policy? |

### Access Keys

| Goal | Example `aliyun` invocation | Notes |
|------|---------------------------|-------|
| Create | `aliyun ram CreateAccessKey --UserName alice` | Secret shown ONCE |
| List | `aliyun ram ListAccessKeys --UserName alice` | |
| Update status | `aliyun ram UpdateAccessKey --UserName alice --AccessKeyId AKxxx --Status Inactive` | |
| Delete | `aliyun ram DeleteAccessKey --UserName alice --AccessKeyId AKxxx` | |
| Last used | `aliyun ram GetAccessKeyLastUsed --AccessKeyId AKxxx` | |

### Login Profiles

| Goal | Example `aliyun` invocation | Notes |
|------|---------------------------|-------|
| Create | `aliyun ram CreateLoginProfile --UserName alice --Password 'MyP@ssw0rd' --PasswordResetRequired true` | |
| Get | `aliyun ram GetLoginProfile --UserName alice` | |
| Update | `aliyun ram UpdateLoginProfile --UserName alice --Password 'NewP@ssw0rd'` | |
| Delete | `aliyun ram DeleteLoginProfile --UserName alice` | |

### MFA

| Goal | Example `aliyun` invocation | Notes |
|------|---------------------------|-------|
| Create device | `aliyun ram CreateVirtualMFADevice --VirtualMFADeviceName alice-mfa` | Returns QR code / seed |
| Bind | `aliyun ram BindMFADevice --SerialNumber mfa-serial --UserName alice --AuthenticationCode1 123456 --AuthenticationCode2 234567` | Two consecutive codes |
| Unbind | `aliyun ram UnbindMFADevice --UserName alice` | |
| Delete device | `aliyun ram DeleteVirtualMFADevice --SerialNumber mfa-serial` | |
| Get user MFA | `aliyun ram GetUserMFAInfo --UserName alice` | |

### Password Policy

| Goal | Example `aliyun` invocation | Notes |
|------|---------------------------|-------|
| Get | `aliyun ram GetPasswordPolicy` | |
| Set | `aliyun ram SetPasswordPolicy --MinimumPasswordLength 12 --RequireUppercaseCharacters true` | |

### STS

| Goal | Example `aliyun` invocation | Notes |
|------|---------------------------|-------|
| AssumeRole | `aliyun sts AssumeRole --RoleArn acs:ram::1234567890123456:role/MyRole --RoleSessionName session1 --DurationSeconds 3600` | |
| GetCallerIdentity | `aliyun sts GetCallerIdentity` | Returns AccountId, Arn, UserId |

## JMESPath Extraction Examples

```bash
# Extract user names only
aliyun ram ListUsers --output cols=UserName rows=Users.User[].UserName

# Extract role ARNs
aliyun ram ListRoles --output cols=Arn rows=Roles.Role[].Arn

# Extract access key IDs and status
aliyun ram ListAccessKeys --UserName alice \
  --output cols=AccessKeyId,Status rows=AccessKeys.AccessKey[]

# Extract policy names
aliyun ram ListPolicies --PolicyType Custom \
  --output cols=PolicyName rows=Policies.Policy[].PolicyName
```

## Critical CLI Notes for RAM

1. **No `--RegionId` needed for most RAM commands** — RAM is global. STS
   `AssumeRole` may accept `--RegionId` for regional endpoints.
2. **PolicyDocument must be valid JSON string** — Use single quotes around the
   entire JSON when passing via CLI to avoid shell escaping issues:
   ```bash
   aliyun ram CreatePolicy --PolicyName my-policy \
     --PolicyDocument '{"Version":"1","Statement":[{"Effect":"Allow","Action":"ecs:*","Resource":"*"}]}'
   ```
3. **Trust policy JSON for roles** — Same JSON string rule applies to
   `AssumeRolePolicyDocument`.
4. **Passwords with special characters** — When creating login profiles, wrap
   passwords in single quotes to prevent shell interpolation:
   ```bash
   aliyun ram CreateLoginProfile --UserName alice --Password 'MyP@$$w0rd!'
   ```
