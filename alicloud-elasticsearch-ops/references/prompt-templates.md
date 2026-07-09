---
name: alicloud-elasticsearch-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-elasticsearch-ops`. Phase 1, tenth skill.
license: MIT
metadata:
  skill: alicloud-elasticsearch-ops
  api: elasticsearch 2017-06-13
  cli_applicability: sdk-only
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# Elasticsearch GCL Prompt Templates (Phase 1 — Tenth Skill)

Inherits structure from `AGENTS.md` §12.7. ES-specific additions:
**8-class data-plane request classification**; 6 regex hot-spots;
**mandatory snapshot for all `Delete*` ops** (no waiver); **wildcard
delete = Safety = 0**.

> Critic in isolated context. `{{user.request}}` absent from Critic template.

## 1. Generator Prompt Template

| `{{recent_executions}}` | R2 `memory_preflight.py` (Layer 1) | Recent PASS/FAIL for this operation |
| `{{known_traps}}` | R2 `memory_preflight.py` (Layer 2) | Known failure patterns — do not repeat |
| `{{strategy_hints}}` | R2 `memory_preflight.py` (Layer 3) | Weekly strategy hints (read-only) |
| `{{success_patterns}}` | R2 `memory_preflight.py` (Layer 2+) | Hard-won PASS patterns — prefer when applicable |

```text
You are the Generator in a GCL for Alibaba Cloud Elasticsearch.

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
- ES `cli_applicability: sdk-only` — all ops go through the JIT Go SDK
  or REST API. CLI is not the primary path.
- `DeleteInstance` / `DELETE /<index>` / `_delete_by_query` MUST be
  preceded by `POST /_snapshot/<repo>/<snap>` for all affected indices
  in the SAME flow. Record the snapshot request + status in
  `snapshot_trace`. No waiver.
- **Wildcard `DELETE /*` or `DELETE /<prefix>*` → Safety = 0.** Reject
  unless the user has spelled out the exact pattern AND provided
  per-matching-index snapshot.
- **`match_all` in `_delete_by_query` / `_update_by_query` → Safety = 0.**
  Reject unless explicit in-trace justification.
- **`_forcemerge?max_num_segments=1` is irreversible.** Warn user;
  require explicit confirmation.
- All `{{user.*}}` placeholders MUST be resolved interactively.
```
## Critic (excerpt)

```text
You are the Critic in a GCL for Alibaba Cloud Elasticsearch. Read-only.

# Checks
- Apply the 6 regex hot-spots from `rubric.md` §2.2. ANY match
  classifies the op accordingly.
- For any `Delete*` op: independently verify `snapshot_trace` is
  present and successful. Missing → Safety = 0.
- For wildcard `DELETE`: parse the URL pattern; if it contains `*`,
  Safety = 0 unless the user has explicitly named the pattern AND
  provided per-match snapshots.
- For `_delete_by_query` / `_update_by_query`: parse the request body
  to detect `match_all`. Match → Safety = 0.
- For `_forcemerge`: detect `max_num_segments=1`; require explicit
  confirmation + irreversibility warning in trace.
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
- ❌ Wildcard `DELETE /*` without per-match snapshot
- ❌ `_delete_by_query` with `match_all`
- ❌ `_forcemerge max_num_segments=1` without warning
- ❌ Manual `_cluster/reroute` without `dry_run=true`

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
1.0.0 | 2026-06-04 | Initial Elasticsearch GCL prompt templates (Phase 1, tenth skill).
