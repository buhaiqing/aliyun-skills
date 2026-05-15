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
