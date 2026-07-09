# Core Concepts — Auto Scaling (ESS)

> Version: 1.0.0 | Last Updated: 2026-06-07

## Architecture

Auto Scaling (ESS) automatically adjusts compute resources (ECS, ECI, or managed instances) based on scaling policies, scheduled tasks, or health checks.

```
┌─────────────────────────────────────────────────────────┐
│                    Auto Scaling Service                   │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │ ScalingGroup │◄─│ScalingConfig │  │ ScalingRule   │   │
│  │ (伸缩组)      │  │ (伸缩配置)    │  │ (伸缩规则)     │   │
│  └──────┬──────┘  └──────────────┘  └───────┬───────┘   │
│         │                                    │           │
│  ┌──────┴──────┐                    ┌────────┴────────┐ │
│  │  Instances  │                    │ ScheduledTask   │ │
│  │  (实例)      │                    │ LifecycleHook   │ │
│  └─────────────┘                    │ Alarm(CloudMonitor)│
│                                      └─────────────────┘ │
│  ┌─────────────┐  ┌──────────────┐                      │
│  │  CLB/ALB    │  │  Notification │                      │
│  │  (负载均衡)   │  │  (通知)      │                      │
│  └─────────────┘  └──────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

### Resource Hierarchy

1. **ScalingGroup** — Main container; defines min/max/desired capacity, network, region
2. **ScalingConfiguration** — Template for new instances (image, instance type, disk, etc.)
3. **ScalingRule** — Defines scaling action (simple, step, target tracking, predictive)
4. **ScheduledTask** — Triggers a rule on schedule
5. **LifecycleHook** — Pauses instance lifecycle for custom actions
6. **Alarm** — CloudMonitor-based trigger for scaling rules
7. **NotificationConfiguration** — Sends scaling event messages

## Limits & Quotas

Use `aliyun ess DescribeLimitation` to check current quotas:

| Resource | Default Limit | Notes |
|----------|--------------|-------|
| Scaling groups per region | 50 | Request increase via quota center |
| Scaling configurations per group | 100 | Soft limit |
| Scaling rules per group | 50 | All rule types |
| Scheduled tasks per region | 50 | Total across all groups |
| Lifecycle hooks per group | 10 | Max |
| Instances per group (manual + auto) | 2000 | Default; can be increased |
| Instance refreshes per group (concurrent) | 1 | Only one refresh at a time |

## Regions & Endpoints

ESS is available in all Alibaba Cloud regions. Use `DescribeRegions` to list:

```bash
aliyun ess DescribeRegions --AcceptLanguage zh-CN
```

API Endpoint: `ess.aliyuncs.com` (auto-routes to region).

## Resource Relationships

| Resource | Depends On | Impact of Deletion |
|----------|------------|-------------------|
| ScalingConfiguration | ScalingGroup | Cannot scale without active config |
| ScalingRule | ScalingGroup | Auto-scaling stops |
| ScheduledTask | ScalingRule/ScalingGroup | Scheduled scaling stops |
| LifecycleHook | ScalingGroup | Lifecycle events bypass hook |
| NotificationConfiguration | ScalingGroup | No event notifications |
| Alarm | ScalingGroup + CloudMonitor | No alarm-based triggers |

## SPOF Analysis

| Scenario | Impact | Mitigation |
|----------|--------|------------|
| No active scaling config | Scale-out fails; cannot launch new instances | Maintain ≥ 1 active config |
| Group disabled | All scaling activity stops | Enable group |
| Quota full | Cannot create more groups/configs | Request quota increase |
| VSwitch unavailable | Cannot launch instances in that AZ | Multi-AZ with BALANCE policy |
| CloudMonitor down | Alarm based rules don't fire | Use predictive + scheduled rules as backup |

## Billing

ESS service itself is free. You pay for:
- ECS/ECI instances launched by ESS
- CLB/ALB/NLB bandwidth
- CloudMonitor metrics (if using alarm-based rules)
- Data transfer