# Observability Integration Guide

> 可观测性三位一体：Metrics（CMS）→ Logs（SLS）→ Traces（ARMS）的联动诊断链路。

---

## Overview

现代云原生运维需要 **Metrics + Logs + Traces** 三位一体的可观测性支撑。CMS 提供 Metrics 层，但根因定位往往需要下沉到 Logs 和 Traces 层。

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Metrics       │────▶│     Logs        │────▶│    Traces       │
│   (CMS)         │     │    (SLS)        │     │   (ARMS)        │
│                 │     │                 │     │                 │
│ CPU/Memory/IO   │     │ Application     │     │ Distributed     │
│ Connection/     │     │ Error/Access    │     │ Call Chain      │
│ Network         │     │ Slow Query      │     │ Latency Breakdown│
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────────┐
                    │   Unified Diagnosis  │
                    │   Root Cause Report  │
                    └─────────────────────┘
```

---

## Metrics → Logs 联动

### When to Delegate to SLS

| CMS Metric Pattern | SLS Query Target | Purpose |
|-------------------|-----------------|---------|
| CPUUtilization spike | Application error log | Find error burst causing CPU spike |
| MemoryUsage leak | Application memory log | Find memory allocation pattern |
| ConnectionUsage high | Database access log | Find connection leak source |
| DropConnection (SLB) | Nginx/Access log | Find dropped request details |
| DiskUsage high | System log | Find large file write operations |

### SLS Query Patterns

```sql
-- 查询特定时间段内的错误日志（按时间关联 CMS 告警）
* AND (__time__ >= 1715673600 AND __time__ <= 1715677200)
AND (level: ERROR OR status: 500)
| SELECT COUNT(*) as error_count, __source__
GROUP BY __source__
ORDER BY error_count DESC

-- 查询慢请求（与 SLB DropConnection 关联）
* AND request_time > 5
AND (__time__ >= 1715673600 AND __time__ <= 1715677200)
| SELECT COUNT(*) as slow_count, upstream_addr
GROUP BY upstream_addr
ORDER BY slow_count DESC

-- 查询数据库慢查询（与 RDS CPU 告警关联）
* AND query_time > 2
AND (__time__ >= 1715673600 AND __time__ <= 1715677200)
| SELECT sql_text, COUNT(*) as count, AVG(query_time) as avg_time
GROUP BY sql_text
ORDER BY count DESC
LIMIT 10
```

### CLI Integration (SLS)

```bash
# 使用 aliyun CLI 查询 SLS（如果已安装 sls 插件）
# 或直接使用 SLS SDK

# 示例：查询指定时间范围内的错误日志
aliyun log GetLogs \
  --ProjectName {{user.sls_project}} \
  --LogstoreName {{user.sls_logstore}} \
  --From $(date -d '1 hour ago' +%s) \
  --To $(date +%s) \
  --Query '* AND (level: ERROR OR status: 500)' \
  --Line 100
```

---

## Metrics → Traces 联动

### When to Delegate to ARMS

| CMS Metric Pattern | ARMS Trace Target | Purpose |
|-------------------|------------------|---------|
| CPUUtilization spike | Application trace | Find hot method/path |
| MemoryUsage leak | JVM/Go memory trace | Find memory allocation hotspot |
| ConnectionUsage high | Database trace | Find slow SQL and connection hold time |
| Latency increase | RPC/HTTP trace | Find bottleneck service |
| Error rate increase | Error trace | Find error root service |

### ARMS Query Patterns

```bash
# ARMS 应用监控 API（通过 OpenAPI）
# 查询指定时间范围内的慢调用

aliyun arms GetMultipleTrace \
  --RegionId {{user.region}} \
  --StartTime $(date -d '1 hour ago' +%s)000 \
  --EndTime $(date +%s)000 \
  --ServiceName {{user.service_name}} \
  --MinDuration 5000
```

### Trace Analysis Workflow

1. **Identify Slow Span**: From ARMS trace, find the span with highest latency
2. **Correlate with Metrics**: Check if the slow span's service has CMS metric anomaly
3. **Drill Down to Logs**: Query SLS logs for the specific trace_id
4. **Synthesize Root Cause**: Combine trace latency breakdown + metric anomaly + log evidence

---

## Unified Observability Query

### Go SDK: Multi-Source Correlation

```go
package main

import (
	"fmt"
	"os"
	"time"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	cms20190101 "github.com/alibabacloud-go/cms-20190101/v7/client"
)

// ObservabilityQuery correlates CMS metrics with SLS logs and ARMS traces
type ObservabilityQuery struct {
	ResourceID    string
	Namespace     string
	MetricName    string
	AlarmTime     time.Time
	SLSProject    string
	SLSLogstore   string
	ARMSService   string
}

func (q *ObservabilityQuery) Execute() (*DiagnosisReport, error) {
	// 1. Query CMS metrics around alarm time
	metrics, err := q.queryCMSMetrics()
	if err != nil {
		return nil, fmt.Errorf("CMS query failed: %w", err)
	}

	// 2. Query SLS logs in same time window
	logs, err := q.querySLSLogs()
	if err != nil {
		// Log warning but continue
		fmt.Fprintf(os.Stderr, "SLS query warning: %v\n", err)
	}

	// 3. Query ARMS traces for slow calls
	traces, err := q.queryARMSTraces()
	if err != nil {
		fmt.Fprintf(os.Stderr, "ARMS query warning: %v\n", err)
	}

	// 4. Correlate and generate report
	report := q.correlate(metrics, logs, traces)
	return report, nil
}

func (q *ObservabilityQuery) queryCMSMetrics() (map[string][]DataPoint, error) {
	// Implementation: query multiple metrics for the resource
	// See Multi-Metric Anomaly Inspection in SKILL.md
	return nil, nil
}

func (q *ObservabilityQuery) querySLSLogs() ([]LogEntry, error) {
	// Implementation: query SLS logs for the time window
	// Requires SLS SDK or API
	return nil, nil
}

func (q *ObservabilityQuery) queryARMSTraces() ([]TraceEntry, error) {
	// Implementation: query ARMS traces for slow calls
	// Requires ARMS SDK or API
	return nil, nil
}

func (q *ObservabilityQuery) correlate(metrics map[string][]DataPoint, logs []LogEntry, traces []TraceEntry) *DiagnosisReport {
	// Implementation: correlate findings across all three sources
	return &DiagnosisReport{}
}

type DiagnosisReport struct {
	Metrics    map[string][]DataPoint
	Logs       []LogEntry
	Traces     []TraceEntry
	RootCause  string
	Confidence float64
}

type LogEntry struct {
	Time    time.Time
	Level   string
	Message string
	TraceID string
}

type TraceEntry struct {
	TraceID   string
	Service   string
	Operation string
	Duration  int64
	Status    string
}
```

---

## Observability Skill Delegation

### Delegation Matrix

| Observability Layer | Skill | When to Delegate |
|--------------------|-------|-----------------|
| Metrics | `alicloud-cms-ops` | Always primary for metric anomaly |
| Logs | `alicloud-sls-ops` (if exists) | When metric anomaly needs log evidence |
| Traces | `alicloud-arms-ops` (if exists) | When latency/performance issue |
| DAS AI Diagnosis | `alicloud-das-ops` | When database performance issue |

### Fallback Strategy

If SLS/ARMS skills are not available:

1. **SLS Fallback**: Use `aliyun log` CLI commands directly
2. **ARMS Fallback**: Use ARMS OpenAPI directly via SDK
3. **Console Fallback**: Provide console URL for manual investigation

---

## Integration Patterns

### Pattern 1: Metrics-Triggered Log Investigation

```
[CMS Alarm: CPUUtilization > 95%]
    │
    ├── 1. Query CMS metrics (confirm + trend)
    ├── 2. If confirmed → Query SLS error logs for same time window
    ├── 3. Correlate: error burst time vs CPU spike time
    ├── 4. If correlated → Identify error source
    └── 5. Generate report: CPU spike caused by error burst
```

### Pattern 2: Latency Investigation with Traces

```
[CMS Alarm: SLB Latency > 5s]
    │
    ├── 1. Query CMS SLB metrics (confirm + backend correlation)
    ├── 2. If backend latency high → Query ARMS traces for slow calls
    ├── 3. Identify slow span (service + method)
    ├── 4. Query SLS logs for that service in same window
    └── 5. Generate report: Latency caused by slow SQL in service X
```

### Pattern 3: Full Stack Root Cause

```
[CMS Alarm: RDS ConnectionUsage > 90%]
    │
    ├── 1. Query CMS RDS metrics (confirm + CPU correlation)
    ├── 2. If CPU low → Connection leak suspected
    ├── 3. Query ARMS traces for database calls (connection hold time)
    ├── 4. Query SLS access logs for connection pool stats
    ├── 5. Delegate DAS for SQL diagnosis
    └── 6. Generate report: Connection leak in service X, method Y
```

---

## References

- [Alibaba Cloud SLS Documentation](https://help.aliyun.com/zh/sls/)
- [Alibaba Cloud ARMS Documentation](https://help.aliyun.com/zh/arms/)
- [OpenTelemetry Trace Specification](https://opentelemetry.io/docs/concepts/signals/traces/)
- [Three Pillars of Observability](https://www.oreilly.com/library/view/distributed-systems-observability/9781492033431/ch04.html)
