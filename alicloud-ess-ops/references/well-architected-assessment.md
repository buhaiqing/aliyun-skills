# Well-Architected Assessment — Auto Scaling (ESS)

> Version: 1.0.0 | Last Updated: 2026-06-07

## 1. Security (安全)

### 1.1 IAM Requirements

Minimum RAM permissions for ESS operations:

| API Operation | Required RAM Action | Resource Scope |
|---------------|--------------------|----------------|
| CreateScalingGroup | `ess:CreateScalingGroup` | `acs:ess:*:*:scalinggroup/*` |
| DescribeScalingGroups | `ess:DescribeScalingGroups` | `acs:ess:*:*:scalinggroup/*` |
| ModifyScalingGroup | `ess:ModifyScalingGroup` | `acs:ess:*:*:scalinggroup/{{id}}` |
| DeleteScalingGroup | `ess:DeleteScalingGroup` | `acs:ess:*:*:scalinggroup/{{id}}` |
| CreateScalingConfiguration | `ess:CreateScalingConfiguration` | `acs:ess:*:*:scalingconfiguration/*` |
| CreateScalingRule | `ess:CreateScalingRule` | `acs:ess:*:*:scalingrule/*` |
| CreateScheduledTask | `ess:CreateScheduledTask` | `acs:ess:*:*:scheduledtask/*` |
| AttachInstances | `ess:AttachInstances` + `ecs:DescribeInstances` | Instance scope |
| DetachLoadBalancers | `ess:DetachLoadBalancers` + `slb:DescribeLoadBalancers` | LB scope |

### 1.2 Credential Management
- Use dedicated RAM user with ESS-scoped policy (not `AdministratorAccess`)
- Rotate access keys every 90 days
- Prefer STS temporary credentials for automated jobs

### 1.3 Network Security
- Use VPC with private VSwitches for scaling instances
- Avoid attaching scaling groups to Classic network
- Use security groups with minimal inbound/outbound rules

## 2. Stability (稳定)

### 2.1 Multi-AZ Deployment
- Use `MultiAZPolicy: BALANCE` for even AZ distribution
- Specify VSwitches in ≥ 2 AZs when creating scaling group
- Use `COMPOSABLE` for custom capacity distribution across AZs

### 2.2 Health Check & Replacement
- Enable health check on scaling group for automatic unhealthy replacement
- Use lifecycle hooks for custom health checking (e.g., application health)
- Set appropriate `DefaultCooldown` (300-600s) to prevent cascading

### 2.3 Deletion Protection
- Always enable `GroupDeletionProtection` on production scaling groups
- Verify deletion protection before executing delete operations

### 2.4 Disaster Recovery
- Replicate scaling group configurations across regions using templates
- Document RTO/RPO for scaling group recovery:
  - RTO: 5-15 min (time to recreate scaling group + config)
  - RPO: depends on application state (stateless apps: near-zero)

## 3. Cost (成本)

### 3.1 Billing Model Comparison
| Resource | Billing Model | Recommendation |
|----------|--------------|----------------|
| ECS instances in group | Pay-As-You-Go/Spot | Spot for fault-tolerant workloads |
| ECI instances in group | Pay-As-You-Go per second | Short-lived batch jobs |
| Data transfer | Pay-By-Traffic | Use CDN or EIP bandwidth packages |

### 3.2 Cost Optimization Patterns
- **Schedule scale-in during off-peak hours** using scheduled tasks
- **Use Spot instances** for non-critical, fault-tolerant workloads
- **Set realistic MinSize** — don't keep idle instances running
- **Use `PredictiveScalingRule`** for proactive scaling based on history
- **Delete unused scaling configurations** to reduce clutter
- **Right-size instance types** — match workload requirements, not over-provision

### 3.3 Waste Detection
| Pattern | Detection | Action |
|---------|-----------|--------|
| Idle instances | MinSize too high with low utilization | Reduce MinSize |
| Over-provisioned | Large instances at low utilization | Switch to smaller instance type |
| Scale-in failure | Repeated scale-in failures | Check removal policies |

## 4. Efficiency (效率)

### 4.1 Automation Patterns
- **Combined triggers:** scheduled + alarm-based for defense in depth
- **Lifecycle hooks:** integrate with CI/CD for rolling updates
- **Instance refresh:** automate AMI/instance type changes without downtime
- **Notifications:** integrate with ChatOps (DingTalk/WeChat/Feishu)

### 4.2 Batch Operations
- Use `AttachInstances` with multiple `InstanceId.N` parameters
- Use `AttachLoadBalancers` with multiple `LoadBalancer.N` parameters
- Use `TagResources` for batch tagging

### 4.3 CI/CD Integration
- Store scaling configuration templates in Git
- Use OpenAPI/CLI for infrastructure-as-code
- Validate scaling group changes in staging before production

## 5. Performance (性能)

### 5.1 Key Metrics with Thresholds

| Metric | Warning Threshold | Critical Threshold | Action |
|--------|------------------|--------------------|--------|
| Scale-out duration | > 5 min | > 10 min | Check launch template and VSwitch capacity |
| Scale-in duration | > 5 min | > 10 min | Check removal completion |
| Scaling activity failure rate | > 5% | > 10% | Review scaling activity details |
| Instance launch success rate | < 95% | < 90% | Check resource availability in region |

### 5.2 Optimal Scaling Rule Configuration

| Scaling Type | Best For | Cooldown | Considerations |
|-------------|----------|----------|----------------|
| SimpleScalingRule | Basic up/down | 300-600s | Simple, may overshoot |
| StepScalingRule | Load-aware scaling | 60-300s | Gradual, metric-responsive |
| TargetTrackingScalingRule | Metric-driven | Auto-managed | Best for CPU/memory/network |
| PredictiveScalingRule | Cyclic patterns | Auto-managed | Requires 24h+ of history |

### 5.3 Performance Tuning
- **Cooldown tuning:** Reduce cooldown for fast-reacting workloads; increase for volatile workloads
- **Step adjustment granularity:** Use smaller step adjustments for finer control
- **Target tracking:** Use `TargetValue` that aligns with SLOs (e.g., CPU 70%, not 90%)
- **Predictive scaling:** Start with default mode, switch to forecast-only to validate, then enable