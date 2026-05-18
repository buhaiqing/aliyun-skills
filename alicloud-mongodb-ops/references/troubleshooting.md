# Troubleshooting Alibaba Cloud MongoDB (DDS)

## Enhanced Error Handling

> **CRITICAL:** Before troubleshooting any MongoDB instance issue, verify the instance status and ensure proper API access.

### Pre-flight Check Execution

```bash
# Verify CLI configuration and credentials
aliyun dds DescribeInstances --RegionId cn-hangzhou --PageSize 1

# Check instance exists and is accessible
aliyun dds DescribeDBInstances --InstanceId "{{user.instance_id}}"
```

### Common Environment Errors

| Error Pattern | Root Cause | Solution |
|---------------|------------|----------|
| `Plugin 'aliyun-cli-dds' is required` | CLI plugin missing | Use SDK fallback or install plugin |
| `ALIBABA_CLOUD_ACCESS_KEY_ID is NOT set` | Credentials not loaded | Create .env file or set environment variables |
| `Cannot reach Alibaba Cloud endpoint` | Network connectivity issue | Check firewall/proxy settings |
| `InvalidInstanceId.NotFound` | Instance ID incorrect or region mismatch | Verify InstanceId and RegionId |
| `ServiceUnavailable` | DDS API temporarily unavailable | Retry with exponential backoff |

### CLI Configuration Issues

#### Issue: Region Mismatch

**Symptom:**
```
InvalidInstanceId.NotFound: The specified InstanceId does not exist.
```

**Root Cause:**
- InstanceId belongs to different region
- RegionId parameter not set correctly

**Diagnostic Flow:**
```bash
# Step 1: List all MongoDB instances across regions
for region in cn-hangzhou cn-shanghai cn-beijing cn-shenzhen; do
  echo "=== Region: $region ==="
  aliyun dds DescribeDBInstances --RegionId $region --PageSize 10
done

# Step 2: Check current CLI default region
aliyun configure list

# Step 3: Verify instance exists in specific region
aliyun dds DescribeDBInstances --RegionId "{{user.region}}" --InstanceId "{{user.instance_id}}"
```

**Solutions:**

**Option A: Specify Correct Region**
```bash
aliyun dds DescribeDBInstances --RegionId cn-shanghai --InstanceId dds-xxx
```

**Option B: Update CLI Default Region**
```bash
aliyun configure --region cn-shanghai
```

#### Issue: Credentials Not Loaded

**Symptom:**
```
ERROR: ALIBABA_CLOUD_ACCESS_KEY_ID is NOT set
ERROR: ALIBABA_CLOUD_ACCESS_KEY_SECRET is NOT set
```

**Root Cause:**
- .env file not found
- Environment variables not exported
- CLI not configured

**Diagnostic Flow:**
```bash
# Step 1: Check environment variables
env | grep ALIBABA_CLOUD

# Step 2: Check CLI config file
cat ~/.aliyun/config.json

# Step 3: Test API call
aliyun dds DescribeDBInstances --RegionId cn-hangzhou --PageSize 1
```

**Solutions:**

**Option A: Create .env File**
```bash
cat > .env <<EOF
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
EOF
```

**Option B: Configure CLI**
```bash
aliyun configure
# Enter AccessKeyId, AccessKeySecret, and default region
```

---

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `InvalidInstanceId.NotFound` / 404 | Instance not found | Verify InstanceId, check region, list all instances |
| `InvalidInstanceStatus` / 400 | Instance not in valid state | Wait for Normal status, check current status via DescribeDBInstances |
| `Forbidden.RAM` / 403 | RAM permission denied | Add `dds:*` policy to RAM user/role |
| `QuotaExceeded.Instance` / 400 | Instance quota exceeded | HALT; user raises quota or deletes unused instances |
| `InsufficientBalance` / 400 | Account balance insufficient | HALT; user must add funds |
| `InvalidParameter` / 400 | Request parameter validation failed | Align body with OpenAPI spec; check required fields |
| `ShardMigrationFailed` | Chunk migration failed during sharding | Check balancer status, network connectivity between shards |
| `ElectionInProgress` / 400 | Primary election in progress | Wait for election completion; monitor replica set status |
| `OplogRollover` | Oplog size too small for workload | Increase oplog size; calculate required retention window |
| `InvalidShardKey` / 400 | Shard key design invalid | Review shard key selection; ensure indexed field |
| `ReplicationLagHigh` | Secondary sync delay exceeds threshold | Check secondary load, network bandwidth, oplog window |
| `InvalidConnectionString` / 400 | Connection string format error | Verify connection string format; check SSL settings |
| `Throttling` / 429 | Rate limit exceeded | Back off exponentially; respect Retry-After header |
| `InternalError` / 5xx | Server-side error | Retry with backoff max 3 times; then HALT with RequestId |
| `OperationDenied` / 403 | Operation not permitted on this instance | Check instance type/architecture limitations |
| `InvalidAccountName` / 400 | Account name format invalid | Use correct naming convention; check for conflicts |
| `AccountAlreadyExists` / 400 | Account name already exists | Use different account name or update existing |
| `InvalidSecurityIPList` / 400 | Whitelist IP format invalid | Verify IP/CIDR format (e.g., 192.168.1.0/24) |
| `BackupAlreadyExists` / 400 | Backup with same ID exists | Use different backup ID or delete existing |
| `InvalidBackupMethod` / 400 | Backup method not supported | Check supported backup methods for instance type |

---

## Symptom-to-Root-Cause Quick Reference

When user reports a problem, use this table to narrow down the investigation path.

| User Symptom | Most Likely Root Cause Category | First Check |
|--------------|----------------------------------|-------------|
| "连接超时" / "Connection timeout" | 白名单未配置或实例状态异常 | 实例状态 + 白名单 + 网络配置 |
| "认证失败" / "Authentication failed" | 密码错误或账号权限问题 | 账号状态 + 密码验证 + 权限配置 |
| "查询慢" / "Slow queries" | 索引缺失或查询效率低 | 慢查询日志 + 索引命中率 |
| "写入阻塞" / "Write blocked" | 写关注级别过高或锁竞争 | 写关注配置 + 锁统计指标 |
| "主从切换频繁" / "Frequent primary switches" | 网络不稳定或选举配置问题 | 选举历史 + 网络延迟 + 优先级配置 |
| "分片数据不均衡" / "Shard data imbalance" | Balancer停止或Shard Key选择不当 | Balancer状态 + Chunk分布统计 |
| "Oplog空间不足" / "Oplog exhaustion" | Oplog配置过小或写入速率过高 | Oplog大小 + 保留窗口 + 写入量统计 |
| "内存使用率高" / "High memory usage" | 工作集过大或索引过多 | 内存指标 + 工作集估算 + 索引统计 |
| "CPU使用率突增" / "CPU spike" | 复杂查询或聚合操作 | 慢查询日志 + 正在运行的操作 |
| "磁盘空间不足" / "Disk space low" | 数据增长过快或未压缩 | 数据大小 + 索引大小 + 压缩配置 |
| "复制延迟高" / "Replication lag high" | Secondary负载高或网络问题 | 复制延迟指标 + Secondary状态 + Oplog窗口 |
| "连接数打满" / "Max connections reached" | 连接池配置不当或连接泄漏 | 连接数指标 + 连接来源分析 |
| "分片迁移失败" / "Chunk migration failed" | 网络问题或Jumbo chunk | Balancer日志 + Chunk大小 + 网络检查 |
| "集群不可用" / "Cluster unavailable" | 多节点故障或配置错误 | 各节点状态 + 选举状态 + 网络连通性 |
| "备份恢复失败" / "Backup restore failed" | 版本不兼容或实例配置差异 | MongoDB版本 + 实例规格 + 存储引擎 |
| "索引创建卡住" / "Index build stuck" | 大表索引或资源不足 | 正在创建的索引 + 资源使用情况 |

---

## Scenario-Based Diagnostic Playbooks

### Scenario 1: "连接超时 / 无法连接" (Connection Timeout)

**Symptoms:** Application cannot connect to MongoDB instance; connection timeouts or refused.

**Diagnostic Flow (execute in order, stop when root cause found):**

```bash
# Step 1: Check if instance exists and is Normal
aliyun dds DescribeDBInstances \
  --RegionId "{{user.region}}" \
  --InstanceId "{{user.instance_id}}" \
  --output cols=InstanceId,DBInstanceStatus,DBInstanceType,ConnectionDomain,Port \
  rows=DBInstances.DBInstance[0].{InstanceId,DBInstanceStatus,DBInstanceType,ConnectionDomain,Port}

# Expected: Status=Normal. If not Normal → wait or investigate.

# Step 2: Check whitelist configuration
aliyun dds DescribeSecurityIPs \
  --InstanceId "{{user.instance_id}}" \
  --output cols=SecurityIPGroupName,SecurityIPListAttribute,SecurityIPList \
  rows=SecurityIPGroups.SecurityIPGroup[].{SecurityIPGroupName,SecurityIPListAttribute,SecurityIPList}

# Expected: Application source IP is in the whitelist.

# Step 3: Check account status
aliyun dds DescribeAccounts \
  --InstanceId "{{user.instance_id}}" \
  --output cols=AccountName,AccountStatus,AccountType \
  rows=Accounts.Account[].{AccountName,AccountStatus,AccountType}

# Expected: Account is Available. If Unavailable → reset password or recreate.

# Step 4: Check connection string format
aliyun dds DescribeDBInstanceAttribute \
  --InstanceId "{{user.instance_id}}" \
  --output cols=ConnectionString,Port,SSLStatus \
  rows=DBInstanceAttribute.{ConnectionString,Port,SSLStatus}

# Step 5: Check connection usage via CMS
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60
```

**Decision Tree:**
- `DBInstanceStatus != Normal` → Wait for instance to stabilize; investigate if stuck
- Source IP not in whitelist → Add IP/CIDR to whitelist via ModifySecurityIPs
- Account status != `Available` → Reset password via ResetAccountPassword
- SSL enabled but client not using SSL → Update connection string to use SSL
- ConnectionUsage > 90% → Connection limit reached; scale up or optimize connection pool
- Replica set connection string format incorrect → Use replica set connection string format
- All above normal → Check VPC routing / security group / network path

---

### Scenario 2: "查询响应慢" / "Slow Query Response"

**Symptoms:** Query latency is high; operations taking longer than expected.

**Diagnostic Flow:**

```bash
# Step 1: Check slow logs for recent slow operations
aliyun dds DescribeSlowLogs \
  --InstanceId "{{user.instance_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --PageSize 20 \
  --output cols=OperationType,Collection,ExecutionTime,ReturnRowCount,ScanRowCount \
  rows=SlowLogs.SlowLog[].{OperationType,Collection,ExecutionTime,ReturnRowCount,ScanRowCount}

# Step 2: Check CPU usage (indicates query load)
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 3: Check memory usage (working set size)
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName MemoryUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 4: Check disk IOPS (indicates read/write pressure)
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName DiskIOPS \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 5: Check if index hit rate is low (via DAS if available)
# Delegate to alicloud-das-ops for performance analysis
```

**Decision Tree:**
- Slow logs show `COLLSCAN` (collection scan) → Missing index; create appropriate index
- `ScanRowCount >> ReturnRowCount` → Low selectivity query; optimize query or add better index
- CPU > 80% + slow aggregations → Complex aggregation pipeline; simplify or use covered queries
- MemoryUsage > 80% → Working set exceeds memory; scale up or optimize data access patterns
- DiskIOPS high → Disk bottleneck; check for unnecessary reads/writes
- Specific collection repeatedly slow → Analyze collection indexes via DescribeDBInstanceIndex
- Query using `$where` or JavaScript → Replace with standard query operators

---

### Scenario 3: "主从切换频繁" / "Frequent Primary Switches"

**Symptoms:** Replica set primary changes frequently; application connections disrupted.

**Diagnostic Flow:**

```bash
# Step 1: Check replica set status
aliyun dds DescribeReplicaSetRole \
  --InstanceId "{{user.instance_id}}" \
  --output cols=ReplicaSetRole,NodeId,NodeStatus,NodeIdAddress \
  rows=ReplicaSets.ReplicaSet[].{ReplicaSetRole,NodeId,NodeStatus,NodeIdAddress}

# Step 2: Check recent election events via logs
aliyun dds DescribeHistoryEvents \
  --InstanceId "{{user.instance_id}}" \
  --StartTime "$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --EventType "Election"

# Step 3: Check network latency between nodes
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName NetworkLatency \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 4: Check node health status
aliyun dds DescribeDBInstanceAttribute \
  --InstanceId "{{user.instance_id}}" \
  --output cols=DBInstanceStatus,ReplicationFactor \
  rows=DBInstanceAttribute.{DBInstanceStatus,ReplicationFactor}

# Step 5: Check if maintenance window overlaps
aliyun dds DescribeDBInstanceAttribute \
  --InstanceId "{{user.instance_id}}" \
  --output cols=MaintainTime,MaintainEndTime \
  rows=DBInstanceAttribute.{MaintainTime,MaintainEndTime}
```

**Decision Tree:**
- NetworkLatency > 100ms → Network instability causing heartbeat failures; investigate network path
- Node status shows `RECOVERING` or `ROLLBACK` → Node recovering; monitor recovery progress
- Multiple elections in short time → Network partition suspected; check VPC connectivity
- Maintenance window causing switches → Reschedule maintenance to off-peak hours
- Primary priority configuration uneven → Review and adjust node priorities
- Secondary resource exhaustion → Secondary unable to keep up; scale up secondary

---

### Scenario 4: "复制延迟高" / "High Replication Lag"

**Symptoms:** Secondary node significantly behind primary; stale reads from secondary.

**Diagnostic Flow:**

```bash
# Step 1: Check replication lag metrics
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName ReplicationLag \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60 \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 2: Check oplog window (time covered by oplog)
# Use MongoDB native command: rs.printReplicationInfo()
# Or check via DescribeDBInstanceAttribute for oplog configuration

# Step 3: Check secondary node CPU and memory
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName SecondaryCpuUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 4: Check network bandwidth usage
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName NetworkInBandwidth,NetworkOutBandwidth \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 5: Check write volume on primary
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName WriteOperations \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60
```

**Decision Tree:**
- ReplicationLag > 60s → Significant lag; investigate root cause
- Oplog window < 1 hour → Oplog too small; increase oplog size
- Secondary CPU > 80% → Secondary overloaded; scale up secondary node
- Network bandwidth saturated → Network bottleneck; upgrade network or reduce sync frequency
- Write volume spike → Primary write burst exceeding secondary sync capacity; temporary lag
- Persistent high lag → Secondary undersized; consider separate secondary specs
- Using `w:majority` write concern → High latency expected; consider `w:1` for faster writes

---

### Scenario 5: "分片迁移失败" / "Chunk Migration Failure"

**Symptoms:** Sharded cluster data distribution uneven; chunk migrations failing.

**Diagnostic Flow:**

```bash
# Step 1: Check balancer status
aliyun dds DescribeShardingBalancer \
  --InstanceId "{{user.instance_id}}" \
  --output cols=BalancerStatus,IsBalancerActive \
  rows=BalancerInfo.{BalancerStatus,IsBalancerActive}

# Step 2: Check chunk distribution across shards
aliyun dds DescribeShardingChunks \
  --InstanceId "{{user.instance_id}}" \
  --output cols=ShardName,ChunkCount,DataSize \
  rows=Chunks.Chunk[].{ShardName,ChunkCount,DataSize}

# Step 3: Check for jumbo chunks (chunks too large to migrate)
# Use MongoDB native command: sh.status() to see jumbo chunks

# Step 4: Check network connectivity between shards
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName InterShardNetworkLatency \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 5: Check migration history/logs
aliyun dds DescribeHistoryEvents \
  --InstanceId "{{user.instance_id}}" \
  --StartTime "$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --EventType "Migration"
```

**Decision Tree:**
- BalancerStatus = `Stopped` → Balancer disabled; enable via SetShardingBalancer
- ChunkCount highly uneven → Balancer should be active; check for blockers
- Jumbo chunks detected → Chunk size > 64MB; split chunk or refine shard key
- InterShardNetworkLatency high → Network issue between shards; check VPC connectivity
- Migration repeatedly failing → Check shard disk space; ensure destination has capacity
- Shard key selection poor → Redesign shard key for better distribution; requires resharding
- `moveChunk` errors in logs → Check for orphaned documents; cleanup using repairDatabase

---

### Scenario 6: "Oplog空间不足" / "Oplog Exhaustion"

**Symptoms:** Oplog fills too quickly; secondary nodes cannot sync; replication breaks.

**Diagnostic Flow:**

```bash
# Step 1: Check current oplog size
aliyun dds DescribeDBInstanceAttribute \
  --InstanceId "{{user.instance_id}}" \
  --output cols=OplogSize,OplogRetentionTime \
  rows=DBInstanceAttribute.{OplogSize,OplogRetentionTime}

# Step 2: Check write operation rate
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName WriteOperations,WriteBytes \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 3: Calculate oplog window
# Oplog Window = OplogSize / (WriteBytes per second)
# Target: Minimum 24-48 hours retention

# Step 4: Check replication lag trend
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName ReplicationLag \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 5: Check if secondary is catching up
aliyun dds DescribeReplicaSetRole \
  --InstanceId "{{user.instance_id}}" \
  --output cols=ReplicaSetRole,OptimeDate,LagTime \
  rows=ReplicaSets.ReplicaSet[].{ReplicaSetRole,OptimeDate,LagTime}
```

**Decision Tree:**
- Oplog retention window < 8 hours → Oplog too small for write volume
  - Calculate required size: `RequiredSize = AverageWriteRate * DesiredRetentionTime`
  - Recommended retention: 24-48 hours minimum
- Secondary falling behind due to oplog rollover → Increase oplog size immediately
- WriteBytes spike → Temporary high write volume; consider throttling
- Oplog cannot be resized dynamically → Plan oplog resize during maintenance
- Multiple secondary nodes lagging → All affected by oplog size; increase uniformly
- Using `w:1` writes → Oplog grows faster; consider batch writes

**Oplog Sizing Formula:**
```
OplogSize (MB) = WriteRate (MB/hour) * DesiredRetentionHours
Example: If writing 1GB/hour, need 24GB oplog for 24-hour retention
```

---

### Scenario 7: "内存使用率高" / "High Memory Usage"

**Symptoms:** Memory usage consistently high; potential eviction or performance degradation.

**Diagnostic Flow:**

```bash
# Step 1: Check memory usage metrics
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName MemoryUsage,MemoryUtilization \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 2: Check working set size estimation
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName WorkingSetSize \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 3: Check index statistics
# Via MongoDB native command: db.collection.getIndexes()

# Step 4: Check data and index size
aliyun dds DescribeDBInstanceAttribute \
  --InstanceId "{{user.instance_id}}" \
  --output cols=DataSize,IndexSize,TotalSize \
  rows=DBInstanceAttribute.{DataSize,IndexSize,TotalSize}

# Step 5: Check connection memory usage
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName ConnectionCount \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60
```

**Decision Tree:**
- MemoryUsage > 90% → Critical; scale up or reduce working set
- WorkingSetSize > 80% of total memory → Working set exceeds capacity
- IndexSize > 30% of memory → Too many indexes; remove unused indexes
- DataSize growing fast → Document growth or append-only pattern; implement TTL indexes
- ConnectionCount high → Each connection uses memory; optimize connection pool
- Query scan rate high → Queries not using indexes effectively; add covered queries
- WiredTiger cache full → Increase cache size or add more memory to instance

---

### Scenario 8: "CPU使用率突增" / "CPU Spike"

**Symptoms:** CPU usage spikes unexpectedly; query performance degradation.

**Diagnostic Flow:**

```bash
# Step 1: Check CPU usage trend
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60 \
  --StartTime "$(date -u -v-2H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 2: Check slow logs for expensive operations
aliyun dds DescribeSlowLogs \
  --InstanceId "{{user.instance_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --PageSize 50

# Step 3: Check operation count
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName OperationsCount \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 4: Check aggregation operations specifically
# Filter slow logs for aggregation operations

# Step 5: Check for index build operations (can cause CPU spike)
aliyun dds DescribeRunningTasks \
  --InstanceId "{{user.instance_id}}"
```

**Decision Tree:**
- Slow logs show aggregation pipelines → Optimize pipeline stages; use $match early
- COLLSCAN operations → Missing indexes; create indexes for query patterns
- Index build in progress → Background index building; wait for completion or cancel
- OperationsCount spike → Traffic surge; consider scaling or rate limiting
- $where or mapReduce operations → Replace with native operators
- In-memory sort detected → Add index for sort fields; limit result size
- Regex operations → Use anchored regex or text search index

---

### Scenario 9: "磁盘空间不足" / "Disk Space Low"

**Symptoms:** Disk usage approaching limits; potential write failures.

**Diagnostic Flow:**

```bash
# Step 1: Check disk usage
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName DiskUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 2: Check data size breakdown
aliyun dds DescribeDBInstanceAttribute \
  --InstanceId "{{user.instance_id}}" \
  --output cols=DataSize,IndexSize,LogSize,BackupSize,DiskUsed \
  rows=DBInstanceAttribute.{DataSize,IndexSize,LogSize,BackupSize,DiskUsed}

# Step 3: Check document count and average size
# Via MongoDB native command: db.collection.stats()

# Step 4: Check for TTL indexes (auto-expiry)
aliyun dds DescribeDBInstanceIndexes \
  --InstanceId "{{user.instance_id}}" \
  --output cols=IndexName,IndexType,ExpireAfterSeconds \
  rows=Indexes.Index[].{IndexName,IndexType,ExpireAfterSeconds}

# Step 5: Check storage engine compression ratio
aliyun dds DescribeDBInstanceAttribute \
  --InstanceId "{{user.instance_id}}" \
  --output cols=StorageEngine,CompressionRatio \
  rows=DBInstanceAttribute.{StorageEngine,CompressionRatio}
```

**Decision Tree:**
- DiskUsage > 85% → Warning; plan expansion
- DiskUsage > 95% → Critical; immediate expansion required
- IndexSize > 40% of total → Redundant indexes; remove unused indexes
- No TTL indexes on growing collections → Implement TTL for time-series data
- CompressionRatio low → Consider data compression or archive old data
- Document growth pattern → Documents growing over time; use fixed schema or cap collection
- Storage engine = WiredTiger → Compression enabled by default; verify compression settings

---

### Scenario 10: "备份恢复失败" / "Backup Restore Failure"

**Symptoms:** Backup restoration fails or incomplete.

**Diagnostic Flow:**

```bash
# Step 1: Check backup status and integrity
aliyun dds DescribeBackups \
  --InstanceId "{{user.instance_id}}" \
  --output cols=BackupId,BackupStatus,BackupSize,BackupMethod \
  rows=Backups.Backup[].{BackupId,BackupStatus,BackupSize,BackupMethod}

# Step 2: Check target instance configuration
aliyun dds DescribeDBInstanceAttribute \
  --InstanceId "{{user.target_instance_id}}" \
  --output cols=Engine,EngineVersion,StorageEngine,DBInstanceType \
  rows=DBInstanceAttribute.{Engine,EngineVersion,StorageEngine,DBInstanceType}

# Step 3: Compare source and target configurations
# Engine version must match or be compatible
# Storage engine must match

# Step 4: Check restore task status
aliyun dds DescribeRestoreTasks \
  --InstanceId "{{user.target_instance_id}}" \
  --output cols=TaskId,TaskStatus,Progress,ErrorCode \
  rows=RestoreTasks.RestoreTask[].{TaskId,TaskStatus,Progress,ErrorCode}

# Step 5: Check backup download status (if using physical backup)
aliyun dds DescribeBackupDownloadURL \
  --BackupId "{{user.backup_id}}"
```

**Decision Tree:**
- BackupStatus = `Failed` → Backup incomplete; use different backup
- Engine version mismatch → Version incompatible; upgrade target instance
- Storage engine mismatch → WiredTiger vs MMAPv1 incompatible; convert or use compatible backup
- Target instance smaller than backup → Insufficient storage; expand target instance
- Restore task shows error code → Check specific error; may need support intervention
- Cross-region restore → Ensure backup accessible in target region
- Sharded cluster backup → Use correct restore procedure for sharded backup

---

## Resource-Level Diagnostic Order

### Instance Issues
1. Verify instance exists: `aliyun dds DescribeDBInstances --InstanceId <id>`
2. Check instance status: should be `Normal` for normal operation
3. Verify region and zone configuration
4. Check instance class and storage capacity
5. Verify network type (VPC) and connection configuration
6. Check MongoDB engine version and storage engine
7. Verify architecture type: standalone / replica set / sharded

### Connection Issues
1. Check instance status is `Normal`
2. Verify whitelist contains source IP/CIDR
3. Check account status is `Available`
4. Verify password is correct
5. Check connection string format (replica set vs standalone)
6. Verify SSL settings match client configuration
7. Check connection usage metrics
8. Verify VPC routing and security group

### Performance Issues
1. Check CPU, memory, and disk metrics
2. Review slow logs for expensive operations
3. Check index usage and hit rate
4. Analyze query patterns and aggregation pipelines
5. Verify working set size vs memory
6. Check connection count and connection pool settings
7. Review disk IOPS and throughput
8. Check for in-progress operations (index builds, etc.)

### Replication Issues
1. Check replica set role and node status
2. Verify primary and secondary nodes are healthy
3. Check replication lag metrics
4. Verify oplog size and retention window
5. Check secondary resource usage
6. Review election history
7. Verify network connectivity between nodes
8. Check write concern settings

### Sharding Issues
1. Check balancer status and activity
2. Review chunk distribution across shards
3. Check for jumbo chunks
4. Verify shard key selection and distribution
5. Check network connectivity between shards
6. Review migration history and failures
7. Check shard resource utilization
8. Verify config server health

### Backup Issues
1. Check backup status and history
2. Verify backup method (snapshot vs logical)
3. Check backup retention policy
4. Verify disk space for backup storage
5. Check instance load during backup window
6. Review restore capability and tested restores
7. Verify cross-region backup configuration

---

## One-Shot Diagnostic Scripts

### Script 1: MongoDB Full Health Check

```bash
#!/bin/bash
# mongodb-full-health-check.sh
# Usage: ./mongodb-full-health-check.sh <InstanceId> <RegionId>

INSTANCE_ID="$1"
REGION="$2"

if [ -z "$INSTANCE_ID" ] || [ -z "$REGION" ]; then
  echo "Usage: ./mongodb-full-health-check.sh <InstanceId> <RegionId>"
  exit 1
fi

echo "========================================"
echo "MongoDB Full Health Check Report"
echo "InstanceId: $INSTANCE_ID"
echo "Region: $REGION"
echo "Timestamp: $(date)"
echo "========================================"

echo ""
echo "=== Instance Status ==="
aliyun dds DescribeDBInstances \
  --RegionId "$REGION" \
  --InstanceId "$INSTANCE_ID" \
  --output cols=InstanceId,DBInstanceStatus,DBInstanceType,Engine,EngineVersion,StorageEngine,ConnectionDomain,Port \
  rows=DBInstances.DBInstance[0].{InstanceId,DBInstanceStatus,DBInstanceType,Engine,EngineVersion,StorageEngine,ConnectionDomain,Port}

echo ""
echo "=== Resource Configuration ==="
aliyun dds DescribeDBInstanceAttribute \
  --InstanceId "$INSTANCE_ID" \
  --output cols=DBInstanceClass,StorageCapacity,DBInstanceStorage,ReplicationFactor \
  rows=DBInstanceAttribute.{DBInstanceClass,StorageCapacity,DBInstanceStorage,ReplicationFactor}

echo ""
echo "=== Key Metrics (Last 15 min) ==="
START_TIME=$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "--- CPU Usage ---"
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName CpuUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  --output cols=Timestamp,Maximum,Minimum,Average rows=Datapoints.Datapoint[]

echo ""
echo "--- Memory Usage ---"
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName MemoryUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "--- Disk Usage ---"
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName DiskUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "--- Connection Usage ---"
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Replica Set Status ==="
aliyun dds DescribeReplicaSetRole \
  --InstanceId "$INSTANCE_ID" \
  --output cols=ReplicaSetRole,NodeId,NodeStatus,NodeIdAddress \
  rows=ReplicaSets.ReplicaSet[].{ReplicaSetRole,NodeId,NodeStatus,NodeIdAddress}

echo ""
echo "=== Slow Logs (Last 1 hour) ==="
SLOW_START=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)
aliyun dds DescribeSlowLogs \
  --InstanceId "$INSTANCE_ID" \
  --StartTime "$SLOW_START" \
  --EndTime "$END_TIME" \
  --PageSize 10 \
  --output cols=OperationType,Collection,ExecutionTime,ReturnRowCount,ScanRowCount \
  rows=SlowLogs.SlowLog[].{OperationType,Collection,ExecutionTime,ReturnRowCount,ScanRowCount}

echo ""
echo "=== Whitelist Configuration ==="
aliyun dds DescribeSecurityIPs \
  --InstanceId "$INSTANCE_ID" \
  --output cols=SecurityIPGroupName,SecurityIPListAttribute,SecurityIPList \
  rows=SecurityIPGroups.SecurityIPGroup[].{SecurityIPGroupName,SecurityIPListAttribute,SecurityIPList}

echo ""
echo "=== Account Status ==="
aliyun dds DescribeAccounts \
  --InstanceId "$INSTANCE_ID" \
  --output cols=AccountName,AccountStatus,AccountType \
  rows=Accounts.Account[].{AccountName,AccountStatus,AccountType}

echo ""
echo "=== Backup Status (Last 5) ==="
aliyun dds DescribeBackups \
  --InstanceId "$INSTANCE_ID" \
  --PageSize 5 \
  --output cols=BackupId,BackupStatus,BackupType,BackupStartTime,BackupSize \
  rows=Backups.Backup[].{BackupId,BackupStatus,BackupType,BackupStartTime,BackupSize}

echo ""
echo "=== Replication Lag (Last 15 min) ==="
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName ReplicationLag \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "========================================"
echo "Health Check Complete"
echo "========================================"
```

### Script 2: MongoDB Performance Deep Dive

```bash
#!/bin/bash
# mongodb-performance-deep-dive.sh
# Usage: ./mongodb-performance-deep-dive.sh <InstanceId> <RegionId>

INSTANCE_ID="$1"
REGION="$2"
START_TIME=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "========================================"
echo "MongoDB Performance Deep Dive"
echo "InstanceId: $INSTANCE_ID"
echo "Analysis Period: $START_TIME to $END_TIME"
echo "========================================"

echo ""
echo "=== CPU Usage Trend ==="
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName CpuUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Memory Usage Trend ==="
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName MemoryUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Disk IOPS ==="
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName DiskIOPS \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Operations Count ==="
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName OperationsCount \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Read/Write Operations ==="
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName ReadOperations,WriteOperations \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Network Bandwidth ==="
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName NetworkInBandwidth,NetworkOutBandwidth \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Slow Logs Analysis ==="
aliyun dds DescribeSlowLogs \
  --InstanceId "$INSTANCE_ID" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  --PageSize 50 \
  --output cols=OperationType,Collection,ExecutionTime,ReturnRowCount,ScanRowCount,QueryPattern \
  rows=SlowLogs.SlowLog[].{OperationType,Collection,ExecutionTime,ReturnRowCount,ScanRowCount,QueryPattern}

echo ""
echo "=== Connection Analysis ==="
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName ConnectionCount,ConnectionUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Query Latency ==="
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName QueryLatency \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "========================================"
echo "Performance Analysis Complete"
echo "========================================"
```

### Script 3: Sharded Cluster Health Check

```bash
#!/bin/bash
# mongodb-sharding-health-check.sh
# Usage: ./mongodb-sharding-health-check.sh <InstanceId> <RegionId>

INSTANCE_ID="$1"
REGION="$2"

echo "========================================"
echo "MongoDB Sharded Cluster Health Check"
echo "InstanceId: $INSTANCE_ID"
echo "========================================"

echo ""
echo "=== Balancer Status ==="
aliyun dds DescribeShardingBalancer \
  --InstanceId "$INSTANCE_ID" \
  --output cols=BalancerStatus,IsBalancerActive,LastMigrationTime \
  rows=BalancerInfo.{BalancerStatus,IsBalancerActive,LastMigrationTime}

echo ""
echo "=== Chunk Distribution ==="
aliyun dds DescribeShardingChunks \
  --InstanceId "$INSTANCE_ID" \
  --output cols=ShardName,ChunkCount,DataSize,IndexSize \
  rows=Chunks.Chunk[].{ShardName,ChunkCount,DataSize,IndexSize}

echo ""
echo "=== Shard Node Status ==="
aliyun dds DescribeShardingNodes \
  --InstanceId "$INSTANCE_ID" \
  --output cols=ShardName,NodeId,NodeStatus,NodeRole \
  rows=Shards.Shard[].{ShardName,NodeId,NodeStatus,NodeRole}

echo ""
echo "=== Config Server Status ==="
aliyun dds DescribeDBInstanceAttribute \
  --InstanceId "$INSTANCE_ID" \
  --output cols=ConfigServerStatus,ConfigServerConnection \
  rows=DBInstanceAttribute.{ConfigServerStatus,ConfigServerConnection}

echo ""
echo "=== Inter-Shard Network Latency ==="
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName InterShardNetworkLatency \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo ""
echo "=== Migration History (Last 24h) ==="
aliyun dds DescribeHistoryEvents \
  --InstanceId "$INSTANCE_ID" \
  --StartTime "$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --EventType "Migration" \
  --PageSize 20

echo ""
echo "========================================"
echo "Sharding Health Check Complete"
echo "========================================"
```

---

## MongoDB-Specific Diagnostic Commands

### Native MongoDB Commands (via Shell)

These commands are executed via MongoDB shell after connecting to the instance.

#### Replica Set Diagnostics

| Command | Purpose | Key Output Fields |
|---------|---------|-------------------|
| `rs.status()` | Replica set health status | `members[].state`, `members[].optimeDate`, `members[].lagTime` |
| `rs.printReplicationInfo()` | Oplog statistics | `configured oplog size`, `log length start to end`, `oplog first event time` |
| `rs.printSlaveReplicationInfo()` | Secondary sync status | `source`, `syncedTo`, `lagTime` |
| `rs.conf()` | Replica set configuration | `members[].priority`, `members[].votes`, `settings.heartbeatIntervalMillis` |
| `db.adminCommand("replSetGetStatus")` | Detailed replica status | `myState`, `members[]`, `syncSourceHost` |

#### Sharding Diagnostics

| Command | Purpose | Key Output Fields |
|---------|---------|-------------------|
| `sh.status()` | Sharding overview | `balancer state`, `shards`, `databases`, `jumbo chunks` |
| `sh.getBalancerState()` | Balancer enabled status | `true/false` |
| `sh.isBalancerRunning()` | Active migration check | `true/false` |
| `db.collection.getShardDistribution()` | Chunk distribution | `Shard key`, `chunks`, `data size per shard` |
| `sh.balancerCollectionStatus("db.collection")` | Collection balance status | `chunks`, `migration status` |
| `db.adminCommand("balancerStatus")` | Detailed balancer info | `inBalancerRound`, `BalancerRoundNum`, `mode` |

#### Server and Database Diagnostics

| Command | Purpose | Key Output Fields |
|---------|---------|-------------------|
| `db.serverStatus()` | Server-wide metrics | `connections`, `opcounters`, `memory`, `locks`, `network` |
| `db.stats()` | Database statistics | `dataSize`, `indexSize`, `collectionCount`, `objectCount` |
| `db.collection.stats()` | Collection statistics | `size`, `storageSize`, `indexSize`, `nindexes`, `wiredTiger` |
| `db.collection.getIndexes()` | Index list | `name`, `key`, `v`, `background` |
| `db.collection.aggregate([{$indexStats: {}}])` | Index usage statistics | `accesses`, `since`, `usage` |
| `db.currentOp()` | Running operations | `op`, `ns`, `secs_running`, `waitingForLock` |
| `db.adminCommand("currentOp")` | All current operations | `inprog[]`, `lockStats` |

#### Performance Diagnostics

| Command | Purpose | Key Output Fields |
|---------|---------|-------------------|
| `db.collection.explain("executionStats").find(query)` | Query execution plan | `executionStats.totalDocsExamined`, `executionStats.executionTimeMillis`, `winningPlan` |
| `db.collection.explain("allPlansExecution").aggregate(pipeline)` | Aggregation plan | `stages[]`, `executionTimeMillis` |
| `db.adminCommand("getLog", "global")` | Global log entries | `log[]` |
| `db.setProfilingLevel(1, 50)` | Enable slow op profiling | `level`, `slowms` |
| `db.system.profile.find().sort({millis:-1}).limit(10)` | Recent slow operations | `op`, `ns`, `millis`, `command` |
| `db.adminCommand("top")` | Collection-level usage | `totals`, `read/write counts`, `time` |

#### Lock and Concurrency Diagnostics

| Command | Purpose | Key Output Fields |
|---------|---------|-------------------|
| `db.serverStatus().locks` | Lock statistics | `Global`, `Database`, `Collection` lock modes |
| `db.serverStatus().globalLock` | Global lock status | `currentQueue`, `activeClients`, `totalTime` |
| `db.currentOp({"waitingForLock": true})` | Waiting operations | `opid`, `secs_running`, `locks` |
| `db.adminCommand("lockInfo")` | Detailed lock info | `lock[]` |

#### Memory and Storage Diagnostics

| Command | Purpose | Key Output Fields |
|---------|---------|-------------------|
| `db.serverStatus().memory` | Memory metrics | `resident`, `virtual`, `mapped` |
| `db.serverStatus().wiredTiger.cache` | WiredTiger cache stats | `cache bytes currently in the cache`, `maximum cache size`, `eviction` |
| `db.collection.stats().wiredTiger` | Collection storage details | `block-manager`, `btree`, `cache` |
| `db.adminCommand("compact")` | Storage compaction | `bytesFreed`, `expired` |
| `db.stats(1024*1024)` | Database size in MB | `dataSize`, `storageSize`, `indexSize`, `totalSize` |

### Diagnostic Query Patterns

#### Find Slow Queries Without Index
```javascript
// Queries with high scan ratio
db.system.profile.find({
  "millis": {$gt: 100},
  "execStats.totalDocsExamined": {$gt: 1000}
}).sort({millis: -1}).limit(20)
```

#### Find Operations Waiting for Lock
```javascript
db.currentOp({
  "waitingForLock": true,
  "secs_running": {$gt: 5}
})
```

#### Check Index Usage Efficiency
```javascript
db.collection.aggregate([
  {$indexStats: {}},
  {$match: {"accesses.ops": {$gt: 0}}},
  {$sort: {"accesses.ops": -1}}
])
```

#### Find Large Documents
```javascript
db.collection.find({
  "$where": function() {
    return Object.bsonsize(this) > 16000; // > 16KB
  }
}).limit(100)
```

#### Calculate Oplog Window
```javascript
// Get oplog first and last entry timestamps
use local
var first = db.oplog.rs.find().sort({ts: 1}).limit(1).next().ts;
var last = db.oplog.rs.find().sort({ts: -1}).limit(1).next().ts;
var windowHours = (last.t - first.t) / 3600;
print("Oplog window: " + windowHours + " hours");
```

#### Check Chunk Distribution Imbalance
```javascript
use config
db.chunks.aggregate([
  {$group: {
    _id: "$shard",
    count: {$sum: 1},
    totalSize: {$sum: "$size"}
  }},
  {$sort: {count: -1}}
])
```

---

## Key Metrics Reference

### Instance-Level Metrics (via CMS)

| Metric | CMS MetricName | Unit | Threshold Suggestion |
|--------|---------------|------|---------------------|
| CPU Usage | `CpuUsage` | % | > 80% warning, > 95% critical |
| Memory Usage | `MemoryUsage` | % | > 80% warning, > 95% critical |
| Disk Usage | `DiskUsage` | % | > 80% warning, > 90% critical |
| Disk IOPS | `DiskIOPS` | count/sec | > 80% of max IOPS warning |
| Connection Usage | `ConnectionUsage` | % | > 80% warning, > 95% critical |
| Connection Count | `ConnectionCount` | count | Monitor trend, compare to max |
| Network In | `NetworkInBandwidth` | bytes/sec | Baseline monitoring |
| Network Out | `NetworkOutBandwidth` | bytes/sec | Baseline monitoring |
| Operations Count | `OperationsCount` | count/sec | Baseline deviation |
| Read Operations | `ReadOperations` | count/sec | Baseline monitoring |
| Write Operations | `WriteOperations` | count/sec | Baseline monitoring |
| Query Latency | `QueryLatency` | ms | > 100ms warning, > 500ms critical |

### Replica Set Metrics

| Metric | CMS MetricName | Unit | Threshold Suggestion |
|--------|---------------|------|---------------------|
| Replication Lag | `ReplicationLag` | seconds | > 60s warning, > 300s critical |
| Oplog Window | `OplogWindow` | hours | < 24h warning, < 8h critical |
| Primary Election Count | `ElectionCount` | count | Frequent elections investigate |
| Heartbeat Latency | `HeartbeatLatency` | ms | > 100ms warning |

### Sharding Metrics

| Metric | CMS MetricName | Unit | Threshold Suggestion |
|--------|---------------|------|---------------------|
| Chunk Count Per Shard | `ChunkCount` | count | Monitor distribution variance |
| Inter-Shard Network Latency | `InterShardNetworkLatency` | ms | > 100ms warning |
| Migration Count | `MigrationCount` | count/hour | High migration rate monitor |
| Balancer Status | `BalancerActive` | boolean | Should be true for active balancing |

### WiredTiger Cache Metrics

| Metric | Command Path | Unit | Threshold Suggestion |
|--------|--------------|------|---------------------|
| Cache Size | `serverStatus().wiredTiger.cache.maximum cache size` | bytes | Default 50% of memory |
| Cache Used | `serverStatus().wiredTiger.cache.cache bytes currently in the cache` | bytes | > 80% of max warning |
| Pages Read to Cache | `serverStatus().wiredTiger.cache.pages read into cache` | count | High reads indicate working set > cache |
| Pages Evicted | `serverStatus().wiredTiger.cache.pages evicted by application threads` | count | High eviction indicates pressure |
| Cache Hit Ratio | Calculated from above | % | < 90% warning |

---

## Alert Configuration Examples

### CloudMonitor Alert Rules

```json
{
  "RuleName": "MongoDB-CPU-High",
  "MetricName": "CpuUsage",
  "Namespace": "acs_mongodb_dashboard",
  "Dimensions": [
    {
      "instanceId": "{{user.instance_id}}"
    }
  ],
  "ComparisonOperator": "GreaterThanThreshold",
  "Threshold": 80,
  "EvaluationCount": 3,
  "Period": 60,
  "ContactGroups": ["dba-team"]
}
```

### Composite Alert: CPU + Slow Queries

```json
{
  "RuleName": "MongoDB-Performance-Degradation",
  "Conditions": [
    {
      "MetricName": "CpuUsage",
      "Threshold": 80,
      "Duration": 300
    },
    {
      "MetricName": "QueryLatency",
      "Threshold": 200,
      "Duration": 300
    }
  ],
  "Logic": "AND",
  "Action": "TriggerSlowLogAnalysis"
}
```

### Composite Alert: Replication Risk

```json
{
  "RuleName": "MongoDB-Replication-Risk",
  "Conditions": [
    {
      "MetricName": "ReplicationLag",
      "Threshold": 300,
      "Duration": 600
    },
    {
      "MetricName": "OplogWindow",
      "Threshold": 8,
      "ComparisonOperator": "LessThanThreshold",
      "Duration": 300
    }
  ],
  "Logic": "OR",
  "Action": "TriggerReplicationDiagnosis"
}
```

### Sharding Balance Alert

```json
{
  "RuleName": "MongoDB-Shard-Imbalance",
  "MetricName": "ChunkDistributionVariance",
  "Namespace": "acs_mongodb_dashboard",
  "Dimensions": [
    {
      "instanceId": "{{user.instance_id}}"
    }
  ],
  "ComparisonOperator": "GreaterThanThreshold",
  "Threshold": 20,
  "EvaluationCount": 5,
  "Action": "TriggerBalancerDiagnosis"
}
```

---

## Diagnostic Order (Standard)

1. **Describe instance** by ID: `aliyun dds DescribeDBInstances --InstanceId <id>`
2. **Check instance status:** `$.DBInstances.DBInstance[0].DBInstanceStatus` should be `Normal`
3. **Check key metrics:** CPU, memory, disk, connections via CMS
4. **Check slow logs:** `aliyun dds DescribeSlowLogs` for recent slow operations
5. **Check whitelist:** `aliyun dds DescribeSecurityIPs` for IP restrictions
6. **Check accounts:** `aliyun dds DescribeAccounts` for account status
7. **Check backups:** `aliyun dds DescribeBackups` for backup status
8. **For replica sets:** Check `DescribeReplicaSetRole` and replication lag metrics
9. **For sharded clusters:** Check `DescribeShardingBalancer` and chunk distribution
10. **Cross-skill delegation:** If DAS available, delegate for performance analysis

---

## Best Practices Summary

### Connection Management
- Use replica set connection string format for replica sets
- Configure proper connection pool size (typically 100-200 per application instance)
- Enable SSL for production environments
- Use appropriate read preferences for read-heavy workloads

### Index Strategy
- Create indexes for all query patterns
- Use covered queries to minimize document scans
- Monitor index usage and remove unused indexes
- Use compound indexes for multi-field queries
- Consider TTL indexes for time-series data

### Write Optimization
- Use appropriate write concern based on durability needs
- Batch writes when possible
- Avoid document growth patterns
- Use bulk operations for large inserts/updates

### Sharding Best Practices
- Choose shard key with good distribution and query locality
- Monitor chunk distribution and balancer activity
- Avoid jumbo chunks by proper shard key selection
- Plan for shard key cardinality

### Replication Best Practices
- Maintain adequate oplog size for write volume
- Monitor replication lag continuously
- Use appropriate read concern levels
- Consider geography when placing secondary nodes

### Monitoring Integration
- Set up alerts for CPU, memory, disk thresholds
- Monitor slow logs daily
- Track replication lag continuously
- Review backup success rates weekly
- Analyze query patterns monthly