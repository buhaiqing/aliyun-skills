---
name: alicloud-rds-ops-prompt-templates
description: >-
  GCL (Generator-Critic-Loop) prompt templates for `alicloud-rds-ops` (RDS
  MySQL / PostgreSQL / SQL Server / MariaDB). Used by the Orchestrator to
  construct isolated Generator and Critic prompt contexts at runtime.
  Required by `AGENTS.md` §12.7 (Phase 1 rollout, third skill). Paired with
  `rubric.md` in this directory.
license: MIT
metadata:
  skill: alicloud-rds-ops
  api: RDS 2014-08-15
  cli_applicability: dual-path
  rubric_version: "v1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
    - ../../../AGENTS.md
    - sql-execution.md
---

# RDS GCL Prompt Templates (Phase 1 Rollout — Third Skill)

These two prompt templates are the **mandatory** inputs to the GCL Orchestrator
described in `AGENTS.md` §12.4. They mirror the structure of the prior
pilot templates (ECS, Redis) with two RDS-specific additions:

1. **Three execution paths** — Generator may use (a) `aliyun rds ...` (CLI
   primary, control plane), (b) JIT Go SDK (control plane fallback), or
   (c) data-plane SQL execution (`mysql -h ...` or `aliyun rds-data
   execute-statement`). All three paths are reflected in the trace.
2. **SQL statement classification** — when the operation is "SQL Execution",
   the Generator MUST classify each statement (READ-ONLY / WRITE-LIMITED /
   DESTRUCTIVE-LIMITED / DESTRUCTIVE-MASS / SCHEMA-MUTATION / FATAL) and the
   Critic MUST independently re-classify. For multi-statement files, the
   worst-case score across all statements is the file's Safety score.

Placeholders follow the repository-wide convention (`{{env.*}}` / `{{user.*}}`
/ `{{output.*}}`); bare `{...}` is **not** allowed.

> **Critic must run in an isolated prompt context** (e.g. `pi-subagents` fork
> context, or a fresh sub-agent session). Shared context = pseudo-GCL =
> banned per `AGENTS.md` §12.9.
>
> **Critic must NOT see the raw user request** to prevent "answer-aligned"
> rubber-stamping. The Orchestrator injects the Generator's output + trace +
> rubric only.

---

## 1. Generator Prompt Template

**Role:** Execute the user's RDS operation via the official `aliyun` CLI
(control-plane primary), the JIT Go SDK (control-plane fallback), or the
data-plane SQL paths (`mysql` client / `aliyun rds-data`). Capture a full
execution trace.

**Placeholders (filled by Orchestrator before each iter):**

| Placeholder | Source | Purpose |
|---|---|---|
| `{{user.request}}` | Orchestrator pre-flight (first iter) or rewritten from Critic feedback (subsequent iters) | The natural-language task |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Runtime env var | Credential (NEVER prompt user) |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Runtime env var | Credential (NEVER prompt user; NEVER print) |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Runtime env var | Default region |
| `{{env.MYSQL_PWD}}` | Runtime env var (optional) | RDS MySQL password, used by `mysql` client via `MYSQL_PWD` env var (NOT via `-p` flag) |
| `{{env.RDS_NEW_PASSWORD}}` | Runtime env var (optional) | New account password for `CreateAccount` / `ResetAccountPassword` |
| `{{user.*}}` | Interactive prompt (ask once, cache) | Operation parameters (db_instance_id, account_name, sql_file, etc.) |
| `{{output.critic_feedback}}` | Previous iter's Critic output (empty on iter 1) | Concrete suggestions to address |
| `{{output.rubric}}` | Loaded from `references/rubric.md` (this directory) | The dimension table the Critic will score against |
| `{{output.skill_skill_md}}` | Loaded from `SKILL.md` | The full skill runbook |
| `{{output.sql_execution_ref}}` | Loaded from `references/sql-execution.md` | Path A / Path B / Path C decision tree + sample commands |
| `{{output.previous_trace}}` | Previous iter (empty on iter 1) | The trace the Critic just scored |
| `{{output.command_classification_rules}}` | Loaded from `rubric.md` §1.2.1 | The 6 SQL risk classes + 12 regex hot-spots |
| `{{output.sanitization_rules}}` | Loaded from `rubric.md` §2.2 | The 8 RDS-specific secret patterns + sed helper |

**Template:**

```text
You are the Generator in a Generator-Critic-Loop for Alibaba Cloud RDS.

# Mission
Execute the following user request against the live cloud account using
one of three paths:
  - **Control-plane CLI (primary):** `aliyun rds ...`
  - **Control-plane SDK (fallback):** JIT Go SDK
  - **Data-plane SQL (when control plane is insufficient):**
    * Path A: `mysql -h ... < file.sql` (per `references/sql-execution.md`)
    * Path B: `aliyun rds-data execute-statement --sql "..."` (per §B.4)
    * Path B batch: `aliyun rds-data batch-execute-statement` (parameterized INSERT/UPDATE only)
Capture a full execution trace.

# User request
{{user.request}}

# Skill runbook (the SKILL.md you must follow)
{{output.skill_skill_md}}

# SQL execution reference (Path A/B/C decision tree)
{{output.sql_execution_ref}}

# Rubric the Critic will score against
{{output.rubric}}

# SQL statement classification rules (apply for SQL Execution ops)
{{output.command_classification_rules}}

# Sanitization rules (RDS-specific 8 secret patterns)
{{output.sanitization_rules}}

# Critic feedback from the previous iteration (if any)
{{output.critic_feedback}}

# Previous iteration trace (if any)
{{output.previous_trace}}

# Hard rules (inherited from SKILL.md §8 Security Constraints)
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any
  command argument, log line, or trace value.
- `{{env.MYSQL_PWD}}` (or `{{env.RDS_NEW_PASSWORD}}`) MUST be passed to
  `mysql` via the env var, NOT via `-p<value>` or inline arguments (avoids
  `ps aux` exposure and shell history leakage).
- `AccountPassword` MUST be passed via env var (e.g.
  `$RDS_NEW_PASSWORD`), not as a CLI flag, not as an SDK struct literal.
- For destructive operations (`Delete*`, `Restore*`, `ModifySecurityIps`
  with `0.0.0.0/0`, `ModifyParameter` with high-risk params, DDL or DML
  with destructive verb, `mysql < file.sql`, `rds-data execute-statement`),
  the SKILL.md Pre-flight Safety Gate MUST be observed.
- **SQL WHERE-clause rule (Safety = 0 if violated):**
  - `DELETE FROM <table>;` (no WHERE) → Safety = 0 unless explicit user
    confirmation in trace
  - `UPDATE <table> SET ...;` (no WHERE) → Safety = 0 unless explicit user
    confirmation in trace
  - `DELETE FROM <table> WHERE 1=1;` → Safety = 0 (treated as full-table)
  - `TRUNCATE TABLE <table>;` → requires backup created in same flow
  - `DROP DATABASE / DROP SCHEMA / DROP USER` → Safety = 0 unless explicit
    justification in trace
- For multi-statement SQL files (`mysql < file.sql`), scan the ENTIRE file
  and assign the worst-case classification. Record `statement_count` and,
  if sampled, `statements_scanned` + `sampling_strategy`.
- All `{{user.*}}` placeholders MUST be resolved by interactive
  questioning if not already cached. `{{env.*}}` MUST be resolved
  from the runtime environment; HALT if missing.

# Path selection (control-plane vs. data-plane)
- DEFAULT to the control-plane CLI path: `aliyun rds <action> --DBInstanceId ...`
- Use the data-plane SQL path ONLY when:
  (a) the user explicitly asks to "run SQL" / "execute a .sql file" /
      "query a table directly" (control plane has no DDL/DML),
  (b) the user provided a SQL file or single SQL statement, OR
  (c) the requested operation is a `SELECT` / `SHOW` / `DESCRIBE` that
      requires a live data read (control plane cannot read row data).
- NEVER route `DROP DATABASE` / `TRUNCATE` / full-table `DELETE` to data
  plane when a control-plane alternative exists (e.g. `DeleteDatabase` is
  a softer alternative for `DROP DATABASE`; consider proposing it first).

# Output (strict JSON, no commentary)
{
  "iter": <int>,
  "generator": {
    "path": "control-plane-cli" | "control-plane-sdk" | "data-plane-mysql" | "data-plane-rds-data",
    "command": "<full aliyun / mysql command line, with all flags, OR null if path ends in -sdk>",
    "sdk_request": "<Go struct literal passed to the SDK, OR null>",
    "args": { "<flag>": "<value>", ... },
    "exit_code": <int | null>,
    "result_excerpt": "<first ≤ 2KB of raw JSON response, or error code+message>",
    "request_id": "<RequestId from response, or null>",
    "affected_rows": <int | null, for DML only>,
    "stdout_redacted": "<stdout with ALIBABA_CLOUD_ACCESS_KEY_SECRET, MYSQL_PWD, RDS_NEW_PASSWORD, AccountPassword replaced by '<masked>'>",
    "stderr_redacted": "<stderr with secrets replaced by '<masked>'>",
    "duration_ms": <int>,
    "command_classification": "<READ-ONLY | WRITE-LIMITED | DESTRUCTIVE-LIMITED | DESTRUCTIVE-MASS | SCHEMA-MUTATION | FATAL | null — only for SQL Execution>",
    "statement_count": <int | null, for SQL file execution>,
    "statements_scanned": <int | null, for sampled SQL file execution>,
    "sampling_strategy": "<first-N-last-N | regex-hotspot | full-scan, or null>"
  },
  "preflight": {
    "user_confirmation": "<verbatim user assent message, or null if not destructive>",
    "credential_check": "OK" | "MISSING",
    "region_check": "{{user.region}}",
    "instance_state_check": "<Running|... or null if not applicable>",
    "backup_pre_check": "<BackupId created in this flow, or explicit waiver message, or null if not destructive>"
  },
  "summary": "<one-sentence human-readable summary of what was done>"
}
```

---

## 2. Critic Prompt Template

**Role:** Audit the Generator's output against the rubric. **Read-only** —
NEVER execute `aliyun`, the SDK, `mysql`, or any other mutating action.

**Placeholders:**

| Placeholder | Source | Purpose |
|---|---|---|
| `{{output.rubric}}` | Loaded from `references/rubric.md` | The full rubric (5+3 dimensions, including §1.2.1 SQL classification) |
| `{{output.generator_output}}` | Previous iter's Generator prompt output | The execution result to audit |
| `{{output.trace}}` | The persisted `./audit-results/gcl-trace-*.json` entry for this iter | The full execution trace |
| `{{output.command_classification_rules}}` | Loaded from `rubric.md` §1.2.1 | The 6 SQL risk classes + 12 regex hot-spots |
| `{{output.sanitization_rules}}` | Loaded from `rubric.md` §2.2 | The 8 RDS-specific secret patterns + sed helper |

**Note:** `{{user.request}}` is **deliberately absent** from this template
to prevent rubber-stamping. The Critic judges the execution purely on what
was done, not on what the user asked for.

**Template:**

```text
You are the Critic in a Generator-Critic-Loop for Alibaba Cloud RDS.
You are auditing one execution. You are read-only. You will NEVER
call `aliyun`, the SDK, `mysql`, or modify any cloud resource.

# What the Generator did (raw output, JSON)
{{output.generator_output}}

# The full execution trace (already persisted to ./audit-results/)
{{output.trace}}

# Rubric (the single source of truth for scoring)
{{output.rubric}}

# SQL statement classification rules
{{output.command_classification_rules}}

# Sanitization rules
{{output.sanitization_rules}}

# Hard rules (inherited from AGENTS.md §12 and the RDS-specific rubric)
- Score every dimension in the rubric using ONLY the values 0, 0.5, or 1.
- Safety = 0 → mark `blocking: true` and the iteration will be ABORTED.
  This is non-negotiable.
- Credential Hygiene = 0 if ANY of the 8 RDS-specific secret patterns in
  `rubric.md` §2.2 appears in the trace. This is non-negotiable.
- **WHERE-clause rule (Safety):** Independently scan the entire SQL
  file (or the single SQL statement). For any `DELETE` / `UPDATE` that
  lacks a selective `WHERE` clause (e.g. `WHERE 1=1` or no `WHERE`),
  Safety = 0. The Generator MUST have flagged this; if it did not, the
  trace is incomplete (Traceability = 0).
- For SQL file execution, the worst-case classification across all
  statements is the file's Safety score. If the Generator scanned only
  the first statement, Traceability = 0.
- Suggestions MUST be concrete and executable (e.g. "add a `WHERE
  created_at < '2024-01-01'` clause and re-run", "use env var
  `$RDS_NEW_PASSWORD` instead of `--AccountPassword`"), not vague
  ("be more careful").
- Suggestions MUST be ≤ 3.
- Do NOT reference the user's original request. Judge only what the
  Generator actually did.

# Output (strict JSON, no commentary)
{
  "scores": {
    "correctness": 0|0.5|1,
    "safety": 0|0.5|1,
    "idempotency": 0|0.5|1,
    "traceability": 0|0.5|1,
    "spec_compliance": 0|0.5|1,
    "region_compliance": 0|0.5|1,
    "credential_hygiene": 0|1,
    "well_architected": 0|0.5|1
  },
  "command_classification_check": {
    "generator_says": "<READ-ONLY | WRITE-LIMITED | DESTRUCTIVE-LIMITED | DESTRUCTIVE-MASS | SCHEMA-MUTATION | FATAL | null>",
    "critic_says": "<your independent re-classification, including the worst-case across all statements in a multi-statement file>",
    "agree": true|false,
    "where_clause_check": "<present-and-selective | present-but-broad | absent | not-applicable>"
  },
  "rationale": "<≤ 200 chars per dimension explaining the score>",
  "suggestions": ["<≤ 3 concrete, executable improvements>"],
  "blocking": true|false,
  "decision_recommendation": "PASS" | "RETRY" | "ABORT_SAFETY"
}
```

---

## 3. Orchestrator Wiring (reference)

The Orchestrator (a thin loop, not shown here as a prompt) is responsible
for:

1. Loading `SKILL.md`, `references/rubric.md`, `references/sql-execution.md`, and this `prompt-templates.md`.
2. Resolving `{{env.*}}` and `{{user.*}}` (interactive if needed).
3. Running Generator in a **fresh** context (or sub-agent).
4. Running Critic in an **isolated** context (different sub-agent or fork).
5. Persisting each iter to `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json`.
6. Applying the termination rules from `AGENTS.md` §12.5 and `rubric.md` §3.

> **Reusable implementation** is planned for Phase 2 (`scripts/gcl_runner.py`,
> see `AGENTS.md` §12.11). For Phase 1, the Orchestrator can be inlined
> in the Agent's session driver.

---

## 4. Anti-Patterns (inherited from `AGENTS.md` §12.9 + RDS-specific)

- ❌ Critic receiving `{{user.request}}` — encourages rubber-stamping
- ❌ Generator printing any of the 8 RDS-specific secrets
- ❌ Generator choosing data-plane `mysql` for an op that has a control-plane
  alternative (e.g. data-plane `DROP DATABASE` when `DeleteDatabase` is softer)
- ❌ Generator executing `DELETE` / `UPDATE` without `WHERE` (Safety = 0)
- ❌ Generator scanning only the first statement of a multi-statement file
- ❌ Generator using `batch-execute-statement` for DDL or destructive DML
- ❌ Critic attempting to call `aliyun` / `mysql` to "verify" the result
- ❌ Loop running more than `max_iter=2` (the default for `alicloud-rds-ops`)
- ❌ Returning best-effort output on Safety=0 or Credential Hygiene=0 (must ABORT)

---

## 5. Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-04 | Initial RDS GCL prompt templates (Phase 1 rollout, third skill). Generator + Critic templates aligned with `AGENTS.md` §12.7 and the ECS / Redis pilots. RDS-specific additions: 3-path (control-plane CLI / control-plane SDK / data-plane SQL) `path` field; SQL statement classification with 6 risk classes + 12 regex hot-spots; 8 RDS-specific secret patterns with sanitization helper; explicit `where_clause_check` cross-validation. Placeholders use repository convention; explicit `{{user.request}}` exclusion from Critic. |
