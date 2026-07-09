# Microsoft SkillOpt Integration — Milestone A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Milestone **A** — minimal offline flywheel from Runtime Harness / GCL signals → sanitized trajectory export → SkillOpt-ready dataset + trainable seed, pilot on `alicloud-ecs-ops`, with human PR gate for any `best_skill.md` merge.

**Architecture:** Platform-owned scripts under `scripts/skill_evolution/` (stdlib Python 3.10). Reads Layer 1 memory JSONL + optional local traces; never mutates hot path. Microsoft SkillOpt (`pip install skillopt`) is **optional** at train time — export/dataset steps work without it. Milestones B/C extend A (benchmark env, nightly queue) — see root `TODO.md`.

**Tech Stack:** Python 3.10+ stdlib, bash, existing `gcl_memory.py` layout, `assets/eval_queries.json`, optional `skillopt` PyPI package.

**Spec reference:** [runtime-harness-glossary.md §1.1](../../runtime-harness-glossary.md#11-与-microsoft-skillopt-的架构关系)

**Out of scope (Milestone B/C):** `skillopt/envs/alicloud-ops/` benchmark package, WebUI epochs, SkillOpt-Sleep nightly cron.

---

## Milestones (A → B → C)

| ID | Name | Deliverable | Status |
|----|------|-------------|--------|
| **M1 — A** | Minimal flywheel | `scripts/skill_evolution/*` export + dataset + pilot docs | 🚧 This plan |
| **M2 — B** | SkillOpt benchmark | `skillopt/envs/alicloud-ops/` dataloader + rollout + scorer | 📋 After M1 green |
| **M3 — C** | Sleep / nightly | L3 queue + recurring FAIL → draft PR | 📋 After M2 |

---

## File structure (Milestone A)

```
scripts/skill_evolution/
├── README.md                      # Operator guide + optional skillopt train cmd
├── export_trajectories.py         # L1 memory → sanitized trajectories.jsonl
├── export_trajectories_test.py
├── build_trainable_seed.py        # SKILL.md → trainable_seed.md (runtime .runtime/)
├── build_trainable_seed_test.py
├── build_dataset.py               # eval_queries + trajectories → dataset.jsonl
├── build_dataset_test.py
├── run_milestone_a.sh             # Orchestrator (export → seed → dataset)
└── fixtures/
    ├── memory_ecs.jsonl
    ├── eval_queries_ecs.json
    └── skill_md_header.md

.runtime/skill-evolution/          # gitignored outputs
└── alicloud-ecs-ops/
    ├── trajectories.jsonl
    ├── trainable_seed.md
    └── dataset.jsonl
```

**Modify:**
- [TODO.md](../../../TODO.md) — M1/M2/M3 tracker
- [docs/runtime-harness-glossary.md](../../runtime-harness-glossary.md) — link to `scripts/skill_evolution/README.md`
- [scripts/skill-change-critic-gate.sh](../../../scripts/skill-change-critic-gate.sh) — classify `scripts/skill_evolution/`
- [scripts/test-skill-evolution-milestone-a.sh](../../../scripts/test-skill-evolution-milestone-a.sh) — unittest wrapper for CI

---

## Task 1: Trajectory export (`export_trajectories.py`)

**Files:**
- Create: `scripts/skill_evolution/export_trajectories.py`
- Create: `scripts/skill_evolution/fixtures/memory_ecs.jsonl`
- Create: `scripts/skill_evolution/export_trajectories_test.py`
- Test: `scripts/skill_evolution/export_trajectories_test.py`

- [ ] **Step 1: Write failing tests**

```python
# export_trajectories_test.py (excerpt)
class ExportTrajectoriesTests(unittest.TestCase):
    def test_export_writes_schema_version_and_redacts_secrets(self):
        out = export_from_memory_dir(FIXTURES / "memory_ecs.jsonl", skill="alicloud-ecs-ops")
        self.assertEqual(out[0]["schema_version"], "1.0")
        self.assertNotIn("LTAI", out[0].get("command", ""))

    def test_missing_memory_dir_returns_empty_list(self):
        self.assertEqual(export_from_memory_dir("/nonexistent", skill="x"), [])
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd scripts/skill_evolution && python3 -m unittest export_trajectories_test -v`  
Expected: `ImportError` or `AttributeError`

- [ ] **Step 3: Implement `export_trajectories.py`**

Key functions:
- `resolve_skills_root()` — `ALIYUN_SKILLS_ROOT` or walk up to repo root
- `sanitize_command(cmd: str) -> str` — mask `LTAI...`, `sk-lf-`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- `load_memory_entries(memory_root, skill) -> list[dict]` — read all `memory_root/{skill}/*.jsonl`
- `to_trajectory_record(entry) -> dict` — map L1 fields to export schema:

```python
{
  "schema_version": "1.0",
  "skill": "alicloud-ecs-ops",
  "operation": "DescribeInstances",
  "timestamp": "2026-06-26T12:00:00Z",
  "source": "gcl-runner" | "skillopt-wrapper",
  "gcl_status": "PASS",
  "rubric_pass": true,
  "scores": {},
  "error_code": null,
  "command": "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
  "duration_ms": 120,
  "failure_pattern": null
}
```

CLI: `python3 export_trajectories.py --skill alicloud-ecs-ops [--memory-root PATH] [--out PATH]`

Default out: `{SKILLS_ROOT}/.runtime/skill-evolution/{skill}/trajectories.jsonl`

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add scripts/skill_evolution/export_trajectories.py scripts/skill_evolution/export_trajectories_test.py scripts/skill_evolution/fixtures/
git commit -m "feat(skill-evolution): export Layer 1 memory to sanitized trajectories"
```

---

## Task 2: Trainable seed extractor (`build_trainable_seed.py`)

**Files:**
- Create: `scripts/skill_evolution/build_trainable_seed.py`
- Create: `scripts/skill_evolution/fixtures/skill_md_header.md`
- Create: `scripts/skill_evolution/build_trainable_seed_test.py`

- [ ] **Step 1: Write failing test**

Extract from `## Overview` through end of `## Product Skill Mission` (exclusive of `## Runtime Rules`); strip YAML frontmatter.

- [ ] **Step 2: Run test — FAIL**

- [ ] **Step 3: Implement**

CLI: `python3 build_trainable_seed.py --skill alicloud-ecs-ops [--skill-md PATH] [--out PATH]`

Default out: `.runtime/skill-evolution/{skill}/trainable_seed.md`

Header comment in output:
```markdown
<!-- trainable_seed.md — Milestone A export for Microsoft SkillOpt; NOT a drop-in SKILL.md replacement -->
```

- [ ] **Step 4: Run test — PASS**

- [ ] **Step 5: Commit**

---

## Task 3: Dataset builder (`build_dataset.py`)

**Files:**
- Create: `scripts/skill_evolution/build_dataset.py`
- Create: `scripts/skill_evolution/fixtures/eval_queries_ecs.json`
- Create: `scripts/skill_evolution/build_dataset_test.py`

- [ ] **Step 1: Write failing tests**

- Join `queries` + `negative_queries` from `assets/eval_queries.json`
- Assign `split`: last 2 positive queries → `heldout`; negatives → `heldout_trigger`; rest → `train`
- Attach `trajectory_count` for skill from trajectories file (may be 0)

Output line schema:
```python
{
  "schema_version": "1.0",
  "query": "创建一台 ECS 实例",
  "expected_skill": "alicloud-ecs-ops",
  "split": "train",
  "priority": "P0",
  "trajectory_count": 3
}
```

- [ ] **Step 2–4: Implement + pass tests**

CLI: `python3 build_dataset.py --skill alicloud-ecs-ops`

- [ ] **Step 5: Commit**

---

## Task 4: Orchestrator + operator docs

**Files:**
- Create: `scripts/skill_evolution/run_milestone_a.sh`
- Create: `scripts/skill_evolution/README.md`
- Create: `scripts/test-skill-evolution-milestone-a.sh`

- [ ] **Step 1: `run_milestone_a.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
SKILL="${1:-alicloud-ecs-ops}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export ALIYUN_SKILLS_ROOT="$ROOT"
python3 "$ROOT/scripts/skill_evolution/export_trajectories.py" --skill "$SKILL"
python3 "$ROOT/scripts/skill_evolution/build_trainable_seed.py" --skill "$SKILL"
python3 "$ROOT/scripts/skill_evolution/build_dataset.py" --skill "$SKILL"
echo "[SUMMARY] outputs under $ROOT/.runtime/skill-evolution/$SKILL/"
if command -v skillopt >/dev/null 2>&1; then
  echo "[HINT] Optional: skillopt train — see scripts/skill_evolution/README.md"
else
  echo "[HINT] pip install skillopt  # optional for offline training"
fi
```

- [ ] **Step 2: README.md** — document flywheel, outputs, manual merge policy (`best_skill.md` → PR into SKILL.md sections only), link glossary §1.1

- [ ] **Step 3: `test-skill-evolution-milestone-a.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../scripts/skill_evolution"
python3 -m unittest discover -p '*_test.py' -v
bash -n ../skill_evolution/run_milestone_a.sh
```

- [ ] **Step 4: Run full suite**

```bash
bash scripts/test-skill-evolution-milestone-a.sh
python3 scripts/check_py310_compat.py
```

- [ ] **Step 5: Commit**

---

## Task 5: Repo wiring (TODO + glossary + critic gate)

**Files:**
- Modify: [TODO.md](../../../TODO.md)
- Modify: [docs/runtime-harness-glossary.md](../../runtime-harness-glossary.md)
- Modify: [scripts/skill-change-critic-gate.sh](../../../scripts/skill-change-critic-gate.sh)

- [ ] **Step 1: Add TODO section** — M1 🚧, M2/M3 📋 with link to this plan

- [ ] **Step 2: Glossary §1.1** — add bullet: Milestone A operator entry → `scripts/skill_evolution/README.md`

- [ ] **Step 3: critic gate** — `scripts/skill_evolution/*` → run `test-skill-evolution-milestone-a.sh`

- [ ] **Step 4: Commit**

```bash
git commit -m "docs: wire MS SkillOpt Milestone A TODO and operator entry"
```

---

## Milestone A acceptance criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| AC-1 | Export redacts credentials | `export_trajectories_test` |
| AC-2 | Pilot ecs-ops seed extracts without frontmatter | `build_trainable_seed_test` |
| AC-3 | Dataset merges eval_queries + split | `build_dataset_test` |
| AC-4 | Orchestrator runs on empty `.runtime/memory` (0 trajectories OK) | `bash scripts/skill_evolution/run_milestone_a.sh alicloud-ecs-ops` exit 0 |
| AC-5 | No hot-path changes to harness / gcl_runner | git diff scope |
| AC-6 | py310 compat | `python3 scripts/check_py310_compat.py` |

**Human gate (not automated in A):** `best_skill.md` diff reviewed → partial merge to `SKILL.md` via PR + `skill-change-critic-gate.sh verify --run`.

---

## Self-review (plan vs spec)

| Requirement | Task |
|-------------|------|
| A export trajectories | Task 1 |
| A package eval_queries | Task 3 |
| A optional skillopt train | Task 4 README |
| A validate + PR gate documented | Task 4 README + AC-6 |
| B/C deferred | Milestones table |
| Local-first / gitignore outputs | `.runtime/skill-evolution/` |
| Orthogonal to Runtime Harness | No wrapper changes |

No placeholders remain in task steps above.

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-06-26-ms-skillopt-milestone-a.md`.

**Recommended:** Subagent-driven per task, or inline execution of Tasks 1–5 in one session (Milestone A is ~2–3 hours).
