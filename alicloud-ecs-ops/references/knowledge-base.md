# ECS Fault Pattern Knowledge Base

> **Purpose:** Fault pattern library for ECS. Each pattern follows the standardized schema.

## ECS-001 — CPU 持续 100%

| 属性 | 内容 |
|------|------|
| 触发指标 | `CPUUtilization` > 95% 持续 10 min |
| 触发阈值 | CPU > 95%, Load > CPU 核数×1.5 |
| 典型特征 | CPU 使用率持续在 95%+，SSH 响应延迟增加 |
| 关联指标 | `LoadAverage` 飙升、`MemoryUtilization` 可能正常 |
| 根因 | 1. 应用代码死循环 2. 编译/打包任务 3. cron 任务集中触发 4. 挖矿进程 |
| 诊断步骤 | 1. `top` 查进程 2. 确认是否在预期窗口期 3. `iotop` 检查 IO 等待 |
| 修复方案 | 1. 临时：kill 异常进程 2. 长期：优化代码或限制 cron 并发 |
| 预防措施 | 设置 CPU > 80% 告警、限制 cron 并发数、挖矿监控 |

## ECS-002 — 内存泄漏

| 属性 | 内容 |
|------|------|
| 触发指标 | `MemoryUtilization` 单调递增，6h 未下降 |
| 触发阈值 | 内存 > 90% 且斜率 > 0.5%/h |
| 典型特征 | 内存持续增长，GC/swap 频率上升，响应变慢 |
| 关联指标 | `CPUUtilization` 可能因 GC 升高，`SwapUsage` 上升 |
| 根因 | 1. Java 对象泄漏 2. 日志累积占内存 3. 未释放的 Buffer/Connection |
| 诊断步骤 | 1. `free -m` 确认 2. Java 应用：jmap dump 分析 3. 检查日志/缓存增长 |
| 修复方案 | 1. 临时：重启应用释放内存 2. 长期：修复泄漏代码或调大堆限制 |
| 预防措施 | 定期 heap dump 分析、设置内存 80% 告警 |

## ECS-003 — 云盘 IO 瓶颈

| 属性 | 内容 |
|------|------|
| 触发指标 | `DiskReadIOPS` + `DiskWriteIOPS` > 规格上限 80% |
| 触发阈值 | IOPS > 80% 上限持续 5 min |
| 典型特征 | 应用超时增加，IO 等待 (`iowait`) 升高 |
| 关联指标 | `CPUUtilization` 中 iowait 占比高，`DiskUtilization` > 80% |
| 根因 | 1. 数据库查询未优化 2. 日志写入过多 3. 备份/迁移任务 |
| 诊断步骤 | 1. `iostat -x 1` 确认 2. 分析慢 IOPS 源 3. 检查云盘类型 |
| 修复方案 | 1. 临时：限制并发写入 2. 长期：升级 ESSD 规格 |
| 预防措施 | 使用 ESSD、设置 IOPS 监控告警 |

## ECS-004 — 实例 NotReachable

| 属性 | 内容 |
|------|------|
| 触发指标 | `InstanceNotReachable` + SSH/ICMP 超时 |
| 触发阈值 | 连续 3 次探测失败 |
| 典型特征 | SSH 超时、ICMP 不通、健康检查失败 |
| 关联指标 | `CPUUtilization` 可能 100% 或 0%（内核 panic） |
| 根因 | 1. 内核 panic 2. OOM kill 3. 安全组变更 4. 底层宿主机故障 |
| 诊断步骤 | 1. ECS 控制台查看系统日志 2. 检查安全组 3. 确认实例状态 |
| 修复方案 | 1. 强制重启 2. 如宿主机故障 → 迁移实例 |
| 预防措施 | 多可用区部署、定期快照备份 |

## ECS-005 — 安全组误配导致服务不可达

| 属性 | 内容 |
|------|------|
| 触发指标 | 外部端口无响应，SLB 健康检查失败 |
| 触发阈值 | 端口 80/443 超时 > 5s |
| 典型特征 | 实例运行正常，但从外部无法访问指定端口 |
| 关联指标 | `VPCPublicIPInRate` = 0（入流量为 0） |
| 根因 | 1. 安全组入规则被删除 2. 端口被安全组 DENY 3. 关联安全组变更 |
| 诊断步骤 | 1. `aliyun ecs DescribeSecurityGroupAttribute` 2. 对比历史规则 |
| 修复方案 | 恢复丢失的安全组入规则 |
| 预防措施 | 安全组变更审计（`alicloud-actiontrail-ops`）、禁止手动修改 |

## Cross-Product — ECS ↔ SLB 级联故障

**场景：** ECS 实例大量异常 → SLB 健康检查失败 → 5xx 飙升

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | ECS 实例 CPU 100%，服务超时 | `alicloud-ecs-ops` |
| T1 | +30s | SLB 后端健康检查标记异常 | `alicloud-slb-ops` |
| T2 | +2 min | 5xx 错误率突增，丢连接上升 | `alicloud-slb-ops` |
| T3 | +5 min | 用户感知服务不可用 | `alicloud-ecs-ops` + `alicloud-slb-ops` |

**诊断顺序：**
1. 先查 SLB 后端健康状态 → 确认 ECS 异常
2. 再查 ECS CPU/Memory → 定位根因
3. 修复 ECS 后，SLB 自动恢复

## Cross-Product — ECS ↔ VPC 网络级联故障

**场景：** VPC 路由变更 → ECS 网络不通 → 业务中断

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | VPC 路由条目被删除或修改 | `alicloud-vpc-ops` |
| T1 | +10s | ECS 无法访问外部服务/NAT | `alicloud-ecs-ops` |
| T2 | +1 min | SNAT 流量突降，SLB 后端不可达 | `alicloud-slb-ops` |

**诊断顺序：**
1. 先查 VPC 路由表 → 确认路由变更
2. 检查 ECS 实例网络 → 确认非 ECS 自身问题
3. 恢复路由配置
