# Polling Patterns — Alibaba Cloud Service K8s (ASK, `aliyun cs`)

> ASK 是阿里云 Serverless K8s，控制面通过 `aliyun cs` 的 `/clusters/{cluster_id}` 拉取状态。

## Generic Polling Templates

### Cluster state until target (`state == running`)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATE=$(aliyun cs GET /clusters/{{cluster_id}} | jq -r '.state')
  [ "$STATE" = "{{target_state}}" ] && break
  echo "ASK cluster state: $STATE, waiting..."
  sleep {{interval}}
done
[ "$STATE" = "{{target_state}}" ] || { echo "TIMEOUT"; exit 1; }
```

> **Terminal 状态**: `running` / `failed` / `deleting` — 见 `SKILL.md` § Failure Recovery。

## Per-Operation Polling Parameters

| Operation | Describe Command | Cluster ID var | Target | Interval | Max Retries |
|-----------|-----------------|----------------|--------|----------|-------------|
| Create ASK cluster | `GET /clusters/{cluster_id}` | `{{output.cluster_id}}` | `running` | 30s | 60 |
| Delete ASK cluster | `GET /clusters/{cluster_id}` | `{{output.cluster_id}}` | `deleting` (then 404) | 30s | 60 |
