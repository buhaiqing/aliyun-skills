# MongoDB Replica Set Operations Reference — Alibaba Cloud

> This reference provides **comprehensive replica set management workflows**, **election mechanism analysis**, **oplog optimization strategies**, **sync delay monitoring**, and **diagnostic playbooks** for Alibaba Cloud MongoDB replica set operations.

---

## 1. Overview: Replica Set Architecture

### 1.1 Replica Set Roles

| Role | Description | Data Storage | Vote Weight | Primary Functions |
|------|-------------|--------------|-------------|-------------------|
| **Primary** | 主节点, 处理所有写操作 | Yes | 1 | 写操作入口, 选举协调者, Oplog生成者 |
| **Secondary** | 从节点, 复制Primary数据 | Yes | 1 | 数据复制, 读请求分流, 故障切换候选者 |
| **Arbiter** | 投票节点, 仅参与选举 | No (仅存储投票信息) | 1 | 投票仲裁, 成本优化, 不存储数据 |

### 1.2 Node Configuration Patterns

| Pattern | Node Count | Configuration | Cost Level | Availability Level | Use Case |
|---------|------------|---------------|------------|-------------------|----------|
| **1-node** | 1 | Standalone | Low | None | 开发测试, 无高可用需求 |
| **3-node (Classic)** | 3 | Primary + 2 Secondary | Medium | High (单节点故障自动恢复) | 生产标准配置, 推荐 |
| **3-node (Arbiter)** | 3 | Primary + 1 Secondary + 1 Arbiter | Low-Medium | High | 成本优化场景, 数据节点仅2个 |
| **5-node** | 5 | Primary + 4 Secondary | High | Very High (双节点故障可恢复) | 关键业务, 跨地域部署 |
| **5-node (Arbiter)** | 5 | Primary + 3 Secondary + 1 Arbiter | Medium-High | Very High | 成本与可靠性平衡 |
| **7-node** | 7 | Primary + 6 Secondary | Very High | Maximum (三节点故障可恢复) | 金融级可靠性需求 |

### 1.3 Automatic Failover Mechanism

```
故障检测与自动切换流程
│
├─ Step 1: 心跳检测 (Heartbeat)
│  ├─ 每个节点每2秒向其他节点发送心跳
│  ├─ Primary检测Secondary状态
│  └─ Secondary检测Primary状态
│
├─ Step 2: 失败判定 (Failure Detection)
│  ├─ Primary心跳超时 (10秒无响应)
│  │  └─ Secondary标记Primary为"疑似不可达"
│  ├─ 连续心跳失败达到阈值
│  │  └─ 触发选举流程
│
├─ Step 3: 选举触发 (Election Trigger)
│  ├─ 检测到Primary不可达
│  ├─ Secondary发起选举请求
│  ├─ 所有投票节点参与投票
│  └─ 获得多数票的Secondary成为新Primary
│
├─ Step 4: 新Primary选举 (New Primary Election)
│  ├─ 基于priority和optime选择候选者
│  ├─ 确保数据完整性(optime最新)
│  ├─ 获得>50%投票节点支持
│  └─ 新Primary开始接受写操作
│
└─ Step 5: 客户端重连 (Client Reconnection)
   ├─ 客户端检测Primary变更
   ├─ 自动连接新Primary (驱动支持)
   └─ 请求重试机制生效
```

**关键参数**:
- **heartbeatIntervalMillis**: 心跳间隔 (默认2秒)
- **electionTimeoutMillis**: 选举超时 (默认10秒)
- **stepDownPeriodSecs**: Primary主动降级等待时间

---

## 2. Primary/Secondary Operations

### 2.1 Role Election Process

| Phase | Action | Duration | Key Metrics |
|-------|--------|----------|-------------|
| **Phase 1: Detection** | 心跳检测Primary不可达 | 0-10s | Heartbeat failures |
| **Phase 2: Candidate Selection** | Secondary自检optime, 确定候选者 | 1-2s | Optime comparison |
| **Phase 3: Voting** | 向所有节点发送选举请求 | 1-5s | Vote responses |
| **Phase 4: Majority Check** | 确认获得>50%投票 | 1-2s | Vote count |
| **Phase 5: Primary Promotion** | 新Primary接管写操作 | 0-5s | Primary status change |

**CLI查询当前角色**:

```bash
# 查询实例副本集角色
aliyun dds DescribeReplicaSetRole \
  --DBInstanceId "{{user.instance_id}}""

# 输出字段解析
# - PrimaryNode: 当前Primary节点ID
# - SecondaryNodes: Secondary节点列表
# - ArbiterNodes: Arbiter节点列表
# - ReplicaSetStatus: 副本集状态 (Normal/Abnormal)
```

### 2.2 Primary Step-down Commands

#### 场景: 人为触发Primary切换

| Trigger | Method | Impact | Recovery Time |
|---------|--------|--------|---------------|
| **维护窗口切换** | MongoDB shell: `rs.stepDown()` | 写操作暂停10-30秒 | 自动选举新Primary |
| **升级Secondary优先级** | MongoDB shell: `rs.reconfig()` | 写操作暂停 | 优先级高的Secondary当选 |
| **强制降级** | MongoDB shell: `rs.stepDown(60, 30)` | 60秒内不参与选举 | 需等待超时或手动恢复 |
| **阿里云API触发** | `SwitchDBInstanceHA` | 自动切换Primary | < 30秒 |

**MongoDB Shell操作示例**:

```javascript
// 连接到Primary节点
mongo --host <primary_host> --port <port> -u <user> -p <password> --authenticationDatabase admin

// 查看当前副本集状态
rs.status()

// Primary主动降级 (推荐: 在维护窗口执行)
rs.stepDown()  // 默认60秒内不参与选举

// 指定降级参数
rs.stepDown(120, 30)  // 120秒内不参与选举, 30秒等待新Primary

// 修改Secondary优先级触发切换
cfg = rs.conf()
cfg.members[1].priority = 5  // 提升Secondary优先级
rs.reconfig(cfg)
```

**阿里云API触发切换**:

```bash
# 阿里云HA切换 (高可用切换)
aliyun dds SwitchDBInstanceHA \
  --DBInstanceId "{{user.instance_id}}" \
  --HATarget "Primary"  # 目标: 切换Primary节点

# 注意: 需要实例状态为Normal
# 切换期间会有短暂写中断 (< 30秒)
```

### 2.3 Secondary Read Preference Configuration

| Read Preference Mode | Description | Use Case | Consistency Level |
|---------------------|-------------|----------|-------------------|
| **primary** (default) | 仅从Primary读取 | 强一致性要求业务 | 强一致 |
| **primaryPreferred** | 优先Primary, 失败时读Secondary | 允许短暂不一致, 优先一致性 | 最终一致 (fallback) |
| **secondary** | 仅从Secondary读取 | 读密集业务, 降低Primary压力 | 最终一致 |
| **secondaryPreferred** | 优先Secondary, 失败时读Primary | 读分流, 允许Primary承担读 | 最终一致 (fallback) |
| **nearest** | 从网络延迟最低的节点读取 | 多地域部署, 优化延迟 | 最终一致 |

**连接字符串配置示例**:

```bash
# Java/Node.js连接字符串
mongodb://user:password@primary:27017,secondary1:27017,secondary2:27017/database?readPreference=secondaryPreferred

# Python (PyMongo)
client = MongoClient(
    "mongodb://primary:27017,secondary1:27017,secondary2:27017",
    readPreference='secondaryPreferred'
)

# Go (mongo-driver)
uri := "mongodb://primary:27017,secondary1:27017,secondary2:27017/?readPreference=secondaryPreferred"
client, _ := mongo.Connect(clientOptions.ApplyURI(uri))
```

### 2.4 Write Concern Levels

| Write Concern | Description | Acknowledgment | Performance | Durability |
|--------------|-------------|----------------|-------------|------------|
| **w: 1** | 仅Primary确认 | Primary写入内存 | High | Low (Primary故障可能丢失) |
| **w: majority** | 多数节点确认 | >50%节点写入内存 | Medium | High (多数节点都有数据) |
| **w: all** | 所有节点确认 | 所有数据节点写入内存 | Low | Maximum (所有节点都有) |
| **w: "CustomTag"** | 指定标签节点确认 | 标记节点写入 | Variable | Custom |
| **w: N** | 指定N个节点确认 | N个Secondary确认 | Medium-High | Medium |

**写入示例**:

```javascript
// 默认 w:1 (仅Primary确认)
db.collection.insertOne({name: "test"})  // 快但风险高

// w:majority (推荐生产配置)
db.collection.insertOne(
  {name: "test"},
  {writeConcern: {w: "majority", wtimeout: 5000}}
)

// w:2 (Primary + 1个Secondary)
db.collection.insertOne(
  {name: "test"},
  {writeConcern: {w: 2, wtimeout: 3000}}
)

// w:all (所有数据节点 - 不包括Arbiter)
db.collection.insertOne(
  {name: "test"},
  {writeConcern: {w: "all", wtimeout: 10000}}
)
```

---

## 3. Election Mechanism

### 3.1 Election Triggers

| Trigger Type | Condition | Detection Time | Action Required |
|--------------|-----------|----------------|-----------------|
| **Primary Failure** | Primary节点进程崩溃/硬件故障 | 10-30秒 | 自动选举 |
| **Network Partition** | Primary与多数Secondary网络隔离 | 10-30秒 | 自动选举 (可能Split Brain) |
| **Primary Step-down** | 人为触发rs.stepDown() | 立即 | 自动选举 |
| **Priority Change** | Secondary优先级调整高于Primary | 配置生效后 | 触发重选举 |
| **Maintenance Window** | 阿里云维护/升级Primary | 维护期间 | 自动临时切换 |

### 3.2 Election Timeout Configuration

| Parameter | Default | Recommended Range | Impact |
|-----------|---------|-------------------|--------|
| **electionTimeoutMillis** | 10000ms (10s) | 10000-30000ms | 选举等待时间, 过短易误判, 过长延迟恢复 |
| **heartbeatIntervalMillis** | 2000ms (2s) | 1000-5000ms | 心跳频率, 影响故障检测速度 |
| **heartbeatTimeoutMillis** | 10000ms | 10000-20000ms | 心跳超时判定阈值 |

**阿里云参数调整**:

```bash
# 查询当前参数配置
aliyun dds DescribeParameters \
  --DBInstanceId "{{user.instance_id}}""

# 修改选举超时参数 (需重启)
aliyun dds ModifyParameter \
  --DBInstanceId "{{user.instance_id}}" \
  --Parameters "[{\"Key\":\"electionTimeoutMillis\",\"Value\":\"15000\"}]"

# 注意: 参数修改后需重启实例生效
# 建议在维护窗口执行
```

### 3.3 Priority-based Election Customization

| Priority Value | Election Weight | Use Case | Recommendation |
|----------------|-----------------|----------|----------------|
| **0** | 不参与选举, 永不成为Primary | 永久Secondary, 专用读节点 | 读密集分流场景 |
| **1** (default) | 标准权重 | 所有节点平等参与选举 | 默认配置 |
| **2-5** | 较高权重 | 希望优先成为Primary的节点 | 配置优先Primary |
| **6-10** | 高权重 | 指定Primary节点 | 明确Primary身份 |
| **>100** | 极高权重, 几乎必然当选 | 强指定Primary | 成本优化 + 高可用 |

**优先级配置示例**:

```javascript
// 查看当前配置
rs.conf()

// 修改优先级
cfg = rs.conf()
cfg.members[0].priority = 10  // Primary优先级高
cfg.members[1].priority = 5   // Secondary中等优先级
cfg.members[2].priority = 0   // 某Secondary永不当选
rs.reconfig(cfg)

// 阿里云创建时指定优先级 (通过NodeInfo)
{
  "NodeClass": "dds.mongo.mid",
  "NodeType": "Primary",
  "Priority": 10
}
```

### 3.4 Arbiters for Vote-only Nodes

#### Arbiter Cost vs Reliability Trade-offs

| Configuration | Data Nodes | Arbiters | Monthly Cost | Failure Tolerance | Vote Quorum |
|---------------|------------|----------|--------------|-------------------|-------------|
| **3-node (Classic)** | 3 | 0 | 3x node cost | 1 node failure | 2/3 = 67% |
| **3-node (Arbiter)** | 2 | 1 | 2x node cost + arbiter | 1 node failure | 2/3 = 67% |
| **5-node (Classic)** | 5 | 0 | 5x node cost | 2 node failures | 3/5 = 60% |
| **5-node (Arbiter)** | 4 | 1 | 4x node cost + arbiter | 1 node failure (safe) | 3/5 = 60% |

**Arbiter最佳实践**:

| Scenario | Arbiter Count | Data Nodes | Total Nodes | Recommendation |
|----------|---------------|------------|-------------|----------------|
| **成本优化生产** | 1 | 2 | 3 | 2+1配置, 成本降33%, 可容忍1节点故障 |
| **高可用生产** | 0 | 3 | 3 | 3节点纯数据, 推荐 |
| **跨地域部署** | 1 | 4 | 5 | 4+1配置, 跨2地域, 地域故障可恢复 |
| **关键业务** | 0 | 5 | 5 | 5节点纯数据, 可容忍2节点故障 |

---

## 4. Oplog Management

### 4.1 Oplog Size Configuration

| Instance Class | Recommended Oplog Size | Oplog Location | Size Calculation |
|----------------|------------------------|----------------|------------------|
| **Small (<4GB)** | 1GB | `local.oplog.rs` | 数据量的5-10% |
| **Medium (4-16GB)** | 2-5GB | `local.oplog.rs` | 数据量的5-10% |
| **Large (>16GB)** | 5-20GB | `local.oplog.rs` | 数据量的5-10%或固定大小 |
| **高写入场景** | 更大配置 | 固定集合 | 写入速率 × 保留窗口 |

**Oplog大小配置**:

```bash
# 阿里云查询当前Oplog配置
aliyun dds DescribeParameters \
  --DBInstanceId "{{user.instance_id}}" \
  --output cols=ParameterName,ParameterValue rows=RunningParameters.Parameter[?ParameterName=='oplogSize'].{ParameterName,ParameterValue}

# Oplog大小参数 (MB单位)
# oplogSize: 1024 (1GB)
# oplogSize: 2048 (2GB)

# 修改Oplog大小 (需重启)
aliyun dds ModifyParameter \
  --DBInstanceId "{{user.instance_id}}" \
  --Parameters "[{\"Key\":\"oplogSize\",\"Value\":\"2048\"}]"
```

### 4.2 Oplog Window Monitoring

| Metric | Key | Description | Threshold | Alert Level |
|--------|-----|-------------|-----------|-------------|
| **Oplog Window Hours** | `MongoDB_OplogWindow` | Oplog覆盖的时间范围 | < 24h → Warning | Warning |
| **Oplog Window Hours** | `MongoDB_OplogWindow` | Oplog覆盖的时间范围 | < 8h → Critical | Critical |
| **Oplog Size Used** | `MongoDB_OplogUsedSize` | 已使用的Oplog空间 | > 90% → Warning | Warning |

**CLI监控Oplog窗口**:

```bash
# 通过阿里云API查询Oplog窗口指标
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.instance_id}}" \
  --Key MongoDB_OplogWindow,MongoDB_OplogUsedSize \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# MongoDB Shell查询Oplog详情
mongo --host <primary> -u <user> -p <password> --authenticationDatabase admin

// 查看Oplog时间范围
db.oplog.rs.find().sort({ts: -1}).limit(1)  // 最新的Oplog条目
db.oplog.rs.find().sort({ts: 1}).limit(1)   // 最旧的Oplog条目

// 计算Oplog窗口
var latest = db.oplog.rs.find().sort({ts: -1}).limit(1).next().ts
var oldest = db.oplog.rs.find().sort({ts: 1}).limit(1).next().ts
var hours = (latest.t - oldest.t) / 3600
print("Oplog窗口: " + hours + "小时")

// 查看Oplog大小
db.oplog.rs.stats().size  // 当前大小
db.oplog.rs.stats().maxSize  // 最大大小
```

### 4.3 Oplog Rollover Prevention

| Prevention Strategy | Method | Impact | Use Case |
|---------------------|--------|--------|----------|
| **增大Oplog大小** | `oplogSize`参数调整 | 减少滚动频率 | 写入量大场景 |
| **降低写入速率** | 批量写入代替单条写入 | 减少Oplog生成 | 业务优化 |
| **加速Secondary同步** | 提升Secondary规格 | 快速消费Oplog | 同步延迟场景 |
| **增加数据节点** | 扩展副本集节点数 | 分担同步压力 | 高写入集群 |

**预防配置清单**:

```javascript
// MongoDB Shell检查Oplog健康度
// 1. 检查Oplog窗口
var windowHours = (db.oplog.rs.find().sort({ts: -1}).limit(1).next().ts.t - 
                   db.oplog.rs.find().sort({ts: 1}).limit(1).next().ts.t) / 3600
if (windowHours < 24) {
  print("⚠️ WARNING: Oplog窗口不足24小时, 需扩容")
}

// 2. 检查Oplog使用率
var stats = db.oplog.rs.stats()
var usagePercent = stats.size / stats.maxSize * 100
if (usagePercent > 90) {
  print("⚠️ WARNING: Oplog使用率超过90%, 需扩容")
}

// 3. 检查写入速率 (每秒Oplog条目)
var count1h = db.oplog.rs.find({ts: {$gt: new Timestamp(Math.floor(Date.now()/1000)-3600, 1)}}).count()
var ratePerSec = count1h / 3600
print("写入速率: " + ratePerSec + "条/秒")
```

### 4.4 Oplog Tailing for Change Streams

| Change Stream Feature | Oplog Dependency | Limitation | Recommendation |
|----------------------|------------------|------------|----------------|
| **实时变更监听** | 需Oplog完整覆盖变更时间 | Oplog滚动后无法追溯 | 确保Oplog窗口 > 业务需要 |
| **增量数据同步** | 基于Oplog位置(timestamp) | Oplog滚动断链 | 监控Oplog窗口, 及时扩容 |
| **CDC数据管道** | 从Oplog提取变更事件 | Oplog滚动丢失数据 | 使用Kafka等缓冲 + 大Oplog |

**Change Stream使用示例**:

```javascript
// MongoDB 3.6+ Change Stream
var changeStream = db.collection.watch()

// 监听所有变更
changeStream.on("change", function(change) {
  print("变更类型: " + change.operationType)
  print("文档ID: " + change.documentKey._id)
  print("完整文档: " + JSON.stringify(change.fullDocument))
})

// 指定起始位置 (恢复断点)
var resumeToken = <从上次中断位置获取>
var changeStream = db.collection.watch([], {resumeAfter: resumeToken})

// 注意: resumeToken必须在Oplog窗口内
// 否则报错: "resume point is no longer in the oplog"
```

---

## 5. Sync Delay Monitoring

### 5.1 Replication Lag Metrics

| Metric | Key | Description | Threshold | Severity |
|--------|-----|-------------|-----------|----------|
| **Replication Lag** | `MongoDB_ReplicationLag` | Secondary落后Primary的时间 | < 10s → Normal | Info |
| **Replication Lag** | `MongoDB_ReplicationLag` | Secondary落后Primary的时间 | > 10s → Warning | Warning |
| **Replication Lag** | `MongoDB_ReplicationLag` | Secondary落后Primary的时间 | > 60s → Critical | Critical |
| **Oplog Apply Rate** | `MongoDB_OplogApplyRate` | Secondary应用Oplog速率 | 低速率 → 检查 | Warning |
| **Initial Sync Progress** | `MongoDB_InitialSyncProgress` | 新节点初始同步进度 | 监控完成度 | Info |

**CLI监控复制延迟**:

```bash
# 阿里云API查询复制延迟
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.instance_id}}" \
  --Key MongoDB_ReplicationLag,MongoDB_OplogApplyRate \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# MongoDB Shell实时查询
mongo --host <secondary> -u <user> -p <password> --authenticationDatabase admin

// 查看Secondary延迟
rs.status().members.forEach(function(m) {
  if (m.state === 2) {  // Secondary
    print("节点: " + m.name)
    print("延迟: " + m.replicationLag + "秒")
    print("Optime: " + m.optime)
  }
})
```

### 5.2 Secondary Catch-up Strategies

| Strategy | Method | Impact | Execution Time |
|----------|--------|--------|----------------|
| **提升Secondary规格** | 升级Secondary CPU/内存 | 加速Oplog应用 | 配置变更生效 |
| **调整buildIndexInBackground** | 设为true减少索引阻塞 | 降低同步阻塞 | 参数调整立即生效 |
| **暂停写入** | 临时停止Primary写入 | 让Secondary追赶 | 业务影响大 |
| **重建Secondary** | 删除并重新添加节点 | 强制全量同步 | 数小时 (视数据量) |

**同步优化命令**:

```javascript
// MongoDB Shell优化Secondary同步

// 1. 检查Secondary状态
rs.status().members.forEach(function(m) {
  printjson({
    name: m.name,
    state: m.stateStr,
    replicationLag: m.replicationLag,
    syncingTo: m.syncingTo
  })
})

// 2. 查看索引构建影响
// buildIndexInBackground参数控制索引构建是否阻塞同步
db.adminCommand({getParameter: 1, buildIndexInBackground: 1})

// 3. 如果Secondary严重延迟, 考虑重建
// (阿里云建议通过API操作, 避免手动MongoDB Shell)

// 重建Secondary步骤:
// a. 删除延迟节点 (阿里云DeleteNode)
// b. 重新添加节点 (阿里云AddNode)
// c. 等待初始同步完成
```

### 5.3 Initial Sync Process

| Phase | Action | Duration | Key Metrics |
|-------|--------|----------|-------------|
| **Phase 1: Preparation** | 复制数据库结构(索引,集合) | 5-30分钟 | Progress: 0-10% |
| **Phase 2: Data Cloning** | 全量复制数据 | 数小时(视数据量) | Progress: 10-90% |
| **Phase 3: Oplog Catch-up** | 应用初始同步期间的Oplog | 视延迟量 | Progress: 90-99% |
| **Phase 4: Index Build** | 构建所有索引 | 视索引数量 | Progress: 99-100% |
| **Phase 5: Normal Sync** | 进入正常同步状态 | 完成 | State: Secondary |

**初始同步监控**:

```bash
# MongoDB Shell监控初始同步进度
mongo --host <syncing_node> -u <user> -p <password> --authenticationDatabase admin

// 查看初始同步状态
db.adminCommand({replSetGetStatus: 1}).members.forEach(function(m) {
  if (m.stateStr === "STARTUP2") {
    printjson({
      name: m.name,
      initialSyncStatus: m.initialSyncStatus,
      progress: m.initialSyncStatus ? m.initialSyncStatus.progress : "N/A"
    })
  }
})

// 阿里云查询节点状态
aliyun dds DescribeReplicaSetRole \
  --DBInstanceId "{{user.instance_id}}""
```

### 5.4 BuildIndexInBackground Impact

| Setting | Value | Impact on Sync | Use Case |
|---------|-------|----------------|----------|
| **buildIndexInBackground** | `false` (default) | 索引构建阻塞同步, 延迟增加 | 不关注同步延迟, 索引快速完成 |
| **buildIndexInBackground** | `true` | 索引后台构建, 不阻塞同步 | 关注同步延迟, 允许索引慢完成 |

**配置调整**:

```bash
# 阿里云修改参数
aliyun dds ModifyParameter \
  --DBInstanceId "{{user.instance_id}}" \
  --Parameters "[{\"Key\":\"buildIndexInBackground\",\"Value\":\"true\"}]"

# 注意: 
# - true: 索引构建不阻塞同步, 但索引构建更慢
# - false: 索引构建快, 但会阻塞同步
# 推荐: 高写入场景设为true, 降低同步延迟影响
```

---

## 6. Arbiter Usage

### 6.1 When to Use Arbiters

| Use Case | Arbiter Pattern | Benefit | Risk |
|----------|-----------------|---------|------|
| **成本优化** | 2+1 (2数据节点 + 1 Arbiter) | 成本降33% | 仅2个数据节点, 数据副本少 |
| **跨地域部署** | 4+1 (跨2地域) | 地域故障可恢复 | Arbiter需在第三方地域 |
| **开发/测试环境** | 1+1+1 | 成本最低 | 无真实高可用 |
| **读密集业务** | 2+1 + 读节点priority=0 | 降低成本 + 读分流 | Arbiter故障影响选举 |

### 6.2 Arbiter Limitations

| Limitation | Description | Impact | Mitigation |
|------------|-------------|--------|------------|
| **无数据存储** | Arbiter不存储数据副本 | 数据副本数减少 | 确保至少2个数据节点 |
| **选举依赖** | Arbiter故障影响投票 | 选举可能失败 | 监控Arbiter状态 |
| **网络依赖** | Arbiter需与所有节点通信 | 网络分区影响选举 | 确保网络稳定 |
| **监控数据缺失** | Arbiter无性能数据 | 监控盲区 | 监控Arbiter存活状态 |

### 6.3 Cost vs Reliability Trade-offs

```
成本与可靠性决策树
│
├─ 业务重要性?
│  ├─ 关键业务 (金融/支付)?
│  │  └─ 推荐: 5-node或7-node纯数据节点
│  │     ├─ 成本: 高
│  │     ├─ 可靠性: 最高 (可容忍2-3节点故障)
│  │     └─ 无Arbiter
│  │
│  ├─ 重要业务 (电商/社交)?
│  │  └─ 推荐: 3-node纯数据 或 5-node (含1 Arbiter)
│  │     ├─ 成本: 中等
│  │     ├─ 可靠性: 高 (可容忍1节点故障)
│  │     └─ 标准配置
│  │
│  └─ 一般业务 (内容/日志)?
│  │  └─ 推荐: 3-node含1 Arbiter (2+1)
│  │     ├─ 成本: 低
│  │     ├─ 可靠性: 中 (可容忍1节点故障)
│  │     └─ 成本优化配置
│  │
│  └─ 开发/测试?
│     └─ 推荐: 1-node Standalone 或 3-node含Arbiter
│        ├─ 成本: 最低
│        ├─ 可靠性: 无/低
│        └─ 仅用于非生产
```

---

## 7. Alibaba Cloud API Integration

### 7.1 Replica Set API Reference

| API | Purpose | Key Parameters | Response Fields |
|-----|---------|----------------|-----------------|
| **CreateReplicaSetInstance** | 创建副本集实例 | `ReplicationFactor`, `NodeInfo`, `EngineVersion` | `DBInstanceId`, `InstanceId` |
| **DescribeReplicaSetRole** | 查询副本集角色 | `DBInstanceId` | `PrimaryNode`, `SecondaryNodes`, `ArbiterNodes` |
| **ModifyDBInstanceSpec** | 修改实例规格(节点数) | `DBInstanceId`, `NodeClass`, `NodeCount` | `RequestId` |
| **SwitchDBInstanceHA** | HA切换Primary | `DBInstanceId`, `HATarget` | `RequestId` |
| **DescribeDBInstancePerformance** | 查询性能指标 | `DBInstanceId`, `Key`, `StartTime`, `EndTime` | `PerformanceKeys` |
| **DescribeParameters** | 查询参数配置 | `DBInstanceId` | `RunningParameters` |
| **ModifyParameter** | 修改参数 | `DBInstanceId`, `Parameters` | `RequestId` |
| **AddNode** | 增加副本集节点 | `DBInstanceId`, `NodeClass`, `NodeType` | `RequestId` |
| **DeleteNode** | 删除副本集节点 | `DBInstanceId`, `NodeId` | `RequestId` |

### 7.2 CreateReplicaSetInstance Example

```bash
# 创建3节点副本集实例
aliyun dds CreateReplicaSetInstance \
  --RegionId "{{user.region}}" \
  --Engine "MongoDB" \
  --EngineVersion "4.2" \
  --DBInstanceClass "dds.mongo.mid" \
  --DBInstanceStorage 20 \
  --ReplicationFactor 3 \
  --VPCId "{{user.vpc_id}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --SecurityIPList "192.168.0.0/16" \
  --AccountName "root" \
  --AccountPassword "{{user.password}}" \
  --ChargeType "PostPaid"

# 创建含Arbiter的副本集 (自定义节点配置)
aliyun dds CreateReplicaSetInstance \
  --RegionId "{{user.region}}" \
  --Engine "MongoDB" \
  --EngineVersion "4.2" \
  --DBInstanceClass "dds.mongo.mid" \
  --DBInstanceStorage 20 \
  --ReplicationFactor 3 \
  --NodeInfo "[{\"NodeClass\":\"dds.mongo.mid\",\"NodeType\":\"Primary\"},{\"NodeClass\":\"dds.mongo.mid\",\"NodeType\":\"Secondary\"},{\"NodeClass\":\"dds.mongo.small\",\"NodeType\":\"Arbiter\"}]" \
  --VPCId "{{user.vpc_id}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --ChargeType "PostPaid"
```

### 7.3 DescribeReplicaSetRole Example

```bash
# 查询副本集角色分布
aliyun dds DescribeReplicaSetRole \
  --DBInstanceId "{{user.instance_id}}""

# 输出解析:
# - PrimaryNode: 当前Primary节点信息
#   - NodeId: 节点ID
#   - NodeClass: 节点规格
#   - RegionId: 地域
#   - ZoneId: 可用区
#
# - SecondaryNodes: Secondary节点列表
#   - Array of NodeInfo
#
# - ArbiterNodes: Arbiter节点列表
#   - Array of NodeInfo (如存在)
#
# - ReplicaSetStatus: 副本集状态
#   - Normal: 正常
#   - Abnormal: 异常
```

### 7.4 ModifyDBInstanceSpec (Change Node Count)

```bash
# 增加节点数 (从3节点扩展到5节点)
aliyun dds ModifyDBInstanceSpec \
  --DBInstanceId "{{user.instance_id}}" \
  --NodeClass "dds.mongo.mid" \
  --NodeCount 5 \
  --OrderType "UPGRADE"

# 注意:
# - 增加节点会引起数据同步, 时间视数据量而定
# - 建议在维护窗口执行
# - NodeCount包括所有数据节点和Arbiter
```

---

## 8. Diagnostic Playbooks

### 8.1 Scenario: "主从切换频繁" (Frequent Primary Switches)

**症状**: 副本集Primary频繁切换, 业务写操作反复中断

**诊断流程**:

```bash
# Step 1: 查询HA切换历史
aliyun dds DescribeDBInstanceHAConfig \
  --DBInstanceId "{{user.instance_id}}""

# Step 2: 查询最近30分钟的节点状态变化
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.instance_id}}" \
  --Key MongoDB_NodeStatus,MongoDB_ElectionCount \
  --StartTime "$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 3: 查询网络延迟指标
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.instance_id}}" \
  --Key MongoDB_NetworkLatency \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 4: 查询错误日志
aliyun dds DescribeErrorLogs \
  --DBInstanceId "{{user.instance_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --DBType "normal"
```

**根因分析**:

| Pattern | Likely Root Cause | Evidence | Solution |
|---------|-------------------|----------|----------|
| **网络延迟波动** | 节点间网络不稳定 | `MongoDB_NetworkLatency`频繁高值 | 检查VPC/跨可用区网络, 升级网络 |
| **节点负载不均** | Primary压力过大 | Primary CPU/IOPS高, Secondary正常 | 读写分离, 升级Primary规格 |
| **参数配置不当** | electionTimeout过短 | 参数值 < 10s | 调整electionTimeoutMillis到15s |
| **硬件故障** | Primary节点硬件问题 | 错误日志有硬件报错 | 联系阿里云更换节点 |
| **优先级配置** | 多节点优先级相近 | Priority配置竞争 | 固定Primary优先级最高 |

**即时行动**:

```bash
# 1. 固定Primary优先级 (MongoDB Shell)
mongo --host <primary> -u root -p <password> --authenticationDatabase admin
cfg = rs.conf()
cfg.members[0].priority = 10  // 提升Primary优先级
cfg.members[1].priority = 1
cfg.members[2].priority = 1
rs.reconfig(cfg)

# 2. 调整选举超时参数
aliyun dds ModifyParameter \
  --DBInstanceId "{{user.instance_id}}" \
  --Parameters "[{\"Key\":\"electionTimeoutMillis\",\"Value\":\"15000\"}]"

# 3. 升级Primary规格 (如压力过大)
aliyun dds ModifyDBInstanceSpec \
  --DBInstanceId "{{user.instance_id}}" \
  --NodeClass "dds.mongo.large" \
  --OrderType "UPGRADE"
```

---

### 8.2 Scenario: "复制延迟高" (High Replication Lag)

**症状**: Secondary复制延迟 > 60秒, 读Secondary返回旧数据

**诊断流程**:

```bash
# Step 1: 查询复制延迟指标
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.instance_id}}" \
  --Key MongoDB_ReplicationLag,MongoDB_OplogApplyRate \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 2: 查询Primary写入压力
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.instance_id}}" \
  --Key MongoDB_TPS,MongoDB_IOPS,MongoDB_CPUUsage \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 3: 查询Secondary规格对比
aliyun dds DescribeReplicaSetRole \
  --DBInstanceId "{{user.instance_id}}""

# Step 4: 查询Oplog窗口
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.instance_id}}" \
  --Key MongoDB_OplogWindow \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

**根因分析**:

| Pattern | Likely Root Cause | Evidence | Solution |
|---------|-------------------|----------|----------|
| **Primary写入高** | Primary TPS过高, Secondary跟不上 | `MongoDB_TPS`持续高, `MongoDB_ReplicationLag`同步上升 | 降低写入速率, 或升级Secondary |
| **Secondary规格低** | Secondary规格低于Primary | `NodeClass` Secondary < Primary | 升级Secondary规格 |
| **索引构建阻塞** | buildIndexInBackground=false | 新增索引期间延迟突增 | 设buildIndexInBackground=true |
| **Oplog窗口小** | Oplog滚动, Secondary追不上 | `MongoDB_OplogWindow` < 写入时间差 | 扩大Oplog大小 |
| **网络延迟** | Secondary网络延迟高 | `MongoDB_NetworkLatency`高 | 检查网络, 同可用区部署 |

**即时行动**:

```bash
# 1. 升级Secondary规格 (阿里云API)
# 先查询Secondary节点ID
aliyun dds DescribeReplicaSetRole \
  --DBInstanceId "{{user.instance_id}}" \
  --output cols=NodeId,NodeClass rows=SecondaryNodes[].{NodeId,NodeClass}

# 升级Secondary规格
aliyun dds ModifyDBInstanceSpec \
  --DBInstanceId "{{user.instance_id}}" \
  --NodeClass "dds.mongo.large" \
  --NodeCount <保持原节点数> \
  --OrderType "UPGRADE"

# 2. 调整索引构建参数
aliyun dds ModifyParameter \
  --DBInstanceId "{{user.instance_id}}" \
  --Parameters "[{\"Key\":\"buildIndexInBackground\",\"Value\":\"true\"}]"

# 3. 扩大Oplog大小
aliyun dds ModifyParameter \
  --DBInstanceId "{{user.instance_id}}" \
  --Parameters "[{\"Key\":\"oplogSize\",\"Value\":\"5120\"}]"
```

---

### 8.3 Scenario: "Oplog空间不足" (Oplog Space Exhaustion)

**症状**: Oplog窗口 < 8小时, Change Stream断链, 新节点无法初始同步

**诊断流程**:

```bash
# Step 1: 查询Oplog窗口和使用率
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.instance_id}}" \
  --Key MongoDB_OplogWindow,MongoDB_OplogUsedSize \
  --StartTime "$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 2: 查询写入速率
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.instance_id}}" \
  --Key MongoDB_TPS,MongoDB_OplogGenerationRate \
  --StartTime "$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 3: 查询当前Oplog参数
aliyun dds DescribeParameters \
  --DBInstanceId "{{user.instance_id}}" \
  --output cols=ParameterName,ParameterValue rows=RunningParameters.Parameter[?ParameterName=='oplogSize'].{ParameterName,ParameterValue}
```

**根因分析**:

| Pattern | Likely Root Cause | Evidence | Solution |
|---------|-------------------|----------|----------|
| **写入速率高** | 写入量持续高, Oplog快速滚动 | `MongoDB_TPS` > 5000, Oplog窗口持续缩小 | 扩大Oplog到10GB+ |
| **OplogSize设置小** | oplogSize参数过小 | oplogSize < 2GB | 调整oplogSize参数 |
| **数据增长快** | 数据量快速增长 | Storage使用率持续上升 | 扩容存储 + 扩大Oplog |
| **Secondary延迟** | Secondary跟不上导致Oplog堆积 | 复制延迟高, Oplog窗口小 | 先解决复制延迟, 再扩Oplog |

**即时行动**:

```bash
# 1. 扩大Oplog大小 (需重启)
aliyun dds ModifyParameter \
  --DBInstanceId "{{user.instance_id}}" \
  --Parameters "[{\"Key\":\"oplogSize\",\"Value\":\"10240\"}]"  # 10GB

# 2. 如果写入速率确实高, 考虑:
# a. 优化写入模式 (批量写入代替单条)
# b. 升级实例规格
# c. 增加Secondary节点分担压力

# 3. MongoDB Shell验证Oplog健康
mongo --host <primary> -u root -p <password> --authenticationDatabase admin
var latest = db.oplog.rs.find().sort({ts: -1}).limit(1).next().ts
var oldest = db.oplog.rs.find().sort({ts: 1}).limit(1).next().ts
var hours = (latest.t - oldest.t) / 3600
print("Oplog窗口: " + hours + "小时")
// 应 > 24小时
```

---

### 8.4 Scenario: "选举超时" (Election Timeout)

**症状**: Primary故障后长时间无新Primary, 副本集不可写

**诊断流程**:

```bash
# Step 1: 查询副本集角色
aliyun dds DescribeReplicaSetRole \
  --DBInstanceId "{{user.instance_id}}""

# Step 2: 查询节点状态
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.instance_id}}" \
  --Key MongoDB_NodeStatus,MongoDB_ElectionCount \
  --StartTime "$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 3: 查询选举超时参数
aliyun dds DescribeParameters \
  --DBInstanceId "{{user.instance_id}}" \
  --output cols=ParameterName,ParameterValue rows=RunningParameters.Parameter[?ParameterName=='electionTimeoutMillis' || ParameterName=='heartbeatTimeoutMillis']

# Step 4: 查询网络延迟
aliyun dds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.instance_id}}" \
  --Key MongoDB_NetworkLatency \
  --StartTime "$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

**根因分析**:

| Pattern | Likely Root Cause | Evidence | Solution |
|---------|-------------------|----------|----------|
| **网络分区** | 多节点网络隔离, 无法投票 | 网络延迟极高或节点不可达 | 检查VPC网络, 恢复网络 |
| **节点数量不足** | 投票节点 < 3, 无法达到多数 | 节点数 = 2 (含Arbiter) 或节点故障 | 确保至少3节点健康 |
| **Arbiter故障** | Arbiter不可达, 影响投票 | Arbiter节点状态异常 | 检查Arbiter存活, 或添加新Arbiter |
| **参数过大** | electionTimeoutMillis过大 | electionTimeoutMillis > 30s | 调整到10-15s |
| **优先级配置冲突** | 所有Secondary priority=0 | rs.conf()显示priority全为0 | 至少一个Secondary priority>0 |

**即时行动**:

```bash
# 1. 检查并修复网络问题 (阿里云工单)

# 2. 调整选举超时参数 (如过大)
aliyun dds ModifyParameter \
  --DBInstanceId "{{user.instance_id}}" \
  --Parameters "[{\"Key\":\"electionTimeoutMillis\",\"Value\":\"10000\"}]"

# 3. 确保至少一个Secondary可选举 (MongoDB Shell)
mongo --host <healthy_secondary> -u root -p <password> --authenticationDatabase admin
cfg = rs.conf()
cfg.members[1].priority = 1  // 至少一个Secondary priority > 0
rs.reconfig(cfg)

# 4. 如Arbiter故障, 添加新Arbiter
aliyun dds AddNode \
  --DBInstanceId "{{user.instance_id}}" \
  --NodeClass "dds.mongo.small" \
  --NodeType "Arbiter"
```

---

## 9. Monitoring Metrics

### 9.1 Key Monitoring Metrics

| Metric | Key | Unit | Threshold | Alert Level | Monitoring Window |
|--------|-----|------|-----------|-------------|-------------------|
| **Replication Lag** | `MongoDB_ReplicationLag` | seconds | > 10s | Warning | 5 min |
| **Replication Lag** | `MongoDB_ReplicationLag` | seconds | > 60s | Critical | 5 min |
| **Oplog Window** | `MongoDB_OplogWindow` | hours | < 24h | Warning | 1 hour |
| **Oplog Window** | `MongoDB_OplogWindow` | hours | < 8h | Critical | 1 hour |
| **Election Count** | `MongoDB_ElectionCount` | count | > 3/hour | Warning | 1 hour |
| **Election Count** | `MongoDB_ElectionCount` | count | > 5/hour | Critical | 1 hour |
| **Node Status** | `MongoDB_NodeStatus` | state | Non-Normal | Critical | 1 min |
| **CPU Usage** | `MongoDB_CPUUsage` | percent | > 80% | Warning | 5 min |
| **CPU Usage** | `MongoDB_CPUUsage` | percent | > 95% | Critical | 5 min |
| **Memory Usage** | `MongoDB_MemoryUsage` | percent | > 85% | Warning | 5 min |
| **IOPS** | `MongoDB_IOPS` | count/s | > 80% of limit | Warning | 5 min |
| **Network Latency** | `MongoDB_NetworkLatency` | ms | > 10ms | Warning | 5 min |
| **Network Latency** | `MongoDB_NetworkLatency` | ms | > 50ms | Critical | 5 min |
| **Connection Count** | `MongoDB_Connections` | count | > 80% of max | Warning | 5 min |

### 9.2 CloudMonitor Integration

```bash
# 通过CloudMonitor (CMS)查询MongoDB指标
aliyun cms DescribeMetricList \
  --Namespace acs_mongodb_dashboard \
  --MetricName MongoDB_ReplicationLag \
  --Dimensions "[{\"instanceId\":\"{{user.instance_id}}\"}]" \
  --Period 60 \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# 可用Namespace: acs_mongodb_dashboard
# 主要MetricName:
# - MongoDB_ReplicationLag (复制延迟)
# - MongoDB_OplogWindow (Oplog窗口)
# - MongoDB_ElectionCount (选举次数)
# - MongoDB_CPUUsage (CPU使用率)
# - MongoDB_MemoryUsage (内存使用率)
# - MongoDB_IOPS (IOPS)
# - MongoDB_Connections (连接数)
# - MongoDB_NetworkLatency (网络延迟)
```

### 9.3 Alert Rule Configuration

```bash
# 创建复制延迟告警规则
aliyun cms CreateAlarm \
  --Namespace acs_mongodb_dashboard \
  --MetricName MongoDB_ReplicationLag \
  --Dimensions "[{\"instanceId\":\"{{user.instance_id}}\"}]" \
  --Period 60 \
  --Statistics "Maximum" \
  --ComparisonOperator "GreaterThanThreshold" \
  --Threshold 10 \
  --EvaluationCount 3 \
  --AlarmName "MongoDB复制延迟告警" \
  --AlarmDescription "复制延迟超过10秒" \
  --NotifyType "1,2,3" \
  --ContactGroups "{{user.contact_group}}"

# 创建选举次数告警规则
aliyun cms CreateAlarm \
  --Namespace acs_mongodb_dashboard \
  --MetricName MongoDB_ElectionCount \
  --Dimensions "[{\"instanceId\":\"{{user.instance_id}}\"}]" \
  --Period 3600 \
  --Statistics "Sum" \
  --ComparisonOperator "GreaterThanThreshold" \
  --Threshold 3 \
  --EvaluationCount 1 \
  --AlarmName "MongoDB选举频繁告警" \
  --AlarmDescription "1小时内选举超过3次" \
  --NotifyType "1,2,3"
```

---

## 10. Best Practices Summary

### 10.1 Replica Set Configuration Best Practices

| Practice | Recommendation | Reason |
|----------|----------------|--------|
| **节点数量** | 生产环境至少3节点 | 确保高可用和自动故障恢复 |
| **节点规格** | Secondary规格 ≥ Primary | 避免同步延迟 |
| **优先级配置** | Primary priority最高且固定 | 防止频繁选举 |
| **选举超时** | electionTimeoutMillis 10-15s | 平衡检测速度和误判 |
| **Oplog大小** | 数据量的5-10%或固定5GB+ | 确保足够窗口 |
| **buildIndexInBackground** | true (高写入场景) | 避免索引阻塞同步 |
| **读偏好** | 根据一致性需求选择 | 读分流 vs 强一致 |
| **写关注** | w:majority (生产) | 确保多数节点确认 |

### 10.2 Monitoring Best Practices

| Practice | Recommendation | Tools |
|----------|----------------|-------|
| **复制延迟监控** | 5分钟检查, >10s告警 | CloudMonitor + MongoDB Shell |
| **Oplog窗口监控** | 1小时检查, <24h告警 | DescribeDBInstancePerformance |
| **选举次数监控** | 1小时汇总, >3次告警 | CloudMonitor ElectionCount |
| **节点状态监控** | 1分钟检查, 异常告警 | DescribeReplicaSetRole |
| **网络延迟监控** | 5分钟检查, >10ms告警 | MongoDB_NetworkLatency |

### 10.3 Operational Checklist

| Check Item | Frequency | Method | Expected |
|------------|-----------|--------|----------|
| **副本集角色分布** | Daily | DescribeReplicaSetRole | 1 Primary + N Secondary |
| **复制延迟** | Every 5 min | DescribeDBInstancePerformance | < 10s |
| **Oplog窗口** | Daily | DescribeDBInstancePerformance | > 24h |
| **节点健康状态** | Every 1 min | DescribeReplicaSetRole | All Normal |
| **Primary稳定性** | Daily | ElectionCount trend | < 1 election/day |
| **备份验证** | Weekly | Restore test | 成功恢复 |

---

## 11. References

- [Alibaba Cloud MongoDB Documentation](https://help.aliyun.com/document_detail/26553.html)
- [MongoDB Replica Set Documentation](https://docs.mongodb.com/manual/replication/)
- [MongoDB Oplog Management](https://docs.mongodb.com/manual/core/replica-set-oplog/)
- [MongoDB Read Preference](https://docs.mongodb.com/manual/core/read-preference/)
- [MongoDB Write Concern](https://docs.mongodb.com/manual/core/write-concern/)
- [MongoDB Change Streams](https://docs.mongodb.com/manual/changeStreams/)