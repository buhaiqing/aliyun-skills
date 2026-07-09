# Idempotency Checklist — Auto Scaling (ESS)

> Version: 1.0.0 | Last Updated: 2026-06-07

## ClientToken Support

ESS supports `ClientToken` for idempotency on all write operations. Always generate UUID v4:

```bash
# Generate UUID v4
CLIENT_TOKEN=$(uuidgen)  # macOS
CLIENT_TOKEN=$(cat /proc/sys/kernel/random/uuid)  # Linux

# Use with API call
aliyun ess CreateScalingGroup \
  --ClientToken "$CLIENT_TOKEN" \
  --ScalingGroupName "my-group" \
  --MinSize 0 --MaxSize 10
```

## Operation Idempotency Table

| Operation | Idempotency Strategy | Duplicate Behavior |
|-----------|---------------------|-------------------|
| CreateScalingGroup | ClientToken | Returns same ScalingGroupId |
| ModifyScalingGroup | ClientToken | Applies changes once; subsequent calls no-op |
| DeleteScalingGroup | ClientToken | First call succeeds; duplicates return success |
| CreateScalingConfiguration | ClientToken | Returns same config ID |
| DeleteScalingConfiguration | ClientToken | First call succeeds; duplicates return success |
| CreateScalingRule | ClientToken | Returns same rule ID |
| DeleteScalingRule | ClientToken | First call succeeds; duplicates return success |
| CreateScheduledTask | ClientToken | Returns same task ID |
| DeleteScheduledTask | ClientToken | First call succeeds; duplicates return success |
| CreateLifecycleHook | ClientToken | Returns same hook ID |
| CompleteLifecycleAction | ClientToken | First call completes; duplicates ignored |
| AttachInstances | ClientToken | First call attaches; duplicates no-op |
| DetachInstances | ClientToken | First call detaches; duplicates return success |
| RemoveInstances | ClientToken | First call removes; duplicates return success |
| EnableScalingGroup | ClientToken | First call enables; duplicates no-op |
| DisableScalingGroup | ClientToken | First call disables; duplicates no-op |
| ExecuteScalingRule | ClientToken | Returns same ScalingActivityId; only executes once |
| StartInstanceRefresh | ClientToken | Returns same task ID; only starts once |
| TagResources | ClientToken | Applies tags idempotently |

## Retry Safety

| Operation | Safe to Retry? | Notes |
|-----------|---------------|-------|
| Describe* operations | ✅ Always | Read-only |
| Create* operations | ✅ With ClientToken | Without ClientToken → duplicate resources |
| Modify* operations | ✅ With ClientToken | Without → repeated modifications |
| Delete* operations | ✅ | Deletion is naturally idempotent |
| RemoveInstances | ✅ With ClientToken | Without → may remove additional instances |
| ExecuteScalingRule | ✅ With ClientToken | Without → multiple scaling activities |

## Retry Logic Template

```bash
# Safe retry with ClientToken
CLIENT_TOKEN=$(uuidgen)
MAX_RETRIES=3
RETRY_DELAY=5

for i in $(seq 1 $MAX_RETRIES); do
  aliyun ess CreateScalingGroup \
    --ClientToken "$CLIENT_TOKEN" \
    --ScalingGroupName "my-group" \
    --MinSize 0 --MaxSize 10 \
    --RegionId "$ALIBABA_CLOUD_REGION_ID" && break
  sleep $RETRY_DELAY
done
```

## Non-Idempotent Patterns (Avoid)

| Pattern | Risk | Safe Alternative |
|---------|------|-----------------|
| `CreateScalingGroup` without ClientToken | Duplicate groups | Always use ClientToken |
| `ExecuteScalingRule` in a retry loop without ClientToken | Multiple scaling events | Use same ClientToken |
| Repeated `AttachInstances` for same instance | Error (already attached) | Check instance status first |
| `RemoveInstances` in a loop without checking | Can remove more than intended | Verify count after each remove |