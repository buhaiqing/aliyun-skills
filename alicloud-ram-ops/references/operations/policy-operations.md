# RAM Policy — Operations

> All policy operations live here: **CreatePolicy / GetPolicy / ListPolicies /
> CreatePolicyVersion / GetPolicyVersion / ListPolicyVersions /
> AttachPolicyToUser / AttachPolicyToRole / AttachPolicyToGroup /
> DetachPolicyFromUser / DetachPolicyFromRole / DetachPolicyFromGroup /
> ListPoliciesForUser / ListPoliciesForRole / ListPoliciesForGroup /
> ListEntitiesForPolicy / DeletePolicy**.
>
> For per-operation JSON paths, see
> [`api-response-reference.md`](../api-response-reference.md). For CLI
> conventions, see [`cli-usage.md`](../cli-usage.md).
> For ready-to-use policy JSON examples, see
> [`policy-examples.md`](../policy-examples.md).

---

## Policy Document Structure

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

> **GCL escalation warnings:**
>
> 1. `Action: "*"` + `Resource: "*"` without `Condition` is flagged
>    high-risk. Agent MUST collect user justification.
> 2. Modifying a custom policy to widen scope (e.g., adding `ram:*` to
>    Action) is a privilege-escalation pattern. See
>    [`rubric.md`](../rubric.md) §1.2.1.
> 3. Attaching `AdministratorAccess` to any non-root identity requires
>    extra justification in the GCL trace.

---

## Operation: Create RAM Policy

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Policy name format | Regex: `^[a-zA-Z0-9_-]{1,128}$` | Valid | Ask for valid name |
| Policy document JSON | Validate JSON structure | Valid JSON with Version, Statement | Fix syntax; retry |
| Policy document size | Length ≤ 6144 characters | Within limit | Split into multiple policies or reduce scope |
| Duplicate | `aliyun ram GetPolicy --PolicyName {{user.policy_name}} --PolicyType Custom` | `EntityNotExist` | Ask reuse vs new name |

### Execution — CLI

```bash
aliyun ram CreatePolicy \
  --PolicyName "{{user.policy_name}}" \
  --PolicyDocument '{{user.policy_document}}' \
  --Description "{{user.policy_description}}"
```

### Post-execution Validation

```bash
aliyun ram GetPolicy \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType Custom
```

Report `PolicyName`, `PolicyType`, `DefaultVersion`, and `Description`.

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityAlreadyExists.Policy` | 0 | — | Ask reuse vs new name |
| `InvalidParameter.PolicyName` | 0 | — | Fix name format; retry once |
| `InvalidParameter.PolicyDocument` | 0 | — | Fix JSON syntax; retry once |
| `LimitExceeded.Policy` | 0 | — | Document size > 6144 chars; split policy |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

## Operation: Create Policy Version

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Policy exists | `aliyun ram GetPolicy --PolicyName {{user.policy_name}} --PolicyType Custom` | Success | HALT; create policy first |
| Version limit | `aliyun ram ListPolicyVersions --PolicyName {{user.policy_name}} --PolicyType Custom` | < 5 versions | Delete old versions first |
| Policy document JSON | Validate JSON structure | Valid JSON with Version, Statement | Fix syntax; retry |
| Document size | Length ≤ 6144 characters | Within limit | Split or reduce scope |

### Execution — CLI

```bash
aliyun ram CreatePolicyVersion \
  --PolicyName "{{user.policy_name}}" \
  --PolicyDocument '{{user.policy_document}}' \
  --SetAsDefault {{user.set_as_default}}
```

> `SetAsDefault`: `true` or `false`. If `true`, the new version becomes the
> default version used for all attachments.

### Post-execution Validation

```bash
aliyun ram GetPolicy \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType Custom
```

Report `PolicyName`, `DefaultVersion`, and version count.

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.Policy` | 0 | — | HALT; policy does not exist |
| `LimitExceeded.Policy.Version` | 0 | — | Delete old non-default versions first |
| `InvalidParameter.PolicyDocument` | 0 | — | Fix JSON syntax; retry once |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |

---

## Operation: Describe Policy

### Execution — CLI

```bash
# Get a custom policy
aliyun ram GetPolicy --PolicyName "{{user.policy_name}}" --PolicyType Custom

# Get a system policy
aliyun ram GetPolicy --PolicyName "AliyunECSReadOnlyAccess" --PolicyType System

# Get a specific version (PolicyDocument is URL-encoded)
aliyun ram GetPolicyVersion \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType Custom \
  --VersionId "{{user.version_id}}"

# List all custom policies
aliyun ram ListPolicies --PolicyType Custom --MaxItems 100

# List all system policies (e.g., find AliyunXxxAccess policies)
aliyun ram ListPolicies --PolicyType System --MaxItems 100 --Scope AlibabaCloud
```

### Present to User

| Field | Path | Notes |
|-------|------|-------|
| PolicyName | `$.Policy.PolicyName` | Plain text |
| PolicyType | `$.Policy.PolicyType` | `Custom` or `System` |
| DefaultVersion | `$.Policy.DefaultVersion` | e.g., `v1`, `v2` |
| Description | `$.Policy.Description` | May be absent |
| PolicyDocument | `$.Policy.PolicyDocument` | URL-encoded — decode before parsing |
| CreateDate | `$.Policy.CreateDate` | ISO 8601 |
| UpdateDate | `$.Policy.UpdateDate` | ISO 8601 |
| AttachmentCount | `$.Policy.AttachmentCount` | Number of attached entities |

---

## Operation: Attach Policy to User

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `GetUser --UserName {{user.user_name}}` | Success | HALT; create user first |
| Policy exists | `GetPolicy --PolicyName {{user.policy_name}} --PolicyType {{user.policy_type}}` | Success | HALT; create policy first |

### Execution — CLI

```bash
aliyun ram AttachPolicyToUser \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType "{{user.policy_type}}" \
  --UserName "{{user.user_name}}"
```

> `PolicyType` is `Custom` or `System`.

### Post-execution Validation

```bash
aliyun ram ListPoliciesForUser --UserName "{{user.user_name}}"
```

---

## Operation: Attach Policy to Role

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Role exists | `GetRole --RoleName {{user.role_name}}` | Success | HALT; create role first |
| Policy exists | `GetPolicy --PolicyName {{user.policy_name}} --PolicyType {{user.policy_type}}` | Success | HALT; create policy first |

### Execution — CLI

```bash
aliyun ram AttachPolicyToRole \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType "{{user.policy_type}}" \
  --RoleName "{{user.role_name}}"
```

### Post-execution Validation

```bash
aliyun ram ListPoliciesForRole --RoleName "{{user.role_name}}"
```

---

## Operation: Attach Policy to Group

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Group exists | `GetGroup --GroupName {{user.group_name}}` | Success | HALT; create group first |
| Policy exists | `GetPolicy --PolicyName {{user.policy_name}} --PolicyType {{user.policy_type}}` | Success | HALT; create policy first |

### Execution — CLI

```bash
aliyun ram AttachPolicyToGroup \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType "{{user.policy_type}}" \
  --GroupName "{{user.group_name}}"
```

### Post-execution Validation

```bash
aliyun ram ListPoliciesForGroup --GroupName "{{user.group_name}}"
```

---

## Operation: Detach Policy

### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation when detaching from a production
  identity.
- **MUST** warn about potential access loss.

### Execution — CLI

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

### Post-execution Validation

```bash
# Per identity, re-list and confirm the policy is gone
aliyun ram ListPoliciesForUser --UserName "{{user.user_name}}"
aliyun ram ListPoliciesForRole --RoleName "{{user.role_name}}"
aliyun ram ListPoliciesForGroup --GroupName "{{user.group_name}}"
```

---

## Operation: Delete RAM Policy

### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- **MUST** check if policy is attached to any user, group, or role using
  `ListEntitiesForPolicy`.
- **MUST** warn that attached entities will lose permissions.
- **MUST NOT** allow deletion of System policies.

### Execution — CLI

```bash
aliyun ram DeletePolicy \
  --PolicyName "{{user.policy_name}}" \
  --PolicyType "Custom"
```

> Only `Custom` policies can be deleted. System policies are managed by Alibaba
> Cloud and cannot be deleted.

### Post-execution Validation

1. Call `GetPolicy` with `--PolicyType Custom` — expect `EntityNotExist.Policy`.
2. Call `ListPolicies --PolicyType Custom` — policy should not appear.
3. Report success.

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.Policy` | 0 | — | HALT; policy does not exist |
| `EntityNotExist` (System policy) | 0 | — | System policies cannot be deleted |
| `DeleteConflict.Policy.Entity` | 0 | — | Detach from all entities first |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |
