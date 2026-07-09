#!/usr/bin/env bash
#
# Langfuse 灰度 Skill 集成测试：ACK + DAS + ALB + CEN
# 验证运行时目录规范、wrapper 引用、Session 共享、本地 trace 闭合、Langfuse 入库。
#

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

PASS=0
FAIL=0
TOTAL=0

record_pass() {
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
    echo "  [PASS] $1"
}

record_fail() {
    FAIL=$((FAIL + 1))
    TOTAL=$((TOTAL + 1))
    echo "  [FAIL] $1"
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $1" >&2
        exit 1
    fi
}

load_env() {
    if [[ ! -f "$ENV_FILE" ]]; then
        echo "ERROR: .env file not found at $ENV_FILE" >&2
        exit 1
    fi

    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        key="${line%%=*}"
        value="${line#*=}"
        key="$(echo "$key" | xargs)"
        value="$(echo "$value" | xargs)"
        if [[ -n "$key" && -z "${!key:-}" ]]; then
            export "$key=$value"
        fi
    done < "$ENV_FILE"
}

validate_env() {
    for var in LANGFUSE_HOST LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY ALIBABA_CLOUD_ACCESS_KEY_ID ALIBABA_CLOUD_ACCESS_KEY_SECRET; do
        if [[ -z "${!var:-}" ]]; then
            echo "ERROR: $var is not set" >&2
            exit 1
        fi
    done
}

static_check_skill() {
    local skill="$1"
    local wrapper="$2"
    local root="${PROJECT_ROOT}/${skill}"

    echo "=== 静态检查: ${skill} ==="

    if [[ -f "${root}/scripts/harness-lib.sh" ]]; then
        record_pass "${skill}: scripts/harness-lib.sh exists (canonical)"
    else
        record_fail "${skill}: scripts/harness-lib.sh missing"
    fi

    if [[ -L "${root}/scripts/skillopt-lib.sh" && "$(readlink "${root}/scripts/skillopt-lib.sh")" == "harness-lib.sh" ]]; then
        record_pass "${skill}: skillopt-lib.sh legacy symlink -> harness-lib.sh"
    elif [[ -f "${root}/scripts/skillopt-lib.sh" && ! -L "${root}/scripts/skillopt-lib.sh" ]]; then
        record_fail "${skill}: skillopt-lib.sh should be symlink to harness-lib.sh (PR-9)"
    else
        record_fail "${skill}: skillopt-lib.sh legacy shim missing"
    fi

    if [[ -f "${root}/references/skillopt-lib.sh" ]]; then
        record_fail "${skill}: references/skillopt-lib.sh still exists (must be scripts/ only)"
    else
        record_pass "${skill}: no references/skillopt-lib.sh"
    fi

    if [[ -f "${root}/scripts/skillopt_runtime.py" ]]; then
        record_fail "${skill}: local scripts/skillopt_runtime.py should be removed (use alicloud-runtime-harness-ops)"
    else
        record_pass "${skill}: no duplicate skillopt_runtime.py"
    fi

    if grep -qE 'skillopt-core-lib\.sh|harness-core-lib\.sh' "${root}/scripts/harness-lib.sh" 2>/dev/null; then
        record_pass "${skill}: overlay sources shared runtime core (legacy or harness path)"
    else
        record_fail "${skill}: overlay missing shared core source"
    fi

    if grep -qE 'source "\$SCRIPT_DIR/(skillopt-lib|harness-lib)\.sh"' "${root}/scripts/${wrapper}"; then
        record_pass "${skill}: wrapper sources scripts overlay lib"
    else
        record_fail "${skill}: wrapper source path is not updated"
    fi

    if bash -n "${root}/scripts/skillopt-lib.sh" && bash -n "${root}/scripts/${wrapper}"; then
        record_pass "${skill}: bash syntax ok"
    else
        record_fail "${skill}: bash syntax failed"
    fi

    if zsh -c "source '${root}/scripts/skillopt-lib.sh'"; then
        record_pass "${skill}: zsh source ok"
    else
        record_fail "${skill}: zsh source failed"
    fi

    if grep -q 'SKILLOPT_JUDGE_' "${root}/scripts/skillopt-lib.sh"; then
        record_fail "${skill}: dead SKILLOPT_JUDGE_* config should be removed (PR-5)"
    else
        record_pass "${skill}: no dead judge config"
    fi

    if grep -q 'skillopt_trace_required()' "${root}/scripts/skillopt-lib.sh"; then
        record_pass "${skill}: trace_required helper exists"
    else
        record_fail "${skill}: trace_required helper missing"
    fi

    if grep -q '\[\[ "$SKILLOPT_LANGFUSE_ENABLED" == "true" \]\] || return 0' "${root}/scripts/skillopt-lib.sh"; then
        record_pass "${skill}: Langfuse post is gated by Langfuse enable flag"
    else
        record_fail "${skill}: Langfuse post is not gated by Langfuse enable flag"
    fi

    echo
}

run_case() {
    local short="$1"
    local skill="$2"
    local wrapper="$3"
    local expected_status="$4"
    local forbidden_output="${5:-}"
    shift 5

    local root="${PROJECT_ROOT}/${skill}"
    local out_file="/tmp/${short}-langfuse-gray.out"
    local err_file="/tmp/${short}-langfuse-gray.err"

    echo "=== 运行用例: ${skill} ==="
    echo "执行: ${wrapper} $*"

    set +e
    "${root}/scripts/${wrapper}" "$@" >"$out_file" 2>"$err_file"
    local rc=$?
    set -e

    local out_size
    out_size="$(wc -c < "$out_file" | tr -d ' ')"
    echo "  exit_code=${rc}, output_bytes=${out_size}"

    if [[ "$out_size" -gt 0 ]]; then
        record_pass "${skill}: command produced output"
    else
        record_fail "${skill}: command output is empty"
    fi

    if [[ -n "$forbidden_output" ]]; then
        if grep -q "$forbidden_output" "$out_file" "$err_file" 2>/dev/null; then
            record_fail "${skill}: output contains forbidden text: ${forbidden_output}"
        else
            record_pass "${skill}: output does not contain forbidden text: ${forbidden_output}"
        fi
    fi

    local trace_file
    trace_file="$(ls -t "${PROJECT_ROOT}/.runtime/traces/${skill}/trace-${SHARED_SESSION}-"*.json 2>/dev/null | head -1 || true)"
    if [[ -z "$trace_file" ]]; then
        record_fail "${skill}: local trace file not found"
        echo
        return
    fi

    local trace_id
    trace_id="$(basename "$trace_file" .json)"
    echo "  trace_id=${trace_id}"

    local local_status local_session input_type output_type output_empty
    local_status="$(jq -r '.status // empty' "$trace_file")"
    local_session="$(jq -r '.session_id // empty' "$trace_file")"
    input_type="$(jq -r '.input | type' "$trace_file")"
    output_type="$(jq -r '.output | type' "$trace_file")"
    output_empty="$(jq -r '(.output == null) or (.output == "")' "$trace_file")"

    if [[ "$local_status" == "$expected_status" ]]; then
        record_pass "${skill}: local trace status=${expected_status}"
    else
        record_fail "${skill}: local trace status expected=${expected_status}, actual=${local_status}"
    fi

    if [[ "$local_session" == "$SHARED_SESSION" ]]; then
        record_pass "${skill}: local trace session matches"
    else
        record_fail "${skill}: local trace session mismatch"
    fi

    if [[ "$input_type" == "array" ]]; then
        record_pass "${skill}: local trace input is array"
    else
        record_fail "${skill}: local trace input type=${input_type}"
    fi

    if [[ "$output_empty" == "false" ]]; then
        record_pass "${skill}: local trace output is non-empty (${output_type})"
    else
        record_fail "${skill}: local trace output is empty"
    fi

    local lf_file="/tmp/${short}-langfuse-gray-trace.json"
    local lf_session=""
    local lf_input_type="null"
    local lf_output_type="null"
    local lf_output_empty="true"
    local lf_name=""
    local lf_trace_display_severity=""
    local lf_flow_span_id=""
    local lf_optimization_count="0"
    local lf_optimization_io_count="0"
    local lf_judgement_level=""
    local lf_judgement_status_message=""
    local lf_judgement_parent=""

    for _ in {1..20}; do
        curl -s -u "${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}" \
            "${LANGFUSE_HOST}/api/public/traces/${trace_id}" \
            -o "$lf_file"

        lf_name="$(jq -r '.name // empty' "$lf_file")"
        lf_session="$(jq -r '.sessionId // empty' "$lf_file")"
        lf_input_type="$(jq -r '.input | type' "$lf_file")"
        lf_output_type="$(jq -r '.output | type' "$lf_file")"
        lf_output_empty="$(jq -r '(.output == null) or (.output == "")' "$lf_file")"
        lf_trace_display_severity="$(jq -r '.metadata.trace_display_severity // empty' "$lf_file")"
        lf_flow_span_id="$(jq -r '.observations[]? | select(.metadata.span_role == "skillopt_flow") | .id' "$lf_file" | tail -1)"
        lf_optimization_count="$(jq -r '[.observations[]? | select(.name == "optimization")] | length' "$lf_file")"
        lf_optimization_io_count="$(jq -r '[.observations[]? | select(.name == "optimization" and (.input != null) and (.output != null))] | length' "$lf_file")"
        lf_judgement_level="$(jq -r '.observations[]? | select(.name == "skillopt.trace_judgement") | .level' "$lf_file" | tail -1)"
        lf_judgement_status_message="$(jq -r '.observations[]? | select(.name == "skillopt.trace_judgement") | .statusMessage // empty' "$lf_file" | tail -1)"
        lf_judgement_parent="$(jq -r '.observations[]? | select(.name == "skillopt.trace_judgement") | .parentObservationId // empty' "$lf_file" | tail -1)"

        if [[ "$lf_session" == "$SHARED_SESSION" && "$lf_input_type" == "array" && "$lf_output_empty" == "false" ]]; then
            if [[ "$expected_status" != "failed" || ( "$lf_judgement_level" == "ERROR" && -n "$lf_flow_span_id" && "$lf_judgement_parent" == "$lf_flow_span_id" && "$lf_optimization_count" == "1" && "$lf_optimization_io_count" == "1" ) ]]; then
                break
            fi
        fi
        sleep 1
    done

    if [[ "$lf_session" == "$SHARED_SESSION" ]]; then
        record_pass "${skill}: Langfuse session matches"
    else
        record_fail "${skill}: Langfuse session mismatch"
    fi

    if [[ "$lf_input_type" == "array" ]]; then
        record_pass "${skill}: Langfuse input is array"
    else
        record_fail "${skill}: Langfuse input type=${lf_input_type}"
    fi

    if [[ "$lf_output_empty" == "false" ]]; then
        record_pass "${skill}: Langfuse output is non-empty (${lf_output_type})"
    else
        record_fail "${skill}: Langfuse output is empty"
    fi

    if [[ "$expected_status" == "failed" ]]; then
        if [[ "$lf_trace_display_severity" == "ERROR" ]]; then
            record_pass "${skill}: Langfuse trace metadata trace_display_severity=ERROR"
        else
            record_fail "${skill}: Langfuse trace_display_severity expected=ERROR, actual=${lf_trace_display_severity:-empty}"
        fi

        if [[ -n "$lf_flow_span_id" ]]; then
            record_pass "${skill}: Langfuse flow span exists"
        else
            record_fail "${skill}: Langfuse flow span is missing"
        fi

        if [[ "$lf_optimization_count" == "1" ]]; then
            record_pass "${skill}: Langfuse optimization observation is single"
        else
            record_fail "${skill}: Langfuse optimization observation count expected=1, actual=${lf_optimization_count}"
        fi

        if [[ "$lf_optimization_io_count" == "1" ]]; then
            record_pass "${skill}: Langfuse optimization observation input/output are set"
        else
            record_fail "${skill}: Langfuse optimization observation input/output missing"
        fi

        if [[ "$lf_judgement_level" == "ERROR" ]]; then
            record_pass "${skill}: Langfuse judgement observation level=ERROR"
        else
            record_fail "${skill}: Langfuse judgement observation level expected=ERROR, actual=${lf_judgement_level:-empty}"
        fi

        if [[ -n "$lf_flow_span_id" && "$lf_judgement_parent" == "$lf_flow_span_id" ]]; then
            record_pass "${skill}: Langfuse judgement observation is attached to flow span"
        else
            record_fail "${skill}: Langfuse judgement parent expected=${lf_flow_span_id:-empty}, actual=${lf_judgement_parent:-empty}"
        fi

        if [[ -n "$lf_judgement_status_message" && "$lf_judgement_status_message" != "null" ]]; then
            record_pass "${skill}: Langfuse judgement observation statusMessage is set"
        else
            record_fail "${skill}: Langfuse judgement observation statusMessage is empty"
        fi
    else
        if [[ "$lf_trace_display_severity" != "ERROR" ]]; then
            record_pass "${skill}: Langfuse trace_display_severity is not ERROR for successful trace"
        else
            record_fail "${skill}: Langfuse trace_display_severity unexpectedly ERROR for successful trace"
        fi
    fi

    echo "  Langfuse: ${lf_name}"
    echo
}

require_cmd jq
require_cmd curl
require_cmd bash
require_cmd zsh
require_cmd aliyun

load_env
validate_env

export SKILLOPT_LANGFUSE_ENABLED="true"
export ALIBABA_CLOUD_REGION_ID="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
SHARED_SESSION="sess-gray-skills-it-$(date +%s)"
export SKILLOPT_SESSION_ID="$SHARED_SESSION"

echo "============================================"
echo "  Langfuse 灰度 Skill 集成测试"
echo "  Session: ${SHARED_SESSION}"
echo "  Langfuse: ${LANGFUSE_HOST}"
echo "============================================"
echo

static_check_skill "alicloud-ack-ops" "ack-skillopt-wrapper.sh"
static_check_skill "alicloud-das-ops" "das-skillopt-wrapper.sh"
static_check_skill "alicloud-alb-ops" "alb-skillopt-wrapper.sh"
static_check_skill "alicloud-cen-ops" "cbn-skillopt-wrapper.sh"

run_case "ack" "alicloud-ack-ops" "ack-skillopt-wrapper.sh" "failed" "" \
    DescribeClusters \
    --skillopt-enable \
    --skillopt-langfuse-enable \
    --skillopt-session-id "$SHARED_SESSION"

run_case "das" "alicloud-das-ops" "das-skillopt-wrapper.sh" "failed" "not a valid api" \
    GetEventSubscription \
    --skillopt-enable \
    --skillopt-langfuse-enable \
    --skillopt-session-id "$SHARED_SESSION" \
    --RegionId cn-shanghai

run_case "alb" "alicloud-alb-ops" "alb-skillopt-wrapper.sh" "success" "" \
    ListLoadBalancers \
    --skillopt-enable \
    --skillopt-langfuse-enable \
    --skillopt-session-id "$SHARED_SESSION" \
    --MaxResults 1

run_case "cen" "alicloud-cen-ops" "cbn-skillopt-wrapper.sh" "success" "" \
    DescribeCens \
    --skillopt-enable \
    --skillopt-langfuse-enable \
    --skillopt-session-id "$SHARED_SESSION" \
    --PageSize 1

echo "============================================"
echo "  集成测试结果: PASS=${PASS}, FAIL=${FAIL}, TOTAL=${TOTAL}"
echo "============================================"

if [[ "$FAIL" -ne 0 ]]; then
    exit 1
fi
