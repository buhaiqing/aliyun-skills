# ACK Core Concepts

## Cluster Types

| Type | Description | Use Case |
|------|-------------|----------|
| `ManagedKubernetes` | Managed control plane, user manages worker nodes | Production workloads requiring node-level control |
| `Kubernetes` | Dedicated control plane on user-managed ECS | Compliance / regulatory requirements |
| ~~`Ask` (Serverless Kubernetes)~~ | **Out of scope for this skill** — see [`alicloud-ask-ops`](../../alicloud-ask-ops/SKILL.md) | Variable workloads, batch jobs |

## Key Resources

### Cluster
A Kubernetes cluster consists of a control plane (managed by Alibaba Cloud for
ManagedKubernetes) and worker nodes (managed by user or auto-managed). Identified
by `cluster_id`.

### Node Pool
A homogeneous group of worker nodes sharing:
- Instance type
- VSwitch
- Operating system image
- Scaling configuration (min/max/desired size)

Node pools enable independent scaling and upgrade of different workload tiers.

### Addon
Cluster components extending Kubernetes functionality:
- **Ingress:** Traffic routing (NGINX, ALB)
- **Monitoring:** Metrics collection (CloudMonitor, Prometheus)
- **Logging:** Log collection (Logtail)
- **Storage:** CSI plugins for cloud storage
- **Network:** CNI plugins (Flannel, Terway)

### Network Model

ACK supports two CNI plugins with different parameter requirements:

| CNI | `pod_cidr` Required? | Key Feature | Use Case |
|-----|----------------------|-------------|----------|
| **Flannel** | Yes | Simple overlay networking | General workloads |
| **Terway** | No | ENI-based, VPC-native IPs | High-density, low-latency |

> **Critical:** When using **Terway**, do **NOT** pass `pod_cidr` in
> CreateCluster request. When using **Flannel**, `pod_cidr` is required.

| Parameter | Default | Required For | Description |
|-----------|---------|--------------|-------------|
| `pod_cidr` | `10.0.0.0/8` | Flannel only | IP range for pods |
| `service_cidr` | `172.16.0.0/16` | All | IP range for services |
| `vpc_id` | required | All | VPC for cluster networking |
| `vswitch_ids` | required | All | VSwitches for worker nodes |

## kubeconfig

The `kubeconfig` file provides kubectl access to the cluster API server. Retrieve
via:

```bash
aliyun cs GET /k8s/{cluster_id}/user_config
```

Two endpoint types:
- **Public:** Accessible from internet (requires public API server enabled)
- **Internal:** Accessible only within VPC
