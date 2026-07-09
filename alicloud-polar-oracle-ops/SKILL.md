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
  version: "1.1.0"
  last_updated: "2026-06-04"
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

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/polar-oracle-skillopt-wrapper.sh` for all Polar-Oracle CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun polar-oracle` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md) |

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
- Task is **PolarDB PostgreSQL** → delegate to: `alicloud-polar-postgresql-ops`
- Task is **standalone Oracle Database** (not PolarDB) → out of scope
- Task is **RDS** → delegate to: `alicloud-rds-ops`
- Task requires **DAS diagnosis** → delegate to: `alicloud-das-ops`

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

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

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

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

> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/polar-oracle-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun polardb-io ...` 命令在执行时应替换为 `./scripts/polar-oracle-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun polardb-io` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。

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
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)（CreateDBCluster → Running, 60×10s）
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

### Operation: Intelligent Inspection

**Purpose:** Proactive discovery of PolarDB Oracle performance bottlenecks, storage risks, and session anomalies.

**5-step workflow:** Discovery (list clusters) → Collection (CPU/Memory/IOPS/Storage/Sessions) → Detection (4 anomaly pattern rules) → Diagnosis (slow SQL, tablespace, sessions) → Report (Markdown).

Full CLI script template at [references/cli-usage.md](references/cli-usage.md#intelligent-inspection).

**Inspection scoring:**

| Metric | Threshold | Score |
|--------|-----------|-------|
| CPUUtilization | < 80% | 10 |
| StorageUsage | < 85% | 10 |
| Sessions | < 80% max | 10 |
| SlowQuery | < 5/hour | 10 |

**Total < 40 → Critical** (immediate action required)

**Anomaly detection rules:**

| Rule | Metric | Threshold |
|------|--------|-----------|
| CPU high | CPUUtilization | > 80% (Warning) / > 95% (Critical) |
| Memory high | MemoryUtilization | > 85% |
| Storage low | StorageUsage | > 85% |
| Connection high | Connections | > 80% max |

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

## Well-Architected Assessment

Evaluated per Alibaba Cloud [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).

| Pillar | Key Guidance |
|--------|-------------|
| **Security** | IAM: `polardb:Describe*`. VPC-only, never `0.0.0.0/0`. Enable SSL. Use ADAM for migration assessment before production cutover |
| **Stability** | Multi-AZ deployment. Auto-failover < 30s. PITR. RTO < 15min, RPO=0. Cruise: backup, node health, account audit |
| **Cost** | Prepaid up to 60% off. Postpaid for migration testing. Disable unused Oracle-compatible features after migration. Decommission original Oracle after cutover |
| **Efficiency** | High Oracle PL/SQL compatibility reduces migration effort. ADAM for assessment. JSON output for CI/CD |
| **Performance** | CpuUsage > 80% scale up, < 40% down. ConnectionUsage > 80% alert. IOPSUsage > 80% alert |

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Polling Patterns](references/polling-patterns.md) — 集群状态/删除轮询模板与 `--waiter` 备选
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)

## Operational Best Practices

- **Least privilege:** RAM scoped to `polardb-io:*` APIs.
- **Migration assessment:** Use ADAM before migrating Oracle workloads.
- **Security:** Minimum SecurityIPList; SSL encryption.
- **Backup:** Daily automated backups with 30+ day retention.
- **Monitoring:** CMS alarms for CPU > 85%, Connections > 80%.

---

## Quality Gate (GCL)

Thirteenth rollout of GCL per [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). **Inherits canonical from `alicloud-polar-mysql-ops`** + Oracle-specific deviations. See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 1, thirteenth skill) |
| `max_iter` | 2 |
| Engine | Oracle 11g/12c/19c |
| Oracle hot-spots | `DROP USER ... CASCADE` (require `expdp`), `ALTER SYSTEM SET ... SCOPE=SPFILE` (require `original_value_backup`), `GRANT DBA` (privilege escalation, require justification), `DROP TABLESPACE ... INCLUDING CONTENTS` (require RMAN) |
| PL/SQL risk | DDL inside `BEGIN ... END;` blocks — Critic must parse inner SQL |
| Credential surface | `ORACLE_PASSWORD` / `POLARDB_ORACLE_NEW_PASSWORD` env vars (NOT `sqlplus user/pass@host`) |

### Changelog
1.0.0 | 2026-06-04 | Thirteenth rollout; inherits canonical + Oracle-specific.

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `dual-path`，CLI/SDK 已覆盖，无需 code snippets.
