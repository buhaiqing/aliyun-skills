# CLI Usage — PolarDB IO (`aliyun polardb-io`)

> Version: 1.0.0 | Last Updated: 2026-05-16

## Conventions

- Output is **JSON by default** — NO `--output json` needed
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- Credentials from env vars

## Command Map

| Goal | Example | Notes |
|------|---------|-------|
| List clusters | `aliyun polardb-io DescribeDBClusters --RegionId {{user.region}}` | JSON |
| Describe cluster | `aliyun polardb-io DescribeDBClusterAttribute --DBClusterId {{id}}` | JSON |
| Describe nodes | `aliyun polardb-io DescribeDBNodes --DBClusterId {{id}}` | JSON |
| Create cluster | `aliyun polardb-io CreateDBCluster --PayType Postpaid --DBNodeClass {{class}} --DBNodeNumber 2 --RegionId {{region}} --VPCId {{vpc}} --VSwitchId {{vsw}}` | Full creation |
| Delete cluster | `aliyun polardb-io DeleteDBCluster --DBClusterId {{id}}` | **Destructive** |
| List regions | `aliyun polardb-io DescribeRegions` | Available regions |
| Create account | `aliyun polardb-io CreateAccount --DBClusterId {{id}} --AccountName {{name}} --AccountPassword {{pwd}}` | New account |
| Create database | `aliyun polardb-io CreateDatabase --DBClusterId {{id}} --DBName {{name}}` | New database |
| Describe backups | `aliyun polardb-io DescribeBackups --DBClusterId {{id}}` | Backup list |
| Describe endpoints | `aliyun polardb-io DescribeDBClusterEndpoints --DBClusterId {{id}}` | All endpoints |

## Polling

```bash
aliyun polardb-io DescribeDBClusterAttribute \
  --DBClusterId "{{cluster_id}}" \
  --waiter expr='DBClusterStatus' to=Running timeout=600 interval=10
```

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.Items.Item[]?`
- Use `--PageSize` to control result sets: `--PageSize 50`
- Example:
```bash
aliyun ecs DescribeInstances --PageSize 50 | jq '{total: .TotalCount, items: [.Items.Item[]? | {id: .Id, name: .Name}]}'
```

