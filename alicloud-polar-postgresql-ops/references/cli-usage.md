# CLI Usage Reference

> Alibaba Cloud CLI (`aliyun`) 完整命令参考 for PolarDB PostgreSQL

## Overview

本文档提供 PolarDB PostgreSQL 的完整 CLI 命令参考，所有命令均经过验证，可直接复制执行。

## Prerequisites

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.Items.Item[]?`
- Example:
```bash
aliyun adb DescribeDBClusters | jq '{clusters: [.Items.DBCluster[]? | {id: .DBClusterId, status: .Status}]}'
```

```bash
# 安装 aliyun CLI
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"

# 或 Homebrew
brew install aliyun-cli

# 验证安装
aliyun version

# 配置凭证
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"

# 验证配置
aliyun polardb DescribeDBClusters --RegionId $ALIBABA_CLOUD_REGION_ID
```

## Cluster Operations

### Create DB Cluster

```bash
aliyun polardb CreateDBCluster \
  --RegionId "{{user.region}}" \
  --DBType "PostgreSQL" \
  --DBVersion "{{user.engine_version}}" \
  --DBClusterClass "{{user.db_node_class}}" \
  --DBNodeClass "{{user.db_node_class}}" \
  --ZoneId "{{user.zone_id}}" \
  --VPCId "{{user.vpc_id}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --PayType "Postpaid" \
  --ClientToken "$(uuidgen)"
```

### Describe DB Clusters

```bash
# List all PostgreSQL clusters
aliyun polardb DescribeDBClusters \
  --DBType "PostgreSQL" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=DBClusterId,DBClusterStatus,DBVersion,DBClusterClass,PayType rows=Items.DBCluster[]

# Describe specific cluster
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Cluster Lifecycle

```bash
# Start cluster
aliyun polardb StartDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Stop cluster
aliyun polardb StopDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Pause cluster (serverless)
aliyun polardb PauseDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Resume cluster
aliyun polardb ResumeDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Delete cluster
aliyun polardb DeleteDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Modify Cluster

```bash
# Modify cluster description
aliyun polardb ModifyDBClusterDescription \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBClusterDescription "{{user.db_cluster_name}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Modify cluster class (scale up/down)
aliyun polardb ModifyDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeClass "{{user.new_node_class}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Node Operations

### Describe DB Nodes

```bash
aliyun polardb DescribeDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Add/Remove Nodes

```bash
# Add read-only node
aliyun polardb AddDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeClass "{{user.db_node_class}}" \
  --ZoneId "{{user.zone_id}}" \
  --ClientToken "$(uuidgen)" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Remove read-only node
aliyun polardb DeleteDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeId "{{user.db_node_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Restart node
aliyun polardb RestartDBNode \
  --DBNodeId "{{user.db_node_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Endpoint Operations

### Describe Endpoints

```bash
aliyun polardb DescribeDBClusterEndpoints \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Create/Modify Endpoints

```bash
# Create endpoint
aliyun polardb CreateDBClusterEndpoint \
  --DBClusterId "{{user.db_cluster_id}}" \
  --EndpointType "Custom" \
  --Nodes "{{user.db_node_ids}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Modify endpoint
aliyun polardb ModifyDBClusterEndpoint \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBEndpointId "{{user.endpoint_id}}" \
  --Nodes "{{user.db_node_ids}}" \
  --ReadWriteMode "{{user.rw_mode}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Delete endpoint
aliyun polardb DeleteDBClusterEndpoint \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBEndpointId "{{user.endpoint_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Account Operations

### Create Account

```bash
aliyun polardb CreateAccount \
  --DBClusterId "{{user.db_cluster_id}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPassword "{{user.account_password}}" \
  --AccountType "Super" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Describe Accounts

```bash
aliyun polardb DescribeAccounts \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=AccountName,AccountStatus,AccountType rows=Accounts.Account[]
```

### Modify Account

```bash
# Reset password
aliyun polardb ResetAccountPassword \
  --DBClusterId "{{user.db_cluster_id}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPassword "{{user.new_password}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Grant account privilege
aliyun polardb GrantAccountPrivilege \
  --DBClusterId "{{user.db_cluster_id}}" \
  --AccountName "{{user.account_name}}" \
  --DBName "{{user.db_name}}" \
  --AccountPrivilege "ReadWrite" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Database Operations

### Create Database

```bash
aliyun polardb CreateDatabase \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBName "{{user.db_name}}" \
  --CharacterSetName "UTF8" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Describe Databases

```bash
aliyun polardb DescribeDatabases \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Backup Operations

### Create Backup

```bash
aliyun polardb CreateBackup \
  --DBClusterId "{{user.db_cluster_id}}" \
  --BackupType "FullBackup" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Describe Backups

```bash
aliyun polardb DescribeBackups \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Backup Policy

```bash
# Describe backup policy
aliyun polardb DescribeBackupPolicy \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Modify backup policy
aliyun polardb ModifyBackupPolicy \
  --DBClusterId "{{user.db_cluster_id}}" \
  --PreferredBackupPeriod "Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday" \
  --PreferredBackupTime "02:00Z-03:00Z" \
  --BackupRetentionPeriod "7" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Serverless Operations

### Describe Serverless Config

```bash
aliyun polardb DescribeDBClusterServerlessConf \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Modify Serverless Config

```bash
aliyun polardb ModifyDBClusterServerlessConf \
  --DBClusterId "{{user.db_cluster_id}}" \
  --ScaleMin "{{user.min_capacity}}" \
  --ScaleMax "{{user.max_capacity}}" \
  --ScaleRoNumMin "{{user.min_ro_nodes}}" \
  --ScaleRoNumMax "{{user.max_ro_nodes}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Security Operations

### Whitelist Management

```bash
# Describe whitelist
aliyun polardb DescribeDBClusterAccessWhitelist \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Modify whitelist
aliyun polardb ModifyDBClusterAccessWhitelist \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBClusterIPArrayName "default" \
  --SecurityIps "{{user.ips}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### SSL/TDE

```bash
# Describe SSL status
aliyun polardb DescribeDBClusterSSL \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Enable SSL
aliyun polardb ModifyDBClusterSSL \
  --DBClusterId "{{user.db_cluster_id}}" \
  --SSLEnabled "Enable" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## CMS Metrics Operations

### Describe Metric List

```bash
# CPU Usage
aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "CPUUtilization" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Period "60" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Memory Usage
aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "MemoryUtilization" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Period "60" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Connections
aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "ConnectionUsage" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Period "60" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# IOPS
aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "IOPSUsage" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Period "60" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Storage
aliyun cms DescribeMetricList \
  --Namespace "acs_polardb_dashboard" \
  --MetricName "DiskUsage" \
  --Dimensions "[{\"instanceId\":\"{{user.db_cluster_id}}\"}]" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Period "3600" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Parameter Operations

### Describe Parameters

```bash
aliyun polardb DescribeDBClusterParameters \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Modify Parameters

```bash
aliyun polardb ModifyDBClusterParameters \
  --DBClusterId "{{user.db_cluster_id}}" \
  --Parameters "[{\"ParameterName\":\"max_connections\",\"ParameterValue\":\"2000\"}]" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Error Handling

### Common Error Codes

| Error Code | Meaning | Action |
|------------|---------|--------|
| `InvalidDBClusterId.NotFound` | Cluster not found | Verify cluster ID |
| `InvalidAccountName.NotFound` | Account not found | Create account first |
| `OperationDenied.ClusterStatus` | Invalid cluster state | Wait for stable state |
| `Throttling` | Rate limit exceeded | Add retry with backoff |
| `InvalidVPCId.NotFound` | VPC not found | Create VPC first |
| `InsufficientBalance` | Account balance low | Top up account |

### Retry Logic

```bash
#!/bin/bash
# retry-wrapper.sh

MAX_RETRIES=3
RETRY_DELAY=5

execute_with_retry() {
    local cmd="$1"
    local retries=0
    
    while [ $retries -lt $MAX_RETRIES ]; do
        result=$(eval "$cmd" 2>&1)
        exit_code=$?
        
        if [ $exit_code -eq 0 ]; then
            echo "$result"
            return 0
        fi
        
        if echo "$result" | grep -q "Throttling"; then
            retries=$((retries + 1))
            sleep $RETRY_DELAY
            continue
        fi
        
        # Non-retryable error
        echo "Error: $result" >&2
        return $exit_code
    done
    
    echo "Max retries exceeded" >&2
    return 1
}

# Usage
execute_with_retry "aliyun polardb DescribeDBClusters --RegionId $ALIBABA_CLOUD_REGION_ID"
```
