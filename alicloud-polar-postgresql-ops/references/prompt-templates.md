---
name: alicloud-polar-postgresql-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-polar-postgresql-ops`. Inherits
  canonical from `alicloud-polar-mysql-ops`; adds PG-specific. Phase 1,
  twelfth skill.
license: MIT
metadata:
  skill: alicloud-polar-postgresql-ops
  engine: postgresql
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
    - ../../alicloud-polar-mysql-ops/references/prompt-templates.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# PolarDB PostgreSQL GCL Prompt Templates (Phase 1 — Twelfth Skill)

Inherits structure from `alicloud-polar-mysql-ops/references/prompt-templates.md`.
**PostgreSQL additions:**
- Client: `psql` (not `mysql`).
- Password env var: `PGPASSWORD` (not `MYSQL_PWD`).
- Connection string: `postgresql://user:<masked>@host:5432/db`.
- Engine-specific hot-spots: `VACUUM FULL`, `ALTER SYSTEM SET`,
  `REINDEX`, `CLUSTER`, `DROP SCHEMA`.

> Critic in isolated context. `{{user.request}}` absent from Critic template.

## Generator (excerpt)

```text
You are the Generator in a GCL for Alibaba Cloud PolarDB PostgreSQL.

# Hard rules (PG additions on top of canonical)
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any trace value.
- `{{env.PGPASSWORD}}` MUST be passed via env var, NOT via `--password` or
  inline `postgresql://user:pass@host`.
- `{{env.POLARDB_PG_NEW_PASSWORD}}` for `ResetAccountPassword` / `CreateAccount`.
- **`VACUUM FULL` locks the table for the duration of the operation** —
  on a large table, this can be hours. Reject or require maintenance
  window.
- **`ALTER SYSTEM SET` is durable cluster-wide** (persists across
  restarts). BEFORE issuing, query the current value via
  `SHOW <setting>` and record in `original_value_backup`. AFTER the
  user's debugging is done, suggest the user revert.
- `REINDEX` / `CLUSTER` lock the affected table. Production maintenance
  window required.
- Inherits canonical PolarDB rules: `DeleteDBCluster` requires final
  backup, `Delete`/`Update` without `WHERE` → Safety = 0, etc.
```

## Critic (excerpt)

```text
You are the Critic in a GCL for Alibaba Cloud PolarDB PostgreSQL. Read-only.

# Checks
- Apply canonical PolarDB checks (DeleteDBCluster backup, endpoint
  type, WHERE-clause, etc.).
- ADD PG-specific regexes:
  - `^vacuum\s+full\b` → DESTRUCTIVE-LIMITED (table lock)
  - `^alter\s+system\s+set\b` → CONFIG-MUTATION (require original_value_backup)
  - `^reindex\b` / `^cluster\b` → DESTRUCTIVE-LIMITED
  - `^drop\s+schema\b` → DESTRUCTIVE-MASS
- Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
- Suggestions ≤ 3, concrete.
```

## Anti-Patterns (PG additions)
- ❌ `VACUUM FULL` on prod table
- ❌ `ALTER SYSTEM SET` without original_value_backup
- ❌ `REINDEX` / `CLUSTER` on prod without maintenance window

## Changelog
1.0.0 | 2026-06-04 | PolarDB PostgreSQL GCL prompt templates (Phase 1, twelfth skill).
