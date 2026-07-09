#!/usr/bin/env bash
#
# Langfuse 事件类型集成测试
# 模拟 Phase 2 文档中定义的 10 种事件类型，验证 Langfuse 上报
#

set -euo pipefail

# 加载环境变量（safe parse: 不执行、不覆盖、保留末行无换行变量）
SKILL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${SKILL_ROOT}/../.env"
if [[ -f "$ENV_FILE" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        local key="${line%%=*}"
        local value="${line#*=}"
        key="$(echo "$key" | xargs 2>/dev/null || echo "$key")"
        value="$(echo "$value" | xargs 2>/dev/null || echo "$value")"
        [[ -n "$key" && -z "${!key:-}" ]] && export "$key=$value"
    done < "$ENV_FILE"
fi

# 加载 skillopt-lib.sh
source "${SKILL_ROOT}/scripts/skillopt-lib.sh"

# 强制启用 Langfuse
export SKILLOPT_LANGFUSE_ENABLED="true"
export SKILLOPT_SKILL_TAG="alicloud-cms-ops"

# 初始化
skillopt_init --skillopt-enable
skillopt_session_init

AUTH=$(printf '%s' "${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}" | base64)
TEST_SESSION="sess-event-test-$(date +%s)"
PASS=0
FAIL=0
TOTAL=0

# 通用上报函数
report_event() {
    local type="$1"
    local body="$2"
    local event_id="evt-${type}-$(date +%s)-${RANDOM}"
    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"

    local payload
    payload=$(jq -n \
        --arg eid "$event_id" \
        --arg type "$type" \
        --arg ts "$ts" \
        --argjson body "$body" \
        '{batch: [{id: $eid, type: $type, timestamp: $ts, body: $body}]}')

    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        "${LANGFUSE_HOST}/api/public/ingestion" \
        -H "Authorization: Basic ${AUTH}" \
        -H "Content-Type: application/json" \
        -d "$payload")

    TOTAL=$((TOTAL + 1))
    if [[ "$http_code" == "201" || "$http_code" == "207" ]]; then
        PASS=$((PASS + 1))
        echo "  [PASS] HTTP $http_code"
    else
        FAIL=$((FAIL + 1))
        echo "  [FAIL] HTTP $http_code"
    fi
}

echo "============================================"
echo "  Langfuse 事件类型集成测试"
echo "  Session: $TEST_SESSION"
echo "  Langfuse: $LANGFUSE_HOST"
echo "============================================"
echo

# ---- 1. api_call_start ----
echo "1. api_call_start (API 调用前)"
report_event "span-create" "$(jq -n \
    --arg tid "trace-api-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: "span-api-start",
        traceId: $tid,
        sessionId: $sid,
        name: "skillopt:api_call_start",
        input: {product: "cms", action: "DescribeMetricList", params: {Namespace: "acs_ecs_dashboard", MetricName: "CPUUtilization"}},
        metadata: {skill: "alicloud-cms-ops", event_type: "api_call_start"}
    }')"
echo

# ---- 2. api_call_success ----
echo "2. api_call_success (API 调用成功)"
report_event "span-create" "$(jq -n \
    --arg tid "trace-api-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: "span-api-success",
        traceId: $tid,
        sessionId: $sid,
        name: "skillopt:api_call_success",
        input: {product: "cms", action: "DescribeMetricList", params: {Namespace: "acs_ecs_dashboard", MetricName: "CPUUtilization"}},
        output: {success: true, request_id: "ABC-123-DEF", duration_ms: 230},
        metadata: {skill: "alicloud-cms-ops", event_type: "api_call_success", duration_ms: 230}
    }')"
echo

# ---- 3. api_call_error ----
echo "3. api_call_error (API 调用失败)"
report_event "span-create" "$(jq -n \
    --arg tid "trace-api-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: "span-api-error",
        traceId: $tid,
        sessionId: $sid,
        name: "skillopt:api_call_error",
        input: {product: "cms", action: "DescribeMetricList"},
        output: {success: false, error_code: "Throttling.User", error_message: "Request was denied due to user flow control"},
        metadata: {skill: "alicloud-cms-ops", event_type: "api_call_error", error_code: "Throttling.User", duration_ms: 150}
    }')"
echo

# ---- 4. optimization_decision ----
echo "4. optimization_decision (参数优化)"
report_event "span-create" "$(jq -n \
    --arg tid "trace-opt-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: "span-opt-decision",
        traceId: $tid,
        sessionId: $sid,
        name: "skillopt:optimization_decision",
        input: {original_params: {Period: 60, Statistics: "Average"}},
        output: {optimized_params: {Period: 300, Statistics: "Average"}, reason: "high_error_rate"},
        metadata: {skill: "alicloud-cms-ops", event_type: "optimization_decision", error_rate: 15.5, reason: "high_error_rate"}
    }')"
echo

# ---- 5. repair_start ----
echo "5. repair_start (开始修复)"
report_event "span-create" "$(jq -n \
    --arg tid "trace-repair-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: "span-repair-start",
        traceId: $tid,
        sessionId: $sid,
        name: "skillopt:repair_start",
        input: {error_code: "Throttling.User", product: "cms", action: "DescribeMetricList"},
        metadata: {skill: "alicloud-cms-ops", event_type: "repair_start", error_code: "Throttling.User", strategy: "exponential_backoff"}
    }')"
echo

# ---- 6. repair_success ----
echo "6. repair_success (修复成功)"
report_event "span-create" "$(jq -n \
    --arg tid "trace-repair-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: "span-repair-success",
        traceId: $tid,
        sessionId: $sid,
        name: "skillopt:repair_success",
        input: {error_code: "Throttling.User", product: "cms", action: "DescribeMetricList", strategy: "exponential_backoff"},
        output: {success: true, retry_count: 2, duration_ms: 3500},
        metadata: {skill: "alicloud-cms-ops", event_type: "repair_success", error_code: "Throttling.User", retry_count: 2, duration_ms: 3500}
    }')"
echo

# ---- 7. repair_failed ----
echo "7. repair_failed (修复失败)"
report_event "span-create" "$(jq -n \
    --arg tid "trace-repair-test-2" \
    --arg sid "$TEST_SESSION" \
    '{
        id: "span-repair-failed",
        traceId: $tid,
        sessionId: $sid,
        name: "skillopt:repair_failed",
        input: {error_code: "InvalidParameter", product: "cms", action: "DescribeMetricList", strategy: "exponential_backoff"},
        output: {success: false, reason: "max_retries_exceeded"},
        metadata: {skill: "alicloud-cms-ops", event_type: "repair_failed", error_code: "InvalidParameter", reason: "max_retries_exceeded", retry_count: 3}
    }')"
echo

# ---- 8. circuit_breaker_open ----
echo "8. circuit_breaker_open (熔断器打开)"
report_event "span-create" "$(jq -n \
    --arg tid "trace-cb-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: "span-cb-open",
        traceId: $tid,
        sessionId: $sid,
        name: "skillopt:circuit_breaker_open",
        metadata: {skill: "alicloud-cms-ops", event_type: "circuit_breaker_open", threshold: 3, consecutive_failures: 3, cooldown_seconds: 60}
    }')"
echo

# ---- 9. circuit_breaker_close ----
echo "9. circuit_breaker_close (熔断器关闭)"
report_event "span-create" "$(jq -n \
    --arg tid "trace-cb-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: "span-cb-close",
        traceId: $tid,
        sessionId: $sid,
        name: "skillopt:circuit_breaker_close",
        metadata: {skill: "alicloud-cms-ops", event_type: "circuit_breaker_close", probe_success: true, total_failures: 3}
    }')"
echo

# ---- 10. circuit_breaker_halfopen ----
echo "10. circuit_breaker_halfopen (熔断器半开)"
report_event "span-create" "$(jq -n \
    --arg tid "trace-cb-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: "span-cb-halfopen",
        traceId: $tid,
        sessionId: $sid,
        name: "skillopt:circuit_breaker_halfopen",
        metadata: {skill: "alicloud-cms-ops", event_type: "circuit_breaker_halfopen", cooldown_elapsed: true, elapsed_seconds: 65}
    }')"
echo

# ---- 创建 Trace 关联 ----
echo "--- 创建 Trace 关联 ---"
report_event "trace-create" "$(jq -n \
    --arg tid "trace-api-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: $tid,
        sessionId: $sid,
        name: "alicloud-cms-ops cms DescribeMetricList",
        input: {product: "cms", action: "DescribeMetricList", params: {Namespace: "acs_ecs_dashboard", MetricName: "CPUUtilization"}},
        output: {success: true, request_id: "ABC-123-DEF", duration_ms: 230, spans: 3},
        metadata: {skill: "alicloud-cms-ops", product: "cms", action: "DescribeMetricList", events: 3}
    }')"

report_event "trace-create" "$(jq -n \
    --arg tid "trace-opt-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: $tid,
        sessionId: $sid,
        name: "alicloud-cms-ops optimization",
        input: {original_params: {Period: 60, Statistics: "Average"}},
        output: {optimized_params: {Period: 300, Statistics: "Average"}, reason: "high_error_rate"},
        metadata: {skill: "alicloud-cms-ops", event_type: "optimization", events: 1}
    }')"

report_event "trace-create" "$(jq -n \
    --arg tid "trace-repair-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: $tid,
        sessionId: $sid,
        name: "alicloud-cms-ops repair Throttling.User",
        input: {error_code: "Throttling.User", product: "cms", action: "DescribeMetricList"},
        output: {success: true, retry_count: 2, duration_ms: 3500},
        metadata: {skill: "alicloud-cms-ops", event_type: "repair", events: 2}
    }')"

report_event "trace-create" "$(jq -n \
    --arg tid "trace-repair-test-2" \
    --arg sid "$TEST_SESSION" \
    '{
        id: $tid,
        sessionId: $sid,
        name: "alicloud-cms-ops repair InvalidParameter (failed)",
        input: {error_code: "InvalidParameter", product: "cms", action: "DescribeMetricList"},
        output: {success: false, reason: "max_retries_exceeded", retry_count: 3},
        metadata: {skill: "alicloud-cms-ops", event_type: "repair_failed", events: 1}
    }')"

report_event "trace-create" "$(jq -n \
    --arg tid "trace-cb-test" \
    --arg sid "$TEST_SESSION" \
    '{
        id: $tid,
        sessionId: $sid,
        name: "alicloud-cms-ops circuit_breaker lifecycle",
        input: {consecutive_failures: 3, threshold: 3},
        output: {state: "open → halfopen → close", probe_success: true},
        metadata: {skill: "alicloud-cms-ops", event_type: "circuit_breaker", events: 3}
    }')"

echo
echo "============================================"
echo "  测试结果: $PASS/$TOTAL 通过, $FAIL 失败"
echo "============================================"
echo
echo "等待 3 秒让异步请求完成..."
sleep 3
echo
echo "=== 从 Langfuse 验证数据 (trace-id 直查, AGENTS.md §15.7 L11) ==="
_TRACE_IDS=(trace-api-test trace-opt-test trace-repair-test trace-repair-test-2 trace-cb-test)
_verified_session_count=0
for _tid in "${_TRACE_IDS[@]}"; do
    _resp="$(curl -s -H "Authorization: Basic ${AUTH}" \
        "${LANGFUSE_HOST}/api/public/traces/${_tid}")"
    _sid="$(printf '%s' "$_resp" | jq -r '.sessionId // empty' 2>/dev/null || true)"
    _name="$(printf '%s' "$_resp" | jq -r '.name // empty' 2>/dev/null || true)"
    if [[ -n "$_sid" && "$_sid" == "$TEST_SESSION" ]]; then
        echo "  [PASS] trace=${_tid} sessionId=ok name=${_name}"
        _verified_session_count=$((_verified_session_count + 1))
    else
        echo "  [FAIL] trace=${_tid} sessionId='${_sid}'"
    fi
done
echo "verified_traces=${_verified_session_count}/${#_TRACE_IDS[@]}"

echo
if [[ $FAIL -eq 0 ]]; then
    echo "所有事件类型上报成功!"
else
    echo "有 $FAIL 个事件上报失败，请检查。"
fi
