# Core Concepts — Alibaba Cloud Redis / Tair (KVStore)

## Product Overview

Alibaba Cloud Redis / Tair (KVStore) is a managed key-value database service that provides:

- **Redis Open Source Edition**: Compatible with community Redis, performance enhanced by 30%
- **Tair Enterprise Edition**: Alibaba's self-developed extension with persistent memory, disk storage, enhanced data structures, and global multi-active capabilities

## Architecture Types

| Architecture | Description | Use Case |
|--------------|-------------|----------|
| **Standard** | Single shard, master-replica HA | Small to medium workloads |
| **Cluster** | Multiple shards, horizontal scaling | Large datasets, high throughput |
| **Read/Write Splitting** | Master + multiple read replicas | Read-heavy workloads |
| **Single Node** | Single replica, no HA | Development, testing, non-critical |

## Instance Types

| Type | Description |
|------|-------------|
| **Redis** | Redis Open Source Edition |
| **Tair** | Tair Enterprise Edition (memory, persistent memory, disk types) |
| **Memcache** | Compatible with Memcached protocol |

## Instance Status Values

| Status | Description | Impact |
|--------|-------------|--------|
| **Normal** | Running normally | Full service available |
| **Creating** | Being created | Not yet available |
| **Changing** | Configuration changing | Brief interruption possible |
| **Inactive** | Disabled | Service unavailable |
| **Flushing** | Data being flushed | Service unavailable |
| **Released** | Released/destroyed | No longer exists |
| **Transforming** | Billing type changing | No impact |
| **Migrating** | Migrating across zones | Brief interruption possible |
| **BackupRecovering** | Restoring from backup | Service unavailable |
| **MinorVersionUpgrading** | Minor version upgrading | Brief interruption possible |
| **NetworkModifying** | Network changing | Brief interruption possible |
| **SSLModifying** | SSL configuration changing | Brief interruption possible |
| **MajorVersionUpgrading** | Major version upgrading | Can still access |

## Network Types

| Type | Description |
|------|-------------|
| **CLASSIC** | Classic network (legacy) |
| **VPC** | Virtual Private Cloud (recommended) |

## Charge Types

| Type | Description |
|------|-------------|
| **PrePaid** | Subscription (monthly/yearly) |
| **PostPaid** | Pay-as-you-go (hourly) |

## Storage Types (Tair)

| Type | Characteristics | Cost |
|------|-----------------|------|
| **Memory** | Pure memory, extreme performance | Baseline |
| **Persistent Memory** | Balance of performance and persistence | ~40% lower |
| **Disk (ESSD/SSD)** | Large capacity, lowest cost | ~70% lower |

## Key Limits

| Limit | Value |
|-------|-------|
| Max shards (Cluster) | 256 |
| Max connections | Varies by instance class |
| Max bandwidth | Varies by instance class |
| Max QPS | Up to 70 million (Tair multi-thread) |
| Backup retention | 7 days default (configurable) |
| Instance name length | 2-128 characters |

## Regions and Zones

Use `DescribeRegions` and `DescribeZones` APIs to query supported regions and availability zones.

## Connection Endpoints

| Type | Format | Example |
|------|--------|---------|
| Intranet | `<instance-id>.redis.rds.aliyuncs.com` | `r-bp1zxszhcgatnx****.redis.rds.aliyuncs.com` |
| Public | Allocated on request | — |
| Direct (Cluster) | For cluster architecture direct access | — |

## Security

- **Whitelist**: IP-based access control (Security IPs)
- **Password**: Instance-level password authentication
- **SSL**: Optional SSL/TLS encryption
- **TDE**: Transparent Data Encryption (Tair enterprise)
- **PrivateLink**: VPC endpoint access

## Maintenance Window

Default maintenance window: 02:00-06:00 (configurable). Alibaba Cloud performs routine maintenance during this window, which may cause brief connection interruptions.

## Backup and Recovery

- **Automated backups**: Daily full backup + incremental backups
- **Manual backups**: On-demand full backup
- **Backup retention**: 7 days default
- **Cross-region backup**: Supported for disaster recovery
- **Point-in-time recovery**: Supported (requires flashback enabled)

## Monitoring Dimensions

| Dimension | Metrics |
|-----------|---------|
| **Performance** | CPU, Memory, Connections, QPS, Bandwidth |
| **Storage** | Used memory, Key count, Expired keys, Evicted keys |
| **Latency** | Average latency, P99 latency |
| **Big Key** | Top big keys analysis |
| **Hot Key** | Top hot keys analysis |
| **Slow Log** | Commands exceeding threshold |

## Scaling Behavior

- **Vertical scaling (ModifyInstanceSpec)**: Change instance class
  - In-place scaling when resources available (no interruption)
  - Migration scaling when resources insufficient (1-2 brief interruptions)
- **Horizontal scaling (Cluster)**: Add/remove shards
  - Online scaling for cloud-native architecture
  - Brief interruption for classic architecture

## High Availability

- **Single AZ**: Master-replica within same zone
- **Multi-AZ**: Master and replica in different zones
- **Global Multi-Active**: Cross-region replication (Tair enterprise)
- **Auto-failover**: < 30 seconds for master-replica switch

## Tair Enterprise Data Types

Tair extends Redis with self-developed data structures:

| Data Type | Description | Use Case |
|-----------|-------------|----------|
| **TairString** | Enhanced string with version control and comparison-set | Distributed locks, rate limiting |
| **TairHash** | Hash with field-level expiration | Session storage, user profiles |
| **TairZset** | Sorted set with aggregation and ranking | Leaderboards, time-series ranking |
| **TairGIS** | Geographic spatial data type | Location-based services |
| **TairSearch** | Full-text search index | Search engines, log analysis |
| **TairDoc** | JSON document store | Document databases, configuration |
| **TairCpc** | Cardinality estimation (HyperLogLog enhanced) | UV counting, cardinality estimation |
| **TairRoaring** | Roaring bitmaps | Tag filtering, user segmentation |
| **TairTs** | Time-series data type | IoT metrics, monitoring data |

> **Note:** Tair data types require Tair Enterprise Edition and compatible client libraries.

## Parameter Management

Key parameters that can be modified:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `maxmemory-policy` | `volatile-lru` | Eviction policy when memory full |
| `timeout` | `0` | Client idle timeout (seconds) |
| `tcp-keepalive` | `300` | TCP keepalive interval |
| `notify-keyspace-events` | `""` | Keyspace notification events |
| `slowlog-log-slower-than` | `10000` | Slow log threshold (microseconds) |
| `slowlog-max-len` | `128` | Maximum slow log entries |
| `lazyfree-lazy-eviction` | `yes` | Asynchronous eviction |
| `lazyfree-lazy-expire` | `yes` | Asynchronous expiration |
| `activedefrag` | `yes` | Active defragmentation |

> **Note:** Some parameter changes require instance restart to take effect.
