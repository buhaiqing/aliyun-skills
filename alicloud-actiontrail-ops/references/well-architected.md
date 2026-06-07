# Well-Architected Assessment — ActionTrail (操作审计)

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to ActionTrail.

## 安全 (Security) — *Primary Pillar for ActionTrail*

| Area | Guidance |
|------|----------|
| **IAM** | Require: `actiontrail:LookupEvents`, `DescribeTrails` (read). `CreateTrail` (config). Scope to `acs:actiontrail:*:*:*` |
| **Audit Trail** | ActionTrail IS the audit layer. Inspect for unauthorized API calls, privilege escalation, trail deletion |
| **Credential Security** | Trail delivery buckets must have SSE-KMS encryption. Restrictive OSS/SLS policies |
| **Trail Protection** | TrailConcealmentInsight detects attempts to disable/delete trails — attacker covering tracks |

## 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | Compliance Trail with `TrailRegion: All`, `EventRW: All` — no audit gaps |
| **面向精细的运维管控** | 7 InsightTypes cover IP, AK, policy changes, password changes, trail concealment |
| **面向风险的应急快恢** | Trail deleted → recreate Compliance Trail immediately. Restore from OSS delivery |

## 成本 (Cost)

Event storage: free for 90 days. OSS delivery for long-term (use lifecycle rules to tier cold data). Insights: free.

## 效率 (Efficiency)

- **Filters:** Filter `LookupEvents` by `ServiceName`, `EventName`, `EventAccessKeyId`
- **Insight Events:** Automated anomaly detection eliminates manual review
- **CI/CD:** Export to SLS for automated compliance scanning

## 性能 (Performance)

`LookupEvents`: ≤ 30 days per query, within 90 days. 50 results per page. `LookupInsightEvents`: 24h delay after enabling.