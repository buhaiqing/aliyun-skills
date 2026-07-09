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

> **完整诊断指南**：[host-io-inspection.md](host-io-inspection.md)

### 003-A — IOPS/吞吐达云盘上限

| 属性 | 内容 |
|------|------|
| 触发指标 | `DiskReadIOPS` + `DiskWriteIOPS` > 规格上限 80% |
| 触发阈值 | IOPS > 80% 上限持续 5 min |
| 典型特征 | 应用超时增加，IO 等待 (`iowait`) 升高 |
| 关联指标 | `CPUUtilization` 中 iowait 占比高，iostat `%util` > 80% |
| 根因 | 1. 数据库查询未优化 2. 日志写入过多 3. 备份/迁移任务 |
| 诊断步骤 | 1. `iostat -x 1` 确认 %util 和 await 2. `iotop` 定位写入大户 3. 确认云盘类型和规格上限 |
| 修复方案 | 1. 临时：限制并发写入 2. 长期：升级 ESSD 规格（PL0→PL1→PL2→PL3） |
| 预防措施 | 使用 ESSD、设置 IOPS 监控告警 |

### 003-B — IO Wait 高（%util 正常）

| 属性 | 内容 |
|------|------|
| 触发指标 | iostat `await` > 10ms 但 `%util` < 60% |
| 触发阈值 | await > 50ms 且 %util < 60% 持续 5 min |
| 典型特征 | CPU 使用率正常但 LoadAverage 飙升（Load > CPU×2），应用响应慢 |
| 关联指标 | `LoadAverage` 升高，`CPUUtilization` 中 iowait 占比高 |
| 根因 | 1. IO 调度器不合理 2. 文件系统 journal 延迟 3. 脏页回写阻塞 |
| 诊断步骤 | 1. `cat /sys/block/*/queue/scheduler` 检查调度器 2. `cat /proc/meminfo \| grep Dirty` 检查脏页 3. `mount \| grep " / "` 检查挂载选项 |
| 修复方案 | 1. 确认调度器为 mq-deadline 或 none 2. 调整 vm.dirty_ratio/vm.dirty_background_ratio 3. 检查文件系统挂载选项（noatime） |
| 预防措施 | 定期检查 IO wait 趋势、设置 LoadAverage > CPU×2 告警 |

### 003-C — 读写比严重失衡

| 属性 | 内容 |
|------|------|
| 触发指标 | `DiskReadIOPS` / `DiskWriteIOPS` > 10:1 或 < 1:10 |
| 触发阈值 | 读写比 > 10:1（读密集）或 < 1:10（写密集） |
| 典型特征 | 读密集：缓存命中率低、随机读多；写密集：日志/数据库写入集中 |
| 关联指标 | 网络带宽（读密集可能伴随高网络入流量）、内存使用率（读密集可能内存不足） |
| 根因 | 1. 缓存未命中导致大量磁盘读 2. 日志写入过多 3. 数据库 WAL 写入 |
| 诊断步骤 | 1. `iotop -b -o -n 3` 定位读/写大户 2. 检查应用缓存命中率 3. 检查日志量 |
| 修复方案 | 1. 读密集：增大缓存、优化索引 2. 写密集：优化日志策略、批量写入 |
| 预防措施 | 监控读写比趋势、设置读写比异常告警 |

### 003-D — 内存不足导致 Swap IO

| 属性 | 内容 |
|------|------|
| 触发指标 | `SwapUsage` > 0 且 `kswapd0` 进程 IO 高 |
| 触发阈值 | SwapUsed > 100MB 且持续 > 10 min |
| 典型特征 | 内存使用率 > 90%，Swap 频繁换入换出，IO wait 飙升 |
| 关联指标 | `MemoryUtilization` > 90%，iostat 显示 `kswapd0` 高 IO |
| 根因 | 1. 应用内存泄漏 2. 实例内存规格不足 3. JVM 堆设置过大 |
| 诊断步骤 | 1. `free -h` 确认 Swap 使用 2. `cat /proc/meminfo \| grep Swap` 3. `iotop` 确认 kswapd0 IO |
| 修复方案 | 1. 临时：重启释放内存 2. 长期：升级实例内存规格 3. 优化应用内存使用 |
| 预防措施 | 设置内存 > 85% 告警、定期检查 Swap 使用 |

### 003-E — 日志 IO 与数据 IO 冲突

| 属性 | 内容 |
|------|------|
| 触发指标 | Nginx/应用日志写入 + 数据库写入同时高 IO |
| 触发阈值 | DiskWriteIOPS > 70% 上限且同时有多个写入进程 |
| 典型特征 | Nginx access_log 写入频繁 + 数据库写入，IO 延迟叠加 |
| 关联指标 | `DiskWriteBPS` 高，`DiskWriteIOPS` 高，多个进程争抢 IO |
| 根因 | 1. 日志和数据共用同一块云盘 2. 日志写入未做缓冲 3. 数据库 WAL + 数据文件共盘 |
| 诊断步骤 | 1. `iotop` 确认写入进程分布 2. `df -hT` 确认文件系统布局 3. 检查日志写入模式 |
| 修复方案 | 1. 日志写入加 buffer（Nginx: `buffer=32k flush=5s`） 2. 日志分离到独立云盘 3. 数据库 WAL 和数据分盘 |
| 预防措施 | 日志和数据分盘部署、日志异步写入 |

### 003-F — 文件系统层 IO 异常

| 属性 | 内容 |
|------|------|
| 触发指标 | iostat `await` 高但无明显 IO 大户进程 |
| 触发阈值 | await > 20ms 且 iotop 无 > 10% IO 的进程 |
| 典型特征 | IO 延迟高但找不到明显写入大户，jbd2/kjournald 进程 IO 高 |
| 关联指标 | jbd2 进程 IO 高、inode 使用率可能高 |
| 根因 | 1. ext4 journal 延迟 2. inode 满 3. 文件系统碎片化 4. mount 选项不当 |
| 诊断步骤 | 1. `iotop` 检查 jbd2/kjournald IO 2. `df -i /` 检查 inode 3. `tune2fs -l /dev/vda1` 检查 journal 4. `mount \| grep " / "` 检查挂载选项 |
| 修复方案 | 1. 调整 journal 大小：`tune2fs -J size=128 /dev/vda1` 2. 清理 inode：删除大量小文件 3. 调整挂载选项：添加 noatime |
| 预防措施 | 使用 xfs（比 ext4 journal 更高效）、设置 inode 监控告警 |

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
