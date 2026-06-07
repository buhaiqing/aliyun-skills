# Diagnostic Quick Reference — RAM

Quick error lookup for common RAM operation failures. For detailed troubleshooting, see [Troubleshooting Guide](troubleshooting.md).

## Common Error Patterns

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

## Quick Diagnostic Commands

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

## When to Escalate

- `InternalError` persists after 3 retries → HALT; provide RequestId to user
- `NoPermission` on RAM itself → User needs `AliyunRAMFullAccess` or equivalent
- Unexpected error not in this table → HALT; ask user to check Alibaba Cloud status page: https://status.aliyun.com