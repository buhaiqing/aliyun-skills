# Troubleshooting — DTS (Data Transmission Service)

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `InvalidParameter` | Request parameter failed validation | Align parameter values with OpenAPI doc; check endpoint types and engine names |
| `InvalidConnectionString` | Source/target connection string invalid | Verify instance ID and region are correct for the endpoint type |
| `InvalidEndpointType` | Unsupported source/target instance type | Check supported source/target matrix; use correct `SourceEndpointInstanceType` |
| `QuotaExceeded.DtsInstance` | DTS instance count exceeded limit | CreateDtsInstance quota reached; delete unused instances or request increase |
| `InsufficientBalance` | Account balance insufficient | HALT — recharge Alibaba Cloud account |
| `PrecheckFailed` | DTS precheck did not pass | Call DescribePreCheckStatus to identify specific items; fix and retry |
| `JobExecutionException` | Job encountered runtime error | Check logs via DescribeDtsServiceLog; inspect source/target connectivity and permissions |
| `SourceOrDestinationNotAllowed` | Source-target combination not supported | Check official [supported source/target matrix](https://help.aliyun.com/zh/dts/supported-sources-and-targets) |
| `InvalidWhiteList` | DTS server IP not in source/target whitelist | Get DTS CIDR via DescribeDTSIP; add to source/target security group or whitelist |
| `SubscriptionNotFound` | Change tracking instance not found | Verify subscription instance ID; check region |
| `InvalidJobName.Duplicate` | Job name already exists | Use unique DtsJobName |
| `Throttling` / 429 | Rate limit exceeded | Retry with exponential backoff; check Retry-After header |
| `InternalError` / 5xx | Server-side error | Retry with backoff; persist RequestId for escalation |
| `InvalidParameter.ResourceOwner` | Resource owner account mismatch | Cross-account operations need correct ResourceOwnerId |
| `InvalidMigrationJob.NotFound` | Migration job not found | Verify job ID; check if instance was already released |
| `SourceEndpointNotConnected` | DTS cannot connect to source | Check source DB status, network, whitelist, credentials |
| `DestinationEndpointNotConnected` | DTS cannot connect to target | Check target DB status, network, whitelist, credentials |
| `InvalidAccountPermission` | Database account lacks required privileges | Source needs SELECT/REPLICATION SLAVE; target needs INSERT/UPDATE/DELETE/CREATE |
| `BinlogNotEnabled` | Source database binlog disabled | Enable binlog on source for incremental sync/migration |
| `BinlogPurged` | Required binlog files already purged | Full re-sync needed; increase binlog retention for future tasks |
| `ObjectNameConflict` | Table/view name already exists on target | Use different migration object mapping or table mapping |
| `DuplicateKey` | Duplicate key conflict during sync | Configure conflict overwrite strategy (OVERWRITE/IGNORE) |
| `StorageLimitExceeded` | Target storage insufficient | Increase target database storage |
| `UnsupportedDataType` | Source has unsupported data type | Check DTS type mapping; exclude unsupported columns |
| `SourceEngineVersionNotSupported` | Source DB version too old | Upgrade source to supported version |
| `NetworkConnectError` | Network connectivity issue between DTS and endpoint | Check network path: VPC, NAT, DTS CIDR whitelist, firewall |

## Diagnostic Order

When a DTS task fails, follow this diagnostic order:

### Step 1: Identify the failure

```bash
# Get detailed job information
aliyun dts DescribeDtsJobDetail \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"

# Check precheck status (if task is prechecking)
aliyun dts DescribePreCheckStatus \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"
```

### Step 2: Check connectivity

```bash
# Test source endpoint connectivity
aliyun dts DescribeConnectionStatus \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --SourceEndpointInstanceType "{{user.source_endpoint_type}}" \
  --SourceEndpointInstanceID "{{user.source_instance_id}}" \
  --SourceEndpointRegion "{{user.source_region}}" \
  --SourceEndpointEngineName "{{user.source_engine}}" \
  --SourceEndpointUserName "{{user.source_username}}" \
  --SourceEndpointPassword "{{user.source_password}}"
```

### Step 3: Check DTS server whitelist

```bash
# Get DTS server CIDR blocks
aliyun dts DescribeDTSIP \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --SourceEndpointRegion "{{user.source_region}}" \
  --DestinationEndpointRegion "{{user.target_region}}"

# Verify CIDR blocks are in source/target security group (via relevant product skill)
```

### Step 4: Review job logs

```bash
# Get DTS service log
aliyun dts DescribeDtsServiceLog \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"
```

### Step 5: Check data consistency (for sync tasks)

```bash
# Run data check
aliyun dts DescribeCheckJobs \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"
```

## Multi-Round Diagnosis

### Round 1 — Precheck Failures

| Precheck Item | Common Cause | Remediation |
|--------------|-------------|-------------|
| Source connectivity | IP not whitelisted, wrong password | Add DTS CIDR, verify password |
| Target connectivity | IP not whitelisted, wrong password | Add DTS CIDR, verify password |
| Source permissions | Insufficient DB account privileges | GRANT SELECT/REPLICATION SLAVE on source |
| Target permissions | Insufficient DB account privileges | GRANT INSERT/UPDATE/DELETE/CREATE on target |
| Object name conflict | Table/view already exists | Use DTS mapping to rename or exclude |
| Source binlog | Binlog disabled or rotation too fast | Enable binlog, increase retention |
| Timezone check | Source/target timezone mismatch | Set consistent timezone |
| Storage quota | Target DB storage full | Increase storage or clean up |

```bash
# Get precheck details for specific item
aliyun dts DescribePreCheckStatus \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}" | jq '.PreCheckDetail[] | {ItemName,CheckResult,ErrorMessage}'
```

### Round 2 — Runtime Failures (during migration/sync)

| Symptom | Likely Cause | Remediation |
|---------|-------------|-------------|
| Sync delay increasing | Target I/O bottleneck, or DTS DU too low | Increase DU limit, check target performance |
| Task stuck at "Migrating" | Large table without primary key | Add primary key to source table |
| Duplicate key errors | Conflicting data on target | Set conflict strategy to OVERWRITE |
| Job repeatedly fails | Source/target network intermittent | Check network stability; increase timeout |
| OOM on DTS | Memory limit for high-throughput task | Decrease DU or split into multiple tasks |

### Round 3 — Data Consistency Issues

```bash
# Check data check report URL
aliyun dts DescribeDataCheckReportUrl \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"

# Get table-level verification details
aliyun dts DescribeDataCheckTableDetails \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"
```

## Recovery Actions

### Precheck Failed

```bash
# Identify specific failed items
PRECHECK=$(aliyun dts DescribePreCheckStatus --RegionId cn-hangzhou --DtsJobId "dtsxxxx12345")

# After fixing issues (e.g., updating password, adding whitelist)
# Retry the task
aliyun dts StartDtsJob --RegionId cn-hangzhou --DtsJobId "dtsxxxx12345"
```

### Task Failed During Migration

```bash
# 1. Check failure reason
aliyun dts DescribeDtsJobDetail --RegionId cn-hangzhou --DtsJobId "dtsxxxx12345" | jq -r '.ErrorMessage'

# 2. Fix the underlying issue (connectivity, permissions, storage)

# 3. If incremental migration, resume from checkpoint
aliyun dts StartDtsJob --RegionId cn-hangzhou --DtsJobId "dtsxxxx12345"

# 4. If full migration failed, may need to reset and re-configure
# WARNING: reset clears progress
aliyun dts ResetDtsJob --RegionId cn-hangzhou --DtsJobId "dtsxxxx12345"
aliyun dts StartDtsJob --RegionId cn-hangzhou --DtsJobId "dtsxxxx12345"
```

### Sync Task High Latency

```bash
# 1. Check current delay
DETAIL=$(aliyun dts DescribeDtsJobDetail --RegionId cn-hangzhou --DtsJobId "dtsxxxx12345")
DELAY=$(echo "$DETAIL" | jq -r '.Delay')

# 2. If delay > threshold, increase DU
aliyun dts ModifyDtsJobDuLimit \
  --RegionId cn-hangzhou \
  --DtsJobId "dtsxxxx12345" \
  --DuLimit 2
```