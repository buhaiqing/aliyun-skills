# AIOps: PolarDB PostgreSQL Auto-Remediation with Safety Controls

> 自动修复能力，基于异常检测结果自动执行修复操作，内置多重安全控制机制确保修复操作的安全性。

## Overview

本节提供**自动修复**能力，与异常检测（12 patterns P001-P012）联动，实现：

- **自动诊断修复**：基于根因分析自动执行修复操作
- **多重安全控制**：影响评估、灰度发布、一键回滚
- **分级响应策略**：警告/高危/紧急三级响应
- **人工确认机制**：高危操作需人工确认

## Safety Control Framework

### 三层安全控制模型

```
┌─────────────────────────────────────────────────────────────┐
│                   Safety Control Framework                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Pre-check (执行前检查)                              │
│  ├── 影响范围评估 (Impact Assessment)                         │
│  ├── 回滚方案准备 (Rollback Plan)                            │
│  └── 维护窗口检查 (Maintenance Window)                        │
│                                                              │
│  Layer 2: Execution (执行控制)                               │
│  ├── 灰度执行 (Canary Execution)                             │
│  ├── 实时监测 (Real-time Monitoring)                         │
│  └── 自动熔断 (Auto Circuit Breaker)                         │
│                                                              │
│  Layer 3: Post-check (执行后验证)                             │
│  ├── 效果验证 (Effect Validation)                            │
│  ├── 业务指标检查 (Business Metric Check)                    │
│  └── 回滚触发条件 (Rollback Trigger)                         │
└─────────────────────────────────────────────────────────────┘
```

### 安全控制参数

| 参数 | 默认值 | 说明 | 范围 |
|------|--------|------|------|
| `auto_remediation_enabled` | `false` | 全局开关 | `true`/`false` |
| `max_concurrent_fixes` | `2` | 最大并发修复数 | 1-5 |
| `canary_percentage` | `10%` | 灰度比例 | 5%-50% |
| `canary_duration` | `5m` | 灰度观察时间 | 3m-30m |
| `rollback_threshold` | `95%` | 回滚触发成功率阈值 | 90%-99% |
| `maintenance_window_only` | `true` | 仅维护窗口执行 | `true`/`false` |
| `human_approval_required` | `true` | 高危操作需人工确认 | `true`/`false` |

## Remediation Action Catalog

### 自动修复动作清单

| Pattern | 修复动作 | 风险等级 | 需确认 | 回滚方式 |
|---------|----------|----------|--------|----------|
| P001 CPU Spike | 参数优化 + SQL限流 | Medium | 是 | 恢复参数 |
| P002 Memory Pressure | 缓存调整 + 连接限制 | Medium | 是 | 恢复配置 |
| P003 Connection Surge | 连接池扩展 | Low | 否 | 缩减连接池 |
| P004 IOPS Bottleneck | 存储扩容 | High | 是 | 不支持 |
| P005 Slow Query Spike | 索引建议 + SQL限流 | Medium | 是 | 取消限流 |
| P006 Buffer Hit Rate Drop | 缓存预热 | Low | 否 | 停止预热 |
| P007 Active Session Spike | 会话清理 | Medium | 是 | 无 |
| P008 Replication Lag | 复制参数调整 | Medium | 是 | 恢复参数 |
| P009 Read Node Imbalance | 负载均衡调整 | Low | 否 | 恢复权重 |
| P010 Storage IO Bottleneck | 存储类型升级 | High | 是 | 不支持 |
| P011 GDN Sync Lag | GDN参数优化 | Medium | 是 | 恢复参数 |
| P012 Serverless Elasticity | 弹性策略调整 | Low | 否 | 恢复策略 |

## Pre-flight Safety Checks

### 检查清单

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| 全局开关 | Config check | `auto_remediation_enabled=true` | HALT; 未启用自动修复 |
| 当前修复数 | State check | `< max_concurrent_fixes` | HALT; 并发限制 |
| 维护窗口 | Time check | Within window or `maintenance_window_only=false` | HALT; 等待维护窗口 |
| 集群状态 | DescribeDBClusterAttribute | `Running` | HALT; 集群不稳定 |
| 备份状态 | DescribeBackups | 24h内有成功备份 | HALT; 先执行备份 |
| 业务低峰 | CMS metrics | QPS < baseline × 1.2 | WAIT; 等待低峰 |

### 影响评估

```go
// ImpactAssessment - 修复影响评估
type ImpactAssessment struct {
    PatternID          string           `json:"pattern_id"`
    RemediationAction  string           `json:"action"`
    AffectedResources  []string         `json:"affected_resources"`
    EstimatedDowntime  time.Duration    `json:"estimated_downtime"`
    DataLossRisk       RiskLevel        `json:"data_loss_risk"`
    PerformanceImpact  string           `json:"performance_impact"`
    RollbackComplexity RollbackComplexity `json:"rollback_complexity"`
}

// RiskLevel - 风险等级
type RiskLevel string
const (
    RiskLow     RiskLevel = "low"
    RiskMedium  RiskLevel = "medium"
    RiskHigh    RiskLevel = "high"
    RiskCritical RiskLevel = "critical"
)

// RollbackComplexity - 回滚复杂度
type RollbackComplexity string
const (
    RollbackSimple    RollbackComplexity = "simple"     // 立即回滚
    RollbackModerate  RollbackComplexity = "moderate"   // 需操作
    RollbackComplex   RollbackComplexity = "complex"    // 需停机
    RollbackImpossible RollbackComplexity = "impossible" // 无法回滚
)

// assessImpact - 评估修复影响
func assessImpact(pattern PatternType, action RemediationAction) *ImpactAssessment {
    assessment := &ImpactAssessment{
        PatternID:         string(pattern),
        RemediationAction: string(action),
    }
    
    switch pattern {
    case PatternCPUSpike:
        assessment.AffectedResources = []string{"CPU", "active sessions"}
        assessment.EstimatedDowntime = 0
        assessment.DataLossRisk = RiskLow
        assessment.PerformanceImpact = "< 5% degradation during fix"
        assessment.RollbackComplexity = RollbackSimple
        
    case PatternStorageIOBottleneck:
        assessment.AffectedResources = []string{"storage", "IOPS"}
        assessment.EstimatedDowntime = 30 * time.Second
        assessment.DataLossRisk = RiskLow
        assessment.PerformanceImpact = " brief I/O pause"
        assessment.RollbackComplexity = RollbackImpossible
        
    case PatternConnectionSurge:
        assessment.AffectedResources = []string{"connections"}
        assessment.EstimatedDowntime = 0
        assessment.DataLossRisk = RiskLow
        assessment.PerformanceImpact = "new connections may be rejected briefly"
        assessment.RollbackComplexity = RollbackSimple
    }
    
    return assessment
}
```

## Remediation Implementation

### 修复动作实现

#### P001 CPU Spike - SQL Throttling

```go
// remediateCPUSpike - 修复CPU突增
func remediateCPUSpike(clusterId string, severity SeverityLevel, assessment *ImpactAssessment) (*RemediationResult, error) {
    // 1. 获取Top慢SQL
    slowQueries := getTopSlowQueries(clusterId, 5)
    
    result := &RemediationResult{
        PatternID:   "P001",
        ActionTaken: "sql_throttle",
        StartTime:   time.Now(),
    }
    
    // 2. 根据严重级别设置限流参数
    var throttlePercent int
    switch severity {
    case SeverityWarning:
        throttlePercent = 20
    case SeverityHigh:
        throttlePercent = 50
    case SeverityCritical:
        throttlePercent = 80
    }
    
    // 3. 执行SQL限流
    for _, query := range slowQueries {
        err := enableSQLThrottle(clusterId, query.SQLId, throttlePercent)
        if err != nil {
            result.Errors = append(result.Errors, err.Error())
            continue
        }
        result.ThrottledQueries = append(result.ThrottledQueries, query.SQLId)
    }
    
    // 4. 等待灰度期
    if assessment.RollbackComplexity == RollbackSimple {
        time.Sleep(canaryDuration)
        
        // 验证效果
        cpuUsage := getCurrentCPUUsage(clusterId)
        if cpuUsage > 80 {
            // 效果不佳，回滚
            rollbackSQLThrottle(clusterId, result.ThrottledQueries)
            result.RollbackTriggered = true
            result.Status = "rolled_back"
        } else {
            result.Status = "success"
        }
    }
    
    result.EndTime = time.Now()
    return result, nil
}
```

#### P003 Connection Surge - Connection Pool Expansion

```bash
# CLI: 修改max_connections参数
aliyun polardb ModifyDBClusterServerlessConf \
  --DBClusterId "{{user.db_cluster_id}}" \
  --ScaleMin "{{user.current_min}}" \
  --ScaleMax "$((user.current_max + 20))" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 记录变更用于回滚
echo "$(date) - Expanded connection pool: {{user.current_max}} -> $((user.current_max + 20))" >> /var/log/polardb-auto-remediation.log
```

#### P008 Replication Lag - Replication Parameter Adjustment

```go
// remediateReplicationLag - 修复复制延迟
func remediateReplicationLag(clusterId, nodeId string, lagSeconds int) (*RemediationResult, error) {
    result := &RemediationResult{
        PatternID:   "P008",
        ActionTaken: "adjust_replication_params",
        StartTime:   time.Now(),
    }
    
    // 计算优化参数
    var maxWorkers, batchSize int
    switch {
    case lagSeconds > 300:
        maxWorkers = 8
        batchSize = 5000
    case lagSeconds > 60:
        maxWorkers = 4
        batchSize = 2000
    default:
        maxWorkers = 2
        batchSize = 1000
    }
    
    // 保存原始参数
    originalParams, _ := getReplicationParams(clusterId, nodeId)
    result.RollbackData = originalParams
    
    // 应用优化参数
    params := map[string]interface{}{
        "max_parallel_workers_per_gather": maxWorkers,
        "wal_receiver_status_interval":    "1s",
        "max_slot_wal_keep_size":          "100GB",
    }
    
    err := modifyReplicationParams(clusterId, nodeId, params)
    if err != nil {
        result.Status = "failed"
        result.Errors = append(result.Errors, err.Error())
        return result, err
    }
    
    // 灰度观察
    time.Sleep(3 * time.Minute)
    
    // 验证效果
    newLag := getReplicationLag(clusterId, nodeId)
    if newLag < lagSeconds/2 {
        result.Status = "success"
        result.Effectiveness = float64(lagSeconds-newLag) / float64(lagSeconds)
    } else {
        // 效果不佳，回滚
        restoreReplicationParams(clusterId, nodeId, originalParams)
        result.RollbackTriggered = true
        result.Status = "rolled_back"
    }
    
    result.EndTime = time.Now()
    return result, nil
}
```

## Safety Controls

### 熔断机制

```go
// CircuitBreaker - 熔断器
type CircuitBreaker struct {
    FailureCount    int
    LastFailureTime time.Time
    State           CircuitState
    Threshold       int
    Timeout         time.Duration
}

type CircuitState string
const (
    CircuitClosed    CircuitState = "closed"    // 正常
    CircuitOpen      CircuitState = "open"      // 熔断
    CircuitHalfOpen  CircuitState = "half_open" // 半开
)

// Execute - 带熔断的执行
func (cb *CircuitBreaker) Execute(operation func() error) error {
    if cb.State == CircuitOpen {
        if time.Since(cb.LastFailureTime) < cb.Timeout {
            return fmt.Errorf("circuit breaker is OPEN")
        }
        cb.State = CircuitHalfOpen
    }
    
    err := operation()
    if err != nil {
        cb.FailureCount++
        cb.LastFailureTime = time.Now()
        
        if cb.FailureCount >= cb.Threshold {
            cb.State = CircuitOpen
            logAlert("Circuit breaker OPEN for auto-remediation")
        }
        return err
    }
    
    // 成功，重置
    cb.FailureCount = 0
    cb.State = CircuitClosed
    return nil
}
```

### 灰度执行

```go
// CanaryExecutor - 灰度执行器
type CanaryExecutor struct {
    Percentage    int           // 灰度比例
    Duration      time.Duration // 观察时长
    SuccessRate   float64       // 成功率阈值
}

// ExecuteWithCanary - 灰度执行修复
func (ce *CanaryExecutor) ExecuteWithCanary(
    fullRemediation func() error,
    canaryCheck func() (successRate float64, err error),
) error {
    // 第一阶段：灰度
    logInfo(fmt.Sprintf("Starting canary execution at %d%%", ce.Percentage))
    
    // 执行部分修复
    if err := fullRemediation(); err != nil {
        return fmt.Errorf("canary execution failed: %w", err)
    }
    
    // 观察期
    time.Sleep(ce.Duration)
    
    // 检查灰度效果
    successRate, err := canaryCheck()
    if err != nil {
        return fmt.Errorf("canary check failed: %w", err)
    }
    
    if successRate < ce.SuccessRate {
        return fmt.Errorf("canary success rate %.2f%% below threshold %.2f%%", 
            successRate*100, ce.SuccessRate*100)
    }
    
    logInfo(fmt.Sprintf("Canary passed with %.2f%% success rate, proceeding to full rollout", successRate*100))
    return nil
}
```

### 回滚机制

```go
// RollbackManager - 回滚管理器
type RollbackManager struct {
    snapshots map[string]*SystemSnapshot
}

type SystemSnapshot struct {
    Timestamp  time.Time
    Parameters map[string]string
    Configs    map[string]interface{}
}

// CreateSnapshot - 创建系统快照
func (rm *RollbackManager) CreateSnapshot(clusterId string) (*SystemSnapshot, error) {
    snapshot := &SystemSnapshot{
        Timestamp:  time.Now(),
        Parameters: make(map[string]string),
        Configs:    make(map[string]interface{}),
    }
    
    // 保存关键参数
    params, _ := describeDBParameters(clusterId)
    for _, param := range params {
        snapshot.Parameters[param.ParameterName] = param.ParameterValue
    }
    
    rm.snapshots[clusterId] = snapshot
    return snapshot, nil
}

// Rollback - 执行回滚
func (rm *RollbackManager) Rollback(clusterId string) error {
    snapshot, exists := rm.snapshots[clusterId]
    if !exists {
        return fmt.Errorf("no snapshot found for cluster %s", clusterId)
    }
    
    logInfo(fmt.Sprintf("Rolling back cluster %s to snapshot at %s", clusterId, snapshot.Timestamp))
    
    // 恢复参数
    for name, value := range snapshot.Parameters {
        if err := modifyDBParameter(clusterId, name, value); err != nil {
            logError(fmt.Sprintf("Failed to rollback parameter %s: %v", name, err))
        }
    }
    
    return nil
}
```

## Output Format

### 自动修复报告

```markdown
# PolarDB PostgreSQL 自动修复报告

**修复时间**: 2026-05-27 16:30:00  
**集群ID**: pg-xxxxx  
**触发模式**: P001 CPU Spike  
**严重程度**: High

## 安全控制检查

| 检查项 | 状态 | 详情 |
|--------|------|------|
| 全局开关 | ✅ 通过 | auto_remediation_enabled=true |
| 并发限制 | ✅ 通过 | 当前1/2 |
| 维护窗口 | ✅ 通过 | 当前在维护窗口内 |
| 集群状态 | ✅ 通过 | Running |
| 备份检查 | ✅ 通过 | 最近备份: 2小时前 |
| 影响评估 | ✅ 通过 | 风险: Medium |

## 影响评估

| 维度 | 评估结果 |
|------|----------|
| **影响资源** | CPU, active sessions |
| **预计停机** | 0秒 |
| **数据丢失风险** | Low |
| **性能影响** | < 5% degradation during fix |
| **回滚复杂度** | Simple |

## 执行详情

| 阶段 | 时间 | 动作 | 结果 |
|------|------|------|------|
| 16:30:00 | 0s | 创建系统快照 | ✅ 成功 |
| 16:30:05 | 5s | 灰度启动 (10%) | ✅ 成功 |
| 16:35:05 | 5m | 灰度观察 | ✅ 成功率 98% |
| 16:35:10 | 5m10s | 全量执行 | ✅ 成功 |
| 16:35:15 | 5m15s | 效果验证 | ✅ CPU降至 45% |

## 修复动作

| SQL ID | 原执行时间 | 限流比例 | 当前状态 |
|--------|-----------|----------|----------|
| sql-abc123 | 12.5s | 50% | Throttled |
| sql-def456 | 8.3s | 50% | Throttled |

## 验证结果

| 指标 | 修复前 | 修复后 | 改善 |
|------|--------|--------|------|
| CPU使用率 | 85.2% | 45.3% | -46.9% |
| 活跃会话 | 245 | 180 | -26.5% |
| 平均响应时间 | 125ms | 85ms | -32% |

## 结论

**修复状态**: ✅ 成功  
**回滚需求**: 否  
**后续建议**: 监控24小时，如CPU稳定则取消限流
```

### JSON 输出格式

```json
{
  "remediation_id": "rem-pg-20260527163000",
  "cluster_id": "pg-xxxxx",
  "timestamp": "2026-05-27T16:30:00Z",
  "pattern_id": "P001",
  "pattern_name": "CPU Spike",
  "severity": "high",
  "safety_checks": {
    "auto_remediation_enabled": {"passed": true, "value": true},
    "concurrent_limit": {"passed": true, "current": 1, "max": 2},
    "maintenance_window": {"passed": true, "in_window": true},
    "cluster_status": {"passed": true, "status": "Running"},
    "backup_check": {"passed": true, "last_backup_hours": 2}
  },
  "impact_assessment": {
    "affected_resources": ["CPU", "active sessions"],
    "estimated_downtime_seconds": 0,
    "data_loss_risk": "low",
    "performance_impact": "< 5% degradation during fix",
    "rollback_complexity": "simple"
  },
  "execution_log": [
    {"time": "16:30:00", "phase": "snapshot", "status": "success"},
    {"time": "16:30:05", "phase": "canary_start", "status": "success", "percentage": 10},
    {"time": "16:35:05", "phase": "canary_observation", "status": "success", "success_rate": 0.98},
    {"time": "16:35:10", "phase": "full_rollout", "status": "success"},
    {"time": "16:35:15", "phase": "validation", "status": "success"}
  ],
  "actions_taken": [
    {
      "action": "sql_throttle",
      "sql_id": "sql-abc123",
      "original_time": "12.5s",
      "throttle_percent": 50,
      "status": "active"
    }
  ],
  "validation_results": {
    "cpu_usage": {"before": 85.2, "after": 45.3, "improvement": -46.9},
    "active_sessions": {"before": 245, "after": 180, "improvement": -26.5},
    "avg_response_time": {"before": 125, "after": 85, "improvement": -32}
  },
  "status": "success",
  "rollback_triggered": false,
  "duration_seconds": 315
}
```

## Acceptance Criteria

| # | Criteria | Detection Method |
|---|----------|------------------|
| ✓ | **安全控制检查100%通过** | 所有 Pre-check 通过 |
| ✓ | **影响评估准确率 > 90%** | 评估结果与实际影响偏差 < 10% |
| ✓ | **灰度成功率 > 95%** | Canary success rate ≥ 95% |
| ✓ | **回滚成功率 > 99%** | Rollback success rate ≥ 99% |
| ✓ | **误修复率 < 1%** | False positive remediation < 1% |
| ✓ | **平均修复时间 < 5分钟** | MTTR < 300s |

## Related References

- [AIOps Anomaly Detection](aiops-anomaly-detection.md) - 12种异常模式检测
- [AIOps Storage Prediction](aiops-storage-prediction.md) - 存储趋势预测
- [AIOps Connection Prediction](aiops-connection-prediction.md) - 连接数趋势预测
- [SQL Execution](sql-execution.md) - SQL执行能力
- [Slow Query Analysis](slow-query-analysis.md) - 慢查询分析
