# Monitoring ASK

## Two-Layer Model

ASK monitoring has **two layers** that are easy to confuse:

| Layer | Namespace | Measures | Use for |
|-------|-----------|----------|---------|
| **K8s control plane + cluster** | `acs_k8s_dashboard` | Cluster-level K8s metrics | Cluster health |
| **ECI Pod layer** | `acs_eci_dashboard` | Per-ECI CPU, memory, network + **region-level quota** | Capacity, cost, HPA, quota |

> **Critical:** `kubectl get nodes` shows 1 virtual node only (virtual-kubelet).
> Do NOT use `kubectl top nodes` for capacity. Use `kubectl top pods` + the
> ECI region-level quota metrics.

## Metric Namespaces

| Namespace | Scope |
|-----------|-------|
| `acs_k8s_dashboard` | Cluster / control plane (shared with ManagedKubernetes) |
| `acs_eci_dashboard` | ECI Pod metrics + region-level ECI quota usage |
| `acs_slb_dashboard` | SLB (ingress / public API server) |

## Cluster-Level Metrics (`acs_k8s_dashboard`)

| Metric | Description | Unit | Dimensions |
|--------|-------------|------|------------|
| `CpuUsage` | Cluster CPU (sum of Pods) | % | clusterId |
| `MemoryUsage` | Cluster memory | % | clusterId |
| `DiskUsage` | Cluster disk | % | clusterId |
| `NetworkInRate` / `NetworkOutRate` | Network rate | bits/s | clusterId |
| `PodStatus` | Pod status distribution | count | clusterId, status |
| `NodeStatus` | Always 1 virtual node in healthy ASK | count | clusterId, status |

> `NodeStatus` always shows 1 Ready + 0 others when healthy. **Do not
> alert on "single node"** — there's only ever one virtual node.

## ECI Pod-Level Metrics (`acs_eci_dashboard`)

| Metric | Description | Dimensions |
|--------|-------------|------------|
| `eci.cpu.usage` | ECI CPU usage | clusterId, namespace, pod, container |
| `eci.memory.usage` | ECI memory usage | clusterId, namespace, pod, container |
| `eci.network.in.bytes` | Network inbound | clusterId, namespace, pod |
| `eci.network.out.bytes` | Network outbound | clusterId, namespace, pod |
| `eci.status` | ECI status distribution | clusterId, namespace, status |

> **⚠️ Verify exact metric names** via
> `aliyun cms DescribeMetricMetaList --Namespace acs_eci_dashboard`
> before production alerting.

## ECI Account-Level Quota Metrics (`acs_eci_dashboard`)

| Metric | Description | Dimensions |
|--------|-------------|------------|
| `eci.vcpu.quota.usage` / `eci.vcpu.quota.total` | Region ECI vCPU usage / total | regionId |
| `eci.memory.quota.usage` / `eci.memory.quota.total` | Region ECI memory usage / total | regionId |
| `eci.instance.count.usage` / `eci.instance.count.total` | Region ECI instance count usage / total | regionId |

> **⚠️ Verify metric names** before production use.

## KPI Thresholds

| KPI | Warning | Critical | Action |
|-----|---------|----------|--------|
| Cluster CPU (Pod sum) | > 70% | > 85% | Optimize requests; raise HPA maxReplicas |
| Cluster Memory (Pod sum) | > 75% | > 90% | Same as above |
| **ECI vCPU quota usage** | > 70% | > 90% | **Raise ECI vCPU quota in ECI console** |
| **ECI memory quota usage** | > 70% | > 90% | **Raise ECI memory quota in ECI console** |
| **ECI instance count quota** | > 70% | > 90% | **Raise ECI instance quota** |
| Pod Pending (FailedScheduling) | > 5 | > 20 | Check ECI quota + image + profile |
| API Server Latency | > 1s | > 5s | Control plane issue (Alibaba-managed) |

## Querying Metrics

```bash
# Cluster CPU
aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard --MetricName CpuUsage \
  --Dimensions '[{"clusterId":"{{user.cluster_id}}"}]' --Period 60

# ECI vCPU quota usage (region-level)
aliyun cms DescribeMetricList \
  --Namespace acs_eci_dashboard --MetricName eci.vcpu.quota.usage \
  --Dimensions '[{"regionId":"{{user.region}}"}]' --Period 300

# ECI memory quota usage
aliyun cms DescribeMetricList \
  --Namespace acs_eci_dashboard --MetricName eci.memory.quota.usage \
  --Dimensions '[{"regionId":"{{user.region}}"}]' --Period 300
```

For detailed CMS workflows, delegate to `alicloud-cms-ops`.

## Kubernetes-Native Monitoring

```bash
# Get kubeconfig (private endpoint — default for ASK)
aliyun cs GET /k8s/{{user.cluster_id}}/user_config \
  --PrivateIpAddress true > ~/.kube/ask-config
export KUBECONFIG=~/.kube/ask-config

# Single virtual node — normal
kubectl get nodes

# Pod-level (use this for capacity, NOT node-level)
kubectl top pods --all-namespaces

# Pod status distribution
kubectl get pods -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,STATUS:.status.phase,NODE:.spec.nodeName'

# HPA status
kubectl get hpa -A

# ECI Pod events
kubectl get events -A --field-selector involvedObject.kind=Pod --sort-by='.lastTimestamp' | tail -20
```

## Alert Recommendations

| Alert | Metric | Threshold | Severity |
|-------|--------|-----------|----------|
| ECI vCPU Quota High | `eci.vcpu.quota.usage` | > 85% quota | **P1** |
| ECI Memory Quota High | `eci.memory.quota.usage` | > 85% quota | **P1** |
| ECI Instance Count Quota High | `eci.instance.count.usage` | > 85% quota | **P1** |
| Pod Pending Storm | `PodStatus` (Pending) | > 20 in 5 min | **P0** |
| Cluster Unavailable | `state` | != `running` | **P0** |
| HPA At Max | `kube_horizontalpodautoscaler_status_current_replicas / spec_max_replicas` | = 1.0 for 10 min | P2 |
| API Server Latency | `apiserver_request_duration_seconds:p99` | > 5s | P1 |

## Alarm Rule (CLI example)

```bash
# ECI vCPU quota near limit
aliyun cms PutMetricAlarm \
  --AlarmName "ask-{{user.cluster_id}}-eci-vcpu-quota" \
  --Namespace acs_eci_dashboard \
  --MetricName eci.vcpu.quota.usage \
  --Dimensions '[{"regionId":"{{user.region}}"}]' \
  --Statistics Average \
  --ComparisonOperator ">=" \
  --Threshold 85 \
  --Period 300 \
  --EvaluationCount 3 \
  --ContactGroups '["{{user.contact_group}}"]'
```

## ARMS Prometheus (optional, ASK-compatible)

ASK supports ARMS Prometheus for K8s-native metrics. Install via addon:

```bash
aliyun cs POST /clusters/{{user.cluster_id}}/addons \
  --body '{"name":"arms-prometheus"}'
```

Useful PromQL:

```promql
# ASK namespace memory usage
sum by (namespace) (container_memory_working_set_bytes{cluster_id="{{user.cluster_id}}"})

# ASK HPA-target CPU per Deployment
sum by (deployment) (
  rate(container_cpu_usage_seconds_total{cluster_id="{{user.cluster_id}}"}[5m])
)

# Pending Pods (ECI scheduling failure indicator)
sum(kube_pod_status_phase{cluster_id="{{user.cluster_id}}",phase="Pending"})
```

## Alert Storm Handling (ASK)

ASK-specific patterns:

1. **ECI quota exhaustion cascade** — many ECI Pods simultaneously
   `FailedScheduling` → page on-call to raise ECI quota immediately
2. **Image pull storm** — all new Pods for an image fail with
   `ImagePullBackOff` → check ACR / network; possibly fall back image
3. **HPA oscillation** — Pods rapidly created/destroyed → check metric
   smoothing, ECI profile availability
4. **Cross-AZ VSwitch exhaustion** — ECI Pods Pending in one AZ → rebalance
   VSwitch / add CIDR

## Dashboard Panels (Essential)

| Panel | Source | What to show |
|-------|--------|--------------|
| Cluster Overview | `acs_k8s_dashboard` | State, current_version, created |
| Cluster CPU/Memory | `acs_k8s_dashboard` | Cluster CPU% + Memory% trend |
| Pod Status Distribution | `acs_k8s_dashboard` `PodStatus` | Running/Pending/Failed counts |
| **ECI vCPU Quota** | `acs_eci_dashboard` | usage / total bar (with 80% line) |
| **ECI Memory Quota** | `acs_eci_dashboard` | usage / total bar (with 80% line) |
| Top ECI Pods by CPU | `kubectl top pods` or Prometheus | Top 10 |
| Top ECI Pods by Memory | `kubectl top pods` or Prometheus | Top 10 |
| HPA Status | `kubectl get hpa` | current/max/desired |
| API Server Latency | Prometheus P99 | apiserver_request_duration_seconds:p99 |

## Monitoring Health Checklist

| Check | Frequency | Tool | Pass Criteria |
|-------|-----------|------|---------------|
| Cluster state = `running` | 1 min | CMS | Always running |
| ECI quota < 80% | 5 min | CMS | Headroom available |
| ECI Pods `Ready` ratio | 1 min | kubectl + CMS | > 95% |
| kubeconfig still valid | Daily | `kubectl get nodes` | Connects successfully |
| ECI Pod cold start P95 | Daily | Prometheus | < 30s |
| HPA not pinned at max | 5 min | CMS / kubectl | current < max for > 90% of time |
