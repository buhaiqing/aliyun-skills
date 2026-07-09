# Troubleshooting — Auto Scaling (ESS)

> Version: 1.0.0 | Last Updated: 2026-06-07

## Error Taxonomy

| Error Code | Type | Agent Action | Max Retries |
|------------|------|-------------|-------------|
| InvalidScalingGroupId.NotFound | Config | HALT — verify scaling group ID; list available groups | 0 |
| InvalidScalingConfigurationId.NotFound | Config | HALT — verify configuration ID | 0 |
| ScalingGroup.IncorrectStatus | State | HALT — group must be Active/Inactive for this operation | 0 |
| ScalingGroup.MaxSizeExceeded | Quota | HALT — DesiredCapacity > MaxSize; adjust bounds | 0 |
| QuotaExceeded.ScalingGroup | Quota | HALT — request quota increase via quota center | 0 |
| QuotaExceeded.ScalingConfiguration | Quota | HALT — delete unused configs or request increase | 0 |
| QuotaExceeded.ScalingInstance | Quota | HALT — instance count limit reached | 0 |
| InvalidParameter | Business | FIX — align parameter with OpenAPI spec; retry once | 1 |
| MissingParameter | Config | FIX — add required parameter documented in OpenAPI | 1 |
| InsufficientBalance | Billing | HALT — recharge account; notify user | 0 |
| Throttling.TooManyRequests | Throttle | RETRY — exponential backoff; respect Retry-After | 3 |
| InternalError | Server | RETRY — 2s, 4s, 8s backoff; capture RequestId | 3 |
| ServiceUnavailable | Server | RETRY — 5s, 10s, 20s backoff | 3 |
| InvalidInstanceId.NotFound | Config | HALT — verify ECS instance ID exists in region | 0 |
| IncorrectInstanceStatus | State | HALT — instance must be Running for attach | 0 |
| InstanceAlreadyInScalingGroup | Conflict | HALT — instance already belongs to another group | 0 |
| ScalingActivity.InProgress | Conflict | HALT — wait for current activity to complete | 3 (poll) |
| LifecycleHook.IncorrectStatus | State | HALT — lifecycle hook expired or already completed | 0 |
| InvalidScheduledTaskName.Duplicate | Conflict | FIX — use a different scheduled task name | 1 |
| ScalingRule.InvalidAdjustmentValue | Business | FIX — adjustment value out of range | 1 |
| EipAddress.Insufficient | Resource | HALT — insufficient EIP in region | 0 |
| VpcNotFound | Config | HALT — VPC not found; delegate to VPC ops | 0 |
| VSwitchId.NotAvailable | Resource | HALT — VSwitch not in available status | 0 |
| NoActiveScalingConfiguration | State | HALT — group has no active scaling config; create one first | 0 |
| OperationDenied.NoDefaultVpc | Config | HALT — region has no default VPC; specify VSwitchIds | 0 |

## Diagnostic Process

### Step 1: Identify the Operation and Error
- Check the API response `StatusCode` and `StatusMessage`.
- For scaling activity failures, use `DescribeScalingActivityDetail`:
  ```bash
  aliyun ess DescribeScalingActivityDetail --ScalingActivityId "{{activity_id}}"
  ```

### Step 2: Classify the Error

| Error Type | Characteristics | Action |
|-----------|-----------------|--------|
| **Config** | Invalid IDs, missing parameters | Verify resource existence |
| **State** | Wrong lifecycle state for operation | Wait or transition state first |
| **Quota** | Limits exceeded | Request increase or clean up |
| **Throttle** | Rate-limited | Backoff and retry |
| **Server** | Internal errors | Retry with backoff |
| **Billing** | Insufficient funds | Recharge account |

### Step 3: Apply Recovery

For each error in the taxonomy table above, follow the `Agent Action` column. After recovery, retry the original operation.

### Step 4: Verify Resolution
```bash
# Check scaling group status
aliyun ess DescribeScalingGroups --ScalingGroupId.1 "{{scaling_group_id}}"

# Check recent activities
aliyun ess DescribeScalingActivities --ScalingGroupId "{{scaling_group_id}}" --PageNumber 1 --PageSize 5
```

## Common Failure Scenarios

### Scenario 1: Cannot Delete Scaling Group
**Symptom:** `DeleteScalingGroup` fails with "group has instances" or "scaling activity in progress".

**Diagnosis:**
```bash
# Check instances in group
aliyun ess DescribeScalingInstances --ScalingGroupId "{{group_id}}"

# Check active scaling activities
aliyun ess DescribeScalingActivities --ScalingGroupId "{{group_id}}" --StatusCode InProgress
```

**Resolution:**
1. If instances exist: either `RemoveInstances` first OR use `--ForceDelete true`
2. If activity in progress: wait for completion, then retry
3. If the group is Active: `DisableScalingGroup` first

### Scenario 2: Scale-out Fails
**Symptom:** Instances fail to launch on scale-out events.

**Diagnosis:**
```bash
# Check scaling activity details
aliyun ess DescribeScalingActivityDetail --ScalingActivityId "{{activity_id}}"

# Check available resources
aliyun ess DescribeElasticStrength --RegionId "{{region}}" --InstanceTypes '["{{instance_type}}"]'
```

**Common causes:**
- Insufficient instance type capacity in AZ → use multi-AZ or different instance type
- VSwitch IP exhaustion → request larger VSwitch CIDR blocks
- Security group quota exceeded → clean up security group rules
- Image not found → verify image exists in region

### Scenario 3: Scale-in Removes Wrong Instances
**Symptom:** ESS removed instances user wanted to keep.

**Diagnosis:**
```bash
# Check removal policy
aliyun ess DescribeScalingGroups --ScalingGroupId.1 "{{group_id}}" \
  --output cols=RemovalPolicies rows=ScalingGroups[0].RemovalPolicies
```

**Resolution:**
- Review `RemovalPolicies`: `OldestInstance`, `NewestInstance`, `OldestScalingConfiguration`
- Use `SetInstancesProtection` to protect specific instances
- Use `EnterStandby` to temporarily remove instances from scale-in consideration

### Scenario 4: Scaling Rule Not Triggering
**Symptom:** Alarm-based scaling rule is not firing.

**Diagnosis:**
```bash
# Check alarm state
aliyun ess DescribeAlarms --AlarmTaskId "{{alarm_id}}"

# Check scaling rule exists and is associated
aliyun ess DescribeScalingRules --ScalingRuleId.1 "{{rule_id}}"
```

**Common causes:**
- Alarm is disabled → `EnableAlarm`
- Metric threshold not breached → verify CloudMonitor data exists
- Scaling group is disabled → `EnableScalingGroup`
- Cooldown period active → wait for cooldown to expire

## Logging & Debugging

Use `DescribeScalingActivities` for history:
```bash
# Recent activities (last 10)
aliyun ess DescribeScalingActivities --ScalingGroupId "{{group_id}}" --PageNumber 1 --PageSize 10

# Activities in date range
aliyun ess DescribeScalingActivities --ScalingGroupId "{{group_id}}" \
  --StartTime "2026-06-01T00:00:00Z" --EndTime "2026-06-07T23:59:59Z"
```

Check `StatusCode`: `Success`, `Fail`, `Rejected`, `InProgress`.