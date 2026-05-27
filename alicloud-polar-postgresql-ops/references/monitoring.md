# Monitoring Reference

> PolarDB PostgreSQL 监控告警配置指南

## Overview

本文档提供 PolarDB PostgreSQL 的监控告警配置指南，包括 CloudMonitor (CMS) 集成、告警规则设置和监控仪表板。

## CMS Metrics

### 核心监控指标

| 指标名 | Namespace | 描述 | 单位 | 采集周期 |
|--------|-----------|------|------|----------|
| **CPUUtilization** | acs_polardb_dashboard | CPU 使用率 | % | 60s |
| **MemoryUtilization** | acs_polardb_dashboard | 内存使用率 | % | 60s |
| **ConnectionUsage** | acs_polardb_dashboard | 连接使用率 | % | 60s |
| **IOPSUsage** | acs_polardb_dashboard | IOPS 使用率 | % | 60s |
| **DiskUsage** | acs_polardb_dashboard | 磁盘使用率 | % | 300s |
| **TPS** | acs_polardb_dashboard | 每秒事务数 | count/s | 60s |
| **QPS** | acs_polardb_dashboard | 每秒查询数 | count/s | 60s |
| **BufferHitRate** | acs_polardb_dashboard | 缓冲区命中率 | % | 60s |
| **ReplicationLag** | acs_polardb_dashboard | 复制延迟 | ms | 60s |
| **ActiveSessions** | acs_polardb_dashboard | 活跃会话数 | count | 60s |

### 查询指标数据

```bash
# CPU 使用率
aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "CPUUtilization" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --Period 60 \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 连接使用率
aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "ConnectionUsage" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --Period 60 \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 复制延迟 (只读节点)
aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "ReplicationLag" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\",\"nodeId\":\"{{user.db_node_id}}\"}]" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --Period 60 \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Alarm Rules

### 告警规则配置

```bash
# CPU 高使用率告警
aliyun cms PutMetricRule \
  --RuleId "polardb-pg-cpu-high" \
  --RuleName "PolarDB PG CPU High" \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "CPUUtilization" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --EvaluationCount 3 \
  --Period 60 \
  --ComparisonOperator "GreaterThanThreshold" \
  --Threshold 80 \
  --Statistics "Average" \
  --ContactGroups "["\"dba-team\""]" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 连接数高使用率告警
aliyun cms PutMetricRule \
  --RuleId "polardb-pg-conn-high" \
  --RuleName "PolarDB PG Connection High" \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "ConnectionUsage" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --EvaluationCount 3 \
  --Period 60 \
  --ComparisonOperator "GreaterThanThreshold" \
  --Threshold 80 \
  --Statistics "Average" \
  --ContactGroups "["\"dba-team\""]" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 磁盘使用率告警
aliyun cms PutMetricRule \
  --RuleId "polardb-pg-disk-high" \
  --RuleName "PolarDB PG Disk High" \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "DiskUsage" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --EvaluationCount 3 \
  --Period 300 \
  --ComparisonOperator "GreaterThanThreshold" \
  --Threshold 85 \
  --Statistics "Average" \
  --ContactGroups "["\"dba-team\""]" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 复制延迟告警
aliyun cms PutMetricRule \
  --RuleId "polardb-pg-repl-lag" \
  --RuleName "PolarDB PG Replication Lag" \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "ReplicationLag" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --EvaluationCount 3 \
  --Period 60 \
  --ComparisonOperator "GreaterThanThreshold" \
  --Threshold 1000 \
  --Statistics "Average" \
  --ContactGroups "["\"dba-team\""]" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### 告警级别建议

| 指标 | 警告 (Warning) | 严重 (Critical) | 紧急 (Emergency) |
|------|---------------|-----------------|------------------|
| CPUUtilization | > 70% | > 85% | > 95% |
| MemoryUtilization | > 75% | > 85% | > 95% |
| ConnectionUsage | > 70% | > 85% | > 95% |
| DiskUsage | > 80% | > 90% | > 95% |
| IOPSUsage | > 70% | > 85% | > 95% |
| BufferHitRate | < 90% | < 85% | < 80% |
| ReplicationLag | > 1s | > 5s | > 10s |
| ActiveSessions | > 200 | > 400 | > 600 |

## Log Monitoring

### 错误日志

```bash
# 查询错误日志
aliyun polardb DescribeErrorLogs \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### 慢查询日志

```bash
# 查询慢日志
aliyun polardb DescribeSlowLogs \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "$(date -u -v-1d +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 查询慢日志记录详情
aliyun polardb DescribeSlowLogRecords \
  --DBClusterId "{{user.db_cluster_id}}" \
  --SQLId "{{user.sql_id}}" \
  --StartTime "$(date -u -v-1d +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Dashboard Templates

### 监控仪表板 JSON

```json
{
  "title": "PolarDB PostgreSQL Monitoring",
  "widgets": [
    {
      "title": "CPU Utilization",
      "type": "line",
      "metrics": [
        {
          "namespace": "acs_polardb_dashboard",
          "metricName": "CPUUtilization",
          "dimensions": "{instanceId:'{{user.db_cluster_id}}'}",
          "statistics": "Average"
        }
      ]
    },
    {
      "title": "Memory Utilization",
      "type": "line",
      "metrics": [
        {
          "namespace": "acs_polardb_dashboard",
          "metricName": "MemoryUtilization",
          "dimensions": "{instanceId:'{{user.db_cluster_id}}'}",
          "statistics": "Average"
        }
      ]
    },
    {
      "title": "Connection Usage",
      "type": "line",
      "metrics": [
        {
          "namespace": "acs_polardb_dashboard",
          "metricName": "ConnectionUsage",
          "dimensions": "{instanceId:'{{user.db_cluster_id}}'}",
          "statistics": "Average"
        }
      ]
    },
    {
      "title": "TPS/QPS",
      "type": "line",
      "metrics": [
        {
          "namespace": "acs_polardb_dashboard",
          "metricName": "TPS",
          "dimensions": "{instanceId:'{{user.db_cluster_id}}'}",
          "statistics": "Average"
        },
        {
          "namespace": "acs_polardb_dashboard",
          "metricName": "QPS",
          "dimensions": "{instanceId:'{{user.db_cluster_id}}'}",
          "statistics": "Average"
        }
      ]
    }
  ]
}
```

## Health Check Script

```bash
#!/bin/bash
# polardb-health-check.sh

CLUSTER_ID="{{user.db_cluster_id}}"
REGION="{{env.ALIBABA_CLOUD_REGION_ID}}"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== PolarDB PostgreSQL Health Check ==="
echo "Cluster: $CLUSTER_ID"
echo "Time: $(date)"
echo ""

# 检查集群状态
echo "[1/5] Cluster Status"
STATE=$(aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "$CLUSTER_ID" \
  --RegionId "$REGION" \
  --output cols=DBClusterStatus rows=DBCluster 2>/dev/null)

if [ "$STATE" = "Running" ]; then
    echo -e "${GREEN}✓ Cluster is Running${NC}"
else
    echo -e "${RED}✗ Cluster status: $STATE${NC}"
fi
echo ""

# 检查节点状态
echo "[2/5] Node Status"
NODES=$(aliyun polardb DescribeDBNodes \
  --DBClusterId "$CLUSTER_ID" \
  --RegionId "$REGION" 2>/dev/null)

echo "$NODES"
echo ""

# 检查 CPU
echo "[3/5] CPU Utilization (last 15 min)"
CPU=$(aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "CPUUtilization" \
  --Dimensions "[{\"instanceId\":\"$CLUSTER_ID\"}]" \
  --Period 900 \
  --StartTime "$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "$REGION" \
  --output cols=Average rows=Datapoints[0].Average 2>/dev/null)

if [ -n "$CPU" ] && [ "$CPU" != "N/A" ]; then
    if (( $(echo "$CPU < 70" | bc -l) )); then
        echo -e "${GREEN}✓ CPU: ${CPU}%${NC}"
    elif (( $(echo "$CPU < 85" | bc -l) )); then
        echo -e "${YELLOW}⚠ CPU: ${CPU}% (Warning)${NC}"
    else
        echo -e "${RED}✗ CPU: ${CPU}% (Critical)${NC}"
    fi
else
    echo "CPU: N/A"
fi
echo ""

# 检查连接
echo "[4/5] Connection Usage (last 15 min)"
CONN=$(aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "ConnectionUsage" \
  --Dimensions "[{\"instanceId\":\"$CLUSTER_ID\"}]" \
  --Period 900 \
  --StartTime "$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "$REGION" \
  --output cols=Average rows=Datapoints[0].Average 2>/dev/null)

if [ -n "$CONN" ] && [ "$CONN" != "N/A" ]; then
    if (( $(echo "$CONN < 70" | bc -l) )); then
        echo -e "${GREEN}✓ Connections: ${CONN}%${NC}"
    elif (( $(echo "$CONN < 85" | bc -l) )); then
        echo -e "${YELLOW}⚠ Connections: ${CONN}% (Warning)${NC}"
    else
        echo -e "${RED}✗ Connections: ${CONN}% (Critical)${NC}"
    fi
else
    echo "Connections: N/A"
fi
echo ""

# 检查磁盘
echo "[5/5] Disk Usage"
DISK=$(aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "DiskUsage" \
  --Dimensions "[{\"instanceId\":\"$CLUSTER_ID\"}]" \
  --Period 300 \
  --StartTime "$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "$REGION" \
  --output cols=Average rows=Datapoints[0].Average 2>/dev/null)

if [ -n "$DISK" ] && [ "$DISK" != "N/A" ]; then
    if (( $(echo "$DISK < 80" | bc -l) )); then
        echo -e "${GREEN}✓ Disk: ${DISK}%${NC}"
    elif (( $(echo "$DISK < 90" | bc -l) )); then
        echo -e "${YELLOW}⚠ Disk: ${DISK}% (Warning)${NC}"
    else
        echo -e "${RED}✗ Disk: ${DISK}% (Critical)${NC}"
    fi
else
    echo "Disk: N/A"
fi
echo ""

echo "=== Health Check Complete ==="
```
