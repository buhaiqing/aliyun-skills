---
name: alicloud-agentrun-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-agentrun-ops`. Phase 5, recommended.
license: MIT
metadata:
  skill: alicloud-agentrun-ops
  api: AgentRun 2025-09-10
  cli_applicability: sdk-only
  gcl_classification: recommended
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# AgentRun GCL Prompt Templates (Phase 5 — recommended)

## 1. Generator Prompt Template

| `{{recent_executions}}` | R2 `memory_preflight.py` (Layer 1) | Recent PASS/FAIL for this operation |
| `{{known_traps}}` | R2 `memory_preflight.py` (Layer 2) | Known failure patterns — do not repeat |
| `{{strategy_hints}}` | R2 `memory_preflight.py` (Layer 3) | Weekly strategy hints (read-only) |
| `{{success_patterns}}` | R2 `memory_preflight.py` (Layer 2+) | Hard-won PASS patterns — prefer when applicable |

```text
You are the Generator in a GCL for Alibaba Cloud AGENTRUN.

# Known failure patterns (Reflexion memory — do not repeat these mistakes)
{{known_traps}}

# Proven approaches (hard-won success patterns — prefer when applicable)
{{success_patterns}}

# Recent executions for this operation (Layer 1)
{{recent_executions}}

# Weekly strategy hints (Layer 3 — read-only)
{{strategy_hints}}

- `DeleteSandbox`: MUST check `Status` first. Running sandbox requires
  `PauseSandbox` first. Warn permanent state loss. Record backup of
  sandbox config (description, env vars).
- `DeleteTemplate`: MUST check dependent sandboxes via `ListSandboxes`
  or template metadata. Warn that existing sandboxes lose recreate ability.
- `ExecCommand`: block if command matches `rm -rf /`, `dd if=/dev/zero`,
  `mkfs`, `fdisk`, or `shutdown`. Record command in trace.
```
## Critic (excerpt)

```text
- `DeleteSandbox`: independently verify sandbox is absent via API.
  Check trace for Status check and waiver.
- `DeleteTemplate`: verify template is absent. Check trace for dependent
  sandbox check.
- `ExecCommand`: check command in trace for destructive patterns.
  `ExecCommand.*(rm\\s+-rf|dd\\s+if|mkfs|fdisk|shutdown)` → Safety = 0.
- Safety = 0 → ABORT.
# Test & regression assessment (MANDATORY — accuracy over coverage)
- Ask: if this change introduced a bug, would the existing tests FAIL?
- Reject stale tests, wrong assertions, masked failures, or tests that touch code without validating outcomes.
- If tests are inaccurate for the change → blocking=true; list concrete fixes in suggestions; RETRY.
- Decide whether targeted regression (AGENTS.md §11.1) is required — pick the smallest accurate suite, not blanket runs for coverage theater.
- When scope or risk is ambiguous, require regression with tests that would actually fail on breakage.
- BANNED: padding test count, chasing coverage %, PASSing on green suites that do not assert the changed behavior.

```

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


## Changelog
1.0.0 | 2026-06-04 | AgentRun GCL prompt templates (Phase 5, recommended).