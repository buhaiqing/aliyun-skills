# Core Concepts — Resource Manager & Tag

## Resource Manager Architecture

### Resource Directory (资源目录)
A hierarchical multi-account management structure. One enterprise management account (enterprise master) creates a root folder, under which member accounts are organized in a tree of folders (max 5 levels deep).

| Concept | Description |
|---------|-------------|
| Master Account | Enterprise management account that owns the directory |
| Member Account | Accounts within the directory — can be ResourceAccount or CloudAccount |
| Root Folder | Top-level folder, created when directory is enabled |
| Folder | Organizational unit in the hierarchy (max 5 levels, including root) |
| Invitation | Process for bringing external accounts into the directory |

### Account Types

| Type | Description | Billing | Logging In |
|------|-------------|---------|------------|
| **CloudAccount** | Independent Alibaba Cloud account with own login credentials | Independent settlement | Has own login credentials |
| **ResourceAccount** | Programmatically created account within directory | Settled via master account (consolidated billing) | No independent login by default; needs RAM user provisioning |

### Resource Groups (资源组)
Logical containers that group cloud resources across products. Used for:
- **Access Control:** Grant RAM permissions based on resource group membership
- **Billing:** Attribute costs to resource groups for cost center tracking
- **Management:** Organize resources by project, environment, or business unit

### Control Policies (管控策略)
Service Control Policies (SCP) that restrict permissions of member accounts:
- **System Policies:** Built-in policies (e.g., `FullAliyunAccess` deny)
- **Custom Policies:** User-defined JSON policy documents
- **Attachment points:** Can be attached to folders (inherited by sub-folders and accounts) or directly to accounts
- **Inheritance:** Child folders inherit parent policies; account = union of all ancestor policies

### Handshake (握手)
The mechanism for inviting external accounts:
- Initiating account sends invitation with optional note
- Target account receives a handshake (valid for 7 days)
- Target account accepts or rejects the handshake
- On acceptance, target account becomes a member of the resource directory

## Tag Architecture

### Tag Model

| Component | Rules |
|-----------|-------|
| Tag Key | 1-128 chars, supports: letters, digits, spaces, `._:/=+-@` |
| Tag Value | 0-256 chars, same charset as key |
| Max Tags/Resource | 20 |
| Max Tag Keys/Account | 1,000 (increased via quota) |
| Max Tag Values/Key | 100 |

### Tag Types

| Type | Description | Use Case |
|------|-------------|----------|
| **Custom Tags** | User-defined key:value pairs | Resource classification, cost allocation |
| **System Tags** | Alibaba Cloud generated (`acs:createdBy`, `acs:project`) | Auto-classification |
| **Propagated Tags** | Tags inherited from resource group or parent resource | Governance consistency |

### Tag Policies (标签策略)
Enforce tag compliance across multiple accounts:
- Define required tag keys and allowed values
- Validate tag presence during resource creation
- Detect non-compliant resources via compliance reports

### Cost Allocation Tags
Tags that appear in billing reports for cost splitting:
- Must be enabled in Billing Center before they appear in bills
- Only tags with values are eligible for cost allocation
- Retroactive: enabling a tag key shows costs from that point forward, not historical

## Limits & Quotas

### Resource Manager Quotas

| Resource | Default Limit |
|----------|--------------|
| Max folder depth | 5 (including root) |
| Max accounts per directory | 100-200 (varies by account type) |
| Max resource groups per account | 100 |
| Max control policies per account | 50 |
| Handshake validity | 7 days |

### Tag Quotas

| Resource | Default Limit |
|----------|--------------|
| Tags per resource | 20 |
| Tag keys per account | 1,000 |
| Tag values per key | 100 |
| Tag policies per account | 10 |

## Endpoints

Both products use **region-independent** endpoints:

| Product | Endpoint | Protocol |
|---------|----------|----------|
| Resource Manager | `resourcemanager.aliyuncs.com` | HTTPS |
| Tag | `tag.aliyuncs.com` | HTTPS |

> **Exception:** `TagResources`, `UntagResources`, `ListTagResources` require `RegionId` parameter (regional resource operations), but the API endpoint remains `tag.aliyuncs.com`.

## Dependency Graph

```
Resource Directory (prerequisite)
├── Folders (organized under root)
│   ├── Accounts (members of folders)
│   │   └── Resource Groups (cross-cutting, account-level)
│   │       └── Resources (ECS, RDS, OSS, etc.)
│   │           └── Tags (metadata on resources)
│   └── Control Policies (attached to folders or accounts)
├── Handshakes (for external account invitations)
└── Tag Policies (cross-account tag governance)
```
