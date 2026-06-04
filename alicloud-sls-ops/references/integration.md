# Integration — Alibaba Cloud Simple Log Service (SLS)

## Overview

This reference covers cross-skill integration patterns for **Simple Log Service (SLS)**,
showing how to compose SLS with other Alibaba Cloud services.

## Cross-Skill Integration

### SLS + ECS (alicloud-ecs-ops)

**Use case:** Collect logs from ECS instances via Logtail

**Pattern:**
1. Use `alicloud-ecs-ops` to verify ECS instance status
2. Configure Logtail on ECS to collect logs to SLS
3. Use SLS to query and analyze logs

**Example:**
```bash
# 1. Check ECS instance status
aliyun ecs DescribeInstances --RegionId cn-hangzhou --InstanceIds '["i-xxx"]'

# 2. Install Logtail on ECS (via Cloud Assistant)
aliyun ecs RunCommand --RegionId cn-hangzhou --InstanceId "i-xxx" \
  --Type RunShellScript --CommandContent "wget http://logtail-release-cn-hangzhou.oss-cn-hangzhou.aliyuncs.com/linux64/logtail.sh && chmod 755 logtail.sh && ./logtail.sh install cn-hangzhou"

# 3. Create logstore in SLS
aliyun sls POST /logstores --header "x-log-apiversion=0.9.0" \
  --body '{"logstore":"ecs-logs","ttl":30,"shardCount":2}' \
  --project "my-project"
```

### SLS + SLB (alicloud-slb-ops)

**Use case:** Collect SLB access logs to SLS for analysis

**Pattern:**
1. Use `alicloud-slb-ops` to enable SLB access logging
2. Configure SLB to send logs to SLS
3. Use SLS to analyze access patterns

**Example:**
```bash
# 1. Enable SLB access logging (via SLB API)
# Refer to alicloud-slb-ops for detailed steps

# 2. Query SLB access logs in SLS
aliyun sls GET /logstores/slb-access-logs/logs \
  --header "x-log-apiversion=0.9.0" \
  --query "from * | select client_ip, request_uri, status_code limit 100" \
  --project "my-project"
```

### SLS + RDS (alicloud-rds-ops)

**Use case:** Collect RDS slow query logs and error logs

**Pattern:**
1. Use `alicloud-rds-ops` to enable RDS log collection
2. Configure RDS to send logs to SLS
3. Use SLS to analyze database performance

**Example:**
```bash
# 1. Enable RDS slow query log collection (via RDS API)
# Refer to alicloud-rds-ops for detailed steps

# 2. Query RDS slow query logs in SLS
aliyun sls GET /logstores/rds-slow-logs/logs \
  --header "x-log-apiversion=0.9.0" \
  --query "from * | select query_time, lock_time, rows_examined limit 100" \
  --project "my-project"
```

### SLS + Redis (alicloud-redis-ops)

**Use case:** Collect Redis slow logs and access logs

**Pattern:**
1. Use `alicloud-redis-ops` to enable Redis log collection
2. Configure Redis to send logs to SLS
3. Use SLS to analyze Redis performance

**Example:**
```bash
# 1. Enable Redis slow log collection (via Redis API)
# Refer to alicloud-redis-ops for detailed steps

# 2. Query Redis slow logs in SLS
aliyun sls GET /logstores/redis-slow-logs/logs \
  --header "x-log-apiversion=0.9.0" \
  --query "from * | select command, duration, key limit 100" \
  --project "my-project"
```

### SLS + ActionTrail (alicloud-actiontrail-ops)

**Use case:** Query ActionTrail audit logs via SLS

**Pattern:**
1. Use `alicloud-actiontrail-ops` to configure ActionTrail to send logs to SLS
2. Use SLS to query audit logs

**Example:**
```bash
# 1. Configure ActionTrail to send logs to SLS (via ActionTrail API)
# Refer to alicloud-actiontrail-ops for detailed steps

# 2. Query ActionTrail logs in SLS
aliyun sls GET /logstores/actiontrail-logs/logs \
  --header "x-log-apiversion=0.9.0" \
  --query "from * | select event_name, user_name, event_time limit 100" \
  --project "my-project"
```

### SLS + CMS (alicloud-cms-ops)

**Use case:** Monitor SLS metrics and create alerts

**Pattern:**
1. Use `alicloud-cms-ops` to monitor SLS metrics
2. Create CloudMonitor alarms for SLS health
3. Use SLS dashboards for log visualization

**Example:**
```bash
# 1. Query SLS metrics in CloudMonitor
# Refer to alicloud-cms-ops for detailed steps

# 2. Create SLS dashboard for visualization
aliyun sls POST /dashboards --header "x-log-apiversion=0.9.0" \
  --body '{"dashboardName":"sls-monitoring","displayName":"SLS Monitoring","charts":[{"title":"Ingestion Volume","type":"line","logstore":"my-logstore","query":"from * | select count(*) as cnt","xAxis":{"type":"time"},"yAxis":{"type":"value"}}]}' \
  --project "my-project"
```

## Data Flow Patterns

### Pattern 1: Log Collection Pipeline

```
ECS/Containers → Logtail → SLS → Index → Query/Alerts
```

**Components:**
- **Logtail:** Log collection agent (installed on ECS or configured in Kubernetes)
- **SLS:** Log storage and indexing
- **Query/Alerts:** Log analysis and notification

### Pattern 2: Multi-Source Aggregation

```
ECS Logs ─┐
SLB Logs ─┼→ SLS → Unified Query → Dashboard
RDS Logs ─┘
```

**Components:**
- **Multiple sources:** Different log types from various services
- **SLS:** Centralized log storage
- **Dashboard:** Unified visualization

### Pattern 3: Real-Time Processing

```
Logs → SLS → Consumer Group → Real-Time Processing → OSS/MaxCompute
```

**Components:**
- **Consumer Group:** Real-time log consumption
- **Processing:** Stream processing application
- **Archive:** Long-term storage

## Authentication & Permissions

### Cross-Skill RAM Roles

| Integration | Required RAM Permissions |
|-------------|------------------------|
| SLS + ECS | `ecs:RunCommand`, `log:CreateLogStore` |
| SLS + SLB | `slb:ModifyLoadBalancerAttribute`, `log:CreateLogStore` |
| SLS + RDS | `rds:ModifyLogBackupPolicy`, `log:CreateLogStore` |
| SLS + Redis | `rds:ModifyLogBackupPolicy`, `log:CreateLogStore` |
| SLS + ActionTrail | `actiontrail:UpdateTrail`, `log:CreateLogStore` |
| SLS + CMS | `cms:PutMetricData`, `log:CreateDashboard` |

### Example Cross-Skill Policy

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:RunCommand",
        "slb:ModifyLoadBalancerAttribute",
        "rds:ModifyLogBackupPolicy",
        "actiontrail:UpdateTrail",
        "cms:PutMetricData",
        "log:CreateProject",
        "log:GetProject",
        "log:CreateLogStore",
        "log:GetLogStore",
        "log:CreateIndex",
        "log:GetLogs",
        "log:CreateAlert",
        "log:CreateDashboard"
      ],
      "Resource": "*"
    }
  ]
}
```

## Endpoint Reference

### SLS Endpoints

| Region | Endpoint |
|--------|----------|
| cn-hangzhou | `{project}.cn-hangzhou.log.aliyuncs.com` |
| cn-shanghai | `{project}.cn-shanghai.log.aliyuncs.com` |
| cn-beijing | `{project}.cn-beijing.log.aliyuncs.com` |
| cn-shenzhen | `{project}.cn-shenzhen.log.aliyuncs.com` |
| us-west-1 | `{project}.us-west-1.log.aliyuncs.com` |
| ap-southeast-1 | `{project}.ap-southeast-1.log.aliyuncs.com` |

### Related Service Endpoints

| Service | Endpoint Pattern |
|---------|------------------|
| ECS | `ecs.aliyuncs.com` |
| SLB | `slb.aliyuncs.com` |
| RDS | `rds.aliyuncs.com` |
| Redis | `r-kvstore.aliyuncs.com` |
| ActionTrail | `actiontrail.aliyuncs.com` |
| CMS | `metrics.cn-hangzhou.aliyuncs.com` |

## Best Practices

### Integration Patterns

- **Decouple components:** Use independent skills for each service
- **Shared variables:** Use `{{user.project_name}}` across skills
- **Error propagation:** HALT on critical failures, retry on transient errors
- **Validation:** Verify each step before proceeding

### Security

- **Least privilege:** Grant only required permissions per integration
- **Credential rotation:** Use RAM roles for cross-service access
- **Audit logging:** Enable ActionTrail for all SLS operations
- **Network security:** Use VPC endpoints where possible

## Reference Documentation

- [SLS Integration Guide](https://help.aliyun.com/zh/sls/developer-reference/integration-guide)
- [SLS Best Practices](https://help.aliyun.com/zh/sls/developer-reference/best-practices-for-log-service)
- [Alibaba Cloud Integration Patterns](https://help.aliyun.com/product/28979.html)
