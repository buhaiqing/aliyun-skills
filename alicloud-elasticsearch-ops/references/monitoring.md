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
| `InstanceCpuUtilization` | % | CPU usage | > 80% → alert; > 90% → critical |
| `InstanceMemoryUtilization` | % | Memory usage | > 85% → alert; > 95% → critical |
| `InstanceDiskUtilization` | % | Disk usage | > 80% → alert; > 95% → urgent expand |
| `InstanceStatus` | - | Instance health state | != Normal → alert |
| `ClusterHealth` | - | Elasticsearch cluster status | != green → alert |
| `NodeCount` | - | Active node count | < expected → alert |
| `SearchQps` | count/s | Query rate | Monitor trend |
| `IndexingQps` | count/s | Write rate | Monitor trend |
| `SearchLatency` | ms | Query latency | > 100ms → warn; > 500ms → alert |
| `IndexingLatency` | ms | Write latency | > 50ms → warn; > 200ms → alert |

### JVM Metrics

| Metric Name | Unit | Description | Threshold |
|-------------|------|-------------|-----------|
| `JVMHeapMemoryUsedPercent` | % | JVM heap usage | > 80% → warn; > 95% → critical |
| `JVMGcCollectionCount` | count | GC frequency | High frequency → warn |
| `JVMGcCollectionTime` | ms | GC pause time | > 500ms → warn |

### Storage Metrics

| Metric Name | Unit | Description | Threshold |
|-------------|------|-------------|-----------|
| `DiskUsedPercent` | % | Disk usage percentage | > 80% → alert |
| `DiskFreeSpace` | GB | Available disk space | < 10GB → alert |
| `ShardCount` | - | Total shards | Monitor for imbalance |

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
| `ES-Instance-CPU-High` | InstanceCpuUtilization | > 80% for 5min | Warning | Check query load |
| `ES-Instance-CPU-Critical` | InstanceCpuUtilization | > 90% for 3min | Critical | Scale up or optimize |
| `ES-Memory-High` | InstanceMemoryUtilization | > 85% for 5min | Warning | Check cache config |
| `ES-Disk-High` | InstanceDiskUtilization | > 80% for 10min | Warning | Clean indices or expand |
| `ES-Disk-Critical` | InstanceDiskUtilization | > 95% for 5min | Critical | Immediate expand |
| `ES-Cluster-Yellow` | ClusterHealth | = yellow | Warning | Check unassigned shards |
| `ES-Cluster-Red` | ClusterHealth | = red | Critical | Node failure investigation |
| `ES-JVM-GC-High` | JVMHeapMemoryUsedPercent | > 85% for 5min | Warning | Tune JVM |
| `ES-Node-Down` | NodeCount | < expected | Critical | Node failure check |
| `ES-Slow-Query` | SearchLatency | > 500ms for 5min | Warning | Analyze slow queries |

### Create Alert Rule via CMS API

```go
// Create alert rule example
import cms "github.com/alibabacloud-go/cms-20190101/v8/client"

request := &cms.CreateAlertRuleRequest{
    RuleName: tea.String("ES-Instance-CPU-High"),
    Namespace: tea.String("acs_elasticsearch"),
    MetricName: tea.String("InstanceCpuUtilization"),
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

*For integration with Go SDK and automation, see [integration.md](integration.md).*