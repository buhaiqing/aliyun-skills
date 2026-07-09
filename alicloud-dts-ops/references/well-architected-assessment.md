# Well-Architected Assessment — DTS (Data Transmission Service)

> **Framework:** Alibaba Cloud [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html)
> **Applicability:** DTS is a data-plane service handling cross-database data flow. The five pillars are assessed for operational guidance.

## 2.1 安全支柱 Security

### IAM Permissions

Minimum RAM permissions required for DTS operations:

| API Operation | Required RAM Action | Resource Scope |
|---------------|--------------------|----------------|
| CreateDtsInstance | `dts:CreateDtsInstance` | `acs:dts:*:*:instance/*` |
| ConfigureDtsJob | `dts:ConfigureDtsJob` | `acs:dts:*:*:instance/*` |
| DescribeDtsJobs | `dts:DescribeDtsJobs` | `acs:dts:*:*:*` |
| DeleteDtsJob | `dts:DeleteDtsJob` | `acs:dts:*:*:instance/*` |
| StartDtsJob | `dts:StartDtsJob` | `acs:dts:*:*:instance/*` |
| StopDtsJob | `dts:StopDtsJob` | `acs:dts:*:*:instance/*` |

**Managed policy:** `AliyunDTSFullAccess` provides full access. For least privilege, create custom policies scoped to specific instances.

### Credential Management

- DTS source/target database passwords are highly sensitive — NEVER log or echo
- Use `{{env.*}}` for Alibaba Cloud credentials
- Database credentials should use dedicated DTS users with minimal privileges
  - Source: `SELECT, REPLICATION SLAVE, REPLICATION CLIENT` (for MySQL CDC)
  - Target: `INSERT, UPDATE, DELETE, CREATE, ALTER` (for data write)

### Network Security

- DTS servers have fixed CIDR blocks — get via `DescribeDTSIP`
- For self-managed databases (ECS/IDC): MUST add DTS CIDR to security group / firewall
- For Alibaba Cloud native databases (RDS, PolarDB): DTS auto-adds CIDR when "Auto Whitelist" is enabled
- Prefer VPC connection for DTS → database communication over public endpoints

### Data in Transit

- All DTS API calls use HTTPS
- Data transfer between DTS and databases can be over public network or VPC
- For sensitive data: use VPC peering or CEN for encrypted in-transit paths

## 2.2 稳定支柱 Stability

### Failure-Oriented Design

| Failure Mode | Mitigation |
|-------------|------------|
| Source database failure | DTS pauses; resumes after source recovers (checkpoint preserved) |
| Target database failure | DTS retries with backoff; cached writes maintained for limited time |
| Network partition | DTS retries with exponential backoff; checkpoint allows resumption |
| DTS service failure (rare) | Alibaba Cloud managed — DTS HA built in; tasks resume automatically |

### Operational Control

- **Precheck:** Always run precheck before starting migration (ConfigureDtsJob → check DescribePreCheckStatus)
- **Staged rollouts:** Test migration in staging environment before production
- **Backup before migration:** Create source database backup before DTS migration
- **Monitor sync delay:** Set up alerts for delay exceeding threshold

### Emergency Recovery

**Phase 1: Backup Verification**
```bash
# Verify source database has valid backup (via relevant DB skill)
# e.g., for RDS MySQL
aliyun rds DescribeBackups --DBInstanceId "{{user.source_instance_id}}"
```

**Phase 2: DTS Recovery**
```bash
# Check task status
aliyun dts DescribeDtsJobDetail \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"

# If failed, check error
# Fix underlying issue (connectivity, permissions, storage)
# Resume from checkpoint
aliyun dts StartDtsJob \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"
```

**Phase 3: Post-Recovery Validation**
```bash
# Verify data consistency
aliyun dts DescribeCheckJobs \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}"

# Check sync delay
DETAIL=$(aliyun dts DescribeDtsJobDetail \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}")
echo "Current delay: $(echo "$DETAIL" | jq -r '.Delay')s"
```

## 2.3 成本支柱 Cost

### Billing Model Comparison

| Model | Charge Basis | Best For | Savings |
|-------|-------------|----------|---------|
| Pay-As-You-Go | Per hour | One-time migration, short tasks | N/A (no commitment) |
| Subscription (1 month) | Monthly | Short sync projects | ~15% vs hourly |
| Subscription (1 year) | Yearly | Long-running production sync | ~50% vs hourly |
| Subscription (3 years) | 3-year commitment | Stable, mission-critical CDC | ~83% vs hourly |

### DTS Unit (DU) Cost Optimization

| Scenario | Recommended DU | Monthly Cost Estimate |
|----------|---------------|----------------------|
| Small migration (< 10 GB) | 1 | Minimal (hourly) |
| Medium sync (10-100 GB/day) | 2 | Moderate |
| Large sync (100+ GB/day) | 4+ | Higher (optimize vs performance) |
| Batch ETL | Varies | Scale down after batch completes |

### Waste Detection

| Idle Pattern | Detection | Action |
|-------------|-----------|--------|
| Migration task finished but instance not deleted | DescribeDtsJobs: status=Finished but instance exists | DeleteDtsJob to release instance |
| Sync task stopped for > 7 days | DescribeDtsJobs: status=Stopped, unchanged for 7+ days | Confirm intentional; release if not needed |
| Over-provisioned DU | Monitor DU usage < 50% sustained | ModifyDtsJobDuLimit to reduce DU |
| Subscription instance with no active task | DescribeDtsJobs returns empty for an instance | Release subscription instance |

## 2.4 效率支柱 Efficiency

### Batch Operations

```bash
# Start multiple DTS tasks at once
aliyun dts StartDtsJobs \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobIds "[\"job1_id\",\"job2_id\",\"job3_id\"]"

# Stop multiple DTS tasks at once
aliyun dts StopDtsJobs \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobIds "[\"job1_id\",\"job2_id\"]"

# Delete multiple jobs
aliyun dts DeleteDtsJobs \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobIds "[\"job1_id\",\"job2_id\"]"
```

### CI/CD Integration

- DTS CLI outputs JSON — compatible with pipeline parsing (jq)
- Can be invoked in deployment pipelines for structured database migration
- Store DTS job IDs in pipeline variables for lifecycle management

### Automation Patterns

| Pattern | Implementation |
|---------|---------------|
| Scheduled migration | CreateDtsInstance + ConfigureDtsJob in script |
| Auto-decommission | Cron job: check Finished tasks → DeleteDtsJob |
| Self-healing sync | Cron job: check Failed status → DescribeDtsJobDetail → retry |
| Cost optimizer | Cron job: check idle instances → DeleteDtsJob |

## 2.5 性能支柱 Performance

### Performance Metrics

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Sync Delay | < 5s | 5-30s | > 60s |
| RPS | > 1000 | 100-1000 | < 100 |
| DU Utilization | < 60% | 60-80% | > 80% |
| Memory Usage | < 70% | 70-85% | > 85% |

### Performance Baseline

Establish baseline after DTS task stabilizes (typically 1 hour after start):

```bash
for i in $(seq 1 12); do
  DETAIL=$(aliyun dts DescribeDtsJobDetail \
    --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
    --DtsJobId "{{user.dts_job_id}}")
  echo "$(date): Delay=$(echo "$DETAIL" | jq -r '.Delay')s"
  sleep 300
done
```

### Scaling Recommendations

| Symptom | Action |
|---------|--------|
| Delay > 60s sustained | Increase DU limit via ModifyDtsJobDuLimit |
| RPS < expected | Check source DB performance; consider scaling source |
| Memory > 85% | Decrease DU or split into parallel tasks |
| Target write bottleneck | Scale up target database (via relevant DB skill) |