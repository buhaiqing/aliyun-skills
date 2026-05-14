# DAS Integration Reference

## Enhanced Self-Healing Framework (MANDATORY)

**DAS is CLI-unsupported — JIT Go SDK is the ONLY execution path.**

All installation flows MUST follow the **Enhanced Self-Healing Framework** defined in [alicloud-skill-generator/references/enhanced-self-healing-framework.md](../alicloud-skill-generator/references/enhanced-self-healing-framework.md).

**Critical for DAS:**
- **Pre-flight Checks:** Network connectivity, disk space, permissions, Go runtime compatibility
- **Intelligent Error Classification:** Network, permission, resource, configuration errors
- **Multi-Path Self-Healing:** Multiple recovery strategies per error type (especially for Go runtime JIT)
- **Health Verification:** Post-installation validation with health score ≥ 8/10
- **Graceful Degradation:** Clear fallback paths when self-healing fails

**Self-Healing Priority for DAS:**
Since DAS has NO CLI fallback, Go runtime JIT download MUST succeed. The Agent MUST:
1. Use multi-version fallback (go1.24→1.23→1.22→1.21)
2. Use multi-mirror fallback (4 mirrors)
3. Implement aggressive retry logic (up to 16 attempts: 4 versions × 4 mirrors)
4. Verify Go runtime health before proceeding
5. Provide clear user guidance if all attempts fail

For detailed implementation, see [alicloud-skill-generator/references/enhanced-self-healing-framework.md](../alicloud-skill-generator/references/enhanced-self-healing-framework.md) Section 3.2.

## API Profile

- **Product:** Database Autonomy Service (DAS)
- **Former Name:** HDM (Hybrid Cloud Database Management)
- **API Version:** `2020-01-16`
- **Style:** RPC
- **Endpoint (Public):** `das.cn-shanghai.aliyuncs.com`
- **Endpoint (VPC):** `das.vpc-proxy.aliyuncs.com`
- **Service Region:** `cn-shanghai` (fixed for all SDK calls, regardless of instance region)
- **OpenAPI Explorer:** https://next.api.aliyun.com/api/DAS/2020-01-16/overview
- **API Documentation:** https://help.aliyun.com/zh/das/developer-reference/api-reference/
- **Error Center:** https://error-center.aliyun.com/product/DAS

## Go SDK

- **Import Path:** `github.com/alibabacloud-go/das-20200116/v5/client`
- **OpenAPI Base:** `github.com/alibabacloud-go/darabonba-openapi/v2/client`
- **Tea Utils:** `github.com/alibabacloud-go/tea/tea`
- **Minimum Go Version:** 1.21
- **JIT Preferred Go Version:** 1.24+

## CLI Support

DAS is **NOT** supported by the official `aliyun` CLI as of 2026-05-14.
All operations require **JIT Go SDK fallback**.

Evidence:
- Official DAS integration docs state CLI is unsupported: https://help.aliyun.com/zh/das/developer-reference/call-api-operations
- `aliyun --help` product list does not include DAS.

## Supported Database Engines

| Engine | Instance Registration | Inspection | SQL Diagnosis | Cache Analysis | Deadlock Analysis | Session Kill | Space Analysis | SQL Throttling | Auto-Scaling | SQL Insight (Pro) |
|--------|----------------------|------------|---------------|----------------|-------------------|--------------|----------------|----------------|--------------|-------------------|
| RDS MySQL | Yes | Yes | Yes | No | Yes | Yes | Yes | Yes | Yes | Yes |
| RDS PostgreSQL | Yes | Yes | Yes | No | No | Yes | Yes | Yes | Yes | Yes |
| RDS SQL Server | Yes | Yes | Yes | No | Yes* | Yes | Yes | No | No | Yes |
| PolarDB MySQL | Yes | Yes | Yes | No | Yes | Yes | Yes | Yes | Yes | Yes |
| PolarDB PostgreSQL | Yes | Yes | Yes | No | No | Yes | Yes | Yes | Yes | Yes |
| PolarDB-X 2.0 | Yes | Yes | Yes | No | Yes | Yes | Yes | Yes | Yes | Yes |
| Tair (Redis) | Yes | Yes | Yes | Yes | No | No | Yes | No | No | Yes |
| MongoDB | Yes | Yes | Yes | No | No | Yes | Yes | No | No | Yes |
| Self-managed MySQL | Yes | Yes | Yes | No | Yes | Yes | Yes | Yes | No | Yes |
| Self-managed PostgreSQL | Yes | Yes | Yes | No | No | Yes | Yes | Yes | No | Yes |
| Self-managed Redis | Yes | Yes | Yes | Yes | No | No | Yes | No | No | Yes |
| Self-managed MongoDB | Yes | Yes | Yes | No | No | Yes | Yes | No | No | Yes |

> *SQL Server deadlock analysis uses `GetDeadLockDetailList` (SQL Server-specific) rather than `CreateLatestDeadLockAnalysis`.

## Cross-Product Delegation

| Task | Delegate To |
|------|-------------|
| Create / delete RDS instance | `alicloud-rds-ops` |
| Create / delete PolarDB instance | `alicloud-polardb-ops` |
| Create / delete Tair instance | `alicloud-redis-ops` (or `alicloud-tair-ops` if exists) |
| Create / delete MongoDB instance | `alicloud-mongodb-ops` |
| RAM permission setup | `alicloud-ram-ops` |
| Billing / recharge | `alicloud-billing-ops` |
| VPC / network configuration | `alicloud-vpc-ops` |

## CloudMonitor (CMS) Integration

### CMS Alarm-Driven Diagnosis

DAS is the **secondary diagnosis skill** for database-related CMS alarms.
When CloudMonitor triggers alarms for RDS, PolarDB, or Redis instances, DAS
provides deep diagnostic analysis.

### Delegation Triggers from CMS

| CMS Alarm Namespace | CMS Alarm Metric | DAS Operations to Invoke |
|--------------------|-----------------|--------------------------|
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

### Delegation Protocol

```
[CMS Alarm Fires]
    │
    ├── 1. Identify namespace + metric from alarm rule
    ├── 2. Invoke primary diagnosis skill (e.g., alicloud-rds-ops)
    ├── 3. If DAS diagnosis is Recommended or severity = Critical:
    │       └── Invoke alicloud-das-ops for deep analysis
    ├── 4. DAS performs:
    │       ├── CreateDiagnosticReport (performance analysis)
    │       ├── GetPfsSqlSamples (SQL-level diagnosis)
    │       ├── CreateLatestDeadLockAnalysis (deadlock detection)
    │       └── CreateCacheAnalysisJob (Redis cache analysis)
    └── 5. Return diagnosis results to CMS for unified report
```

### DAS Diagnosis Flow Example

When CMS detects high CPU usage on an RDS instance:

```go
// 1. CMS alarm triggers → alicloud-cms-ops identifies acs_rds_dashboard/CpuUsage
// 2. alicloud-cms-ops invokes alicloud-rds-ops to check instance status
// 3. alicloud-cms-ops invokes alicloud-das-ops for deep diagnosis

// Create diagnostic report
req := &das20200116.CreateDiagnosticReportRequest{
    DBInstanceId: tea.String("rm-2ze8g2am97624****"),
    StartTime:    tea.String("2026-05-14T09:00:00Z"),
    EndTime:      tea.String("2026-05-14T10:00:00Z"),
}
resp, err := client.CreateDiagnosticReport(req)

// Get SQL samples for performance analysis
sqlReq := &das20200116.GetPfsSqlSamplesRequest{
    InstanceId: tea.String("rm-2ze8g2am97624****"),
    StartTime:  tea.Int64(1747198800000),
    EndTime:    tea.Int64(1747202400000),
}
sqlResp, err := client.GetPfsSqlSamples(sqlReq)
```

## DAS Pro (Enterprise Edition)

DAS Pro provides advanced features:
- SQL Insight (full SQL audit log)
- Auto-SQL optimization
- Auto-space optimization
- Auto-scaling
- Extended data retention

Pro features require:
1. Active Pro license for the instance
2. Sufficient storage quota (check via `GetDasProServiceUsage`)
3. Account balance sufficient for pay-as-you-go charges

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | AccessKey ID |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | AccessKey Secret |
| `ALIBABA_CLOUD_REGION_ID` | Yes | User's default region (used for context, but DAS SDK calls always use `cn-shanghai`) |

## Notes

- DAS is logically a **global service** with a **single physical endpoint** in Shanghai. The `RegionId` parameter in API calls must always be `cn-shanghai`, even if the target database instance is in `cn-beijing`, `cn-hangzhou`, or overseas regions.
- For VPC access, use `das.vpc-proxy.aliyuncs.com` and ensure the caller is within the Alibaba Cloud VPC network.
- Some DAS operations are **asynchronous** (cache analysis, diagnostic reports). Always implement polling with documented intervals and max wait times.
- DAS Agent (LLM chat) is a console-only feature and cannot be automated via OpenAPI.
