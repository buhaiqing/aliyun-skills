# Governance & Adversarial Review — alicloud-das-ops

## Purpose

This document provides an adversarial review framework for the DAS operations
skill, catching destructive-action shortcuts, credential leaks, API
hallucination, and idempotency gaps before merge or execution.

## Adversarial Scenarios

### 1. Destructive without confirmation

| Operation | Safety Gate Present | Verdict |
|-----------|---------------------|---------|
| `CreateKillInstanceSessionTask` | YES — requires session list presentation + user confirmation | PASS |
| `CreateSqlLimitTask` | YES — requires SQL pattern + limit parameter confirmation | PASS |
| `SetAutoScalingConfig` | YES — warns about restart/connection flash + user confirmation | PASS |
| `AddHDMInstance` | PARTIAL — warns about monitoring overhead; no confirmation required because registration is non-destructive and idempotent | PASS |

### 2. Credential echo

| Check | Verdict |
|-------|---------|
| No secret literals in any generated file | PASS |
| `{{env.*}}` placeholders used correctly | PASS |
| SDK examples use `os.Getenv` without printing values | PASS |
| `printResponse` only prints API response body, never credentials | PASS |

### 3. API hallucination

| Check | Verdict |
|-------|---------|
| All operation IDs traceable to DAS 2020-01-16 OpenAPI | PASS |
| Response field paths verified against OpenAPI Explorer | PASS |
| Endpoint `das.cn-shanghai.aliyuncs.com` confirmed by official docs | PASS |
| `aliyun` CLI unsupported claim verified by official integration docs | PASS |

### 4. Idempotency gap

| Operation | Idempotent | Documented | Verdict |
|-----------|------------|------------|---------|
| `AddHDMInstance` | YES | YES | PASS |
| `CreateDiagnosticReport` | NO (creates new report each time) | YES | PASS |
| `CreateCacheAnalysisJob` | NO (creates new job each time) | YES | PASS |
| `CreateLatestDeadLockAnalysis` | NO (creates new analysis each time) | YES | PASS |
| `CreateKillInstanceSessionTask` | NO (fire-and-forget) | YES | PASS |
| `CreateSqlLimitTask` | NO (creates new rule) | YES | PASS |
| `SetEventSubscription` | YES (overwrites settings) | YES | PASS |
| `SetAutoScalingConfig` | YES (overwrites config) | YES | PASS |

### 5. Throttling blindness

| Check | Verdict |
|-------|---------|
| Exponential backoff documented for `Throttling` errors | PASS |
| Poll intervals documented (minimum 5s) | PASS |
| Max wait times documented to prevent infinite polling | PASS |

### 6. Region drift

| Check | Verdict |
|-------|---------|
| No hardcoded region in user-facing logic | PASS |
| `cn-shanghai` is DAS service requirement, not agent hardcoding | PASS |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` used for context | PASS |

### 7. Error recovery gap

| Error Code | Recovery Documented | Verdict |
|------------|---------------------|---------|
| `InvalidDBInstanceId.NotFound` | YES | PASS |
| `InvalidParameter` | YES | PASS |
| `OperationDenied.InstanceStatus` | YES | PASS |
| `Throttling` | YES | PASS |
| `InsufficientBalance` | YES | PASS |

### 8. Data safety gaps

| Check | Verdict |
|-------|---------|
| `GetDBInstanceConnectivityDiagnosis` warns against using production admin passwords | PASS |
| DAS Pro storage usage alerts prevent data loss from quota exhaustion | PASS |
| Session kill requires explicit user confirmation | PASS |

## Governance Checklist

- [x] All `{{env.*}}` placeholders use correct environment variable names
- [x] No secret literals in any generated file
- [x] SDK-only path documented with evidence (CLI does not support DAS)
- [x] Safety gates present before destructive operations
- [x] Retry and timeout policies consistent across operations
- [x] DAS standard response structure (`Code`, `Message`, `RequestId`, `Data`, `Success`) documented
- [x] Shared SDK client initialization pattern reduces code duplication
- [x] Cross-product delegation rules documented
- [x] Engine support matrix documented in `integration.md`

## See Also

- [alicloud-skill-generator governance](../alicloud-skill-generator/references/governance-and-adversarial-review.md)
- [Agent Skill OpenSpec](https://agentskills.io/specification)
