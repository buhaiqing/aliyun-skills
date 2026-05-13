# API & SDK — RAM

## OpenAPI

- Spec: https://help.aliyun.com/zh/ram/developer-reference/api-ram-2015-05-01-overview
- Base path: `https://ram.aliyuncs.com/`
- API version: `2015-05-01`
- Signature style: RPC

## SDK Operations Map

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Create user | CreateUser | `client.CreateUser()` | `aliyun ram CreateUser` |
| Get user | GetUser | `client.GetUser()` | `aliyun ram GetUser` |
| Update user | UpdateUser | `client.UpdateUser()` | `aliyun ram UpdateUser` |
| Delete user | DeleteUser | `client.DeleteUser()` | `aliyun ram DeleteUser` |
| List users | ListUsers | `client.ListUsers()` | `aliyun ram ListUsers` |
| Create group | CreateGroup | `client.CreateGroup()` | `aliyun ram CreateGroup` |
| Get group | GetGroup | `client.GetGroup()` | `aliyun ram GetGroup` |
| Delete group | DeleteGroup | `client.DeleteGroup()` | `aliyun ram DeleteGroup` |
| List groups | ListGroups | `client.ListGroups()` | `aliyun ram ListGroups` |
| Add user to group | AddUserToGroup | `client.AddUserToGroup()` | `aliyun ram AddUserToGroup` |
| Remove user from group | RemoveUserFromGroup | `client.RemoveUserFromGroup()` | `aliyun ram RemoveUserFromGroup` |
| List users for group | ListUsersForGroup | `client.ListUsersForGroup()` | `aliyun ram ListUsersForGroup` |
| Create role | CreateRole | `client.CreateRole()` | `aliyun ram CreateRole` |
| Get role | GetRole | `client.GetRole()` | `aliyun ram GetRole` |
| Update role | UpdateRole | `client.UpdateRole()` | `aliyun ram UpdateRole` |
| Delete role | DeleteRole | `client.DeleteRole()` | `aliyun ram DeleteRole` |
| List roles | ListRoles | `client.ListRoles()` | `aliyun ram ListRoles` |
| Create policy | CreatePolicy | `client.CreatePolicy()` | `aliyun ram CreatePolicy` |
| Get policy | GetPolicy | `client.GetPolicy()` | `aliyun ram GetPolicy` |
| Delete policy | DeletePolicy | `client.DeletePolicy()` | `aliyun ram DeletePolicy` |
| List policies | ListPolicies | `client.ListPolicies()` | `aliyun ram ListPolicies` |
| Create policy version | CreatePolicyVersion | `client.CreatePolicyVersion()` | `aliyun ram CreatePolicyVersion` |
| Get policy version | GetPolicyVersion | `client.GetPolicyVersion()` | `aliyun ram GetPolicyVersion` |
| Delete policy version | DeletePolicyVersion | `client.DeletePolicyVersion()` | `aliyun ram DeletePolicyVersion` |
| List policy versions | ListPolicyVersions | `client.ListPolicyVersions()` | `aliyun ram ListPolicyVersions` |
| Attach policy to user | AttachPolicyToUser | `client.AttachPolicyToUser()` | `aliyun ram AttachPolicyToUser` |
| Attach policy to role | AttachPolicyToRole | `client.AttachPolicyToRole()` | `aliyun ram AttachPolicyToRole` |
| Attach policy to group | AttachPolicyToGroup | `client.AttachPolicyToGroup()` | `aliyun ram AttachPolicyToGroup` |
| Detach policy from user | DetachPolicyFromUser | `client.DetachPolicyFromUser()` | `aliyun ram DetachPolicyFromUser` |
| Detach policy from role | DetachPolicyFromRole | `client.DetachPolicyFromRole()` | `aliyun ram DetachPolicyFromRole` |
| Detach policy from group | DetachPolicyFromGroup | `client.DetachPolicyFromGroup()` | `aliyun ram DetachPolicyFromGroup` |
| List policies for user | ListPoliciesForUser | `client.ListPoliciesForUser()` | `aliyun ram ListPoliciesForUser` |
| List policies for role | ListPoliciesForRole | `client.ListPoliciesForRole()` | `aliyun ram ListPoliciesForRole` |
| List policies for group | ListPoliciesForGroup | `client.ListPoliciesForGroup()` | `aliyun ram ListPoliciesForGroup` |
| List entities for policy | ListEntitiesForPolicy | `client.ListEntitiesForPolicy()` | `aliyun ram ListEntitiesForPolicy` |
| Create access key | CreateAccessKey | `client.CreateAccessKey()` | `aliyun ram CreateAccessKey` |
| Update access key | UpdateAccessKey | `client.UpdateAccessKey()` | `aliyun ram UpdateAccessKey` |
| Delete access key | DeleteAccessKey | `client.DeleteAccessKey()` | `aliyun ram DeleteAccessKey` |
| List access keys | ListAccessKeys | `client.ListAccessKeys()` | `aliyun ram ListAccessKeys` |
| Get access key last used | GetAccessKeyLastUsed | `client.GetAccessKeyLastUsed()` | `aliyun ram GetAccessKeyLastUsed` |
| Create login profile | CreateLoginProfile | `client.CreateLoginProfile()` | `aliyun ram CreateLoginProfile` |
| Get login profile | GetLoginProfile | `client.GetLoginProfile()` | `aliyun ram GetLoginProfile` |
| Update login profile | UpdateLoginProfile | `client.UpdateLoginProfile()` | `aliyun ram UpdateLoginProfile` |
| Delete login profile | DeleteLoginProfile | `client.DeleteLoginProfile()` | `aliyun ram DeleteLoginProfile` |
| Create virtual MFA device | CreateVirtualMFADevice | `client.CreateVirtualMFADevice()` | `aliyun ram CreateVirtualMFADevice` |
| Bind MFA device | BindMFADevice | `client.BindMFADevice()` | `aliyun ram BindMFADevice` |
| Unbind MFA device | UnbindMFADevice | `client.UnbindMFADevice()` | `aliyun ram UnbindMFADevice` |
| Delete virtual MFA device | DeleteVirtualMFADevice | `client.DeleteVirtualMFADevice()` | `aliyun ram DeleteVirtualMFADevice` |
| Get user MFA info | GetUserMFAInfo | `client.GetUserMFAInfo()` | `aliyun ram GetUserMFAInfo` |
| Set password policy | SetPasswordPolicy | `client.SetPasswordPolicy()` | `aliyun ram SetPasswordPolicy` |
| Get password policy | GetPasswordPolicy | `client.GetPasswordPolicy()` | `aliyun ram GetPasswordPolicy` |
| AssumeRole (STS) | AssumeRole | `stsClient.AssumeRole()` | `aliyun sts AssumeRole` |
| GetCallerIdentity (STS) | GetCallerIdentity | `stsClient.GetCallerIdentity()` | `aliyun sts GetCallerIdentity` |

## Request / Response Notes

- **Required fields:**
  - `CreateUser`: `UserName`
  - `CreateRole`: `RoleName`, `AssumeRolePolicyDocument`
  - `CreatePolicy`: `PolicyName`, `PolicyDocument`
  - `CreateAccessKey`: `UserName`
  - `AssumeRole`: `RoleArn`, `RoleSessionName`
- **Pagination:** `ListUsers`, `ListRoles`, `ListGroups`, `ListPolicies` support
  `MaxItems` (default 100, max 1000) and `Marker` for pagination.
- **PolicyDocument encoding:** The `PolicyDocument` field in responses
  (e.g., `GetPolicy`, `GetRole`) is **URL-encoded**. Decode before parsing as
  JSON.
- **Global endpoint:** `ram.aliyuncs.com` (no region-specific endpoint needed
  for most operations).
- **STS endpoint:** `sts.aliyuncs.com` or regional endpoints like
  `sts.cn-hangzhou.aliyuncs.com`.

## Go SDK Package

```bash
go get github.com/alibabacloud-go/ram-20150501/v2/client
go get github.com/alibabacloud-go/sts-20150401/v2/client
```

## SDK Client Initialization

```go
import (
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    ram "github.com/alibabacloud-go/ram-20150501/v2/client"
)

config := &openapi.Config{
    AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
    AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
    Endpoint:        tea.String("ram.aliyuncs.com"),
}

client, err := ram.NewClient(config)
```
