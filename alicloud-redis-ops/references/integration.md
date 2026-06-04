# Integration — Alibaba Cloud Redis / Tair (KVStore)

## Enhanced Self-Healing Framework (MANDATORY)

All installation flows MUST follow the **Enhanced Self-Healing Framework** defined in [alicloud-skill-generator/references/enhanced-self-healing-framework.md](../../alicloud-skill-generator/references/enhanced-self-healing-framework.md).

**Key Self-Healing Capabilities:**
- **Pre-flight Checks:** Network connectivity, disk space, permissions, system compatibility
- **Intelligent Error Classification:** Network, permission, resource, configuration errors
- **Multi-Path Self-Healing:** Multiple recovery strategies per error type
- **Health Verification:** Post-installation validation with health score ≥ 8/10
- **Graceful Degradation:** Clear fallback paths when self-healing fails

### Go Runtime Bootstrap (Enhanced Self-Healing)

The Agent MUST use enhanced self-healing for Go runtime JIT download:

**Multi-Version & Multi-Mirror Strategy:**
- **Primary:** Go 1.24+ (latest stable)
- **Fallback:** Go 1.23 → 1.22 → 1.21 (minimum compatibility)
- **Mirrors:** Official + China CDN mirrors (4 mirrors)

**Self-Healing Capabilities:**

| Error Type | Self-Healing Actions | Max Attempts |
|------------|---------------------|--------------|
| Download timeout | Mirror switch, timeout increase, version fallback | 4 versions × 4 mirrors |
| Download incomplete | File size check (>100MB), re-download, cache clear | 3 |
| Extract failure | Integrity check, re-download, clean workspace | 2 |
| Version incompatible | Fallback to compatible version (go1.21+) | 4 versions |
| PATH setup fail | Use absolute path, verify binary exists | 1 |

**Health Check:**
- Go binary exists and executable
- Version ≥ go1.21
- Workspace initialized
- Dependencies cached

For detailed implementation, see [alicloud-skill-generator/references/enhanced-self-healing-framework.md](../../alicloud-skill-generator/references/enhanced-self-healing-framework.md) Section 3.2.

## VPC Integration

### Prerequisites

Before creating a Redis/Tair instance in a VPC:

1. **VPC must exist** in target region
2. **VSwitch must exist** in target zone within the VPC
3. **Security groups** (if used) must allow Redis port access

### Verification Flow

```bash
# Verify VPC exists
aliyun vpc describe-vpcs --RegionId "{{user.region}}" --VpcId "{{user.vpc_id}}"

# Verify VSwitch exists
aliyun vpc describe-v-switches --RegionId "{{user.region}}" --VSwitchId "{{user.vswitch_id}}"
```

### Network Architecture

```
┌─────────────────────────────────────────┐
│              VPC                        │
│  ┌─────────────────────────────────┐    │
│  │         VSwitch (Zone A)        │    │
│  │  ┌─────────────────────────┐    │    │
│  │  │   Redis/Tair Instance   │    │    │
│  │  │   (Private IP)          │    │    │
│  │  └─────────────────────────┘    │    │
│  │           ▲                     │    │
│  │           │                     │    │
│  │  ┌────────┴────────┐            │    │
│  │  │  ECS / Container │            │    │
│  │  │  (Application)   │            │    │
│  │  └─────────────────┘            │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

## RAM Integration

### Least Privilege Policy

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "r-kvstore:DescribeInstances",
        "r-kvstore:DescribeInstanceAttribute",
        "r-kvstore:DescribeAccounts",
        "r-kvstore:DescribeBackups",
        "r-kvstore:DescribeSecurityIps",
        "r-kvstore:DescribeParameters",
        "r-kvstore:DescribeSlowLogs",
        "r-kvstore:DescribeHistoryMonitorValues",
        "r-kvstore:DescribeMonitorItems",
        "r-kvstore:DescribeRegions",
        "r-kvstore:DescribeZones",
        "r-kvstore:DescribeAvailableResource",
        "r-kvstore:DescribeEngineVersion",
        "r-kvstore:DescribeIntranetAttribute"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "r-kvstore:CreateInstance",
        "r-kvstore:RestartInstance",
        "r-kvstore:DeleteInstance",
        "r-kvstore:ModifyInstanceSpec",
        "r-kvstore:CreateAccount",
        "r-kvstore:DeleteAccount",
        "r-kvstore:ResetAccountPassword",
        "r-kvstore:CreateBackup",
        "r-kvstore:RestoreInstance",
        "r-kvstore:ModifySecurityIps",
        "r-kvstore:ModifyParameter",
        "r-kvstore:ModifyInstanceMaintainTime",
        "r-kvstore:ModifyInstanceSSL",
        "r-kvstore:ModifyIntranetBandwidth",
        "r-kvstore:MigrateToOtherZone",
        "r-kvstore:UpgradeMinorVersion",
        "r-kvstore:FlushInstance"
      ],
      "Resource": "acs:r-kvstore:*:*:instance/*",
      "Condition": {
        "StringEquals": {
          "r-kvstore:InstanceName": "{{user.allowed_prefix}}*"
        }
      }
    }
  ]
}
```

### Read-Only Policy

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "r-kvstore:Describe*"
      ],
      "Resource": "*"
    }
  ]
}
```

## CI/CD Integration

### Terraform Integration

```hcl
resource "alicloud_kvstore_instance" "example" {
  instance_name  = "my-redis-instance"
  instance_class = "redis.master.small.default"
  engine_version = "5.0"
  region_id      = "cn-hangzhou"
  zone_id        = "cn-hangzhou-h"
  vswitch_id     = alicloud_vswitch.example.id
  security_ips   = ["10.0.0.0/8"]
  
  config {
    maxmemory_policy = "volatile-lru"
    slowlog_log_slower_than = "10000"
  }
}
```

### Pulumi Integration

```typescript
import * as alicloud from "@pulumi/alicloud";

const redis = new alicloud.kvstore.Instance("example", {
    instanceName: "my-redis-instance",
    instanceClass: "redis.master.small.default",
    engineVersion: "5.0",
    regionId: "cn-hangzhou",
    zoneId: "cn-hangzhou-h",
    vswitchId: vswitch.id,
    securityIps: ["10.0.0.0/8"],
});
```

### Ansible Integration

```yaml
- name: Create Redis instance
  ali_rds_instance:
    region: cn-hangzhou
    zone: cn-hangzhou-h
    instance_name: my-redis-instance
    instance_class: redis.master.small.default
    engine_version: "5.0"
    vswitch_id: "{{ vswitch_id }}"
    security_ips: "10.0.0.0/8"
```

## Application Integration

### Connection String Patterns

| Architecture | Connection Pattern | Example |
|--------------|-------------------|---------|
| Standard | Single endpoint | `r-bp1zxszhcgatnx****.redis.rds.aliyuncs.com:6379` |
| Cluster | Cluster-aware client | Same endpoint, client handles redirection |
| Read/Write Splitting | Multiple endpoints | Master + read replica endpoints |

### Client Configuration Best Practices

```python
# Python (redis-py) example
import redis

# Standard instance
r = redis.Redis(
    host='r-bp1zxszhcgatnx****.redis.rds.aliyuncs.com',
    port=6379,
    password='your-password',
    db=0,
    socket_timeout=5,
    socket_connect_timeout=5,
    health_check_interval=30,
    max_connections=50
)

# Cluster instance
from rediscluster import RedisCluster

startup_nodes = [
    {"host": "r-bp1zxszhcgatnx****.redis.rds.aliyuncs.com", "port": "6379"}
]
rc = RedisCluster(
    startup_nodes=startup_nodes,
    password='your-password',
    skip_full_coverage_check=True,
    max_connections_per_node=50
)
```

```java
// Java (Jedis) example
JedisPoolConfig poolConfig = new JedisPoolConfig();
poolConfig.setMaxTotal(50);
poolConfig.setMaxIdle(10);
poolConfig.setMinIdle(5);

JedisPool jedisPool = new JedisPool(
    poolConfig,
    "r-bp1zxszhcgatnx****.redis.rds.aliyuncs.com",
    6379,
    5000,  // timeout
    "your-password"
);
```

## Multi-Region Integration

### Cross-Region Replication (Tair Enterprise)

Tair Enterprise supports global multi-active replication:

```bash
# Check if instance supports global multi-active
aliyun r-kvstore describe-instance-attribute --InstanceId "{{user.instance_id}}"

# Configure cross-region replication via console or advanced APIs
```

### Disaster Recovery Pattern

```
Region A (Primary)          Region B (DR)
┌─────────────┐            ┌─────────────┐
│  Tair Instance │◄────────►│  Tair Instance │
│  (Read/Write)  │  Sync    │  (Read/Write)  │
└─────────────┘            └─────────────┘
       ▲                          ▲
       │                          │
       └──────────┬───────────────┘
                  │
            ┌─────┴─────┐
            │  Application │
            │  (Multi-Active)│
            └───────────┘
```

## Backup Integration

### OSS Backup Storage

Automated backups can be stored in OSS for long-term retention:

1. Enable cross-region backup in console
2. Configure OSS bucket for backup storage
3. Set retention policy

### Restore to New Instance

```bash
# Create new instance from backup
aliyun r-kvstore create-instance \
  --RegionId "{{user.region}}" \
  --InstanceName "{{user.new_instance_name}}" \
  --InstanceClass "{{user.instance_class}}" \
  --EngineVersion "{{user.engine_version}}" \
  --ZoneId "{{user.zone_id}}" \
  --NetworkType "VPC" \
  --VPCId "{{user.vpc_id}}" \
  --VSwitchId "{{user.vswitch_id}}"

# After creation, restore from backup
aliyun r-kvstore restore-instance \
  --InstanceId "{{output.new_instance_id}}" \
  --BackupId "{{user.backup_id}}"
```

## Monitoring Integration

### Prometheus Integration

Use CloudMonitor exporter or custom exporter to scrape metrics:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'alicloud-redis'
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: /metrics
    params:
      instance_id: ['r-bp1zxszhcgatnx****']
```

### Grafana Dashboard

Import CloudMonitor data source and create dashboards for:

- Instance status overview
- Resource utilization (CPU, memory, connections)
- Throughput and latency
- Cache hit rate
- Replication lag
- Slow query analysis

## CloudMonitor (CMS) Integration

### Metric Query

Redis/Tair metrics are available via CloudMonitor under the `acs_kvstore_dashboard` namespace.
Delegate to `alicloud-cms-ops` for metric queries and alarm management.

```bash
# Query Redis CPU usage (delegate to alicloud-cms-ops)
aliyun cms DescribeMetricList \
  --Namespace acs_kvstore_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Query Redis memory usage
aliyun cms DescribeMetricList \
  --Namespace acs_kvstore_dashboard \
  --MetricName MemoryUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Query Redis connection usage
aliyun cms DescribeMetricList \
  --Namespace acs_kvstore_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60
```

### Alarm Rule Management

Create monitoring alarms for Redis/Tair instances via CMS:

```bash
# Create CPU usage alarm
aliyun cms PutMetricAlarm \
  --AlarmName "redis-{{user.instance_id}}-cpu-high" \
  --Namespace acs_kvstore_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Statistics Average \
  --ComparisonOperator ">=" \
  --Threshold 80 \
  --Period 300 \
  --EvaluationCount 3 \
  --ContactGroups '["{{user.contact_group}}"]'
```

### Alarm-to-Diagnosis Delegation

When CMS alarms fire for Redis/Tair, the following delegation protocol applies:

| Alarm Metric | Primary Diagnosis Skill | Secondary Diagnosis Skill |
|-------------|------------------------|--------------------------|
| CpuUsage | `alicloud-redis-ops` | `alicloud-das-ops` (cache analysis) |
| MemoryUsage | `alicloud-redis-ops` | `alicloud-das-ops` (cache analysis) |
| ConnectionUsage | `alicloud-redis-ops` | `alicloud-das-ops` |
| IntranetInRatio / IntranetOutRatio | `alicloud-redis-ops` | `alicloud-vpc-ops` |

### Delegation Protocol

```
[CMS Alarm Fires (acs_kvstore_dashboard)]
    │
    ├── 1. Identify metric from alarm rule
    ├── 2. Invoke alicloud-redis-ops to check instance status
    ├── 3. If resource abnormal → check config, slow logs, connections
    ├── 4. If cache analysis needed → invoke alicloud-das-ops
    └── 5. Compile unified diagnosis report
```

## Security Integration

### SSL/TLS Configuration

```bash
# Enable SSL
aliyun r-kvstore modify-instance-ssl \
  --InstanceId "{{user.instance_id}}" \
  --SSLEnabled "Enable"

# Client connection with SSL
# redis-cli --tls -h r-bp1zxszhcgatnx****.redis.rds.aliyuncs.com -p 6379 -a your-password
```

### PrivateLink Integration

For secure cross-VPC access:

```bash
# Create VPC endpoint (via VPC console or API)
aliyun vpc create-vpc-endpoint \
  --RegionId "{{user.region}}" \
  --VpcId "{{user.vpc_id}}" \
  --ServiceName "com.aliyuncs.r-kvstore"
```

## Event-Driven Integration

### EventBridge Integration

Alibaba Cloud EventBridge can capture Redis/Tair events:

| Event Type | Description | Action |
|------------|-------------|--------|
| Instance Created | New instance provisioned | Notify team, update CMDB |
| Instance Deleted | Instance released | Cleanup resources, update CMDB |
| Backup Completed | Backup finished | Verify backup, notify team |
| Backup Failed | Backup failed | Alert on-call, retry |
| Instance Status Changed | Status transition | Alert if abnormal |
| Parameter Modified | Config changed | Audit log, notify team |

### Function Compute Integration

```python
# Function Compute handler for Redis events
import json
import logging

def handler(event, context):
    evt = json.loads(event)
    
    if evt['eventName'] == 'Instance:InstanceStatusChanged':
        instance_id = evt['content']['InstanceId']
        new_status = evt['content']['InstanceStatus']
        
        if new_status != 'Normal':
            # Send alert
            logging.warning(f"Instance {instance_id} status changed to {new_status}")
            # Trigger notification (DingTalk, SMS, etc.)
    
    return 'success'
```
