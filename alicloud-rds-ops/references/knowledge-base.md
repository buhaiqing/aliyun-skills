# RDS Fault Pattern Knowledge Base

> **Purpose:** Fault pattern library for RDS MySQL. Each pattern follows the standardized schema.

## RDS-001 — CPU 持续 100%

| 属性 | 内容 |
|------|------|
| 触发指标 | `CpuUsage` > 95% 持续 10 min |
| 触发阈值 | CPU > 95% |
| 典型特征 | 慢查询突增，连接等待时间飙升 |
| 关联指标 | 慢 SQL 数量、活跃连接数、`IOPSUsage` |
| 根因 | 1. 全表扫描 2. 锁等待/死锁 3. 大事务 4. 缺少索引 |
| 诊断步骤 | 1. 查看慢 SQL 日志 2. 分析执行计划 3. 检查锁等待 |
| 修复方案 | 1. 临时：kill 慢查询 2. 长期：优化 SQL/添加索引 |
| 预防措施 | DAS SQL 优化建议、定期 SQL 审计、慢查询监控 |

## RDS-002 — 连接数打满

| 属性 | 内容 |
|------|------|
| 触发指标 | `ConnectionUsage` > 90% |
| 触发阈值 | 连接数 > 90% 最大连接数 持续 5 min |
| 典型特征 | 新连接被拒绝，应用报连接池耗尽错误 |
| 关联指标 | `ActiveConnections` 高、`CpuUsage` 高 |
| 根因 | 1. 连接泄漏 2. 连接池配置过大 3. 慢查询持有连接 |
| 诊断步骤 | 1. `SHOW PROCESSLIST` 2. 分析空闲连接 3. 查慢查询 |
| 修复方案 | 1. 临时：kill 空闲连接 2. 长期：优化连接池/超时配置 |
| 预防措施 | 连接数 80% 告警、设置 idle timeout |

## RDS-003 — 磁盘空间不足

| 属性 | 内容 |
|------|------|
| 触发指标 | `DiskUsage` > 85% |
| 触发阈值 | 磁盘 > 90% 持续 10 min |
| 典型特征 | 写入失败，binlog 无法写入 |
| 关联指标 | `IOPSUsage` 可能下降（写入被阻塞） |
| 根因 | 1. binlog 累积 2. 数据增长 3. 临时表 |
| 诊断步骤 | 1. 查各数据库大小 2. 查 binlog 大小 3. 查过期数据 |
| 修复方案 | 1. 清理 binlog 2. 扩盘 3. 清理无用数据 |
| 预防措施 | 磁盘 70% 预警、自动清理 binlog |

## RDS-004 — 主从延迟

| 属性 | 内容 |
|------|------|
| 触发指标 | `MySQL_ThreadRunning` + `ReplicationLag` |
| 触发阈值 | 主从延迟 > 30s 持续 5 min |
| 典型特征 | 只读实例数据不一致 |
| 关联指标 | 只读实例 CPU/IOPS 高 |
| 根因 | 1. 大事务同步 2. 只读实例配置低 3. 网络延迟 |
| 诊断步骤 | 1. `SHOW SLAVE STATUS` 2. 查同步线程状态 |
| 修复方案 | 1. 升级只读实例规格 2. 避免大事务 |
| 预防措施 | 主从延迟 10s 告警 |

## RDS-005 — 慢查询风暴

| 属性 | 内容 |
|------|------|
| 触发指标 | 慢 SQL 数量 > 10/5 min |
| 触发阈值 | 慢查询 > 10/5 min |
| 典型特征 | CPU/IOPS 飙升，响应延迟增加 |
| 关联指标 | `CpuUsage` + `IOPSUsage` 同步上升 |
| 根因 | 1. 发布新代码含低效 SQL 2. 数据量增长导致全表扫描 3. 统计信息过期 |
| 诊断步骤 | 1. DAS 慢 SQL 分析 2. 查执行计划变更 |
| 修复方案 | 1. 优化 SQL/加索引 2. 回滚代码 3. 更新统计信息 |
| 预防措施 | DAS SQL 审核、慢查询自动告警 |

## Cross-Product — RDS 过载 → ECS 应用超时 → SLB 5xx

**场景：** RDS 慢查询 → 应用连接池等待 → ECS 超时 → SLB 502

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | RDS 慢查询突增，CPU 飙升 | `alicloud-rds-ops` |
| T1 | +30s | 应用连接等待，响应超时 | `alicloud-ecs-ops` |
| T2 | +2 min | SLB 后端健康检查失败，5xx 上升 | `alicloud-slb-ops` |
| T3 | +5 min | 用户完全不可用 | `alicloud-rds-ops`（根因） |

**诊断顺序：** SLB 5xx → 查 ECS 状态 → ECS 报 RDS 连接超时 → 查 RDS 慢查询/连接数

## Cross-Product — Redis 失效 → RDS 直连过载

**场景：** Redis 实例故障 → 缓存穿透 → RDS 连接暴增 → 过载

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | Redis 主从切换/不可用 | `alicloud-redis-ops` |
| T1 | +10s | 应用回源 RDS，连接数暴涨 | `alicloud-rds-ops` |
| T2 | +1 min | RDS 连接打满，拒绝新连接 | `alicloud-rds-ops` |

**关键措施：** 应用降级策略（返回缓存默认值）、RDS 限流、缓存降级开关
