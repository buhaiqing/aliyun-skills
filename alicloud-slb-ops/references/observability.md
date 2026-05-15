# SLB Observability Integration

> **Purpose:** Metrics→Logs→Traces linkage for SLB instances.

## Metrics → Logs 联动

| CMS 指标异常 | 日志查询目标 | 目的 |
|-------------|-------------|------|
| `InstanceStatusCode5xx` 突增 | Nginx/Access 日志中 `status >= 500` | 确认 5xx 请求详情和被丢弃的请求 |
| `InstanceRt` 突增 | Access 日志中的 `request_time` > 1s | 定位慢请求来源和后端响应时间 |
| `InstanceDropConnection` 上升 | 防火墙/安全组日志 | 确认被丢弃的连接来自哪个源 IP |
| `InstanceUpstreamCode5xx` 突增 | 后端应用错误日志 | 确认 5xx 来自后端而非 SLB 自身 |

### 查询示例

```bash
# SLB Access Log 查询（SLS）
aliyun log GetLogs \
  --project "{{user.sls_project}}" \
  --logstore "slb-access-log" \
  --query "status >= 500 | SELECT upstream_addr, host, uri, count(\*) group by upstream_addr, host"
```

## Metrics → Traces 联动

| CMS 指标异常 | Trace 目标 | 目的 |
|-------------|-----------|------|
| SLB 整体延迟增加 | ARMS 从入口 SLB 开始的 Trace | 定位后端服务中的慢调用链 |
| 5xx 错误 | ARMS Error Span with HTTP status = 5xx | 定位具体出错的后端和代码行 |

## 降级策略

若 SLS/ARMS 不可用：
1. 检查 SLB 健康检查状态
2. 逐一检查后端服务器响应
3. 启用精细化监控（`EnableHighDefinationMonitor`）
