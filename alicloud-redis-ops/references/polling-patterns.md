# Polling Patterns — Redis/Tair

## Generic Polling Template

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun r-kvstore {{describe_command}} \
    --RegionId "{{user.region}}" \
    --InstanceId "{{user.instance_id}}" \
    --output cols={{status_field}} rows={{status_path}})
  [ "$STATUS" = "{{target_status}}" ] && break
  sleep {{interval}}
done
```

## Per-Operation Polling Parameters

| Operation | Describe Command | Status Field | Status Path | Target Status | Interval | Max Retries |
|-----------|-----------------|-------------|-------------|---------------|----------|-------------|
| CreateInstance | describe-instances | InstanceStatus | Instances.KVStoreInstance[0].InstanceStatus | Normal | 10s | 60 |
| RestartInstance | describe-instances | InstanceStatus | Instances.KVStoreInstance[0].InstanceStatus | Normal | 10s | 30 |
| DeleteInstance | describe-instances | TotalCount | TotalCount | 0 | 10s | 30 |
| ModifyInstanceSpec | describe-instances | InstanceStatus | Instances.KVStoreInstance[0].InstanceStatus | Normal | 10s | 60 |
| CreateAccount | describe-accounts | AccountStatus | Accounts.Account[0].AccountStatus | Available | 5s | 24 |
| DeleteAccount | describe-accounts | AccountName | Accounts.Account[0].AccountName | (empty) | 5s | 24 |
| ResetAccountPassword | describe-accounts | AccountStatus | Accounts.Account[0].AccountStatus | Available | 5s | 24 |
| CreateBackup | describe-backups | BackupStatus | Backups.Backup[0].BackupStatus | Success | 10s | 60 |
| RestoreInstance | describe-instances | InstanceStatus | Instances.KVStoreInstance[0].InstanceStatus | Normal | 10s | 60 |
| ModifyInstanceSSL | describe-instances | InstanceStatus | Instances.KVStoreInstance[0].InstanceStatus | Normal | 10s | 12 |
| MigrateToOtherZone | describe-instances | InstanceStatus | Instances.KVStoreInstance[0].InstanceStatus | Normal | 10s | 60 |
| UpgradeMinorVersion | describe-instances | InstanceStatus | Instances.KVStoreInstance[0].InstanceStatus | Normal | 10s | 60 |
| FlushInstance | describe-instances | InstanceStatus | Instances.KVStoreInstance[0].InstanceStatus | Normal | 10s | 30 |
