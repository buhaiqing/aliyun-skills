# Monitoring — Alibaba Cloud Simple Log Service (SLS)

## Overview

Alibaba Cloud **Simple Log Service (SLS)** provides built-in monitoring capabilities
via CloudMonitor integration. This reference covers monitoring metrics, alarms, and
observability best practices.

## SLS CloudMonitor Metrics

### Logstore Metrics

| Metric | Description | Unit | Dimensions |
|--------|-------------|------|------------|
| `LogstoreIngestion流量` | Log ingestion volume | Bytes | project, logstore |
| `LogstoreIngestion条数` | Log ingestion count | Count | project, logstore |
| `Logstore索引流量` | Index traffic | Bytes | project, logstore |
| `Logstore索引条数` | Index count | Count | project, logstore |
| `Logstore写流量` | Write throughput | Bytes/s | project, logstore |
| `Logstore读流量` | Read throughput | Bytes/s | project, logstore |
| `Logstore分片数` | Shard count | Count | project, logstore |
| `Logstore分片使用率` | Shard utilization | Percent | project, logstore |

### Alert Metrics

| Metric | Description | Unit | Dimensions |
|--------|-------------|------|------------|
| `Alert触发次数` | Alert trigger count | Count | project, alertName |
| `Alert通知发送次数` | Alert notification count | Count | project, alertName |
| `Alert通知发送失败次数` | Alert notification failure count | Count | project, alertName |

### Dashboard Metrics

| Metric | Description | Unit | Dimensions |
|--------|-------------|------|------------|
| `Dashboard查询次数` | Dashboard query count | Count | project, dashboardName |
| `Dashboard查询耗时` | Dashboard query latency | Milliseconds | project, dashboardName |

## Alarm Configuration

### High Ingestion Volume Alarm

```json
{
  "namespace": "acs_sls",
  "metricName": "LogstoreIngestion流量",
  "dimensions": {
    "project": "{{user.project_name}}",
    "logstore": "{{user.logstore}}"
  },
  "period": 300,
  "statistics": "Sum",
  "comparisonOperator": ">",
  "threshold": 1073741824,
  "evaluationCount": 3,
  "contactGroups": ["ops-team"]
}
```

### High Shard Utilization Alarm

```json
{
  "namespace": "acs_sls",
  "metricName": "Logstore分片使用率",
  "dimensions": {
    "project": "{{user.project_name}}",
    "logstore": "{{user.logstore}}"
  },
  "period": 300,
  "statistics": "Average",
  "comparisonOperator": ">",
  "threshold": 80,
  "evaluationCount": 3,
  "contactGroups": ["ops-team"]
}
```

### Alert Failure Alarm

```json
{
  "namespace": "acs_sls",
  "metricName": "Alert通知发送失败次数",
  "dimensions": {
    "project": "{{user.project_name}}",
    "alertName": "{{user.alert_name}}"
  },
  "period": 300,
  "statistics": "Sum",
  "comparisonOperator": ">",
  "threshold": 0,
  "evaluationCount": 1,
  "contactGroups": ["ops-team"]
}
```

## Log-Based Monitoring

### Error Log Alert

```json
{
  "alertName": "error-log-alert",
  "displayName": "Error Log Alert",
  "type": "alert",
  "schedule": {
    "type": "FixedRate",
    "interval": "1m"
  },
  "configuration": {
    "query": "level:ERROR",
    "chartQuery": "level:ERROR | select count(*) as cnt",
    "condition": {
      "condition": ">",
      "threshold": 10
    }
  },
  "notification": {
    "notificationList": [
      {
        "type": "IM",
        "id": "my-im-group"
      }
    ]
  }
}
```

### Slow Query Alert

```json
{
  "alertName": "slow-query-alert",
  "displayName": "Slow Query Alert",
  "type": "alert",
  "schedule": {
    "type": "FixedRate",
    "interval": "5m"
  },
  "configuration": {
    "query": "query_time > 1000",
    "chartQuery": "query_time > 1000 | select count(*) as cnt",
    "condition": {
      "condition": ">",
      "threshold": 5
    }
  }
}
```

## SLS Log Analytics

### Query Patterns

**Error Analysis:**
```sql
level:ERROR | select __time__, source, message order by __time__ desc limit 100
```

**Performance Analysis:**
```sql
query_time > 1000 | select avg(query_time) as avg_time, max(query_time) as max_time, count(*) as cnt
```

**Traffic Analysis:**
```sql
from * | select date_trunc('hour', __time__) as hour, count(*) as cnt group by hour order by hour
```

**User Activity:**
```sql
user_name:* | select user_name, count(*) as cnt group by user_name order by cnt desc limit 10
```

### Dashboard Widgets

**Line Chart (Time Series):**
```json
{
  "title": "Log Volume",
  "type": "line",
  "logstore": "{{user.logstore}}",
  "query": "from * | select count(*) as cnt",
  "xAxis": {
    "type": "time"
  },
  "yAxis": {
    "type": "value"
  }
}
```

**Bar Chart (Categorical):**
```json
{
  "title": "Error by Source",
  "type": "bar",
  "logstore": "{{user.logstore}}",
  "query": "level:ERROR | select source, count(*) as cnt group by source order by cnt desc",
  "xAxis": {
    "type": "category"
  },
  "yAxis": {
    "type": "value"
  }
}
```

**Number (Single Value):**
```json
{
  "title": "Total Errors",
  "type": "number",
  "logstore": "{{user.logstore}}",
  "query": "level:ERROR | select count(*) as cnt"
}
```

**Table (Detailed Data):**
```json
{
  "title": "Recent Errors",
  "type": "table",
  "logstore": "{{user.logstore}}",
  "query": "level:ERROR | select __time__, source, message order by __time__ desc limit 10"
}
```

## Best Practices

### Monitoring Strategy

1. **Key Metrics:** Monitor ingestion volume, shard utilization, and alert failures
2. **Thresholds:** Set appropriate thresholds based on baseline traffic
3. **Notifications:** Use IM, email, and SMS for critical alerts
4. **Dashboards:** Create dashboards for operational visibility

### Alert Configuration

1. **Rate:** Use FixedRate (1m-5m) for real-time alerts
2. **Thresholds:** Set thresholds based on historical patterns
3. **Duration:** Use evaluationCount to avoid false positives
4. **Escalation:** Configure multi-level notifications

### Log Analysis

1. **Indexing:** Create indexes for fields you frequently query
2. **Saved Searches:** Save frequently used queries for quick access
3. **Dashboards:** Build dashboards for different use cases
4. **Retention:** Set appropriate TTL based on compliance requirements

## Reference Documentation

- [SLS Monitoring Guide](https://help.aliyun.com/zh/sls/developer-reference/monitoring-guide)
- [SLS CloudMonitor Integration](https://help.aliyun.com/zh/sls/developer-reference/cloudmonitor-integration)
- [SLS Dashboard Guide](https://help.aliyun.com/zh/sls/developer-reference/dashboard-guide)
