# NAS Well-Architected Assessment

This document maps Alibaba Cloud File Storage NAS operations to the five
pillars of the Alibaba Cloud
[Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).

## 1. 安全 (Security)

| Area | Guidance |
|------|----------|
| **Identity & Access (IAM)** | Grant least-privilege `nas:*` permissions per role (see `references/integration.md` for the minimal policy). Use STS for short-lived credentials where possible. |
| **Permission groups** | Replace the default `DEFAULT_VPC_GROUP_NAME` (which allows `0.0.0.0/0` RDWR) with a dedicated group with restricted `SourceCidrIp`. Audit rules quarterly. |
| **Network isolation** | Mount targets are VPC-scoped. Use separate VPCs per environment (dev / staging / prod). Use CEN or VPN for cross-VPC access; do not expose NAS via public IP. |
| **Encryption in transit** | Use NFSv4.1 with Kerberos (when AD/LDAP is configured) for mutual auth. SMB 3.x supports encryption — enable on clients. |
| **Encryption at rest** | NAS supports server-side encryption with KMS-managed or customer-managed CMKs. Default is service-managed keys; for regulated workloads specify `KMSKeyId` on file system create. |
| **Credential security** | Never put NAS credentials in `ps aux` history. Use `REDISCLI_AUTH`-style env vars or `~/.smbcredentials` with `chmod 600`. |
| **Audit trail** | All control-plane operations are logged in ActionTrail. Enable periodic audit review of `DeleteFileSystem`, `DeleteMountTarget`, `ModifyAccessRule`, and `DisableAndCleanRecycleBin`. |

### Security Pre-flight Checklist

- [ ] Caller RAM policy includes only required NAS actions
- [ ] Default access group replaced with restricted group
- [ ] Mount target vSwitch is in a non-public subnet
- [ ] ECS security group egress includes TCP/2049 (NFS) or TCP/445 (SMB)
- [ ] ActionTrail logging is enabled and delivered to SLS
- [ ] KMS CMK configured for production file systems

## 2. 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **Multi-AZ** | Create one mount target per availability zone (or VPC). Client mounts the nearest MT to avoid cross-AZ traffic. |
| **Backup** | Always enable an auto-snapshot policy before any destructive operation. For DR, replicate snapshots cross-region via HBR. |
| **Recycle bin** | Enable recycle bin on all `standard` file systems (1–180 days retention). Default to 14 days. |
| **Recycle bin ≠ backup** | Recycle bin only catches `rm`-deleted files. Snapshot is the real backup. Use both. |
| **Failure-oriented design** | Plan for: (1) snapshot failure (poll `DescribeAutoSnapshotTasks`); (2) recycle bin expiration (alert at 80% retention); (3) mount target going `Inactive` (re-create). |
| **DR runbook** | Phase 1: Snapshot captured in primary region. Phase 2: Snapshot replicated to secondary region via HBR. Phase 3: Restore from snapshot in DR region; re-create mount targets. |
| **Lifecycle tier-down** | Move cold data to IA or Archive storage via lifecycle policy. Reduces storage cost without changing application access. |

### DR Runbook (Cross-Region Snapshot Replica)

```
Phase 1 — Detect
  - CMS alarm: snapshot creation failed for FileSystemId X
  - OR: primary region degraded
  - OR: RPO exceeded (last successful snapshot > 24h old)

Phase 2 — Diagnose
  - alicloud nas DescribeAutoSnapshotTasks --FileSystemId X (last status)
  - alicloud nas DescribeFileSystems --FileSystemId X (current state)
  - alicloud nas DescribeSnapshots --FileSystemId X (last good snapshot)

Phase 3 — Restore (DR)
  - alicloud hbr CreateReplicationVaultPair (setup cross-region replication)
  - alicloud hbr CreateReplication (replicate last good snapshot to DR region)
  - alicloud nas CreateFileSystem (new FS in DR region from replicated snapshot)
  - alicloud nas CreateMountTarget in DR region
  - alicloud nas ResetFileSystem (optional, to bring new FS to the right state)
  - Update client configuration to mount from DR region
```

### Stability Pre-flight Checklist

- [ ] Auto-snapshot policy applied to all production file systems
- [ ] Recycle bin enabled (for `standard` FSs) with ≥ 7 day retention
- [ ] Mount targets in ≥ 2 AZs (HA)
- [ ] CMS alarms for `MountTargetStatus=0` (inactive)
- [ ] ActionTrail event subscription for `Delete*` and `Disable*` events
- [ ] DR plan documented and tested annually

## 3. 成本 (Cost)

| Item | Cost | Optimization |
|------|------|--------------|
| General-purpose NAS (`standard` Performance) | Per GB-month, metered | Use `Capacity` storage type for cold data (3-5x cheaper than `Performance`) |
| General-purpose NAS (`standard` Capacity) | Per GB-month, tiered by used capacity | Best for > 1 TB workloads |
| General-purpose NAS (`standard` Premium) | Per GB-month | Use only when `Performance` is insufficient |
| Extreme NAS | Per GiB-month + per MB/s-month provisioned | Right-size `Capacity` and `Bandwidth`; don't over-provision |
| CPFS | Per GiB-month + per MB/s-month provisioned | Use `economic` for cold data; `advance_100` for hot |
| Snapshot storage | Per GB-month | Delete old snapshots; use `RetentionDays` |
| Recycle bin | Free, but counts as standard storage | Reduce `RetentionDays`; clean up before disable |
| Lifecycle tier-down | Free, but tiered storage is cheaper | Always enable for /archive, /backup, /log dirs |
| StoragePackage (Storage Plan) | Prepaid discount | Purchase for steady-state workloads (> 5 TB) |

### Cost Optimization Patterns

**Pattern 1: Lifecycle tier-down for log volumes**

```bash
# Move /var/log to IA after 30 days, Archive after 180 days
aliyun nas CreateLifecyclePolicy \
  --FileSystemId "$FS_ID" \
  --LifecyclePolicyName "logs-tierdown" \
  --LifecycleRuleConfig '{
    "Rules": [
      {"Path": "/var/log", "IA": {"Days": 30}, "Archive": {"Days": 180}}
    ]
  }'
```

**Pattern 2: Right-size Extreme NAS bandwidth**

For an Extreme NAS workload using only 30 MB/s/TiB average throughput,
downgrade from `advance` to `standard` storage type to save ~50% on the
bandwidth component. Verify with CMS `WriteBytes` / `ReadBytes` metrics
first.

**Pattern 3: StoragePackage for steady state**

```bash
# List available storage plans
aliyun nas DescribeStoragePackages

# Purchase via console or pricing API (no direct CreateStoragePackage API;
# purchase in NAS console or via Pricing API)
```

**Pattern 4: Snapshot retention tuning**

Auto-snapshot policies default to 7-day retention. For file systems with
heavy churn, consider 3-day retention + manual snapshots before major
changes.

### Cost Pre-flight Checklist

- [ ] Lifecycle policies enabled for cold paths
- [ ] StoragePackage purchased for steady-state workloads > 5 TB
- [ ] Snapshot retention tuned (default 7d may be too long for dev)
- [ ] Idle file systems (no I/O in 30d) identified and either tiered down or deleted
- [ ] Recycle bin retention = 7 days (default) — adjust per compliance needs

## 4. 效率 (Efficiency)

| Pattern | Implementation |
|---------|----------------|
| **Batch mount target creation** | For multi-AZ HA, create all mount targets in one batch via loop with retry |
| **Reusable snapshot policies** | Create one auto-snapshot policy; apply to many file systems (one policy → many FSs) |
| **Fileset operations** (CPFS) | Use filesets to partition CPFS — improves metadata scalability |
| **Reusable access groups** | Create one access group per environment; bind many FSs to it |
| **Concurrent client mounts** | Up to 1000+ NFS clients per file system (no tuning needed) |
| **CLI batch** | Use `xargs -I{}` or `for` loops to fan out operations |

### Batch Mount Target Creation (Multi-AZ HA)

```bash
# Inputs
FS_ID="31a8e42551a44ad496****"
GROUP="web-app-group"
VPC_ID="vpc-bp1****"
ZONES_AND_VSW=(
  "cn-hangzhou-h vsw-bp1****001"
  "cn-hangzhou-i vsw-bp1****002"
  "cn-hangzhou-g vsw-bp1****003"
)

for ZV in "${ZONES_AND_VSW[@]}"; do
  read -r ZONE VSW <<< "$ZV"
  echo "Creating mount target in $ZONE ($VSW)..."
  aliyun nas CreateMountTarget \
    --FileSystemId "$FS_ID" \
    --AccessGroupName "$GROUP" \
    --VpcId "$VPC_ID" \
    --VswId "$VSW" \
    --NetworkType Vpc
  sleep 2  # Throttling courtesy
done
```

### Efficiency Pre-flight Checklist

- [ ] Mount targets in all required AZs (not just one)
- [ ] Single shared auto-snapshot policy reused across FSs (not per-FS policy)
- [ ] Single access group per environment (not per-FS group)
- [ ] Filesets used on CPFS to partition metadata namespace

## 5. 性能 (Performance)

### Storage Class Performance

| Storage Class | Throughput / IOPS | Latency Target | Cost |
|---------------|-------------------|----------------|------|
| `Performance` (standard) | High per GB | 5-10 ms | $$ |
| `Capacity` (standard) | Scaled by usage | 10-20 ms | $ |
| `Premium` (standard) | Highest in standard | 3-5 ms | $$$ |
| `standard` (extreme) | 100 MB/s/TiB | 1-3 ms | $$$ |
| `advance` (extreme) | 1000 MB/s/TiB | 1 ms | $$$$ |
| `advance_100` (CPFS) | 100 MB/s/TiB | sub-ms | $$$ |
| `advance_200` (CPFS) | 200 MB/s/TiB | sub-ms | $$$$ |
| `economic` (CPFS) | 50 MB/s/TiB | ms | $$ |

### Client-Side Tuning

**NFS:**

```bash
# Maximum throughput (1 MB rsize/wsize)
mount -t nfs -o vers=4,minorversion=1,rsize=1048576,wsize=1048576,noacl,async \
  <mount-domain>:/ /mnt/nas

# Maximum IOPS (smaller chunks, more concurrent)
mount -t nfs -o vers=3,rsize=32768,wsize=32768,noacl \
  <mount-domain>:/ /mnt/nas
```

**SMB:**

```bash
# /etc/samba/smb.conf (client side) — enable Multichannel
[global]
  server multi channel support = yes
  client multi channel support = yes
```

### Performance Monitoring (CMS)

| Metric | Threshold | Action |
|--------|-----------|--------|
| `ReadLatency` (standard) | > 50 ms | Check for `Capacity` tier saturation; consider `Performance` |
| `WriteLatency` (extreme) | > 10 ms | Check throughput (`Bandwidth` provisioning); upgrade |
| `ReadIOPS` saturation | > 80% of provisioned | Upgrade to higher tier or use CPFS |
| `SizeUsedPercentage` | > 80% | Add capacity or enable lifecycle tier-down |

### Performance Pre-flight Checklist

- [ ] Storage class chosen matches workload I/O profile
- [ ] Client mount options use `rsize=wsize=1048576` (NFS) or Multichannel (SMB)
- [ ] CMS alarms set for `ReadLatency`, `WriteLatency` thresholds per tier
- [ ] For CPFS / Extreme: throughput provisioned (not just capacity)
- [ ] Fileset partitioning in place for CPFS workloads

## Cross-Pillar Summary

| Pillar | Top 3 Actions |
|--------|---------------|
| **Security** | Replace default access group; enable KMS encryption; restrict mount targets to private subnets |
| **Stability** | Enable auto-snapshot + recycle bin; create multi-AZ mount targets; document DR runbook |
| **Cost** | Enable lifecycle tier-down; purchase StoragePackage for steady state; delete unused FSs |
| **Efficiency** | Reuse snapshot policies and access groups; multi-AZ mount targets; filesets for CPFS |
| **Performance** | Right-size storage class; tune client mount options; monitor via CMS |
