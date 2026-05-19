# Monitoring KMS

## Key Metrics (Cloud Monitor / CMS)

KMS integrates with Alibaba Cloud Cloud Monitor Service (CMS) for operational metrics.

| Metric | Namespace | Description | Unit | Typical Threshold |
|--------|-----------|-------------|------|-------------------|
| `Encrypt QPS` | `acs_kms` | Encrypt API calls per second | Count/s | Alert if > 80% of QPS limit |
| `Decrypt QPS` | `acs_kms` | Decrypt API calls per second | Count/s | Alert if > 80% of QPS limit |
| `Encrypt Latency` | `acs_kms` | P95 latency for Encrypt operation | ms | Alert if > 50ms |
| `Decrypt Latency` | `acs_kms` | P95 latency for Decrypt operation | ms | Alert if > 50ms |
| `API Error Rate` | `acs_kms` | Failed API calls / Total API calls | % | Alert if > 1% |
| `Key Usage Count` | `acs_kms` | Number of operations per key | Count | Alert on sudden drops (potential outage) |
| `Secret Access Count` | `acs_kms` | GetSecretValue calls count | Count | Alert on unusual patterns |

## Alert Configuration Example

```bash
# Create CMS alarm for KMS error rate
aliyun cms PutMetricAlarm \
  --Name "KMS-High-Error-Rate" \
  --Namespace "acs_kms" \
  --MetricName "APIErrorRate" \
  --ComparisonOperator "GreaterThanThreshold" \
  --Threshold 0.01 \
  --Period 60 \
  --EvaluationCount 3 \
  --ContactGroups "ops-team" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Key Operational Checks

| Check | Description | Frequency |
|-------|-------------|-----------|
| Keys approaching PendingDeletion | Detect keys in deletion grace period | Daily |
| Disabled keys in use | Identify applications referencing disabled keys | Weekly |
| Secret rotation compliance | Verify critical secrets have rotation enabled | Weekly |
| DKMS instance health | Check instance status and resource utilization | Daily |
| API quota consumption | Monitor API call volume against monthly limits | Daily |

## Anomaly Patterns

| Pattern | Possible Cause | Investigation |
|---------|---------------|---------------|
| Sudden drop in Encrypt/Decrypt QPS | Key disabled or deleted | `DescribeKey` for referenced keys |
| Latency spike | Network issue or KMS service degradation | Check VPC connectivity; retry with public endpoint |
| Increased 403 errors | RAM policy change or credential expiry | Check RAM policies and AccessKey status |
| Secret access failure | Secret deleted or in PendingDeletion | `DescribeSecret` to check state |
| Throttling at 429 | Runaway script loop or traffic spike | Implement client-side rate limiting |
