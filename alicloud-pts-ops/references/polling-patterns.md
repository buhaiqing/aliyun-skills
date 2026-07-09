# Polling Patterns — Performance Testing Service (PTS, `aliyun pts`)

> PTS 场景运行异步结束；通过 `aliyun pts get-pts-scene-running-status` 查询状态。

## Generic Polling Templates

### Scene running status until terminal

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun pts get-pts-scene-running-status --scene-id "{{scene_id}}" \
    --region "${ALIBABA_CLOUD_REGION_ID}" | jq -r '.Status // .status // empty')
  echo "[$(date +%H:%M:%S)] [DIAG] status=$STATUS"
  [[ "$STATUS" == "Finished" || "$STATUS" == "WaitStart" ]] && break
  sleep {{interval}}
done
```

> **Terminal 状态**: `Finished`（完成） / `WaitStart`（排队）— 报告通过 `get-pts-reports-by-scene-id` 或 `list-pts-reports` 取。

## Per-Operation Polling Parameters

| Operation | Describe Command | Target | Interval | Max Retries |
|-----------|-----------------|--------|----------|-------------|
| start-pts-scene | `get-pts-scene-running-status` | `Finished` / `WaitStart` | 30s | 60 |
