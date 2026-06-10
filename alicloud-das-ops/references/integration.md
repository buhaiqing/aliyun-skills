# DAS Integration Reference

## Enhanced Self-Healing Framework

**DAS is CLI-unsupported — JIT Go SDK is the ONLY execution path.**

All installation flows MUST follow the **Enhanced Self-Healing Framework** defined in [alicloud-skill-generator/references/enhanced-self-healing-framework.md](../../alicloud-skill-generator/references/enhanced-self-healing-framework.md).

**Critical for DAS:**
- Pre-flight: Network, disk, permissions, Go runtime
- Multi-version fallback (go1.24→1.23→1.22→1.21)
- Multi-mirror fallback (4 mirrors)
- Aggressive retry (16 attempts: 4 versions × 4 mirrors)
- Verify Go runtime health before proceeding

## API Profile

- **Product:** Database Autonomy Service (DAS, formerly HDM)
- **API Version:** `2020-01-16` (RPC style)
- **Endpoint:** `das.cn-shanghai.aliyuncs.com` (public), `das.vpc-proxy.aliyuncs.com` (VPC)
- **Service Region:** `cn-shanghai` (fixed, regardless of instance region)
- **OpenAPI Explorer:** https://next.api.aliyun.com/api/DAS/2020-01-16/overview
- **Error Center:** https://error-center.aliyun.com/product/DAS

## Go SDK

- **Import:** `github.com/alibabacloud-go/das-20200116/v5/client`
- **OpenAPI Base:** `github.com/alibabacloud-go/darabonba-openapi/v2/client`
- **Tea Utils:** `github.com/alibabacloud-go/tea/tea`
- **Go Version:** >=1.21 (JIT preferred: 1.24+)

## CLI Support

DAS is **NOT** supported by `aliyun` CLI as of 2026-05-14. All operations require JIT Go SDK.

## Engine Support

| Engine | Reg | Insp | Diag | Cache | Deadlk | Kill | Space | Throttle | Scale | Insight |
|--------|-----|------|------|-------|--------|------|-------|----------|-------|---------|
| RDS MySQL | Y | Y | Y | - | Y | Y | Y | Y | Y | Y |
| RDS PostgreSQL | Y | Y | Y | - | - | Y | Y | Y | Y | Y |
| RDS SQL Server | Y | Y | Y | - | Y* | Y | Y | - | - | Y |
| PolarDB MySQL | Y | Y | Y | - | Y | Y | Y | Y | Y | Y |
| PolarDB PG | Y | Y | Y | - | - | Y | Y | Y | Y | Y |
| PolarDB-X 2.0 | Y | Y | Y | - | Y | Y | Y | Y | Y | Y |
| Tair (Redis) | Y | Y | Y | Y | - | - | Y | - | - | Y |
| MongoDB | Y | Y | Y | - | - | Y | Y | - | - | Y |
| Self MySQL | Y | Y | Y | - | Y | Y | Y | Y | - | Y |
| Self PG | Y | Y | Y | - | - | Y | Y | Y | - | Y |
| Self Redis | Y | Y | Y | Y | - | - | Y | - | - | Y |
| Self MongoDB | Y | Y | Y | - | - | Y | Y | - | - | Y |

> \*SQL Server uses `GetDeadLockDetailList` (SQL Server-specific) instead of `CreateLatestDeadLockAnalysis`.

## Cross-Product Delegation

| Task | Delegate To |
|------|-------------|
| Create/delete RDS instance | `alicloud-rds-ops` |
| Create/delete PolarDB instance | `alicloud-polar-mysql-ops` / `alicloud-polar-pg-ops` / `alicloud-polar-oracle-ops` |
| Create/delete Tair instance | `alicloud-redis-ops` |
| Create/delete MongoDB instance | `alicloud-mongodb-ops` |
| RAM permission setup | `alicloud-ram-ops` |
| Billing / recharge | `alicloud-billing-ops` |
| VPC / network | `alicloud-vpc-ops` |

## CloudMonitor (CMS) Integration

### CMS Alarm → DAS Diagnosis

| CMS Alarm Namespace | Metric | DAS Operations |
|--------------------|--------|----------------|
| `acs_rds_dashboard` | ConnectionUsage | `CreateLatestDeadLockAnalysis`, `GetQueryOptimizeData` |
| `acs_rds_dashboard` | CpuUsage | `CreateDiagnosticReport`, `GetPfsSqlSamples` |
| `acs_rds_dashboard` | IOPSUsage | `CreateDiagnosticReport`, `GetPfsSqlSamples` |
| `acs_rds_dashboard` | MemoryUsage | `CreateDiagnosticReport` |
| `acs_polardb_dashboard` | CpuUsage | `CreateDiagnosticReport`, `GetPfsSqlSamples` |
| `acs_polardb_dashboard` | ConnectionUsage | `CreateLatestDeadLockAnalysis`, `GetQueryOptimizeData` |
| `acs_polardb_dashboard` | IOPSUsage | `CreateDiagnosticReport`, `GetPfsSqlSamples` |
| `acs_kvstore_dashboard` | CpuUsage | `CreateCacheAnalysisJob` |
| `acs_kvstore_dashboard` | MemoryUsage | `CreateCacheAnalysisJob` |
| `acs_mongodb_dashboard` | CpuUsage | `CreateDiagnosticReport` |

### Diagnosis Flow

```
CMS alarm → identify namespace+metric → invoke primary skill (rds-ops etc.)
→ if DAS diagnosis recommended/severity=Critical → invoke alicloud-das-ops
→ DAS: CreateDiagnosticReport + GetPfsSqlSamples + CreateLatestDeadLockAnalysis + CreateCacheAnalysisJob
→ return results for unified report
```

## DAS Pro (Enterprise Edition)

Advanced features (SQL Insight, auto-SQL optimization, auto-space, auto-scaling, extended retention):
1. Active Pro license for the instance
2. Sufficient storage quota (`GetDasProServiceUsage`)
3. Account balance for pay-as-you-go charges

## Notes

- DAS is a **global service** with a **single physical endpoint** in Shanghai. `RegionId` must always be `cn-shanghai`.
- For VPC: `das.vpc-proxy.aliyuncs.com`, caller must be in Alibaba Cloud VPC.
- Some operations are **async** (cache analysis, diagnostic reports). Implement polling with documented intervals/max wait.
- DAS Agent (LLM chat) is console-only, not automatable via OpenAPI.
