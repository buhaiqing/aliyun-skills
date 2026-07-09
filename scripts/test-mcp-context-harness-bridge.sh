#!/usr/bin/env bash
# Harness bridge — MCP context sidecar → trace.context_metadata.mcp
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0 FAIL=0
ok() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

echo "=== MCP context harness bridge (Phase 4.5) ==="
export ALIYUN_SKILLS_ROOT="$ROOT"
unset ALIBABA_CLOUD_RUNTIME_DIR HARNESS_AGENT_TURN_USAGE

source "${ROOT}/scripts/lib/mcp-context-common.sh"

meta="$(bash "${ROOT}/scripts/mcp-context/collect-cursor.sh" --fixture-dir "${ROOT}/scripts/fixtures/mcp-context/cursor/03-loaded-and-invoked")"
mcp_context_write_sidecar "$meta"

_lt="${ROOT}/.runtime/tmp/mcp-bridge-$$"
mkdir -p "$_lt/traces"
_SKILLOPT_SKILL_ROOT="$ROOT/alicloud-ecs-ops"
SKILLOPT_SKILL_TAG="alicloud-ecs-ops"
SKILLOPT_LOG_FILE="$_lt/test.log"
SKILLOPT_LOG_FORMAT=text
SKILLOPT_LANGFUSE_ENABLED=false
SKILLOPT_SESSION_ID="sess-mcp-bridge-$$"
SKILLOPT_RUNTIME_DATA="$_lt/runtime.json"
printf '%s\n' '{}' > "$SKILLOPT_RUNTIME_DATA"
ALIBABA_CLOUD_RUNTIME_DIR="$_lt"

source "${ROOT}/alicloud-runtime-harness-ops/scripts/harness-paths.sh"
source "${ROOT}/alicloud-runtime-harness-ops/scripts/harness-core-lib.sh"

skillopt_session_init
skillopt_trace_start "ecs" "McpBridgeSmoke" "--RegionId" "cn-hangzhou"
_trace="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"

if jq -e '.context_metadata.mcp.mcp_tool_utilization == 0.5' "$_trace" >/dev/null 2>&1; then
    ok "trace context_metadata.mcp utilization 0.5"
else
    bad "trace missing mcp metadata: $(jq -c '.context_metadata' "$_trace" 2>/dev/null)"
fi

skillopt_trace_end "success" "" '{"Code":"200"}'
_session="${_SKILLOPT_RUNTIME_ROOT}/skillopt-session-${SKILLOPT_SESSION_ID}.json"
if jq -e '.context_metadata.mcp.mcp_tools_loaded | length == 2' "$_session" >/dev/null 2>&1; then
    ok "session rollup merged context_metadata.mcp"
else
    bad "session missing mcp rollup"
fi

rm -rf "$_lt" "${ROOT}/.runtime/token/context" 2>/dev/null || true
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]]
