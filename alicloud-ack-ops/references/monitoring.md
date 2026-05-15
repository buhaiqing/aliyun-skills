# Monitoring ACK

## Overview

ACK (Alibaba Cloud Container Service for Kubernetes) integrates with CloudMonitor
for infrastructure-level monitoring. For Kubernetes-native monitoring (Prometheus,
Grafana, `kubectl top`), use kubeconfig access.

## Metric Namespaces

| Namespace | Scope | Description |
|-----------|-------|-------------|
| `acs_k8s_dashboard` | Cluster | Kubernetes cluster-level metrics |
| `acs_ecs_dashboard` | Node | ECS node-level metrics (CPU, memory, disk) |
| `acs_slb_dashboard` | SLB | SLB metrics for ingress/services |

## Cluster-Level Metrics

| Metric Name | Description | Unit | Dimensions |
|-------------|-------------|------|------------|
| `CpuUsage` | Cluster CPU usage | % | clusterId |
| `MemoryUsage` | Cluster memory usage | % | clusterId |
| `DiskUsage` | Cluster disk usage | % | clusterId |
| `NetworkInRate` | Network inbound rate | bits/s | clusterId |
| `NetworkOutRate` | Network outbound rate | bits/s | clusterId |
| `PodStatus` | Pod status distribution | count | clusterId, status |
| `NodeStatus` | Node status distribution | count | clusterId, status |

## Node-Level Metrics (via ECS)

| Metric Name | Description | Unit | Dimensions |
|-------------|-------------|------|------------|
| `cpu.utilization` | ECS node CPU usage | % | instanceId |
| `memory.utilization` | ECS node memory usage | % | instanceId |
| `disk.utilization` | ECS node disk usage | % | instanceId |
| `network.in` | Network inbound traffic | bytes/s | instanceId |
| `network.out` | Network outbound traffic | bytes/s | instanceId |

## Key Performance Indicators (KPIs)

### Critical KPIs

| KPI | Warning Threshold | Critical Threshold | Action |
|-----|-------------------|-------------------|--------|
| Cluster CPU Usage | > 70% | > 85% | Scale out node pool or optimize scheduling |
| Cluster Memory Usage | > 75% | > 90% | Scale out node pool or optimize memory usage |
| Node NotReady Ratio | > 10% | > 30% | Check node health via `alicloud-ecs-ops` |
| Pod CrashLoopBackOff | > 5 pods | > 20 pods | Check application logs and configuration |
| API Server Latency | > 1s | > 5s | Check control plane load |
| Disk Usage (node) | > 80% | > 90% | Clean up images, logs, or expand disk |
| Network Error Rate | > 1% | > 5% | Check network policies and VPC routing |

### Business KPIs

| KPI | Target | Measurement |
|-----|--------|-------------|
| Cluster Availability | 99.9% | Cluster `running` state uptime |
| Node Availability | 99.9% | Node `Ready` state ratio |
| Pod Availability | 99.9% | Running pods / total pods ratio |
| Deployment Rollout Success | 100% | Deployment status after update |

## Querying Metrics via CLI

```bash
# Query cluster CPU usage (delegate to alicloud-cms-ops)
aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"clusterId":"{{user.cluster_id}}"}]' \
  --Period 60 \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Query cluster memory usage
aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName MemoryUsage \
  --Dimensions '[{"clusterId":"{{user.cluster_id}}"}]' \
  --Period 60

# Query node CPU usage (via ECS metrics)
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName cpu.utilization \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60
```

## Kubernetes-Native Monitoring

### kubeconfig Access

```bash
# Get kubeconfig
aliyun cs GET /k8s/{{user.cluster_id}}/user_config > ~/.kube/ack-config
export KUBECONFIG=~/.kube/ack-config

# Check node resource usage
kubectl top nodes

# Check pod resource usage
kubectl top pods --all-namespaces

# Check node conditions
kubectl describe nodes | grep -A5 Conditions

# Check pod events
kubectl get events --all-namespaces --sort-by='.lastTimestamp'
```

### Key kubectl Commands for Monitoring

```bash
# List all pods with status
kubectl get pods --all-namespaces -o wide

# Check deployment rollout status
kubectl rollout status deployment/{{user.deployment_name}} -n {{user.namespace}}

# Check resource usage per namespace
kubectl top pods -n {{user.namespace}}

# Check node resource allocation
kubectl describe node {{user.node_name}} | grep -A3 "Allocated resources"

# Check persistent volume claims
kubectl get pvc --all-namespaces
```

## Multi-Metric Anomaly Inspection

Execute joint巡检 on ACK clusters to identify compound anomaly patterns.

### Supported Anomaly Patterns

| Pattern | Metrics Involved | Detection Logic | Severity | Interpretation |
|---------|-----------------|-----------------|----------|----------------|
| CPU-Memory 集群过载 | `CpuUsage` + `MemoryUsage` | CPU > 85% AND Memory > 90% 持续 10 min | Critical | 集群资源耗尽，需扩缩容或驱逐低优先级 Pod |
| 节点不可用风暴 | `NodeStatus` + `cpu.utilization` | NotReady nodes > 30% AND 存活节点 CPU 飙升 | Critical | 可能底层 ECS 故障、网络分区、或 kubelet 异常 |
| Pod 大规模重启 | `PodStatus` (CrashLoopBackOff) + `NetworkInRate` | CrashLoop > 20 pods AND 网络流量突降 | Critical | 应用大规模异常，可能配置错误或镜像拉取失败 |
| 磁盘-IO 瓶颈 | `DiskUsage` + `disk.utilization` | 集群磁盘 > 90% AND 节点磁盘 > 95% | Critical | 镜像/日志占满磁盘，需清理或扩盘 |
| 网络-连接异常 | `NetworkInRate` + `NetworkOutRate` | 流量突降 > 60% AND NodeStatus 正常 | Warning | 可能 VPC 路由异常、安全组变更、或 CNI 插件异常 |
| API Server 延迟 | `CpuUsage` (control plane) + Pod creation latency | CPU > 80% AND new pod scheduling > 30s | Warning | API Server 过载，可能大量 watch/leader election 竞争 |

### Execution — CLI

```bash
# Fetch cluster-level metrics (delegate to alicloud-cms-ops for detailed queries)
aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"clusterId":"c-xxx"}]' \
  --Period 300

aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName MemoryUsage \
  --Dimensions '[{"clusterId":"c-xxx"}]' \
  --Period 300

# Check node-level metrics via ECS
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName cpu.utilization \
  --Dimensions '[{"instanceId":"i-xxx"}]' \
  --Period 300
```

### Recovery & Cross-Skill Delegation

| Pattern | Primary Skill | Delegated Skill | Action |
|---------|--------------|-----------------|--------|
| CPU-Memory 过载 | `alicloud-ack-ops` | `alicloud-ecs-ops` (节点扩容) | 扩缩容 node pool |
| 节点不可用 | `alicloud-ack-ops` | `alicloud-ecs-ops` + `alicloud-vpc-ops` | 检查 ECS 状态和网络 |
| Pod 重启风暴 | `alicloud-ack-ops` | — | 检查 Pod events + 应用日志 |
| 网络异常 | `alicloud-ack-ops` | `alicloud-vpc-ops` (检查 VPC 路由/CNI) | 排查网络配置 |

## Alert Storm Handling

When ACK generates >10 alarms within 5 minutes:

1. **Aggregate by clusterId**: Coalesce node/pod-level alarms into cluster-level event
2. **Identify root resource**: 
   - If multiple nodes NotReady simultaneously → likely VPC/ECS infrastructure issue
   - If multiple pods CrashLoopBackOff in same deployment → likely application issue
3. **Suppress by namespace**: Group pod alarms by namespace to reduce noise
4. **Cross-Skill trigger**: If node-level anomalies dominate → delegate to `alicloud-ecs-ops` immediately

## Alert-Driven Diagnostic Decision Tree

```
[ACK Alarm Fires]
    │
    ├── Step 1: Verify alarm validity — Current metric vs threshold
    │
    ├── Step 2: Check cluster status — `acs_k8s_dashboard` state
    │
    ├── Step 3: Check node health — Describe node status via `alicloud-ecs-ops`
    │       └── If multiple NotReady nodes → infrastructure issue
    │
    ├── Step 4: Check pod health — kubectl get pods + describe
    │       └── If CrashLoopBackOff > X% → application config issue
    │
    ├── Step 5: Multi-metric correlation — CPU+Memory+Disk+PodStatus joint analysis
    │
    ├── Step 6: Cross-Skill diagnosis
    │       ├── Node issue → `alicloud-ecs-ops` + `alicloud-vpc-ops`
    │       └── App issue → Application logs (SLS)
    │
    └── Step 7: Generate unified diagnostic report
```

## Log Collection

ACK supports log collection via Logtail (SLS):

1. Enable log collection in cluster addons
2. Configure Logtail DaemonSet for container stdout/stderr
3. Query logs via SLS console or API

```bash
# Check if logtail addon is installed
aliyun cs GET /clusters/{{user.cluster_id}}/addons | jq '.addons[] | select(.name=="logtail-ds")'
```

## Alert Recommendations

| Alert | Metric | Threshold | Severity |
|-------|--------|-----------|----------|
| High cluster CPU | `CpuUsage` | > 85% | Critical |
| High cluster memory | `MemoryUsage` | > 90% | Critical |
| Node NotReady | `NodeStatus` | > 10% of nodes | Critical |
| Pod CrashLoopBackOff | `PodStatus` | > 5 pods | Warning |
| High node disk usage | `disk.utilization` | > 90% | Warning |
| API Server unavailable | Cluster state | != `running` | Critical |

## Dashboard Recommendations

### Essential Dashboard Panels

1. **Cluster Overview**: State, node count, pod count, version
2. **Resource Usage**: Cluster CPU/memory usage trend
3. **Node Health**: Node status distribution, NotReady nodes list
4. **Pod Health**: Pod status distribution, CrashLoopBackOff pods
5. **Workload Status**: Deployment/StatefulSet/DaemonSet availability
6. **Network**: Inbound/outbound traffic, error rates
7. **Storage**: PVC status, disk usage on nodes

## Integration with CloudMonitor

ACK metrics are automatically published to CloudMonitor. You can:

- Set up alarm rules in CloudMonitor console
- Use CloudMonitor API to query metrics
- Integrate with DingTalk, SMS, or email for notifications
- Export metrics to external monitoring systems via CloudMonitor

For detailed metric queries and alert configuration, delegate to `alicloud-cms-ops`.