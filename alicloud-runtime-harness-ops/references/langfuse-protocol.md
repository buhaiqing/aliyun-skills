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

## Trace Metadata — `invocation` Schema

Every trace (both local `.runtime/traces/` file and Langfuse mirror) carries an `invocation` block that identifies how the `aliyun` command was invoked.

### Local trace file (`trace-*.json`) — nested `invocation` object

```json
{
  "invocation": {
    "entrypoint": "wrapper" | "direct" | "gcl_runner",
    "wrapper": "<product>-harness-wrapper.sh | null",
    "wrapper_version": "<SKILLOPT_HARNESS_LIB_VERSION> | null",
    "raw_command": "<original argv> | null"
  }
}
```

| Field | Type | `wrapper` | `direct` | `gcl_runner` |
|-------|------|-----------|----------|--------------|
| `entrypoint` | string | `"wrapper"` | `"direct"` | `"gcl_runner"` |
| `wrapper` | string\|null | wrapper script name | `null` | `null` |
| `wrapper_version` | string\|null | harness lib version | `null` | `null` |
| `raw_command` | string\|null | `null` | original argv | `null` |

### Langfuse trace `metadata` — flattened fields

Langfuse mirrors the same signal as flat key-value pairs (no nested object):

| Langfuse metadata key | Value |
|----------------------|-------|
| `invocation_entrypoint` | `"wrapper"` / `"direct"` / `"gcl_runner"` |
| `invocation_wrapper` | wrapper script name, or `null` |

### Entrypoint values

| Value | Meaning |
|-------|---------|
| `wrapper` | `aliyun` call went through the product's `*-harness-wrapper.sh` (correct path) |
| `direct` | `require_skillopt_wrapper` guard rejected the call; trace emitted with `raw_command` preserved |
| `gcl_runner` | Invocation emitted by the GCL Runner itself |

### Audit

Use `scripts/audit-wrapper-coverage.sh <trace_dir>` to scan local traces for any `entrypoint != "wrapper"` or missing `invocation` block. See [AGENTS.md §15.8](../../AGENTS.md) for the mandatory wrapper-first enforcement rules.

See also [AGENTS.md §15.7](../../AGENTS.md) Langfuse lessons L1–L11.
