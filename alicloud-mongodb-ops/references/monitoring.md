# Monitoring Alibaba Cloud MongoDB

## Key Metrics

### Performance Metrics (via DescribeDBInstancePerformance)

#### Core MongoDB Metrics

| Metric | Key | Unit | Threshold Suggestion |
|--------|-----|------|---------------------|
| CPU Usage | `MongoDB_CPUUsage` | % | > 80% warning, > 95% critical |
| Memory Usage | `MongoDB_MemoryUsage` | % | > 80% warning, > 95% critical |
| Connections | `MongoDB_Connections` | count | > 80% of max_connections warning |
| QPS | `MongoDB_QPS` | count/sec | Baseline deviation |
| IOPS | `MongoDB_IOPS` | count/sec | > 80% of max IOPS warning |
| Disk Usage | `MongoDB_DiskUsage` | % | > 80% warning, > 90% critical |
| Oplog Window | `MongoDB_OplogWindow` | hours | < 24h warning, < 12h critical |
| Replication Lag | `MongoDB_ReplicationLag` | seconds | > 10s warning, > 300s critical |

#### Connection Metrics

| Metric | Key | Unit | Threshold Suggestion |
|--------|-----|------|---------------------|
| Active Connections | `MongoDB_ActiveConnections` | count | Baseline + 50% warning |
| Available Connections | `MongoDB_AvailableConnections` | count | < 20% of max warning |
| Connection Created | `MongoDB_ConnectionsCreated` | count/sec | High rate indicates churn |
| Connection Closed | `MongoDB_ConnectionsClosed` | count/sec | Monitor for abnormal closures |

#### Operation Metrics

| Metric | Key | Unit | Threshold Suggestion |
|--------|-----|------|---------------------|
| Insert Operations | `MongoDB_InsertOps` | count/sec | Baseline tracking |
| Query Operations | `MongoDB_QueryOps` | count/sec | Baseline tracking |
| Update Operations | `MongoDB_UpdateOps` | count/sec | Baseline tracking |
| Delete Operations | `MongoDB_DeleteOps` | count/sec | Baseline tracking |
| GetMore Operations | `MongoDB_GetMoreOps` | count/sec | High rate may indicate slow queries |

### Replica Set Metrics

#### Replication Health

| Metric | Key | Unit | Threshold Suggestion |
|--------|-----|------|---------------------|
| Election Count | `MongoDB_ElectionCount` | count | > 5/day warning (unstable) |
| Primary Switch Count | `MongoDB_PrimarySwitchCount` | count | > 3/day warning |
| Secondary Health | `MongoDB_SecondaryHealth` | status | != "healthy" critical |
| Replication Lag | `MongoDB_ReplicationLag` | seconds | > 10s warning, > 300s critical |
| Oplog Window | `MongoDB_OplogWindow` | hours | < 24h warning |

#### Replica Set State Monitoring

| State | Description | Action |
|-------|-------------|--------|
| PRIMARY | Accepts writes | Monitor load |
| SECONDARY | Replicating data | Monitor lag |
| ARBITER | Voting only | No data ops |
| STARTUP | Initializing | Wait for completion |
| RECOVERING | Syncing after outage | Monitor progress |
| UNKNOWN | Network issue | Check connectivity |

### Sharding Metrics

#### Shard Health

| Metric | Key | Unit | Threshold Suggestion |
|--------|-----|------|---------------------|
| Shard Balance Status | `MongoDB_ShardBalanceStatus` | status | != "balanced" warning |
| Chunk Migration Count | `MongoDB_ChunkMigrationCount` | count | High count indicates imbalance |
| Mongos Connections | `MongoDB_MongosConnections` | count | Per mongos instance |
| Active Shard Count | `MongoDB_ActiveShardCount` | count | < expected count critical |
| Chunk Distribution | `MongoDB_ChunkDistribution` | ratio | > 20% imbalance warning |

#### Chunk Migration Monitoring

| Metric | Key | Unit | Threshold Suggestion |
|--------|-----|------|---------------------|
| Migrations Active | `MongoDB_MigrationsActive` | count | > 3 concurrent warning |
| Migrations Success | `MongoDB_MigrationsSuccess` | count | Track success rate |
| Migrations Failed | `MongoDB_MigrationsFailed` | count | > 0 investigate |
| Migration Duration | `MongoDB_MigrationDuration` | seconds | > 600s warning |

### WiredTiger Cache Metrics

#### Cache Performance

| Metric | Key | Unit | Threshold Suggestion |
|--------|-----|------|---------------------|
| Cache Hit Ratio | `MongoDB_CacheHitRatio` | % | < 95% warning, < 90% critical |
| Bytes Read Into Cache | `MongoDB_BytesReadIntoCache` | bytes/sec | High rate indicates cache miss |
| Bytes Written From Cache | `MongoDB_BytesWrittenFromCache` | bytes/sec | Monitor throughput |
| Cache Pages Read | `MongoDB_CachePagesRead` | pages/sec | High indicates pressure |
| Cache Pages Written | `MongoDB_CachePagesWritten` | pages/sec | High indicates eviction |
| Cache Dirty Pages | `MongoDB_CacheDirtyPages` | count | > 20% of max warning |

#### Memory Pressure Indicators

| Indicator | Formula | Threshold |
|-----------|---------|-----------|
| Cache Fill Ratio | `bytes_current / bytes_max` | > 80% warning |
| Eviction Rate | `pages_evicted / pages_read` | > 1.0 warning |
| Checkpoint Activity | `checkpoint_time` | > 60s between checkpoints |

### Lock Metrics

| Metric | Key | Unit | Threshold Suggestion |
|--------|-----|------|---------------------|
| Global Lock Acquire Wait | `MongoDB_GlobalLockWait` | microseconds | High values indicate contention |
| Read Lock Wait | `MongoDB_ReadLockWait` | microseconds | Baseline + 50% warning |
| Write Lock Wait | `MongoDB_WriteLockWait` | microseconds | Baseline + 50% warning |
| Queued Readers | `MongoDB_QueuedReaders` | count | > 10 warning |
| Queued Writers | `MongoDB_QueuedWriters` | count | > 5 warning |

## Alert Example (CloudMonitor)

### Single Metric Alert

```json
{
  "RuleName": "MongoDB-CPU-High",
  "MetricName": "MongoDB_CPUUsage",
  "Namespace": "acs_mongodb_dashboard",
  "Dimensions": [
    {
      "DBInstanceId": "{{user.db_instance_id}}"
    }
  ],
  "ComparisonOperator": "GreaterThanThreshold",
  "Threshold": 80,
  "EvaluationCount": 3,
  "ContactGroups": ["dba-team"]
}
```

### Replica Set Alert

```json
{
  "RuleName": "MongoDB-ReplicationLag-Critical",
  "MetricName": "MongoDB_ReplicationLag",
  "Namespace": "acs_mongodb_dashboard",
  "Dimensions": [
    {
      "DBInstanceId": "{{user.db_instance_id}}"
    }
  ],
  "ComparisonOperator": "GreaterThanThreshold",
  "Threshold": 300,
  "EvaluationCount": 2,
  "ContactGroups": ["dba-team"]
}
```

### Cache Performance Alert

```json
{
  "RuleName": "MongoDB-CacheHitRatio-Low",
  "MetricName": "MongoDB_CacheHitRatio",
  "Namespace": "acs_mongodb_dashboard",
  "Dimensions": [
    {
      "DBInstanceId": "{{user.db_instance_id}}"
    }
  ],
  "ComparisonOperator": "LessThanThreshold",
  "Threshold": 95,
  "EvaluationCount": 5,
  "ContactGroups": ["dba-team"]
}
```

## Multi-Dimensional Alert Rules

### Composite Alert: CPU + Connections + Cache

```json
{
  "RuleName": "MongoDB-Performance-Degradation",
  "Conditions": [
    {
      "MetricName": "MongoDB_CPUUsage",
      "Threshold": 80,
      "Duration": 300
    },
    {
      "MetricName": "MongoDB_Connections",
      "Threshold": 80,
      "Duration": 300
    },
    {
      "MetricName": "MongoDB_CacheHitRatio",
      "Threshold": 95,
      "ComparisonOperator": "LessThanThreshold",
      "Duration": 300
    }
  ],
  "Logic": "AND",
  "Action": "TriggerDiagnosisWorkflow"
}
```

### Composite Alert: Replication + Oplog

```json
{
  "RuleName": "MongoDB-Replication-Risk",
  "Conditions": [
    {
      "MetricName": "MongoDB_ReplicationLag",
      "Threshold": 60,
      "Duration": 180
    },
    {
      "MetricName": "MongoDB_OplogWindow",
      "Threshold": 24,
      "ComparisonOperator": "LessThanThreshold",
      "Duration": 180
    }
  ],
  "Logic": "AND",
  "Action": "TriggerReplicationDiagnosis"
}
```

### Composite Alert: Sharding Balance

```json
{
  "RuleName": "MongoDB-Sharding-Imbalance",
  "Conditions": [
    {
      "MetricName": "MongoDB_ShardBalanceStatus",
      "Threshold": "balanced",
      "ComparisonOperator": "NotEquals"
    },
    {
      "MetricName": "MongoDB_ChunkMigrationCount",
      "Threshold": 10,
      "Duration": 300
    }
  ],
  "Logic": "AND",
  "Action": "TriggerShardingDiagnosis"
}
```

## Monitoring Best Practices

### 1. Baseline Establishment

Collect metrics for 1-2 weeks to establish normal patterns:
- Record typical QPS ranges by business hour
- Document connection patterns (peak vs off-peak)
- Measure average replication lag under normal load
- Track cache hit ratio baseline for your workload

### 2. Multi-Dimensional Alerts

Combine metrics for comprehensive coverage:
- **Performance**: CPU + Connections + CacheHitRatio + LockWait
- **Capacity**: DiskUsage + DiskGrowthRate + IOPS
- **Replication**: ReplicationLag + OplogWindow + SecondaryHealth
- **Sharding**: ShardBalanceStatus + ChunkMigrationCount

### 3. Replica Set Monitoring

Critical for HA deployments:
- Monitor election frequency (indicates instability)
- Track replication lag on all secondaries
- Ensure oplog window covers expected outage time
- Verify all secondaries report healthy status

### 4. Sharding Health Checks

For sharded clusters:
- Monitor chunk balance across shards
- Track active migrations and failures
- Ensure all shards are active and reachable
- Monitor mongos connection distribution

### 5. WiredTiger Cache Optimization

Key for performance:
- Cache hit ratio < 95% indicates working set exceeds cache
- High eviction rate signals memory pressure
- Dirty pages buildup can delay checkpoints
- Consider increasing cache size if hit ratio consistently low

### 6. Capacity Planning

Track resource growth:
- Monitor disk usage trend monthly
- Calculate data growth rate for projections
- Plan for connection limit increases
- Evaluate IOPS requirements for workload changes

### 7. Lock Contention Analysis

Detect performance bottlenecks:
- High queued readers indicate read contention
- High queued writers indicate write contention
- Global lock wait > 100ms requires investigation
- Correlate with slow query patterns

### 8. Correlation Analysis

When multiple alerts fire:
- CPU high + Cache miss: working set exceeded
- Replication lag + Oplog short: high write volume
- Lock wait + Slow ops: query optimization needed
- Connection high + Lock wait: connection pool issue

---

## Security Monitoring & Audit

### Database Profiling (Slow Operations)

Enable MongoDB profiling to capture slow operations for security and performance analysis:

```javascript
// Enable profiling for operations > 100ms (level 1)
// Run via MongoDB shell connected to the instance
db.setProfilingLevel(1, 100)

// View recent slow operations
db.system.profile.find().sort({ millis: -1 }).limit(20)

// Check profiling status
db.getProfilingStatus()
```

> **Note:** Profiling has performance overhead. Use level 1 (slow ops only) in production; disable (`level 0`) during high-traffic periods if needed.

### Audit Log Considerations

Alibaba Cloud MongoDB audit capabilities vary by instance type and version:

| Capability | Availability | Enable Method |
|------------|-------------|---------------|
| **Operation Audit** | Enterprise / specific versions | Console or API (`ModifyAuditPolicy`) |
| **ActionTrail** | All instances | Account-level via Alibaba Cloud ActionTrail |
| **Slow Log Analysis** | All instances | `DescribeSlowLogRecords` API |

**Recommended Security Monitoring Workflow:**

1. **Enable ActionTrail** for all API calls to DDS (account-level)
2. **Enable database profiling** (level 1, 100ms threshold) for operational visibility
3. **Review slow logs daily** via `DescribeSlowLogRecords`
4. **Set alerts** for unusual query patterns (e.g., high `ScanRowCount`)

**Audit-Related Alerts:**

```json
{
  "RuleName": "MongoDB-Unusual-Query-Pattern",
  "MetricName": "QueryLatency",
  "Namespace": "acs_mongodb_dashboard",
  "Dimensions": [{"DBInstanceId": "{{user.db_instance_id}}"}],
  "ComparisonOperator": "GreaterThanThreshold",
  "Threshold": 500,
  "EvaluationCount": 3,
  "Action": "TriggerSecurityReview"
}
```