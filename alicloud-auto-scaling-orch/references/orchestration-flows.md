# Orchestration Flows — 六场景完整编排步骤

> 详细编排步骤、CLI 命令、参数映射和验证逻辑。
> 注意：本文件只描述"编排层"的逻辑。实际 CLI/SDK 执行委托给下游 Skill。

---

## 目录

1. [S1 — CPU/内存指标驱动扩缩](#s1--cpu内存指标驱动扩缩)
2. [S2 — 定时业务周期扩缩](#s2--定时业务周期扩缩)
3. [S3 — 预测性扩缩](#s3--预测性扩缩)
4. [S4 — 复合多指标扩缩](#s4--复合多指标扩缩)
5. [S5 — 大促弹性保障](#s5--大促弹性保障)
6. [S6 — 闲置资源自动回收](#s6--闲置资源自动回收)
7. [通用验证与回滚](#通用验证与回滚)

---

## S1 — CPU/内存指标驱动扩缩

### 编排步骤

#### Step 1: 感知 — 采集当前负载

```bash
# 委托 cms-ops: 获取最近 1h CPU 指标
aliyun cms DescribeMetricList \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "CpuUtilization" \
  --Dimensions "[{\"instanceId\":\"i-xxx\"}]" \
  --Period 300 \
  --Length 12

# 委托 cms-ops: 获取最近 1h 内存指标
aliyun cms DescribeMetricList \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "memory_usedutilization" \
  --Dimensions "[{\"instanceId\":\"i-xxx\"}]" \
  --Period 300 \
  --Length 12
```

#### Step 2: 决策 — 计算目标容量

```
当前 CPU = avg(last_5_periods) = 75%
目标利用率 = 60%
期望容量 = ceil(当前实例数 × 当前CPU / 目标利用率)
         = ceil(3 × 0.75 / 0.60) = ceil(3.75) = 4
→ 扩容 1 台
```

#### Step 3: 编排 — 创建伸缩规则

```bash
# 委托 ess-ops: 创建目标追踪规则
aliyun ess CreateScalingRule \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScalingRuleName "orch-cpu-target-{{user.policy_name}}" \
  --ScalingRuleType "TargetTrackingScalingRule" \
  --MetricName "CpuUtilization" \
  --TargetValue {{user.cpu_target|60}} \
  --EstimatedInstanceWarmup 120

# 委托 ess-ops: 创建缩容规则 (Simple)
aliyun ess CreateScalingRule \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScalingRuleName "orch-cpu-scalein-{{user.policy_name}}" \
  --ScalingRuleType "SimpleScalingRule" \
  --AdjustmentType "QuantityChangeInCapacity" \
  --AdjustmentValue "-{{user.scale_in_qty|1}}" \
  --Cooldown {{user.cooldown|300}}

# 委托 ess-ops: 创建缩容告警
aliyun ess CreateAlarm \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --Name "orch-cpu-low-{{user.policy_name}}" \
  --Description "CPU低于{{user.cpu_threshold_low|30}}%持续10min" \
  --MetricName "CpuUtilization" \
  --Statistics "Average" \
  --Period 300 \
  --Threshold {{user.cpu_threshold_low|30}} \
  --ComparisonOperator "<=" \
  --EvaluationCount 2
```

#### Step 4: 验证

```bash
# 委托 cms-ops: 确认指标回归
aliyun cms DescribeMetricLast \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "CpuUtilization" \
  --Dimensions "[{\"instanceId\":\"i-xxx\"}]"

# 委托 ess-ops: 确认伸缩活动状态
aliyun ess DescribeScalingActivities \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --PageNumber 1 --PageSize 5
```

---

## S2 — 定时业务周期扩缩

### 编排步骤

#### Step 1: 感知 — 确认当前伸缩组状态

```bash
# 委托 ess-ops: 获取伸缩组信息
aliyun ess DescribeScalingGroups \
  --ScalingGroupId.1 "{{user.scaling_group_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

#### Step 2: 决策 — 确认定时参数

```
当前 MinSize=1, MaxSize=10, DesiredCapacity=2
目标时间段:
  09:00 → DesiredCapacity=5 (扩容+3)
  18:00 → DesiredCapacity=2 (缩容-3)
```

#### Step 3: 编排 — 创建定时任务

```bash
# 委托 ess-ops: 创建扩容定时任务
aliyun ess CreateScheduledTask \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ScheduledTaskName "orch-scaleup-{{user.policy_name}}" \
  --Description "定时扩容 ({{user.schedule_cron}})" \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScheduledAction "{\"DesiredCapacity\": {{user.scale_out_desired|5}}}" \
  --RecurrenceType "Cron" \
  --RecurrenceValue "{{user.schedule_cron}}" \
  --LaunchTime "{{user.schedule_start_time}}" \
  --TimeZone "{{user.schedule_timezone|Asia/Shanghai}}"

# 委托 ess-ops: 创建缩容定时任务
aliyun ess CreateScheduledTask \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ScheduledTaskName "orch-scaledown-{{user.policy_name}}" \
  --Description "定时缩容 ({{user.schedule_cron_in}})" \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScheduledAction "{\"DesiredCapacity\": {{user.scale_in_desired|1}}}" \
  --RecurrenceType "Cron" \
  --RecurrenceValue "{{user.schedule_cron_in}}" \
  --LaunchTime "{{user.schedule_end_time}}" \
  --TimeZone "{{user.schedule_timezone|Asia/Shanghai}}"
```

#### Step 4: 验证

```bash
# 委托 ess-ops: 确认定时任务创建成功
aliyun ess DescribeScheduledTasks \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ScheduledTaskName.1 "orch-scaleup-{{user.policy_name}}" \
  --ScheduledTaskName.2 "orch-scaledown-{{user.policy_name}}"
```

---

## S3 — 预测性扩缩

### 编排步骤

#### Step 1: 感知 — 获取历史指标

```bash
# 委托 cms-ops: 获取 14 天 CPU 历史
aliyun cms DescribeMetricList \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "CpuUtilization" \
  --Period 3600 \
  --StartTime "$(date -d '14 days ago' -u +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

#### Step 2: 决策 — 检查周期性

```
检查: CPU 历史是否有明显日/周周期
  日周期: 每天相同时间段有规律波动 → 适合 Predictive
  周周期: 工作日/周末模式明显 → 适合 Predictive
  无明显周期 → 降级到 S1 (TargetTracking)

决策: 创建 PredictiveScalingRule
```

#### Step 3: 编排 — 创建预测规则

```bash
# 委托 ess-ops: 创建预测规则
aliyun ess CreateScalingRule \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScalingRuleName "orch-predictive-{{user.policy_name}}" \
  --ScalingRuleType "PredictiveScalingRule" \
  --MetricName "CpuUtilization" \
  --PredictiveScalingMode "PredictAndScale" \
  --PredictiveValueBehavior "MaxOverridePredictiveValue" \
  --PredictiveValueBuffer 20 \
  --PredictiveTaskBufferTime 300 \
  --EstimatedInstanceWarmup 180 \
  --TargetValue {{user.predictive_target|60}}
```

> `PredictiveScalingMode` 参数：
> - `PredictAndScale`: 预测并执行扩缩（推荐）
> - `PredictOnly`: 仅预测，不执行（预览模式）
>
> `PredictiveValueBehavior`:
> - `MaxOverridePredictiveValue`: 取预测值与实际值的 Max（推荐）
> - `PredictiveValueOverrideMax`: 仅使用预测值
> - `PredictiveValueOverrideMaxWithBuffer`: 预测值 + Buffer 取 Max

#### Step 4: 验证

```bash
# 委托 ess-ops: 确认规则创建
aliyun ess DescribeScalingRules \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScalingRuleType "PredictiveScalingRule"
```

---

## S4 — 复合多指标扩缩

### 编排步骤

#### Step 1: 感知 — 采集 CPU + 内存双指标

```bash
# 委托 cms-ops: 并行采集两个指标
aliyun cms DescribeMetricLast \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "CpuUtilization" &
aliyun cms DescribeMetricLast \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "memory_usedutilization" &
wait
```

#### Step 2: 决策 — 双指标矩阵判定

```
决策矩阵:
  CPU=75%, Mem=82%
  → "确认区": CPU > 70% AND Mem > 80%
  → 扩容 2 台 (StepScalingRule 中档)

  CPU=95%, Mem=60%
  → "危险区": CPU > 90% OR Mem > 90%
  → 扩容 5 台 (StepScalingRule 高档)
```

#### Step 3: 编排 — 创建 Step 规则

```bash
# 委托 ess-ops: 创建 StepScalingRule
aliyun ess CreateScalingRule \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScalingRuleName "orch-composite-{{user.policy_name}}" \
  --ScalingRuleType "StepScalingRule" \
  --AdjustmentType "QuantityChangeInCapacity" \
  --StepAdjustments.1.MetricIntervalLowerBound 0 \
  --StepAdjustments.1.MetricIntervalUpperBound 20 \
  --StepAdjustments.1.ScalingAdjustment {{user.scale_out_qty|2}} \
  --StepAdjustments.2.MetricIntervalLowerBound 20 \
  --StepAdjustments.2.MetricIntervalUpperBound 100 \
  --StepAdjustments.2.ScalingAdjustment {{user.scale_out_qty|5}} \
  --Cooldown {{user.cooldown|300}}

# 委托 cms-ops: 创建组合告警
aliyun cms PutResourceMetricRule \
  --RuleName "orch-composite-alert-{{user.policy_name}}" \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "CpuUtilization" \
  --Threshold "{{user.cpu_threshold_high|70}}" \
  --ComparisonOperator "GreaterThanThreshold" \
  --Statistics "Average" \
  --Period 300 \
  --EvaluationCount 2
```

> **注意**: StepScalingRule 只能关联一个告警。复合判断（CPU AND 内存）推荐在 CMS 级别做多个告警联动，或使用编排脚本做前置判断后再触发 ESS 规则。

#### Step 4: 验证

```bash
# 委托 ess-ops + cms-ops 双验证
aliyun ess DescribeScalingRules --ScalingGroupId "{{user.scaling_group_id}}"
aliyun cms DescribeMetricRuleList --RuleName "orch-composite-alert-{{user.policy_name}}"
```

---

## S5 — 大促弹性保障

### 编排步骤

#### Step 1: 感知 — 采集历史峰值

```bash
# 委托 cms-ops: 获取过去 30 天 CPU 峰值
aliyun cms DescribeMetricList \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "CpuUtilization" \
  --Period 3600 \
  --StartTime "$(date -d '30 days ago' -u +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

#### Step 2: 决策 — 计算大促容量

```
历史峰值 CPU = 85%（过去 30 天）
安全系数 = 1.5（大促流量倍数预估）
目标利用率 = 60%

大促期望容量 = ceil(当前实例数 × 历史峰值CPU × 安全系数 / 目标利用率)
            = ceil(5 × 0.85 × 1.5 / 0.60) = ceil(10.625) = 11

→ 预扩容至 12 台（比计算多 1 台作为 buffer）
```

#### Step 3: 编排 — 部署大促策略

```bash
# 步骤 A: 临时提升 MaxSize
aliyun ess ModifyScalingGroup \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --MaxSize {{user.event_max_capacity|20}} \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 步骤 B: 创建预扩容定时任务 (提前 2h)
aliyun ess CreateScheduledTask \
  --ScheduledTaskName "orch-event-scaleup-{{user.policy_name}}" \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScheduledAction "{\"DesiredCapacity\": {{user.event_desired_capacity|12}}}" \
  --LaunchTime "{{user.event_launch_time}}" \
  --RecurrenceType "Once"

# 步骤 C: 创建渐缩定时任务 (结束后 30min 开始)
SCALE_IN_STEPS=4
for i in $(seq 1 $SCALE_IN_STEPS); do
  STEP_DESIRED=$(echo "12 - (12 - 2) * $i / $SCALE_IN_STEPS" | bc)
  STEP_TIME=$(date -d "{{user.event_end_time}} + $((i * 30)) minutes" -u +%Y-%m-%dT%H:%M:%SZ)
  aliyun ess CreateScheduledTask \
    --ScheduledTaskName "orch-event-scalein-step${i}-{{user.policy_name}}" \
    --ScalingGroupId "{{user.scaling_group_id}}" \
    --ScheduledAction "{\"DesiredCapacity\": $STEP_DESIRED}" \
    --LaunchTime "$STEP_TIME" \
    --RecurrenceType "Once"
done

# 步骤 D: 恢复 MaxSize
aliyun ess ModifyScalingGroup \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --MaxSize {{user.max_capacity|10}} \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

#### Step 4: 验证

```bash
# 验证所有定时任务是否创建成功
aliyun ess DescribeScheduledTasks \
  --ScheduledTaskName.1 "orch-event-scaleup-{{user.policy_name}}" \
  --ScheduledTaskName.2 "orch-event-scalein-step1-{{user.policy_name}}"

# 验证伸缩组 MaxSize 已恢复
aliyun ess DescribeScalingGroups \
  --ScalingGroupId.1 "{{user.scaling_group_id}}"
```

---

## S6 — 闲置资源自动回收

### 编排步骤

#### Step 1: 感知 — 采集长时间窗口低负载

```bash
# 委托 cms-ops: 获取 N 天 CPU 历史
DAYS="{{user.idle_duration_days|7}}"
aliyun cms DescribeMetricList \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "CpuUtilization" \
  --Period 3600 \
  --StartTime "$(date -d "${DAYS} days ago" -u +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

#### Step 2: 决策 — 判定闲置状态

```
CPU_P99 = 3.2%（过去 7 天）
阈值 = 5%
判定: P99 < 5% → 闲置状态 → 建议缩容

节省预估:
  当前实例: 3 台 (ecs.g7.xlarge, ¥0.55/h)
  缩容至: 1 台 (MinSize)
  日节省: 2 × ¥0.55 × 24 = ¥26.4/天
  月节省: ~¥792
```

#### Step 3: 编排 — 执行回收

```bash
# 步骤 A: 通知用户 (24h 预警)
# 通过 cms-ops 发送告警通知
aliyun cms PutEventRule \
  --RuleName "orch-idle-notify-{{user.policy_name}}" \
  --EventPattern "{\"product\":\"ESS\",\"name\":\"IdleCleanupWarning\"}"

# 步骤 B: 创建缩容定时任务 (24h 后执行)
aliyun ess CreateScheduledTask \
  --ScheduledTaskName "orch-idle-cleanup-{{user.policy_name}}" \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScheduledAction "{\"DesiredCapacity\": {{user.idle_target_capacity|1}}}" \
  --LaunchTime "$(date -d '+24 hours' -u +%Y-%m-%dT%H:%M:%SZ)"

# 步骤 C: 同时创建保护性告警 (如果缩容后负载回升则告警)
aliyun ess CreateAlarm \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --Name "orch-idle-protect-{{user.policy_name}}" \
  --MetricName "CpuUtilization" \
  --Statistics "Average" \
  --Period 300 \
  --Threshold 50 \
  --ComparisonOperator ">=" \
  --EvaluationCount 2
```

#### Step 4: 验证

```bash
# 24h 后验证:
# 1. 查当前实例数
aliyun ess DescribeScalingInstances \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 2. 查 CPU 是否平稳
aliyun cms DescribeMetricLast \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "CpuUtilization"
```

---

## 通用验证与回滚

### 扩缩容验证检查表

| 检查项 | 方法 | 通过条件 |
|--------|------|---------|
| 伸缩活动完成 | ess-ops DescribeScalingActivities | StatusCode=Success |
| 实例数正确 | ess-ops DescribeScalingInstances | count == 目标值 |
| 实例健康 | ess-ops DescribeScalingInstances | HealthStatus=Healthy |
| SLB 已注册 | slb-ops DescribeHealthStatus | 新实例均为正常 |
| CPU 回归 | cms-ops DescribeMetricLast | 目标范围内 |
| 无异常告警 | cms-ops DescribeMetricRuleCount | 无 ALARM 状态 |

### 回滚策略

| 失败场景 | 回滚动作 | 执行者 |
|---------|---------|--------|
| 扩容后实例不健康 | ess-ops 自动替换（健康检查）| ess-ops 自动 |
| SLB 注册失败 | 重试 3 次，失败后删除新实例 | 编排引擎 |
| CPU 不降反升 | 继续扩容（熔断条件内） | 编排引擎 |
| 缩容后 CPU 飙升 | 取消缩容 + 紧急扩容 | 编排引擎 |
| MaxSize 改不回去 | 重试 3 次 + 记录错误 | HALT + 通知 |

### 熔断触发条件

```
if (近24h扩缩次数 > 5) → 熔断 1 小时
if (当前有活动未完成) → 排队等待
if (余额不足) → HALT + 通知
if (目标容量 > 配额) → 自动调整 + 通知
if (1h内方向反转 > 3次) → 熔断 + 分析报告
```