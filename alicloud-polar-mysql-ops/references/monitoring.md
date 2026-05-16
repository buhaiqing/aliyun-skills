# Monitoring & Alerts — PolarDB MySQL

> Version: 1.0.0 | Last Updated: 2026-05-16

## CloudMonitor Namespace

`acs_polardb_dashboard`

## Key Metrics

| Metric | Description | Unit | Typical Threshold |
|--------|-------------|------|-------------------|
| CpuUsage | CPU utilization percentage | % | Warning: > 80%, Critical: > 95% |
| MemoryUsage | Memory utilization percentage | % | Warning: > 80%, Critical: > 95% |
| IOPSUsage | IOPS utilization percentage | % | Warning: > 80%, Critical: > 90% |
| ConnectionUsage | Connection utilization percentage | % | Warning: > 80%, Critical: > 95% |
| DiskUsage | Storage utilization percentage | % | Warning: > 85%, Critical: > 95% |
| TPS | Transactions per second | count/s | Alert on sudden drops |
| QPS | Queries per second | count/s | Alert on sudden drops |
| DiskDataAmount | Data stored on disk | GB | Alert when approaching limit |
| InnodbBufferUsageRatio | InnoDB buffer pool hit ratio | % | Warning: < 90% |
| ActiveSessions | Active sessions count | count | Alert based on workload |
| SlowQueries | Slow query count | count/s | Warning: > 10/h |

## Alarm Configuration

```bash
# Create CPU alarm rule
aliyun cms PutMetricAlarm \
  --Name "PolarDB-MySQL-CPU-Alert" \
  --Namespace acs_polardb_dashboard \
  --MetricName CpuUsage \
  --Dimensions '{"instanceId":"<db_cluster_id>"}' \
  --Statistics Average \
  --ComparisonOperator GreaterThanOrEqualToThreshold \
  --Threshold 85 \
  --NotifyType 0 \
  --ContactGroups "<contact-group>" \
  --SilenceTime 3600
```

## Delegation Points

- For CMS alarm rules → `alicloud-cms-ops`
- For performance diagnosis → `alicloud-das-ops`
- For this skill cluster health check → Follow Cruise workflow in SKILL.md
