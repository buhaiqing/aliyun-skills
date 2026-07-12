# Monitoring & Alerts — Alibaba Cloud Elasticsearch

> **Purpose:** Metrics namespaces, key performance indicators, alert thresholds, dashboard setup.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-17

---

## 1. Monitoring Architecture

### Data Sources

| Source | Type | Purpose |
|--------|------|---------|
| **CloudMonitor (CMS)** | Metrics | Instance-level performance metrics |
| **Elasticsearch Internal** | Cluster health | Node-level, index-level metrics |
| **SLS (Log Service)** | Logs | Search logs, slow queries, access logs |
| **ActionTrail** | Audit | API call history |

---

## 2. Key Metrics (CMS Namespace)

### Instance-Level Metrics

Namespace: `acs_elasticsearch`

| Metric Name | Unit | Description | Threshold Recommendation |
|-------------|------|-------------|--------------------------|
| `NodeCPUUtilization` | % | CPU usage | > 80% → alert; > 90% → critical |
| `NodeStatsSystemMemoryUtilization` | % | System memory usage | > 85% → alert; > 95% → critical |
| `NodeDiskUtilization` | % | Disk usage | > 80% → alert; > 95% → urgent expand |
| `ClusterStatus` | - | Cluster health (0=normal) | != 0 → alert |
| `ClusterNodeCount` | - | Active node count | < expected → alert |
| `ClusterQueryQPS` | count/s | Query rate | Monitor trend |
| `ClusterIndexQPS` | count/s | Write rate | Monitor trend |
| `ClusterSearchLatency` | ms | Query latency | > 100ms → warn; > 500ms → alert |
| `ClusterIndexingLatency` | ms | Write latency | > 50ms → warn; > 200ms → alert |

### JVM Metrics

| Metric Name | Unit | Description | Threshold |
|-------------|------|-------------|-----------|
| `NodeHeapMemoryUtilization` | % | JVM heap usage | > 80% → warn; > 95% → critical |
| `NodeStatsFullGcCollectionCount` | count | GC frequency (total) | High frequency → warn |
| `JVMGCOldCollectionDuration` | ms | Old GC pause time | > 500ms → warn |

### Storage Metrics

| Metric Name | Unit | Description | Threshold |
|-------------|------|-------------|-----------|
| `NodeDiskUtilization` | % | Disk usage percentage | > 80% → alert |
| `NodeFreeStorageSpace` | MiB | Available disk space | < 10240 MiB → alert |
| `ClusterShardCount` | - | Total shards | Monitor for imbalance |

---

## 3. Elasticsearch Internal Metrics

### Cluster Health API

```
GET _cluster/health
```

Response fields:
```json
{
  "status": "green",  // green/yellow/red
  "number_of_nodes": 3,
  "number_of_data_nodes": 3,
  "active_shards": 150,
  "relocating_shards": 0,
  "initializing_shards": 0,
  "unassigned_shards": 0
}
```

| Field | Healthy Value | Alert Trigger |
|-------|--------------|----------------|
| `status` | `green` | `yellow` or `red` |
| `unassigned_shards` | 0 | > 0 |
| `relocating_shards` | 0 | > 2 (check rebalance) |
| `initializing_shards` | 0 | > 0 (check node startup) |

### Node Stats API

```
GET _nodes/stats
```

Key metrics:
| Field | Description | Alert Threshold |
|-------|-------------|-----------------|
| `jvm.mem.heap_used_percent` | JVM heap usage | > 85% |
| `fs.disk_usage.percent` | Disk usage per node | > 80% |
| `os.cpu.percent` | CPU per node | > 90% |
| `process.open_file descriptors` | File handles | Near limit |

### Index Stats API

```
GET _stats
```

Key metrics:
| Field | Description | Alert Threshold |
|-------|-------------|-----------------|
| `indexing.index_current` | Active indexing ops | High → bottleneck |
| `search.query_current` | Active queries | High → congestion |
| `merges.current` | Merge operations | High → IO pressure |

---

## 4. Alert Configuration

### Recommended Alert Rules

| Alert Name | Metric | Condition | Severity | Action |
|------------|--------|-----------|----------|--------|
| `ES-Node-CPU-High` | NodeCPUUtilization | > 80% for 5min | Warning | Check query load |
| `ES-Node-CPU-Critical` | NodeCPUUtilization | > 90% for 3min | Critical | Scale up or optimize |
| `ES-Memory-High` | NodeStatsSystemMemoryUtilization | > 85% for 5min | Warning | Check cache config |
| `ES-Disk-High` | NodeDiskUtilization | > 80% for 10min | Warning | Clean indices or expand |
| `ES-Disk-Critical` | NodeDiskUtilization | > 95% for 5min | Critical | Immediate expand |
| `ES-Cluster-Unhealthy` | ClusterStatus | != 0 | Warning | Check cluster health |
| `ES-JVM-GC-High` | NodeHeapMemoryUtilization | > 85% for 5min | Warning | Tune JVM |
| `ES-Node-Down` | ClusterNodeCount | < expected | Critical | Node failure check |
| `ES-Slow-Query` | ClusterSearchLatency | > 500ms for 5min | Warning | Analyze slow queries |

### Create Alert Rule via CMS API

```go
// Create alert rule example
import cms "github.com/alibabacloud-go/cms-20190101/v8/client"

request := &cms.CreateAlertRuleRequest{
    RuleName: tea.String("ES-Instance-CPU-High"),
    Namespace: tea.String("acs_elasticsearch"),
    MetricName: tea.String("NodeCPUUtilization"),
    Dimensions: tea.String("{\"instanceId\":\"es-cn-xxx\"}"),
    Evaluations: tea.String("[{\"threshold\":\"80\",\"comparisonOperator\":\"GreaterThan\",\"times\":\"3\"}]"),
    AlertActionConfig: tea.String("{\"webhook\":\"https://alert-webhook.url\"}"),
}
```

---

## 5. Log Monitoring (SLS Integration)

### Log Types

| Log Type | Content | Analysis Purpose |
|----------|---------|------------------|
| **Search Log** | Query execution details | Slow query analysis |
| **Access Log** | API access records | Security, usage patterns |
| **Engine Log** | Elasticsearch internal logs | Error investigation |

### Slow Query Analysis

```go
// List search logs for slow queries
request := &elasticsearch.ListSearchLogRequest{
    InstanceId: tea.String(instanceId),
    StartTime: tea.String(startTime),
    EndTime:   tea.String(endTime),
    Query:     tea.String("slow"),  // Filter slow queries
}

response, err := client.ListSearchLog(request)
// Analyze slow query patterns
for _, log := range response.Body.Result.Logs {
    content := tea.ToString(log.Content)
    if strings.Contains(content, "took") {
        // Extract query time
        fmt.Printf("Slow query log: %s\n", content)
    }
}
```

---

## 6. Dashboard Templates

### Key Dashboard Panels

1. **Cluster Overview**
   - Instance status
   - Cluster health
   - Node count
   - Shard distribution

2. **Performance**
   - CPU utilization (per node)
   - Memory utilization
   - JVM heap usage
   - GC frequency

3. **Storage**
   - Disk utilization (per node)
   - Index count
   - Document count
   - Storage size trend

4. **Operations**
   - Query QPS trend
   - Write QPS trend
   - Latency trend
   - Error rate

5. **JVM**
   - Heap memory usage
   - GC collection count
   - GC pause time
   - Thread count

---

## 7. Well-Architected Monitoring Alignment

| Pillar | Monitoring Requirement | Reference |
|--------|------------------------|-----------|
| **Security** | Audit logs, access patterns | well-architected-assessment.md §2.1 |
| **Stability** | Cluster health, node status, backup verification | well-architected-assessment.md §2.2 |
| **Cost** | Resource utilization trends, idle detection | well-architected-assessment.md §2.3 |
| **Efficiency** | Operation latency, automation metrics | well-architected-assessment.md §2.4 |
| **Performance** | QPS, latency, throughput baselines | well-architected-assessment.md §2.5 |

---

## 8. Multi-Metric Anomaly Patterns (AIOps)

### 8.1 Anomaly Pattern Detection Library (≥4 Combinations)

| Pattern ID | Pattern Name | Trigger Metrics | Root Cause Hypothesis |
|------------|--------------|-----------------|----------------------|
| **P1** | CPU-JVM-Heap-Correlation | CPU>80% + JVM>85% + Latency>200ms | Memory-intensive queries causing GC pressure |
| **P2** | Disk-Indexing-Correlation | Disk>80% + IndexingLatency>100ms + MergeOps high | Heavy indexing workload, segment buildup |
| **P3** | Cluster-Shard-Anomaly | Cluster=yellow + UnassignedShards>0 + NodeCount<expected | Node failure or allocation constraints |
| **P4** | Network-Query-Anomaly | ConnectionTimeout + QueryQueue full + Coordinator overload | Network bandwidth saturation or insufficient coordinators |
| **P5** | JVM-GC-Latency-Correlation | FullGC>10/hr + Pause>500ms + P95Latency>1s | Heap size too small or memory leak |
| **P6** | CPU-SearchQps-Correlation | CPU>80% + SearchQps spike + SlowQueries>threshold | Query optimization needed or missing cache |
| **P7** | Disk-Shard-Correlation | Disk>80% per node + ShardCount imbalance + Rebalancing slow | Hot node due to shard distribution issue |
| **P8** | Memory-Cache-Miss | Memory high + Cache hit rate low + Query latency high | Cache configuration issue or insufficient memory |

### 8.2 Pattern Detection Implementation

```go
func detectMultiMetricAnomalies(instanceId string, metrics MetricsSnapshot) []AnomalyPattern {
    patterns := []AnomalyPattern{}
    
    // Pattern P1: CPU-JVM-Heap-Correlation
    if metrics.CPU > 80 && metrics.JVMHeap > 85 && metrics.SearchLatency > 200 {
        patterns = append(patterns, AnomalyPattern{
            PatternId:          "P1",
            PatternName:        "CPU-JVM-Heap-Correlation",
            TriggeredMetrics:   []string{"CPU", "JVMHeap", "SearchLatency"},
            Values:             map[string]float64{"CPU": metrics.CPU, "JVMHeap": metrics.JVMHeap, "SearchLatency": metrics.SearchLatency},
            RootCauseHypothesis: "Memory-intensive queries causing GC pressure",
            Severity:           "Warning",
            Remediation:        "Enable query cache, reduce result set size, add coordinator nodes",
        })
    }
    
    // Pattern P2: Disk-Indexing-Correlation
    if metrics.DiskUtilization > 80 && metrics.IndexingLatency > 100 && metrics.MergeOps > threshold {
        patterns = append(patterns, AnomalyPattern{
            PatternId:          "P2",
            PatternName:        "Disk-Indexing-Correlation",
            TriggeredMetrics:   []string{"DiskUtilization", "IndexingLatency", "MergeOps"},
            RootCauseHypothesis: "Heavy indexing workload, segment buildup",
            Severity:           "Warning",
            Remediation:        "Force merge old indices, adjust merge policy, expand disk",
        })
    }
    
    // Pattern P3: Cluster-Shard-Anomaly
    if metrics.ClusterHealth == "yellow" && metrics.UnassignedShards > 0 && metrics.NodeCount < expectedNodes {
        patterns = append(patterns, AnomalyPattern{
            PatternId:          "P3",
            PatternName:        "Cluster-Shard-Anomaly",
            TriggeredMetrics:   []string{"ClusterHealth", "UnassignedShards", "NodeCount"},
            RootCauseHypothesis: "Node failure or allocation constraints",
            Severity:           "Critical",
            Remediation:        "Restart failed node, adjust allocation settings",
        })
    }
    
    // Pattern P5: JVM-GC-Latency-Correlation
    if metrics.FullGCCount > 10 && metrics.GCPauseTime > 500 && metrics.SearchLatencyP95 > 1000 {
        patterns = append(patterns, AnomalyPattern{
            PatternId:          "P5",
            PatternName:        "JVM-GC-Latency-Correlation",
            TriggeredMetrics:   []string{"FullGCCount", "GCPauseTime", "SearchLatencyP95"},
            RootCauseHypothesis: "Heap size too small or memory leak",
            Severity:           "Critical",
            Remediation:        "Increase heap size (max 32GB), switch to G1GC, optimize aggregations",
        })
    }
    
    // Pattern P6: CPU-SearchQps-Correlation
    if metrics.CPU > 80 && metrics.SearchQps > baselineQps*2 && metrics.SlowQueryCount > threshold {
        patterns = append(patterns, AnomalyPattern{
            PatternId:          "P6",
            PatternName:        "CPU-SearchQps-Correlation",
            TriggeredMetrics:   []string{"CPU", "SearchQps", "SlowQueryCount"},
            RootCauseHypothesis: "Query optimization needed or missing cache",
            Severity:           "Warning",
            Remediation:        "Optimize queries, enable query cache, add nodes",
        })
    }
    
    return patterns
}

type AnomalyPattern struct {
    PatternId          string
    PatternName        string
    TriggeredMetrics   []string
    Values             map[string]float64
    RootCauseHypothesis string
    Severity           string
    Remediation        string
}

type MetricsSnapshot struct {
    CPU                float64
    JVMHeap            float64
    DiskUtilization    float64
    SearchLatency      float64
    IndexingLatency    float64
    ClusterHealth      string
    UnassignedShards   int
    NodeCount          int
    FullGCCount        int
    GCPauseTime        float64
    SearchLatencyP95   float64
    SearchQps          float64
    SlowQueryCount     int
    MergeOps           float64
}
```

### 8.3 Pattern Correlation Matrix

| Pattern | CPU | JVM | Disk | Network | Cluster | Latency | GC | Correlation Strength |
|---------|-----|-----|------|---------|---------|---------|----|--------------------|
| **P1** | ✅ | ✅ | - | - | - | ✅ | ⚠️ | 85% |
| **P2** | - | - | ✅ | - | - | ✅ | - | 80% |
| **P3** | - | - | ⚠️ | - | ✅ | ⚠️ | - | 90% |
| **P4** | - | - | - | ✅ | - | ✅ | - | 75% |
| **P5** | ⚠️ | ✅ | - | - | - | ✅ | ✅ | 95% |
| **P6** | ✅ | ⚠️ | - | - | - | ✅ | - | 70% |

### 8.4 Anomaly Detection Dashboard Queries

```yaml
# Grafana/PromQL queries for anomaly detection

CPU-JVM-Heap Correlation:
  - acs_elasticsearch:NodeCPUUtilization{instanceId="*"} > 80
  - acs_elasticsearch:NodeHeapMemoryUtilization{instanceId="*"} > 85
  - acs_elasticsearch:ClusterSearchLatency{instanceId="*"} > 200

Disk-Indexing Correlation:
  - acs_elasticsearch:NodeDiskUtilization{instanceId="*"} > 80
  - acs_elasticsearch:ClusterIndexingLatency{instanceId="*"} > 100
  - Custom metric: MergeOpsCount > threshold

Cluster-Shard Anomaly:
  - acs_elasticsearch:ClusterStatus{instanceId="*"} != 0
  - acs_elasticsearch:ClusterShardCount{instanceId="*"} > expected
  - acs_elasticsearch:ClusterNodeCount{instanceId="*"} < expected

JVM-GC-Latency Correlation:
  - acs_elasticsearch:NodeStatsFullGcCollectionCount{instanceId="*"} > 10
  - acs_elasticsearch:JVMGCOldCollectionDuration{instanceId="*"} > 500
  - acs_elasticsearch:ClusterSearchLatency{instanceId="*"} > 1000
```

---

## 9. Proactive Monitoring Integration

### 9.1 Proactive Inspection Metrics

| Inspection Type | Metrics Checked | Anomaly Patterns Detected |
|-----------------|-----------------|---------------------------|
| **Quick Check** | Instance status, Cluster health | P3 (Cluster-Shard-Anomaly) |
| **Daily Check** | Full metrics suite | P1, P2, P3, P5, P6 |
| **Weekly Check** | Trends, capacity | P7 (Disk-Shard), P8 (Memory-Cache) |

### 9.2 Anomaly Alert Rule Templates

```json
{
  "rule_name": "Multi-Metric-Anomaly-P1-CPU-JVM-Heap",
  "namespace": "acs_elasticsearch",
  "conditions": [
    {"metric": "NodeCPUUtilization", "operator": "GreaterThan", "threshold": 80, "period": 5},
    {"metric": "NodeHeapMemoryUtilization", "operator": "GreaterThan", "threshold": 85, "period": 5},
    {"metric": "ClusterSearchLatency", "operator": "GreaterThan", "threshold": 200, "period": 5}
  ],
  "correlation_type": "AND",
  "severity": "Warning",
  "actions": ["Notify", "TriggerRemediation"],
  "remediation_script": "operations/proactive-inspection.md#P1"
}
```

---

*For anomaly handling patterns, see [operations/proactive-inspection.md](../operations/proactive-inspection.md).*