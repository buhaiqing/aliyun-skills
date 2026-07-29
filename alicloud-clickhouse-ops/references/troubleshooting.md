# Troubleshooting Guide — Alibaba Cloud ClickHouse

> **Purpose:** Common error codes, diagnostic procedures, and recovery patterns.
> **Version:** 1.0.0
> **Last Updated:** 2026-07-29
> **CLI Applicability:** `dual-path` (Enterprise Edition CLI `2023-05-22` + Classic Edition SDK `2019-11-11`)

---

## 1. Error Code Reference (≥ 10 Codes)

| Code / HTTP | Meaning | Agent Action | UX Feedback |
|-------------|---------|--------------|-------------|
| `InvalidParameter` / 400 | Request parameter validation failed | Fix parameter per OpenAPI spec | `[ERROR] InvalidParameter: Check parameter values. See API docs for valid ranges.` |
| `InvalidParameter.NodeCount` / 400 | Node count out of valid range (2-16 fixed, 4-32 serverless) | Adjust to valid range | `[ERROR] InvalidParameter.NodeCount: Node count {n} not in valid range. Use 2-16 (fixed) or 4-32 (serverless).` |
| `InvalidParameter.StorageQuota` / 400 | Storage quota out of valid range | Adjust to valid range | `[ERROR] InvalidParameter.StorageQuota: Storage {gb}GB invalid. Max 32000GB per node.` |
| `InvalidDBInstanceId.NotFound` / 404 | Instance ID does not exist | Verify ID via DescribeDBInstances | `[ERROR] InvalidDBInstanceId.NotFound: Instance {id} not found. Verify ID or describe in region.` |
| `InvalidDBName.NotFound` / 400 | Database name not found on instance | Verify via DescribeDBInstanceDataSources | `[ERROR] InvalidDBName.NotFound: Database {dbname} not found on {instance}.` |
| `InvalidAccountName.NotFound` / 400 | Account name does not exist | Verify via DescribeAccounts | `[ERROR] InvalidAccountName.NotFound: Account {account} not found on {instance}.` |
| `InvalidAccountPassword` / 400 | Password does not meet complexity rules | Use password meeting complexity | `[ERROR] InvalidAccountPassword: Password must be 8-32 chars, mix of upper/lower/digit/symbol.` |
| `RegionNotSupported` / 400 | ClickHouse not available in this region | Use supported region | `[ERROR] RegionNotSupported: ClickHouse not available in {region}. Use: cn-hangzhou, cn-shanghai, etc.` |
| `QuotaExceeded.DBInstance` / 400 | Instance quota limit reached | Request quota increase | `[ERROR] QuotaExceeded: Instance quota reached. Default 10 per region. Request quota increase at console.` |
| `QuotaExceeded.Account` / 400 | Account count exceeds 100 per cluster | Delete unused accounts | `[ERROR] QuotaExceeded.Account: Max 100 accounts per cluster. Delete unused accounts first.` |
| `QuotaExceeded.DB` / 400 | Database count exceeds 256 per cluster | Delete unused databases | `[ERROR] QuotaExceeded.DB: Max 256 databases per cluster. Delete unused databases first.` |
| `VpcNotFound` / 404 | VPC ID not found in region | Create VPC via vpc-ops | `[ERROR] VpcNotFound: VPC {id} not found. Create VPC using alicloud-vpc-ops.` |
| `VswitchNotFound` / 404 | VSwitch not found | Create VSwitch in VPC | `[ERROR] VswitchNotFound: VSwitch {id} not found. Create in VPC first.` |
| `Forbidden.RAM` / 403 | RAM policy denies action | Add RAM permission | `[ERROR] Forbidden.RAM: RAM policy denies {action}. Add clickhouse:* permission.` |
| `OperationDenied.InstanceStatus` / 403 | Instance in wrong state for operation | Wait for stable state | `[ERROR] OperationDenied: Instance status {status} not valid for operation. Wait for Running.` |
| `OperationDenied.PendingTask` / 403 | Another operation in progress | Wait and retry | `[ERROR] OperationDenied: Pending operation. Wait 30s and retry.` |
| `OperationDenied.NotSupportInEdition` / 403 | Operation not supported in current edition (Classic vs Enterprise) | Use edition-appropriate operation | `[ERROR] OperationDenied.NotSupportInEdition: {op} not supported in {edition}. Use Enterprise/Classic edition path.` |
| `Throttling` / 429 | API rate limit exceeded | Exponential backoff retry | `⚠️ Throttling: Rate limit. Retrying in 2s... (attempt {n}/3)` |
| `InternalError` / 500 | Server-side error | Retry with backoff; escalate | `[ERROR] InternalError: Server error. RequestId: {id}. Retry or escalate.` |
| `ServiceUnavailable` / 503 | Service temporarily unavailable | Retry later | `[ERROR] ServiceUnavailable: Service down. Retry in 60s.` |
| `EngineVersionNotSupported` / 400 | Engine version not available | Use supported version | `[ERROR] EngineVersionNotSupported: Version {v} not supported. Use 23.x for Enterprise, 21.x for Classic.` |
| `CategoryNotSupported` / 400 | Cluster category not available | Use valid category (Fixed/Serverless) | `[ERROR] CategoryNotSupported: Category {cat} not valid. Use: Fixed or Serverless.` |
| `InvalidConnectionString` / 400 | Endpoint connection string invalid | Use valid prefix | `[ERROR] InvalidConnectionString: Connection prefix {prefix} not valid. Use 5-40 lowercase chars.` |
| `BackupInProgress` / 409 | Backup already running | Wait for current backup | `[ERROR] BackupInProgress: Backup in progress. Wait for completion before creating another.` |
| `SecurityIPListInvalid` / 400 | Security IP list format invalid | Use valid CIDR/IP | `[ERROR] SecurityIPListInvalid: {list} not valid. Use CIDR (10.0.0.0/8) or IP (1.2.3.4).` |
| `ComputingGroupNotFound` / 404 | Computing group ID not found | Verify via DescribeEndpoints | `[ERROR] ComputingGroupNotFound: ComputingGroup {cg} not found. Check Enterprise Edition spec.` |

---

## 2. Diagnostic Procedure

### Order of Investigation

```text
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Describe Instance → Get current status            │
│          aliyun clickhouse DescribeDBInstanceAttribute      │
│            --RegionId {{region}} --DBInstanceId {{id}}     │
├─────────────────────────────────────────────────────────────┤
│  Step 2: List Instances → Verify instance exists in region │
│          aliyun clickhouse DescribeDBInstances              │
│            --RegionId {{region}}                            │
├─────────────────────────────────────────────────────────────┤
│  Step 3: Check Instance Status → Identify operation state  │
│          Status: Running | Creating | Stopped | Upgrading   │
├─────────────────────────────────────────────────────────────┤
│  Step 4: Check Endpoints → Verify network connectivity     │
│          aliyun clickhouse DescribeEndpoints                │
│            --DBInstanceId {{id}} --RegionId {{region}}      │
├─────────────────────────────────────────────────────────────┤
│  Step 5: Check Slow Logs → Review query performance         │
│          aliyun clickhouse DescribeSlowLogRecords           │
│            --DBInstanceId {{id}}                            │
├─────────────────────────────────────────────────────────────┤
│  Step 6: Check CMS Metrics → Review resource usage         │
│          aliyun cms DescribeMetricList                      │
│            --Namespace acs_clickhouse --MetricName cpu_usage│
├─────────────────────────────────────────────────────────────┤
│  Step 7: Check Process List → Identify running queries     │
│          aliyun clickhouse DescribeProcessList              │
│            --DBInstanceId {{id}} --RegionId {{region}}     │
├─────────────────────────────────────────────────────────────┤
│  Step 8: Check Backup Policy → Verify backup configuration  │
│          aliyun clickhouse DescribeBackupPolicy             │
│            --DBInstanceId {{id}} --RegionId {{region}}      │
└─────────────────────────────────────────────────────────────┘
```

### Diagnostic Code Examples

#### Check Instance Status (CLI - Enterprise Edition)

```bash
# Get instance detail
aliyun clickhouse DescribeDBInstanceAttribute \
  --RegionId cn-hangzhou \
  --DBInstanceId cc-bp1xxxxxxxxxx

# Parse status from JSON output
STATUS=$(aliyun clickhouse DescribeDBInstanceAttribute \
  --RegionId cn-hangzhou \
  --DBInstanceId cc-bp1xxxxxxxxxx \
  --output cols=DBInstanceStatus \
  rows=Data.DBInstance.DBInstanceStatus 2>/dev/null)
echo "Instance Status: $STATUS"
```

#### Kill Long-Running Query (Enterprise Edition)

```bash
# Step 1: Find long queries
aliyun clickhouse DescribeProcessList \
  --DBInstanceId cc-bp1xxxxxxxxxx \
  --RegionId cn-hangzhou

# Step 2: Kill the query by process ID
aliyun clickhouse KillProcess \
  --DBInstanceId cc-bp1xxxxxxxxxx \
  --RegionId cn-hangzhou \
  --ProcessId 12345
```

#### Check Backup Status (Enterprise Edition)

```bash
# List recent backups
aliyun clickhouse DescribeBackups \
  --DBInstanceId cc-bp1xxxxxxxxxx \
  --RegionId cn-hangzhou \
  --StartTime "$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Verify backup policy
aliyun clickhouse DescribeBackupPolicy \
  --DBInstanceId cc-bp1xxxxxxxxxx \
  --RegionId cn-hangzhou
```

#### Pull CMS Metrics (Cross-Edition)

```bash
# CPU usage for last hour
aliyun cms DescribeMetricList \
  --Namespace acs_clickhouse \
  --MetricName cpu_usage \
  --Dimensions '{"instanceId":"cc-bp1xxxxxxxxxx"}' \
  --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

#### Classic Edition SDK Pattern (Go)

```go
import (
    "fmt"
    "os"
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    clickhouse "github.com/alibabacloud-go/clickhouse-20191111/v3/client"
)

config := &openapi.Config{
    AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
    AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
    Endpoint:        tea.String("clickhouse.aliyuncs.com"),
}
client, _ := clickhouse.NewClient(config)

resp, err := client.DescribeDBInstanceAttribute(&clickhouse.DescribeDBInstanceAttributeRequest{
    RegionId:     tea.String("cn-hangzhou"),
    DBInstanceId: tea.String("cc-bp1xxxxxxxxxx"),
})
if err != nil {
    if strings.Contains(err.Error(), "InvalidDBInstanceId.NotFound") {
        fmt.Println("❌ Instance not found")
        return
    }
    panic(err)
}
fmt.Printf("Status: %s\n", *resp.Body.Data.DBInstance.DBInstanceStatus)
```

---

## 3. Common Failure Scenarios

### 3.1 Cannot Connect to ClickHouse

**Symptoms:**
- Application connection timeout
- `Connection refused` errors
- DNS resolution failures

**Diagnostic Path:**

```text
1. DescribeEndpoints → check endpoint exists
2. DescribeSecurityIPList → check client IP is whitelisted
3. Check VPC peering / route table → verify network path
4. cms DescribeMetricList connection_usage → check connection load
```

**Recovery:**

| Root Cause | Action |
|------------|--------|
| Client IP not whitelisted | `ModifySecurityIPList` to add client CIDR |
| Endpoint not created | `CreateEndpoint` to provision endpoint |
| VPC peering broken | Delegate to `alicloud-vpc-ops` |
| Connection quota exceeded | Scale cluster or reduce application pool size |

### 3.2 Slow Query Performance

**Symptoms:**
- Queries taking longer than usual
- High CPU/memory utilization
- `slow_query_count` alarm firing

**Diagnostic Path:**

```text
1. DescribeSlowLogTrend → identify peak hours
2. DescribeSlowLogRecords → get actual slow queries
3. DescribeProcessList → see currently running queries
4. cms memory_usage / cpu_usage → correlate with metrics
```

**Recovery:**

| Root Cause | Action |
|------------|--------|
| Long-running query | `KillProcess` after user confirmation |
| Unoptimized query | Suggest query rewrite (CTE, pre-aggregation) |
| Insufficient resources | `ModifyDBInstanceClass` to scale up |
| Storage I/O bottleneck | Upgrade disk or redistribute data |

### 3.3 Instance Stuck in Creating/Upgrading

**Symptoms:**
- Instance state stays in `Creating` / `Upgrading` for > 30 minutes
- API calls return `OperationDenied.PendingTask`

**Diagnostic Path:**

```text
1. DescribeDBInstanceAttribute → confirm stuck state
2. Check Status reason field (if available) → may surface underlying issue
3. ActionTrail → check recent API calls for errors
```

**Recovery:**

| Root Cause | Action |
|------------|--------|
| Resource provisioning delay | Wait + retry DescribeDBInstanceAttribute (up to 60min) |
| Underlying resource failure | Open ticket via workorder; do NOT retry blindly |
| Quota transient violation | Check `QuotaExceeded` errors in API response |

### 3.4 Backup Failure

**Symptoms:**
- `DescribeBackups` returns empty for the time range
- `BackupInProgress` repeated
- Backup retention not enforced

**Diagnostic Path:**

```text
1. DescribeBackupPolicy → verify policy is set
2. DescribeBackups → list actual backup runs
3. Check backup window time vs. current time
```

**Recovery:**

| Root Cause | Action |
|------------|--------|
| Policy not set | `CreateBackupPolicy` with appropriate schedule |
| Backup window conflict | `ModifyBackupPolicy` to set non-overlapping window |
| Disk space insufficient | `ModifyDBInstanceConfig` to reduce retention OR scale storage |
| Concurrent backup in progress | Wait for previous backup to complete |

### 3.5 Security IP Lockout

**Symptoms:**
- All connections refused after security IP change
- Even known IPs cannot connect

**Recovery (Critical):**

```bash
# Reset to allow all (development only — DO NOT use in production)
aliyun clickhouse ModifySecurityIPList \
  --DBInstanceId cc-bp1xxxxxxxxxx \
  --RegionId cn-hangzhou \
  --SecurityIPList "0.0.0.0/0" \
  --ModifyMode 0

# Production: add specific IP without removing existing
aliyun clickhouse ModifySecurityIPList \
  --DBInstanceId cc-bp1xxxxxxxxxx \
  --RegionId cn-hangzhou \
  --SecurityIPList "10.0.0.0/8,172.16.0.0/12" \
  --ModifyMode 1  # 1=append, 0=overwrite
```

> **Warning:** `--ModifyMode 0` (overwrite) can lock out all clients. Always use `1` (append) unless explicitly resetting.

### 3.6 Edition Mismatch (Classic vs Enterprise)

**Symptoms:**
- `OperationDenied.NotSupportInEdition` error
- Command not found in CLI
- SDK method returns "API not found"

**Recovery:**

| Symptom | Cause | Action |
|---------|-------|--------|
| `StartDBInstance` not found | Classic edition does not support stop/start | Use Enterprise Edition CLI only |
| `ComputingGroupId` rejected | Classic edition has no Computing Groups | Omit ComputingGroupId parameter |
| `NodeScaleMin` rejected | Classic edition is fixed-spec only | Use `NodeCount` instead |
| `ModifyDBInstanceClass` succeeds but no scaling | Classic only supports vertical scaling | Plan for new instance migration |

### 3.7 Plugin Not Installed (CLI)

**Symptoms:**
- `aliyun clickhouse` returns "command not found"
- Or returns "unsupported product"

**Recovery:**

```bash
# Install the ClickHouse plugin
aliyun plugin install --names aliyun-cli-clickhouse

# Verify installation
aliyun clickhouse DescribeRegions

# If plugin install fails (network issue):
# 1. Check `aliyun version` (must be v3.0.0+)
# 2. Check network: `curl -I https://github.com/aliyun/aliyun-cli/releases`
# 3. Manually download from https://github.com/aliyun/aliyun-cli-clickhouse/releases
```

---

## 4. Edition Selection Decision Tree

```text
Need serverless scaling / multi-AZ / Computing Groups?
├─ YES → Use Enterprise Edition CLI (2023-05-22)
│         aliyun clickhouse ...
└─ NO  → Is instance already Classic?
        ├─ YES → Use Classic Edition SDK (2019-11-11)
        │         github.com/alibabacloud-go/clickhouse-20191111
        └─ NO  → Default to Enterprise Edition CLI
                  (new instances should use Enterprise)
```

---

## 5. Recovery Runbook Summary

| Symptom | First Action | Escalation |
|---------|--------------|------------|
| Connection refused | DescribeSecurityIPList | vpc-ops if VPC issue |
| Slow query | DescribeSlowLogTrend | Open ticket if > 10x baseline |
| Stuck creating | Wait 30min, retry | Workorder if > 60min |
| Backup missing | DescribeBackupPolicy | Manual snapshot via DescribeBackups |
| IP lockout | ModifySecurityIPList append | Workorder for production lockout |
| Edition mismatch | Switch to Enterprise CLI | Migrate Classic to Enterprise |
| Plugin missing | aliyun plugin install | Manual download from GitHub |

---

*For metric definitions, see [monitoring.md](monitoring.md). For CLI command map, see [cli-usage.md](cli-usage.md). For SDK method map, see [api-sdk-usage.md](api-sdk-usage.md).*
