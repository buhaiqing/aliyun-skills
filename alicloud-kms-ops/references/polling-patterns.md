# Polling Patterns — Key Management Service (KMS, `aliyun kms`)

> KMS 状态变更极快（DisableKey/EnableKey/ScheduleKeyDeletion 通常 1s 内生效）。
> 所有轮询模板取自 `DescribeKey` 的 `KeyState` 字段。

## Generic Polling Templates

### Key state until desired

```bash
for i in $(seq 1 {{max_retries}}); do
  STATE=$(aliyun kms DescribeKey --KeyId "{{user.key_id}}" --RegionId "{{user.region}}" | jq -r '.Key.KeyState')
  [ "$STATE" = "{{desired_state}}" ] && break
  sleep {{interval}}
done
[ "$STATE" = "{{desired_state}}" ] || { echo "TIMEOUT state=$STATE"; exit 1; }
```

## Per-Operation Polling Parameters

| Operation | Describe Command | Field | Target | Interval | Max Retries |
|-----------|-----------------|-------|--------|----------|-------------|
| DisableKey | DescribeKey | `Key.KeyState` | `Disabled` | 1s | 15 |
| EnableKey | DescribeKey | `Key.KeyState` | `Enabled` | 1s | 15 |
| ScheduleKeyDeletion | DescribeKey | `Key.KeyState` | `PendingDeletion` | 5s | 12 |

> See [core-concepts.md](core-concepts.md) for key lifecycle states and PendingWindowInDays constraints.
