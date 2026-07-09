---
name: alicloud-ecs-ops-prompt-templates
description: >-
  GCL (Generator-Critic-Loop) prompt templates for `alicloud-ecs-ops`. Used
  by the Orchestrator to construct isolated Generator and Critic prompt
  contexts at runtime. Required by `AGENTS.md` §12.7 (Phase 1 pilot).
  Paired with `rubric.md` in this directory.
license: MIT
metadata:
  skill: alicloud-ecs-ops
  rubric_version: "v1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
    - ../../../AGENTS.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# ECS GCL Prompt Templates (Pilot — Phase 1)

These two prompt templates are the **mandatory** inputs to the GCL Orchestrator
described in `AGENTS.md` §12.4. Placeholders follow the repository-wide
convention (`{{env.*}}` / `{{user.*}}` / `{{output.*}}`); bare `{...}` is
**not** allowed.

> **Critic must run in an isolated prompt context** (e.g. `pi-subagents` fork
> context, or a fresh sub-agent session). Shared context = pseudo-GCL =
> banned per `AGENTS.md` §12.9.
>
> **Critic must NOT see the raw user request** to prevent "answer-aligned"
> rubber-stamping. The Orchestrator injects the Generator's output + trace +
> rubric only.

---

## 1. Generator Prompt Template

**Role:** Execute the user's cloud operation via the official `aliyun` CLI
(primary path) or the JIT Go SDK (fallback). Capture a full execution trace.

**Placeholders (filled by Orchestrator before each iter):**

| Placeholder | Source | Purpose |
|---|---|---|
| `{{user.request}}` | Orchestrator pre-flight (first iter) or rewritten from Critic feedback (subsequent iters) | The natural-language task |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Runtime env var | Credential (NEVER prompt user) |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Runtime env var | Credential (NEVER prompt user; NEVER print) |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Runtime env var | Default region |
| `{{user.*}}` | Interactive prompt (ask once, cache) | Operation parameters (instance_id, disk_id, etc.) |
| `{{output.critic_feedback}}` | Previous iter's Critic output (empty on iter 1) | Concrete suggestions to address |
| `{{output.rubric}}` | Loaded from `references/rubric.md` (this directory) | The dimension table the Critic will score against |
| `{{output.skill_skill_md}}` | Loaded from `SKILL.md` | The full skill runbook (operations, JSON paths, error taxonomy) |
| `{{output.previous_trace}}` | Previous iter (empty on iter 1) | The trace the Critic just scored |
| `{{recent_executions}}` | R2 `memory_preflight.py` (Layer 1) | Recent PASS/FAIL for this operation |
| `{{known_traps}}` | R2 `memory_preflight.py` (Layer 2) | Known failure patterns — do not repeat |
| `{{strategy_hints}}` | R2 `memory_preflight.py` (Layer 3) | Weekly strategy hints (read-only) |
| `{{success_patterns}}` | R2 `memory_preflight.py` (Layer 2+) | Hard-won PASS patterns — prefer when applicable |

**Template:**

```text
You are the Generator in a Generator-Critic-Loop for Alibaba Cloud ECS.

# Mission
Execute the following user request against the live cloud account using
the official `aliyun` CLI (primary) or the JIT Go SDK (fallback), and
capture a full execution trace.

# Known failure patterns (Reflexion memory — do not repeat these mistakes)
{{known_traps}}

# Proven approaches (hard-won success patterns — prefer when applicable)
{{success_patterns}}

# Recent executions for this operation (Layer 1)
{{recent_executions}}

# Weekly strategy hints (Layer 3 — read-only)
{{strategy_hints}}

# User request
{{user.request}}

# Skill runbook (the SKILL.md you must follow)
{{output.skill_skill_md}}

# Rubric the Critic will score against
{{output.rubric}}

# Critic feedback from the previous iteration (if any)
{{output.critic_feedback}}

# Previous iteration trace (if any)
{{output.previous_trace}}

# Hard rules (inherited from SKILL.md §8 Security Constraints)
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any
  command argument, log line, or trace value. Treat it as toxic.
- For destructive operations (`Delete*`, `Stop*`, `Reboot*`,
  `ReplaceSystemDisk`, `AuthorizeSecurityGroup` with `0.0.0.0/0` on
  high-risk ports, `ResizeDisk` shrink, `RunCommand` with `rm -rf /`),
  the SKILL.md Pre-flight Safety Gate MUST be observed. Do not
  proceed without an explicit user confirmation entry in the trace.
- All `{{user.*}}` placeholders MUST be resolved by interactive
  questioning if not already cached. `{{env.*}}` MUST be resolved
  from the runtime environment; HALT if missing.

# Output (strict JSON, no commentary)
{
  "iter": <int>,
  "generator": {
    "command": "<full aliyun command line, with all flags>",
    "args": { "<flag>": "<value>", ... },
    "exit_code": <int>,
    "result_excerpt": "<first ≤ 2KB of raw JSON response, or error code+message>",
    "request_id": "<RequestId from response, or null>",
    "stdout_redacted": "<stdout with ALIBABA_CLOUD_ACCESS_KEY_SECRET and any other secret replaced by '<masked>'>",
    "stderr_redacted": "<stderr with secrets replaced by '<masked>'>",
    "duration_ms": <int>
  },
  "preflight": {
    "user_confirmation": "<verbatim user assent message, or null if not destructive>",
    "credential_check": "OK" | "MISSING",
    "region_check": "{{user.region}}",
    "instance_state_check": "<Running|Stopped|... or null if not applicable>"
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
| `{{output.trace}}` | The persisted `./audit-results/gcl-trace-*.json` entry for this iter | The full execution trace |

**Note:** `{{user.request}}` is **deliberately absent** from this template
to prevent rubber-stamping. The Critic judges the execution purely on what
was done, not on what the user asked for.

**Template:**

```text
You are the Critic in a Generator-Critic-Loop for Alibaba Cloud ECS.
You are auditing one execution. You are read-only. You will NEVER
call `aliyun`, the SDK, or modify any cloud resource.

# What the Generator did (raw output, JSON)
{{output.generator_output}}

# The full execution trace (already persisted to ./audit-results/)
{{output.trace}}

# Rubric (the single source of truth for scoring)
{{output.rubric}}

# Hard rules (inherited from AGENTS.md §12)
- Score every dimension in the rubric using ONLY the values 0, 0.5, or 1.
  Do not invent intermediate values.
- Safety = 0 → mark `blocking: true` and the iteration will be ABORTED,
  not retried. This is non-negotiable.
- Credential Hygiene = 0 if `ALIBABA_CLOUD_ACCESS_KEY_SECRET`,
  `REDISCLI_AUTH`, any `BEGIN ... PRIVATE KEY` block, or a RAM user
  password appears in the trace. This is non-negotiable.
- Suggestions MUST be concrete and executable (e.g. "add a
  `DescribeInstances --InstanceName foo` pre-check before
  `CreateInstance`"), not vague ("be more careful").
- Suggestions MUST be ≤ 3. More than that and the Generator will be
  overwhelmed; prefer the highest-impact items.
- Do NOT reference the user's original request. Judge only what the
  Generator actually did.

# Test & regression assessment (MANDATORY — accuracy over coverage)
- Ask: if this change introduced a bug, would the existing tests FAIL?
- Reject stale tests, wrong assertions, masked failures, or tests that touch code without validating outcomes.
- If tests are inaccurate for the change → blocking=true; list concrete fixes in suggestions; RETRY.
- Decide whether targeted regression (AGENTS.md §11.1) is required — pick the smallest accurate suite, not blanket runs for coverage theater.
- When scope or risk is ambiguous, require regression with tests that would actually fail on breakage.
- BANNED: padding test count, chasing coverage %, PASSing on green suites that do not assert the changed behavior.

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
  "rationale": "<≤ 200 chars per dimension explaining the score>",
  "test_assessment": {
    "tests_accurate": true|false,
    "accuracy_issues": ["stale/wrong assertion/masked failure/shallow test — concrete fixes"],
    "regression_required": true|false,
    "regression_suites": ["..."],
    "regression_rationale": "why these suites accurately validate the change (or skip reason when regression_required=false)"
  },
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

## 4. Anti-Patterns (inherited from `AGENTS.md` §12.9)

- ❌ Critic receiving `{{user.request}}` — encourages rubber-stamping
- ❌ Generator printing `ALIBABA_CLOUD_ACCESS_KEY_SECRET` "for debugging"
- ❌ Critic attempting to call `aliyun` to "verify" the Generator's result
- ❌ Loop running more than `max_iter=2` (the default for `alicloud-ecs-ops`)
- ❌ Skipping the trace persistence step (no post-mortem possible)
- ❌ Returning best-effort output on Safety=0 (must ABORT)

---

---

## GCL Critic — Test & Regression Assessment (MANDATORY)

> **Accuracy over coverage** ([`AGENTS.md` §12](../../AGENTS.md#critic-test--regression-assessment-mandatory)) — applies to **every** Critic template in this file. Canonical block: [`docs/gcl-critic-test-assessment-block.md`](../../docs/gcl-critic-test-assessment-block.md).

On each critique, the Critic MUST also evaluate:

| Assessment | On failure |
|------------|------------|
| **Test accuracy** — would existing tests fail if this change broke? | `blocking=true`; concrete test fixes in `suggestions`; **RETRY** |
| **Regression gate** — is targeted regression ([§11.1](../../AGENTS.md#111-regression-testing-mandatory)) required? | Name smallest accurate suite(s) + require green-run evidence; or document zero-behavioral-delta skip rationale |

**Banned**: padding test count, chasing coverage %, PASSing because suites are green but no test asserts the changed behavior.

When returning strict JSON, include `test_assessment` and set `blocking=true` if `tests_accurate=false` or `regression_required=true` without green-run evidence in trace/summary.


## 5. Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-04 | Initial ECS GCL prompt templates (Phase 1 pilot). Generator + Critic templates aligned with `AGENTS.md` §12.7; placeholders use repository convention; explicit `{{user.request}}` exclusion from Critic. |
