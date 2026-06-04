# NAS Core Concepts

## What is Alibaba Cloud File Storage NAS?

Alibaba Cloud **File Storage NAS** is a fully managed, shared, distributed
file system. Unlike block storage (EBS) which is attached to a single ECS
instance, NAS is accessed over the network using standard file protocols
(NFS, SMB) and is shared across many compute clients.

**Key properties:**

| Property | Value |
|----------|-------|
| Protocols | NFS v3, NFS v4.1, SMB 2.x, SMB 3.x |
| Access pattern | Concurrent read/write from many clients |
| Durability | 99.999999999% (12 nines) for General-purpose / Extreme; 12 nines for CPFS |
| Availability | Service-level targets per storage type |
| Scaling | Capacity and throughput scale independently of compute |

## Four File System Families

NAS exposes four product families through the same OpenAPI (`2017-06-26`).
Choosing the right family is the most important decision in NAS deployment.

| Family | `FileSystemType` | Storage | Throughput Tier | Use Case | Pricing Model |
|--------|------------------|---------|-----------------|----------|---------------|
| **General-purpose NAS** | `standard` | Capacity-bucket (`Performance` / `Capacity` / `Premium`) | Up to 10 GB/s aggregate | Web apps, container storage, log archive, media processing | Pay-as-you-go (GB used) |
| **Extreme NAS** | `extreme` | Provisioned capacity | 100 MB/s/TiB → 1000 MB/s/TiB per file system | High-IOPS OLTP, EDA, low-latency analytics | Pay-as-you-go (GiB + MB/s) |
| **CPFS** | `cpfs` | Provisioned capacity | `advance_100` / `advance_200` (100–200 MB/s/TiB baseline) / `economic` | HPC, AI training, life sciences, rendering | Pay-as-you-go (GiB + MB/s) |
| **CPFS SE** | `cpfsse` | Zone-redundant, provisioned | `advance_100` (100 MB/s/TiB) | Mission-critical HPC, zone-redundant parallel FS | Pay-as-you-go (GiB + MB/s) |

> **Decision flow:**
> - Generic shared storage for web/containers? → **General-purpose (`standard`)**
> - Low-latency / high-IOPS single file system? → **Extreme (`extreme`)**
> - HPC / AI / parallel workloads? → **CPFS (`cpfs`)**
> - Zone-redundant parallel? → **CPFS SE (`cpfsse`)**

## Mount Topology

A NAS file system is not directly addressable. Clients mount it through a
**mount target**, which binds the file system to a specific VPC and vSwitch.

```
                            ┌─────────────────────┐
                            │   NAS File System   │
                            │ 31a8e4xxxxxx (NFS)  │
                            └──────────┬──────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
   ┌────▼─────┐                  ┌─────▼─────┐                  ┌──────▼────┐
   │ MT-1     │                  │ MT-2      │                  │ MT-3      │
   │ VPC-A    │                  │ VPC-B     │                  │ VPC-A     │
   │ VSW-A-z1 │                  │ VSW-B-z1  │                  │ VSW-A-z2  │
   └────┬─────┘                  └─────┬─────┘                  └──────┬────┘
        │                              │                              │
   ┌────▼─────┐                  ┌─────▼─────┐                  ┌──────▼────┐
   │ ECS-A1   │                  │ ECS-B1    │                  │ ECS-A2    │
   │ mount    │                  │ mount     │                  │ mount     │
   └──────────┘                  └───────────┘                  └───────────┘
```

**Key rules:**

- A file system can have **multiple mount targets** — typically one per VPC,
  per availability zone, or per business unit.
- A mount target is **VPC-scoped** — clients outside the VPC cannot reach it
  (use ClassicLink or VPN for hybrid access; or use Express Connect / SAG).
- The mount target's vSwitch **must be in the same zone as the compute
  clients** that will mount it, to avoid cross-AZ traffic charges.
- A mount target is bound to **one** access group (permission group).
- The mount protocol (NFS or SMB) is set at the **file system** level, not the
  mount target. A single file system cannot serve both NFS and SMB in the
  General-purpose family — but CPFS / Extreme are NFS-only.

## Permission Model: Access Groups and Rules

Alibaba Cloud NAS uses a two-level permission system:

```
AccessGroup (e.g., "web-app-group")
  ├── AccessRule #1: 10.0.0.0/8    RDWR  root_squash  priority=1
  ├── AccessRule #2: 10.1.0.0/16   RDONLY root_squash  priority=2
  └── AccessRule #3: 192.168.0.0/16 RDWR  all_squash   priority=3
```

- **AccessGroup** (权限组) — Container of rules. Bound to a mount target.
- **AccessRule** (权限规则) — Authorizes a source CIDR with `RWAccessType`
  (RDWR / RDONLY) and `UserAccessType` (no_squash / root_squash / all_squash).
- **Priority** — 1–100; lower = higher priority. When multiple rules match,
  the highest-priority rule wins.
- **Default group** `DEFAULT_VPC_GROUP_NAME` — Created automatically in each
  region, with one rule authorizing `0.0.0.0/0` RDWR. **Replace this for
  production.**

**Quotas:**

- 20 access groups per region per account
- 300 rules per access group

## File System ID Formats

| Family | ID Prefix | Example |
|--------|-----------|---------|
| General-purpose NAS | `31a8e4****` (numeric) | `31a8e42551a44ad496****` |
| Extreme NAS | `extreme-****` | `extreme-0015****` |
| CPFS | `cpfs-****` | `cpfs-125487****` |
| CPFS SE | `cpfsse-****` | `cpfsse-022c71b134****` |

## Snapshots and Lifecycle

| Feature | Supported FS Types | Purpose | Cost |
|---------|--------------------|---------|------|
| **Manual snapshot** | All 4 families | Point-in-time file system state | Per-GB-month |
| **Auto snapshot policy** | All 4 families | Recurring snapshots (e.g., daily 03:00) | Per-GB-month |
| **Recycle bin** | `standard` only | Recover `rm`-deleted files (1–180 days) | Free (storage counted as standard) |
| **Lifecycle policy** | `standard` only | Tier down to IA / Archive based on access time | Reduces storage cost |
| **Cross-region snapshot** | All (CPFS in preview) | DR via replicated snapshots | Per-GB transfer + per-GB-month |

## Region and Zone Availability

NAS is **not** available in every region or zone. **Always call
`DescribeRegions` and `DescribeZones` first** to discover current support,
especially for Extreme NAS and CPFS (which have narrower availability than
General-purpose).

```bash
# Discover supported regions
aliyun nas DescribeRegions

# Discover supported zones in a region
aliyun nas DescribeZones --RegionId cn-hangzhou
```

## Service Activation

NAS is a pay-as-you-go service, but **must be explicitly activated** in each
region before creating file systems. Activation is a one-time operation:

```bash
aliyun nas OpenNASService --RegionId cn-hangzhou
```

Activation returns an `OrderId` even though no money is charged. Subsequent
`OpenNASService` calls in the same region are idempotent.

## Limits and Quotas

| Limit | Value | Notes |
|-------|-------|-------|
| File systems per region | 100 (default; raiseable via ticket) | Per account |
| Mount targets per file system | 1 per (VPC + vSwitch) pair | A FS in 3 zones × 2 VPCs = up to 6 MTs |
| Access groups per region | 20 | |
| Access rules per access group | 300 | |
| Snapshots per file system | 128 (default; raiseable) | |
| File size | Up to 1 PiB per file (CPFS) | NFS client may have lower limits |
| Concurrent NFS clients | 1000+ per file system | |

> **Always consult current limits** at
> <https://help.aliyun.com/zh/nas/product-overview/limits> and via ticket.

## Cross-Product Relationships

```
                    ┌─────────────────────┐
                    │    Alibaba Cloud    │
                    │       NAS FS        │
                    └──────────┬──────────┘
                               │
       ┌───────────┬───────────┼───────────┬───────────────┐
       │           │           │           │               │
   ┌───▼───┐  ┌────▼────┐  ┌────▼────┐  ┌───▼────┐  ┌───────▼────────┐
   │  VPC  │  │   ECS   │  │   KMS   │  │  RAM  │  │  HBR / SMS DR  │
   │(Mount │  │(Mount   │  │(SSE-KMS │  │(Per-  │  │(Cross-region   │
   │Target)│  │ Client) │  │ encrypt)│  │ mission│  │ replication)   │
   └───────┘  └─────────┘  └─────────┘  └────────┘  └────────────────┘
```

- **VPC**: required for mount targets
- **ECS / containers**: required as mount clients
- **KMS**: optional — server-side encryption with customer-managed CMK
- **RAM**: required for access control (users / roles)
- **HBR / SMS**: required for cross-region snapshot-based DR
