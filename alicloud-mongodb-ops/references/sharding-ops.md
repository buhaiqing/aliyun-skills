# MongoDB Sharding Operations Reference

> **Resource Type:** Sharded Cluster (分片集群) on Alibaba Cloud MongoDB / ApsaraDB for MongoDB

This reference provides comprehensive operational guidance for MongoDB sharding on Alibaba Cloud, including balancer control, shard key selection, chunk management, mongos operations, and diagnostic playbooks.

---

## 1. Overview: Sharding Architecture on Alibaba Cloud

### Architecture Components

Alibaba Cloud MongoDB sharded cluster consists of three core components:

| Component | Role | Alibaba Cloud API Term |
|-----------|------|------------------------|
| **Mongos (Query Router)** | Routes queries to appropriate shards; manages chunk metadata | `Mongos` |
| **Shard (Data Node)** | Stores actual data; replica set per shard for HA | `Shard` |
| **Config Server** | Stores cluster metadata (chunk mapping, shard list) | `ConfigServer` (3-node replica set) |

### Instance Type Identification

```bash
# Check if instance is sharded cluster
aliyun dds DescribeDBInstances \
  --RegionId "{{user.region}}" \
  --DBInstanceId "{{user.db_instance_id}}" \
  --output cols=DBInstanceType rows=DBInstances.DBInstance[0].DBInstanceType

# Expected: "sharding" for sharded cluster
# Other values: "standalone", "replicaset"
```

### Network Address Types for Sharded Cluster

| Address Type | Use Case | API Response Field |
|--------------|----------|---------------------|
| **Mongos Address** | Application connection endpoint | `ConnectionString` (mongos) |
| **Shard Address** | Direct shard access (maintenance) | `ShardConnectionString` |
| **Config Server Address** | Internal metadata management | Not directly exposed via API |

```bash
# Get sharding network addresses
aliyun dds DescribeShardingNetworkAddress \
  --DBInstanceId "{{user.db_instance_id}}"
```

### Default Configuration

| Parameter | Default Value | Alibaba Cloud Constraint |
|-----------|---------------|--------------------------|
| Chunk Size | 64 MB | Configurable via parameter |
| Config Server Replicas | 3 | Fixed for HA |
| Min Shards | 2 | Minimum for production |
| Max Shards | 32 | Per cluster limit |

---

## 2. Balancer Control

### Balancer Overview

The balancer automatically distributes chunks across shards to maintain data balance. On Alibaba Cloud, balancer operations are managed via MongoDB shell commands executed through the mongos endpoint.

### Balancer Status Check

```javascript
// Connect to mongos and check balancer state
// Via MongoDB shell (application must have network access)
sh.getBalancerState()

// Check balancer lock (if balancer is active)
sh.isBalancerRunning()
```

### Enable/Disable Balancer

#### Scenario: Disable Balancer for Maintenance

```javascript
// Disable balancer (stops new migrations)
sh.stopBalancer()

// Verify balancer is stopped
sh.getBalancerState()  // Expected: false
```

#### Scenario: Enable Balancer After Maintenance

```javascript
// Enable balancer
sh.startBalancer()

// Verify balancer is running
sh.getBalancerState()  // Expected: true
```

### Balancer Window Configuration (Maintenance Windows)

Configure balancer to run only during specific time windows (low-traffic periods):

```javascript
// Set balancer window: e.g., 01:00 - 06:00 (UTC)
db.getSiblingDB("config").settings.updateOne(
  { _id: "balancer" },
  { $set: { 
    activeWindow: { 
      start: "01:00", 
      stop: "06:00" 
    } 
  }},
  { upsert: true }
)

// Remove balancer window (balancer runs continuously)
db.getSiblingDB("config").settings.updateOne(
  { _id: "balancer" },
  { $unset: { activeWindow: "" }
)
```

**Recommended Window Times (UTC):**

| Region | Recommended Window | Reason |
|--------|-------------------|--------|
| cn-hangzhou | 01:00 - 06:00 | Lowest traffic period |
| cn-shanghai | 02:00 - 07:00 | Business off-hours |
| cn-beijing | 03:00 - 08:00 | Night maintenance |

### Chunk Migration Monitoring

#### Monitor Active Migrations

```javascript
// Check for active migrations
db.getSiblingDB("config").migrations.find({ state: { $in: ["ready", "ongoing"] } })

// View migration details
db.getSiblingDB("config").migrations.find().pretty()
```

#### Migration Metrics via API

```bash
# Check cluster performance during migration
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.db_instance_id}}" \
  --Key "CpuUsage,MemoryUsage,IOPSUsage" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

### Balancer API Operations

Alibaba Cloud provides limited direct balancer API control. Most balancer operations require MongoDB shell access:

| Operation | Method | Access |
|-----------|--------|--------|
| Check balancer state | MongoDB shell | mongos endpoint |
| Start/stop balancer | MongoDB shell | mongos endpoint |
| Configure window | MongoDB shell | mongos endpoint |
| Monitor migrations | MongoDB shell + CMS metrics | mongos + API |

---

## 3. Shard Key Selection Strategy

### Cardinality Considerations

Shard key cardinality directly affects chunk distribution and query efficiency:

| Cardinality Level | Characteristics | Example |
|-------------------|-----------------|---------|
| **High** | Many unique values; good distribution | User ID, UUID, hashed fields |
| **Medium** | Limited unique values; acceptable | Region code, category ID |
| **Low** | Few unique values; poor distribution | Boolean flag, status enum |

**Decision Matrix:**

```
If cardinality < shard_count * 10:
  → WARNING: Potential for jumbo chunks or uneven distribution
  → Recommendation: Use hashed shard key or compound key
```

### Write Distribution Patterns

| Pattern | Shard Key Strategy | Pros | Cons |
|---------|-------------------|------|------|
| **Random Writes** | Hashed shard key | Even distribution | Range queries inefficient |
| **Sequential Writes** | Hashed shard key (NOT ranged) | Avoids hotspot | Range queries inefficient |
| **Region-based Writes** | Compound key (region + id) | Locality + distribution | Multi-region complexity |
| **Time-series Writes** | Compound key (time + id) | Time locality | Hot shard if monotonically increasing |

### Hashed vs Ranged Shard Keys

#### Hashed Shard Key

```javascript
// Create hashed shard key (recommended for even distribution)
sh.shardCollection("mydb.users", { userId: "hashed" })

// Characteristics:
// - Even chunk distribution across shards
// - Random write pattern (no hotspot)
// - Range queries broadcast to all shards
// - Good for high-cardinality fields
```

**Best for:**
- User IDs, session IDs, random UUIDs
- High write volume with random distribution
- Single-document queries by shard key

#### Ranged Shard Key

```javascript
// Create ranged shard key
sh.shardCollection("mydb.orders", { orderId: 1 })

// Characteristics:
// - Sequential data locality
// - Efficient range queries
// - Risk: hotspot on monotonically increasing keys
// - Good for time-series with compound key
```

**Best for:**
- Time-based queries (with compound key)
- Geographic region partitioning
- When data locality improves query performance

### Compound Shard Key Pattern

```javascript
// Compound key: region + userId (ranged + hashed)
sh.shardCollection("mydb.transactions", { region: 1, userId: "hashed" })

// Benefits:
// - Region locality for queries
// - userId hashed for write distribution
// - Optimal for multi-region applications
```

### Anti-Patterns: Shard Keys to Avoid

| Anti-Pattern | Problem | Impact |
|--------------|---------|--------|
| **Monotonically Increasing Key** | All writes go to single shard | Write bottleneck |
| **Low Cardinality Key** | Limited chunk count | Jumbo chunks |
| **Single-field Timestamp** | Hot shard for recent writes | Uneven distribution |
| **Large Embedded Object** | Index overhead | Performance degradation |

**Example Anti-Pattern (Avoid):**

```javascript
// DON'T: shard by timestamp alone
sh.shardCollection("mydb.logs", { timestamp: 1 })
// Result: All recent writes go to single shard

// DO: Use compound key with hashed component
sh.shardCollection("mydb.logs", { timestamp: 1, logId: "hashed" })
// Result: Writes distributed, time locality preserved
```

### Shard Key Selection Checklist

```
Pre-sharding Checklist:
[ ] Cardinality: > 1000 unique values per shard
[ ] Write pattern: No single-point hotspot
[ ] Query pattern: Most queries include shard key
[ ] Cardinality growth: Field values grow over time
[ ] Update frequency: Shard key is immutable (recommended)
```

---

## 4. Chunk Management

### Chunk Size Configuration

Default chunk size is 64MB. Configuration via MongoDB parameter:

```javascript
// Check current chunk size
db.getSiblingDB("config").settings.findOne({ _id: "chunksize" })

// Modify chunk size (requires cluster restart)
db.getSiblingDB("config").settings.updateOne(
  { _id: "chunksize" },
  { $set: { value: 128 } }  // Set to 128MB
)
```

**Chunk Size Trade-offs:**

| Size | Migration Frequency | Query Efficiency | Memory Usage |
|------|---------------------|------------------|--------------|
| 64MB (default) | High | Good | Moderate |
| 128MB | Medium | Better | Higher |
| 256MB | Low | Excellent | High |

### Chunk Splitting Thresholds

Automatic splitting occurs when:

- Chunk size > 1/2 of configured chunk size (32MB default)
- Chunk contains > threshold documents

Manual split (for jumbo chunk prevention):

```javascript
// Find chunk boundaries
db.getSiblingDB("config").chunks.find({ ns: "mydb.collection" })

// Manually split chunk at specific value
sh.splitAt("mydb.collection", { shardKey: "split_point_value" })

// Find split point automatically
sh.splitFind("mydb.collection", { shardKey: "query_point" })
```

### Chunk Migration Troubleshooting

#### Common Migration Issues

| Issue | Symptom | Cause | Solution |
|-------|---------|-------|----------|
| **Migration Timeout** | Migration stuck > 1h | Network latency, large chunk | Increase chunk size, check network |
| **Orphaned Documents** | Documents on wrong shard | Failed migration cleanup | Manual cleanup via cleanupOrphaned |
| **Lock Wait** | Migration blocked | DDL operation in progress | Stop DDL, retry migration |
| **Jumbo Chunk** | Chunk > max size | Low cardinality shard key | Change shard key or split manually |

#### Manual Migration Control

```javascript
// Move specific chunk to target shard
sh.moveChunk("mydb.collection", { shardKey: "value" }, "shard01")

// Check migration status
db.getSiblingDB("config").migrations.find({ ns: "mydb.collection" })
```

### Jumbo Chunks Handling

Jumbo chunks exceed the maximum migration size and cannot be moved automatically.

#### Detect Jumbo Chunks

```javascript
// Find jumbo chunks
db.getSiblingDB("config").chunks.find({
  ns: "mydb.collection",
  jumbo: true
}).pretty()

// Alternative: Check chunk size
db.getSiblingDB("config").chunks.aggregate([
  { $match: { ns: "mydb.collection" } },
  { $project: { 
    min: "$min",
    max: "$max",
    sizeEstimate: { $subtract: ["$max.shardKey", "$min.shardKey"] }
  }}
])
```

#### Resolve Jumbo Chunks

**Option A: Refine Shard Key (Recommended)**

```javascript
// Add compound shard key to increase cardinality
// Requires collection re-sharding (complex operation)
```

**Option B: Manual Split**

```javascript
// Split jumbo chunk into smaller pieces
sh.splitFind("mydb.collection", { shardKey: "midpoint_value" })

// Verify split succeeded
db.getSiblingDB("config").chunks.find({ 
  ns: "mydb.collection",
  min: { shardKey: "midpoint_value" }
})
```

**Option C: Force Migration (Advanced)**

```javascript
// WARNING: Advanced operation, use with caution
// Temporarily increase chunk size limit
db.getSiblingDB("config").settings.updateOne(
  { _id: "chunksize" },
  { $set: { value: 512 } }  // 512MB temporarily
)

// Move chunk
sh.moveChunk("mydb.collection", { shardKey: "value" }, "target_shard")

// Restore chunk size
db.getSiblingDB("config").settings.updateOne(
  { _id: "chunksize" },
  { $set: { value: 64 } }
)
```

---

## 5. Mongos (Query Router) Operations

### Connection Management

#### Mongos Connection String

```bash
# Get mongos connection string via API
aliyun dds DescribeShardingNetworkAddress \
  --DBInstanceId "{{user.db_instance_id}}" \
  --output cols=ConnectionString,Port rows=NetworkAddresses[?Role=='mongos']
```

#### Connection Pool Configuration

Recommended connection pool settings for mongos:

```yaml
# Application connection pool
maxPoolSize: 100          # Per mongos instance
minPoolSize: 10           # Maintain minimum connections
maxIdleTimeMS: 60000      # Close idle connections after 60s
waitQueueTimeoutMS: 5000  # Wait timeout for connection
```

#### Mongos Instance Scaling

```bash
# Add mongos node via API
aliyun dds AddShardingNode \
  --DBInstanceId "{{user.db_instance_id}}" \
  --NodeType "mongos" \
  --NodeInfo.NumberOfNodes 1

# Expected: New mongos endpoint added
# Poll for new address
aliyun dds DescribeShardingNetworkAddress \
  --DBInstanceId "{{user.db_instance_id}}"
```

### Query Routing Logic

| Query Type | Routing Behavior | Performance |
|------------|------------------|-------------|
| **Shard Key Exact Match** | Direct to single shard | Optimal |
| **Shard Key Range** | Target subset of shards | Good |
| **No Shard Key** | Broadcast to all shards | Poor |
| **Shard Key + Sort** | Merge sort across shards | Moderate |

#### Query Optimization Guidelines

```javascript
// Optimal: Query includes shard key
db.users.findOne({ userId: "user123" })  // Single shard

// Good: Range on shard key
db.orders.find({ orderId: { $gt: "1000", $lt: "2000" } })

// Avoid: Query without shard key (broadcast)
db.users.find({ name: "John" })  // Scans all shards

// Better: Add shard key hint
db.users.find({ name: "John", userId: "user123" })
```

### Multiple Mongos Deployment Patterns

| Pattern | Configuration | Use Case |
|---------|---------------|----------|
| **Single Mongos** | 1 mongos instance | Dev/test, low traffic |
| **Multi Mongos (Same Zone)** | 2-4 mongos in same zone | Production, moderate traffic |
| **Multi Mongos (Multi Zone)** | Mongos per zone | High availability, multi-region |
| **Load Balancer + Mongos** | LB fronting mongos pool | Enterprise, unified endpoint |

**Recommended Mongos Count:**

| Shard Count | Min Mongos | Recommended Mongos |
|-------------|------------|---------------------|
| 2-4 | 2 | 3 |
| 5-10 | 3 | 4-5 |
| 11-20 | 4 | 6-8 |
| 21-32 | 5 | 8-10 |

### Performance Optimization

#### Mongos Metrics to Monitor

```bash
# Monitor mongos via CMS
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName MongosConnectionUsage \
  --Dimensions '[{"instanceId":"{{user.db_instance_id}}"}]' \
  --Period 60
```

| Metric | Threshold | Action |
|--------|-----------|--------|
| MongosConnectionUsage | > 80% | Add mongos or scale pool |
| MongosCpuUsage | > 70% | Add mongos instances |
| MongosMemoryUsage | > 85% | Scale mongos spec |
| QueryLatency | > 100ms avg | Check query routing |

---

## 6. Shard Management via Alibaba Cloud API

### AddShardNode API

Add a new shard to the cluster:

```bash
# Add shard node
aliyun dds AddShardingNode \
  --DBInstanceId "{{user.db_instance_id}}" \
  --NodeType "shard" \
  --NodeInfo.ShardInfo.ShardClass "{{user.shard_class}}" \
  --NodeInfo.ShardInfo.ShardStorage "{{user.shard_storage}}" \
  --NodeInfo.ShardInfo.ReplicationFactor "{{user.replication_factor|3}}"
```

#### Pre-flight for AddShard

| Check | Method | Expected |
|-------|--------|----------|
| Instance exists | `DescribeDBInstances` | Status = Running |
| Instance type | `DescribeDBInstances` | DBInstanceType = sharding |
| Shard quota | `DescribeAvailableResource` | Available capacity |
| Current shard count | `DescribeDBInstanceAttribute` | < max limit (32) |

#### Post-execution Validation

```bash
# Poll for new shard status
for i in $(seq 1 60); do
  STATUS=$(aliyun dds DescribeDBInstanceAttribute \
    --DBInstanceId "{{user.db_instance_id}}" \
    --output cols=DBInstanceStatus rows=DBInstances.DBInstance[0].DBInstanceStatus)
  [ "$STATUS" = "Running" ] && break
  sleep 10
done

# Verify shard count increased
aliyun dds DescribeShardingNetworkAddress \
  --DBInstanceId "{{user.db_instance_id}}" \
  --output cols=Role,NodeId rows=NetworkAddresses[?Role=='shard']
```

### RemoveShardNode API

Remove a shard from the cluster (data must be migrated first):

```bash
# Remove shard node
aliyun dds RemoveShardingNode \
  --DBInstanceId "{{user.db_instance_id}}" \
  --NodeId "{{user.shard_node_id}}"
```

#### Pre-flight for RemoveShard (CRITICAL)

**WARNING: Data loss risk. Ensure data is migrated before removal.**

| Check | Method | Required State |
|-------|--------|----------------|
| Shard data count | MongoDB shell | Chunks = 0 on target shard |
| Balancer state | MongoDB shell | Running (migrates chunks) |
| Shard not primary | MongoDB shell | Not primary config server |
| User confirmation | Interactive | Explicit approval |

```javascript
// Pre-removal: Verify shard is empty
db.getSiblingDB("config").chunks.find({ shard: "shard_to_remove" }).count()
// Expected: 0 before removal

// If chunks exist, manually move them
sh.moveChunk("mydb.collection", { shardKey: "range" }, "new_shard")
```

### Shard Status Monitoring

```bash
# Get all shard nodes
aliyun dds DescribeShardingNetworkAddress \
  --DBInstanceId "{{user.db_instance_id}}" \
  --output cols=NodeId,Role,ConnectionString rows=NetworkAddresses[]

# Get shard metrics via CMS
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName ShardCpuUsage,ShardMemoryUsage \
  --Dimensions '[{"instanceId":"{{user.db_instance_id}}"}]' \
  --Period 60
```

### Balanced Cluster Validation

Validate cluster balance via MongoDB shell:

```javascript
// Check data distribution across shards
db.getSiblingDB("config").chunks.aggregate([
  { $group: {
    _id: "$shard",
    chunkCount: { $sum: 1 }
  }},
  { $sort: { chunkCount: -1 }}
])

// Expected: Similar chunk counts across shards
// Imbalance threshold: max_count - min_count > 5 chunks
```

**Balance Score Calculation:**

```
Balance Score = (max_chunks - min_chunks) / total_chunks * 100
- Score < 5%: Healthy
- Score 5-15%: Monitor
- Score > 15%: Investigate balancer
```

---

## 7. Diagnostic Commands and Playbooks

### Scenario: "数据分布不均衡" (Unbalanced Data Distribution)

**Symptoms:** Uneven chunk distribution across shards; some shards overloaded.

**Diagnostic Flow:**

```bash
# Step 1: Check chunk distribution via MongoDB shell
# (Requires mongos connection)
# JavaScript:
db.getSiblingDB("config").chunks.aggregate([
  { $group: { _id: "$shard", count: { $sum: 1 } } },
  { $sort: { count: -1 } }
])

# Step 2: Check balancer status
sh.getBalancerState()
sh.isBalancerRunning()

# Step 3: Check for jumbo chunks preventing migration
db.getSiblingDB("config").chunks.find({ jumbo: true })

# Step 4: Check shard key cardinality
db.mydb.collection.distinct("shardKeyField").length
```

**Decision Tree:**

| Finding | Root Cause | Solution |
|---------|------------|----------|
| Balancer off | Manual stop or config | `sh.startBalancer()` |
| Jumbo chunks | Low cardinality key | Split manually or refine shard key |
| Window restriction | Time window set | Adjust or remove window |
| Low cardinality | Shard key design | Re-design shard key (complex) |

**Resolution Steps:**

```javascript
// 1. Enable balancer if stopped
sh.startBalancer()

// 2. Split jumbo chunks
sh.splitFind("mydb.collection", { shardKey: "split_point" })

// 3. Manually move chunks to balance
sh.moveChunk("mydb.collection", { shardKey: "value" }, "underloaded_shard")
```

---

### Scenario: "分片迁移失败" (Chunk Migration Failure)

**Symptoms:** Migration stuck or fails; chunks not moving to target shard.

**Diagnostic Flow:**

```bash
# Step 1: Check migration status
# MongoDB shell:
db.getSiblingDB("config").migrations.find({ state: { $ne: "done" } })

# Step 2: Check for locks blocking migration
db.getSiblingDB("config").locks.find()

# Step 3: Check network connectivity
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.db_instance_id}}" \
  --Key "NetworkInRate,NetworkOutRate"

# Step 4: Check shard health
aliyun dds DescribeShardingNetworkAddress \
  --DBInstanceId "{{user.db_instance_id}}"
```

**Common Causes and Solutions:**

| Error Pattern | Cause | Solution |
|---------------|-------|----------|
| `MigrationAborted` | Target shard unavailable | Check shard status, retry |
| `LockConflict` | DDL operation in progress | Wait for DDL completion |
| `NetworkTimeout` | Network latency | Increase timeout, check network |
| `ChunkTooLarge` | Jumbo chunk | Split chunk before migration |
| `QuotaExceeded` | Target shard full | Scale shard storage |

**Manual Migration Recovery:**

```javascript
// Cancel stuck migration
db.getSiblingDB("config").migrations.deleteOne({ _id: "migration_id" })

// Retry migration
sh.moveChunk("mydb.collection", { shardKey: "value" }, "target_shard")

// Cleanup orphaned documents if migration partially completed
// On affected shard:
db.mydb.collection.cleanupOrphaned("shardKeyField")
```

---

### Scenario: "查询路由慢" (Slow Query Routing)

**Symptoms:** Queries taking longer than expected; mongos CPU high.

**Diagnostic Flow:**

```bash
# Step 1: Check mongos performance
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName MongosCpuUsage,MongosMemoryUsage \
  --Dimensions '[{"instanceId":"{{user.db_instance_id}}"}]' \
  --Period 60

# Step 2: Check query execution stats
# MongoDB shell:
db.mydb.collection.explain("executionStats").find({ query })

# Step 3: Check if query includes shard key
# Look for "SHARDING_FILTER" in explain output

# Step 4: Check slow logs
aliyun dds DescribeSlowLogRecords \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

**Decision Tree:**

| Finding | Root Cause | Solution |
|---------|------------|----------|
| Mongos CPU > 80% | Query broadcast | Add shard key to queries |
| No SHARDING_FILTER | Query without shard key | Optimize query pattern |
| Mongos connections high | Connection pool issue | Add mongos instances |
| Slow logs show scatter | Broadcast queries | Index optimization + shard key |

**Query Optimization:**

```javascript
// Before: Broadcast query (slow)
db.orders.find({ status: "pending" })

// After: Include shard key (fast)
db.orders.find({ orderId: "order123", status: "pending" })

// Or use hint for shard key
db.orders.find({ status: "pending" }).hint({ orderId: 1 })
```

---

### Scenario: "添加分片失败" (Add Shard Failure)

**Symptoms:** AddShardNode API call fails or new shard not functioning.

**Diagnostic Flow:**

```bash
# Step 1: Check API error response
aliyun dds AddShardingNode \
  --DBInstanceId "{{user.db_instance_id}}" \
  --NodeType "shard" \
  --NodeInfo.ShardInfo.ShardClass "{{user.shard_class}}"

# Step 2: Check quota
aliyun dds DescribeAvailableResource \
  --RegionId "{{user.region}}" \
  --Engine "MongoDB" \
  --EngineVersion "{{user.engine_version}}"

# Step 3: Check instance status
aliyun dds DescribeDBInstanceAttribute \
  --DBInstanceId "{{user.db_instance_id}}" \
  --output cols=DBInstanceStatus rows=DBInstances.DBInstance[0].DBInstanceStatus
```

**Common API Errors:**

| Error Code | Cause | Solution |
|------------|-------|----------|
| `QuotaExceeded.Shard` | Shard quota limit | Request quota increase |
| `InvalidInstanceStatus` | Instance not Running | Wait for stable state |
| `ShardClassUnavailable` | Spec not available | Check available specs |
| `ShardLimitExceeded` | Max shards (32) reached | Cannot add more |

---

### Scenario: "删除分片数据丢失风险" (Remove Shard Data Loss Risk)

**Symptoms:** User requests shard removal; data still on shard.

**Pre-flight Safety Checks:**

```javascript
// CRITICAL: Verify shard is empty BEFORE API call
db.getSiblingDB("config").chunks.count({ shard: "shard_to_remove" })
// Must be 0

// If not zero, migrate all chunks first
var chunks = db.getSiblingDB("config").chunks.find({ shard: "shard_to_remove" })
chunks.forEach(function(chunk) {
  sh.moveChunk(chunk.ns, chunk.min, "another_shard")
})

// Verify migration complete
db.getSiblingDB("config").chunks.count({ shard: "shard_to_remove" })
// Must be 0 before RemoveShardNode API call
```

**Safety Protocol:**

```
1. Check chunk count on target shard
2. If chunks > 0:
   a. Enable balancer
   b. Wait for automatic migration OR
   c. Manually move chunks
3. Re-verify chunk count = 0
4. Get explicit user confirmation
5. Execute RemoveShardNode API
```

---

## 8. API Reference Table

### Sharding-Specific APIs

| API | Purpose | Key Parameters | Risk Level |
|-----|---------|----------------|------------|
| `CreateShardingInstance` | Create sharded cluster | `ShardingInfo.ShardNumber`, `ShardingInfo.MongosNumber`, `ShardingInfo.ConfigServer` | Low |
| `AddShardingNode` | Add mongos or shard | `NodeType`, `NodeInfo.ShardInfo` or `NodeInfo.MongosInfo` | Medium |
| `RemoveShardingNode` | Remove shard or mongos | `NodeId` | **High** — data loss risk |
| `DescribeShardingNetworkAddress` | Get network addresses | `DBInstanceId` | None |
| `ModifyShardingNetworkAddress` | Modify address type | `NetworkType`, `ConnectionStringType` | Low |

### CreateShardingInstance Parameters

```bash
aliyun dds CreateDBInstance \
  --RegionId "{{user.region}}" \
  --Engine "MongoDB" \
  --EngineVersion "{{user.engine_version}}" \
  --DBInstanceClass "{{user.db_instance_class}}" \
  --DBInstanceStorage "{{user.db_instance_storage}}" \
  --DBInstanceDescription "{{user.description}}" \
  --NetworkType "VPC" \
  --VPCId "{{user.vpc_id}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --SecurityIPList "{{user.security_ips}}" \
  --StorageType "{{user.storage_type}}" \
  --ReplicationFactor "{{user.replication_factor}}" \
  --ZoneId "{{user.zone_id}}" \
  --ShardingInfo.ShardNumber "{{user.shard_count}}" \
  --ShardingInfo.MongosNumber "{{user.mongos_count}}" \
  --ShardingInfo.ConfigServer "{{user.config_server_class}}"
```

### AddShardingNode Examples

```bash
# Add a mongos node
aliyun dds AddShardingNode \
  --DBInstanceId "dds-xxxxxxx" \
  --NodeType "mongos" \
  --NodeInfo.NumberOfNodes 1

# Add a shard node
aliyun dds AddShardingNode \
  --DBInstanceId "dds-xxxxxxx" \
  --NodeType "shard" \
  --NodeInfo.ShardInfo.ShardClass "dds.shard.mid" \
  --NodeInfo.ShardInfo.ShardStorage 100 \
  --NodeInfo.ShardInfo.ReplicationFactor 3
```

### RemoveShardingNode Example

```bash
# Remove shard (ensure data migrated first)
aliyun dds RemoveShardingNode \
  --DBInstanceId "dds-xxxxxxx" \
  --NodeId "d-xxxxxxx"  # Shard node ID from DescribeShardingNetworkAddress
```

---

## 9. Monitoring Metrics Reference

### Sharding Metrics (CMS Namespace: acs_mongodb_dashboard)

| Metric | Unit | Threshold | Description |
|--------|------|-----------|-------------|
| `ShardCpuUsage` | % | > 80% | Shard CPU utilization |
| `ShardMemoryUsage` | % | > 85% | Shard memory utilization |
| `ShardConnectionUsage` | % | > 80% | Shard connection usage |
| `ShardDiskUsage` | % | > 90% | Shard disk utilization |
| `MongosCpuUsage` | % | > 70% | Mongos CPU utilization |
| `MongosMemoryUsage` | % | > 85% | Mongos memory usage |
| `MongosConnectionUsage` | % | > 80% | Mongos connection count |
| `ChunkMigrationCount` | count | Monitor | Active migrations |

### Monitoring Script

```bash
#!/bin/bash
# sharding-health-check.sh
# Usage: ./sharding-health-check.sh <DBInstanceId> <RegionId>

INSTANCE_ID="$1"
REGION="$2"
START_TIME=$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '15 min ago' +%Y-%m-%dT%H:%M:%SZ)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "=== Sharding Cluster Health Check ==="
echo "Instance: $INSTANCE_ID"
echo ""

# Check instance type
TYPE=$(aliyun dds DescribeDBInstances \
  --RegionId "$REGION" \
  --DBInstanceId "$INSTANCE_ID" \
  --output cols=DBInstanceType rows=DBInstances.DBInstance[0].DBInstanceType)
echo "[1] Instance Type: $TYPE"

if [ "$TYPE" != "sharding" ]; then
  echo "WARNING: Not a sharding instance"
  exit 1
fi

# Get shard addresses
echo ""
echo "[2] Sharding Network Addresses:"
aliyun dds DescribeShardingNetworkAddress \
  --DBInstanceId "$INSTANCE_ID"

# Check shard metrics
echo ""
echo "[3] Shard Performance (Last 15 min):"
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName ShardCpuUsage,ShardMemoryUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

# Check mongos metrics
echo ""
echo "[4] Mongos Performance (Last 15 min):"
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName MongosCpuUsage,MongosConnectionUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

# Check slow logs
echo ""
echo "[5] Recent Slow Logs:"
aliyun dds DescribeSlowLogRecords \
  --DBInstanceId "$INSTANCE_ID" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  --PageSize 10
```

---

## 10. Quick Reference Card

### Essential MongoDB Shell Commands for Sharding

```javascript
// Cluster status
sh.status()

// Balancer control
sh.startBalancer()
sh.stopBalancer()
sh.getBalancerState()
sh.isBalancerRunning()

// Collection sharding
sh.enableSharding("mydb")
sh.shardCollection("mydb.collection", { key: 1 })

// Chunk operations
sh.splitAt("mydb.collection", { key: "value" })
sh.splitFind("mydb.collection", { key: "value" })
sh.moveChunk("mydb.collection", { key: "value" }, "shardName")

// Info queries
db.getSiblingDB("config").chunks.find({ ns: "mydb.collection" })
db.getSiblingDB("config").shards.find()
db.getSiblingDB("config").migrations.find()
```

### Common Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Shard CPU | 70% | 85% |
| Shard Memory | 80% | 90% |
| Shard Disk | 80% | 95% |
| Mongos CPU | 60% | 80% |
| Mongos Connections | 75% | 90% |
| Chunk Imbalance | 10% | 20% |
| Active Migrations | > 3 | > 10 |

### Emergency Contacts

| Situation | Immediate Action |
|-----------|------------------|
| Data imbalance > 30% | Stop writes, enable balancer |
| Jumbo chunks detected | Split chunks manually |
| Shard failure | Check replication, may need restore |
| Mongos overload | Add mongos instances |
| Migration stuck > 2h | Cancel migration, retry |

---

## Appendix: Error Codes Reference

| Error Code | HTTP | Description | Agent Action |
|------------|------|-------------|--------------|
| `InvalidShardInfo` | 400 | Shard config invalid | Fix parameters |
| `ShardNotFound` | 404 | Shard ID not found | Verify NodeId |
| `ShardNotEmpty` | 400 | Shard has data | Migrate data first |
| `QuotaExceeded.Shard` | 400 | Shard quota limit | Request quota increase |
| `ShardLimitExceeded` | 400 | Max shards reached | Cannot add more |
| `MigrationInProgress` | 400 | Migration active | Wait or cancel |
| `BalancerLocked` | 400 | Balancer locked by DDL | Wait for completion |
| `InvalidShardKey` | 400 | Shard key invalid | Fix shard key spec |
| `ChunkTooLarge` | 400 | Jumbo chunk detected | Split chunk |
| `NetworkAddressConflict` | 400 | Address already exists | Use different address |

---

## Related References

- [Core Concepts](core-concepts.md) — MongoDB architecture overview
- [API & SDK Usage](api-sdk-usage.md) — Complete API reference
- [Troubleshooting Guide](troubleshooting.md) — General error handling
- [Monitoring & Alerts](monitoring.md) — Metrics and alerting setup

---

*Last Updated: 2026-05-19 | Version: 1.0.0 | alicloud-mongodb-ops skill*