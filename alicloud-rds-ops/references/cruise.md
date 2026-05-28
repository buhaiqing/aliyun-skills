## RDS Cruise (巡检工作流)

The **RDS Cruise** is a composite workflow that runs multiple checks in sequence
for comprehensive instance health assessment. Use this when the user asks to
"巡检", "检查", "健康检查", "health check", "cruise", or "inspect" an RDS instance.

### Cruise Execution Order

| Step | Operation | Purpose | On Failure |
|------|-----------|---------|------------|
| 1 | **DescribeDBInstanceAttribute** | Verify instance exists and get full status | HALT if not found |
| 2 | **DescribeDBInstanceNetInfo** | Check connection endpoints and network config | Log warning |
| 3 | **DescribeDBInstanceHAConfig** | Verify HA status and sync mode | Log warning if single-AZ |
| 4 | **DescribeResourceUsage** | Check disk, data, log, backup usage | Alert if > 80% |
| 5 | **DescribeDBInstancePerformance** | Check CPU, memory, connections, IOPS | Alert if thresholds exceeded |
| 6 | **DescribeSlowLogs** | Identify top slow queries | Log top 5 |
| 7 | **DescribeBackups** | Verify recent backup success | Alert if no successful backup in 24h |
| 8 | **DescribeParameters** | Check critical parameter values | Log non-default values |
| 9 | **DescribeErrorLogs** | Check recent errors | Log if errors found |
| 10 | **DescribeAccounts** | Audit accounts and privileges | Log if Super accounts exist |
| 11 | **DescribeDBInstanceIPArrayList** | Verify whitelist configuration | Log if too permissive (0.0.0.0/0) |

### Cruise CLI Script

```bash
#!/bin/bash
# RDS Cruise — Comprehensive Health Check
DB_INSTANCE_ID="{{user.db_instance_id}}"
REGION="{{user.region}}"
# Cross-platform date calculation (macOS and Linux)
if date -v-1d +%Y-%m-%dT%H:%M:%SZ >/dev/null 2>&1; then
  START_TIME="$(date -u -v-1d +%Y-%m-%dT%H:%M:%SZ)"
else
  START_TIME="$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ)"
fi
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "=== RDS Cruise: $DB_INSTANCE_ID ==="
echo ""

# 1. Instance Attribute
echo "[1/11] Instance Attribute"
aliyun rds DescribeDBInstanceAttribute --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 2. Net Info
echo "[2/11] Network Info"
aliyun rds DescribeDBInstanceNetInfo --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 3. HA Config
echo "[3/11] HA Configuration"
aliyun rds DescribeDBInstanceHAConfig --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 4. Resource Usage
echo "[4/11] Resource Usage"
aliyun rds DescribeResourceUsage --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 5. Performance — CPU
echo "[5/11] Performance (CPU)"
aliyun rds DescribeDBInstancePerformance \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --Key MySQL_CPUUsage --StartTime "$START_TIME" --EndTime "$END_TIME"
echo ""

# 6. Slow Logs
echo "[6/11] Slow Queries (Top 5)"
aliyun rds DescribeSlowLogs \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  --output cols=SQLText,MySQLTotalExecutionCounts,MySQLTotalExecutionTimes rows=Items.SQLSlowLog[0:5].{SQLText,MySQLTotalExecutionCounts,MySQLTotalExecutionTimes}
echo ""

# 7. Backups
echo "[7/11] Backups (Last 24h)"
aliyun rds DescribeBackups \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --StartTime "$START_TIME" --EndTime "$END_TIME"
echo ""

# 8. Parameters — Critical
echo "[8/11] Critical Parameters"
aliyun rds DescribeParameters --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 9. Error Logs
echo "[9/11] Error Logs"
aliyun rds DescribeErrorLogs \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --StartTime "$START_TIME" --EndTime "$END_TIME"
echo ""

# 10. Accounts
echo "[10/11] Accounts"
aliyun rds DescribeAccounts --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 11. IP Whitelist
echo "[11/11] IP Whitelist"
aliyun rds DescribeDBInstanceIPArrayList --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

echo "=== RDS Cruise Complete ==="
```

### Cruise Thresholds & Alerts

| Check | Warning Threshold | Critical Threshold | Agent Action |
|-------|-------------------|-------------------|--------------|
| Disk Usage | > 80% | > 90% | Alert; suggest storage expansion. Note: Calculate from `DiskUsed/DBInstanceStorage*100` |
| CPU Usage | > 80% | > 95% | Alert; suggest instance upgrade or query optimization |
| Memory Usage | > 80% | > 95% | Alert; suggest instance upgrade |
| Connections | > 80% of max_connections | > 95% | Alert; suggest connection pooling |
| Slow Queries | > 10 in 1h | > 50 in 1h | Alert; suggest index optimization |
| Backup Age | > 24h | > 48h | Alert; verify backup policy |
| Error Logs | Any errors | Repeated errors | Log; investigate root cause |
| IP Whitelist | 0.0.0.0/0 present | — | Security alert; restrict access |
| HA Sync Mode | Async | — | Warning; suggest Sync for critical workloads |

### Supported Anomaly Patterns (Multi-Indicator Correlation)

The following compound anomaly patterns are supported for advanced巡检 detection:

| # | Pattern Name | Condition | Diagnosis Path | DAS Trigger |
|---|--------------|-----------|----------------|-------------|
| 1 | CPU-IOPS 双高 | CPU > 80% + IOPS接近上限 | Section 1.1 + 1.5 | IOPS持续5分钟→DAS分析 |
| 2 | 连接-慢查询关联 | Connections > 80% + SlowQueries增加 | Section 1.3 + 8.1 | 慢查询>阈值→CreateDiagnosticReport |
| 3 | 内存-缓冲池瓶颈 | Memory > 85% + BufferPoolHitRate < 95% | Section 1.2 | 内存异常持续5分钟→DAS SQL诊断 |
| 4 | 磁盘-写入延迟 | DiskUsage > 85% + WriteLatency突增 | Section 1.4 + 1.5 | 磁盘写入延迟→DAS分析 |

> **Note:** Multi-indicator patterns require correlation analysis. See [Alert Diagnosis & Root Cause Analysis](references/alert-diagnosis.md) Section 2.1 for the Multi-Dimensional Correlation Matrix.

### DAS Diagnostic Delegation Triggers

When the following conditions are met, automatically delegate to DAS (Database Autonomy Service) for advanced diagnosis:

| Trigger Condition | DAS Action | Threshold |
|-------------------|------------|-----------|
| Slow query count exceeds threshold | DAS `CreateDiagnosticReport` | > 10 queries/hour |
| Performance anomaly persists > 5 minutes | DAS SQL diagnosis | 连续5分钟 CPU/Memory/IOPS异常 |
| Low execution efficiency detected | DAS `AnalyzePerformance` | SQL执行时间 > 1s 批量出现 |
| Buffer pool hit rate drops | DAS `AnalyzeInstance` | BufferPoolHitRate < 95% |
| Write latency spikes | DAS `AnalyzeIO` | WriteLatency 突增 > 100% |

> **Note:** DAS delegation requires the RDS instance to have DAS access enabled. Use `aliyun rds ModifyDasFlag` to enable if needed.

---

### Quick Diagnosis CLI (All-in-One)

For rapid triage, execute this composite command:

```bash
#!/bin/bash
# RDS Smart Diagnosis — Rapid Triage
DB_INSTANCE_ID="{{user.db_instance_id}}"
REGION="{{user.region}}"

# Cross-platform date
if date -v-1H +%Y-%m-%dT%H:%M:%SZ >/dev/null 2>&1; then
  START_TIME="$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"
else
  START_TIME="$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)"
fi
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "=== RDS Smart Diagnosis: $DB_INSTANCE_ID ==="
echo ""

# 1. Instance status and spec
echo "[1/6] Instance Attribute"
aliyun rds DescribeDBInstanceAttribute --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --output cols=DBInstanceId,DBInstanceStatus,Engine,EngineVersion,DBInstanceClass,DBInstanceStorage,MaxConnections rows=Items.DBInstanceAttribute[0].{DBInstanceId,DBInstanceStatus,Engine,EngineVersion,DBInstanceClass,DBInstanceStorage,MaxConnections}
echo ""

# 2. Resource usage
echo "[2/6] Resource Usage"
aliyun rds DescribeResourceUsage --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 3. Performance snapshot
echo "[3/6] Performance Snapshot"
aliyun rds DescribeDBInstancePerformance \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --Key MySQL_CPUUsage,MySQL_MemoryUsage,MySQL_Sessions,MySQL_ActiveSessions,MySQL_IOPS,MySQL_TPS,MySQL_QPS \
  --StartTime "$START_TIME" --EndTime "$END_TIME"
echo ""

# 4. HA status
echo "[4/6] HA Configuration"
aliyun rds DescribeDBInstanceHAConfig --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"
echo ""

# 5. Top slow queries
echo "[5/6] Top 5 Slow Queries"
aliyun rds DescribeSlowLogs \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  --output cols=SQLText,MySQLTotalExecutionCounts,MySQLTotalExecutionTimes,MySQLMaxExecutionTime rows=Items.SQLSlowLog[0:5].{SQLText,MySQLTotalExecutionCounts,MySQLTotalExecutionTimes,MySQLMaxExecutionTime}
echo ""

# 6. Recent errors
echo "[6/6] Recent Errors"
aliyun rds DescribeErrorLogs \
  --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  --output cols=ErrorInfo,CreateTime rows=Items.ErrorLog[0:5].{ErrorInfo,CreateTime}
echo ""

echo "=== Diagnosis Data Collection Complete ==="
echo "Apply correlation matrix and engine-specific diagnostic tree to identify root cause."
```

> **Note:** Replace `MySQL_*` metric keys with `Pg_*` or `MSSQL_*` prefixes
> for PostgreSQL or SQL Server instances.