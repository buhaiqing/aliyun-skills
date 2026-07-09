# ASK Core Concepts

## What is ASK (Serverless Kubernetes)?

ASK is Alibaba Cloud's **fully-managed Serverless Kubernetes** offering
(产品名: 容器服务 Serverless Kubernetes 版). The key insight:

> **There are no nodes to manage. The K8s control plane is Alibaba-managed.
> Each Pod runs as an ECI (Elastic Container Instance) on demand.**

```
┌─────────────────────────────────────────────────────────────────┐
│                       ASK Cluster                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         Managed Control Plane (Alibaba-owned)             │   │
│  │   • API Server  • etcd  • Scheduler  • Controller Mgr   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                      │
│                            ▼ (virtual-kubelet)                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              ECI Elastic Container Instances              │   │
│  │   ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  │   │
│  │   │Pod 1│  │Pod 2│  │Pod 3│  │Pod 4│  │Pod 5│  │ ... │  │   │
│  │   │ECI A│  │ECI B│  │ECI C│  │ECI D│  │ECI E│  │     │  │   │
│  │   └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│            VPC (User-owned)                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ VSwitch 1│  │ VSwitch 2│  │  NAT GW  │  │  SLB (opt.)  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Key Differences from ACK ManagedKubernetes

| Dimension | ManagedKubernetes | ASK Serverless |
|-----------|-------------------|----------------|
| Worker nodes | User-managed (ECS) | **None** (ECI directly) |
| Node pool | ✅ Yes | ❌ No concept |
| Cluster autoscaler | ✅ | ❌ (HPA/CronHPA only) |
| UpgradeCluster | ✅ User-triggered | ❌ Alibaba-managed |
| ScaleOutCluster | ✅ Add nodes | ❌ N/A |
| Worker instance type | Required | N/A |
| Billing unit | ECS hourly | **Per-Pod vCPU×sec, mem×sec** |
| Control plane cost | Free | Free |
| kubectl get nodes | N real nodes | **1 virtual node** (virtual-kubelet) |
| hostNetwork / hostPID | ✅ | ❌ **ECI forbids** |
| DaemonSet (e.g. logtail-ds) | ✅ | ⚠️ May not schedule on ECI |
| Cold start | N/A | **~5-30s for first ECI Pod** |

## ECI (Elastic Container Instance)

ECI is the compute primitive of ASK. Each Pod = 1 ECI instance. Key facts:

- **Billing:** Per-second, by vCPU + memory + (optional) GPU
- **Spec range:** 0.25 vCPU / 0.5 GiB to 64 vCPU / 512 GiB per ECI
- **Quota:** Per-region account-level (not per-cluster)
- **Network:** ECI Pod ENI attaches to user's VPC/VSwitch; uses VPC security
  groups and route tables
- **Storage:** Cloud disks (CSI), NAS (CSI), OSS (CSI sidecars)
- **Image registry:** Any registry reachable from VPC; ACR recommended

### ECI Profile

A named bundle of ECI scheduling defaults (instance family, vCPU:mem ratio,
GPU model, security group, etc.). Profiles let multiple ASK clusters or
namespaces share consistent ECI settings.

- Default profile: `default`
- Profile is cluster-level (`$.profile` in DescribeClusterDetail)
- Profile changes via ModifyCluster (if supported; verify in OpenAPI)
- Custom profiles created out-of-band; cluster references by name

## Virtual Kubelet (the "1 virtual node")

When you run `kubectl get nodes` on an ASK cluster, you see **one** node named
something like `virtual-kubelet-cn-hangzhou-k`. This is **not a real
machine** — it's a virtual node that virtual-kubelet registers to bridge
K8s scheduling with ECI API calls.

> **⚠️ Agent warning:** Do not interpret "1 node" as "1 unit of capacity".
> Capacity in ASK is unbounded (subject to ECI quota). The virtual node is
> a scheduling interface, not a resource boundary.

## Resource Boundaries (what to monitor)

| Resource | Where to query | Why it matters |
|----------|---------------|----------------|
| ECI vCPU quota (account) | `acs_eci_dashboard` namespace | New Pods Pending when quota exhausted |
| ECI memory quota (account) | `acs_eci_dashboard` namespace | Same as above |
| ECI instance count quota | `acs_eci_dashboard` namespace | Same as above |
| ECI per-Pod spec limits | ECI spec table | Pod won't schedule if spec exceeds max |
| Cluster control plane | `acs_k8s_dashboard` namespace | API server health (Alibaba-managed) |
| Pod-level metrics | `kubectl top pods` / `acs_eci_dashboard` | HPA target / cost analysis |

## Network Model

ASK inherits the user's VPC. Key concepts:

| Concept | Role | Agent concern |
|---------|------|---------------|
| **VPC** | L2/L3 isolation | ECI Pod ENIs attach to user's VPC |
| **VSwitch (one or more, multi-AZ recommended)** | Subnet for ECI ENIs | Must have enough free IPs; prefer multi-AZ for HA |
| **NAT Gateway** | Egress to internet | Pods needing internet access require NAT in VPC; auto-SNAT is **off** by default |
| **Security Group** | L4 firewall on ECI ENIs | Inherits / assigns per cluster; restrict ingress to known sources |
| **Route Table** | VPC routing | Usually default; custom routes for private connectivity (e.g. to on-prem) |
| **PrivateZone** | Internal DNS | Enables `*.cluster.local` to resolve across VPC |
| **SLB (optional)** | Public K8s API server exposure | Auto-created when `endpoint_public_access_enabled=true` |

## Scheduling & Scaling

ASK has **no cluster autoscaler and no node pool scaler**. All scaling is
**Pod-level**:

| Mechanism | Use case | Example |
|-----------|----------|---------|
| **HPA** (Horizontal Pod Autoscaler) | CPU/memory/custom-metric driven | Scale on `cpu > 70%` |
| **CronHPA** | Time-based | Scale up at 8am, down at 10pm |
| **KEDA** | Event-driven | Scale on RabbitMQ queue length |
| **VPA** (Vertical Pod Autoscaler) | Adjust requests/limits | Less common in ASK; ASK billing is per-spec, so VPA may increase cost |
| **Manual** | `kubectl scale` | One-off |

> **Critical:** When HPA cannot scale (e.g. ECI quota exhausted, account
> balance low), Pods go `Pending` with `FailedScheduling`. Diagnose via
> `kubectl describe pod` Events — see [Troubleshooting](troubleshooting.md).

## Addon Compatibility (Node-level vs ECI-level)

Standard K8s addons can be classified by whether they assume worker nodes:

| Pattern | ASK Behavior | Example |
|---------|-------------|---------|
| Deployment | ✅ Works normally | `nginx-ingress-controller`, `metric-server`, `arms-prometheus` |
| DaemonSet (1 Pod per node) | ⚠️ Pods run on virtual-kubelet, may duplicate / not work as expected | `logtail-ds`, `node-problem-detector` |
| Static Pod / hostPath | ❌ Not supported on ECI | `kube-proxy` hostPath mounts |
| Node-level RBAC | ❌ ECI has no `node` role binding target | `node-exporter` |

**Rule of thumb:** If the addon's purpose is "observe/control a node", it
probably doesn't work in ASK. If it's a workload running in Pods, it's fine.

## Cost Model

```
Hourly ASK cost = Σ over running ECI Pods of
                  (vCPU_request × vCPU_price_per_sec) +
                  (memory_request_GB × mem_price_per_sec) +
                  (GPU_count × GPU_price_per_sec)

+ NAT Gateway hourly fee (if used)
+ SLB hourly fee (if endpoint_public_access_enabled)
+ (No fee for control plane, no idle node cost)
```

**Cost optimization levers:**
- Set HPA `minReplicas` low for dev, higher for prod
- Use CronHPA to scale down overnight
- Use ECI Savings Plans for stable 24/7 baseline
- Use ECI Spot for fault-tolerant batch

## Limits & Quotas (verify against current docs)

| Limit | Typical value | Source |
|-------|---------------|--------|
| Max ECI vCPU per region | 10000 (raiseable) | ECI console |
| Max ECI memory per region (GB) | 20000 (raiseable) | ECI console |
| Max ASK clusters per region | 50 (raiseable) | ACK console |
| Max Pods per ECI | 1 (ECI = Pod, not VM) | ECI spec |
| Max vCPU per ECI | 64 | ECI spec |
| Max memory per ECI (GB) | 512 | ECI spec |

> **Always query current quota before creating large clusters.** Use
> `aliyun eci ListUsage --body '{"RegionId":"your_region"}'` (verify CLI command).
> See [OpenAPI Verify Checklist](openapi-verify-checklist.md).

## When to Use ASK vs ManagedKubernetes

| Scenario | Recommendation |
|----------|----------------|
| Burst traffic (e.g. e-commerce promo) | **ASK** |
| Steady high-traffic production (always-on baseline) | **ManagedKubernetes** + savings plans |
| CI/CD runners, batch jobs | **ASK** (pay only for execution) |
| Stateful workloads needing host-level access | **ManagedKubernetes** |
| ML training (GPU) | Either, but verify GPU ECI availability per region |
| Dev/test environment, sporadic usage | **ASK** |
| Regulatory requirement for dedicated control plane | **Kubernetes** (dedicated) |
