# R6 — Remediation Confirmation & Stability Tracking

> **Status**: 6.1–6.4 implemented (2026-06-21).
> **Owner**: `alicloud-gcl-runner-ops`
> **Related**: [success-patterns.md](success-patterns.md) (R4 positive baseline) · [memory-preflight.md](memory-preflight.md) (R2 trap injection) · [cross-skill-patterns.md](cross-skill-patterns.md) (R5)

## Problem

Layer 2 `{{known_traps}}` warns about recurring failures but cannot tell whether a trap is **still active** or **stably fixed**. Agents keep seeing high-count traps long after the team adopted the correct fix.

R6 closes the loop:

1. Preflight injects traps → count **opportunities** to apply the fix.
2. PASS after traps were shown → advance **consecutive success** streak.
3. **K** consecutive successes → `remediated=True` (deprioritized in retrieve).
4. Same failure recurs → **unmark** and increment `recent_failures`.

---

## 6.1 — Schema fields

Tracked categories: `cli_parameter`, `runtime`, `max_iter`, `near_miss`, `generalized_cli`.

| Field | Type | Meaning |
|-------|------|---------|
| `remediated` | bool | Trap considered stably fixed |
| `remediated_at` | string | ISO UTC when last confirmed |
| `total_opportunities` | int | Preflight showed this trap before an execution |
| `recent_failures` | int | Failures since last confirmation (relapse counter) |
| `consecutive_successes` | int | PASS streak while trap was in preflight |

Legacy rows backfill via `_ensure_remediation_fields()` on store/update.

---

## 6.2 — Dynamic confirmation window K

```python
remediation_confirm_window_k(pattern) -> int  # 2..5
```

| Signal (`count + total_opportunities`) | K |
|----------------------------------------|---|
| ≥ 20 | 5 |
| ≥ 10 | 4 |
| ≥ 5 | 3 |
| else | 2 |

High-frequency traps need more consecutive PASS evidence before deprioritization.

---

## 6.3 — Update hooks

| Event | Function | Behavior |
|-------|----------|----------|
| GCL run with `known_traps` | `remediation_record_opportunities()` | `total_opportunities++` per matched trap |
| GCL **PASS** with traps | `remediation_record_success_streak()` | `consecutive_successes++`; at K → `remediated=True` |
| Failure `reflexion_store` dedup hit | `remediation_record_failure_event()` | reset streak; `recent_failures++`; clear `remediated` |
| `gcl_runner.py` main | `remediation_apply_from_trace(trace)` | orchestrates opportunities + PASS streak |

Retrieve: remediated rows use score × `REMEDIATION_SCORE_PENALTY` (0.35). `format_known_traps` annotates `remediated=yes`.

---

## Roadmap

| # | Task | Status |
|---|------|--------|
| 6.1 | Schema fields on tracked categories | ✅ |
| 6.2 | Dynamic K from frequency | ✅ |
| 6.3 | Confirm / unmark loop + runner hook | ✅ |
| 6.4 | `RemediationTests` | ✅ |

---

## Quality gates

| ID | Check |
|----|-------|
| RM-1 | K successes after trap-informed PASS → `remediated=True` |
| RM-2 | Recurring failure → `remediated=False`, streak reset |
| RM-3 | Remediated patterns rank below active traps in retrieve |
| RM-4 | `total_opportunities` increments only when traps were injected |
