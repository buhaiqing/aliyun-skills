# Well-Architected Assessment — ECI

This document maps ECI operations to Alibaba Cloud's
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
        "eci:CreateContainerGroup",
        "eci:DescribeContainerGroups",
        "eci:DescribeContainerGroup",
        "eci:DescribeContainerGroupQuota",
        "eci:DeleteContainerGroup",
        "eci:UpdateContainerGroup",
        "eci:ExecContainerCommand"
      ],
      "Resource": "acs:eci:*:*:containergroup/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "vpc:DescribeVpcs",
        "vpc:DescribeVSwitches",
        "ecs:DescribeSecurityGroups"
      ],
      "Resource": "*"
    }
  ]
}
```

> **Do NOT use `eci:*` wildcard in production.** Scope to specific actions.

### Network Isolation

| Recommendation | Rationale |
|----------------|-----------|
| Place ECI in **private subnets** (no public IP) | Reduce attack surface |
| **Restrict SecurityGroup** ingress to known sources | Default SG may be too permissive |
| Use **NAT Gateway** for egress only (no EIP on ECI) | Auditable egress |
| **Multi-AZ VSwitches** for HA | Single AZ = SPOF |
| **Private registry** (ACR) over public DockerHub | Reduced supply-chain risk |

### Image Security

| Recommendation | Rationale |
|----------------|-----------|
| **Pin image digest** (`@sha256:...`) | Prevent supply-chain substitution |
| **Scan** with ACR vulnerability scanner | Catch CVEs at build time |
| **Minimal base image** (distroless, alpine) | Smaller attack surface |
| **Non-root user** in Dockerfile | Container escapes limited |
| **Read-only root filesystem** where possible | Limit runtime tampering |

### Exec Security

`ExecContainerCommand` is equivalent to `docker exec` — treat as
**privileged** access:

- **Log every exec invocation** (corp audit)
- **Restrict to on-call** via `eci:ExecContainerCommand` policy
- **Prefer kubectl exec** (via ASK) over ECI exec for K8s workloads

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

| Pattern | ECI Implementation |
|---------|---------------------|
| **Idempotency** | Always pass `ClientToken` for CreateContainerGroup |
| **RestartPolicy=Never** for batch | Avoids infinite restart loop (and infinite billing) |
| **RestartPolicy=OnFailure** for retry-able | With backoff (verify ECI supports) |
| **External state** | Cloud disk / RDS / OSS — ECI is ephemeral |
| **Quota headroom** | Keep region usage < 80% |

### Fine-Grained Operations Control

| Metric to Monitor | Why |
|-------------------|-----|
| ECI Scheduling duration | Quota / capacity issue indicator |
| Container `RestartCount` | Crash loop detection |
| OOMKilled events | Memory right-sizing |
| Image pull duration | Cold start contributor |
| `Failed` ECI count | Configuration / image issue indicator |

### Risk-Oriented Fast Recovery

| Metric | Value |
|--------|-------|
| **RTO (single ECI recreation)** | ~30-60s (image pull dependent) |
| **RTO (bulk recreation)** | Parallel with `&` + rate-limit awareness |
| **RPO (stateless)** | 0 |
| **RPO (stateful)** | Per underlying storage; cloud disk = sync, OSS = async |

#### DR Runbook

```
Phase 1: Verify
    - List current ECIs: aliyun eci DescribeContainerGroups
    - Identify failed/missing workloads

Phase 2: Restore
    - Recreate ECI: aliyun eci CreateContainerGroup (with same image + spec)
    - For stateful: reattach volume, restore data from snapshot

Phase 3: Validate
    - Status == Running: aliyun eci DescribeContainerGroup
    - Smoke test: aliyun eci ExecContainerCommand ... --Command "<health-check>"
```

### Explicit Confirmation on Destructive Ops

| Operation | Confirmation Required |
|-----------|----------------------|
| DeleteContainerGroup | Yes — kills running workloads |
| Bulk cleanup script | Yes — log what you delete first |
| UpdateContainerGroup (image change) | Yes — forces restart |

## §2.3 成本 (Cost)

### Billing Model

```
Per-second cost = (Cpu × vCPU_price) +
                  (Memory_GB × mem_price) +
                  (Gpu × gpu_price) +
                  (volume costs, if any)
```

| Model | Best For | Savings |
|-------|----------|---------|
| **ECI on-demand** | Variable workloads, batch | Baseline |
| **ECI Savings Plans** | Stable 24/7 baseline | Up to 60% |
| **ECI Spot** | Fault-tolerant batch | Up to 90% |
| **GPU ECI** | ML inference, batch | Pay per use |
| NAT Gateway (egress) | Internet-bound ECI | Flat hourly |

> **No idle cost** for ECI (unlike ECS nodes). This is the primary cost
> advantage.

### Waste Detection

| Pattern | Detection | Action |
|---------|-----------|--------|
| `RestartPolicy=Always` + crash | `RestartCount` rising | Change to `Never` or `OnFailure` |
| Over-provisioned Cpu/Memory | `eci.cpu.usage` < 10% avg over 7d | Right-size |
| Long-running idle ECI | Running > 24h with no activity | Delete or set TTL |
| Cloud disk / NAS not cleaned up | ECI deleted but disk still exists | Build cleanup pass |

### Right-Sizing Mapping

| Observation | Recommendation |
|-------------|----------------|
| Container uses 30% of `Cpu` | Reduce `Cpu` by 30% |
| Container OOMKilled | Bump `Memory` |
| Container uses 80% of `Memory` | Bump `Memory` to usage + 20% headroom |
| ECIs finish in seconds but `Memory` is high | Reduce `Memory` (don't pay for unused) |
| Image pull > 60s | Use smaller image / same-region ACR |

## §2.4 效率 (Efficiency)

### Batch Creation

For many independent ECIs:

```bash
# Create 10 ECIs in parallel (respect rate limit)
for i in $(seq 1 10); do
  aliyun eci CreateContainerGroup --RegionId $REGION \
    --ContainerGroupName "job-$i" \
    --Container.1.Name worker --Container.1.Image "job:v1" \
    --Cpu 1 --Memory 2 \
    --VSwitchId $VSW --SecurityGroupId $SG \
    --RestartPolicy Never &
done
wait
```

### Image Pre-Pull

ECI doesn't have a built-in image cache pre-pull. For latency-sensitive
workloads:
- Use **smaller images** (multi-stage builds, distroless)
- **Same-region ACR** to minimize image pull network cost
- Consider **ASK with pre-pulled image** for repeated workloads

### Right-Sizing

ECI bills per-spec, not per-usage. Right-size `Cpu` / `Memory` to actual
workload. The "default" of `Cpu=1, Memory=2` is rarely correct for batch
workloads.

### CI/CD Integration

- All `aliyun eci` commands output JSON by default
- Pipe to `jq` for parsing
- Mask credentials in CI logs
- Use `ClientToken` for idempotent retry in CI

## §2.5 性能 (Performance)

### Performance Baselines

| Metric | Healthy Range | Action if Outside |
|--------|---------------|-------------------|
| Image pull (cold start) | < 60s for 1GB image | Optimize image; same-region ACR |
| Container Ready latency (after image pulled) | < 10s | Inspect app startup |
| ECI Scheduling duration | < 30s | Check quota, VSwitch IP |
| Container CPU usage | < 70% avg | Increase Cpu or scale out |
| Container Memory usage | < 80% avg | Increase Memory |

### Auto-Scaling

ECI doesn't have a built-in auto-scaler. For dynamic scaling:

| Pattern | Tool |
|---------|------|
| Scale ECI on metric (CPU, queue length) | External scheduler (e.g. KEDA + virtual-kubelet, or your own controller) |
| Scale ECI on time | Cron + script |
| Burst handling | Pre-create a pool of warm ECIs (`min count`) |
| Steady baseline | ECI Savings Plans |

> **For most auto-scaling scenarios, prefer ASK + HPA over direct ECI
> management.**

### Key Performance Guidance

- **Right-size `Cpu` / `Memory`** — over-provisioning is direct cost waste
- **Pin image digest** — `image:v1` is mutable; `@sha256:...` is not
- **Multi-container** when tightly coupled (sidecar pattern) — share
  network and lifecycle
- **InitContainer** (verify support) for one-time setup before main app

---

## §附录 Quick Reference Card

```
┌───────────────────────────────────────────────────────┐
│  ECI 5-Pillar Summary                                 │
├───────────────────────────────────────────────────────┤
│  Security: Private SG, NAT egress, pinned digest,    │
│            logged exec                               │
│  Stability: ClientToken, RestartPolicy=Never,         │
│             external state, quota headroom           │
│  Cost: Per-sec billing, right-size, no idle cost,    │
│        RestartPolicy sanity check                    │
│  Efficiency: Batch via &+wait, smaller images,       │
│              same-region ACR                         │
│  Performance: Image pull < 60s, Scheduling < 30s,    │
│                CPU < 70%, Mem < 80%                  │
└───────────────────────────────────────────────────────┘
```
