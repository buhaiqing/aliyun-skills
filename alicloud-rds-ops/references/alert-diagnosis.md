# Alert Diagnosis & Root Cause Analysis — Alibaba Cloud RDS

> This reference provides **intelligent diagnosis workflows**, **multi-dimensional correlation analysis**, **engine-specific diagnostic trees**, and **automated root-cause localization** for RDS alerts and performance issues.

---

## 1. Alert-to-Root-Cause Correlation Matrix

When an alert fires, use this matrix to determine the most likely root causes and the diagnostic order.

### 1.1 CPU Alerts

| Alert Condition | Primary Symptoms | Likely Root Causes | Diagnostic Order |
|-----------------|------------------|-------------------|------------------|
| CPU > 95% (Critical) | CPU 持续高 | 1. Slow queries causing lock contention<br>2. High concurrent connections<br>3. Full table scans (high IOPS + low buffer hit)<br>4. Large sorting / temp table operations<br>5. Replication lag (slave catching up) | 1. Check `ActiveSessions` vs `Sessions`<br>2. Check `DescribeSlowLogs` for top queries<br>3. Check `IOPS` and `InnoDBBufferRatio`<br>4. Check `DescribeErrorLogs` for lock wait timeout |
| CPU > 80% (Warning) | CPU 周期性或持续升高 | 1. Business traffic growth<br>2. Suboptimal query plans<br>3. Missing indexes<br>4. Scheduled jobs (backup, statistics collection) | 1. Compare with historical baseline<br>2. Check `DescribeSlowLogs` for new queries<br>3. Check backup schedule timing<br>4. Review `DescribeSQLLogRecords` for pattern |
| CPU spike (sudden) | CPU 瞬间飙升后恢复 | 1. Single heavy query (DDL, large aggregation)<br>2. Connection burst<br>3. Cache invalidation storm | 1. Check `DescribeSQLLogRecords` for high-latency SQL<br>2. Check connection count trend<br>3. Check `DescribeBinlogFiles` for DDL events |

### 1.2 Memory Alerts

| Alert Condition | Primary Symptoms | Likely Root Causes | Diagnostic Order |
|-----------------|------------------|-------------------|------------------|
| Memory > 95% | Memory 持续高 | 1. Buffer pool too large for workload<br>2. High concurrent connections (per-connection memory)<br>3. Large temp tables / sorting in memory<br>4. Memory leak (rare in managed RDS) | 1. Check `max_connections` vs actual connections<br>2. Check `DescribeSlowLogs` for `Using temporary`, `Using filesort`<br>3. Check `innodb_buffer_pool_size` ratio to instance memory<br>4. Check `DescribeParameters` for memory-related settings |
| Memory > 80% | Memory 缓慢增长 | 1. Gradual connection accumulation<br>2. Growing dataset fitting into buffer<br>3. Long-running transactions holding memory | 1. Check connection trend over time<br>2. Check `DataSize` growth from `DescribeResourceUsage`<br>3. Check `DescribeSQLLogRecords` for long transactions |

### 1.3 Connection Alerts

| Alert Condition | Primary Symptoms | Likely Root Causes | Diagnostic Order |
|-----------------|------------------|-------------------|------------------|
| Connections > 95% of max | Connection refused / timeout | 1. Connection leak (app not closing connections)<br>2. Slow queries holding connections<br>3. Connection pool misconfiguration<br>4. DDoS / brute force attack | 1. Check `ActiveSessions` vs `Sessions` (idle ratio)<br>2. Check `DescribeSlowLogs` for long-running queries<br>3. Check `DescribeSQLLogRecords` for repeated connection attempts from same IP<br>4. Check `SecurityIPList` for unauthorized IPs |
| Connections > 80% | Connection count high but stable | 1. Business growth<br>2. Connection pool too large<br>3. Read/write splitting not configured | 1. Compare with historical baseline<br>2. Check if read-only instances exist (`DescribeReadDBInstances`)<br>3. Recommend connection pooling or proxy |

### 1.4 Disk Alerts

| Alert Condition | Primary Symptoms | Likely Root Causes | Diagnostic Order |
|-----------------|------------------|-------------------|------------------|
| Disk > 90% | Disk full risk | 1. Data growth<br>2. Log accumulation (binlog / slow log / error log)<br>3. Large temp files<br>4. Backup retention too long | 1. Check `DataSize` vs `LogSize` from `DescribeResourceUsage`<br>2. Check `DescribeBinlogFiles` for retention<br>3. Check `DescribeSlowLogs` volume<br>4. Check `DescribeBackups` retention policy |
| Disk > 80% | Disk usage growing | 1. Normal business growth<br>2. Unoptimized tables (fragmentation)<br>3. Replication lag causing binlog accumulation | 1. Check disk growth rate over 7 days<br>2. Check `DescribeDBInstanceHAConfig` for replication lag<br>3. Check `DescribeBinlogFiles` size and count |

### 1.5 IOPS Alerts

| Alert Condition | Primary Symptoms | Likely Root Causes | Diagnostic Order |
|-----------------|------------------|-------------------|------------------|
| IOPS > 80% of max | IO wait high | 1. Buffer pool miss (data not in memory)<br>2. Full table scans<br>3. High write volume (bulk insert/update)<br>4. Checkpoint activity | 1. Check `InnoDBBufferRatio` (should be > 95%)<br>2. Check `DescribeSlowLogs` for `SELECT *` without index<br>3. Check `DescribeSQLLogRecords` for batch operations<br>4. Check `innodb_io_capacity` setting |

### 1.6 Replication / HA Alerts

| Alert Condition | Primary Symptoms | Likely Root Causes | Diagnostic Order |
|-----------------|------------------|-------------------|------------------|
| Async sync mode | HA risk | 1. Sync mode degraded to Async<br>2. Network latency between AZs<br>3. Slave IO/SQL thread lag | 1. Check `DescribeDBInstanceHAConfig` for `SyncMode`<br>2. Check `DescribeDBInstanceAttribute` for node status<br>3. Check `DescribeErrorLogs` for replication errors |
| Replication lag | Read inconsistency | 1. Slave under-provisioned<br>2. Large transaction on master<br>3. Network bottleneck | 1. Check read-only instance class vs master<br>2. Check `DescribeBinlogFiles` for large transactions<br>3. Check `DescribeDBInstancePerformance` for slave IO/SQL thread metrics |

---

## 2. Multi-Dimensional Correlation Analysis

When multiple alerts fire simultaneously, use correlation analysis to identify the **primary root cause** vs **secondary effects**.

### 2.1 Correlation Matrix

| Symptom Combo | Primary Root Cause | Secondary Effects | Confirmation |
|---------------|-------------------|-------------------|--------------|
| CPU↑ + Connections↑ + SlowQuery↑ | **Slow query causing connection pile-up** | CPU high (query execution), connections high (waiting clients) | Top slow query has high `MySQLTotalExecutionCounts` and `MySQLTotalExecutionTimes` |
| CPU↑ + IOPS↑ + BufferHit↓ | **Full table scan / buffer pool too small** | CPU high (data processing), IOPS high (disk reads) | Slow queries show `Using where` without index; `InnoDBBufferRatio` < 90% |
| CPU↑ + Memory↑ + TempTable↑ | **Large in-memory sort / aggregation** | CPU high (sorting), memory high (temp tables) | Slow queries show `Using temporary`, `Using filesort` |
| Connections↑ + CPU↓ | **Connection leak / idle connections** | Connections high but CPU low (no active work) | `ActiveSessions` << `Sessions`; many idle connections |
| Disk↑ + LogSize↑ + Binlog↑ | **Binlog accumulation / replication lag** | Disk high (log files), replication at risk | `DescribeBinlogFiles` shows large files; `DescribeDBInstanceHAConfig` shows lag |
| Disk↑ + DataSize↑ + Backup↓ | **Data growth + backup failure** | Disk high (data + failed backup accumulation) | `DescribeBackups` shows recent failures; `DataSize` growing fast |
| CPU↑ + ErrorLog↑ + LockWait↑ | **Lock contention / deadlock** | CPU high (spinning on locks), errors from lock wait timeout | `DescribeErrorLogs` shows `Lock wait timeout exceeded`; slow queries show `Locked` time |

### 2.2 Dimensional Analysis Decision Tree

```
收到多维度告警
│
├─ CPU 高?
│  ├─ 连接数同时高?
│  │  ├─ 慢查询多? → 根因: 慢查询导致连接堆积
│  │  │  └─ 行动: 分析慢查询, 建议加索引或优化SQL
│  │  └─ 慢查询不多? → 根因: 连接泄漏或连接池过大
│  │     └─ 行动: 检查应用连接池配置, 检查idle连接
│  ├─ IOPS 同时高?
│  │  ├─ Buffer命中率低? → 根因: 全表扫描或缓冲池不足
│  │  │  └─ 行动: 检查慢查询执行计划, 考虑扩容内存
│  │  └─ Buffer命中率正常? → 根因: 写入量突增
│  │     └─ 行动: 检查批量操作, 检查binlog生成速率
│  └─ 仅CPU高? → 根因: 复杂计算型查询或定时任务
│     └─ 行动: 检查SQL审计记录, 检查定时任务时间
│
├─ 连接数高?
│  ├─ CPU 同时高? → (已处理, 见上)
│  └─ CPU 正常? → 根因: 连接泄漏或连接风暴
│     └─ 行动: 检查idle连接比例, 检查连接来源IP
│
├─ 磁盘高?
│  ├─ LogSize 占比高?
│  │  ├─ Binlog 多? → 根因: 写入量大或复制延迟
│  │  │  └─ 行动: 检查复制延迟, 考虑清理binlog
│  │  └─ ErrorLog 多? → 根因: 大量错误产生日志
│  │     └─ 行动: 分析错误日志模式, 修复源头问题
│  └─ DataSize 占比高? → 根因: 数据增长或表膨胀
│     └─ 行动: 检查表碎片, 考虑归档或扩容
│
└─ 复制延迟?
   ├─ Master IOPS 高? → 根因: 大事务或写入峰值
   │  └─ 行动: 拆分大事务, 错峰写入
   └─ Slave 规格低? → 根因: 从库性能不足
      └─ 行动: 升级只读实例规格
```

---

## 3. Engine-Specific Diagnostic Trees

### 3.1 MySQL Diagnostic Tree

```
MySQL 故障诊断
│
├─ 性能问题
│  ├─ CPU 高
│  │  ├─ SHOW PROCESSLIST (via DescribeSQLLogRecords)
│  │  │  ├─ 大量 "Sending data" → 全表扫描或大数据量返回
│  │  │  ├─ 大量 "Waiting for table lock" → MyISAM 锁竞争 (应迁移到InnoDB)
│  │  │  ├─ 大量 "Waiting for row lock" → InnoDB 行锁竞争
│  │  │  └─ 大量 "Copying to tmp table" → 临时表过大
│  │  └─ 慢查询分析 (DescribeSlowLogs)
│  │     ├─ Rows_sent 大 → 返回数据量过大, 检查SELECT *
│  │     ├─ Rows_examined >> Rows_sent → 扫描行数远大于返回, 缺索引
│  │     └─ Lock_time 高 → 锁竞争严重
│  ├─ 连接问题
│  │  ├─ Too many connections → max_connections 不足或连接泄漏
│  │  ├─ Aborted_connects 高 → 网络问题或暴力破解
│  │  └─ Threads_connected 高但 Threads_running 低 → 连接泄漏
│  └─ IO 问题
│     ├─ Innodb_data_reads 高 → 缓冲池不足或全表扫描
│     ├─ Innodb_log_writes 高 → 事务提交过于频繁
│     └─ Innodb_dblwr_writes 高 → 双写缓冲压力 (SSD上可关闭)
│
├─ 复制问题
│  ├─ Slave_IO_Running: No
│  │  ├─ Last_IO_Error: 连接问题 → 检查网络/防火墙
│  │  └─ Last_IO_Error: binlog 不存在 → 主库binlog已清理
│  ├─ Slave_SQL_Running: No
│  │  ├─ Last_SQL_Error: 重复键 → 数据不一致, 需跳过或重建
│  │  └─ Last_SQL_Error: 表不存在 → DDL未同步或过滤规则问题
│  └─ Seconds_Behind_Master 高
│     ├─ Slave 规格低 → 升级只读实例
│     ├─ 大事务 → 拆分事务
│     └─ 并行复制未开启 → 开启 slave_parallel_workers
│
└─ 锁问题
   ├─ Lock wait timeout → 事务过长或锁竞争
   ├─ Deadlock found → 应用逻辑问题, 需重试机制
   └─ Metadata lock wait → DDL期间长事务阻塞
```

### 3.2 PostgreSQL Diagnostic Tree

```
PostgreSQL 故障诊断
│
├─ 性能问题
│  ├─ CPU 高
│  │  ├─ pg_stat_activity (via DescribeSQLLogRecords)
│  │  │  ├─ state = 'active', wait_event_type = 'Client' → 正常活跃查询
│  │  │  ├─ state = 'active', wait_event_type = 'IO' → IO瓶颈
│  │  │  └─ state = 'idle in transaction' → 事务未提交, 可能持有锁
│  │  └─ 慢查询分析
│  │     ├─ shared_blks_hit / shared_blks_read 比例低 → 缓冲池不足
│  │     ├─ temp_blks_written 高 → work_mem 不足, 写入临时文件
│  │     └─ calls 高但 mean_time 低 → 总调用次数过多
│  ├─ 连接问题
│  │  ├─ max_connections 接近上限 → 连接池配置或连接泄漏
│  │  └─ idle connections 多 → 应用未释放连接
│  └─ IO 问题
│     ├─ checkpoints_req / checkpoints_timed 比例高 → checkpoint过于频繁
│     ├─ buffers_backend 高 → 后台写压力大, shared_buffers可能不足
│     └─ blks_read 高但 blks_hit 低 → 缓冲池未命中
│
├─ VACUUM 问题
│  ├─ dead_tuples 高 → autovacuum 未跟上
│  ├─ table_bloat 高 → 需要手动 VACUUM FULL (注意锁表)
│  └─ xid_wraparound 风险 → 紧急 VACUUM, 防止数据库停止
│
├─ WAL 问题
│  ├─ WAL 文件堆积 → archive_command 失败或复制延迟
│  └─ replication_slot 滞后 → 从库未消费 WAL, 导致磁盘满
│
└─ 锁问题
   ├─ pg_locks 中 granted = false → 锁等待
   ├─ locktype = 'relation', mode = 'AccessExclusiveLock' → DDL阻塞
   └─ deadlock detected → 应用事务顺序不一致
```

### 3.3 SQL Server Diagnostic Tree

```
SQL Server 故障诊断
│
├─ 性能问题
│  ├─ CPU 高
│  │  ├─ sys.dm_exec_requests (via DescribeSQLLogRecords)
│  │  │  ├─ status = 'running', wait_type = 'SOS_SCHEDULER_YIELD' → CPU密集型查询
│  │  │  ├─ status = 'suspended', wait_type = 'PAGEIOLATCH_*' → IO等待
│  │  │  └─ status = 'suspended', wait_type = 'LCK_M_*' → 锁等待
│  │  └─ 慢查询分析
│  │     ├─ logical_reads 高 → 缺少索引或统计信息过期
│  │     ├─ physical_reads 高 → 内存不足, 数据未在缓冲池
│  │     └─ worker_time 高 → 复杂查询计划或类型转换
│  ├─ 内存问题
│  │  ├─ Buffer cache hit ratio < 95% → 内存不足
│  │  ├─ Page life expectancy 低 → 内存压力, 页面被快速换出
│  │  └─ Memory grants pending 高 → 查询内存分配不足
│  └─ IO 问题
│     ├─ Avg. Disk sec/Read > 20ms → 磁盘延迟高
│     ├─ Checkpoint pages/sec 高 → checkpoint过于频繁
│     └─ Lazy writes/sec 高 → 缓冲池压力, 内存不足
│
├─ 阻塞问题
│  ├─ sys.dm_exec_requests blocking_session_id > 0 → 阻塞链
│  ├─ wait_type = 'LCK_M_S' / 'LCK_M_X' → 读写阻塞
│  └─ wait_duration_ms 高 → 长期阻塞, 需终止阻塞者
│
├─ TempDB 问题
│  ├─ TempDB 争用 (PAGELATCH_UP) → 多个会话同时创建临时对象
│  ├─ TempDB 空间满 → 大排序或哈希操作
│  └─ 解决方案: 增加TempDB数据文件数量, 使用SSD
│
└─ 日志问题
   ├─ Transaction Log 满 → 日志备份未运行或长事务
   ├─ Log Reuse Wait = 'LOG_BACKUP' → 需要日志备份
   └─ Log Reuse Wait = 'REPLICATION' → 复制未消费日志
```

---

## 4. Time-Series Analysis Patterns

When analyzing metrics over time, identify these patterns to guide diagnosis:

### 4.1 Pattern Recognition Guide

| Pattern | Visual Shape | Likely Cause | Diagnostic Action |
|---------|-------------|--------------|-------------------|
| **Sudden Spike** | 瞬间垂直上升后恢复 | 单次大查询, DDL操作, 连接风暴 | 检查 `DescribeSQLLogRecords` 对应时间窗口的高延迟SQL |
| **Gradual Ramp** | 缓慢持续上升 | 业务增长, 数据积累, 连接泄漏 | 对比7天/30天趋势; 检查 `DataSize` 增长; 检查连接趋势 |
| **Periodic Wave** | 规律性波峰波谷 | 定时任务, 定时备份, 批处理作业 | 检查波峰时间点; 关联 `DescribeBackups` 和 `DescribeBinlogFiles` 时间 |
| **Step Change** | 阶梯式跳跃后平稳 | 配置变更, 应用发布, 索引变更 | 检查变更时间窗口; 检查 `DescribeParameters` 修改历史 |
| **Sawtooth** | 锯齿状反复升降 | 内存压力导致频繁GC/flush, 连接池反复创建销毁 | 检查 `MemoryUsage` 和 `Sessions` 的同步锯齿模式 |
| **Flatline High** | 持续高位平稳 | 持续高负载, 配置不足, 缺少索引 | 检查慢查询是否持续存在; 检查实例规格是否匹配负载 |
| **Correlation with External Event** | 与业务事件同步 | 促销活动, 数据同步, 报表生成 | 关联业务日历; 检查 `DescribeSQLLogRecords` 中的批量操作 |

### 4.2 Baseline Deviation Analysis

```
基线偏离分析流程
│
├─ 获取当前指标值 (Current)
├─ 获取历史基线 (Baseline)
│  ├─ 同时间段昨天 (D-1)
│  ├─ 同时间段上周同一天 (W-1)
│  └─ 同时间段上月同一天 (M-1)
├─ 计算偏离度
│  ├─ Deviation = (Current - Baseline) / Baseline * 100%
│  ├─ 偏离度 > 50% → 显著异常, 需立即调查
│  ├─ 偏离度 20-50% → 中度异常, 需关注趋势
│  └─ 偏离度 < 20% → 正常波动
└─ 判断异常类型
   ├─ D-1 和 W-1 同时偏离 → 系统性问题 (配置变更/应用变更)
   ├─ 仅 D-1 偏离 → 短期问题 (单次查询/临时任务)
   └─ 仅 W-1 偏离 → 周期性业务变化 (周末/月末效应)
```

---

## 5. Automated Diagnosis Workflow

### 5.1 Smart Alert Response Workflow

When user reports an alert (e.g., "RDS CPU 告警"), Agent 执行以下自动化诊断流程：

#### Phase 1: Alert Triage (30 seconds)

```
1. 获取实例基本信息
   → DescribeDBInstanceAttribute
   → 确认 Engine, Version, Status, Class

2. 获取当前性能快照
   → DescribeDBInstancePerformance (Key: CPU, Memory, Connections, IOPS)
   → DescribeResourceUsage

3. 判断告警严重程度
   ├─ 实例状态 != Running → 优先处理状态问题
   ├─ CPU > 95% 或 Disk > 90% → Critical, 立即深入诊断
   └─ 其他 → Warning, 标准诊断流程
```

#### Phase 2: Multi-Dimensional Correlation (60 seconds)

```
4. 根据告警类型, 执行关联检查
   ├─ CPU 告警 → 同时获取 Connections, IOPS, SlowLogs
   ├─ Disk 告警 → 同时获取 ResourceUsage, BinlogFiles, Backups
   ├─ Connection 告警 → 同时获取 SQLLogRecords, Accounts
   └─ Replication 告警 → 同时获取 HAConfig, ReadDBInstances

5. 应用关联矩阵 (Section 2.1)
   → 识别 Primary Root Cause vs Secondary Effects
```

#### Phase 3: Engine-Specific Deep Dive (90 seconds)

```
6. 根据 Engine 类型, 执行引擎特定诊断
   ├─ MySQL → 检查 InnoDB 状态, 锁等待, 复制状态
   ├─ PostgreSQL → 检查 VACUUM 状态, WAL 堆积, 连接状态
   └─ SQL Server → 检查 阻塞链, TempDB 争用, 日志重用

7. 获取时间窗口内的详细日志
   → DescribeSlowLogs (最近1小时)
   → DescribeErrorLogs (最近1小时)
   → DescribeSQLLogRecords (最近1小时, 按 latency 排序)
```

#### Phase 4: Root Cause Synthesis (30 seconds)

```
8. 综合分析所有数据, 生成诊断报告
   ├─ 根因分类: [查询性能] / [连接管理] / [资源配置] / [复制延迟] / [锁竞争]
   ├─ 影响评估: [仅性能下降] / [有宕机风险] / [数据一致性风险]
   └─ 建议行动: [立即优化SQL] / [扩容实例] / [调整参数] / [联系阿里云支持]

9. 输出结构化诊断结果
   ├─ 告警摘要
   ├─ 根因分析 (含证据链)
   ├─ 影响评估
   ├─ 即时建议 (可立即执行)
   └─ 长期建议 (需计划执行)
```

### 5.2 Diagnosis Report Template

```markdown
## RDS 智能诊断报告

### 实例信息
- DBInstanceId: {{user.db_instance_id}}
- Engine: {{engine}} {{version}}
- Class: {{class}}
- Status: {{status}}

### 告警摘要
- 告警类型: {{alert_type}}
- 触发时间: {{alert_time}}
- 当前值: {{current_value}} (阈值: {{threshold}})

### 根因分析
**主要根因**: {{primary_root_cause}}
**置信度**: {{confidence}}%
**证据链**:
1. {{evidence_1}}
2. {{evidence_2}}
3. {{evidence_3}}

**次要影响**:
- {{secondary_effect_1}}
- {{secondary_effect_2}}

### 影响评估
- 可用性影响: {{availability_impact}}
- 性能影响: {{performance_impact}}
- 数据风险: {{data_risk}}

### 即时建议 (可立即执行)
1. {{immediate_action_1}}
2. {{immediate_action_2}}

### 长期建议
1. {{long_term_action_1}}
2. {{long_term_action_2}}

### 相关操作命令
```bash
# 验证诊断结果
{{verification_commands}}
```
```

---

## 6. Common Failure Scenario Playbooks

### 6.1 Scenario: "CPU 100% + 连接数爆满"

**症状**: CPU 持续 100%, 连接数接近 max_connections, 应用报告连接超时

**诊断剧本**:

```bash
# Step 1: 获取性能快照 (10s)
aliyun rds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.db_instance_id}}" \
  --Key MySQL_CPUUsage,MySQL_Sessions,MySQL_ActiveSessions,MySQL_IOPS \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 2: 获取慢查询 (20s)
aliyun rds DescribeSlowLogs \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output cols=SQLText,MySQLTotalExecutionCounts,MySQLTotalExecutionTimes,MySQLMaxExecutionTime rows=Items.SQLSlowLog[0:10].{SQLText,MySQLTotalExecutionCounts,MySQLTotalExecutionTimes,MySQLMaxExecutionTime}

# Step 3: 获取SQL审计 (20s)
aliyun rds DescribeSQLLogRecords \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output cols=SQLText,Latency,AccountName rows=Items.SQLRecord[0:10].{SQLText,Latency,AccountName}

# Step 4: 获取错误日志 (10s)
aliyun rds DescribeErrorLogs \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

**根因判断**:
- 如果慢查询中某条 SQL 的 `MySQLTotalExecutionCounts` > 1000 且 `MySQLTotalExecutionTimes` > 10000ms → **根因: 热点慢查询**
- 如果 `ActiveSessions` ≈ `Sessions` 且慢查询不多 → **根因: 连接泄漏**
- 如果错误日志中有大量 `Lock wait timeout exceeded` → **根因: 锁竞争**

**即时行动**:
1. 如果是热点慢查询 → 建议 kill 该慢查询进程 (如可能), 建议加索引
2. 如果是连接泄漏 → 建议重启应用连接池, 临时增加 max_connections
3. 如果是锁竞争 → 建议找出持有锁的事务, 考虑终止长事务

---

### 6.2 Scenario: "磁盘 95% + 备份失败"

**症状**: 磁盘使用率 95%, 最近备份状态 Failed, 应用写入变慢

**诊断剧本**:

```bash
# Step 1: 资源使用详情
aliyun rds DescribeResourceUsage --DBInstanceId "{{user.db_instance_id}}"

# Step 2: 备份状态
aliyun rds DescribeBackups \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output cols=BackupId,BackupStatus,BackupSize rows=Items.Backup[].{BackupId,BackupStatus,BackupSize}

# Step 3: Binlog 文件
aliyun rds DescribeBinlogFiles \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output cols=LogFileName,FileSize rows=Items.BinLogFile[].{LogFileName,FileSize}

# Step 4: 错误日志
aliyun rds DescribeErrorLogs \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "$(date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

**根因判断**:
- 如果 `LogSize` >> `DataSize` → **根因: Binlog 堆积** (复制延迟或保留期过长)
- 如果 `BackupSize` 极大且备份失败 → **根因: 数据量过大导致备份空间不足**
- 如果错误日志有 `Disk full` → **根因: 磁盘物理满**

**即时行动**:
1. Binlog 堆积 → 检查复制延迟, 考虑清理过期 binlog
2. 数据量大 → 建议扩容存储, 或归档历史数据
3. 磁盘物理满 → 紧急扩容, 或删除不必要的日志文件

---

### 6.3 Scenario: "复制延迟 + 只读实例查询慢"

**症状**: 只读实例复制延迟 > 30s, 只读实例查询响应慢

**诊断剧本**:

```bash
# Step 1: HA 配置
aliyun rds DescribeDBInstanceHAConfig --DBInstanceId "{{user.db_instance_id}}"

# Step 2: 只读实例列表
aliyun rds DescribeReadDBInstances --DBInstanceId "{{user.db_instance_id}}"

# Step 3: 主库性能 (判断主库是否压力过大)
aliyun rds DescribeDBInstancePerformance \
  --DBInstanceId "{{user.db_instance_id}}" \
  --Key MySQL_TPS,MySQL_IOPS \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 4: Binlog 文件大小 (判断大事务)
aliyun rds DescribeBinlogFiles \
  --DBInstanceId "{{user.db_instance_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output cols=LogFileName,FileSize rows=Items.BinLogFile[].{LogFileName,FileSize}
```

**根因判断**:
- 如果主库 TPS 极高 → **根因: 主库写入压力过大, 从库跟不上**
- 如果 Binlog 文件突然变大 → **根因: 大事务导致复制延迟**
- 如果从库规格 < 主库规格 → **根因: 从库性能不足**
- 如果 `SyncMode` = `Async` → **根因: 异步复制, 延迟是预期行为**

**即时行动**:
1. 主库写入压力大 → 建议拆分大事务, 错峰写入
2. 大事务 → 建议将大事务拆分为小批次
3. 从库规格低 → 建议升级只读实例规格
4. 异步复制 → 建议评估是否需要改为同步 (影响可用性)

---

## 7. Alert Severity Escalation Matrix

| Severity | Condition | Auto-Action | Human Notification | Response Time |
|----------|-----------|-------------|-------------------|---------------|
| **P0-Critical** | CPU > 95% AND Disk > 90%<br>OR Instance Status != Running<br>OR Replication lag > 300s | 立即执行诊断工作流<br>自动收集所有相关日志 | 立即通知 DBA + 业务负责人<br>电话/短信 | 5 分钟内 |
| **P1-High** | CPU > 95% OR Disk > 90%<br>OR Connections > 95%<br>OR Replication lag > 60s | 执行诊断工作流<br>收集性能指标和慢查询 | 通知 DBA<br>企业微信/钉钉 | 15 分钟内 |
| **P2-Medium** | CPU > 80% OR Disk > 80%<br>OR Connections > 80%<br>OR Slow queries > 50/hour | 执行标准检查<br>生成趋势报告 | 通知 DBA<br>邮件/工单 | 1 小时内 |
| **P3-Low** | CPU > 70% OR Disk > 70%<br>OR Buffer hit < 90%<br>OR Backup age > 24h | 记录日志<br>纳入日报 | 日报汇总 | 24 小时内 |

---

## 8. Intelligent Recommendations Engine

基于诊断结果, Agent 应自动生成以下类型的建议:

### 8.1 Query Optimization Recommendations

| Finding | Confidence | Recommendation | Priority |
|---------|-----------|----------------|----------|
| Rows_examined / Rows_sent > 1000 | High | 为 WHERE 条件列添加索引 | P1 |
| `Using temporary` + `Using filesort` | High | 优化 ORDER BY / GROUP BY, 增加 sort_buffer_size | P1 |
| `SELECT *` on large table | Medium | 只查询需要的列, 减少网络传输 | P2 |
| No index used on JOIN | High | 为 JOIN 条件列添加复合索引 | P1 |
| Subquery in SELECT | Medium | 改写为 JOIN 或使用派生表 | P2 |

### 8.2 Configuration Tuning Recommendations

| Finding | Confidence | Recommendation | Risk |
|---------|-----------|----------------|------|
| Buffer hit ratio < 90% | High | 增加 innodb_buffer_pool_size (需重启) | Low |
| max_connections 经常接近上限 | High | 增加 max_connections 或优化连接池 | Low |
| Slow query log 未开启 | High | 开启慢查询日志, 设置 long_query_time = 1s | Low |
| innodb_log_file_size 太小 | Medium | 增加 redo log 大小 (需重建实例) | Medium |
| query_cache 开启且命中率低 | High | 关闭 query_cache (MySQL 8.0 已移除) | Low |

### 8.3 Scaling Recommendations

| Finding | Confidence | Recommendation | Cost Impact |
|---------|-----------|----------------|-------------|
| CPU > 80% 持续 7 天 | High | 升级实例规格 (CPU/Memory) | High |
| Disk > 80% 且增长快 | High | 扩容存储或归档历史数据 | Medium |
| IOPS > 80% 持续 | High | 升级存储类型 (SSD -> ESSD) 或增加 IOPS | High |
| Read-heavy workload | Medium | 增加只读实例, 配置读写分离 | Medium |
| Connection > 80% 持续 | Medium | 增加只读实例分担连接, 或使用数据库代理 | Medium |

---

## 9. Agent Execution Guidelines for Diagnosis

When user reports an alert or performance issue, Agent MUST follow this execution order:

1. **Acknowledge** the alert and confirm instance ID
2. **Triage** — get instance status and basic info (DescribeDBInstanceAttribute)
3. **Correlate** — get multi-dimensional metrics based on alert type
4. **Deep-dive** — get engine-specific diagnostics
5. **Synthesize** — apply correlation matrix to identify root cause
6. **Report** — output structured diagnosis report (Section 5.2 template)
7. **Recommend** — provide prioritized, actionable recommendations
8. **Verify** — if user executes recommendation, verify improvement

> **IMPORTANT**: Agent MUST NOT jump to conclusions without collecting sufficient evidence. Always collect at least 3 data points before declaring a root cause.
