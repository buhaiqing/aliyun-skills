# Monitoring Alibaba Cloud ECS

## Key Metrics

ECS metrics are available through CloudMonitor (`acs_ecs_dashboard` namespace):

| Metric Name | Description | Unit |
|-------------|-------------|------|
| `CPUUtilization` | CPU usage percentage | % |
| `InternetInRate` | Inbound internet traffic | bits/s |
| `InternetOutRate` | Outbound internet traffic | bits/s |
| `IntranetInRate` | Inbound intranet traffic | bits/s |
| `IntranetOutRate` | Outbound intranet traffic | bits/s |
| `DiskReadBPS` | Disk read throughput | bytes/s |
| `DiskWriteBPS` | Disk write throughput | bytes/s |
| `DiskReadIOPS` | Disk read IOPS | count/s |
| `DiskWriteIOPS` | Disk write IOPS | count/s |
| `MemoryUtilization` | Memory usage percentage | % |
| `LoadAverage` | System load average | - |
| `VPCPublicIPConnection` | Public IP connection count | count |
| `VPCPublicIPInRate` | VPC public IP inbound rate | bits/s |
| `VPCPublicIPOutRate` | VPC public IP outbound rate | bits/s |

## CloudMonitor CLI

```bash
# Describe metric list
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"i-bp67acfmxazb4ph***"}]' \
  --StartTime "2026-05-01T00:00:00Z" \
  --EndTime "2026-05-14T00:00:00Z"

# Describe metric metadata
aliyun cms DescribeMetricMetaList --Namespace acs_ecs_dashboard
```

## Alert Example (structure only)

```json
{
  "AlertName": "ecs-cpu-high",
  "Namespace": "acs_ecs_dashboard",
  "MetricName": "CPUUtilization",
  "Dimensions": [
    {
      "instanceId": "i-bp67acfmxazb4ph***"
    }
  ],
  "EvaluationCount": 3,
  "Period": 60,
  "Statistics": "Average",
  "ComparisonOperator": ">",
  "Threshold": 80,
  "ContactGroups": ["ecs-admins"]
}
```

## Multi-Metric Anomaly Inspection

Execute joint巡检 on ECS instances to identify compound anomaly patterns. Anomaly patterns below use ≥2 metrics combined with detection logic for higher signal-to-noise ratio.

### Supported Anomaly Patterns

| Pattern | Metrics Involved | Detection Logic | Severity | Interpretation |
|---------|-----------------|-----------------|----------|----------------|
| CPU-Memory 双高压 | `CPUUtilization` + `MemoryUtilization` | CPU > 85% AND Memory > 90% 持续 5 min | Critical | 实例整体过载，需扩容或迁移 workload |
| 磁盘-IO 瓶颈 | `DiskReadIOPS` + `DiskWriteIOPS` + `CPUUtilization` | IO > 80% 阈值 AND CPU iowait 高 | Critical | 存储 IO 成为系统瓶颈，考虑换 ESSD 或拆分 IO 密集型应用 |
| 流量突降异常 | `InternetInRate` + `InternetOutRate` + `CPUUtilization` | 流量较 1h 均值下降 > 70% AND CPU 正常 | Warning | 可能网络中断、SLB 摘除、或 DNS/路由变更 |
| CPU-Load 不匹配 | `CPUUtilization` + `LoadAverage` | Load > CPU×2 OR CPU > 90% AND Load < 2 | Warning | Load 远高于 CPU → 可能 IO 等待/锁竞争；CPU 高但 Load 低 → 单核打满 |
| 连接数-流量背离 | `VPCPublicIPConnection` + `InternetOutRate` | 连接数高但流量极低 | Warning | 可能遭遇 Slowloris/DDoS 攻击或连接泄漏 |
| 内存趋势泄漏 | `MemoryUtilization` (趋势) | 斜率连续 6h 正增长 OR 每次 GC 后基线抬升 | Warning | 应用内存泄漏，重启可短期缓解 |

### Execution — CLI

```bash
# Fetch multiple metrics for 1h window (300s period to reduce API calls)
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"i-xxx"}]' \
  --Period 300 --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"

aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName MemoryUtilization \
  --Dimensions '[{"instanceId":"i-xxx"}]' \
  --Period 300

aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName LoadAverage \
  --Dimensions '[{"instanceId":"i-xxx"}]' \
  --Period 300
```

### Recovery & Cross-Skill Delegation

| Pattern | Primary Skill | Delegated Skill | Action |
|---------|--------------|-----------------|--------|
| CPU-Memory 双高 | `alicloud-ecs-ops` | `alicloud-cms-ops` (告警联动) | 垂直扩容或水平扩容 |
| 磁盘-IO 瓶颈 | `alicloud-ecs-ops` | — | 更换 ESSD 云盘规格 |
| 流量突降 | `alicloud-ecs-ops` | `alicloud-slb-ops` (检查 SLB 状态) | 确认 SLB 健康检查/路由 |
| 内存泄漏趋势 | `alicloud-ecs-ops` | `alicloud-cms-ops` (趋势告警) | 应用级排查 + 计划重启 |

## Alert Storm Handling

When >10 ECS alarms trigger within 5 minutes from the same cluster/region, enter storm mode:

1. **Aggregate by instanceId**: Coalesce multiple metrics of same instance into single event
2. **Identify root resource**: Find the first-alarm instance; correlated alarms within ±2 min are symptoms
3. **Suppress duplicates**: Only notify the primary alarm; suppress secondary alarms with reference to root
4. **Focus diagnosis**: Delegate root instance deep diagnosis to `alicloud-ecs-ops` execution flows
5. **Check escalation**: If ≥5 instances share the alarm pattern, check shared dependencies (SLB, VPC, shared storage)

## Alert-Driven Diagnostic Decision Tree

```
[ECS Alarm Fires]
    │
    ├── Step 1: Verify alarm validity — Current metric value vs threshold
    │
    ├── Step 2: Check ECS instance status — State, health, recent restarts
    │       └── If NotAvailable → Check ECS events (maintenance, stop)
    │
    ├── Step 3: Multi-metric correlation — CPU+Memory+IO+Network joint analysis
    │       └── Match anomaly pattern from table above
    │
    ├── Step 4: Cross-Skill diagnosis
    │       ├── If network anomaly → Delegate to `alicloud-vpc-ops` / `alicloud-slb-ops`
    │       └── If IO anomaly → Check cloud disk type via `alicloud-ecs-ops`
    │
    └── Step 5: Generate unified diagnostic report
```

ECS instances can send logs to Alibaba Cloud Log Service:

```bash
# Install Logtail on ECS instance
# Configure machine group in SLS console
# Create log collection configuration
```

## Auto Scaling

For dynamic scaling based on metrics:

```bash
# Describe scaling groups
aliyun ess DescribeScalingGroups --RegionId cn-hangzhou

# Describe scaling configurations
aliyun ess DescribeScalingConfigurations --RegionId cn-hangzhou
```
