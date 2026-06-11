# Governance & Adversarial Review — alicloud-das-ops

## Adversarial Scenarios

### 1. Destructive without confirmation
| Operation | Safety Gate |
|-----------|-------------|
| `CreateKillInstanceSessionTask` | Session list presentation + user confirmation |
| `CreateSqlLimitTask` | SQL pattern + limit parameter confirmation |
| `SetAutoScalingConfig` | Warns about restart/connection flash + user confirmation |
| `AddHDMInstance` | Monitoring overhead warning (idempotent, no confirmation required) |

### 2. Credential echo
- No secret literals in any file
- `{{env.*}}` placeholders used correctly
- SDK examples use `os.Getenv` without printing values
- `printResponse` only prints API response body

### 3. API hallucination
- All operation IDs traceable to DAS 2020-01-16 OpenAPI
- Response field paths verified against OpenAPI Explorer
- Endpoint `das.cn-shanghai.aliyuncs.com` confirmed by official docs
- `aliyun` CLI unsupported claim verified by official integration docs

### 4. Idempotency gap
| Operation | Idempotent | Documented |
|-----------|------------|------------|
| `AddHDMInstance` | YES | YES |
| `CreateDiagnosticReport` | NO (creates new each time) | YES |
| `CreateCacheAnalysisJob` | NO (creates new each time) | YES |
| `CreateLatestDeadLockAnalysis` | NO (creates new each time) | YES |
| `CreateKillInstanceSessionTask` | NO (fire-and-forget) | YES |
| `CreateSqlLimitTask` | NO (creates new rule) | YES |
| `SetEventSubscription` | YES (overwrites) | YES |
| `SetAutoScalingConfig` | YES (overwrites) | YES |

### 5. Throttling blindness
- Exponential backoff documented for `Throttling` errors
- Poll intervals documented (minimum 5s)
- Max wait times documented to prevent infinite polling

### 6. Region drift
- No hardcoded region in user-facing logic
- `cn-shanghai` is DAS service requirement, not agent hardcoding
- `{{env.ALIBABA_CLOUD_REGION_ID}}` used for context

### 7. Error recovery gap
- All 5 documented error codes have recovery actions

### 8. Data safety gaps
- `GetDBInstanceConnectivityDiagnosis` warns against production admin passwords
- DAS Pro storage usage alerts prevent data loss
- Session kill requires explicit user confirmation

## Governance Checklist

- [x] All `{{env.*}}` placeholders use correct environment variable names
- [x] No secret literals in any generated file
- [x] SDK-only path documented with evidence
- [x] Safety gates present before destructive operations
- [x] Retry and timeout policies consistent
- [x] DAS standard response structure documented
- [x] Shared SDK client initialization pattern
- [x] Cross-product delegation rules documented
- [x] Engine support matrix documented in `integration.md`

## See Also

- [alicloud-skill-generator governance](../../alicloud-skill-generator/references/governance-and-adversarial-review.md)
- [Agent Skill OpenSpec](https://agentskills.io/specification)
