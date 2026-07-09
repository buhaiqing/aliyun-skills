# Idempotency Checklist — DTS (Data Transmission Service)

## Why Idempotency Matters for DTS

DTS operations involve paid resources and data flows. Duplicate executions can cause:
- Multiple DTS instances (billing waste)
- Duplicate tasks with same configuration
- Overlapping data sync causing integrity issues

## Operation Idempotency

| Operation | Idempotent? | Mechanism | Retry Safe? |
|-----------|-------------|-----------|-------------|
| CreateDtsInstance | ❌ Not idempotent | Each call creates a new instance; no client token support | No — duplicates cause billing |
| ConfigureDtsJob | ⚠️ Conditional | Same job name + same endpoints → `InvalidJobName.Duplicate` | Check existence via DescribeDtsJobs first |
| StartDtsJob | ✅ Idempotent | Starting an already-running task returns success | Yes |
| StopDtsJob | ✅ Idempotent | Stopping an already-stopped task returns success | Yes |
| SuspendDtsJob | ✅ Idempotent | Suspending an already-suspended task returns success | Yes |
| DeleteDtsJob | ✅ Idempotent | Deleting an already-deleted task returns success (or NotFound) | Yes |
| ResetDtsJob | ❌ Destructive | Each reset clears progress irreversibly | No — confirm before retry |
| DescribeDtsJobs | ✅ Idempotent | Read-only | Yes |
| DescribeDtsJobDetail | ✅ Idempotent | Read-only | Yes |
| DescribeConnectionStatus | ✅ Idempotent | Read-only (no side effects) | Yes |
| ModifyDtsJobName | ⚠️ Conditional | Idempotent for same name; duplicate name causes error | Check new name uniqueness |
| ModifyDtsJobDuLimit | ✅ Idempotent | Setting same DU limit returns success | Yes |
| CreateConsumerChannel | ❌ Not idempotent | Each call creates a new consumer group | No — check existence first |
| ModifyConsumerChannel | ✅ Idempotent | Idempotent for same channel config | Yes |
| DeleteConsumerChannel | ✅ Idempotent | Deleting an already-deleted channel succeeds | Yes |
| RenewInstance | ❌ Not idempotent | Each call may extend subscription by 1 period | Check remaining period first |
| TransferPayType | ❌ Not idempotent | Billing model change is single-shot | Check current pay type first |

## Idempotent Operation Patterns

### Pattern 1: Check-Then-Create (DTS Instance)

```bash
# Check if a suitable DTS instance already exists
EXISTING=$(aliyun dts DescribeDtsJobs \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --Type migration \
  --Status NotStarted | jq '.DtsJobList | length')

if [ "$EXISTING" -eq 0 ]; then
  # Create only if none found
  aliyun dts CreateDtsInstance \
    --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
    --Type migration --PayType PostPaid \
    --SourceRegionId "{{user.source_region}}" \
    --DestinationRegionId "{{user.target_region}}"
else
  echo "⚠️ DTS instance already exists. Reusing existing."
fi
```

### Pattern 2: Check-Then-Configure (DTS Job)

```bash
# Check if job with same name already exists
JOB=$(aliyun dts DescribeDtsJobs \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --Type migration | jq --arg NAME "migrate-job" \
  '.DtsJobList[] | select(.DtsJobName == $NAME) | .DtsJobId' -r)

if [ -z "$JOB" ]; then
  # Configure only if job doesn't exist with same name
  aliyun dts ConfigureDtsJob --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} ...
else
  echo "ℹ️ Job $JOB already exists with this name. Skipping create."
fi
```

### Pattern 3: Idempotent Delete

```bash
# Delete is idempotent — safe to call even if already deleted
aliyun dts DeleteDtsJob \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}" || echo "ℹ️ Job already deleted or not found"
```

### Pattern 4: Idempotent Modify (DU Limit)

```bash
# Setting same DU limit is idempotent
CURRENT_DU=$(aliyun dts DescribeDtsJobDetail \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}" | jq -r '.DuLimit // 1')

if [ "$CURRENT_DU" != "{{user.desired_du}}" ]; then
  aliyun dts ModifyDtsJobDuLimit \
    --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
    --DtsJobId "{{user.dts_job_id}}" \
    --DuLimit "{{user.desired_du}}"
fi
```

## Retry Safety Matrix

| Error Type | Can Retry? | Retry Mechanism | Max Retries |
|-----------|------------|----------------|-------------|
| Throttling (429) | ✅ Yes | Exponential backoff | 3 |
| InternalError (5xx) | ⚠️ Conditional | Check idempotency table first | 3 |
| InvalidParameter | ❌ No | Fix parameter first | 0 |
| QuotaExceeded | ❌ No | HALT — request quota increase | 0 |
| PrecheckFailed | ⚠️ Conditional | Fix precheck items; retry StartDtsJob | 2 |
| JobExecutionException | ⚠️ Conditional | Diagnose root cause; retry StartDtsJob | 2 |
| CreateDtsInstance duplicate | ❌ No | Check existence first | 0 |
| Network timeout | ✅ Yes | Exponential backoff | 3 |