# Observability — FC 3.0 (Metrics → Logs → Traces)

## Architecture

```
    ┌────────────────┐
    │  FC Execution  │
    └───────┬────────┘
            │
    ┌───────┼────────┐
    │       │        │
    ▼       ▼        ▼
┌──────┐ ┌─────┐ ┌────────┐
│ CMS  │ │ SLS │ │ ARMS   │
│Metrics│ │Logs │ │Traces  │
└──────┘ └─────┘ └────────┘
```

## Metrics → Logs Linkage

| CMS Metric Anomaly | SLS Log Query | Purpose |
|-------------------|---------------|---------|
| `FunctionFunctionErrors` spike | `Level: ERROR` in function log | Identify specific error messages |
| `FunctionMaxDuration` timeout | `Level: WARN` + slow operations | Find long-running code paths |
| `FunctionMaxMemoryUsageMB` high | No direct SLS metric — use CloudMonitor | Memory leak investigation |
| `FunctionClientErrors` 429 rate spike | Invocation logs with 429 status | Identify throttled invocations |

## SLS Log Query for FC Functions

Function invocation logs are written to SLS by default. Sample queries:

```bash
# Via CLI / Console
* | select message, level, requestId, traceId from log where level >= 'WARN' limit 100

# Find error invocations
* | select requestId, message, level, functionName from log where level = 'ERROR' | limit 50

# Track cold start (init duration)
* | select functionName, coldStart, duration, requestId
  from log
  where coldStart = true
  | limit 100

# Find timeout-invocations
* | select requestId, functionName, duration, timeout, error
  from log
  where errorCode = 'Function.Timeout'
```

## Metrics → Traces Linkage

FC functions can integrate with ARMS (Application Real-Time Monitoring Service) for distributed tracing:

| FC Metric | ARMS Trace Query | Purpose |
|-----------|-----------------|---------|
| High `FunctionAvgDuration` | Trace by function name, sort by duration | Find slow spans within function |
| `FunctionFunctionErrors` | Trace with tag `error = true` | Trace error propagation across services |
| `FunctionClientErrors` | Trace by calling service | Find which caller is sending bad requests |

## Observability Best Practices

1. **Enable instance-level metrics**: Required for per-instance memory/CPU granularity
2. **Configure SLS log retention**: Default 7 days; extend to 30+ for audit
3. **Set up alert rules**: For each pattern in knowledge-base.md, create a CMS alert
4. **Use ARMS for distributed tracing**: Enable for functions calling other services
5. **Tag functions**: Include `env`, `service`, `version` for observability correlation