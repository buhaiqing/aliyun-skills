#!/bin/bash
# SkillOpt Core Library for alicloud-dns-ops
# Self-repair and dynamic optimization for Alibaba Cloud DNS CLI commands
# (alidns / pvtz). Compatible with macOS (BSD grep/sed) and Linux.

_SKILLOPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SKILLOPT_SKILL_ROOT="$(dirname "$_SKILLOPT_LIB_DIR")"

# SKILLOPT_ENABLED resolved in skillopt_init (env / .env / flags)
SKILLOPT_REPORT=false
SKILLOPT_RETRIES=3
SKILLOPT_BACKOFF=(1 2 4)
SKILLOPT_LAST_OUTPUT=""
SKILLOPT_PARAMS=()

# 熔断器配置
SKILLOPT_CB_ENABLED=false
SKILLOPT_CB_THRESHOLD=5
SKILLOPT_CB_COOLDOWN=60

# Observability configuration
SKILLOPT_LOG_FORMAT="${SKILLOPT_LOG_FORMAT:-text}"  # text | json
SKILLOPT_METRICS_DIR="${SKILLOPT_METRICS_DIR:-}"    # empty = no export
SKILLOPT_LOG_LABEL="DNS-SkillOpt"
SKILLOPT_SKILL_TAG="alicloud-dns-ops"

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
SKILLOPT_LOG_FILE="${ALIBABA_CLOUD_LOG_DIR:-${_SKILLOPT_LOGS_DIR:-$_SKILLOPT_RUNTIME_ROOT}}/dns-skillopt-$(date +%Y%m%d).log"
SKILLOPT_RUNTIME_DATA="${_SKILLOPT_METRICS_DATA_DIR:-$_SKILLOPT_RUNTIME_ROOT}/dns-skillopt-runtime.json"
# --- End shared core ---

# DNS-specific self-repair override (alidns / pvtz).
# Read-only actions only; mutating actions are never auto-repaired.
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
        Throttling.User|Throttling)
            skillopt_log "repair[Throttling]: exponential backoff"
            for sleep_s in "${SKILLOPT_BACKOFF[@]}"; do
                skillopt_log "repair[Throttling]: wait ${sleep_s}s (attempt)"
                sleep "$sleep_s"
                if skillopt_run_aliyun "$product" "$action" "${params[@]}"; then
                    skillopt_log "repair[Throttling]: succeeded"
                    repair_failed=0
                    break
                fi
            done
            ;;

        ConnectionTimeout|ConnectTimeout)
            skillopt_log "repair[Timeout]: retry with --Timeout 30"
            local new_params=("${params[@]}")
            local has_timeout=false
            for p in "${new_params[@]}"; do
                [[ "$p" == "--Timeout" ]] && has_timeout=true
            done
            $has_timeout || new_params+=("--Timeout" "30")
            if skillopt_run_aliyun "$product" "$action" "${new_params[@]}"; then
                repair_failed=0
            fi
            ;;

        InvalidParameter|InvalidParameterValue|MissingParameter|InvalidDomainName|InvalidRecordType)
            skillopt_log "repair[InvalidParam]: verify RegionId / domain name / record type"
            local new_params=("${params[@]}")
            local has_region=false
            for p in "${new_params[@]}"; do
                [[ "$p" == "--RegionId" ]] && has_region=true
            done
            if ! $has_region; then
                local region="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
                skillopt_log "repair[InvalidParam]: injecting RegionId=$region"
                new_params+=("--RegionId" "$region")
                if skillopt_run_aliyun "$product" "$action" "${new_params[@]}"; then
                    repair_failed=0
                fi
            fi
            ;;

        DomainNotFound|RecordNotFound|ZoneNotFound|ResourceNotFound)
            skillopt_log "repair[NotFound]: DNS resource missing — HALT, verify domain/record/zone exists"
            ;;

        Forbidden|NoPermission)
            skillopt_log "repair[Forbidden]: RAM hint: ensure AK has alidns:* / pvtz:* permissions"
            ;;

        QuotaExceeded)
            skillopt_log "repair[QuotaExceeded]: DNS quota reached — delete unused records or upgrade edition"
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
}


if [ -n "$BASH_VERSION" ]; then
    export -f skillopt_init skillopt_log skillopt_is_readonly_action \
              skillopt_extract_error_code skillopt_run_aliyun skillopt_repair_error \
              skillopt_update_runtime skillopt_optimize_params \
              skillopt_cb_reset skillopt_session_init skillopt_trace_start skillopt_trace_span \
              skillopt_trace_span_io skillopt_trace_end
fi
