# Core Concepts: Alibaba Cloud ClickHouse

## Product Overview

ApsaraDB for ClickHouse (云数据库 ClickHouse 版) is a fully managed real-time analytics database service based on the open-source ClickHouse. Alibaba Cloud offers two editions:

| Edition | API Version | Description |
|---------|-------------|-------------|
| **Enterprise Edition** | `2023-05-22` | Fully managed, serverless scaling, multi-AZ deployment. CLI-supported. |
| **Classic Edition** | `2019-11-11` | Original offering, instance-based. SDK-only. |

This skill primarily targets the **Enterprise Edition** (CLI-supported). The Classic Edition is covered via SDK fallback.

## Architecture

A ClickHouse Enterprise Edition cluster (DBInstance) consists of:

```
┌──────────────────────────────────────────┐
│           ClickHouse DBInstance          │
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  Node 1  │  │  Node 2  │  │ Node N │ │
│  └──────────┘  └──────────┘  └────────┘ │
│                                          │
│  ┌──────────────────────────────────────┐│
│  │  Computing Groups (optional)         ││
│  │  ┌────┐ ┌────┐ ┌────┐              ││
│  │  │CG1 │ │CG2 │ │CG3 │              ││
│  │  └────┘ └────┘ └────┘              ││
│  └──────────────────────────────────────┘│
└──────────────────────────────────────────┘
```

- **DBInstance**: The cluster resource, containing 2-16 nodes
- **Computing Group**: Logical compute group within a cluster (Enterprise Edition)
- **Endpoint**: Network endpoint (public/private) for connecting to the cluster

## Instance States

| State | Description | Billable |
|-------|-------------|----------|
| `Running` | Normal running | Yes |
| `Stopped` | Paused (suspended) | No (storage-only) |
| `Starting` | Starting up | - |
| `Stopping` | Stopping | - |
| `Restarting` | Rebooting | - |
| `Deleting` | Being released | - |
| `Upgrading` | Minor version upgrade in progress | - |
| `ConfigModifying` | Config change in progress | - |

## Specifications & Limits

### Instance Types

Enterprise Edition supports the following compute modes:

| Mode | Node Count | Node Scale | Use Case |
|------|-----------|------------|----------|
| **Fixed** | 2-16 | Fixed spec | Predictable workloads |
| **Serverless** | 4-32 (elastic) | Min-Max range | Variable workloads |

### Hard Limits

| Resource | Limit |
|----------|-------|
| Max nodes per cluster | 16 (fixed), 32 (serverless) |
| Min nodes per cluster | 2 (fixed), 4 (serverless) |
| Storage per node | Up to 32000 GB (configurable) |
| Max DB instances per account | Default 10 (contact support to raise) |
| Max databases per cluster | 256 |
| Max accounts per cluster | 100 |

### Regions

Available in major regions: China (Hangzhou, Shanghai, Beijing, Shenzhen, etc.), International (Singapore, US, Germany, etc.). Use `aliyun clickhouse DescribeRegions` to query the full list.

## Quotas

| Quota Type | Default | Notes |
|-----------|---------|-------|
| DB instances per region | 10 | Soft limit, can be raised via ticket |
| Storage per instance | Varies by spec | Configurable at creation and via ModifyDBInstanceClass |

## Related Products

| Product | Relationship |
|---------|-------------|
| **ECS** | Data source for ClickHouse queries (ECS runs client applications) |
| **CMS** | Cloud Monitor — metrics, alarms for ClickHouse clusters |
| **SLS** | Log Service — can ship logs to ClickHouse for analysis |
| **DMS** | Data Management — can manage ClickHouse as a data source |
| **VPC** | Network isolation — ClickHouse clusters are deployed in VPC |

## Delegation Rules

| SHOULD Use | SHOULD NOT Use |
|------------|---------------|
| `alicloud-cms-ops` for setting up monitoring alarms on ClickHouse metrics | This skill for data-plane operations (INSERT/SELECT queries) |
| `alicloud-vpc-ops` for VPC network configuration | This skill for cross-product orchestration |
| `alicloud-sls-ops` for log ingestion pipeline setup | |
