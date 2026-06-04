# FinOps Analysis for alicloud-cms-ops

## Overview

This reference guide provides FinOps (Financial Operations) capabilities for CloudMonitor (CMS), enabling cost optimization, idle resource detection, and financial anomaly alerting through cross-skill delegation.

## Cost Namespace Reference

### Billing Namespace

| Namespace | Metric | Description | Unit | Frequency |
|-----------|--------|-------------|------|-----------|
| `acs_billing_dashboard` | `DailyBillAmount` | Daily billing amount | USD/CNY | Daily |
| `acs_billing_dashboard` | `MonthlyBillForecast` | Monthly cost forecast | USD/CNY | Daily update |
| `acs_billing_dashboard` | `ResourceCostBreakdown` | Cost by resource type | USD/CNY | Hourly |
| `acs_billing_dashboard` | `CostAnomalyRate` | Cost anomaly percentage | % | Hourly |

### Resource Usage Namespace

| Namespace | Metric | Description | Threshold | Action |
|-----------|--------|-------------|-----------|--------|
| `acs_resource_usage` | `InstanceIdleRate` | ECS idle rate | < 5% CPU for 7d | DetectIdleResources |
| `acs_resource_usage` | `StorageIdleRate` | OSS/Block storage idle | < 1KB/s for 7d | DescribeStorageUsage |
| `acs_resource_usage` | `NetworkIdleRate` | SLB/ENI idle rate | < 5 connections for 7d | DescribeLoadBalancerAttribute |
| `acs_resource_usage` | `DatabaseIdleRate` | RDS/PolarDB idle | < 10 connections for 7d | DescribeDBInstanceAttribute |

### Product-Specific Cost Metrics

| Product | Namespace | Key Metrics | FinOps Integration |
|---------|-----------|-------------|-------------------|
| ECS | `acs_ecs_dashboard` | CPUUtilization, InternetInRate | DetectIdleResources |
| RDS | `acs_rds_dashboard` | ConnectionUsage, CpuUsage, IOPSUsage | UnderutilizedInstanceDetection |
| OSS | `acs_oss_dashboard` | StorageSize, RequestCount | StorageOptimization |
| SLB | `acs_slb_dashboard` | InstanceActiveConnection, DropConnection | IdleLoadBalancerDetection |
| Redis | `acs_kvstore_dashboard` | ConnectionUsage, CpuUsage, MemoryUsage | RightSizingAnalysis |
| PolarDB | `acs_polardb_dashboard` | CpuUsage, ConnectionUsage, StorageUsage | ClusterOptimization |

## Idle Resource Detection Patterns

### ECS Idle Detection

```yaml
idle_ecs_detection:
  criteria:
    cpu_threshold: "avg(CPUUtilization) < 5% for 7 days"
    network_threshold: "avg(InternetInRate) < 1 KB/s for 7 days"
    process_check: "no critical processes running"
    
  detection_flow:
    1. CMS: QueryMetricLast (CPUUtilization, InternetInRate)
    2. Delegate: alicloud-ecs-ops DescribeInstances
    3. Analyze: Process list via CloudAssistant
    4. Output: Idle instances list
    
  outputs:
    idle_instances:
      - instance_id: "i-xxx"
        idle_days: 30
        daily_cost: 50
        potential_savings: "1500/month"
    total_idle_count: 5
    estimated_savings: "$7500/month"
```

**CLI Example**:
```bash
# Query ECS idle rate (last 7 days)
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --InstanceId i-xxx \
  --StartTime "$(date -d '-7 days' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date +%Y-%m-%dT%H:%M:%SZ)" \
  --Period 86400

# Delegate to ECS skill for detailed analysis
aliyun ecs DescribeInstances \
  --InstanceIds '["i-xxx"]' \
  --Status Running
```

### RDS Underutilized Detection

```yaml
underutilized_rds_detection:
  criteria:
    connection_threshold: "avg(ConnectionUsage) < 10 for 7 days"
    cpu_threshold: "avg(CpuUsage) < 20% for 7 days"
    storage_utilization: "StorageUsage < 30%"
    
  detection_flow:
    1. CMS: QueryMetricLast (ConnectionUsage, CpuUsage)
    2. Delegate: alicloud-rds-ops DescribeDBInstances
    3. Analyze: Instance specification vs usage
    4. Output: Right-sizing recommendations
    
  outputs:
    underutilized_instances:
      - instance_id: "rm-xxx"
        current_spec: "rds.mysql.c1.large"
        suggested_spec: "rds.mysql.c1.medium"
        savings: "200/month"
        confidence: 0.85
```

### OSS Storage Anomaly Detection

```yaml
storage_cost_anomaly:
  criteria:
    growth_rate: "StorageSize growth > 50% in 24 hours"
    cost_spike: "DailyBillAmount > threshold + 30%"
    
  detection_flow:
    1. CMS: DescribeMetricLast (StorageSize)
    2. Analyze: Growth rate calculation
    3. Delegate: alicloud-oss-ops GetBucketUsage
    4. Output: Anomaly root cause
    
  outputs:
    anomaly_type: "rapid_growth|cost_spike|abnormal_access"
    root_cause: "log accumulation|backup duplication|unused_objects"
    recommended_action: "lifecycle_policy|cleanup|archive"
```

### SLB Idle Detection

```yaml
idle_slb_detection:
  criteria:
    connection_threshold: "avg(InstanceActiveConnection) < 5 for 7 days"
    traffic_threshold: "avg(TrafficRXNew) < 100 bytes/s for 7 days"
    
  outputs:
    idle_loadbalancers:
      - lb_id: "lb-xxx"
        daily_cost: 20
        potential_savings: "600/month"
        recommendation: "release_or_downgrade"
```

## FinOps Alarm Templates

### Template 1: Idle ECS Detection Alarm

```yaml
alarm_template:
  name: "IdleECSDetection"
  namespace: acs_ecs_dashboard
  metrics:
    - CPUUtilization
    - InternetInRate
  criteria:
    expression: "avg(cpu) < 5 AND avg(network_in) < 1KB/s"
    period: 604800  # 7 days in seconds
  severity: warning
  delegate_to: alicloud-ecs-ops
  action: DetectIdleResources
  notification:
    - channel: email
      message: "检测到闲置 ECS 实例，预估可节省 ${{estimated_savings}}/月"
```

### Template 2: Cost Spike Alarm

```yaml
alarm_template:
  name: "CostSpikeDetection"
  namespace: acs_billing_dashboard
  metric: DailyBillAmount
  criteria:
    expression: "value > baseline_avg * 1.5"
    period: 86400
    baseline_days: 30
  severity: critical
  delegate_to: 
    - alicloud-ecs-ops
    - alicloud-rds-ops
  actions:
    - DetectIdleResources
    - DescribeDBInstanceAttribute
  notification:
    - channel: dingtalk
      message: "成本异常，日账单超过基线 50%"
```

### Template 3: Storage Growth Anomaly

```yaml
alarm_template:
  name: "StorageGrowthAnomaly"
  namespace: acs_oss_dashboard
  metric: StorageSize
  criteria:
    expression: "growth_rate_24h > 50%"
    period: 86400
  severity: warning
  delegate_to: alicloud-oss-ops
  action: GetBucketUsage
  notification:
    - channel: email
      message: "OSS 存储空间24小时内增长超过50%"
```

## Cost Optimization Suggestion Templates

### Right-Sizing Recommendations

```yaml
right_sizing_recommendation:
  inputs:
    - resource_type: "{{user.resource_type}}"  # ecs|rds|redis|polardb
    - time_range: "{{user.time_range}}"        # 30d default
    - utilization_threshold: 0.3               # < 30% = underutilized
    
  analysis_flow:
    1. Collect: Metric data from CMS
    2. Compare: Current spec vs actual usage
    3. Calculate: Potential savings
    4. Validate: Impact on performance
    5. Recommend: Optimal specification
    
  outputs:
    recommendations:
      - type: "downgrade"
        resource: "i-xxx"
        current_spec: "ecs.g6.xlarge"
        suggested_spec: "ecs.g6.large"
        current_cost: 400
        suggested_cost: 200
        savings: 200
        confidence: 0.85
        impact_analysis: "No performance degradation expected"
        
      - type: "right_size"
        resource: "rm-xxx"
        current_spec: "rds.mysql.x4.large"
        suggested_spec: "rds.mysql.x2.large"
        current_cost: 800
        suggested_cost: 400
        savings: 400
        confidence: 0.75
        impact_analysis: "May affect peak performance"
        
    total_potential_savings: 600
    implementation_priority:
      - P0: confidence >= 0.9, savings >= 500
      - P1: confidence >= 0.8, savings >= 200
      - P2: confidence >= 0.7, savings >= 100
```

### Reserved Instance Recommendations

```yaml
reserved_instance_recommendation:
  inputs:
    - usage_pattern: "{{user.usage_pattern}}"  # steady|variable|seasonal
    - commitment_period: 12                    # months
    
  analysis:
    steady_usage:
      criteria: "usage variance < 20% over 90 days"
      recommendation: "Convert to RI, estimated savings 40-60%"
      
    variable_usage:
      criteria: "usage variance 20-50%"
      recommendation: "Partial RI + Pay-as-you-go, savings 20-40%"
      
    seasonal_usage:
      criteria: "usage variance > 50%"
      recommendation: "Pay-as-you-go optimal"
      
  outputs:
    ri_recommendations:
      - instance_type: "ecs.g6.xlarge"
        current_cost: 400
        ri_cost: 160
        savings_percent: 60
        commitment: 12 months
        break_even_point: 4 months
```

### Resource Release Recommendations

```yaml
release_recommendation:
  inputs:
    - idle_threshold_days: 30
    - cost_threshold: 100
    
  criteria:
    - idle_days >= 30
    - no_critical_processes
    - no_recent_access
    - cost >= 100
    
  outputs:
    release_candidates:
      - resource: "i-yyy"
        type: "ecs"
        idle_days: 45
        monthly_cost: 150
        release_savings: 150
        confidence: 0.95
        validation_steps:
          - CheckCloudAssistantStatus
          - VerifyNoActiveConnections
          - ConfirmNoScheduledTasks
          
    total_release_savings: 500
    risk_assessment:
      level: "low"
      reason: "No active services detected"
```

## CLI Command Examples

### Query Cost Metrics

```bash
# Query daily billing amount
aliyun cms DescribeMetricList \
  --Namespace acs_billing_dashboard \
  --MetricName DailyBillAmount \
  --StartTime "2026-05-01T00:00:00Z" \
  --EndTime "2026-05-26T00:00:00Z" \
  --Period 86400

# Query ECS utilization for idle detection
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --InstanceId i-xxx \
  --StartTime "$(date -d '-30 days' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date +%Y-%m-%dT%H:%M:%SZ)" \
  --Period 86400
```

### Create FinOps Alarm Rule

```bash
# Create idle ECS detection alarm
aliyun cms PutAlarmRule \
  --AlarmName "IdleECSDetection" \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Threshold 5 \
  --ComparisonOperator LessThan \
  --Period 604800 \
  --EvaluationCount 1 \
  --ContactGroups '["FinOpsTeam"]'

# Create cost spike alarm
aliyun cms PutAlarmRule \
  --AlarmName "CostSpikeDetection" \
  --Namespace acs_billing_dashboard \
  --MetricName DailyBillAmount \
  --Threshold 1500 \
  --ComparisonOperator GreaterThan \
  --Period 86400 \
  --EvaluationCount 3 \
  --ContactGroups '["FinanceTeam","OpsTeam"]'
```

### Delegation to Product Skills

```bash
# Delegate to ECS for idle resource analysis
# (CMS alarm fires → ECS skill execution)
aliyun ecs DescribeInstances \
  --InstanceIds '["i-xxx","i-yyy"]' \
  --Status Running \
  --Filter '[
    {"Name":"cpu-utilization","Value":"<5"},
    {"Name":"network-in-rate","Value":"<1KB"}
  ]'

# Delegate to RDS for underutilization analysis
aliyun rds DescribeDBInstances \
  --DBInstanceStatus Running \
  --Filter '[
    {"Name":"connection-usage","Value":"<10"},
    {"Name":"cpu-usage","Value":"<20"}
  ]'
```

## Cost Calculation Formulas

### Idle Resource Cost Savings

```
Daily_Savings = Instance_Daily_Cost × Idle_Rate
Monthly_Savings = Daily_Savings × 30
Annual_Savings = Monthly_Savings × 12

Total_Idle_Savings = Σ(All_Idle_Resources × Monthly_Cost)
```

### Right-Sizing Savings

```
Savings_Per_Instance = (Current_Spec_Cost - Suggested_Spec_Cost)
Confidence_Adjusted_Savings = Savings × Confidence_Score
Total_RightSizing_Savings = Σ(All_RightSized_Instances × Confidence_Adjusted_Savings)
```

### Reserved Instance Break-Even Analysis

```
Break_Even_Months = RI_Commitment_Cost / (Monthly_PayG_Cost - Monthly_RI_Cost)
ROI = (Total_PayG_Cost - Total_RI_Cost) / RI_Commitment_Cost × 100%
```

## Integration Best Practices

### FinOps Workflow Integration

```yaml
finops_workflow:
  daily:
    - Check: DailyBillAmount anomaly
    - Action: Alert if > baseline + 30%
    - Delegate: ECS/RDS idle detection
    
  weekly:
    - Check: InstanceIdleRate aggregate
    - Action: Generate idle resource report
    - Delegate: Right-sizing analysis
    
  monthly:
    - Check: MonthlyBillForecast vs actual
    - Action: Cost optimization review
    - Delegate: Reserved instance recommendations
```

### Alarm-to-Action Delegation

```yaml
delegation_protocol:
  Step_1_CMS_Alarm: "Cost/idle metric triggers alarm"
  Step_2_Confidence_Score: "Calculate anomaly confidence"
  Step_3_Threshold_Check:
    - If confidence >= 0.8: Immediate delegation
    - If confidence 0.5-0.8: Validate with additional metrics
    - If confidence < 0.5: Monitor only
  Step_4_Skill_Delegation:
    - ECS idle → alicloud-ecs-ops DetectIdleResources
    - RDS idle → alicloud-rds-ops DescribeDBInstanceAttribute
    - OSS anomaly → alicloud-oss-ops GetBucketUsage
  Step_5_Action_Execution:
    - Generate savings report
    - Create optimization recommendations
    - Notify stakeholders
```

### Cross-Skill Correlation

```
[CMS Alarm] → [Confidence Score] → [Skill Delegation]
     │              │                    │
     │              │                    ├── ECS: DetectIdleResources
     │              │                    ├── RDS: RightSizingAnalysis
     │              │                    └── OSS: StorageOptimization
     │              │
     │              └── Validation before delegation
     │
     └── DAS Integration: CreateDiagnosticReport for resource correlation
```

## References

- [CMS API Documentation](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/api-reference-cms-2019-01-01/)
- [Billing API Reference](https://help.aliyun.com/zh/bss/developer-reference/api-bss-2018-05-01-overview)
- [FinOps Foundation Best Practices](https://www.finops.org/framework/)