<!-- markdownlint-disable MD003 MD013 MD022 MD024 MD034 MD041 MD060 -->

# Monitoring — Alibaba Cloud Security Center

## Overview

Security Center is both a **detection product** and a source of **security metrics**. Monitor:

1. **Platform health** — agent online rate, API errors, export job progress
2. **Risk posture** — alert volume, unfixed vulns, baseline pass rate, security score
3. **Downstream integration** — SLS/OSS exports, CMS custom metrics (when configured)

## Built-in Statistics APIs

Use these APIs before external monitoring when triaging posture:

```bash
# Global counts (alerts, vulns, baseline — field names per response)
aliyun sas DescribeAllRegionsStatistics

# Vulnerability statistics
aliyun sas DescribeVulNumStatistics
aliyun sas DescribeVulMetaCountStatistics

# Alert statistics by group
aliyun sas GetSuspiciousStatistics

# Container cluster alerts
aliyun sas GetClusterSuspEventStatistics
```

## Agent Coverage Monitoring

**Metric (conceptual):** `agent_online_ratio = online_assets / total_assets`

```bash
# Offline agents
aliyun sas DescribeCloudCenterInstances \
  --Criteria '[{"name":"clientStatus","value":"offline"}]' \
  --PageSize 100

# Online agents
aliyun sas DescribeCloudCenterInstances \
  --Criteria '[{"name":"clientStatus","value":"online"}]' \
  --PageSize 100
```

**Alert threshold (recommended):**

| Signal | Warning | Critical |
|--------|---------|----------|
| Offline agent % | > 5% | > 15% |
| Important asset offline | any | > 0 for 24h |

## Alert Storm Handling

When `DescribeSuspEvents` returns high volume:

1. Group by `EventName` and `Level` (aggregate in analysis tool)
2. Identify single-asset bursts vs account-wide spikes
3. Use `CreateSimilarSecurityEventsQueryTask` for correlated alert search
4. Apply whitelist only after confirming false positive (`OperationCancelIgnoreSuspEvent`)

## Export & Long-Term Retention

```bash
aliyun sas ExportSuspEvents
aliyun sas DescribeSuspEventExportInfo
aliyun sas ExportRecord
aliyun sas DescribeExportInfo
```

Delegate **SLS dashboards/alarms** on exported logs to `alicloud-sls-ops` when present.

## Cloud Monitor (CMS) Integration

Security Center console may expose integration with **Cloud Monitor**. Typical custom-metric patterns (verify namespace in your account):

| Metric concept | Use |
|----------------|-----|
| Suspicious event count | Alert rate anomaly |
| Unfixed vulnerability count | Patch SLA tracking |
| Baseline risk count | Compliance drift |

Configure CMS alarms when product metrics are available in your region/edition. Use `alicloud-cms-ops` for alarm CRUD.

## Recommended Alert Rules (Operational)

| Rule | Source | Action |
|------|--------|--------|
| Critical alert on important asset | DescribeSuspEvents + asset Importance=2 | Page on-call |
| AK leak detected | DescribeAccesskeyLeakList | Force key rotation (RAM) |
| Agent offline > 24h on prod | DescribeCloudCenterInstances | Auto-ticket + install repair |
| Security score drop > 10% week-over-week | GetSecurityScoreRule + history | Review DescribeSecureSuggestion |

## Delivery Health (Multi-Account)

For resource directory / multi-account setups:

```bash
aliyun sas DescribeMonitorAccounts
aliyun sas CreateMonitorAccount
```

Monitor sync failures separately per member account.

## Integration with ActionTrail

Security Center changes (policy updates, agent uninstall) should be correlated with API audit:

- Delegate: `aliyun actiontrail LookupEvents --ServiceName Sas` (verify exact ServiceName in events)

See [observability.md](observability.md) for Metrics → Logs → Traces linkage.
