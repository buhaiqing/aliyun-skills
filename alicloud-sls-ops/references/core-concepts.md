# Core Concepts — Alibaba Cloud Simple Log Service (SLS)

## Overview

Alibaba Cloud **Simple Log Service** (SLS, 日志服务) is a fully managed log collection,
storage, analysis, and visualization service. It provides real-time log analytics,
intelligent alerting, and comprehensive observability capabilities.

**Key value proposition:** Complete log lifecycle management — from collection to
analysis to archival — with pay-as-you-go pricing and millisecond-level query latency.

## Architecture

### Service Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Simple Log Service (SLS)                  │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Project  │  │ Logstore │  │  Index   │  │  Shard   │  │
│  │          │  │          │  │          │  │          │  │
│  │ ─────── │  │ ─────── │  │ ─────── │  │ ─────── │  │
│  │ Project │  │ Log     │  │ Full-   │  │ Write   │  │
│  │ Name    │  │ Store   │  │ Text    │  │ Shard   │  │
│  │         │  │ Name    │  │ Index   │  │         │  │
│  │ Region  │  │ TTL     │  │         │  │ Read    │  │
│  │         │  │ Shard   │  │ Key     │  │ Shard   │  │
│  │         │  │ Count   │  │ Value   │  │         │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Alert   │  │Dashboard │  │  ETL     │  │Consumer  │  │
│  │  Rule    │  │          │  │          │  │  Group   │  │
│  │ ─────── │  │ ─────── │  │ ─────── │  │ ─────── │  │
│  │ Alert   │  │Widgets  │  │ Transform│  │ Consumer│  │
│  │ Name    │  │         │  │ Pipeline │  │ Group   │  │
│  │ Query   │  │ Layout  │  │          │  │         │  │
│  │ Period  │  │         │  │          │  │         │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Collection:** Logtail agents collect logs from ECS, containers, or on-premises
2. **Ingestion:** Logs are sent to SLS via REST API or SDK
3. **Storage:** Logs are stored in shards within logstores
4. **Indexing:** Full-text or key-value indexes enable fast queries
5. **Analysis:** SQL queries, dashboards, and alerts provide insights
6. **Archival:** Data can be exported to OSS, MaxCompute, or other storage

## Key Resources

### Project

- **Identifier:** `projectName`
- **Scope:** Global (unique across all regions)
- **Limits:** 3-63 characters, lowercase letters, numbers, hyphens
- **Max projects per region:** 10 (default)

### Logstore

- **Identifier:** `logstore`
- **Scope:** Within a project
- **Limits:** 3-63 characters, lowercase letters, numbers, hyphens
- **Max logstores per project:** 200
- **Shards:** 1-256 (determines write throughput)

### Index

- **Identifier:** `logstore` (one index per logstore)
- **Types:** Full-text, key-value, JSON
- **Max indexed fields:** 200

### Alert

- **Identifier:** `alertName`
- **Scope:** Within a project
- **Query:** SQL-based log analysis
- **Notification:** IM, webhook, email, SMS

### Dashboard

- **Identifier:** `dashboardName`
- **Scope:** Within a project
- **Widgets:** Line chart, bar chart, pie chart, table, log pattern, number, etc.

## Resource Limits

| Resource | Limit | Notes |
|----------|-------|-------|
| Projects per region | 10 | Default quota |
| Logstores per project | 200 | Can request increase |
| Shards per logstore | 256 | Determines write throughput |
| Indexed fields | 200 | Per logstore |
| Alert rules per project | 50 | Can request increase |
| Dashboards per project | 50 | Can request increase |
| Dashboard widgets | 50 | Per dashboard |
| Consumer groups per logstore | 10 | For real-time consumption |
| Log size | 512 KB | Per log entry |
| Query timeout | 60 seconds | For GetLogs API |

## Logstore Retention

| TTL Range | Description |
|-----------|-------------|
| 1-3650 days | Retention period (default 30) |
| 0 | No expiration (permanent) |

> **Note:** Retention of 0 means logs are kept indefinitely. Set based on compliance
> requirements.

## Index Configuration

### Full-Text Index

```json
{
  "fullTextIndex": {
    "caseSensitive": false,
    "includeChinese": true,
    "token": ["@", " ", ","]
  }
}
```

### Key-Value Index

```json
{
  "keys": {
    "level": {
      "type": "text",
      "token": ["@"],
      "caseSensitive": false,
      "includeChinese": true
    },
    "message": {
      "type": "text",
      "token": ["@", " "],
      "caseSensitive": false,
      "includeChinese": true
    }
  }
}
```

## Quotas and Limits

| Resource | Default Limit | Increase Possible |
|----------|---------------|-------------------|
| Projects per region | 10 | Yes |
| Logstores per project | 200 | Yes |
| Shards per logstore | 256 | Yes |
| GetLogs queries | 500 QPS | Yes |
| GetHistograms queries | 500 QPS | Yes |
| Write requests | 1000 QPS per shard | Yes |

## SLS vs Other Services

| Aspect | SLS | DataWorks | MaxCompute | OSS |
|--------|-----|-----------|------------|-----|
| Primary Use | Log collection & analysis | Data integration & development | Big data processing | Object storage |
| Latency | Milliseconds | Batch | Batch | N/A |
| Query | SQL | SQL | SQL | N/A |
| Real-time | Yes | No | No | No |
| Cost Model | Pay per ingested GB | Pay per CU | Pay per CU | Pay per GB stored |

## Best Practices

### Log Collection

- Use Logtail for ECS and container log collection
- Configure log collection in Kubernetes via CRDs
- Use data ingestion for on-premises logs
- Set up logtail pipeline configs for log processing

### Storage & Indexing

- Set appropriate TTL based on compliance requirements
- Create indexes for fields you frequently query
- Use JSON parsing for structured logs
- Monitor shard usage to avoid write throttling

### Query & Analysis

- Use SQL queries for complex analysis
- Create saved searches for frequently used queries
- Use dashboards for operational visibility
- Set up alerts for critical log patterns

### Cost Optimization

- Archive old logs to OSS or MaxCompute
- Use appropriate retention periods
- Monitor ingestion volume
- Optimize index configuration to reduce storage

## Reference Documentation

- [SLS Product Documentation](https://help.aliyun.com/product/28979.html)
- [SLS OpenAPI Reference](https://help.aliyun.com/zh/sls/developer-reference/api-overview)
- [SLS Best Practices](https://help.aliyun.com/zh/sls/developer-reference/best-practices-for-log-service)
