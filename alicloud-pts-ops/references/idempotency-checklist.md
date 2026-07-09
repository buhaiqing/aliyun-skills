# Idempotency Checklist — PTS

> Version: 1.0.0 | Last Updated: 2026-06-16

## Write Operations

| Operation | Idempotent? | Pattern |
|-----------|-------------|---------|
| `create-pts-scene` | No | Check `list-pts-scene --key-word` first |
| `save-pts-scene` | Partial | Same SceneId → update |
| `start-pts-scene` | No | Check status ≠ `Running` before start |
| `stop-pts-scene` | Yes | Safe to call multiple times |
| `delete-pts-scene` | Yes | Second delete → `SceneNotFound` (treat as success) |
| `start-debug-pts-scene` | No | Stop debug before re-debug |

## Retry Safety

| Error | Retry? | Notes |
|-------|--------|-------|
| `Throttling.User` | Yes | Same parameters, backoff |
| `InternalError` | Yes | Same SceneId / scene-id |
| `SceneAlreadyRunning` | No | Stop first, then new start |
| `InvalidParameter` | No | Fix payload first |
| `CreateSceneFail` | Once | After JSON fix only |

## Automation Patterns

### Check-then-create scene

```bash
EXIST=$(aliyun pts list-pts-scene --page-number 1 --page-size 10 \
  --key-word "{{user.scene_name}}" --region "${ALIBABA_CLOUD_REGION_ID}" \
  | jq -r '.SceneViewList[]? | select(.SceneName=="{{user.scene_name}}") | .SceneId' | head -1)
if [ -n "$EXIST" ]; then
  echo "[RESULT] scene_id=$EXIST (reused)"
else
  aliyun pts create-pts-scene --scene "$(cat scene.json)" ...
fi
```

### Safe stop before delete

```bash
aliyun pts stop-pts-scene --scene-id "{{scene_id}}" 2>/dev/null || true
sleep 5
aliyun pts delete-pts-scene --scene-id "{{scene_id}}"
```

## CI/CD Notes

- Never auto-`start-pts-scene` on production without manual approval gate
- Pin Scene JSON in VCS; parameterize only `target_url` per env
- Archive `report_id` in build artifacts for traceability
