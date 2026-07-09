#!/usr/bin/env bash
# TEL X-14 / X-15 — Cursor native usage + per-turn attribution bridge (simulated e2e).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

ok() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

echo "=== Agent turn X-14/X-15 bridge ==="
export ALIYUN_SKILLS_ROOT="$ROOT"
unset HARNESS_AGENT_TURN_USAGE SKILLOPT_AGENT_TURN_USAGE HARNESS_AGENT_TURN_ID TRACEPARENT ALIBABA_CLOUD_RUNTIME_DIR

for f in \
    "$ROOT/scripts/lib/agent-turn-usage.sh" \
    "$ROOT/scripts/agent-turn/collect-cursor-usage.sh" \
    "$ROOT/assets/hooks/cursor/after-agent-response.sh" \
    "$ROOT/assets/hooks/cursor/pre-tool-harness-wrapper.sh"; do
    bash -n "$f" && ok "bash -n $(basename "$f")" || bad "syntax $(basename "$f")"
done

# shellcheck source=lib/agent-turn-usage.sh
source "$ROOT/scripts/lib/agent-turn-usage.sh"

native_fixture="$ROOT/scripts/fixtures/agent-turn/cursor/native-after-agent-response.json"
parsed="$(agent_turn_parse_cursor_stdin "$(cat "$native_fixture")")"
if printf '%s' "$parsed" | jq -e '.source == "cursor_native_api" and .total_tokens == 53800' >/dev/null 2>&1; then
    ok "X-14 native tokenUsage parse"
else
    bad "native parse: $parsed"
fi

if bash "$ROOT/scripts/agent-turn/collect-cursor-usage.sh" --fixture "$native_fixture" | jq -e '.total_tokens == 53800' >/dev/null 2>&1; then
    ok "collect-cursor-usage fixture"
else
    bad "collect-cursor-usage"
fi

rm -rf "$ROOT/.runtime/token/context"
printf '%s' "$(cat "$native_fixture")" | bash "$ROOT/assets/hooks/cursor/after-agent-response.sh"
turn_id="$(agent_turn_read_current_turn_id 2>/dev/null || true)"
[[ -n "$turn_id" ]] && ok "hook wrote current-turn-id" || bad "current-turn-id missing"
[[ -f "$(agent_turn_turn_record_path "$turn_id" 2>/dev/null || echo missing)" ]] && ok "per-turn sidecar written" || bad "per-turn sidecar"

cmd='cd alicloud-ecs-ops && ./scripts/ecs-harness-wrapper.sh DescribeInstances --PageSize 1'
out="$(printf '%s' "{\"command\":$(printf '%s' "$cmd" | jq -Rs .)}" | bash "$ROOT/assets/hooks/cursor/pre-tool-harness-wrapper.sh")"
if printf '%s' "$out" | jq -e '.updated_input.command | test("HARNESS_AGENT_TURN_ID")' >/dev/null 2>&1; then
    ok "pre-tool exports HARNESS_AGENT_TURN_ID"
else
    bad "pre-tool turn id: $out"
fi
if printf '%s' "$out" | jq -e '.updated_input.command | test("HARNESS_AGENT_TURN_USAGE")' >/dev/null 2>&1; then
    bad "pre-tool should skip usage env for cursor native"
else
    ok "pre-tool skips HARNESS_AGENT_TURN_USAGE (X-14)"
fi

_lt="${ROOT}/.runtime/tmp/x14-x15-$$"
mkdir -p "$_lt/traces"
SKILLOPT_SKILL_TAG="alicloud-ecs-ops"
SKILLOPT_LOG_FILE="$_lt/test.log"
SKILLOPT_LOG_FORMAT=text
SKILLOPT_LANGFUSE_ENABLED=false
SKILLOPT_SESSION_ID="sess-x14-x15-$$"
SKILLOPT_RUNTIME_DATA="$_lt/runtime.json"
printf '%s\n' '{}' > "$SKILLOPT_RUNTIME_DATA"
ALIBABA_CLOUD_RUNTIME_DIR="$_lt"
export HARNESS_CODING_AGENT="cursor"
export HARNESS_AGENT_TURN_ID="$turn_id"
unset HARNESS_AGENT_TURN_USAGE

HARNESS_ROOT="$ROOT/alicloud-runtime-harness-ops"
# shellcheck source=/dev/null
source "$HARNESS_ROOT/scripts/harness-paths.sh"
# shellcheck source=/dev/null
source "$HARNESS_ROOT/scripts/harness-core-lib.sh"

skillopt_session_init
skillopt_trace_start "ecs" "NativeTurnBridge" "--RegionId" "cn-hangzhou"
_trace="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"

if jq -e '.llm_generations[0].total_tokens == 53800' "$_trace" >/dev/null 2>&1; then
    ok "harness ingested native turn via HARNESS_AGENT_TURN_ID (no usage env)"
else
    bad "ingest failed: $(jq -c '.llm_generations' "$_trace" 2>/dev/null || echo missing)"
fi
if jq -e --arg tid "$turn_id" '.agent_turn_id == $tid' "$_trace" >/dev/null 2>&1; then
    ok "trace.agent_turn_id set (X-15)"
else
    bad "agent_turn_id missing"
fi
skillopt_trace_end "success" "" '{"Code":"200"}'

# X-15: two turns → distinct attribution
turn_a="$ROOT/scripts/fixtures/agent-turn/cursor/turn-attribution-turn-a.json"
turn_b="$ROOT/scripts/fixtures/agent-turn/cursor/turn-attribution-turn-b.json"
id_a="$(agent_turn_parse_cursor_stdin "$(cat "$turn_a")" | jq -r '.turn_id')"
id_b="$(agent_turn_parse_cursor_stdin "$(cat "$turn_b")" | jq -r '.turn_id')"
agent_turn_write_turn_record "$(agent_turn_normalize_json "$(agent_turn_parse_cursor_stdin "$(cat "$turn_a")")")"
export HARNESS_AGENT_TURN_ID="$id_a"
SKILLOPT_SESSION_ID="sess-x15-a-$$"
skillopt_session_init
skillopt_trace_start "ecs" "TurnA" "--PageSize" "1"
_trace_a="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
tok_a="$(jq -r '.llm_generations[0].total_tokens // 0' "$_trace_a")"
skillopt_trace_end "success" "" '{"Code":"200"}'

agent_turn_write_turn_record "$(agent_turn_normalize_json "$(agent_turn_parse_cursor_stdin "$(cat "$turn_b")")")"
export HARNESS_AGENT_TURN_ID="$id_b"
SKILLOPT_SESSION_ID="sess-x15-b-$$"
skillopt_session_init
skillopt_trace_start "ecs" "TurnB" "--PageSize" "1"
_trace_b="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
tok_b="$(jq -r '.llm_generations[0].total_tokens // 0' "$_trace_b")"
skillopt_trace_end "success" "" '{"Code":"200"}'

if [[ "$tok_a" == "3200" && "$tok_b" == "5400" && "$id_a" != "$id_b" ]]; then
    ok "distinct turn attribution tokens"
else
    bad "turn tokens a=$tok_a b=$tok_b ids=$id_a/$id_b"
fi

# token_rollup by_turn dimension
trace_out="${_lt}/trace-rollup-x15.json"
jq -n \
    --arg tid "$id_a" \
    --arg sid "sess-rollup" \
    '{
        trace_id: "trace-rollup-x15",
        session_id: $sid,
        skill: "alicloud-ecs-ops",
        action: "DescribeInstances",
        status: "success",
        agent_turn_id: $tid,
        start_time: "2026-06-22T12:00:00Z",
        end_time: "2026-06-22T12:00:01Z",
        llm_usage: {prompt_tokens: 3000, completion_tokens: 200, total_tokens: 3200},
        llm_generations: [{role: "agent_turn", total_tokens: 3200, prompt_tokens: 3000, completion_tokens: 200}]
    }' > "$trace_out"
if python3 - <<PY
import json
import sys
from pathlib import Path
sys.path.insert(0, "${ROOT}/scripts")
import token_rollup as tr
trace = json.loads(Path("${trace_out}").read_text(encoding="utf-8"))
rec = tr.normalize_wrapper_trace(trace, Path("${trace_out}"))
assert rec is not None and rec.agent_turn_id == "${id_a}"
agg = tr.aggregate_records([rec])
assert "${id_a}" in agg.get("by_turn", {})
PY
then
    ok "token_rollup by_turn dimension"
else
    bad "token_rollup by_turn"
fi

rm -rf "$_lt" "$ROOT/.runtime/token/context"
rm -f "$ROOT/.runtime/sessions/alicloud-ecs-ops/skillopt-session-sess-x1"*.json 2>/dev/null || true

echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]]
