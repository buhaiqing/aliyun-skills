<!-- markdownlint-disable MD003 MD013 MD022 MD024 MD034 MD041 MD060 -->

# Observability — Security Center

## Metrics → Logs → Traces Linkage

### Metrics (Posture KPIs)

| KPI | Primary API | Notes |
|-----|-------------|-------|
| Open critical alerts | `DescribeSuspEvents` + filter Level | Time-bounded queries |
| Unfixed CVE count | `DescribeVulNumStatistics` | By severity if available |
| Baseline pass rate | `DescribeCheckWarningSummary` | Trend weekly |
| Agent online % | `DescribeCloudCenterInstances` | Criteria on clientStatus |
| Security score | Console + `GetSecurityScoreRule` | Deduction modules |

### Logs (Detail & Forensics)

| Log source | Access | Use |
|------------|--------|-----|
| Security Center alert export | `ExportSuspEvents` | SOC SIEM ingestion |
| Security Center log analysis | Product log feature APIs | Search alert descriptions |
| ActionTrail | `alicloud-actiontrail-ops` | API-level change attribution |
| Host logs on ECS | `alicloud-ecs-ops` + SLS | Correlate with `DescribeSuspEventDetail` |

**Correlation example:**

1. Alert `SuspUuid` → `DescribeSuspEventDetail` (process, path, user)
2. Same window → ActionTrail `LookupEvents` on affected instance ID
3. Host `/var/log/` via SLS agent (if installed)

### Traces

Security Center host alerts are not OpenTelemetry traces. Treat **alert timeline + API audit + host logs** as the distributed trace equivalent.

## Proactive Inspection Checklist

| Check | Frequency | Command / API |
|-------|-----------|---------------|
| Offline agents | Daily | `DescribeCloudCenterInstances` + clientStatus=offline |
| Critical vulns | Daily | `DescribeVulList --Type cve` |
| AK leaks | Daily | `DescribeAccesskeyLeakList` |
| Baseline summary | Weekly | `DescribeCheckWarningSummary` |
| Global stats | Weekly | `DescribeAllRegionsStatistics` |

## Alarm Storm Handling

1. Pause auto-handle playbooks
2. Aggregate `DescribeSuspEvents` by `EventName`
3. Sample 3 events with `DescribeSuspEventDetail`
4. If false positive → time-bound whitelist
5. If attack → isolate assets (confirm) + ActionTrail + RAM review

## Delegation for Observability Stack

| Capability | Skill |
|------------|-------|
| SLS query/alert | `alicloud-sls-ops` (when present) |
| CMS metric alarm | `alicloud-cms-ops` |
| API audit | `alicloud-actiontrail-ops` |
