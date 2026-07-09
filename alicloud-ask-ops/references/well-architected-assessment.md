# Well-Architected Assessment — ASK

This document maps ASK operations to Alibaba Cloud's
[Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html)
five pillars.

## §2.1 安全 (Security)

### Minimum RAM Permissions

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cs:CreateCluster",
        "cs:DescribeClusters",
        "cs:DescribeClusterDetail",
        "cs:DescribeClusterUserKubeConfig",
        "cs:DescribeClusterEndpoints",
        "cs:DeleteCluster",
        "cs:ModifyCluster",
        "cs:DescribeAddons",
        "cs:InstallAddon",
        "cs:DescribeClusterNodes"
      ],
      "Resource": "acs:cs:*:*:cluster/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "vpc:DescribeVpcs",
        "vpc:DescribeVSwitches"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "eci:CreateContainerGroup",
        "eci:DescribeContainerGroups",
        "eci:ListUsage"
      ],
      "Resource": "*"
    }
  ]
}
```

> **Do NOT use `cs:*` wildcard in production.** Scope to specific actions.
> ECI actions may be needed for advanced debugging.

### Network Isolation

| Recommendation | Rationale |
|----------------|-----------|
| `endpoint_public_access_enabled=false` (default) | API server stays VPC-only |
| Use **PrivateZone** for service DNS | Avoids leaking internal DNS to public resolvers |
| **Multi-AZ VSwitches** for ECI ENIs | HA + fault isolation |
| Restrict **security group** on ECI ENIs | Default SG may be too permissive |
| Use **SLB** with access logs for public API server (if enabled) | Audit trail |
| Disable public IP on ECI Pods unless needed | Reduce attack surface |

### Workload Security

| Recommendation | Rationale |
|----------------|-----------|
| Enable **Pod Security Standards (PSS)** | Restrict privileged containers |
| Use **OPA Gatekeeper** for policy enforcement | Cross-cutting guardrails |
| ECI forbids `hostNetwork` / `hostPID` | Confirmed by design — no action needed |
| **Image scanning** via ACR before deploy | Catches CVEs at build time |
| Rotate **cluster certificates** (managed by ACK) | Reduces cert exposure window |
| Kubeconfig **chmod 600**, never commit | Kubeconfig = client cert |
| Enable **K8s audit logging** | Forensics for security incidents |

### Credential Masking (MANDATORY)

| Execution Path | Safe | Unsafe |
|----------------|------|--------|
| Console | `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"` | `...=LTAI5t...` |
| Error message | `API call failed (credential omitted)` | `... actual secret ...` |
| Log | `[INFO] Secret=***` | `[INFO] Secret=LTAI5t...` |
| Bash check | `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"` | `echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET` |
| Go SDK | `tea.String(os.Getenv(...))` | `fmt.Printf("%+v", config)` |

## §2.2 稳定 (Stability)

### Failure-Oriented Design

| Pattern | ASK-Specific Implementation |
|---------|------------------------------|
| **Multi-AZ** | VSwitches in ≥ 2 AZs; ECI Pods distribute naturally |
| **Pod-level HA** | HPA `minReplicas >= 2` for production; PodDisruptionBudget |
| **Stateless workloads** | ECI Pods are ephemeral — design for it (no local state) |
| **State persistence** | Use external RDS / OSS / cloud disks (CSI) for any state |
| **Cold start tolerance** | First ECI Pod = 5-30s; design user experience for it |
| **Quota headroom** | Keep ECI quota usage < 80% |

### Fine-Grained Operations Control

| Metric to Monitor | Why |
|-------------------|-----|
| API Server latency P99 | Control plane is shared; high latency = upstream issue |
| HPA scaling events | Pattern of failures |
| ECI Pod OOMKilled | Right-size memory requests |
| Image pull latency | Cold start contributor |
| Pending Pod count | Quota / VSwitch / profile issue indicator |

### Risk-Oriented Fast Recovery

| Metric | Value |
|--------|-------|
| **RTO (cluster recreation)** | ~3-5 min |
| **RTO (ECI Pod re-schedule)** | ~30s |
| **RPO (stateless)** | 0 |
| **RPO (stateful)** | Per underlying storage; cloud disk = synchronous, OSS = async |

#### DR Runbook

```
Phase 1: Verify
    - Check cluster API health: kubectl get --raw=/healthz
    - Check ECI quota: aliyun cms DescribeMetricList
    - Check Pod readiness: kubectl get pods -A

Phase 2: Restore
    - If cluster is gone: re-run aliyun cs POST /clusters
    - If ECI quota exhausted: raise quota in ECI console
    - Reapply manifests: kubectl apply -f manifests/
    - Workloads auto-schedule to new ECI Pods

Phase 3: Validate
    - Pod scheduling: kubectl get pods -A
    - Service connectivity: kubectl get svc,endpoints -A
    - Application health: curl /healthz from outside
```

### Explicit Confirmation on Destructive Ops

| Operation | Confirmation Required |
|-----------|----------------------|
| DeleteCluster | Yes — irreversible |
| Modify deletion_protection = true | Yes — blocks future delete |
| Modify deletion_protection = false | Yes — enables delete |
| Force delete cluster | Yes — may leave orphaned resources |

## §2.3 成本 (Cost)

### Billing Model Comparison

| Model | Best For | Cost vs On-Demand |
|-------|----------|-------------------|
| **ECI on-demand (vCPU×sec, mem×sec)** | Variable workloads, dev/test, batch | Baseline |
| **ECI Savings Plans** | Stable 24/7 baseline | Up to 60% off |
| **ECI Spot** | Fault-tolerant batch / async jobs | Up to 90% off |
| **NAT Gateway hourly fee** | Pods needing internet | Flat hourly |
| **SLB hourly fee** | Public API server | Flat hourly |
| **Cluster control plane** | Always | **Free** |

> **No idle-node cost in ASK.** This is the primary cost advantage over
> ManagedKubernetes. You pay only for running ECI Pods.

### Waste Detection

| Pattern | Detection | Action |
|---------|-----------|--------|
| Idle ECI Pods | `kubectl top pods` shows CPU < 5% for 30 min | Tighten HPA `minReplicas`; review workload |
| Over-provisioned requests | request/usage ratio > 3x for > 7 days | Reduce requests (HPA uses requests, not limits) |
| HPA min > 0 but no traffic | 0 requests for > 1h | Set HPA `minReplicas=0` for dev |
| NAT Gateway without traffic | 0 SNAT bytes for > 7d | Delete NAT (after ECI Pods drained) |
| ECI Spot interrupted repeatedly | > 3 interruptions / hour | Switch to Savings Plans |

### Right-Sizing Mapping

| Observation | Recommendation |
|-------------|----------------|
| Pod uses 50% of `requests.cpu` | Reduce `requests.cpu` by 30%, let HPA handle spikes |
| Pod uses 80% of `requests.memory` | Bump `requests.memory` to actual + 20% headroom |
| Pod is OOMKilled | Bump memory `limits` (and matching `requests` for billing) |
| Cluster has 0 ECI Pods for 7d | Delete cluster (with confirmation) |

## §2.4 效率 (Efficiency)

### Auto-Scaling

| Mechanism | When | Caveat |
|-----------|------|--------|
| **HPA** | CPU/memory/custom metric | Needs `metric-server` addon |
| **CronHPA** | Predictable diurnal patterns | Use `ack-kubernetes-cronhpa` addon |
| **KEDA** | Event-driven (queue length, etc.) | Installed separately |

### Batch Operations

For creating many clusters / applying many manifests:
- Use **ArgoCD / Flux** for GitOps (not imperative apply)
- Use **Helm** for templated deployments
- Use **kubectl -l** to operate on label-selected resources
- For cluster creation: parallelize via shell `&` with rate-limit awareness

### CI/CD Integration

- All `aliyun cs` commands output JSON by default — no `--output json` needed
- Pipe to `jq` for parsing
- Use `--waiter` for CreateCluster / DeleteCluster
- Mask credentials in CI logs

## §2.5 性能 (Performance)

### Performance Baselines

| Metric | Healthy Range | Action if Outside |
|--------|---------------|-------------------|
| ECI Pod cold start P95 | < 30s | Optimize image; use same-region ACR |
| HPA scale-out latency | < 60s | Check metric-server; check ECI quota |
| API Server P99 latency | < 1s | (Alibaba-managed; contact support if persistent) |
| Cluster CPU (Pod sum) | < 70% | Reduce requests or scale up |

### Auto-Scaling Trigger Table

| Metric | Source | Scale Up | Scale Down | Window |
|--------|--------|----------|------------|--------|
| Pod CPU | `kubectl top` or `eci.cpu.usage` | > 70% | < 30% | 5 min |
| Pod Memory | `kubectl top` or `eci.memory.usage` | > 80% | < 50% | 5 min |
| Custom (queue length) | KEDA scaler | varies | 0 | 1 min |
| Cron (time) | CronHPA | schedule | schedule | — |

### Key Performance Guidance

- **HPA uses `requests`, not `limits`.** Set `requests` accurately.
  `limits` only matter for OOMKilled / CPU throttling.
- **Set `priorityClassName`** for critical workloads to win ECI scheduling
  under quota pressure.
- **Pre-pull images** for latency-sensitive services (set HPA `minReplicas >= 1`).
- **Use same-region ACR** to minimize image pull time.
- **Avoid GPU ECI for non-GPU workloads** (cost, availability).
