# Troubleshooting — PTS

> Version: 1.0.0 | Last Updated: 2026-06-16

## Error Taxonomy

| Error Code | Type | Agent Action | Max Retries |
|------------|------|-------------|-------------|
| `CreateSceneFail` | Business | Fix Scene JSON; verify required fields | 1 |
| `ListPtsSceneFail` | Business | Shorten `--key-word` to ≤30 chars | 1 |
| `InvalidParameter` | Config | Align with OpenAPI; check URL/RPS ranges | 1 |
| `MissingParameter` | Config | Add required `--scene-id` / pagination | 0 |
| `SceneNotFound` | Config | HALT — verify SceneId via `list-pts-scene` | 0 |
| `SceneStatusError` | State | HALT — stop running scene before modify/delete | 0 |
| `SceneAlreadyRunning` | Conflict | `stop-pts-scene` then retry | 1 |
| `ReportNotFound` | Config | HALT — list reports for scene | 0 |
| `Forbidden` / `NoPermission` | IAM | HALT — add `pts:*` or scoped policy | 0 |
| `Throttling.User` | Throttle | RETRY — exponential backoff | 3 |
| `InternalError` | Server | RETRY — 2s, 4s, 8s; capture RequestId | 3 |
| `ServiceUnavailable` | Server | RETRY — 5s, 10s, 20s | 3 |
| `InsufficientBalance` | Billing | HALT — recharge account | 0 |
| `QuotaExceeded` | Quota | HALT — reduce agents/RPS or request quota | 0 |
| `VpcConfigError` | Network | Fix VPC binding; delegate `alicloud-vpc-ops` | 0 |
| `TargetConnectTimeout` | Network | Check URL, SG, SLB health | 0 |
| `AgentResourceInsufficient` | Quota | Reduce `agentCount` | 1 |
| `DebugTimeout` | Runtime | Increase timeout; fix target availability | 1 |
| `InvalidSceneJson` | Business | Validate JSON with `jq .` before submit | 1 |
| `BaselineNotFound` | Config | Create baseline from report first | 0 |

## Diagnostic Process

### Step 1: Classify Failure Phase

| Phase | Symptom | First Command |
|-------|---------|---------------|
| Create/Save | 400 + Message about Scene JSON | Validate JSON structure |
| Debug | No sample logs | `get-pts-debug-sample-logs` |
| Start | Immediate failure | `get-pts-scene-running-status` |
| Running | High error rate | `get-pts-scene-running-data` |
| Report | Empty metrics | Confirm test reached `Finished` |

### Step 2: Scene State Check

```bash
aliyun pts get-pts-scene --scene-id "{{scene_id}}" --region "${ALIBABA_CLOUD_REGION_ID}"
aliyun pts get-pts-scene-running-status --scene-id "{{scene_id}}" --region "${ALIBABA_CLOUD_REGION_ID}"
```

### Step 3: Network Path (Intranet Targets)

```bash
aliyun pts get-user-vpcs --region "${ALIBABA_CLOUD_REGION_ID}"
# Verify target reachable from PTS VPC — delegate SLB/ECS health checks
```

### Step 4: Target Service Correlation

If PTS reports success but latency high → delegate to target product skill (RDS, Redis, SLB).

## Common Scenarios

### Scenario 1: Scene Won't Start

**Causes:** Already `Running`; invalid `LoadConfig`; quota; unpaid account.

**Resolution:**
1. `get-pts-scene-running-status` — stop if active
2. `start-debug-pts-scene` — isolate config vs capacity issue
3. Reduce `agentCount` and `allRpsLimit`; retry

### Scenario 2: High Error Rate During Test

**Causes:** Target overload; wrong checkpoint; auth headers missing; rate limiting on target.

**Resolution:**
1. `stop-pts-scene` if production impact
2. Review `relationList[].apiList[].headerList` and checkpoints
3. Lower RPS; fix target capacity (ECS/SLB scaling)

### Scenario 3: CreatePtsScene JSON Rejected

**Message:** "创建或者修改场景入参必须是实体类Scene的JSON串"

**Resolution:**
- Ensure top-level keys match OpenAPI `Scene` entity
- Use `save-pts-scene --help` for nested structure reference
- Test with minimal scene (single GET URL) first

### Scenario 4: Keyword Search Fails

**Error:** `ListPtsSceneFail` — keyword length

**Resolution:** `--key-word` max 30 characters; use exact `SceneId` for precision.

## Escalation Checklist

- [ ] `RequestId` captured from failed response
- [ ] SceneId + region documented
- [ ] Target URL and environment (prod/staging) noted
- [ ] Last successful debug log attached
