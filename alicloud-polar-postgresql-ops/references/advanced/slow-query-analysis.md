# Slow Query Analysis

> PolarDB PostgreSQL 慢查询分析指南

## Overview

本文档提供 PolarDB PostgreSQL 慢查询分析的完整指南，包括慢日志查询、Top N 识别和优化建议。

## Slow Log Configuration

### View Slow Log Settings

```bash
# 查看慢日志配置
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=SlowLogSize rows=DBCluster
```

### Modify Slow Log Settings

```bash
# 修改慢日志阈值（需要修改参数组）
aliyun polardb ModifyDBClusterParameters \
  --DBClusterId "{{user.db_cluster_id}}" \
  --Parameters "[{\"ParameterName\":\"log_min_duration_statement\",\"ParameterValue\":\"1000\"}]" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Query Slow Logs

### CLI: DescribeSlowLogs

```bash
# 查询慢日志概览
aliyun polardb DescribeSlowLogs \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 按数据库过滤
aliyun polardb DescribeSlowLogs \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --DBName "{{user.db_name}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### CLI: DescribeSlowLogRecords

```bash
# 查询慢日志详细记录
aliyun polardb DescribeSlowLogRecords \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 查询特定 SQL 的慢日志
aliyun polardb DescribeSlowLogRecords \
  --DBClusterId "{{user.db_cluster_id}}" \
  --SQLId "{{user.sql_id}}" \
  --StartTime "$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Top N Slow Queries

### Identify Top Slow Queries

```bash
#!/bin/bash
# top-slow-queries.sh

CLUSTER_ID="{{user.db_cluster_id}}"
REGION="{{env.ALIBABA_CLOUD_REGION_ID}}"
START_TIME="$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "=== Top 10 Slow Queries (Last 24h) ==="

aliyun polardb DescribeSlowLogs \
  --DBClusterId "$CLUSTER_ID" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  --RegionId "$REGION" \
  --output json | jq -r '.Items.SQLSlowLog | sort_by(.MaxExecutionTime) | reverse | .[0:10] | .[] | "SQL ID: \(.SQLId)\nTime: \(.MaxExecutionTime)ms\nCount: \(.TotalExecutionCounts)\nDB: \(.DBName)\nSQL: \(.SQLText)\n---"'
```

### Slow Query Statistics

```bash
#!/bin/bash
# slow-query-stats.sh

CLUSTER_ID="{{user.db_cluster_id}}"
REGION="{{env.ALIBABA_CLOUD_REGION_ID}}"
START_TIME="$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "=== Slow Query Statistics (Last 24h) ==="

# 获取慢日志统计
SLOW_LOGS=$(aliyun polardb DescribeSlowLogs \
  --DBClusterId "$CLUSTER_ID" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  --RegionId "$REGION" \
  --output json)

# 统计总数
TOTAL_COUNT=$(echo "$SLOW_LOGS" | jq '.Items.SQLSlowLog | length')
echo "Total Slow Queries: $TOTAL_COUNT"

# 按数据库统计
echo ""
echo "By Database:"
echo "$SLOW_LOGS" | jq -r '.Items.SQLSlowLog | group_by(.DBName) | .[] | "  \(.[0].DBName): \(length) queries"'

# 统计平均执行时间
echo ""
echo "Average Execution Time by DB:"
echo "$SLOW_LOGS" | jq -r '.Items.SQLSlowLog | group_by(.DBName) | .[] | "  \(.[0].DBName): \(map(.AvgExecutionTime | tonumber) | add / length) ms"'
```

## Analysis Queries

### System Views

```sql
-- 查看当前慢查询 (需要 superuser 权限)
SELECT pid, usename, application_name, client_addr, 
       query_start, state, query,
       EXTRACT(EPOCH FROM (NOW() - query_start)) AS execution_time_seconds
FROM pg_stat_activity
WHERE state = 'active'
  AND query_start < NOW() - INTERVAL '5 seconds'
ORDER BY query_start;

-- 查看等待锁的查询
SELECT wait_event_type, wait_event, count(*)
FROM pg_stat_activity
WHERE wait_event_type IS NOT NULL
GROUP BY wait_event_type, wait_event
ORDER BY count(*) DESC;

-- 查看表扫描情况
SELECT schemaname, tablename, seq_scan, seq_tup_read,
       idx_scan, idx_tup_fetch,
       CASE WHEN seq_scan + idx_scan = 0 THEN 0
            ELSE round(100.0 * seq_scan / (seq_scan + idx_scan), 2)
       END as seq_scan_percent
FROM pg_stat_user_tables
ORDER BY seq_scan DESC
LIMIT 20;
```

## Optimization Recommendations

### Index Recommendations

```sql
-- 查找缺少索引的表 (高 seq_scan)
SELECT schemaname, tablename, seq_scan, seq_tup_read,
       seq_tup_read / NULLIF(seq_scan, 0) AS avg_tuples_per_scan
FROM pg_stat_user_tables
WHERE seq_scan > 100
  AND idx_scan < seq_scan * 0.1
ORDER BY seq_tup_read DESC;

-- 查找无用索引 (很少使用)
SELECT schemaname, tablename, indexrelname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan < 10
ORDER BY idx_scan;
```

### Query Analysis

```sql
-- 分析查询执行计划
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
SELECT * FROM your_table WHERE condition;

-- 查看查询统计
SELECT query, calls, total_exec_time, mean_exec_time,
       rows, 100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

## Automated Analysis Script

```bash
#!/bin/bash
# slow-query-analyzer.sh

CLUSTER_ID="{{user.db_cluster_id}}"
REGION="{{env.ALIBABA_CLOUD_REGION_ID}}"
START_TIME="$(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "# PolarDB PostgreSQL Slow Query Analysis Report"
echo "**Cluster**: $CLUSTER_ID"
echo "**Period**: $START_TIME to $END_TIME"
echo "**Generated**: $(date)"
echo ""

# 1. 慢查询概览
echo "## 1. Slow Query Overview"
SLOW_LOGS=$(aliyun polardb DescribeSlowLogs \
  --DBClusterId "$CLUSTER_ID" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  --RegionId "$REGION" \
  --output json)

TOTAL_COUNT=$(echo "$SLOW_LOGS" | jq '.Items.SQLSlowLog | length')
TOTAL_EXEC_TIME=$(echo "$SLOW_LOGS" | jq '[.Items.SQLSlowLog[].TotalExecutionTime | tonumber] | add')
AVG_EXEC_TIME=$(echo "$SLOW_LOGS" | jq '[.Items.SQLSlowLog[].AvgExecutionTime | tonumber] | add / length')

echo "| Metric | Value |"
echo "|--------|-------|"
echo "| Total Slow Queries | $TOTAL_COUNT |"
echo "| Total Execution Time | ${TOTAL_EXEC_TIME}ms |"
echo "| Average Execution Time | ${AVG_EXEC_TIME}ms |"
echo ""

# 2. Top 10 慢查询
echo "## 2. Top 10 Slowest Queries"
echo ""
echo "| Rank | SQL ID | Max Time | Count | Database |"
echo "|------|--------|----------|-------|----------|"
echo "$SLOW_LOGS" | jq -r '.Items.SQLSlowLog | sort_by(.MaxExecutionTime | tonumber) | reverse | .[0:10] | to_entries | .[] | "| \(.key + 1) | \(.value.SQLId[0:8])... | \(.value.MaxExecutionTime)ms | \(.value.TotalExecutionCounts) | \(.value.DBName) |"'
echo ""

# 3. 按数据库统计
echo "## 3. Statistics by Database"
echo ""
echo "| Database | Query Count | Total Time (ms) |"
echo "|----------|-------------|-----------------|"
echo "$SLOW_LOGS" | jq -r '.Items.SQLSlowLog | group_by(.DBName) | .[] | "| \(.[0].DBName) | \(length) | \([.[].TotalExecutionTime | tonumber] | add) |"'
echo ""

# 4. 优化建议
echo "## 4. Optimization Recommendations"
echo ""
echo "### 4.1 High Frequency Slow Queries"
echo "以下查询执行次数多且耗时较长，建议优先优化："
echo ""
echo "$SLOW_LOGS" | jq -r '.Items.SQLSlowLog | sort_by(.TotalExecutionCounts | tonumber) | reverse | .[0:5] | .[] | "- SQL ID: `\(.SQLId)`\n  - Count: \(.TotalExecutionCounts)\n  - Avg Time: \(.AvgExecutionTime)ms\n  - SQL: `\(.SQLText[0:100])...`\n"'

echo "### 4.2 General Recommendations"
echo ""
echo "1. **Add Indexes**: For queries with high seq_scan ratios"
echo "2. **Optimize WHERE clauses**: Ensure proper index usage"
echo "3. **Limit Result Sets**: Use LIMIT for large result sets"
echo "4. **Analyze Tables**: Run ANALYZE for updated statistics"
echo "5. **Check Connection Pooling**: Avoid connection overhead"

echo ""
echo "---"
echo "*End of Report*"
```

## Output Format

### Markdown Report

```markdown
# PolarDB PostgreSQL Slow Query Analysis Report
**Cluster**: pg-xxxxx
**Period**: 2026-05-26T10:00:00Z to 2026-05-27T10:00:00Z

## 1. Slow Query Overview

| Metric | Value |
|--------|-------|
| Total Slow Queries | 156 |
| Total Execution Time | 2456000ms |
| Average Execution Time | 15744ms |

## 2. Top 10 Slowest Queries

| Rank | SQL ID | Max Time | Count | Database |
|------|--------|----------|-------|----------|
| 1 | abc123... | 12500ms | 45 | production |
| 2 | def456... | 8900ms | 23 | production |

## 3. Optimization Recommendations

### 3.1 High Frequency Slow Queries
- SQL ID: `abc123`
  - Count: 45
  - Avg Time: 12500ms
  - Recommendation: Add index on `orders.created_at`
```

## Acceptance Criteria

| # | Criteria | Verification |
|---|----------|--------------|
| ✓ | **正确获取慢日志** | `DescribeSlowLogs` 返回数据 |
| ✓ | **Top N 查询识别** | 正确排序并提取 Top 10 |
| ✓ | **统计分析准确** | 聚合数据正确 |
| ✓ | **优化建议有效** | 建议可操作且有效 |
