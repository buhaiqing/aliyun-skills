---
name: alicloud-polar-mysql-ops-rubric
description: >-
  GCL rubric for `alicloud-polar-mysql-ops` (PolarDB MySQL — cluster
  lifecycle, accounts, databases, backup, nodes, endpoints, SQL
  execution). Phase 1, eleventh skill. **Canonical for all 4 PolarDB
  skills** (polar-mysql, polar-postgresql, polar-oracle, polar-pg).
  Paired with `prompt-templates.md`.
license: MIT
metadata:
  skill: alicloud-polar-mysql-ops
  api: PolarDB 2022-05-30
  cli_applicability: dual-path
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - prompt-templates.md
    - ../../alicloud-rds-ops/references/rubric.md
---

# PolarDB GCL Rubric (Phase 1 — Eleventh Skill — **Canonical for all 4 PolarDB variants**)

PolarDB is the **distributed relational database family** for Alibaba Cloud.
This rubric is the **canonical source** for all 3 PolarDB skills
(`alicloud-polar-mysql-ops`, `alicloud-polar-postgresql-ops`,
`alicloud-polar-oracle-ops`). The other 2
rubrics inherit this structure with engine-specific notes
(MySQL → PostgreSQL → Oracle).

PolarDB inherits the **RDS-style GCL risk model** (DDL/DML with WHERE-clause
hard rule, control-plane delete with backup) and adds **cluster-level
ops** (multi-node, RW/RO splitting, distributed transactions).

> **Hard rules:** Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
> **`DeleteDBCluster` is irreversible** — PolarDB has no recycle bin for
> clusters. The trace MUST show a final backup created in the same flow.
> **SQL Execution WHERE-clause rule (inherited from RDS):** `DELETE` /
> `UPDATE` without `WHERE` → Safety = 0.

## 1. Per-Op Safety Sub-Rules

| Operation | Sub-rule (Score 1) |
|---|---|
| `DeleteDBCluster` | (a) user confirmation naming `{{user.db_cluster_id}}` AND `{{user.db_cluster_name}}`; (b) `DBClusterStatus == Running`; (c) **final backup created in the same flow** (no waiver); (d) no active endpoints serving production; (e) for cross-region clusters: all child nodes terminated |
| `CreateDBCluster` | (a) user confirmation of region, engine, version, node spec, primary count; (b) quota not exceeded; (c) VPC + VSwitch verified; (d) `DBClusterName` does not duplicate an existing cluster in the region |
| `ModifyDBCluster` (scale up) | (a) user confirmation; (b) brief connection interruption warned |
| `ModifyDBCluster` (scale **down** / downgrade) | (a) user confirmation; (b) **data size < new storage capacity**; (c) current connections < new max_connections (via CMS) |
| `CreateAccount` | (a) `AccountName` not `root` / `admin`; (b) `AccountPassword` via env var; (c) `AccountType` ∈ {Normal, Super}; (d) password complexity met (engine-specific) |
| `DeleteAccount` | (a) user confirmation; (b) account verified via `DescribeAccounts` |
| `ResetAccountPassword` | (a) user confirmation; (b) `AccountPassword` NOT in trace; (c) complexity met |
| `CreateBackup` | (a) cluster is `Running`; (b) backup retention within quota |
| `RestoreDBCluster` | (a) user confirmation; (b) `BackupId` verified; (c) cross-cluster restore requires extra confirmation; (d) **target cluster must NOT be serving production** during restore (or maintenance window confirmed) |
| `Manage Endpoints` (create / modify / delete) | (a) user confirmation; (b) for RW endpoint delete: warn that writes will fail; (c) for RO endpoint delete: warn that read-only traffic shifts to primary |
| `Node Management` (add / remove node) | (a) user confirmation; (b) for node removal: ensure replica set still has quorum (≥ 2 of 3 nodes) |
| `Upgrade Cluster Version` | (a) user confirmation; (b) **final backup created**; (c) maintenance window confirmed |
| `Start / Stop Cluster` | (a) user confirmation; (b) **warn that cluster is unavailable during stop**; (c) no active writes pending |
| `SQL Execution` (data-plane) | See §2 — inherits RDS WHERE-clause rule + 6-class classification |

## 2. SQL Execution (data-plane) — inherits from `alicloud-rds-ops` rubric

PolarDB SQL execution uses `mysql` / `psql` / `sqlplus` client via
endpoint (Primary for writes, Cluster for RW-splitting, Custom for
specific node groups). The 6-class classification from RDS rubric applies
unchanged:

| Risk class | SQL verbs (MySQL variant) | SQL verbs (PG/Oracle variants) | Sub-rule |
|---|---|---|---|
| READ-ONLY | `SELECT`, `SHOW`, `EXPLAIN` | `SELECT`, `\d`, `EXPLAIN` | None |
| WRITE-LIMITED | `INSERT`, `UPDATE` (with WHERE), `REPLACE` | `INSERT`, `UPDATE` (with WHERE) | User confirmation; selective WHERE |
| DESTRUCTIVE-LIMITED | `DELETE` (with WHERE), `TRUNCATE`, `DROP TABLE` | `DELETE` (with WHERE), `TRUNCATE`, `DROP TABLE` | User confirmation; backup created in same flow |
| DESTRUCTIVE-MASS | `DELETE` / `UPDATE` without WHERE, `DROP DATABASE` | `DELETE` / `UPDATE` without WHERE, `DROP DATABASE` / `DROP SCHEMA` | **Safety = 0** unless explicit justification |
| SCHEMA-MUTATION | `CREATE TABLE`, `ALTER TABLE`, `GRANT` | `CREATE TABLE`, `ALTER TABLE`, `GRANT` | User confirmation; impact analysis |
| FATAL | `SHUTDOWN`, `SET GLOBAL` high-risk vars | `pg_terminate_backend` (broad), `ALTER SYSTEM` high-risk | Hard block |

> **Engine-specific regex hot-spots** are inherited from RDS rubric §1.2.1
> with PG additions: `^drop\s+schema\b`, `^vacuum\s+full\b` (locks the
> table for the duration), `^alter\s+system\s+set\b` (durable cluster-wide
> setting change).

## 3. Other Dimensions
- **Correctness**: 1.0 for `Delete*` (post-execution `DescribeDBClusterAttribute`).
- **Idempotency**: `CreateDBCluster` must check `DescribeDBClusters --DBClusterName` first. `CreateAccount` must check `DescribeAccounts`. `CreateBackup` natural idempotent.
- **Traceability**: `DeleteDBCluster` requires `backup_trace`; SQL Execution requires `affected_rows` and `statement_count`.
- **Spec Compliance**: engine version in supported set (MySQL 5.6/5.7/8.0; PG 11/12/13/14/15; Oracle 11g/12c/19c; PG-2021 13/14); node count in {1, 2, 4, 8, 16}.
- **Region Compliance**: regional. PolarDB does NOT support cross-region cluster access without DTS.
- **Credential Hygiene**: 8 patterns from RDS + new: `DBClusterName` is not a secret. `polardb-AccountPassword` is a secret.
- **Well-Architected**: stability (≥ 2 nodes for prod); cost (right-sized node spec); performance (PolarDB MySQL uses parallel query for > 1TB).

## 4. Worked Example

`DeleteDBCluster` PASS (with final backup):

```json
{
  "iter": 1,
  "generator": {
    "command": "aliyun polardb DeleteDBCluster --DBClusterId pc-bp1...",
    "exit_code": 0
  },
  "preflight": {
    "user_confirmation": "User confirmed: 'delete pc-bp1... (legacy-mysql-cluster), backup pc-bp1-final created at 2026-06-04T13:50Z.'",
    "backup_trace": [
      {"command": "CreateBackup --DBClusterId pc-bp1...", "result": "BackupId pc-bp1-final", "status": "Success"}
    ]
  },
  "critic": { "scores": { "correctness": 1, "safety": 1, "idempotency": 1,
    "traceability": 1, "spec_compliance": 1, "region_compliance": 1,
    "credential_hygiene": 1, "well_architected": 1 }, "blocking": false },
  "decision": "PASS"
}
```

## 5. Anti-Patterns
- ❌ `DeleteDBCluster` without final backup (no waiver)
- ❌ `DELETE` / `UPDATE` without WHERE
- ❌ `VACUUM FULL` on production table (long lock)
- ❌ `ALTER SYSTEM SET` without backup of original value
- ❌ `DROP DATABASE` / `DROP SCHEMA` without backup
- ❌ Wildcard GRANT (e.g. `GRANT ALL ON *.*`)

## 6. Changelog
1.0.0 | 2026-06-04 | Initial PolarDB GCL rubric (Phase 1, eleventh skill, **canonical for all 4 PolarDB variants**). Inherits RDS WHERE-clause + 6-class SQL classification; adds cluster-level ops (DeleteDBCluster with final backup, Manage Endpoints, Node Management).
