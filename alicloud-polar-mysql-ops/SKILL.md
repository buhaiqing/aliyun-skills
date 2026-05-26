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
  version: "1.1.0"
  last_updated: "2026-05-26"
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
- User asks to "巡检", "health check", or diagnose a PolarDB MySQL cluster

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

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field value (including `ALIBABA_CLOUD_ACCESS_KEY_ID`) in console output, debug messages, error messages, or logs. If credential information must be displayed for debugging or troubleshooting purposes, use the masking format: show only the first 4 characters followed by `****` (e.g., `abcd****`). This masking rule applies to ALL output channels: stdout, stderr, log files, debug traces, error messages, and diagnostic reports. Verify existence only via `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"`.

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

| User Input Pattern | Diagnosis Type |
|-------------------|----------------|
| "CPU 告警" / "CPU 高" | CPU Performance |
| "磁盘告警" / "空间不足" | Disk Capacity (storage) |
| "连接数告警" | Connection Exhaustion |
| "慢查询" / "SQL 慢" | Query Performance |
| "集群宕机" / "连不上" | Availability |
| "巡检异常" / "健康检查失败" | General Health |

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
- [FinOps: Node Analysis](references/finops-node-analysis.md) — 节点级成本优化分析
- [FinOps: Storage Tier Analysis](references/finops-storage-tier-analysis.md) — 存储层级成本优化分析

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
