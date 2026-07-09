# Runtime Harness Observability

## Local-first trace (canonical)

Every `skillopt_wrap()` / `harness_wrap()` invocation writes:

- `.runtime/traces/<skill-tag>/trace-*.json` — full input/output, spans, optional `memory_preflight`
- `.runtime/sessions/<skill-tag>/skillopt-session-*.json` — session index (filename legacy)

This happens **regardless** of `HARNESS_LANGFUSE_ENABLED` / `SKILLOPT_LANGFUSE_ENABLED`.

`trace_end` also calls `memory_store_lite` → Layer 1 JSONL (with `error_code` on allowlisted failures); allowlisted failures also invoke plan **B** → Layer 2 via `store-wrapper-lite` (see [memory-strategy.md](../../docs/memory-strategy.md)).

### TTL cleanup

| Variable | Default | Command |
|----------|---------|---------|
| `TRACE_KEEP_DAYS` | `7` | `make memory-maintain-apply` (L1 TTL + L2 maintain + `promote-from-memory`) |

```bash
make memory-maintain              # dry-run (L1 TTL + L2 maintain/prune + L1→L2 promote + traces)
GCL_REFLEXION_REPORT_ON_MAINTAIN=true make memory-maintain-apply
TRACE_KEEP_DAYS=14 make memory-maintain-apply
python3 alicloud-aiops-cruise/scripts/lib/runtime_cleanup.py --traces-only --apply
```

## Phase 1 — Prometheus (all product overlays)

Set in environment or wrapper:

```bash
export HARNESS_METRICS_DIR="/var/lib/node_exporter/textfile_collector"
export SKILLOPT_LOG_FORMAT="json"
```

Metrics exported by `skillopt_export_metrics()` in shared core to `skillopt_${SKILLOPT_SKILL_TAG}.prom`.

## Phase 2 — Langfuse (optional mirror)

Local trace is always written first. Langfuse only adds remote HTTP ingestion:

```bash
export HARNESS_LANGFUSE_ENABLED=true
export HARNESS_SESSION_ID="sess-workflow-$(date +%s)"
```

Full architecture: [docs/harness-observability-architecture.md](../../docs/harness-observability-architecture.md).
