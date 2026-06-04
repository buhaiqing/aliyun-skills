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

---

## Intelligent Alert Convergence (智能告警收敛)

Advanced alert correlation and deduplication powered by AI/ML patterns for reducing alert fatigue.

### Convergence Patterns

| Pattern ID | Pattern Name | Detection Logic |收敛效果 |
|------------|--------------|------------------|---------|
| 1 | **同实例多指标告警** | 同一实例的CPU/内存/磁盘同时告警 | 合并为1条，携带所有指标 |
| 2 | **级联告警** | ECS告警→SLB告警→RDS告警（因果链） | 只保留根因告警 |
| 3 | **重复告警** | 同一告警在5分钟内重复触发 | 抑制重复，仅通知首次 |
| 4 | **依赖资源告警** | 多实例因同一SLB/VPC问题告警 | 按依赖树合并 |
| 5 | **计划内告警** | 已知维护窗口内的告警 | 自动静默 |

### CLI Implementation

```bash
# Step 1: Fetch recent alerts within time window
aliyun cms DescribeAlertHistoryList \
  --StartTime "$(date -u -v-10M +%Y-%m-%dT%H:%MZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%MZ)" \
  --Namespace acs_ecs_dashboard \
  --Output cols=AlertName,InstanceId,AlertTime rows=AlertHistoryList[]

# Step 2: Group by instanceId (同实例合并)
aliyun cms DescribeAlertHistoryList ... | \
  jq '.AlertHistoryList[] | {instanceId: .InstanceId, alertName: .AlertName}' | \
  jq -s 'group_by(.instanceId) | map({instanceId: .[0].instanceId, alerts: map(.alertName) | unique})'

# Step 3: Check for cascade patterns (依赖关系分析)
# 需要结合VPC/SLB拓扑数据
```

### SDK Implementation (Intelligent Correlation)

```go
type AlertConverger struct {
    cmsClient *cms.Client
    vpcClient *vpc.Client
    slbClient *slb.Client
}

type ConvergedAlert struct {
    RootCause        string   // 根因实例/资源
    AlertType        string   // 告警类型
    AffectedCount    int      // 影响的实例数
    AlertList        []string // 原始告警列表
    Severity         string   // 最高告警级别
    RecommendedAction string  // 建议操作
}

// detectCascadeAlerts analyzes cascade patterns across dependencies
func (c *AlertConverger) detectCascadeAlerts(alerts []Alert) []ConvergedAlert {
    var converged []ConvergedAlert

    // Build dependency graph
    dependencyGraph := c.buildDependencyGraph()

    // Group alerts by root cause
    alertGroups := c.groupByRootCause(alerts, dependencyGraph)

    for _, group := range alertGroups {
        converged = append(converged, ConvergedAlert{
            RootCause:        group.rootResource,
            AlertType:        group.alertType,
            AffectedCount:    group.count,
            AlertList:        group.alertNames,
            Severity:         c.getHighestSeverity(group.alerts),
            RecommendedAction: c.getRecommendedAction(group),
        })
    }

    return converged
}

func (c *AlertConverger) buildDependencyGraph() map[string][]string {
    // ECS → SLB → RDS 依赖关系
    return map[string][]string{
        "slb-xxx": {"ecs-1", "ecs-2", "ecs-3"},
        "rds-xxx": {"ecs-1", "ecs-2"},
    }
}

func (c *AlertConverger) groupByRootCause(alerts []Alert, depGraph map[string][]string) []AlertGroup {
    // 1. 同实例多指标 → 合并
    // 2. 级联告警 → 找根因
    // 3. 重复告警 → 去重
    // ...
    return groups
}
```

### Convergence Report Format

```markdown
## 智能告警收敛报告

### 收敛统计

| 指标 | 数值 |
|------|------|
| 原始告警数 | 156 |
| 收敛后告警数 | 23 |
| 收敛率 | 85% |
| 级联告警识别 | 8组 |
| 重复告警抑制 | 45条 |

### 收敛后告警明细

#### 🔴 根因告警 (需立即处理)

| 告警ID | 资源 | 类型 | 影响范围 | 建议操作 |
|--------|------|------|----------|----------|
| ALERT-001 | slb-xxx | SLB后端全挂 | 12个ECS实例 | 检查ECS应用状态 |

#### 🟡 依赖告警 (已收敛)

| 原始告警 | 收敛说明 |
|----------|----------|
| ECS-1 CPU高 | 级联至SLB，已合并 |
| ECS-2 CPU高 | 级联至SLB，已合并 |
| ECS-3 CPU高 | 级联至SLB，已合并 |

### 收敛前后对比

```
收敛前: [ECS-1告警][ECS-2告警][ECS-3告警][SLB告警][RDS告警] = 5条
收敛后: [SLB根因告警] = 1条 ✅
```

### Integration

- **EventBridge**: 将收敛后的告警发送到EventBridge触发自动化流程
- **Notification**: 收敛告警通过钉钉/短信/邮件通知
- **Incident**: 严重告警自动创建Jira/工单
```

### Auto-Action Mapping

| Convergence Type | Auto-Action | Manual-Required |
|------------------|-------------|-----------------|
| 根因告警 | 自动创建工单 | 确认 |
| 级联告警 | 抑制从属告警 | 否 |
| 重复告警 | 静默重复 | 否 |
| 计划内告警 | 自动静默 | 否 |

### Configuration

```bash
# 启用智能收敛 (通过CMS告警规则配置)
aliyun cms PutMetricRuleTargets \
  --RuleId "ecs-cpu-high-rule" \
  --TargetType "notification" \
  --Payload "{\"alertConvergence\": true, \"cascadeAnalysis\": true}"
```

> **See also:** [Observability Integration](observability.md)

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
