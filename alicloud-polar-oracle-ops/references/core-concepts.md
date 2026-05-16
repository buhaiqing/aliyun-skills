# Core Concepts — PolarDB Oracle-compatible (IO)

> Version: 1.0.0 | Last Updated: 2026-05-16

## Architecture

PolarDB Oracle-compatible (PolarDB O / PolarDB IO) is Alibaba Cloud's cloud-native
database compatible with Oracle syntax, providing:

- **Oracle PL/SQL Compatibility:** Native support for PL/SQL, stored procedures, triggers
- **Oracle Data Types:** Full support for Oracle-compatible data types
- **Compute-Storage Separation:** Cloud-native architecture with distributed storage
- **Enterprise Migration Tool:** Designed for Oracle-to-cloud migration scenarios

## Supported Features

| Feature | Support |
|---------|---------|
| PL/SQL | Yes |
| Stored Procedures | Yes |
| Triggers | Yes |
| Views | Yes |
| Oracle Data Types | Yes |
| Oracle Functions | Partial |
| Packages | Partial |
| Sequences | Yes |

## Migration Tools

| Tool | Purpose |
|------|---------|
| ADAM (Advanced Database & Application Migration) | Assess Oracle compatibility |
| OMS (Oracle Migration Service) | Migrate data from Oracle |
| DTS | Data migration |

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
| `alicloud-polar-mysql-ops` | PolarDB MySQL tasks |
| `alicloud-polar-pg-ops` | PolarDB PostgreSQL tasks |
| `alicloud-rds-ops` | RDS Oracle (not supported; only RDS MySQL/PG) |
