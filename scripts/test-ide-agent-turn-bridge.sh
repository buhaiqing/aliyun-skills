#!/usr/bin/env bash
# TEL Phase 4 — simulated IDE hook → harness wrapper bridge (no real IDE).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

ok() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

echo "=== IDE agent turn bridge (Phase 4 simulated e2e) ==="
export ALIYUN_SKILLS_ROOT="$ROOT"
unset HARNESS_AGENT_TURN_USAGE SKILLOPT_AGENT_TURN_USAGE ALIBABA_CLOUD_RUNTIME_DIR

for f in \
    "$ROOT/scripts/lib/agent-turn-usage.sh" \
    "$ROOT/scripts/hooks/simulate-ide-agent-turn.sh" \
    "$ROOT/assets/hooks/cursor/session-start.sh" \
    "$ROOT/assets/hooks/cursor/after-agent-response.sh" \
    "$ROOT/assets/hooks/cursor/pre-tool-harness-wrapper.sh" \
    "$ROOT/assets/hooks/claude-code/session-start.sh" \
    "$ROOT/assets/hooks/claude-code/after-agent-turn.sh"; do
    bash -n "$f" && ok "bash -n $(basename "$f")" || bad "syntax $(basename "$f")"
done

# shellcheck source=lib/agent-turn-usage.sh
source "$ROOT/scripts/lib/agent-turn-usage.sh"
fixture="$ROOT/scripts/fixtures/agent-turn-cursor.json"
norm="$(agent_turn_normalize_json "$(cat "$fixture")")"
[[ "$norm" == *'"total_tokens":12800'* ]] && ok "normalize fixture cursor" || bad "normalize fixture"

rm -rf "$ROOT/.runtime/token/context"
agent_turn_write_sidecar "$norm"
[[ -f "$ROOT/.runtime/token/context/agent-turn-latest.json" ]] && ok "sidecar written" || bad "sidecar missing"

# Harness picks up sidecar on trace_start (env unset)
_lt="${ROOT}/.runtime/tmp/ide-bridge-$$"
mkdir -p "$_lt/traces"
_SKILLOPT_SKILL_ROOT="$ROOT/alicloud-ecs-ops"
SKILLOPT_SKILL_TAG="alicloud-ecs-ops"
SKILLOPT_LOG_FILE="$_lt/test.log"
SKILLOPT_LOG_FORMAT=text
SKILLOPT_LANGFUSE_ENABLED=false
SKILLOPT_SESSION_ID="sess-ide-bridge-$$"
SKILLOPT_RUNTIME_DATA="$_lt/runtime.json"
printf '%s\n' '{}' > "$SKILLOPT_RUNTIME_DATA"
ALIBABA_CLOUD_RUNTIME_DIR="$_lt"
export HARNESS_CODING_AGENT="cursor"

HARNESS_ROOT="$ROOT/alicloud-runtime-harness-ops"
# shellcheck source=/dev/null
source "$HARNESS_ROOT/scripts/harness-paths.sh"
# shellcheck source=/dev/null
source "$HARNESS_ROOT/scripts/harness-core-lib.sh"

skillopt_session_init
skillopt_trace_start "ecs" "IdeBridgeSmoke" "--RegionId" "cn-hangzhou"
_trace="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"

if jq -e '.llm_generations[0].role == "agent_turn" and .llm_generations[0].total_tokens == 12800' "$_trace" >/dev/null 2>&1; then
    ok "harness ingested sidecar on trace_start"
else
    bad "sidecar not ingested: $(jq -c '.llm_generations' "$_trace" 2>/dev/null || echo missing)"
fi

skillopt_trace_end "success" "" '{"Code":"200"}'
_session="${_SKILLOPT_RUNTIME_ROOT}/skillopt-session-${SKILLOPT_SESSION_ID}.json"
if jq -e '.llm_usage_total.total_tokens == 12800' "$_session" >/dev/null 2>&1; then
    ok "session rollup after sidecar bridge"
else
    bad "session rollup: $(jq -c '.llm_usage_total' "$_session" 2>/dev/null || echo missing)"
fi

# Env wins over sidecar
export HARNESS_AGENT_TURN_USAGE='{"turn_id":"env-win","coding_agent":"cursor","model":"gpt-4","prompt_tokens":10,"completion_tokens":1,"total_tokens":11}'
SKILLOPT_SESSION_ID="sess-ide-bridge-env-$$"
skillopt_session_init
skillopt_trace_start "ecs" "EnvWins" "--RegionId" "cn-hangzhou"
_trace2="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
if jq -e '.llm_generations[0].total_tokens == 11' "$_trace2" >/dev/null 2>&1; then
    ok "HARNESS_AGENT_TURN_USAGE env overrides sidecar"
else
    bad "env precedence failed"
fi
skillopt_trace_end "success" "" '{"Code":"200"}'

# Cursor hook scripts (fixture stdin)
printf '%s' '{"conversation_id":"conv-abc","usage":{"prompt_tokens":50,"completion_tokens":5,"total_tokens":55}}' | \
    bash "$ROOT/assets/hooks/cursor/after-agent-response.sh"
if jq -e '.total_tokens == 55 and .coding_agent == "cursor"' "$(agent_turn_sidecar_path)" >/dev/null 2>&1; then
    ok "cursor after-agent-response hook wrote sidecar"
else
    bad "cursor hook sidecar"
fi

cmd='cd alicloud-ecs-ops && ./scripts/ecs-harness-wrapper.sh DescribeInstances --PageSize 1'
out="$(printf '%s' "{\"command\":$(printf '%s' "$cmd" | jq -Rs .)}" | bash "$ROOT/assets/hooks/cursor/pre-tool-harness-wrapper.sh")"
if printf '%s' "$out" | jq -e '.updated_input.command | test("HARNESS_AGENT_TURN_USAGE")' >/dev/null 2>&1; then
    ok "cursor pre-tool prepends HARNESS exports for wrapper"
else
    bad "cursor pre-tool output: $out"
fi

rm -rf "$_lt" "$ROOT/.runtime/token/context"
rm -f "$ROOT/.runtime/sessions/alicloud-ecs-ops/skillopt-session-sess-ide-bridge-"*.json 2>/dev/null || true

echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]]
