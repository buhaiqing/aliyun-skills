# Troubleshooting ECI (VERIFIED 2026-06-02)

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `InvalidParameter` / 400 | Request validation failed | Cross-check body with OpenAPI; see common ECI-invalid fields below |
| `InvalidParameter.CPU.Memory` / 400 | Cpu/Memory spec invalid or container sum > CG | Match container spec ≤ CG spec |
| `InvalidParameter.DuplicatedName` | Container names not unique in CG | Rename containers |
| `InvalidParameter.DuplicatedVolumeName` | Volume names not unique | Rename volumes |
| `QuotaExceeded` / 400 | ECI region quota exhausted | HALT; user raises ECI quota in ECI console |
| `InvalidVSwitchId.IpNotEnough` / 400 | VSwitch CIDR exhausted | HALT; expand VSwitch CIDR or use another VSwitch |
| `InvalidDiskId.NotFound` / 404 | Cloud disk ID not found | Verify disk exists; or use FlexVolume |
| `ImageSnapshot.NotFound` / 404 | Image cache not found | Create via `CreateImageCache` first, or remove `ImageSnapshotId` |
| `ImagePullError` | Image not found or registry credentials wrong | Verify image name; verify `ImageRegistryCredential` (Server/UserName/Password) |
| `OperationDenied.VswZoneMisMatch` / 403 | VSwitch not in the specified Zone | Use VSwitch matching CG's ZoneId |
| `OperationDenied.SecurityGroupMisMatch` / 403 | VSwitchId and SecurityGroupId not in same VPC | Use SG in the same VPC |
| `DiskVolume.NotSupport` | DiskVolume type deprecated | Switch to FlexVolume with `alicloud/disk` driver |
| `UnsupportedVolumeType` | Volume type not supported for ECI | Switch to supported volume type (EmptyDir / NFS / etc.) |
| `InsufficientBalance` / 400 | Account balance insufficient | HALT |
| `ErrorCheckAcl` / 403 | RAM permission denied | Delegate to RAM skill or user adds `eci:*` policy |
| `ContainerGroupNotFound` / 404 | ECI does not exist | Verify `ContainerGroupId`; may already be deleted |
| `ContainerGroupInTransition` / 409 | ECI is in a non-stable state | Wait for terminal state; retry |
| `DependencyResourceExist` / 400 | Resources still bound to ECI | Ask user to release volumes / attached resources |
| Throttling / 429 | API rate limit | Back off exponentially; respect `Retry-After` |
| `InternalError` / 500 | Server-side error | Retry with backoff; then HALT with `RequestId` |

### Common ECI-specific `InvalidParameter` triggers

| Body field | Likely cause |
|------------|--------------|
| Missing `VSwitchId` | ECI needs a VSwitch; pre-create via `alicloud-vpc-ops` |
| Missing `SecurityGroupId` | Pre-create via `alicloud-vpc-ops` / `alicloud-ecs-ops` |
| `Cpu` < 0.25 or > 64 | Out of ECI spec range |
| `Memory` < 0.5 or > 512 (verify) | Out of ECI spec range |
| Sum of container specs > CG total | Mismatch; container sum must ≤ CG total |
| Image from private registry without `ImageRegistryCredential` | Add credential block with `Server`/`UserName`/`Password` |
| `RestartPolicy` invalid value | Verify allowed values: `Never` / `Always` / `OnFailure` |
| `ExecContainerCommand --Command` is a string, not JSON array | Use `'["cmd","arg1"]'` format |
| `ImageRegistryCredential.UserName` typo (should be `UserName`, not `Username`) | Fix field name |

---

## Symptom-to-Root-Cause Quick Reference

| User Symptom | Most Likely Root Cause Category | First Check |
|--------------|----------------------------------|-------------|
| "ECI 一直 Scheduling" | Quota exhausted or VSwitch IP insufficient | `ListUsage` + VSwitch `AvailableIpAddress` |
| "ECI 创建失败" | Invalid VSwitch / SG / image | `DescribeContainerGroup` for events (if created) |
| "ECI 容器起不来" | Image pull error, app crash | ExecCommand + container logs |
| "ECI 创建后访问不到" | Security group ingress, missing EIP, route table | SG rule + EIP + route table |
| "ECI 删除失败" | Resources still bound (volume) | Describe ECI; release dependencies |
| "ECI 费用异常高" | `RestartPolicy=Always` + crash, or over-provisioned | Inspect logs; right-size |
| "ExecContainerCommand 失败" | ECI not in `Running`, or wrong container name | Status + container name |
| "ECI 配额不足" | Region quota exhausted | Raise quota in ECI console |

---

## Scenario-Based Diagnostic Playbooks

### Scenario 1: "ECI 一直 Scheduling" (Stuck in Scheduling)

**Symptoms:** ECI is created but never transitions to `Running`. Status
remains `Scheduling` for minutes.

**Diagnostic Flow:**

```bash
# Step 1: Verify status
aliyun eci DescribeContainerGroups --RegionId $REGION \
  --ContainerGroupIds.1 "[\"$CG_ID\"]" \
  --output cols=ContainerGroupId,Status \
  rows=ContainerGroups[].{ContainerGroupId:ContainerGroupId,Status:Status}

# Step 2: Check ECI region quota (CORRECTED command)
aliyun eci ListUsage --body "{\"RegionId\":\"$REGION\"}"

# Step 3: Check VSwitch free IPs
aliyun vpc DescribeVSwitches --VSwitchId $VSW_ID \
  --output cols=AvailableIpAddress,CidrBlock \
  rows=VSwitches.VSwitch[].{AvailableIpAddress:AvailableIpAddress,CidrBlock:CidrBlock}

# Step 4: Check if region/zone has capacity
# (no direct API; usually related to ECI quota)
```

**Decision Tree:**

- Quota field in ListUsage response > 0.9 → Quota exhausted; raise in ECI console
- VSwitch `AvailableIpAddress < 5` → Expand VSwitch CIDR or pick another
- Quota OK, IP OK → May be ECI capacity issue; try another AZ/VSwitch

---

### Scenario 2: "ECI 创建失败" (Creation Failed)

**Symptoms:** CreateContainerGroup returns an error or ECI immediately
transitions to `Failed`.

**Diagnostic Flow:**

```bash
# Step 1: Check for events on the ECI
aliyun eci DescribeContainerGroup --RegionId $REGION --ContainerGroupId $CG_ID \
  | jq '.Events, .Status'

# Step 2: Verify VSwitch / SG exist
aliyun vpc DescribeVSwitches --VSwitchId $VSW_ID
aliyun ecs DescribeSecurityGroups --SecurityGroupIds.1 $SG_ID

# Step 3: Verify image is reachable
# Try a known-good public image (nginx:1.25) to isolate image vs infra issue

# Step 4: Check RAM role / permissions
aliyun ram GetUser
```

**Decision Tree:**

- Events show `InvalidVSwitchId.IpNotEnough` → Expand VSwitch
- Events show `QuotaExceeded` → Raise quota
- Events show `ImagePullError` → Fix image name / `ImageRegistryCredential` (Server/UserName/Password)
- Events show `SecurityGroupNotFound` → Create SG via `alicloud-vpc-ops`
- All OK but still failing → Contact Alibaba support with `RequestId`

---

### Scenario 3: "ECI 容器起不来" (Container Won't Start)

**Symptoms:** ECI is in `Running` but containers keep restarting or never
become ready.

**Diagnostic Flow:**

```bash
# Step 1: Check container status
aliyun eci DescribeContainerGroup --RegionId $REGION --ContainerGroupId $CG_ID \
  | jq '.Containers[] | {Name, Status, RestartCount, Image}'

# Step 2: Get container logs via Exec (CORRECTED Command syntax)
aliyun eci ExecContainerCommand --RegionId $REGION \
  --ContainerGroupId $CG_ID --ContainerName app \
  --Command '["/bin/sh", "-c", "ls -la /tmp && cat /var/log/app.log 2>/dev/null | tail -50"]' \
  --Sync true

# Step 3: Inspect container's process / port
aliyun eci ExecContainerCommand ... --Command '["ps","auxf"]' --Sync true
aliyun eci ExecContainerCommand ... --Command '["netstat","-tlnp"]' --Sync true
aliyun eci ExecContainerCommand ... --Command '["ss","-tlnp"]' --Sync true

# Step 4: Check if RestartPolicy is causing infinite restart
# (RestartPolicy=Always + crash = infinite loop)
```

**Decision Tree:**

- `RestartCount` climbing rapidly → App crash; inspect logs
- Container exits immediately → Check `Command` / `Arg` / image `ENTRYPOINT`
- Container running but port not listening → App not started; inspect logs
- `OOMKilled` → Increase `Memory`
- App depends on missing config (env var, secret) → Pass via `EnvironmentVar[]`

---

### Scenario 4: "ECI 访问不到" (Cannot Reach ECI)

**Symptoms:** ECI is `Running` but you can't curl/SSH to it from inside
or outside the VPC.

**Diagnostic Flow:**

```bash
# Step 1: Confirm ECI is in Running with valid IP
aliyun eci DescribeContainerGroup --RegionId $REGION --ContainerGroupId $CG_ID \
  | jq '{Status, IntranetIp, Containers}'

# Step 2: Test from another ECI / ECS in same VPC
# aliyun ecs RunCommand ... to exec ping/curl

# Step 3: Check Security Group ingress
aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId $SG_ID \
  | jq '.Permissions.Permission[] | select(.Direction=="ingress")'

# Step 4: Check route table for VSwitch
aliyun vpc DescribeRouteTables --VpcId $VPC_ID

# Step 5: For internet access from ECI, check NAT Gateway
aliyun vpc DescribeNatGateways --VpcId $VPC_ID \
  | jq '.NatGateways.NatGateway[] | {NatGatewayId, Status}'
```

**Decision Tree:**

- ECI has no `IntranetIp` → ENI not attached; investigate
- SG has no ingress rule for source CIDR → Add rule
- Route table doesn't have route to target → Add route
- ECI needs internet but no NAT → Create NAT Gateway via `alicloud-nat-ops`
  OR use `AutoCreateEip=true` when creating the ECI
- ECI needs internet but no SNAT entry for VSwitch → Add SNAT entry

---

### Scenario 5: "ECI 删除失败" (Delete Failed)

**Symptoms:** `DeleteContainerGroup` returns `DependencyResourceExist` or
similar.

**Diagnostic Flow:**

```bash
# Step 1: Describe ECI to see attached resources
aliyun eci DescribeContainerGroup --RegionId $REGION --ContainerGroupId $CG_ID \
  | jq '{Volumes, Status}'

# Step 2: Check if cloud disk / NAS is still attached
aliyun ecs DescribeDisks --RegionId $REGION \
  --DiskIds.1 $DISK_ID

# Step 3: Check if any other CG references the same volume
# (manual: search DescribeContainerGroups output for the volume)
```

**Decision Tree:**

- Volume attached → User must release; cannot delete ECI while volume bound
- ECI in `Pending` / `Running` → Wait for terminal state, then delete
- Other dependency → Resolve per API error message

---

### Scenario 6: "ECI 费用异常高" (Unexpected Cost)

**Symptoms:** ECI cost in billing is much higher than expected.

**Diagnostic Flow:**

```bash
# Step 1: List all your ECIs and their status
aliyun eci DescribeContainerGroups --RegionId $REGION \
  --output cols=ContainerGroupId,Name,Status,Cpu,Memory,CreatedTime \
  rows=ContainerGroups[].{ContainerGroupId:ContainerGroupId,Name:ContainerGroupName,Status:Status,Cpu:Cpu,Memory:Memory,CreatedTime:CreatedTime}

# Step 2: Find ECIs with high RestartCount (crash loops)
aliyun eci DescribeContainerGroups --RegionId $REGION \
  --output cols=ContainerGroupId,Name,ContainerRestartCount \
  rows=ContainerGroups[].{ContainerGroupId:ContainerGroupId,Name:ContainerGroupName,ContainerRestartCount:sum(Containers[].RestartCount)}

# Step 3: Find ECIs running for > 24h with no activity
# (combine with SLS logs or business-level activity)
```

**Decision Tree:**

- `RestartPolicy=Always` + crash loop → **infinite billing**; change to `Never`
- Over-provisioned `Cpu` / `Memory` → Right-size to actual usage
- ECIs running but idle → Delete or set TTL
- Cloud disk / NAS not cleaned up → Build cleanup pass

---

## ECI Status Reference

| Status | Meaning | Actionable? |
|--------|---------|--------------|
| `Pending` | Provisioning ENI / pulling image | Wait; investigate if > 60s |
| `Scheduling` | Awaiting ECI quota / VSwitch IP | Check quota; raise if needed |
| `Running` | At least 1 container running | Yes — can Exec |
| `Succeeded` | All containers exited 0 (RestartPolicy=Never/OnFailure) | Yes — can delete |
| `Failed` | At least 1 container exited non-zero | Yes — read logs; consider recreate |
| `SchedulingFailed` | Quota exhausted, cannot schedule | Raise quota; retry |

---

## One-Shot Diagnostic Scripts

### Script 1: ECI Health Snapshot

```bash
#!/bin/bash
# eci-snapshot.sh <RegionId>
REGION="$1"

echo "=== ECI Quota (corrected command) ==="
aliyun eci ListUsage --body "{\"RegionId\":\"$REGION\"}"

echo ""
echo "=== Status Distribution ==="
aliyun eci DescribeContainerGroups --RegionId $REGION \
  --output cols=Status rows=ContainerGroups[].Status \
  | sort | uniq -c

echo ""
echo "=== Failed ECIs ==="
aliyun eci DescribeContainerGroups --RegionId $REGION --Status Failed \
  --output cols=ContainerGroupId,Name \
  rows=ContainerGroups[].{ContainerGroupId:ContainerGroupId,Name:ContainerGroupName}

echo ""
echo "=== Scheduling > 5min (potential quota issue) ==="
# (no direct time filter; would need to filter by CreatedTime)
```

### Script 2: Bulk Delete Failed/Succeeded ECIs Older Than N Hours

```bash
#!/bin/bash
# eci-bulk-cleanup.sh <RegionId> <MaxAgeHours>
REGION="$1"
MAX_AGE_HOURS="$2"
NOW=$(date +%s)

aliyun eci DescribeContainerGroups --RegionId "$REGION" \
  --Status Succeeded --Status Failed \
  --output cols=ContainerGroupId,CreatedTime \
  rows=ContainerGroups[].{ContainerGroupId:ContainerGroupId,CreatedTime:CreatedTime} \
  | while read -r ID CREATED; do
      CREATED_TS=$(date -d "$CREATED" +%s 2>/dev/null || echo 0)
      AGE_HOURS=$(( (NOW - CREATED_TS) / 3600 ))
      if [ "$AGE_HOURS" -gt "$MAX_AGE_HOURS" ]; then
        echo "Deleting $ID (age: ${AGE_HOURS}h)"
        aliyun eci DeleteContainerGroup --RegionId "$REGION" --ContainerGroupId "$ID"
      fi
    done
```

> Use with caution. Always log what you delete.

---

## Diagnostic Order (Standard)

1. **Check ECI status:** `aliyun eci DescribeContainerGroup --ContainerGroupId $ID`
2. **Check quota** if `Scheduling`: `aliyun eci ListUsage --body '{"RegionId":"..."}'`
3. **Check VSwitch free IPs** if `Scheduling`: `aliyun vpc DescribeVSwitches`
4. **Check container logs / events** if `Failed`: `DescribeContainerGroup` `$.Events`
5. **Exec into container** for interactive diagnosis: `aliyun eci ExecContainerCommand --Command '["..."]'` (JSON array!)
6. **Cross-skill delegation:** if VPC issue → `alicloud-vpc-ops`; if RAM → `alicloud-ram-ops`; if image pull → `alicloud-acr-ops` (when present)
