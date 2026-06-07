# RAM Role & STS — Operations

> All role and STS operations live here: **CreateRole / GetRole / ListRoles /
> UpdateRole / DeleteRole / STS AssumeRole / STS GetCallerIdentity**.
>
> For per-operation JSON paths, see
> [`api-response-reference.md`](../api-response-reference.md). For CLI
> conventions, see [`cli-usage.md`](../cli-usage.md).

---

## Trust Policy Document Structure

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

> **GCL escalation warning:** A trust policy with `Principal: {"RAM":
> ["acs:ram::*:*"]}` (any account) is a privilege-escalation pattern. The
> agent MUST collect explicit user justification in the GCL trace before
> submitting. See [`rubric.md`](../rubric.md) §1.2.1.

---

## Operation: Create RAM Role

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Role name format | Regex: `^[a-zA-Z0-9_.@-]{1,64}$` | Valid | Ask for valid name |
| Trust policy JSON | Validate JSON structure | Valid JSON | Fix syntax; retry |
| Duplicate | `aliyun ram GetRole --RoleName {{user.role_name}}` | `EntityNotExist` | Ask reuse vs new name |

### Execution — CLI

```bash
# Trust policy must be a properly escaped JSON string
aliyun ram CreateRole \
  --RoleName "{{user.role_name}}" \
  --AssumeRolePolicyDocument '{{user.assume_role_policy_document}}' \
  --Description "{{user.description}}" \
  --MaxSessionDuration {{user.max_session_duration}}
```

> `MaxSessionDuration` is optional (default 3600 seconds, max 43200).

### Execution — JIT Go SDK

```go
request := &ram.CreateRoleRequest{
    RoleName:                 tea.String(os.Getenv("RAM_ROLE_NAME")),
    AssumeRolePolicyDocument: tea.String(os.Getenv("RAM_TRUST_POLICY")),
    Description:              tea.String(os.Getenv("RAM_ROLE_DESCRIPTION")),
}
response, err := client.CreateRole(request)
```

### Post-execution Validation

1. Read `{{output.role_arn}}` from `$.Role.Arn`.
2. Call `GetRole` to confirm:
   ```bash
   aliyun ram GetRole --RoleName "{{user.role_name}}"
   ```
3. Report `RoleName`, `RoleId`, `Arn`, and `MaxSessionDuration`.

---

## Operation: Describe RAM Role

### Execution — CLI

```bash
# Get single role
aliyun ram GetRole --RoleName "{{user.role_name}}"

# List all roles (paginated)
aliyun ram ListRoles --MaxItems 100

# Extract ARN
aliyun ram GetRole --RoleName "{{user.role_name}}" \
  --output cols=RoleName,RoleId,Arn,MaxSessionDuration rows=Role
```

### Present to User

| Field | Path | Notes |
|-------|------|-------|
| RoleName | `$.Role.RoleName` | Plain text |
| RoleId | `$.Role.RoleId` | Plain text |
| Arn | `$.Role.Arn` | Full ARN for AssumeRole |
| MaxSessionDuration | `$.Role.MaxSessionDuration` | Seconds |
| CreateDate | `$.Role.CreateDate` | ISO 8601 |
| AssumeRolePolicyDocument | `$.Role.AssumeRolePolicyDocument` | URL-encoded JSON |

---

## Operation: Update RAM Role

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Role exists | `aliyun ram GetRole --RoleName {{user.role_name}}` | Success | HALT; create role first |
| New role name format | If renaming, regex `^[a-zA-Z0-9_.@-]{1,64}$` | Valid | Ask for valid name |
| Trust policy JSON | If updating, validate JSON | Valid JSON | Fix syntax; retry |
| MaxSessionDuration | If provided, 900–43200 | In range | Fix value; retry |

### Execution — CLI

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

### Post-execution Validation

```bash
aliyun ram GetRole --RoleName "{{user.new_role_name}}"
```

Report updated fields to user.

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.Role` | 0 | — | HALT; role does not exist |
| `EntityAlreadyExists.Role` | 0 | — | New name already taken; ask different name |
| `InvalidParameter.AssumeRolePolicyDocument` | 0 | — | Fix trust policy JSON; retry once |
| `InvalidParameter.MaxSessionDuration` | 0 | — | Fix to 900–43200; retry once |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |

---

## Operation: Delete RAM Role

### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- **MUST** check for attached policies (`ListPoliciesForRole`) and warn that
  they will be implicitly detached.
- **MUST** warn that any running STS sessions are not affected, but new
  AssumeRole calls will fail.

### Execution — CLI

```bash
aliyun ram DeleteRole --RoleName "{{user.role_name}}"
```

### Post-execution Validation

1. Call `GetRole` — expect `EntityNotExist.Role`.
2. Report success.

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.Role` | 0 | — | HALT; role does not exist |
| `DeleteConflict.Role.Policy` | 0 | — | Detach all policies first |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

## Operation: STS AssumeRole

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Role exists | `aliyun ram GetRole --RoleName {{user.role_name}}` | Success | HALT; create role first |
| Role ARN | Parse from `GetRole` | Valid ARN | HALT |
| Trust policy permits caller | Inspect `AssumeRolePolicyDocument` | Caller is in `Principal` | HALT; fix trust policy |

### Execution — CLI

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

### Execution — JIT Go SDK

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

### Post-execution Validation

1. Read `$.Credentials.AccessKeyId`, `$.Credentials.AccessKeySecret`,
   `$.Credentials.SecurityToken`, `$.Credentials.Expiration`.
2. Display temporary credentials to user (these expire; no need for one-time
   restriction like permanent AKs, but still treat as sensitive).
3. Report `Expiration` timestamp.

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.Role` | 0 | — | HALT; role does not exist |
| `InvalidParameter.DurationSeconds` | 0 | — | Fix to 900–43200; retry once |
| `NoPermission` | 0 | — | HALT; caller lacks `sts:AssumeRole` |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

> **GCL escalation warning:** If the target role has `AdministratorAccess`
> attached AND `DurationSeconds > 3600`, the agent MUST collect explicit
> user justification in the GCL trace. See [`rubric.md`](../rubric.md) §1.2.

---

## Operation: Get Caller Identity

### Execution — CLI

```bash
aliyun sts GetCallerIdentity
```

### Present to User

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

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `NoPermission` | 0 | — | HALT; caller lacks STS permissions |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |
