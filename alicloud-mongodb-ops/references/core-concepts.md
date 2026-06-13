# Core Concepts — Alibaba Cloud MongoDB

## What is MongoDB?

云数据库 MongoDB (MongoDB) is an Alibaba Cloud service for managing cloud resources.

## Key Concepts

- **DBInstance**: Primary resource type
- **Account**: Primary resource type
- **Backup**: Primary resource type

## Resource Lifecycle

### Status Flow
- **Creating**: Resource is being provisioned
- **Running/Available**: Resource is operational
- **Modifying**: Resource configuration is being changed
- **Deleting**: Resource is being removed
- **Deleted**: Resource has been removed

## Dependencies

- **Region**: Resources are region-specific
- **VPC**: Most resources require VPC network
- **RAM**: Access control via RAM policies

## Limits and Quotas

| Limit | Default | Adjustable |
|-------|---------|------------|
| Resources per region | Varies by product | Yes |
| API rate limit | 100-1000 QPS | Contact support |
| Resource tags | 20 per resource | No |

## Service Endpoints

- **Public Endpoint**: dds.aliyuncs.com
- **VPC Endpoint**: dds-vpc.aliyuncs.com (if available)
