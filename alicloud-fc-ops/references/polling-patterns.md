# Polling Patterns — Function Compute (FC 3.0, `aliyun fc-open`)

> FC 函数部署/更新为异步操作；通过 `GET /2023-03-30/functions/{name}` 取 `state`。

## Generic Polling Templates

### Function state until `ACTIVE`

```bash
for i in $(seq 1 {{max_retries}}); do
  STATE=$(aliyun fc-open GET /2023-03-30/functions/{{function_name}} | jq -r '.state')
  [ "$STATE" = "{{target_state}}" ] && break
  sleep {{interval}}
done
[ "$STATE" = "{{target_state}}" ] || echo "Function in state: $STATE"
```

> **Terminal 状态**: `Active` / `Inactive` / `Failed` — `Failed` 时检查 `stateReason` / `stateReasonCode`。

## Per-Operation Polling Parameters

| Operation | Describe Command | Target | Interval | Max Retries |
|-----------|-----------------|--------|----------|-------------|
| CreateFunction | `GET /2023-03-30/functions/{name}` | `ACTIVE` | 5s | 60 |
| UpdateFunction / UpdateFunctionCode | `GET /2023-03-30/functions/{name}` | `ACTIVE` | 5s | 60 |
