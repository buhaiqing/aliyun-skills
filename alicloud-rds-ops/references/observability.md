# RDS Observability Integration

> **Purpose:** Metrics→Logs→Traces linkage for RDS MySQL instances.

## Metrics → Logs 联动

| CMS 指标异常 | DAS/SLS 查询目标 | 目的 |
|-------------|-----------------|------|
| `CpuUsage` 突增 | DAS 慢 SQL 分析 (`slowsql`) | 确认慢查询是否导致 CPU 飙升 |
| `MemoryUsage` 突增 | DAS SQL 分析（大结果集/临时表） | 确认大量排序/分组操作 |
| `ConnectionUsage` 高 | `SHOW PROCESSLIST` + 应用连接日志 | 确认连接泄漏来源应用 |
| `IOPSUsage` 高 | DAS SQL 分析 + binlog 写入日志 | 确认密集 IO 的 SQL 源 |
| `DiskUsage` > 80% | binlog 增长日志 + 数据库大小统计 | 确认磁盘占用的原因 |
| `ActiveConnections` 异常 | 慢查询与活跃连接关联分析 | 确认慢查询持有连接情况 |

### 查询示例

```bash
# DAS 获取慢 SQL 分析
aliyun das GetSlowSQLRecord \
  --DBInstanceId "{{user.rds_instance_id}}" \
  --StartTime "2026-05-16T00:00:00Z" \
  --EndTime "2026-05-16T01:00:00Z"

# 获取实例 SQL 洞察
aliyun das GetRequestAnalysis \
  --DBInstanceId "{{user.rds_instance_id}}" \
  --StartTime "2026-05-16T00:00:00Z"
```

## Metrics → Traces 联动

| CMS 指标异常 | Trace 目标 | 目的 |
|-------------|-----------|------|
| RDS 查询延迟突增 | ARMS 数据库 Trace | 定位慢 SQL 源头应用和调用链路 |
| RDS 错误率增加 | ARMS Error Span with DB error | 定位出错的应用代码和 SQL 语句 |
| 连接等待超时 | ARMS 数据库连接 Trace | 定位连接池等待的应用服务 |

## Metrics → DAS 联动

| CMS 指标异常 | DAS 诊断能力 | 目的 |
|-------------|-------------|------|
| CPU 持续高 | DAS 自治诊断 + SQL 优化建议 | AI 分析 SQL 执行计划和优化方案 |
| 连接数高 | DAS 连接分析 + 活跃会话分析 | 找出连接持有者和空闲连接 |
| 磁盘满 | DAS 空间分析 + 清理建议 | 推荐可清理的大表/binlog |
| 慢查询风暴 | DAS 慢 SQL 分析 + 索引建议 | AI 推荐最优索引方案 |

### DAS 委托调用

```bash
# 创建 DAS 诊断报告
aliyun das CreateDiagnosticReport \
  --InstanceIds "[\"{{user.rds_instance_id}}\"]" \
  --StartTime "2026-05-16T00:00:00Z" \
  --EndTime "2026-05-16T01:00:00Z"

# 获取诊断报告
aliyun das DescribeDiagnosticReport \
  --ReportId "{{output.report_id}}"
```

## 降级策略

若 DAS 不可用：
1. 直接连接 RDS 使用 `SHOW PROCESSLIST`、`EXPLAIN`、`SHOW ENGINE INNODB STATUS` 排查
2. 查询慢 SQL 日志文件
3. 使用 RDS 控制台的 SQL 洞察功能

---

## 4. 预测性可观测性

> **Purpose:** 从 Metrics → Prediction 联动，实现事前预警而非事后诊断。

### Metrics → Prediction 联动

| CMS 指标 | 预测目标 | 预测算法 | 提前预警 | 置信度 |
|----------|----------|----------|----------|--------|
| DiskUsage 趋势 | 磁盘满预测 | 线性回归 | 7 天 | 85% |
| Connections 趋势 | 连接耗尽预测 | 指数平滑 | 3 天 | 80% |
| TPS 增长趋势 | 容量瓶颈预测 | ARIMA | 14 天 | 75% |
| CPU 增长趋势 | CPU 饱和预测 | 线性回归 | 24 小时 | 90% |

### 异常检测联动

| 异常类型 | 检测方法 | 置信度阈值 | Action |
|----------|----------|------------|--------|
| 基线偏离 | 3σ 规则 | 95% | 自动触发诊断工作流 |
| 季节偏离 | 同期对比 (W-1) | 80% | 业务关联分析 |
| 突发峰值 | CUSUM 检测 | 90% | 紧急诊断 |
| 渐进增长 | 趋势分析 | 85% | 容量预警 |

### DAS 智能诊断增强

```bash
# DAS 容量预测
aliyun das CreateCapacityPrediction \
  --DBInstanceId "{{user.db_instance_id}}" \
  --PredictionType "DiskFull" \
  --PredictionDays 30 \
  --StartTime "2026-05-01T00:00:00Z" \
  --EndTime "2026-05-30T00:00:00Z"

# DAS 异常检测
aliyun das DetectAnomaly \
  --DBInstanceId "{{user.db_instance_id}}" \
  --MetricName "CpuUsage" \
  --Algorithm "BaselineDeviation" \
  --Threshold "3σ"

# DAS 智能诊断报告
aliyun das CreateDiagnosticReport \
  --InstanceIds "[\"{{user.db_instance_id}}\"]" \
  --DiagnosticType "AnomalyAnalysis" \
  --StartTime "2026-05-16T00:00:00Z" \
  --EndTime "2026-05-16T01:00:00Z"
```

### 预测报告解读

| 预测报告字段 | 含义 | Agent Action |
|--------------|------|--------------|
| `PredictionResult` | 预测结论 | Severity ≥ P1 → 立即响应 |
| `ConfidenceLevel` | 置信度 | > 90% → 执行建议；60-90% → 监控 |
| `DaysToThreshold` | 达到阈值天数 | < 7 天 → P1；< 3 天 → P0 |
| `GrowthTrend` | 增长趋势类型 | Linear → 正常；Exponential → 异常 |
| `Recommendation` | 建议行动 | 按优先级执行 |

### 预测 → 告警 → 诊断 联动流程

```
预测性分析触发
│
├─ 磁盘增长预测 → Days_to_90 < 7
│  ├─ 触发 CloudMonitor 预测告警
│  ├─ 触发诊断 (alert-diagnosis.md §1.4)
│  └─ 建议: 扩容申请流程
│
├─ CPU 增长预测 → 预计 24h 内饱和
│  ├─ 触发诊断 (alert-diagnosis.md §1.1)
│  └─ 建议: 规格升级计划
│
└─ 连接增长预测 → 预计 6h 内耗尽
   ├─ 触发诊断 (alert-diagnosis.md §1.3)
   └─ 建议: 连接泄漏排查 + 紧急扩容
```

> **详细预测分析**: 参考 [AIOps Prediction & Anomaly Detection](../references/advanced/aiops-prediction.md)
