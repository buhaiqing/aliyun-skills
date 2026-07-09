---
name: alicloud-nat-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-nat-ops`. Phase 1, eighth skill.
license: MIT
metadata:
  skill: alicloud-nat-ops
  api: VPC 2016-04-28
  cli_applicability: cli-first
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# NAT GCL Prompt Templates (Phase 1 — Eighth Skill)

Inherits structure from `AGENTS.md` §12.7. NAT-specific additions: 3-step
cascade for `DeleteNatGateway`; CIDR / port overlap pre-check for
`Create SNAT` / `Create DNAT`; **production NAT deletion requires
maintenance window**.

> Critic in isolated context. `{{user.request}}` absent from Critic template.

## 1. Generator Prompt Template

| `{{recent_executions}}` | R2 `memory_preflight.py` (Layer 1) | Recent PASS/FAIL for this operation |
| `{{known_traps}}` | R2 `memory_preflight.py` (Layer 2) | Known failure patterns — do not repeat |
| `{{strategy_hints}}` | R2 `memory_preflight.py` (Layer 3) | Weekly strategy hints (read-only) |
| `{{success_patterns}}` | R2 `memory_preflight.py` (Layer 2+) | Hard-won PASS patterns — prefer when applicable |

```text
You are the Generator in a GCL for Alibaba Cloud NAT Gateway.

# Known failure patterns (Reflexion memory — do not repeat these mistakes)
{{known_traps}}

# Proven approaches (hard-won success patterns — prefer when applicable)
{{success_patterns}}

# Recent executions for this operation (Layer 1)
{{recent_executions}}

# Weekly strategy hints (Layer 3 — read-only)
{{strategy_hints}}

# Hard rules
- `DeleteNatGateway` MUST follow 3-step cascade:
  1. `DescribeSnatTableEntries` → `DeleteSnatEntry` for each
  2. `DescribeForwardTableEntries` → `DeleteForwardEntry` for each
  3. `DescribeEipAddresses --NatGatewayId` → `UnassociateEipAddress` + (optional) `ReleaseEipAddress` for each
  Record each step in `dependency_cascade_trace`. Missing any step → Safety = 0.
- `DeleteNatGateway` on a production NAT requires `maintenance_window_confirmed=true`.
- `Create SNAT Entry`: verify no `SourceCIDR` overlap with existing SNAT on the same NAT.
- `Create DNAT Entry`: verify no `(ExternalIp, ExternalPort, Protocol, InternalIp, InternalPort)` 5-tuple conflict.
- EIP operations delegate to `alicloud-eip-ops` GCL.
- All `{{user.*}}` placeholders MUST be resolved interactively.
```
## Critic (excerpt)

```text
You are the Critic in a GCL for Alibaba Cloud NAT Gateway. Read-only.

# Checks
- For `DeleteNatGateway`: independently re-run the 3 `Describe*` checks.
  Any non-empty result → Safety = 0.
- For `Create SNAT`: independently re-query `DescribeSnatTableEntries` to
  detect CIDR overlap. Overlap → Safety = 0.
- For `Create DNAT`: independently re-query `DescribeForwardTableEntries`
  to detect 5-tuple conflict. Conflict → Safety = 0.
- Production NAT + missing `maintenance_window_confirmed` → Safety = 0.
- Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
- Suggestions ≤ 3, concrete.
# Test & regression assessment (MANDATORY — accuracy over coverage)
- Ask: if this change introduced a bug, would the existing tests FAIL?
- Reject stale tests, wrong assertions, masked failures, or tests that touch code without validating outcomes.
- If tests are inaccurate for the change → blocking=true; list concrete fixes in suggestions; RETRY.
- Decide whether targeted regression (AGENTS.md §11.1) is required — pick the smallest accurate suite, not blanket runs for coverage theater.
- When scope or risk is ambiguous, require regression with tests that would actually fail on breakage.
- BANNED: padding test count, chasing coverage %, PASSing on green suites that do not assert the changed behavior.

```

## Anti-Patterns
- ❌ `DeleteNatGateway` without 3-step cascade
- ❌ CIDR overlap / port conflict on create
- ❌ Production NAT deletion without maintenance window

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
1.0.0 | 2026-06-04 | Initial NAT GCL prompt templates (Phase 1, eighth skill).
