# ECS Observability Integration

> **Purpose:** Metrics→Logs→Traces linkage for ECS instances.

## Metrics → Logs 联动

| CMS 指标异常 | SLS 查询目标 | 目的 |
|-------------|-------------|------|
| `CPUUtilization` 突增 | `* ERROR \| SELECT count(\*) by level FROM log` | 确认错误日志爆发是否导致 CPU 飙升 |
| `MemoryUtilization` 泄漏 | `memory\|out_of_memory\|gc \| SELECT \*` | 确认 OOM/GC 模式 |
| `LoadAverage` > CPU×2 | `cpu\|iowait \| SELECT \*` | 确认是否 IO 等待导致 Load 飙升 |
| `DiskReadIOPS` / `DiskWriteIOPS` 异常 | `disk\|io \| SELECT \* by process` | 确认进程级 IO 源 |
| `InternetOutRate` 突增 | `access \| SELECT host, remote_addr, count(\*) group by host` | 确认异常流量源 |

## IO 三层联动诊断路径

> 当 IO 指标异常时，按 Metrics → Logs → Host 三层逐层下钻，定位根因。

### 第一层：云监控指标确认异常

| CMS 指标 | Warning | Critical | 判定逻辑 |
|----------|---------|----------|----------|
| `DiskReadIOPS` / `DiskWriteIOPS` | > 70% 云盘上限 | > 85% 云盘上限 | 需查云盘类型确认上限 |
| `DiskReadBPS` / `DiskWriteBPS` | > 70% 云盘吞吐上限 | > 85% 云盘吞吐上限 | ESSD PL1: 350MB/s |
| `LoadAverage` > CPU×2 | 持续 5 min | 持续 10 min | IO wait 导致 Load 飙升 |

### 第二层：进程级 IO 定位

> 通过 Cloud Assistant 执行 `iotop -b -o -n 3` 定位 IO 大户进程。

```bash
# 进程级 IO 快照脚本
iotop_script='#!/bin/bash
echo "=== TOP IO PROCESSES ==="
iotop -b -o -n 1 -d 1 2>/dev/null || echo "[WARN] iotop not installed"
echo ""
echo "=== IOSTAT (3x2s) ==="
iostat -xmd 2 3 2>/dev/null || echo "[WARN] sysstat not installed"
echo ""
echo "=== MEMORY ==="
free -h 2>/dev/null
cat /proc/meminfo 2>/dev/null | grep -E "SwapTotal|SwapFree|Dirty|Writeback"
'
```

**常见 IO 大户进程：**

| 进程 | 典型场景 | 根因 |
|------|----------|------|
| `jbd2/kjournald` | ext4 journal 写入 | 文件系统日志延迟 |
| `kswapd0` | 内存不足导致 swap | 内存规格不足或泄漏 |
| `nginx` / `java` | 应用日志写入 | 日志未做缓冲 |
| `mysqld` | 数据库 WAL/数据写入 | 慢查询或写入集中 |
| `rsync/tar` | 备份/迁移任务 | 临时 IO 峰值 |

### 第三层：Host 深度诊断

> 详见 [host-io-inspection.md](host-io-inspection.md) — 完整的 Host IO 诊断指南。

**诊断决策树：**

```
IO 异常
├── %util > 80% → IOPS/吞吐达上限 → 升级云盘类型
├── %util 正常 + await 高 → IO 调度/文件系统层问题
│   ├── kswapd0 高 → 内存不足 → 升级内存
│   ├── jbd2 高 → ext4 journal → 调整 journal 或切 xfs
│   └── mount 选项 → 添加 noatime
├── 读写比失衡 → 缓存/日志策略问题
└── inode > 95% → 清理小文件
```

### 查询示例

```bash
# 查询 ECS 应用错误日志 (SLS)
aliyun log GetLogs \
  --project "{{user.sls_project}}" \
  --logstore "{{user.sls_logstore}}" \
  --query "\* ERROR" \
  --from "2026-05-16T00:00:00Z" \
  --to "2026-05-16T01:00:00Z"
```

## Metrics → Traces 联动

| CMS 指标异常 | Trace 目标 | 目的 |
|-------------|-----------|------|
| API 响应延迟突增 | ARMS RPC/HTTP Trace | 定位热点方法/慢依赖 |
| CPU 突增 | ARMS CPU FlameGraph | 定位热点代码路径 |
| 错误率增加 | ARMS Error Trace | 定位错误根因服务 |

## 降级策略

若 ARMS/SLS 不可用：
1. 直接 SSH 到 ECS 使用 `top`、`iotop`、`journalctl` 排查
2. 使用 `dmesg` 查看内核日志 (OOM、panic)
3. 检查 `/var/log/messages` 和 `/var/log/syslog`
