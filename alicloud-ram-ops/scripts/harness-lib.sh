#!/bin/bash
# SkillOpt Core Library for alicloud-ram-ops
# Self-repair and dynamic optimization for RAM operations.
# Compatible with macOS (BSD grep/sed) and Linux.

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
SKILLOPT_LOG_LABEL="RAM-SkillOpt"
SKILLOPT_SKILL_TAG="alicloud-ram-ops"

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
SKILLOPT_LOG_FILE="${ALIBABA_CLOUD_LOG_DIR:-${_SKILLOPT_LOGS_DIR:-$_SKILLOPT_RUNTIME_ROOT}}/ram-skillopt-$(date +%Y%m%d).log"
SKILLOPT_RUNTIME_DATA="${_SKILLOPT_METRICS_DATA_DIR:-$_SKILLOPT_RUNTIME_ROOT}/ram-skillopt-runtime.json"
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
        Throttling.User|Throttling)
            skillopt_log "repair[Throttling]: exponential backoff + raise Period"
            local attempt=0
            local new_params=("${params[@]}")

            local has_period=false
            for p in "${new_params[@]}"; do
                [[ "$p" == "--Period" ]] && has_period=true
            done
            $has_period || new_params+=("--Period" "300")

            for sleep_s in "${SKILLOPT_BACKOFF[@]}"; do
                skillopt_log "repair[Throttling]: wait ${sleep_s}s (attempt $((attempt+1)))"
                sleep "$sleep_s"
                if skillopt_run_aliyun "$product" "$action" "${new_params[@]}"; then
                    skillopt_log "repair[Throttling]: succeeded after ${sleep_s}s"
                    repair_failed=0
                    break
                fi
                attempt=$((attempt + 1))
            done
            ;;

        InvalidParameter|InvalidJSON|MissingParameter|MissingParameter.RegionId|InvalidParameter.RegionId|MissingRegionId|DataRetentionExceeded|InvalidTimeRange|TimeRangeExceeded|InvalidParameter.StartTime|InvalidParameter.TimeRange)
            skillopt_log "repair[InvalidParam]: check RegionId, TimeRange, or JSON params"
            local new_params=()
            local skip_next=false
            local modified=false

            # 1. RegionId missing check
            local has_region=false
            for p in "${params[@]}"; do
                [[ "$p" == "--RegionId" ]] && has_region=true
            done

            # 2. TimeRange/DataRetention check
            local is_retention_error=false
            if [[ "$error_code" == "DataRetentionExceeded" || "$error_code" == "InvalidTimeRange" || "$error_code" == "TimeRangeExceeded" || "$error_code" == "InvalidParameter.StartTime" || "$error_code" == "InvalidParameter.TimeRange" ]]; then
                is_retention_error=true
            elif [[ "$SKILLOPT_LAST_OUTPUT" == *"retention"* || "$SKILLOPT_LAST_OUTPUT" == *"31 days"* || "$SKILLOPT_LAST_OUTPUT" == *"30 days"* || "$SKILLOPT_LAST_OUTPUT" == *"exceed"* ]]; then
                for p in "${params[@]}"; do
                    [[ "$p" == "--StartTime" ]] && is_retention_error=true
                done
            fi

            local is_region_error=false
            if [[ "$error_code" == "MissingParameter.RegionId" || "$error_code" == "InvalidParameter.RegionId" || "$error_code" == "MissingRegionId" ]]; then
                is_region_error=true
            elif [[ "$error_code" == "MissingParameter" ]] && ! $has_region; then
                is_region_error=true
            fi

            if $is_region_error; then
                skillopt_log "repair[RegionId]: RegionId is missing, attempting auto-completion"
                local region="${ALIBABA_CLOUD_REGION_ID:-}"
                if [[ -z "$region" ]]; then
                    region="$(aliyun ecs DescribeRegions --output cols=RegionId rows=Regions.Region 2>/dev/null | head -n 1 | tr -d ' \r\n' || true)"
                fi
                if [[ -z "$region" ]]; then
                    region="cn-hangzhou"
                fi
                skillopt_log "repair[RegionId]: using region $region"
                new_params=("${params[@]}" "--RegionId" "$region")
                modified=true
            elif $is_retention_error; then
                skillopt_log "repair[TimeRange]: Data retention exceeded, shrinking StartTime to 14 days ago"
                skillopt_get_14_days_ago() {
                    local format_type="$1"
                    local now_s
                    now_s="$(date +%s)"
                    local fourteen_days_ago_s=$((now_s - 14 * 86400))
                    if [[ "$format_type" == "ms" ]]; then
                        echo "$((fourteen_days_ago_s * 1000))"
                    elif [[ "$format_type" == "s" ]]; then
                        echo "$fourteen_days_ago_s"
                    else
                        if command -v python3 &>/dev/null; then
                            python3 -c "import datetime; print((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14)).strftime('%Y-%m-%dT%H:%M:%SZ'))"
                        else
                            date -u -d '14 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-14d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "2026-06-02T00:00:00Z"
                        fi
                    fi
                }

                for ((i=0; i<${#params[@]}; i++)); do
                    local arg="${params[$i]}"
                    if $skip_next; then
                        skip_next=false
                        continue
                    fi
                    if [[ "$arg" == "--StartTime" && $((i+1)) -lt ${#params[@]} ]]; then
                        local val="${params[$((i+1))]}"
                        local new_val=""
                        if [[ "$val" =~ ^[0-9]+$ ]]; then
                            if [[ ${#val} -ge 12 ]]; then
                                new_val="$(skillopt_get_14_days_ago "ms")"
                            else
                                new_val="$(skillopt_get_14_days_ago "s")"
                            fi
                        else
                            new_val="$(skillopt_get_14_days_ago "string")"
                        fi
                        new_params+=("--StartTime" "$new_val")
                        skip_next=true
                        modified=true
                        skillopt_log "repair[TimeRange]: adjusted StartTime from $val to $new_val"
                    else
                        new_params+=("$arg")
                    fi
                done
            else
                # Fallback to JSON parameter validation
                local jp=()
                for ((i=0; i<${#params[@]}; i++)); do
                    local arg="${params[$i]}"
                    if $skip_next; then
                        skip_next=false
                        continue
                    fi
                    
                    local is_json_param=false
                    for p in "${jp[@]}"; do
                        if [[ "$arg" == "--$p" ]]; then
                            is_json_param=true
                            break
                        fi
                    done

                    if $is_json_param && [[ $((i+1)) -lt ${#params[@]} ]]; then
                        local raw_val="${params[$((i+1))]}"
                        local fixed_val
                        fixed_val="$(printf '%s' "$raw_val" | jq -c '.' 2>/dev/null || echo "$raw_val")"
                        if [[ "$raw_val" != "$fixed_val" ]]; then
                            new_params+=("$arg" "$fixed_val")
                            modified=true
                        else
                            new_params+=("$arg" "$raw_val")
                        fi
                        skip_next=true
                    else
                        new_params+=("$arg")
                    fi
                done
            fi

            if $modified; then
                skillopt_log "repair[InvalidParam]: retrying with modified params"
                if skillopt_run_aliyun "$product" "$action" "${new_params[@]}"; then
                    skillopt_log "repair[InvalidParam]: succeeded"
                    repair_failed=0
                fi
            else
                skillopt_log "repair[InvalidParam]: no modifications applied"
            fi
            ;;

        ResourceNotFound)
            skillopt_log "repair[ResourceNotFound]: verify resource existence"
            local instance_id=""
            for ((i=0; i<${#params[@]}; i++)); do
                if [[ "${params[$i]}" == "--Dimensions" && $((i+1)) -lt ${#params[@]} ]]; then
                    instance_id="$(printf '%s' "${params[$((i+1))]}" | jq -r '.[0].instanceId // empty' 2>/dev/null)"
                    break
                fi
            done
            local region="${ALIBABA_CLOUD_REGION_ID:-}"
            for ((i=0; i<${#params[@]}; i++)); do
                [[ "${params[$i]}" == "--RegionId" ]] && region="${params[$((i+1))]}" && break
            done

            if [[ -n "$instance_id" && -n "$region" ]]; then
                skillopt_log "repair[ResourceNotFound]: checking $instance_id in $region"
                local check_cmd=""
                if [[ "$instance_id" =~ ^i- ]]; then
                    check_cmd="aliyun ecs DescribeInstances --RegionId $region --InstanceIds [\"$instance_id\"]"
                elif [[ "$instance_id" =~ ^rm- ]]; then
                    check_cmd="aliyun rds DescribeDBInstances --RegionId $region --DBInstanceId $instance_id"
                elif [[ "$instance_id" =~ ^r- ]]; then
                    check_cmd="aliyun r-kvstore DescribeInstances --RegionId $region --InstanceIds $instance_id"
                elif [[ "$instance_id" =~ ^lb- ]]; then
                    check_cmd="aliyun slb DescribeLoadBalancers --RegionId $region --LoadBalancerId $instance_id"
                elif [[ "$instance_id" =~ ^dds- ]]; then
                    check_cmd="aliyun dds DescribeDBInstances --RegionId $region --DBInstanceId $instance_id"
                elif [[ "$instance_id" =~ ^pc- ]]; then
                    check_cmd="aliyun polardb DescribeDBClusters --RegionId $region --DBClusterId $instance_id"
                elif [[ "$instance_id" =~ ^eip- ]]; then
                    check_cmd="aliyun vpc DescribeEipAddresses --RegionId $region --AllocationId $instance_id"
                elif [[ "$instance_id" =~ ^vpc- ]]; then
                    check_cmd="aliyun vpc DescribeVpcs --RegionId $region --VpcId $instance_id"
                fi

                local exists=false
                if [[ -n "$check_cmd" ]]; then
                    skillopt_log "repair[ResourceNotFound]: executing probe: $check_cmd"
                    if eval "$check_cmd" >/dev/null 2>&1; then
                        exists=true
                    fi
                else
                    # Fallback for generic/unrecognized instance prefixes: assume true and retry
                    exists=true
                fi

                if $exists; then
                    skillopt_log "repair[ResourceNotFound]: resource exists, retrying"
                    if skillopt_run_aliyun "$product" "$action" "${params[@]}"; then
                        repair_failed=0
                    fi
                else
                    skillopt_log "repair[ResourceNotFound]: resource $instance_id not found in $region"
                fi
            else
                skillopt_log "repair[ResourceNotFound]: cannot extract instanceId/region, skipping"
            fi
            ;;

        Forbidden|NoPermission)
            skillopt_log "repair[Forbidden]: RAM policy suggestion"
            skillopt_log "HINT: Ensure AK has policy: {\"Action\":[\"ecs:*\"],\"Effect\":\"Allow\",\"Resource\":\"*\"}"
            ;;

        ConnectionTimeout|ConnectTimeout)
            skillopt_log "repair[Timeout]: retrying with increased timeout"
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

        QuotaExceeded)
            skillopt_log "Quota exceeded for ECS"
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

    if awk "BEGIN { exit !($query_count > 1000) }" 2>/dev/null; then
        local has_period=false
        for p in "${SKILLOPT_PARAMS[@]+"${SKILLOPT_PARAMS[@]}"}"; do
            [[ "$p" == "--Period" ]] && has_period=true
        done
        if ! $has_period; then
            SKILLOPT_PARAMS+=("--Period" "300")
            skillopt_log "optimize: high query_count=${query_count} → added --Period 300"
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
