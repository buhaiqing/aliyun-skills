# Langfuse Protocol (Shared Runtime)

Canonical implementation: `scripts/harness-core-lib.sh` + `scripts/harness_runtime.py` in `alicloud-runtime-harness-ops`.

Legacy shims: `alicloud-skillopt-ops/scripts/skillopt-{core-lib,paths}.sh` delegate to the above.

## Key Rules

0. **Local-first**: every `skillopt_wrap()` writes `${SKILLS_DIR}/.runtime/traces/<skill-tag>/trace-*.json`; Langfuse HTTP is an optional mirror when `HARNESS_LANGFUSE_ENABLED=true` (or legacy `SKILLOPT_LANGFUSE_ENABLED=true`).
1. `SKILLOPT_SKILL_TAG` MUST be full skill name (`alicloud-ecs-ops`).
2. Load repo `.env` with `while read ... || [[ -n "$line" ]]` (no `source .env` alone).
3. Trace name: `${SKILLOPT_SKILL_TAG} ${product} ${action}`.
4. On trace failure: set `metadata.trace_display_severity=ERROR` + `skillopt.trace_judgement` span.
5. `skillopt_trace_start` uses `SKILLOPT_REMAINING` params, not raw `$@` (avoids jq flag injection).

## Validation

```bash
cd alicloud-runtime-harness-ops
./test-harness-integration.sh
```

See also [AGENTS.md §15.7](../../AGENTS.md) Langfuse lessons L1–L11.
