# Polling Patterns — ECI (`aliyun eci`)

> **Note:** `aliyun eci` does **not** support `--waiter` subcommands. All polling uses shell loops with `DescribeContainerGroup(s)` and `sleep`.

## Generic Polling Templates

### ContainerGroup status until terminal (`Status`)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun eci DescribeContainerGroups \
    --RegionId "{{user.region}}" \
    --ContainerGroupIds.1 "[\"{{output.container_group_id}}\"]" \
    --output cols=Status rows=ContainerGroups[].Status | tr -d '[:space:]')
  case "$STATUS" in
    {{target_status_list}) echo "Reached terminal status: $STATUS"; break ;;
    *) echo "Status: $STATUS, waiting..."; sleep {{interval}} ;;
  esac
done
[ "$STATUS" = "{{target_status}}" ] || { echo "TIMEOUT"; exit 1; }
```

### ContainerGroup absence after delete (`Status` empty / 404)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun eci DescribeContainerGroup \
    --RegionId "{{user.region}}" \
    --ContainerGroupId "{{user.container_group_id}}" \
    --output cols=Status rows=Status 2>/dev/null || echo "NOT_FOUND")
  [ "$STATUS" = "NOT_FOUND" ] || [ -z "$STATUS" ] && echo "Deleted successfully" && break
  sleep {{interval}}
done
```

## Per-Operation Polling Parameters

| Operation | Describe Command | Extra Params | Target | Interval | Max Retries |
|-----------|-----------------|--------------|--------|----------|-------------|
| CreateContainerGroup | DescribeContainerGroups | `--ContainerGroupIds.1` | `Running` / `Succeeded` / `Failed` | 5s | 60 |
| UpdateContainerGroup | DescribeContainerGroup | — | `Running` | 5s | 24 |
| RestartContainerGroup | DescribeContainerGroup | — | `Running` | 5s | 24 |
| DeleteContainerGroup | DescribeContainerGroup | — | `NOT_FOUND` or empty | 5s | 24 |

> **State Transitions** (initial / target / interval / max wait budgets) remain in `SKILL.md` § Expected State Transitions (ContainerGroup).