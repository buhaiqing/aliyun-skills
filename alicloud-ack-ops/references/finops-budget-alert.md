# ACK Budget Alert Integration

Configure cluster cost budget threshold alerts via CloudMonitor.

## Alert Configuration

```bash
aliyun cms PutMetricRuleTargets \
  --RuleId "ack-cost-alert" \
  --Namespace "acs_user_dashboard" \
  --MetricName "cluster_monthly_cost" \
  --Threshold "500" \
  --ComparisonOperator "GreaterThanThreshold" \
  --Statistics "Average" \
  --Period "86400" \
  --ContactGroups "ops-team"
```

## Alert Rules

| Alert | Threshold | Severity | Response |
|-------|-----------|----------|----------|
| 月度成本超标 | >80% budget | P2 | Review resources, identify waste |
| 日成本激增 | >150% baseline | P3 | Check auto-scaling activity |
| 闲置资源累积 | >3 idle nodes | P3 | Clean up idle resources |