# Core Concepts — Runtime Harness Shared Runtime

## What is Runtime Harness?

**Runtime Harness** is this repo's **cross-skill runtime framework** (not an Alibaba Cloud product API). It provides self-repair, dynamic parameter optimization, Langfuse distributed tracing, and Prometheus metrics for all `alicloud-*-ops` product skills.

> **Legacy name**: SkillOpt — internal symbols still use `skillopt_*` / `SKILLOPT_*` until PR-10. See [runtime-harness-glossary.md](../../docs/runtime-harness-glossary.md).

## Architecture (PR-8/9 canonical)

```
alicloud-[product]-ops/scripts/harness-lib.sh   ← product overlay (repair, wrap)
    │
    ├─ source alicloud-runtime-harness-ops/scripts/harness-paths.sh
    └─ source alicloud-runtime-harness-ops/scripts/harness-core-lib.sh
            ├─ skillopt_init / harness_init — log, metrics, circuit breaker
            └─ scripts/harness_runtime.py (Langfuse ingestion)
```

**Legacy compat**: product overlays may still `source skillopt-lib.sh` (symlink) and `*-skillopt-wrapper.sh` (shim); both delegate to harness paths above.

## Key Concepts

| Concept | Meaning |
|---------|---------|
| **Shared core** | `harness-core-lib.sh` — single copy in `alicloud-runtime-harness-ops` |
| **Product overlay** | Per-skill `harness-lib.sh` — product repair rules + `skillopt_wrap()` / `harness_wrap()` hooks |
| **Session** | `HARNESS_SESSION_ID` (preferred) or `SKILLOPT_SESSION_ID` — correlates traces across skills |
| **Trace** | One local JSON trace per wrapper call (`trace-*.json`); optional Langfuse mirror when enabled |
| **Circuit breaker** | Opens after consecutive failures; prevents request storms |
| **Runtime data** | `${SKILLS_DIR}/.runtime/metrics/<skill-tag>/*-skillopt-runtime.json` — error rates, repair counts |

## Lifecycle

### Wrapper Invocation Flow

1. **Init** — `skillopt_init()` loads env, resolves paths, validates Langfuse creds if enabled
2. **Trace start** — `skillopt_trace_start()` always writes local trace JSON; mirrors to Langfuse when enabled
3. **Execute** — `skillopt_wrap()` / `harness_wrap()` runs `aliyun` via overlay; captures output to `SKILLOPT_LAST_OUTPUT`
4. **Repair** (read-only only) — on failure, overlay applies product-specific fix and retries once
5. **Trace end** — `skillopt_trace_end()` persists output; exports metrics to `.prom` file
6. **Report** — `skillopt_report()` prints session summary

## Dependencies

| Dependency | Required | Purpose |
|------------|----------|---------|
| `ALIYUN_SKILLS_ROOT` | Yes | Resolve shared skill path |
| Bash 4+ | Yes | Array-safe expansion, `[[ ]]` |
| Python 3.10+ | Yes (Langfuse) | `harness_runtime.py` ingestion |
| `jq`, `curl` | Yes (Langfuse) | JSON parsing, HTTP ingestion |
| Langfuse credentials | Optional | Distributed tracing |
| Product `aliyun` CLI | Via overlay | Actual cloud API calls |

## Limits

| Limit | Default | Notes |
|-------|---------|-------|
| Max dynamic retries | 6 | Hard cap in core (float throttling prevention) |
| Circuit breaker threshold | Configurable | `SKILLOPT_CB_THRESHOLD` |
| Mutating command repair | Disabled | Read-only actions only (`Describe*`, `List*`, etc.) |
| Trace output size | Truncated | Large JSON responses truncated before Langfuse ingest |

## Related Docs

- [Integration](integration.md) — overlay wiring
- [Langfuse Protocol](langfuse-protocol.md) — L1–L11 rules
- [Observability](observability.md) — Prometheus + JSON logs
- [docs/harness-integration-guide.md](../../docs/harness-integration-guide.md) — full guide
