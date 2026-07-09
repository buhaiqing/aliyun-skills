---
name: alicloud-polar-pg-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba Cloud PolarDB PostgreSQL clusters (云原生数据库PolarDB PostgreSQL版) — cluster lifecycle, compute node scaling, account management, backup restoration, performance monitoring, and read/write splitting. User mentions PolarDB, PolarDB PostgreSQL, PolarDB PG, 云原生数据库PostgreSQL, PolarDB PG集群, or describes PG cluster-specific scenarios (creation, scaling, endpoint configuration) even without explicit naming. CLI: `aliyun polardb-pg`, SDK: polardb-pg-2021-11-26. NOT for RDS PostgreSQL, PolarDB MySQL, PolarDB Oracle-compatible (IO), Redis/Tair, MongoDB, or billing/RAM-only tasks.
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
  api_profile: "PolarDB PG 2021-11-26 / https://help.aliyun.com/zh/polardb/polardb-for-postgresql/"
  cli_applicability: dual-path
  cli_support_evidence: "Confirmed via `aliyun help polardb-pg` — PolarDB PostgreSQL is supported by the official aliyun CLI."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

# Alibaba Cloud PolarDB PostgreSQL Operations Skill

## Overview

PolarDB PostgreSQL is Alibaba Cloud's cloud-native PostgreSQL-compatible database with
compute-storage separation, distributed architecture, and parallel query support. This
skill is an **operational runbook** for agents: explicit scope, credential rules,
pre-flight checks, **dual-path execution** (official **SDK/API** and **CLI** flows),
response validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` supports PolarDB PG via the
  `polardb-pg` product slug. Each execution flow documents **both** the SDK step and
  the `aliyun` step for every operation.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "PolarDB PostgreSQL" OR "PolarDB PG" OR "云原生数据库PolarDB PostgreSQL版"
  OR "PolarDB PG集群"
- Task keywords: PG集群, compute node, read/write splitting, parallel query, distributed
  storage, 计算节点
- Task involves CRUD/lifecycle on **PolarDB PG DBClusters** (create, describe, modify,
  delete, start, stop, restart, upgrade)
- Task involves **compute node scaling** (add/remove DB nodes)
- Task involves **accounts, databases, backups, performance monitoring, endpoints**
- User requests "巡检", "health check", or PG cluster diagnosis

### SHOULD NOT Use This Skill When

- Task is purely billing / RAM → billing skill / `alicloud-ram-ops`
- Task is about **RDS PostgreSQL** → delegate to: `alicloud-rds-ops`
- Task is about **PolarDB MySQL** → delegate to: `alicloud-polar-mysql-ops`
- Task is about **PolarDB Oracle-compatible (O)** → delegate to: `alicloud-polar-oracle-ops`
- Task is about **Redis / MongoDB** → respective product skills
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
| `{{user.engine_version}}` | PG version (11/12/13/14) | Ask once; default 14 |
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
| DescribeDBClusters | `$.Items.DBCluster[].DBClusterStatus` | string | Status: Creating, Running, Stopped |
| DescribeDBClusters | `$.Items.DBCluster[].DBVersion` | string | PG version (11,12,13,14) |
| DescribeDBClusterAttribute | `$.DBClusterDescription` | string | Cluster description |
| CreateAccount | `$.RequestId` | string | Request ID |
| DescribeAccounts | `$.Accounts.Account[].AccountName` | array | Account names |
| CreateDatabase | `$.RequestId` | string | Request ID |
| DescribeBackups | `$.Items.Backup[].BackupId` | array | Backup IDs |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateDBCluster | — | `Running` | 10s | 600s |
| AddDBNodes | `Running` | `Running` | 10s | 600s |
| RemoveDBNodes | `Running` | `Running` | 10s | 300s |
| DeleteDBCluster | any stable | absent | 10s | 300s |
| StartDBCluster | `Stopped` | `Running` | 10s | 300s |
| StopDBCluster | `Running` | `Stopped` | 10s | 300s |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-16 | Initial PolarDB PG skill with dual-path support |

## Quick Start

### Prerequisites
- [ ] `aliyun` CLI installed
- [ ] Credentials configured in env vars
- [ ] Region set

### First Command
```bash
aliyun polardb-pg DescribeDBClusters --DBVersion PostgreSQL --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Execution Flows (Agent-Readable)

### Operation: Create DB Cluster

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars | Non-empty keys | HALT |
| Region | `aliyun polardb-pg DescribeRegions` | Supported | Suggest valid region |
| VPC/VSwitch | `aliyun vpc DescribeVpcs` | Exist | Delegate to `alicloud-vpc-ops` |
| PayType | Confirm Postpaid/Prepaid | Valid | Suggest Postpaid |

#### Execution — CLI (Primary Path)

```bash
aliyun polardb-pg CreateDBCluster \
  --DBVersion "{{user.engine_version|14}}" \
  --DBNodeClass "{{user.db_node_class}}" \
  --PayType Postpaid \
  --DBNodeNumber 2 \
  --StorageType cloud_essd \
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
	polardbpg "github.com/alibabacloud-go/polardb-pg-20211126/v2/client"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
	}
	client, _ := polardbpg.NewClient(config)

	req := &polardbpg.CreateDBClusterRequest{
		DBVersion:            tea.String(os.Getenv("ENGINE_VERSION")),
		DBNodeClass:          tea.String(os.Getenv("DB_NODE_CLASS")),
		PayType:              tea.String("Postpaid"),
		RegionId:             tea.String(os.Getenv("REGION")),
		VPCId:                tea.String(os.Getenv("VPC_ID")),
		VSwitchId:            tea.String(os.Getenv("VSWITCH_ID")),
		DBClusterDescription: tea.String(os.Getenv("CLUSTER_NAME")),
		SecurityIPList:       tea.String(os.Getenv("SECURITY_IP_LIST")),
		ClientToken:          tea.String(os.Getenv("CLIENT_TOKEN")),
	}
	resp, _ := client.CreateDBCluster(req)
	fmt.Printf("Created PolarDB PG cluster: %s\n", tea.ToString(resp.Body.DBClusterId))
}
```

#### Post-execution Validation

Poll until `DBClusterStatus` is `Running`:
```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun polardb-pg DescribeDBClusterAttribute \
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
# List all PostgreSQL clusters
aliyun polardb-pg DescribeDBClusters --DBVersion PostgreSQL --RegionId "{{user.region}}"

# Describe specific cluster
aliyun polardb-pg DescribeDBClusterAttribute --DBClusterId "{{user.db_cluster_id}}"

# Extract key fields
aliyun polardb-pg DescribeDBClusters --DBVersion PostgreSQL --RegionId "{{user.region}}" \
  --output cols=DBClusterId,DBClusterStatus,DBVersion,PayType rows=Items.DBCluster[].{DBClusterId,DBClusterStatus,DBVersion,PayType}
```

---

### Operation: Delete DB Cluster

#### Pre-flight (Safety Gate)**

- **MUST** obtain explicit confirmation before irreversible delete.
- Recommend final backup before deletion.

#### Execution — CLI

```bash
aliyun polardb-pg DeleteDBCluster --DBClusterId "{{user.db_cluster_id}}"
```

#### Post-execution Validation

Poll until cluster is absent.

---

### Operation: Manage Nodes

#### Add DB Nodes — CLI

```bash
aliyun polardb-pg AddDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeClass "{{user.db_node_class}}" \
  --DBNodesCount "{{user.db_nodes_count|1}}"
```

#### Remove DB Nodes — CLI

> **Safety Gate:** Confirm before removing.

```bash
aliyun polardb-pg RemoveDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeIds "{{user.db_node_ids}}"
```

#### Describe DB Nodes — CLI

```bash
aliyun polardb-pg DescribeDBNodes --DBClusterId "{{user.db_cluster_id}}"
```

---

### Operation: Manage Accounts

#### Create Account — CLI

```bash
aliyun polardb-pg CreateAccount \
  --DBClusterId "{{user.db_cluster_id}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPassword "{{user.account_password}}" \
  --AccountType "Normal"
```

#### Describe Accounts — CLI

```bash
aliyun polardb-pg DescribeAccounts --DBClusterId "{{user.db_cluster_id}}"
```

---

### Operation: Manage Databases

#### Create Database — CLI

```bash
aliyun polardb-pg CreateDatabase \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBName "{{user.db_name}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPrivilege "ReadWrite"
```

---

### Operation: Backup Management

#### Create Backup — CLI

```bash
aliyun polardb-pg CreateBackup --DBClusterId "{{user.db_cluster_id}}"
```

#### Describe Backups — CLI

```bash
aliyun polardb-pg DescribeBackups \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"
```

#### Configure Backup Policy — CLI

```bash
aliyun polardb-pg ModifyBackupPolicy \
  --DBClusterId "{{user.db_cluster_id}}" \
  --PreferredBackupTime "02:00Z-03:00Z" \
  --PreferredBackupPeriod "Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday" \
  --BackupRetentionPeriod 30
```

---

### Operation: Manage Endpoints

#### Describe Endpoints — CLI

```bash
aliyun polardb-pg DescribeDBClusterEndpoints --DBClusterId "{{user.db_cluster_id}}"
```

#### Modify Endpoint (RW Splitting) — CLI

```bash
aliyun polardb-pg ModifyDBClusterEndpoint \
  --DBClusterId "{{user.db_cluster_id}}" \
  --EndpointId "{{user.endpoint_id}}" \
  --ReadWriteSplittingPolicy "LoadBalance"
```

---

### Operation: Upgrade Cluster

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation before upgrade.
- Suggest backup before upgrade.

#### Execution — CLI

```bash
aliyun polardb-pg UpgradeDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeClass "{{user.target_node_class}}"
```

---

### Operation: Start / Stop Cluster

```bash
# Stop cluster
aliyun polardb-pg StopDBCluster --DBClusterId "{{user.db_cluster_id}}"

# Start cluster
aliyun polardb-pg StartDBCluster --DBClusterId "{{user.db_cluster_id}}"
```

---

## PolarDB PG Cruise (Health Check)

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
3. **Verify**: `aliyun polardb-pg DescribeDBClusters --DBVersion PostgreSQL`

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)

## Operational Best Practices

- **Least privilege:** RAM scoped to `polardb-pg:*` APIs.
- **Availability:** Multi-AZ for production.
- **Security:** Minimum SecurityIPList; SSL encryption.
- **Backup:** Daily automated backups with 30+ day retention.
- **Monitoring:** CMS alarms for CPU > 85%, Connections > 80%.
