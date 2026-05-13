# CLI — Alibaba Cloud RDS (`aliyun rds`)

## Install and Config

- Install: see [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- **CRITICAL Credentials:** The `aliyun` CLI reads from env vars
  `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR
  `~/.aliyun/config.json` (JSON format).
- For sandbox environments, set env vars directly (preferred) or use `--config-path`.

## Conventions (Agent Execution)

- Output is **JSON by default** — NO `--output json` needed for plain JSON
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- `--no-interactive` does NOT exist in `aliyun` CLI — all commands are non-interactive by default
- Document **exact** JSON paths after verifying with a real invocation

## CLI vs API Coverage Gap

| Operation (API / SDK) | Available via `aliyun`? | Notes |
|------------------------|---------------------|-------|
| CreateDBInstance | yes | Full support |
| DescribeDBInstances | yes | Full support |
| RestartDBInstance | yes | Full support |
| DeleteDBInstance | yes | Full support |
| DescribeAccounts | yes | Full support |
| CreateAccount | yes | Full support |
| DescribeDatabases | yes | Full support |
| DescribeBackups | yes | Full support |
| DescribeSlowLogs | yes | Full support |
| DescribeResourceUsage | yes | Full support |
| DescribeDBInstancePerformance | yes | Full support |
| DescribeDBInstanceHAConfig | yes | Full support |
| ModifySecurityIps | yes | Full support |
| DescribeParameters | yes | Full support |
| ModifyParameter | yes | Full support |
| DescribeRegions | yes | Full support |
| DescribeAvailableClasses | yes | Full support |
| DescribeAvailableResource | yes | Full support |
| DescribeDBInstanceAttribute | yes | Full support |
| DescribeDBInstanceNetInfo | yes | Full support |
| DescribeDBInstanceIPArrayList | yes | Full support |
| DescribeBinlogFiles | yes | Full support |
| DescribeErrorLogs | yes | Full support |
| DescribeSQLLogRecords | yes | Full support |
| ModifyDBInstanceSpec | yes | Full support |
| UpgradeDBInstanceEngineVersion | yes | Full support |
| DescribeAvailableZones | yes | Full support |

> RDS is fully supported by the `aliyun` CLI. All operations documented in this skill
> have CLI equivalents.

## Command Map

| Goal | Example `aliyun` invocation | Notes |
|------|--------------------------|-------|
| Create Instance | `aliyun rds CreateDBInstance --RegionId cn-hangzhou --Engine MySQL --EngineVersion 8.0 ...` | JSON output by default |
| Describe Instances | `aliyun rds DescribeDBInstances --RegionId cn-hangzhou` | JSON output by default |
| Describe Instance | `aliyun rds DescribeDBInstances --RegionId cn-hangzhou --DBInstanceId rm-xxx` | JSON output by default |
| Restart Instance | `aliyun rds RestartDBInstance --DBInstanceId rm-xxx` | JSON output by default |
| Delete Instance | `aliyun rds DeleteDBInstance --DBInstanceId rm-xxx` | JSON output by default |
| Describe Accounts | `aliyun rds DescribeAccounts --DBInstanceId rm-xxx` | JSON output by default |
| Create Account | `aliyun rds CreateAccount --DBInstanceId rm-xxx --AccountName user --AccountPassword pass` | JSON output by default |
| Describe Databases | `aliyun rds DescribeDatabases --DBInstanceId rm-xxx` | JSON output by default |
| Describe Backups | `aliyun rds DescribeBackups --DBInstanceId rm-xxx --StartTime 2026-05-01T00:00:00Z --EndTime 2026-05-14T00:00:00Z` | JSON output by default |
| Describe Slow Logs | `aliyun rds DescribeSlowLogs --DBInstanceId rm-xxx --StartTime 2026-05-01T00:00:00Z --EndTime 2026-05-14T00:00:00Z` | JSON output by default |
| Describe Resource Usage | `aliyun rds DescribeResourceUsage --DBInstanceId rm-xxx` | JSON output by default |
| Describe Performance | `aliyun rds DescribeDBInstancePerformance --DBInstanceId rm-xxx --Key MySQL_CPUUsage --StartTime 2026-05-01T00:00:00Z --EndTime 2026-05-14T00:00:00Z` | JSON output by default |
| Describe HA Config | `aliyun rds DescribeDBInstanceHAConfig --DBInstanceId rm-xxx` | JSON output by default |
| Modify Security IPs | `aliyun rds ModifySecurityIps --DBInstanceId rm-xxx --SecurityIps 10.0.0.0/8` | JSON output by default |
| Describe Parameters | `aliyun rds DescribeParameters --DBInstanceId rm-xxx` | JSON output by default |
| Modify Parameter | `aliyun rds ModifyParameter --DBInstanceId rm-xxx --Parameters '{"wait_timeout":"600"}'` | JSON output by default |
| Extract fields | `aliyun rds DescribeDBInstances --output cols=DBInstanceId,Status rows=Items.DBInstance[].{DBInstanceId,Status}` | JMESPath tabular mode |
| Poll state | `for i in $(seq 1 60); do STATUS=$(aliyun rds DescribeDBInstances --DBInstanceId rm-xxx --output cols=DBInstanceStatus rows=Items.DBInstance[0].DBInstanceStatus); [ "$STATUS" = "Running" ] && break; sleep 10; done` | Shell loop polling |
| Describe Instance Attribute | `aliyun rds DescribeDBInstanceAttribute --DBInstanceId rm-xxx` | JSON output by default |
| Describe Net Info | `aliyun rds DescribeDBInstanceNetInfo --DBInstanceId rm-xxx` | JSON output by default |
| Describe IP Array List | `aliyun rds DescribeDBInstanceIPArrayList --DBInstanceId rm-xxx` | JSON output by default |
| Describe Binlog Files | `aliyun rds DescribeBinlogFiles --DBInstanceId rm-xxx --StartTime 2026-05-01T00:00:00Z --EndTime 2026-05-14T00:00:00Z` | JSON output by default |
| Describe Error Logs | `aliyun rds DescribeErrorLogs --DBInstanceId rm-xxx --StartTime 2026-05-01T00:00:00Z --EndTime 2026-05-14T00:00:00Z` | JSON output by default |
| Describe SQL Log Records | `aliyun rds DescribeSQLLogRecords --DBInstanceId rm-xxx --StartTime 2026-05-01T00:00:00Z --EndTime 2026-05-14T00:00:00Z` | JSON output by default |
| Modify Instance Spec | `aliyun rds ModifyDBInstanceSpec --DBInstanceId rm-xxx --DBInstanceClass rds.mysql.s2.large --DBInstanceStorage 100` | JSON output by default |
| Upgrade Engine Version | `aliyun rds UpgradeDBInstanceEngineVersion --DBInstanceId rm-xxx --EngineVersion 8.0` | JSON output by default |
| Describe Available Zones | `aliyun rds DescribeAvailableZones --RegionId cn-hangzhou --Engine MySQL --EngineVersion 8.0` | JSON output by default |
| Create Database | `aliyun rds CreateDatabase --DBInstanceId rm-xxx --DBName mydb --CharacterSetName utf8mb4` | JSON output by default |
| Delete Database | `aliyun rds DeleteDatabase --DBInstanceId rm-xxx --DBName mydb` | JSON output by default |
| Delete Account | `aliyun rds DeleteAccount --DBInstanceId rm-xxx --AccountName myuser` | JSON output by default |
| Describe Read-only Instances | `aliyun rds DescribeReadDBInstances --DBInstanceId rm-xxx` | JSON output by default |
| Create Backup | `aliyun rds CreateBackup --DBInstanceId rm-xxx --BackupMethod Physical --BackupType FullBackup` | JSON output by default |
| Restore DB Instance | `aliyun rds RestoreDBInstance --DBInstanceId rm-xxx --BackupId 123456` | JSON output by default |
