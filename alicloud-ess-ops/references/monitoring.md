# Monitoring — Auto Scaling (ESS)

> Version: 1.0.0 | Last Updated: 2026-06-07

## CloudMonitor Metrics

Auto Scaling metrics are available through CloudMonitor (CMS). Key metrics:

| Metric Name | Description | Unit | Dimensions |
|------------|-------------|------|------------|
| `CpuUtilization` | Avg CPU usage of instances in group | % | scaling_group, instanceType |
| `MemoryUtilization` | Avg Memory usage of instances | % | scaling_group, instanceType |
| `IntranetInRate` | Inbound network traffic | bit/s | scaling_group, instanceId |
| `IntranetOutRate` | Outbound network traffic | bit/s | scaling_group, instanceId |
| `DiskReadBPS` | Disk read throughput | byte/s | scaling_group, instanceId |
| `DiskWriteBPS` | Disk write throughput | byte/s | scaling_group, instanceId |
| `GroupCpuUtilization` | Avg CPU across all instances in group | % | scaling_group |
| `GroupMemoryUtilization` | Avg memory across all instances | % | scaling_group |

## Scaling Activity Metrics (Built-in)

ESS provides built-in activity tracking via `DescribeScalingActivities`:

| Metric | Source | Purpose |
|--------|--------|---------|
| Total scaling activities | `DescribeScalingActivities` | Count of all scaling events |
| Success/Fail rate | StatusCode in activities | Health of auto-scaling |
| Active instance count | `DescribeScalingInstances` | Current capacity tracking |
| Average scaling duration | Activity StartTime/EndTime | Performance baseline |

## Suggested CloudMonitor Alarms

| Alarm | Metric | Threshold | Evaluation Period | Action |
|-------|--------|-----------|-------------------|--------|
| High CPU (scale-out trigger) | `GroupCpuUtilization` | > 80% | 5 min × 3 periods | Scale out with step rule |
| Low CPU (scale-in trigger) | `GroupCpuUtilization` | < 20% | 5 min × 3 periods | Scale in with step rule |
| High Memory | `GroupMemoryUtilization` | > 85% | 5 min × 3 periods | Scale out |
| Instance Failure | N/A (health check) | Unhealthy instance count > 0 | Immediate | Replace instance |
| Scale-out Error | `DescribeActivities` StatusCode=Fail | 1 occurrence | Immediate | Alert and retry |

## Dashboard Template

Create a CloudMonitor dashboard for ESS with:

```
Row 1: [GroupCpuUtilization] [GroupMemoryUtilization] [Active Instance Count]
Row 2: [Scale-out Success Rate] [Scale-in Success Rate] [Scaling Frequency]
Row 3: [IntranetInRate] [IntranetOutRate] [DiskReadBPS / DiskWriteBPS]
```

## Notification Configuration

ESS can send scaling event notifications via:

| Target | NotificationArn Format | Use Case |
|--------|----------------------|----------|
| CloudMonitor | `acs:cms:{{region}}:{{account_id}}:contact/{{contact_name}}` | Email/SMS alerts |
| MNS Queue | `acs:mns:{{region}}:{{account_id}}:/queues/{{queue_name}}` | Programmatic processing |
| MNS Topic | `acs:mns:{{region}}:{{account_id}}:/topics/{{topic_name}}` | Pub/Sub notifications |

### Supported Notification Types

| Type | Description |
|------|-------------|
| `autoscaling:SCALE_OUT_SUCCESS` | Scale-out succeeded |
| `autoscaling:SCALE_IN_SUCCESS` | Scale-in succeeded |
| `autoscaling:SCALE_OUT_ERROR` | Scale-out failed |
| `autoscaling:SCALE_IN_ERROR` | Scale-in failed |
| `autoscaling:SCALE_REJECT` | Scaling request rejected |
| `autoscaling:SCHEDULE_SCALE_OUT_SUCCESS` | Scheduled scale-out succeeded |
| `autoscaling:SCHEDULE_SCALE_IN_SUCCESS` | Scheduled scale-in succeeded |
| `autoscaling:SCHEDULE_SCALE_OUT_ERROR` | Scheduled scale-out failed |
| `autoscaling:SCHEDULE_SCALE_IN_ERROR` | Scheduled scale-in failed |