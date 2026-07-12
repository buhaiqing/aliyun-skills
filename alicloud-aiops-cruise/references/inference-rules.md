# 链路关联推理规则表 + 修复步骤

> **用途**：Agent 在 Phase 3 中查询此表，将分散的 Analyzer 输出组合成推理链。
> **每个规则包含**：现象组合 -> 根因推理 -> 阶梯式修复步骤 -> 修复验证。

## [NOTE] 提示知识力

> **本文件是巡检报告的灵魂。** 巡检的价值不在于发现问题（监控告警已经做了），而在于输出**可执行的修复路径**。每个规则都给出了从"确认-修复-验证"的完整闭环，让看报告的人拿到后就知道第一步做什么、第二步做什么。

---

## 1. SLB -> ECS 链路

### SLB-ECS-01: SLB健康检查失败 + ECS进程正常

| 属性 | 内容 |
|---|---|
| **现象** | SLB UnhealthyServerCount > 0 AND ECS状态Running且进程正常 |
| **推理** | 网络连通性问题（安全组入方向/ACL/ECS内防火墙拦截） |
| **级别** | Warning（单个后端异常）/ Critical（>50%后端异常） |

**[FIX] 修复步骤：**

```
Step 1: 确认异常后端
  aliyun slb DescribeHealthStatus --RegionId $REGION --LoadBalancerId $LB_ID
  -> 查哪个 ECS 端口异常

Step 2: 查安全组入方向
  aliyun ecs DescribeSecurityGroupAttribute --RegionId $REGION --SecurityGroupId $SG_ID
  -> 确认 SLB 健康检查源 IP 段是否在入方向白名单中
  -> SLB 健康检查源 IP 段: 100.64.0.0/10, 10.0.0.0/8

Step 3: CloudAssistant 进 ECS 查监听
  aliyun ecs RunCommand --CommandContent "ss -tlnp | grep <端口号>"
  -> 确认服务进程是否在监听该端口

Step 4: 查 ECS 内防火墙
  [AUTO-QUIET] aliyun ecs RunCommand --CommandContent "iptables -L -n | grep <端口号>"
  -> 如有 DROP 规则，添加 ACCEPT

Step 5: 验证
  aliyun slb DescribeHealthStatus --LoadBalancerId $LB_ID
  -> 确认异常后端恢复为 normal
```

---

### SLB-ECS-03: SLB并发连接高 + 新建连接正常（连接泄漏）

| 属性 | 内容 |
|---|---|
| **现象** | ActiveConnection > 70%规格上限 AND NewConnection 正常 |
| **推理** | 长连接堆积，应用层连接泄漏（CLOSE_WAIT 过多） |
| **级别** | Warning |

**[FIX] 修复步骤：**

```
Step 1: 查 ECS 连接状态分布
  [AUTO-QUIET] aliyun ecs RunCommand --CommandContent "ss -tan | awk '{print \$1}' | sort | uniq -c"
  -> CLOSE_WAIT 过多 -> 应用未正确关闭连接
  -> TIME_WAIT 过多 -> 短连接场景正常

Step 2: 定位泄漏进程
  aliyun ecs RunCommand --CommandContent "ss -tanp | grep CLOSE_WAIT | head -10"
  -> 找到对应 PID

Step 3: 临时缓解
  SLB 侧设置连接空闲超时: aliyun slb SetLoadBalancerTCPListenerAttribute
  -> HealthCheckConnectTimeout=10, IdleTimeout=60

Step 4: 应用修复
  联系开发修复连接泄漏（不在巡检范围内，出建议即可）

Step 5: 验证
  观察 SLB ActiveConnection 是否回落
```

---

## 2. ECS 层

### ECS-01: CPU和内存双高

| 属性 | 内容 |
|---|---|
| **现象** | CPU > 70% AND memory_usedutilization(需agent) > 80% |
| **推理** | ECS 资源双重瓶颈，需定位消耗资源的进程 |
| **级别** | Warning（>70%）/ Critical（>85%） |

**[FIX] 修复步骤：**

```
Step 1: CloudAssistant 查 TOP 进程
  [AUTO-QUIET] aliyun ecs RunCommand --CommandContent "ps aux --sort=-%cpu | head -10"
  -> 定位 CPU 消耗最高的进程

Step 2: 查内存消耗
  [AUTO-QUIET] aliyun ecs RunCommand --CommandContent "ps aux --sort=-%mem | head -10"
  -> 定位内存消耗最高的进程

Step 3: 分析是否为预期行为
  -> 如果是业务高峰期 -> 监控趋势，考虑升配
  -> 如果是异常进程 -> 进一步排查（查 crontab / 入侵检测）
  -> 如果是内存泄漏 -> 联系开发

Step 4: 升配（如需）
  -> 控制台操作或 aliyun ecs ModifyInstanceSpec
  -> [WARN] 仅出建议，不自动执行！

Step 5: 验证
  观察 30min 后 CPU/内存是否回落
```

---

## 3. RDS 数据库层

### RDS-01: CPU高 + 慢查询多

| 属性 | 内容 |
|---|---|
| **现象** | RDS CPUUsage > 80% AND SlowQueryCount > 100/min |
| **推理** | 慢SQL导致CPU飙升，需定位慢SQL并优化 |
| **级别** | Critical |

**[FIX] 修复步骤：**

```
Step 1: DAS 查慢 SQL 明细（JIT Go SDK）
  -> 从 assets/code-snippets/ 动态生成 das_slow_query.go
  -> INSTANCE_ID=rm-xxx go run das_slow_query.go
  -> 获取 SqlText、执行次数、平均耗时

Step 2: 分析慢 SQL 类型
  -> 全表扫描（无 WHERE 或 WHERE 无索引）-> 加索引
  -> 大排序/大聚合 -> 优化 SQL 或加缓存
  -> 锁等待 -> 查 DAS 锁分析

Step 3: 临时缓解
  -> 联系业务方 Kill 长时间运行的会话（需谨慎）
  -> 或启用 DAS SQL 限流（高危操作，需确认）

Step 4: 根因修复
  -> 创建索引: CREATE INDEX ... ON ... (column)
  -> 改写 SQL: 避免 SELECT *，避免函数索引

Step 5: 验证
  观察 RDS CPU 是否回落，慢查询数是否下降
```

### RDS-04: 磁盘使用率超标

| 属性 | 内容 |
|---|---|
| **现象** | RDS DiskUsage > 85% |
| **推理** | 磁盘即将写满，数据库可能进入只读模式 |
| **级别** | Warning（>75%）/ Critical（>90%） |

**[FIX] 修复步骤：**

```
Step 1: 紧急判断
  -> DiskUsage > 95%: 立即扩容（否则数据库马上只读）
  -> DiskUsage 85-95%: 先查空间构成再操作

Step 2: DAS 查空间分析（JIT Go SDK）
  -> 查数据文件、日志文件、临时文件占比
  -> 查最大表 TOP 10

Step 3: 选择修复策略（按优先级）
  ├─ 方案A: 存储空间扩容（最快，不停服）
  │   [AUTO-CONFIRM] aliyun rds ModifyDBInstanceSpec --DBInstanceId rm-xxx --DBInstanceStorage 200  (待 L2 准入)
  │
  ├─ 方案B: 清理 binlog（仅适用 MySQL）
  │   [AUTO-NOTIFY] CALL mysql.rds_cycle_binlog();  -- 清理已消费的 binlog（命中 W-02）
  │   [SUGGESTED] aliyun rds ModifyDBInstanceSpec --BinlogRetentionHours 24
  │
  ├─ 方案C: 清理大表归档
  │   -> 导出历史数据到 OSS，删除本地表
  │   -> DTS 同步到分析库后清理
  │
  └─ 方案D: 设置自动清理策略
      -> 开启 RDS 自动扩容（如有）
      -> 设置 CloudMonitor 磁盘告警（85%触发）

Step 4: 验证
  aliyun cms DescribeMetricList --Namespace acs_rds_dashboard --MetricName DiskUsage ...
  -> 确认磁盘使用率开始下降
```

---

## 4. Redis 层

### REDIS-01: 内存高 + 逐出

| 属性 | 内容 |
|---|---|
| **现象** | Redis MemoryUsage > 80% AND 逐出次数 > 0 |
| **推理** | 内存不足触发 maxmemory-policy 淘汰，可能影响命中率 |
| **级别** | Warning |

**[FIX] 修复步骤：**

```
Step 1: DAS 缓存分析查大key（JIT Go SDK）
  INSTANCE_ID=r-xxx go run das_cache_analysis.go
  -> 获取大key列表（key名称、类型、大小）

Step 2: 判断大key类型
  -> String 大 value: 压缩 value 或拆分 key
  -> Hash 大 key: 分桶（hash按field拆分）
  -> List/Set 大 key: 限制长度或改为增量处理

Step 3: 选择修复策略
  ├─ 方案A: 惰性删除（逐出策略改为 allkeys-lru）
  │   [AUTO-NOTIFY] aliyun r-kvstore ModifyInstanceConfig --Config '{"maxmemory-policy":"allkeys-lru"}'  (命中 W-03)
  │
  ├─ 方案B: 本地缓存兜底
  │   在应用层加本地缓存（Caffeine/Guava），减少 Redis 压力
  │
  └─ 方案C: 升配
      如持续增长，考虑升配 Redis 规格

Step 4: 验证
  -> 观察 MemoryUsage 是否稳定
  -> 观察 evicted_keys 指标是否归零
```

---

## 5. NAT 层

### NAT-01: SNAT连接高 / 端口分配失败

| 属性 | 内容 |
|---|---|
| **现象** | EniPacketsDropPortAllocationFail > 0 OR SnatConnection > 80%规格上限 |
| **推理** | SNAT 端口即将耗尽——阿里云 NAT 网关最常见的故障模式 |
| **级别** | Critical（端口分配失败 > 0 即 Critical） |

**[FIX] 修复步骤：**

```
Step 1: 确认端口耗尽
  aliyun cms DescribeMetricList --Namespace acs_nat_gateway --MetricName EniPacketsDropPortAllocationFail
  -> >0 确认出现过端口分配失败

Step 2: 查当前 SNAT 连接数
  aliyun cms DescribeMetricList --Namespace acs_nat_gateway --MetricName SnatConnection
  -> 确认接近规格上限（Small=10000, Medium=50000, Large=200000）

Step 3: 选择修复策略
  ├─ 方案A: 升配 NAT 网关（最快）
  │   -> 控制台操作或 API
  │   [WARN] 仅出建议
  │
  ├─ 方案B: 增加 SNAT IP
  │   -> 每个 SNAT IP 提供 65535 个端口
  │   aliyun vpc CreateSnatEntry --SnatIp "x.x.x.x"
  │
  ├─ 方案C: 应用侧优化
  │   -> 启用连接复用（Keep-Alive）
  │   -> 减少短连接，改为长连接
  │
  └─ 方案D: 增加 NAT 网关（高可用）
      创建第二个 NAT 网关 + 拆分 SNAT 条目

Step 4: 验证
  -> 观察 EniPacketsDropPortAllocationFail 是否归零
  -> 观察 SnatConnection 是否回落
```

---

## 5.1 主机 IO 层

### ECS-IO-01: IOPS/吞吐达云盘上限

| 属性 | 内容 |
|---|---|
| **现象** | iostat %util > 80% AND DiskReadIOPS/DiskWriteIOPS > 70% 云盘上限 |
| **推理** | 云盘 IOPS 或吞吐已达规格上限，应用 IO 请求排队 |
| **级别** | Warning（%util > 60%）/ Critical（%util > 80%） |
| **适用场景** | 普通应用服务器、Nginx 服务器 |

**[FIX] 修复步骤：**

```
Step 1: 确认云盘类型和上限
  aliyun ecs DescribeDisks --InstanceId $INST_ID
  -> 查 Category（cloud_essd / cloud_ssd / cloud_efficiency）
  -> 对照规格上限：PL0(10000IOPS/180MB), PL1(50000IOPS/350MB), PL2(100000IOPS/750MB), PL3(1000000IOPS/4000MB)

Step 2: 定位 IO 大户
  [AUTO-QUIET] aliyun ecs RunCommand --CommandContent "iotop -b -o -n 1"
  -> 找到写入/读取最多的进程

Step 3: 选择修复策略
  ├─ 方案A: 升级云盘类型（推荐，不停服）
  │   -> 控制台操作或 aliyun ecs ModifyDiskSpec
  │   [WARN] 仅出建议，不自动执行
  │
  ├─ 方案B: 日志写入优化（Nginx 场景）
  │   -> access_log buffer=32k flush=5s
  │   -> error_log warn;  # 降低日志级别
  │
  └─ 方案C: 应用层优化
      -> 批量写入替代逐条写入
      -> 异步 IO 替代同步 IO

Step 4: 验证
  aliyun cms DescribeMetricList --MetricName DiskReadIOPS / DiskWriteIOPS ...
  -> 确认 IOPS 回落到安全水位
```

---

### ECS-IO-02: 内存不足导致 Swap IO

| 属性 | 内容 |
|---|---|
| **现象** | SwapUsed > 0 AND kswapd0 进程 IO 高 AND memory_usedutilization > 90% |
| **推理** | 内存不足触发 swap 换入换出，IO wait 飙升 |
| **级别** | Warning（SwapUsed > 100MB）/ Critical（SwapUsed > 500MB） |
| **适用场景** | 普通应用服务器（Java/Node.js 内存密集型应用） |

**[FIX] 修复步骤：**

```
Step 1: 确认内存和 Swap 状态
  free -h
  cat /proc/meminfo | grep -E "SwapTotal|SwapFree|Dirty"

Step 2: CloudAssistant 查内存大户
  [AUTO-QUIET] aliyun ecs RunCommand --CommandContent "ps aux --sort=-%mem | head -10"
  -> 定位内存消耗最高的进程

Step 3: 选择修复策略
  ├─ 方案A: 临时释放（立即生效）
  │   -> 重启内存泄漏的应用
  │   -> 清理缓存：echo 3 > /proc/sys/vm/drop_caches（谨慎）
  │
  ├─ 方案B: 长期优化
  │   -> 升级实例内存规格
  │   -> 优化应用内存使用（JVM -Xmx 调整）
  │
  └─ 方案C: 限制 Swap
      -> sysctl vm.swappiness=10  # 降低 swap 倾向

Step 4: 验证
  free -h  # 确认 SwapUsed 下降
  iostat -xmd 2 1  # 确认 IO wait 下降
```

---

### ECS-IO-03: 日志 IO 与数据 IO 冲突

| 属性 | 内容 |
|---|---|
| **现象** | DiskWriteIOPS > 70% 上限 AND iotop 显示多个写入进程（nginx + mysql 等） |
| **推理** | Nginx/应用日志写入 + 数据库写入同时高 IO，IO 延迟叠加 |
| **级别** | Warning（读写比 > 10:1 或 < 1:10）/ Critical（IOPS > 85%） |
| **适用场景** | Nginx + 数据库同机部署、日志未做缓冲 |

**[FIX] 修复步骤：**

```
Step 1: 确认 IO 冲突源
  iotop -b -o -n 3
  -> 确认哪些进程在争抢 IO

Step 2: 选择修复策略
  ├─ 方案A: Nginx 日志缓冲（推荐）
  │   -> access_log buffer=32k flush=5s;
  │   -> error_log /var/log/nginx/error.log warn;
  │
  ├─ 方案B: 日志分离到独立云盘
  │   -> 创建独立云盘挂载到 /var/log
  │   -> 日志和数据 IO 物理隔离
  │
  ├─ 方案C: 数据库 WAL 分盘
  │   -> MySQL: innodb_log_group_home_dir 指向独立云盘
  │   -> PostgreSQL: pg_wal 独立挂载
  │
  └─ 方案D: 日志异步写入
      -> 应用层异步写日志（Log4j2 AsyncAppender / Logback AsyncAppender）

Step 3: 验证
  iotop -b -o -n 1  # 确认 IO 冲突缓解
  iostat -xmd 2 1   # 确认 %util 和 await 下降
```

---

### ECS-IO-04: 文件系统层 IO 异常

| 属性 | 内容 |
|---|---|
| **现象** | iostat await > 20ms AND iotop 无 > 10% IO 的进程 AND jbd2/kjournald IO 高 |
| **推理** | ext4 journal 延迟、inode 满或文件系统碎片化 |
| **级别** | Warning（await > 10ms）/ Critical（await > 50ms） |
| **适用场景** | ext4 文件系统、大量小文件场景 |

**[FIX] 修复步骤：**

```
Step 1: 确认文件系统类型
  df -hT /
  mount | grep " / "

Step 2: 检查 journal 和 inode
  tune2fs -l /dev/vda1 | grep "Journal"  # ext4 journal
  df -i /                                  # inode 使用率

Step 3: 选择修复策略
  ├─ 方案A: 调整 journal 大小
  │   tune2fs -J size=128 /dev/vda1  # 增大 journal
  │
  ├─ 方案B: 清理 inode
  │   find / -xdev -type f | wc -l  # 统计文件数
  │   删除大量小文件或归档
  │
  ├─ 方案C: 优化挂载选项
  │   mount -o remount,noatime /  # 减少 atime 写入
  │
  └─ 方案D: 切换文件系统（新盘推荐）
      -> xfs 比 ext4 在高并发 IO 场景下 journal 更高效

Step 4: 验证
  iostat -xmd 2 1   # 确认 await 下降
  df -i /            # 确认 inode 使用率正常
```

---

### ECS-IO-05: IO Wait 高但 %util 正常

| 属性 | 内容 |
|---|---|
| **现象** | iostat await > 10ms AND %util < 60% AND LoadAverage > CPU×2 |
| **推理** | IO 调度器不合理或脏页回写阻塞，非 IOPS 瓶颈 |
| **级别** | Warning（await > 10ms）/ Critical（await > 50ms） |
| **适用场景** | 调度器为 cfq 或 deadline 但场景不匹配 |

**[FIX] 修复步骤：**

```
Step 1: 检查 IO 调度器
  cat /sys/block/*/queue/scheduler
  -> 云盘推荐: mq-deadline 或 none（NVMe）

Step 2: 检查脏页
  cat /proc/meminfo | grep -E "Dirty|Writeback"
  -> Dirty > 100MB 说明脏页回写慢

Step 3: 选择修复策略
  ├─ 方案A: 切换 IO 调度器
  │   echo mq-deadline > /sys/block/vda/queue/scheduler
  │   -> 持久化：编辑 /etc/default/grub
  │
  ├─ 方案B: 调整脏页参数
  │   sysctl vm.dirty_ratio=10
  │   sysctl vm.dirty_background_ratio=5
  │
  └─ 方案C: 添加 noatime
      mount -o remount,noatime /

Step 4: 验证
  iostat -xmd 2 1  # 确认 await 下降且 LoadAverage 回落
  uptime            # 确认 LoadAverage 正常
```

---

### ECS-IO-06: inode 耗尽

| 属性 | 内容 |
|---|---|
| **现象** | df -i / 显示 inode 使用率 > 95% |
| **推理** | inode 耗尽导致无法创建新文件，即使磁盘空间充足 |
| **级别** | Warning（> 80%）/ Critical（> 95%） |
| **适用场景** | 大量小文件场景（日志、缓存、session 文件） |

**[FIX] 修复步骤：**

```
Step 1: 确认 inode 使用率
  df -i /
  -> IUse% > 95% 确认 inode 耗尽

Step 2: 定位小文件大户
  find / -xdev -type f | awk -F/ '{print $1"/"$2}' | sort | uniq -c | sort -rn | head -10
  -> 找到哪个目录下文件最多

Step 3: 选择修复策略
  ├─ 方案A: 清理临时文件
  │   -> /tmp, /var/tmp, /var/cache
  │
  ├─ 方案B: 清理日志
  │   -> 大量小日志文件: find /var/log -name "*.log.*" -mtime +7 -delete
  │
  ├─ 方案C: 归档到 OSS
  │   -> 历史小文件上传 OSS 后删除本地
  │
  └─ 方案D: 重建文件系统（极端情况）
      -> 格式化时增大 inode 密度: mkfs.ext4 -i 4096 /dev/vda1
      [WARN] 需停服，仅在新盘场景使用

Step 4: 验证
  df -i /  # 确认 inode 使用率下降
```

---

## 6. ACK 容器层

### ACK-LIMITS-01: CPU Limits 超分 + 实际负载低

| 属性 | 内容 |
|---|---|
| **现象** | `node.cpu.limit / node.cpu.capacity > 120%` AND `node.cpu.usage_rate / node.cpu.capacity < 60%` |
| **推理** | Pod CPU limit 设置虚高（开发者习惯性填大值），导致节点"数字上超分"但实际压力不大 |
| **级别** | Warning |

**[FIX] 修复步骤：**

```
Step 1: 确认超分节点
  node.cpu.limit / node.cpu.capacity = {ratio}%  -> 超分 {over} core

Step 2: 钻取 Top 5 高 limit Pod
  pod.cpu.limit -> 按节点过滤 -> 按 limit 倒排
  -> 得到 [{pod, namespace, limit, usage, oversale_rate}, ...]

Step 3: 判断每个 Pod 是否可优化
  ┌─ usage_rate / limit < 30% -> 明显虚高，建议降 limit 至 {usage*2}
  ├─ usage_rate / limit 30~60% -> 可优化，建议降 limit 至 {usage*1.5}
  └─ usage_rate / limit > 60% -> 合理，保持不动

Step 4: 降 limit（需用户确认）
  kubectl edit deployment {name} -n {ns} --cpu-limits={new_value}
  -> 或通过 ACK 控制台修改

Step 5: 验证
  重新采集 node.cpu.limit / node.cpu.capacity -> 确认超卖比下降
```

---

### ACK-LIMITS-02: CPU Limits 超分 + 实际负载高

| 属性 | 内容 |
|---|---|
| **现象** | `node.cpu.limit / node.cpu.capacity > 120%` AND `node.cpu.usage_rate / node.cpu.capacity > 70%` |
| **推理** | 双重风险：超分 + 高负载，流量尖峰必然触发 CPU Throttling |
| **级别** | Critical |

**[FIX] 修复步骤：**

```
Step 1: 紧急判断
  查看 node.cpu.usage_rate 是否接近 node.cpu.limit
  -> 如果 usage 已超过 node.cpu.capacity * 0.8 -> 有 immediate Throttling 风险

Step 2: 紧急扩容（需用户确认）
  方案A: 节点池扩容（水平扩展，加节点）
    aliyun cs POST /clusters/{clusterId}/nodepools/{poolId} --body '{{"desired_size": {new_size}}}'
  方案B: 增加 Pod 副本数 + 降单副本 limit
    kubectl scale deployment {name} -n {ns} --replicas={current*2}
    -> 配合降 limit 确保新的总 limit 不超

Step 3: 长期治理
  对高 limit 低 usage 的 Pod 降 limit（同 ACK-LIMITS-01 Step 3）
  实施 HPA 让 Pod 自动扩缩

Step 4: 验证
  观察 5min 后 node.cpu.usage_rate 是否回落，Throttling 是否消失
```

---

### ACK-LIMITS-03: Memory Limits 超分

| 属性 | 内容 |
|---|---|
| **现象** | `node.memory.limit / node.memory.capacity > 120%` |
| **推理** | 内存超分，物理内存有限不会被 swap 消化，OOMKill 风险真实存在 |
| **级别** | Warning（>120%）/ Critical（>150%） |

**[FIX] 修复步骤：**

```
Step 1: 查 OOMKill 记录
  acs_k8s -> pod 维度 -> 查 OOMKill 事件
  -> 或通过 DescribeClusterEvents 查近期 OOM 事件

Step 2: 查节点内存实际 usage
  node.memory.working_set / node.memory.capacity -> 实际水位
  ┌─ 实际水位 < 70% -> 超分但无实际压力，可优化 limit
  └─ 实际水位 > 70% -> 有实质 OOM 风险 -> 立即扩容

Step 3: 钻取高内存 limit Pod
  pod.memory.limit 倒排 -> 结合 pod.memory.working_set 判断真实需求

Step 4: 修复
  -> 降低虚高 memory limit
  -> 对确需大内存的 Pod 增加 resource reservation（保证节点有足够 allocatable）

Step 5: 验证
  观察 24h 内 OOMKill 事件是否归零
```

---

## 7. 安全层

### SG-01/SG-02: 安全组 0.0.0.0/0 高危规则

| 属性 | 内容 |
|---|---|
| **现象** | 安全组规则 SourceCidrIp=0.0.0.0/0 AND PortRange ∈ {22,3389,3306,6379,5432} |
| **推理** | 管理/数据库端口暴漏公网，暴力破解和数据泄露高风险 |
| **级别** | Critical（存在即 Critical） |

**[FIX] 修复步骤：**

```
Step 1: 确认规则详情
  aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId $SG_ID
  -> 找到具体哪条规则是 0.0.0.0/0

Step 2: 判断是否真的需要公网访问
  -> 不需要: 直接删除该规则
    aliyun ecs RevokeSecurityGroup --SecurityGroupId $SG_ID
    --SourceCidrIp 0.0.0.0/0 --PortRange 22/22 --IpProtocol tcp
  -> 需要但可限制来源: 替换为指定 IP 段
  -> 必须公网: 使用 CloudFirewall 统一管控

Step 3: 替代方案（推荐）
  -> SSH/RDP: 使用阿里云堡垒机（Bastionhost）
  -> 数据库: 使用 DMS（数据管理服务）
  -> API: 使用 API 网关 + WAF

Step 4: 验证
  aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId $SG_ID
  -> 确认 0.0.0.0/0 规则已清除
```

---

## 8. 综合链路

### FULL-01: 全链路正常但用户报障

| 属性 | 内容 |
|---|---|
| **现象** | 所有资源指标正常 + 用户报障（慢/不可用） |
| **推理** | 非阿里云基础设施问题 -> 应用层或外部依赖 |
| **级别** | Info |

**[FIX] 修复步骤：**

```
Step 1: 查 ActionTrail 是否有配置变更
  aliyun actiontrail LookupEvents --StartTime $START --EndTime $END
  -> 近期有人改过配置？回滚试试

Step 2: 查 SLS 应用日志
  -> 应用错误率上升？慢接口分布？
  -> 需要 SLS 访问权限

Step 3: 查 APM（ARMS）
  -> 如果有接入 ARMS 应用监控，查看调用链
  -> 根因通常在应用代码、数据库慢查询、外部 API

Step 4: 查第三方依赖
  -> 是否依赖第三方 API？
  -> 是否依赖本地 IDC 机房？
  -> DNS 解析是否正常？

结论: "阿里云基础设施正常，建议查应用层或外部依赖"
```

---

## 推理优先级规则

```
1. Safety 优先：SG-01/02 端口暴漏 -> 立即标记 Critical
2. 容量优先：RDS-04 磁盘 > 90% -> 立即标记 Critical
3. 链路上游优先：SLB 异常先于 ECS 排查
4. 数据层优先于计算层：RDS 异常比 ECS 异常更影响用户感知
5. 确认性优先：有明确证据的排前面，"可能"的排后面
6. **ACK 超分优先**：limits 超卖比 > 150% 且实际负载 > 70% -> 立即标记 Critical
```