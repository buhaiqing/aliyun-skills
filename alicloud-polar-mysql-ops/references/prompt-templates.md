---
name: alicloud-polar-mysql-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-polar-mysql-ops` (**canonical for all
  4 PolarDB variants**). Phase 1, eleventh skill.
license: MIT
metadata:
  skill: alicloud-polar-mysql-ops
  api: PolarDB 2022-05-30
  cli_applicability: dual-path
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
    - ../../alicloud-rds-ops/references/rubric.md
---

# PolarDB GCL Prompt Templates (Phase 1 — Eleventh Skill — **Canonical for all 4 PolarDB variants**)

Inherits structure from `AGENTS.md` §12.7 and the RDS pilot. PolarDB
additions: **cluster-level ops** (`DeleteDBCluster` with mandatory final
backup, `Manage Endpoints`, `Node Management`); **endpoint selection
rules** (Primary for writes, Cluster for RW-splitting, Custom for node
groups); **PG/Oracle engine-specific SQL regex** (covered in rubric §2).

> Critic in isolated context. `{{user.request}}` absent from Critic template.

## Generator (excerpt)

```text
You are the Generator in a GCL for Alibaba Cloud PolarDB.

# Hard rules
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any trace value.
- `AccountPassword` MUST be passed via env var (`$POLARDB_NEW_PASSWORD`),
  NOT via `--AccountPassword "value"`.
- `DeleteDBCluster` MUST be preceded by `CreateBackup` in the SAME
  flow. Record in `backup_trace`. No waiver.
- `DeleteDBCluster` with `DBClusterStatus == Running` and serving
  production traffic requires `maintenance_window_confirmed=true`.
- `Upgrade Cluster Version` requires final backup + maintenance window.
- SQL Execution (data-plane via `mysql` / `psql` / `sqlplus`):
  - Use **Primary endpoint** for writes.
  - Use **Cluster endpoint** for read-write splitting.
  - Use **Custom endpoint** for specific node group.
  - Inherits RDS WHERE-clause rule: `DELETE` / `UPDATE` without
    `WHERE` → Safety = 0.
  - `DROP DATABASE` / `DROP SCHEMA` / `TRUNCATE` / `VACUUM FULL` →
    require backup in same flow.
- Engine-specific PG additions: `VACUUM FULL` (locks table);
  `ALTER SYSTEM SET` (durable cluster-wide change).
- All `{{user.*}}` placeholders MUST be resolved interactively.
```

## Critic (excerpt)

```text
You are the Critic in a GCL for Alibaba Cloud PolarDB. Read-only.

# Checks
- For `DeleteDBCluster`: independently verify `backup_trace` is present
  and successful. Missing → Safety = 0.
- For SQL Execution: apply the RDS WHERE-clause + 6-class regexes
  from `rubric.md` §2.
- For PG/Oracle engines: apply additional regexes
  (`^vacuum\s+full\b`, `^alter\s+system\s+set\b`).
- For endpoint ops: verify the endpoint type matches the operation
  type (write → Primary, read → Cluster/Custom).
- Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
- Suggestions ≤ 3, concrete.
```

## Anti-Patterns
- ❌ `DeleteDBCluster` without final backup
- ❌ `DELETE` / `UPDATE` without WHERE
- ❌ `VACUUM FULL` on prod table
- ❌ `ALTER SYSTEM SET` without backup of original value
- ❌ Write to RO endpoint (will fail or degrade)

## Changelog
1.0.0 | 2026-06-04 | Initial PolarDB GCL prompt templates (Phase 1, eleventh skill, **canonical for all 4 PolarDB variants**).
