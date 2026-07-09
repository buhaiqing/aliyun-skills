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

## Multi-Metric Anomaly Inspection

### Supported Anomaly Patterns

| Pattern | Metrics Involved | Detection Logic | Severity | Interpretation |
|---------|-----------------|-----------------|----------|----------------|
| AK 篡改模式 | `IpInsight` + `AkInsight` + `ApiCallRateInsight` | 新 IP + 异常 AK 调用 + 调用率突增 3x+ | Critical | AccessKey 可能被盗用并正在执行批量操作 |
| 权限提升+审计隐藏 | `PolicyChangeInsight` + `TrailConcealmentInsight` | 策略变更后 5 min 内 Trail 被禁用 | Critical | 攻击者提权后试图关闭审计 |
| 密码重置+异地登录 | `PasswordChangeInsight` + `IpInsight` | 密码变更后来自新 IP 的登录 | Critical | 账户可能被接管 |
| API 错误风暴 | `ApiErrorRateInsight` + `ApiCallRateInsight` | 错误率突增 AND 总调用量下降 | Warning | 可能资源删除导致级联依赖不可用 |
| 大规模删除事件 | `eventName LIKE 'Delete%'` count + `DescribeTrailDeliveryMetricData` | 删除事件 > 10/5 min + 事件量突增 | Critical | 批量删除资源，可能是恶意操作或配置脚本错误 |
| Root 账户异常活动 | `eventType = 'ConsoleSignin'` (root) + `IpInsight` | Root 登录 + 来自新 IP 或新区域 | Warning | Root 账户异常登录，需立即验证 |

### Recovery & Cross-Skill Delegation

| Pattern | Primary Skill | Delegated Skill | Action |
|---------|--------------|-----------------|--------|
| AK 篡改 | `alicloud-actiontrail-ops` | `alicloud-ram-ops` (禁用/旋转 AK) | 立即禁用可疑 AK |
| 权限+审计隐藏 | `alicloud-actiontrail-ops` | `alicloud-ram-ops` (审计权限变更) | 恢复 Trail + 审计权限变更记录 |
| 批量删除 | `alicloud-actiontrail-ops` | 产品 Skill (如 `alicloud-ecs-ops`) | 确认删除事件并恢复资源 |

## Alert Storm Handling

1. **Aggregate by userIdentity**: Multiple Insight events for same user → single security event
2. **Prioritize by severity**: `TrailConcealmentInsight` and `PolicyChangeInsight` always take priority over `ApiErrorRateInsight`
3. **Correlate time window**: Multiple Insight events within ±2 min of each other likely share the same root actor

## Alert-Driven Diagnostic Decision Tree

```
[ActionTrail Alert/Insight Event]
    │
    ├── Step 1: Verify event — Check Insight event details and timestamp
    │
    ├── Step 2: Check user activity — Lookup all events for userIdentity in time window
    │
    ├── Step 3: Multi-insight correlation — Check if multiple Insight types fire for same user
    │       └── Match anomaly pattern from table above
    │
    ├── Step 4: Cross-Skill diagnosis
    │       ├── If user AK change → Delegate to `alicloud-ram-ops`
    │       ├── If resource deletion → Delegate to affected product skill
    │       └── If trail disabled → Re-enable trail immediately
    │
    └── Step 5: Generate security incident report
```