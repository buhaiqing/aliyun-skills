#!/bin/bash
# SkillOpt overlay for alicloud-gcl-runner-ops
# Routes execution to scripts/gcl_runner.py (Python) instead of aliyun CLI.
# Observability: Langfuse tracing, metrics, circuit breaker via shared core.

_SKILLOPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SKILLOPT_SKILL_ROOT="$(dirname "$_SKILLOPT_LIB_DIR")"

SKILLOPT_REPORT=false
SKILLOPT_RETRIES=3
SKILLOPT_BACKOFF=(1 2 4)
SKILLOPT_LAST_OUTPUT=""
SKILLOPT_PARAMS=()

SKILLOPT_CB_ENABLED=false
SKILLOPT_CB_THRESHOLD=5
SKILLOPT_CB_COOLDOWN=60

SKILLOPT_LOG_FORMAT="${SKILLOPT_LOG_FORMAT:-text}"
SKILLOPT_METRICS_DIR="${SKILLOPT_METRICS_DIR:-}"
SKILLOPT_LOG_LABEL="GCL-Runner-SkillOpt"
SKILLOPT_SKILL_TAG="alicloud-gcl-runner-ops"

SKILLOPT_LANGFUSE_ENABLED="${SKILLOPT_LANGFUSE_ENABLED:-false}"
LANGFUSE_HOST="${LANGFUSE_HOST:-}"
LANGFUSE_PUBLIC_KEY="${LANGFUSE_PUBLIC_KEY:-}"
LANGFUSE_SECRET_KEY="${LANGFUSE_SECRET_KEY:-}"

SKILLOPT_SESSION_ID="${SKILLOPT_SESSION_ID:-}"

if [[ -z "${_SKILLOPT_SKILLS_ROOT:-}" ]]; then
    _SKILLOPT_SKILLS_ROOT="${ALIYUN_SKILLS_ROOT:-$(git -C "$_SKILLOPT_SKILL_ROOT" rev-parse --show-toplevel 2>/dev/null || dirname "$_SKILLOPT_SKILL_ROOT")}"
fi
_SKILLOPT_SHARED_ROOT="${SKILLOPT_SHARED_ROOT:-${_SKILLOPT_SKILLS_ROOT}/alicloud-skillopt-ops}"
# shellcheck source=/dev/null
source "${_SKILLOPT_SHARED_ROOT}/scripts/skillopt-paths.sh"
# shellcheck source=/dev/null
source "${_SKILLOPT_SHARED_ROOT}/scripts/skillopt-core-lib.sh"
SKILLOPT_LOG_FILE="${ALIBABA_CLOUD_LOG_DIR:-${_SKILLOPT_LOGS_DIR:-$_SKILLOPT_RUNTIME_ROOT}}/gcl-runner-skillopt-$(date +%Y%m%d).log"
SKILLOPT_RUNTIME_DATA="${_SKILLOPT_METRICS_DATA_DIR:-$_SKILLOPT_RUNTIME_ROOT}/gcl-runner-skillopt-runtime.json"

# Override: run gcl_runner.py instead of aliyun for product gcl-runner.
skillopt_run_aliyun() {
    local product="$1"; shift
    local action="$1"; shift
    local tmp_out
    tmp_out="$(mktemp "${TMPDIR:-/tmp}/skillopt-out.XXXXXX")"

    local err_state
    if [[ -o errexit ]]; then err_state="set -e"; else err_state="set +e"; fi
    set +e
    if [[ "$product" == "gcl-runner" ]]; then
        local skills_root="${ALIYUN_SKILLS_ROOT:-${_SKILLOPT_SKILLS_ROOT:-}}"
        if [[ -n "$skills_root" ]]; then
            ALIYUN_SKILLS_ROOT="$skills_root" python3 "${_SKILLOPT_LIB_DIR}/gcl_runner.py" "$@" >"$tmp_out" 2>&1
        else
            python3 "${_SKILLOPT_LIB_DIR}/gcl_runner.py" "$@" >"$tmp_out" 2>&1
        fi
    else
        aliyun "$product" "$action" "$@" >"$tmp_out" 2>&1
    fi
    local rc=$?
    $err_state
    SKILLOPT_LAST_OUTPUT="$(cat "$tmp_out")"
    rm -f "$tmp_out"
    return $rc
}

skillopt_repair_error() {
    local error_code="$1"; shift
    local product="$1"; shift
    local action="$1"; shift
    local params=("$@")

    if [[ "$SKILLOPT_ENABLED" != "true" ]]; then
        skillopt_log "repair skipped (disabled): $error_code"
        return 1
    fi

    if [[ "$product" != "gcl-runner" ]]; then
        skillopt_log "repair skipped (non-gcl product): $product"
        return 1
    fi

    skillopt_log "repair start: error=$error_code gcl_runner run"
    local repair_failed=1

    case "$error_code" in
        RUBRIC_MISSING|PRE_FLIGHT_FAIL|SpecCompliance)
            skillopt_log "repair[Rubric]: verify references/rubric.md exists for --skill"
            skillopt_log "HINT: ensure ALIYUN_SKILLS_ROOT points at repo root with rubric.md"
            ;;
        MAX_ITER|max_iter)
            local new_params=("${params[@]}")
            local has_max=false max_val=2 i=0
            while [[ $i -lt ${#new_params[@]} ]]; do
                if [[ "${new_params[$i]}" == "--max-iter" && $((i + 1)) -lt ${#new_params[@]} ]]; then
                    has_max=true
                    max_val="${new_params[$((i + 1))]}"
                    if [[ "$max_val" =~ ^[0-9]+$ ]] && [[ "$max_val" -lt 6 ]]; then
                        new_params[$((i + 1))]=$((max_val + 1))
                        skillopt_log "repair[MAX_ITER]: raised --max-iter from $max_val to $((max_val + 1))"
                        if skillopt_run_aliyun "$product" "$action" "${new_params[@]}"; then
                            repair_failed=0
                        fi
                    fi
                    break
                fi
                i=$((i + 1))
            done
            if ! $has_max; then
                skillopt_log "repair[MAX_ITER]: retry with --max-iter 3"
                if skillopt_run_aliyun "$product" "$action" "${params[@]}" --max-iter 3; then
                    repair_failed=0
                fi
            fi
            ;;
        *)
            skillopt_log "repair: no GCL handler for $error_code (mutating subprocess not retried)"
            ;;
    esac

    skillopt_update_runtime "$error_code" "$repair_failed"
    return "$repair_failed"
}

skillopt_optimize_params() {
    local product="$1"
    local action="$2"
    [[ "$product" == "gcl-runner" ]] || return 0

    skillopt_log "optimize: gcl_runner (${#SKILLOPT_PARAMS[@]} args)"

    if [[ ! -f "$SKILLOPT_RUNTIME_DATA" ]]; then
        return 0
    fi

    local error_rate
    error_rate="$(jq -r '.error_rate // 0' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null || echo "0")"
    if awk -v r="$error_rate" 'BEGIN { exit (r > 30) ? 0 : 1 }'; then
        local i=0 bumped=false
        while [[ $i -lt ${#SKILLOPT_PARAMS[@]} ]]; do
            if [[ "${SKILLOPT_PARAMS[$i]}" == "--max-iter" && $((i + 1)) -lt ${#SKILLOPT_PARAMS[@]} ]]; then
                local cur="${SKILLOPT_PARAMS[$((i + 1))]}"
                if [[ "$cur" =~ ^[0-9]+$ ]] && [[ "$cur" -lt 6 ]]; then
                    SKILLOPT_PARAMS[$((i + 1))]=$((cur + 1))
                    skillopt_log "optimize: error_rate=${error_rate}% → --max-iter $cur → $((cur + 1))"
                    bumped=true
                fi
                break
            fi
            i=$((i + 1))
        done
        if ! $bumped; then
            skillopt_log "optimize: error_rate=${error_rate}% (no --max-iter to tune)"
        fi
    fi
}

if [[ -n "${BASH_VERSION:-}" ]]; then
    export -f skillopt_init skillopt_log skillopt_is_readonly_action \
              skillopt_extract_error_code skillopt_run_aliyun skillopt_repair_error \
              skillopt_update_runtime skillopt_optimize_params skillopt_export_metrics \
              skillopt_cb_check skillopt_cb_record_failure skillopt_cb_record_success \
              skillopt_cb_reset \
              skillopt_session_init skillopt_trace_start skillopt_trace_span \
              skillopt_trace_span_io skillopt_trace_end skillopt_wrap skillopt_report
fi
