# Generator-Critic-Loop (GCL) — 速查清单

> **Source**: extracted from `AGENTS.md §12`. MANDATORY for every cloud operation
> scored against a quantified rubric.

Enforce Generator ↔ Critic adversarial loop on every cloud operation, scored against a quantified rubric.

**Full spec**: [`docs/gcl-spec.md`](gcl-spec.md)

---

## 1. Roles

| Role | Responsibility | Banned |
|------|---------------|--------|
| **Generator (G)** | Execute the cloud operation | Modify rubric, self-score |
| **Hallucination Detector (H)** | Pre-execution structural validity check (v1.5.0) | Execute API calls, mutate G's output |
| **Critic (C)** | Independently audit G's output; assess test accuracy + regression need (§2) | Call `aliyun`/SDK, mutate resources |
| **Orchestrator (O)** | Loop control, termination decision | Execute or score |

---

## 2. Critic Test & Regression Assessment (MANDATORY)

| Assessment | Critic action | On failure |
|------------|---------------|------------|
| **Test accuracy** | Judge whether tests correctly exercise changed behavior. Ask: *if this broke, would tests fail?* | Set `blocking=true`, trigger **RETRY** |
| **Regression verification** | Decide smallest accurate suite for the change; require green runs | Skip only with zero-behavioral-delta rationale |

**Banned**: padding test count, chasing coverage %, or PASSing because a suite ran green while no test asserts the changed behavior.

---

## 3. Rubric Dimensions (≥5)

| Dimension | Meaning | Safety=0 |
|-----------|---------|----------|
| **Correctness** | Resource ID/state/config matches request | — |
| **Safety** | Destructive operations confirmed or protected | **Immediate ABORT** |
| **Idempotency** | Repeating the call has no side effects | — |
| **Traceability** | Output is auditable | — |
| **Spec Compliance** | Complies with core-concepts.md constraints | — |

---

## 4. Loop Flow

**H pre-check** (when enabled) → **G execute** → **C critique** → **O decide**

---

## 5. Termination Conditions (first match wins)

| Condition | Action |
|-----------|--------|
| **PASS** | All dimensions pass → return G's result |
| **MAX_ITER** | Reached max_iter → return best-so-far |
| **SAFETY_FAIL** | Safety=0 → **ABORT** |
| **HALLUCINATION_ABORT** | H detected unresolved → **ABORT** (v1.5.0) |

---

## 6. Trace Audit

Every GCL run MUST persist JSON trace to `.runtime/audit/gcl-runner-ops/gcl-trace-*.json` (gitignored under `.runtime/`). Credential fields MUST be masked per `AGENTS.md §8`.

---

## 7. Skill Classification + Per-Skill Defaults

Full 30+ skill table: [`docs/gcl-spec.md §8`](gcl-spec.md#8-per-skill-defaults)

| Level | max_iter | Key Risk |
|-------|:--------:|----------|
| **required** | 2 | Data destruction / instance deletion / irreversible |
| **recommended** | 3 | Resource deletion / config changes; batch messaging; bucket/FS delete |
| **optional** | 5 | Read-only audit / diagnostic |

---

## 8. Anti-Patterns (banned)

Shared context G+C, subjective scoring, unbounded loop, **Critic seeing user request**, silently downgrading on Safety fail, trace not persisted, Critic mutating resources, trace leaking secrets. Full list: [`docs/gcl-spec.md §9`](gcl-spec.md#9-anti-patterns-banned).

---

## 9. Shared Runner & Rollout

Cross-skill: delegate via product `SKILL.md` **Delegation Rules** to [`alicloud-gcl-runner-ops`](../alicloud-gcl-runner-ops/SKILL.md). New-skill GCL artifacts: [`alicloud-skill-generator/references/gcl-rollout-spec.md`](../alicloud-skill-generator/references/gcl-rollout-spec.md).

---

## 10. 相关规范

- **完整 GCL 规范**：见 [`docs/gcl-spec.md`](gcl-spec.md)（roles / rubric / trace schema / anti-patterns 完整版）
- **双轨测试**：见 [`docs/dual-track-testing.md`](dual-track-testing.md)（Track 1 dry-run / Track 2 真实环境）
- **Runtime Harness**：见 [`docs/runtime-harness-quickref.md`](runtime-harness-quickref.md)（CLI wrapper + Langfuse trace 集成）