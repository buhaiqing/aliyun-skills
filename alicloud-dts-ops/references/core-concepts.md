# Core Concepts — DTS (Data Transmission Service)

## Architecture

DTS provides three core capabilities:

| Capability | Description | Typical Use Case |
|------------|-------------|-----------------|
| **Data Migration** | One-time or scheduled bulk data transfer from source to target | Migrate self-managed MySQL to RDS |
| **Data Synchronization** | Real-time, ongoing sync between two databases (unidirectional or bidirectional) | Active geo-redundancy, read replicas |
| **Change Tracking (订阅)** | Capture real-time CDC events from source database for downstream consumption | Event-driven architectures, cache invalidation, data lake ingestion |

### Architecture Components

```
[Source Database] ←→ [DTS Server (Data Plane)] ←→ [Target Database]
                          ↕
                    [DTS Control Plane]
                          ↕
                    [DTS Instance (Billing)]
                          ↕
                    [Consumer Channel] (for change tracking only)
```

### Resource Hierarchy

| Resource | Parent | Description |
|----------|--------|-------------|
| DTS Instance | Alibaba Cloud Account | Billing unit; purchased via CreateDtsInstance |
| DTS Job | DTS Instance | Migration/sync/subscribe task configured on an instance |
| Consumer Channel | DTS Instance (subscribe) | Downstream consumer group for change tracking |

## Supported Source/Target Matrix

DTS supports 100+ source/target combinations. Common ones include:

| Source → Target | Migration | Sync | Change Tracking |
|----------------|-----------|------|-----------------|
| MySQL → MySQL/RDS MySQL | ✅ | ✅ | ✅ |
| MySQL → PolarDB MySQL | ✅ | ✅ | ✅ |
| MySQL → AnalyticDB | ✅ | ✅ | ❌ |
| MySQL → Elasticsearch | ✅ | ✅ | ❌ |
| Oracle → MySQL/RDS MySQL | ✅ | ❌ | ❌ |
| SQL Server → RDS SQL Server | ✅ | ✅ | ✅ |
| PostgreSQL → RDS PostgreSQL | ✅ | ✅ | ✅ |
| MongoDB → MongoDB/DDS | ✅ | ✅ | ✅ |
| Redis → Redis/Tair | ✅ | ✅ | ✅ |
| PolarDB MySQL → MySQL/RDS | ✅ | ✅ | ✅ |
| Self-managed (ECS/IDC) → RDS | ✅ | ✅ | ✅ |
| Cross-region (any) | ✅ | ✅ | ✅ |
| Cross-account (any) | ✅ | ✅ | ✅ |

> See full matrix: https://help.aliyun.com/zh/dts/supported-sources-and-targets

## Limits and Quotas

| Resource | Default Limit | Can Increase? |
|----------|--------------|---------------|
| DTS instances per region | 10 (pay-as-you-go) / varies (subscription) | ✅ Submit quota request |
| Concurrent migration tasks | 5 per account per region | ✅ Submit quota request |
| Concurrent sync tasks | 20 per account per region | ✅ Submit quota request |
| Consumer channels per instance | 5 | ❌ Fixed |
| Max sync delay alert threshold | 60s (default), configurable | ✅ Modify alert rule |
| Object names length | Max 128 characters | ❌ Fixed per database |

## Regions and Endpoints

- API endpoint: `dts.aliyuncs.com`
- DTS is available in all major Alibaba Cloud regions
- Cross-region tasks are supported; source and target can be in different regions
- For China regions, use `dts.aliyuncs.com`; for international, same global endpoint

## DTS Instance Types

| Type | CLI Value | Description |
|------|-----------|-------------|
| Migration | `migration` | Data migration instance |
| Synchronization | `synchronization` | Data sync instance |
| Change Tracking | `subscribe` | Change tracking (CDC) instance |

## Billing Models

| Model | Description | Best For |
|-------|-------------|----------|
| Pay-As-You-Go (PostPaid) | Per-hour billing | Short-term migrations, variable workloads |
| Subscription (PrePaid) | Monthly/yearly commitment | Long-running sync tasks, production CDC |
| DTS Unit (DU) | Control task throughput | Performance-sensitive workloads |

## Key Concepts

### Precheck
Before any DTS task starts, a precheck validates:
- Source/target connectivity
- Database account permissions
- Binlog configuration (for incremental sync)
- Storage capacity on target
- Object name conflicts

### Checkpoint / Resumption
DTS maintains checkpoints for incremental migration and sync. If a task fails:
- **Migration:** May resume from checkpoint if incremental phase was active
- **Sync:** Resumes automatically from checkpoint after fixing the issue
- **Full migration:** Must re-run from start if full phase fails

### Data Consistency Verification
Use DescribeCheckJobs to trigger data verification between source and target:
- Number verification: Compare row counts of each table
- Full verification: Compare row-by-row data
- Structure verification: Compare table schemas

### DU (DTS Unit)
Each DTS task consumes DUs (compute units). Higher DU = faster throughput.
- Default: 1 DU
- Range: 1–100 DU (depending on instance type)
- Modify via `ModifyDtsJobDuLimit`

## Single Point of Failure Analysis

| SPOF | Impact | Mitigation |
|------|--------|------------|
| Single DTS instance | Task fails if instance crashes | DTS is managed service (HA built-in) |
| Source database (during sync) | Data flow halts | Source-side HA (RDS HA, self-managed replication) |
| Target database | Data accumulation, sync stops | Target-side HA (multi-AZ RDS, DR target) |
| Network between source/target | Task fails, data loss risk | Use DTS retry + checkpoint mechanism |

## Dependency Graph

```
DTS Task
  ├── Source Database (RDS / PolarDB / MongoDB / Redis / ECS / external)
  │     └── VPC / Security Group / DTS CIDR Whitelist
  ├── Target Database (RDS / PolarDB / MongoDB / Redis / AnalyticDB / ES)
  │     └── VPC / Security Group / DTS CIDR Whitelist
  └── DTS Instance (Billing)
        └── Alibaba Cloud Account / RAM Permissions
```