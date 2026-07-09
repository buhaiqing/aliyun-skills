# Well-Architected Assessment — Alibaba Cloud Elasticsearch

> **Purpose:** Five-pillar assessment patterns for Elasticsearch operations aligned with Alibaba Cloud Well-Architected Framework (卓越架构).
> **Version:** 1.0.0
> **Last Updated:** 2026-05-17
> **Reference:** [阿里云卓越架构](https://help.aliyun.com/zh/product/2362200.html)

---

## Table of Contents

1. [Framework Overview](#1-framework-overview)
2. [Security Pillar (安全支柱)](#2-安全支柱-security)
3. [Stability Pillar (稳定支柱)](#3-稳定支柱-stability)
4. [Cost Pillar (成本支柱)](#4-成本支柱-cost)
5. [Efficiency Pillar (效率支柱)](#5-效率支柱-efficiency)
6. [Performance Pillar (性能支柱)](#6-性能支柱-performance)
7. [Assessment Checklist](#7-assessment-checklist)

---

## 1. Framework Overview

Alibaba Cloud Well-Architected Framework defines five pillars for cloud architecture excellence:

| Pillar | Core Focus | Elasticsearch Relevance |
|--------|-----------|-------------------------|
| **安全 (Security)** | Identity, network, data security | IAM, VPC isolation, HTTPS, whitelist |
| **稳定 (Stability)** | HA, DR, failure-oriented design | Multi-zone, snapshot backup, restart runbook |
| **成本 (Cost)** | Cost visibility, optimization | Instance sizing, reserved instances, storage tiering |
| **效率 (Efficiency)** | DevOps, automation, incident response | Batch operations, CI/CD integration, diagnostic automation |
| **性能 (Performance)** | Scaling, observability, baselines | JVM tuning, index optimization, query latency |

---

## 2. 安全支柱 (Security)

### 2.1 Identity & Access Management

#### Minimum RAM Permissions

| Operation | Required RAM Action | Resource Scope |
|-----------|--------------------|----------------|
| DescribeInstance | `elasticsearch:DescribeInstance` | `acs:elasticsearch:*:*:instance/*` |
| ListInstance | `elasticsearch:ListInstance` | `acs:elasticsearch:*:*:instance/*` |
| CreateInstance | `elasticsearch:CreateInstance` | `acs:elasticsearch:*:*:instance/*` |
| UpdateInstance | `elasticsearch:UpdateInstance` | `acs:elasticsearch:*:*:instance/{instanceId}` |
| DeleteInstance | `elasticsearch:DeleteInstance` | `acs:elasticsearch:*:*:instance/{instanceId}` |
| RestartInstance | `elasticsearch:RestartInstance` | `acs:elasticsearch:*:*:instance/{instanceId}` |
| CreateSnapshot | `elasticsearch:CreateSnapshot` | `acs:elasticsearch:*:*:instance/{instanceId}` |
| DiagnoseInstance | `elasticsearch:DiagnoseInstance` | `acs:elasticsearch:*:*:instance/{instanceId}` |

#### RAM Policy Template

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "elasticsearch:DescribeInstance",
        "elasticsearch:ListInstance",
        "elasticsearch:DiagnoseInstance",
        "elasticsearch:ListSnapshots",
        "elasticsearch:DescribeSnapshot"
      ],
      "Resource": "acs:elasticsearch:*:*:instance/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "elasticsearch:CreateInstance",
        "elasticsearch:UpdateInstance",
        "elasticsearch:DeleteInstance",
        "elasticsearch:RestartInstance",
        "elasticsearch:CreateSnapshot",
        "elasticsearch:DeleteSnapshot"
      ],
      "Resource": "acs:elasticsearch:*:*:instance/${instanceId}",
      "Condition": {
        "StringEquals": {"elasticsearch:InstanceType": "Standard"}
      }
    }
  ]
}
```

#### Best Practices

- **Never use `AdministratorAccess`** for Elasticsearch operations
- **Create dedicated RAM user/role** for Elasticsearch management
- **Use STS temporary credentials** for automated operations
- **Enable MFA** for interactive console access

### 2.2 Network Security

#### VPC Isolation

| Configuration | Recommendation | API |
|---------------|---------------|-----|
| VPC deployment | Use VPC, avoid public network | `CreateInstance` with VpcId |
| VPC endpoint | Create VPC endpoint for internal access | `CreateVpcEndpoint` |
| IP whitelist | Limit access to trusted IPs | `ModifyWhiteIps` |

#### Whitelist Management

```go
// Update IP whitelist (recommended pattern)
request := &elasticsearch.ModifyWhiteIpsRequest{
    InstanceId:     tea.String(instanceId),
    WhiteIpList:    tea.String("192.168.1.0/24,10.0.0.0/8"),  // CIDR format
    ModifyMode:     tea.String("Cover"),  // Cover or Append or Delete
}
```

#### Public Network Access

| Setting | Recommendation | Notes |
|---------|---------------|-------|
| `UpdatePublicNetwork(true)` | Avoid for production | Use VPC only |
| `UpdatePublicNetwork(false)` | Recommended | Disable public access |

### 2.3 Data Security

#### HTTPS Configuration

```go
// Enable HTTPS (recommended)
request := &elasticsearch.OpenHttpsRequest{
    InstanceId: tea.String(instanceId),
}

// Disable HTTPS (not recommended for production)
request := &elasticsearch.CloseHttpsRequest{
    InstanceId: tea.String(instanceId),
}
```

#### Credential Masking (MANDATORY)

| Context | Required Pattern |
|---------|-----------------|
| SDK execution | Use `os.Getenv()` — never log or print |
| Console output | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=abcd****` |
| Error messages | `Error: API failed (credential omitted)` |
| Verification | `test -n "$SECRET"` — existence check only |

---

## 3. 稳定支柱 (Stability)

### 3.1 面向失败的架构设计 (Failure-Oriented Design)

#### Multi-Zone Deployment

| ZoneCount | Availability | Recommended |
|-----------|--------------|-------------|
| 1 | Single zone | Development only |
| 2 | Cross-zone HA | Minimum for production |
| 3 | Maximum HA | **Recommended for production** |

```go
// Create multi-zone instance
request := &elasticsearch.CreateInstanceRequest{
    ZoneCount: tea.Int32(3),  // 3-zone deployment
    // ... other parameters
}
```

#### Node Configuration for HA

| Node Type | Minimum for HA | Notes |
|-----------|---------------|-------|
| Data Node | 3 | Distributed across zones |
| Master Node | 3 (dedicated) | Separate from data nodes |
| Coordinator Node | 2+ | Optional, for query routing |

### 3.2 备份与恢复 (Backup & Recovery)

#### Backup Operations

| Operation | API | Frequency Recommendation |
|-----------|-----|-------------------------|
| Create snapshot | `CreateSnapshot` | Daily for production |
| Cross-region copy | Manual via OSS | Weekly for DR |
| Retention policy | Console config | 7-30 days based on RPO |

#### Backup Before Destructive Operations

```go
// MANDATORY: Create snapshot before destructive changes
func safeRestart(client *elasticsearch.Client, instanceId string) error {
    // Step 1: Create pre-change snapshot
    snapRequest := &elasticsearch.CreateSnapshotRequest{
        InstanceId:    tea.String(instanceId),
        SnapshotName:  tea.String("pre-restart-" + time.Now().Format("20060102-150405")),
    }
    client.CreateSnapshot(snapRequest)
    
    // Step 2: Wait for snapshot success
    waitForSnapshot(client, instanceId, snapName, "Success")
    
    // Step 3: Execute restart
    restartRequest := &elasticsearch.RestartInstanceRequest{
        InstanceId: tea.String(instanceId),
    }
    client.RestartInstance(restartRequest)
    
    return nil
}
```

#### Recovery Runbook

**Phase 1: Backup Verification**
```go
// Verify backup exists
response, err := client.DescribeSnapshot(&elasticsearch.DescribeSnapshotRequest{
    InstanceId:    tea.String(instanceId),
    SnapshotName:  tea.String(snapshotName),
})
// Check status = "Success"
```

**Phase 2: Recovery Execution**
```go
// Restore from snapshot (if instance available)
// Note: Elasticsearch restore is typically done via ES API, not OpenAPI
// For full instance recovery, may need to recreate instance and restore data
```

**Phase 3: Post-Recovery Validation**
1. Verify instance status = `Normal`
2. Check cluster health = `green`
3. Validate index count matches backup
4. Run smoke queries against restored data

#### RTO/RPO Targets

| Metric | Target | Notes |
|--------|--------|-------|
| RTO (Recovery Time) | < 30 minutes | From snapshot restore initiation |
| RPO (Recovery Point) | < 24 hours | With daily snapshots |
| Cross-region RPO | < 7 days | With weekly cross-region backup |

### 3.3 确认机制 (Confirmation Gates)

#### Destructive Operation Confirmation

| Operation | Confirmation Required |
|-----------|----------------------|
| RestartInstance | WARN user: service interruption |
| DeleteInstance | MUST confirm: irreversible data loss |
| UpdateInstance (spec change) | WARN user: may cause restart |
| UpgradeEngineVersion | MUST confirm: backup recommended |

---

## 4. 成本支柱 (Cost)

### 4.1 Billing Models

| Model | Use Case | Savings |
|-------|----------|---------|
| **Pay-As-You-Go (后付费)** | Dev/test, short-term | N/A |
| **Subscription (包年包月)** | Production, stable workloads | Up to 85% vs pay-as-you-go |
| **Reserved Instance** | Long-term commitment | Additional 20-30% savings |

### 4.2 Instance Sizing Guide

| Workload Type | Recommended Spec | Node Count | Monthly Cost (Est.) |
|---------------|-----------------|------------|---------------------|
| Development | `elasticsearch.sn1ne.large` | 1 | ¥200 |
| Small production | `elasticsearch.sn2ne.large` | 3 | ¥900 |
| Medium production | `elasticsearch.sn2ne.xlarge` | 3 | ¥1,800 |
| Large production | `elasticsearch.sn2ne.2xlarge` | 5 | ¥4,500 |
| Enterprise | `elasticsearch.sn2ne.4xlarge` | 5+ | ¥9,000+ |

### 4.3 Idle Resource Detection

| Pattern | Detection Method | Action |
|---------|------------------|--------|
| CPU < 10% for 7 days | CMS metric `InstanceCpuUtilization` | Downgrade spec or stop |
| QPS < 1 for 7 days | CMS `SearchQps` | Consider stopping (pause billing) |
| Storage < 20% used | CMS `InstanceDiskUtilization` | Reduce disk size |

```go
// Idle detection pattern
func detectIdleInstance(client *elasticsearch.Client, instanceId string) {
    // Get metrics for last 7 days
    // If CPU avg < 10%, QPS avg < 1, recommend downgrade or stop
    fmt.Println("⚠️ Instance appears idle. Consider:")
    fmt.Println("  - Downgrading node spec")
    fmt.Println("  - Stopping instance to pause billing")
}
```

### 4.4 Storage Tiering

| Tier | Use Case | Cost |
|------|----------|------|
| Hot (SSD) | Active indices, frequent queries | High |
| Warm (Efficiency disk) | Historical data, infrequent access | 40% cheaper |
| Cold (Archive) | Long-term retention, rare access | 80% cheaper |

---

## 5. 效率支柱 (Efficiency)

### 5.1 Automation Patterns

#### Batch Operations

```go
// Batch update multiple instances
func batchUpdate(client *elasticsearch.Client, instanceIds []string) {
    for _, id := range instanceIds {
        // Process each instance
        // Wait for stabilization between operations
        processInstance(client, id)
        waitForInstance(client, id, "Normal", 300)
    }
}
```

#### CI/CD Integration

```yaml
# Pipeline step for ES validation
- name: Validate Elasticsearch
  run: |
    # Run health check
    curl -s "${ES_ENDPOINT}/_cluster/health" | jq '.status == "green"'
    
    # Run diagnostic
    go run ./diagnose.go --instance-id ${INSTANCE_ID}
```

### 5.2 Diagnostic Automation

```go
func automatedDiagnostic(client *elasticsearch.Client, instanceId string) {
    // Trigger diagnosis
    response, err := client.DiagnoseInstance(&elasticsearch.DiagnoseInstanceRequest{
        InstanceId: tea.String(instanceId),
    })
    
    // Get report
    reportId := tea.ToString(response.Body.Result.ReportId)
    
    // Fetch report results
    report, err := client.DescribeDiagnoseReport(&elasticsearch.DescribeDiagnoseReportRequest{
        InstanceId: tea.String(instanceId),
        ReportId:   tea.String(reportId),
    })
    
    // Parse and alert on findings
    for _, finding := range report.Body.Result.Findings {
        if tea.ToString(finding.Severity) == "High" {
            fmt.Printf("🚨 High severity issue: %s\n", tea.ToString(finding.Message))
        }
    }
}
```

---

## 6. 性能支柱 (Performance)

### 6.1 Key Performance Metrics

| Metric | Threshold | Action |
|--------|-----------|--------|
| `SearchLatency` | > 100ms → warn; > 500ms → alert | Optimize queries, tune JVM |
| `IndexingLatency` | > 50ms → warn; > 200ms → alert | Check write throughput |
| `JVMHeapMemoryUsedPercent` | > 80% → warn; > 95% → critical | Increase heap or reduce load |
| `InstanceCpuUtilization` | > 80% → warn; > 90% → critical | Scale up nodes |

### 6.2 JVM Tuning Recommendations

| Setting | Recommended Value | Notes |
|---------|------------------|-------|
| Heap Size | 50% of node memory | Max 32GB |
| GC Type | G1GC (ES 7+) | Better for large heaps |
| Thread Pool | Adjust per workload | Monitor rejection |

### 6.3 Index Optimization

| Pattern | Recommendation |
|---------|---------------|
| Shard count | 1 shard per 50GB data; max 1,000 per index |
| Replica count | 1 (HA), 2 (critical data) |
| Refresh interval | Default 1s; increase for bulk indexing |
| Merge policy | Tiered merge for write-heavy |

### 6.4 Scaling Triggers

| Condition | Action |
|-----------|--------|
| CPU > 80% sustained | Scale up node spec or add nodes |
| Disk > 80% | Expand disk or move data to warm nodes |
| Query latency > 500ms | Optimize queries or add coordinator nodes |
| Indexing queue full | Scale up write capacity |

---

## 7. Assessment Checklist

### P0 — MUST Pass

| Pillar | Check | Status |
|--------|-------|--------|
| Security | RAM policy scoped to Elasticsearch only | ✅ |
| Security | Credential masking enforced | ✅ |
| Security | IP whitelist configured (not 0.0.0.0/0) | ✅ |
| Stability | Instance has ≥ 3 data nodes (production) | ✅ |
| Stability | Daily snapshot backup enabled | ✅ |
| Stability | Destructive operations require confirmation | ✅ |
| Cost | Instance spec appropriate for workload | ✅ |
| Performance | JVM heap < 85% utilization | ✅ |
| Performance | Cluster health = green | ✅ |

### P1 — SHOULD Pass

| Pillar | Check | Status |
|--------|-------|--------|
| Security | HTTPS enabled for all connections | ⚠️ |
| Security | VPC endpoint used (not public) | ⚠️ |
| Stability | Multi-zone deployment (ZoneCount ≥ 2) | ⚠️ |
| Stability | Dedicated master nodes (3) | ⚠️ |
| Stability | Cross-region backup copy | ⚠️ |
| Cost | Reserved instance for stable workloads | ⚠️ |
| Cost | Warm nodes for cold data | ⚠️ |
| Efficiency | Automated health diagnostics | ⚠️ |
| Efficiency | CI/CD integration for validation | ⚠️ |
| Performance | Query latency < 100ms average | ⚠️ |
| Performance | Index-level optimization (shards/replicas) | ⚠️ |

---

*This assessment aligns Elasticsearch operations with Alibaba Cloud Well-Architected Framework best practices.*