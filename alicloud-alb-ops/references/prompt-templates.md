---
name: alicloud-alb-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-alb-ops` (ALB — instance lifecycle,
  listeners, server groups, forwarding rules, ACLs, health checks, security
  policies). Phase 1 rollout.
license: MIT
metadata:
  skill: alicloud-alb-ops
  api: ALB 2020-06-16
  cli_applicability: dual-path
  rubric_version: "1.0.0"
  last_updated: "2026-06-07"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# ALB GCL Prompt Templates (Phase 1 — First Rollout)

Inherits structure from `AGENTS.md` §12.7 and prior pilots. ALB-specific additions: **cascading delete** (`DeleteLoadBalancer` removes all listeners, rules, server group associations); **deletion protection check** mandatory before delete; **server group empty check** after removal (no healthy servers → 503).

> Critic in isolated context. `{{user.request}}` absent from Critic template.

## 1. Generator Prompt Template

| `{{recent_executions}}` | R2 `memory_preflight.py` (Layer 1) | Recent PASS/FAIL for this operation |
| `{{known_traps}}` | R2 `memory_preflight.py` (Layer 2) | Known failure patterns — do not repeat |
| `{{strategy_hints}}` | R2 `memory_preflight.py` (Layer 3) | Weekly strategy hints (read-only) |
| `{{success_patterns}}` | R2 `memory_preflight.py` (Layer 2+) | Hard-won PASS patterns — prefer when applicable |

```text
You are the Generator in a GCL for Alibaba Cloud ALB.

# Known failure patterns (Reflexion memory — do not repeat these mistakes)
{{known_traps}}

# Proven approaches (hard-won success patterns — prefer when applicable)
{{success_patterns}}

# Recent executions for this operation (Layer 1)
{{recent_executions}}

# Weekly strategy hints (Layer 3 — read-only)
{{strategy_hints}}

# Hard rules
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any trace value.
- `DeleteLoadBalancer`: must check `DeletionProtectionEnabled == false` first
  (use GetLoadBalancerAttribute). If enabled, HALT — user must disable.
- `DeleteLoadBalancer`: record cascade warning in trace (confirms user
  knows listeners, rules, server groups will be deleted).
- `RemoveServersFromServerGroup`: verify remaining healthy servers > 0
  AFTER removal (otherwise 503).
- `DeleteServerGroup`: verify NOT referenced by any listener/rule
  (use GetListenerAttribute + ListRules).
- `DeleteAcl`: verify NOT associated with any listener (use ListAclRelations).
- `DeleteSecurityPolicy`: verify NOT referenced by any HTTPS listener
  (use ListSecurityPolicyRelations).
- All `{{user.*}}` placeholders MUST be resolved interactively.
```
## Critic (excerpt)

```text
You are the Critic in a GCL for Alibaba Cloud ALB. Read-only.

# Checks
- For `DeleteLoadBalancer`: re-query `GetLoadBalancerAttribute`
  to verify `DeletionProtectionEnabled == false` BEFORE the delete call.
  Check trace for cascade warning acknowledgement.
- For `RemoveServersFromServerGroup`: verify trace captures server
  count before/after removal; alert if remaining count = 0.
- For `DeleteServerGroup` / `DeleteAcl` / `DeleteSecurityPolicy`:
  verify trace shows dependency check (not referenced).
- Apply the per-op Safety sub-rules from `rubric.md` §1.
- Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
- Suggestions ≤ 3, concrete.
- Do NOT reference the user's original request (rubber-stamping prevention).
# Test & regression assessment (MANDATORY — accuracy over coverage)
- Ask: if this change introduced a bug, would the existing tests FAIL?
- Reject stale tests, wrong assertions, masked failures, or tests that touch code without validating outcomes.
- If tests are inaccurate for the change → blocking=true; list concrete fixes in suggestions; RETRY.
- Decide whether targeted regression (AGENTS.md §11.1) is required — pick the smallest accurate suite, not blanket runs for coverage theater.
- When scope or risk is ambiguous, require regression with tests that would actually fail on breakage.
- BANNED: padding test count, chasing coverage %, PASSing on green suites that do not assert the changed behavior.

```

## Anti-Patterns

| ❌ Anti-Pattern | Why It's Wrong |
|----------------|----------------|
| Deleting ALB without checking deletion protection | Will fail — API returns `DeleteProtectionEnabled` |
| Removing last healthy server from server group | Causes 503 for all clients |
| Deleting a server group still referenced by a listener | API rejects, but G should have checked |
| Not escaping JSON arrays in CLI args | Causes `InvalidParameter` error |

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

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-07 | Initial ALB GCL prompt templates