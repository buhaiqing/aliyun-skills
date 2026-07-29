# Monitoring: ClickHouse

## Cloud Monitor (CMS) Metrics

ApsaraDB for ClickHouse integrates with Alibaba Cloud Monitor (CMS). Key metrics:

| Metric ID | Description | Unit | Recommended Alarm |
|-----------|-------------|------|-------------------|
| `insert_rows_per_second` | Insert rows per second | rows/s | |
| `inserted_rows` | Total inserted rows | count | |
| `inserted_bytes` | Total inserted data volume | bytes | |
| `select_rows_per_second` | Select rows per second | rows/s | |
| `selected_rows` | Total selected rows | count | |
| `selected_bytes` | Total selected data volume | bytes | |
| `query_count` | Query count per second | qps | |
| `failed_query_count` | Failed query count | count/min | > 0 (investigate) |
| `slow_query_count` | Slow queries | count/min | > threshold |
| `connection_usage` | Connection usage | % | > 80% |
| `data_usage` | Data storage usage | bytes | > 80% capacity |
| `cpu_usage` | CPU utilization | % | > 80% for 10min |
| `memory_usage` | Memory utilization | % | > 85% for 10min |
| `disk_usage` | Disk utilization | % | > 80% for 10min |
| `io_util` | I/O utilization | % | > 80% |

> Use `aliyun cms DescribeMetricList --Namespace acs_clickhouse --MetricName cpu_usage` to query metrics programmatically.

## View Metrics via CLI

```bash
# List available metrics
aliyun cms DescribeMetricMetaList --Namespace acs_clickhouse

# Query CPU usage for the last hour (Linux date)
aliyun cms DescribeMetricList \
  --Namespace acs_clickhouse \
  --MetricName cpu_usage \
  --Dimensions '{"instanceId":"ch-xxx"}' \
  --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

## Recommended Alarms

| Alarm | Metric | Threshold | Duration | Action |
|-------|--------|-----------|----------|--------|
| High CPU | `cpu_usage` | > 80% | 600s | Scale up or optimize queries |
| High Memory | `memory_usage` | > 85% | 600s | Scale up or optimize memory-intensive queries |
| High Disk | `disk_usage` | > 80% | 600s | Clean data or scale storage |
| Connection Spike | `connection_usage` | > 80% | 300s | Check application connections |
| Query Failures | `failed_query_count` | > 0 | 60s | Investigate query errors |

## Related CMS Skills

For detailed alarm configuration, use `alicloud-cms-ops`:

```bash
aliyun cms PutResourceMetricRule \
  --Namespace acs_clickhouse \
  --MetricName cpu_usage \
  --RuleName clickhouse-high-cpu \
  --ContactGroups default \
  --Threshold "80" \
  --Statistics Average \
  --Period 300 \
  --EvaluationCount 2
```
