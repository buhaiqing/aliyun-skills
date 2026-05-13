# Core Concepts — Alibaba Cloud RDS

## What is RDS?

Alibaba Cloud RDS (Relational Database Service) is a managed relational database service
that supports MySQL, PostgreSQL, SQL Server, and MariaDB. It handles routine database
maintenance tasks such as provisioning, patching, backup, recovery, failure detection,
and repair.

## Key Concepts

### DB Instance

The primary resource in RDS. A DB instance is an isolated database environment running
in the cloud. Each instance can contain multiple user-created databases.

- **DBInstanceId**: Unique identifier for the instance (e.g., `rm-uf6wjk5xxxxxxx`)
- **DBInstanceClass**: Instance type defining CPU and memory (e.g., `rds.mysql.s1.large`)
- **DBInstanceStorage**: Storage capacity in GB
- **DBInstanceStatus**: Lifecycle state (Running, Creating, Deleting, Rebooting, etc.)
- **Engine**: Database engine (MySQL, PostgreSQL, SQLServer, MariaDB)
- **EngineVersion**: Engine version (e.g., 8.0, 13.0)

### Database Account

Accounts used to authenticate and access databases within an instance.

- **AccountName**: Unique name within the instance
- **AccountType**: `Normal` (regular user) or `Super` (privileged user)
- **AccountStatus**: `Available` or `Unavailable`

### Database

A logical database within a DB instance.

- **DBName**: Unique name within the instance
- **CharacterSetName**: Default character set (e.g., utf8mb4)
- **DBStatus**: Creating, Running, Deleting

### Backup

RDS supports automated and manual backups.

- **BackupId**: Unique identifier for the backup
- **BackupType**: `FullBackup` or `IncrementalBackup`
- **BackupMode**: `Automated` or `Manual`
- **BackupStatus**: `Success` or `Failed`

### Security Group / Whitelist

Controls network access to the DB instance.

- **SecurityIPList**: Comma-separated list of IP addresses or CIDR blocks
- **DBInstanceIPArrayName**: Name of the IP whitelist group

### High Availability (HA)

RDS supports multi-AZ deployments for high availability.

- **SyncMode**: `Sync` or `Async` replication
- **HAMode**: `RPO` (Recovery Point Objective) or `RTO` (Recovery Time Objective)
- **Master/Slave**: Primary and standby nodes

## Network Types

- **Intranet**: Access within VPC (recommended for production)
- **Internet**: Public network access (less secure, use with caution)

## Instance Families

| Family | Use Case |
|--------|----------|
| General Purpose | Development, testing, small workloads |
| Dedicated | Production workloads requiring consistent performance |
| Shared | Cost-sensitive, non-critical workloads |

## Storage Types

- **cloud_ssd**: Standard SSD
- **cloud_essd**: Enhanced SSD (recommended for production)
- **local_ssd**: Local SSD (high performance, limited availability)
