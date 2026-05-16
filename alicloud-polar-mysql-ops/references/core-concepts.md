# Core Concepts — PolarDB MySQL

> Version: 1.0.0 | Last Updated: 2026-05-16

## Architecture

PolarDB MySQL is a cloud-native relational database with:

| Feature | Description |
|---------|-------------|
| **Compute-Storage Separation** | Compute nodes and distributed storage are decoupled |
| **Shared Distributed Storage** | All nodes share a single distributed storage (up to 100TB) |
| **Multi-node Architecture** | One primary writer + multiple read-only replicas |
| **Serverless Computing** | RCUs (RDS Compute Units) auto-scale from 0.5 to 32 RCUs |
| **Parallel Query** | Supports parallel execution for complex analytical queries |
| **Hot Standby** | Sub-second failover to standby node |

## Key Resource Relationships

```
PolarDB Cluster (DBCluster)
├── Primary Node (Writer)
├── Read-Only Nodes (Readers) [0..N]
├── Endpoints (RW split, custom)
├── Databases [0..N]
├── Accounts [0..N]
├── Backup Sets
└── Storage (shared, auto-scaling)
```

## Supported Engine Versions

| Version | MySQL Compatible | Status |
|---------|-----------------|--------|
| 5.6 | 5.6.x | Supported |
| 5.7 | 5.7.x | Supported |
| 8.0 | 8.0.x | Recommended default |

## Cluster Types

| Type | Code | Description |
|------|------|-------------|
| Normal | Normal | Standard cluster with primary + read nodes |
| Standard | Standard | Single-node development/testing cluster |
| Basic | Basic | Minimal cost, limited features |
| Serverless | Serverless | Auto-scaling compute based on workload |
| Archive | ARCHIVE | Low-cost storage for cold data |

## Storage Types

| Type | Code | IOPS Level | Use Case |
|------|------|-----------|----------|
| ESSD PL1 | PL1 | 50K IOPS | General purpose |
| ESSD PL2 | PL2 | 100K IOPS | High performance |
| ESSD PL3 | PL3 | 200K IOPS | OLTP workloads |
| PSLevel5 | PSLevel5 | PolarFS Level 5 | Optimal for PolarDB |

## Regions and Zones

PolarDB MySQL is available in most Alibaba Cloud regions. Use `DescribeRegions` and
`DescribeAvailableClasses` to verify availability in the target region.

## Quotas and Limits (typical)

| Resource | Default Limit | Notes |
|----------|--------------|-------|
| Clusters per account | 20 | Adjustable via support ticket |
| Nodes per cluster | Up to 16 | 1 primary + 15 read replicas |
| Databases per cluster | 200 | Per cluster limit |
| Accounts per cluster | 100 | Per cluster limit |
| Backup retention | 732 days | Maximum retention period |
| Backup set size | No limit | Stored in dedicated PolarDB backup storage |
| Read-only nodes | 15 | Per cluster |
| Storage per cluster | 100 TB | Maximum shared storage size |
| Serverless RCU range | 0.5 – 32 | Auto-scaling range |

## State Machine

```
Creating → Running ─┐
   ╲               │
   └── Failed ─────┘

Running ──→ Restarting ──→ Running
Running ──→ Deleting ──→ Deleted
Running ──→ Modifying ──→ Running
Running ──→ Stopped ──→ Restarting ──→ Running
Running ──→ Paused ──→ Resuming ──→ Running (Serverless)
```

## Network

- **VPC Required:** PolarDB clusters must be deployed in a VPC.
- **Intranet Only:** No public IP. Use NAT Gateway or SLB for public access.
- **Endpoints:** Primary (writer), Custom, and RW-splitting endpoints supported.

## Delegation Points

| Related Skill | Trigger Condition |
|---------------|-------------------|
| `alicloud-vpc-ops` | VPC/VSwitch creation or verification |
| `alicloud-rds-ops` | RDS MySQL-related tasks |
| `alicloud-polar-pg-ops` | PolarDB PostgreSQL tasks |
| `alicloud-polar-oracle-ops` | PolarDB Oracle-compatible tasks |
| `alicloud-das-ops` | SQL diagnosis, automatic tuning, deadlock analysis |
| `alicloud-cms-ops` | CloudMonitor alarm configuration |
