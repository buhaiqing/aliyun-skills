# DAS API Documentation Mapping

> **Purpose:** Provide a canonical mapping between skill operations and their
> official Alibaba Cloud API documentation URLs. This file is the single source
> of truth for API doc links and should be updated whenever Alibaba Cloud
> publishes new API versions or changes documentation URLs.
>
> **Maintenance Rule:** When adding a new operation to `SKILL.md`, add its doc
> link here first, then reference it in the operation section.

## SQL Concurrency Control (SQL 并发控制 / SQL 限流)

| Operation | API Doc URL | SDK Request Type | SDK Response Type |
|-----------|-------------|------------------|-------------------|
| `EnableSqlConcurrencyControl` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-enablesqlconcurrencycontrol | `EnableSqlConcurrencyControlRequest` | `EnableSqlConcurrencyControlResponse` |
| `DisableSqlConcurrencyControl` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-disablesqlconcurrencycontrol | `DisableSqlConcurrencyControlRequest` | `DisableSqlConcurrencyControlResponse` |
| `DisableAllSqlConcurrencyControlRules` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-disableallsqlconcurrencycontrolrules | `DisableAllSqlConcurrencyControlRulesRequest` | `DisableAllSqlConcurrencyControlRulesResponse` |
| `GetRunningSqlConcurrencyControlRules` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getrunningsqlconcurrencycontrolrules | `GetRunningSqlConcurrencyControlRulesRequest` | `GetRunningSqlConcurrencyControlRulesResponse` |
| `GetSqlConcurrencyControlRulesHistory` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getsqlconcurrencycontrolruleshistory | `GetSqlConcurrencyControlRulesHistoryRequest` | `GetSqlConcurrencyControlRulesHistoryResponse` |
| `GetSqlConcurrencyControlKeywordsFromSqlText` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getsqlconcurrencycontrolkeywordsfromsqltext | `GetSqlConcurrencyControlKeywordsFromSqlTextRequest` | `GetSqlConcurrencyControlKeywordsFromSqlTextResponse` |

## Legacy SQL Throttling

| Operation | API Doc URL | SDK Request Type | SDK Response Type |
|-----------|-------------|------------------|-------------------|
| `CreateSqlLimitTask` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-createsqllimittask | `CreateSqlLimitTaskRequest` | `CreateSqlLimitTaskResponse` |
| `DescribeSqlLimitTasks` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-describesqllimittasks | `DescribeSqlLimitTasksRequest` | `DescribeSqlLimitTasksResponse` |

## Instance Management

| Operation | API Doc URL | SDK Request Type | SDK Response Type |
|-----------|-------------|------------------|-------------------|
| `AddHDMInstance` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-addhdminstance | `AddHDMInstanceRequest` | `AddHDMInstanceResponse` |
| `GetInstanceInspections` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getinstanceinspections | `GetInstanceInspectionsRequest` | `GetInstanceInspectionsResponse` |

## Diagnostics & Analysis

| Operation | API Doc URL | SDK Request Type | SDK Response Type |
|-----------|-------------|------------------|-------------------|
| `CreateDiagnosticReport` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-creatediagnosticreport | `CreateDiagnosticReportRequest` | `CreateDiagnosticReportResponse` |
| `CreateCacheAnalysisJob` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-createcacheanalysisjob | `CreateCacheAnalysisJobRequest` | `CreateCacheAnalysisJobResponse` |
| `CreateLatestDeadLockAnalysis` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-createlatestdeadlockanalysis | `CreateLatestDeadLockAnalysisRequest` | `CreateLatestDeadLockAnalysisResponse` |
| `GetSpaceSummary` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getspacesummary | `GetSpaceSummaryRequest` | `GetSpaceSummaryResponse` |

## Session Management

| Operation | API Doc URL | SDK Request Type | SDK Response Type |
|-----------|-------------|------------------|-------------------|
| `CreateKillInstanceSessionTask` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-createkillinstancesessiontask | `CreateKillInstanceSessionTaskRequest` | `CreateKillInstanceSessionTaskResponse` |
| `GetSessionList` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getsessionlist | `GetSessionListRequest` | `GetSessionListResponse` |

## Events & Subscriptions

| Operation | API Doc URL | SDK Request Type | SDK Response Type |
|-----------|-------------|------------------|-------------------|
| `SetEventSubscription` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-seteventsubscription | `SetEventSubscriptionRequest` | `SetEventSubscriptionResponse` |
| `GetEventSubscription` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-geteventsubscription | `GetEventSubscriptionRequest` | `GetEventSubscriptionResponse` |
| `GetAutonomousNotifyEventsInRange` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getautonomousnotifyeventsinrange | `GetAutonomousNotifyEventsInRangeRequest` | `GetAutonomousNotifyEventsInRangeResponse` |
| `GetAutonomousNotifyEventContent` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getautonomousnotifyeventcontent | `GetAutonomousNotifyEventContentRequest` | `GetAutonomousNotifyEventContentResponse` |

## Auto-Scaling

| Operation | API Doc URL | SDK Request Type | SDK Response Type |
|-----------|-------------|------------------|-------------------|
| `SetAutoScalingConfig` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-setautoscalingconfig | `SetAutoScalingConfigRequest` | `SetAutoScalingConfigResponse` |
| `GetAutoScalingConfig` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getautoscalingconfig | `GetAutoScalingConfigRequest` | `GetAutoScalingConfigResponse` |

## SQL Insight & Query Governance

| Operation | API Doc URL | SDK Request Type | SDK Response Type |
|-----------|-------------|------------------|-------------------|
| `DescribeSqlLogStatistic` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-describesqllogstatistic | `DescribeSqlLogStatisticRequest` | `DescribeSqlLogStatisticResponse` |
| `GetQueryOptimizeData` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getqueryoptimizedata | `GetQueryOptimizeDataRequest` | `GetQueryOptimizeDataResponse` |
| `GetPfsSqlSamples` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getpfssqlsamples | `GetPfsSqlSamplesRequest` | `GetPfsSqlSamplesResponse` |

## DAS Pro

| Operation | API Doc URL | SDK Request Type | SDK Response Type |
|-----------|-------------|------------------|-------------------|
| `GetDasProServiceUsage` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getdasproserviceusage | `GetDasProServiceUsageRequest` | `GetDasProServiceUsageResponse` |

## Connectivity Diagnosis

| Operation | API Doc URL | SDK Request Type | SDK Response Type |
|-----------|-------------|------------------|-------------------|
| `GetDBInstanceConnectivityDiagnosis` | https://help.aliyun.com/zh/das/developer-reference/api-das-2020-01-16-getdbinstanceconnectivitydiagnosis | `GetDBInstanceConnectivityDiagnosisRequest` | `GetDBInstanceConnectivityDiagnosisResponse` |

---

## Update Log

| Date | Change | Operator |
|------|--------|----------|
| 2026-06-01 | Added SQL concurrency control APIs (EnableSqlConcurrencyControl, DisableSqlConcurrencyControl, DisableAllSqlConcurrencyControlRules, GetRunningSqlConcurrencyControlRules, GetSqlConcurrencyControlRulesHistory, GetSqlConcurrencyControlKeywordsFromSqlText) | AGI |
| 2026-05-14 | Initial mapping with core DAS operations | AGI |
