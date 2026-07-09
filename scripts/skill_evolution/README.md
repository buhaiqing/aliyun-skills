# Skill Evolution — Milestone A (Microsoft SkillOpt flywheel)

> Architecture: [runtime-harness-glossary.md §1.1](../../docs/runtime-harness-glossary.md#11-与-microsoft-skillopt-的架构关系)  
> Implementation plan: [2026-06-26-ms-skillopt-milestone-a.md](../../docs/superpowers/plans/2026-06-26-ms-skillopt-milestone-a.md)

Offline pipeline from **Runtime Harness / GCL Layer 1 memory** → SkillOpt-ready artifacts. Does **not** modify wrapper hot path.

## Quick start (pilot: `alicloud-ecs-ops`)

```bash
export ALIYUN_SKILLS_ROOT="$PWD"
bash scripts/skill_evolution/run_milestone_a.sh alicloud-ecs-ops
```

Outputs (gitignored):

```
.runtime/skill-evolution/alicloud-ecs-ops/
├── trajectories.jsonl    # sanitized L1 memory export
├── trainable_seed.md     # SKILL.md trainable sections (not full SKILL.md)
└── dataset.jsonl         # eval_queries + split + trajectory_count
```

## Steps

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 1 | `export_trajectories.py` | `.runtime/memory/{skill}/*.jsonl` | `trajectories.jsonl` |
| 2 | `build_trainable_seed.py` | `{skill}/SKILL.md` | `trainable_seed.md` |
| 3 | `build_dataset.py` | `trainable_seed.md` + `assets/eval_queries.json` + `trajectories.jsonl` | `dataset.jsonl` |

## Optional: Microsoft SkillOpt training

Requires separate install (not a repo dependency). **Do not** auto-replace `SKILL.md` — merge `best_skill.md` via reviewed PR only (triggers / overview / troubleshooting summaries; never `references/`, AGENTS.md TE-6).

```bash
pip install 'skillopt>=0.1.0'
bash scripts/test-skill-evolution-train-smoke.sh   # CI-safe mock → best_skill.md
```

## Tests

```bash
bash scripts/test-skill-evolution-milestone-a.sh
bash scripts/test-skill-evolution-milestone-b.sh
bash scripts/test-skill-evolution-train-smoke.sh
```

## Milestone B — benchmark adapter (`alicloud_ops`)

Consumes Milestone A outputs and runs mock-safe rollout + scorer smoke tests.

```bash
export ALIYUN_SKILLS_ROOT="$PWD"
bash scripts/skill_evolution/run_milestone_b.sh alicloud-ecs-ops
```

Benchmark modules: `benchmark/alicloud_ops/` (`dataloader.py`, `rollout.py`, `scorer.py`, `adapter.py`).
`run_milestone_b.sh` syncs `trainable_seed.md` → `.runtime/.../initial.md` and materializes SkillOpt splits.

Set `SKILL_EVOLUTION_MOCK_ROLLOUT=1` for CI (no cloud credentials). Real harness rollout is opt-in.

## Nightly / automated queue (planned)

**Goal:** Make the flywheel run unattended — nightly scan of failed L1 / L2 memory, rank by impact (failure count × priority), queue `skillopt train` jobs, auto-draft PRs against `SKILL.md`.

**Will deliver (planned):**

- Nightly scheduler (cron / GitHub Actions) consuming L1 + L2 JSONL stores.
- Priority queue keyed by `(skill, failure_pattern.count, eval_priority)` — see `docs/failure-patterns.md`.
- Optional SkillOpt-Sleep training runner (offline epochs against `benchmark/alicloud_ops/`).
- PR drafter: diff `best_skill.md` vs current `SKILL.md`, open PR through `scripts/skill-change-critic-gate.sh verify --run`, never auto-merge.

**Depends on:** M1 + M2 green; remains human-gated on merge.
