# Batch Operations — Alibaba Cloud Elasticsearch

> **Purpose:** Batch management patterns for multi-instance operations with safety controls.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-17

---

## 1. Batch Operation Safety Framework

### 1.1 Batch Operation Principles

| Principle | Implementation |
|-----------|----------------|
| **Staggered Execution** | Delay between operations to avoid cascade failures |
| **Pre-flight Validation** | Check all instances before starting batch |
| **Rollback Capability** | Pre-change snapshots for all affected instances |
| **Progress Tracking** | Real-time progress reporting and failure tracking |
| **Stop-on-Critical** | Halt batch on critical failures |

### 1.2 Batch Operation Decision Matrix

| Batch Size | Strategy | Recommended Stagger |
|------------|----------|---------------------|
| **1-3 instances** | Sequential | 30 seconds |
| **4-10 instances** | Semi-parallel (2-3 concurrent) | 60 seconds |
| **11-50 instances** | Batches of 5, staggered batches | 120 seconds |
| **> 50 instances** | Delegate to automation pipeline | N/A |

---

## 2. Batch Restart Instances

### 2.1 Safe Batch Restart Pattern

```go
func batchRestartInstances(client *elasticsearch.Client, instanceIds []string, profile string) {
    results := make(map[string]RestartResult)
    
    // Pre-flight: Validate all instances are in Normal state
    fmt.Println("=== Pre-flight Validation ===")
    for _, id := range instanceIds {
        inst, err := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
            InstanceId: tea.String(id),
        })
        if err != nil {
            results[id] = RestartResult{Status: "Error", Message: err.Error()}
            continue
        }
        
        status := tea.ToString(inst.Body.Result.Status)
        if status != "Normal" {
            results[id] = RestartResult{Status: "Skipped", Message: fmt.Sprintf("Status=%s", status)}
            fmt.Printf("⚠️ Skipping %s: status=%s\n", id, status)
        } else {
            results[id] = RestartResult{Status: "Ready"}
            fmt.Printf("✅ %s ready for restart\n", id)
        }
    }
    
    // Check change window
    if err := checkChangeWindow(profile, true); err != nil {
        fmt.Println("❌ Batch restart blocked: outside change window")
        return
    }
    
    // Execute restarts with stagger
    fmt.Println("\n=== Batch Restart Execution ===")
    stagger := 30 * time.Second
    
    for i, id := range instanceIds {
        if results[id].Status != "Ready" {
            continue
        }
        
        // Create pre-change snapshot
        fmt.Printf("[%d/%d] Creating snapshot for %s...\n", i+1, len(instanceIds), id)
        if err := createPreChangeSnapshot(client, id, "restart"); err != nil {
            results[id] = RestartResult{Status: "Error", Message: "Snapshot failed"}
            continue
        }
        
        // Execute restart
        fmt.Printf("[%d/%d] Restarting %s...\n", i+1, len(instanceIds), id)
        _, err := client.RestartInstance(&elasticsearch.RestartInstanceRequest{
            InstanceId: tea.String(id),
        })
        
        if err != nil {
            results[id] = RestartResult{Status: "Failed", Message: err.Error()}
            fmt.Printf("❌ Restart failed for %s: %v\n", id, err)
        } else {
            results[id] = RestartResult{Status: "Triggered"}
            fmt.Printf("✅ Restart triggered for %s\n", id)
        }
        
        // Stagger before next instance
        if i < len(instanceIds)-1 {
            time.Sleep(stagger)
        }
    }
    
    // Post-execution: Wait for all instances to return to Normal
    fmt.Println("\n=== Post-execution Validation ===")
    waitForBatchNormal(client, instanceIds, results, 600)
    
    // Report results
    printBatchReport(results)
}

type RestartResult struct {
    Status  string
    Message string
}

func waitForBatchNormal(client *elasticsearch.Client, instanceIds []string, results map[string]RestartResult, timeout int) {
    for i := 0; i < timeout/10; i++ {
        allNormal := true
        for _, id := range instanceIds {
            if results[id].Status != "Triggered" {
                continue
            }
            
            inst, _ := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
                InstanceId: tea.String(id),
            })
            
            status := tea.ToString(inst.Body.Result.Status)
            if status == "Normal" {
                results[id] = RestartResult{Status: "Completed"}
                fmt.Printf("✅ %s: Normal\n", id)
            } else {
                allNormal = false
                fmt.Printf("⏳ %s: %s\n", id, status)
            }
        }
        
        if allNormal {
            break
        }
        time.Sleep(10 * time.Second)
    }
}

func printBatchReport(results map[string]RestartResult) {
    fmt.Println("\n=== Batch Restart Report ===")
    completed := 0
    failed := 0
    skipped := 0
    
    for id, result := range results {
        fmt.Printf("%s: %s (%s)\n", id, result.Status, result.Message)
        switch result.Status {
        case "Completed":
            completed++
        case "Failed", "Error":
            failed++
        case "Skipped":
            skipped++
        }
    }
    
    fmt.Printf("\nSummary: Completed=%d, Failed=%d, Skipped=%d\n", completed, failed, skipped)
}
```

---

## 3. Batch Spec Upgrade

### 3.1 Batch Node Spec Upgrade Pattern

```go
func batchUpgradeNodeSpec(client *elasticsearch.Client, instanceIds []string, targetSpec string) {
    // Validate target spec is valid
    validSpecs := []string{
        "elasticsearch.sn2ne.large",
        "elasticsearch.sn2ne.xlarge",
        "elasticsearch.sn2ne.2xlarge",
        "elasticsearch.sn2ne.4xlarge",
    }
    
    if !contains(validSpecs, targetSpec) {
        fmt.Printf("❌ Invalid target spec: %s\n", targetSpec)
        return
    }
    
    fmt.Println("=== Batch Spec Upgrade ===")
    fmt.Printf("Target Spec: %s\n", targetSpec)
    fmt.Printf("Instances: %d\n", len(instanceIds))
    
    // Pre-flight: Check current specs and create snapshots
    for _, id := range instanceIds {
        inst, _ := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
            InstanceId: tea.String(id),
        })
        
        currentSpec := tea.ToString(inst.Body.Result.NodeSpec)
        fmt.Printf("Current spec for %s: %s → %s\n", id, currentSpec, targetSpec)
        
        // Create snapshot before upgrade
        createPreChangeSnapshot(client, id, "spec-upgrade")
    }
    
    // Execute upgrades in batches of 3
    batchSize := 3
    for i := 0; i < len(instanceIds); i += batchSize {
        batch := instanceIds[i:min(i+batchSize, len(instanceIds))]
        
        fmt.Printf("\nProcessing batch %d-%d...\n", i+1, i+len(batch))
        
        for _, id := range batch {
            _, err := client.UpdateInstance(&elasticsearch.UpdateInstanceRequest{
                InstanceId: tea.String(id),
                NodeSpec:   tea.String(targetSpec),
            })
            
            if err != nil {
                fmt.Printf("❌ Upgrade failed for %s: %v\n", id, err)
            } else {
                fmt.Printf("✅ Upgrade triggered for %s\n", id)
            }
        }
        
        // Wait for batch to stabilize before next batch
        if i+batchSize < len(instanceIds) {
            fmt.Println("Waiting 120s for batch stabilization...")
            time.Sleep(120 * time.Second)
        }
    }
}
```

---

## 4. Batch Snapshot Creation

### 4.1 Daily Backup Automation Pattern

```go
func createDailyBackups(client *elasticsearch.Client, instanceIds []string) {
    today := time.Now().Format("20060102")
    snapshotPrefix := "daily-backup-" + today
    
    fmt.Println("=== Daily Backup Creation ===")
    fmt.Printf("Date: %s\n", today)
    
    results := make(map[string]string)
    
    for _, id := range instanceIds {
        snapshotName := snapshotPrefix + "-" + id
        
        // Check instance status
        inst, _ := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
            InstanceId: tea.String(id),
        })
        
        status := tea.ToString(inst.Body.Result.Status)
        if status != "Normal" {
            results[id] = "Skipped: instance not Normal"
            fmt.Printf("⚠️ Skipping %s: status=%s\n", id, status)
            continue
        }
        
        // Check for existing daily backup
        existing := checkExistingSnapshot(client, id, snapshotPrefix)
        if existing != "" {
            results[id] = "Skipped: backup exists (" + existing + ")"
            fmt.Printf("⚠️ Skipping %s: backup already exists\n", id)
            continue
        }
        
        // Create snapshot
        _, err := client.CreateSnapshot(&elasticsearch.CreateSnapshotRequest{
            InstanceId:    tea.String(id),
            SnapshotName:  tea.String(snapshotName),
            Description:   tea.String("Automated daily backup"),
        })
        
        if err != nil {
            results[id] = "Failed: " + err.Error()
            fmt.Printf("❌ Snapshot failed for %s\n", id)
        } else {
            results[id] = "Created: " + snapshotName
            fmt.Printf("✅ Snapshot created for %s: %s\n", id, snapshotName)
        }
        
        // Stagger to avoid quota throttling
        time.Sleep(5 * time.Second)
    }
    
    printBackupReport(results)
}

func checkExistingSnapshot(client *elasticsearch.Client, instanceId, prefix string) string {
    snapshots, _ := client.ListSnapshots(&elasticsearch.ListSnapshotsRequest{
        InstanceId: tea.String(instanceId),
    })
    
    for _, snap := range snapshots.Body.Result.Snapshots {
        name := tea.ToString(snap.SnapshotName)
        if strings.HasPrefix(name, prefix) {
            return name
        }
    }
    return ""
}
```

---

## 5. Batch Configuration Update

### 5.1 Batch Whitelist Update Pattern

```go
func batchUpdateWhitelist(client *elasticsearch.Client, instanceIds []string, newIPs []string, mode string) {
    ipList := strings.Join(newIPs, ",")
    
    fmt.Println("=== Batch Whitelist Update ===")
    fmt.Printf("Mode: %s\n", mode)
    fmt.Printf("IPs: %s\n", ipList)
    
    for _, id := range instanceIds {
        // Get current whitelist
        inst, _ := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
            InstanceId: tea.String(id),
        })
        
        currentList := tea.ToString(inst.Body.Result.WhiteIpList)
        fmt.Printf("Current whitelist for %s: %s\n", id, currentList)
        
        // Calculate new whitelist based on mode
        var targetList string
        switch mode {
        case "Cover":
            targetList = ipList
        case "Append":
            if currentList != "" {
                targetList = currentList + "," + ipList
            } else {
                targetList = ipList
            }
        case "Delete":
            currentIPs := strings.Split(currentList, ",")
            newIPSet := make(map[string]bool)
            for _, ip := range currentIPs {
                newIPSet[ip] = true
            }
            for _, ip := range newIPs {
                delete(newIPSet, ip)
            }
            remaining := []string{}
            for ip := range newIPSet {
                remaining = append(remaining, ip)
            }
            targetList = strings.Join(remaining, ",")
        }
        
        // Update whitelist
        _, err := client.ModifyWhiteIps(&elasticsearch.ModifyWhiteIpsRequest{
            InstanceId:     tea.String(id),
            WhiteIpList:    tea.String(targetList),
            ModifyMode:     tea.String(mode),
        })
        
        if err != nil {
            fmt.Printf("❌ Whitelist update failed for %s: %v\n", id, err)
        } else {
            fmt.Printf("✅ Whitelist updated for %s: %s\n", id, targetList)
        }
        
        time.Sleep(10 * time.Second)
    }
}
```

---

## 6. Batch Health Check

### 6.1 Batch Cluster Health Verification

```go
func batchHealthCheck(client *elasticsearch.Client, instanceIds []string) {
    fmt.Println("=== Batch Health Check ===")
    
    healthSummary := make(map[string]ClusterHealthInfo)
    
    for _, id := range instanceIds {
        health, err := client.DescribeElasticsearchHealth(&elasticsearch.DescribeElasticsearchHealthRequest{
            InstanceId: tea.String(id),
        })
        
        if err != nil {
            healthSummary[id] = ClusterHealthInfo{Status: "Error", Message: err.Error()}
            continue
        }
        
        status := tea.ToString(health.Body.Result.Status)
        nodes := tea.ToInt32(health.Body.Result.NumberOfNodes)
        shards := tea.ToInt32(health.Body.Result.ActiveShards)
        unassigned := tea.ToInt32(health.Body.Result.UnassignedShards)
        
        healthSummary[id] = ClusterHealthInfo{
            Status:      status,
            Nodes:       nodes,
            Shards:      shards,
            Unassigned:  unassigned,
        }
        
        icon := "✅"
        if status == "yellow" {
            icon = "⚠️"
        } else if status == "red" {
            icon = "❌"
        }
        
        fmt.Printf("%s %s: health=%s, nodes=%d, shards=%d, unassigned=%d\n",
            icon, id, status, nodes, shards, unassigned)
    }
    
    // Generate summary
    green := 0
    yellow := 0
    red := 0
    error := 0
    
    for _, info := range healthSummary {
        switch info.Status {
        case "green":
            green++
        case "yellow":
            yellow++
        case "red":
            red++
        default:
            error++
        }
    }
    
    fmt.Printf("\n=== Summary ===\n")
    fmt.Printf("Green: %d, Yellow: %d, Red: %d, Error: %d\n", green, yellow, red, error)
    
    // Alert on red clusters
    if red > 0 || error > 0 {
        fmt.Println("🚨 CRITICAL: Some clusters are unhealthy!")
    }
}

type ClusterHealthInfo struct {
    Status     string
    Nodes      int32
    Shards     int32
    Unassigned int32
    Message    string
}
```

---

## 7. Batch Operation Templates

### 7.1 Template: Production Weekly Maintenance

```yaml
# Weekly Maintenance Batch Operations
# Execute: Sunday 02:00-06:00 (change window)

Operations:
  1. Pre-flight Check (batch-health-check)
     - Verify all instances Normal and green
     - Document current state

  2. Daily Backup (create-daily-backups)
     - Create snapshots for all instances
     - Verify snapshot success

  3. Health Optimization (conditional)
     - If cluster yellow: shard rebalance
     - If disk > 70%: cleanup old indices

  4. Post-maintenance Validation
     - Batch health check
     - Verify all services restored
```

### 7.2 Template: Emergency Patch Rollout

```yaml
# Emergency Patch Rollout (controlled execution)
# Trigger: Security vulnerability or critical fix

Operations:
  1. Assessment (batch-health-check)
     - Identify healthy instances for patch

  2. Snapshot Backup (create-daily-backups)
     - Pre-patch snapshots for rollback

  3. Staged Rollout (batch-restart with monitoring)
     - Stage 1: 10% instances (pilot)
     - Stage 2: 30% instances
     - Stage 3: 60% instances
     - Stage 4: 100% instances

  4. Monitoring Per Stage
     - Wait 5 minutes between stages
     - Health check after each stage
     - Halt if red clusters detected

  5. Rollback Procedure (if failure)
     - Restore from pre-patch snapshots
```

---

## 8. Batch Operation Checklist

### Pre-flight Checklist

```
□ All instances identified and documented
□ Current health status verified (all Normal/green)
□ Change window confirmed
□ Snapshots created for rollback
□ Stagger strategy defined
□ Progress tracking enabled
□ Stop-on-critical threshold set
```

### Execution Checklist

```
□ Pre-flight completed successfully
□ Batch operation started with progress reporting
□ Stagger delays applied correctly
□ Errors captured and logged
□ Failed instances marked for retry
□ Critical failures trigger halt
```

### Post-execution Checklist

```
□ All instances verified (status Normal)
□ Cluster health verified (green)
□ Services tested from application
□ Results documented
□ Failed instances scheduled for retry
□ Cleanup performed (temporary files)
```

---

*These batch operation patterns provide safe, controlled multi-instance management.*