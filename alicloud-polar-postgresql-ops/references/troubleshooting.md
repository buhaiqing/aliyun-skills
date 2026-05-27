# Troubleshooting Guide

> PolarDB PostgreSQL 故障排查指南

## Overview

本文档提供 PolarDB PostgreSQL 常见问题的诊断和解决方法。

## Connection Issues

### Connection Refused

**症状：**
```
psql: could not connect to server: Connection refused
```

**诊断步骤：**

```bash
# 1. 检查集群状态
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 期望: DBClusterStatus = Running

# 2. 检查白名单配置
aliyun polardb DescribeDBClusterAccessWhitelist \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 3. 检查安全组
aliyun ecs DescribeSecurityGroupAttribute \
  --SecurityGroupId "{{user.security_group_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

**解决方案：**

1. 集群未运行：启动集群
```bash
aliyun polardb StartDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

2. 白名单限制：添加客户端 IP
```bash
aliyun polardb ModifyDBClusterAccessWhitelist \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBClusterIPArrayName "default" \
  --SecurityIps "{{user.client_ip}}/32" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Connection Timeout

**症状：**
```
psql: connection to server at "..." timed out
```

**诊断步骤：**

```bash
# 1. 检查网络连通性
telnet {{user.endpoint}} 5432

# 2. 检查连接数
aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "ConnectionUsage" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

**解决方案：**

1. 检查 VPC 和路由表配置
2. 如果连接数已满，增加 max_connections 或关闭空闲连接

### Too Many Connections

**症状：**
```
FATAL: sorry, too many clients already
```

**诊断：**
```bash
# 查看当前连接数
# 需要通过 SQL 执行：
SELECT count(*) FROM pg_stat_activity;
SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
```

**解决方案：**

1. 增加 max_connections
```bash
aliyun polardb ModifyDBClusterParameters \
  --DBClusterId "{{user.db_cluster_id}}" \
  --Parameters "[{\"ParameterName\":\"max_connections\",\"ParameterValue\":\"2000\"}]" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

2. 关闭空闲连接 (SQL)
```sql
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' 
  AND state_change < NOW() - INTERVAL '1 hour';
```

## Performance Issues

### High CPU Usage

**诊断：**

```bash
# 1. 查看 CPU 指标
aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "CPUUtilization" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --Period 60 \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

**解决方案：**

1. 查看慢查询 (SQL)
```sql
SELECT pid, usename, application_name, client_addr, 
       query_start, state, query
FROM pg_stat_activity
WHERE state = 'active'
  AND query_start < NOW() - INTERVAL '1 minute';
```

2. 升级节点规格
```bash
aliyun polardb ModifyDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeClass "{{user.larger_node_class}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Slow Queries

**诊断：**

```bash
# 查询慢日志
aliyun polardb DescribeSlowLogs \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

**解决方案：**

参见 [Slow Query Analysis](slow-query-analysis.md)

### High Replication Lag

**症状：**
只读节点数据延迟过大

**诊断：**

```bash
# 查看复制延迟指标
aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "ReplicationLag" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\",\"nodeId\":\"{{user.db_node_id}}\"}]" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# SQL 查看复制状态
SELECT * FROM pg_stat_replication;
```

**解决方案：**

1. 检查网络带宽
2. 增加 max_parallel_workers_per_gather
3. 重启只读节点

```bash
aliyun polardb RestartDBNode \
  --DBNodeId "{{user.db_node_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Storage Issues

### Disk Full

**症状：**
```
ERROR: could not extend file: No space left on device
```

**诊断：**

```bash
# 查看磁盘使用率
aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "DiskUsage" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

**解决方案：**

1. 扩展存储空间
```bash
aliyun polardb ModifyDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StorageSpace "{{user.new_storage_gb}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

2. 清理 WAL 文件
```sql
-- 检查 WAL 保留策略
SHOW wal_keep_size;
```

3. 删除不必要的备份
```bash
aliyun polardb DescribeBackups \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

aliyun polardb DeleteBackup \
  --DBClusterId "{{user.db_cluster_id}}" \
  --BackupId "{{user.old_backup_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Cluster State Issues

### Cluster Stuck in Creating

**诊断：**

```bash
# 查看集群详情
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 查看错误日志
aliyun polardb DescribeErrorLogs \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

**解决方案：**

- 如果超过 30 分钟仍在 creating，提交工单
- 检查 VPC 和 VSwitch 配置
- 检查账户余额

### Node Restart Loop

**诊断：**

```bash
# 查看节点状态
aliyun polardb DescribeDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 查看错误日志
aliyun polardb DescribeErrorLogs \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

**解决方案：**

1. 检查节点资源是否超限
2. 重启节点
```bash
aliyun polardb RestartDBNode \
  --DBNodeId "{{user.db_node_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Error Codes Reference

| Error Code | Description | Solution |
|------------|-------------|----------|
| `InvalidDBClusterId.NotFound` | 集群不存在 | 检查 cluster ID |
| `InvalidAccountName.NotFound` | 账户不存在 | 创建账户 |
| `OperationDenied.ClusterStatus` | 集群状态不允许操作 | 等待集群稳定 |
| `OperationDenied.AccountStatus` | 账户状态异常 | 检查账户状态 |
| `Throttling` | 请求频率过高 | 增加重试延迟 |
| `InvalidVPCId.NotFound` | VPC 不存在 | 创建 VPC |
| `InsufficientBalance` | 账户余额不足 | 充值 |
| `QuotaExceeded` | 配额超限 | 申请提升配额 |

## Diagnostic Script

```bash
#!/bin/bash
# polardb-diagnostic.sh

CLUSTER_ID="{{user.db_cluster_id}}"
REGION="{{env.ALIBABA_CLOUD_REGION_ID}}"

echo "=== PolarDB PostgreSQL Diagnostic Report ==="
echo "Cluster: $CLUSTER_ID"
echo "Time: $(date)"
echo ""

# 1. 集群基本信息
echo "[1/7] Cluster Information"
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "$CLUSTER_ID" \
  --RegionId "$REGION" \
  --output cols=DBClusterId,DBClusterStatus,DBVersion,DBClusterClass,PayType,StorageUsed,StorageSpace rows=DBCluster
echo ""

# 2. 节点状态
echo "[2/7] Node Status"
aliyun polardb DescribeDBNodes \
  --DBClusterId "$CLUSTER_ID" \
  --RegionId "$REGION"
echo ""

# 3. 账户状态
echo "[3/7] Accounts"
aliyun polardb DescribeAccounts \
  --DBClusterId "$CLUSTER_ID" \
  --RegionId "$REGION" \
  --output cols=AccountName,AccountStatus,AccountType rows=Accounts.Account[]
echo ""

# 4. 性能指标
echo "[4/7] Performance Metrics (Last 15 min)"
for metric in CPUUtilization MemoryUtilization ConnectionUsage DiskUsage; do
    VALUE=$(aliyun cms DescribeMetricList \
      --Namespace "acs_polardb_dashboard" \
      --MetricName "$metric" \
      --Dimensions "[{\"instanceId\":\"$CLUSTER_ID\"}]" \
      --Period 900 \
      --StartTime "$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)" \
      --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --RegionId "$REGION" \
      --output cols=Average rows=Datapoints[0].Average 2>/dev/null || echo "N/A")
    echo "  $metric: $VALUE"
done
echo ""

# 5. 白名单配置
echo "[5/7] Whitelist Configuration"
aliyun polardb DescribeDBClusterAccessWhitelist \
  --DBClusterId "$CLUSTER_ID" \
  --RegionId "$REGION"
echo ""

# 6. 错误日志
echo "[6/7] Recent Error Logs (Last 1 hour)"
aliyun polardb DescribeErrorLogs \
  --DBClusterId "$CLUSTER_ID" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "$REGION" | head -20
echo ""

# 7. 慢查询统计
echo "[7/7] Slow Query Count (Last 1 hour)"
aliyun polardb DescribeSlowLogs \
  --DBClusterId "$CLUSTER_ID" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --RegionId "$REGION" | jq -r '.Items.SQLSlowLog | length' 2>/dev/null || echo "N/A"
echo ""

echo "=== Diagnostic Report Complete ==="
```
