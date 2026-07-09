# Polling Patterns — MongoDB (`aliyun dds`)

## Generic Polling Templates

### Instance status until target (`DBInstanceStatus`)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun dds DescribeDBInstanceAttribute \
    --DBInstanceId "{{user.db_instance_id}}" \
    --output cols=DBInstanceStatus rows=DBInstances.DBInstance[0].DBInstanceStatus)
  [ "$STATUS" = "{{target_status}}" ] && break
  sleep {{interval}}
done
[ "$STATUS" = "{{target_status}}" ] || { echo "TIMEOUT"; exit 1; }
```

### Instance absence after delete (`TotalRecordCount=0`)

```bash
for i in $(seq 1 {{max_retries}}); do
  RESULT=$(aliyun dds DescribeDBInstances \
    --RegionId "{{user.region}}" \
    --DBInstanceId "{{user.db_instance_id}}" \
    --output cols=TotalRecordCount rows=TotalRecordCount)
  [ "$RESULT" = "0" ] && break
  sleep {{interval}}
done
```

> **Go SDK** status wait helper: [api-sdk-usage.md § Instance Status Validation](api-sdk-usage.md#instance-status-validation).

## Per-Operation Polling Parameters

| Operation | Describe Command | Extra Params | Target | Interval | Max Retries |
|-----------|-----------------|--------------|--------|----------|-------------|
| CreateDBInstance | DescribeDBInstanceAttribute | `{{output.db_instance_id}}` | `Running` | 10s | 60 |
| RestartDBInstance | DescribeDBInstanceAttribute | — | `Running` | 10s | 30 |
| ModifyDBInstanceSpec | DescribeDBInstanceAttribute | — | `Running` | 10s | 60 |
| DeleteDBInstance | DescribeDBInstances | `--RegionId` required | `TotalRecordCount=0` | 10s | 30 |
| AddShard (sharding) | DescribeDBInstanceAttribute | — | `Running` | 10s | 60 |

> **State Transitions** (interval / max wait budgets) remain in `SKILL.md` § Instance Lifecycle.
