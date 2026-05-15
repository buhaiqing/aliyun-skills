# Redis Fault Pattern Knowledge Base

> **Purpose:** Fault pattern library for Redis. Each pattern follows the standardized schema.

## Redis-001 — 内存打满

| 属性 | 内容 |
|------|------|
| 触发指标 | Memory Usage > 95% |
| 触发阈值 | 内存使用率 > 95% 持续 5 min |
| 典型特征 | 写入拒绝、LRU 淘汰频繁、部分命令 OOM |
| 关联指标 | evicted_keys 飙升、rejected_connections 上升 |
| 根因 | 1. 大 key/热 key 2. 过期策略不当 3. 无过期时间 key 累积 |
| 诊断步骤 | 1. `bigkeys` 分析 2. 查过期配置 3. 查 key 数量趋势 |
| 修复方案 | 1. 临时：删除无用 key、手动触发淘汰 2. 长期：设置 TTL、拆分大 key |
| 预防措施 | 设置内存 80% 告警、大 key 扫描、key 过期策略配置 |

## Redis-002 — CPU 100%

| 属性 | 内容 |
|------|------|
| 触发指标 | CPU Utilization > 95% |
| 触发阈值 | CPU > 95% 持续 3 min |
| 典型特征 | 命令响应延迟飙升，超时连接增加 |
| 关联指标 | latency 增加、每秒连接数下降 |
| 根因 | 1. `KEYS *` / 大 key 操作 2. Lua 脚本循环 3. 大量批量操作 |
| 诊断步骤 | 1. `slowlog get` 查慢命令 2. `monitor` 查实时命令 |
| 修复方案 | 1. 终止大 key 操作 2. 拆分批量命令 |
| 预防措施 | 禁用 `KEYS` 命令、`slowlog` 定期分析 |

## Redis-003 — 连接数打满

| 属性 | 内容 |
|------|------|
| 触发指标 | Connected Clients → maxclients |
| 触发阈值 | 连接数 > 90% maxclients |
| 典型特征 | 新连接被拒绝，客户端报 `max number of clients reached` |
| 关联指标 | rejected_connections 非零 |
| 根因 | 1. 连接泄漏 2. 连接池配置过大 3. 大量微服务共享 |
| 诊断步骤 | 1. `client list` 查连接来源 2. 检查连接超时配置 |
| 修复方案 | 1. 临时：重启空闲客户端 2. 长期：优化连接池配置 |
| 预防措施 | 连接数 80% 告警、idle timeout 设置 |

## Redis-004 — 主从切换

| 属性 | 内容 |
|------|------|
| 触发指标 | 主节点不可用，从节点提升为主 |
| 触发阈值 | Sentinel/Failover 事件触发 |
| 典型特征 | 短暂读写中断（通常 < 30s），客户端连接重连 |
| 关联指标 | 主从延迟突增、failover 日志 |
| 根因 | 1. 主节点网络异常 2. 主节点 OOM 3. 计划内维护 |
| 诊断步骤 | 1. 查 Sentinel 日志 2. 确认新主节点状态 |
| 修复方案 | 1. 确认客户端重定向 2. 如非预期 → 检查网络/OOM |
| 预防措施 | 主从监控、网络连通性监控 |

## Redis-005 — 持久化阻塞

| 属性 | 内容 |
|------|------|
| 触发指标 | `rdb_last_bgsave_status` = err / `aof_last_rewrite_status` = err |
| 触发阈值 | RDB/AOF 持久化失败或延迟 > 30s |
| 典型特征 | 写入延迟增加，磁盘 IO 飙升 |
| 关联指标 | `fork_perc` (fork 耗时)、磁盘写延迟 |
| 根因 | 1. 磁盘空间不足 2. fork 内存不足 3. 磁盘 IO 瓶颈 |
| 诊断步骤 | 1. 查磁盘空间/IO 2. 查 fork 状态 3. 查 Redis 日志 |
| 修复方案 | 1. 清理磁盘 2. 降低持久化频率 3. 升级磁盘 |
| 预防措施 | 磁盘 80% 告警、持久化时间监控 |

## Cross-Product — Redis 缓存雪崩 → RDS 过载

**场景：** Redis 大量 key 同时过期 → 请求全部打向 RDS → 数据库过载

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | Redis 大量 key 同时过期/实例故障 | `alicloud-redis-ops` |
| T1 | +5s | 应用回源查询 RDS | `alicloud-rds-ops` |
| T2 | +30s | RDS CPU/连接飙升 | `alicloud-rds-ops` |
| T3 | +2 min | SLB 5xx 突增 | `alicloud-slb-ops` |

**关键措施：** TTL 分散设置、降级策略（返回缓存或默认值）、RDS 限流
