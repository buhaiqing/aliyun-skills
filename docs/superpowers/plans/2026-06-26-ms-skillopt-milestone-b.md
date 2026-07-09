# Microsoft SkillOpt Integration — Milestone B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Deliver Milestone **B** — repo-owned SkillOpt benchmark adapter under `scripts/skill_evolution/benchmark/alicloud_ops/` with `dataloader`, `rollout`, `scorer`, mock-safe tests, and `run_milestone_b.sh` orchestrator consuming Milestone A outputs.

**Architecture:** Benchmark lives **in this repo** (not inside PyPI `skillopt` package). Modules follow Microsoft SkillOpt env contract (`dataloader.py`, `rollout.py`, `initial.md`) so operators can `PYTHONPATH=scripts/skill_evolution/benchmark skillopt train --env alicloud_ops` when `skillopt` is installed. Rollout supports `SKILL_EVOLUTION_MOCK_ROLLOUT=1` for CI (no cloud credentials). Reuses Milestone A: `.runtime/skill-evolution/{skill}/dataset.jsonl`, `trainable_seed.md`, `trajectories.jsonl`.

**Tech Stack:** Python 3.10 stdlib, unittest, optional `skillopt` CLI, existing harness wrapper paths.

**Depends on:** Milestone A commit (`scripts/skill_evolution/*`).

**Out of scope (Milestone C):** nightly queue, Langfuse scan, auto PR.

---

## File structure

```
scripts/skill_evolution/benchmark/alicloud_ops/
├── initial.md                 # seed skill doc (generated pointer; tests use fixture)
├── dataloader.py              # load dataset.jsonl → train/val splits
├── rollout.py                 # execute query against skill (mock or harness stub)
├── scorer.py                  # score rollout result
├── __init__.py
└── fixtures/
    ├── dataset.jsonl
    └── trainable_seed.md

scripts/skill_evolution/
├── run_milestone_b.sh         # A outputs → benchmark smoke
├── benchmark_smoke_test.py    # unittest without skillopt pip
└── README.md                  # M2 section

scripts/test-skill-evolution-milestone-b.sh
```

---

## Task 1: Dataloader + initial.md

**Files:**
- Create: `scripts/skill_evolution/benchmark/alicloud_ops/dataloader.py`
- Create: `scripts/skill_evolution/benchmark/alicloud_ops/__init__.py`
- Create: `scripts/skill_evolution/benchmark/alicloud_ops/fixtures/dataset.jsonl`
- Create: `scripts/skill_evolution/benchmark/alicloud_ops/dataloader_test.py`

**Contract:**
- `load_dataset(path) -> dict` with keys `train`, `heldout`, `heldout_trigger` (lists of row dicts)
- `resolve_dataset_path(skills_root, skill)` → `.runtime/skill-evolution/{skill}/dataset.jsonl`
- Filter by `split` field from Milestone A schema

**Tests:** 3 cases — split parsing, missing file raises, empty heldout ok.

---

## Task 2: Rollout + scorer

**Files:**
- Create: `scripts/skill_evolution/benchmark/alicloud_ops/rollout.py`
- Create: `scripts/skill_evolution/benchmark/alicloud_ops/scorer.py`
- Create: `scripts/skill_evolution/benchmark/alicloud_ops/rollout_test.py`
- Create: `scripts/skill_evolution/benchmark/alicloud_ops/scorer_test.py`

**Rollout contract:**
- `run_rollout(query: str, skill_md: str, *, mock: bool | None) -> dict`
- Mock mode (`SKILL_EVOLUTION_MOCK_ROLLOUT=1` or `mock=True`): return `{"status": "mock", "skill_loaded": True, "query": query}`
- Real mode: verify `{skill}/scripts/*-harness-wrapper.sh` exists; run **read-only** smoke via subprocess with `_SKILLOPT_SKIP_WRAPPER_CHECK=1` only in tests with aliyun stub — **default CI uses mock only**

**Scorer contract:**
- `score_rollout(rollout: dict, expected_skill: str) -> float` in [0,1]
- Mock: 1.0 if `skill_loaded` else 0.0
- Optional: bump score if `rubric_pass` in rollout metadata

---

## Task 3: Orchestrator + integration

**Files:**
- Create: `scripts/skill_evolution/run_milestone_b.sh`
- Create: `scripts/skill_evolution/benchmark_smoke_test.py`
- Create: `scripts/test-skill-evolution-milestone-b.sh`
- Modify: `scripts/skill_evolution/README.md`, `TODO.md`, `scripts/skill-change-critic-gate.sh`
- Create: `scripts/skill_evolution/benchmark/alicloud_ops/initial.md` (short pointer to trainable_seed)

**run_milestone_b.sh:**
1. Run `run_milestone_a.sh` if dataset missing
2. Copy/sync `trainable_seed.md` → `benchmark/alicloud_ops/initial.md` (or generate inline)
3. `python3 -m unittest benchmark_smoke_test` with `SKILL_EVOLUTION_MOCK_ROLLOUT=1`
4. Print hint for `skillopt train` if installed

**Acceptance:**
```bash
bash scripts/test-skill-evolution-milestone-b.sh
bash scripts/skill_evolution/run_milestone_b.sh alicloud-ecs-ops
```

---

## Milestone B acceptance

| AC | Check |
|----|-------|
| B1 | dataloader splits match Milestone A `split` values |
| B2 | rollout mock mode works without credentials |
| B3 | scorer returns 0..1 |
| B4 | smoke test green |
| B5 | py310 compat |
