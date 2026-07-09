# 主机 IO 巡检与诊断指南

> **用途**：当 ECS 实例出现磁盘 IO 疑似异常时，Agent 按此指南从云监控→OS 层→文件系统层逐层下钻，定位 IO 根因。
> **适用场景**：普通应用服务器、Nginx 服务器、日志服务器等 Linux ECS 实例。
> **前置条件**：ECS 实例处于 Running 状态，已安装 Cloud Assistant Agent。

---

## 1. 云监控层：确认 IO 异常

> 先通过 CloudMonitor 确认是否存在 IO 异常，避免盲目下钻。

### 1.1 可用 IO 指标

| 指标名 | 含义 | 命名空间 | 说明 |
|--------|------|----------|------|
| `DiskReadBPS` | 磁盘读取吞吐 (Bytes/s) | `acs_ecs_dashboard` | 云盘级别 |
| `DiskWriteBPS` | 磁盘写入吞吐 (Bytes/s) | `acs_ecs_dashboard` | 云盘级别 |
| `DiskReadIOPS` | 磁盘读取 IOPS | `acs_ecs_dashboard` | 云盘级别 |
| `DiskWriteIOPS` | 磁盘写入 IOPS | `acs_ecs_dashboard` | 云盘级别 |
| `DiskUtilization` | 磁盘使用率 (%) | `acs_ecs_dashboard` | 部分实例类型可用 |

> **注意**：CloudMonitor 的 IO 指标是**云盘级别**，不是块设备级别。如果一个 ECS 挂载了多块云盘，需要分别查询。

### 1.2 采集命令

```bash
INSTANCE_ID="{{user.instance_id}}"
REGION="{{env.ALIBABA_CLOUD_REGION_ID}}"
START_TIME=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# 读 IOPS
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName DiskReadIOPS \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 300 \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  | jq '[.Datapoints | fromjson | [.[].Maximum] | max // 0] | add'

# 写 IOPS
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName DiskWriteIOPS \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 300 \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  | jq '[.Datapoints | fromjson | [.[].Maximum] | max // 0] | add'

# 读吞吐 (MB/s)
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName DiskReadBPS \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 300 \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  | jq '[.Datapoints | fromjson | [.[].Maximum] | max // 0] | add / 1048576'

# 写吞吐 (MB/s)
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName DiskWriteBPS \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 300 \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  | jq '[.Datapoints | fromjson | [.[].Maximum] | max // 0] | add / 1048576'
```

### 1.3 云盘类型与 IO 上限参考

| 云盘类型 | IOPS 上限 | 吞吐上限 | 适用场景 |
|----------|-----------|----------|----------|
| cloud (HDD) | 数百 | 数十 MB/s | 低频访问 |
| cloud_efficiency (SATA SSD) | ~10,000 | ~180 MB/s | 一般应用 |
| cloud_ssd | ~20,000 | ~300 MB/s | 数据库 |
| cloud_essd PL0 | ~10,000 | ~180 MB/s | 轻量应用 |
| cloud_essd PL1 | ~50,000 | ~350 MB/s | 数据库 |
| cloud_essd PL2 | ~100,000 | ~750 MB/s | 高性能数据库 |
| cloud_essd PL3 | ~1,000,000 | ~4,000 MB/s | 核心数据库 |

> **判定**：如果 CloudMonitor IOPS/吞吐已接近云盘类型上限 → IO 瓶颈在存储层，考虑升级云盘。

---

## 2. OS 层：iostat 深度分析

> 当 CloudMonitor 确认 IO 异常后，通过 Cloud Assistant 进入 ECS 内部做块设备级分析。

### 2.1 iostat 核心字段解读

```bash
# 安装 sysstat（如未安装）
command -v iostat >/dev/null 2>&1 || yum install -y sysstat || apt-get install -y sysstat

# 采集 5 次，间隔 2 秒
iostat -xmd 2 5
```

| 字段 | 含义 | 告警阈值 |
|------|------|----------|
| `%util` | 设备繁忙百分比（有 IO 请求占总时间比例） | > 80% 严重，> 60% 关注 |
| `await` | IO 请求平均等待时间 (ms) | > 10ms 关注，> 50ms 严重 |
| `svctm` | IO 请求平均服务时间 (ms) — **已废弃**，仅供参考 | — |
| `avgqu-sz` | 平均队列长度 | > 4 关注，> 16 严重 |
| `r_await` | 读请求平均等待时间 (ms) | > 10ms 关注 |
| `w_await` | 写请求平均等待时间 (ms) | > 15ms 关注（写通常比读慢） |
| `rrqm/s` | 每秒读合并请求数 | 合并率高说明顺序读多 |
| `wrqm/s` | 每秒写合并请求数 | 合并率高说明顺序写多 |
| `r/s` | 每秒读请求数 | — |
| `w/s` | 每秒写请求数 | — |
| `rkB/s` | 每秒读吞吐 (KB) | — |
| `wkB/s` | 每秒写吞吐 (KB) | — |

### 2.2 关键诊断模式

#### 模式 A：%util 高 + await 正常 (< 5ms)
```
结论：IO 请求量大但响应快，云盘性能充足
原因：正常高负载，非瓶颈
处理：观察，无需处理
```

#### 模式 B：%util 高 + await 高 (> 10ms)
```
结论：IO 请求等待严重
原因：云盘 IOPS/吞吐到达上限，或 IO 调度不合理
处理：
  1. 确认云盘类型（iostat 显示的设备名 → 阿里云控制台查云盘类型）
  2. 如已达上限 → 升级云盘
  3. 如未达上限 → 检查 IO 调度器和文件系统
```

#### 模式 C：%util 正常 + await 异常高
```
结论：IO 不繁忙但等待时间长
原因：IO 调度器问题、文件系统 journal 延迟、或后台 flush/fdatasync 阻塞
处理：
  1. 检查 IO 调度器：cat /sys/block/*/queue/scheduler
  2. 检查 journal 模式：tune2fs -l /dev/vda1 | grep "Default mount options"
  3. 检查 dirty page 回写：cat /proc/meminfo | grep Dirty
```

#### 模式 D：读写比严重失衡
```
结论：读或写单方向压力过大
原因：日志写入过多 / 读放大 / 缓存未命中
处理：
  1. iotop 定位写入大户
  2. 检查日志级别和日志量
  3. 检查应用缓存命中率
```

---

## 3. 进程级：iotop 定位写入大户

```bash
# 安装 iotop（如未安装）
command -v iotop >/dev/null 2>&1 || yum install -y iotop || apt-get install -y iotop

# 只显示正在进行 IO 的进程（非交互模式，适合 CloudAssistant）
iotop -b -o -n 3 -d 2
```

| 字段 | 含义 |
|------|------|
| `TID` / `PID` | 进程 ID |
| `PRIO` | IO 优先级 |
| `DISK READ` | 读速率 |
| `DISK WRITE` | 写速率 |
| `SWAPIN` | Swap 换入比例 |
| `IO>` | 等待 IO 的时间百分比 |
| `COMMAND` | 进程命令 |

### 3.1 常见 IO 大户进程

| 进程 | IO 类型 | 说明 |
|------|---------|------|
| `mysqld` / `postgres` | 数据读写 | 数据库工作负载 |
| `nginx` | access log 写入 | 高并发时日志 IO 可观 |
| `java` (应用进程) | 日志 + 数据 | 取决于应用逻辑 |
| `rsyslogd` / `journald` | 系统日志写入 | 日志量异常时 |
| `kswapd0` | Swap IO | 内存不足导致 swap |
| `flush-*` | 脏页回写 | 内核脏页回写线程 |
| `jbd2/*` / `kjournald` | 文件系统 journal | ext4/xfs journal 写入 |
| `atop` / `sar` | 监控工具 IO | 监控工具本身产生的 IO |

---

## 4. 文件系统层诊断

### 4.1 检查文件系统类型和挂载选项

```bash
# 文件系统类型
df -hT / | tail -1

# 挂载选项
mount | grep " / "

# 关键挂载选项说明
# noatime/relatime — 减少元数据写入
# barrier=0 — 关闭写屏障（风险：断电可能丢数据）
# discard — SSD TRIM（对云盘有意义）
# data=writeback/ext3 — journal 模式
```

### 4.2 常见文件系统 IO 问题

| 问题 | 表现 | 解决 |
|------|------|------|
| ext4 journal 延迟 | jbd2 进程 IO 高 | 切换 xfs 或调整 journal 大小 |
| inode 满 | 无法创建新文件 | `df -i` 检查 inode 使用率 |
| 碎片化 | 顺序读变随机读 | `e4defrag` 或备份重建 |
| barrier 写入 | 高写入时延迟增加 | 了解风险后可关闭 |
| noatime 未设置 | 每次读都写 atime | 挂载选项加 `noatime` |

### 4.3 检查 inode 使用率

```bash
df -i /
# IUse% > 80% 需关注，> 95% 严重
```

---

## 5. 内存与 IO 关联分析

> 高 IO 往往与内存不足相关——内存不够导致 swap，swap 产生大量磁盘 IO。

### 5.1 检查 Swap 使用

```bash
free -h
cat /proc/meminfo | grep -E "SwapTotal|SwapFree|Dirty|Writeback"
```

| 指标 | 含义 | 处理 |
|------|------|------|
| SwapUsed > 0 | 有进程被换出 | 内存不足，考虑升配或优化内存使用 |
| Dirty > 100MB | 脏页积压 | 回写线程可能跟不上写入速度 |
| Writeback > 0 | 正在回写 | 正常，持续高则异常 |

### 5.2 检查 OOM 历史

```bash
dmesg -T | grep -i "oom\|out of memory" | tail -5
# 有 OOM 记录说明曾发生内存不足
```

---

## 6. IO 调度器检查

```bash
# 查看当前调度器
cat /sys/block/*/queue/scheduler

# 常见调度器
# mq-deadline — 适合大多数场景（推荐）
# bfq — 适合桌面/交互式
# kyber — 适合快速设备（NVMe/ESSD）
# none/noop — 适合虚拟化环境
```

> **阿里云 ECS 默认**：virtio 块设备通常使用 `mq-deadline` 或 `none`，无需调整。

---

## 7. 综合决策树

```
ECS IO 异常
│
├─ 1. CloudMonitor 确认 IO 异常
│   ├─ IOPS/吞吐 接近云盘上限 → 升级云盘类型
│   └─ IOPS/吞吐 未达上限 → 进入 OS 层分析
│
├─ 2. iostat 分析
│   ├─ %util 高 + await 正常 → 高负载正常，观察
│   ├─ %util 高 + await 高 → IO 瓶颈
│   │   ├─ 确认云盘类型 → 已达上限 → 升级
│   │   └─ 未达上限 → 检查文件系统/调度器
│   ├─ %util 正常 + await 异常高 → 调度/文件系统问题
│   └─ 读写比失衡 → 定位 IO 大户
│
├─ 3. iotop 定位进程
│   ├─ 数据库进程 → 检查慢查询/索引
│   ├─ Nginx → 检查 access_log 写入量/缓冲
│   ├─ 应用进程 → 检查日志级别/缓存策略
│   ├─ jbd2/kjournald → 文件系统 journal 问题
│   └─ kswapd0 → 内存不足导致 swap
│
├─ 4. 内存关联
│   ├─ SwapUsed > 0 → 升级内存或优化应用
│   └─ Dirty > 100MB → 检查回写策略
│
└─ 5. 文件系统层
    ├─ inode 满 → 清理小文件
    ├─ 碎片化 → 备份重建
    └─ mount 选项不合理 → 调整挂载参数
```

---

## 8. 应用服务器 IO 场景速查

### 8.1 Nginx 服务器

| IO 来源 | 特征 | 优化 |
|---------|------|------|
| access_log 写入 | 大量小写入，随机 IO | 使用 buffer + flush 间隔 |
| error_log 写入 | 少量，异常时突增 | 调整日志级别 |
| proxy_temp 临时文件 | 大响应体时 | 增加内存缓冲，减少落盘 |
| ssl_session_cache | SSL 握手时 | 共享内存缓存，不落盘 |

**Nginx 日志 IO 优化示例**：
```nginx
access_log /var/log/nginx/access.log main buffer=32k flush=5s;
error_log /var/log/nginx/error.log warn;
```

### 8.2 普通应用服务器（Java/Python/Go）

| IO 来源 | 特征 | 优化 |
|---------|------|------|
| 应用日志 | 大量小写入 | 异步日志 + buffer |
| 数据库连接池 | 读写取决于业务 | 检查慢查询 |
| 文件上传/下载 | 大块顺序 IO | 调整 OS 缓存 |
| Session 持久化 | 小写入 | 移至 Redis |

---

## 9. Cloud Assistant 执行模板

> 以下脚本可通过 `aliyun ecs RunCommand` 一键执行，适用于批量巡检。

```bash
# 一键 IO 诊断脚本（5 个子命令）
cat << 'SCRIPT'
#!/bin/bash
echo "=== DISK INFO ==="
lsblk -d -o NAME,SIZE,TYPE,ROTA,MODEL 2>/dev/null || fdisk -l 2>/dev/null | head -20

echo "=== FILESYSTEM ==="
df -hT / 2>/dev/null

echo "=== MOUNT OPTIONS ==="
mount | grep " / " 2>/dev/null

echo "=== IOSTAT (5x2s) ==="
iostat -xmd 2 5 2>/dev/null || echo "sysstat not installed"

echo "=== TOP IO PROCESSES ==="
iotop -b -o -n 1 -d 1 2>/dev/null || echo "iotop not installed"

echo "=== MEMORY/SWAP ==="
free -h 2>/dev/null
cat /proc/meminfo 2>/dev/null | grep -E "SwapTotal|SwapFree|Dirty|Writeback"

echo "=== INODE ==="
df -i / 2>/dev/null

echo "=== DMESG OOM ==="
dmesg -T 2>/dev/null | grep -i "oom\|out of memory" | tail -3
SCRIPT
```
