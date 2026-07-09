# Polling Patterns — DTS (`aliyun dts`)

## Generic Polling Templates

### DTS task status until target (`DescribeDtsJobDetail`)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun dts DescribeDtsJobDetail \
    --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
    --DtsJobId "{{user.dts_job_id}}" | jq -r '.Status')
  echo "Status: $STATUS"
  [ "$STATUS" = "{{target_status}}" ] && break
  [ "$STATUS" = "Failed" ] && { echo "❌ Task failed"; break; }
  sleep {{interval}}
done
[ "$STATUS" = "{{target_status}}" ] || { echo "TIMEOUT"; exit 1; }
```

### DTS task migration/sync completion (`Migrating` / `Synchronizing` / `Finished`)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun dts DescribeDtsJobDetail \
    --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
    --DtsJobId "{{user.dts_job_id}}" | jq -r '.Status')
  echo "Status: $STATUS"
  [ "$STATUS" = "Migrating" ] || [ "$STATUS" = "Synchronizing" ] && break
  [ "$STATUS" = "Finished" ] && { echo "✅ Task completed"; break; }
  [ "$STATUS" = "Failed" ] && { echo "❌ Task failed"; break; }
  sleep {{interval}}
done
```

### Polling until deletion confirmed (resource no longer found)

```bash
for i in $(seq 1 {{max_retries}}); do
  RESULT=$(aliyun dts DescribeDtsJobDetail \
    --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
    --DtsJobId "{{user.dts_job_id}}" 2>&1)
  if echo "$RESULT" | grep -q "InvalidJobName\|JobNotFound\|not found"; then
    break
  fi
  sleep {{interval}}
done
```

## Per-Operation Polling Parameters

| Operation | Describe Command | Extra Params | Target Status | Interval | Max Retries |
|-----------|-----------------|--------------|---------------|----------|-------------|
| ConfigureDtsJob (Migration) | DescribeDtsJobDetail | `{{output.dts_job_id}}` | `Migrating` / `Synchronizing` / `Finished` | 10s | 60 |
| ConfigureDtsJob (Sync) | DescribeDtsJobDetail | `{{output.dts_job_id}}` | `Synchronizing` | 10s | 60 |
| ConfigureDtsJob (Subscribe) | DescribeDtsJobDetail | `{{output.dts_job_id}}` | `Subscribe` | 10s | 60 |
| StartDtsJob | DescribeDtsJobDetail | `{{user.dts_job_id}}` | `Migrating` / `Synchronizing` | 10s | 30 |
| StopDtsJob | DescribeDtsJobDetail | `{{user.dts_job_id}}` | `Stopped` | 10s | 30 |
| SuspendDtsJob | DescribeDtsJobDetail | `{{user.dts_job_id}}` | `Suspended` | 10s | 30 |
| ResetDtsJob | DescribeDtsJobDetail | `{{user.dts_job_id}}` | `NotStarted` | 10s | 30 |
| DeleteDtsJob | DescribeDtsJobDetail | `{{user.dts_job_id}}` | `JobNotFound` (error) | 10s | 20 |

> **State Transitions** (interval / max wait budgets) remain in `SKILL.md` § Execution Flows.