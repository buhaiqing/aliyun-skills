# API & Runtime — Runtime Harness Shared Framework

Runtime Harness is a **local runtime framework**, not an Alibaba Cloud OpenAPI product. This document maps shared runtime operations agents invoke.

> Internal function names remain `skillopt_*` until PR-10 symbol rename. User-facing config prefers `HARNESS_*` env / `--harness-*` CLI (PR-7).

## Entry Points

| Goal | Command / Function | Location |
|------|-------------------|----------|
| Integration test | `bash test-harness-integration.sh` | `alicloud-runtime-harness-ops/` |
| Multi-skill session test | `bash scripts/test-multi-skill-session.sh` | repo root |
| Product wrapper (preferred) | `./scripts/<product>-harness-wrapper.sh <action> [args]` | per product skill |
| Product wrapper (legacy) | `./scripts/<product>-skillopt-wrapper.sh <action> [args]` | shim → harness wrapper |
| Langfuse span ingest | `python3 scripts/harness_runtime.py` | shared (called by core lib) |

## Shared Core Functions

| Goal | Function | Notes |
|------|----------|-------|
| Initialize runtime | `skillopt_init()` | Loads env, validates Langfuse if enabled |
| Wrap CLI call | `skillopt_wrap()` / `harness_wrap()` | Overlay delegates here; handles trace + repair gate |
| Start trace | `skillopt_trace_start()` | Always writes local `trace-*.json`; mirrors to Langfuse when enabled |
| End trace | `skillopt_trace_end()` | Updates local trace; `memory_store_lite` → Layer 1; plan **B** → Layer 2 when allowlisted |
| Export metrics | `skillopt_export_metrics()` | Writes `.prom` textfile |
| Session init | `skillopt_session_init()` | Local session index; optional Langfuse session create |
| Report summary | `skillopt_report()` | Prints session stats |

## Path Resolution

```bash
# From product overlay — canonical source block
source "${_HARNESS_SHARED_ROOT}/scripts/harness-paths.sh"
source "${_HARNESS_SHARED_ROOT}/scripts/harness-core-lib.sh"
```

| Variable | Set By | Purpose |
|----------|--------|---------|
| `_HARNESS_RUNTIME_PY` / `_SKILLOPT_RUNTIME_PY` | `harness-paths.sh` | Absolute path to shared Python runtime |
| `_HARNESS_SHARED_ROOT` | overlay or env | `alicloud-runtime-harness-ops` directory |
| `SKILLOPT_SKILL_TAG` | overlay (required) | Full skill name, e.g. `alicloud-ecs-ops` |

## Langfuse Ingestion API

Base: `${LANGFUSE_HOST}/api/public/ingestion`

| Event Type | Purpose |
|------------|---------|
| `trace-create` | New trace per wrapper invocation |
| `span-create` | Flow span + repair/judgement spans |
| `trace-update` | Final output + severity metadata |

Each batch item MUST include top-level `id`, `type`, and `timestamp` (not only inside `body`).

## Environment Variables

| Variable (preferred) | Legacy alias | Default | Purpose |
|---------------------|--------------|---------|---------|
| `HARNESS_ENABLED` | `SKILLOPT_ENABLED` | `false` | Enable self-repair + optimization |
| `HARNESS_LANGFUSE_ENABLED` | `SKILLOPT_LANGFUSE_ENABLED` | `false` | Enable Langfuse remote mirror |
| `HARNESS_SESSION_ID` | `SKILLOPT_SESSION_ID` | auto | Multi-skill session correlation |
| `HARNESS_METRICS_DIR` | `SKILLOPT_METRICS_DIR` | — | Prometheus textfile export directory |
| `TRACE_KEEP_DAYS` | — | `7` | TTL for local trace JSON + session index |
| `SKILLOPT_CB_ENABLED` | — | `true` | Circuit breaker toggle |
| `SKILLOPT_CB_THRESHOLD` | — | `5` | Consecutive failures before open |

When both `HARNESS_*` and `SKILLOPT_*` are set, `HARNESS_*` wins (PR-7).

## Product Overlay Contract

Product `scripts/harness-lib.sh` MUST implement:

| Hook | Responsibility |
|------|----------------|
| `skillopt_repair_<pattern>()` | Product-specific error repair (read-only only) |
| `skillopt_optimize_params()` | Pre-execution parameter tuning |
| `skillopt_is_readonly_action()` | Gate repair on mutating commands |

See [Integration](integration.md) for wiring details.
