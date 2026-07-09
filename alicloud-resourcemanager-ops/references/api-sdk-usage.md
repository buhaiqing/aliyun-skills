# API & SDK — Resource Manager & Tag

## OpenAPI References

- Resource Manager: [API Reference (2020-03-31)](https://help.aliyun.com/zh/resource-management/developer-reference/api-overview)
- Tag: [API Reference (2018-08-28)](https://help.aliyun.com/zh/tag/developer-reference/api-reference)

## Go SDK Packages

| Product | Go SDK Package | Import Path |
|---------|---------------|-------------|
| Resource Manager | resourcemanager-20200331/v2 | `github.com/alibabacloud-go/resourcemanager-20200331/v2/client` |
| Tag | tag-20180828/v2 | `github.com/alibabacloud-go/tag-20180828/v2/client` |

## SDK Operations Map — Resource Manager

| Goal | API OperationId | CLI Available? | Required Fields | Optional Fields |
|------|-----------------|---------------|-----------------|-----------------|
| Get Directory | GetResourceDirectory | Yes | — | — |
| Enable Directory | EnableResourceDirectory | Yes | — | — |
| List Accounts | ListAccounts | Yes | — | PageNumber, PageSize |
| Get Account | GetAccount | Yes | AccountId | — |
| Create Resource Acct | CreateResourceAccount | Yes | DisplayName | ParentFolderId, PayerAccountId |
| Create Cloud Acct | CreateCloudAccount | Yes | DisplayName, Email | ParentFolderId, PayerAccountId |
| Remove Cloud Acct | RemoveCloudAccount | Yes | AccountId | — |
| Move Account | MoveAccount | Yes | AccountId, DestinationFolderId | — |
| List Folders | ListFoldersForParent | Yes | ParentFolderId | PageNumber, PageSize |
| Get Folder | GetFolder | Yes | FolderId | — |
| Create Folder | CreateFolder | Yes | FolderName, ParentFolderId | — |
| Update Folder | UpdateFolder | Yes | FolderId, NewFolderName | — |
| Delete Folder | DeleteFolder | Yes | FolderId | — |
| List Resource Groups | ListResourceGroups | Yes | — | PageNumber, PageSize, Status |
| Get Resource Group | GetResourceGroup | Yes | ResourceGroupId | IncludeTags |
| Create Resource Group | CreateResourceGroup | Yes | DisplayName, Name | — |
| Update Resource Group | UpdateResourceGroup | Yes | ResourceGroupId, NewDisplayName | — |
| Delete Resource Group | DeleteResourceGroup | Yes | ResourceGroupId | — |
| Move Resources | MoveResources | Yes | Resources, ResourceGroupId | — |
| List Resources | ListResources | Yes | — | ResourceGroupId, ResourceId, ResourceType, Service, Region, PageNumber, PageSize |
| List Control Policies | ListControlPolicies | Yes | — | PolicyType, Language, PageNumber, PageSize |
| Get Control Policy | GetControlPolicy | Yes | PolicyId | Language |
| Attach Control Policy | AttachControlPolicy | Yes | PolicyId, TargetId | — |
| Detach Control Policy | DetachControlPolicy | Yes | PolicyId, TargetId | — |
| Invite Account | InviteAccountToResourceDirectory | Yes | TargetEntity, TargetType | Note |
| Get Handshake | GetHandshake | Yes | HandshakeId | — |
| Accept Handshake | AcceptHandshake | Yes | HandshakeId | — |
| List Ancestors | ListAncestors | Yes | ChildId | — |

## SDK Operations Map — Tag

| Goal | API OperationId | CLI Available? | Required Fields | Optional Fields |
|------|-----------------|---------------|-----------------|-----------------|
| List Tag Keys | ListTagKeys | Yes | — | NextToken, MaxResult, Category, FuzzyType, QueryType |
| List Tag Values | ListTagValues | Yes | Key | NextToken, MaxResult, FuzzyType |
| Create Tags | CreateTags | Yes | TagKeyValueParamList | — |
| Delete Tag | DeleteTag | Yes | Key, Value | — |
| Tag Resources | TagResources | Yes | RegionId, ResourceARN[], Tags | — |
| Untag Resources | UntagResources | Yes | RegionId, ResourceARN[], TagKey[] | — |
| List Tag Resources | ListTagResources | Yes | RegionId | ResourceARN[], TagFilter, NextToken, MaxResult |
| List Tag Policies | ListTagPolicies | Yes | — | NextToken, MaxResult |
| Get Policy | GetPolicy | Yes | PolicyId | — |
| Create Policy | CreatePolicy | Yes | PolicyName, PolicyDesc, PolicyContent | — |
| Delete Policy | DeletePolicy | Yes | PolicyId | — |
| Attach Config Rule | AttachConfigRuleToPolicy | Yes | TargetId, TargetType, PolicyId | — |
| Effective Policy | GetEffectivePolicy | Yes | TargetId, TargetType | — |
| Policy Enable Status | GetPolicyEnableStatus | Yes | UserType, TargetId | — |

## Pagination

### Resource Manager:
- `PageNumber` (1-based) + `PageSize` (default 10, max 100)
- Response includes `TotalCount` and `PageSize`

### Tag:
- `NextToken` (cursor-based) + `MaxResult` (default 50, max 1000)
- Response includes `NextToken` for next page; empty = last page

## Request/Response Notes

### Resource Manager Common Patterns:

**ListAccounts response:**
```json
{
  "RequestId": "...",
  "TotalCount": 5,
  "PageNumber": 1,
  "PageSize": 10,
  "Accounts": {
    "Account": [
      {
        "AccountId": "123456789012",
        "AccountName": "account@example.com",
        "DisplayName": "dev-account",
        "Status": "CreateSuccess",
        "Type": "ResourceAccount",
        "JoinMethod": "created",
        "FolderId": "fd-xxxx"
      }
    ]
  }
}
```

**CreateResourceAccount response:**
```json
{
  "RequestId": "...",
  "Account": {
    "AccountId": "123456789012",
    "AccountName": "account@example.com",
    "DisplayName": "dev-account",
    "Status": "CreateVerifying",
    "Type": "ResourceAccount"
  }
}
```

**ListResourceGroups response:**
```json
{
  "RequestId": "...",
  "TotalCount": 3,
  "PageNumber": 1,
  "PageSize": 10,
  "ResourceGroups": {
    "ResourceGroup": [
      {
        "Id": "rg-xxxx",
        "Name": "my-rg",
        "DisplayName": "Production",
        "Status": "OK",
        "AccountId": "123456789012",
        "CreateDate": "2024-01-15T08:00:00Z"
      }
    ]
  }
}
```

### Tag Common Patterns:

**TagResources request:**
```json
{
  "RegionId": "cn-hangzhou",
  "ResourceARN": ["acs:ecs:cn-hangzhou:123456789012:instance/i-xxxx"],
  "Tags": "{\"env\":\"production\",\"project\":\"app1\"}"
}
```

**TagResources response:**
```json
{
  "RequestId": "...",
  "FailedResources": {
    "TagResource": [
      {
        "ResourceARN": "acs:ecs:...",
        "Code": "InvalidParameter.ResourceType",
        "Message": "Resource type not supported"
      }
    ]
  }
}
```

### State Transitions (Resource Manager)

| Operation | Initial State | Terminal State | Poll Interval | Max Wait |
|-----------|---------------|----------------|---------------|----------|
| CreateResourceAccount | CreateVerifying | CreateSuccess | 5s | 120s |
| CreateCloudAccount | CreateVerifying | CreateSuccess | 5s | 120s |
| RemoveCloudAccount | — | account absent from ListAccounts | 5s | 60s |
| DeleteFolder | — | folder absent from ListFolders | 5s | 30s |
| DeleteResourceGroup | — | group absent from ListResourceGroups | 5s | 30s |

### Resource Type Reference (for MoveResources / TagResources)

| Product | Resource Type | Example ARN Pattern |
|---------|---------------|---------------------|
| ECS | instance | `acs:ecs:{region}:{uid}:instance/{id}` |
| ECS | disk | `acs:ecs:{region}:{uid}:disk/{id}` |
| ECS | snapshot | `acs:ecs:{region}:{uid}:snapshot/{id}` |
| ECS | image | `acs:ecs:{region}:{uid}:image/{id}` |
| ECS | securitygroup | `acs:ecs:{region}:{uid}:securitygroup/{id}` |
| RDS | instance | `acs:rds:{region}:{uid}:dbinstance/{id}` |
| OSS | bucket | `acs:oss:{region}:{uid}:{bucketname}` |
| SLB | loadbalancer | `acs:slb:{region}:{uid}:loadbalancer/{id}` |
| VPC | vpc | `acs:vpc:{region}:{uid}:vpc/{id}` |
| VPC | vswitch | `acs:vpc:{region}:{uid}:vswitch/{id}` |
