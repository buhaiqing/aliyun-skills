---
name: alicloud-polar-mysql-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba Cloud PolarDB MySQL clusters (云原生数据库PolarDB MySQL版) — cluster lifecycle, account management, database management, backup restoration, performance monitoring, serverless scaling, and GDN. User mentions PolarDB, PolarDB MySQL, PolarDB集群, 云原生数据库, PolarDB for MySQL, or describes cluster-specific scenarios (creation, scaling, endpoint configuration, serverless, read/write splitting) even without explicit naming. CLI: `aliyun polardb`, SDK: polardb-2022-05-30. NOT for RDS MySQL, PolarDB PostgreSQL, PolarDB Oracle-compatible (IO), Redis/Tair, MongoDB, or billing/RAM-only tasks.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.5.0"
  last_updated: "2026-06-04"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "PolarDB 2022-05-30 / https://help.aliyun.com/zh/polardb/polardb-for-mysql/"
  cli_applicability: dual-path
  cli_support_evidence: "Confirmed via `aliyun help polardb` — PolarDB MySQL is supported by the official aliyun CLI."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud PolarDB MySQL Operations Skill

## Overview

PolarDB MySQL is Alibaba Cloud's cloud-native relational database, MySQL-compatible,
featuring compute-storage separation, serverless scaling, and global database networks
(GDN). This skill is an **operational runbook** for agents: explicit scope, credential
rules, pre-flight checks, **dual-path execution** (official **SDK/API** and **CLI** flows),
response validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` fully supports PolarDB MySQL
  via the `polardb` product slug. Each execution flow documents **both** the SDK step
  and the `aliyun` step for every operation.

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers and delegation rules |
| 2 | **Structured I/O** | Placeholders (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) with type and source |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute → Validate → Recover |
| 4 | **Complete Failure Strategies** | Error taxonomy with ≥ 10 product-specific codes; HALT vs retry |
| 5 | **Absolute Single Responsibility** | PolarDB MySQL clusters only; delegates other products |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "PolarDB MySQL" OR "PolarDB for MySQL" OR "云原生数据库PolarDB MySQL版"
  OR "PolarDB集群" with MySQL context
- Task keywords: 集群 (cluster), 节点 (node), 读写分离 (read/write split), 弹性
  (elastic), Serverless, 全局数据库 (GDN), endpoint, DBNode, DBEndpoint
- Task involves CRUD or lifecycle on **PolarDB DBClusters** (create, describe, modify,
  delete, start, stop, pause, resume, upgrade)
- Task involves **cluster nodes** (add, remove, restart DBNodes)
- Task involves **cluster endpoints** (create, modify, release, configure RW splitting)
- Task involves **accounts** (create privileged/ordinary accounts, grant privileges)
- Task involves **databases** (create, delete databases within cluster)
- Task involves **backups** (create, describe, restore, configure backup policy)
- Task involves **performance monitoring** (CPU, memory, IOPS, connections, TPS/QPS)
- Task involves **security** (whitelist, SSL, TDE, data masking)
- Task involves **serverless** scaling (configure serverless, monitor RCUs)
- Task involves **SQL execution** on PolarDB cluster (run SQL, execute .sql file, query slow logs)
- User asks to "巡检", "health check", or diagnose a PolarDB MySQL cluster
- User asks to "执行 SQL", "跑 SQL 文件", "导入数据" on PolarDB cluster
- User asks to "查询慢 SQL 统计" on PolarDB cluster (统计数据，不含诊断优化)
- User asks to "预测存储", "容量预测", "存储趋势" on PolarDB cluster
- User asks to "预测连接数", "连接趋势", "高峰预警" on PolarDB cluster
- User asks to "异常检测", "根因分析", "CPU突增" on PolarDB cluster
- User mentions "AIOps", "智能运维", "预测分析" with PolarDB context

> **⚠️ 与 DAS skill 边界说明：**
> - **本 Skill 负责**：SQL 执行（ExecuteSQL/ExecuteSQLFile）、慢日志统计查询（DescribeSlowLogRecords）
> - **DAS Skill 负责**：慢 SQL **诊断优化**、SQL 性能分析、锁分析、自动 SQL 限流
> - 边界关键词："执行 SQL" → PolarDB；"优化 SQL"、"诊断慢 SQL" → DAS

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to billing skill
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops`
- Task is about **RDS MySQL** → delegate to: `alicloud-rds-ops`
- Task is about **PolarDB PostgreSQL** → delegate to: `alicloud-polar-pg-ops`
- Task is about **PolarDB Oracle-compatible (O)** → delegate to: `alicloud-polar-oracle-ops`
- Task is about **Redis / Tair** → delegate to: `alicloud-redis-ops`
- Task requires **DAS diagnosis** (SQL throttling, auto-scaling, deadlock analysis)
  → delegate to: `alicloud-das-ops`
- User insists on **console-only** flows with no API

### Delegation Rules

- If creating a cluster in a VPC, verify VPC and VSwitch exist (via `alicloud-vpc-ops`)
  before cluster creation.
- If DAS diagnosis needed (slow SQL, deadlock, auto-optimization), use `alicloud-das-ops`.
- If CloudMonitor alarm triggered, use `alicloud-cms-ops` for alarm rule management,
  then this skill for cluster health check.
- Multi-product requests: handle each product with its skill.

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Documented default if allowed |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.db_cluster_id}}` | DBCluster ID | Ask once; reuse |
| `{{user.db_cluster_name}}` | Cluster description | Ask once; reuse |
| `{{user.engine_version}}` | MySQL version (5.6/5.7/8.0) | Ask once; default 8.0 |
| `{{user.db_node_class}}` | Node specification | Ask once; reuse |
| `{{user.vpc_id}}` | VPC ID | Ask once; reuse |
| `{{user.vswitch_id}}` | VSwitch ID | Ask once; reuse |
| `{{user.account_name}}` | Account name | Ask once; reuse |
| `{{user.account_password}}` | Account password | Ask once |
| `{{user.db_name}}` | Database name | Ask once; reuse |
| `{{output.db_cluster_id}}` | From API/CLI response | Parse per OpenAPI |
| `{{output.request_id}}` | From API response | For correlation |

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for all paths, fields, enums, and response shapes.
- **ClientToken:** Generate UUID v4 for write operations for idempotency.
- **Timestamps:** ISO 8601 format.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateDBCluster | `$.DBClusterId` | string | New cluster ID |
| DescribeDBClusters | `$.Items.DBCluster[].DBClusterId` | array | Cluster IDs |
| DescribeDBClusters | `$.Items.DBCluster[].DBClusterStatus` | string | Cluster status |
| DescribeDBClusters | `$.Items.DBCluster[].DBType` | string | MySQL |
| DescribeDBClusters | `$.Items.DBCluster[].DBVersion` | string | Engine version |
| DescribeDBClusters | `$.Items.DBCluster[].DBClusterClass` | string | Cluster class |
| DescribeDBClusters | `$.Items.DBCluster[].PayType` | string | Postpaid / Prepaid |
| DescribeDBClusters | `$.Items.DBCluster[].RegionId` | string | Region ID |
| DescribeDBClusters | `$.Items.DBCluster[].VPCId` | string | VPC ID |
| DescribeDBClusters | `$.Items.DBCluster[].StorageUsed` | string | Storage used (bytes) |
| DescribeDBClusterAttribute | `$.DBClusterDescription` | string | Cluster description |
| CreateAccount | `$.RequestId` | string | Request ID |
| DescribeAccounts | `$.Accounts.Account[].AccountName` | array | Account names |
| DescribeAccounts | `$.Accounts.Account[].AccountPrivilege` | string | Account privilege |
| CreateDatabase | `$.RequestId` | string | Request ID |
| DescribeDatabases | `$.Databases.Database[].DBName` | array | Database names |
| DescribeBackups | `$.Items.Backup[].BackupId` | array | Backup IDs |
| DescribeBackupPolicy | `$.PreferredBackupTime` | string | Backup window |
| DescribeBackupPolicy | `$.PreferredBackupPeriod` | string | Backup days |
| CreateBackup | `$.BackupJobId` | string | Backup job ID |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateDBCluster | — | `Running` | 10s | 600s |
| StartDBCluster | `Paused` / `Stopped` | `Running` | 10s | 300s |
| StopDBCluster | `Running` | `Stopped` | 10s | 300s |
| PauseDBCluster | `Running` | `Paused` | 10s | 300s |
| ResumeDBCluster | `Paused` | `Running` | 10s | 300s |
| DeleteDBCluster | any stable | absent | 10s | 300s |
| CreateAccount | — | `Available` | 5s | 120s |
| AddDBNodes | `Running` | `Running` (with new nodes) | 10s | 600s |
| UpgradeDBCluster | `Running` | `Running` | 10s | 600s |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.5.0 | 2026-05-27 | Extend AIOps anomaly detection: 12 patterns (P001-P012), 5 PolarDB-specific patterns (Replication Lag, Read Node Imbalance, Storage IO, GDN Sync, Serverless Elasticity), Pattern Correlation Engine (DOPS-85277) |
| 1.4.0 | 2026-05-26 | Add Slow Query Analysis workflow: DescribeSlowLogs/DescribeSlowLogRecords, Top N identification, index optimization recommendations, and diagnostic report template (DOPS-85274) |
| 1.3.0 | 2026-05-26 | Add AIOps capabilities: Storage Prediction (30/60/90 days), Connection Prediction (cycle detection), Anomaly Detection (root cause correlation) (DOPS-85275) |
| 1.2.0 | 2026-05-26 | Add SQL execution capability (ExecuteSQL, ExecuteSQLFile, DescribeSlowQueryLogs) with safety controls (DOPS-85273) |
| 1.1.0 | 2026-05-26 | Add FinOps storage tier (PSLevel) cost optimization analysis (DOPS-85270) |
| 1.0.0 | 2026-05-16 | Initial PolarDB MySQL skill with dual-path (CLI + SDK) support |

## Quick Start

### Prerequisites
- [ ] `aliyun` CLI installed
- [ ] Credentials: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region: `ALIBABA_CLOUD_REGION_ID`

### First Command
```bash
# List all PolarDB MySQL clusters in region
aliyun polardb DescribeDBClusters --DBType MySQL --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Capabilities at a Glance

| Operation | Description | Risk |
|-----------|-------------|------|
| CreateDBCluster | Create PolarDB MySQL cluster | Low |
| DescribeDBClusters | View cluster details | None |
| ModifyDBCluster | Modify cluster configuration | Medium |
| DeleteDBCluster | Delete cluster | **High** |
| AddDBNodes / RemoveDBNodes | Scale compute nodes | Medium |
| CreateAccount / CreateDatabase | Create accounts & databases | Low |
| DescribeBackups / CreateBackup | Backup management | Low |
| UpgradeDBCluster | Upgrade cluster specification | Medium |
| StartDBCluster / StopDBCluster | Start or stop cluster | Low |
| PauseDBCluster / ResumeDBCluster | Serverless pause/resume | Low |
| ExecuteSQL | Execute single SQL statement | Medium |
| ExecuteSQLFile | Execute .sql file with multiple statements | Medium |
| DescribeSlowQueryLogs | Query slow SQL statistics | None |
| SlowQueryAnalysis | Full slow query workflow: Top N, index recommendations, report | None |
| PredictStorageTrend | Predict storage growth (30/60/90 days) | None |
| PredictConnectionPeak | Predict connection peak based on cycle | None |
| DetectAnomaly | CPU anomaly detection + root cause analysis | None |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI + SDK) → Validate → Recover**.

### Operation: Create DB Cluster

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys | HALT; user configures |
| Region | `aliyun polardb DescribeRegions` | `{{user.region}}` supported | Suggest valid region |
| Engine / Version | `aliyun polardb DescribeDBClusterAvailableClasses` | `MySQL` version supported | Suggest valid combo |
| VPC/VSwitch | `aliyun vpc DescribeVpcs` / `DescribeVSwitches` | Exist in region | Delegate to `alicloud-vpc-ops` |
| PayType | Confirm Postpaid or Prepaid | Valid | Suggest Postpaid (default) |

#### Execution — CLI (Primary Path)

```bash
aliyun polardb CreateDBCluster \
  --DBType MySQL \
  --DBVersion "{{user.engine_version|8.0}}" \
  --DBCategory "{{user.db_category|Normal}}" \
  --PayType Postpaid \
  --DBNodeClass "{{user.db_node_class}}" \
  --DBNodeNumber "{{user.db_node_number|2}}" \
  --StorageType PSLevel5 \
  --StorageSpace "{{user.storage_space|50}}" \
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
	polardb "github.com/alibabacloud-go/polardb-20220530/v3/client"
	teautil "github.com/alibabacloud-go/tea-utils/v2/service"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
	}
	client, _ := polardb.NewClient(config)

	req := &polardb.CreateDBClusterRequest{
		DBType:              tea.String("MySQL"),
		DBVersion:           tea.String(os.Getenv("ENGINE_VERSION")),
		PayType:             tea.String("Postpaid"),
		DBNodeClass:         tea.String(os.Getenv("DB_NODE_CLASS")),
		RegionId:            tea.String(os.Getenv("REGION")),
		VPCId:               tea.String(os.Getenv("VPC_ID")),
		VSwitchId:           tea.String(os.Getenv("VSWITCH_ID")),
		DBClusterDescription: tea.String(os.Getenv("CLUSTER_NAME")),
		SecurityIPList:      tea.String(os.Getenv("SECURITY_IP_LIST")),
		ClientToken:         tea.String(os.Getenv("CLIENT_TOKEN")),
	}
	resp, _ := client.CreateDBCluster(req)
	fmt.Printf("Created PolarDB cluster: %s\n", tea.ToString(resp.Body.DBClusterId))
}
```

#### Post-execution Validation

1. Read `{{output.db_cluster_id}}` from `$.DBClusterId`.
2. Poll until `DBClusterStatus` is `Running`:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun polardb DescribeDBClusterAttribute \
    --DBClusterId "{{output.db_cluster_id}}" \
    --output cols=DBClusterStatus rows=DBClusterStatus)
  [ "$STATUS" = "Running" ] && break
  sleep 10
done
```

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` / 400 | 0–1 | — | Fix args from OpenAPI; retry once |
| `DBClusterQuotaExceeded` | 0 | — | HALT; user raises quota |
| `InsufficientBalance` | 0 | — | HALT; recharge account |
| `ResourceAlreadyExists` | 0 | — | Ask reuse vs new name |
| `VPCIdNotFound` / `VSwitchIdNotFound` | 0 | — | Delegate to `alicloud-vpc-ops` |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Describe DB Clusters

#### Execution — CLI

```bash
# List all MySQL clusters
aliyun polardb DescribeDBClusters --DBType MySQL --RegionId "{{user.region}}"

# Describe specific cluster
aliyun polardb DescribeDBClusterAttribute --DBClusterId "{{user.db_cluster_id}}"

# Extract key fields
aliyun polardb DescribeDBClusters --DBType MySQL --RegionId "{{user.region}}" \
  --output cols=DBClusterId,DBClusterStatus,DBVersion,PayType,DBClusterDescription rows=Items.DBCluster[].{DBClusterId,DBClusterStatus,DBVersion,PayType,DBClusterDescription}
```

#### Execution — JIT Go SDK

```go
req := &polardb.DescribeDBClustersRequest{
	DBType:   tea.String("MySQL"),
	RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
}
resp, _ := client.DescribeDBClusters(req)
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Cluster ID | `$.DBClusterId` | Plain text |
| Description | `$.DBClusterDescription` | User-defined name |
| Status | `$.DBClusterStatus` | Creating, Running, Stopped, Paused, Restarting |
| Engine Version | `$.DBVersion` | 5.6, 5.7, 8.0 |
| Node Class | `$.DBNodeClass` | e.g., polar.mysql.x4.medium |
| Node Count | `$.DBNodeNumber` | Primary + read nodes |
| VPC / VSwitch | `$.VPCId` / `$.VSwitchId` | Network config |
| Storage Used | `$.StorageUsed` | Bytes |
| Expire Time | `$.ExpireTime` | ISO 8601 (Prepaid only) |
| PayType | `$.PayType` | Postpaid / Prepaid |

---

### Operation: Modify DB Cluster (Scale / Upgrade)

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation before modifying cluster.
- Warn user that spec change may cause brief downtime.
- Verify cluster is in `Running` status.

#### Execution — CLI

```bash
aliyun polardb ModifyDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeClass "{{user.target_node_class}}"
```

To upgrade version:
```bash
aliyun polardb UpgradeDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBVersion "{{user.target_version}}"
```

#### Execution — JIT Go SDK

```go
req := &polardb.ModifyDBClusterRequest{
	DBClusterId: tea.String(os.Getenv("DB_CLUSTER_ID")),
	DBNodeClass: tea.String(os.Getenv("TARGET_NODE_CLASS")),
}
resp, _ := client.ModifyDBCluster(req)
```

#### Post-execution Validation

Poll `DBClusterStatus` returns to `Running`.

---

### Operation: Delete DB Cluster

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of cluster
  `{{user.db_cluster_id}}` (`{{user.db_cluster_name}}`).
- **MUST NOT** proceed without clear user assent.
- Recommend: Create final backup before deletion (optional, user decides).

#### Execution — CLI

```bash
aliyun polardb DeleteDBCluster --DBClusterId "{{user.db_cluster_id}}"
```

#### Execution — JIT Go SDK

```go
req := &polardb.DeleteDBClusterRequest{
	DBClusterId: tea.String(os.Getenv("DB_CLUSTER_ID")),
}
resp, _ := client.DeleteDBCluster(req)
```

#### Post-execution Validation

Poll until cluster is absent (DescribeDBClusterAttribute returns error or empty):

```bash
for i in $(seq 1 30); do
  RESULT=$(aliyun polardb DescribeDBClusterAttribute \
    --DBClusterId "{{user.db_cluster_id}}" 2>/dev/null || echo "not_found")
  [ "$RESULT" = "not_found" ] && break
  sleep 10
done
```

---

### Operation: Manage Accounts

#### Create Account — CLI

```bash
aliyun polardb CreateAccount \
  --DBClusterId "{{user.db_cluster_id}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPassword "{{user.account_password}}" \
  --AccountType "{{user.account_type|Normal}}"
```

#### Describe Accounts — CLI

```bash
aliyun polardb DescribeAccounts --DBClusterId "{{user.db_cluster_id}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Account Name | `$.Accounts.Account[].AccountName` | Plain text |
| Account Type | `$.Accounts.Account[].AccountType` | Normal (privileged) |
| Status | `$.Accounts.Account[].AccountStatus` | Available, Creating |
| Granted Privileges | `$.Accounts.Account[].DatabasePrivileges[]` | Associated databases |

---

### Operation: Manage Databases

#### Create Database — CLI

```bash
aliyun polardb CreateDatabase \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBName "{{user.db_name}}" \
  --CharacterSetName "utf8mb4" \
  --AccountName "{{user.account_name}}" \
  --AccountPrivilege "ReadWrite"
```

#### Describe Databases — CLI

```bash
aliyun polardb DescribeDatabases --DBClusterId "{{user.db_cluster_id}}"
```

---

### Operation: Backup Management

#### Create Backup — CLI

```bash
aliyun polardb CreateBackup \
  --DBClusterId "{{user.db_cluster_id}}" \
  --BackupLevel "{{user.backup_level|ClusterLevel}}" \
  --BackupMethod "{{user.backup_method|Physical}}"
```

#### Describe Backups — CLI

```bash
aliyun polardb DescribeBackups \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"
```

#### Configure Backup Policy — CLI

```bash
aliyun polardb ModifyBackupPolicy \
  --DBClusterId "{{user.db_cluster_id}}" \
  --PreferredBackupTime "{{user.backup_time|02:00Z-03:00Z}}" \
  --PreferredBackupPeriod "{{user.backup_days|Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday}}" \
  --BackupRetentionPeriod "{{user.retention|30}}"
```

#### Present Backups

| Field | Path | Notes |
|-------|------|-------|
| Backup ID | `$.Items.Backup[].BackupId` | Plain text |
| Status | `$.Items.Backup[].BackupStatus` | Success, Failed |
| Type | `$.Items.Backup[].BackupType` | Snapshot, Physical, Logical |
| Size | `$.Items.Backup[].BackupSize` | Bytes |
| StartTime | `$.Items.Backup[].BackupStartTime` | ISO 8601 |

---

### Operation: Node Management

#### Add DB Nodes — CLI

```bash
aliyun polardb AddDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeClass "{{user.db_node_class}}" \
  --DBNodesCount "{{user.db_nodes_count|1}}"
```

#### Remove DB Nodes — CLI

> **Safety Gate:** Confirm before removing. Verify node has no active connections.

```bash
aliyun polardb RemoveDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeIds "{{user.db_node_ids}}"
```

#### Describe DB Nodes — CLI

```bash
aliyun polardb DescribeDBNodes \
  --DBClusterId "{{user.db_cluster_id}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Node ID | `$.Items.DBDetail[].DBNodeId` | Unique identifier |
| Region | `$.Items.DBDetail[].RegionId` | Region |
| Role | `$.Items.DBDetail[].Role` | Reader, Writer |
| Zone ID | `$.Items.DBDetail[].ZoneId` | Availability zone |
| Health | `$.Items.DBDetail[].HealthStatus` | Healthy, Unhealthy |

---

### Operation: Manage Endpoints

#### Describe Endpoints — CLI

```bash
aliyun polardb DescribeDBClusterEndpoints \
  --DBClusterId "{{user.db_cluster_id}}"
```

#### Modify Read/Write Splitting — CLI

```bash
aliyun polardb ModifyDBClusterEndpoint \
  --DBClusterId "{{user.db_cluster_id}}" \
  --EndpointId "{{user.endpoint_id}}" \
  --ReadWriteSplittingPolicy "{{user.rw_policy|LoadBalance}}" \
  --ReadNodes "{{user.read_nodes}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Endpoint | `$.EndItems.Endpoint[].DBEndpointId` | Endpoint ID |
| Connection String | `$.EndItems.Endpoint[].Address[].ConnectionString` | Host address |
| Port | `$.EndItems.Endpoint[].Address[].Port` | Port number |
| Type | `$.EndItems.Endpoint[].DBEndpointType` | Primary / Custom |
| Node List | `$.EndItems.Endpoint[].DBEndpointNodeIdList[]` | Attached nodes |

---

### Operation: SQL Execution

PolarDB MySQL 支持通过 mysql 客户端执行 SQL，提供多种 Endpoint 类型实现读写分离和查询优化。

#### Endpoint Types for SQL Execution

| Endpoint Type | Connection String Pattern | Use Case |
|---------------|---------------------------|----------|
| **Primary** | `pc-xxxx.mysql.polardb.rds.aliyuncs.com` | All write operations (INSERT, UPDATE, DELETE, DDL) |
| **Cluster** | `pc-xxxx-cluster.mysql.polardb.rds.aliyuncs.com` | Read-write splitting, automatic query routing |
| **Custom** | User-defined | Specific node group (e.g., read-only nodes for analytics) |

#### Operations

| Operation | Description | How to Execute |
|-----------|-------------|----------------|
| **ExecuteSQL** | Execute single SQL statement | mysql client with selected endpoint |
| **ExecuteSQLFile** | Execute .sql file with multiple statements | mysql client with input redirect |
| **DescribeSlowQueryLogs** | Query slow SQL statistics | `aliyun polardb DescribeSlowLogRecords` |

#### Safety Controls

- **Dangerous SQL Detection**: DROP, TRUNCATE, DELETE without WHERE → User confirmation required
- **Endpoint Selection**: Write operations → Primary Endpoint; Read operations → Cluster/Custom Endpoint
- **Result Masking**: Sensitive data (passwords, PII) not displayed in output

> **完整实现**请参阅: [references/sql-execution.md](references/sql-execution.md)

---

### Operation: Slow Query Analysis (慢查询分析)

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Cluster Status | `DescribeDBClusterAttribute` | `Running` | HALT if not ready |
| Time Range | Validate `{{user.start_time}}` to `{{user.end_time}}` | ≤ 7 days | Adjust range or split query |
| Slow Log Enabled | Check audit log collector | Enabled | Warn if disabled |

#### Execution — CLI: Slow Log Statistics (统计概览)

```bash
# Query slow SQL statistics (聚合统计)
aliyun polardb DescribeSlowLogs \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"
```

#### Execution — CLI: Slow Log Records (详细记录)

```bash
# Query detailed slow SQL records (支持分页)
aliyun polardb DescribeSlowLogRecords \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --PageSize 100 \
  --PageNumber 1
```

#### Execution — JIT Go SDK

```go
// DescribeSlowLogs - 统计概览
req := &polardb.DescribeSlowLogsRequest{
    DBClusterId: tea.String(os.Getenv("DB_CLUSTER_ID")),
    StartTime:   tea.String(os.Getenv("START_TIME")),
    EndTime:     tea.String(os.Getenv("END_TIME")),
}
resp, _ := client.DescribeSlowLogs(req)

// DescribeSlowLogRecords - 详细记录
reqDetail := &polardb.DescribeSlowLogRecordsRequest{
    DBClusterId: tea.String(os.Getenv("DB_CLUSTER_ID")),
    StartTime:   tea.String(os.Getenv("START_TIME")),
    EndTime:     tea.String(os.Getenv("END_TIME")),
    PageSize:    tea.Int32(100),
    PageNumber:  tea.Int32(1),
}
respDetail, _ := client.DescribeSlowLogRecords(reqDetail)
```

#### Response Field Mapping

**DescribeSlowLogs (统计概览):**

| Field | JSON Path | Description |
|-------|-----------|-------------|
| SQL Text | `$.Items.SQLSlowLog[].SQLText` | SQL statement pattern |
| DB Name | `$.Items.SQLSlowLog[].DBName` | Database name |
| Slow Log Counts | `$.Items.SQLSlowLog[].SlowLogCounts` | Number of slow query occurrences |
| Total Counts | `$.Items.SQLSlowLog[].TotalCounts` | Total query executions |
| Max Query Time | `$.Items.SQLSlowLog[].MaxQueryTime` | Maximum execution time (seconds) |
| Avg Query Time | `$.Items.SQLSlowLog[].AvgQueryTime` | Average execution time (seconds) |

**DescribeSlowLogRecords (详细记录):**

| Field | JSON Path | Description |
|-------|-----------|-------------|
| SQL Text | `$.Items.SQLSlowRecord[].SQLText` | Complete SQL statement |
| Query Time | `$.Items.SQLSlowRecord[].QueryTime` | Duration in seconds |
| Query Time (ms) | `$.Items.SQLSlowRecord[].QueryTimeMS` | Duration in milliseconds |
| Lock Time (ms) | `$.Items.SQLSlowRecord[].LockTimeMS` | Lock wait time |
| Rows Examined | `$.Items.SQLSlowRecord[].ParseRowCounts` | Rows scanned |
| Rows Returned | `$.Items.SQLSlowRecord[].ReturnRowCounts` | Rows returned |
| Client IP | `$.Items.SQLSlowRecord[].HostAddress` | Client IP address |
| Start Time | `$.Items.SQLSlowRecord[].QueryStartTime` | Query execution start timestamp |

#### Slow Query Analysis Workflow

**Step 1: Top N 慢查询识别**

```bash
# 获取 Top N 慢查询（按总耗时排序）
aliyun polardb DescribeSlowLogRecords \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --PageSize 100 | \
  jq '.Items.SQLSlowRecord[] | {sql: .SQLText, time: .QueryTimeMS, rows_scanned: .ParseRowCounts, db: .DBName}' | \
  sort -k2 -nr | head -{{user.top_n|10}}
```

**Step 2: 执行计划分析**

Analyze execution patterns from slow log records:

| Pattern | Detection Criteria | Action |
|---------|-------------------|--------|
| Full Table Scan | `ParseRowCounts` > 10,000 AND high scan ratio | Create composite index on filter columns |
| High Lock Time | `LockTimeMS` > 1000 | Optimize transaction size |
| Large Offset Pagination | SQL contains `LIMIT ... OFFSET` with large offset | Key-based pagination recommended |
| Missing Index | `ParseRowCounts` / `ReturnRowCounts` > 100 | Add covering index |

**Step 3: 诊断报告模板**

```markdown
PolarDB 慢查询分析报告:
├── Top 10 慢查询
│   ├── SQL: SELECT ... (执行时间: 12.5s, 次数: 245)
│   ├── 表扫描: 全表扫描 (rows: 1,200,000)
│   └── 建议: 添加索引 idx_xxx
├── 慢查询趋势
│   ├── 今日慢查询数: 45 (↑ 20%)
│   └── 平均执行时间: 3.2s
└── 根因分析
    ├── 连接-慢查询关联: 存在 3 个热点查询
    └── 索引缺失: 涉及 5 张表
```

> **深度诊断边界：** 如需深度 SQL 优化建议、执行计划 EXPLAIN、锁分析、SQL 限流，委托至 `alicloud-das-ops` Skill。

> **详细工作流文档**请参阅: [references/slow-query-analysis.md](references/slow-query-analysis.md)

---

## PolarDB MySQL Cruise (Health Check Workflow)

For comprehensive cluster health assessment when user requests "巡检" or "health check":

| Step | Operation | Purpose | Alert Threshold |
|------|-----------|---------|-----------------|
| 1 | **DescribeDBClusterAttribute** | Verify cluster exists, get status | HALT if NotFound |
| 2 | **DescribeDBNodes** | Check all node health statuses | Alert if Unhealthy node |
| 3 | **DescribeDBClusterEndpoints** | Verify connectivity endpoints | Log warning if no endpoint |
| 4 | **DescribeBackupPolicy** | Check backup schedule configured | Alert if no backup policy |
| 5 | **DescribeBackups** | Verify recent backup success | Alert if > 24h no backup |
| 6 | **DescribeAccounts** | Audit accounts | Warn if no accounts |
| 7 | **DescribeDatabases** | Check database count | Log for awareness |

---

## FinOps: PolarDB Node-Level Resource Analysis

For comprehensive cost optimization through node-level resource efficiency analysis.

### Extended Cruise Workflow (Step 8)

| Step | Operation | Purpose | Alert Threshold |
|------|-----------|---------|-----------------|
| **8** | **DescribeDBNodes + GetMetricStatisticsData** | Node-level CPU/Memory efficiency | Alert if reader node CPU < 30% |

### Quick Analysis

```bash
# Get all nodes with roles (RegionId optional but recommended)
aliyun polardb DescribeDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=DBNodeId,Role,ZoneId,HealthStatus rows=Items.DBDetail[]
```

### Output Example

```
PolarDB 节点级分析:
├── 主节点 (polar-xxx-writer) - CPU: avg 45%, peak 78%
├── 只读节点1 (polar-xxx-reader-1) - CPU: avg 8% ⚠️ 利用率低
├── 只读节点2 (polar-xxx-reader-2) - CPU: avg 35%
└── 优化建议: 移除只读节点1 (节省 ￥800/月)
```

> **完整实现**请参阅: [references/finops-node-analysis.md](references/finops-node-analysis.md)

---

## FinOps: PolarDB Storage Tier (PSLevel) Cost Optimization

For comprehensive cost optimization through storage tier (PSLevel) efficiency analysis.

### Extended Cruise Workflow (Step 9)

| Step | Operation | Purpose | Alert Threshold |
|------|-----------|---------|-----------------|
| **9** | **DescribeDBClusterAttribute + CMS Metrics** | Storage tier suitability + pack optimization | Alert if IOPS < 30% tier capacity |

### Analysis Scope

- **存储层级适配度**: PSLevel1-5 性能与成本对比，识别过度/不足配置
- **存储包购买建议**: 基于当前用量和增长趋势推荐最优规格
- **数据分层策略**: 热/冷数据分布分析，归档路径建议

### Output Example

```
PolarDB 存储层级分析:
├── 当前配置: PSLevel2 - IOPS利用率24% ⚠️ 过度配置
├── 建议降级: PSLevel3 - 预期节省23%
├── 存储包建议: 1TB包 - 月度节省￥170
└── 数据分层: 冷数据77% - 归档至PSLevel5节省65%
```

> **完整实现**请参阅: [references/finops-storage-tier-analysis.md](references/finops-storage-tier-analysis.md)

---

## AIOps: PolarDB Storage Space Trend Prediction

For predictive capacity planning through storage growth trend analysis.

### Extended Cruise Workflow (Step 10)

| Step | Operation | Purpose | Alert Threshold |
|------|-----------|---------|-----------------|
| **10** | **CMS GetMetricStatisticsData + Trend Analysis** | Storage growth prediction (30/60/90 days) | Alert if predicted to reach 85% within 30 days |

### Analysis Scope

- **存储增长预测**: 基于30天历史数据预测 30/60/90 天存储增长趋势
- **阈值到达时间**: 预测达到 85%/95%/100% 阈值的具体日期
- **扩容建议生成**: 根据预警级别自动触发扩容建议和存储包购买推荐

### Prediction Accuracy

| Algorithm | Accuracy Target | Use Case |
|-----------|-----------------|----------|
| Linear Regression | 85-95% | 稳定增长趋势 |
| Weighted Moving Average | 82-92% | 波动型增长 |
| Exponential Smoothing | 88-95% | 季节性波动 |

### Output Example

```
PolarDB 存储空间趋势预测:
├── 当前使用: 750.5 GB / 1000 GB (75.05%)
├── 增长分析: 日增 0.25%, 月增 7.5%
├── 未来预测:
│   ├── 30天后: 825.5 GB (82.6%)
│   ├── 60天后: 900.5 GB (90.1%) ⚠️
│   └── 90天后: 975.5 GB (97.6%) 🚨
├── 阈值预测:
│   ├── 85%预警: 40天后 (2026-07-05)
│   ├── 95%高危: 80天后 (2026-08-15)
│   └── 100%满载: 100天后 (2026-09-04)
└── 扩容建议: 增加 250GB + 购买 500GB 存储包
```

> **完整实现**请参阅: [references/aiops-storage-prediction.md](references/aiops-storage-prediction.md)

---

## AIOps: PolarDB Connection Trend Prediction

For proactive connection bottleneck prevention through business cycle analysis.

### Extended Cruise Workflow (Step 11)

| Step | Operation | Purpose | Alert Threshold |
|------|-----------|---------|-----------------|
| **11** | **CMS GetMetricStatisticsData + Cycle Detection** | Connection peak prediction | Alert if predicted peak > 80% of max_connections |

### Analysis Scope

- **业务周期识别**: 检测日/周/月周期模式，识别高峰时段
- **高峰连接预测**: 预测下一个高峰时段的连接数峰值
- **瓶颈风险评估**: 评估 80%/90%/100% 阈值风险，提前预警

### Cycle Detection Confidence

| Cycle Type | Detection Method | Confidence Target |
|------------|------------------|-------------------|
| Daily Cycle | Hourly pattern analysis | > 80% |
| Weekly Cycle | Workday vs weekend analysis | > 70% |
| Monthly Cycle | STL decomposition | > 85% |

### Output Example

```
PolarDB 连接数趋势预测:
├── 当前连接: 2,850 / 5,000 (57.0%)
├── 周期检测:
│   ├── 日周期: 高峰 10:00-12:00 (置信度 88%)
│   └── 周周期: 高峰 周一/周二 (置信度 72%)
├── 高峰预测:
│   ├── 下一个高峰: 3,800 (76.0%) @ 2026-05-27 10:00
│   └── 本周高峰: 4,200 (84.0%) @ 2026-05-28 10:00
├── 阈值风险:
│   ├── 80%预警: ⚠️ 将达到 (medium)
│   ├── 90%高危: ⚠️ 将达到 (high)
│   └── 100%上限: ✅ 不会超过
└── 优化建议: 调整 max_connections → 6000，预热连接池
```

> **完整实现**请参阅: [references/aiops-connection-prediction.md](references/aiops-connection-prediction.md)

---

## AIOps: PolarDB Anomaly Detection

For automated performance anomaly detection with root cause correlation.

### Extended Cruise Workflow (Step 12)

| Step | Operation | Purpose | Alert Threshold |
|------|-----------|---------|-----------------|
| **12** | **Multi-Metric Analysis + Correlation** | Anomaly detection + root cause tracing | Alert on CPU spike > 50% sudden increase |

### Detection Architecture

| Layer | Algorithm | Detection Type |
|-------|-----------|----------------|
| Layer 1 | Threshold comparison | Static threshold (CPU > 85%, SlowQueries > 50/h) |
| Layer 2 | Trend analysis | Moving average + slope (连续3周期上升 > 10%) |
| Layer 3 | Sudden spike detection | Statistical deviation (突增 > 50%) |

### Root Cause Chain Model

```
异常传播链路:
CPU Spike (突增) → Slow Query Increase (慢查询增加) → Lock Wait (锁等待) → Connection Bottleneck (连接瓶颈)
```

### Output Example

```
PolarDB 异常检测报告:
├── 主异常: CPU突增 85.2% (基线 33% → 当前 85.2%, 突增 52%)
├── 关联异常: 慢查询增加 (120/h, 基线 20/h)
├── 根因链路:
│   CPU突增 → 慢查询 → 锁等待 45s → 连接瓶颈 92%
├── Top慢SQL:
│   ├── SELECT * FROM orders WHERE... (12.5s, 扫描850万行)
│   └── UPDATE inventory SET... (8.3s, 锁等待12s)
└── 优化建议: SQL限流 + 索引优化 + 调整连接池
```

> **完整实现**请参阅: [references/aiops-anomaly-detection.md](references/aiops-anomaly-detection.md)

---

## Prerequisites

1. **Install `aliyun` CLI** (primary execution path):
   ```bash
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   ```
2. **Bootstrap Go runtime** (JIT SDK fallback — see execution-environment.md)
3. **Configure Credentials**:
   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```
   > **IMPORTANT:** When outputting the above commands to console or logs, the agent MUST replace `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` with the masking format `****` instead of the actual secret value (i.e., display as `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"`). Never resolve `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` to its actual value in any visible output.

4. **Verify Configuration**:
   ```bash
   aliyun polardb DescribeDBClusters --DBType MySQL
   ```

## Intelligent Diagnosis Workflow

| User Input Pattern | Diagnosis Type | AIOps Enhancement |
|-------------------|----------------|-------------------|
| "CPU 告警" / "CPU 高" | CPU Performance | **AIOps Anomaly Detection** (根因链路追踪) |
| "磁盘告警" / "空间不足" | Disk Capacity (storage) | **AIOps Storage Prediction** (30/60/90天趋势) |
| "连接数告警" | Connection Exhaustion | **AIOps Connection Prediction** (周期高峰预测) |
| "慢查询" / "SQL 慢" | Query Performance | Anomaly Detection (慢查询关联) |
| "集群宕机" / "连不上" | Availability | Manual diagnosis |
| "巡检异常" / "健康检查失败" | General Health | Extended Cruise Workflow (Step 8-12) |
| "异常检测" / "根因分析" | Anomaly Detection | **AIOps Layer 1-3** (阈值/趋势/突增) |
| "容量预测" / "趋势分析" | Capacity Planning | **AIOps Prediction** (存储/连接) |

### Supported Anomaly Patterns

| # | Pattern | Detection Criteria | Common Causes | Recommended Action |
|---|---------|-------------------|---------------|-------------------|
| 1 | **CPU-IOPS双高** | CPU > 80% + IOPS 接近上限 | 复杂查询/分析型SQL、短时间内大量并发 | 检查慢查询、优化SQL、增加只读节点 |
| 2 | **连接-慢查询关联** | Connections 高 + SlowQueries 增加 | 连接池耗尽、慢查询积累阻塞 | 排查慢SQL、优化连接池、检查阻塞 |
| 3 | **内存-缓冲池瓶颈** | Memory > 85% + BufferPoolHitRate < 95% | 缓冲池配置不足、大表全表扫描 | 扩容内存、优化SQL、调整缓冲池大小 |
| 4 | **存储-延迟模式** | StorageUsage > 85% + Latency 突增 | 存储空间不足、写入阻塞 | 扩容存储、清理历史数据、归档冷数据 |

> **Note:** For complex anomaly diagnosis (SQL throttling, deadlock analysis, auto-scaling), delegate to `alicloud-das-ops`.

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to PolarDB MySQL.

### 安全 (Security)

| Area | Guidance |
|------|----------|
| **IAM** | Require: `polardb:Describe*`, `polardb:CreateDBCluster` scoped to `acs:polardb:*:*:dbcluster/*` |
| **Network** | VPC-only. White-list application IPs — never `0.0.0.0/0`. SSL encryption for in-transit data |
| **Data at Rest** | Enable TDE. Use cluster-level encryption keys |

### 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | Deploy read-write nodes + multiple read-only nodes across zones. Auto-failover < 30s |
| **面向精细的运维管控** | Monitor CPU, connections, IOPS, storage. CMS alerts at 80% |
| **面向风险的应急快恢** | Point-in-time restore via backup. **RTO:** < 10 min. **RPO:** 0 (binlog) |

### 成本 (Cost)

| Billing | Best For | Savings |
|---------|----------|---------|
| Postpaid (按量) | Dev/test, variable workloads | N/A |
| Prepaid (包年包月) | Stable production | Up to 60% |
| Serverless | Unpredictable workloads | Pay per capacity unit |
| Storage Pack | Large storage needs | Lower per-GB cost |

**Waste:** Read-only nodes with < 5% query routing → remove or consolidate. Storage > 70% free → consider downgrade at next cycle.

### 效率 (Efficiency)

- **Read-Write Splitting:** Automatic routing to read-only nodes
- **Parallel Query:** Enable for analytical queries on large datasets
- **CI/CD:** JSON output by default, compatible with pipelines

### 性能 (Performance)

| Metric | CMS Namespace | Scale Up | Scale Down | Window |
|--------|--------------|----------|------------|--------|
| CpuUsage | `acs_polardb_dashboard` | > 80% | < 40% | 5 min |
| ConnectionUsage | `acs_polardb_dashboard` | > 80% | < 50% | 5 min |
| IopsUsage | `acs_polardb_dashboard` | > 80% | < 50% | 5 min |
| StorageUsage | `acs_polardb_dashboard` | > 85% | < 60% | 5 min |

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)
- [SQL Execution](references/sql-execution.md) — SQL 执行能力（ExecuteSQL、ExecuteSQLFile、慢查询）
- [Slow Query Analysis Workflow](references/slow-query-analysis.md) — 慢查询分析工作流：Top N、趋势分析、索引优化建议
- [FinOps: Node Analysis](references/finops-node-analysis.md) — 节点级成本优化分析
- [FinOps: Storage Tier Analysis](references/finops-storage-tier-analysis.md) — 存储层级成本优化分析
- [AIOps: Storage Prediction](references/aiops-storage-prediction.md) — 存储空间趋势预测（30/60/90天）
- [AIOps: Connection Prediction](references/aiops-connection-prediction.md) — 连接数趋势预测（业务周期分析）
- [AIOps: Anomaly Detection](references/aiops-anomaly-detection.md) — 异常检测与根因分析

## Related Skills & References

- See: [alicloud-das-ops](../alicloud-das-ops/SKILL.md) — DAS诊断联动 (SQL throttling, deadlock analysis, auto-scaling)
- See: [Proactive Inspection Template](../alicloud-skill-generator/templates/proactive-inspection.md) — 主动巡检模板

## Operational Best Practices

- **Least privilege:** RAM policies scoped to `polardb:*` APIs only.
- **Availability:** Deploy across multiple zones for production.
- **Cost:** Use Postpaid for elasticity, Prepaid for stable long-term workloads.
- **Security:** Restrict SecurityIPList to minimum; use SSL encryption.
- **Backup:** Enable automated daily backups with 30+ day retention.
- **Monitoring:** Set CMS alarms for CPU > 85%, Connections > 80%, Storage > 85%.
- **Serverless:** Consider Serverless mode for variable workload clusters.

---

## Quality Gate (GCL)

Eleventh rollout of GCL per [`AGENTS.md` §12](../../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). **This skill is the canonical PolarDB rubric** for all 4 PolarDB variants. See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 1, eleventh skill, **canonical for all 4 PolarDB variants**) |
| `max_iter` | 2 |
| Inherits | RDS WHERE-clause + 6-class SQL classification |
| Most-scrutinized | `DeleteDBCluster` (mandatory final backup, **no waiver**), `Manage Endpoints` (RW/RO mismatch), SQL Execution WHERE-clause rule |
| Endpoint selection | Primary (writes) / Cluster (RW-split) / Custom (node group) |

### Changelog
1.0.0 | 2026-06-04 | Eleventh rollout; canonical for polar-postgresql, polar-oracle, polar-pg.

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `dual-path`，CLI/SDK 已覆盖，无需 code snippets.
