# Monitoring & Alerts — Alibaba Cloud Redis / Tair (KVStore)

## Monitoring Overview

Alibaba Cloud Redis / Tair provides built-in monitoring through CloudMonitor and API-based metric retrieval. This document covers monitoring dimensions, key metrics, alert thresholds, and automated monitoring flows.

## Metric Collection

### Primary API: DescribeHistoryMonitorValues

```bash
aliyun r-kvstore describe-history-monitor-values \
  --InstanceId "{{user.instance_id}}" \
  --MonitorKeys "UsedMemory,UsedConnection,CpuUsage" \
  --StartTime "2026-05-14T00:00:00Z" \
  --EndTime "2026-05-14T23:59:59Z"
```

### Available Monitor Keys

| Category | Monitor Key | Unit | Description |
|----------|-------------|------|-------------|
| **Memory** | `UsedMemory` | bytes | Used memory |
| | `MemoryUsage` | % | Memory utilization |
| | `Keys` | count | Total key count |
| | `ExpiredKeys` | count | Expired key count |
| | `EvictedKeys` | count | Evicted key count |
| **CPU** | `CpuUsage` | % | CPU utilization |
| **Connections** | `UsedConnection` | count | Used connections |
| | `ConnectionUsage` | % | Connection usage percentage |
| **Throughput** | `UsedQPS` | count/s | Queries per second |
| | `IntranetIn` | bytes/s | Inbound traffic |
| | `IntranetOut` | bytes/s | Outbound traffic |
| | `InFlow` | bytes/s | Inbound flow |
| | `OutFlow` | bytes/s | Outbound flow |
| **Bandwidth** | `IntranetInRatio` | % | Inbound bandwidth usage |
| | `IntranetOutRatio` | % | Outbound bandwidth usage |
| **Latency** | `AvgRt` | microseconds | Average response time |
| | `MaxRt` | microseconds | Max response time |
| **Cache** | `HitRate` | % | Cache hit rate |
| **Errors** | `FailedCount` | count | Failed command count |
| **Replication** | `DataDelay` | seconds | Data replication delay |

> Use `DescribeMonitorItems` to get the exact list of available metrics for a specific instance, as available metrics vary by instance type and architecture.

## Key Performance Indicators (KPIs)

### Critical KPIs

| KPI | Warning Threshold | Critical Threshold | Action |
|-----|-------------------|-------------------|--------|
| CPU Usage | > 70% | > 85% | Scale up or optimize queries |
| Memory Usage | > 75% | > 90% | Scale up, enable eviction, or optimize data |
| Connection Usage | > 70% | > 85% | Scale up or optimize connection pooling |
| Average Latency | > 5ms | > 20ms | Investigate slow queries, scale up, or optimize |
| Cache Hit Rate | < 85% | < 70% | Review caching strategy |
| Replication Delay | > 1s | > 5s | Investigate network or instance load |
| Failed Commands | > 0.1% | > 1% | Investigate errors and capacity |

### Business KPIs

| KPI | Target | Measurement |
|-----|--------|-------------|
| Availability | 99.99% | Instance `Normal` status uptime |
| Backup Success Rate | 100% | `DescribeBackups` → `BackupStatus` = `Success` |
| Recovery Time Objective (RTO) | < 30 min | Time from failure to restored service |
| Recovery Point Objective (RPO) | < 1 hour | Time since last successful backup |

## Automated Monitoring Flows

### Flow: Instance Health Check

```bash
#!/bin/bash
# Automated health check script

INSTANCE_ID="{{user.instance_id}}"
REGION_ID="{{user.region}}"

# Check instance status
STATUS=$(aliyun r-kvstore describe-instances \
  --RegionId "$REGION_ID" \
  --InstanceId "$INSTANCE_ID" \
  --output cols=InstanceStatus rows=Instances.KVStoreInstance[0].InstanceStatus)

if [ "$STATUS" != "Normal" ]; then
  echo "ALERT: Instance status is $STATUS"
  exit 1
fi

# Check key metrics
METRICS=$(aliyun r-kvstore describe-history-monitor-values \
  --InstanceId "$INSTANCE_ID" \
  --MonitorKeys "CpuUsage,MemoryUsage,ConnectionUsage,AvgRt" \
  --StartTime "$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-5M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)")

# Parse and alert on thresholds
# (Add threshold checking logic based on metric values)

echo "Health check passed"
```

### Flow: Daily Performance Report

```bash
#!/bin/bash
# Daily performance report

INSTANCE_ID="{{user.instance_id}}"
START_TIME="$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Collect metrics
METRICS=$(aliyun r-kvstore describe-history-monitor-values \
  --InstanceId "$INSTANCE_ID" \
  --MonitorKeys "CpuUsage,MemoryUsage,UsedQPS,AvgRt,HitRate" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME")

# Collect slow logs
SLOW_LOGS=$(aliyun r-kvstore describe-slow-logs \
  --InstanceId "$INSTANCE_ID" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME")

# Generate report
echo "=== Daily Performance Report ==="
echo "Instance: $INSTANCE_ID"
echo "Period: $START_TIME to $END_TIME"
echo ""
echo "Metrics: $METRICS"
echo ""
echo "Slow Logs: $SLOW_LOGS"
```

## Alerting Strategy

### Alert Severity Levels

| Severity | Response Time | Escalation |
|----------|--------------|------------|
| **P0 - Critical** | Immediate | Page on-call engineer |
| **P1 - High** | 15 minutes | Notify team lead |
| **P2 - Medium** | 1 hour | Create ticket |
| **P3 - Low** | 4 hours | Log for review |

### Alert Rules

#### P0 Alerts

- Instance status != `Normal` for > 5 minutes
- Memory usage > 90%
- Connection usage > 90%
- Replication delay > 5 seconds
- Backup failure

#### P1 Alerts

- CPU usage > 85% for > 10 minutes
- Average latency > 20ms for > 10 minutes
- Cache hit rate < 70%
- Failed commands > 1%

#### P2 Alerts

- CPU usage > 70% for > 30 minutes
- Memory usage > 75% for > 30 minutes
- Average latency > 5ms for > 30 minutes
- Cache hit rate < 85%

#### P3 Alerts

- Slow query count > threshold
- Connection usage > 70%
- Replication delay > 1 second

## Capacity Planning

### Growth Tracking

Monitor these metrics over time to plan capacity:

| Metric | Tracking Period | Growth Indicator |
|--------|----------------|------------------|
| `Keys` | Weekly | Key count growth rate |
| `UsedMemory` | Weekly | Memory growth rate |
| `UsedQPS` | Daily | Peak QPS trend |
| `UsedConnection` | Daily | Connection usage trend |

### Scaling Triggers

| Condition | Action |
|-----------|--------|
| Memory usage > 75% for 7 days | Plan vertical scaling |
| QPS > 80% of max for 7 days | Plan horizontal scaling (cluster) |
| Connection usage > 80% for 7 days | Plan instance class upgrade |
| Replication delay consistently > 1s | Investigate network or upgrade |

## Tair-Specific Monitoring

### Persistent Memory Metrics

| Metric | Monitor Key | Unit | Description |
|--------|-------------|------|-------------|
| Persistent Memory Usage | `PersistentMemoryUsage` | % | Persistent memory utilization |
| Memory Tier Hit Rate | `MemoryTierHitRate` | % | Hot data in memory tier ratio |
| Disk Usage | `DiskUsage` | % | Disk storage utilization (Tair disk type) |

### Tair Performance Metrics

| Metric | Monitor Key | Unit | Description |
|--------|-------------|------|-------------|
| TairString Operations | `TairStringOps` | count/s | TairString command rate |
| TairHash Operations | `TairHashOps` | count/s | TairHash command rate |
| TairZset Operations | `TairZsetOps` | count/s | TairZset command rate |
| TairGIS Operations | `TairGISOps` | count/s | TairGIS command rate |
| TairSearch Operations | `TairSearchOps` | count/s | TairSearch command rate |

> **Note:** Tair-specific metrics require Tair Enterprise Edition. Use `DescribeMonitorItems` to verify availability for your instance.

## Log Monitoring

### Slow Log Analysis

```bash
# Get slow logs for analysis
aliyun r-kvstore describe-slow-logs \
  --InstanceId "{{user.instance_id}}" \
  --StartTime "2026-05-14T00:00:00Z" \
  --EndTime "2026-05-14T23:59:59Z" \
  --output cols=SQLText,ElapsedTime,ExecuteTime rows=Items.SlowLog[].{SQLText,ElapsedTime,ExecuteTime}
```

### Slow Log Thresholds

| Instance Type | Default Threshold | Recommended Threshold |
|---------------|-------------------|----------------------|
| Standard | 10000 μs (10ms) | 5000 μs (5ms) |
| Cluster | 10000 μs (10ms) | 3000 μs (3ms) |
| Tair | 10000 μs (10ms) | 2000 μs (2ms) |

Adjust via `slowlog-log-slower-than` parameter.

## Dashboard Recommendations

### Essential Dashboard Panels

1. **Instance Status**: Current status, uptime
2. **Resource Usage**: CPU, memory, connections over time
3. **Throughput**: QPS, inbound/outbound traffic
4. **Latency**: Average and max response time
5. **Cache Efficiency**: Hit rate, evicted keys
6. **Replication**: Replication delay (if applicable)
7. **Slow Queries**: Slow log count and top slow commands
8. **Backup Status**: Last backup time, backup success rate

## Integration with CloudMonitor

Alibaba Cloud Redis / Tair metrics are automatically published to CloudMonitor. You can:

- Set up alarm rules in CloudMonitor console
- Use CloudMonitor API to query metrics
- Integrate with DingTalk, SMS, or email for notifications
- Export metrics to external monitoring systems via CloudMonitor
