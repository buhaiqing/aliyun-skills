# M3 (SkillOpt Evolution Flywheel — C Phase) · SPEC

> Companion to M1 (`2026-06-26-ms-skillopt-milestone-a.md`) and M2
> (`2026-06-26-ms-skillopt-milestone-b.md`). This SPEC re-baselines M3 against
> the **actual repo state** discovered on 2026-07-30, because the TODO.md M3
> checklist is stale (M3.1/M3.2/M3.4/M3.6 are already implemented in code).

## 1. Problem & Why

The flywheel goal: turn Runtime Harness / GCL **Layer 1 (memory)** and **Layer 2
(reflexion)** failure patterns into an *unattended* improvement loop — rank
skills by failure impact, optionally train (SkillOpt-Sleep, offline), and emit a
`best_skill.md` candidate that flows into a **human-gated PR** against `SKILL.md`.

M1/M2 delivered the offline export + benchmark adapter. The loop is NOT yet
self-driving: there is no orchestrator that consumes the nightly queue and
produces `best_skill.md` candidates, and no scheduler to run it unattended.

## 2. Current State Audit (2026-07-30)

| TODO item | Claimed | Actual | Verdict |
|-----------|---------|--------|---------|
| M3.1 `queue_nightly.py` | `[ ]` | exists, scans L1+L2+L3 (`scan_l3_strategy`, `W_L3=0.2`) | **DONE** |
| M3.2 L3 integrate (`strategy-baseline.json`) | `[ ]` | `queue_nightly.py` already reads `docs/strategy-baseline.json` + `strategy-report.md` | **DONE** |
| M3.3 `run_milestone_c.sh` | `[ ]` | **missing** | **TODO** |
| M3.4 PR drafter (via `skill-change-critic-gate.sh`) | `[ ]` | `scripts/skill-change-critic-gate.sh` exists (18153 B) | **DONE (gate exists; wiring needed)** |
| M3.5 scheduler (cron / GHA) | `[ ]` | no `.github/workflows/skill-evolution-weekly.yml` | **TODO** |
| M3.6 `test-skill-evolution-milestone-c.sh` | `[ ]` | exists, tests queue sorting w/ mock L1/L2 | **DONE** |

**True remaining scope = M3.3 + M3.5 + close TODO.md staleness.**

## 3. Success Criteria (INV — non-negotiable floors)

- **INV-1 (local-first):** all queue scan + training run against `.runtime/`
  (gitignored) artifacts; never mutate `SKILL.md` on disk. `best_skill.md` is a
  *candidate* only.
- **INV-2 (human-gated merge):** PR is **draft**, opened only after
  `scripts/skill-change-critic-gate.sh verify --run` passes. **Never auto-merge.**
- **INV-3 (no hot-path impact):** M3 tooling is offline/batch; zero change to
  wrapper / harness hot path (per README "Does not modify wrapper hot path").
- **INV-4 (CI-safe):** `run_milestone_c.sh` and the scheduler MUST run under
  `SKILL_EVOLUTION_MOCK_ROLLOUT=1` in CI (no cloud creds, no real train unless
  explicitly enabled).

## 4. Scope

**In:**
- M3.3 `scripts/skill_evolution/run_milestone_c.sh`: for each queued skill →
  `run_milestone_b.sh` (B rollout) → optional `skillopt train` (offline, mock
  path in CI) → write `.runtime/skill-evolution/{skill}/best_skill.md`.
- M3.5 scheduler: local cron snippet **and** git-signal-only GHA
  (`.github/workflows/skill-evolution-weekly.yml`) that runs `queue_nightly.py`
  → `run_milestone_c.sh` → PR drafter; runtime queue stays on maintainer
  machine (Local-first, per `docs/memory-strategy.md`).
- Close TODO.md M3 checklist (mark real-done items, keep M3.3/M3.5 open until shipped).

**Out (explicitly):** real SkillOpt training infrastructure install; auto-merge;
modifying `references/` / `AGENTS.md` via the flywheel (README forbids).

## 5. Risks / Open Questions

- M3.5 GHA: repo policy forbids runtime queue on GHA (Local-first). The GHA must
  be **git-signal-only** (dispatch/notify), not execute training. Confirm this
  interpretation matches `docs/memory-strategy.md` before writing the workflow.
- `skillopt` package is an optional extra (`pip install 'skillopt>=0.1.0'`).
  `run_milestone_c.sh` must degrade to "export candidate from seed only" when
  `skillopt` absent (mock path), exactly like `run_milestone_b.sh`'s mock mode.

## 6. Acceptance / Verification

- `bash scripts/skill_evolution/test-skill-evolution-milestone-c.sh` stays green.
- New: `bash scripts/skill_evolution/run_milestone_c.sh --dry-run alicloud-ecs-ops`
  produces a `best_skill.md` candidate under `.runtime/` without touching `SKILL.md`.
- New unit/integration test for `run_milestone_c.sh` (mock train path, no commit).
- Scheduler (cron + GHA) runs end-to-end in mock mode without cloud creds.
- Post-change: TODO.md M3 section reconciled with actual state.
