# Core Concepts — Alibaba Cloud DAS

## What is DAS?

数据库自治服务 (DAS) is an Alibaba Cloud service for managing cloud resources.

## Key Concepts

- **Instance**: Primary resource type
- **Alarm**: Primary resource type
- **SlowLog**: Primary resource type

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

- **Public Endpoint**: das.aliyuncs.com
- **VPC Endpoint**: das-vpc.aliyuncs.com (if available)
