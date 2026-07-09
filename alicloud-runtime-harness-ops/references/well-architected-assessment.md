# Well-Architected Assessment — Runtime Harness Shared Runtime

Evaluates the Runtime Harness shared framework against Alibaba Cloud's
[Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).

## 安全 (Security)

| Requirement | Guidance |
|-------------|----------|
| **Credential handling** | Langfuse keys via env only; never log `LANGFUSE_SECRET_KEY` or cloud AccessKey secrets |
| **Trace sanitization** | `harness_runtime.py` truncates large outputs; no credential fields in trace payloads |
| **Mutating command protection** | Repair disabled for non-read-only actions — prevents double-execution side effects |
| **Wrapper-first enforcement** | `WRAPPER_BYPASS` (exit 6) alerts when agents skip harness wrapper |
| **Least privilege** | Product RAM policies scoped per skill; shared runtime needs no cloud API permissions |

## 稳定 (Stability)

| Requirement | Guidance |
|-------------|----------|
| **Circuit breaker** | Opens after `SKILLOPT_CB_THRESHOLD` consecutive failures; prevents request storms |
| **Retry cap** | Dynamic retries hard-capped at 6 |
| **Idempotent repair** | Read-only repair patterns only; mutating ops run once |
| **Graceful fallback** | Wrapper falls back to native `aliyun` if overlay lib missing |
| **Integration test** | `test-harness-integration.sh` validates path resolution + core sourcing |

## 成本 (Cost)

| Requirement | Guidance |
|-------------|----------|
| **Local runtime** | No cloud charges for Runtime Harness framework itself |
| **Langfuse hosting** | Self-hosted or cloud Langfuse — cost depends on trace volume |
| **Metrics export** | Prometheus textfile — zero additional cloud API calls |

## 效率 (Efficiency)

| Requirement | Guidance |
|-------------|----------|
| **Shared core (DRY)** | Single `harness-core-lib.sh` + `harness_runtime.py` for 36+ product skills |
| **Overlay pattern** | Product libs are thin stubs (~repair + optimize hooks) |
| **Session correlation** | One `HARNESS_SESSION_ID` spans multi-skill agent workflows |
| **Automated repair** | Known error patterns (Throttling, InvalidParameter) auto-fixed on read-only ops |

## 性能 (Performance)

| Metric | Source | Optimization |
|--------|--------|--------------|
| `skillopt_error_rate` | `.prom` textfile | Circuit breaker + dynamic retry tuning |
| `skillopt_repair_success` | runtime JSON | Track repair effectiveness per skill |
| `skillopt_circuit_breaker_state` | core lib | Monitor open/half-open states |
| Trace latency | Langfuse | Batch ingestion via `harness_runtime.py` |

---

*Five pillars: Security, Stability, Cost, Efficiency, Performance.*
