# NAS Troubleshooting

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `InvalidFileSystem.NotFound` | File system ID does not exist | Verify with `DescribeFileSystems`; check region |
| `InvalidMountTarget.NotFound` | Mount target ID does not exist | Verify with `DescribeMountTargets --FileSystemId <id>` |
| `InvalidAccessGroup.NotFound` | Permission group does not exist | Run `CreateAccessGroup` first |
| `InvalidAccessRule.NotFound` | Rule ID does not exist in group | Run `DescribeAccessRules --AccessGroupName <name>` |
| `InvalidSnapshot.NotFound` | Snapshot ID does not exist | Verify with `DescribeSnapshots` |
| `InvalidVSwitchId.NotFound` | vSwitch ID does not exist in VPC | Delegate to `alicloud-vpc-ops` |
| `InvalidParameter` | Missing or malformed parameter | Cross-check against `aliyun nas <op> --help` and OpenAPI |
| `InvalidParameter.ProtocolType` | Protocol type doesn't match `FileSystemType` | See [SKILL.md](../SKILL.md#parameter-matrix-verified-against-aliyun-nas-createfilesystem---help) parameter matrix |
| `InvalidParameter.StorageType` | Storage type invalid for the chosen FS type | Same matrix |
| `InvalidParameter.Priority` | Rule priority out of range (1–100) | Use 1–100 |
| `InvalidParameter.SourceCidrIp` | CIDR malformed | Use valid IPv4 CIDR (e.g., `10.0.0.0/8`) |
| `InvalidParameter.UserAccessType` | Invalid enum | Valid: `no_squash`, `root_squash`, `all_squash` |
| `InvalidParameter.RWAccessType` | Invalid enum | Valid: `RDONLY`, `RDWR` |
| `InvalidParameter.LifecycleRuleConfig` | JSON malformed | Re-validate; see OpenAPI schema |
| `InvalidParameter.MountTargetDomain` | Domain conflicts with existing | Choose a different VPC+vSwitch or delete existing MT |
| `ServiceNotOpened` | NAS not activated in region | Run `OpenNASService` first |
| `ServiceAlreadyOpened` | Already activated | Idempotent — proceed |
| `QuotaExceeded` | Account-level FS quota exhausted | Delete unused FS or raise quota via ticket |
| `QuotaExceeded.FileSystem` | Per-region FS count limit | Same as above |
| `QuotaExceeded.Snapshot` | Snapshot count limit for FS | Delete old snapshots or raise quota |
| `QuotaExceeded.AccessGroup` | 20 access groups per region limit | Delete unused groups |
| `QuotaExceeded.AccessRule` | 300 rules per group limit | Consolidate rules (use broader CIDRs) |
| `OperationDenied.FileSystemStatus` | FS is mid-state (Pending / Stopping / etc.) | Wait; re-check with `DescribeFileSystems` |
| `OperationDenied.MountTargetDomainAlreadyExists` | Duplicate mount target for VPC+vSwitch | **Non-idempotent** — re-use existing |
| `OperationDenied.HasMountTargets` | Cannot delete FS with active mount targets | Delete mount targets first |
| `OperationDenied.HasActiveBackupPlan` | FS is in HBR/SMS plan | Remove via `alicloud-hbr-ops` first |
| `OperationDenied.FileSystemType` | Feature not supported for this FS type | E.g., recycle bin / lifecycle only on `standard` |
| `OperationDenied.ResetDuringWrite` | File system has active writes | Stop app traffic, retry |
| `Forbidden.RAM` | Caller lacks `nas:*` permission | Defer to `alicloud-ram-ops` to add policy |
| `Forbidden.AccessGroup` | Access group not authorized for caller | Verify access group name and FS access policy |
| `Throttling` | API rate limit exceeded | Exponential backoff: 1s, 2s, 4s, 8s |
| `InsufficientBalance` | Account balance too low | Defer to `alicloud-billing-ops` to recharge |
| `InternalError` / 500 | Server-side error | Retry with backoff; escalate with `RequestId` if persistent |
| `EndpointResolutionFailure` | SDK cannot resolve NAS endpoint | Explicitly set `Endpoint: "nas.<region>.aliyuncs.com"` |

## Diagnostic Order (Standard)

1. **Verify service activation** — `aliyun nas OpenNASService --RegionId <region>` and confirm no error.
2. **Verify region and zone** — `DescribeRegions` and `DescribeZones` show whether the FS type is supported.
3. **Verify file system status** — `DescribeFileSystems --FileSystemId <id>` and check `Status`.
4. **Verify mount target** — `DescribeMountTargets --FileSystemId <id>` and check `Status == "Active"`.
5. **Verify access group / rules** — `DescribeAccessGroups` and `DescribeAccessRules`.
6. **Check RAM policy** — `aliyun ram ListPoliciesForUser --UserName <user>` (delegate to `alicloud-ram-ops`).
7. **Check from client side** — `showmount -e <mount-domain>` (NFS) or `smbclient -L <mount-domain>` (SMB).
8. **Check VPC routing** — Confirm ECS security group allows NFS (2049) / SMB (445) outbound.

## Common Failure Scenarios and Resolutions

### Scenario 1: "CreateFileSystem returns InvalidParameter.ProtocolType"

**Cause:** `ProtocolType` does not match `FileSystemType`. The most common
mismatch is using `ProtocolType=NFS` with `FileSystemType=cpfs` (CPFS uses
`ProtocolType=cpfs`).

**Fix:** Re-check the parameter matrix in
[SKILL.md](../SKILL.md#parameter-matrix-verified-against-aliyun-nas-createfilesystem---help).

```bash
# Wrong:
aliyun nas CreateFileSystem --FileSystemType cpfs --ProtocolType NFS --StorageType advance_200

# Right:
aliyun nas CreateFileSystem --FileSystemType cpfs --ProtocolType cpfs --StorageType advance_200 \
  --Capacity 4096 --Bandwidth 2048 --ClientToken "$(uuidgen)"
```

### Scenario 2: "MountTarget fails with OperationDenied.FileSystemStatus"

**Cause:** File system is in `Pending` state. Newly created file systems
take 30–120 seconds to reach `Running`.

**Fix:** Poll `DescribeFileSystems` until `Status == "Running"`, then retry
`CreateMountTarget`.

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun nas DescribeFileSystems --FileSystemId <id> --PageSize 1 | jq -r '.FileSystems.FileSystem[0].Status')
  [ "$STATUS" = "Running" ] && break
  sleep 10
done
```

### Scenario 3: "Mount target created but client cannot mount"

**Cause (most common):** ECS security group does not allow outbound to
TCP/2049 (NFS) or TCP/445 (SMB).

**Fix:** Add security group egress rule:
```bash
aliyun ecs AuthorizeSecurityGroupEgress --SecurityGroupId <sg> \
  --IpProtocol tcp --PortRange 2049/2049 --DestCidrIp 0.0.0.0/0
```

**Other causes:**

- Mount target vSwitch is in a different zone than ECS → cross-AZ traffic
  charges; performance may be lower. Recreate MT in the same zone as ECS.
- ECS and NAS in different VPCs → not directly reachable. Use Express
  Connect / CEN / VPN.
- Source IP not in any `AccessRule`'s `SourceCidrIp` → add a new rule
  via `CreateAccessRule`.

### Scenario 4: "DeleteFileSystem returns OperationDenied.HasMountTargets"

**Cause:** File system has at least one mount target still in `Active` state.

**Fix:**

```bash
# List mount targets
aliyun nas DescribeMountTargets --FileSystemId <id>

# Delete each
for MT in $(aliyun nas DescribeMountTargets --FileSystemId <id> | jq -r '.MountTargets.MountTarget[].MountTargetId'); do
  aliyun nas DeleteMountTarget --FileSystemId <id> --MountTargetId "$MT"
done

# Wait for deletion
for i in $(seq 1 60); do
  COUNT=$(aliyun nas DescribeMountTargets --FileSystemId <id> | jq '.MountTargets.MountTarget | length')
  [ "$COUNT" -eq 0 ] && break
  sleep 5
done

# Now delete the file system
aliyun nas DeleteFileSystem --FileSystemId <id>
```

### Scenario 5: "ResetFileSystem returns InvalidSnapshot.NotFound"

**Cause:** Snapshot was deleted or never existed in this region.

**Fix:** List available snapshots:
```bash
aliyun nas DescribeSnapshots --FileSystemId <id>
```
Choose a snapshot from a region/file system you have access to. **Note that
cross-FS snapshot rollback is not supported** — the snapshot must be from
the same file system you are resetting.

### Scenario 6: "EnableRecycleBin returns OperationDenied.FileSystemType"

**Cause:** Recycle bin is only supported on `standard` (General-purpose)
file systems. Attempting it on `extreme` / `cpfs` / `cpfsse` returns this
error.

**Fix:** Use a General-purpose file system, or accept that the FS type
does not support recycle bin and use snapshots + a manual restore process
instead.

### Scenario 7: "NFS mount hangs / times out"

**Cause (one of):**

1. Security group missing egress for TCP/2049 — see Scenario 3.
2. MTU mismatch — try with `mount -o rsize=32768,wsize=32768`.
3. ClassicLink / VPC peering not configured for cross-VPC access.
4. Client NFS version mismatch — try `vers=3` then `vers=4.1`.

**Diagnostic commands:**

```bash
# Test TCP reachability
nc -zv <mount-target-domain> 2049

# Try NFSv3 explicitly
sudo mount -t nfs -o vers=3,proto=tcp,nolock,noacl <mount-target-domain>:/ /mnt/nas

# Try NFSv4.1 explicitly
sudo mount -t nfs -o vers=4,minorversion=1 <mount-target-domain>:/ /mnt/nas

# Show exported paths
showmount -e <mount-target-domain>
```

### Scenario 8: "SMB mount fails with NT_STATUS_ACCESS_DENIED"

**Cause:** SMB ACL is enabled and the connecting AD user lacks permission,
or the source IP is not in any `AccessRule`.

**Fix:**

```bash
# 1. Check SMB ACL status
aliyun nas DescribeSmbAcl --FileSystemId <id>

# 2. List access rules and verify source CIDR includes client
aliyun nas DescribeAccessRules --AccessGroupName <name>

# 3. Add a permissive rule (temporary for diagnosis)
aliyun nas CreateAccessRule --AccessGroupName <name> \
  --SourceCidrIp "10.0.0.0/8" --RWAccessType RDWR \
  --UserAccessType root_squash --Priority 1
```

### Scenario 9: "QuotaExceeded.AccessGroup"

**Cause:** Region already has 20 access groups (account-wide limit).

**Fix:**

```bash
# List existing access groups
aliyun nas DescribeAccessGroups --output cols=AccessGroupName rows=AccessGroups.AccessGroup[].AccessGroupName

# Identify unused groups (use DescribeMountTargets to find ones with no MT)
# Delete them:
aliyun nas DeleteAccessGroup --AccessGroupName "unused-group-name"
```

### Scenario 10: "Throttling errors during batch operations"

**Cause:** NAS API has per-account rate limits. Bulk operations (e.g.,
creating 50 mount targets) hit the limit.

**Fix:** Add exponential backoff:

```bash
# Bash with retry
for i in $(seq 1 5); do
  if aliyun nas <op> <args>; then
    break
  fi
  echo "Retry $i after $((2**i))s..."
  sleep $((2**i))
done
```

For Go SDK:

```go
for i := 0; i < 5; i++ {
    _, err := client.SomeOp(req)
    if err == nil { break }
    if isThrottlingErr(err) {
        time.Sleep(time.Duration(1<<i) * time.Second)
        continue
    }
    panic(err)
}
```

## Self-Diagnosis Quick Reference

| User Symptom | Most Likely Root Cause | First Diagnostic Step |
|--------------|------------------------|-----------------------|
| "NAS not available" | `ServiceNotOpened` | `aliyun nas OpenNASService --RegionId <region>` |
| "Cannot mount" | Security group / access rule / wrong zone | `nc -zv <mt-domain> 2049`; check SG egress; check `DescribeAccessRules` |
| "Permission denied" on mount | Access rule missing for source CIDR | `DescribeAccessRules`; add rule |
| "Filesystem stuck in Pending" | Capacity-bound FS still provisioning | Wait up to 600s; re-check `DescribeFileSystems` |
| "Snapshot creation fails" | Quota or FS status | `DescribeSnapshots` count; check `OperationDenied.FileSystemStatus` |
| "Recycle bin empty for restore" | Retention expired or recycle bin disabled | `GetRecycleBinAttribute`; `ListRecentlyRecycledDirectories` |
| "Cannot delete file system" | Has mount targets / in HBR plan | `DescribeMountTargets`; check `alicloud-hbr-ops` |
| "Slow IOPS" | Wrong storage type or capacity-bound FS | `DescribeFileSystems` → check `StorageType` and `MeteredSize` |
| "Cross-VPC mount fails" | VPC not peered; not in same VPC as MT | Delegate to `alicloud-vpc-ops` |
| "SMB ACL changes not taking effect" | SMB service not restarted; client cache | Restart SMB service; reconnect |
