# AIOps Anomaly Patterns — PolarDB MySQL

> Version: 1.0.0 | Last Updated: 2026-05-27
> 
> **Scope**: DOPS-85277 — 扩展 PolarDB 自动根因分析能力

## Overview

本文档定义 PolarDB MySQL 的 12 种异常检测模式，包括 7 种通用数据库异常模式和 5 种 PolarDB 特有模式。每种模式包含检测指标、阈值配置、根因分析和关联规则。

---

## Pattern Catalog Summary

| Code | Pattern Name | Severity | Category | Description |
|------|-------------|----------|----------|-------------|
| P001 | CPU Spike | Critical | General | CPU 使用率短时间内突增超过阈值 |
| P002 | Memory Pressure | Warning | General | 内存使用率持续高位，存在 OOM 风险 |
| P003 | IOPS Bottleneck | Critical | General | IOPS 使用率超过阈值，存储性能受限 |
| P004 | Connection Surge | Warning | General | 连接数突增，接近最大连接数限制 |
| P005 | Slow Query Spike | Warning | General | 慢查询数量显著增加 |
| P006 | Buffer Pool Hit Rate Drop | Warning | General | InnoDB 缓冲池命中率下降 |
| P007 | Active Session Spike | Critical | General | 活跃会话数突增，可能阻塞业务 |
| P008 | Replication Lag | Critical | PolarDB | 主从复制延迟超过安全阈值 |
| P009 | Read Node Imbalance | Warning | PolarDB | 只读节点间负载不均衡 |
| P010 | Storage IO Bottleneck | Critical | PolarDB | 存储层 IO 延迟异常 |
| P011 | GDN Sync Lag | Critical | PolarDB | 全球数据库网络同步延迟 |
| P012 | Serverless Elasticity Frequent | Warning | PolarDB | Serverless 弹性伸缩过于频繁 |

---

## General Patterns (P001-P007)

### P001: CPU Spike (CPU 突增)

**Pattern Definition**
- **Code**: P001
- **Name**: CPU Spike
- **Severity**: Critical
- **Description**: CPU 使用率在短时间（1-5 分钟）内突增超过 50%，或超过阈值（Warning: 80%, Critical: 95%）

**Detection Metrics**

| Metric | Namespace | Unit | Collection Period |
|--------|-----------|------|-------------------|
| CpuUsage | acs_polardb_dashboard | % | 60s |
| CpuUsage | acs_polardb_cluster | % | 60s |

**Threshold Configuration**

| Level | Threshold | Sudden Change | Duration |
|-------|-----------|---------------|----------|
| Warning | >= 80% | > 30% in 1min | 3 cycles |
| Critical | >= 95% | > 50% in 1min | 1 cycle |

**Root Cause Analysis**

| Priority | Root Cause | Evidence | Verification |
|----------|-----------|----------|--------------|
| 1 | 慢查询激增 | SlowQueries 同时上升 | 查询慢日志记录 |
| 2 | 大事务执行 | ActiveSessions + LockWait | 检查事务状态 |
| 3 | 连接突增 | ConnectionUsage 上升 | 检查连接来源 |
| 4 | 计划任务 | 定时任务触发 | 检查定时任务 |
| 5 | 应用峰值 | 业务流量正常增长 | 对比历史同期 |

**Correlation Rules**

```yaml
correlations:
  - pattern: P005  # Slow Query Spike
    condition: SlowQueries > 50/h AND time_diff < 5min
    confidence: high
  
  - pattern: P004  # Connection Surge
    condition: ConnectionUsage > 80% AND time_diff < 5min
    confidence: medium
  
  - pattern: P007  # Active Session Spike
    condition: ActiveSessions > threshold AND time_diff < 3min
    confidence: high
```

**Detection Algorithm**

```go
func DetectCPUAnomaly(points []MetricPoint, thresholds ThresholdConfig) *AnomalyEvent {
    // Layer 1: Threshold check
    current := points[len(points)-1].Value
    if current >= thresholds.Critical {
        return &AnomalyEvent{
            Type: AnomalyThreshold,
            Metric: "CpuUsage",
            Severity: "critical",
            Value: current,
            Threshold: thresholds.Critical,
        }
    }
    
    // Layer 2: Sudden spike detection
    if len(points) >= 3 {
        baseline := calculateMean(points[:len(points)-1])
        changePct := (current - baseline) / baseline * 100
        if changePct >= 50 {
            return &AnomalyEvent{
                Type: AnomalySuddenSpike,
                Metric: "CpuUsage",
                Severity: "critical",
                Value: current,
                ChangePercent: changePct,
            }
        }
    }
    
    return nil
}
```

---

### P002: Memory Pressure (内存压力)

**Pattern Definition**
- **Code**: P002
- **Name**: Memory Pressure
- **Severity**: Warning
- **Description**: 内存使用率持续超过阈值，存在 OOM 风险

**Detection Metrics**

| Metric | Namespace | Unit | Collection Period |
|--------|-----------|------|-------------------|
| MemoryUsage | acs_polardb_dashboard | % | 60s |
| InnodbBufferUsageRatio | acs_polardb_dashboard | % | 300s |

**Threshold Configuration**

| Level | Threshold | Trend Window | Sudden Change |
|-------|-----------|--------------|---------------|
| Warning | >= 85% | 5min × 3 | > 20% in 5min |
| Critical | >= 95% | - | > 30% in 5min |

**Root Cause Analysis**

| Priority | Root Cause | Evidence |
|----------|-----------|----------|
| 1 | Buffer Pool 配置不当 | InnodbBufferUsageRatio < 95% |
| 2 | 大查询占用内存 | Sort/Join 操作增多 |
| 3 | 连接数过多 | 每个连接占用内存累积 |
| 4 | 临时表激增 | CreatedTmpTables 上升 |

**Correlation Rules**

```yaml
correlations:
  - pattern: P006  # Buffer Pool Hit Rate Drop
    condition: InnodbBufferUsageRatio < 90%
    confidence: high
  
  - pattern: P004  # Connection Surge
    condition: ConnectionUsage > 70%
    confidence: medium
```

---

### P003: IOPS Bottleneck (IOPS 瓶颈)

**Pattern Definition**
- **Code**: P003
- **Name**: IOPS Bottleneck
- **Severity**: Critical
- **Description**: IOPS 使用率超过阈值，存储性能成为瓶颈

**Detection Metrics**

| Metric | Namespace | Unit | Collection Period |
|--------|-----------|------|-------------------|
| IopsUsage | acs_polardb_dashboard | % | 60s |
| IOPS | acs_polardb_dashboard | count/s | 60s |

**Threshold Configuration**

| Level | Threshold | Duration |
|-------|-----------|----------|
| Warning | >= 80% | 3min |
| Critical | >= 90% | 1min |

**Root Cause Analysis**

| Priority | Root Cause | Evidence |
|----------|-----------|----------|
| 1 | 大量随机 IO | IOPS 高但吞吐量低 |
| 2 | 全表扫描 | RowsExamined 激增 |
| 3 | Buffer Pool 不足 | InnodbBufferUsageRatio 低 |
| 4 | 存储层限制 | 达到存储规格上限 |

**Correlation Rules**

```yaml
correlations:
  - pattern: P005  # Slow Query Spike
    condition: SlowQueries > 30/h AND RowsExamined > 10000
    confidence: high
  
  - pattern: P001  # CPU Spike
    condition: CpuUsage > 70%
    confidence: medium
```

---

### P004: Connection Surge (连接突增)

**Pattern Definition**
- **Code**: P004
- **Name**: Connection Surge
- **Severity**: Warning
- **Description**: 连接数在短时间内突增，接近最大连接数限制

**Detection Metrics**

| Metric | Namespace | Unit | Collection Period |
|--------|-----------|------|-------------------|
| ConnectionUsage | acs_polardb_dashboard | % | 60s |
| ActiveConnections | acs_polardb_dashboard | count | 60s |
| MaxConnections | acs_polardb_dashboard | count | 300s |

**Threshold Configuration**

| Level | Threshold | Sudden Change |
|-------|-----------|---------------|
| Warning | >= 80% | > 30% in 5min |
| Critical | >= 95% | > 50% in 5min |

**Root Cause Analysis**

| Priority | Root Cause | Evidence |
|----------|-----------|----------|
| 1 | 应用连接池配置不当 | 连接数持续高位 |
| 2 | 连接泄漏 | 连接数只增不减 |
| 3 | 业务流量突增 | QPS 同时上升 |
| 4 | 慢查询阻塞 | ActiveSessions 高 |

---

### P005: Slow Query Spike (慢查询突增)

**Pattern Definition**
- **Code**: P005
- **Name**: Slow Query Spike
- **Severity**: Warning
- **Description**: 慢查询数量显著超过基线或阈值

**Detection Metrics**

| Metric | Namespace | Unit | Collection Period |
|--------|-----------|------|-------------------|
| SlowQueries | acs_polardb_dashboard | count/h | 300s |
| SlowQueryCount | acs_polardb_cluster | count | 60s |

**Threshold Configuration**

| Level | Threshold | Sudden Change |
|-------|-----------|---------------|
| Warning | > 50/h | > 200% baseline |
| Critical | > 100/h | > 500% baseline |

**Root Cause Analysis**

| Priority | Root Cause | Evidence |
|----------|-----------|----------|
| 1 | 索引缺失 | RowsExamined >> RowsSent |
| 2 | 数据量激增 | 表行数显著增长 |
| 3 | 统计信息过期 | 执行计划改变 |
| 4 | 锁等待 | LockTime 高 |

---

### P006: Buffer Pool Hit Rate Drop (缓冲池命中率下降)

**Pattern Definition**
- **Code**: P006
- **Name**: Buffer Pool Hit Rate Drop
- **Severity**: Warning
- **Description**: InnoDB 缓冲池命中率显著下降

**Detection Metrics**

| Metric | Namespace | Unit | Collection Period |
|--------|-----------|------|-------------------|
| InnodbBufferUsageRatio | acs_polardb_dashboard | % | 300s |
| InnodbBufferHitRatio | acs_polardb_dashboard | % | 300s |

**Threshold Configuration**

| Level | Threshold | Sudden Change |
|-------|-----------|---------------|
| Warning | < 90% | < 85% |
| Critical | < 85% | < 80% |

**Root Cause Analysis**

| Priority | Root Cause | Evidence |
|----------|-----------|----------|
| 1 | Buffer Pool 太小 | 配置低于数据热集 |
| 2 | 全表扫描激增 | 大量冷数据加载 |
| 3 | 数据访问模式改变 | 随机访问增加 |

---

### P007: Active Session Spike (活跃会话突增)

**Pattern Definition**
- **Code**: P007
- **Name**: Active Session Spike
- **Severity**: Critical
- **Description**: 活跃会话数突增，可能导致请求排队和超时

**Detection Metrics**

| Metric | Namespace | Unit | Collection Period |
|--------|-----------|------|-------------------|
| ActiveSessions | acs_polardb_dashboard | count | 60s |
| RunningSessions | acs_polardb_dashboard | count | 60s |

**Threshold Configuration**

| Level | Threshold | Sudden Change |
|-------|-----------|---------------|
| Warning | > 80% max_connections | > 30% in 3min |
| Critical | > 90% max_connections | > 50% in 3min |

**Root Cause Analysis**

| Priority | Root Cause | Evidence |
|----------|-----------|----------|
| 1 | 慢查询堆积 | 会话长时间运行 |
| 2 | 锁等待 | LockWait 高 |
| 3 | 应用线程池膨胀 | 并发请求激增 |

---

## PolarDB-Specific Patterns (P008-P012)

### P008: Replication Lag (主从延迟异常)

**Pattern Definition**
- **Code**: P008
- **Name**: Replication Lag
- **Severity**: Critical
- **Description**: 主从复制延迟超过安全阈值，只读节点数据可能过期

**Detection Metrics**

| Metric | Namespace | Unit | Collection Period |
|--------|-----------|------|-------------------|
| ReplicationLag | acs_polardb_cluster | ms | 60s |
| ReplicationDelay | acs_polardb_dashboard | ms | 60s |

**Threshold Configuration**

| Level | Threshold | Duration |
|-------|-----------|----------|
| Warning | >= 1000ms | 3min |
| Critical | >= 5000ms | 1min |

**Root Cause Analysis**

| Priority | Root Cause | Evidence | Verification |
|----------|-----------|----------|--------------|
| 1 | 主节点压力过大 | CpuUsage 高 | 检查主节点指标 |
| 2 | 大事务执行 | Binlog 文件大 | 检查事务大小 |
| 3 | 网络延迟 | 跨可用区部署 | 检查网络延迟 |
| 4 | 从节点 IO 瓶颈 | IopsUsage 高 | 检查从节点 IO |
| 5 | DDL 操作 | 表锁等待 | 检查 DDL 历史 |

**PolarDB CLI Detection**

```bash
# Get replication lag metrics
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_cluster \
  --MetricName ReplicationLag \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Statistics Average,Maximum \
  --Period 60 \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Get read node status for correlation
aliyun polardb DescribeDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

**Go SDK Detection**

```go
func DetectReplicationLag(clusterId string, threshold int64) *AnomalyEvent {
    // Fetch ReplicationLag metric
    metricData := fetchMetric(clusterId, "ReplicationLag", "acs_polardb_cluster")
    
    currentLag := metricData.LastValue
    if currentLag >= threshold {
        severity := "warning"
        if currentLag >= 5000 {
            severity = "critical"
        }
        
        // Analyze root cause
        causes := []string{}
        if isPrimaryNodeHighLoad(clusterId) {
            causes = append(causes, "主节点压力过大")
        }
        if hasLargeTransaction(clusterId) {
            causes = append(causes, "大事务执行中")
        }
        
        return &AnomalyEvent{
            Type: AnomalyThreshold,
            Metric: "ReplicationLag",
            Severity: severity,
            Value: float64(currentLag),
            Threshold: float64(threshold),
            RootCauses: causes,
            PatternCode: "P008",
        }
    }
    return nil
}
```

---

### P009: Read Node Imbalance (只读节点不均衡)

**Pattern Definition**
- **Code**: P009
- **Name**: Read Node Imbalance
- **Severity**: Warning
- **Description**: 只读节点间 CPU/连接使用率差异过大，负载不均衡

**Detection Metrics**

| Metric | Namespace | Unit | Collection Period |
|--------|-----------|------|-------------------|
| PolarDBReadNodeCPUUsage | acs_polardb_dashboard | % | 60s |
| PolarDBReadNodeConnections | acs_polardb_dashboard | count | 60s |

**Threshold Configuration**

| Level | Threshold | Calculation |
|-------|-----------|-------------|
| Warning | diff >= 30% | (max - min) / avg > 30% |
| Critical | diff >= 50% | (max - min) / avg > 50% |

**Root Cause Analysis**

| Priority | Root Cause | Evidence |
|----------|-----------|----------|
| 1 | Endpoint 权重配置不均 | 特定节点权重过高 |
| 2 | 节点健康状态异常 | 某节点被剔除 |
| 3 | 业务热点集中 | 特定查询集中到某节点 |
| 4 | 跨可用区延迟 | 部分节点延迟高 |

**Detection Algorithm**

```go
func DetectReadNodeImbalance(clusterId string, diffThreshold float64) *AnomalyEvent {
    // Get all read node metrics
    nodes := getReadNodes(clusterId)
    cpuUsages := []float64{}
    
    for _, node := range nodes {
        cpu := fetchNodeMetric(node.NodeId, "PolarDBReadNodeCPUUsage")
        cpuUsages = append(cpuUsages, cpu)
    }
    
    // Calculate imbalance
    maxCPU, minCPU, avgCPU := calculateStats(cpuUsages)
    diffPct := (maxCPU - minCPU) / avgCPU * 100
    
    if diffPct >= diffThreshold {
        return &AnomalyEvent{
            Type: AnomalyTrend,
            Metric: "ReadNodeUsageDiff",
            Severity: "warning",
            Value: diffPct,
            Threshold: diffThreshold,
            Description: fmt.Sprintf("只读节点负载不均衡: 差异 %.1f%% (最高 %.1f%%, 最低 %.1f%%)", 
                diffPct, maxCPU, minCPU),
            PatternCode: "P009",
        }
    }
    return nil
}
```

---

### P010: Storage IO Bottleneck (存储 IO 瓶颈)

**Pattern Definition**
- **Code**: P010
- **Name**: Storage IO Bottleneck
- **Severity**: Critical
- **Description**: 存储层 IO 延迟异常，影响数据库响应时间

**Detection Metrics**

| Metric | Namespace | Unit | Collection Period |
|--------|-----------|------|-------------------|
| StorageIOAvgLatency | acs_polardb_dashboard | ms | 60s |
| StorageIORWLatency | acs_polardb_dashboard | ms | 60s |

**Threshold Configuration**

| Level | Threshold | Duration |
|-------|-----------|----------|
| Warning | >= 10ms | 3min |
| Critical | >= 50ms | 1min |

**Root Cause Analysis**

| Priority | Root Cause | Evidence |
|----------|-----------|----------|
| 1 | 存储层 PSLevel 不足 | 存储规格限制 |
| 2 | 并发写入过高 | WriteIOPS 激增 |
| 3 | 大查询全表扫描 | ReadIOPS 激增 |
| 4 | 存储节点热点 | 特定 Page 访问集中 |

---

### P011: GDN Sync Lag (GDN 同步延迟)

**Pattern Definition**
- **Code**: P011
- **Name**: GDN Sync Lag
- **Severity**: Critical
- **Description**: 全球数据库网络 (GDN) 主从集群间同步延迟过高

**Detection Metrics**

| Metric | Namespace | Unit | Collection Period |
|--------|-----------|------|-------------------|
| GDNSyncLag | acs_polardb_cluster | ms | 60s |
| CrossRegionReplicationLag | acs_polardb_dashboard | ms | 300s |

**Threshold Configuration**

| Level | Threshold | Duration |
|-------|-----------|----------|
| Warning | >= 500ms | 5min |
| Critical | >= 2000ms | 3min |

**Root Cause Analysis**

| Priority | Root Cause | Evidence |
|----------|-----------|----------|
| 1 | 跨地域网络延迟 | 物理距离导致 |
| 2 | 主集群写入压力 | 主集群 CPU/IO 高 |
| 3 | 从集群回放瓶颈 | 从集群资源不足 |
| 4 | Binlog 传输延迟 | 网络带宽不足 |

---

### P012: Serverless Elasticity Frequent (Serverless 弹性频繁)

**Pattern Definition**
- **Code**: P012
- **Name**: Serverless Elasticity Frequent
- **Severity**: Warning
- **Description**: Serverless 集群 RCU 弹性伸缩频率过高，影响稳定性

**Detection Metrics**

| Metric | Namespace | Unit | Collection Period |
|--------|-----------|------|-------------------|
| RCUChangeCount | acs_polardb_cluster | count/h | 300s |
| ServerlessRCU | acs_polardb_dashboard | count | 60s |
| ScaleUpCount | acs_polardb_dashboard | count/h | 300s |
| ScaleDownCount | acs_polardb_dashboard | count/h | 300s |

**Threshold Configuration**

| Level | Threshold | Description |
|-------|-----------|-------------|
| Warning | > 10 次/h | 弹性频率偏高 |
| Critical | > 20 次/h | 弹性过于频繁 |

**Root Cause Analysis**

| Priority | Root Cause | Evidence |
|----------|-----------|----------|
| 1 | 弹性阈值配置过窄 | MinRCU 与 MaxRCU 接近 |
| 2 | 负载波动大 | QPS 不稳定 |
| 3 | 弹性策略激进 | 伸缩响应过于敏感 |
| 4 | 定时任务影响 | 固定时间弹性 |

---

## Pattern Correlation Matrix

### Multi-Pattern Correlation Rules

```yaml
correlation_chains:
  # Chain 1: CPU → Slow Query → Lock
  - name: "CPU_SlowQuery_Lock_Chain"
    patterns: [P001, P005, P007]
    condition: all_detected_within(10min)
    root_cause: "慢查询导致 CPU 升高，同时引发锁等待"
    
  # Chain 2: Memory → Buffer Pool → IO
  - name: "Memory_Buffer_IO_Chain"
    patterns: [P002, P006, P003]
    condition: P002 AND (P006 OR P003)
    root_cause: "内存不足导致 Buffer Pool 失效，引发 IO 瓶颈"
    
  # Chain 3: Replication → Read Node
  - name: "Replication_ReadNode_Chain"
    patterns: [P008, P009]
    condition: P008 AND P009
    root_cause: "复制延迟导致读节点数据不一致，负载不均衡"
    
  # Chain 4: Connection → Active Session → CPU
  - name: "Connection_Session_CPU_Chain"
    patterns: [P004, P007, P001]
    condition: P004 → P007 → P001 (sequential, 5min apart)
    root_cause: "连接突增导致活跃会话堆积，最终引发 CPU 高"
```

---

## Implementation Reference

### Go SDK Pattern Detection Interface

```go
// PatternDetector interface for all anomaly patterns
type PatternDetector interface {
    // Get pattern code
    GetCode() string
    
    // Get pattern name
    GetName() string
    
    // Detect anomaly
    Detect(clusterId string, timeRange TimeRange) *AnomalyEvent
    
    // Correlate with other patterns
    Correlate(event *AnomalyEvent, otherEvents []AnomalyEvent) *CorrelationChain
}

// BasePattern provides common functionality
type BasePattern struct {
    Code        string
    Name        string
    Severity    string
    Thresholds  ThresholdConfig
}

// PatternRegistry for managing all patterns
type PatternRegistry struct {
    patterns map[string]PatternDetector
}

func (r *PatternRegistry) Register(detector PatternDetector) {
    r.patterns[detector.GetCode()] = detector
}

func (r *PatternRegistry) DetectAll(clusterId string, timeRange TimeRange) []AnomalyEvent {
    events := []AnomalyEvent{}
    for _, detector := range r.patterns {
        if event := detector.Detect(clusterId, timeRange); event != nil {
            events = append(events, *event)
        }
    }
    return events
}
```

### CLI Batch Detection Command

```bash
# Detect all patterns for a cluster
aliyun polardb AIOpsDetectAnomalies \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Patterns "P001,P002,P003,P004,P005,P006,P007,P008,P009,P010,P011,P012" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-27 | Initial release — 12 anomaly patterns for DOPS-85277 |
