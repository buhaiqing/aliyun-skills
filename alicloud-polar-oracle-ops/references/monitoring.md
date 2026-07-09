# Monitoring & Alerts — PolarDB Oracle-compatible (IO)

> Version: 1.0.0 | Last Updated: 2026-05-16

## CloudMonitor Namespace

`acs_polardb_io_dashboard`

## Key Metrics

| Metric | Description | Threshold |
|--------|-------------|-----------|
| CpuUsage | CPU utilization | Warning: > 80%, Critical: > 95% |
| MemoryUsage | Memory utilization | Warning: > 80%, Critical: > 95% |
| IOPSUsage | IOPS utilization | Warning: > 80% |
| ConnectionUsage | Connection utilization | Warning: > 80%, Critical: > 95% |
| TPS | Transactions per second | Alert on sudden drops |
| QPS | Queries per second | Alert on sudden drops |

## Delegation Points

- For CMS alarm rules → `alicloud-cms-ops`
- For performance diagnosis → `alicloud-das-ops`
