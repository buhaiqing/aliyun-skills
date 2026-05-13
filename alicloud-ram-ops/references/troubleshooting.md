# Troubleshooting RAM

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `EntityAlreadyExists.User` | User already exists | Ask reuse vs new name |
| `EntityAlreadyExists.Group` | Group already exists | Ask reuse vs new name |
| `EntityAlreadyExists.Role` | Role already exists | Ask reuse vs new name |
| `EntityAlreadyExists.Policy` | Policy already exists | Ask reuse vs new name |
| `EntityNotExist.User` | User does not exist | HALT; verify name or create first |
| `EntityNotExist.Group` | Group does not exist | HALT; verify name or create first |
| `EntityNotExist.Role` | Role does not exist | HALT; verify name or create first |
| `EntityNotExist.Policy` | Policy does not exist | HALT; verify name or create first |
| `EntityNotExist.LoginProfile` | No login profile for user | HALT; create login profile first |
| `DeleteConflict.User.Group` | User still in groups | Remove from all groups first |
| `DeleteConflict.User.AccessKey` | User still has access keys | Delete access keys first |
| `DeleteConflict.User.Policy` | User still has attached policies | Detach all policies first |
| `DeleteConflict.Role.Policy` | Role still has attached policies | Detach all policies first |
| `DeleteConflict.Policy.Version` | Policy has multiple versions | Delete non-default versions first |
| `InvalidParameter.UserName` | Invalid user name format | Fix to `^[a-zA-Z0-9_.@-]{1,64}$` |
| `InvalidParameter.PolicyName` | Invalid policy name format | Fix to `^[a-zA-Z0-9_-]{1,128}$` |
| `InvalidParameter.PolicyDocument` | Invalid policy JSON | Validate JSON structure; check Version="1" |
| `InvalidParameter.AssumeRolePolicyDocument` | Invalid trust policy | Validate JSON; ensure Principal is correct |
| `InvalidParameter.AccessKeyId.NotFound` | Access key not found | Verify key ID belongs to user |
| `NoPermission` | Insufficient RAM permissions | User needs `AliyunRAMFullAccess` or scoped policy |
| `NoPermission.STS` | Insufficient STS permissions | User needs `sts:AssumeRole` on role resource |
| `LimitExceeded.AccessKey` | Max 2 access keys per user | Delete old key before creating new |
| `LimitExceeded.Policy.Version` | Max 5 versions per policy | Delete old versions before creating new |
| `MalformedPolicyDocument` | Policy syntax error | Check JSON validity, Action/Resource format |
| `Throttling` | Rate limit exceeded | Back off exponentially; max 3 retries |
| `InternalError` | Server-side error | Retry with 2s/4s/8s backoff; then HALT with RequestId |

## Diagnostic Order

1. **Verify identity exists:**
   ```bash
   aliyun ram GetUser --UserName "{{user.user_name}}"
   aliyun ram GetRole --RoleName "{{user.role_name}}"
   aliyun ram GetPolicy --PolicyName "{{user.policy_name}}" --PolicyType Custom
   ```

2. **Check attached dependencies before delete:**
   ```bash
   # For users
   aliyun ram ListPoliciesForUser --UserName "{{user.user_name}}"
   aliyun ram ListGroupsForUser --UserName "{{user.user_name}}"
   aliyun ram ListAccessKeys --UserName "{{user.user_name}}"
   aliyun ram GetLoginProfile --UserName "{{user.user_name}}"
   aliyun ram GetUserMFAInfo --UserName "{{user.user_name}}"

   # For roles
   aliyun ram ListPoliciesForRole --RoleName "{{user.role_name}}"

   # For policies
   aliyun ram ListEntitiesForPolicy --PolicyName "{{user.policy_name}}" --PolicyType Custom
   ```

3. **Verify caller permissions:**
   ```bash
   aliyun sts GetCallerIdentity
   ```
   Check if caller has `AliyunRAMFullAccess` or equivalent custom policy.

4. **Verify policy syntax:**
   ```bash
   # Test by creating a minimal policy
   aliyun ram CreatePolicy --PolicyName test-policy \
     --PolicyDocument '{"Version":"1","Statement":[{"Effect":"Allow","Action":"ecs:DescribeInstances","Resource":"*"}]}'
   ```

5. **Check CLI metadata coverage:**
   ```bash
   aliyun ram --help
   aliyun sts --help
   ```

## RAM-Specific Issues

### Issue: "NoPermission" when managing RAM

**Cause:** The caller (RAM user or role) does not have permission to manage RAM
resources.

**Resolution:**
- Attach `AliyunRAMFullAccess` system policy for full RAM management.
- Or attach a custom policy with specific RAM actions:
  ```json
  {
    "Version": "1",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "ram:Get*",
          "ram:List*",
          "ram:CreateUser",
          "ram:DeleteUser",
          "ram:CreateRole",
          "ram:DeleteRole"
        ],
        "Resource": "*"
      }
    ]
  }
  ```

### Issue: "DeleteConflict.User.Group" when deleting user

**Cause:** User is still a member of one or more groups.

**Resolution:**
```bash
# List groups for user
aliyun ram ListGroupsForUser --UserName "{{user.user_name}}"

# Remove from each group
aliyun ram RemoveUserFromGroup --GroupName "group1" --UserName "{{user.user_name}}"

# Then delete user
aliyun ram DeleteUser --UserName "{{user.user_name}}"
```

### Issue: "DeleteConflict.User.AccessKey" when deleting user

**Cause:** User still has active or inactive access keys.

**Resolution:**
```bash
# List and delete all access keys
aliyun ram ListAccessKeys --UserName "{{user.user_name}}"
aliyun ram DeleteAccessKey --UserName "{{user.user_name}}" --AccessKeyId "AKxxx"
```

### Issue: "MalformedPolicyDocument" when creating policy

**Cause:** The policy document JSON has syntax errors or violates RAM policy rules.

**Diagnostic steps:**
1. **Validate JSON syntax:**
   ```bash
   echo '{{user.policy_document}}' | jq .
   ```
2. **Check required fields:**
   - `Version` MUST be exactly `"1"`
   - `Statement` MUST be an array of objects
   - Each statement MUST have `Effect` (`Allow` or `Deny`)
   - Each statement MUST have `Action` (string or array)
   - Each statement MUST have `Resource` (string or array)
3. **Check common mistakes:**
   - Trailing commas in JSON arrays/objects
   - Unquoted keys or values
   - `Effect` spelled incorrectly (e.g., `effect` instead of `Effect`)
   - `Action` using wrong service prefix (e.g., `ec2:` instead of `ecs:`)
4. **Test with minimal policy:**
   ```bash
   aliyun ram CreatePolicy --PolicyName test-policy \
     --PolicyDocument '{"Version":"1","Statement":[{"Effect":"Allow","Action":"ecs:DescribeInstances","Resource":"*"}]}'
   ```

### Issue: PolicyDocument URL-encoded in response

**Cause:** RAM API returns `PolicyDocument` as URL-encoded string.

**Resolution:**
```bash
# Extract and decode
aliyun ram GetPolicy --PolicyName my-policy --PolicyType Custom | \
  jq -r '.Policy.PolicyDocument' | \
  python3 -c "import sys,urllib.parse; print(urllib.parse.unquote(sys.stdin.read()))"
```

### Issue: STS AssumeRole fails with "NoPermission.STS"

**Cause:** The caller does not have `sts:AssumeRole` permission on the target
role, or the role's trust policy does not trust the caller.

**Resolution:**
1. Check role trust policy:
   ```bash
   aliyun ram GetRole --RoleName "{{user.role_name}}"
   ```
2. Ensure trust policy Principal includes the caller.
3. Ensure caller has policy with `sts:AssumeRole` on the role ARN.

### Issue: Access key secret lost after creation

**Cause:** `CreateAccessKey` returns the secret only once. There is no API to
retrieve it later.

**Resolution:**
- If the secret is lost, create a new access key and delete the old one.
- Use STS AssumeRole instead of long-term access keys where possible.
