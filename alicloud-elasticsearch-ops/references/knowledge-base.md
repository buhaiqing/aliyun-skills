# Knowledge Base — Alibaba Cloud Elasticsearch Operations

> **Purpose:** Common issues, known limitations, version-specific behaviors, and resolution patterns.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-17

---

## 1. Common Error Patterns & Quick Fixes

### 1.1 Instance Creation Failures

| Error Pattern | Root Cause | Quick Fix |
|---------------|------------|-----------|
| `QuotaExceeded.Instance` | Region quota limit reached | Request quota increase at quota console |
| `VpcNotFound` | VPC ID doesn't exist or wrong region | Create VPC via alicloud-vpc-ops |
| `VswitchNotFound` | VSwitch not in correct zone | Create VSwitch in target zone |
| `InvalidParameter.Version` | ES version not supported in region | Check supported versions via GetRegionConfiguration |
| `ChargeTypeMismatch` | Billing type conflict | Use PostPaid for testing, PrePaid for production |

### 1.2 Instance Status Issues

| Status | Possible Cause | Resolution |
|--------|----------------|------------|
| `Activating` (stuck >10min) | VPC connectivity issue | Check VSwitch, retry or recreate |
| `Inactive` | Instance stopped manually | Activate via console or API |
| `Failed` | Resource exhaustion or config error | Run DiagnoseInstance, check logs |
| `Locked` | Payment overdue or security lock | Resolve billing, check security status |

### 1.3 Cluster Health Issues

| Health Status | Indicators | Quick Diagnosis |
|---------------|------------|-----------------|
| `yellow` | unassigned_shards > 0 | Check node status, shard allocation |
| `red` | primary shards unassigned | Node failure, disk full, or network partition |
| `green` but slow | High query latency | Check JVM heap, index optimization |

### 1.4 Connection Failures

| Symptom | Diagnostic Steps | Resolution |
|---------|------------------|------------|
| Connection refused | 1. Check whitelist 2. Verify endpoint | ModifyWhiteIps to add client IP |
| SSL handshake failed | HTTPS not enabled or cert mismatch | Enable HTTPS via OpenHttps API |
| Authentication failed | Wrong credentials or expired | Reset password via UpdateInstance |
| Timeout | Network latency or overloaded nodes | Add coordinator nodes, check load |

---

## 2. Known Limitations & Workarounds

### 2.1 SDK/CLI Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| No `aliyun` CLI support | Must use Go SDK | JIT Go SDK execution pattern |
| No Terraform provider | Manual infrastructure | Use SDK scripts for automation |
| API version 2017-06-13 only | Limited to v6 SDK | Use correct SDK package version |

### 2.2 Elasticsearch Version Behaviors

| Version | Known Behavior | Recommendation |
|---------|----------------|----------------|
| `6.7_aliyun` | Legacy version, limited features | Upgrade to 7.x for new deployments |
| `7.10_aliyun` | Stable, widely used | **Recommended for most use cases** |
| `8.5_aliyun` | New features, possible incompatibilities | Test thoroughly before upgrade |
| `8.9_aliyun` | Latest, breaking changes from 7.x | Review migration guide before upgrade |

### 2.3 Regional Availability

| Region | Elasticsearch Available | Notes |
|--------|------------------------|-------|
| `cn-hangzhou` | ✅ Yes | Primary region, all versions |
| `cn-shanghai` | ✅ Yes | Secondary region |
| `cn-beijing` | ✅ Yes | All versions |
| `cn-shenzhen` | ✅ Yes | All versions |
| `cn-qingdao` | ⚠️ Limited | Not all versions available |
| `ap-southeast-1` (Singapore) | ✅ Yes | International region |

### 2.4 Node Spec Constraints

| Spec | Max Disk Size | Max Nodes | Use Case |
|------|--------------|-----------|----------|
| `elasticsearch.sn1ne.large` | 500GB | 50 | Small workloads |
| `elasticsearch.sn2ne.large` | 2TB | 100 | Standard production |
| `elasticsearch.sn2ne.xlarge` | 5TB | 200 | Medium workloads |
| `elasticsearch.sn2ne.2xlarge` | 10TB | 500 | Large workloads |
| `elasticsearch.sn2ne.4xlarge` | 20TB | 1000 | Enterprise |

---

## 3. Version-Specific Behaviors

### 3.1 ES 6.x → 7.x Migration

| Change | Impact | Migration Action |
|--------|--------|------------------|
| Mapping changes | Type removal | Remove `_type` from queries |
| Index template format | Legacy templates deprecated | Update to new template API |
| Java version | JDK 11+ required | Ensure client compatibility |
| Circuit breaker defaults | Different thresholds | Adjust breaker settings |

### 3.2 ES 7.x → 8.x Migration

| Change | Impact | Migration Action |
|--------|--------|------------------|
| Security enabled by default | All connections require auth | Update client configuration |
| Query DSL changes | Deprecated syntax removed | Update complex queries |
| Allocation settings | New allocation awareness | Update cluster settings |
| Kibana version | Must match ES version exactly | Upgrade Kibana together |

---

## 4. Common Performance Issues

### 4.1 JVM Heap Pressure

| Pattern | Cause | Resolution |
|---------|-------|------------|
| Heap > 90% sustained | Large result sets, memory-intensive queries | Add coordinator nodes, optimize queries |
| Frequent Full GC | Heap too small or inefficient | Increase heap to 50% of RAM, use G1GC |
| GC pauses > 500ms | Large heap with CMS GC | Switch to G1GC or ZGC |

### 4.2 Disk Performance

| Pattern | Cause | Resolution |
|---------|-------|------------|
| Disk I/O wait high | Heavy indexing, large merges | Use cloud_ssd, tune merge policy |
| Disk usage > 80% | Data growth exceeds capacity | Expand disk or add warm nodes |
| Segment count high | Frequent small updates | Force merge to reduce segments |

### 4.3 Query Latency

| Pattern | Cause | Resolution |
|---------|-------|------------|
| Search latency > 500ms | Complex aggregations, no caching | Use query cache, optimize aggs |
| Indexing latency > 200ms | Bulk size mismatch, refresh too frequent | Adjust bulk size, increase refresh_interval |
| Bulk rejection | Thread pool full | Increase thread pool, optimize bulk size |

---

## 5. Troubleshooting Decision Tree

### 5.1 Instance Not Starting

```
Instance stuck in "Activating"
│
├── Check VPC/VSwitch
│   ├── VPC exists? → NO: Create VPC
│   ├── VSwitch in correct zone? → NO: Create VSwitch
│   └── Security group allows ES traffic? → NO: Update security group
│
├── Check Quota
│   ├── Instance quota reached? → YES: Request quota increase
│   └── Node quota reached? → YES: Reduce nodes or request quota
│
├── Check Region Configuration
│   ├── Version supported? → NO: Use supported version
│   └── Spec available? → NO: Use valid spec
│
└── Check Logs
    ├── CloudMonitor events? → Review for errors
    └── ActionTrail? → Check for failed API calls
```

### 5.2 Cluster Health Degraded

```
Cluster health != green
│
├── Cluster yellow (unassigned replicas)
│   ├── Check node count ≥ replica_count + 1
│   ├── Check disk space on all nodes
│   ├── Check shard allocation settings
│   └── Resolution: Add nodes or reduce replicas
│
├── Cluster red (unassigned primaries)
│   ├── Identify failed nodes
│   ├── Check disk failure
│   ├── Check network partition
│   └ Resolution: Restore nodes, recover shards
│
└── Cluster green but performance issues
    ├── Check JVM heap usage
    ├── Check query patterns
    ├── Check index configuration
    └── Resolution: Tune JVM, optimize queries
```

---

## 6. Best Practices Summary

### 6.1 Instance Creation Checklist

```
Pre-flight:
□ VPC created in target region
□ VSwitch created in each zone (multi-zone)
□ Security group configured
□ RAM policy with elasticsearch permissions
□ Credentials validated (format + existence)
□ Quota checked (instance + nodes)

Instance Config:
□ ZoneCount ≥ 3 (production)
□ Dedicated master nodes (3)
□ NodeAmount ≥ 3 (data nodes)
□ DiskType = cloud_ssd (production)
□ HTTPS enabled
□ IP whitelist configured (not 0.0.0.0/0)

Post-creation:
□ Snapshot created (daily backup policy)
□ CMS alert rules configured
□ Health check passed (green)
□ Connection tested from application
```

### 6.2 Upgrade Checklist

```
Pre-upgrade:
□ Current version documented
□ Target version validated (supported)
□ Snapshot created (pre-upgrade backup)
□ Application compatibility tested
□ Change window confirmed

Upgrade:
□ UpgradeEngineVersion API called
□ Monitor progress via DescribeInstance
□ Check for errors in logs

Post-upgrade:
□ Cluster health verified (green)
□ Index functionality tested
□ Query compatibility verified
□ Application integration tested
□ Snapshot created (post-upgrade backup)
```

---

## 7. Quick Reference Commands

### 7.1 Instance Status Check

```go
// Quick status check script
response, _ := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
    InstanceId: tea.String(instanceId),
})
fmt.Printf("Status: %s\n", tea.ToString(response.Body.Result.Status))
fmt.Printf("Health: %s\n", tea.ToString(response.Body.Result.Health))
```

### 7.2 Cluster Health Check

```go
health, _ := client.DescribeElasticsearchHealth(&elasticsearch.DescribeElasticsearchHealthRequest{
    InstanceId: tea.String(instanceId),
})
fmt.Printf("Cluster: %s | Nodes: %d | Shards: %d\n",
    tea.ToString(health.Body.Result.Status),
    tea.ToInt32(health.Body.Result.NumberOfNodes),
    tea.ToInt32(health.Body.Result.ActiveShards))
```

### 7.3 Snapshot Verification

```go
snapshots, _ := client.ListSnapshots(&elasticsearch.ListSnapshotsRequest{
    InstanceId: tea.String(instanceId),
})
for _, snap := range snapshots.Body.Result.Snapshots {
    fmt.Printf("%s | %s | %s\n",
        tea.ToString(snap.SnapshotName),
        tea.ToString(snap.Status),
        tea.ToString(snap.CreateTime))
}
```

---

*This knowledge base provides quick reference for common Elasticsearch operations troubleshooting.*