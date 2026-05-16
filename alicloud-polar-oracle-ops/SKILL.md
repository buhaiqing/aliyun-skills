---
name: alicloud-polar-oracle-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba Cloud PolarDB Oracle-compatible clusters (PolarDB 兼容Oracle版, PolarDB O引擎) — cluster lifecycle, Oracle-compatible features, account management, backup restoration, performance monitoring, and migration scenarios. User mentions PolarDB Oracle, PolarDB O, PolarDB-O, PolarDB IO, 兼容Oracle, O引擎, Oracle迁移, or describes Oracle-compatible database scenarios (PL/SQL, stored procedures, data migration from Oracle) even without explicit naming. CLI: `aliyun polardb-io`, SDK: polardb-io. NOT for PolarDB MySQL, PolarDB PostgreSQL, RDS, standalone Oracle Database, Redis/Tair, or billing/RAM-only tasks.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-05-16"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "PolarDB IO 2021-11-26 / https://help.aliyun.com/zh/polardb/polardb-compatible-for-oracle/"
  cli_applicability: dual-path
  cli_support_evidence: "Confirmed via `aliyun help polardb-io` — PolarDB Oracle-compatible is supported by the official aliyun CLI."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

# Alibaba Cloud PolarDB Oracle-compatible Operations Skill

## Overview

PolarDB Oracle-compatible (PolarDB O / PolarDB IO) is Alibaba Cloud's cloud-native
database fully compatible with Oracle PL/SQL syntax, designed for enterprise Oracle
migration scenarios. This skill is an **operational runbook** for agents: explicit scope,
credential rules, pre-flight checks, **dual-path execution** (official **SDK/API** and
**CLI** flows), response validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` supports PolarDB-O via the
  `polardb-io` product slug. Each execution flow documents **both** the SDK step and
  the `aliyun` step for every operation.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "PolarDB Oracle" OR "PolarDB O" OR "PolarDB-O" OR "PolarDB IO" OR
  "云原生数据库PolarDB 兼容Oracle版" OR "PolarDB O引擎" OR "兼容Oracle"
- Task involves CRUD/lifecycle on **PolarDB-O DBClusters** (create, describe, modify,
  delete, start, stop, restart)
- Task involves **Oracle migration assessment** (ADAM, OMS compatibility)
- Task involves **accounts, databases, backups, endpoints, performance monitoring**
- Task keywords: PL/SQL, stored procedure, Oracle迁移 (Oracle migration), O引擎

### SHOULD NOT Use This Skill When

- Task is pure billing / RAM → billing / `alicloud-ram-ops`
- Task is **PolarDB MySQL** → delegate to: `alicloud-polar-mysql-ops`
- Task is **PolarDB PostgreSQL** → delegate to: `alicloud-polar-pg-ops`
- Task is **standalone Oracle Database** (not PolarDB) → out of scope
- Task is **RDS** → delegate to: `alicloud-rds-ops`
- Task requires **DAS diagnosis** → delegate to: `alicloud-das-ops`

### Delegation Rules

- VPC/VSwitch verification → `alicloud-vpc-ops`
- DAS diagnosis → `alicloud-das-ops`
- CMS alarm configuration → `alicloud-cms-ops`

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Runtime env | NEVER ask user |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Runtime env | NEVER ask user |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Runtime env | Documented default |
| `{{user.region}}` | User-supplied region | Ask once |
| `{{user.db_cluster_id}}` | Cluster ID | Ask once |
| `{{user.db_node_class}}` | Node specification | Ask once |
| `{{user.vpc_id}}` | VPC ID | Ask once |
| `{{user.vswitch_id}}` | VSwitch ID | Ask once |
| `{{user.account_name}}` | Account name | Ask once |
| `{{user.account_password}}` | Account password | Ask once |
| `{{user.db_name}}` | Database name | Ask once |
| `{{output.db_cluster_id}}` | From API response | Parse per OpenAPI |

## API and Response Conventions

- **ClientToken:** Generate UUID v4 for write operations for idempotency.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateDBCluster | `$.DBClusterId` | string | New cluster ID |
| DescribeDBClusters | `$.Items.DBCluster[].DBClusterId` | array | Cluster IDs |
| DescribeDBClusters | `$.Items.DBCluster[].DBClusterStatus` | string | Status |
| DescribeDBClusters | `$.Items.DBCluster[].DBVersion` | string | Engine version |
| DescribeDBClusterAttribute | `$.DBClusterDescription` | string | Cluster description |
| CreateAccount | `$.RequestId` | string | Request ID |
| DescribeAccounts | `$.Accounts.Account[].AccountName` | array | Account names |
| CreateDatabase | `$.RequestId` | string | Request ID |
| DescribeBackups | `$.Items.Backup[].BackupId` | array | Backup IDs |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateDBCluster | — | `Running` | 10s | 600s |
| DeleteDBCluster | any stable | absent | 10s | 300s |
| StartDBCluster | `Stopped` | `Running` | 10s | 300s |
| StopDBCluster | `Running` | `Stopped` | 10s | 300s |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-16 | Initial PolarDB Oracle-compatible skill with dual-path support |

## Quick Start

### Prerequisites
- [ ] `aliyun` CLI installed
- [ ] Credentials configured
- [ ] Region set

### First Command
```bash
aliyun polardb-io DescribeDBClusters --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Execution Flows (Agent-Readable)

### Operation: Create DB Cluster

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars | Non-empty keys | HALT |
| Region | `aliyun polardb-io DescribeRegions` | Supported | Suggest valid region |
| VPC/VSwitch | `aliyun vpc DescribeVpcs` | Exist | Delegate to `alicloud-vpc-ops` |

#### Execution — CLI (Primary Path)

```bash
aliyun polardb-io CreateDBCluster \
  --DBNodeClass "{{user.db_node_class}}" \
  --PayType Postpaid \
  --DBNodeNumber 2 \
  --RegionId "{{user.region}}" \
  --VPCId "{{user.vpc_id}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --DBClusterDescription "{{user.db_cluster_name}}" \
  --SecurityIPList "{{user.security_ip_list|10.0.0.0/8}}"
```

#### Execution — JIT Go SDK (Fallback Path)

```go
package main

import (
	"fmt"
	"os"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	polardbio "github.com/alibabacloud-go/polardb-io-20211126/v3/client"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
	}
	client, _ := polardbio.NewClient(config)

	req := &polardbio.CreateDBClusterRequest{
		DBNodeClass:          tea.String(os.Getenv("DB_NODE_CLASS")),
		PayType:              tea.String("Postpaid"),
		DBNodeNumber:         tea.Int32(2),
		RegionId:             tea.String(os.Getenv("REGION")),
		VPCId:                tea.String(os.Getenv("VPC_ID")),
		VSwitchId:            tea.String(os.Getenv("VSWITCH_ID")),
		DBClusterDescription: tea.String(os.Getenv("CLUSTER_NAME")),
		SecurityIPList:       tea.String(os.Getenv("SECURITY_IP_LIST")),
		ClientToken:          tea.String(os.Getenv("CLIENT_TOKEN")),
	}
	resp, _ := client.CreateDBCluster(req)
	fmt.Printf("Created PolarDB-O cluster: %s\n", tea.ToString(resp.Body.DBClusterId))
}
```

#### Post-execution Validation

Poll until `DBClusterStatus` is `Running`:
```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun polardb-io DescribeDBClusterAttribute \
    --DBClusterId "{{output.db_cluster_id}}" \
    --output cols=DBClusterStatus rows=DBClusterStatus)
  [ "$STATUS" = "Running" ] && break
  sleep 10
done
```

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` / 400 | 0–1 | — | Fix args from OpenAPI |
| `DBClusterQuotaExceeded` | 0 | — | HALT |
| `InsufficientBalance` | 0 | — | HALT |
| `ResourceAlreadyExists` | 0 | — | Ask reuse vs rename |
| Throttling / 429 | 3 | exponential | Back off |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Describe DB Clusters

#### Execution — CLI

```bash
# List all Oracle-compatible clusters
aliyun polardb-io DescribeDBClusters --RegionId "{{user.region}}"

# Describe specific cluster
aliyun polardb-io DescribeDBClusterAttribute --DBClusterId "{{user.db_cluster_id}}"

# Extract key fields
aliyun polardb-io DescribeDBClusters --RegionId "{{user.region}}" \
  --output cols=DBClusterId,DBClusterStatus,DBVersion,PayType rows=Items.DBCluster[].{DBClusterId,DBClusterStatus,DBVersion,PayType}
```

---

### Operation: Delete DB Cluster

#### Pre-flight (Safety Gate)**

- **MUST** obtain explicit confirmation before irreversible delete.
- Recommend final backup.

#### Execution — CLI

```bash
aliyun polardb-io DeleteDBCluster --DBClusterId "{{user.db_cluster_id}}"
```

#### Post-execution Validation

Poll until cluster is absent.

---

### Operation: Manage Nodes

#### Add DB Nodes — CLI

```bash
aliyun polardb-io AddDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeClass "{{user.db_node_class}}" \
  --DBNodesCount "{{user.db_nodes_count|1}}"
```

#### Remove DB Nodes — CLI

> **Safety Gate:** Confirm before removing.

```bash
aliyun polardb-io RemoveDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeIds "{{user.db_node_ids}}"
```

#### Describe DB Nodes — CLI

```bash
aliyun polardb-io DescribeDBNodes --DBClusterId "{{user.db_cluster_id}}"
```

---

### Operation: Manage Accounts

#### Create Account — CLI

```bash
aliyun polardb-io CreateAccount \
  --DBClusterId "{{user.db_cluster_id}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPassword "{{user.account_password}}" \
  --AccountType "Super"
```

#### Describe Accounts — CLI

```bash
aliyun polardb-io DescribeAccounts --DBClusterId "{{user.db_cluster_id}}"
```

---

### Operation: Manage Databases

#### Create Database — CLI

```bash
aliyun polardb-io CreateDatabase \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBName "{{user.db_name}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPrivilege "ReadWrite"
```

---

### Operation: Backup Management

#### Create Backup — CLI

```bash
aliyun polardb-io CreateBackup --DBClusterId "{{user.db_cluster_id}}"
```

#### Describe Backups — CLI

```bash
aliyun polardb-io DescribeBackups \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"
```

#### Configure Backup Policy — CLI

```bash
aliyun polardb-io ModifyBackupPolicy \
  --DBClusterId "{{user.db_cluster_id}}" \
  --PreferredBackupTime "02:00Z-03:00Z" \
  --PreferredBackupPeriod "Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday" \
  --BackupRetentionPeriod 30
```

---

### Operation: Manage Endpoints

#### Describe Endpoints — CLI

```bash
aliyun polardb-io DescribeDBClusterEndpoints --DBClusterId "{{user.db_cluster_id}}"
```

---

### Operation: Start / Stop Cluster

```bash
# Stop cluster
aliyun polardb-io StopDBCluster --DBClusterId "{{user.db_cluster_id}}"

# Start cluster
aliyun polardb-io StartDBCluster --DBClusterId "{{user.db_cluster_id}}"
```

---

### Operation: Upgrade Cluster

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation before upgrade.
- Suggest backup before upgrade.

#### Execution — CLI

```bash
aliyun polardb-io UpgradeDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeClass "{{user.target_node_class}}"
```

---

## PolarDB IO Cruise (Health Check)

| Step | Operation | Purpose | Alert Threshold |
|------|-----------|---------|-----------------|
| 1 | **DescribeDBClusterAttribute** | Verify cluster exists, status | HALT if NotFound |
| 2 | **DescribeDBNodes** | Check all node health | Alert if Unhealthy |
| 3 | **DescribeBackupPolicy** | Check backup schedule | Warn if no policy |
| 4 | **DescribeBackups** | Verify recent backup success | Alert if > 24h no backup |
| 5 | **DescribeAccounts** | Audit accounts | Log |
| 6 | **DescribeDatabases** | Check databases | Log |

## Prerequisites

1. **Install CLI**: `/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"`
2. **Configure Credentials**: export `ALIBABA_CLOUD_ACCESS_KEY_*` env vars
3. **Verify**: `aliyun polardb-io DescribeDBClusters`

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to PolarDB Oracle-compatible.

### 安全 (Security)

| Area | Guidance |
|------|----------|
| **IAM** | Require: `polardb:Describe*` scoped to `acs:polardb:*:*:dbcluster/*` |
| **Network** | VPC-only. White-list app IPs. SSL encryption |
| **Migration Security** | Use ADAM for Oracle→PolarDB migration assessment. Test schema compatibility before production cutover |

### 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | Multi-AZ deployment. Auto-failover < 30s. Compatible with Oracle HA patterns |
| **面向精细的运维管控** | Cruise health check: backup status, node health, account audit |
| **面向风险的应急快恢** | Point-in-time restore. **RTO:** < 15 min. **RPO:** 0 |

### 成本 (Cost)

| Billing | Best For | Savings |
|---------|----------|---------|
| Prepaid (包年包月) | Stable Oracle migration workloads | Up to 60% |
| Postpaid (按量) | Migration testing phase | N/A |

**Waste:** Oracle-compatible features unused after migration → disable. Idle clusters after cutover → decommission original Oracle.

### 效率 (Efficiency)

- **Oracle Compatibility:** Reduce migration effort with high Oracle syntax compatibility
- **ADAM:** Use Alibaba Cloud Database Autonomy Management for migration assessment
- **CI/CD:** JSON output by default

### 性能 (Performance)

| Metric | CMS Namespace | Scale Up | Scale Down | Window |
|--------|--------------|----------|------------|--------|
| CpuUsage | `acs_polardb_dashboard` | > 80% | < 40% | 5 min |
| ConnectionUsage | `acs_polardb_dashboard` | > 80% | < 50% | 5 min |
| IopsUsage | `acs_polardb_dashboard` | > 80% | < 50% | 5 min |

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)

## Operational Best Practices

- **Least privilege:** RAM scoped to `polardb-io:*` APIs.
- **Migration assessment:** Use ADAM before migrating Oracle workloads.
- **Security:** Minimum SecurityIPList; SSL encryption.
- **Backup:** Daily automated backups with 30+ day retention.
- **Monitoring:** CMS alarms for CPU > 85%, Connections > 80%.
