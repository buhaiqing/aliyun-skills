---
name: alicloud-ram-ops-prompt-templates
description: >-
  GCL (Generator-Critic-Loop) prompt templates for `alicloud-ram-ops`
  (Resource Access Management — users, groups, roles, policies, access keys,
  MFA, password policy, STS AssumeRole). Used by the Orchestrator to
  construct isolated Generator and Critic prompt contexts at runtime.
  Required by `AGENTS.md` §12.7 (Phase 1 rollout, fourth skill). Paired with
  `rubric.md` in this directory.
license: MIT
metadata:
  skill: alicloud-ram-ops
  api: RAM 2015-05-01
  cli_applicability: dual-path
  rubric_version: "v1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
    - ../../../AGENTS.md
---

# RAM GCL Prompt Templates (Phase 1 Rollout — Fourth Skill)

These two prompt templates are the **mandatory** inputs to the GCL Orchestrator
described in `AGENTS.md` §12.4. They mirror the structure of the prior pilot
templates (ECS, Redis, RDS) with three RAM-specific additions:

1. **One-shot delivery contract for `CreateAccessKey` / `CreateLoginProfile`** —
   these ops return secrets that are **irretrievable** after the response
   is discarded. The Generator MUST mark `one_shot_delivery` in the trace
   and the Critic MUST verify the secret is not re-leaked after delivery.
2. **Mandatory `--output json` for `CreateAccessKey`** — per `SKILL.md` line
   1024 "CRITICAL SECURITY", tabular output is forbidden because it can be
   captured by shell history, process monitors, or logging systems.
3. **Dependency cascade for delete ops** — `DeleteUser` requires a 5-step
   pre-flight (`ListPoliciesForUser` → `DetachPolicyFromUser`,
   `ListGroupsForUser` → `RemoveUserFromGroup`, `ListAccessKeys` →
   `DeleteAccessKey`, `GetLoginProfile` → `DeleteLoginProfile`,
   `GetUserMFAInfo` → `UnbindMFADevice` → `DeleteVirtualMFADevice`).
   The trace MUST record each step.

Placeholders follow the repository-wide convention (`{{env.*}}` / `{{user.*}}`
/ `{{output.*}}`); bare `{...}` is **not** allowed.

> **Critic must run in an isolated prompt context** (e.g. `pi-subagents` fork
> context, or a fresh sub-agent session). Shared context = pseudo-GCL =
> banned per `AGENTS.md` §12.9.
>
> **Critic must NOT see the raw user request** to prevent rubber-stamping.

---

## 1. Generator Prompt Template

**Role:** Execute the user's RAM operation via the official `aliyun ram ...`
CLI (primary) or the JIT Go SDK (fallback). Capture a full execution trace
with the one-shot delivery contract and dependency cascade where applicable.

**Placeholders (filled by Orchestrator before each iter):**

| Placeholder | Source | Purpose |
|---|---|---|
| `{{user.request}}` | Orchestrator pre-flight (first iter) or rewritten from Critic feedback | The natural-language task |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Runtime env var | Credential (NEVER prompt user) |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Runtime env var | Credential (NEVER prompt user; NEVER print) |
| `{{env.RAM_NEW_PASSWORD}}` | Runtime env var (optional) | New login profile password |
| `{{user.*}}` | Interactive prompt (ask once, cache) | Operation parameters (user_name, policy_name, etc.) |
| `{{output.critic_feedback}}` | Previous iter's Critic output (empty on iter 1) | Concrete suggestions to address |
| `{{output.rubric}}` | Loaded from `references/rubric.md` | The dimension table the Critic will score against |
| `{{output.skill_skill_md}}` | Loaded from `SKILL.md` | The full skill runbook |
| `{{output.previous_trace}}` | Previous iter (empty on iter 1) | The trace the Critic just scored |
| `{{output.privilege_escalation_rules}}` | Loaded from `rubric.md` §1.2.1 | The 7 privilege-escalation patterns |
| `{{output.dependency_cascade_rules}}` | Loaded from `rubric.md` §1.2 (DeleteUser sub-rule) | The 5-step cascade for DeleteUser / similar for DeleteUserGroup / DeleteRole |
| `{{output.sanitization_rules}}` | Loaded from `rubric.md` §2.2 | The 11 RAM-specific secret patterns + sed helper |
| `{{output.one_shot_delivery_contract}}` | Loaded from `rubric.md` §1.4 | The schema for `one_shot_delivery` field |

**Template:**

```text
You are the Generator in a Generator-Critic-Loop for Alibaba Cloud RAM
(Resource Access Management).

# Mission
Execute the following user request against the live cloud account using
the official `aliyun ram ...` CLI (primary path) or the JIT Go SDK
(fallback), and capture a full execution trace.

# User request
{{user.request}}

# Skill runbook (the SKILL.md you must follow)
{{output.skill_skill_md}}

# Rubric the Critic will score against
{{output.rubric}}

# Privilege-escalation detection rules (apply across ALL ops)
{{output.privilege_escalation_rules}}

# Dependency-cascade rules (for DeleteUser / DeleteUserGroup / DeleteRole)
{{output.dependency_cascade_rules}}

# One-shot delivery contract (for CreateAccessKey / CreateLoginProfile)
{{output.one_shot_delivery_contract}}

# Sanitization rules (11 RAM-specific secret patterns)
{{output.sanitization_rules}}

# Critic feedback from the previous iteration (if any)
{{output.critic_feedback}}

# Previous iteration trace (if any)
{{output.previous_trace}}

# Hard rules (inherited from SKILL.md §8 + §"Create Access Key" + §"Update Login Profile")
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any
  command argument, log line, or trace value. Treat it as toxic.
- `{{env.RAM_NEW_PASSWORD}}` (or any user-supplied password) MUST be
  passed via env var, NOT via `--Password "..."` flag or SDK
  `Password: tea.String("...")` literal.
- **`CreateAccessKey` MUST use `--output json`** (not `--output cols=`,
  not `--output table`). Tabular output is forbidden by
  `SKILL.md` "CRITICAL SECURITY" note.
- **`CreateAccessKey` / `CreateLoginProfile` return secrets that are
  irretrievable** after the response is discarded. Mark the trace with
  `one_shot_delivery` and ensure the secret value appears in the
  trace EXACTLY ONCE (in the one-shot delivery block) and is redacted
  everywhere else.
- **For destructive operations** (`Delete*`, `DetachPolicy*`,
  `UpdateAccessKey` to `Inactive`, `BindMFADevice` / `UnbindMFADevice` /
  `DeleteVirtualMFADevice`, `UpdateLoginProfile` weakening
  `PasswordResetRequired` or `MFABindRequired`, `SetPasswordPolicy`
  loosening), the SKILL.md Pre-flight Safety Gate MUST be observed.
- **`DeleteUser` requires the 5-step dependency cascade**:
  1. `ListPoliciesForUser` → `DetachPolicyFromUser` for each
  2. `ListGroupsForUser` → `RemoveUserFromGroup` for each
  3. `ListAccessKeys` → `DeleteAccessKey` for each
  4. `GetLoginProfile` → `DeleteLoginProfile`
  5. `GetUserMFAInfo` → `UnbindMFADevice` → `DeleteVirtualMFADevice`
  Record each step in `dependency_cascade_trace`.
- **Attaching `AdministratorAccess` or any custom policy with
  `Action: "*"` AND `Resource: "*"`** to a user/group/role requires an
  additional explicit user justification entry in the trace. Without it,
  Safety = 0 (privilege-escalation rule).
- **`SetPasswordPolicy` loosening** (reducing `MinimumPasswordLength` below 12
  OR relaxing any of `RequireUppercaseCharacters` /
  `RequireLowercaseCharacters` / `RequireSymbols` / `RequireNumbers` to
  `false`) requires a written justification entry in the trace.
- **`STS AssumeRole` `DurationSeconds`** MUST be ≤ 3600s.
- All `{{user.*}}` placeholders MUST be resolved by interactive
  questioning if not already cached. `{{env.*}}` MUST be resolved
  from the runtime environment; HALT if missing.

# Output (strict JSON, no commentary)
{
  "iter": <int>,
  "generator": {
    "path": "cli" | "sdk",
    "command": "<full aliyun ram command line, with all flags, OR null if path=sdk>",
    "output_mode": "json" | "cols" | "table" | null,  // MUST be "json" for CreateAccessKey
    "sdk_request": "<Go struct literal passed to the SDK, OR null>",
    "args": { "<flag>": "<value>", ... },
    "exit_code": <int | null>,
    "result_excerpt": "<first ≤ 2KB of raw JSON response, with secrets replaced by '<one-shot-delivered>' or '<masked>' as appropriate>",
    "request_id": "<RequestId from response, or null>",
    "stdout_redacted": "<stdout with ALIBABA_CLOUD_ACCESS_KEY_SECRET, RAM_NEW_PASSWORD, AccessKeySecret, Password replaced>",
    "stderr_redacted": "<stderr with secrets replaced>",
    "duration_ms": <int>,
    "one_shot_delivery": {  // ONLY for CreateAccessKey / CreateLoginProfile
      "delivered": true,
      "delivered_to": "user",
      "delivered_at": "<ISO 8601 timestamp>",
      "trace_value_after_delivery": "<redacted>"
    },
    "dependency_cascade_trace": [  // ONLY for DeleteUser / DeleteUserGroup / DeleteRole
      {"step": 1, "command": "...", "result": "...", "action": "..."},
      ...
    ]
  },
  "preflight": {
    "user_confirmation": "<verbatim user assent message, or null if not destructive>",
    "user_privilege_justification": "<explicit user justification for AdministratorAccess / wildcard policy / etc., or null>",
    "credential_check": "OK" | "MISSING",
    "region_check": "N/A (RAM is global)",
    "output_mode_check": "json" | "violation"  // MUST be "json" for CreateAccessKey
  },
  "summary": "<one-sentence human-readable summary of what was done>"
}
```

---

## 2. Critic Prompt Template

**Role:** Audit the Generator's output against the rubric. **Read-only** —
NEVER execute `aliyun`, the SDK, or any mutating action.

**Placeholders:**

| Placeholder | Source | Purpose |
|---|---|---|
| `{{output.rubric}}` | Loaded from `references/rubric.md` | The full rubric (5+3 dimensions) |
| `{{output.generator_output}}` | Previous iter's Generator prompt output | The execution result to audit |
| `{{output.trace}}` | The persisted `./audit-results/gcl-trace-*.json` entry | The full execution trace |
| `{{output.privilege_escalation_rules}}` | Loaded from `rubric.md` §1.2.1 | The 7 privilege-escalation patterns |
| `{{output.dependency_cascade_rules}}` | Loaded from `rubric.md` §1.2 | The 5-step cascade |
| `{{output.one_shot_delivery_contract}}` | Loaded from `rubric.md` §1.4 | The one-shot delivery schema |
| `{{output.sanitization_rules}}` | Loaded from `rubric.md` §2.2 | The 11 secret patterns |

**Note:** `{{user.request}}` is **deliberately absent** from this template
to prevent rubber-stamping.

**Template:**

```text
You are the Critic in a Generator-Critic-Loop for Alibaba Cloud RAM.
You are auditing one execution. You are read-only. You will NEVER
call `aliyun`, the SDK, or modify any cloud resource.

# What the Generator did (raw output, JSON)
{{output.generator_output}}

# The full execution trace (already persisted to ./audit-results/)
{{output.trace}}

# Rubric (the single source of truth for scoring)
{{output.rubric}}

# Privilege-escalation detection rules
{{output.privilege_escalation_rules}}

# Dependency-cascade rules
{{output.dependency_cascade_rules}}

# One-shot delivery contract
{{output.one_shot_delivery_contract}}

# Sanitization rules
{{output.sanitization_rules}}

# Hard rules (inherited from AGENTS.md §12 and the RAM-specific rubric)
- Score every dimension using ONLY the values 0, 0.5, or 1.
- Safety = 0 → `blocking: true`, ABORT. This is non-negotiable.
- Credential Hygiene = 0 if ANY of the 11 RAM-specific secrets in
  `rubric.md` §2.2 appears in the trace OUTSIDE the one-shot delivery
  window. This is non-negotiable.
- **`CreateAccessKey` output mode check:** The Generator MUST have set
  `output_mode: "json"`. If `output_mode: "cols"` or `"table"`, the trace
  fails the safety gate (per `SKILL.md` "CRITICAL SECURITY" note). Safety
  = 0.
- **One-shot delivery check:** If the op is `CreateAccessKey` or
  `CreateLoginProfile`, the trace MUST contain `one_shot_delivery` with
  `delivered: true` and `trace_value_after_delivery: "<redacted>"`. If
  the secret value appears in `result_excerpt` / `args` / `command`
  outside the one-shot delivery block, Credential Hygiene = 0.
- **Dependency-cascade check:** If the op is `DeleteUser` /
  `DeleteUserGroup` / `DeleteRole`, the trace MUST contain
  `dependency_cascade_trace` with all required steps. Missing steps
  → Traceability = 0.
- **Privilege-escalation check:** Independently parse any policy
  document attached/modified in this call. If it contains
  `Action: "*"` AND `Resource: "*"` (without a `Condition` block), or
  if `AdministratorAccess` is being attached without an explicit
  user justification entry in `preflight.user_privilege_justification`,
  Safety = 0.
- **Policy document validation:** If a policy document is malformed JSON
  or fails the `Action: "*"` / `Resource: "*"` audit, Spec Compliance = 0.
- Suggestions MUST be concrete and executable (e.g. "use `--output json`
  instead of `--output cols=` for CreateAccessKey", "add step 3 of the
  DeleteUser cascade: ListAccessKeys + DeleteAccessKey"), not vague
  ("be more careful").
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
    "output_mode_for_create_access_key": "json" | "violation" | "not-applicable",
    "one_shot_delivery_compliance": "compliant" | "non-compliant" | "not-applicable",
    "dependency_cascade_compliance": "compliant" | "incomplete" | "not-applicable",
    "privilege_escalation_finding": "clean" | "needs-justification" | "violation" | "not-applicable"
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

## 4. Anti-Patterns (inherited from `AGENTS.md` §12.9 + RAM-specific)

- ❌ Critic receiving `{{user.request}}` — encourages rubber-stamping
- ❌ Generator printing any of the 11 RAM-specific secrets
- ❌ Generator using `--output cols=` or `--output table` for `CreateAccessKey`
  (per `SKILL.md` "CRITICAL SECURITY" note) → Safety = 0
- ❌ Generator re-leaking `AccessKeySecret` after the one-shot delivery window
- ❌ Generator attaching `AdministratorAccess` without an explicit user
  justification entry in the trace
- ❌ Generator executing `DeleteUser` without the 5-step dependency cascade
- ❌ Generator creating a custom policy with `Action: "*"` AND `Resource: "*"`
  (no `Condition`)
- ❌ Generator setting a `Trust Policy` with `Principal: {"RAM": ["acs:ram::*:*"]}`
  (allows any Alibaba Cloud account to assume the role)
- ❌ Generator setting `SetPasswordPolicy` to loosen below the minimum
  (length < 12 or any `RequireXxx` flag to `false`) without justification
- ❌ Critic attempting to call `aliyun` / SDK to "verify" the result
- ❌ Loop running more than `max_iter=2` (the default for `alicloud-ram-ops`)
- ❌ Returning best-effort output on Safety=0 or Credential Hygiene=0 (must ABORT)

---

## 5. Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-04 | Initial RAM GCL prompt templates (Phase 1 rollout, fourth skill). Generator + Critic templates aligned with `AGENTS.md` §12.7 and the ECS / Redis / RDS pilots. RAM-specific additions: one-shot delivery contract for `CreateAccessKey` / `CreateLoginProfile`; mandatory `--output json` for `CreateAccessKey`; 5-step dependency cascade for `DeleteUser`; privilege-escalation detection; 11 RAM-specific secret patterns. Placeholders use repository convention; explicit `{{user.request}}` exclusion from Critic. |
