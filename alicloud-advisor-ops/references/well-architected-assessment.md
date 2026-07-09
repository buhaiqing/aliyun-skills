# Advisor — Well-Architected Assessment

> **Five-pillar assessment for the Advisor skill itself.** Advisor
> consumes Alibaba Cloud's Well-Architected Framework and surfaces
> findings across all five pillars; this document describes how to
> consume those findings through the `alicloud advisor` API.

Reference: [Alibaba Cloud Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).

## Pillar Overview

| Pillar | Advisor Coverage | API Surface |
|--------|------------------|-------------|
| **Security** | Security group misconfigurations, exposed ports, missing encryption | `DescribeAdvices` (filter `Category=Security`) |
| **Stability** | Single points of failure, missing backups, no redundancy | `DescribeAdvices` (filter `Category=Stability`) |
| **Cost** | Idle/oversized resources, savings estimates | `DescribeCostCheckAdvices`, `DescribeCostOptimizationOverview` |
| **Efficiency** | Underutilized resources, right-sizing | `DescribeAdvices` (filter `Category=Performance`) |
| **Performance** | High latency, throughput bottlenecks | `DescribeAdvices` (filter `Category=Performance`) |

## Security (安全)

Advisor's security checks include:

- ECS / RDS / SLB security group rules with `0.0.0.0/0` for sensitive
  ports (22, 3389, 3306, 1433, etc.).
- OSS buckets with public read/write access.
- RDS instances without TLS / audit log enabled.
- RAM users with overly broad policies.
- ActionTrail not enabled / delivery not configured.

### Workflow

```bash
# 1. Get all security-related advices
aliyun advisor describe-advices-page \
  --page-number 1 \
  --page-size 100 \
  | jq '.Advices[] | select(.CheckId | startswith("Ecs.SecurityGroup"))'

# 2. Triage by severity, drill into specific resources
# 3. Delegate to alicloud-ecs-ops (or relevant skill) for remediation
# 4. Re-trigger inspection to confirm fix
aliyun advisor refresh-advisor-resource --product Ecs --resource-id sg-xxx
```

### Key Check IDs (Security)

| Check ID | Risk |
|----------|------|
| `Ecs.SecurityGroup.OpenPort22` | SSH exposed to internet |
| `Ecs.SecurityGroup.OpenPort3389` | RDP exposed to internet |
| `Rds.SecurityGroup.OpenPort3306` | MySQL exposed to internet |
| `Oss.Bucket.PublicRead` | OSS bucket public-readable |
| `Ram.User.NoMfa` | RAM user without MFA |
| `ActionTrail.NotEnabled` | Audit trail disabled |

## Stability (稳定)

Advisor's stability checks include:

- ECS without snapshot / image backup.
- Single-AZ deployments for critical workloads.
- No multi-instance deployment for stateful services.
- Missing auto-scaling configuration.
- Database without high-availability edition.

### Workflow

```bash
# Get stability advices
aliyun advisor describe-advices-page \
  --page-number 1 \
  --page-size 100 \
  | jq '.Advices[] | select(.CheckId | contains("Snapshot") or contains("Backup") or contains("Single"))'
```

### Key Check IDs (Stability)

| Check ID | Risk |
|----------|------|
| `Ecs.Disk.NoSnapshot` | Disk has no automatic snapshot |
| `Rds.NoHighAvailability` | RDS is single-node |
| `Slb.SingleInstance` | SLB not in HA mode |
| `Ecs.SingleAz` | All instances in one AZ |

## Cost (成本)

This is Advisor's strongest pillar. The cost optimization API surface
provides actionable savings estimates.

### Workflow

```bash
# 1. Get top-level savings estimate
aliyun advisor describe-cost-optimization-overview

# 2. Drill into specific categories
aliyun advisor describe-cost-check-advices \
  --severity Critical \
  --page-number 1 --page-size 50

# 3. Aggregate by check item
aliyun advisor describe-cost-check-results --group-by Check

# 4. Apply fixes (delegate to per-product skills)
# Example: idle ECS
aliyun advisor describe-cost-check-advices \
  --product Ecs \
  | jq '.Advices[] | select(.CheckId == "Ecs.IdleInstance")'
# → delegate to alicloud-ecs-ops for DeleteInstance or StopInstance
```

### Key Check IDs (Cost)

| Check ID | Action | Typical Savings |
|----------|--------|-----------------|
| `Ecs.IdleInstance` | Stop or release idle ECS | Variable |
| `Ecs.OversizedInstance` | Downgrade spec | 30-50% of instance cost |
| `Rds.Oversized` | Downgrade RDS spec | 30-50% of RDS cost |
| `Oss.ColdData` | Tier to IA / Archive | 60-80% storage cost |
| `Eip.Unattached` | Release unused EIP | EIP hourly cost |
| `Nat.IdleGateway` | Release unused NAT | NAT hourly cost |

### Cost Optimization Decision Tree

```
For each cost advice:
  Is the resource actively used? (check CMS metrics)
    No → Release / Delete
    Yes but low utilization (<20%):
      Is it stateless? → Right-size down
      Is it stateful? → Investigate why (cache, baseline)
    Yes with high utilization:
      Check ReservedInstance / SavingsPlan coverage
      Consider subscription (1yr/3yr) for stable workloads
```

## Efficiency (效率)

Advisor's efficiency / right-sizing checks overlap with cost but
focus on **utilization**, not monetary savings:

- CPU < 20% over 7 days → consider downgrade.
- Memory < 30% over 7 days → consider smaller spec.
- Network IO < 5% → consider shared instance type.

### Workflow

```bash
# Get efficiency advices (filter Performance category with cost dimension)
aliyun advisor describe-advices \
  --product Ecs
# Filter client-side by description containing "low utilization" or similar
```

## Performance (性能)

Advisor's performance checks include:

- High latency on RDS / Redis / SLB.
- Connection pool exhaustion risk.
- IOPS saturation on EBS.
- Network bandwidth ceiling reached.

### Workflow

```bash
# Get performance advices
aliyun advisor describe-advices-page \
  --page-number 1 --page-size 100 \
  | jq '.Advices[] | select(.Category == "Performance")'

# For each advice, drill into the underlying metric
# Delegate to alicloud-cms-ops with the metric from the advice
```

## Cross-Pillar Trade-offs

Some checks pull across pillars:

- **Oversized instance** (Cost) vs **Performance baseline** (Efficiency):
  downgrading may hurt performance. Always check both.
- **Stability** (multi-AZ, HA) vs **Cost** (more resources = more cost):
  balance via risk tolerance.
- **Security** (encryption, audit) vs **Cost** (encrypted storage costs more):
  security wins unless budget is critical.

Advisor does **not** resolve these trade-offs; it surfaces them and
the user (or the agent) makes the call.

## Severity Mapping (WA Framework → Advisor)

| Well-Architected Severity | Advisor Severity |
|--------------------------|------------------|
| Critical (security breach imminent) | `Critical` |
| High (stability risk, performance degradation) | `Warning` |
| Medium (best practice violation) | `Info` |
| Low (cost optimization opportunity) | `Info` / `Warning` (depending on savings %) |

## Audit Trail Integration

For compliance, Advisor findings should be:

1. Captured in ActionTrail (Advisor reads the same resources, so
   ActionTrail will reflect user's remediation actions).
2. Stored in OSS / SLS for long-term retention.
3. Routed to a ticketing system for tracking.

```bash
# Example: cross-check Advisor fix with ActionTrail
# After fixing a security group issue:
aliyun advisor refresh-advisor-resource --product Ecs --resource-id sg-xxx
# Wait 1 minute
# Then verify the revocation event in ActionTrail
aliyun actiontrail LookupEvents \
  --EventName RevokeSecurityGroup \
  --ServiceName Ecs \
  --StartTime 2026-06-06T00:00:00Z \
  --EndTime 2026-06-06T23:59:59Z
```

## Reporting and Dashboards

Common dashboards built from Advisor:

| Dashboard | Data Source | Refresh |
|-----------|-------------|---------|
| Account Health Overview | `DescribeAdvices` (counts by severity) | Hourly |
| Cost Savings Tracker | `DescribeCostOptimizationOverview` | Daily |
| Top 10 Risks | `DescribeAdvices` (top 10 by Severity, ResourceId) | Hourly |
| Cost Trend | `GetHistoryAdvices` (severity=Info, cost-related) | Daily |
| Inspection Coverage | `DescribeAdvisorResources` (count by product) | Daily |

## Reference

- [Alibaba Cloud Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html)
- [Advisor severity levels](https://help.aliyun.com/zh/advisor/user-guide/severity-levels)
- [Advisor cost check items](https://help.aliyun.com/zh/advisor/user-guide/cost-check-items)
