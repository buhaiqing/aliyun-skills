# ECI Core Concepts

## What is ECI?

**ECI (Elastic Container Instance)** is Alibaba Cloud's Serverless container
runtime. Each ECI is a **ContainerGroup** — a pod-equivalent unit that runs
in your VPC, billed per-second by vCPU + memory (+ optional GPU), with
**no node to manage**.

```
┌────────────────────────────────────────────────────────────────┐
│                          User VPC                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    ContainerGroup (ECI)                   │  │
│  │   ┌──────────┐    ┌──────────┐    (shared netns,         │  │
│  │   │Container │    │Container │     shared volumes,         │  │
│  │   │  "app"   │    │  "side"  │     shared lifecycle)       │  │
│  │   │image:v1  │    │image:log │                             │  │
│  │   └────┬─────┘    └────┬─────┘                             │  │
│  │        └──────┬───────┘                                    │  │
│  │               │  eth0 (ENI)                                │  │
│  │               ▼                                            │  │
│  └───────────────┼────────────────────────────────────────────┘  │
│                  │                                              │
│                  ▼                                              │
│           ┌──────────────┐    ┌──────────┐   ┌──────────────┐  │
│           │  VSwitch     │    │  NAT GW  │   │SecurityGroup │  │
│           └──────────────┘    └──────────┘   └──────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

## Key Concepts

| Term | Definition | K8s Equivalent |
|------|------------|----------------|
| **ContainerGroup** | The ECI unit; 1..N containers + shared network + shared volumes | Pod |
| **Container** | Individual container inside a ContainerGroup | Container |
| **ContainerGroupId** | Unique ID for the ECI | Pod UID |
| **Region / VPC / VSwitch / SecurityGroup** | Network binding (inherits from user VPC) | Same |

## Three Ways to Use ECI

| Pattern | Description | Use this skill? |
|---------|-------------|----------------|
| **Standalone ECI** | Direct `aliyun eci CreateContainerGroup` calls | ✅ Yes |
| **ASK (cluster_type=Ask)** | ECI used as K8s Pod backend, managed via K8s API | ❌ Use `alicloud-ack-serverless-ops` |
| **Virtual Kubelet bridge** | Other K8s clusters schedule ECI via virtual-kubelet | ❌ Use the parent cluster's skill |

> **Critical:** Don't run both this skill and `alicloud-ack-serverless-ops`
> on the same workload. If the user says "manage my ASK cluster", use the
> ASK skill. If they say "create an ECI directly", use this one.

## RestartPolicy

| Value | Behavior | Use case |
|-------|----------|----------|
| `Never` | Container exits → ECI terminates (transitions to `Succeeded` or `Failed`) | Batch jobs, one-off tasks |
| `OnFailure` | Restart only on non-zero exit | Retry-able tasks with backoff |
| `Always` | Always restart (even on exit 0) | Long-running services (but consider ASK instead) |

> **⚠️ `Always` + a crashed container = infinite billing.** Use sparingly.

## Resource Spec

| Field | Type | Description |
|-------|------|-------------|
| `Cpu` | float | Total vCPU for the ContainerGroup (e.g. `1.0`, `2.5`) |
| `Memory` | float | Total memory in GB (e.g. `2.0`, `8.0`) |
| `Container[].Cpu` | float | Per-container vCPU (verify support) |
| `Container[].Memory` | float | Per-container memory in GB (verify support) |

**Limits (typical, verify with current docs):**

| Dimension | Min | Max |
|-----------|-----|-----|
| vCPU | 0.25 | 64 |
| Memory (GB) | 0.5 | 512 |
| Containers per CG | 1 | 10 (verify) |

## Network

ECI inherits the user's VPC. Key bindings:

| Field | Required | Description |
|-------|----------|-------------|
| `VSwitchId` | ✅ Yes | Subnet for the ECI ENI |
| `SecurityGroupId` | ✅ Yes | SecurityGroup on the ECI ENI |
| `VpcId` | Optional | Inferred from VSwitch; specify to disambiguate |
| `IntranetIp` | (output) | ECI's private IP, assigned from VSwitch CIDR |

**Egress:** ECI uses the VPC's NAT Gateway for internet access. **No
default outbound** — pre-create NAT if needed.

## Storage / Volumes

| Volume Type | Use case | Notes |
|-------------|----------|-------|
| **EmptyDir** | Scratch space | Per-ContainerGroup lifecycle |
| **ConfigFile** | Mount ConfigMap-like data | **Verify support** |
| **NAS** | Shared filesystem across ECIs | NFS v3; pre-provision NAS filesystem |
| **OSS** | Object storage mount | via ossfs / sidecar |
| **Cloud Disk** | Persistent block storage | Per-AZ; cannot attach across AZ |

> **⚠️ Verify** the exact support matrix via OpenAPI verify checklist.

## Private Image Registry

For private registry (e.g. ACR), pass credentials:

```bash
--ImageRegistryCredential.Server "registry.cn-hangzhou.aliyuncs.com" \
--ImageRegistryCredential.User "<username>" \
--ImageRegistryCredential.Password "<password>"
```

> **⚠️ Verify exact parameter shape** via `aliyun eci CreateContainerGroup --help`.

## Lifecycle / Status

| Status | Meaning | Agent Action |
|--------|---------|--------------|
| `Pending` | Provisioning ENI / pulling image | Wait; investigate if > 60s |
| `Scheduling` | Awaiting ECI quota / VSwitch IP | Check quota; raise if needed |
| `Running` | At least 1 container running | Yes — can Exec |
| `Succeeded` | All containers exited 0 (RestartPolicy=Never/OnFailure) | Yes — read logs / delete |
| `Failed` | At least 1 container exited non-zero | Yes — read logs; consider recreate |
| `SchedulingFailed` | Quota exhausted, cannot schedule | Raise quota; retry |

## Billing Model

```
Per-second cost = (Cpu × vCPU_price) + (Memory_GB × mem_price) + (Gpu × gpu_price)
                + (volume costs, if any)
```

- **No idle cost** when ContainerGroup is not running
- **No control plane cost** (none for ECI)
- **NAT Gateway** separately billed (if used)
- **Volume costs** depend on volume type (NAS, OSS, cloud disk)

**Optimization levers:**
- `RestartPolicy=Never` to avoid infinite restart
- Right-size `Cpu` / `Memory` to actual usage
- Use ECI Spot for fault-tolerant batch
- Use ECI Savings Plans for stable 24/7 baseline

## Limits & Quotas (verify against current docs)

| Limit | Typical value | Source |
|-------|---------------|--------|
| Max vCPU per ContainerGroup | 64 | ECI spec |
| Max memory per CG (GB) | 512 | ECI spec |
| Region vCPU quota | 10000+ (raiseable) | ECI console |
| Region memory quota (GB) | 20000+ (raiseable) | ECI console |
| Containers per CG | 10 (verify) | ECI spec |
| Volumes per CG | (verify) | ECI spec |

> **Always query current quota** before large batch creation:
> `aliyun eci ListUsage --body '{"RegionId":"'$REGION'"}'`

## When to Use ECI vs ASK

| Scenario | Recommendation |
|----------|----------------|
| One-off batch job | **ECI** (no cluster overhead) |
| Long-running services | **ASK** (K8s ecosystem, easier management) |
| CI/CD runners | **ECI** (pay only for execution) |
| ML inference on demand | **ECI** (GPU available) |
| Scheduled jobs (cron-like) | Either; ECI + external scheduler, or ASK CronHPA |
| Multi-container tightly coupled (sidecar) | Either; same API in both |
| Need HPA / K8s Service / K8s Ingress | **ASK** (K8s ecosystem) |
| Need to integrate with existing K8s cluster | **Virtual Kubelet** (other K8s + ECI) |
