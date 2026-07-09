#!/bin/bash
# SkillOpt Core Library for alicloud-advisor-ops
# Self-repair and dynamic optimization for Advisor CLI commands.
# Compatible with macOS (BSD grep/sed) and Linux.

_SKILLOPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SKILLOPT_SKILL_ROOT="$(dirname "$_SKILLOPT_LIB_DIR")"

# SKILLOPT_ENABLED resolved in skillopt_init (env / .env / flags)
SKILLOPT_REPORT=false
SKILLOPT_RETRIES=3
SKILLOPT_BACKOFF=(1 2 4)
SKILLOPT_LAST_OUTPUT=""
# Working parameter array — mutated in-place by skillopt_optimize_params.
SKILLOPT_PARAMS=()

# Circuit breaker configuration
SKILLOPT_CB_ENABLED=false
SKILLOPT_CB_THRESHOLD=5       # consecutive failures to trip
SKILLOPT_CB_COOLDOWN=60       # seconds before half-open probe

# Observability configuration
SKILLOPT_LOG_FORMAT="${SKILLOPT_LOG_FORMAT:-text}"  # text | json
SKILLOPT_METRICS_DIR="${SKILLOPT_METRICS_DIR:-}"    # empty = no export
SKILLOPT_LOG_LABEL="Advisor-SkillOpt"
SKILLOPT_SKILL_TAG="alicloud-advisor-ops"

# Langfuse tracing configuration
SKILLOPT_LANGFUSE_ENABLED="${SKILLOPT_LANGFUSE_ENABLED:-false}"
LANGFUSE_HOST="${LANGFUSE_HOST:-}"
LANGFUSE_PUBLIC_KEY="${LANGFUSE_PUBLIC_KEY:-}"
LANGFUSE_SECRET_KEY="${LANGFUSE_SECRET_KEY:-}"

# Session & Trace state
SKILLOPT_SESSION_ID="${SKILLOPT_SESSION_ID:-}"


# --- Shared SkillOpt core (alicloud-skillopt-ops) ---
if [[ -z "${_SKILLOPT_SKILLS_ROOT:-}" ]]; then
    _SKILLOPT_SKILLS_ROOT="${ALIYUN_SKILLS_ROOT:-$(git -C "$_SKILLOPT_SKILL_ROOT" rev-parse --show-toplevel 2>/dev/null || dirname "$_SKILLOPT_SKILL_ROOT")}"
fi
_SKILLOPT_SHARED_ROOT="${SKILLOPT_SHARED_ROOT:-${_SKILLOPT_SKILLS_ROOT}/alicloud-skillopt-ops}"
# shellcheck source=/dev/null
source "${_SKILLOPT_SHARED_ROOT}/scripts/skillopt-paths.sh"
# shellcheck source=/dev/null
source "${_SKILLOPT_SHARED_ROOT}/scripts/skillopt-core-lib.sh"
SKILLOPT_LOG_FILE="${ALIBABA_CLOUD_LOG_DIR:-${_SKILLOPT_LOGS_DIR:-$_SKILLOPT_RUNTIME_ROOT}}/advisor-skillopt-$(date +%Y%m%d).log"
SKILLOPT_RUNTIME_DATA="${_SKILLOPT_METRICS_DATA_DIR:-$_SKILLOPT_RUNTIME_ROOT}/advisor-skillopt-runtime.json"
# --- End shared core ---

skillopt_repair_error() {
    local error_code="$1"; shift
    local product="$1";    shift
    local action="$1";     shift
    local params=("$@")

    if [[ "$SKILLOPT_ENABLED" != "true" ]]; then
        skillopt_log "repair skipped (disabled): $error_code"
        return 1
    fi

    if ! skillopt_is_readonly_action "$action"; then
        skillopt_log "repair skipped (mutating action): $product $action"
        return 1
    fi

    skillopt_log "repair start: error=$error_code cmd=$product $action"
    local repair_failed=1

    case "$error_code" in
        UnknownProduct|PluginNotInstalled)
            skillopt_log "repair[Plugin]: Advisor plugin missing, attempting install"
            if aliyun plugin install --names aliyun-cli-advisor 2>/dev/null; then
                skillopt_log "repair[Plugin]: plugin installed successfully, retrying command"
                if skillopt_run_aliyun "$product" "$action" "${params[@]}"; then
                    repair_failed=0
                fi
            else
                skillopt_log "repair[Plugin]: plugin installation failed — run 'aliyun plugin install --names aliyun-cli-advisor' manually"
            fi
            ;;

        Throttling.User|Throttling)
            skillopt_log "repair[Throttling]: exponential backoff"
            local attempt=0

            for sleep_s in "${SKILLOPT_BACKOFF[@]}"; do
                skillopt_log "repair[Throttling]: wait ${sleep_s}s (attempt $((attempt+1)))"
                sleep "$sleep_s"
                if skillopt_run_aliyun "$product" "$action" "${params[@]}"; then
                    skillopt_log "repair[Throttling]: succeeded after ${sleep_s}s"
                    repair_failed=0
                    break
                fi
                attempt=$((attempt + 1))
            done
            ;;

        InvalidParameter|MissingParameter)
            skillopt_log "repair[InvalidParam]: checking common Advisor parameter issues"
            local new_params=()
            local skip_next=false
            local modified=false

            # Advisor is region-agnostic — drop --RegionId if present
            for ((i=0; i<${#params[@]}; i++)); do
                local arg="${params[$i]}"
                if $skip_next; then
                    skip_next=false
                    continue
                fi
                if [[ "$arg" == "--RegionId" ]]; then
                    skip_next=true
                    modified=true
                    skillopt_log "repair[InvalidParam]: stripping --RegionId (Advisor is region-agnostic)"
                elif [[ "$arg" == "--biz-language" && "$error_code" == "InvalidParameter" ]]; then
                    # --biz-language zh/en might cause issues for some API versions
                    skip_next=true
                    modified=true
                    skillopt_log "repair[InvalidParam]: stripping --biz-language"
                else
                    new_params+=("$arg")
                fi
            done

            if $modified; then
                skillopt_log "repair[InvalidParam]: retrying with stripped params"
                if skillopt_run_aliyun "$product" "$action" "${new_params[@]}"; then
                    skillopt_log "repair[InvalidParam]: succeeded"
                    repair_failed=0
                fi
            else
                skillopt_log "repair[InvalidParam]: no common fix applicable"
            fi
            ;;

        Forbidden|NoPermission)
            skillopt_log "repair[Forbidden]: RAM policy suggestion"
            skillopt_log "HINT: Ensure AK has policy: {\"Action\":[\"advisor:*\"],\"Effect\":\"Allow\",\"Resource\":\"*\"}"
            skillopt_log "HINT: For read-only: {\"Action\":[\"advisor:Describe*\",\"advisor:Get*\"],\"Effect\":\"Allow\",\"Resource\":\"*\"}"
            ;;

        QuotaExceeded)
            skillopt_log "repair[QuotaExceeded]: daily inspection quota exceeded or API quota exhausted"
            skillopt_log "HINT: Wait until next day or upgrade your Advisor plan"
            ;;

        TaskNotFound)
            skillopt_log "repair[TaskNotFound]: task ID may have expired or is invalid"
            skillopt_log "HINT: Re-trigger with RefreshAdvisorCheck to get a new TaskId"
            ;;

        InspectFailed)
            skillopt_log "repair[InspectFailed]: inspection task failed server-side, retrying once"
            sleep 10
            if skillopt_run_aliyun "$product" "$action" "${params[@]}"; then
                skillopt_log "repair[InspectFailed]: retry succeeded"
                repair_failed=0
            else
                skillopt_log "repair[InspectFailed]: retry also failed — report to user"
            fi
            ;;

        ServiceUnavailable)
            skillopt_log "repair[ServiceUnavailable]: service temporarily unavailable, retrying"
            local attempt=0
            for sleep_s in "${SKILLOPT_BACKOFF[@]}"; do
                skillopt_log "repair[ServiceUnavailable]: wait ${sleep_s}s (attempt $((attempt+1)))"
                sleep "$sleep_s"
                if skillopt_run_aliyun "$product" "$action" "${params[@]}"; then
                    skillopt_log "repair[ServiceUnavailable]: succeeded after ${sleep_s}s"
                    repair_failed=0
                    break
                fi
                attempt=$((attempt + 1))
            done
            ;;

        InternalError)
            skillopt_log "repair[InternalError]: server-side error, retrying with backoff"
            local attempt=0
            for sleep_s in "${SKILLOPT_BACKOFF[@]}"; do
                skillopt_log "repair[InternalError]: wait ${sleep_s}s (attempt $((attempt+1)))"
                sleep "$sleep_s"
                if skillopt_run_aliyun "$product" "$action" "${params[@]}"; then
                    skillopt_log "repair[InternalError]: succeeded after ${sleep_s}s"
                    repair_failed=0
                    break
                fi
                if (( attempt >= 1 )); then
                    skillopt_log "repair[InternalError]: max retries reached, giving up"
                    break
                fi
                attempt=$((attempt + 1))
            done
            ;;

        *)
            skillopt_log "repair: no handler for $error_code"
            ;;
    esac

    skillopt_update_runtime "$error_code" "$repair_failed"

    if [[ $repair_failed -eq 0 ]]; then
        printf '%s\n' "$SKILLOPT_LAST_OUTPUT"
    fi

    return $repair_failed
}

skillopt_optimize_params() {
    local product="$1"
    local action="$2"

    if [[ "$SKILLOPT_ENABLED" != "true" ]]; then
        return 0
    fi

    skillopt_log "optimize: $product $action (${#SKILLOPT_PARAMS[@]} params)"

    local runtime_data='{}'
    [[ -f "$SKILLOPT_RUNTIME_DATA" ]] && \
        runtime_data="$(jq '.' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null || echo '{}')"

    local error_rate query_count
    error_rate="$(printf '%s' "$runtime_data" | jq -r '.error_rate // 0')"
    query_count="$(printf '%s' "$runtime_data" | jq -r '.query_count // 0')"

    if awk "BEGIN { exit !($error_rate > 5) }" 2>/dev/null; then
        if [[ $SKILLOPT_RETRIES -lt 6 ]]; then
            SKILLOPT_RETRIES=$((SKILLOPT_RETRIES + 1))
            skillopt_log "optimize: error_rate=${error_rate}% → retries=$SKILLOPT_RETRIES"
        else
            skillopt_log "optimize: error_rate=${error_rate}% (retries capped at $SKILLOPT_RETRIES)"
        fi
    fi

    # Advisor has no --Period parameter; optimization is primarily retry tuning
    if awk "BEGIN { exit !($query_count > 500) }" 2>/dev/null; then
        skillopt_log "optimize: query_count=${query_count} — consider using paginated APIs (DescribeAdvicesPage) for large result sets"
    fi
}


skillopt_check_and_poll_empty() {
    local product="$1"
    local action="$2"
    local output="$3"
    shift 3
    local params=("$@")

    if [[ "$SKILLOPT_ENABLED" != "true" ]]; then
        return 0
    fi

    if ! skillopt_is_readonly_action "$action"; then
        return 0
    fi

    local has_filter=false
    for p in "${params[@]+"${params[@]}"}"; do
        if [[ "$p" == "--advice-id" || "$p" == "--check-id" || "$p" == "--product" || "$p" == "--resource-id" ]]; then
            has_filter=true
            break
        fi
    done

    if ! $has_filter; then
        return 0
    fi

    local is_empty=false
    if printf '%s' "$output" | jq -e '(.Advices == null or .Advices == []) or (.Data == null or .Data == [])' >/dev/null 2>&1; then
        is_empty=true
    fi

    if ! $is_empty; then
        return 0
    fi

    skillopt_log "check_and_poll_empty: output is empty with active filter, possible propagation delay. Polling..."
    local poll_backoffs=(10 20 30)
    local attempt=1
    local poll_success=false

    for sleep_s in "${poll_backoffs[@]}"; do
        skillopt_log "check_and_poll_empty: wait ${sleep_s}s before poll attempt $attempt"
        sleep "$sleep_s"

        if skillopt_run_aliyun "$product" "$action" "${params[@]}"; then
            local poll_out="$SKILLOPT_LAST_OUTPUT"
            if ! printf '%s' "$poll_out" | jq -e '(.Advices == null or .Advices == []) or (.Data == null or .Data == [])' >/dev/null 2>&1; then
                skillopt_log "check_and_poll_empty: propagation succeeded on attempt $attempt"
                poll_success=true
                break
            fi
        else
            skillopt_log "check_and_poll_empty: poll attempt $attempt failed with CLI error"
        fi
        attempt=$((attempt + 1))
    done

    if $poll_success; then
        return 0
    else
        skillopt_log "check_and_poll_empty: polling timed out, returning empty result"
        SKILLOPT_LAST_OUTPUT="$output"
        return 0
    fi
}

# 导出函数供子进程使用（仅 bash 支持）
if [ -n "$BASH_VERSION" ]; then
    export -f skillopt_init skillopt_log skillopt_is_readonly_action \
              skillopt_extract_error_code skillopt_run_aliyun skillopt_repair_error \
              skillopt_update_runtime skillopt_optimize_params \
              skillopt_check_and_poll_empty skillopt_export_metrics \
              skillopt_cb_check skillopt_cb_record_failure skillopt_cb_record_success \
              skillopt_cb_reset \
              skillopt_session_init skillopt_trace_start skillopt_trace_span \
              skillopt_trace_span_io skillopt_trace_end
fi
