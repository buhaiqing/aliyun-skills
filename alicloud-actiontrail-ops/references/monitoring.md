# Monitoring — Alibaba Cloud ActionTrail (操作审计)

## Overview

ActionTrail itself is a monitoring and audit service. This reference covers how to
monitor the health and performance of ActionTrail delivery, and how to use ActionTrail
data for monitoring other Alibaba Cloud services.

## ActionTrail Delivery Monitoring

### Delivery Metrics

Use `DescribeTrailDeliveryMetricData` to monitor trail delivery health:

```bash
aliyun actiontrail DescribeTrailDeliveryMetricData --TrailName {{user.trail_name}}
```

Key metrics:
- **Delivery success rate**: Percentage of events successfully delivered
- **Delivery latency**: Time between event occurrence and delivery
- **Event volume**: Number of events delivered per time period
- **Delivery errors**: Count of delivery failures

### Trail Status Monitoring

Regularly check trail status to ensure logging is active:

```bash
aliyun actiontrail GetTrailStatus --Name {{user.trail_name}}
```

Key indicators:
- `IsLogging`: Whether the trail is actively delivering events
- `LatestDeliveryTime`: Timestamp of the most recent successful delivery
- `LatestNotificationTime`: Timestamp of the most recent notification

## Alerting with ActionTrail + SLS

When ActionTrail delivers events to SLS, you can set up alerts:

1. **Create a trail** with SLS delivery destination
2. **Configure SLS alert rules** for specific event patterns:
   - Root account login events
   - Failed API calls (high error rate)
   - Unauthorized access attempts
   - Resource deletion events
   - Security group modifications
3. **Set up notification channels** (SMS, email, webhook)

### Example SLS Alert Queries

**Detect root account login:**
```sql
* | SELECT count(*) as login_count WHERE eventType = 'ConsoleSignin' AND userIdentity.type = 'root-account'
```

**Detect failed API calls:**
```sql
* | SELECT eventName, count(*) as error_count WHERE errorMessage != 'success' GROUP BY eventName
```

**Detect resource deletion:**
```sql
* | SELECT eventName, resourceName, userIdentity.userName WHERE eventName LIKE 'Delete%'
```

## ActionTrail Governance Metrics

Use `GetGovernanceMetrics` to assess your ActionTrail configuration maturity:

```bash
aliyun actiontrail GetGovernanceMetrics
```

This API returns metrics on:
- Whether trails are configured
- Whether multi-region trails exist
- Whether SLS delivery is configured
- Whether insight is enabled
- Overall governance score

## Anomaly Detection with Insight

ActionTrail Insight provides automated anomaly detection:

### Insight Types

| Insight Type | What It Detects | Use Case | Real-World Scenario |
|-------------|-----------------|----------|---------------------|
| `IpInsight` | Operations from unfamiliar IP addresses | Detect AccessKey theft | Hacker uses stolen AK from a new geographic region |
| `ApiCallRateInsight` | Unusual changes in API call frequency | Detect potential compromise or misconfiguration | Offboarding employee bulk-deletes resources, causing call rate spike |
| `ApiErrorRateInsight` | Unusual increase in API error rates | Detect service issues or permission problems | Deleted resource has hidden dependency — dependent service calls fail with high error rate |
| `AkInsight` | Unusual AccessKey call patterns | Detect AK misuse | Stolen AK used at abnormal hours or to call unusual services |
| `PolicyChangeInsight` | Permission/policy changes | Detect unauthorized privilege escalation | Compromised account grants itself admin permissions |
| `PasswordChangeInsight` | Password change events | Detect account compromise | Attacker resets password after gaining access |
| `TrailConcealmentInsight` | Trail disable/deletion attempts | Detect audit evasion | Attacker disables audit trail to cover malicious activity |

### Enable Insight

```bash
# Enable all 7 insight types for comprehensive monitoring
aliyun actiontrail EnableInsight --InsightType IpInsight
aliyun actiontrail EnableInsight --InsightType ApiCallRateInsight
aliyun actiontrail EnableInsight --InsightType ApiErrorRateInsight
aliyun actiontrail EnableInsight --InsightType AkInsight
aliyun actiontrail EnableInsight --InsightType PolicyChangeInsight
aliyun actiontrail EnableInsight --InsightType PasswordChangeInsight
aliyun actiontrail EnableInsight --InsightType TrailConcealmentInsight
```

### Query Insight Events

```bash
# Query specific insight type
aliyun actiontrail LookupInsightEvents --InsightType IpInsight

# Query with time range
aliyun actiontrail LookupInsightEvents \
  --InsightType ApiCallRateInsight \
  --StartTime "2026-05-01T00:00:00Z" \
  --EndTime "2026-05-15T23:59:59Z"
```

## Dashboards

### Key Metrics to Track

| Metric | Source | Purpose |
|--------|--------|---------|
| Trail count per region | `DescribeUserTrailCount` | Ensure quota not exceeded |
| Trails with active logging | `GetTrailStatus` per trail | Detect disabled trails |
| Event delivery latency | `DescribeTrailDeliveryMetricData` | Monitor delivery health |
| Event volume trend | `DescribeUserLogCount` | Track audit data growth |
| Alert count trend | `DescribeUserAlertCount` | Monitor security events |
| Governance score | `GetGovernanceMetrics` | Track compliance maturity |

### Recommended Monitoring Frequency

| Check | Frequency | Action on Failure |
|-------|-----------|-------------------|
| Trail status | Daily | Re-enable logging if disabled |
| Delivery metrics | Hourly | Investigate delivery failures |
| Insight events | Daily | Review anomalies |
| Governance score | Weekly | Improve configuration |
| Trail count | Weekly | Clean up unused trails |