# Core Concepts — PolarDB PostgreSQL

> Version: 1.0.0 | Last Updated: 2026-05-16

## Architecture

PolarDB PostgreSQL features:
- **Compute-Storage Separation:** Independent scaling of compute nodes and distributed storage
- **Shared Distributed Storage:** All nodes access a single distributed storage system
- **Write Scalability:** Improved write performance over RDS PostgreSQL
- **Parallel Processing:** Parallel query execution support

## Engine Versions

| Version | PostgreSQL Compatible |
|---------|----------------------|
| 11 | 11.x |
| 12 | 12.x |
| 13 | 13.x |
| 14 | 14.x (Recommended) |

## Quotas and Limits

| Resource | Default Limit |
|----------|--------------|
| Clusters per account | 20 |
| Nodes per cluster | Up to 16 |
| Databases per cluster | 200 |
| Accounts per cluster | 100 |
| Storage per cluster | 100 TB |

## Delegation Points

| Related Skill | Trigger Condition |
|---------------|-------------------|
| `alicloud-vpc-ops` | VPC/VSwitch creation or verification |
| `alicloud-rds-ops` | RDS PostgreSQL tasks |
| `alicloud-polar-mysql-ops` | PolarDB MySQL tasks |
| `alicloud-polar-oracle-ops` | PolarDB Oracle-compatible tasks |
| `alicloud-das-ops` | SQL diagnosis, automatic tuning |
