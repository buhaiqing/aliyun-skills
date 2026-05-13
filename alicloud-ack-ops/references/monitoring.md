# Monitoring ACK

## Key Metrics

ACK integrates with CloudMonitor. Key metric namespaces:

- `acs_k8s` — Kubernetes cluster-level metrics
- `acs_ecs_dashboard` — ECS node-level metrics (CPU, memory, disk)
- `acs_slb_dashboard` — SLB metrics for ingress/services

## Common Metrics

| Metric | Namespace | Description |
|--------|-----------|-------------|
| `cpu.utilization` | `acs_ecs_dashboard` | ECS instance CPU usage |
| `memory.utilization` | `acs_ecs_dashboard` | ECS instance memory usage |
| `disk.utilization` | `acs_ecs_dashboard` | Disk usage |
| `network.in` | `acs_ecs_dashboard` | Network inbound traffic |
| `network.out` | `acs_ecs_dashboard` | Network outbound traffic |

## Log Collection

ACK supports log collection via Logtail (SLS):

1. Enable log collection in cluster addons
2. Configure Logtail DaemonSet for container stdout/stderr
3. Query logs via SLS console or API

## Alert Example (Structure)

```json
{
  "alert_name": "ack-high-cpu",
  "metric": "cpu.utilization",
  "namespace": "acs_ecs_dashboard",
  "dimensions": ["cluster_id", "instance_id"],
  "condition": "> 80",
  "duration": "5m",
  "silence": "30m"
}
```

## kubeconfig Access

For Kubernetes-native monitoring (`kubectl top nodes`, Prometheus, etc.):

```bash
# Get kubeconfig
aliyun cs GET /k8s/{cluster_id}/user_config

# Save to file and use kubectl
export KUBECONFIG=/path/to/kubeconfig
kubectl top nodes
kubectl top pods --all-namespaces
```
