# Troubleshooting Alibaba Cloud RAM

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `EntityAlreadyExists` / 409 | User/group/role/policy already exists | Ask reuse vs new name |
| `EntityNotExist` / 404 | User/group/role/policy not found | Verify name; check region (RAM is global) |
| `InvalidParameter` / 400 | Request failed validation | Check parameter format per OpenAPI spec |
| `InvalidParameter.UserName` | Invalid user name format | 1-64 chars, letters/digits/.@-_ |
| `InvalidParameter.PolicyDocument` | Invalid policy JSON | Validate JSON structure and RAM policy syntax |
| `NoPermission` / 403 | Insufficient permissions to perform operation | User needs `ram:*` or specific RAM action |
| `DeleteConflict` / 409 | Resource has dependencies | Remove dependencies first (AccessKey, login profile, group membership) |
| `EntityQuotaExceeded` / 400 | Quota exceeded for this resource type | HALT; user raises quota or deletes unused resources |
| `Throttling` / 429 | Rate limit exceeded | Back off exponentially; respect Retry-After |
| `InternalError` / 500 | Server-side error | Retry with backoff; then HALT with RequestId |

---

## Symptom-to-Root-Cause Quick Reference

When user reports a problem, use this table to narrow down the investigation path.

| User Symptom | Most Likely Root Cause Category | First Check |
|--------------|----------------------------------|-------------|
| "访问被拒绝" / "AccessDenied" | 缺少对应资源的RAM权限 | GetCallerIdentity + 检查策略 |
| "创建用户失败" / "EntityAlreadyExists" | 用户名已存在 | ListUsers 检查 |
| "删除用户失败" / "DeleteConflict" | 用户仍有依赖资源 | 检查AccessKey/登录配置/组成员 |
| "AssumeRole失败" | 信任策略配置错误 | GetRole 检查信任策略 |
| "AccessKey无法使用" | 密钥状态为Inactive或已删除 | ListAccessKeys 检查状态 |
| "控制台登录失败" | 登录配置未创建或密码错误 | GetLoginProfile 检查 |
| "MFA绑定失败" | TOTP验证码错误或设备已绑定 | GetUserMFAInfo 检查 |
| "策略不生效" | 策略语法错误或未正确附加 | GetPolicy 检查策略文档 |
| "无法删除策略" | 策略被引用或版本问题 | ListEntitiesForPolicy 检查引用 |
| "用户组删除失败" | 组内仍有用户 | ListUsersForGroup 检查组成员 |
| "角色删除失败" | 角色被策略引用 | ListPoliciesForRole 检查 |
| "跨账号访问不通" | 信任策略或附加策略错误 | GetRole + 信任策略检查 |

---

## Scenario-Based Diagnostic Playbooks

### Scenario 1: "用户无法访问云资源" (Access Denied)

**Symptoms:** RAM user reports "AccessDenied" when trying to access a cloud resource.

**Diagnostic Flow (execute in order, stop when root cause found):**

```bash
# Step 1: Verify the caller identity
aliyun sts GetCallerIdentity

# Step 2: List policies attached to the user
aliyun ram ListPoliciesForUser --UserName "{{user.user_name}}" \
  --output cols=PolicyName,PolicyType,DefaultVersion rows=Policies.Policy[].{PolicyName,PolicyType,DefaultVersion}

# Step 3: Check if user is in a group with policies
aliyun ram ListGroupsForUser --UserName "{{user.user_name}}" \
  --output cols=GroupName rows=Groups.Group[].GroupName

# Step 4: For each group, list attached policies
aliyun ram ListPoliciesForGroup --GroupName "{{user.group_name}}" \
  --output cols=PolicyName,PolicyType rows=Policies.Policy[].{PolicyName,PolicyType}

# Step 5: Check if the required action is in the policy
aliyun ram GetPolicy --PolicyName "{{user.policy_name}}" --PolicyType "Custom"
# Decode the URL-encoded PolicyDocument and check for required action
```

**Decision Tree:**
- No policies attached → Attach required policy (e.g., `AliyunECSReadOnlyAccess`)
- Policy exists but action not included → Update policy to include required action
- Policy has `"Effect": "Deny"` with `"Resource": "*"` → Deny overrides Allow; remove deny
- Policy has `"Condition"` that doesn't match request context → Check condition keys
- User in group with correct policy → Check if group policy is correctly attached
- All policies correct → Check resource-level policies (bucket policy, etc.)

---

### Scenario 2: "AccessKey轮换" (Access Key Rotation)

**Symptoms:** Need to rotate an access key due to security policy or suspected compromise.

**Diagnostic Flow:**

```bash
# Step 1: List existing access keys
aliyun ram ListAccessKeys --UserName "{{user.user_name}}" \
  --output cols=AccessKeyId,Status,CreateDate rows=AccessKeys.AccessKey[].{AccessKeyId,Status,CreateDate}

# Step 2: Check last used time for each key
aliyun ram GetAccessKeyLastUsed --UserName "{{user.user_name}}" --UserAccessKeyId "{{user.access_key_id}}" \
  --output cols=LastUsedDate rows=AccessKeyLastUsed.LastUsedDate

# Step 3: Create new access key
aliyun ram CreateAccessKey --UserName "{{user.user_name}}"
# → Display AccessKeyId and AccessKeySecret ONCE

# Step 4: After user confirms applications updated → disable old key
aliyun ram UpdateAccessKey --UserName "{{user.user_name}}" --UserAccessKeyId "{{old_key}}" --Status Inactive

# Step 5: After grace period → delete old key
aliyun ram DeleteAccessKey --UserName "{{user.user_name}}" --UserAccessKeyId "{{old_key}}"
```

**Decision Tree:**
- Key count = 2 (max) → Must delete one key before creating new one
- Key unused > 90 days → Safe to delete immediately
- Key used recently → Follow rotation flow with grace period
- Suspected compromise → Disable immediately, create new key, then delete compromised key

---

### Scenario 3: "跨账号角色扮演失败" (Cross-Account AssumeRole Failure)

**Symptoms:** Cannot assume a RAM role from another account.

**Diagnostic Flow:**

```bash
# Step 1: Check if the role exists
aliyun ram GetRole --RoleName "{{user.role_name}}" \
  --output cols=RoleName,Arn,AssumeRolePolicyDocument rows='{RoleName,Arn,AssumeRolePolicyDocument}'

# Step 2: Decode and check the trust policy
# The AssumeRolePolicyDocument is URL-encoded; decode and check:
# - Principal.RAM contains the correct account ID
# - Action includes "sts:AssumeRole"
# - Effect is "Allow"

# Step 3: Check policies attached to the role
aliyun ram ListPoliciesForRole --RoleName "{{user.role_name}}" \
  --output cols=PolicyName,PolicyType rows=Policies.Policy[].{PolicyName,PolicyType}

# Step 4: Test AssumeRole
aliyun sts AssumeRole --RoleArn "{{output.role_arn}}" --RoleSessionName "test-session"
```

**Decision Tree:**
- Role not found → Create role with correct trust policy
- Trust policy has wrong account ID → Update trust policy with correct account
- Trust policy missing `sts:AssumeRole` → Add `sts:AssumeRole` action
- No policies attached to role → Attach policies for resource access
- AssumeRole returns `AccessDenied` → Check if source account has `sts:AssumeRole` permission

---

### Scenario 4: "策略不生效" (Policy Not Taking Effect)

**Symptoms:** A RAM policy was attached but the expected permission change is not observed.

**Diagnostic Flow:**

```bash
# Step 1: Get the policy document
aliyun ram GetPolicy --PolicyName "{{user.policy_name}}" --PolicyType "Custom" \
  --output cols=PolicyDocument rows=PolicyDocument

# Step 2: Decode the URL-encoded policy document
# Check for:
# - Correct Action list
# - Correct Resource ARN
# - Effect is "Allow" (not "Deny")
# - No Condition that might restrict access

# Step 3: Check policy version (if multiple versions)
aliyun ram ListPolicyVersions --PolicyName "{{user.policy_name}}" --PolicyType "Custom" \
  --output cols=VersionId,IsDefaultVersion,CreateDate rows=PolicyVersions.PolicyVersion[].{VersionId,IsDefaultVersion,CreateDate}

# Step 4: Verify the policy is attached to the correct entity
aliyun ram ListEntitiesForPolicy --PolicyName "{{user.policy_name}}" --PolicyType "Custom" \
  --output cols=EntityType,EntityName rows=Entities.Entity[].{EntityType,EntityName}
```

**Decision Tree:**
- Policy not attached → Attach to user/group/role
- Wrong policy version active → SetDefaultPolicyVersion to correct version
- Policy has `"Effect": "Deny"` → Deny overrides Allow; remove deny statement
- Policy has restrictive `"Condition"` → Check if request context matches condition
- Policy attached to wrong entity → Detach and reattach to correct entity
- Resource-level policy (OSS/SLS bucket policy) blocking → Check resource-level policy

---

## Diagnostic Order (Standard)

1. **Verify caller identity:** `aliyun sts GetCallerIdentity`
2. **Check user/group/role existence:** `GetUser`, `GetGroup`, `GetRole`
3. **List attached policies:** `ListPoliciesForUser`, `ListPoliciesForGroup`, `ListPoliciesForRole`
4. **Inspect policy document:** `GetPolicy` + decode URL-encoded document
5. **Check policy version:** `ListPolicyVersions` to verify active version
6. **Check access keys:** `ListAccessKeys` + `GetAccessKeyLastUsed`
7. **Check login profile:** `GetLoginProfile` for console access
8. **Check MFA status:** `GetUserMFAInfo` for MFA binding
9. **Cross-skill delegation:** If resource access issue → delegate to product-specific skill (e.g., `alicloud-ecs-ops`)

---

## One-Shot Diagnostic Scripts

### Script 1: Full RAM User Audit

```bash
#!/bin/bash
# ram-user-audit.sh
# Usage: ./ram-user-audit.sh <UserName>

USER_NAME="$1"

echo "=== User Details ==="
aliyun ram GetUser --UserName "$USER_NAME" \
  --output cols=UserId,UserName,DisplayName,CreateDate,LastLoginDate \
  rows='{UserId,UserName,DisplayName,CreateDate,LastLoginDate}'

echo ""
echo "=== Attached Policies ==="
aliyun ram ListPoliciesForUser --UserName "$USER_NAME" \
  --output cols=PolicyName,PolicyType,AttachDate \
  rows=Policies.Policy[].{PolicyName,PolicyType,AttachDate}

echo ""
echo "=== Group Memberships ==="
aliyun ram ListGroupsForUser --UserName "$USER_NAME" \
  --output cols=GroupName rows=Groups.Group[].GroupName

echo ""
echo "=== Access Keys ==="
aliyun ram ListAccessKeys --UserName "$USER_NAME" \
  --output cols=AccessKeyId,Status,CreateDate \
  rows=AccessKeys.AccessKey[].{AccessKeyId,Status,CreateDate}

echo ""
echo "=== Login Profile ==="
aliyun ram GetLoginProfile --UserName "$USER_NAME" 2>/dev/null || echo "No login profile"

echo ""
echo "=== MFA Status ==="
aliyun ram GetUserMFAInfo --UserName "$USER_NAME" 2>/dev/null || echo "No MFA device"
```

### Script 2: Policy Impact Analysis

```bash
#!/bin/bash
# ram-policy-impact-analysis.sh
# Usage: ./ram-policy-impact-analysis.sh <PolicyName> <PolicyType>

POLICY_NAME="$1"
POLICY_TYPE="${2:-Custom}"

echo "=== Policy Details ==="
aliyun ram GetPolicy --PolicyName "$POLICY_NAME" --PolicyType "$POLICY_TYPE" \
  --output cols=PolicyName,PolicyType,DefaultVersion,AttachmentCount,PolicyDocument \
  rows='{PolicyName,PolicyType,DefaultVersion,AttachmentCount,PolicyDocument}'

echo ""
echo "=== Entities Using This Policy ==="
aliyun ram ListEntitiesForPolicy --PolicyName "$POLICY_NAME" --PolicyType "$POLICY_TYPE" \
  --output cols=EntityType,EntityName,AttachDate \
  rows=Entities.Entity[].{EntityType,EntityName,AttachDate}

echo ""
echo "=== Policy Versions ==="
aliyun ram ListPolicyVersions --PolicyName "$POLICY_NAME" --PolicyType "$POLICY_TYPE" \
  --output cols=VersionId,IsDefaultVersion,CreateDate \
  rows=PolicyVersions.PolicyVersion[].{VersionId,IsDefaultVersion,CreateDate}
```