---
name: alicloud-resourcemanager-ops
description: >-
  Use this skill to manage Alibaba Cloud Resource Directory, accounts, folders, resource groups, tags, tag policies, and tag governance — account creation/movement/removal, folder hierarchy management, resource group CRUD and resource movement, control policies for governance, account invitations/external joins, tag key/value lifecycle, batch resource tagging/untagging, tag-based cost allocation, resource group-based cost attribution, tag compliance auditing, and governance (unused accounts, tag coverage gaps, policy violations). User mentions "资源目录", "账号", "子账号", "资源夹", "文件夹", "资源组", "标签", "标签策略", "标签治理", "分账", "成本归属", "resourcemanager", "resource manager", "tag", "tag policy", "TagResources", "CreateResourceGroup", "ListResourceGroups", "ListTagKeys" — even without naming the product explicitly. Not for RAM permissions/identity management (delegate to alicloud-ram-ops), billing/queries outside tag-based cost allocation (delegate to alicloud-billing-ops), resource-level CRUD for specific products (delegate to product-specific skills e.g., alicloud-ecs-ops, alicloud-rds-ops), or monitoring (delegate to alicloud-cms-ops).
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints. Both `aliyun resourcemanager` and `aliyun tag` are fully supported.
  Region-independent (global) endpoints: resourcemanager.aliyuncs.com and tag.aliyuncs.com.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-05-30"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "ResourceManager 2020-03-31 / Tag 2018-08-28"
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun help resourcemanager | grep -i list` — Resource Manager CLI exposes
    all operations: ListAccounts, ListFolders, ListResourceGroups, CreateResourceGroup,
    CreateFolder, MoveAccount, ListControlPolicies, etc. Confirmed via `aliyun help tag | grep -i list` —
    Tag CLI exposes: ListTagKeys, ListTagValues, TagResources, UntagResources, ListTagResources,
    CreateTags, DeleteTag, ListTagPolicies, CreatePolicy, AttachConfigRuleToPolicy.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Resource Manager & Tag Operations Skill

## Overview

Resource Manager (资源管理) provides enterprise-grade multi-account management and resource grouping on Alibaba Cloud: **Resource Directory** for account hierarchy, **Resource Groups** for logical grouping, and **Control Policies** for governance. **Tag** (标签) provides metadata tagging for resources, enabling cost allocation, compliance enforcement, and resource classification. This skill is an **operational runbook** for agents covering both products.

> **UX Compliance:** This skill follows the [User Experience Specification](../alicloud-skill-generator/references/user-experience-spec.md). All operations include onboarding guidance, minimal prompts, smart defaults, clear feedback, and user-friendly error handling.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Both `aliyun resourcemanager` and `aliyun tag` CLI support this product. This skill ships `references/cli-usage.md` and documents **both** the CLI step and the JIT Go SDK fallback for every operation. Both products use **region-independent** endpoints — no `--RegionId` parameter needed.

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers covering Resource Manager + Tag domains; explicit delegation to alicloud-ram-ops, alicloud-billing-ops, alicloud-cms-ops, product-specific skills |
| 2 | **Structured I/O** | `{{env.*}}` for credentials/region, `{{user.*}}` for resource IDs/names/config, `{{output.*}}` for API response capture |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute (CLI primary + Go SDK fallback) → Validate → Recover |
| 4 | **Complete Failure Strategies** | Error taxonomy with 12+ product-specific error codes covering RM and Tag; HALT vs retry per error type |
| 5 | **Absolute Single Responsibility** | Covers ResourceManager + Tag (governance pair); delegates RAM, billing, monitoring, product-specific CRUD |

### Well-Architected Framework Integration (卓越架构)

| Pillar | Skill Integration | Reference |
|--------|-------------------|-----------|
| **安全 (Security)** | Control policies for governance, least-privilege RAM for operations, tag-based access control | `references/well-architected-assessment.md` §2.1 |
| **稳定 (Stability)** | Resource group isolation, folder hierarchy best practices, disaster recovery patterns | `references/well-architected-assessment.md` §2.2 |
| **成本 (Cost)** | Tag-based cost allocation (FinOps), resource group cost attribution, idle account detection | `references/well-architected-assessment.md` §2.3 |
| **效率 (Efficiency)** | Batch tagging via TagResources, bulk account operations, Terraform integration | `references/well-architected-assessment.md` §2.4 |
| **性能 (Performance)** | API rate limits, pagination best practices, tag policy evaluation performance | `references/well-architected-assessment.md` §2.5 |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud Resource Manager" OR "资源管理" OR "resourcemanager"
- User mentions "Alibaba Cloud Tag" OR "标签" OR "标签策略" OR "标签治理" OR "tag"
- Task involves **Resource Directory** (开通/查询资源目录, EnableResourceDirectory, GetResourceDirectory)
- Task involves **Account management** (创建/移除/移动账号, CreateResourceAccount, CreateCloudAccount, RemoveCloudAccount, MoveAccount)
- Task involves **Folder hierarchy** (创建/更新/删除文件夹, CreateFolder, UpdateFolder, DeleteFolder, ListFolders)
- Task involves **Resource Groups** (创建/更新/删除/查询资源组, CreateResourceGroup, UpdateResourceGroup, DeleteResourceGroup, ListResourceGroups)
- Task involves **Resource Group membership** (迁移资源, MoveResources, ListResources)
- Task involves **Control Policies** (管控策略查询/绑定/解绑, ListControlPolicies, AttachControlPolicy, DetachControlPolicy)
- Task involves **Account Invitation** (邀请外部账号, InviteAccountToResourceDirectory, GetHandshake, AcceptHandshake)
- Task involves **Tag lifecycle** (创建/删除/查询标签键值, CreateTags, DeleteTag, ListTagKeys, ListTagValues)
- Task involves **Resource tagging** (批量打标/解标/查询, TagResources, UntagResources, ListTagResources)
- Task involves **Tag Policies** (标签策略管理, CreatePolicy, ListTagPolicies, AttachConfigRuleToPolicy)
- Task involves **FinOps cost allocation** (标签分账, 资源组分账, 成本归属)
- Task involves **Governance audits** (闲置账号检测, 未打标资源发现, 标签合规审计, 管控策略合规检查)

### SHOULD NOT Use This Skill When

- Task is purely RAM / permission / identity management → delegate to: `alicloud-ram-ops`
- Task is billing queries / cost analysis outside tag-based allocation → delegate to: `alicloud-billing-ops`
- Task is resource-level CRUD for specific products (ECS, RDS, OSS, etc.) → delegate to: `alicloud-ecs-ops`, `alicloud-rds-ops`, etc.
- Task is monitoring / alerting → delegate to: `alicloud-cms-ops`
- Task is IAM credential key management → delegate to: `alicloud-ram-ops`
- User insists on **console-only** flows with no API → state limitation; do not invent undocumented HTTP steps

### Delegation Rules

- Resource Directory is a prerequisite for resource groups and control policies — verify directory status first.
- When creating accounts, RAM user provisioning is handled by `alicloud-ram-ops`.
- When moving resources between groups, verify resource existence via the respective product skill.
- Tag-based access control (ABAC) policies are managed by `alicloud-ram-ops`.

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | For tag operations scoped to a region (TagResources) |
| `{{user.account_name}}` | User-supplied account display name | Ask once; reuse |
| `{{user.account_id}}` | User-supplied account UID | Ask once; reuse |
| `{{user.folder_id}}` | User-supplied folder ID | Ask once; reuse |
| `{{user.folder_name}}` | User-supplied folder name | Ask once; reuse |
| `{{user.parent_folder_id}}` | Parent folder ID for hierarchy | Ask once; reuse |
| `{{user.resource_group_id}}` | Resource group ID | Ask once; reuse |
| `{{user.resource_group_name}}` | Resource group display name | Ask once; reuse |
| `{{user.policy_id}}` | Control/tag policy ID | Ask once; reuse |
| `{{user.tag_key}}` | Tag key name | Ask once; reuse |
| `{{user.tag_value}}` | Tag value | Ask once; reuse |
| `{{user.resource_id}}` | Resource ARN or ID to tag/move | Ask once; reuse |
| `{{user.resource_type}}` | Resource type (e.g., instance, disk) | Ask once; reuse |
| `{{user.target_resource_group_id}}` | Target RG for MoveResources | Ask once; reuse |
| `{{output.resource_directory_id}}` | From API response | Parse per OpenAPI |
| `{{output.account_id}}` | From CreateAccount response | Parse per OpenAPI |
| `{{output.folder_id}}` | From CreateFolder response | Parse per OpenAPI |
| `{{output.resource_group_id}}` | From CreateResourceGroup response | Parse per OpenAPI |
| `{{output.handshake_id}}` | From InviteAccount response | Parse per OpenAPI |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET` in console output, debug messages, error messages, or logs. Use existence checks only: `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "set"`.

## API and Response Conventions (Agent-Readable)

- **Resource Manager endpoint:** `resourcemanager.aliyuncs.com` — region-independent, no `RegionId` parameter.
- **Tag endpoint:** `tag.aliyuncs.com` — region-independent for management APIs; regional for resource tagging APIs (`TagResources` uses `RegionId`).
- **Response format:** All APIs return JSON. Key fields: `RequestId`, operation-specific data fields.
- **Pagination:** `MaxResults` (default 10, max 100) + `NextToken` for list operations.

### Centralized JSON Paths

```
# Common JSON Paths:
# ResourceDirectory: $.ResourceDirectory.{MasterAccountId,MasterAccountName,RootFolderId,Status}
# Account list: $.Accounts.Account[].{AccountId,AccountName,DisplayName,Status,Type,JoinMethod}
# Account create: $.Account.{AccountId,AccountName,DisplayName,Status,Type}
# Folder list: $.Folders.Folder[].{FolderId,FolderName,ParentFolderId}
# ResourceGroup list: $.ResourceGroups.ResourceGroup[].{Id,Name,DisplayName,Status,AccountId}
# Resource list: $.Resources.Resource[].{ResourceId,ResourceType,ResourceGroupId}
# ControlPolicy list: $.ControlPolicies.ControlPolicy[].{PolicyId,PolicyName,PolicyType}
# TagKeys list: $.Keys.Key[].{Key,Category}
# TagValues list: $.Values[]
# TagResources response: $.FailedResources[].{ResourceARN,Code,Message}
```

## Quick Start

### What This Skill Does
Manages Alibaba Cloud Resource Manager (resource directory, accounts, folders, resource groups, control policies) and Tag (tag keys/values, resource tagging, tag policies, cost allocation governance).

### Prerequisites
- [ ] `aliyun` CLI installed (or Go runtime for JIT fallback)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Enterprise management account with Resource Directory enabled

### Verify Setup
```bash
# Check Resource Manager access
aliyun resourcemanager GetResourceDirectory

# Check Tag access
aliyun tag ListTagKeys
```

### Your First Command
```bash
# List accounts in your resource directory
aliyun resourcemanager ListAccounts

# List resource groups
aliyun resourcemanager ListResourceGroups
```

### Next Steps
- [Core Concepts](references/core-concepts.md) — Understand Resource Directory hierarchy and tag architecture
- [Common Operations](#execution-flows) — Account, folder, resource group, tag management
- [Troubleshooting](references/troubleshooting.md) — Fix common issues

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| Get Resource Directory | Query directory status and master account | Low | None |
| List / Get Accounts | View account details | Low | None |
| Create Resource Account | Create member resource account | Medium | Low |
| Create Cloud Account | Create member cloud account | Medium | Low |
| Remove Cloud Account | Remove cloud account from directory | Medium | **High** — irreversible |
| Move Account | Move account between folders | Low | Low |
| List / Get Folders | View folder hierarchy | Low | None |
| Create / Update / Delete Folder | Folder lifecycle management | Medium | **High** for delete |
| List / Get Resource Groups | View resource groups | Low | None |
| Create / Update / Delete RG | Resource group lifecycle | Medium | **High** for delete |
| Move Resources | Move resources between groups | Medium | Medium |
| List Control Policies | View governance policies | Low | None |
| Attach / Detach Policy | Bind/unbind control policies | Medium | Medium |
| Invite Account | Invite external account to directory | Medium | Low |
| List Tag Keys / Values | Query existing tags | Low | None |
| Create / Delete Tag | Tag lifecycle management | Low | Low |
| Tag / Untag Resources | Batch resource metadata | Medium | Low |
| Tag Policy Management | Governance policy for tags | Medium | Medium |
| Tag Compliance Audit | Detect policy violations | Medium | None |
| Cost Allocation (FinOps) | Tag/RG-based cost attribution | Medium | None |
| Governance Audit | Idle accounts, untagged resources | Low | None |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-30 | Initial skill covering Resource Manager + Tag operations |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI primary + Go SDK fallback) → Validate → Recover**. Do not skip phases.

> **Region note:** Resource Manager APIs are region-independent. Tag management APIs (CreateTags, DeleteTag, ListTagKeys, etc.) are also region-independent. Only `TagResources`, `UntagResources`, `ListTagResources` require `--RegionId`.

---

### Operation 1: Get Resource Directory

**When to use:** Query whether Resource Directory is enabled and get master account info.

**Pre-flight:**

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Credentials | Verify env vars | Non-empty AK/SK | HALT; configure credentials |
| CLI | `aliyun version` | Exit code 0 | Install aliyun CLI |

**Execution — CLI:**
```bash
aliyun resourcemanager GetResourceDirectory
```

**Execution — Go SDK:**
```go
client, _ := resourcemanager.NewClient(&openapi.Config{
    AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
    AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
    Endpoint:        tea.String("resourcemanager.aliyuncs.com"),
})
resp, _ := client.GetResourceDirectory(&resourcemanager.GetResourceDirectoryRequest{})
```

**Validate:** Check `$.ResourceDirectory.Status` = `Enabled`; extract `MasterAccountId`, `RootFolderId`.

---

### Operation 2: List / Get Accounts

**CLI:**
```bash
# List all accounts (JSON output by default)
aliyun resourcemanager ListAccounts

# Get specific account
aliyun resourcemanager GetAccount --AccountId "{{user.account_id}}"
```

**Go SDK:**
```go
// ListAccounts with pagination
req := &resourcemanager.ListAccountsRequest{MaxResults: tea.Int32(100)}
resp, _ := client.ListAccounts(req)

// GetAccount
req2 := &resourcemanager.GetAccountRequest{AccountId: tea.String(accountId)}
resp2, _ := client.GetAccount(req2)
```

**Validate:** For ListAccounts, parse `$.Accounts.Account[]`; for GetAccount, verify `$.Account.Status`.

---

### Operation 3: Create Resource Account

**When to use:** Programmatically create a member account within the resource directory.

**Pre-flight:**

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Directory enabled | GetResourceDirectory | Status=Enabled | HALT; enable directory first |
| Account name unique | Search ListAccounts | Name not found | Ask for unique name |
| Parent folder exists | GetFolder with `{{user.parent_folder_id}}` | Valid folder | HALT; create folder first |

**Execution — CLI:**
```bash
aliyun resourcemanager CreateResourceAccount \
  --DisplayName "{{user.account_name}}" \
  --ParentFolderId "{{user.parent_folder_id}}"
```

**Execution — Go SDK:**
```go
req := &resourcemanager.CreateResourceAccountRequest{
    DisplayName: tea.String(accountName),
}
if parentFolderId != "" {
    req.ParentFolderId = tea.String(parentFolderId)
}
resp, _ := client.CreateResourceAccount(req)
```

**Validate:** Parse `$.Account.AccountId`, poll until `Status` = `CreateSuccess`.

---

### Operation 4: Create Cloud Account

**CLI:**
```bash
aliyun resourcemanager CreateCloudAccount \
  --DisplayName "{{user.account_name}}" \
  --Email "{{user.email}}"
```

**Go SDK:**
```go
req := &resourcemanager.CreateCloudAccountRequest{
    DisplayName: tea.String(accountName),
    Email:       tea.String(email),
})
resp, _ := client.CreateCloudAccount(req)
```

---

### Operation 5: Remove Cloud Account

> **SAFETY GATE — Destructive:** Account removal is irreversible. **MUST** obtain explicit confirmation.

**Pre-flight:** Confirm with user: `Remove cloud account {{user.account_id}} ({{user.account_name}})? This CANNOT be undone.`

**CLI:**
```bash
aliyun resourcemanager RemoveCloudAccount --AccountId "{{user.account_id}}"
```

**Go SDK:**
```go
req := &resourcemanager.RemoveCloudAccountRequest{AccountId: tea.String(accountId)}
resp, _ := client.RemoveCloudAccount(req)
```

**Validate:** ListAccounts to confirm account no longer appears.

---

### Operation 6: Move Account Between Folders

**CLI:**
```bash
aliyun resourcemanager MoveAccount \
  --AccountId "{{user.account_id}}" \
  --DestinationFolderId "{{user.parent_folder_id}}"
```

**Go SDK:**
```go
req := &resourcemanager.MoveAccountRequest{
    AccountId:          tea.String(accountId),
    DestinationFolderId: tea.String(destFolderId),
}
resp, _ := client.MoveAccount(req)
```

---

### Operation 7-9: Folder CRUD

**When to use:** Manage the organizational folder hierarchy.

**List Folders — CLI:**
```bash
# List root folders
aliyun resourcemanager ListFoldersForParent --ParentFolderId "r-xxxx"
```

**Get Folder — CLI:**
```bash
aliyun resourcemanager GetFolder --FolderId "{{user.folder_id}}"
```

**Create Folder — CLI:**
```bash
aliyun resourcemanager CreateFolder \
  --FolderName "{{user.folder_name}}" \
  --ParentFolderId "{{user.parent_folder_id}}"
```

**Delete Folder — CLI:**
> **SAFETY GATE:** Confirm folder is empty (no sub-folders, no accounts). Must obtain user confirmation.

```bash
aliyun resourcemanager DeleteFolder --FolderId "{{user.folder_id}}"
```

---

### Operation 10-12: Resource Group CRUD

**When to use:** Logical grouping of cloud resources for management, billing, and access control.

**List Resource Groups — CLI:**
```bash
aliyun resourcemanager ListResourceGroups
```

**Get Resource Group — CLI:**
```bash
aliyun resourcemanager GetResourceGroup --ResourceGroupId "{{user.resource_group_id}}"
```

**Create Resource Group — CLI:**
```bash
aliyun resourcemanager CreateResourceGroup \
  --DisplayName "{{user.resource_group_name}}" \
  --Name "{{user.resource_group_name}}"
```

**Go SDK:**
```go
req := &resourcemanager.CreateResourceGroupRequest{
    DisplayName: tea.String(displayName),
    Name:        tea.String(name),
}
resp, _ := client.CreateResourceGroup(req)
```

**Delete Resource Group — CLI:**
> **SAFETY GATE:** Confirm resource group is empty. Must obtain user confirmation.

```bash
aliyun resourcemanager DeleteResourceGroup --ResourceGroupId "{{user.resource_group_id}}"
```

---

### Operation 13: Move Resources Between Resource Groups

**When to use:** Reorganize resources across resource groups for cost attribution or access control changes.

**Pre-flight:** ListResources to verify resource exists; validate target RG exists.

**CLI:**
```bash
aliyun resourcemanager MoveResources \
  --ResourceGroupId "{{user.target_resource_group_id}}" \
  --Resources.1.ResourceId "{{user.resource_id}}" \
  --Resources.1.ResourceType "{{user.resource_type}}"
```

**Go SDK:**
```go
req := &resourcemanager.MoveResourcesRequest{
    ResourceGroupId: tea.String(targetRGId),
    Resources: []*resourcemanager.MoveResourcesRequestResources{
        {ResourceId: tea.String(resourceId), ResourceType: tea.String(resourceType)},
    },
}
resp, _ := client.MoveResources(req)
```

**Validate:** Check response for `$.Resources[].Status` = `OK`. Failed resources have per-resource error codes.

---

### Operation 14-15: Control Policies

**When to use:** Enforce governance via Service Control Policies (SCP) on folders or accounts.

**List Control Policies — CLI:**
```bash
aliyun resourcemanager ListControlPolicies --PolicyType "System"
```

**Attach Control Policy — CLI:**
```bash
aliyun resourcemanager AttachControlPolicy \
  --PolicyId "{{user.policy_id}}" \
  --TargetId "{{user.folder_id}}"
```

**Detach Control Policy — CLI:**
```bash
aliyun resourcemanager DetachControlPolicy \
  --PolicyId "{{user.policy_id}}" \
  --TargetId "{{user.folder_id}}"
```

---

### Operation 16-17: Account Invitation & Handshake

**When to use:** Invite an external Alibaba Cloud account to join your resource directory.

**Invite Account — CLI:**
```bash
aliyun resourcemanager InviteAccountToResourceDirectory \
  --TargetEntity "{{user.target_account_id}}" \
  --TargetType "Account" \
  --Note "Invitation from {{output.master_account_name}}"
```

**Get Handshake — CLI:**
```bash
aliyun resourcemanager GetHandshake --HandshakeId "{{output.handshake_id}}"
```

**Accept Handshake — CLI:**
```bash
aliyun resourcemanager AcceptHandshake --HandshakeId "{{output.handshake_id}}"
```

**Validate:** Handshake expires in 7 days. Check `$.Handshake.Status` = `Accepted`.

---

### Operation 18: List Ancestors

**When to use:** Traverse the folder path for a resource or account.

**CLI:**
```bash
aliyun resourcemanager ListAncestors --ChildId "{{user.account_id}}"
```

---

### Operation 19-20: Tag Key/Value Management

**When to use:** Create predefined tag keys and values for governance and cost allocation.

**List Tag Keys — CLI:**
```bash
aliyun tag ListTagKeys
```

**List Tag Values — CLI:**
```bash
aliyun tag ListTagValues --Key "{{user.tag_key}}"
```

**Create Tags — CLI:**
```bash
aliyun tag CreateTags --TagKeyValueParamList='[
  {"Key":"{{user.tag_key}}","Value":"{{user.tag_value}}"}
]'
```

**Delete Tag — CLI:**
```bash
aliyun tag DeleteTag --Key "{{user.tag_key}}" --Value "{{user.tag_value}}"
```

---

### Operation 21-22: Resource Tagging Operations

**When to use:** Add, remove, or query tags on cloud resources.

**Tag Resources — CLI:**
```bash
aliyun tag TagResources \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ResourceARN '["acs:ecs:cn-hangzhou:{{output.account_id}}:instance/i-xxxx"]' \
  --Tags '{"env":"production","project":"app1"}'
```

**Untag Resources — CLI:**
```bash
aliyun tag UntagResources \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ResourceARN '["acs:ecs:cn-hangzhou:{{output.account_id}}:instance/i-xxxx"]' \
  --TagKey '["env"]'
```

**Go SDK:**
```go
req := &tag.TagResourcesRequest{
    RegionId:    tea.String(region),
    ResourceARN: tea.StringSlice([]string{resourceARN}),
    Tags:        tea.String(`{"env":"production"}`),
}
resp, _ := client.TagResources(req)
// Check FailedResources for partial failures
```

**Validate:** For TagResources, check `$.FailedResources` array — if non-empty, each entry has `ResourceARN`, `Code`, `Message`.

---

### Operation 23: List Tag Resources

**When to use:** Query resources by tag filters — key for cost allocation auditing.

**CLI:**
```bash
aliyun tag ListTagResources \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --TagFilter.Key "env" \
  --TagFilter.Value "production"
```

---

### Operation 24-25: Tag Policy Management

**When to use:** Define and enforce tag compliance rules across accounts.

**List Tag Policies — CLI:**
```bash
aliyun tag ListTagPolicies
```

**Create Tag Policy — CLI:**
```bash
aliyun tag CreatePolicy \
  --PolicyName "require-env-tag" \
  --PolicyDesc "Require env tag on all resources" \
  --PolicyContent '{"tags":{"env":{"tag_key":"@string","tag_value":["production","staging","development"]}}}'
```

**Attach Config Rule to Policy — CLI:**
```bash
aliyun tag AttachConfigRuleToPolicy \
  --TargetId "{{user.account_id}}" \
  --TargetType "USER" \
  --PolicyId "{{user.policy_id}}"
```

---

### Operation 26: Tag-Based Cost Allocation (FinOps)

**When to use:** Set up cost allocation tags for accurate billing split by business unit, project, or environment.

**Flow:**
1. **Enable cost allocation tags** — Use billing console or API to activate tag key for cost splitting.
2. **Audit tag coverage** — Use `ListTagResources` to find untagged resources.
3. **Remediate** — Apply missing tags via `TagResources`.

**CLI — Find untagged resources across accounts:**
```bash
# Per resource type, list resources and check tag presence
# Use product-specific APIs (ECS DescribeInstances, RDS DescribeDBInstances, etc.)
# then cross-reference with tag data from ListTagResources
```

See [references/tag-governance.md](references/tag-governance.md) for the complete cost allocation workflow.

---

### Operation 27: Resource Group-Based Cost Attribution (FinOps)

**When to use:** Use resource groups to attribute costs to business units without requiring tags.

**Flow:**
1. **Design resource group hierarchy** — Map to cost centers (e.g., `rg-bu-marketing`, `rg-bu-engineering`)
2. **List resources by group** — `aliyun resourcemanager ListResources --ResourceGroupId "{{user.resource_group_id}}"`
3. **Cross-reference with billing** — Use `alicloud-billing-ops` to query costs per resource group.

---

### Operation 28: Governance — Idle Account Detection

**When to use:** Periodically audit for unused or abandoned member accounts.

**CLI:**
```bash
# List all accounts and check Status field
aliyun resourcemanager ListAccounts

# Filter for accounts with no recent activity (manual review needed)
# Status values: CreateSuccess, PromoteCheckFailed, etc.
```

See [references/tag-governance.md](references/tag-governance.md) for the complete governance audit workflow.

---

### Operation 29: Governance — Tag Compliance Audit

**When to use:** Check for resources violating tag policies or missing required tags.

**CLI:**
```bash
# List all tag policies
aliyun tag ListTagPolicies

# Get compliance report per policy
aliyun tag GetPolicyEnableStatus \
  --TargetType "USER" \
  --TargetId "{{user.account_id}}"
```

---

## Failure Recovery (Agent-Readable)

### Error Taxonomy (Resource Manager + Tag — 12+ codes)

| Error Code | API | Agent Action | UX Feedback |
|------------|-----|-------------|-------------|
| `EntityAlreadyExists.ResourceDirectory` | RM | HALT | `[ERROR] Resource Directory already enabled. Master account: {{output.master_account_id}}` |
| `EntityNotExists.ResourceDirectory` | RM | HALT | `[ERROR] Resource Directory not enabled. Enable it first: aliyun resourcemanager EnableResourceDirectory` |
| `InvalidParameter.AccountStatus` | RM | FIX — verify account state | `[ERROR] Account in invalid state for this operation. Check account status.` |
| `LimitExceeded.FolderDepth` | RM | HALT | `[ERROR] Maximum folder depth (5 levels) exceeded. Reorganize hierarchy.` |
| `LimitExceeded.AccountsPerFolder` | RM | HALT | `[ERROR] Maximum accounts per folder reached. Create sub-folder or move accounts.` |
| `InvalidParameter.FolderName` | RM | FIX — rename | `[ERROR] Invalid folder name. Use alphanumeric, hyphen, underscore only.` |
| `InvalidParameter.TagKey` | Tag | FIX — valid key | `[ERROR] Invalid tag key format. Keys: 1-128 chars, alphanumeric + . _ - @` |
| `LimitExceeded.TagsPerResource` | Tag | HALT | `[ERROR] Maximum 20 tags per resource reached. Remove unused tags first.` |
| `LimitExceeded.ResourcePerPage` | Tag | FIX — paginate | `[ERROR] Too many resources in single request. Use pagination with MaxResults.` |
| `EntityAlreadyExists.Folder` | RM | FIX — unique name | `[ERROR] Folder name already exists in parent. Choose a unique name.` |
| `EntityAlreadyExists.ResourceGroup` | RM | FIX — unique name | `[ERROR] Resource group name already exists. Choose a unique name.` |
| `InvalidParameter.PolicyType` | RM | FIX — valid type | `[ERROR] Invalid control policy type. Supported: System, Custom.` |
| `Forbidden.RAM` | Both | HALT | `[ERROR] Insufficient RAM permissions. Required: resourcemanager:* or tag:*` |
| Throttling / 429 | Both | Retry 3x exponential backoff | `⚠️ Rate limit reached. Retrying in {backoff}s...` |
| `InternalError` / 5xx | Both | Retry 3x, then HALT | `[ERROR] Internal server error. Escalate with RequestId: {RequestId}.` |

## Prerequisites

1. **Install `aliyun` CLI:**

   ```bash
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   # Or: brew install aliyun-cli
   ```

2. **Bootstrap Go runtime** (for JIT SDK fallback):

   ```bash
   if ! command -v go &> /dev/null; then
       OS=$(uname -s | tr '[:upper:]' '[:lower:]')
       ARCH=$(uname -m)
       [ "$ARCH" = "x86_64" ] && ARCH="amd64"
       [ "$ARCH" = "aarch64" ] && ARCH="arm64"
       mkdir -p /tmp/go-runtime
       curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
       export PATH="/tmp/go-runtime/go/bin:$PATH"
       export GOPATH="/tmp/go-workspace"
       export GOCACHE="/tmp/go-cache"
       export GOMODCACHE="/tmp/go-modcache"
       export GOPROXY="https://goproxy.cn,direct"
   fi
   go version
   ```

3. **Configure Credentials:**

   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring](references/monitoring.md)
- [Integration](references/integration.md)
- [Well-Architected Assessment](references/well-architected-assessment.md)
- [Tag Governance (FinOps/Audit)](references/tag-governance.md)

## Operational Best Practices

- **Least privilege:** Create dedicated RAM roles for Resource Manager and Tag operations with scoped policies.
- **Folder hierarchy:** Design org structure (max 5 levels) before creating accounts — moving accounts post-creation is safe but disruptive.
- **Tag strategy:** Define tag taxonomy before resource creation. Use tag policies to enforce compliance.
- **Cost allocation:** Enable cost allocation tags in billing console; regularly audit tag coverage.
- **Control policies:** Start with read-only SCPs; gradually introduce restrictive policies.

## Token Efficiency Guidelines (P0 — 强制)

### TE-1: API Query > Static Tables
Use API commands to discover current state rather than hardcoding limits.
### TE-2: No docstrings in code
Inline comments only in Go SDK scripts.
### TE-3: Compact error tables
One-line error entries with Agent Action column — see Failure Recovery section.
### TE-4: Centralized JSON paths
File-top comment block; one per resource type — see API and Response Conventions section.
### TE-5: YAML anchors in example-config.yaml
Use `&base` to eliminate repeated fields.
### TE-6: Eliminate cross-file duplicate flows
SKILL.md has full flows; reference files provide supplementary detail only.
