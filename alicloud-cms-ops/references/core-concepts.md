# Core Concepts — CloudMonitor (CMS)

## Architecture Overview

CloudMonitor (CMS) is Alibaba Cloud's unified monitoring and alerting service.
It collects metrics from cloud resources, allows custom metric publishing, and
supports alarm rule configuration.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Cloud Resources │────▶│ CloudMonitor    │────▶│ Metrics Storage │
│ (ECS, RDS, etc) │     │ (Collection)    │     │ (Time-Series)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │ Alarm Engine    │
                        │ (Evaluation)    │
                        └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │ Notifications   │
                        │ (MNS, SMS, etc) │
                        └─────────────────┘
```

## Key Concepts

### Metrics

A metric is a time-series data point representing a measurable aspect of a
resource. Examples:
- `CPUUtilization` — CPU usage percentage
- `MemoryUsage` — Memory usage percentage
- `DiskUsage` — Disk usage percentage
- `InternetInRate` — Network inbound rate

### Namespaces

Namespaces group metrics by product. Format: `acs_<product>_dashboard`.

| Product | Namespace |
|---------|-----------|
| ECS | `acs_ecs_dashboard` |
| RDS | `acs_rds_dashboard` |
| SLB | `acs_slb_dashboard` |
| OSS | `acs_oss_dashboard` |
| Redis | `acs_kvstore_dashboard` |

### Dimensions

Dimensions are key-value pairs that identify a specific resource instance.
Common dimension keys:
- `instanceId` — ECS, RDS, Redis instances
- `userId` — OSS buckets
- `clusterId` — Kubernetes clusters

Format in API: JSON array of objects `[{"instanceId":"i-xxx"}]`.

### Period

Aggregation interval in seconds:
- `15` — High resolution (7-day retention)
- `60` — Standard (31-day retention)
- `300` — 5-minute (91-day retention)
- `900` — 15-minute (91-day retention)
- `3600` — 1-hour (91-day retention)

### Alarm Rules

An alarm rule defines:
- **Metric** to monitor
- **Threshold** and **ComparisonOperator** (`>=`, `>`, `<`, `<=`, `==`, `!=`)
- **Statistics** (Average, Minimum, Maximum, Value)
- **EvaluationCount** — consecutive periods before triggering
- **ContactGroups** — who to notify
- **EffectiveInterval** — time window (e.g., `00:00-23:59`)

### Monitor Groups

Application groups that aggregate resources for unified monitoring and alarming.

## Data Flow

1. **Collection:** CloudMonitor collects metrics from resources every minute.
2. **Storage:** Time-series data stored with retention based on Period.
3. **Query:** Users query via `DescribeMetricList` or `DescribeMetricLast`.
4. **Evaluation:** Alarm engine evaluates rules every Period.
5. **Notification:** Triggers notify via MNS, SMS, email, or DingTalk.

## API Versions

| Version | Style | Use Case |
|---------|-------|----------|
| Cms/2019-01-01 | RPC | Metric queries, alarm management |
| Cms/2024-03-30 | ROA | CloudMonitor 2.0 advanced features |

## References

- [CMS Product Overview](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/product-overview/)
- [Metric Reference](https://help.aliyun.com/document_detail/163515.html)
