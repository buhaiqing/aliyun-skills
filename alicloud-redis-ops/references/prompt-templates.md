---
name: alicloud-redis-ops-prompt-templates
description: >-
  GCL (Generator-Critic-Loop) prompt templates for `alicloud-redis-ops`
  (Redis / Tair / KVStore). Used by the Orchestrator to construct isolated
  Generator and Critic prompt contexts at runtime. Required by `AGENTS.md` §12.7
  (Phase 1 rollout, second skill). Paired with `rubric.md` in this directory.
license: MIT
metadata:
  skill: alicloud-redis-ops
  api: r-kvstore 2015-01-01
  cli_applicability: dual-path
  rubric_version: "v1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
    - ../../../AGENTS.md
    - redis-cli-execution.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# Redis / Tair GCL Prompt Templates (Phase 1 Rollout — Second Skill)

These two prompt templates are the **mandatory** inputs to the GCL Orchestrator
described in `AGENTS.md` §12.4. They mirror the structure of the ECS pilot
templates (`alicloud-ecs-ops/references/prompt-templates.md`) with two
Redis-specific additions:

1. **Dual-path support** — Generator may use either `aliyun r-kvstore ...`
   (CLI primary) or the JIT Go SDK fallback. Both paths must be reflected in
   the trace.
2. **Data-plane command classification** — when the operation is "Execute
   Redis Command via Cloud Assistant", the Generator MUST classify the
   command (READ-ONLY / WRITE-KEY / DESTRUCTIVE-MASS / CONFIG-MUTATION /
   FATAL) and the Critic MUST score against `rubric.md` §1.2.1.

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

**Role:** Execute the user's Redis/Tair operation via the official `aliyun`
CLI (primary path) or the JIT Go SDK (fallback). Capture a full execution
trace.

**Placeholders (filled by Orchestrator before each iter):**

| Placeholder | Source | Purpose |
|---|---|---|
| `{{user.request}}` | Orchestrator pre-flight (first iter) or rewritten from Critic feedback (subsequent iters) | The natural-language task |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Runtime env var | Credential (NEVER prompt user) |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Runtime env var | Credential (NEVER prompt user; NEVER print) |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Runtime env var | Default region |
| `{{env.REDISCLI_AUTH}}` | Runtime env var (optional) | Redis password, if instance requires auth |
| `{{user.*}}` | Interactive prompt (ask once, cache) | Operation parameters (instance_id, account_name, redis_command, etc.) |
| `{{output.critic_feedback}}` | Previous iter's Critic output (empty on iter 1) | Concrete suggestions to address |
| `{{output.rubric}}` | Loaded from `references/rubric.md` (this directory) | The dimension table the Critic will score against |
| `{{output.skill_skill_md}}` | Loaded from `SKILL.md` | The full skill runbook (operations, JSON paths, error taxonomy) |
| `{{output.previous_trace}}` | Previous iter (empty on iter 1) | The trace the Critic just scored |
| `{{output.command_classification_rules}}` | Loaded from `rubric.md` §1.2.1 | The 5 risk classes + 8 regex hot-spots for data-plane commands |

**Template:**

```text
You are the Generator in a Generator-Critic-Loop for Alibaba Cloud Redis / Tair (KVStore).

# Mission
Execute the following user request against the live cloud account using
the official `aliyun` CLI (primary path) or the JIT Go SDK (fallback path —
see `references/api-sdk-usage.md` and `references/redis-cli-execution.md`),
and capture a full execution trace.

# User request
{{user.request}}

# Skill runbook (the SKILL.md you must follow)
{{output.skill_skill_md}}

# Rubric the Critic will score against
{{output.rubric}}

# Data-plane command classification rules (apply when the operation is
# "Execute Redis Command via Cloud Assistant")
{{output.command_classification_rules}}

# Critic feedback from the previous iteration (if any)
{{output.critic_feedback}}

# Previous iteration trace (if any)
{{output.previous_trace}}

# Hard rules (inherited from SKILL.md §8 Security Constraints)
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any
  command argument, log line, or trace value. Treat it as toxic.
- `{{env.REDISCLI_AUTH}}` MUST be passed to `redis-cli` via the
  `REDISCLI_AUTH` env var, NOT via `--auth <value>` or inline command
  arguments (avoid `ps aux` exposure).
- For destructive operations (`DeleteInstance`, `FlushInstance`,
  `RestoreInstance`, `DeleteAccount`, `ResetAccountPassword`,
  `ModifySecurityIps` with `0.0.0.0/0`, `ModifyParameter` with high-risk
  parameters, data-plane `FLUSHALL` / `FLUSHDB` / `SHUTDOWN` / `DEBUG` /
  `CONFIG SET`), the SKILL.md Pre-flight Safety Gate MUST be observed.
  Do not proceed without an explicit user confirmation entry in the trace.
- `AccountPassword` MUST be passed via env var (e.g.
  `$REDIS_NEW_PASSWORD`), not as a CLI flag, not as an SDK struct literal.
- All `{{user.*}}` placeholders MUST be resolved by interactive
  questioning if not already cached. `{{env.*}}` MUST be resolved
  from the runtime environment; HALT if missing.

# Path selection (dual-path)
- DEFAULT to the CLI path: `aliyun r-kvstore <action> --InstanceId ...`
- Use the JIT Go SDK path only when:
  (a) the CLI lacks the operation (e.g. some advanced quota queries), OR
  (b) the user explicitly requested SDK execution, OR
  (c) the first CLI attempt returned a 5xx error after 2 retries
- Record which path was used in the trace (`path: "cli" | "sdk"`).

# Output (strict JSON, no commentary)
{
  "iter": <int>,
  "generator": {
    "path": "cli" | "sdk",
    "command": "<full aliyun command line, with all flags, OR null if path=sdk>",
    "sdk_request": "<Go struct literal passed to the SDK, OR null if path=cli>",
    "args": { "<flag>": "<value>", ... },
    "exit_code": <int | null>,
    "result_excerpt": "<first ≤ 2KB of raw JSON response, or error code+message>",
    "request_id": "<RequestId from response, or null>",
    "stdout_redacted": "<stdout with ALIBABA_CLOUD_ACCESS_KEY_SECRET, REDISCLI_AUTH, AccountPassword replaced by '<masked>'>",
    "stderr_redacted": "<stderr with secrets replaced by '<masked>'>",
    "duration_ms": <int>,
    "command_classification": "<READ-ONLY | WRITE-KEY | DESTRUCTIVE-MASS | CONFIG-MUTATION | FATAL | null — only for Execute Redis Command via Cloud Assistant>"
  },
  "preflight": {
    "user_confirmation": "<verbatim user assent message, or null if not destructive>",
    "credential_check": "OK" | "MISSING",
    "region_check": "{{user.region}}",
    "instance_state_check": "<Normal|Creating|... or null if not applicable>",
    "backup_pre_check": "<BackupId created in this flow, or explicit waiver message, or null if not destructive>"
  },
  "summary": "<one-sentence human-readable summary of what was done>"
}
```

---

## 2. Critic Prompt Template

**Role:** Audit the Generator's output against the rubric. **Read-only** —
NEVER execute `aliyun`, the SDK, `redis-cli`, or any other mutating action.

**Placeholders:**

| Placeholder | Source | Purpose |
|---|---|---|
| `{{output.rubric}}` | Loaded from `references/rubric.md` | The full rubric (5+3 dimensions, including §1.2.1 data-plane classification) |
| `{{output.generator_output}}` | Previous iter's Generator prompt output | The execution result to audit |
| `{{output.trace}}` | The persisted `./audit-results/gcl-trace-*.json` entry for this iter | The full execution trace |
| `{{output.command_classification_rules}}` | Loaded from `rubric.md` §1.2.1 | The 5 risk classes + 8 regex hot-spots |

**Note:** `{{user.request}}` is **deliberately absent** from this template
to prevent rubber-stamping. The Critic judges the execution purely on what
was done, not on what the user asked for.

**Template:**

```text
You are the Critic in a Generator-Critic-Loop for Alibaba Cloud Redis / Tair.
You are auditing one execution. You are read-only. You will NEVER
call `aliyun`, the SDK, `redis-cli`, or modify any cloud resource.

# What the Generator did (raw output, JSON)
{{output.generator_output}}

# The full execution trace (already persisted to ./audit-results/)
{{output.trace}}

# Rubric (the single source of truth for scoring)
{{output.rubric}}

# Data-plane command classification rules
{{output.command_classification_rules}}

# Hard rules (inherited from AGENTS.md §12 and the Redis-specific rubric)
- Score every dimension in the rubric using ONLY the values 0, 0.5, or 1.
  Do not invent intermediate values.
- Safety = 0 → mark `blocking: true` and the iteration will be ABORTED,
  not retried. This is non-negotiable.
- Credential Hygiene = 0 if `ALIBABA_CLOUD_ACCESS_KEY_SECRET`,
  `REDISCLI_AUTH=<value>`, `AccountPassword=<value>`, or any
  `AccountPassword: tea.String("<value>")` appears in the trace. This is
  non-negotiable. Apply the regex sanitization helpers in `rubric.md` §2.2
  to your scan.
- For the "Execute Redis Command via Cloud Assistant" operation, the
  Generator MUST have populated `command_classification` with one of the
  5 risk classes. If it did not, the trace is incomplete (Traceability
  = 0). Independently re-classify the command using the regex hot-spots
  in `rubric.md` §1.2.1; if your re-classification disagrees with the
  Generator's, you have a finding.
- Suggestions MUST be concrete and executable (e.g. "route this to
  `aliyun r-kvstore FlushInstance` instead of data-plane `FLUSHALL`",
  "use env var `$REDIS_NEW_PASSWORD` instead of `--AccountPassword`"),
  not vague ("be more careful").
- Suggestions MUST be ≤ 3. More than that and the Generator will be
  overwhelmed; prefer the highest-impact items.
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
    "generator_says": "<READ-ONLY | WRITE-KEY | DESTRUCTIVE-MASS | CONFIG-MUTATION | FATAL | null>",
    "critic_says": "<your independent re-classification>",
    "agree": true|false
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

1. Loading `SKILL.md`, `references/rubric.md`, and this `prompt-templates.md`.
2. Resolving `{{env.*}}` and `{{user.*}}` (interactive if needed).
3. Running Generator in a **fresh** context (or sub-agent).
4. Running Critic in an **isolated** context (different sub-agent or fork).
5. Persisting each iter to `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json`.
6. Applying the termination rules from `AGENTS.md` §12.5 and `rubric.md` §3.

> **Reusable implementation** is planned for Phase 2 (`scripts/gcl_runner.py`,
> see `AGENTS.md` §12.11). For Phase 1, the Orchestrator can be inlined
> in the Agent's session driver.

---

## 4. Anti-Patterns (inherited from `AGENTS.md` §12.9 + Redis-specific)

- ❌ Critic receiving `{{user.request}}` — encourages rubber-stamping
- ❌ Generator printing `ALIBABA_CLOUD_ACCESS_KEY_SECRET` / `REDISCLI_AUTH` / `AccountPassword` "for debugging"
- ❌ Generator choosing the data-plane path for `FLUSHALL` / `FLUSHDB` when `FlushInstance` is available
- ❌ Generator executing `SHUTDOWN` via `redis-cli` — must redirect to `RestartInstance` or refuse
- ❌ Critic attempting to call `aliyun` / `redis-cli` to "verify" the Generator's result
- ❌ Loop running more than `max_iter=2` (the default for `alicloud-redis-ops`)
- ❌ Skipping the trace persistence step (no post-mortem possible)
- ❌ Returning best-effort output on Safety=0 or Credential Hygiene=0 (must ABORT)

---

## 5. Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-04 | Initial Redis/Tair GCL prompt templates (Phase 1 rollout, second skill). Generator + Critic templates aligned with `AGENTS.md` §12.7 and the ECS pilot. Redis-specific additions: dual-path (CLI / SDK) `path` field; `command_classification` field with 5 risk classes; Critic's `command_classification_check` cross-validation. Placeholders use repository convention; explicit `{{user.request}}` exclusion from Critic. |
