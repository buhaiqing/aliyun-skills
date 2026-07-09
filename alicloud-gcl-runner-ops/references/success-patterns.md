# R4 — Success Pattern Memory (Layer 2+)

> **Status**: R4 complete (4.1–4.6). Human report: `docs/success-patterns.md` via `gcl_reflexion.py success-report`.
> **Owner**: `alicloud-gcl-runner-ops` — product skills MUST NOT duplicate store/retrieve logic.
> **Related**: [memory-preflight.md](memory-preflight.md) (R2 slots) · [memory-strategy.md](../../docs/memory-strategy.md) · Layer 2 failures in `gcl_reflexion.py`

## Problem

Layer 2 today captures **failure** and **near-miss** patterns (`failure-patterns.md`, `{{known_traps}}`).
It does not record **what worked** after recovery — the command shape, iteration count, or context that led to a durable PASS.

Without positive reference:

- Generator repeats trial-and-error even when a prior session already found a stable path.
- `{{known_traps}}` warns what failed but not which follow-up succeeded.
- R6 (remediation confirmation) tracks trap stability via `remediated` / `consecutive_successes` — see [remediation-tracking.md](remediation-tracking.md).

R4 adds **success pattern memory**: small, deduped, retrieval-bounded records of **hard-won PASS** outcomes.

---

## 4.1 — Hard-won PASS vs ordinary PASS

### Definitions

| Term | Meaning |
|------|---------|
| **Ordinary PASS** | First-iteration success with no relevant pre-flight traps and strong critic scores — expected baseline; **do not store**. |
| **Hard-won PASS** | PASS that required recovery, prior trap context, or multi-iteration refinement — **store** as success pattern. |

### Capture gate (all required)

1. `trace["final"]["status"] == "PASS"` (not `dry-run`, not `SAFETY_FAIL`, not `MAX_ITER`, not `WRAPPER_BYPASS`).
2. Final critic `blocking == false` and `safety` score `> 0`.
3. At least one **hard-won signal** below is true.

### Hard-won signals (any one triggers capture)

| ID | Signal | Detection |
|----|--------|-----------|
| **HW-1** | Multi-iteration recovery | `len(trace["iterations"]) >= 2` |
| **HW-2** | Trap-informed pass | `memory_preflight` present and `known_traps` non-empty (list length ≥ 1) |
| **HW-3** | Score recovery | ∃ earlier iteration with `sum(scores) < final_sum(scores)` by ≥ 0.5 |
| **HW-4** | Near-miss resolved | Final pass but ∃ earlier iteration with any dimension `< 0.8` |
| **HW-5** | Hallucination recovery | H gate failed then passed on regen (future; `regenerated == true` on later iter) |

### Ordinary PASS (skip store) — all must hold

| ID | Condition |
|----|-----------|
| **OR-1** | `len(iterations) == 1` |
| **OR-2** | `memory_preflight` empty or `known_traps` empty |
| **OR-3** | `min(final_critic.scores.values()) >= 0.95` |
| **OR-4** | No HW-3 / HW-4 trajectory in earlier iterations |

> **Rationale**: OR-* avoids polluting the store with routine read-only Describe* that always pass. HW-* ensures we only index passes that carry transferable signal.

### Non-capture (explicit bans)

| Case | Reason |
|------|--------|
| `--dry-run` | No real generator execution |
| `test_assessment` only runs | Synthetic traces |
| Wrapper-lite PASS without GCL loop | Different schema; defer to R4.1b |
| Secrets in command | `sanitize()` must run before persist; drop if `<masked>` introduced |

### `capture_reason` enum (stored field)

| Value | When |
|-------|------|
| `multi_iter` | HW-1 |
| `traps_informed` | HW-2 (may coincide with HW-1) |
| `score_recovery` | HW-3 |
| `near_miss_resolved` | HW-4 |
| `hallucination_recovery` | HW-5 |

If multiple apply, prefer the **most specific** order: `hallucination_recovery` > `multi_iter` > `near_miss_resolved` > `score_recovery` > `traps_informed`.

### Hint generation (for retrieval, not LLM-generated at store time)

Deterministic template from trace (implementation 4.4):

```text
PASS after {iterations} iteration(s) ({capture_reason}).
Command: {command_excerpt}
{if preflight_had_traps}Preflight listed {trap_count} known trap(s).{/if}
{if low_dims}Earlier low dimensions: {low_dims}.{/if}
Final scores: {scores_summary}
```

---

## 4.2 — Schema & storage draft

### File layout

| Path | Git | Purpose |
|------|-----|---------|
| `.runtime/reflexion/success_patterns.json` | gitignore | Aggregated success pattern store (source of truth) |
| `docs/success-patterns.md` | committed (optional, phase 4.5+) | Human-readable report (≤ 150 lines, mirror `failure-patterns.md`) |

Same root as Layer 2 failures (`GCL_REFLEXION_ROOT` / `.runtime/reflexion/`), **separate file** so maintain/report paths stay independent.

### Top-level store shape

```json
{
  "version": "1.0.0",
  "updated_at": "2026-06-21T12:00:00Z",
  "patterns": []
}
```

### Pattern object (required fields)

| Field | Type | Description |
|-------|------|-------------|
| `skill` | string | `alicloud-{product}-ops` |
| `operation` | string | Rubric op name (e.g. `DeleteInstance`) |
| `command_excerpt` | string | Sanitized command, max 200 chars |
| `command_hash` | string | `sha256:` hex of normalized command (whitespace-collapsed) for dedup |
| `capture_reason` | string | Enum above |
| `iterations` | int | Final iteration count |
| `scores_summary` | string | Compact `dim=value` list, low dims first |
| `scores_min` | float | `min(scores.values())` at final iter |
| `preflight_had_traps` | bool | Whether HW-2 contributed |
| `trap_count` | int | `len(known_traps)` at preflight |
| `hint` | string | Deterministic retrieval text, max 300 chars |
| `count` | int | Dedup hit count (starts at 1) |
| `first_seen` | string | ISO 8601 UTC |
| `last_seen` | string | ISO 8601 UTC |
| `source` | string | `gcl-runner` (default) |

### Optional fields

| Field | Type | Description |
|-------|------|-------------|
| `execution_path` | string | From generator: `wrapper` \| `direct_aliyun` \| … |
| `matched_trap_categories` | string[] | Categories from preflight traps (e.g. `cli_parameter`) |
| `trace_path` | string | Relative path to exemplar trace (debug only; may omit in production) |

### Dedup key

```text
(skill, operation, command_hash, capture_reason)
```

On match: increment `count`, update `last_seen`, refresh `hint` only if `scores_min` improved.

### Trace attachment (write path preview)

```json
{
  "success_pattern": {
    "captured": true,
    "capture_reason": "multi_iter",
    "store_key": "alicloud-ecs-ops:DeleteInstance:sha256:abc…"
  }
}
```

When skipped (ordinary PASS): `"success_pattern": { "captured": false, "reason": "ordinary_pass" }`.

### Retrieval API (4.3 preview)

```python
success_retrieve(
    skill: str,
    operation: str | None = None,
    top_k: int = 3,
    root: Path | None = None,
    min_count: int = 1,
) -> list[dict[str, Any]]
```

Sort: time-weighted score (reuse `_time_weighted_score` from reflexion) × boost if `preflight_had_traps` on current op.

### R2 slot extension (4.4+ — not active until retrieve ships)

| Slot | Layer | Source | Default budget |
|------|-------|--------|----------------|
| `{{success_patterns}}` | 2+ | `success_retrieve(skill, op, top_k=3)` | 600 chars |

Empty fallback: `(none — no hard-won success patterns for this skill/operation)`.

Generator template addition (opt-in per skill):

```text
# Proven approaches (success patterns — prefer when applicable)
{{success_patterns}}
```

**Critic rule unchanged**: Critic MUST NOT receive success patterns if they embed user request text; hints are command/score metadata only.

---

## Implementation roadmap

| # | Task | Status |
|---|------|--------|
| 4.1 | Hard-won PASS rules (this doc) | ✅ draft |
| 4.2 | Schema + storage path (this doc) | ✅ draft |
| 4.3 | `success_store()` / `success_retrieve()` in `gcl_reflexion.py` | ✅ |
| 4.4 | `extract_success_pattern()` + `gcl_runner.py` PASS hook | ✅ |
| 4.5 | `gcl_reflexion_test.py` + `docs/success-patterns.md` report | ✅ |
| 4.6 | `memory_preflight.py` + `{{success_patterns}}` slot | ✅ |

---

## Quality gates (preview)

| ID | Check |
|----|-------|
| SP-1 | Ordinary PASS does not increment store size |
| SP-2 | HW-1 multi-iter trace produces exactly one dedup row per command_hash |
| SP-3 | `success_retrieve` returns ≤ `top_k`, sorted weighted |
| SP-4 | No secrets in stored `command_excerpt` / `hint` |
| SP-5 | `success_patterns.json` atomic write (same as `reflexion.json`) |

---

## Anti-patterns

| Banned | Why |
|--------|-----|
| Store every PASS | Noise; defeats token budget |
| LLM-generated hints at store time | Non-deterministic; audit risk |
| Critic reads `{{success_patterns}}` | Rubber-stamping / user-request leakage |
| Merge success into `reflexion.json` failure categories | Confuses Layer 2 failure analytics |
| Cross-skill success without R5 normalization | Premature; R5 owns generalization |
