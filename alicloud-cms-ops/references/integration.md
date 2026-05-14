# Integration Guide for alicloud-cms-ops

## Enhanced Self-Healing Framework (MANDATORY)

All installation flows MUST follow the **Enhanced Self-Healing Framework** defined in [alicloud-skill-generator/references/enhanced-self-healing-framework.md](../alicloud-skill-generator/references/enhanced-self-healing-framework.md).

**Key Self-Healing Capabilities:**
- **Pre-flight Checks:** Network connectivity, disk space, permissions, system compatibility
- **Intelligent Error Classification:** Network, permission, resource, configuration errors
- **Multi-Path Self-Healing:** Multiple recovery strategies per error type
- **Health Verification:** Post-installation validation with health score ≥ 8/10
- **Graceful Degradation:** Clear fallback paths when self-healing fails

For detailed implementation, see [alicloud-skill-generator/references/enhanced-self-healing-framework.md](../alicloud-skill-generator/references/enhanced-self-healing-framework.md).

## API/SDK Profile

| Attribute | Value |
|-----------|-------|
| Product | CloudMonitor (CMS, 云监控) |
| API Version (Primary) | Cms/2019-01-01 |
| API Style | RPC |
| API Version (Advanced) | Cms/2024-03-30 |
| API Style (Advanced) | ROA |
| Endpoint | metrics.aliyuncs.com |
| SDK Package (Primary) | github.com/alibabacloud-go/cms-20190101/v7 |
| SDK Package (Advanced) | github.com/alibabacloud-go/cms-2024-03-30/v2 |
| CLI Product Slug | cms |

## Cross-Product Dependencies

### Resource Verification Delegation

Before creating alarm rules, verify the target resource exists using its
product-specific skill:

| Monitored Resource | Verification Skill | Key API |
|-------------------|-------------------|---------|
| ECS Instance | alicloud-ecs-ops | DescribeInstances |
| RDS Instance | alicloud-rds-ops | DescribeDBInstances |
| SLB Instance | alicloud-slb-ops | DescribeLoadBalancers |
| OSS Bucket | alicloud-oss-ops | GetBucketInfo |
| Redis Instance | alicloud-redis-ops | DescribeInstances |
| MongoDB Instance | alicloud-mongodb-ops | DescribeDBInstances |
| PolarDB Cluster | alicloud-polardb-ops | DescribeDBClusters |
| Kubernetes | alicloud-ack-ops | DescribeClusters |

### Notification Dependencies

| Notification Channel | Dependency | Setup Skill |
|---------------------|-----------|-------------|
| MNS Topic | alicloud-mns-ops | CreateTopic |
| SMS | alicloud-sms-ops | SendSms |
| Email | Built-in CMS | Configure in console |
| DingTalk Robot | Built-in CMS | Configure in console |

## Environment Setup

### Required Environment Variables

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
```

### Optional Environment Variables

```bash
export ALIBABA_CLOUD_ENDPOINT="metrics.aliyuncs.com"  # Custom endpoint
export ALIBABA_CLOUD_READ_TIMEOUT=30                    # Read timeout (seconds)
export ALIBABA_CLOUD_CONNECT_TIMEOUT=10                 # Connect timeout (seconds)
```

### RAM Policy Templates

#### Read-Only Policy

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cms:DescribeMetricList",
        "cms:DescribeMetricLast",
        "cms:DescribeMetricData",
        "cms:DescribeMetricTop",
        "cms:DescribeMetricMetaList",
        "cms:DescribeProjectMeta",
        "cms:DescribeMetricAlarmList",
        "cms:DescribeMonitorGroups",
        "cms:DescribeMonitorGroupInstances",
        "cms:DescribeContactGroupList",
        "cms:DescribeContactList"
      ],
      "Resource": "*"
    }
  ]
}
```

#### Full Access Policy

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "cms:*",
      "Resource": "*"
    }
  ]
}
```

## Metric Namespace Reference

### Common Namespaces

| Product | Namespace | Documentation |
|---------|-----------|---------------|
| ECS | acs_ecs_dashboard | [ECS Metrics](https://help.aliyun.com/document_detail/163515.html) |
| RDS | acs_rds_dashboard | [RDS Metrics](https://help.aliyun.com/document_detail/26316.html) |
| SLB | acs_slb_dashboard | [SLB Metrics](https://help.aliyun.com/document_detail/27591.html) |
| OSS | acs_oss_dashboard | [OSS Metrics](https://help.aliyun.com/document_detail/31900.html) |
| Redis | acs_kvstore_dashboard | [Redis Metrics](https://help.aliyun.com/document_detail/43887.html) |
| MongoDB | acs_mongodb_dashboard | [MongoDB Metrics](https://help.aliyun.com/document_detail/61147.html) |
| PolarDB | acs_polardb_dashboard | [PolarDB Metrics](https://help.aliyun.com/document_detail/131472.html) |
| Kubernetes | acs_k8s_dashboard | [K8s Metrics](https://help.aliyun.com/document_detail/148667.html) |
| Function Compute | acs_fc_dashboard | [FC Metrics](https://help.aliyun.com/document_detail/73399.html) |
| SLS | acs_sls_dashboard | [SLS Metrics](https://help.aliyun.com/document_detail/93739.html) |

### Custom Namespace

For custom metrics, use: `acs_custom` or your own namespace.

## Data Retention

| Period | Retention | Use Case |
|--------|-----------|----------|
| < 60s | 7 days | Real-time monitoring |
| 60s | 31 days | Standard monitoring |
| ≥ 300s | 91 days | Long-term trending |

## Integration Patterns

### Pattern 1: Metric Collection Pipeline

```
[Cloud Resources] → [CMS] → [DescribeMetricList] → [Time-Series DB] → [Grafana]
```

Use this skill for the CMS API calls; use `alicloud-ecs-ops` etc. for resource
management.

### Pattern 2: Alarm-Driven Automation

```
[CMS Alarm] → [MNS Topic] → [Function Compute] → [Auto-Remediation]
```

Use this skill to configure alarms; use `alicloud-fc-ops` for Function Compute
automation.

### Pattern 3: Multi-Cloud Monitoring

```
[Alibaba Cloud CMS] → [DescribeMetricList] → [Data Export] → [Prometheus/Grafana]
```

Use this skill for data extraction; standard Prometheus/Grafana for
visualization.

---

## Alarm-to-Diagnosis Delegation Matrix

> This matrix defines the **cross-skill delegation protocol** when CMS alarms fire. The agent MUST follow this matrix to route diagnosis to the correct product skill and DAS.

### Delegation Matrix by Namespace & Metric

| Alarm Namespace | Alarm Metric | Primary Diagnosis Skill | Secondary Diagnosis Skill | DAS Delegation |
|----------------|--------------|------------------------|--------------------------|----------------|
| `acs_ecs_dashboard` | CPUUtilization | `alicloud-ecs-ops` | `alicloud-vpc-ops` (network) | Optional |
| `acs_ecs_dashboard` | MemoryUsage | `alicloud-ecs-ops` | — | Optional |
| `acs_ecs_dashboard` | DiskUsage | `alicloud-ecs-ops` | — | Optional |
| `acs_ecs_dashboard` | LoadAverage | `alicloud-ecs-ops` | — | Optional |
| `acs_ecs_dashboard` | InternetInRate / InternetOutRate | `alicloud-ecs-ops` | `alicloud-vpc-ops` | Optional |
| `acs_rds_dashboard` | ConnectionUsage | `alicloud-rds-ops` | `alicloud-das-ops` | **Recommended** |
| `acs_rds_dashboard` | CpuUsage | `alicloud-rds-ops` | `alicloud-das-ops` | **Recommended** |
| `acs_rds_dashboard` | IOPSUsage | `alicloud-rds-ops` | `alicloud-das-ops` | **Recommended** |
| `acs_rds_dashboard` | MemoryUsage | `alicloud-rds-ops` | `alicloud-das-ops` | **Recommended** |
| `acs_slb_dashboard` | DropConnection | `alicloud-slb-ops` | `alicloud-ecs-ops` (backend) | Optional |
| `acs_slb_dashboard` | DropPacketRX / DropPacketTX | `alicloud-slb-ops` | `alicloud-ecs-ops` | Optional |
| `acs_slb_dashboard` | InstanceActiveConnection | `alicloud-slb-ops` | `alicloud-ecs-ops` | Optional |
| `acs_kvstore_dashboard` | ConnectionUsage | `alicloud-redis-ops` | — | Optional |
| `acs_kvstore_dashboard` | CpuUsage | `alicloud-redis-ops` | — | Optional |
| `acs_kvstore_dashboard` | MemoryUsage | `alicloud-redis-ops` | — | Optional |
| `acs_polardb_dashboard` | CpuUsage | `alicloud-polardb-ops` | `alicloud-das-ops` | **Recommended** |
| `acs_polardb_dashboard` | ConnectionUsage | `alicloud-polardb-ops` | `alicloud-das-ops` | **Recommended** |
| `acs_polardb_dashboard` | IOPSUsage | `alicloud-polardb-ops` | `alicloud-das-ops` | **Recommended** |
| `acs_mongodb_dashboard` | CpuUsage | `alicloud-mongodb-ops` | `alicloud-das-ops` | Optional |
| `acs_k8s_dashboard` | * | `alicloud-ack-ops` | `alicloud-ecs-ops` (node) | Optional |
| `acs_oss_dashboard` | * | `alicloud-oss-ops` | — | Optional |
| `acs_fc_dashboard` | * | `alicloud-fc-ops` | — | Optional |

### Delegation Protocol

```
[Alarm Fires]
    │
    ├── 1. Identify namespace + metric from alarm rule
    ├── 2. Look up Primary Skill in matrix
    ├── 3. Invoke Primary Skill to check resource status
    ├── 4. If resource abnormal → Invoke Secondary Skill (if defined)
    ├── 5. If DAS = "Recommended" → Always invoke alicloud-das-ops
    ├── 6. If DAS = "Optional" and severity = Critical → Invoke alicloud-das-ops
    └── 7. Compile unified report from all skill outputs
```

### DAS Delegation Triggers

| Trigger Condition | DAS Operations to Invoke |
|------------------|-------------------------|
| Database alarm (RDS/PolarDB) | `GetInstanceInspections`, `CreateDiagnosticReport` |
| Connection-related alarm | `CreateLatestDeadLockAnalysis`, `GetQueryOptimizeData` |
| Performance degradation | `CreateDiagnosticReport`, `GetPfsSqlSamples` |
| Cache/Redis alarm | `CreateCacheAnalysisJob` |
| Autonomous event suspected | `GetAutonomousNotifyEventsInRange` |

### Diagnosis Result Correlation

When multiple skills are invoked, correlate their findings:

1. **Time Correlation**: Check if anomalies occurred within the same time window (±5 minutes)
2. **Resource Correlation**: Check if resources have dependency relationships
   - SLB backend → ECS instance
   - RDS read replica → RDS primary
   - K8s pod → K8s node (ECS)
3. **Metric Correlation**: Check if multiple metrics for the same resource spiked together
4. **Causation Analysis**: If Resource A failed at T1 and Resource B failed at T2>T1, investigate if A caused B

### Correlation Example

```
Timeline:
  T1: ECS i-001 CPUUtilization spikes (acs_ecs_dashboard)
  T2: SLB lb-001 DropConnection increases (acs_slb_dashboard)
  T3: RDS rm-001 ConnectionUsage increases (acs_rds_dashboard)

Correlation:
  - i-001 is backend of lb-001 → lb-001 DropConnection likely caused by i-001 CPU
  - rm-001 is database for app on i-001 → ConnectionUsage increase due to slow queries from overloaded i-001

Root Cause: i-001 CPU saturation → cascading failure
Action: Scale i-001 or optimize app
```

---

## References

- [CMS API Documentation](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/api-reference-cms-2019-01-01/)
- [CMS 2.0 API Documentation](https://help.aliyun.com/zh/cms/cloudmonitor-2-0/developer-reference/api-reference/)
- [Alibaba Cloud Go SDK](https://github.com/alibabacloud-go/cms-20190101)
- [Metric Reference](https://help.aliyun.com/document_detail/163515.html)
