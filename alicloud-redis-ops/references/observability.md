# Redis Observability Integration

> **Purpose:** Metrics→Logs for Redis instances.

## Metrics → Traces 联动

| CMS 指标异常 | Trace 目标 | 目的 |
|-------------|-----------|------|
| Redis 查询延迟突增 | ARMS 缓存 Trace / OpenTelemetry Redis Span | 定位慢查询和调用方服务 |
| 缓存命中率下降 | 应用 Trace 中的 `cache` 段分析 | 确认缓存穿透的源头业务 |
| 连接等待增加 | ARMS 连接池 Trace | 定位连接等待的应用实例 |

## Metrics → SLS 日志联动

| CMS 指标异常 | SLS 查询目标 | 目的 |
|-------------|-------------|------|
| `CPUUtilization` 突增 | 应用 Redis 慢日志 + `* COMMAND > 100ms` | 确认慢命令源头 |
| `MemoryUsage` 异常 | 审计日志中 `bigkey` 事件 + 应用 key 写入日志 | 定位大 key 产生方 |
| `ConnectionUsage` 高 | 应用侧连接日志 + `client list` | 定位连接泄漏的客户端 |

## Metrics → DAS 联动

| CMS 指标异常 | DAS/分析能力 | 目的 |
|-------------|-------------|------|
| 内存打满 | DAS 大 key/热 key 分析 | 识别需要优化的 key |
| CPU 100% | DAS 慢命令分析 | 定位导致 CPU 高的命令 |
| 连接满 | DAS 连接分析 | 分析哪些客户端占用了最多的连接 |

## 降级策略

若 SLS/ARMS 不可用：
1. 直接 Redis CLI `INFO`、`SLOWLOG GET`、`CLIENT LIST`、`MEMORY DOCTOR` 排查
2. 使用 `redis-cli --bigkeys` 和 `redis-cli --hotkeys`
3. 检查 Redis 实例慢日志文件
