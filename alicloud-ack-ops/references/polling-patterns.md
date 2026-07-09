# Polling Patterns — ACK (`aliyun cs`)

## Generic Polling Templates

### Cluster status until target (`state`)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATE=$(aliyun cs GET /clusters/{{cluster_id}} | jq -r '.state')
  [ "$STATE" = "{{target_status}}" ] && break
  echo "Cluster state: $STATE, waiting..."
  sleep {{interval}}
done
```

### Resource absence after delete (API returns 404)

```bash
for i in $(seq 1 {{max_retries}}); do
  RESULT=$(aliyun cs GET /clusters/{{cluster_id}} 2>/dev/null || echo "not_found")
  [ "$RESULT" = "not_found" ] && break
  sleep {{interval}}
done
```

### CLI native waiter (preferred when supported)

See [cli-usage.md § Command Map](cli-usage.md#command-map):

```bash
aliyun cs GET /clusters/{id} \
  --waiter expr='state' to=running timeout=1800 interval=30
```

## Per-Operation Polling Parameters

| Operation | Describe Command | Cluster ID var | Target | Interval | Max Retries |
|-----------|-----------------|----------------|--------|----------|-------------|
| CreateCluster | `GET /clusters/{{cluster_id}}` | `{{output.cluster_id}}` | `running` | 30s | 60 |
| UpgradeCluster | `GET /clusters/{{cluster_id}}` | `{{user.cluster_id}}` | `running` | 30s | 120 |
| ScaleOutCluster | `GET /clusters/{{cluster_id}}` | `{{user.cluster_id}}` | `running` | 30s | 60 |
| CreateNodePool | `GET /clusters/{id}/nodepools/{{pool_id}}` | `{{output.node_pool_id}}` | `active` | 30s | 30 |
| ModifyNodePool | `GET /clusters/{id}/nodepools/{{pool_id}}` | `{{user.node_pool_id}}` | `active` | 30s | 30 |
| DeleteCluster | `GET /clusters/{{cluster_id}}` (absence) | `{{user.cluster_id}}` | `not_found` | 30s | 60 |
| DeleteNodePool | `GET /clusters/{id}/nodepools/{{pool_id}}` (absence) | `{{user.node_pool_id}}` | `not_found` | 30s | 30 |

> **Expected State Transitions** (interval / max wait budgets) remain in `SKILL.md` § State Transitions table.