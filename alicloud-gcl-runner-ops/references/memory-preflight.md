# R2 Memory Pre-flight — Prompt Slot Protocol

> **Scope**: Platform-owned read path for the three-layer memory architecture.
> Product skills delegate to `alicloud-gcl-runner-ops`; do not duplicate retrieval logic in per-skill runbooks.

## Unified CLI

```bash
python3 alicloud-gcl-runner-ops/scripts/memory_preflight.py \
  --skill alicloud-ecs-ops \
  --operation DeleteInstance \
  --format slots
```

`gcl_runner.py` calls the same `preflight_retrieve()` before `run_loop()`, attaches results to
`trace["memory_preflight"]` and `trace["generator_prompt_with_memory"]` (Local-first P0 loop).
Disable with `--disable-memory-preflight` or `GCL_MEMORY_PREFLIGHT_ENABLED=false`.

## Prompt Slots

| Slot | Layer | Source | Default budget |
|------|-------|--------|----------------|
| `{{recent_executions}}` | 1 | `memory_retrieve(skill, op, top_k=3)` | 600 chars |
| `{{known_traps}}` | 2 | `reflexion_retrieve(skill, op, top_k=5)` | 800 chars |
| `{{strategy_hints}}` | 3 | `strategy_retrieve(skill, op)` | 800 chars |
| `{{success_patterns}}` | 2+ | `success_retrieve(skill, op, top_k=3)` | 600 chars |

Orchestrators inject these into the **Generator** prompt (not the Critic — Critic must not see raw user request per GCL anti-patterns).

> **R4–R6** (shipped): Success patterns — [success-patterns.md](success-patterns.md); cross-skill generalization — [cross-skill-patterns.md](cross-skill-patterns.md); remediation tracking — [remediation-tracking.md](remediation-tracking.md).

### Retrieval tiers (`reflexion_retrieve`)

| Tier | Categories | Notes |
|------|------------|-------|
| 0 | `cli_parameter`, `runtime`, `max_iter`, `near_miss` | Skill-specific |
| 1 | `generalized_cli` | R5: ≥3 skills share `normalized_key` |
| 2 | `cross_skill`, others | Orchestration / generic |

Remediated traps (R6) are deprioritized in ranking; `format_known_traps` may show `remediated=yes`.

When no data exists, slots render human-readable placeholders (not empty strings):

- `(none — no recent executions in Layer 1 memory)`
- `(none — no matching failure patterns in Reflexion memory)`
- `(none — strategy baseline not available)`
- `(none — no hard-won success patterns for this skill/operation)`

## Trace attachment

**GCL path**: Every GCL run persists retrieved hints under `trace["memory_preflight"]`.
When the skill ships `references/prompt-templates.md` §1 Generator, the runner also
fills memory slots into `trace["generator_prompt_with_memory"]` for LLM Orchestrators.

**Wrapper path (Local-first)**: Every `skillopt_wrap()` writes local `trace-*.json`
(canonical). `_skillopt_memory_preflight_r2()` merges the same R2 payload into
`trace["memory_preflight"]`. On failed allowlisted API errors, plan **B** writes
Layer 2 via `store-wrapper-lite` (see [`memory-strategy.md`](../../docs/memory-strategy.md)).
Langfuse, when enabled, mirrors the trace remotely only.

```json
{
  "version": "1.0.0",
  "skill": "alicloud-ecs-ops",
  "operation": "DeleteInstance",
  "empty": false,
  "recent_executions": [ ... ],
  "known_traps": [ ... ],
  "success_patterns": [ ... ],
  "strategy_hints": { ... },
  "slots": {
    "recent_executions": "...",
    "known_traps": "...",
    "success_patterns": "...",
    "strategy_hints": "..."
  }
}
```

When `references/prompt-templates.md` §1 exists, the trace also includes:

```json
{
  "generator_prompt_with_memory": "... filled Generator section with slots substituted ..."
}
```

## Generator template example

Add to `references/prompt-templates.md` §1 Generator:

```text
# Known failure patterns (Reflexion memory — do not repeat these mistakes)
{{known_traps}}

# Proven approaches (hard-won success patterns — prefer when applicable)
{{success_patterns}}

# Recent executions for this operation (Layer 1)
{{recent_executions}}

# Weekly strategy hints (Layer 3 — read-only)
{{strategy_hints}}
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GCL_MEMORY_PREFLIGHT_ENABLED` | `true` | Master switch in `gcl_runner.py` |
| `SKILLOPT_MEMORY_PREFLIGHT_ENABLED` | `true` | Master switch in `skillopt_wrap()` R2 hook |
| `GCL_KNOWN_TRAPS_MAX_CHARS` | `800` | Truncate `{{known_traps}}` |
| `GCL_STRATEGY_HINTS_MAX_CHARS` | `800` | Truncate `{{strategy_hints}}` |
| `GCL_RECENT_EXECUTIONS_MAX_CHARS` | `600` | Truncate `{{recent_executions}}` |
| `GCL_SUCCESS_PATTERNS_MAX_CHARS` | `600` | Truncate `{{success_patterns}}` |
| `GCL_REFLEXION_AUTO_REPORT` | `false` | Regenerate `failure-patterns.md` and `success-patterns.md` after each GCL run |
| `GCL_REFLEXION_REPORT_ON_MAINTAIN` | `false` | Regenerate both reports after `make memory-maintain-apply` |
| `GCL_REFLEXION_REPORT_SORT_BY` | `weighted` | Sort for maintain-time report: `weighted` \| `count` |
