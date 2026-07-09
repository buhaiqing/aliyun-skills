# Troubleshooting — Runtime Harness Shared Runtime

## Common Error Codes

| Code / Symptom | Meaning | Agent Action |
|----------------|---------|--------------|
| `SkillOpt runtime not found` | `_HARNESS_RUNTIME_PY` / `_SKILLOPT_RUNTIME_PY` missing | Set `ALIYUN_SKILLS_ROOT`; verify `alicloud-runtime-harness-ops/scripts/harness_runtime.py` exists |
| `source harness-paths.sh before harness-core-lib.sh` | Wrong source order | Source `harness-paths.sh` first in overlay |
| `LANGFUSE_* is not set` | Langfuse enabled but creds missing | Configure `.env` or disable `HARNESS_LANGFUSE_ENABLED` |
| `exit_code_6` / `WRAPPER_BYPASS` | Direct `aliyun` bypass detected | Use `*-harness-wrapper.sh`; see AGENTS.md §15.8 |
| `Throttling` / 429 | Cloud API rate limit | Harness backs off; wait and retry |
| `InvalidParameter` / 400 | CLI parameter format wrong | Run `aliyun <product> <action> --help`; fix RepeatList/JSON format |
| `Forbidden.RAM` / 403 | Insufficient RAM permissions | Add product-specific RAM policy |
| Circuit breaker open | Consecutive failures exceeded threshold | Check underlying API errors; reset via new session |
| Empty Langfuse output | `SKILLOPT_LAST_OUTPUT` not captured | Ensure disabled branch uses `skillopt_run_aliyun`, not direct `aliyun` |
| HTTP 207 (Langfuse) | Partial ingestion failure | Verify batch items have top-level `id` + `timestamp` |
| Trace not visible in Langfuse UI | Pagination / wrong lookup | Query `/api/public/traces/{trace_id}` directly, not list page |
| `jq: invalid JSON` | Metadata default `\{\}` | Use `local metadata="${3:-{}}"` in trace helpers |
| zsh `export -f` error | Bash-only function export | Guard with `if [ -n "$BASH_VERSION" ]` |

## Diagnostic Order

1. **Verify shared core exists**: `test -f alicloud-runtime-harness-ops/scripts/harness-core-lib.sh`
2. **Check path resolution**: `source harness-paths.sh`; echo `$_HARNESS_RUNTIME_PY`
3. **Run integration test**: `export ALIYUN_SKILLS_ROOT="$PWD" && bash alicloud-runtime-harness-ops/test-harness-integration.sh`
4. **Check wrapper**: Product wrapper must source `harness-lib.sh` (or legacy `skillopt-lib.sh` symlink), not a local copy of `harness_runtime.py`
5. **Validate Langfuse** (if enabled): Direct trace lookup by ID after wrapper run
6. **Inspect local trace JSON**: `${SKILLS_DIR}/.runtime/traces/<skill-tag>/trace-*.json` (legacy: `alicloud-*/.runtime/traces/`)
7. **Trace TTL cleanup**: `make memory-maintain-apply` (default 7d, `TRACE_KEEP_DAYS`)

## Common Issues

### Shared core not found

```bash
export ALIYUN_SKILLS_ROOT="$(git rev-parse --show-toplevel)"
test -f "$ALIYUN_SKILLS_ROOT/alicloud-runtime-harness-ops/scripts/harness-core-lib.sh"
```

### Langfuse trace missing output

Root cause: `skillopt_wrap()` disabled branch calling `aliyun` directly instead of `skillopt_run_aliyun`. See AGENTS.md §15.9.

### Multi-skill session mismatch

- Set explicit `HARNESS_SESSION_ID` (or `SKILLOPT_SESSION_ID`) before each wrapper call
- Validate with `bash scripts/test-multi-skill-session.sh --local`

### Repair not triggering

- Repair only runs for read-only actions (`Describe*`, `List*`, `Get*`, `Query*`)
- Mutating commands (`Delete*`, `Put*`, `Create*`) execute exactly once — by design

### Metrics not exported

- Set `HARNESS_METRICS_DIR` / `SKILLOPT_METRICS_DIR` to node_exporter textfile collector path
- Verify `skillopt_${SKILLOPT_SKILL_TAG}.prom` appears after wrapper run

## Getting Help

- [Integration Guide](../../docs/harness-integration-guide.md)
- [Observability Architecture](../../docs/harness-observability-architecture.md)
- [Langfuse Protocol](langfuse-protocol.md)
