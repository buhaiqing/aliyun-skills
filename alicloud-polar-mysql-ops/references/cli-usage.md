# CLI Usage — PolarDB MySQL (`aliyun polardb`)

> Version: 1.0.0 | Last Updated: 2026-05-16

## Conventions (agent execution)

- Output is **JSON by default** — NO `--output json` needed
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- Credentials read from `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` env vars
- Region from `ALIBABA_CLOUD_REGION_ID` env var

## Command Map

| Goal | Example Invocation | Notes |
|------|-------------------|-------|
| List clusters | `aliyun polardb DescribeDBClusters --DBType MySQL --RegionId {{user.region}}` | JSON output |
| Describe cluster | `aliyun polardb DescribeDBClusterAttribute --DBClusterId {{cluster_id}}` | JSON output |
| Extract fields | `aliyun polardb DescribeDBClusters --DBType MySQL --RegionId {{user.region}} --output cols=DBClusterId,DBClusterStatus rows=Items.DBCluster[].{DBClusterId,DBClusterStatus}` | JMESPath |
| List regions | `aliyun polardb DescribeRegions` | Available regions |
| Describe nodes | `aliyun polardb DescribeDBNodes --DBClusterId {{cluster_id}}` | All nodes |
| Describe accounts | `aliyun polardb DescribeAccounts --DBClusterId {{cluster_id}}` | All accounts |
| Describe databases | `aliyun polardb DescribeDatabases --DBClusterId {{cluster_id}}` | All databases |
| List backups | `aliyun polardb DescribeBackups --DBClusterId {{cluster_id}} --StartTime "{{start}}" --EndTime "{{end}}"` | Backup history |
| Describe endpoints | `aliyun polardb DescribeDBClusterEndpoints --DBClusterId {{cluster_id}}` | All endpoints |
| Performance metrics | `aliyun polardb DescribeDBClusterPerformance --DBClusterId {{cluster_id}} --Key "CpuUsage" --StartTime "{{start}}" --EndTime "{{end}}"` | Time-series data |
| Create cluster | `aliyun polardb CreateDBCluster --DBType MySQL --DBVersion 8.0 --PayType Postpaid --DBNodeClass polar.mysql.x4.medium --DBNodeNumber 2 --RegionId {{user.region}} --VPCId {{user.vpc_id}} --VSwitchId {{user.vswitch_id}}` | Full cluster creation |
| Delete cluster | `aliyun polardb DeleteDBCluster --DBClusterId {{cluster_id}}` | **Destructive** — requires confirmation |
| Describe regions | `aliyun polardb DescribeRegions` | List regions |
| Available classes | `aliyun polardb DescribeDBClusterAvailableClasses --RegionId {{user.region}} --DBType MySQL --DBVersion 8.0` | Valid node classes |

## Polling with `--waiter`

```bash
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --waiter expr='DBClusterStatus' to=Running timeout=600 interval=10
```

## CLI vs API Coverage

Core operations (create, describe, modify, delete) are fully covered by CLI. Advanced
operations (GDN management, TDE configuration, audit log settings) may require SDK.
