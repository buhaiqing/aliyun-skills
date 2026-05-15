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
