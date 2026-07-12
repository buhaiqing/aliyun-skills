# Observability Configuration — Alibaba Cloud Elasticsearch

> **Purpose:** Complete observability stack configuration for AIOps integration.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-17

---

## 1. Observability Architecture

### 1.1 Three Pillars of Observability

| Pillar | Data Source | Purpose | Integration |
|--------|-------------|---------|-------------|
| **Metrics** | CloudMonitor (CMS) | Quantitative system state | Real-time dashboards, alerts |
| **Logs** | Elasticsearch logs, SLS | Event-based context | Slow query analysis, error tracking |
| **Traces** | Application traces (optional) | Request flow analysis | Distributed tracing integration |

### 1.2 Observability Stack Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Observability Stack                               │
├─────────────────────────────────────────────────────────────────────┤
│  Metrics Layer                                                       │
│  ├── CloudMonitor (CMS) - Instance metrics                          │
│  ├── Elasticsearch Internal - Cluster/node stats                    │
│  ├── Custom Metrics - Business metrics                              │
│  └── Storage: Prometheus/Grafana                                    │
├─────────────────────────────────────────────────────────────────────┤
│  Logs Layer                                                          │
│  ├── Search Logs - Query execution details                          │
│  ├── Access Logs - API access records                               │
│  ├── Engine Logs - Internal ES logs                                 │
│  └── Storage: SLS (Log Service)                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Tracing Layer (Optional)                                            │
│  ├── Application Traces - Request flow                              │
│  ├── ES Query Traces - Query execution path                         │
│  └── Storage: ARMS/XRay                                             │
├─────────────────────────────────────────────────────────────────────┤
│  Visualization Layer                                                 │
│  ├── Grafana Dashboards - Metrics visualization                     │
│  ├── Kibana - Log analysis, query debugging                         │
│  ├── Console - Instance management                                  │
│  └── Custom Reports - AIOps diagnostic reports                      │
├─────────────────────────────────────────────────────────────────────┤
│  Alerting Layer                                                      │
│  ├── CMS Alert Rules - Metric-based alerts                          │
│  ├── Log-based Alerts - Error pattern alerts                        │
│  ├── Anomaly Detection - Multi-metric correlation alerts            │
│  └── Integration: Webhook, Email, SMS, DingTalk                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Metrics Configuration

### 2.1 Core Metrics Collection

| Metric Category | Metrics | Collection Method | Frequency |
|-----------------|---------|-------------------|-----------|
| **Instance** | CPU, Memory, Disk, Status | CMS API | 60 seconds |
| **JVM** | Heap, GC count, GC time | ES API `_nodes/stats` | 60 seconds |
| **Cluster** | Health, Nodes, Shards | ES API `_cluster/health` | 60 seconds |
| **Performance** | Search latency, Indexing latency | CMS API | 60 seconds |
| **Operations** | QPS, Connection count | CMS API | 60 seconds |

### 2.2 CMS Metric Collection Setup

```go
func setupMetricsCollection(instanceId string) {
    // CMS namespace: acs_elasticsearch
    metrics := []string{
        "NodeCPUUtilization",
        "NodeStatsSystemMemoryUtilization",
        "NodeDiskUtilization",
        "NodeHeapMemoryUtilization",
        "JVMGCOldCollectionCount",
        "JVMGCOldCollectionDuration",
        "ClusterSearchLatency",
        "ClusterIndexingLatency",
        "ClusterQueryQPS",
        "ClusterIndexQPS",
        "ClusterStatus",
        "ClusterNodeCount",
    }
    
    for _, metric := range metrics {
        // Create metric collection rule
        // Delegate to alicloud-cms-ops if available
        fmt.Printf("Setting up collection for: %s\n", metric)
    }
}
```

### 2.3 Custom Metrics Definition

```yaml
Custom Metrics:

Business Metrics:
  - QuerySuccessRate: (successful_queries / total_queries) * 100
  - IndexingThroughput: documents_indexed_per_second
  - CacheHitRate: (cache_hits / total_requests) * 100
  - ShardBalanceScore: standard_deviation(shard_count_per_node)

Derived Metrics:
  - GCPressureIndex: gc_collection_time / total_runtime
  - QueryEfficiencyScore: search_qps / avg_latency
  - DiskGrowthRate: disk_usage_change_per_hour
```

---

## 3. Logs Configuration

### 3.1 Log Types and Retention

| Log Type | Content | Retention | Purpose |
|----------|---------|-----------|---------|
| **Search Log** | Query execution, timing, errors | 7 days | Slow query analysis |
| **Access Log** | Client access, authentication | 30 days | Security audit |
| **Engine Log** | ES internal operations, errors | 7 days | Troubleshooting |
| **Audit Log** | Configuration changes | 90 days | Compliance |

### 3.2 Log Collection via SLS

```go
func setupLogCollection(instanceId string) {
    // ListSearchLog API for Elasticsearch logs
    request := &elasticsearch.ListSearchLogRequest{
        InstanceId: tea.String(instanceId),
        StartTime: tea.String(time.Now().Add(-24*time.Hour).Format("2006-01-02T15:04:05Z")),
        EndTime:   tea.String(time.Now().Format("2006-01-02T15:04:05Z")),
        Query:     tea.String(""), // All logs
    }
    
    // Enable SLS integration
    // Delegate to alicloud-sls-ops if available
    fmt.Println("Log collection configured")
}
```

### 3.3 Slow Query Log Analysis

```go
func analyzeSlowQueries(instanceId string, thresholdMs int) []SlowQuery {
    logs, _ := client.ListSearchLog(&elasticsearch.ListSearchLogRequest{
        InstanceId: tea.String(instanceId),
        StartTime: tea.String(startTime),
        EndTime:   tea.String(endTime),
        Query:     tea.String("slow"), // Filter slow queries
    })
    
    slowQueries := []SlowQuery{}
    
    for _, log := range logs.Body.Result.Logs {
        content := tea.ToString(log.Content)
        
        // Extract query time
        if strings.Contains(content, "took") {
            tookMs := extractQueryTime(content)
            if tookMs > thresholdMs {
                slowQueries = append(slowQueries, SlowQuery{
                    Query:      extractQuery(content),
                    TookMs:     tookMs,
                    Timestamp:  tea.ToString(log.Timestamp),
                    Indices:    extractIndices(content),
                })
            }
        }
    }
    
    return slowQueries
}

type SlowQuery struct {
    Query     string
    TookMs    int
    Timestamp string
    Indices   []string
}
```

---

## 4. Dashboards Configuration

### 4.1 Grafana Dashboard Panels

**Dashboard 1: Instance Overview**
```
Panel Group: Instance Health
- Instance Status (gauge)
- Cluster Health (gauge)
- Node Count (stat)
- Uptime (stat)

Panel Group: Resource Utilization
- CPU Utilization (graph, 7d)
- Memory Utilization (graph, 7d)
- Disk Utilization (graph, 7d)
- JVM Heap (graph, 7d)
```

**Dashboard 2: Performance Metrics**
```
Panel Group: Query Performance
- Search QPS (graph)
- Search Latency (P50, P95, P99)
- Slow Query Count (counter)
- Query Cache Hit Rate (gauge)

Panel Group: Write Performance
- Indexing QPS (graph)
- Indexing Latency (graph)
- Bulk Queue Depth (gauge)
- Merge Operations (graph)
```

**Dashboard 3: JVM Analysis**
```
Panel Group: JVM Health
- Heap Memory Usage (graph)
- GC Collection Count (graph)
- GC Pause Time (graph)
- Thread Count (stat)

Panel Group: GC Analysis
- Young GC Frequency (graph)
- Full GC Frequency (graph)
- GC Time Distribution (heatmap)
```

**Dashboard 4: Cluster Health**
```
Panel Group: Cluster State
- Cluster Health (gauge)
- Active Shards (stat)
- Unassigned Shards (stat)
- Relocating Shards (stat)

Panel Group: Node Distribution
- Node Status Table (table)
- Shard Distribution (pie)
- Disk Usage per Node (bar)
- Load per Node (heatmap)
```

### 4.2 Dashboard JSON Template

```json
{
  "dashboard": {
    "title": "Elasticsearch Observability",
    "panels": [
      {
        "title": "Instance CPU",
        "type": "graph",
        "targets": [
          {
            "expr": "acs_elasticsearch_NodeCPUUtilization{instanceId=\"$instance_id\"}",
            "legendFormat": "CPU %"
          }
        ],
        "thresholds": [
          {"value": 80, "color": "yellow"},
          {"value": 90, "color": "red"}
        ]
      },
      {
        "title": "JVM Heap",
        "type": "graph",
        "targets": [
          {
            "expr": "acs_elasticsearch_NodeHeapMemoryUtilization{instanceId=\"$instance_id\"}",
            "legendFormat": "Heap %"
          }
        ],
        "thresholds": [
          {"value": 85, "color": "yellow"},
          {"value": 95, "color": "red"}
        ]
      }
    ]
  }
}
```

---

## 5. Alerting Configuration

### 5.1 Alert Rule Categories

| Category | Alert Rules | Severity |
|----------|-------------|----------|
| **Instance Health** | Status != Normal, InstanceDown | Critical |
| **Cluster Health** | ClusterYellow, ClusterRed, NodeDown | Critical |
| **Resource** | CPUHigh, DiskHigh, JVMHigh | Warning |
| **Performance** | LatencyHigh, QpsAnomaly | Warning |
| **Anomaly** | MultiMetricCorrelation | Warning |

### 5.2 Complete Alert Rule Set

```yaml
Alert Rules:

Instance Health:
  - ES-Instance-Down:
      condition: InstanceStatus != "Normal" for 2 min
      severity: Critical
      actions: [Notify, TriggerDiagnosis]
      
  - ES-Instance-Creating-Stuck:
      condition: InstanceStatus = "Activating" for > 10 min
      severity: Warning
      actions: [Notify, CheckVPC]

Cluster Health:
  - ES-Cluster-Yellow:
      condition: ClusterHealth = "yellow" for 5 min
      severity: Warning
      actions: [Notify, CheckShards]
      
  - ES-Cluster-Red:
      condition: ClusterHealth = "red"
      severity: Critical
      actions: [Notify, EmergencyResponse]
      
  - ES-Node-Down:
      condition: NodeCount < expected
      severity: Critical
      actions: [Notify, RestartNode]

Resource Alerts:
  - ES-CPU-High:
      condition: NodeCPUUtilization > 80% for 5 min
      severity: Warning
      actions: [Notify, OptimizeQueries]
      
  - ES-CPU-Critical:
      condition: NodeCPUUtilization > 90% for 3 min
      severity: Critical
      actions: [Notify, ScaleUp]
      
  - ES-Disk-High:
      condition: NodeDiskUtilization > 80% for 10 min
      severity: Warning
      actions: [Notify, CleanupOrExpand]
      
  - ES-Disk-Critical:
      condition: NodeDiskUtilization > 95% for 5 min
      severity: Critical
      actions: [Notify, ImmediateExpand]
      
  - ES-JVM-High:
      condition: NodeHeapMemoryUtilization > 85% for 5 min
      severity: Warning
      actions: [Notify, TuneJVM]

Performance Alerts:
  - ES-Latency-High:
      condition: SearchLatency > 500ms for 5 min
      severity: Warning
      actions: [Notify, AnalyzeSlowQueries]
      
  - ES-Qps-Anomaly:
      condition: ClusterQueryQPS change > 50% from baseline
      severity: Warning
      actions: [Notify, AnalyzeWorkload]

Anomaly Alerts:
  - ES-MultiMetric-P1:
      condition: CPU>80% AND JVM>85% AND Latency>200ms
      severity: Warning
      actions: [Notify, TriggerRemediation]
      pattern: CPU-JVM-Heap-Correlation
      
  - ES-MultiMetric-P5:
      condition: FullGC>10/hr AND GCPause>500ms AND P95>1s
      severity: Critical
      actions: [Notify, JVMTuning]
      pattern: JVM-GC-Latency-Correlation
```

### 5.3 Alert Notification Channels

```yaml
Notification Channels:

Webhook:
  url: https://alert-webhook.internal/api/es-alerts
  format: JSON
  headers: {"Content-Type": "application/json"}

Email:
  recipients: [ops-team@example.com]
  subject: "Elasticsearch Alert: {{alert_name}}"

SMS:
  recipients: [oncall-phone]
  template: "ES Alert: {{alert_name}} on {{instance_id}}"

DingTalk/Slack:
  webhook: https://dingtalk-webhook
  template: |
    🚨 Elasticsearch Alert
    Alert: {{alert_name}}
    Instance: {{instance_id}}
    Severity: {{severity}}
    Value: {{current_value}}
    Threshold: {{threshold}}
    Action: {{recommended_action}}
```

---

## 6. Observability Integration with AIOps

### 6.1 Observability → AIOps Data Flow

```
Metrics → Anomaly Detection → Pattern Matching → Remediation
Logs → Error Analysis → Root Cause Hypothesis → Diagnosis
Traces → Request Analysis → Bottleneck Identification → Optimization
```

### 6.2 Integration Points

| Observability Component | AIOps Integration | Output |
|------------------------|-------------------|--------|
| **CMS Metrics** | proactive-inspection.md | Multi-metric anomaly patterns |
| **Search Logs** | troubleshooting.md | Error pattern classification |
| **Alert Rules** | alarm-storm-handling.md | Deduplication, suppression |
| **Dashboards** | diagnostic-report-schema.md | Visualization in reports |

---

## 7. Observability Best Practices

### 7.1 Configuration Checklist

```
Metrics Collection:
□ CMS namespace configured (acs_elasticsearch)
□ All core metrics collected
□ Custom metrics defined (if needed)
□ Collection frequency appropriate

Logs Collection:
□ SLS project/logstore created
□ Elasticsearch logs enabled
□ Retention policy set
□ Log query templates ready

Dashboards:
□ Grafana dashboards created
□ Key panels configured
□ Thresholds visualized
□ Drill-down enabled

Alert Rules:
□ Critical alerts configured
□ Warning alerts configured
□ Notification channels set
□ Remediation actions linked

Integration:
□ AIOps patterns integrated
□ Cross-skill delegation ready
□ Report generation automated
```

---

*For monitoring metrics details, see [monitoring.md](monitoring.md). For proactive inspection, see [../operations/proactive-inspection.md](../operations/proactive-inspection.md).*