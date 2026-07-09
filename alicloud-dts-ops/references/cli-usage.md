# CLI — DTS (`aliyun dts`)

## Install and Config

- Install: see [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- **Recommended:** Install DTS plugin for enhanced features:
  ```bash
  aliyun plugin install --names aliyun-cli-dts
  ```
- Credentials: env vars `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR `~/.aliyun/config.json`
- Output is **JSON by default** — no `--output json` needed

## Conventions (agent execution)

- All DTS CLI commands follow RPC-style: `aliyun dts <ApiName> --Param1 value1 --Param2 value2`
- Output is JSON by default; use `jq` for field extraction
- Sensitive parameters (database passwords) are passed as `--SourceEndpointPassword` — ensure execution environment does not log them
- For JMESPath extraction: `aliyun dts DescribeDtsJobs --output cols=DtsJobId,Status rows=DtsJobList[].[DtsJobId,Status]`

## CLI vs API Coverage Gap

| Operation (API/SDK) | Available via `aliyun`? | Notes |
|----------------------|------------------------|-------|
| DescribeDtsJobs | ✅ Full | Primary list API (all job types) |
| DescribeDtsJobDetail | ✅ Full | Detailed job status |
| ConfigureDtsJob | ✅ Full | Universal config (MIGRATE/SYNC/SUBSCRIBE) |
| CreateDtsInstance | ✅ Full | Purchase unified instance |
| StartDtsJob | ✅ Full | Start single job |
| StopDtsJob | ✅ Full | Stop single job |
| SuspendDtsJob | ✅ Full | Pause job |
| DeleteDtsJob | ✅ Full | Delete job + release instance |
| ResetDtsJob | ✅ Full | Reset failed job |
| DescribeConnectionStatus | ✅ Full | Test source/target connectivity |
| ModifyDtsJobName | ✅ Full | Rename job |
| ModifyDtsJobPassword | ✅ Full | Update database password |
| ModifyDtsJobDuLimit | ✅ Full | Adjust DU limit |
| CreateConsumerChannel | ✅ Full | Create consumer group |
| DescribeConsumerChannel | ✅ Full | List consumer groups |
| DescribeDTSIP | ✅ Full | Get DTS server CIDR blocks |
| DescribePreCheckStatus | ✅ Full | Precheck details |
| DescribeCheckJobs | ✅ Full | Data consistency verification |
| DescribeMigrationJobs | ✅ Full | Legacy list API (migration only) |
| DescribeSynchronizationJobs | ✅ Full | Legacy list API (sync only) |
| DescribeSubscriptionInstances | ✅ Full | Legacy list API (subscribe only) |
| CreateMigrationJob | ✅ Full | Legacy purchase (migration only) |
| CreateSynchronizationJob | ✅ Full | Legacy purchase (sync only) |
| RenewInstance | ✅ Full | Renew subscription instance |
| TransferPayType | ✅ Full | Change billing method |
| TransferInstanceClass | ✅ Full | Upgrade/downgrade instance |
| DescribeDataCheckTableDetails | ✅ Full | Data consistency check details |
| CreateJobMonitorRule | ✅ Full | Create alert rule |
| TagResources | ✅ Full | Tag DTS instances |

## Common CLI Patterns

### List and Filter
```bash
# All tasks
aliyun dts DescribeDtsJobs --RegionId cn-hangzhou

# Filter by type
aliyun dts DescribeDtsJobs --RegionId cn-hangzhou --Type migration

# Filter by status
aliyun dts DescribeDtsJobs --RegionId cn-hangzhou --Status Migrating

# Paginated
aliyun dts DescribeDtsJobs --RegionId cn-hangzhou --PageNumber 1 --PageSize 50
```

### Extract Specific Fields
```bash
# Projection with jq
aliyun dts DescribeDtsJobs --RegionId cn-hangzhou | jq '.DtsJobList[] | {DtsJobId, Status, DtsJobName, Delay}'

# JMESPath with CLI (tabular output)
aliyun dts DescribeDtsJobs --RegionId cn-hangzhou \
  --output cols=DtsJobId,Status,DtsJobName rows=DtsJobList[].[DtsJobId,Status,DtsJobName]
```

### Check Specific Job
```bash
aliyun dts DescribeDtsJobDetail --RegionId cn-hangzhou --DtsJobId "dtsxxxx12345"
```

### Poll Until Terminal State
```bash
# Poll migration until finished
for i in $(seq 1 60); do
  STATUS=$(aliyun dts DescribeDtsJobDetail \
    --RegionId cn-hangzhou --DtsJobId "dtsxxxx12345" | jq -r '.Status')
  [ "$STATUS" = "Finished" ] && { echo "✅ Done"; exit 0; }
  [ "$STATUS" = "Failed" ] && { echo "❌ Failed"; exit 1; }
  sleep 10
done
```