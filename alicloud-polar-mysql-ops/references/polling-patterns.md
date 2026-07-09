# Polling Patterns — PolarDB MySQL (`aliyun polardb`)

## Generic Polling Templates

### Cluster status until target (`DBClusterStatus`)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun polardb DescribeDBClusterAttribute \
    --DBClusterId "{{cluster_id}}" \
    --output cols=DBClusterStatus rows=DBClusterStatus)
  [ "$STATUS" = "{{target_status}}" ] && break
  sleep {{interval}}
done
```

### Cluster absence after delete (API error → gone)

```bash
for i in $(seq 1 {{max_retries}}); do
  RESULT=$(aliyun polardb DescribeDBClusterAttribute \
    --DBClusterId "{{user.db_cluster_id}}" 2>/dev/null || echo "not_found")
  [ "$RESULT" = "not_found" ] && break
  sleep {{interval}}
done
```

### CLI native waiter (preferred when supported)

See [cli-usage.md § Polling with `--waiter`](cli-usage.md#polling-with---waiter):

```bash
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --waiter expr='DBClusterStatus' to=Running timeout=600 interval=10
```

## Per-Operation Polling Parameters

| Operation | Describe Command | Cluster ID var | Target | Interval | Max Retries |
|-----------|-----------------|----------------|--------|----------|-------------|
| CreateDBCluster | DescribeDBClusterAttribute | `{{output.db_cluster_id}}` | `Running` | 10s | 60 |
| StartDBCluster / ResumeDBCluster | DescribeDBClusterAttribute | `{{user.db_cluster_id}}` | `Running` | 10s | 30 |
| StopDBCluster | DescribeDBClusterAttribute | `{{user.db_cluster_id}}` | `Stopped` | 10s | 30 |
| PauseDBCluster | DescribeDBClusterAttribute | `{{user.db_cluster_id}}` | `Paused` | 10s | 30 |
| DeleteDBCluster | DescribeDBClusterAttribute (absence) | `{{user.db_cluster_id}}` | `not_found` | 10s | 30 |
| AddDBNodes / UpgradeDBCluster | DescribeDBClusterAttribute | `{{user.db_cluster_id}}` | `Running` | 10s | 60 |

> **Expected State Transitions** (interval / max wait budgets) remain in `SKILL.md` § API Response Paths.
