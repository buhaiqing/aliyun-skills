# CLI — Alibaba Cloud Redis / Tair (`aliyun r-kvstore`)

## Install and Config

- Install: see [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- **CRITICAL Credentials:** The `aliyun` CLI reads from env vars
  `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR
  `~/.aliyun/config.json` (JSON format).
- For sandbox environments, set env vars directly (preferred) or use `--config-path`.

## Conventions (Agent Execution)

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.Items.Item[]?`
- Use `--PageSize` to control result sets: `--PageSize 50`
- Example:
```bash
aliyun ecs DescribeInstances --PageSize 50 | jq '{total: .TotalCount, items: [.Items.Item[]? | {id: .Id, name: .Name}]}'
```

- Output is **JSON by default** — NO `--output json` needed for plain JSON
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- `--no-interactive` does NOT exist in `aliyun` CLI — all commands are non-interactive by default
- Document **exact** JSON paths after verifying with a real invocation

## CLI vs API Coverage Gap

| Operation (API / SDK) | Available via `aliyun`? | Notes |
|------------------------|---------------------|-------|
| CreateInstance | yes | Full support |
| DescribeInstances | yes | Full support |
| DescribeInstanceAttribute | yes | Full support |
| RestartInstance | yes | Full support |
| DeleteInstance | yes | Full support |
| ModifyInstanceSpec | yes | Full support |
| DescribeAccounts | yes | Full support |
| CreateAccount | yes | Full support |
| DeleteAccount | yes | Full support |
| ResetAccountPassword | yes | Full support |
| DescribeBackups | yes | Full support |
| CreateBackup | yes | Full support |
| RestoreInstance | yes | Full support |
| DescribeSecurityIps | yes | Full support |
| ModifySecurityIps | yes | Full support |
| DescribeParameters | yes | Full support |
| ModifyParameter | yes | Full support |
| DescribeSlowLogs | yes | Full support |
| DescribeHistoryMonitorValues | yes | Full support |
| DescribeMonitorItems | yes | Full support |
| DescribeIntranetAttribute | yes | Full support |
| ModifyIntranetBandwidth | yes | Full support |
| DescribeRegions | yes | Full support |
| DescribeZones | yes | Full support |
| DescribeAvailableResource | yes | Full support |
| MigrateToOtherZone | yes | Full support |
| ModifyInstanceMaintainTime | yes | Full support |
| ModifyInstanceSSL | yes | Full support |
| DescribeEngineVersion | yes | Full support |
| UpgradeMinorVersion | yes | Full support |
| FlushInstance | yes | Full support |

> Redis / Tair (R-kvstore) is fully supported by the `aliyun` CLI. All operations documented in this skill have CLI equivalents.

## Command Map

| Goal | Example `aliyun` invocation | Notes |
|------|--------------------------|-------|
| Create Instance | `aliyun r-kvstore create-instance --RegionId cn-hangzhou --InstanceName myredis --InstanceClass redis.master.small.default --EngineVersion 5.0 ...` | JSON output by default |
| Describe Instances | `aliyun r-kvstore describe-instances --RegionId cn-hangzhou` | JSON output by default |
| Describe Instance | `aliyun r-kvstore describe-instances --RegionId cn-hangzhou --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Describe Instance Attribute | `aliyun r-kvstore describe-instance-attribute --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Restart Instance | `aliyun r-kvstore restart-instance --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Delete Instance | `aliyun r-kvstore delete-instance --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Modify Instance Spec | `aliyun r-kvstore modify-instance-spec --InstanceId r-bp1zxszhcgatnx**** --InstanceClass redis.master.mid.default --OrderType UPGRADE` | JSON output by default |
| Describe Accounts | `aliyun r-kvstore describe-accounts --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Create Account | `aliyun r-kvstore create-account --InstanceId r-bp1zxszhcgatnx**** --AccountName myuser --AccountPassword mypass` | JSON output by default |
| Delete Account | `aliyun r-kvstore delete-account --InstanceId r-bp1zxszhcgatnx**** --AccountName myuser` | JSON output by default |
| Reset Account Password | `aliyun r-kvstore reset-account-password --InstanceId r-bp1zxszhcgatnx**** --AccountName myuser --AccountPassword newpass` | JSON output by default |
| Describe Backups | `aliyun r-kvstore describe-backups --InstanceId r-bp1zxszhcgatnx**** --StartTime 2026-05-01T00:00:00Z --EndTime 2026-05-14T00:00:00Z` | JSON output by default |
| Create Backup | `aliyun r-kvstore create-backup --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Restore Instance | `aliyun r-kvstore restore-instance --InstanceId r-bp1zxszhcgatnx**** --BackupId 12345678` | JSON output by default |
| Describe Security IPs | `aliyun r-kvstore describe-security-ips --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Modify Security IPs | `aliyun r-kvstore modify-security-ips --InstanceId r-bp1zxszhcgatnx**** --SecurityIps 10.0.0.0/8` | JSON output by default |
| Describe Parameters | `aliyun r-kvstore describe-parameters --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Modify Parameter | `aliyun r-kvstore modify-parameter --InstanceId r-bp1zxszhcgatnx**** --ParameterName maxmemory-policy --ParameterValue allkeys-lru` | JSON output by default |
| Describe Slow Logs | `aliyun r-kvstore describe-slow-logs --InstanceId r-bp1zxszhcgatnx**** --StartTime 2026-05-01T00:00:00Z --EndTime 2026-05-14T00:00:00Z` | JSON output by default |
| Describe History Monitor Values | `aliyun r-kvstore describe-history-monitor-values --InstanceId r-bp1zxszhcgatnx**** --MonitorKeys UsedMemory,UsedConnection,UsedQPS --StartTime 2026-05-01T00:00:00Z --EndTime 2026-05-14T00:00:00Z` | JSON output by default |
| Describe Monitor Items | `aliyun r-kvstore describe-monitor-items --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Describe Intranet Attribute | `aliyun r-kvstore describe-intranet-attribute --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Modify Intranet Bandwidth | `aliyun r-kvstore modify-intranet-bandwidth --InstanceId r-bp1zxszhcgatnx**** --Bandwidth 256` | JSON output by default |
| Describe Regions | `aliyun r-kvstore describe-regions` | JSON output by default |
| Describe Zones | `aliyun r-kvstore describe-zones --RegionId cn-hangzhou` | JSON output by default |
| Describe Available Resource | `aliyun r-kvstore describe-available-resource --RegionId cn-hangzhou` | JSON output by default |
| Migrate To Other Zone | `aliyun r-kvstore migrate-to-other-zone --InstanceId r-bp1zxszhcgatnx**** --ZoneId cn-hangzhou-b` | JSON output by default |
| Modify Instance Maintain Time | `aliyun r-kvstore modify-instance-maintain-time --InstanceId r-bp1zxszhcgatnx**** --MaintainStartTime 02:00Z --MaintainEndTime 06:00Z` | JSON output by default |
| Modify Instance SSL | `aliyun r-kvstore modify-instance-ssl --InstanceId r-bp1zxszhcgatnx**** --SSLEnabled Enable` | JSON output by default |
| Describe Engine Version | `aliyun r-kvstore describe-engine-version --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Upgrade Minor Version | `aliyun r-kvstore upgrade-minor-version --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Flush Instance | `aliyun r-kvstore flush-instance --InstanceId r-bp1zxszhcgatnx****` | JSON output by default |
| Extract fields | `aliyun r-kvstore describe-instances --output cols=InstanceId,InstanceStatus,InstanceClass rows=Instances.KVStoreInstance[].{InstanceId,InstanceStatus,InstanceClass}` | JMESPath tabular mode |
| Poll state | `for i in $(seq 1 60); do STATUS=$(aliyun r-kvstore describe-instances --InstanceId r-bp1zxszhcgatnx**** --output cols=InstanceStatus rows=Instances.KVStoreInstance[0].InstanceStatus); [ "$STATUS" = "Normal" ] && break; sleep 10; done` | Shell loop polling |
| Poll with `--waiter` | `aliyun r-kvstore describe-instances --InstanceId r-bp1zxszhcgatnx**** --waiter expr='Instances.KVStoreInstance[0].InstanceStatus' to=Normal timeout=600 interval=10` | Native CLI waiter (when supported) |

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.Items.Item[]?`
- Use `--PageSize` to control result sets: `--PageSize 50`
- Example:
```bash
aliyun ecs DescribeInstances --PageSize 50 | jq '{total: .TotalCount, items: [.Items.Item[]? | {id: .Id, name: .Name}]}'
```

