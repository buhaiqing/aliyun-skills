# IDE Agent Token Hooks (TEL Phase 4)

Templates bridge **IDE Agent LLM usage** into Runtime Harness via `HARNESS_AGENT_TURN_USAGE` and optional **sidecar** files under `.runtime/token/context/`.

## Install (Cursor)

1. Copy hook scripts are already under `assets/hooks/cursor/` (paths relative to repo root).
2. Merge `assets/hooks/cursor/hooks.json.example` into `.cursor/hooks.json` (or symlink commands).
3. `chmod +x assets/hooks/cursor/*.sh`
4. Set `export ALIYUN_SKILLS_ROOT=/path/to/aliyun-skills` in your shell profile or Cursor env.

**Flow**

1. `sessionStart` → writes `harness-session-id.txt` + `traceparent-latest.txt` (W3C root) + `HARNESS_SESSION_ID`
2. `afterAgentResponse` → normalizes usage → `agent-turn-latest.json` (includes `w3c_traceparent` when available)
3. `preToolUse` (Shell) → prepends `export TRACEPARENT=...` (child span) + optional `HARNESS_*` before wrapper commands

## W3C traceparent (X-13)

Standard env: `TRACEPARENT` (`00-{trace-id}-{parent-id}-{flags}`). Sidecar: `.runtime/token/context/traceparent-latest.txt`.

When `TRACEPARENT` is set and `HARNESS_AGENT_TURN_USAGE` is unset, harness ingests agent-turn sidecar only if `w3c_traceparent` shares the same W3C trace-id.

## Cursor native usage (X-14) + turn attribution (X-15)

| Path / env | Role |
|------------|------|
| `tokenUsage` in hook stdin | Cursor native API (fixture: `scripts/fixtures/agent-turn/cursor/`) |
| `.runtime/token/context/agent-turn-by-turn/{turn_id}.json` | Per-turn usage record |
| `current-turn-id.txt` | Active turn pointer for pre-tool |
| `HARNESS_AGENT_TURN_ID` | Wrapper reads per-turn file (no full usage JSON env when native) |
| Trace `agent_turn_id` / rollup `by_turn` | Cost attribution per agent turn |

```bash
bash scripts/test-agent-turn-x14-x15-bridge.sh
bash scripts/test-otel-traceparent-bridge.sh
```

## Install (Claude Code)

1. Merge `assets/hooks/claude-code/settings.hooks.example.json` into `.claude/settings.json` hooks section.
2. `chmod +x assets/hooks/claude-code/*.sh`

## Env contract (`HARNESS_AGENT_TURN_USAGE`)

```json
{
  "turn_id": "turn-abc",
  "coding_agent": "cursor",
  "model": "claude-sonnet-4",
  "prompt_tokens": 45000,
  "completion_tokens": 1200,
  "total_tokens": 46200,
  "context_metadata": {}
}
```

Harness reads (priority): env `HARNESS_AGENT_TURN_USAGE` → legacy `SKILLOPT_AGENT_TURN_USAGE` → sidecar `.runtime/token/context/agent-turn-latest.json`.

## Simulate (CI / no IDE)

```bash
export ALIYUN_SKILLS_ROOT="$PWD"
bash scripts/hooks/simulate-ide-agent-turn.sh --write-sidecar scripts/fixtures/agent-turn-cursor.json
# wrapper trace_start picks up sidecar when env unset
bash scripts/test-ide-agent-turn-bridge.sh
bash scripts/test-otel-traceparent-bridge.sh
```

See [docs/token-efficiency-runtime.md](../../docs/token-efficiency-runtime.md) §7.4 / §7.8.
