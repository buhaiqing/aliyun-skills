# M3 (SkillOpt Evolution Flywheel — C Phase) · PLAN

> Implements SPEC `2026-07-30-ms-skillopt-milestone-c-spec.md`.
> Follows repo workflow: SPEC → PLAN → Implement (TDD + GCL).

## Re-baseline (why this plan is small)

Audit on 2026-07-30 found M3 is ~70% done in code already:
- M3.1 `queue_nightly.py` ✅ (scans L1/L2/L3)
- M3.2 L3 integration ✅ (`scan_l3_strategy` in queue_nightly.py)
- M3.4 PR-drafter gate ✅ (`scripts/skill-change-critic-gate.sh` exists)
- M3.6 `test-skill-evolution-milestone-c.sh` ✅

**Remaining = M3.3 (orchestrator) + M3.5 (scheduler) + TODO.md reconciliation.**

## P1 — `run_milestone_c.sh` orchestrator (M3.3)

**Goal:** turn a queued skill into a `best_skill.md` candidate, offline + CI-safe.

Steps:
1. Read queue from `queue_nightly.py --format json` (reuse, don't re-scan).
2. For each queued skill: run `run_milestone_b.sh <skill>` (B rollout; respects
   `SKILL_EVOLUTION_MOCK_ROLLOUT=1`).
3. Optional offline train: if `skillopt` importable → `skillopt train` against
   `benchmark/alicloud_ops/`; else mock path (seed-only, like
   `test-skill-evolution-train-smoke.sh`).
4. Write `.runtime/skill-evolution/<skill>/best_skill.md` (candidate only).
5. `--dry-run` flag: print plan, write nothing.

**TDD:**
- RED: write `test-run-milestone-c.sh` asserting (a) `best_skill.md` produced
  under `.runtime/`, (b) `SKILL.md` untouched, (c) mock path works w/o `skillopt`.
- GREEN: implement `run_milestone_c.sh`.
- Verify: `bash scripts/skill_evolution/test-run-milestone-c.sh`.

**Checkpoint V1:** `run_milestone_c.sh --dry-run alicloud-ecs-ops` exits 0 and
emits candidate to `.runtime/` only.

## P2 — PR drafter wiring (M3.4, previously listed as TODO)

**Goal:** wire existing `skill-change-critic-gate.sh` so a candidate becomes a
**draft** PR only after the gate passes; never auto-merge.

Steps:
1. In `run_milestone_c.sh`, after writing `best_skill.md`, add a
   `--draft-pr` step: diff `best_skill.md` vs `SKILL.md` selected sections, then
   call `scripts/skill-change-critic-gate.sh verify --run`.
2. On gate pass → open **draft** PR (gh CLI or hub), label `skill-evolution`,
   assign no auto-merge. On gate fail → stop, leave candidate for human review.
3. Keep `--dry-run` to skip PR open.

**Checkpoint V2:** with a mocked gate-pass fixture, a draft PR is created; with a
mocked gate-fail fixture, no PR and non-zero exit.

## P3 — Scheduler (M3.5)

**Goal:** unattended end-to-end run, Local-first compliant.

Steps:
1. Local cron snippet: `scripts/skill_evolution/cron-nightly.sh` →
   `queue_nightly.py` → `run_milestone_c.sh` → PR drafter. Documented, not
   committed as active cron.
2. Git-signal-only GHA: `.github/workflows/skill-evolution-weekly.yml` that
   **dispatches/notify** (no training on GHA, per Local-first). If repo policy
   forbids even dispatch-on-GHA, fall back to cron-only and document the reason
   in README. **Confirm interpretation with user before writing GHA** (see
   SPEC §5 risk).
3. CI runs scheduler in `SKILL_EVOLUTION_MOCK_ROLLOUT=1` (no creds).

**Checkpoint V3:** `cron-nightly.sh` runs end-to-end in mock mode; GHA (if
approved) runs green on `pull_request` dry-run.

## P4 — Close TODO.md staleness

**Goal:** reconcile `TODO.md` M3 checklist with actual state.

Steps:
1. Mark M3.1/M3.2/M3.4/M3.6 as ✅ (already in code).
2. Keep M3.3/M3.5 as the only open `[ ]` until P1/P3 ship.
3. Add a one-line note: "M3 re-baselined 2026-07-30 — see plan."

**Checkpoint V4:** `grep -c` open M3 items == 2 (M3.3, M3.5).

## Execution order & dependencies

```
P1 (orchestrator) ──▶ P2 (PR wiring, depends on P1 candidate)
P3 (scheduler) ──▶ depends on P1+P2
P4 (TODO close) ──▶ after P1+P3 land
```

All steps are non-destructive to `SKILL.md` (INV-1/2). Each step: TDD first,
then implement, then verify checkpoint independently (do not trust self-report).

## GCL note

Per `gcl-rules.md`, new scripts (P1/P3) + TODO.md change trigger the GCL
multi-sub-agent loop. This plan's implementation phase will spawn Generator +
≥2 parallel Critics, ≤3 rounds. P4 (doc-only reconcile) is <5-line-ish but
touches TODO.md broadly → still run 2-round self-review.
