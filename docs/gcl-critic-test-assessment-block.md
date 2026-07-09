# GCL Critic — Test & Regression Assessment Block

> Canonical text for all `references/prompt-templates.md` Critic templates.
> Source: [`AGENTS.md` §12](../AGENTS.md#critic-test--regression-assessment-mandatory) / [`gcl-spec.md` §2.1](gcl-spec.md#21-critic-test--regression-assessment-mandatory).

**Core principle — accuracy over coverage**: Do **not** optimize for coverage metrics or test count. Optimize for whether tests **accurately** validate changed behavior and would **reliably catch** real regressions.

---

## Excerpt (append to every Critic `# Hard rules` / `# Checks` section)

```text
# Test & regression assessment (MANDATORY)
- Ask: if this change introduced a bug, would the existing tests FAIL?
- Reject stale tests, wrong assertions, masked failures, or tests that touch code without validating outcomes.
- If tests are inaccurate for the change → blocking=true; list concrete fixes in suggestions; RETRY.
- Decide whether targeted regression (AGENTS.md §11.1) is required — pick the smallest accurate suite, not blanket runs for coverage theater.
- When scope or risk is ambiguous, require regression with tests that would actually fail on breakage.
- BANNED: padding test count, chasing coverage %, PASSing on green suites that do not assert the changed behavior.
```

---

## JSON extension (add to Critic strict-JSON output schema)

```json
  "test_assessment": {
    "tests_accurate": true|false,
    "accuracy_issues": ["stale/wrong assertion/masked failure/shallow test — concrete fixes"],
    "regression_required": true|false,
    "regression_suites": ["bash alicloud-<product>-ops/test-skillopt-backward-compatibility.sh", "..."],
    "regression_rationale": "why these suites accurately validate the change (or skip reason when regression_required=false)"
  },
```

Set `blocking=true` when any rubric dimension fails **or** `test_assessment.tests_accurate=false` **or** `regression_required=true` but no green-run evidence is in the trace/completion summary.

---

## Standalone section (copy into each `prompt-templates.md`)

```markdown
---

## GCL Critic — Test & Regression Assessment (MANDATORY)

> **Accuracy over coverage** — applies to **every** Critic template in this file.

On each critique, the Critic MUST also evaluate:

| Assessment | On failure |
|------------|------------|
| **Test accuracy** — would existing tests fail if this change broke? | `blocking=true`; concrete test fixes in `suggestions`; **RETRY** |
| **Regression gate** — is targeted regression ([§11.1](../../AGENTS.md#111-regression-testing-mandatory)) required? | Name smallest accurate suite(s) + require green-run evidence; or document zero-behavioral-delta skip rationale |

**Banned**: padding test count, chasing coverage %, PASSing because suites are green but no test asserts the changed behavior.

When returning strict JSON, include `test_assessment` per [gcl-critic-test-assessment-block.md](../../docs/gcl-critic-test-assessment-block.md).
```

---

## Agent execution gate (MANDATORY before done)

Templates alone do not enforce the Critic. Every executing Agent MUST run:

```bash
bash scripts/skill-change-critic-gate.sh classify
bash scripts/skill-change-critic-gate.sh template
# Edit .runtime/audit/skill-change-verdict.json — tests_accurate + accuracy_rationale
bash scripts/skill-change-critic-gate.sh verify --verdict .runtime/audit/skill-change-verdict.json --run
```

Mechanical layer picks **minimum** regression suites from git diff; Agent layer judges **test accuracy** (not coverage %). Both must PASS (exit 0).
