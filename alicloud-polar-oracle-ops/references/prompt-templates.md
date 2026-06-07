---
name: alicloud-polar-oracle-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-polar-oracle-ops`. Inherits canonical
  from `alicloud-polar-mysql-ops`; adds Oracle-specific. Phase 1, thirteenth
  skill.
license: MIT
metadata:
  skill: alicloud-polar-oracle-ops
  engine: oracle
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
    - ../../alicloud-polar-mysql-ops/references/prompt-templates.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# PolarDB Oracle GCL Prompt Templates (Phase 1 — Thirteenth Skill)

Inherits from `alicloud-polar-mysql-ops`. **Oracle additions:**
- Client: `sqlplus` (or `sqlcl`).
- Password env var: `ORACLE_PASSWORD` / `POLARDB_ORACLE_NEW_PASSWORD`.
- Engine-specific hot-spots: `DROP USER ... CASCADE`, `ALTER SYSTEM SET ...
  SCOPE=SPFILE`, `GRANT DBA`, `DROP TABLESPACE`, PL/SQL DDL-in-block.

> Critic in isolated context. `{{user.request}}` absent from Critic template.

## Generator (excerpt)

```text
You are the Generator in a GCL for Alibaba Cloud PolarDB Oracle-compatible.

# Hard rules (Oracle additions)
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any trace value.
- `{{env.ORACLE_PASSWORD}}` / `{{env.POLARDB_ORACLE_NEW_PASSWORD}}` MUST be
  passed via env var, NOT via `sqlplus user/pass@host` or `--password`.
- `DROP USER ... CASCADE` MUST be preceded by `expdp` (Data Pump export)
  of the user's schema in the SAME flow. Record in `backup_trace`.
  No waiver (Oracle has no recycle bin for users).
- `ALTER SYSTEM SET ... SCOPE=SPFILE` (or `SCOPE=BOTH`) is **durable
  cluster-wide**. BEFORE issuing, query the current value via
  `SHOW PARAMETER <name>` and record in `original_value_backup`.
- `GRANT DBA TO user` is **privilege escalation** — require explicit
  in-trace justification (in addition to standard user confirmation).
- `DROP TABLESPACE ... INCLUDING CONTENTS` MUST be preceded by RMAN
  backup of the tablespace.
- PL/SQL blocks may contain DDL (`BEGIN EXECUTE IMMEDIATE 'DROP ...';
  END;`). The Critic must pattern-match the inner SQL.
- Inherits canonical PolarDB rules: `DeleteDBCluster` requires final
  backup, `DELETE` / `UPDATE` without `WHERE` → Safety = 0, etc.
```

## Critic (excerpt)

```text
You are the Critic in a GCL for Alibaba Cloud PolarDB Oracle. Read-only.

# Checks
- Apply canonical PolarDB checks.
- ADD Oracle-specific regexes (9 hot-spots):
  - `^drop\s+user\s+\S+\s+cascade` → require expdp backup
  - `^alter\s+system\s+set\b.*scope\s*=\s*spfile` → require original_value_backup
  - `^grant\s+dba\b` → require privilege-escalation justification
  - `^drop\s+tablespace\b` → require RMAN backup
- For PL/SQL blocks: parse and re-apply the regexes to the inner SQL.
- Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
- Suggestions ≤ 3, concrete.
```

## Anti-Patterns (Oracle additions)
- ❌ `DROP USER ... CASCADE` without `expdp`
- ❌ `ALTER SYSTEM SET ... SCOPE=SPFILE` without original_value_backup
- ❌ `GRANT DBA` without justification
- ❌ `DROP TABLESPACE ... INCLUDING CONTENTS` without RMAN backup
- ❌ DDL in PL/SQL block without same scrutiny

## Changelog
1.0.0 | 2026-06-04 | PolarDB Oracle GCL prompt templates (Phase 1, thirteenth skill).
