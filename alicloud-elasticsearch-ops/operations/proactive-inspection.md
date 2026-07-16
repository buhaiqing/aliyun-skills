# Proactive Inspection Workflow — Alibaba Cloud Elasticsearch

> **Purpose:** Automated proactive health inspection patterns for AIOps.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-17

---

## 1. Inspection Framework Overview

### 1.1 Proactive Inspection Principles

| Principle | Implementation |
|-----------|----------------|
| **Scheduled Execution** | Daily/Weekly automated checks |
| **Multi-metric Correlation** | Combine CPU, Memory, Disk, JVM metrics |
| **Threshold-based Alerts** | Dynamic thresholds with baseline comparison |
| **Auto-remediation Triggers** | Trigger corrective actions on detected anomalies |
| **Report Generation** | Structured inspection reports with severity rating |

### 1.2 Inspection Schedule Matrix

| Inspection Type | Frequency | Metrics Checked | Severity Threshold |
|-----------------|-----------|-----------------|-------------------|
| **Quick Health Check** | Every 5 min | Instance status, Cluster health | Critical |
| **Daily Inspection** | Daily 02:00 | Full metrics suite | Warning |
| **Weekly Deep Inspection** | Sunday 03:00 | Historical trends, capacity planning | Info |
| **Pre-Change Inspection** | Before ops | Snapshot verification, cluster state | Mandatory |

---

## 2. Multi-Metric Anomaly Inspection

### 2.1 Anomaly Pattern Library (≥4 Combinations)

#### Pattern 1: CPU + JVM Heap Correlation

```yaml
Pattern: CPU-JVM-Heap-Correlation
Trigger Condition:
  - CPU utilization > 80% AND
  - JVM heap > 85% AND
  - Search latency > 200ms
Root Cause Hypothesis:
  - Memory-intensive queries causing GC pressure
  - Large result sets without pagination
  - Missing query caching
Diagnosis Steps:
  1. GET _nodes/stats/jvm → Check GC frequency
  2. GET _nodes/hot_threads → Identify CPU-consuming threads
  3. Analyze slow query logs → Find heavy aggregations
Auto-Remediation:
  - Enable query cache
  - Reduce result set size
  - Add coordinator nodes
Escalation:
  - If unresolved > 30 min → Scale up node spec
```

#### Pattern 2: Disk + Indexing Correlation

```yaml
Pattern: Disk-Indexing-Correlation
Trigger Condition:
  - Disk usage > 80% AND
  - Indexing latency > 100ms AND
  - Merge operations high
Root Cause Hypothesis:
  - Heavy indexing workload
  - Insufficient merge thread pool
  - Large segment files
Diagnosis Steps:
  1. GET _cat/indices?v&s=store.size:desc → Find large indices
  2. GET _cat/segments?v → Check segment count
  3. Check merge policy settings → Validate merge config
Auto-Remediation:
  - Force merge old indices
  - Adjust merge policy
  - Expand disk or add warm nodes
Escalation:
  - If disk > 95% → Emergency disk expansion
```

#### Pattern 3: Cluster Health + Shard Correlation

```yaml
Pattern: Cluster-Shard-Anomaly
Trigger Condition:
  - Cluster health = yellow AND
  - Unassigned shards > 0 AND
  - Node count < expected
Root Cause Hypothesis:
  - Node failure or restart in progress
  - Shard allocation constraints
  - Disk space shortage on target nodes
Diagnosis Steps:
  1. GET _cluster/health?level=shards → Identify unassigned shards
  2. GET _cat/shards?v&s=state → List shard states
  3. GET _cluster/allocation/explain → Check allocation reason
Auto-Remediation:
  - Restart failed node
  - Adjust allocation settings
  - Clear disk space on target nodes
Escalation:
  - If cluster red → Immediate node investigation
```

#### Pattern 4: Network + Query Correlation

```yaml
Pattern: Network-Query-Anomaly
Trigger Condition:
  - Connection timeout errors AND
  - Query queue full AND
  - Coordinator nodes overloaded
Root Cause Hypothesis:
  - Network bandwidth saturation
  - Insufficient coordinator capacity
  - Heavy aggregation queries
Diagnosis Steps:
  1. Check network latency between nodes
  2. GET _nodes/stats/transport → Check transport metrics
  3. Analyze query queue depth → Identify bottleneck
Auto-Remediation:
  - Add coordinator nodes
  - Optimize heavy queries
  - Increase network bandwidth
Escalation:
  - If timeout rate > 10% → Network infrastructure review
```

#### Pattern 5: JVM GC + Search Latency Correlation

```yaml
Pattern: JVM-GC-Latency-Correlation
Trigger Condition:
  - Full GC count high (> 10/hour) AND
  - GC pause time > 500ms AND
  - Search latency P95 > 1s
Root Cause Hypothesis:
  - Heap size too small
  - Memory leak or inefficient data structures
  - Large aggregation results
Diagnosis Steps:
  1. GET _nodes/stats/jvm → Analyze GC patterns
  2. Enable heap dump analysis → Check memory distribution
  3. Profile search queries → Find problematic aggregations
Auto-Remediation:
  - Increase heap size (max 32GB)
  - Switch to G1GC
  - Optimize aggregation queries
Escalation:
  - If GC pause > 1s → JVM tuning specialist
```

#### Pattern 6: CPU + Search QPS Correlation

```yaml
Pattern: CPU-SearchQps-Correlation
Trigger Condition:
  - CPU utilization > 80% AND
  - Search QPS spike (> 2x baseline) AND
  - Slow query count > threshold
Root Cause Hypothesis:
  - Query optimization needed
  - Missing query cache
  - Heavy aggregations without optimization
Diagnosis Steps:
  1. GET _nodes/stats/indices → Check query cache hit rate
  2. ListSearchLog → Analyze slow queries
  3. GET _cat/indices?v → Check index sizes
Auto-Remediation:
  - Optimize queries (reduce result set, add filters)
  - Enable query cache
  - Add data nodes for load distribution
Escalation:
  - If CPU > 95% sustained → Scale up node spec
```

#### Pattern 7: Disk + Shard Correlation

```yaml
Pattern: Disk-Shard-Correlation
Trigger Condition:
  - Disk usage > 80% per node AND
  - Shard count imbalance across nodes AND
  - Rebalancing slow or stuck
Root Cause Hypothesis:
  - Hot node due to uneven shard distribution
  - Shard allocation constraints
  - Large shards on specific nodes
Diagnosis Steps:
  1. GET _cat/allocation?v → Check disk per node
  2. GET _cat/shards?v&s=store.size:desc → Identify large shards
  3. GET _cluster/settings → Check allocation settings
Auto-Remediation:
  - Rebalance shards manually
  - Adjust allocation settings
  - Add warm nodes for large indices
Escalation:
  - If disk > 95% on any node → Emergency rebalance
```

#### Pattern 8: Memory + Cache Miss Correlation

```yaml
Pattern: Memory-Cache-Miss-Correlation
Trigger Condition:
  - Memory utilization high AND
  - Cache hit rate low (< 50%) AND
  - Query latency high (> 200ms)
Root Cause Hypothesis:
  - Cache configuration issue
  - Insufficient memory for caching
  - Cache eviction due to small size
Diagnosis Steps:
  1. GET _nodes/stats/indices → Check cache stats
  2. GET _nodes/stats/jvm → Check heap pressure
  3. Analyze query patterns → Identify cache-friendly queries
Auto-Remediation:
  - Increase cache size
  - Enable field data cache
  - Optimize queries for caching
Escalation:
  - If cache hit < 30% sustained → Cache tuning specialist
```

---

## 3. Daily Inspection Workflow

### 3.1 Daily Inspection Checklist

```go
func performDailyInspection(client *elasticsearch.Client, instanceId string) *InspectionReport {
    report := &InspectionReport{
        InstanceId:    instanceId,
        Timestamp:     time.Now(),
        InspectionType: "Daily",
    }
    
    // Check 1: Instance Status (Critical)
    fmt.Println("=== Check 1: Instance Status ===")
    inst, err := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
        InstanceId: tea.String(instanceId),
    })
    if err != nil {
        report.AddFinding("InstanceStatus", "Error", err.Error())
        return report
    }
    
    status := tea.ToString(inst.Body.Result.Status)
    if status == "Normal" {
        report.AddFinding("InstanceStatus", "Pass", "Instance running normally")
    } else {
        report.AddFinding("InstanceStatus", "Critical", fmt.Sprintf("Status=%s", status))
    }
    
    // Check 2: Cluster Health (Critical)
    fmt.Println("=== Check 2: Cluster Health ===")
    health, _ := client.DescribeElasticsearchHealth(&elasticsearch.DescribeElasticsearchHealthRequest{
        InstanceId: tea.String(instanceId),
    })
    
    clusterHealth := tea.ToString(health.Body.Result.Status)
    unassignedShards := tea.ToInt32(health.Body.Result.UnassignedShards)
    
    if clusterHealth == "green" && unassignedShards == 0 {
        report.AddFinding("ClusterHealth", "Pass", "Cluster healthy")
    } else if clusterHealth == "yellow" {
        report.AddFinding("ClusterHealth", "Warning", 
            fmt.Sprintf("Cluster yellow, unassigned shards=%d", unassignedShards))
    } else {
        report.AddFinding("ClusterHealth", "Critical", 
            fmt.Sprintf("Cluster red, immediate action required"))
    }
    
    // Check 3: JVM Heap Usage (Warning threshold: 85%)
    fmt.Println("=== Check 3: JVM Heap Usage ===")
    // Assume metrics fetched from CMS
    jvmUsage := getJVMMetrics(instanceId)
    if jvmUsage < 70 {
        report.AddFinding("JVMHeap", "Pass", fmt.Sprintf("JVM heap=%d%%", jvmUsage))
    } else if jvmUsage < 85 {
        report.AddFinding("JVMHeap", "Warning", fmt.Sprintf("JVM heap=%d%%, consider tuning", jvmUsage))
    } else {
        report.AddFinding("JVMHeap", "Critical", fmt.Sprintf("JVM heap=%d%%, immediate action", jvmUsage))
        report.TriggerAutoRemediation("JVM_GC_Latency_Correlation")
    }
    
    // Check 4: Disk Usage (Warning threshold: 80%)
    fmt.Println("=== Check 4: Disk Usage ===")
    diskUsage := getDiskMetrics(instanceId)
    if diskUsage < 70 {
        report.AddFinding("DiskUsage", "Pass", fmt.Sprintf("Disk usage=%d%%", diskUsage))
    } else if diskUsage < 80 {
        report.AddFinding("DiskUsage", "Warning", fmt.Sprintf("Disk usage=%d%%, plan expansion", diskUsage))
    } else {
        report.AddFinding("DiskUsage", "Critical", fmt.Sprintf("Disk usage=%d%%, expand now", diskUsage))
        report.TriggerAutoRemediation("Disk_Indexing_Correlation")
    }
    
    // Check 5: Snapshot Verification (Mandatory)
    fmt.Println("=== Check 5: Snapshot Verification ===")
    snapshots, _ := client.ListSnapshots(&elasticsearch.ListSnapshotsRequest{
        InstanceId: tea.String(instanceId),
    })
    
    recentBackup := false
    for _, snap := range snapshots.Body.Result.Snapshots {
        snapTime := parseTime(tea.ToString(snap.CreateTime))
        if snapTime.After(time.Now().Add(-24 * time.Hour)) {
            recentBackup = true
            break
        }
    }
    
    if recentBackup {
        report.AddFinding("Snapshot", "Pass", "Recent backup exists")
    } else {
        report.AddFinding("Snapshot", "Warning", "No backup in last 24 hours")
        report.TriggerAutoRemediation("CreateDailyBackup")
    }
    
    // Check 6: Multi-Metric Correlation
    fmt.Println("=== Check 6: Multi-Metric Correlation ===")
    patterns := detectAnomalyPatterns(instanceId)
    for _, pattern := range patterns {
        report.AddFinding(pattern.Name, pattern.Severity, pattern.Description)
        if pattern.Severity == "Critical" {
            report.TriggerAutoRemediation(pattern.RemediationAction)
        }
    }
    
    return report
}

type InspectionReport struct {
    InstanceId     string
    Timestamp      time.Time
    InspectionType string
    Findings       []Finding
    RemediationActions []string
}

type Finding struct {
    Category   string
    Severity   string // Pass, Warning, Critical
    Message    string
    Timestamp  time.Time
}

func (r *InspectionReport) AddFinding(category, severity, message string) {
    r.Findings = append(r.Findings, Finding{
        Category:  category,
        Severity:  severity,
        Message:   message,
        Timestamp: time.Now(),
    })
}

func (r *InspectionReport) TriggerAutoRemediation(action string) {
    r.RemediationActions = append(r.RemediationActions, action)
}
```

### 3.2 Weekly Deep Inspection

```go
func performWeeklyDeepInspection(client *elasticsearch.Client, instanceId string) *InspectionReport {
    report := &InspectionReport{
        InstanceId:     instanceId,
        Timestamp:      time.Now(),
        InspectionType: "WeeklyDeep",
    }
    
    // Trend Analysis (7-day metrics)
    fmt.Println("=== Trend Analysis ===")
    cpuTrend := getMetricTrend(instanceId, "InstanceCpuUtilization", 7)
    diskTrend := getMetricTrend(instanceId, "InstanceDiskUtilization", 7)
    queryLatencyTrend := getMetricTrend(instanceId, "SearchLatency", 7)
    
    // Capacity Planning
    fmt.Println("=== Capacity Planning ===")
    diskGrowthRate := calculateGrowthRate(diskTrend)
    estimatedDaysToFull := int((100 - diskTrend.Current) / diskGrowthRate)
    
    if estimatedDaysToFull < 30 {
        report.AddFinding("Capacity", "Warning", 
            fmt.Sprintf("Disk full in ~%d days, plan expansion", estimatedDaysToFull))
    } else if estimatedDaysToFull < 60 {
        report.AddFinding("Capacity", "Info",
            fmt.Sprintf("Disk full in ~%d days, monitor trend", estimatedDaysToFull))
    } else {
        report.AddFinding("Capacity", "Pass", "Sufficient capacity")
    }
    
    // Index Health Analysis
    fmt.Println("=== Index Health Analysis ===")
    indices := getIndicesStats(instanceId)
    for _, idx := range indices {
        if idx.DocCount > 10000000 { // 10M+ docs
            report.AddFinding("LargeIndex", "Info",
                fmt.Sprintf("Index %s has %d docs, consider ILM policy", idx.Name, idx.DocCount))
        }
        if idx.ShardCount > 50 {
            report.AddFinding("ShardCount", "Warning",
                fmt.Sprintf("Index %s has %d shards, optimize shard count", idx.Name, idx.ShardCount))
        }
    }
    
    // Node Distribution Check
    fmt.Println("=== Node Distribution Check ===")
    nodes := getNodeStats(instanceId)
    for _, node := range nodes {
        if node.DiskUsage > 90 {
            report.AddFinding("NodeDisk", "Warning",
                fmt.Sprintf("Node %s disk=%d%%, rebalance shards", node.Name, node.DiskUsage))
        }
    }
    
    return report
}
```

---

## 4. Pre-Change Inspection

### 4.1 Pre-Change Safety Gate

```go
func preChangeInspection(client *elasticsearch.Client, instanceId, changeType string) (bool, error) {
    fmt.Printf("=== Pre-Change Inspection for %s ===\n", changeType)
    
    checks := []PreChangeCheck{
        {Name: "InstanceStatus", Required: true, CheckFunc: checkInstanceStatus},
        {Name: "ClusterHealth", Required: true, CheckFunc: checkClusterHealth},
        {Name: "SnapshotExists", Required: true, CheckFunc: checkSnapshotExists},
        {Name: "NoPendingOps", Required: true, CheckFunc: checkNoPendingOperations},
        {Name: "ChangeWindow", Required: false, CheckFunc: checkChangeWindow},
    }
    
    allPass := true
    
    for _, check := range checks {
        result, err := check.CheckFunc(client, instanceId)
        if err != nil {
            fmt.Printf("❌ %s: %v\n", check.Name, err)
            if check.Required {
                return false, fmt.Errorf("%s check failed: %w", check.Name, err)
            }
            allPass = false
        } else {
            fmt.Printf("✅ %s: passed\n", check.Name)
        }
    }
    
    return allPass, nil
}

type PreChangeCheck struct {
    Name      string
    Required  bool
    CheckFunc func(*elasticsearch.Client, string) (bool, error)
}

func checkSnapshotExists(client *elasticsearch.Client, instanceId string) (bool, error) {
    // Check for snapshot created within last 24 hours
    snapshots, _ := client.ListSnapshots(&elasticsearch.ListSnapshotsRequest{
        InstanceId: tea.String(instanceId),
    })
    
    for _, snap := range snapshots.Body.Result.Snapshots {
        snapTime := parseTime(tea.ToString(snap.CreateTime))
        if snapTime.After(time.Now().Add(-24 * time.Hour)) {
            return true, nil
        }
    }
    
    return false, fmt.Errorf("No snapshot in last 24 hours")
}
```

---

## 5. Inspection Report Template

### 5.1 Standard Report Format

```markdown
# Elasticsearch Inspection Report

**Instance ID:** {{instance_id}}
**Timestamp:** {{timestamp}}
**Inspection Type:** {{inspection_type}}
**Overall Status:** {{overall_status}}

## Summary

| Category | Status | Severity | Message |
|----------|--------|----------|---------|
| Instance Status | ✅ Pass | - | Instance running normally |
| Cluster Health | ⚠️ Warning | Warning | Cluster yellow, unassigned shards=2 |
| JVM Heap | ✅ Pass | - | JVM heap=65% |
| Disk Usage | ⚠️ Warning | Warning | Disk usage=78%, plan expansion |
| Snapshot | ✅ Pass | - | Recent backup exists |

## Anomaly Patterns Detected

| Pattern | Severity | Description | Remediation |
|---------|----------|-------------|-------------|
| Disk_Indexing_Correlation | Warning | Disk+Indexing anomaly detected | Force merge old indices |

## Remediation Actions Triggered

1. CreateDailyBackup - Snapshot created: auto-backup-{{timestamp}}
2. ShardReassignment - Unassigned shards reassigned

## Capacity Planning

- Disk growth rate: 0.5%/day
- Estimated days to full: ~44 days
- Recommendation: Plan disk expansion within 30 days

## Next Inspection

Scheduled: {{next_inspection_time}}
```

---

## 6. Automated Remediation Actions

### 6.1 Remediation Action Library

| Action | Trigger Pattern | Execution | Verification |
|--------|-----------------|-----------|--------------|
| `CreateDailyBackup` | No snapshot in 24h | CreateSnapshot API | Check snapshot success |
| `ShardReassignment` | Unassigned shards > 0 | ES API shard reroute | Check unassigned count |
| `JVMTuning` | JVM heap > 85% | Update heap settings | Check heap usage |
| `DiskExpansion` | Disk > 80% | UpdateInstance disk size | Check disk usage |
| `NodeRestart` | Node failed | RestartInstance API | Check node status |
| `ForceMergeIndices` | High segment count | ES API force merge | Check segment count |

---

## 7. Inspection Integration with AIOps

### 7.1 Cross-Skill Delegation for Remediation

```yaml
Remediation Delegation Matrix:

| Issue | Primary Skill | Delegation |
|-------|---------------|------------|
| Disk expansion needed | alicloud-elasticsearch-ops | Self-handle via UpdateInstance |
| Network issues | alicloud-elasticsearch-ops | Check whitelist + delegate to alicloud-vpc-ops |
| RAM permission issues | alicloud-elasticsearch-ops | Delegate to alicloud-ram-ops |
| Monitoring alerts | alicloud-cms-ops | Delegate for alert rule creation |
| ActionTrail audit | alicloud-actiontrail-ops | Delegate for operation history |
```

---

## 8. Cross-Reference with AIOps Components

| Component | Integration Point | Reference |
|-----------|-------------------|-----------|
| **Multi-Metric Anomaly** | P1-P8 detection patterns | `references/monitoring.md#8` |
| **Alarm Storm Handling** | Storm triggers inspection | `operations/alarm-storm-handling.md#9` |
| **Diagnostic Report** | Inspection generates report | `reports/diagnostic-report-schema.md` |
| **Cross-Skill Diagnosis** | Dependency delegation | `references/integration.md#6` |
| **Self-Reflection** | Multi-round analysis | `references/troubleshooting.md#6` |
| **Standardized Prompts** | Inspection prompt templates | `references/prompt-examples.md#4` |

---

*This proactive inspection workflow provides automated health monitoring with multi-metric anomaly detection. See [alarm-storm-handling.md](alarm-storm-handling.md) for integrated storm handling workflow.*