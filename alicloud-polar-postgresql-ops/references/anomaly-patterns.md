# 异常模式检测指南

本文档定义了 PolarDB PostgreSQL 集群的异常模式检测规则，用于智能巡检和监控告警。

## 异常模式定义

### PG-01: CPU-IOPS双高

**检测条件:**
- CPU使用率 > 80%
- IOPS达到瓶颈 (IOPSUsage > 80%)

**严重程度:** 高 (High)

**可能原因:**
- 复杂查询或全表扫描
- 并发连接过多
- 大批量数据写入

**Agent 建议操作:**
1. 使用 `DescribeSlowLogRecords` 查看慢查询
2. 检查 `pg_stat_activity` 当前连接
3. 考虑升配或添加只读节点

---

### PG-02: 连接池异常

**检测条件:**
- ActiveConnections >= MaxConnections * 0.9 (90%)

**严重程度:** 高 (High)

**可能原因:**
- 连接泄漏 (未关闭的连接)
- 连接池配置不当
- 突发大量并发请求

**Agent 建议操作:**
1. 检查应用连接池配置
2. 分析 `pg_stat_activity` 中的长时间空闲连接
3. 考虑增大 `max_connections` 参数
4. 排查是否存在慢查询阻塞连接

---

### PG-03: 内存-缓冲池瓶颈

**检测条件:**
- Memory使用率 > 85%
- BufferPoolHitRate < 95%

**严重程度:** 中 (Medium)

**可能原因:**
- 缓冲池配置过小
- 热数据量超过缓冲池大小
- 大规模顺序扫描

**Agent 建议操作:**
1. 检查 `shared_buffers` 参数配置
2. 分析 `pg_stat_database` 中的缓存命中率
3. 考虑优化 `effective_cache_size`
4. 识别大表并考虑使用分区

---

### PG-04: 存储空间预警

**检测条件:**
- StorageUsage > 85%

**严重程度:** 高 (High)

**可能原因:**
- 数据量持续增长
- 大量未清理的日志
- 备份保留策略过久

**Agent 建议操作:**
1. 检查存储使用详情
2. 清理过期备份
3. 分析大表和索引
4. 考虑存储扩容

---

## API 调用示例

获取多个性能指标进行交叉分析：

```bash
aliyun polardb DescribeDBClusterPerformance \
  --DBClusterId "{{user.db_cluster_id}}" \
  --PerformanceKeys "cpuUsage,iopsUsage,connectionUsage,memoryUsage,storageUsage,bufferPoolHitRate"
```

## 阈值配置建议

| 指标 | 预警阈值 | 告警阈值 | 说明 |
|------|----------|----------|------|
| CPU | 70% | 85% | 持续5分钟 |
| IOPS | 70% | 85% | 持续5分钟 |
| 连接数 | 70% | 90% | 峰值统计 |
| 内存 | 75% | 85% | 持续5分钟 |
| 存储 | 75% | 85% | 立即告警 |
| 缓存命中率 | 95% | 90% | 持续统计 |

## 自动化巡检集成

在 PolarDB PG Cruise 健康检查中集成异常模式检测：

```yaml
health_check_with_anomaly_detection:
  - step: performance_metrics
    api: DescribeDBClusterPerformance
    keys: [cpuUsage, iopsUsage, connectionUsage, memoryUsage, storageUsage, bufferPoolHitRate]
    anomaly_detection:
      enabled: true
      patterns: [PG-01, PG-02, PG-03, PG-04]
    alert_on_anomaly: true
```