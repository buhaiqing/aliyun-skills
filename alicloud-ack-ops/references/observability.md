# ACK Observability Integration

> **Purpose:** Metrics→Logs→Traces linkage for ACK clusters.

## Metrics → Logs 联动

| CMS 指标异常 | Kubernetes/应用日志查询目标 | 目的 |
|-------------|---------------------------|------|
| `CpuUsage` 突增 | Pod 日志 `kubectl logs` + OOM/panic 日志 | 确认代码错误/内存泄漏导致 CPU 飙升 |
| `MemoryUsage` 泄漏 | Pod 日志 + JVM OOM + container restart events | 确认容器内存泄漏模式 |
| `PodStatus` 大规模异常 | Pod Event `kubectl get events` + 控制器日志 | 定位 Pod 异常根因（镜像/配置/资源不足） |
| `NodeStatus` NotReady | Node 日志 `journalctl -u kubelet` + ECS 系统日志 | 确认是 Kubelet 异常还是底层 ECS 故障 |
| `DiskUsage` > 90% | 磁盘清理日志 + `/var/log` 增长趋势 | 确认哪类数据占满磁盘（container/image/log） |

### 查询示例

```bash
# 查询 Pod 日志（kubectl）
kubectl logs pod-name -n namespace --tail=1000 | grep -E "ERROR|WARN|OOM|panic"

# 查询 Event（按 Pod/Node 过滤）
kubectl get events --namespace namespace --field-selector reason=BackOff

# 查询 SLS 应用日志
aliyun log GetLogs \
  --project "{{user.sls_project}}" \
  --logstore "{{user.sls_logstore}}" \
  --query "* ERROR" \
  --from "2026-05-16T00:00:00Z" \
  --to "2026-05-16T01:00:00Z"
```

## Metrics → Traces 联动

| CMS 指标异常 | Trace (ARMS/SkyWalking) 目标 | 目的 |
|-------------|---------------------------|------|
| 集群整体延迟增加 | ARMS Top Services Trace | 识别延迟突增的入口服务 |
| 错误率突增 | ARMS Error Trace with HTTP 5xx/4xx | 定位错误根因服务和异常类型 |
| 单个 Namespace 异常 | ARMS Namespace 级别 Trace | 隔离异常应用到具体 Namespace |

## Metrics → Kubernetes 事件联动

| CMS 指标异常 | Kubernetes Event 类型 | 目的 |
|-------------|---------------------|------|
| Pod Pending | `FailedScheduling` + `Unschedulable` | 识别调度失败原因（CPU/Memory/亲和性） |
| Pod CrashLoopBackOff | `BackOff` + `Failed` | 确认重启原因（OOM/Exit Code/Config） |
| Node NotReady | `NodeNotReady` + `KubeletNotReady` | 定位节点异常类型 |

## Metrics → Prometheus/Grafana 联动

ACK 支持阿里云 Prometheus 服务（Prometheus Monitoring）：

| CMS 指标异常 | Prometheus 查询 | 目的 |
|-------------|----------------|------|
| 集群内存使用高 | `kube_pod_container_resource_limits{namespace=~".*",resource="memory"}` | 查看容器级内存限制分配 |
| CPU 使用不均 | `rate(container_cpu_usage_seconds_total[5m])` | 识别 CPU 热点 Pod/Node |
| 连接数饱和 | `node_netstat_Tcp_CurrEstab` | 确认 TCP 连接分布 |

## 降级策略

若 ARMS/SLS 不可用：
1. 直接使用 `kubectl get events --all-namespaces --sort-by='.lastTimestamp'`
2. 使用 `kubectl describe node` 和 `kubectl describe pod` 排查
3. 使用 `journalctl -u kubelet` 查看节点日志
4. 登录 ECS 节点使用 `docker logs` 或 `crictl logs` 查看容器日志
