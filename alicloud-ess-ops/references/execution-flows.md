# Execution Flows — Auto Scaling (ESS)

> Version: 1.0.0 | Last Updated: 2026-06-07
> Load Condition: 仅在用户执行具体操作时加载
> Token Cost Estimate: ~400 tokens

---

## Table of Contents

1. [Create Scaling Group](#1-create-scaling-group)
2. [Modify Scaling Group](#2-modify-scaling-group)
3. [Delete Scaling Group](#3-delete-scaling-group)
4. [Scaling Configuration](#4-scaling-configuration)
5. [Scaling Rules](#5-scaling-rules)
6. [Scheduled Tasks](#6-scheduled-tasks)
7. [Lifecycle Hooks](#7-lifecycle-hooks)
8. [Instance Management](#8-instance-management)
9. [Load Balancer Association](#9-load-balancer-association)
10. [Enable/Disable Scaling Group](#10-enabledisable-scaling-group)
11. [Alarm-Based Scaling Rules](#11-alarm-based-scaling-rules)
12. [Instance Refresh](#12-instance-refresh)
13. [Notification Configuration](#13-notification-configuration)
14. [Tag Management](#14-tag-management)
15. [Set Group Deletion Protection](#15-set-group-deletion-protection)
16. [Query Scaling Activities](#16-query-scaling-activities)

---

### 1. Create Scaling Group

```bash
aliyun ess CreateScalingGroup \
  --RegionId "{{user.region}}" \
  --ScalingGroupName "{{user.scaling_group_name}}" \
  --MinSize "{{user.min_size|0}}" \
  --MaxSize "{{user.max_size|10}}" \
  --DefaultCooldown "{{user.default_cooldown|300}}" \
  --VSwitchIds "[\"{{user.vswitch_ids}}\"]" \
  --RemovalPolicies "[\"OldestScalingConfiguration\",\"OldestInstance\"]" \
  --MultiAZPolicy "{{user.multi_az_policy|BALANCE}}" \
  --GroupDeletionProtection "{{user.group_deletion_protection|false}}" \
  --ClientToken "{{output.client_token}}"
```

**Output:** `$.ScalingGroupId`

**JIT Go SDK fallback:**
```go
request := &ess.CreateScalingGroupRequest{
    RegionId:         tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    ScalingGroupName: tea.String(os.Getenv("SCALING_GROUP_NAME")),
    MinSize:          tea.Int(0), MaxSize: tea.Int(10),
    VSwitchIds: tea.String("[\""+os.Getenv("VSWITCH_IDS")+"\"]"),
    DefaultCooldown: tea.Int(300), MultiAZPolicy: tea.String("BALANCE"),
}
```

**MultiAZPolicy:** `BALANCE` (default), `PRIORITY`, `COMPOSABLE`.
**RemovalPolicies:** `OldestScalingConfiguration`, `NewestInstance`, `OldestInstance`, `CustomPolicy`.

---

### 2. Modify Scaling Group

```bash
aliyun ess ModifyScalingGroup \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScalingGroupName "{{user.new_name}}" \
  --MinSize "{{user.new_min_size}}" \
  --MaxSize "{{user.new_max_size}}" \
  --DefaultCooldown "{{user.new_cooldown}}" \
  --RemovalPolicies "[\"OldestScalingConfiguration\",\"OldestInstance\"]" \
  --ActiveScalingConfigurationId "{{user.scaling_configuration_id}}"
```

---

### 3. Delete Scaling Group

```bash
# Safe delete (fails if instances exist)
aliyun ess DeleteScalingGroup \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --RegionId "{{user.region}}"

# Force delete (removes all instances first)
aliyun ess DeleteScalingGroup \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ForceDelete true \
  --RegionId "{{user.region}}"
```

> ⚠️ **Destructive** — must pass safety gate in SKILL.md first.

---

### 4. Scaling Configuration

```bash
# Create ECS scaling configuration
aliyun ess CreateScalingConfiguration \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScalingConfigurationName "{{user.config_name}}" \
  --ImageId "{{user.image_id}}" \
  --InstanceType "{{user.instance_type}}" \
  --SecurityGroupId "{{user.security_group_id}}" \
  --SystemDiskCategory "{{user.system_disk_category|cloud_essd}}" \
  --SystemDiskSize "{{user.system_disk_size|40}}"

# Create ECI scaling configuration
aliyun ess CreateEciScalingConfiguration \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScalingConfigurationName "{{user.eci_config_name}}" \
  --ImageId "{{user.image_id}}" --Cpu "{{user.cpu|2}}" --Memory "{{user.memory|4}}"

# List, activate, deactivate, delete
aliyun ess DescribeScalingConfigurations --ScalingGroupId "{{user.scaling_group_id}}"
aliyun ess ModifyScalingGroup --ScalingGroupId "{{user.scaling_group_id}}" --ActiveScalingConfigurationId "{{user.scaling_configuration_id}}"
aliyun ess DeactivateScalingConfiguration --ScalingConfigurationId "{{user.scaling_configuration_id}}"
aliyun ess DeleteScalingConfiguration --ScalingConfigurationId "{{user.scaling_configuration_id}}"
```

**Output:** `$.ScalingConfigurationId`

---

### 5. Scaling Rules

```bash
# Simple scaling rule
aliyun ess CreateScalingRule \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScalingRuleName "{{user.rule_name}}" \
  --ScalingRuleType "{{user.rule_type|SimpleScalingRule}}" \
  --AdjustmentType "{{user.adjustment_type|QuantityChangeInCapacity}}" \
  --AdjustmentValue "{{user.adjustment_value|1}}" \
  --Cooldown "{{user.cooldown|300}}"

# Target tracking rule
aliyun ess CreateScalingRule \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScalingRuleName "{{user.rule_name}}" \
  --ScalingRuleType "TargetTrackingScalingRule" \
  --MetricName "{{user.metric_name|CpuUtilization}}" \
  --TargetValue "{{user.target_value|80.0}}"

# Step scaling rule
aliyun ess CreateScalingRule \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ScalingRuleType "StepScalingRule" \
  --AdjustmentType "QuantityChangeInCapacity" \
  --StepAdjustments "[{\"MetricIntervalLowerBound\":0,\"ScalingAdjustment\":1}]"

aliyun ess DescribeScalingRules --ScalingGroupId "{{user.scaling_group_id}}"
aliyun ess ExecuteScalingRule --ScalingRuleAri "{{user.scaling_rule_ari}}" --ClientToken "{{output.client_token}}"
aliyun ess DeleteScalingRule --ScalingRuleId "{{user.scaling_rule_id}}"
```

**ScalingRuleType:** `SimpleScalingRule`, `StepScalingRule`, `TargetTrackingScalingRule`, `PredictiveScalingRule`.
**AdjustmentType:** `QuantityChangeInCapacity`, `PercentChangeInCapacity`, `TotalCapacity`.
**ExecuteScalingRule** returns `$.ScalingActivityId`.

---

### 6. Scheduled Tasks

```bash
aliyun ess CreateScheduledTask \
  --ScheduledTaskName "{{user.task_name}}" \
  --RegionId "{{user.region}}" \
  --ScheduledAction "{{user.scheduled_action}}" \
  --LaunchTime "{{user.launch_time}}" \
  --RecurrenceType "{{user.recurrence_type|Daily}}" \
  --RecurrenceValue "{{user.recurrence_value|1}}" \
  --RecurrenceEndTime "{{user.recurrence_end_time}}" \
  --TaskEnabled "{{user.task_enabled|true}}"

aliyun ess DescribeScheduledTasks --RegionId "{{user.region}}"
aliyun ess ModifyScheduledTask --ScheduledTaskId "{{user.scheduled_task_id}}" --LaunchTime "{{user.new_launch_time}}"
aliyun ess DeleteScheduledTask --ScheduledTaskId "{{user.scheduled_task_id}}"
```

> **ScheduledAction:** The ARN (`ScalingRuleAri`) of the rule to execute.
> **RecurrenceType:** `Daily`, `Weekly`, `Monthly`, `Cron`.

---

### 7. Lifecycle Hooks

```bash
aliyun ess CreateLifecycleHook \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --LifecycleHookName "{{user.hook_name}}" \
  --LifecycleTransition "{{user.lifecycle_transition}}" \
  --HeartbeatTimeout "{{user.heartbeat_timeout|600}}" \
  --DefaultResult "{{user.default_result|CONTINUE}}" \
  --NotificationArn "{{user.notification_arn}}"

aliyun ess DescribeLifecycleHooks --ScalingGroupId "{{user.scaling_group_id}}"
aliyun ess CompleteLifecycleAction --LifecycleHookId "{{user.lifecycle_hook_id}}" --LifecycleActionResult "{{user.action_result|CONTINUE}}" --InstanceId "{{user.instance_id}}"
aliyun ess RecordLifecycleActionHeartbeat --LifecycleHookId "{{user.lifecycle_hook_id}}" --InstanceId "{{user.instance_id}}"
aliyun ess DeleteLifecycleHook --LifecycleHookId "{{user.lifecycle_hook_id}}" --ScalingGroupId "{{user.scaling_group_id}}"
```

> **LifecycleTransition:** `Autoscaling:EC2Instance-Launching`, `Autoscaling:EC2Instance-Terminating`.
> **DefaultResult / LifecycleActionResult:** `CONTINUE`, `ABANDON`.

---

### 8. Instance Management

```bash
# Attach instances
aliyun ess AttachInstances \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --InstanceId.1 "{{user.instance_id_1}}" \
  --InstanceId.2 "{{user.instance_id_2}}" \
  --Entrusted "{{user.entrusted|true}}" \
  --RegionId "{{user.region}}"

# Detach instances
aliyun ess DetachInstances \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --InstanceId.1 "{{user.instance_id}}" \
  --DetachOption "{{user.detach_option|null}}" \
  --RegionId "{{user.region}}"

# Remove instances (⚠️ Destructive)
aliyun ess RemoveInstances \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --InstanceId.1 "{{user.instance_id}}" \
  --RemovePolicy "{{user.remove_policy|OldestInstance}}" \
  --RegionId "{{user.region}}"

# Standby management
aliyun ess EnterStandby --ScalingGroupId "{{user.scaling_group_id}}" --InstanceId.1 "{{user.instance_id}}"
aliyun ess ExitStandby --ScalingGroupId "{{user.scaling_group_id}}" --InstanceId.1 "{{user.instance_id}}"

# Health & protection
aliyun ess SetInstanceHealth --InstanceId "{{user.instance_id}}" --HealthStatus "{{user.health_status|Healthy}}"
aliyun ess SetInstancesProtection --ScalingGroupId "{{user.scaling_group_id}}" --InstanceId.1 "{{user.instance_id}}" --ProtectedFromScaleIn "{{user.protected|true}}"

# List instances
aliyun ess DescribeScalingInstances --ScalingGroupId "{{user.scaling_group_id}}"
```

> **RemoveInstances** permanently removes instances. **RemovePolicy:** `OldestInstance`, `NewestInstance`, `OldestScalingConfiguration`.

---

### 9. Load Balancer Association

```bash
# Attach/Detach CLB
aliyun ess AttachLoadBalancers --ScalingGroupId "{{user.scaling_group_id}}" --LoadBalancer.1 "{{user.lb_id}}" --ForceAttach "{{user.force_attach|true}}"
aliyun ess DetachLoadBalancers --ScalingGroupId "{{user.scaling_group_id}}" --LoadBalancer.1 "{{user.lb_id}}" --ForceDetach "{{user.force_detach|false}}"

# Attach/Detach ALB server group
aliyun ess AttachAlbServerGroups --ScalingGroupId "{{user.scaling_group_id}}" --AlbServerGroup.1.AlbServerGroupId "{{user.alb_sg_id}}" --AlbServerGroup.1.Port "{{user.port|80}}" --AlbServerGroup.1.Weight "{{user.weight|100}}"
aliyun ess DetachAlbServerGroups --ScalingGroupId "{{user.scaling_group_id}}" --AlbServerGroup.1.AlbServerGroupId "{{user.alb_sg_id}}"

# Attach/Detach VServerGroup
aliyun ess AttachVServerGroups --ScalingGroupId "{{user.scaling_group_id}}" --VServerGroup.1.LoadBalancerId "{{user.lb_id}}" --VServerGroup.1.VServerGroupAttribute.1.VServerGroupId "{{user.vsg_id}}" --VServerGroup.1.VServerGroupAttribute.1.Port "{{user.port|80}}"

# Attach/Detach RDS
aliyun ess AttachDBInstances --ScalingGroupId "{{user.scaling_group_id}}" --DBInstance.1 "{{user.rds_id}}" --ForceAttach "{{user.force_attach|true}}"
aliyun ess DetachDBInstances --ScalingGroupId "{{user.scaling_group_id}}" --DBInstance.1 "{{user.rds_id}}" --ForceDetach "{{user.force_detach|false}}"
```

---

### 10. Enable/Disable Scaling Group

```bash
aliyun ess EnableScalingGroup \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --ActiveScalingConfigurationId "{{user.scaling_configuration_id}}" \
  --InstanceId.1 "{{user.instance_id}}"

aliyun ess DisableScalingGroup --ScalingGroupId "{{user.scaling_group_id}}"
```

**Validate:** `$.ScalingGroups[0].LifecycleState` should be `Active` / `Inactive`.

---

### 11. Alarm-Based Scaling Rules

```bash
# Create alarm
aliyun ess CreateAlarm \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --Name "{{user.alarm_name}}" \
  --MetricName "{{user.metric_name|CpuUtilization}}" \
  --ComparisonOperator "{{user.comparison_operator|>}}" \
  --Threshold "{{user.threshold|80.0}}" \
  --EvaluationCount "{{user.evaluation_count|3}}" \
  --Period "{{user.period|300}}" \
  --Statistics "{{user.statistics|Average}}" \
  --Dimensions.1.DimensionKey "scaling_group" \
  --Dimensions.1.DimensionValue "{{user.scaling_group_id}}"

aliyun ess DescribeAlarms --ScalingGroupId "{{user.scaling_group_id}}"
aliyun ess EnableAlarm --AlarmTaskId "{{user.alarm_task_id}}"
aliyun ess DisableAlarm --AlarmTaskId "{{user.alarm_task_id}}"
aliyun ess ModifyAlarm --AlarmTaskId "{{user.alarm_task_id}}" --Threshold "{{user.new_threshold}}"
aliyun ess DeleteAlarm --AlarmTaskId "{{user.alarm_task_id}}"
```

> **Alarm state:** `ALARM` (triggering), `OK` (normal), `INSUFFICIENT_DATA`.

---

### 12. Instance Refresh

```bash
# Start refresh
aliyun ess StartInstanceRefresh \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --DesiredConfiguration "{{user.scaling_configuration_id}}" \
  --MaxHealthyPercentage "{{user.max_healthy|100}}" \
  --MinHealthyPercentage "{{user.min_healthy|100}}" \
  --BatchInfo "[{\"BatchSize\":1,\"Percentage\":100}]" \
  --RefreshMode "{{user.refresh_mode|Rollout}}" \
  --RegionId "{{user.region}}"

# Cancel / Query
aliyun ess CancelInstanceRefresh --ScalingGroupId "{{user.scaling_group_id}}" --InstanceRefreshTaskId "{{user.refresh_task_id}}"
aliyun ess DescribeInstanceRefreshes --ScalingGroupId "{{user.scaling_group_id}}" --InstanceRefreshTaskId.1 "{{user.refresh_task_id}}"
```

> ⚠️ **Destructive** — replaces existing instances. Must pass safety gate.

---

### 13. Notification Configuration

```bash
aliyun ess CreateNotificationConfiguration \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --NotificationArn "{{user.notification_arn}}" \
  --NotificationType.1 "autoscaling:SCALE_OUT_SUCCESS" \
  --NotificationType.2 "autoscaling:SCALE_IN_SUCCESS" \
  --NotificationType.3 "autoscaling:SCALE_OUT_ERROR" \
  --NotificationType.4 "autoscaling:SCALE_IN_ERROR"

aliyun ess DescribeNotificationConfigurations --ScalingGroupId "{{user.scaling_group_id}}"
aliyun ess DeleteNotificationConfiguration --ScalingGroupId "{{user.scaling_group_id}}" --NotificationArn "{{user.notification_arn}}"
```

> **NotificationType:** `autoscaling:SCALE_OUT_SUCCESS`, `autoscaling:SCALE_IN_SUCCESS`, `autoscaling:SCALE_OUT_ERROR`, `autoscaling:SCALE_IN_ERROR`, `autoscaling:SCALE_REJECT`, etc.

---

### 14. Tag Management

```bash
aliyun ess TagResources \
  --ResourceType scalinggroup \
  --ResourceId.1 "{{user.scaling_group_id}}" \
  --Tag.1.Key "{{user.tag_key}}" \
  --Tag.1.Value "{{user.tag_value}}"

aliyun ess ListTagResources --ResourceType scalinggroup --ResourceId.1 "{{user.scaling_group_id}}"
aliyun ess UntagResources --ResourceType scalinggroup --ResourceId.1 "{{user.scaling_group_id}}" --TagKey.1 "{{user.tag_key}}"
```

---

### 15. Set Group Deletion Protection

```bash
aliyun ess SetGroupDeletionProtection \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --GroupDeletionProtection true

aliyun ess SetGroupDeletionProtection \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --GroupDeletionProtection false
```

---

### 16. Query Scaling Activities

```bash
aliyun ess DescribeScalingActivities \
  --ScalingGroupId "{{user.scaling_group_id}}" \
  --PageNumber 1 --PageSize 20

aliyun ess DescribeScalingActivityDetail --ScalingActivityId "{{user.scaling_activity_id}}"
```

> Key fields: `StatusCode` (Success/Fail/Rejected), `StatusMessage` (error details).