# Standardized Prompt Templates — Alibaba Cloud ClickHouse

> **Purpose:** Reusable natural-language prompt examples for consistent AIOps interactions.
> **Version:** 1.0.0
> **Last Updated:** 2026-07-29
> **CLI Applicability:** `dual-path` (Enterprise Edition CLI `2023-05-22` + Classic Edition SDK `2019-11-11`)

---

## 1. Prompt Template Categories

| Category | Purpose | Usage Context |
|----------|---------|----------------|
| **Operation Prompts** | Execute specific operations | Create, modify, delete, restart instances |
| **Diagnostic Prompts** | Troubleshoot issues | Error resolution, slow query analysis |
| **Inspection Prompts** | Proactive monitoring | Daily/weekly inspections, capacity review |
| **Analysis Prompts** | Performance analysis | Optimization, cost analysis |
| **Report Prompts** | Generate reports | Inspection, compliance reports |

---

## 2. Operation Prompt Templates

### 2.1 Create ClickHouse Instance (Enterprise Edition)

```markdown
# Create ClickHouse Instance

**Context:**
- Region: {{region_id}}
- Environment: {{profile}} (production / staging / dev)
- Purpose: {{purpose}}

**Edition Selection:**
- Edition: Enterprise Edition (CLI `2023-05-22`) — required for serverless, multi-AZ, Computing Groups
- Plugin required: `aliyun-cli-clickhouse` (verify with `aliyun plugin list`)

**Required Parameters:**
- Description: {{instance_description}}
- Node Count: {{node_count}} (2-16 for Fixed; or use Serverless below)
- Engine Version: {{engine_version}} (latest stable: 23.x)

**Optional Parameters (Serverless):**
- NodeScaleMin: {{node_scale_min}} (min 4)
- NodeScaleMax: {{node_scale_max}} (recommend explicit; max 32)

**Optional Parameters (Multi-AZ):**
- MultiZone: {{multi_zone_json}} (zones + vswitches)

**Optional Parameters:**
- DBTimeZone: {{db_time_zone}} (default: UTC)
- StorageQuota: {{storage_quota_gb}}GB (per node, max 32000)
- ResourceGroupId: {{resource_group_id}}

**Pre-flight Checks:**
1. Verify plugin: `aliyun plugin list | grep aliyun-cli-clickhouse`
2. Verify region: `aliyun clickhouse DescribeRegions`
3. Check quota: `aliyun clickhouse DescribeDBInstances --RegionId {{region_id}}` (count < 10)
4. Validate VPC: see `alicloud-vpc-ops`
5. Validate VSwitch: see `alicloud-vpc-ops`

**Execution:**
- Execute: `aliyun clickhouse CreateDBInstance ...`
- Poll: `DescribeDBInstanceAttribute` every 30s until status = `Running` (max 30min)
- Validate: Endpoint accessible; security IP set

**Expected Output:**
- DBInstanceId: {{output.db_instance_id}}
- Status: Running
- Endpoints: {{output.endpoints}}
- NodeCount: {{output.node_count}}

**Error Handling:**
- QuotaExceeded → Request quota increase
- VpcNotFound / VswitchNotFound → Delegate to alicloud-vpc-ops
- InvalidParameter.NodeCount → Adjust to 2-16 (Fixed) or 4-32 (Serverless)
- EngineVersionNotSupported → Use 23.x for Enterprise
```

### 2.2 Restart ClickHouse Instance

```markdown
# Restart ClickHouse Instance

**Context:**
- Instance ID: {{instance_id}}
- Reason: {{restart_reason}}
- Maintenance Window: {{maintenance_window}}

**Pre-flight Safety Gate (REQUIRED):**
- ⚠️ Restart causes temporary service interruption
- Confirm: User has explicitly approved restart of {{instance_id}}
- Verify: `DescribeDBInstanceAttribute` shows status = `Running` (or `Stopped` for Start)
- Verify: No `OperationDenied.PendingTask` in current state
- Recommend: Backup before restart if data is critical

**Execution (Enterprise Edition):**
```bash
aliyun clickhouse RestartDBInstance \
  --DBInstanceId {{instance_id}} \
  --RegionId {{region_id}}
```

**Execution (Classic Edition — SDK):**
```go
client.RestartInstance(&clickhouse.RestartInstanceRequest{
    RegionId:     tea.String(regionId),
    DBInstanceId: tea.String(instanceId),
})
```

**Post-execution Validation:**
- Poll `DescribeDBInstanceAttribute` every 10s
- Status transition: `Running` → `Restarting` → `Running`
- Timeout: 300s
- On timeout: investigate `Status` reason; do not retry blindly

**Error Handling:**
- OperationDenied.InstanceStatus → Wait for stable state
- OperationDenied.PendingTask → Wait 30s, retry
- Throttling → Exponential backoff (2s → 4s → 8s)
```

### 2.3 Scale Up / Down ClickHouse Instance

```markdown
# Scale ClickHouse Instance

**Context:**
- Instance ID: {{instance_id}}
- Current Spec: {{current_node_count}} nodes × {{current_storage_gb}}GB
- Target Spec: {{target_node_count}} nodes × {{target_storage_gb}}GB
- Reason: {{scale_reason}} (capacity / cost / performance)

**Pre-flight Safety Gate:**
- ⚠️ Scale-down MAY cause data loss if storage > target quota
- Confirm: User has explicitly approved {{scale_direction}} for {{instance_id}}
- Verify: `cms DescribeMetricList --MetricName data_usage` < target storage
- Verify: No `OperationDenied.PendingTask` in current state

**Execution (Horizontal Scale - Enterprise):**
```bash
aliyun clickhouse ModifyDBInstanceClass \
  --DBInstanceId {{instance_id}} \
  --RegionId {{region_id}} \
  --NodeCount {{target_node_count}}
```

**Execution (Vertical Scale - Classic via SDK):**
```go
client.ModifyDBCluster(&clickhouse.ModifyDBClusterRequest{
    RegionId:     tea.String(regionId),
    DBInstanceId: tea.String(instanceId),
    // ... target spec fields
})
```

**Post-execution Validation:**
- Poll `DescribeDBInstanceAttribute` until status returns to `Running`
- Validate new node count / storage matches request
- Verify all endpoints still functional

**Error Handling:**
- OperationDenied.NotSupportInEdition → Wrong path; switch to Enterprise CLI
- StorageQuotaExceeded → Reduce data first or increase target
- PendingTask → Wait 30s, retry
```

### 2.4 Delete ClickHouse Instance

```markdown
# Delete ClickHouse Instance

**Context:**
- Instance ID: {{instance_id}}
- Instance Name: {{instance_name}}
- Data Backup Status: {{backup_status}}

**Pre-flight Safety Gate (MANDATORY):**
- ⚠️ Delete is IRREVERSIBLE — all data, backups, accounts will be lost
- Confirm: User has explicitly approved deletion of {{instance_name}} ({{instance_id}})
- Verify: Recent successful backup exists
  - `aliyun clickhouse DescribeBackups --StartTime <24h-ago> --EndTime <now>`
  - At least one backup with status = `Success`
- Verify: Instance status = `Running` (not currently being modified)
- Recommend: Create final manual backup before delete

**Execution (Enterprise Edition):**
```bash
# Pre-check: confirm backup
aliyun clickhouse DescribeBackups \
  --DBInstanceId {{instance_id}} \
  --RegionId {{region_id}} \
  --StartTime "$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# After user confirmation AND backup verification:
aliyun clickhouse DeleteDBInstance \
  --DBInstanceId {{instance_id}} \
  --RegionId {{region_id}}
```

**Execution (Classic Edition — SDK):**
```go
client.DeleteDBCluster(&clickhouse.DeleteDBClusterRequest{
    RegionId:     tea.String(regionId),
    DBInstanceId: tea.String(instanceId),
})
```

**Post-execution Validation:**
- Poll `DescribeDBInstanceAttribute` until `InvalidDBInstanceId.NotFound` (deleted)
- Timeout: 600s
- Verify: Cluster no longer appears in `DescribeDBInstances` list

**Error Handling:**
- InvalidDBInstanceId.NotFound → Already deleted (treat as success)
- OperationDenied.InstanceStatus → Wait for stable state
- BackupInProgress → Wait for backup to complete, then retry
```

### 2.5 Create ClickHouse Account

```markdown
# Create ClickHouse Account

**Context:**
- Instance ID: {{instance_id}}
- Account Name: {{account_name}}
- Account Type: {{account_type}} (Normal / Super)
- Authority: {{dml_auth_setting}} (ReadOnly / ReadWrite / All)
- Password: [REDACTED — do not include in trace]

**Pre-flight Checks:**
- Verify instance exists: `DescribeDBInstanceAttribute`
- Verify account doesn't exist: `DescribeAccounts`
- Verify password meets complexity:
  - Length: 8-32 chars
  - Composition: 3 of {upper / lower / digit / symbol}
- Verify authority choice is valid for account type:
  - Super accounts: can be any authority
  - Normal accounts: cannot use DDLOnly

**Execution (Enterprise Edition):**
```bash
aliyun clickhouse CreateAccount \
  --DBInstanceId {{instance_id}} \
  --Account {{account_name}} \
  --AccountType {{account_type}} \
  --Password "{{password}}" \
  --RegionId {{region_id}}
```

**Post-execution Validation:**
- Verify: `DescribeAccounts` shows new account
- Test: Connection test from authorized client (manual)

**Error Handling:**
- InvalidAccountPassword → Re-prompt with complexity rules
- QuotaExceeded.Account → Max 100 accounts; delete unused first
- InvalidDBInstanceId.NotFound → Instance deleted between checks
```

### 2.6 Modify Security IP Whitelist

```markdown
# Modify Security IP Whitelist

**Context:**
- Instance ID: {{instance_id}}
- Current Whitelist: {{current_whitelist}}
- New IPs: {{new_ips}}
- Modify Mode: {{modify_mode}} (1=append [default], 0=overwrite)

**Pre-flight Safety Gate:**
- ⚠️ `ModifyMode=0` (overwrite) can lock out all clients
- Recommend: Use `ModifyMode=1` (append) unless explicitly resetting
- Verify: {{new_ips}} is in valid CIDR or single IP format
- Confirm: User has explicitly approved adding {{new_ips}}

**Execution:**
```bash
# Append (safe, default)
aliyun clickhouse ModifySecurityIPList \
  --DBInstanceId {{instance_id}} \
  --RegionId {{region_id}} \
  --SecurityIPList "{{new_ips}}" \
  --GroupName default \
  --ModifyMode 1

# Overwrite (only when explicitly approved to reset)
aliyun clickhouse ModifySecurityIPList \
  --DBInstanceId {{instance_id}} \
  --RegionId {{region_id}} \
  --SecurityIPList "{{new_ips}}" \
  --GroupName default \
  --ModifyMode 0
```

**Post-execution Validation:**
- `DescribeSecurityIPList` to verify new whitelist
- Test: Connection from new IP (manual)

**Error Handling:**
- SecurityIPListInvalid → Verify CIDR format (e.g., 10.0.0.0/8)
- OperationDenied.PendingTask → Wait 30s, retry
```

---

## 3. Diagnostic Prompt Templates

### 3.1 Slow Query Investigation

```markdown
# Investigate Slow Queries

**Context:**
- Instance ID: {{instance_id}}
- Time Range: {{time_range}}
- Threshold: {{query_duration_ms}}ms

**Diagnostic Path:**
1. Pull slow query trend:
```bash
aliyun clickhouse DescribeSlowLogTrend \
  --DBInstanceId {{instance_id}} \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --QueryDurationMs {{query_duration_ms}}
```

2. Get top slow query records:
```bash
aliyun clickhouse DescribeSlowLogRecords \
  --DBInstanceId {{instance_id}} \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --PageSize 20
```

3. Check current process list (for active long queries):
```bash
aliyun clickhouse DescribeProcessList \
  --DBInstanceId {{instance_id}} \
  --RegionId {{region_id}}
```

4. Correlate with CMS metrics:
```bash
aliyun cms DescribeMetricList \
  --Namespace acs_clickhouse \
  --MetricName cpu_usage,memory_usage,disk_usage \
  --Dimensions '{"instanceId":"{{instance_id}}"}' \
  --StartTime <1h-ago> --EndTime <now>
```

**Output:**
- Top 10 slow queries with: duration, scanned rows, query text
- Peak time analysis
- Resource correlation (CPU/memory at slow query time)
- Root cause hypothesis

**Recommended Actions:**
- Optimize query (suggestion based on query text)
- Add index / pre-aggregation
- Scale up cluster
- Kill runaway query (if confirmed)
```

### 3.2 Connection Issue Investigation

```markdown
# Investigate Connection Issues

**Context:**
- Instance ID: {{instance_id}}
- Client IP: {{client_ip}}
- Error: {{connection_error}}

**Diagnostic Path:**
1. Verify endpoint exists:
```bash
aliyun clickhouse DescribeEndpoints \
  --DBInstanceId {{instance_id}} \
  --RegionId {{region_id}}
```

2. Verify client IP is whitelisted:
```bash
aliyun clickhouse DescribeSecurityIPList \
  --DBInstanceId {{instance_id}} \
  --RegionId {{region_id}}
```

3. Check connection usage:
```bash
aliyun cms DescribeMetricList \
  --Namespace acs_clickhouse \
  --MetricName connection_usage \
  --Dimensions '{"instanceId":"{{instance_id}}"}' \
  --StartTime <1h-ago> --EndTime <now>
```

4. Verify network path (delegate to alicloud-vpc-ops if VPC issue suspected)

**Output:**
- Endpoint status
- Whitelist status (is client IP allowed?)
- Connection usage trend
- Network path verification

**Recommended Actions:**
- Add IP to whitelist (use ModifyMode=1, append)
- Create endpoint if missing
- Scale cluster if connection_usage > 80%
- Delegate to vpc-ops if VPC peering broken
```

---

## 4. Inspection Prompt Templates

### 4.1 Daily Health Inspection

```markdown
# Daily ClickHouse Health Inspection

**Scope:** All ClickHouse instances in region {{region_id}}

**For each instance:**
1. Status check: `DescribeDBInstanceAttribute` (must be `Running`)
2. Backup verification: `DescribeBackups` last 24h (at least 1 Success)
3. Backup policy: `DescribeBackupPolicy` (set and recent)
4. Slow query count: `DescribeSlowLogTrend` (alerts if spike)
5. Failed query count: CMS metric (alert if > 0)
6. Resource usage: CMS metrics (CPU/Memory/Disk/Connection)
7. Account audit: `DescribeAccounts` (no unexpected accounts)
8. Endpoint audit: `DescribeEndpoints` (no orphan endpoints)

**Output Format:**
| Instance | Status | Backup | CPU | Memory | Disk | Conn | Slow Q/min | Failed Q/min | Issues |
|----------|--------|--------|-----|--------|------|------|------------|--------------|--------|

**Alert Conditions:**
- Status != Running
- No backup in last 24h
- Any metric > 80% sustained 10min
- failed_query_count > 0
- Unexpected accounts detected
```

### 4.2 Weekly Capacity Review

```markdown
# Weekly ClickHouse Capacity Review

**Scope:** Production ClickHouse instances

**Analysis:**
1. Resource utilization trends (7-day, 30-day)
2. Storage growth rate (project 30/60/90 day capacity)
3. Query performance trends (P50/P95/P99)
4. Connection patterns (peak hours)
5. Backup size growth
6. Cost per instance (estimated)

**Output:**
| Instance | Avg CPU | Peak CPU | Storage Used | Storage Growth/wk | Projected Full | Cost/mo | Optimization |
|----------|---------|----------|--------------|--------------------|----------------|---------|--------------|

**Recommended Actions:**
- Right-size underutilized instances (avg CPU < 20%)
- Scale up approaching-capacity instances
- Consider Serverless for variable workloads
- Delete idle dev/test clusters
```

---

## 5. Analysis Prompt Templates

### 5.1 Cost Analysis

```markdown
# ClickHouse Cost Analysis

**Inputs:**
- Time period: {{time_period}}
- Region: {{region_id}}

**For each instance:**
1. Compute cost: NodeCount × hours × hourly_rate
2. Storage cost: storage_gb × monthly_rate
3. Backup cost: backup_size × retention × rate
4. Network cost: outbound traffic (if applicable)

**Output:**
| Instance | Edition | Spec | Compute Cost | Storage Cost | Backup Cost | Total | Recommendation |
|----------|---------|------|--------------|--------------|-------------|-------|----------------|

**Optimization Suggestions:**
- Serverless for variable workloads
- Right-size over-provisioned Fixed clusters
- Reduce backup retention
- Consolidate dev/test clusters
- Stop (not delete) for short-term pause
```

### 5.2 Performance Analysis

```markdown
# ClickHouse Performance Analysis

**Inputs:**
- Instance ID: {{instance_id}}
- Time period: {{time_period}}

**Analysis:**
1. Query latency: P50/P95/P99 from `DescribeSlowLogTrend`
2. Query throughput: qps from CMS
3. Resource utilization: CPU/Memory/Disk/IO
4. Top slow queries: `DescribeSlowLogRecords`
5. Failed query patterns
6. Storage I/O patterns

**Output:**
- Performance summary
- Bottleneck identification
- Top 10 slow queries with optimization suggestions
- Scaling recommendations
```

---

## 6. Report Prompt Templates

### 6.1 Inspection Report

```markdown
# Generate ClickHouse Inspection Report

**Scope:** {{scope}} (all instances / single instance / region)
**Period:** {{period}}

**Sections:**
1. Executive Summary
   - Total instances
   - Healthy / Warning / Critical counts
   - Total estimated monthly cost
2. Status Overview
   - Per-instance status table
3. Backup Status
   - Last backup per instance
   - Backup policy compliance
4. Resource Utilization
   - Top 10 highest CPU
   - Top 10 highest memory
   - Top 10 highest storage
5. Performance
   - Slow query trends
   - Failed query patterns
6. Security
   - Whitelist audit
   - Account audit
7. Cost Analysis
   - Cost by instance
   - Cost optimization opportunities
8. Recommendations
   - P0 (immediate)
   - P1 (this week)
   - P2 (this month)
9. Action Items
   - Owner / Due date / Status
```

### 6.2 Compliance Report

```markdown
# Generate ClickHouse Compliance Report

**Scope:** {{scope}}
**Standard:** Alibaba Cloud Well-Architected Framework

**Check Items:**
- [ ] All prod clusters in VPC
- [ ] All prod clusters have backup policy
- [ ] All prod clusters have multi-AZ (Enterprise)
- [ ] No public endpoints in production
- [ ] No 0.0.0.0/0 in security whitelist (prod)
- [ ] RAM least-privilege applied
- [ ] ActionTrail enabled
- [ ] Recent backup exists (24h)
- [ ] CMS alarms configured for prod
- [ ] Slow query monitoring enabled

**Output:**
| Check | Result | Evidence | Remediation |
|-------|--------|----------|-------------|
```

---

*These standardized prompt examples provide consistent AIOps interaction patterns. For GCL internal templates, see [prompt-templates.md](prompt-templates.md). For error codes, see [troubleshooting.md](troubleshooting.md).*
