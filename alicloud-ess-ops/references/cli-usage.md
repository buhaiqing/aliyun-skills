# CLI Usage — Auto Scaling (`aliyun ess`)

> Version: 1.0.0 | Last Updated: 2026-06-07

## Command Map

### Scaling Group Operations

| Goal | Example |
|------|---------|
| List groups | `aliyun ess DescribeScalingGroups --RegionId {{user.region}}` |
| Get group | `aliyun ess DescribeScalingGroups --ScalingGroupId.1 {{group_id}}` |
| Create group | `aliyun ess CreateScalingGroup --ScalingGroupName "my-group" --MinSize 1 --MaxSize 10 --VSwitchIds "[\"{{vswitch_id}}\"]" --RegionId {{region}}` |
| Modify group | `aliyun ess ModifyScalingGroup --ScalingGroupId {{group_id}} --MaxSize 20` |
| Enable group | `aliyun ess EnableScalingGroup --ScalingGroupId {{group_id}} --ActiveScalingConfigurationId {{config_id}}` |
| Disable group | `aliyun ess DisableScalingGroup --ScalingGroupId {{group_id}}` |
| Delete group | `aliyun ess DeleteScalingGroup --ScalingGroupId {{group_id}} --ForceDelete true` **Destructive** |
| Set del protection | `aliyun ess SetGroupDeletionProtection --ScalingGroupId {{group_id}} --GroupDeletionProtection true` |
| Check limits | `aliyun ess DescribeLimitation` |
| Extract fields | `aliyun ess DescribeScalingGroups --RegionId {{region}} --output cols=ScalingGroupId,Name,State,MinSize,MaxSize rows=ScalingGroups[].{ScalingGroupId,ScalingGroupName,LifecycleState,MinSize,MaxSize}` |

### Scaling Configuration Operations

| Goal | Example |
|------|---------|
| Create config | `aliyun ess CreateScalingConfiguration --ScalingGroupId {{group_id}} --ImageId {{image_id}} --InstanceType ecs.g7.large --ScalingConfigurationName "my-config"` |
| Create ECI config | `aliyun ess CreateEciScalingConfiguration --ScalingGroupId {{group_id}} --ImageId {{image_id}} --Cpu 2 --Memory 4` |
| List configs | `aliyun ess DescribeScalingConfigurations --ScalingGroupId {{group_id}}` |
| Set as active | `aliyun ess ModifyScalingGroup --ScalingGroupId {{group_id}} --ActiveScalingConfigurationId {{config_id}}` |
| Deactivate | `aliyun ess DeactivateScalingConfiguration --ScalingConfigurationId {{config_id}}` |
| Delete config | `aliyun ess DeleteScalingConfiguration --ScalingConfigurationId {{config_id}}` |

### Scaling Rule Operations

| Goal | Example |
|------|---------|
| Create simple rule | `aliyun ess CreateScalingRule --ScalingGroupId {{group_id}} --ScalingRuleName "scale-out" --AdjustmentType QuantityChangeInCapacity --AdjustmentValue 1 --Cooldown 300` |
| Create target tracking | `aliyun ess CreateScalingRule --ScalingGroupId {{group_id}} --ScalingRuleName "cpu-tracking" --ScalingRuleType TargetTrackingScalingRule --MetricName CpuUtilization --TargetValue 80.0` |
| Create step rule | `aliyun ess CreateScalingRule --ScalingGroupId {{group_id}} --ScalingRuleType StepScalingRule --AdjustmentType QuantityChangeInCapacity --StepAdjustments "[{\\\"MetricIntervalLowerBound\\\":0,\\\"ScalingAdjustment\\\":1}]"` |
| List rules | `aliyun ess DescribeScalingRules --ScalingGroupId {{group_id}}` |
| Execute rule | `aliyun ess ExecuteScalingRule --ScalingRuleAri {{rule_ari}} --ClientToken {{uuid}}` |
| Delete rule | `aliyun ess DeleteScalingRule --ScalingRuleId {{rule_id}}` |

### Scheduled Task Operations

| Goal | Example |
|------|---------|
| Create daily task | `aliyun ess CreateScheduledTask --ScheduledTaskName "scale-up-morning" --ScheduledAction {{rule_ari}} --LaunchTime "2026-06-08T08:00:00Z" --RecurrenceType Daily --RecurrenceValue 1 --TaskEnabled true` |
| Create cron task | `aliyun ess CreateScheduledTask --ScheduledTaskName "weekday-scale" --ScheduledAction {{rule_ari}} --RecurrenceType Cron --RecurrenceValue "0 9 * * 1-5"` |
| List tasks | `aliyun ess DescribeScheduledTasks --RegionId {{region}}` |
| Modify task | `aliyun ess ModifyScheduledTask --ScheduledTaskId {{task_id}} --LaunchTime "2026-07-01T08:00:00Z"` |
| Delete task | `aliyun ess DeleteScheduledTask --ScheduledTaskId {{task_id}}` |

### Lifecycle Hook Operations

| Goal | Example |
|------|---------|
| Create hook | `aliyun ess CreateLifecycleHook --ScalingGroupId {{group_id}} --LifecycleHookName "my-hook" --LifecycleTransition "Autoscaling:EC2Instance-Launching" --HeartbeatTimeout 600 --DefaultResult CONTINUE` |
| List hooks | `aliyun ess DescribeLifecycleHooks --ScalingGroupId {{group_id}}` |
| Complete action | `aliyun ess CompleteLifecycleAction --LifecycleHookId {{hook_id}} --LifecycleActionResult CONTINUE --InstanceId {{instance_id}}` |
| Heartbeat | `aliyun ess RecordLifecycleActionHeartbeat --LifecycleHookId {{hook_id}} --InstanceId {{instance_id}}` |
| Delete hook | `aliyun ess DeleteLifecycleHook --LifecycleHookId {{hook_id}} --ScalingGroupId {{group_id}}` |

### Instance Management

| Goal | Example |
|------|---------|
| List instances | `aliyun ess DescribeScalingInstances --ScalingGroupId {{group_id}}` |
| Attach instances | `aliyun ess AttachInstances --ScalingGroupId {{group_id}} --InstanceId.1 {{instance_id_1}} --InstanceId.2 {{instance_id_2}} --Entrusted true` |
| Detach instances | `aliyun ess DetachInstances --ScalingGroupId {{group_id}} --InstanceId.1 {{instance_id}}` |
| Remove instances | `aliyun ess RemoveInstances --ScalingGroupId {{group_id}} --InstanceId.1 {{instance_id}}` **Destructive** |
| Enter standby | `aliyun ess EnterStandby --ScalingGroupId {{group_id}} --InstanceId.1 {{instance_id}}` |
| Exit standby | `aliyun ess ExitStandby --ScalingGroupId {{group_id}} --InstanceId.1 {{instance_id}}` |
| Set health | `aliyun ess SetInstanceHealth --InstanceId {{instance_id}} --HealthStatus Unhealthy` |
| Set protection | `aliyun ess SetInstancesProtection --ScalingGroupId {{group_id}} --InstanceId.1 {{instance_id}} --ProtectedFromScaleIn true` |

### Load Balancer Association

| Goal | Example |
|------|---------|
| Attach CLB | `aliyun ess AttachLoadBalancers --ScalingGroupId {{group_id}} --LoadBalancer.1 {{lb_id}} --ForceAttach true` |
| Detach CLB | `aliyun ess DetachLoadBalancers --ScalingGroupId {{group_id}} --LoadBalancer.1 {{lb_id}}` |
| Attach ALB | `aliyun ess AttachAlbServerGroups --ScalingGroupId {{group_id}} --AlbServerGroup.1.AlbServerGroupId {{alb_sg_id}} --AlbServerGroup.1.Port 80 --AlbServerGroup.1.Weight 100` |
| Detach ALB | `aliyun ess DetachAlbServerGroups --ScalingGroupId {{group_id}} --AlbServerGroup.1.AlbServerGroupId {{alb_sg_id}}` |
| Attach DB | `aliyun ess AttachDBInstances --ScalingGroupId {{group_id}} --DBInstance.1 {{rds_id}}` |

### Notification Configuration

| Goal | Example |
|------|---------|
| Create notification | `aliyun ess CreateNotificationConfiguration --ScalingGroupId {{group_id}} --NotificationArn {{arn}} --NotificationType.1 "autoscaling:SCALE_OUT_SUCCESS" --NotificationType.2 "autoscaling:SCALE_IN_SUCCESS"` |
| List notifications | `aliyun ess DescribeNotificationConfigurations --ScalingGroupId {{group_id}}` |
| Delete notification | `aliyun ess DeleteNotificationConfiguration --ScalingGroupId {{group_id}} --NotificationArn {{arn}}` |

### Instance Refresh

| Goal | Example |
|------|---------|
| Start refresh | `aliyun ess StartInstanceRefresh --ScalingGroupId {{group_id}} --DesiredConfiguration {{config_id}} --MinHealthyPercentage 100 --BatchInfo "[{\\\"BatchSize\\\":1,\\\"Percentage\\\":100}]"` |
| Query refresh | `aliyun ess DescribeInstanceRefreshes --ScalingGroupId {{group_id}} --InstanceRefreshTaskId.1 {{task_id}}` |
| Cancel refresh | `aliyun ess CancelInstanceRefresh --ScalingGroupId {{group_id}} --InstanceRefreshTaskId {{task_id}}` |

### Alarm Operations

| Goal | Example |
|------|---------|
| Create alarm | `aliyun ess CreateAlarm --ScalingGroupId {{group_id}} --Name "cpu-high" --MetricName CpuUtilization --ComparisonOperator ">" --Threshold 80 --EvaluationCount 3 --Period 300 --Statistics Average --Dimensions.1.DimensionKey "scaling_group" --Dimensions.1.DimensionValue {{group_id}}` |
| List alarms | `aliyun ess DescribeAlarms --ScalingGroupId {{group_id}}` |
| Enable alarm | `aliyun ess EnableAlarm --AlarmTaskId {{alarm_id}}` |
| Disable alarm | `aliyun ess DisableAlarm --AlarmTaskId {{alarm_id}}` |
| Delete alarm | `aliyun ess DeleteAlarm --AlarmTaskId {{alarm_id}}` |

### Tag Operations

| Goal | Example |
|------|---------|
| Tag resource | `aliyun ess TagResources --ResourceType scalinggroup --ResourceId.1 {{group_id}} --Tag.1.Key "env" --Tag.1.Value "prod"` |
| List tags | `aliyun ess ListTagResources --ResourceType scalinggroup --ResourceId.1 {{group_id}}` |
| Untag | `aliyun ess UntagResources --ResourceType scalinggroup --ResourceId.1 {{group_id}} --TagKey.1 "env"` |

### Infrastructure

| Goal | Example |
|------|---------|
| List regions | `aliyun ess DescribeRegions --AcceptLanguage zh-CN` |
| Elastic strength | `aliyun ess DescribeElasticStrength --RegionId {{region}} --InstanceTypes "[\\\"ecs.g7.large\\\"]" --SystemDiskCategory cloud_essd` |
| Check auth | `aliyun ess VerifyAuthentication` |

## Coverage Gap (SDK-only)

All major ESS operations are available via CLI. The following edge-case operations may require SDK:

| Operation | Reason |
|-----------|--------|
| Complex Tag filter queries | SDK provides richer type system |
| Custom pagination loops with SDK state | SDK for scripted automation |
| Multi-step orchestration (create group → config → rule → enable) | SDK for atomic transactions |

## CLI JSON Output Notes

- Default output format is JSON (no `--output json` needed).
- Use `--output cols=... rows=...` for JMESPath column extraction.
- Indexed array parameters: `InstanceId.1`, `InstanceId.2`, `LoadBalancer.1`.
- Use `--ClientToken` for idempotency.