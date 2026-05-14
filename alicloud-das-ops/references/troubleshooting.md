# DAS Troubleshooting Reference

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `InvalidDBInstanceId.NotFound` | Instance ID does not exist or not registered in DAS | Verify instance ID via engine-specific skill; run `AddHDMInstance` to register |
| `OperationDenied.InstanceStatus` | Instance not in valid state for operation | Wait for instance to reach `Running` state |
| `InvalidParameter` | Missing or malformed parameter | Cross-check request parameters against OpenAPI spec; verify `RegionId` is `cn-shanghai` |
| `Throttling` | API rate limit exceeded | Exponential backoff (1s, 2s, 4s, 8s); reduce call frequency |
| `InsufficientBalance` | Account balance insufficient for DAS Pro features | Delegate to `alicloud-billing-ops` for recharge |
| `EndpointResolutionFailure` | SDK cannot resolve DAS endpoint | Explicitly set endpoint to `das.cn-shanghai.aliyuncs.com` |
| `InternalError` / 500 | Server-side error | Retry with backoff; then HALT with RequestId |

---

## Symptom-to-Root-Cause Quick Reference

When user reports a problem, use this table to narrow down the investigation path.

| User Symptom | Most Likely Root Cause Category | DAS Diagnostic Operation |
|--------------|----------------------------------|--------------------------|
| "数据库CPU飙升" | 慢查询或并发突增 | CreateDiagnosticReport + GetPfsSqlSamples |
| "数据库连接打满" | 连接泄漏或突发流量 | GetSessionList + CreateKillInstanceSessionTask |
| "慢查询增多" | 索引缺失或SQL效率低 | GetQueryOptimizeData + 索引建议 |
| "磁盘空间不足" | 数据增长或日志未清理 | GetSpaceSummary + 空间分析 |
| "Redis内存暴涨" | 大Key或内存泄漏 | CreateCacheAnalysisJob |
| "数据库死锁" | 并发事务冲突 | CreateLatestDeadLockAnalysis |
| "SQL限流需要" | 突发流量导致系统过载 | CreateSqlLimitTask |
| "自治事件告警" | DAS检测到异常行为 | GetAutonomousNotifyEventsInRange |
| "实例注册失败" | 实例不存在或引擎不支持 | 验证实例ID + 引擎类型 |
| "巡检评分低" | 存在性能或配置问题 | GetInstanceInspections + CreateDiagnosticReport |
| "自动弹性未触发" | 配置错误或Pro许可过期 | GetDasProServiceUsage + SetAutoScalingConfig |
| "SQL洞察无数据" | Pro许可过期或存储不足 | GetDasProServiceUsage + DescribeSqlLogStatistic |
| "网络连通性失败" | 安全组或白名单配置错误 | GetDBInstanceConnectivityDiagnosis |

---

## Scenario-Based Diagnostic Playbooks

### Scenario 1: "数据库CPU飙升" (Database CPU Spike)

**Symptoms:** CMS alarm fires for high CPU usage on RDS/PolarDB instance.

**Diagnostic Flow (execute in order, stop when root cause found):**

```go
// Step 1: Verify instance is registered in DAS
// Delegate to alicloud-cms-ops to confirm alarm details

// Step 2: Create diagnostic report for the time window
req := &das.CreateDiagnosticReportRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    StartTime:  tea.String("2026-05-14T09:00:00Z"),
    EndTime:    tea.String("2026-05-14T10:00:00Z"),
}
resp, err := client.CreateDiagnosticReport(req)

// Step 3: Get SQL samples for performance analysis
sqlReq := &das.GetPfsSqlSamplesRequest{
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    StartTime:  tea.Int64(startTimeMs),
    EndTime:    tea.Int64(endTimeMs),
}
sqlResp, err := client.GetPfsSqlSamples(sqlReq)

// Step 4: Get query optimization data
optReq := &das.GetQueryOptimizeDataRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    StartTime:  tea.String("2026-05-14T00:00:00Z"),
    EndTime:    tea.String("2026-05-14T23:59:59Z"),
}
optResp, err := client.GetQueryOptimizeData(optReq)
```

**Decision Tree:**
- Diagnostic report identifies specific slow queries → Optimize identified SQL statements
- PFS samples show high `lock_time` or `rows_examined` → Add appropriate indexes
- Query governance data shows high-frequency queries → Consider query caching or optimization
- No specific SQL identified → Check instance规格; may need vertical scaling
- If CPU spike correlates with business peak → Consider read replicas or connection pooling

---

### Scenario 2: "Redis内存暴涨" (Redis Memory Spike)

**Symptoms:** CMS alarm fires for high memory usage on Redis/Tair instance.

**Diagnostic Flow:**

```go
// Step 1: Verify instance is registered in DAS
// Delegate to alicloud-redis-ops to check instance status

// Step 2: Create cache analysis job
cacheReq := &das.CreateCacheAnalysisJobRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
cacheResp, err := client.CreateCacheAnalysisJob(cacheReq)

// Step 3: Poll until job completes
for i := 0; i < 60; i++ {
    descReq := &das.DescribeCacheAnalysisJobRequest{
        InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
        JobId:      tea.String(jobId),
    }
    descResp, err := client.DescribeCacheAnalysisJob(descReq)
    if tea.ToString(descResp.Body.Data.Status) == "SUCCESS" {
        // Parse large key results
        break
    }
    time.Sleep(10 * time.Second)
}
```

**Decision Tree:**
- Large keys found (string > 10KB, hash/set/list > 10000 elements) → Split large keys
- Key count growing rapidly → Set TTL; review data retention policy
- Memory fragmentation high → Restart instance during maintenance window
- No large keys but memory still high → Check `maxmemory-policy` setting

---

### Scenario 3: "数据库连接打满" (Connection Pool Exhausted)

**Symptoms:** CMS alarm fires for high connection usage; applications report connection errors.

**Diagnostic Flow:**

```go
// Step 1: Get current active sessions
sessionReq := &das.GetSessionListRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
sessionResp, err := client.GetSessionList(sessionReq)

// Step 2: Identify problematic sessions
// Check for:
// - Long-running queries (> 60s)
// - Idle-in-transaction sessions
// - Too many connections from same host

// Step 3: Kill problematic sessions if needed
killReq := &das.CreateKillInstanceSessionTaskRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    // Specify session IDs to kill
    SessionIds: tea.String("sessionId1,sessionId2"),
}
killResp, err := client.CreateKillInstanceSessionTask(killReq)
```

**Decision Tree:**
- Many idle-in-transaction sessions → Check application transaction handling
- Many connections from same host → Check application connection pool settings
- Long-running queries blocking others → Kill sessions; optimize slow queries
- Connection count at max limit → Increase `max_connections` or scale up instance
- Connections spike during business hours → Add connection pooling middleware

---

### Scenario 4: "数据库死锁" (Database Deadlock)

**Symptoms:** Applications report deadlock errors; transactions fail.

**Diagnostic Flow:**

```go
// Step 1: Create deadlock analysis
deadlockReq := &das.CreateLatestDeadLockAnalysisRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
deadlockResp, err := client.CreateLatestDeadLockAnalysis(deadlockReq)

// Step 2: Get deadlock history
historyReq := &das.GetDeadLockHistoryRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    StartTime:  tea.String("2026-05-14T00:00:00Z"),
    EndTime:    tea.String("2026-05-14T23:59:59Z"),
}
historyResp, err := client.GetDeadLockHistory(historyReq)
```

**Decision Tree:**
- Deadlock involves specific tables → Check transaction order; ensure consistent access order
- Deadlock frequency increasing → Review application transaction logic
- Deadlock with index-related locks → Add missing indexes to reduce lock range
- Multiple deadlocks in short period → Consider lowering isolation level if appropriate

---

### Scenario 5: "巡检评分低" (Low Inspection Score)

**Symptoms:** DAS inspection score is below acceptable threshold.

**Diagnostic Flow:**

```go
// Step 1: Get current inspection score
inspectReq := &das.GetInstanceInspectionsRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
inspectResp, err := client.GetInstanceInspections(inspectReq)

// Step 2: If score < 60, create detailed diagnostic report
if score < 60 {
    reportReq := &das.CreateDiagnosticReportRequest{
        RegionId:   tea.String("cn-shanghai"),
        InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    }
    reportResp, err := client.CreateDiagnosticReport(reportReq)
}

// Step 3: Check for autonomous events
eventReq := &das.GetAutonomousNotifyEventsInRangeRequest{
    RegionId:   tea.String("cn-shanghai"),
    InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
    StartTime:  tea.String("2026-05-14T00:00:00Z"),
    EndTime:    tea.String("2026-05-14T23:59:59Z"),
}
eventResp, err := client.GetAutonomousNotifyEventsInRange(eventReq)
```

**Decision Tree:**
- Score < 60 → Create diagnostic report for detailed analysis
- Score 60-80 → Review specific low-scoring dimensions
- Score > 80 → Instance is healthy; no action needed
- Autonomous events present → Review event details for specific recommendations

---

## Diagnostic Order (Standard)

1. **Verify instance registration:** `GetInstanceInspections` — if error, run `AddHDMInstance`
2. **Check inspection score:** `GetInstanceInspections` — score < 60 indicates issues
3. **Create diagnostic report:** `CreateDiagnosticReport` for time window of interest
4. **Check autonomous events:** `GetAutonomousNotifyEventsInRange` for recent anomalies
5. **Deep dive by symptom:**
   - CPU → `GetPfsSqlSamples` + `GetQueryOptimizeData`
   - Memory (Redis) → `CreateCacheAnalysisJob`
   - Connections → `GetSessionList`
   - Deadlock → `CreateLatestDeadLockAnalysis`
   - Space → `GetSpaceSummary`
6. **Cross-skill delegation:** If instance not found → engine-specific skill; if billing issue → `alicloud-billing-ops`

---

## One-Shot Diagnostic Scripts

### Script 1: Full DAS Health Check

```go
package main

import (
    "encoding/json"
    "fmt"
    "os"
    "time"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    das "github.com/alibabacloud-go/das-20200116/v5/client"
    "github.com/alibabacloud-go/tea/tea"
)

func newDASClient() (*das.Client, error) {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("das.cn-shanghai.aliyuncs.com"),
    }
    return das.NewClient(config)
}

func main() {
    instanceId := os.Getenv("INSTANCE_ID")
    if instanceId == "" {
        fmt.Println("INSTANCE_ID is required")
        os.Exit(1)
    }

    client, err := newDASClient()
    if err != nil {
        panic(err)
    }

    fmt.Printf("=== DAS Health Check for %s ===\n\n", instanceId)

    // 1. Check inspection score
    inspectReq := &das.GetInstanceInspectionsRequest{
        RegionId:   tea.String("cn-shanghai"),
        InstanceId: tea.String(instanceId),
    }
    inspectResp, err := client.GetInstanceInspections(inspectReq)
    if err != nil {
        fmt.Printf("[1/4] Inspection: ERROR - %v\n", err)
    } else {
        b, _ := json.MarshalIndent(inspectResp.Body, "", "  ")
        fmt.Printf("[1/4] Inspection Score:\n%s\n\n", string(b))
    }

    // 2. Check autonomous events (last 24h)
    now := time.Now().UTC()
    startTime := now.Add(-24 * time.Hour).Format("2006-01-02T15:04:05Z")
    endTime := now.Format("2006-01-02T15:04:05Z")

    eventReq := &das.GetAutonomousNotifyEventsInRangeRequest{
        RegionId:   tea.String("cn-shanghai"),
        InstanceId: tea.String(instanceId),
        StartTime:  tea.String(startTime),
        EndTime:    tea.String(endTime),
    }
    eventResp, err := client.GetAutonomousNotifyEventsInRange(eventReq)
    if err != nil {
        fmt.Printf("[2/4] Autonomous Events: ERROR - %v\n", err)
    } else {
        b, _ := json.MarshalIndent(eventResp.Body, "", "  ")
        fmt.Printf("[2/4] Autonomous Events (24h):\n%s\n\n", string(b))
    }

    // 3. Check DAS Pro usage
    proReq := &das.GetDasProServiceUsageRequest{
        RegionId:   tea.String("cn-shanghai"),
        InstanceId: tea.String(instanceId),
    }
    proResp, err := client.GetDasProServiceUsage(proReq)
    if err != nil {
        fmt.Printf("[3/4] DAS Pro: ERROR - %v\n", err)
    } else {
        b, _ := json.MarshalIndent(proResp.Body, "", "  ")
        fmt.Printf("[3/4] DAS Pro Usage:\n%s\n\n", string(b))
    }

    // 4. Check SQL insight stats
    sqlReq := &das.DescribeSqlLogStatisticRequest{
        RegionId:   tea.String("cn-shanghai"),
        InstanceId: tea.String(instanceId),
    }
    sqlResp, err := client.DescribeSqlLogStatistic(sqlReq)
    if err != nil {
        fmt.Printf("[4/4] SQL Insight: ERROR - %v\n", err)
    } else {
        b, _ := json.MarshalIndent(sqlResp.Body, "", "  ")
        fmt.Printf("[4/4] SQL Insight Stats:\n%s\n", string(b))
    }
}
```

### SDK / Build Issues

#### `go get` fails for das-20200116
- Ensure Go version is >= 1.21.
- Check network access to `proxy.golang.org` or configure `GOPROXY` (e.g., `https://goproxy.cn,direct` for China regions).
- Verify the import path: `github.com/alibabacloud-go/das-20200116/v5/client`.

#### JIT build timeout
- DAS SDK compilation is usually fast (< 10s). If timeout occurs, check disk space and network.
- Pre-warm the module cache by running `go mod tidy` in the workspace before critical operations.

### Diagnostic Tips

- Always verify instance registration status with `GetInstanceInspections` before running diagnosis or optimization operations.
- For DAS Pro features (SQL insight, auto-scaling, auto-SQL optimization), first verify the instance has an active Pro license via `GetDasProServiceUsage`.
- When polling async tasks (cache analysis, diagnostic report), use the documented poll interval and max wait times. Do not poll more frequently than every 5 seconds to avoid throttling.
- DAS endpoint is fixed to `das.cn-shanghai.aliyuncs.com` — always set explicitly in SDK config.