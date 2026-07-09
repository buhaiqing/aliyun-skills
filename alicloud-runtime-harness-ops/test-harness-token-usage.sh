#!/usr/bin/env bash
# Phase 2 TEL — harness trace llm_generations[] + Prometheus LLM counters
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$ROOT")"
PASS=0
FAIL=0

ok() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

echo "=== alicloud-runtime-harness-ops token usage (Phase 2 + 3) ==="

bash -n "$ROOT/scripts/harness-core-lib.sh" && ok "harness-core-lib bash -n" || bad "harness-core-lib syntax"

if grep -q 'generation-create' "$ROOT/scripts/harness_runtime.py"; then
  ok "harness_runtime.py generation-create subcommand"
else
  bad "harness_runtime.py missing generation-create"
fi

if grep -q 'skillopt_record_llm_usage()' "$ROOT/scripts/harness-core-lib.sh"; then
  ok "skillopt_record_llm_usage defined"
else
  bad "skillopt_record_llm_usage missing"
fi

if grep -q '_skillopt_session_rollup_from_trace' "$ROOT/scripts/harness-core-lib.sh"; then
  ok "session rollup from trace defined"
else
  bad "session rollup missing"
fi

if grep -q 'agent-turn-latest.json' "$ROOT/scripts/harness-core-lib.sh"; then
  ok "harness reads IDE sidecar agent-turn-latest.json (Phase 4)"
else
  bad "sidecar ingest missing in harness-core-lib"
fi

if grep -q '_skillopt_ingest_mcp_context' "$ROOT/scripts/harness-core-lib.sh"; then
  ok "harness ingests mcp-context sidecar (Phase 4.5)"
else
  bad "mcp context ingest missing"
fi

_lt_root="${REPO_ROOT}/.runtime/tmp/harness-token-$$"
mkdir -p "$_lt_root/traces" "$_lt_root/metrics"
_SKILLOPT_SKILL_ROOT="$REPO_ROOT/alicloud-ecs-ops"
SKILLOPT_SKILL_TAG="alicloud-ecs-ops"
SKILLOPT_LOG_FILE="$_lt_root/test.log"
SKILLOPT_LOG_FORMAT=text
SKILLOPT_LANGFUSE_ENABLED=false
SKILLOPT_SESSION_ID="sess-token-$$"
SKILLOPT_METRICS_DIR="$_lt_root/metrics"
SKILLOPT_RUNTIME_DATA="$_lt_root/ecs-skillopt-runtime.json"
printf '%s\n' '{}' > "$SKILLOPT_RUNTIME_DATA"
ALIBABA_CLOUD_RUNTIME_DIR="$_lt_root"
export ALIYUN_SKILLS_ROOT="$REPO_ROOT"
export HARNESS_CODING_AGENT="cursor"

# shellcheck source=/dev/null
source "$ROOT/scripts/harness-paths.sh"
# shellcheck source=/dev/null
source "$ROOT/scripts/harness-core-lib.sh"

_resolved="$(skillopt_resolve_coding_agent)"
[[ "$_resolved" == "cursor" ]] && ok "resolve_coding_agent honors HARNESS_CODING_AGENT" || bad "resolve_coding_agent expected cursor got $_resolved"

skillopt_session_init
skillopt_trace_start "ecs" "TokenUsageSmoke" "--RegionId" "cn-hangzhou"
_trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"

if jq -e '.llm_generations == [] and .llm_usage.total_tokens == 0 and .coding_agent == "cursor"' "$_trace_file" >/dev/null 2>&1; then
  ok "trace_start seeds llm_generations/llm_usage/coding_agent"
else
  bad "trace_start missing TEL seed fields"
fi

skillopt_record_llm_usage "$(jq -n '{
  role: "gcl_critic",
  model: "gpt-4o-mini",
  prompt_tokens: 120,
  completion_tokens: 30,
  total_tokens: 150,
  source: "harness_gcl_critic",
  attribution_confidence: "observed",
  latency_ms: 42
}')"

if jq -e '
  (.llm_generations | length) == 1 and
  .llm_generations[0].coding_agent == "cursor" and
  .llm_generations[0].model == "gpt-4o-mini" and
  .llm_generations[0].total_tokens == 150 and
  .llm_usage.total_tokens == 150
' "$_trace_file" >/dev/null 2>&1; then
  ok "record_llm_usage appends generation + rollup"
else
  bad "record_llm_usage trace schema mismatch"
fi

_mem_file="${REPO_ROOT}/.runtime/memory/alicloud-ecs-ops/TokenUsageSmoke.jsonl"
_lines_before=0
[[ -f "$_mem_file" ]] && _lines_before="$(wc -l < "$_mem_file" | tr -d ' ')"

skillopt_trace_end "success" "" '{"Code":"200"}'

if [[ -f "$_mem_file" ]]; then
  _last="$(tail -1 "$_mem_file")"
  if echo "$_last" | jq -e 'has("llm_usage") | not' >/dev/null 2>&1; then
    ok "Layer 1 memory_store_lite excludes llm_usage"
  else
    bad "Layer 1 entry must not contain llm_usage"
  fi
else
  ok "Layer 1 memory file absent (isolated run)"
fi

skillopt_export_metrics
_prom="$_lt_root/metrics/skillopt_${SKILLOPT_SKILL_TAG}.prom"
if [[ -f "$_prom" ]] && grep -q 'harness_llm_total_tokens_total' "$_prom"; then
  ok "Prometheus export includes harness_llm_* counters"
else
  bad "Prometheus file missing harness_llm_total_tokens_total"
fi

# Regression guard: metrics file must be written atomically (tmp+rename).
if grep -q 'cat > "\$metrics_file"' "$ROOT/scripts/harness-core-lib.sh"; then
  bad "Prometheus metrics write is non-atomic (cat > directly)"
else
  ok "Prometheus metrics write uses atomic tmp+rename pattern"
fi

# Behavior guard: rapid exports should never leave the file empty or partial.
(
  for _ in $(seq 1 100); do
    skillopt_export_metrics
  done
) &_export_pid=$!
_atomic_ok=1
for _ in $(seq 1 500); do
  if [[ -f "$_prom" ]]; then
    if [[ ! -s "$_prom" ]] || ! grep -q '^skillopt_total_calls{' "$_prom" 2>/dev/null; then
      _atomic_ok=0
      break
    fi
  fi
done
wait $_export_pid
if [[ "$_atomic_ok" -eq 1 ]]; then
  ok "Prometheus file never empty/partial during rapid exports"
else
  bad "Prometheus file became empty/partial during rapid exports"
fi

echo "=== Phase 3: Session rollup + HARNESS_AGENT_TURN_USAGE ==="
_lt3="${REPO_ROOT}/.runtime/tmp/harness-token-p3-$$"
mkdir -p "$_lt3/traces"
SKILLOPT_SESSION_ID="sess-token-p3-$$"
SKILLOPT_LOG_FILE="$_lt3/test.log"
ALIBABA_CLOUD_RUNTIME_DIR="$_lt3"
SKILLOPT_RUNTIME_DATA="$_lt3/runtime.json"
printf '%s\n' '{}' > "$SKILLOPT_RUNTIME_DATA"
export HARNESS_AGENT_TURN_USAGE='{"turn_id":"turn-1","coding_agent":"cursor","model":"claude-sonnet-4","prompt_tokens":1000,"completion_tokens":200,"total_tokens":1200,"context_metadata":{}}'

skillopt_session_init
skillopt_trace_start "ecs" "SessionRollupSmoke" "--RegionId" "cn-hangzhou"
_trace_p3="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
_session_p3="${_SKILLOPT_RUNTIME_ROOT}/skillopt-session-${SKILLOPT_SESSION_ID}.json"

if jq -e '(.llm_generations | length) == 1 and .llm_generations[0].role == "agent_turn"' "$_trace_p3" >/dev/null 2>&1; then
  ok "HARNESS_AGENT_TURN_USAGE ingested on trace_start"
else
  bad "agent turn not ingested from env"
fi

skillopt_record_llm_usage "$(jq -n '{
  role: "gcl_critic",
  model: "gpt-4o-mini",
  source: "harness_gcl_critic",
  prompt_tokens: 50,
  completion_tokens: 10,
  total_tokens: 60,
  attribution_confidence: "observed"
}')"
skillopt_trace_end "success" "" '{"Code":"200"}'

if jq -e '
  .llm_usage_total.total_tokens == 1260 and
  .agent_model == "claude-sonnet-4" and
  .context_metadata == {} and
  ([.llm_usage_by_agent_model[].total_tokens] | add) == 1260
' "$_session_p3" >/dev/null 2>&1; then
  ok "session rollup reconcile (1260 tokens across buckets)"
else
  bad "session rollup mismatch: $(jq -c '{total: .llm_usage_total, buckets: .llm_usage_by_agent_model}' "$_session_p3" 2>/dev/null || echo missing)"
fi

export HARNESS_AGENT_TURN_USAGE='{not-json'
SKILLOPT_SESSION_ID="sess-token-p3-bad-$$"
skillopt_session_init
skillopt_trace_start "ecs" "BadTurnUsage" "--RegionId" "cn-hangzhou"
if skillopt_trace_end "success" "" '{"Code":"200"}'; then
  ok "malformed HARNESS_AGENT_TURN_USAGE fail-open"
else
  bad "malformed agent turn usage crashed wrapper path"
fi
unset HARNESS_AGENT_TURN_USAGE

rm -rf "$_lt3"
rm -rf "$_lt_root"

echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]]
