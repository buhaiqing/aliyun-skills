# Knowledge Base — FC Fault Patterns

## fault_pattern: fc_memory_oom

| Attribute | Value |
|-----------|-------|
| **Pattern** | FC-FUNC-001 — Function OOM (Out of Memory) |
| **Trigger metric** | `FunctionMaxMemoryUtilization` > 95% |
| **Symptom** | Function invocation fails; exit code indicates out of memory |
| **Impact** | Invocation failure, possible data loss for sync calls |
| **Root cause** | 1. Memory allocation too low 2. Memory leak in function 3. Large payload processing |
| **Diagnostic steps** | 1. Check `FunctionMaxMemoryUsageMB` vs configured `memorySize` 2. Check if memory trend is increasing over time (leak) 3. Check payload size |
| **Fix — temporary** | Increase `memorySize` to 2x current value |
| **Fix — permanent** | Profile function memory; fix leaks; use streaming for large payloads |
| **Prevention** | Set CloudMonitor alert: `FunctionMaxMemoryUtilization` > 80% |

## fault_pattern: fc_throttle_cascade

| Attribute | Value |
|-----------|-------|
| **Pattern** | FC-FUNC-002 — Concurrency Throttle Cascade |
| **Trigger metric** | `FunctionConcurrencyThrottles` > 0 AND rising |
| **Symptom** | 429 errors; invocations rejected; upstream services affected |
| **Impact** | Service degradation; timeout from calling services |
| **Root cause** | 1. Concurrency limit too low for load 2. Account limit reached 3. Traffic spike |
| **Diagnostic steps** | 1. Check `GetConcurrencyConfig` 2. Check account-level concurrency limit 3. Check if traffic is seasonal or sustained |
| **Fix — temporary** | Request concurrency quota increase |
| **Fix — permanent** | Set provisioned instances for baseline; optimize function to reduce per-invocation duration |
| **Prevention** | Track `FunctionInstanceCount` vs `maxConcurrency`; monitor traffic trends |

## fault_pattern: fc_cold_start_spike

| Attribute | Value |
|-----------|-------|
| **Pattern** | FC-FUNC-003 — Cold Start Latency Spike |
| **Trigger metric** | `FunctionP90Duration` >> `FunctionAvgDuration` (p90 > 5x avg) |
| **Symptom** | Periodic high latency for function invocations |
| **Impact** | User-facing latency spikes; SLA violations |
| **Root cause** | 1. Insufficient provisioned instances 2. Large code package 3. VPC binding ENI setup |
| **Diagnostic steps** | 1. Check cold vs warm duration ratio in CloudMonitor 2. Check code package size 3. Check VPC binding config |
| **Fix — temporary** | Set provisioned instances = 1 |
| **Fix — permanent** | Optimize code package (< 10MB); use layers; increase memory for faster init |
| **Prevention** | Set provisioned instances for latency-SLA functions |

## fault_pattern: fc_timeout_risk

| Attribute | Value |
|-----------|-------|
| **Pattern** | FC-FUNC-004 — Function Timeout Risk |
| **Trigger metric** | `FunctionMaxDuration` approaching configured timeout (≥ 80%) |
| **Symptom** | Function occasionally times out; partial results |
| **Impact** | Invocation failure; async retries exhaust |
| **Root cause** | 1. Downstream API slow 2. Large data processing 3. Infinite loop |
| **Diagnostic steps** | 1. Check timeout vs duration metrics 2. Check downstream service latency 3. Review function logs for slow operations |
| **Fix — temporary** | Increase timeout setting |
| **Fix — permanent** | Optimize code; add circuit breaker for downstream calls |
| **Prevention** | Set CloudMonitor alert: `FunctionMaxDuration` > 90% of timeout |

## fault_pattern: fc_async_retry_exhaust

| Attribute | Value |
|-----------|-------|
| **Pattern** | FC-FUNC-005 — Async Retry Exhaustion |
| **Trigger metric** | Async invocations failing after max retry attempts |
| **Symptom** | Async invocations silently discarded; no DLQ configured |
| **Impact** | Data loss for async events; unreliable event processing |
| **Root cause** | 1. `maximumRetryAttempts` too low 2. No DLQ configured 3. Downstream service unavailable |
| **Diagnostic steps** | 1. Check `GetAsyncInvokeConfig` 2. Check DLQ destination 3. Check downstream service health |
| **Fix — temporary** | Increase `maximumRetryAttempts` to 3; configure DLQ |
| **Fix — permanent** | Set DLQ (SNS/Log Service); implement retry logic in function code |
| **Prevention** | Configure `destination.onFailure` DLQ for all async functions |

## fault_pattern: fc_provision_waste

| Attribute | Value |
|-----------|-------|
| **Pattern** | FC-FUNC-006 — Idle Provisioned Instances |
| **Trigger metric** | `FunctionInstanceProvisionCount` > 0 AND `FunctionTotalInvocations` ≈ 0 (24h) |
| **Symptom** | Paying for unused provisioned capacity |
| **Impact** | Cost waste |
| **Root cause** | 1. Provisioned instances not scaled down 2. Deprecated function still provisioned |
| **Diagnostic steps** | 1. Check provisioned count 2. Check invocation count for 24h 3. Check if function is still used |
| **Fix — temporary** | Set provisioned `target: 0` |
| **Fix — permanent** | Automate provisioned scaling based on traffic patterns |
| **Prevention** | Run weekly idle function inspection |

## fault_pattern: fc_execution_role_expired

| Attribute | Value |
|-----------|-------|
| **Pattern** | FC-FUNC-007 — Execution Role/STS Expired |
| **Trigger metric** | `FunctionFunctionErrors` spike with `AccessDenied` |
| **Symptom** | Functions fail to access OSS/RDS/external resources |
| **Impact** | Complete function failure |
| **Root cause** | 1. RAM role revoked 2. STS expired 3. Policy changed |
| **Diagnostic steps** | 1. Check RAM role status 2. Check RAM policies 3. Check STS credentials |
| **Fix — immediate** | Verify and re-attach RAM policy |
| **Fix — permanent** | Use long-lived execution role (not temporary STS) |
| **Prevention** | Monitor `FunctionFunctionErrors` with `AccessDenied` pattern |