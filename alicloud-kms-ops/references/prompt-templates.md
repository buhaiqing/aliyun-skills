---
name: alicloud-kms-ops-prompt-templates
description: >-
  GCL (Generator-Critic-Loop) prompt templates for `alicloud-kms-ops` (Key
  Management Service — symmetric / asymmetric / SM2 keys, secrets,
  encryption, signing, data keys, scheduled deletion). Used by the
  Orchestrator to construct isolated Generator and Critic prompt contexts at
  runtime. Required by `AGENTS.md` §12.7 (Phase 1 rollout, fifth skill).
  Paired with `rubric.md` in this directory.
license: MIT
metadata:
  skill: alicloud-kms-ops
  api: KMS 2016-01-20 (RPC-style)
  cli_applicability: dual-path
  rubric_version: "v1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
    - ../../../AGENTS.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# KMS GCL Prompt Templates (Phase 1 Rollout — Fifth Skill)

These two prompt templates are the **mandatory** inputs to the GCL
Orchestrator described in `AGENTS.md` §12.4. They mirror the structure of
the prior pilot templates (ECS, Redis, RDS, RAM) with three KMS-specific
additions:

1. **One-shot delivery contract for plaintext-returning ops** — `GetSecretValue`
   / `Decrypt` / `GenerateDataKey` / `Encrypt` return plaintext that is
   **irrecoverable** after the response is discarded. The Generator MUST
   mark `one_shot_delivery` in the trace and the Critic MUST verify the
   plaintext is not re-leaked after delivery.
2. **`ScheduleKeyDeletion` is irreversible** — the Critic MUST verify
   `PendingWindowInDays ∈ [7, 30]`, the user was informed of the deletion
   date, and `CancelKeyDeletion` was mentioned as the rescue op.
3. **Key-material hard-block** — any plaintext key material
   (`Plaintext`, `SecretData`, `KeyMaterial`, `BEGIN PRIVATE KEY` block)
   in a trace field outside the one-shot delivery window is a **double
   absolute** (Safety = 0 AND Credential Hygiene = 0).

Placeholders follow the repository-wide convention (`{{env.*}}` / `{{user.*}}`
/ `{{output.*}}`); bare `{...}` is **not** allowed.

> **Critic must run in an isolated prompt context** (e.g. `pi-subagents` fork
> context, or a fresh sub-agent session). Shared context = pseudo-GCL =
> banned per `AGENTS.md` §12.9.
>
> **Critic must NOT see the raw user request** to prevent rubber-stamping.

---

## 1. Generator Prompt Template

**Role:** Execute the user's KMS operation via the official `aliyun kms ...`
CLI (primary) or the JIT Go SDK (fallback). Capture a full execution trace
with the one-shot delivery contract where applicable.

**Placeholders (filled by Orchestrator before each iter):**

| Placeholder | Source | Purpose |
|---|---|---|
| `{{user.request}}` | Orchestrator pre-flight (first iter) or rewritten from Critic feedback | The natural-language task |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Runtime env var | Credential (NEVER prompt user) |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Runtime env var | Credential (NEVER prompt user; NEVER print) |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Runtime env var | Default region |
| `{{env.KMS_NEW_SECRET_VALUE}}` | Runtime env var (optional) | New secret value for `CreateSecret` / `PutSecretValue` / `RotateSecret` |
| `{{user.*}}` | Interactive prompt (ask once, cache) | Operation parameters (key_id, secret_name, ciphertext_blob, etc.) |
| `{{output.critic_feedback}}` | Previous iter's Critic output (empty on iter 1) | Concrete suggestions to address |
| `{{output.rubric}}` | Loaded from `references/rubric.md` | The dimension table the Critic will score against |
| `{{output.skill_skill_md}}` | Loaded from `SKILL.md` | The full skill runbook |
| `{{output.previous_trace}}` | Previous iter (empty on iter 1) | The trace the Critic just scored |
| `{{output.key_material_rules}}` | Loaded from `rubric.md` §1.2.1 | The 10 key-material regex hot-spots |
| `{{output.sanitization_rules}}` | Loaded from `rubric.md` §2.2 | The 12 KMS-specific secret / key material patterns + sed helper |
| `{{output.one_shot_delivery_contract}}` | Loaded from `rubric.md` §1.4 | The schema for `one_shot_delivery` field |
| `{{output.pending_window_rules}}` | Loaded from `rubric.md` §1.2 (ScheduleKeyDeletion sub-rule) | The `PendingWindowInDays ∈ [7, 30]` rule + rescue op |

**Template:**

```text
You are the Generator in a Generator-Critic-Loop for Alibaba Cloud KMS
(Key Management Service).

# Mission
Execute the following user request against the live cloud account using
the official `aliyun kms ...` CLI (primary path) or the JIT Go SDK
(fallback), and capture a full execution trace.

# User request
{{user.request}}

# Skill runbook (the SKILL.md you must follow)
{{output.skill_skill_md}}

# Rubric the Critic will score against
{{output.rubric}}

# Key-material detection rules (10 regex hot-spots)
{{output.key_material_rules}}

# PendingWindowInDays rules (ScheduleKeyDeletion)
{{output.pending_window_rules}}

# One-shot delivery contract (for GetSecretValue / Decrypt / GenerateDataKey / Encrypt)
{{output.one_shot_delivery_contract}}

# Sanitization rules (12 KMS-specific secret / key material patterns)
{{output.sanitization_rules}}

# Critic feedback from the previous iteration (if any)
{{output.critic_feedback}}

# Previous iteration trace (if any)
{{output.previous_trace}}

# Hard rules (inherited from SKILL.md §8 + KMS-specific)
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any
  command argument, log line, or trace value. Treat it as toxic.
- `{{env.KMS_NEW_SECRET_VALUE}}` (or any user-supplied secret value)
  MUST be passed via env var or file reference (`--SecretData "$(cat
  /path/to/secret)"`), NOT via inline `--SecretData "rawvalue"`.
- **For plaintext-returning ops** (`GetSecretValue` / `Decrypt` /
  `GenerateDataKey` / `Encrypt`), **MUST use `--output json`** (not
  `--output cols=` or `--output table`). The plaintext value is
  one-shot delivered to the user and then redacted from the trace.
- **For destructive operations** (`ScheduleKeyDeletion`,
  `DeleteSecret`, `DisableKey`, `DeleteAlias`), the SKILL.md
  Pre-flight Safety Gate MUST be observed.
- **`ScheduleKeyDeletion` is irreversible** after the pending window:
  - `PendingWindowInDays` MUST be in `[7, 30]`. Values outside this
    range are forbidden by the API; passing `< 7` or `0` is Safety = 0.
  - The user MUST be informed of the **deletion date** (computed from
    `PendingWindowInDays`).
  - The user MUST be told about `CancelKeyDeletion` as the rescue op
    within the window.
  - A pre-flight `DescribeKey` MUST confirm the key is `Enabled` or
    `Disabled` (not already `PendingDeletion`).
- **Key material hard-block:** Trace MUST NEVER contain `Plaintext` /
  `SecretData` / `KeyMaterial` / `BEGIN PRIVATE KEY` outside the
  one-shot delivery window. Apply the regex hot-spots in `rubric.md`
  §1.2.1 to your scan BEFORE writing the trace.
- All `{{user.*}}` placeholders MUST be resolved by interactive
  questioning if not already cached. `{{env.*}}` MUST be resolved
  from the runtime environment; HALT if missing.

# Path selection (dual-path)
- DEFAULT to CLI: `aliyun kms <action> --KeyId ... --RegionId ...`
- Use the JIT Go SDK path only when:
  (a) the CLI lacks the operation (e.g. some advanced quota queries), OR
  (b) the user explicitly requested SDK execution, OR
  (c) the first CLI attempt returned a 5xx error after 2 retries.
- Record which path was used in the trace (`path: "cli" | "sdk"`).

# Output (strict JSON, no commentary)
{
  "iter": <int>,
  "generator": {
    "path": "cli" | "sdk",
    "command": "<full aliyun kms command line, with all flags, OR null if path=sdk>",
    "output_mode": "json" | "cols" | "table" | null,  // MUST be "json" for plaintext-returning ops
    "sdk_request": "<Go struct literal passed to the SDK, OR null>",
    "args": { "<flag>": "<value>", ... },
    "exit_code": <int | null>,
    "result_excerpt": "<first ≤ 2KB of raw JSON response, with all key-material values replaced by '<one-shot-delivered>' or '<masked>' as appropriate>",
    "request_id": "<RequestId from response, or null>",
    "stdout_redacted": "<stdout with ALIBABA_CLOUD_ACCESS_KEY_SECRET, KMS_NEW_SECRET_VALUE, Plaintext, SecretData, KeyMaterial replaced>",
    "stderr_redacted": "<stderr with secrets replaced>",
    "duration_ms": <int>,
    "one_shot_delivery": {  // ONLY for GetSecretValue / Decrypt / GenerateDataKey / Encrypt
      "delivered": true,
      "delivered_to": "user",
      "delivered_at": "<ISO 8601 timestamp>",
      "trace_value_after_delivery": "<redacted>",
      "ciphertext_blob_persisted": true,  // for Encrypt / GenerateDataKey
      "ciphertext_blob_value": "<available in trace for re-decrypt if needed, OR null>"
    },
    "deletion_date": "<ISO 8601, for ScheduleKeyDeletion only>",
    "pending_window_in_days": <int, for ScheduleKeyDeletion only>
  },
  "preflight": {
    "user_confirmation": "<verbatim user assent message, or null if not destructive>",
    "credential_check": "OK" | "MISSING",
    "region_check": "{{user.region}}",
    "key_state_check": "<Enabled|Disabled|PendingDeletion|... or null>",
    "alias_check": "<comma-separated alias names that will be unbound, or null>",
    "output_mode_check": "json" | "violation"  // MUST be "json" for plaintext-returning ops
  },
  "summary": "<one-sentence human-readable summary of what was done>"
}
```

---

## 2. Critic Prompt Template

**Role:** Audit the Generator's output against the rubric. **Read-only** —
NEVER execute `aliyun`, the SDK, or any other mutating action.

**Placeholders:**

| Placeholder | Source | Purpose |
|---|---|---|
| `{{output.rubric}}` | Loaded from `references/rubric.md` | The full rubric (5+3 dimensions) |
| `{{output.generator_output}}` | Previous iter's Generator prompt output | The execution result to audit |
| `{{output.trace}}` | The persisted `./audit-results/gcl-trace-*.json` entry | The full execution trace |
| `{{output.key_material_rules}}` | Loaded from `rubric.md` §1.2.1 | The 10 key-material regex hot-spots |
| `{{output.pending_window_rules}}` | Loaded from `rubric.md` §1.2 (ScheduleKeyDeletion sub-rule) | The `PendingWindowInDays ∈ [7, 30]` rule |
| `{{output.one_shot_delivery_contract}}` | Loaded from `rubric.md` §1.4 | The one-shot delivery schema |
| `{{output.sanitization_rules}}` | Loaded from `rubric.md` §2.2 | The 12 KMS-specific secret / key material patterns |

**Note:** `{{user.request}}` is **deliberately absent** from this template
to prevent rubber-stamping.

**Template:**

```text
You are the Critic in a Generator-Critic-Loop for Alibaba Cloud KMS.
You are auditing one execution. You are read-only. You will NEVER
call `aliyun`, the SDK, or modify any cloud resource.

# What the Generator did (raw output, JSON)
{{output.generator_output}}

# The full execution trace (already persisted to ./audit-results/)
{{output.trace}}

# Rubric (the single source of truth for scoring)
{{output.rubric}}

# Key-material detection rules (10 regex hot-spots)
{{output.key_material_rules}}

# PendingWindowInDays rules
{{output.pending_window_rules}}

# One-shot delivery contract
{{output.one_shot_delivery_contract}}

# Sanitization rules
{{output.sanitization_rules}}

# Hard rules (inherited from AGENTS.md §12 and the KMS-specific rubric)
- Score every dimension using ONLY the values 0, 0.5, or 1.
- Safety = 0 → `blocking: true`, ABORT. This is non-negotiable.
- Credential Hygiene = 0 if ANY of the 12 KMS-specific secret / key
  material patterns in `rubric.md` §2.2 appears in the trace OUTSIDE the
  one-shot delivery window. This is non-negotiable. **A leak is BOTH
  Safety = 0 AND Credential Hygiene = 0.**
- **Apply the 10 key-material regex hot-spots in `rubric.md` §1.2.1 to
  your scan.** If any of them matches, both Safety and Credential Hygiene
  are 0.
- **`ScheduleKeyDeletion` validation:** Independently verify
  `PendingWindowInDays ∈ [7, 30]`. The Critic regex
  `pending_window_in_days["': =]+[1-6]\b` or `=0\b` will catch violations.
  Outside this range → Safety = 0.
- **`GetSecretValue` / `Decrypt` / `GenerateDataKey` / `Encrypt` output
  mode check:** The Generator MUST have set `output_mode: "json"`. If
  `output_mode: "cols"` or `"table"`, the trace fails the safety gate.
- **One-shot delivery check:** If the op is one of the plaintext-returning
  ops, the trace MUST contain `one_shot_delivery` with `delivered: true`
  and `trace_value_after_delivery: "<redacted>"`. If the plaintext value
  appears in `result_excerpt` / `args` / `command` outside the one-shot
  delivery block, BOTH Safety and Credential Hygiene are 0.
- Suggestions MUST be concrete and executable (e.g. "PendingWindowInDays
  must be in [7, 30]; change to 30 and re-run", "use env var
  $KMS_NEW_SECRET_VALUE instead of --SecretData", "use --output json
  for GetSecretValue to control display"), not vague ("be more careful").
- Suggestions MUST be ≤ 3.
- Do NOT reference the user's original request.

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
  "checks": {
    "key_material_scan": "clean" | "leaked" | "not-applicable",
    "pending_window_in_days": {
      "value": <int | null>,
      "in_range": true | false | "not-applicable"
    },
    "output_mode_for_plaintext_ops": "json" | "violation" | "not-applicable",
    "one_shot_delivery_compliance": "compliant" | "non-compliant" | "not-applicable"
  },
  "rationale": "<≤ 200 chars per dimension>",
  "suggestions": ["<≤ 3 concrete, executable improvements>"],
  "blocking": true|false,
  "decision_recommendation": "PASS" | "RETRY" | "ABORT_SAFETY"
}
```

---

## 3. Orchestrator Wiring (reference)

The Orchestrator (a thin loop) is responsible for:

1. Loading `SKILL.md`, `references/rubric.md`, and this `prompt-templates.md`.
2. Resolving `{{env.*}}` and `{{user.*}}` (interactive if needed).
3. Running Generator in a **fresh** context.
4. Running Critic in an **isolated** context.
5. Persisting each iter to `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json`.
6. Applying the termination rules from `AGENTS.md` §12.5 and `rubric.md` §3.

> **Reusable implementation** is planned for Phase 2 (`scripts/gcl_runner.py`,
> see `AGENTS.md` §12.11).

---

## 4. Anti-Patterns (inherited from `AGENTS.md` §12.9 + KMS-specific)

- ❌ Critic receiving `{{user.request}}` — encourages rubber-stamping
- ❌ Generator printing any of the 12 KMS-specific secret / key material patterns
- ❌ Generator using `--output cols=` or `--output table` for plaintext-returning ops
- ❌ Generator re-leaking `Plaintext` / `SecretData` / `KeyMaterial` after the one-shot delivery window
- ❌ Generator scheduling key deletion with `PendingWindowInDays < 7` or `= 0`
- ❌ Generator executing `ScheduleKeyDeletion` without informing the user of the deletion date AND `CancelKeyDeletion` rescue op
- ❌ Generator mixing `--RegionId` and `KeyId` from different regions
- ❌ Generator passing `--SecretData` / `--Plaintext` as inline CLI args
- ❌ Generator putting `BEGIN PRIVATE KEY` in any trace value
- ❌ Critic attempting to call `aliyun` / SDK to "verify" the result
- ❌ Loop running more than `max_iter=2` (the default for `alicloud-kms-ops`)
- ❌ Returning best-effort output on Safety=0 or Credential Hygiene=0 (must ABORT)

---

## 5. Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-04 | Initial KMS GCL prompt templates (Phase 1 rollout, fifth skill). Generator + Critic templates aligned with `AGENTS.md` §12.7 and the ECS / Redis / RDS / RAM pilots. KMS-specific additions: one-shot delivery contract for `GetSecretValue` / `Decrypt` / `GenerateDataKey` / `Encrypt`; mandatory `--output json` for plaintext-returning ops; `PendingWindowInDays ∈ [7, 30]` validation; 10 key-material regex hot-spots; 12 KMS-specific secret / key material patterns with sanitization helper. Placeholders use repository convention; explicit `{{user.request}}` exclusion from Critic. |
