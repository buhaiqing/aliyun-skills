# Troubleshooting ASK

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `ErrorClusterNotFound` / 404 | Cluster does not exist | Verify `cluster_id`; may already be deleted |
| `ErrorClusterState` / 400 | Cluster not in valid state for operation | Wait for cluster to reach stable state (`running`) |
| `ErrorCheckAcl` / 403 | RAM permission denied | Delegate to RAM skill or user adds `cs:*` policy |
| `InvalidParameter` / 400 | Request validation failed | Cross-check body with OpenAPI; see common ASK-invalid fields below |
| `QuotaExceeded.Cluster` / 400 | Cluster count quota exceeded | HALT; user raises cluster quota via console |
| `QuotaExceeded.Vcpu` / 400 | ECI vCPU quota exceeded | HALT; user raises ECI vCPU quota |
| `QuotaExceeded.Memory` / 400 | ECI memory quota exceeded | HALT; user raises ECI memory quota |
| `QuotaExceeded.ECIInstance` / 400 | ECI instance count quota exceeded | HALT; user raises ECI instance quota |
| `InsufficientBalance` / 400 | Account balance insufficient | HALT |
| `DeletionProtection` / 400 | Cluster has deletion_protection=true | Refuse delete; ask user to disable |
| `DependencyResourceExist` / 400 | Resources still bound to cluster | Ask user to release SLB, PVCs, or other dependencies |
| `InternalError` / 500 | Server-side error | Retry with backoff; then HALT with `RequestId` |
| Throttling / 429 | API rate limit | Back off exponentially; respect `Retry-After` |

### Common ASK-specific `InvalidParameter` triggers

| Body field | Likely cause |
|------------|--------------|
| Includes `num_of_nodes` | ASK has no worker nodes; remove |
| Includes `worker_instance_types` | Remove |
| Missing `vpc_id` / `vswitch_ids` | ECI Pods need VPC/VSwitch |
| `container_cidr` is invalid / missing | **Verify** which network field is required (see [api-sdk-usage.md](api-sdk-usage.md)) |
| Missing required field (e.g. `profile`) | Check [OpenAPI Verify Checklist](openapi-verify-checklist.md) |

---

## Symptom-to-Root-Cause Quick Reference

| User Symptom | Most Likely Root Cause Category | First Check |
|--------------|----------------------------------|-------------|
| "Pod一直Pending" | ECI quota exhausted or spec exceeds ECI max | `kubectl describe pod` Events + ECI quota |
| "ECI调度失败" | ECI profile mismatch or vSwitch IP shortage | ECI profile config + VSwitch free IPs |
| "集群创建失败" | VPC/VSwitch config error or ECI quota | VPC validation + ECI quota check |
| "删除集群失败" | Deletion protection on, or resources bound | Check `$.deletion_protection` + `DescribeClusterDetail` |
| "kubectl get nodes 只有1个" | Normal — that's virtual-kubelet | Don't interpret as under-provisioned |
| "HPA不生效" | ECI quota, missing metrics-server, or wrong request | metric-server status + ECI quota |
| "ECI Pod 启动慢" | ECI image pull + cold start | ACR proximity + image size |
| "ECI Pod 出不去公网" | No NAT Gateway in VPC | `alicloud-nat-ops` to create NAT |
| "升级K8s版本失败" | ASK doesn't support UpgradeCluster | Reject; advise new cluster |
| "kubeconfig 拉取失败" | `endpoint_public_access_enabled=false` and not in VPC | Use `--PrivateIpAddress true` if in VPC, or enable public access |

---

## Scenario-Based Diagnostic Playbooks

### Scenario 1: "Pod一直Pending" (Pod Stuck in Pending)

**Symptoms:** Pod remains in `Pending` state. Cannot start. (Note: in ASK, "Pending" usually means ECI scheduling failed, NOT "waiting for node".)

**Diagnostic Flow:**

```bash
# Step 1: Get kubeconfig
aliyun cs GET /k8s/{{user.cluster_id}}/user_config > /tmp/ask-kubeconfig
export KUBECONFIG=/tmp/ask-kubeconfig

# Step 2: Check pod events
kubectl describe pod {{user.pod_name}} -n {{user.namespace}} | grep -A15 Events

# Step 3: Check ECI quota (verify CLI command first!)
# aliyun eci ListUsage --body '{"RegionId":"'$REGION'"}'

# Step 4: Check pod spec vs ECI max
kubectl get pod {{user.pod_name}} -n {{user.namespace}} -o json \
  | jq '.spec.containers[].resources'
```

**Decision Tree:**
- Events show `FailedScheduling: 0/N nodes are available` → ECI quota exhausted
- Events show `Insufficient eci vcpu` / `Insufficient eci memory` → Quota exhausted; raise ECI quota
- Events show `vSwitch ip insufficient` → VSwitch CIDR exhausted; add a larger VSwitch or remove unused ENIs
- Events show `Image pull error` → ACR or network issue
- Events show `forbidden: exceeded quota` → Quota issue
- Pod spec requests > ECI max (e.g. 128 vCPU) → Reduce request

---

### Scenario 2: "ECI 调度失败" (ECI Scheduling Failed)

**Symptoms:** New ECI Pods won't schedule, even though cluster has capacity.

**Diagnostic Flow:**

```bash
# Step 1: Check ECI profile exists and is correctly named
# aliyun eci DescribeContainerGroupProfile (verify CLI)

# Step 2: Check VSwitch has free IPs
aliyun vpc DescribeVSwitches --VSwitchId {{user.vswitch_id}} \
  --output cols=AvailableIpAddress,CidrBlock rows=VSwitches.VSwitch[].{AvailableIpAddress:AvailableIpAddress,CidrBlock:CidrBlock}

# Step 3: Check security group allows ECI ENI attachment
aliyun ecs DescribeSecurityGroups --RegionId $REGION

# Step 4: Check if ECI profile is restricted to specific instance families
# Verify profile config in ECI console
```

**Decision Tree:**
- VSwitch `AvailableIpAddress < Pod count` → Expand VSwitch CIDR or add VSwitch
- ECI profile has narrow instance family → Use broader profile or `default`
- Security group too restrictive → Loosen inbound from K8s API server CIDR
- Profile unavailable in current region → Use `default` profile

---

### Scenario 3: "集群创建失败" (Cluster Creation Failure)

**Symptoms:** ASK cluster creation fails or stuck in `initial`.

**Diagnostic Flow:**

```bash
# Step 1: Check cluster state
aliyun cs GET /clusters/{{user.cluster_id}} | jq '{cluster_id, state, cluster_type, current_version}'

# Step 2: Verify VPC and VSwitch exist
aliyun vpc DescribeVpcs --VpcId {{user.vpc_id}}
aliyun vpc DescribeVSwitches --VSwitchId {{user.vswitch_id}}

# Step 3: Check ECI vCPU/memory quota (region-level)
# aliyun eci ListUsage --body '{"RegionId":"'$REGION'"}'

# Step 4: Check RAM role
aliyun ram GetRole --RoleName "AliyunCSDefaultRole" 2>/dev/null \
  || echo "Role missing — create via alicloud-ram-ops"
```

**Decision Tree:**
- VPC/VSwitch not found → Create first via `alicloud-vpc-ops`
- ECI quota insufficient → Raise ECI quota in ECI console
- RAM role `AliyunCSDefaultRole` missing → Create via `alicloud-ram-ops`
- `ErrorCheckAcl` → RAM permission; `alicloud-ram-ops`
- `InsufficientBalance` → Add funds

---

### Scenario 4: "删除集群失败" (Delete Cluster Failed)

**Symptoms:** `DELETE /clusters/{id}` returns error.

**Diagnostic Flow:**

```bash
# Step 1: Check if deletion_protection is on
aliyun cs GET /clusters/{{user.cluster_id}} | jq '.deletion_protection'

# Step 2: Check for bound resources
aliyun cs GET /clusters/{{user.cluster_id}} | jq '{state, vpc_id, tags}'

# Step 3: List any SLBs auto-created for the cluster
# (no direct API; check via alicloud-slb-ops and filter by cluster tag)
```

**Decision Tree:**
- `deletion_protection = true` → Ask user to disable; retry
- `DependencyResourceExist` → User must release SLB / PVCs / DNS records
- Cluster state = `updating` / `initial` → Wait for stable state, retry
- `ErrorClusterNotFound` (404) → Already deleted; inform user

---

### Scenario 5: "HPA 不生效" (HPA Not Scaling)

**Symptoms:** HPA exists but `currentReplicas` stays at `minReplicas` even under load.

**Diagnostic Flow:**

```bash
# Step 1: Check HPA status
kubectl get hpa -n {{user.namespace}}
kubectl describe hpa {{user.hpa_name}} -n {{user.namespace}}

# Step 2: Check metrics-server is running
kubectl get pods -n kube-system -l k8s-app=metric-server
kubectl top nodes  # if this works, metrics-server is OK

# Step 3: Check ECI quota (HPA can scale but ECI may not be available)
# aliyun eci ListUsage --body '{"RegionId":"'$REGION'"}'

# Step 4: Check HPA target metrics are being scraped
kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/{{user.namespace}}/pods
```

**Decision Tree:**
- metrics-server missing → Install via addon (or via `kubectl apply` of metrics-server manifest)
- ECI quota exhausted → HPA can't create more ECI Pods; raise quota
- HPA `minReplicas` is the cap → Check if HPA has maxReplicas configured
- ECI profile mismatch → Pod spec may not match profile's instance family

---

### Scenario 6: "ECI Pod 启动慢" (ECI Pod Cold Start Slow)

**Symptoms:** First request to ASK service takes 5-30s.

**Diagnostic Flow:**

```bash
# Step 1: Check image size
# (large image → longer pull → longer cold start)
# aliyun cr DescribeImageManifest (if ACR)

# Step 2: Check if ACR is in same region as ASK cluster
# Cross-region image pull = slow

# Step 3: Check ECI pool warm-up
# If HPA minReplicas = 0, every request triggers cold start
```

**Decision Tree:**
- Image > 1GB → Optimize (multi-stage build, distroless)
- Cross-region image pull → Mirror to same-region ACR
- `minReplicas=0` for latency-sensitive service → Set `minReplicas >= 1`
- Network egress slow for image pull → Use ACR VPC endpoint

---

### Scenario 7: "ECI Pod 出不去公网" (ECI Pod Can't Reach Internet)

**Symptoms:** Pods running, but `curl https://example.com` fails with timeout.

**Diagnostic Flow:**

```bash
# Step 1: Check NAT Gateway exists in VPC
aliyun vpc DescribeNatGateways --VpcId {{user.vpc_id}} \
  --output cols=NatGatewayId,Status rows=NatGateways.NatGateway[].{NatGatewayId:NatGatewayId,Status:Status}

# Step 2: Check VSwitch has SNAT entry pointing to NAT
aliyun vpc DescribeSnatTableEntries --SourceVSwitchId {{user.vswitch_id}}

# Step 3: Check security group egress allows 0.0.0.0/0
aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId {{user.sg_id}}
```

**Decision Tree:**
- No NAT Gateway in VPC → Create via `alicloud-nat-ops`
- No SNAT entry for VSwitch → Add SNAT entry
- Security group egress restricted → Add egress rule for 0.0.0.0/0 (or specific destinations)
- DNS resolution fails inside Pod → Check CoreDNS / PrivateZone config

---

## Cluster State Reference

| State | Meaning | Actionable? |
|-------|---------|-------------|
| `initial` | Creating | Wait |
| `running` | Healthy | Yes |
| `updating` | Mutating (rare in ASK) | Wait |
| `failed` | Creation failed | Check logs; delete and recreate |
| `deleting` | Deleting | Wait |
| `deleted` | Deleted | N/A |

---

## One-Shot Diagnostic Scripts

### Script 1: ASK Cluster Health Check

```bash
#!/bin/bash
# ask-full-health-check.sh <ClusterId> <RegionId>
CLUSTER_ID="$1"
REGION="$2"

echo "=== Cluster Status ==="
aliyun cs GET /clusters/$CLUSTER_ID | jq '{cluster_id, name, cluster_type, state, current_version, created}'

echo ""
echo "=== ECI Quota (verify CLI) ==="
# aliyun eci ListUsage --body '{"RegionId":"'$REGION'"}'

echo ""
echo "=== Kubeconfig + Node Check ==="
aliyun cs GET /k8s/$CLUSTER_ID/user_config > /tmp/kubeconfig
export KUBECONFIG=/tmp/kubeconfig
kubectl get nodes -o wide
kubectl get pods -A --field-selector=status.phase!=Running | head -20

echo ""
echo "=== Recent Events ==="
kubectl get events -A --sort-by='.lastTimestamp' | tail -20
```

### Script 2: Pending Pods Deep Inspection

```bash
#!/bin/bash
# ask-pending-pods.sh
export KUBECONFIG=/tmp/kubeconfig

kubectl get pods -A --field-selector=status.phase=Pending -o json | \
  jq -r '.items[] | {ns:.metadata.namespace, pod:.metadata.name, reason:[
    .status.conditions[]? | select(.status=="False" and .reason=="PodScheduled") | .message
  ][0]}'
```

---

## Diagnostic Order (Standard)

1. **Describe cluster** by ID: `aliyun cs GET /clusters/{cluster_id}`
2. **Confirm cluster_type + profile identify ASK** — if not ASK, delegate to `alicloud-ack-ops`
3. **Check `state`** — must be `running` for most operations
4. **Get kubeconfig** (private endpoint): `aliyun cs GET /k8s/{id}/user_config --PrivateIpAddress true`
5. **Check ECI quota** at region level (verify CLI)
6. **List pending pods:** `kubectl get pods -A --field-selector=status.phase=Pending`
7. **Describe a pending pod:** `kubectl describe pod ...` — read Events
8. **Cross-skill delegation:** if VPC issue → `alicloud-vpc-ops`; if ECI quota → [`alicloud-eci-ops`](../../alicloud-eci-ops/SKILL.md); if RAM → `alicloud-ram-ops`
