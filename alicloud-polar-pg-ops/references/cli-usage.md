# CLI Usage — PolarDB PostgreSQL (`aliyun polardb-pg`)

> Version: 1.0.0 | Last Updated: 2026-05-16

## Conventions

- Output is **JSON by default** — NO `--output json` needed
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- Credentials from env vars

## Command Map

| Goal | Example | Notes |
|------|---------|-------|
| List clusters | `aliyun polardb-pg DescribeDBClusters --DBVersion PostgreSQL --RegionId {{user.region}}` | JSON |
| Describe cluster | `aliyun polardb-pg DescribeDBClusterAttribute --DBClusterId {{id}}` | JSON |
| Describe nodes | `aliyun polardb-pg DescribeDBNodes --DBClusterId {{id}}` | JSON |
| Create cluster | `aliyun polardb-pg CreateDBCluster --DBVersion 14 --PayType Postpaid --DBNodeClass {{class}} --DBNodeNumber 2 --RegionId {{region}} --VPCId {{vpc}} --VSwitchId {{vsw}}` | Full creation |
| Delete cluster | `aliyun polardb-pg DeleteDBCluster --DBClusterId {{id}}` | **Destructive** |
| List regions | `aliyun polardb-pg DescribeRegions` | Available regions |
| Create account | `aliyun polardb-pg CreateAccount --DBClusterId {{id}} --AccountName {{name}} --AccountPassword {{pwd}}` | New account |
| Create database | `aliyun polardb-pg CreateDatabase --DBClusterId {{id}} --DBName {{name}}` | New database |
| Describe backups | `aliyun polardb-pg DescribeBackups --DBClusterId {{id}}` | Backup list |
| Describe endpoints | `aliyun polardb-pg DescribeDBClusterEndpoints --DBClusterId {{id}}` | All endpoints |

## Polling

```bash
aliyun polardb-pg DescribeDBClusterAttribute \
  --DBClusterId "{{cluster_id}}" \
  --waiter expr='DBClusterStatus' to=Running timeout=600 interval=10
```
