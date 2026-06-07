# API & SDK Usage — Auto Scaling (ESS)

> Version: 1.0.0 | Last Updated: 2026-06-07

## OpenAPI

- **Service Endpoint:** `ess.aliyuncs.com`
- **API Version:** 2014-08-28
- **Official Documentation:** https://help.aliyun.com/zh/auto-scaling/developer-reference/api-ess-2014-08-28-overview

## Go SDK

- **Package:** `github.com/alibabacloud-go/ess-20140828/v2/client`
- **OpenAPI:** `github.com/alibabacloud-go/darabonba-openapi/v2/client`
- **Tea:** `github.com/alibabacloud-go/tea/tea`

> JIT Go SDK client template & JIT workflow in [`integration.md`](integration.md).

## SDK Operations Map

### Scaling Group Operations

| Goal | API OperationId | Notes |
|------|-----------------|-------|
| Create | `CreateScalingGroup` | Requires VSwitchIds or LoadBalancer |
| List | `DescribeScalingGroups` | Pagination: PageNumber + PageSize |
| Modify | `ModifyScalingGroup` | Change name, capacity, cooldown, policies |
| Enable | `EnableScalingGroup` | Requires active config |
| Disable | `DisableScalingGroup` | Stops all scaling activities |
| Delete | `DeleteScalingGroup` | **Destructive** — requires safety gate; ForceDelete optional |
| Apply | `ApplyScalingGroup` | Applies scaling configuration changes |
| Set deletion protection | `SetGroupDeletionProtection` | true/false |
| Change resource group | `ChangeResourceGroup` | Move to different resource group |
| Describe limitation | `DescribeLimitation` | Check quotas |

### Scaling Configuration Operations

| Goal | API OperationId | Notes |
|------|-----------------|-------|
| Create (ECS) | `CreateScalingConfiguration` | ImageId + InstanceType required |
| Create (ECI) | `CreateEciScalingConfiguration` | Cpu + Memory or ImageId |
| List | `DescribeScalingConfigurations` | Filter by scaling group |
| Modify (ECS) | `ModifyScalingConfiguration` | Update any config field |
| Modify (ECI) | `ModifyEciScalingConfiguration` | Update ECI config fields |
| Deactivate | `DeactivateScalingConfiguration` | Set lifecycle to Inactive |
| Delete | `DeleteScalingConfiguration` | Cannot delete active config |
| Delete (ECI) | `DeleteEciScalingConfiguration` | Delete ECI config |

### Scaling Rule Operations

| Goal | API OperationId | Notes |
|------|-----------------|-------|
| Create | `CreateScalingRule` | Type: Simple/Step/TargetTracking/Predictive |
| List | `DescribeScalingRules` | Filter by group or rule IDs |
| Modify | `ModifyScalingRule` | Change adjustment, cooldown, thresholds |
| Execute | `ExecuteScalingRule` | Returns ScalingActivityId |
| Delete | `DeleteScalingRule` | Banned if referenced by scheduled task |

### Scheduled Task Operations

| Goal | API OperationId | Notes |
|------|-----------------|-------|
| Create | `CreateScheduledTask` | Recurrence: Daily/Weekly/Monthly/Cron |
| List | `DescribeScheduledTasks` | Filter by group, task IDs, or name |
| Modify | `ModifyScheduledTask` | Update schedule or action |
| Delete | `DeleteScheduledTask` | |

### Lifecycle Hook Operations

| Goal | API OperationId | Notes |
|------|-----------------|-------|
| Create | `CreateLifecycleHook` | Transition: Launching/Terminating |
| List | `DescribeLifecycleHooks` | Filter by group or hook IDs |
| Modify | `ModifyLifecycleHook` | Change timeout, result, notification |
| Complete | `CompleteLifecycleAction` | CONTINUE or ABANDON |
| Record heartbeat | `RecordLifecycleActionHeartbeat` | Extend waiting period |
| Delete | `DeleteLifecycleHook` | |

### Alarm Operations

| Goal | API OperationId | Notes |
|------|-----------------|-------|
| Create | `CreateAlarm` | CloudMonitor metric-based alarm |
| List | `DescribeAlarms` | Filter by group or alarm IDs |
| Modify | `ModifyAlarm` | Change threshold, comparison, period |
| Enable | `EnableAlarm` | Activate alarm |
| Disable | `DisableAlarm` | Deactivate alarm |
| Delete | `DeleteAlarm` | |

### Instance Management Operations

| Goal | API OperationId | Notes |
|------|-----------------|-------|
| List instances | `DescribeScalingInstances` | Filter by group, instance IDs |
| Attach | `AttachInstances` | Add existing ECS/ECI to group |
| Detach | `DetachInstances` | Remove from group without releasing |
| Remove | `RemoveInstances` | **Destructive** — permanently remove/release |
| Enter standby | `EnterStandby` | Pause instance; no traffic |
| Exit standby | `ExitStandby` | Resume normal operation |
| Set health status | `SetInstanceHealth` | Healthy/Unhealthy |
| Set protection | `SetInstancesProtection` | ProtectedFromScaleIn true/false |

### Load Balancer Operations

| Goal | API OperationId | Notes |
|------|-----------------|-------|
| Attach CLB | `AttachLoadBalancers` | ForceAttach optional |
| Detach CLB | `DetachLoadBalancers` | ForceDetach optional |
| Attach ALB | `AttachAlbServerGroups` | ALB server group |
| Detach ALB | `DetachAlbServerGroups` | |
| Attach VServerGroup | `AttachVServerGroups` | CLB VServerGroup |
| Detach VServerGroup | `DetachVServerGroups` | |
| Attach ServerGroup | `AttachServerGroups` | ALB/NLB server group |
| Detach ServerGroup | `DetachServerGroups` | |
| Attach DB | `AttachDBInstances` | RDS instances |
| Detach DB | `DetachDBInstances` | |

### Notification Operations

| Goal | API OperationId | Notes |
|------|-----------------|-------|
| Create | `CreateNotificationConfiguration` | With NotificationTypes |
| List | `DescribeNotificationConfigurations` | |
| List types | `DescribeNotificationTypes` | |
| Delete | `DeleteNotificationConfiguration` | |

### Instance Refresh Operations

| Goal | API OperationId | Notes |
|------|-----------------|-------|
| Start | `StartInstanceRefresh` | Requires DesiredConfiguration |
| Cancel | `CancelInstanceRefresh` | |
| Resume | `ResumeInstanceRefresh` | Resume paused refresh |
| Suspend | `SuspendInstanceRefresh` | Pause refresh |
| Rollback | `RollbackInstanceRefresh` | Rollback to previous config |
| Query | `DescribeInstanceRefreshes` | |

### Tag & Utility Operations

| Goal | API OperationId | Notes |
|------|-----------------|-------|
| Tag resources | `TagResources` | |
| Untag resources | `UntagResources` | |
| List tag keys | `ListTagKeys` | |
| List tag values | `ListTagValues` | |
| List tagged resources | `ListTagResources` | |
| Describe regions | `DescribeRegions` | |
| Describe elastic strength | `DescribeElasticStrength` | Regional capacity check |
| Verify auth | `VerifyAuthentication` / `VerifyUser` | Credential validation |
| Rebalance instances | `RebalanceInstances` | Rebalance across zones |

## Request / Response Notes

- **Pagination:** Use `PageNumber` + `PageSize` (default 10, max 50). Response includes `TotalCount`.
- **ClientToken:** All write operations support idempempotency via `ClientToken`. Always generate UUID v4.
- **Async operations:** Scaling activities are async. The response includes `ScalingActivityId`. Poll with `DescribeScalingActivities`.
- **Array parameters:** ESS uses indexed array syntax (e.g., `InstanceId.1`, `InstanceId.2`, `ScalingGroupId.1`).
- **JSON arrays:** Some newer operations (TagResources) use JSON-encoded arrays.

## Go SDK Template

```go
package main

import (
    "fmt"
    "os"
    "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    ess "github.com/alibabacloud-go/ess-20140828/v2/client"
    "github.com/alibabacloud-go/tea/tea"
)

func main() {
    // Read credentials from env
    config := &client.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    essClient, err := ess.NewClient(config)
    if err != nil {
        panic(err)
    }
    // ... operation code
}
```

> ⚠️ **DANGER:** `config` structs and `fmt.Println(config)` can leak credentials.
> NEVER echo, log, or print the config or credential values.