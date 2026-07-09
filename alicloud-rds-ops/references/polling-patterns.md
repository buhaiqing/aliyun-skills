# Polling Patterns — RDS

## Generic Polling Templates

### Status until target (instance / account / database / backup)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun rds {{describe_command}} \
    --RegionId "{{user.region}}" \
    {{extra_params}} \
    --output cols={{status_field}} rows={{status_path}})
  [ "$STATUS" = "{{target_status}}" ] && break
  sleep {{interval}}
done
[ "$STATUS" = "{{target_status}}" ] || { echo "TIMEOUT"; exit 1; }
```

### Resource absence (`TotalRecordCount=0`)

```bash
for i in $(seq 1 {{max_retries}}); do
  RESULT=$(aliyun rds {{describe_command}} \
    --RegionId "{{user.region}}" \
    {{extra_params}} \
    --output cols=TotalRecordCount rows=TotalRecordCount)
  [ "$RESULT" = "0" ] && break
  sleep {{interval}}
done
```

### Engine version upgrade (status + version)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun rds DescribeDBInstances \
    --RegionId "{{user.region}}" \
    --DBInstanceId "{{user.db_instance_id}}" \
    --output cols=DBInstanceStatus,EngineVersion rows=Items.DBInstance[0].{DBInstanceStatus,EngineVersion})
  echo "$STATUS" | grep -q "Running" && echo "$STATUS" | grep -q "{{user.engine_version}}" && break
  sleep {{interval}}
done
```

## Per-Operation Polling Parameters

| Operation | Describe Command | Extra Params | Status Field / Path | Target | Interval | Max Retries |
|-----------|-----------------|-------------|---------------------|--------|----------|-------------|
| CreateDBInstance | DescribeDBInstances | `--DBInstanceId "{{output.db_instance_id}}"` | `DBInstanceStatus` / `Items.DBInstance[0].DBInstanceStatus` | `Running` | 10s | 60 |
| RestartDBInstance | DescribeDBInstances | `--DBInstanceId "{{user.db_instance_id}}"` | `DBInstanceStatus` / `Items.DBInstance[0].DBInstanceStatus` | `Running` | 10s | 30 |
| DeleteDBInstance | DescribeDBInstances | `--DBInstanceId "{{user.db_instance_id}}"` | `TotalRecordCount` | `0` | 10s | 30 |
| CreateAccount | DescribeAccounts | `--AccountName "{{user.account_name}}"` | `AccountStatus` / `Accounts.DBInstanceAccount[0].AccountStatus` | `Available` | 5s | 24 |
| DeleteAccount | DescribeAccounts | `--AccountName "{{user.account_name}}"` | `TotalRecordCount` | `0` | 5s | 12 |
| CreateDatabase | DescribeDatabases | `--DBName "{{user.db_name}}"` | `DBStatus` / `Databases.Database[0].DBStatus` | `Running` | 5s | 24 |
| DeleteDatabase | DescribeDatabases | `--DBName "{{user.db_name}}"` | `TotalRecordCount` | `0` | 5s | 12 |
| CreateBackup | DescribeBackups | time window params | `BackupStatus` / `Items.Backup[0].BackupStatus` | `Success` | 10s | 60 |
| RestoreDBInstance | DescribeDBInstances | `--DBInstanceId "{{user.db_instance_id}}"` | `DBInstanceStatus` / `Items.DBInstance[0].DBInstanceStatus` | `Running` | 10s | 60 |
| ModifyDBInstanceSpec | DescribeDBInstances | `--DBInstanceId "{{user.db_instance_id}}"` | `DBInstanceStatus` / `Items.DBInstance[0].DBInstanceStatus` | `Running` | 10s | 30 |
| UpgradeDBInstanceEngineVersion | DescribeDBInstances | `--DBInstanceId "{{user.db_instance_id}}"` | multi-field template above | `Running` + version | 10s | 60 |

> **JIT Go SDK**: use synchronous `Describe*` polling with the same intervals and target states.
