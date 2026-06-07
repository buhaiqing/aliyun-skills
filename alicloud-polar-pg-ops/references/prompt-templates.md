---
name: alicloud-polar-pg-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-polar-pg-ops`. Inherits canonical
  from `alicloud-polar-mysql-ops`; adds polar-pg 2021-11-26 API
  deviations. Phase 1, fourteenth skill.
license: MIT
metadata:
  skill: alicloud-polar-pg-ops
  engine: postgresql
  api: polardb-pg 2021-11-26
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
    - ../../alicloud-polar-mysql-ops/references/prompt-templates.md
    - ../../alicloud-polar-postgresql-ops/references/prompt-templates.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# PolarDB PG (2021) GCL Prompt Templates (Phase 1 — Fourteenth Skill)

Inherits from `alicloud-polar-mysql-ops` and `alicloud-polar-postgresql-ops`.
**polar-pg-ops 2021-11-26 deviations:**
- CLI: `aliyun polardb-pg` (NOT `aliyun polardb`).
- Operation names: `CreateDBInstance` / `DeleteDBInstance` /
  `DescribeDBInstanceAttribute` (NOT `*DBCluster*`).
- Engine versions: PG 11–14 (NOT PG 15).

> Critic in isolated context. `{{user.request}}` absent from Critic template.

## Generator (excerpt)

```text
You are the Generator in a GCL for Alibaba Cloud PolarDB PostgreSQL (2021 API).

# Hard rules
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any trace value.
- `{{env.PGPASSWORD}}` / `{{env.POLARDB_PG_NEW_PASSWORD}}` MUST be passed via env var.
- `DeleteDBInstance` MUST be preceded by `CreateBackup` in the SAME flow.
  No waiver. Record in `backup_trace`.
- **Use the 2021-11-26 operation names**: `CreateDBInstance` /
  `DeleteDBInstance` / `DescribeDBInstanceAttribute` (NOT the 2022
  `*DBCluster*` names). Wrong API for this skill → Spec Compliance = 0.
- **Engine version must be PG 11/12/13/14** (NOT PG 15 — not supported
  on the 2021-11-26 API).
- Inherits all canonical PolarDB + PG-specific rules:
  `DELETE` / `UPDATE` without `WHERE` → Safety = 0;
  `VACUUM FULL` locks table;
  `ALTER SYSTEM SET` requires original_value_backup;
  etc.
```

## Critic (excerpt)

```text
You are the Critic in a GCL for Alibaba Cloud PolarDB PG (2021). Read-only.

# Checks
- Apply canonical PolarDB + PG-specific checks.
- ADD polar-pg-ops 2021 deviations:
  - Verify operation name matches 2021-11-26 API
    (`CreateDBInstance` / `DeleteDBInstance` /
    `DescribeDBInstanceAttribute`).
  - Verify engine version is PG 11/12/13/14 (reject PG 15).
- Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
- Suggestions ≤ 3, concrete.
```

## Anti-Patterns (polar-pg-ops specific)
- ❌ Using 2022-05-30 operation names on this skill
- ❌ Requesting PG 15

## Changelog
1.0.0 | 2026-06-04 | PolarDB PG (2021) GCL prompt templates (Phase 1, fourteenth skill).
