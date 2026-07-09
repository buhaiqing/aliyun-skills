# RAM User, LoginProfile, AccessKey & MFA — Operations

> All per-user resource operations live here:
> **User** (Create/Describe/Update/Delete) +
> **LoginProfile** (Create/Get/Update/Delete) +
> **AccessKey** (Create/List/Update/Delete + Rotation) +
> **Virtual MFA** (Create/Bind/Unbind/Delete + `GetUserMFAInfo`).
>
> For per-operation JSON paths, see
> [`api-response-reference.md`](../api-response-reference.md). For CLI
> conventions, see [`cli-usage.md`](../cli-usage.md).

---

## Operation: Create RAM User

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SDK / deps | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys / valid config | HALT; user configures env |
| User name format | Regex: `^[a-zA-Z0-9_.@-]{1,64}$` | Valid | Ask for valid name |
| Duplicate | `aliyun ram GetUser --UserName {{user.user_name}}` | `EntityNotExist` | Ask reuse vs new name |

### Execution — CLI (`aliyun`) (Primary Path)

```bash
aliyun ram CreateUser \
  --UserName "{{user.user_name}}" \
  --DisplayName "{{user.display_name}}" \
  --MobilePhone "{{user.mobile_phone}}" \
  --Email "{{user.email}}"
```

> Optional parameters: `DisplayName`, `MobilePhone`, `Email`, `Comments`.
> All are optional; only `UserName` is required.

### Execution — JIT Go SDK (Fallback Path)

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

### Post-execution Validation

1. Read `{{output.user_id}}` from `$.User.UserId`.
2. Call `GetUser` to confirm existence:
   ```bash
   aliyun ram GetUser --UserName "{{user.user_name}}"
   ```
3. Report `UserName`, `UserId`, and `CreateDate` to the user.

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityAlreadyExists.User` | 0 | — | Ask reuse vs new name |
| `InvalidParameter.UserName` | 0 | — | Fix name format; retry once |
| `InvalidParameter.DisplayName` | 0 | — | Fix display name; retry once |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

## Operation: Describe RAM User

### Execution — CLI

```bash
# Get single user
aliyun ram GetUser --UserName "{{user.user_name}}"

# List all users (paginated)
aliyun ram ListUsers --MaxItems 100

# Extract specific fields
aliyun ram GetUser --UserName "{{user.user_name}}" \
  --output cols=UserName,UserId,CreateDate,LastLoginDate rows=User
```

### Present to User

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

## Operation: Update RAM User

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `aliyun ram GetUser --UserName {{user.user_name}}` | Success | HALT; create user first |
| New user name format | If renaming, regex `^[a-zA-Z0-9_.@-]{1,64}$` | Valid | Ask for valid name |
| Duplicate new name | If renaming, `GetUser` with new name | `EntityNotExist` | Ask different name |

### Execution — CLI

```bash
aliyun ram UpdateUser \
  --UserName "{{user.user_name}}" \
  --NewUserName "{{user.new_user_name}}" \
  --NewDisplayName "{{user.new_display_name}}" \
  --NewMobilePhone "{{user.new_mobile_phone}}" \
  --NewEmail "{{user.new_email}}"
```

> At least one of `NewUserName`, `NewDisplayName`, `NewMobilePhone`,
> `NewEmail` must be provided. `NewUserName` renames the user; all other
> fields update existing attributes.

### Post-execution Validation

```bash
aliyun ram GetUser --UserName "{{user.new_user_name}}"
```

Report updated fields to user.

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.User` | 0 | — | HALT; user does not exist |
| `EntityAlreadyExists.User` | 0 | — | New name already taken; ask different name |
| `InvalidParameter.NewUserName` | 0 | — | Fix format; retry once |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |

---

## Operation: Delete RAM User

### Pre-flight (Safety Gate)

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

### Execution — CLI

```bash
aliyun ram DeleteUser --UserName "{{user.user_name}}"
```

### Post-execution Validation

1. Call `GetUser` — expect `EntityNotExist.User` or equivalent 404.
2. Call `ListAccessKeys` — should return empty for this user.
3. Report success to user.

### Failure Recovery

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

## Operation: Create Login Profile

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `GetUser` | Success | HALT; create user first |
| No existing profile | `GetLoginProfile` | `EntityNotExist` | Ask update vs skip |

### Execution — CLI

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

## Operation: Get Login Profile

### Execution — CLI

```bash
aliyun ram GetLoginProfile --UserName "{{user.user_name}}"
```

> Returns `$.LoginProfile.{UserName,PasswordResetRequired,MFABindRequired}`.
> Throws `EntityNotExist.LoginProfile` if no profile is set.

---

## Operation: Update Login Profile

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `GetUser` | Success | HALT; create user first |
| Profile exists | `GetLoginProfile` | Success | HALT; create profile first |

### Execution — CLI

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

### Post-execution Validation

```bash
aliyun ram GetLoginProfile --UserName "{{user.user_name}}"
```

Report `PasswordResetRequired` and `MFABindRequired` status.

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.User` | 0 | — | HALT; user does not exist |
| `EntityNotExist.LoginProfile` | 0 | — | HALT; create login profile first |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |

---

## Operation: Delete Login Profile

### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- **MUST** warn that the user will lose console access.

### Execution — CLI

```bash
aliyun ram DeleteLoginProfile --UserName "{{user.user_name}}"
```

---

## Operation: Create Access Key for RAM User

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `aliyun ram GetUser --UserName {{user.user_name}}` | Success | HALT; create user first |
| Key limit | `aliyun ram ListAccessKeys --UserName {{user.user_name}}` | < 2 keys | HALT; delete old key first |

### Execution — CLI

```bash
aliyun ram CreateAccessKey --UserName "{{user.user_name}}"
```

### Post-execution Validation

1. Read `{{output.access_key_id}}` and `{{output.access_key_secret}` from
   response.
2. **CRITICAL:** Display `AccessKeyId` and `AccessKeySecret` to the user
   **exactly once**. After this, the secret is irretrievable.
3. Call `ListAccessKeys` to confirm the new key is `Active`.

### Security Handling

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

## Operation: List Access Keys

### Execution — CLI

```bash
aliyun ram ListAccessKeys --UserName "{{user.user_name}}"
```

### Present to User

| Field | Path | Notes |
|-------|------|-------|
| AccessKeyId | `$.AccessKeys.AccessKey[].AccessKeyId` | Plain text |
| Status | `$.AccessKeys.AccessKey[].Status` | `Active` or `Inactive` |
| CreateDate | `$.AccessKeys.AccessKey[].CreateDate` | ISO 8601 |

### When to check `GetAccessKeyLastUsed`

Call `GetAccessKeyLastUsed --AccessKeyId <id>` to learn **when** the key
last authenticated to the API. Use this during:

- **Key rotation:** confirm the old key is no longer in use before
  `DeleteAccessKey`.
- **Least-privilege audit:** flag keys with no recent usage as candidates
  for deletion.

---

## Operation: Update Access Key Status

### Execution — CLI

```bash
aliyun ram UpdateAccessKey \
  --UserName "{{user.user_name}}" \
  --AccessKeyId "{{user.access_key_id}}" \
  --Status "Inactive"
```

> `Status` values: `Active` or `Inactive`.

---

## Operation: Delete Access Key

### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- **MUST** warn that any application using this key will immediately lose access.
- **MUST** check `GetAccessKeyLastUsed` to see if the key was recently used.

### Execution — CLI

```bash
aliyun ram DeleteAccessKey \
  --UserName "{{user.user_name}}" \
  --AccessKeyId "{{user.access_key_id}}"
```

---

## Operation: Access Key Rotation

### Flow

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

## Operation: Create Virtual MFA Device

### Execution — CLI

```bash
aliyun ram CreateVirtualMFADevice \
  --VirtualMFADeviceName "{{user.mfa_device_name}}"
```

### Post-execution Validation

1. Read `$.VirtualMFADevice.SerialNumber` and `$.VirtualMFADevice.Base32StringSeed`
   or `$.VirtualMFADevice.QRCodePNG` from response.
2. Present QR code or base32 seed to user for device enrollment.
3. After user enrolls device, call `BindMFADevice` with two consecutive TOTP codes.

---

## Operation: Bind MFA Device

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `GetUser` | Success | HALT; create user first |
| Serial provided | User provided SerialNumber from `CreateVirtualMFADevice` | Non-empty | Ask user for serial |
| Two TOTP codes | User provided 2 consecutive codes | 6 digits each | Ask user to wait & re-enter |

### Execution — CLI

```bash
aliyun ram BindMFADevice \
  --SerialNumber "{{output.mfa_serial_number}}" \
  --UserName "{{user.user_name}}" \
  --AuthenticationCode1 "{{user.totp_code_1}}" \
  --AuthenticationCode2 "{{user.totp_code_2}}"
```

> `AuthenticationCode1` and `AuthenticationCode2` must be two consecutive
> TOTP codes from the user's MFA device.

### Post-execution Validation

```bash
aliyun ram GetUserMFAInfo --UserName "{{user.user_name}}"
```

> Expect `$.UserMFAInfo.MFADevice` to contain the bound device ARN.

---

## Operation: Unbind MFA Device

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `GetUser` | Success | HALT; create user first |
| MFA bound | `GetUserMFAInfo` | Has MFA device | HALT; no MFA to unbind |

### Execution — CLI

```bash
aliyun ram UnbindMFADevice --UserName "{{user.user_name}}"
```

> After unbinding, the virtual MFA device still exists and can be re-bound or
> deleted separately.

### Post-execution Validation

```bash
aliyun ram GetUserMFAInfo --UserName "{{user.user_name}}"
```

Expect no MFA device attached.

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.User` | 0 | — | HALT; user does not exist |
| `EntityNotExist.MFADevice` | 0 | — | HALT; no MFA device bound |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |

---

## Operation: Delete Virtual MFA Device

### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- **MUST** warn that the user will lose MFA protection.

### Execution — CLI

```bash
aliyun ram DeleteVirtualMFADevice \
  --SerialNumber "{{output.mfa_serial_number}}"
```
