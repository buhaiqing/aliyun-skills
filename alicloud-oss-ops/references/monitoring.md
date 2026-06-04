# Monitoring & Alerts — Alibaba Cloud OSS

## Monitoring Overview

OSS provides monitoring through **Cloud Monitor (CMS)** and the
`GetBucketStat` / `ListObject` APIs. CMS metric data has a 1-minute granularity
and is available for free on the OSS namespace. This document covers the
metric catalog, alert thresholds, and request-statistics patterns.

## CMS Metric Namespace

**Namespace:** `acs_oss_dashboard`

## Key Metrics

### Storage

| Metric | Unit | Description |
|--------|------|-------------|
| `BucketSize` | bytes | Total storage size of the bucket |
| `ObjectCount` | count | Total object count |

### Network

| Metric | Unit | Description |
|--------|------|-------------|
| `InternetIn` | bytes | Public inbound traffic |
| `InternetOut` | bytes | Public outbound traffic |
| `IntranetIn` | bytes | Internal (same-region) inbound |
| `IntranetOut` | bytes | Internal (same-region) outbound |
| `CDNIn` | bytes | Traffic from CDN |
| `CDNOut` | bytes | Traffic to CDN |
| `OriginIn` | bytes | Traffic from origin to OSS |
| `OriginOut` | bytes | Traffic from OSS to origin |
| `ReplicationIn` | bytes | CRR inbound traffic |
| `ReplicationOut` | bytes | CRR outbound traffic |

### Requests (counts)

| Metric | Unit | Description |
|--------|------|-------------|
| `GetRequestCount` | count | GET + HEAD requests |
| `PutRequestCount` | count | PUT + POST requests |
| `DeleteRequestCount` | count | DELETE requests |
| `AllRequestCount` | count | All requests |

### Latency

| Metric | Unit | Description |
|--------|------|-------------|
| `ServerLatency` | ms | Average server-side processing time |
| `E2ELatency` | ms | End-to-end latency (for GET, includes network) |

### Error Rates

| Metric | Unit | Description |
|--------|------|-------------|
| `ErrorRequestCount` | count | Requests returning 4xx/5xx |
| `ErrorCode4xxCount` | count | 4xx errors |
| `ErrorCode5xxCount` | count | 5xx errors |

## Querying Metrics via CLI

OSS metrics are queried via Cloud Monitor (`aliyun cms`).

```bash
# Get bucket size over the last hour
aliyun cms DescribeMetricList \
  --Namespace acs_oss_dashboard \
  --MetricName BucketSize \
  --Dimensions "[{\"BucketName\":\"{{user.bucket_name}}\"}]" \
  --Period 60 \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Get request count by type
aliyun cms DescribeMetricList \
  --Namespace acs_oss_dashboard \
  --MetricName AllRequestCount \
  --Dimensions "[{\"BucketName\":\"{{user.bucket_name}}\"}]" \
  --Period 60
```

> **Tip:** Use the `alicloud-cms-ops` skill to monitor OSS via CMS with
> pre-built alerts. This skill owns the metric namespace; CMS ops owns the
> alert delivery.

## Real-Time Request Statistics

`GetBucketStat` returns **current** statistics without waiting for CMS
aggregation (good for dashboards / `describe` operations).

| Field | Description |
|-------|-------------|
| `$.Storage` | Total storage (bytes) |
| `$.ObjectCount` | Total object count |
| `$.MultipartUploadCount` | In-progress multipart uploads |
| `$.GetRequestCount` | Cumulative GET requests since creation |
| `$.PutRequestCount` | Cumulative PUT requests since creation |
| `$.LiveChannelCount` | Live channels (for RTMP) |

```bash
aliyun oss GetBucketStat --Bucket "{{user.bucket_name}}"
```

## Storage Class Distribution

Use `ossutil` to derive storage class distribution at a point in time:

```bash
ossutil ls oss://{{user.bucket_name}} -r --meta 2>/dev/null \
  | awk '{ for(i=1;i<=NF;i++) if($i=="X-Oss-Storage-Class:") print $(i+1) }' \
  | sort | uniq -c
```

## Alert Recommendations

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| Storage growth spike | `BucketSize` delta > 50% in 1h | Warning | Investigate upload pattern |
| 5xx error rate high | `ErrorCode5xxCount` > 10/min | Critical | Check OSS status, contact support |
| 4xx spike (AccessDenied) | `ErrorCode4xxCount` > 100/min | Warning | Check policy / credentials |
| Outbound traffic spike | `InternetOut` > 1 GB/min | Warning | Verify legitimate use / cost spike |
| Multipart upload leak | `MultipartUploadCount` > 1000 | Warning | Set lifecycle abort rule |
| E2E latency high | `E2ELatency` > 1000 ms | Warning | Check CDN / network |

## Pre-Built CMS Alert Template

```bash
# Create a 5xx error rate alert
aliyun cms PutResourceMetricRule \
  --RuleName "OSS-5xx-High" \
  --Namespace acs_oss_dashboard \
  --MetricName ErrorCode5xxCount \
  --Dimensions "[{\"BucketName\":\"my-bucket\"}]" \
  --Statistics "Average" \
  --Threshold 10 \
  --ComparisonOperator "GreaterThanThreshold" \
  --ContactGroups "['ops-team']"
```

## Cost Monitoring

OSS billing comes from five sources:

| Source | Metric | Cost Driver |
|--------|--------|-------------|
| **Storage** | `BucketSize` (by class) | Bytes × hours × class price |
| **Requests** | `Get/Put/Delete/AllRequestCount` | Per 10,000 requests |
| **Traffic** | `InternetOut` (NOT `InternetIn`) | Egress GB |
| **Data retrieval** | `RestoreObject` calls | Per GB retrieved from Archive/ColdArchive |
| **CRR traffic** | `ReplicationOut` | Cross-region egress |

> **Cost-pillar recommendation:** Use the Billing skill (`alicloud-billing-ops`)
> to track OSS charges by bucket via the `OSS-Storage`、`OSS-Traffic`、
> `OSS-Request` billing items.

## Integration with SLS

For detailed access logs, enable bucket logging (writes to another bucket),
then ingest into SLS (Simple Log Service) for long-term analysis:

1. `ossutil set-acl` + `PutBucketLogging` to enable access log delivery
2. Configure SLS logtail to read the log prefix
3. Query with SQL: `SELECT * FROM oss_log WHERE status >= 400`
