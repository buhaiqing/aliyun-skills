#!/usr/bin/env bash
# TEL X-13 — W3C traceparent IDE → harness bridge (simulated e2e, no real IDE).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

ok() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

echo "=== OTel traceparent bridge (X-13 simulated e2e) ==="
export ALIYUN_SKILLS_ROOT="$ROOT"
unset HARNESS_AGENT_TURN_USAGE SKILLOPT_AGENT_TURN_USAGE TRACEPARENT TRACESTATE ALIBABA_CLOUD_RUNTIME_DIR

for f in \
    "$ROOT/scripts/lib/otel-traceparent.sh" \
    "$ROOT/assets/hooks/cursor/session-start.sh" \
    "$ROOT/assets/hooks/cursor/pre-tool-harness-wrapper.sh"; do
    bash -n "$f" && ok "bash -n $(basename "$f")" || bad "syntax $(basename "$f")"
done

# shellcheck source=lib/otel-traceparent.sh
source "$ROOT/scripts/lib/otel-traceparent.sh"

FIX_TP="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
if otel_traceparent_validate "$FIX_TP"; then
    ok "validate fixture traceparent"
else
    bad "validate fixture traceparent"
fi

otel_traceparent_parse "$FIX_TP" || bad "parse fixture"
[[ "$OTEL_TRACE_ID" == "4bf92f3577b34da6a3ce929d0e0e4736" ]] && ok "parse trace_id" || bad "parse trace_id"

child="$(otel_traceparent_child "$FIX_TP")"
otel_traceparent_parse "$child" || bad "child parse"
[[ "$OTEL_TRACE_ID" == "4bf92f3577b34da6a3ce929d0e0e4736" ]] && ok "child preserves trace_id" || bad "child trace_id"
[[ "$OTEL_PARENT_SPAN_ID" != "00f067aa0ba902b7" ]] && ok "child new parent_span_id" || bad "child parent_span_id"

otel_traceparent_same_trace "$FIX_TP" "$child" && ok "same_trace helper" || bad "same_trace"

rm -rf "$ROOT/.runtime/token/context"
otel_traceparent_write_sidecar "$FIX_TP"
[[ "$(otel_traceparent_read_sidecar)" == "$FIX_TP" ]] && ok "traceparent sidecar roundtrip" || bad "sidecar"

# Session start generates root traceparent when absent
printf '%s' '{"conversation_id":"x13-conv"}' | bash "$ROOT/assets/hooks/cursor/session-start.sh"
if otel_traceparent_validate "$(otel_traceparent_read_sidecar 2>/dev/null || true)"; then
    ok "session-start wrote traceparent sidecar"
else
    bad "session-start traceparent"
fi

# Agent turn sidecar with w3c_traceparent (no env injection path)
# shellcheck source=lib/agent-turn-usage.sh
source "$ROOT/scripts/lib/agent-turn-usage.sh"
ROOT_TP="$(otel_traceparent_read_sidecar)"
USAGE_JSON="$(agent_turn_normalize_json "$(jq -n --arg tp "$ROOT_TP" '{
    turn_id: "turn-x13",
    coding_agent: "cursor",
    model: "claude-sonnet-4",
    prompt_tokens: 9000,
    completion_tokens: 500,
    total_tokens: 9500,
    w3c_traceparent: $tp
}')")"
agent_turn_write_sidecar "$USAGE_JSON"

CHILD_TP="$(otel_traceparent_child "$ROOT_TP")"
export TRACEPARENT="$CHILD_TP"
unset HARNESS_AGENT_TURN_USAGE

_lt="${ROOT}/.runtime/tmp/otel-bridge-$$"
mkdir -p "$_lt/traces"
SKILLOPT_SKILL_TAG="alicloud-ecs-ops"
SKILLOPT_LOG_FILE="$_lt/test.log"
SKILLOPT_LOG_FORMAT=text
SKILLOPT_LANGFUSE_ENABLED=false
SKILLOPT_SESSION_ID="sess-otel-x13-$$"
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
skillopt_trace_start "ecs" "OtelBridgeSmoke" "--RegionId" "cn-hangzhou"
_trace="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"

if jq -e '.w3c_trace_context.trace_id != null' "$_trace" >/dev/null 2>&1; then
    ok "harness ingested w3c_trace_context from TRACEPARENT"
else
    bad "w3c_trace_context missing: $(jq -c '.w3c_trace_context' "$_trace" 2>/dev/null || echo null)"
fi

if jq -e '.llm_generations[0].role == "agent_turn" and .llm_generations[0].total_tokens == 9500' "$_trace" >/dev/null 2>&1; then
    ok "agent turn ingested via TRACEPARENT sidecar correlation (no env)"
else
    bad "agent turn via traceparent: $(jq -c '.llm_generations' "$_trace" 2>/dev/null || echo missing)"
fi

skillopt_trace_end "success" "" '{"Code":"200"}'

# pre-tool hook exports TRACEPARENT for wrapper commands
cmd='cd alicloud-ecs-ops && ./scripts/ecs-harness-wrapper.sh DescribeInstances --PageSize 1'
out="$(printf '%s' "{\"command\":$(printf '%s' "$cmd" | jq -Rs .)}" | bash "$ROOT/assets/hooks/cursor/pre-tool-harness-wrapper.sh")"
if printf '%s' "$out" | jq -e '.updated_input.command | test("TRACEPARENT=00-")' >/dev/null 2>&1; then
    ok "cursor pre-tool prepends TRACEPARENT for wrapper"
else
    bad "cursor pre-tool TRACEPARENT: $out"
fi

# Mismatch traceparent must not ingest agent turn
MISMATCH_TP="$(otel_traceparent_generate_root)"
export TRACEPARENT="$(otel_traceparent_child "$MISMATCH_TP")"
SKILLOPT_SESSION_ID="sess-otel-mismatch-$$"
skillopt_session_init
skillopt_trace_start "ecs" "Mismatch" "--RegionId" "cn-hangzhou"
_trace2="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
if jq -e '(.llm_generations | length) == 0' "$_trace2" >/dev/null 2>&1; then
    ok "trace-id mismatch skips stale agent-turn sidecar"
else
    bad "mismatch should not ingest agent turn"
fi
skillopt_trace_end "success" "" '{"Code":"200"}'

rm -rf "$_lt" "$ROOT/.runtime/token/context"
rm -f "$ROOT/.runtime/sessions/alicloud-ecs-ops/skillopt-session-sess-otel-"*.json 2>/dev/null || true

echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]]
