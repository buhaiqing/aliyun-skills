# R5 — Cross-Skill Pattern Generalization (Layer 2)

> **Status**: 5.1–5.4 implemented (2026-06-21).
> **Owner**: `alicloud-gcl-runner-ops` — product skills MUST NOT duplicate normalization logic.
> **Related**: [success-patterns.md](success-patterns.md) (R4) · [memory-preflight.md](memory-preflight.md) (R2) · existing `cross_skill` category (orchestration chain failures — **different** from R5)

## Problem

Layer 2 `cli_parameter` rows are deduped per `(skill, command, error)` string. The same
API mistake on ECS, RDS, and Redis produces three near-identical traps that do not
surface as a single transferable lesson.

R5 adds **error normalization**, **cross-skill aggregation** into `generalized_cli`, and
**tiered retrieve** so agents see `specific > generalized_cli > generic`.

> **Not in scope for R5**: The existing `cross_skill` **category** remains for
> source→target orchestration failures (`redis-ops` → `ecs-ops`). R5 generalized traps
> live in `generalized_cli` (distinct from orchestration `cross_skill`).

---

## 5.1 — Error normalization

### API

```python
normalize_error_pattern(error: str, command: str | None = None) -> dict[str, str]
```

Returns:

| Field | Example | Purpose |
|-------|---------|---------|
| `error_code` | `MissingParam` | Canonical Alibaba / CLI error token |
| `param` | `InstanceId` | Primary parameter name when extractable |
| `normalized_key` | `MissingParam:InstanceId` | Stable cross-skill grouping key (5.2) |
| `semantic` | `repeatlist_suffix` | Heuristic fix class for retrieval hints |

Empty input → all fields empty strings (no-op).

### Store hook

On `reflexion_store()` for `category=cli_parameter`, enrich pattern with normalization
fields before dedup. Per-skill dedup keys unchanged; `normalized_key` is metadata for 5.2.

---

## 5.2 — Cross-skill aggregator

### API

```python
reflexion_aggregate_generalized(
    root=None,
    min_skills=3,
    min_count=1,
    apply=False,
) -> dict
```

Scans all `cli_parameter` rows with a non-empty `normalized_key`, groups by key, and
when **≥ `min_skills` distinct skills** share the key, builds one `generalized_cli` row:

| Field | Meaning |
|-------|---------|
| `normalized_key` | Group key e.g. `MissingParam:InstanceId` |
| `skills` | Distinct contributing skills |
| `skill_count` | `len(skills)` |
| `count` | Sum of member counts |
| `fix` | Highest-count member fix text |
| `semantic` | From normalization |

With `apply=True`, replaces `store["generalized_cli"]` entirely (rebuild, not merge).

### CLI

```bash
python3 gcl_reflexion.py aggregate-generalized [--min-skills 3] [--apply]
```

`make memory-maintain-apply` (via `scripts/runtime_cleanup.py`) runs this after
`promote-from-memory` and `success-report`.

---

## 5.3 — Tiered retrieve

`reflexion_retrieve(skill, ...)` ranks patterns in three tiers:

| Tier | Categories | Match rule |
|------|------------|------------|
| **0 — specific** | `cli_parameter`, `runtime`, `max_iter`, `near_miss` | `skill` matches query |
| **1 — generalized** | `generalized_cli` | query skill ∈ row `skills` |
| **2 — generic** | `cross_skill`, others | source/skill match |

Within each tier, sort by time-weighted score (`_time_weighted_score`). Return value
includes `_tier` and `_score` for debugging.

`format_known_traps()` annotates generalized rows with `cross_skill_skills=N`.

---

## Roadmap

| # | Task | Status |
|---|------|--------|
| 5.1 | `normalize_error_pattern()` + store enrich | ✅ |
| 5.2 | Aggregator — ≥3 skills share `normalized_key` | ✅ |
| 5.3 | `reflexion_retrieve` priority `specific > generalized > generic` | ✅ |
| 5.4 | Tests for aggregate + retrieve | ✅ |

---

## Quality gates

| ID | Check |
|----|-------|
| CS-1 | Same `normalized_key` for ecs/rds/redis `MissingParam: InstanceId` variants |
| CS-2 | Secrets / instance ids never appear in `normalized_key` |
| CS-3 | Unknown error text → empty `normalized_key` (no false grouping) |
| CS-4 | `reflexion_store` enriches `cli_parameter` rows idempotently |
| CS-5 | Aggregate requires ≥3 skills; 2-skill groups produce zero generalized rows |
| CS-6 | Retrieve returns tier-0 skill rows before tier-1 `generalized_cli` |
