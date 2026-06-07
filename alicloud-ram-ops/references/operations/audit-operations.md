# RAM Audit, Password Policy & Key Rotation — Operations

> Cross-user operations live here: **SetPasswordPolicy / GetPasswordPolicy /
> Least-Privilege Audit** (read-only inspection across all identities) and
> **Access Key Rotation** (multi-step flow that touches several per-user
> operations). Per-step operations link out to
> [`user-operations.md`](user-operations.md) and
> [`policy-operations.md`](policy-operations.md).
>
> For per-operation JSON paths, see
> [`api-response-reference.md`](../api-response-reference.md). For CLI
> conventions, see [`cli-usage.md`](../cli-usage.md).

---

## Operation: Set Password Policy

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Min length | 8–32 | In range | Fix to 8–32 |
| Max login attempts | 3–32 | In range | Fix to 3–32 |
| Password reuse | 1–24 | In range | Fix to 1–24 |
| Max password age | 0–180 | In range | Fix to 0–180 (0 = no expiration) |
| Loosening? | Compare against `GetPasswordPolicy` | New values are NOT less strict | Require explicit user confirmation |

> **GCL escalation warning:** Setting `MinimumPasswordLength < 12`,
> disabling symbol/number requirements, or raising `MaxLoginAttempts`
> above 5 is a **loosening** change. The agent MUST collect explicit
> user justification. See [`rubric.md`](../rubric.md) §1.2.

### Execution — CLI

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

### Post-execution Validation

```bash
aliyun ram GetPasswordPolicy
```

Report all policy settings to user.

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` | 0 | — | Fix out-of-range value; retry once |
| `NoPermission` | 0 | — | HALT; need `AliyunRAMFullAccess` |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |

---

## Operation: Get Password Policy

### Execution — CLI

```bash
aliyun ram GetPasswordPolicy
```

### Present to User

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

## Operation: Least-Privilege Audit

### Flow

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

### Risk Classification Heuristics

| Finding | Risk | Remediation Hint |
|---------|------|------------------|
| Custom policy with `Action: "*"` + `Resource: "*"` and no `Condition` | **High** | Replace with least-privilege policy (scope Action + Resource + add Condition) |
| Custom policy with `Action: "ram:*"` | **High** | Scope to `ram:Get*` / `ram:List*` (read-only) unless write is required |
| Custom policy with `Action: "ecs:Delete*"` or `Action: "rds:Delete*"` | **High** | Restrict to specific instance ARNs and add `Condition` |
| Access key unused for > 90 days (`GetAccessKeyLastUsed`) | **Medium** | Rotate or delete — see [Key Rotation](user-operations.md#operation-access-key-rotation) |
| User with both `AdministratorAccess` AND console login | **High** | Use a role with scope-bounded `Aliyun*Admin` instead |
| Login profile without MFA (`MFABindRequired=false`) | **Medium** | Run MFA setup flow (see [Bind MFA](user-operations.md#operation-bind-mfa-device)) |
| Password policy `MinimumPasswordLength < 12` | **Medium** | Call `SetPasswordPolicy` with min length 12 |

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `NoPermission` | 0 | — | HALT; need `AliyunRAMReadOnlyAccess` minimum |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

## Operation: Access Key Rotation (Multi-Step Flow)

> **User-supervised:** This flow MUST wait for explicit user confirmation
> between the "new key active" step and the "delete old key" step. The
> agent MUST NOT auto-delete the old key after the grace period.

### Pre-flight Checks (one-time, before starting)

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `GetUser` | Success | HALT; create user first |
| Current key count | `ListAccessKeys --UserName {{user.user_name}}` | ≤ 1 key (room for one new) | HALT; delete old first or escalate |
| Grace period | Ask user | User-defined (recommend 24h) | HALT; require explicit value |

### Step-by-Step Flow

1. **Create new access key**
   → [`user-operations.md` §Create Access Key](user-operations.md#operation-create-access-key-for-ram-user)

2. **Display new key pair ONCE** to the user. The agent MUST NOT log the
   `AccessKeySecret` to any file or chat history after display.

3. **Instruct user** to update all applications / CI pipelines / SDK
   configs with the new `AccessKeyId` + `AccessKeySecret`.

4. **Wait for user confirmation** that applications are updated. Provide
   a way to skip the wait for testing environments (with explicit caveat).

5. **Update old key status to `Inactive`**
   → [`user-operations.md` §Update Access Key Status](user-operations.md#operation-update-access-key-status)

6. **Monitor for errors** for the user-defined grace period (default 24h).
   Suggest the user check application logs / API error rates.

7. **Delete old access key** — only after grace period AND user confirmation
   → [`user-operations.md` §Delete Access Key](user-operations.md#operation-delete-access-key)

### Failure Recovery (per-step)

Each step's failure recovery lives in its linked operation. For the
**multi-step flow as a whole**:

| Error pattern | Agent Action |
|---------------|--------------|
| New key created but app update failed | Keep both keys Active; do NOT advance to step 5 until user confirms |
| Old key Inactive but app still uses it | Re-activate old key (`UpdateAccessKey --Status Active`) and re-iterate from step 3 |
| `DeleteAccessKey` fails on stale dependency | HALT; investigate before retrying |

> **Best practice:** Rotate access keys every 90 days. See
> [`operational-best-practices.md`](../operational-best-practices.md) for
> the full guidance set.
