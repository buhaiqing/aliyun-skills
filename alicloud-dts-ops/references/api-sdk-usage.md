# API & SDK — DTS (Data Transmission Service)

## OpenAPI

- **Spec:** [DTS 2020-01-01](https://help.aliyun.com/zh/dts/developer-reference/api-dts-2020-01-01-overview)
- **Base path:** `https://dts.aliyuncs.com`
- **Protocol:** HTTP (RPC-style)

## SDK Operations Map

### Core Operations (New API — preferred)

| Goal | OperationId | CLI Command | SDK Method |
|------|-------------|-------------|------------|
| Purchase DTS instance | CreateDtsInstance | `aliyun dts CreateDtsInstance` | `CreateDtsInstance` |
| Configure job | ConfigureDtsJob | `aliyun dts ConfigureDtsJob` | `ConfigureDtsJob` |
| Start job | StartDtsJob | `aliyun dts StartDtsJob` | `StartDtsJob` |
| Start multiple jobs | StartDtsJobs | `aliyun dts StartDtsJobs` | `StartDtsJobs` |
| Stop job | StopDtsJob | `aliyun dts StopDtsJob` | `StopDtsJob` |
| Stop multiple jobs | StopDtsJobs | `aliyun dts StopDtsJobs` | `StopDtsJobs` |
| Suspend job | SuspendDtsJob | `aliyun dts SuspendDtsJob` | `SuspendDtsJob` |
| Delete job | DeleteDtsJob | `aliyun dts DeleteDtsJob` | `DeleteDtsJob` |
| List jobs | DescribeDtsJobs | `aliyun dts DescribeDtsJobs` | `DescribeDtsJobs` |
| Get job detail | DescribeDtsJobDetail | `aliyun dts DescribeDtsJobDetail` | `DescribeDtsJobDetail` |
| Reset job | ResetDtsJob | `aliyun dts ResetDtsJob` | `ResetDtsJob` |
| Test connectivity | DescribeConnectionStatus | `aliyun dts DescribeConnectionStatus` | `DescribeConnectionStatus` |
| Modify job name | ModifyDtsJobName | `aliyun dts ModifyDtsJobName` | `ModifyDtsJobName` |
| Modify password | ModifyDtsJobPassword | `aliyun dts ModifyDtsJobPassword` | `ModifyDtsJobPassword` |
| Modify DU limit | ModifyDtsJobDuLimit | `aliyun dts ModifyDtsJobDuLimit` | `ModifyDtsJobDuLimit` |
| Create consumer channel | CreateConsumerChannel | `aliyun dts CreateConsumerChannel` | `CreateConsumerChannel` |
| Describe consumer channel | DescribeConsumerChannel | `aliyun dts DescribeConsumerChannel` | `DescribeConsumerChannel` |
| Modify consumer channel | ModifyConsumerChannel | `aliyun dts ModifyConsumerChannel` | `ModifyConsumerChannel` |
| Delete consumer channel | DeleteConsumerChannel | `aliyun dts DeleteConsumerChannel` | `DeleteConsumerChannel` |
| Describe precheck status | DescribePreCheckStatus | `aliyun dts DescribePreCheckStatus` | `DescribePreCheckStatus` |
| Describe DTS IP | DescribeDTSIP | `aliyun dts DescribeDTSIP` | `DescribeDTSIP` |
| Describe check jobs | DescribeCheckJobs | `aliyun dts DescribeCheckJobs` | `DescribeCheckJobs` |
| Describe data check details | DescribeDataCheckTableDetails | `aliyun dts DescribeDataCheckTableDetails` | `DescribeDataCheckTableDetails` |
| Create monitor rule | CreateJobMonitorRule | `aliyun dts CreateJobMonitorRule` | `CreateJobMonitorRule` |
| Describe monitor rule | DescribeJobMonitorRule | `aliyun dts DescribeJobMonitorRule` | `DescribeJobMonitorRule` |
| White IP list | WhiteIpList | `aliyun dts WhiteIpList` | `WhiteIpList` |
| Renew instance | RenewInstance | `aliyun dts RenewInstance` | `RenewInstance` |
| Change billing method | TransferPayType | `aliyun dts TransferPayType` | `TransferPayType` |
| Upgrade/downgrade instance class | TransferInstanceClass | `aliyun dts TransferInstanceClass` | `TransferInstanceClass` |

### Legacy Operations (still supported)

| Goal | OperationId | Notes |
|------|-------------|-------|
| Purchase migration instance | CreateMigrationJob | Prefer CreateDtsInstance |
| Purchase sync instance | CreateSynchronizationJob | Prefer CreateDtsInstance |
| Purchase subscription instance | CreateSubscriptionInstance | Prefer CreateDtsInstance |
| Configure migration job | ConfigureMigrationJob | Prefer ConfigureDtsJob |
| Configure sync job | ConfigureSynchronizationJob | Prefer ConfigureDtsJob |
| Configure subscription | ConfigureSubscription | Prefer ConfigureDtsJob |
| Start migration | StartMigrationJob | Prefer StartDtsJob |
| Start sync | StartSynchronizationJob | Prefer StartDtsJob |
| List migration jobs | DescribeMigrationJobs | Prefer DescribeDtsJobs |
| List sync jobs | DescribeSynchronizationJobs | Prefer DescribeDtsJobs |
| Check sync status | DescribeSynchronizationJobStatus | Prefer DescribeDtsJobDetail |

## Common JSON Paths

### DescribeDtsJobs
```
$.DtsJobList[].DtsJobId         → Task ID
$.DtsJobList[].DtsJobName       → Task name
$.DtsJobList[].Status           → Current status
$.DtsJobList[].JobType          → "MIGRATE" / "SYNC" / "SUBSCRIBE"
$.DtsJobList[].PayType          → "PostPaid" / "PrePaid"
$.DtsJobList[].CreateTime       → Creation time
$.DtsJobList[].Delay            → Sync delay (seconds)
$.TotalRecordCount              → Total item count
$.PageNumber                    → Current page
```

### ConfigureDtsJob
```
$.DtsJobId      → New job ID
$.InstanceId    → DTS instance ID
$.ErrCode       → Error code (if failed)
```

### DescribeDtsJobDetail
```
$.DtsJobId              → Task ID
$.Status                → Current status
$.JobType               → Task type
$.Delay                 → Sync delay
$.DtsJobName            → Task name
$.SourceEndpoint.*      → Source connection details
$.DestinationEndpoint.* → Target connection details
$.PrecheckStatus        → Precheck status
$.MigrationProgress     → Migration progress (%)
$.StructureInitializationStatus → Structure sync status
$.DataInitializationStatus     → Data initialization status
$.SynchronizationDetails       → Sync details (for sync jobs)
```

### DescribeConnectionStatus
```
$.ConnectDetail[].Status        → "Success" / "Failed"
$.ConnectDetail[].ErrorMessage  → Error message (if failed)
```

### DescribeDTSIP
```
$.IPList         → Array of CIDR blocks
```

## Pagination

DescribeDtsJobs uses page-based pagination:
- `PageSize` (default 30, max 100)
- `PageNumber` (starts at 1)
- Response: `$.PageNumber`, `$.TotalRecordCount`, `$.DtsJobList[]`

```bash
# Paginate through all DTS jobs
PAGE=1
while true; do
  RESPONSE=$(aliyun dts DescribeDtsJobs --PageNumber $PAGE --PageSize 50)
  echo "$RESPONSE" | jq '.DtsJobList[] | {DtsJobId, Status, JobType}'
  TOTAL=$(echo "$RESPONSE" | jq -r '.TotalRecordCount')
  PAGE_SIZE=$(echo "$RESPONSE" | jq -r '.PageSize')
  PAGE=$((PAGE + 1))
  [ $(( (PAGE-1) * PAGE_SIZE )) -ge "$TOTAL" ] && break
done
```

## Request/Response Notes

- All operations require `RegionId` parameter
- Source/target database passwords are sensitive — mask them in logs
- ConfigureDtsJob parameters vary by source/target endpoint type — refer to OpenAPI doc for full parameter list
- Async operations (ConfigureDtsJob with AutoStart) return immediately; poll DescribeDtsJobDetail for actual status
- `DescribeConnectionStatus` makes real connections to source/target — test before full configuration