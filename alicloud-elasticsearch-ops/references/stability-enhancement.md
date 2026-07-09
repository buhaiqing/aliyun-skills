# Stability Enhancement Guide — Alibaba Cloud Elasticsearch

> **Purpose:** High availability, fault recovery, and change management aligned with Alibaba Cloud Well-Architected Framework Stability Pillar.
> **Version:** 2.0.0
> **Last Updated:** 2026-05-17
> **Reference:** [阿里云卓越架构 - 稳定支柱](https://help.aliyun.com/zh/product/2362200.html)

---

## 1. High Availability Architecture

### 1.1 Multi-Zone Deployment Matrix

| ZoneCount | Availability Level | Data Nodes | Master Nodes | Use Case |
|-----------|-------------------|------------|--------------|----------|
| **1** | Single Zone | 1-3 | 0 (embedded) | Development only |
| **2** | Cross-Zone HA | 3+ | 3 (dedicated) | Minimum production |
| **3** | Maximum HA | 5+ | 3 (dedicated) | **Recommended for production** |

### 1.2 Recommended HA Configuration

```go
// Production-grade HA instance creation
request := &elasticsearch.CreateInstanceRequest{
    RegionId:          tea.String(regionId),
    InstanceName:      tea.String(instanceName),
    EsVersion:         tea.String("7.10_aliyun"),
    NodeSpec:          tea.String("elasticsearch.sn2ne.large"),
    NodeAmount:        tea.Int32(5),        // 5 data nodes minimum
    DataNodeAmount:    tea.Int32(5),
    ZoneCount:         tea.Int32(3),        // 3-zone deployment
    MasterSpec:        tea.String("elasticsearch.sn1ne.large"),
    MasterAmount:      tea.Int32(3),        // 3 dedicated master nodes
    DiskType:          tea.String("cloud_ssd"),
    DiskSize:          tea.Int32(100),
    VpcId:             tea.String(vpcId),
    VswitchId:         tea.String(vswitchId),
}
```

### 1.3 Node Role Separation

| Node Type | Purpose | Recommended Count | Spec Recommendation |
|-----------|---------|-------------------|---------------------|
| **Data Node** | Store data, execute queries | 3-10 | `elasticsearch.sn2ne.large` to `elasticsearch.sn2ne.4xlarge` |
| **Master Node** | Cluster state management | 3 (dedicated) | `elasticsearch.sn1ne.large` (separate from data nodes) |
| **Coordinator Node** | Query routing, aggregations | 2-5 (optional) | `elasticsearch.sn1ne.large` |

---

## 2. Backup & Recovery Strategy

### 2.1 Backup Policy Matrix

| Backup Type | Frequency | Retention | Purpose |
|-------------|-----------|-----------|---------|
| **Daily Snapshot** | Daily at 02:00 | 7 days | RPO < 24 hours |
| **Weekly Snapshot** | Sunday 03:00 | 30 days | Monthly compliance audit |
| **Pre-Change Snapshot** | Before destructive ops | 48 hours | Rollback safety |
| **Cross-Region Copy** | Weekly | 90 days | Disaster Recovery (DR) |

### 2.2 Automated Backup Workflow

```go
func createPreChangeSnapshot(client *elasticsearch.Client, instanceId, changeType string) error {
    snapshotName := fmt.Sprintf("pre-%s-%s", changeType, time.Now().Format("20060102-150405"))
    
    // Step 1: Check instance status
    inst, err := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
        InstanceId: tea.String(instanceId),
    })
    if err != nil {
        return fmt.Errorf("DescribeInstance failed: %w", err)
    }
    
    status := tea.ToString(inst.Body.Result.Status)
    if status != "Normal" {
        return fmt.Errorf("Instance not in Normal state: %s", status)
    }
    
    // Step 2: Create snapshot
    request := &elasticsearch.CreateSnapshotRequest{
        InstanceId:    tea.String(instanceId),
        SnapshotName:  tea.String(snapshotName),
        Description:   tea.String(fmt.Sprintf("Pre-%s backup for rollback", changeType)),
    }
    
    response, err := client.CreateSnapshot(request)
    if err != nil {
        return fmt.Errorf("CreateSnapshot failed: %w", err)
    }
    
    fmt.Printf("✅ Snapshot created: %s\n", snapshotName)
    
    // Step 3: Wait for snapshot completion
    return waitForSnapshotSuccess(client, instanceId, snapshotName, 600)
}

func waitForSnapshotSuccess(client *elasticsearch.Client, instanceId, snapshotName string, timeoutSeconds int) error {
    for i := 0; i < timeoutSeconds/10; i++ {
        response, err := client.DescribeSnapshot(&elasticsearch.DescribeSnapshotRequest{
            InstanceId:    tea.String(instanceId),
            SnapshotName:  tea.String(snapshotName),
        })
        if err != nil {
            return err
        }
        
        status := tea.ToString(response.Body.Result.Status)
        if status == "Success" {
            fmt.Println("✅ Snapshot completed successfully")
            return nil
        }
        if status == "Failed" {
            return fmt.Errorf("Snapshot creation failed")
        }
        
        time.Sleep(10 * time.Second)
        fmt.Printf("⏳ Snapshot progress: %d%%\n", tea.ToInt32(response.Body.Result.Progress))
    }
    
    return fmt.Errorf("Snapshot timeout after %d seconds", timeoutSeconds)
}
```

### 2.3 Recovery RTO/RPO Targets

| Metric | Target | Method |
|--------|--------|--------|
| **RTO (Recovery Time)** | < 30 minutes | Snapshot restore to new instance |
| **RPO (Recovery Point)** | < 24 hours | Daily automated snapshot |
| **Cross-Region RTO** | < 2 hours | Cross-region backup restore |
| **Cross-Region RPO** | < 7 days | Weekly cross-region copy |

---

## 3. Fault Classification & Recovery Runbook Matrix

### 3.1 Fault Classification Tree

```
Fault Detection (DescribeInstance + DiagnoseInstance)
│
├── Instance Status != Normal
│   ├── Activating (timeout > 10min)
│   │   └── RUNBOOK: activation-stuck-recovery
│   ├── Inactive
│   │   └── RUNBOOK: instance-activation-recovery
│   └── Failed
│       └── RUNBOOK: instance-failure-investigation
│
├── Cluster Health != green
│   ├── Cluster yellow
│   │   ├── unassigned_shards > 0
│   │   │   └── RUNBOOK: shard-reassignment
│   │   └── relocating_shards > 2
│   │       └── RUNBOOK: rebalance-monitor
│   └── Cluster red
│       ├── Node down detected
│       │   └── RUNBOOK: node-failure-recovery
│       └── Disk full detected
│           └── RUNBOOK: disk-emergency-expansion
│
├── Connection Issue
│   ├── Connection refused
│   │   └── RUNBOOK: network-whitelist-check
│   ├── Authentication failed
│   │   └── RUNBOOK: credential-verification
│   └── Timeout
│       └── RUNBOOK: latency-investigation
│
└── Performance Degradation
    ├── JVM heap > 85%
    │   └── RUNBOOK: jvm-tuning
    ├── CPU > 80% sustained
    │   └── RUNBOOK: workload-optimization
    └── Disk > 80%
        └── RUNBOOK: storage-optimization
```

### 3.2 Recovery Runbook Catalog

#### RUNBOOK: activation-stuck-recovery

```yaml
Trigger: Instance stuck in "Activating" for > 10 minutes

Step 1: Diagnose (0-2 min)
  - DescribeInstance → Get status, progress
  - ListActionRecords → Check recent operations
  - DiagnoseInstance → Trigger diagnostic

Step 2: Root Cause Analysis (2-5 min)
  - Check VPC/VSwitch connectivity
  - Verify quota limits
  - Check CloudMonitor events

Step 3: Recovery Actions (5-10 min)
  - If quota issue → Request quota increase
  - If VPC issue → Delegate to alicloud-vpc-ops
  - If system stuck → Contact support with RequestId

Step 4: Escalation (if unresolved > 10 min)
  - Generate escalation report
  - Include: InstanceId, Region, RequestId, diagnostic report
```

#### RUNBOOK: instance-failure-investigation

```yaml
Trigger: Instance status = "Failed"

Step 1: Immediate Assessment
  - DescribeInstance → Capture failure state
  - ListDiagnoseReport → Check for failure cause
  - ListSearchLog → Search for ERROR patterns

Step 2: Failure Classification
  - Type A: Resource exhaustion (disk/memory)
    → Action: Expand disk, upgrade spec
  - Type B: Configuration error
    → Action: Rollback to last snapshot
  - Type C: System failure
    → Action: Escalate with full diagnostic

Step 3: Recovery Decision
  - If snapshot exists → Restore from last good snapshot
  - If no snapshot → Create new instance, reconfigure

Step 4: Post-Recovery Validation
  - DescribeInstance → Status = Normal
  - DescribeElasticsearchHealth → Cluster = green
  - Smoke test queries
```

#### RUNBOOK: cluster-red-recovery

```yaml
Trigger: Cluster health = "red" OR unassigned_shards > 0

Priority: CRITICAL (immediate response)

Step 1: Node Status Check
  - GET _cat/nodes?v → Check node availability
  - Identify missing/failed nodes

Step 2: Shard Analysis
  - GET _cluster/health?level=shards → Identify problem shards
  - GET _cat/shards?v&s=state → List unassigned shards

Step 3: Recovery Actions
  - If node down:
    → Restart node via RestartInstance
    → Monitor node rejoin
  - If disk full on node:
    → RUNBOOK: disk-emergency-expansion
  - If shard corruption:
    → Reinitialize corrupted shards (ES API)

Step 4: Cluster Restoration
  - Monitor cluster health transition: red → yellow → green
  - Verify shard allocation completed

Expected Recovery Time: 10-30 minutes
```

#### RUNBOOK: network-whitelist-check

```yaml
Trigger: Connection refused to ES endpoint

Step 1: Endpoint Verification
  - DescribeInstance → Get Endpoints array
  - Verify endpoint URL matches expected

Step 2: Whitelist Check
  - DescribeInstance → Get WhiteIpList
  - Verify client IP in whitelist
  - Check if whitelist is empty (all blocked)

Step 3: Network Connectivity
  - Ping endpoint from client
  - Check VPC routing (if VPC endpoint)
  - Verify security group rules (delegate to alicloud-ecs-ops)

Step 4: Whitelist Update (if needed)
  - ModifyWhiteIps → Add client IP CIDR
  - Validate: connection restored

Expected Recovery Time: 5-10 minutes
```

#### RUNBOOK: jvm-tuning

```yaml
Trigger: JVM heap usage > 85% sustained for > 5 minutes

Step 1: Heap Analysis
  - GET _nodes/stats/jvm → Detailed JVM metrics
  - Identify heap pressure pattern (gradual vs spike)

Step 2: Immediate Relief
  - If spike → Trigger manual GC (ES API)
  - If gradual → Reduce query load temporarily

Step 3: Configuration Optimization
  - Adjust heap size (UpdateInstance)
  - Recommended: 50% of node memory, max 32GB
  - Switch to G1GC (ES 7+)

Step 4: Workload Optimization
  - Reduce heavy aggregations
  - Implement query caching
  - Add coordinator nodes if needed

Expected Recovery Time: 30-60 minutes
```

---

## 4. Change Management (Safety Gates)

### 4.1 Change Window Definition

| Environment | Change Window | Override Policy |
|-------------|---------------|-----------------|
| **Production** | 02:00 - 06:00 local time | Requires 2 approvers |
| **UAT** | 00:00 - 06:00 local time | Requires 1 approver |
| **INT** | 18:00 - 22:00 local time | No override needed |
| **Dev** | Any time | No restriction |

### 4.2 Change Window Check Implementation

```go
type ChangeWindow struct {
    StartHour int
    EndHour   int
    Approvals int
}

var changeWindows = map[string]ChangeWindow{
    "production": {StartHour: 2, EndHour: 6, Approvals: 2},
    "uat":        {StartHour: 0, EndHour: 6, Approvals: 1},
    "int":        {StartHour: 18, EndHour: 22, Approvals: 0},
    "dev":        {StartHour: 0, EndHour: 24, Approvals: 0},
}

func checkChangeWindow(profile string, destructive bool) error {
    window := changeWindows[profile]
    
    currentHour := time.Now().Hour()
    
    if currentHour >= window.StartHour && currentHour < window.EndHour {
        fmt.Printf("✅ Within change window (%02d:00-%02d:00)\n", 
            window.StartHour, window.EndHour)
        return nil
    }
    
    if destructive {
        fmt.Printf("⚠️ Outside change window (%02d:00-%02d:00)\n", 
            window.StartHour, window.EndHour)
        fmt.Printf("   Current time: %02d:00\n", currentHour)
        fmt.Println("   Destructive operation requires explicit override.")
        
        // Require user confirmation for override
        fmt.Print("   Proceed anyway? [yes/no]: ")
        var response string
        fmt.Scanln(&response)
        
        if response != "yes" {
            return fmt.Errorf("Operation blocked: outside change window")
        }
        
        if window.Approvals > 0 {
            fmt.Printf("   Note: %d approvals required for override.\n", window.Approvals)
        }
    }
    
    return nil
}

// Usage before destructive operations
func safeRestart(client *elasticsearch.Client, instanceId, profile string) error {
    // Pre-flight: Change window check
    if err := checkChangeWindow(profile, true); err != nil {
        return err
    }
    
    // Pre-flight: Create snapshot
    if err := createPreChangeSnapshot(client, instanceId, "restart"); err != nil {
        return err
    }
    
    // Execute restart
    request := &elasticsearch.RestartInstanceRequest{
        InstanceId: tea.String(instanceId),
    }
    
    _, err := client.RestartInstance(request)
    return err
}
```

### 4.3 Destructive Operation Confirmation Matrix

| Operation | Confirmation Required | Change Window | Snapshot Required |
|-----------|----------------------|---------------|-------------------|
| **RestartInstance** | WARN: service interruption | Recommended | ✅ Yes (pre-change) |
| **DeleteInstance** | MUST: irreversible data loss | Required | ⚠️ N/A (data lost) |
| **UpdateInstance (spec)** | WARN: may cause restart | Recommended | ✅ Yes |
| **UpgradeEngineVersion** | MUST: backup recommended | Required | ✅ Yes |
| **ModifyWhiteIps** | WARN: may block access | Optional | ❌ No |

---

## 5. Chaos Engineering (Proactive Resilience)

### 5.1 Failure Injection Tests

| Test Scenario | Injection Method | Expected Outcome |
|---------------|------------------|------------------|
| **Node failure simulation** | RestartInstance on 1 node | Cluster remains green, shard rebalances |
| **Network partition** | ModifyWhiteIps to block 1 node | Cluster yellow, node reconnects after whitelist restore |
| **Disk pressure** | Write large test indices | Disk expansion triggered or alert fired |
| **Query overload** | High QPS test queries | Coordinator nodes added or query cache enabled |

### 5.2 Proactive Health Checks

```go
// Daily proactive health inspection
func dailyHealthCheck(client *elasticsearch.Client, instanceId string) {
    // Check 1: Instance status
    inst, _ := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
        InstanceId: tea.String(instanceId),
    })
    status := tea.ToString(inst.Body.Result.Status)
    fmt.Printf("Instance Status: %s %s\n", status, 
        status == "Normal" ? "✅" : "❌")
    
    // Check 2: Cluster health
    health, _ := client.DescribeElasticsearchHealth(&elasticsearch.DescribeElasticsearchHealthRequest{
        InstanceId: tea.String(instanceId),
    })
    clusterHealth := tea.ToString(health.Body.Result.Status)
    fmt.Printf("Cluster Health: %s %s\n", clusterHealth,
        clusterHealth == "green" ? "✅" : 
        clusterHealth == "yellow" ? "⚠️" : "❌")
    
    // Check 3: Snapshot existence (within last 24 hours)
    snapshots, _ := client.ListSnapshots(&elasticsearch.ListSnapshotsRequest{
        InstanceId: tea.String(instanceId),
    })
    recentBackup := false
    for _, snap := range snapshots.Body.Result.Snapshots {
        snapTime := tea.ToString(snap.CreateTime)
        // Check if snapshot created within 24 hours
        if time.Parse(snapTime).After(time.Now().Add(-24 * time.Hour)) {
            recentBackup = true
            break
        }
    }
    fmt.Printf("Recent Backup: %s\n", recentBackup ? "✅" : "❌")
    
    // Check 4: Multi-zone verification
    zoneCount := tea.ToInt32(inst.Body.Result.ZoneCount)
    fmt.Printf("Zone Count: %d %s\n", zoneCount,
        zoneCount >= 3 ? "✅" : "⚠️")
}
```

---

## 6. Stability Assessment Checklist

### P0 — MUST Pass (Critical)

| Check | Status | Evidence |
|-------|--------|----------|
| Instance has ≥ 3 data nodes (production) | ✅ | §1.1 Multi-zone matrix |
| Dedicated master nodes (3) configured | ✅ | §1.3 Node role separation |
| Daily snapshot backup enabled | ✅ | §2.1 Backup policy |
| Destructive operations require confirmation | ✅ | §4.3 Confirmation matrix |
| Change window check implemented | ⚠️ | §4.2 Change window check |
| Recovery runbook exists for critical faults | ⚠️ | §3.2 Runbook catalog |

### P1 — SHOULD Pass (Important)

| Check | Status | Evidence |
|-------|--------|----------|
| Multi-zone deployment (ZoneCount ≥ 2) | ⚠️ | §1.1 HA matrix |
| Cross-region backup copy configured | ⚠️ | §2.1 Backup policy |
| Proactive health checks scheduled | ⚠️ | §5.2 Daily health check |
| Chaos engineering tests documented | ⚠️ | §5.1 Failure injection |

---

*This guide aligns Elasticsearch operations with Alibaba Cloud Well-Architected Framework Stability Pillar best practices.*