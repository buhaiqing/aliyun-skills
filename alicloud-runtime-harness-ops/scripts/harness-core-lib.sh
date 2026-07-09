#!/bin/bash
# Runtime Harness shared core library — alicloud-runtime-harness-ops
# Sourced by per-product scripts/skillopt-lib.sh (legacy) or harness-lib.sh overlays.
# Requires: _SKILLOPT_SKILL_ROOT, SKILLOPT_SKILL_TAG, SKILLOPT_LOG_LABEL (optional)

: "${_SKILLOPT_SKILL_ROOT:?set _SKILLOPT_SKILL_ROOT before sourcing harness-core-lib.sh}"
: "${SKILLOPT_SKILL_TAG:?set SKILLOPT_SKILL_TAG before sourcing harness-core-lib.sh}"

if [[ -z "${_SKILLOPT_RUNTIME_PY:-}" ]]; then
    echo "ERROR: source harness-paths.sh (or legacy skillopt-paths.sh) before harness-core-lib.sh" >&2
    return 1 2>/dev/null || exit 1
fi

: "${_SKILLOPT_RUNTIME_ROOT:?source harness-paths.sh before harness-core-lib.sh}"
: "${_SKILLOPT_TRACE_DIR:?harness-paths.sh must set _SKILLOPT_TRACE_DIR}"

SKILLOPT_SESSION_ID="${SKILLOPT_SESSION_ID:-}"
SKILLOPT_CURRENT_TRACE_ID="${SKILLOPT_CURRENT_TRACE_ID:-}"
SKILLOPT_CURRENT_FLOW_SPAN_ID="${SKILLOPT_CURRENT_FLOW_SPAN_ID:-}"
SKILLOPT_CURRENT_FLOW_SPAN_NAME="${SKILLOPT_CURRENT_FLOW_SPAN_NAME:-}"
SKILLOPT_TRACE_START_TIME="${SKILLOPT_TRACE_START_TIME:-}"
SKILLOPT_LANGFUSE_APP="${SKILLOPT_LANGFUSE_APP:-aliyun-skills}"

# PR-7: HARNESS_* canonical user-facing env; SKILLOPT_* legacy compat (HARNESS wins when set).
_skillopt_harness_merge_env() {
    # Ignore mirror values from a prior skillopt_init unless the user changed HARNESS_* since then.
    if [[ -n "${_SKILLOPT_HARNESS_MIRROR_ENABLED+x}" && "${HARNESS_ENABLED:-}" == "${_SKILLOPT_HARNESS_MIRROR_ENABLED}" ]]; then
        unset HARNESS_ENABLED
    fi
    if [[ -n "${_SKILLOPT_HARNESS_MIRROR_LANGFUSE+x}" && "${HARNESS_LANGFUSE_ENABLED:-}" == "${_SKILLOPT_HARNESS_MIRROR_LANGFUSE}" ]]; then
        unset HARNESS_LANGFUSE_ENABLED
    fi
    if [[ -n "${_SKILLOPT_HARNESS_MIRROR_SESSION+x}" && "${HARNESS_SESSION_ID:-}" == "${_SKILLOPT_HARNESS_MIRROR_SESSION}" ]]; then
        unset HARNESS_SESSION_ID
    fi
    unset _SKILLOPT_HARNESS_MIRROR_ENABLED _SKILLOPT_HARNESS_MIRROR_LANGFUSE _SKILLOPT_HARNESS_MIRROR_SESSION

    if [[ -n "${HARNESS_ENABLED:-}" ]]; then
        SKILLOPT_ENABLED="$HARNESS_ENABLED"
    fi
    if [[ -n "${HARNESS_LANGFUSE_ENABLED:-}" ]]; then
        SKILLOPT_LANGFUSE_ENABLED="$HARNESS_LANGFUSE_ENABLED"
    fi
    if [[ -n "${HARNESS_SESSION_ID:-}" ]]; then
        SKILLOPT_SESSION_ID="$HARNESS_SESSION_ID"
    fi
}

_skillopt_harness_export_mirrors() {
    HARNESS_ENABLED="$SKILLOPT_ENABLED"
    HARNESS_LANGFUSE_ENABLED="$SKILLOPT_LANGFUSE_ENABLED"
    HARNESS_SESSION_ID="$SKILLOPT_SESSION_ID"
    _SKILLOPT_HARNESS_MIRROR_ENABLED="$SKILLOPT_ENABLED"
    _SKILLOPT_HARNESS_MIRROR_LANGFUSE="$SKILLOPT_LANGFUSE_ENABLED"
    _SKILLOPT_HARNESS_MIRROR_SESSION="$SKILLOPT_SESSION_ID"
    export HARNESS_ENABLED HARNESS_LANGFUSE_ENABLED HARNESS_SESSION_ID
}

skillopt_init() {
    local _cli_enable=false _cli_disable=false

    # Load .env file if exists (only set variables that are not already set)
    local env_file="${_SKILLOPT_SKILLS_ROOT}/.env"
    if [[ -f "$env_file" ]]; then
        while IFS= read -r line || [[ -n "$line" ]]; do
            [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
            key="${line%%=*}"
            value="${line#*=}"
            key="$(echo "$key" | xargs)"
            value="$(echo "$value" | xargs)"
            if [[ -n "$key" && -z "${!key:-}" ]]; then
                export "$key=$value"
            fi
        done < "$env_file"
    fi

    _skillopt_harness_merge_env

    # Precedence: CLI flags > shell env / .env > default false
    SKILLOPT_ENABLED="${SKILLOPT_ENABLED:-false}"
    SKILLOPT_LANGFUSE_ENABLED="${SKILLOPT_LANGFUSE_ENABLED:-false}"
    SKILLOPT_LOG_FORMAT="${SKILLOPT_LOG_FORMAT:-text}"
    SKILLOPT_RETRIES="${SKILLOPT_RETRIES:-3}"
    SKILLOPT_CB_ENABLED="${SKILLOPT_CB_ENABLED:-false}"
    SKILLOPT_CB_THRESHOLD="${SKILLOPT_CB_THRESHOLD:-5}"
    
    mkdir -p "$_SKILLOPT_RUNTIME_ROOT" 2>/dev/null || true
    chmod 700 "$_SKILLOPT_RUNTIME_ROOT" 2>/dev/null || true
    mkdir -p "${_SKILLOPT_TRACE_DIR:-$_SKILLOPT_RUNTIME_ROOT/traces}" 2>/dev/null || true
    [[ -d "${_SKILLOPT_TRACE_DIR:-$_SKILLOPT_RUNTIME_ROOT/traces}" ]] && chmod 700 "${_SKILLOPT_TRACE_DIR:-$_SKILLOPT_RUNTIME_ROOT/traces}" 2>/dev/null || true
    mkdir -p "$(dirname "$SKILLOPT_LOG_FILE")" 2>/dev/null || true
    [[ -n "${SKILLOPT_RUNTIME_DATA:-}" ]] && mkdir -p "$(dirname "$SKILLOPT_RUNTIME_DATA")" 2>/dev/null || true

    SKILLOPT_REMAINING=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --skillopt-enable|--harness-enable)
                _cli_enable=true
                shift ;;
            --skillopt-disable|--harness-disable)
                _cli_disable=true
                shift ;;
            --skillopt-report|--harness-report)
                SKILLOPT_REPORT=true
                shift ;;
            --skillopt-log-file|--harness-log-file)
                SKILLOPT_LOG_FILE="$2"
                shift 2 ;;
            --skillopt-retries|--harness-retries)
                SKILLOPT_RETRIES="$2"
                shift 2 ;;
            --skillopt-backoff|--harness-backoff)
                IFS=' ' read -r -a SKILLOPT_BACKOFF <<< "$2"
                shift 2 ;;
            --skillopt-cb-enable|--harness-cb-enable)
                SKILLOPT_CB_ENABLED=true
                shift ;;
            --skillopt-cb-disable|--harness-cb-disable)
                SKILLOPT_CB_ENABLED=false
                shift ;;
            --skillopt-cb-threshold|--harness-cb-threshold)
                SKILLOPT_CB_THRESHOLD="$2"
                shift 2 ;;
            --skillopt-cb-cooldown|--harness-cb-cooldown)
                SKILLOPT_CB_COOLDOWN="$2"
                shift 2 ;;
            --skillopt-langfuse-enable|--harness-langfuse-enable)
                SKILLOPT_LANGFUSE_ENABLED=true
                shift ;;
            --skillopt-langfuse-disable|--harness-langfuse-disable)
                SKILLOPT_LANGFUSE_ENABLED=false
                shift ;;
            --skillopt-session-id|--harness-session-id)
                SKILLOPT_SESSION_ID="$2"
                shift 2 ;;
            *)
                SKILLOPT_REMAINING+=("$1")
                shift ;;
        esac
    done

    if [[ "$_cli_disable" == true ]]; then
        SKILLOPT_ENABLED=false
    elif [[ "$_cli_enable" == true ]]; then
        SKILLOPT_ENABLED=true
    fi

    _skillopt_harness_export_mirrors

    skillopt_log "init: enabled=$SKILLOPT_ENABLED langfuse=$SKILLOPT_LANGFUSE_ENABLED retries=$SKILLOPT_RETRIES cb_enabled=$SKILLOPT_CB_ENABLED cb_threshold=$SKILLOPT_CB_THRESHOLD"
    
    # Validate Langfuse configuration if enabled
    if [[ "$SKILLOPT_LANGFUSE_ENABLED" == "true" ]]; then
        local missing_vars=()
        [[ -z "$LANGFUSE_HOST" ]] && missing_vars+=("LANGFUSE_HOST")
        [[ -z "$LANGFUSE_PUBLIC_KEY" ]] && missing_vars+=("LANGFUSE_PUBLIC_KEY")
        [[ -z "$LANGFUSE_SECRET_KEY" ]] && missing_vars+=("LANGFUSE_SECRET_KEY")
        
        if [[ ${#missing_vars[@]} -gt 0 ]]; then
            local error_msg="HARNESS_LANGFUSE_ENABLED=true but missing required environment variables: ${missing_vars[*]}"
            echo "ERROR: $error_msg" >&2
            skillopt_log "ERROR: $error_msg"
            return 1
        fi
    fi
}

skillopt_log() {
    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
    
    if [[ "$SKILLOPT_LOG_FORMAT" == "json" ]]; then
        # JSON Lines format (machine-parseable, for Filebeat/Promtail collection)
        local msg="$1"
        # Escape special characters for JSON
        msg="${msg//\\/\\\\}"
        msg="${msg//\"/\\\"}"
        printf '{"ts":"%s","skill":"%s","level":"info","msg":"%s","pid":%d}\n' \
            "$ts" "$SKILLOPT_SKILL_TAG" "$msg" "$$" >> "$SKILLOPT_LOG_FILE"
    else
        # Plain text format (human-readable, backward compatible)
        printf '[%s] [%s] %s\n' "$ts" "${SKILLOPT_LOG_LABEL:-SkillOpt}" "$1" >> "$SKILLOPT_LOG_FILE"
    fi
}

# Export Prometheus metrics to textfile directory
skillopt_export_metrics() {
    local metrics_dir="${SKILLOPT_METRICS_DIR:-}"
    [[ -z "$metrics_dir" ]] && return 0
    
    mkdir -p "$metrics_dir" 2>/dev/null || return 0
    
    local metrics_file="${metrics_dir}/skillopt_${SKILLOPT_SKILL_TAG}.prom"
    
    local current='{}'
    if [[ -n "${SKILLOPT_RUNTIME_DATA:-}" && -f "$SKILLOPT_RUNTIME_DATA" ]]; then
        current="$(jq '.' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null || echo '{}')"
    fi
    
    local total_calls total_failures error_rate repair_success query_count
    total_calls="$(printf '%s' "$current" | jq -r '.total_calls // 0')"
    total_failures="$(printf '%s' "$current" | jq -r '.total_failures // 0')"
    error_rate="$(printf '%s' "$current" | jq -r '.error_rate // 0')"
    repair_success="$(printf '%s' "$current" | jq -r '.total_repair_success // 0')"
    query_count="$(printf '%s' "$current" | jq -r '.query_count // 0')"
    
    local cb_state="closed" cb_failures=0 cb_state_num=0
    cb_state="$(printf '%s' "$current" | jq -r '.cb_state // "closed"')"
    cb_failures="$(printf '%s' "$current" | jq -r '.cb_consecutive_failures // 0')"
    case "$cb_state" in
        closed) cb_state_num=0 ;;
        open) cb_state_num=1 ;;
        half-open) cb_state_num=2 ;;
        *) cb_state_num=-1 ;;
    esac
    
    local _tmp_metrics_file="${metrics_file}.tmp.$$"
    cat > "$_tmp_metrics_file" << EOF
# HELP skillopt_total_calls Total API calls made through SkillOpt
# TYPE skillopt_total_calls counter
skillopt_total_calls{skill="${SKILLOPT_SKILL_TAG}"} ${total_calls}

# HELP skillopt_total_failures Total failed API calls
# TYPE skillopt_total_failures counter
skillopt_total_failures{skill="${SKILLOPT_SKILL_TAG}"} ${total_failures}

# HELP skillopt_error_rate Current error rate percentage
# TYPE skillopt_error_rate gauge
skillopt_error_rate{skill="${SKILLOPT_SKILL_TAG}"} ${error_rate}

# HELP skillopt_repair_success Total successful self-repairs
# TYPE skillopt_repair_success counter
skillopt_repair_success{skill="${SKILLOPT_SKILL_TAG}"} ${repair_success}

# HELP skillopt_query_count Total queries executed
# TYPE skillopt_query_count counter
skillopt_query_count{skill="${SKILLOPT_SKILL_TAG}"} ${query_count}

# HELP skillopt_circuit_breaker_state Circuit breaker state (0=closed, 1=open, 2=half-open)
# TYPE skillopt_circuit_breaker_state gauge
skillopt_circuit_breaker_state{skill="${SKILLOPT_SKILL_TAG}"} ${cb_state_num}

# HELP skillopt_circuit_breaker_failures Consecutive failures in circuit breaker
# TYPE skillopt_circuit_breaker_failures gauge
skillopt_circuit_breaker_failures{skill="${SKILLOPT_SKILL_TAG}"} ${cb_failures}
EOF

    if [[ -n "${SKILLOPT_RUNTIME_DATA:-}" && -f "$SKILLOPT_RUNTIME_DATA" ]]; then
        local llm_lines
        llm_lines="$(jq -r '
            (.llm_metrics // {}) | to_entries[] |
            "# HELP harness_llm_prompt_tokens_total LLM prompt tokens recorded by harness\n" +
            "# TYPE harness_llm_prompt_tokens_total counter\n" +
            "harness_llm_prompt_tokens_total{skill=\"\($skill)\",coding_agent=\"\(.value.coding_agent)\",model=\"\(.value.model)\",source=\"\(.value.source)\"} \(.value.prompt_tokens // 0)\n" +
            "# HELP harness_llm_completion_tokens_total LLM completion tokens recorded by harness\n" +
            "# TYPE harness_llm_completion_tokens_total counter\n" +
            "harness_llm_completion_tokens_total{skill=\"\($skill)\",coding_agent=\"\(.value.coding_agent)\",model=\"\(.value.model)\",source=\"\(.value.source)\"} \(.value.completion_tokens // 0)\n" +
            "# HELP harness_llm_total_tokens_total LLM total tokens recorded by harness\n" +
            "# TYPE harness_llm_total_tokens_total counter\n" +
            "harness_llm_total_tokens_total{skill=\"\($skill)\",coding_agent=\"\(.value.coding_agent)\",model=\"\(.value.model)\",source=\"\(.value.source)\"} \(.value.total_tokens // 0)\n"
        ' --arg skill "$SKILLOPT_SKILL_TAG" "$SKILLOPT_RUNTIME_DATA" 2>/dev/null || true)"
        if [[ -n "$llm_lines" ]]; then
            printf '%s\n' "$llm_lines" >> "$_tmp_metrics_file"
        fi
    fi

    mv "$_tmp_metrics_file" "$metrics_file"
}

# Resolve Coding Agent for token attribution (Phase 2 TEL).
skillopt_resolve_coding_agent() {
    if [[ -n "${HARNESS_CODING_AGENT:-}" ]]; then
        printf '%s\n' "$HARNESS_CODING_AGENT"
        return 0
    fi
    if [[ -n "${SKILLOPT_CODING_AGENT:-}" ]]; then
        printf '%s\n' "$SKILLOPT_CODING_AGENT"
        return 0
    fi
    if [[ -n "${TRAE_SESSION_ID:-}" ]]; then printf '%s\n' "trae"; return 0; fi
    if [[ -n "${CLAUDE_CONVERSATION_ID:-}" ]]; then printf '%s\n' "claude_code"; return 0; fi
    if [[ -n "${CODEBUDDY_SESSION_ID:-}" ]]; then printf '%s\n' "codebuddy"; return 0; fi
    if [[ -n "${OPENCODE_SESSION_ID:-}" ]]; then printf '%s\n' "opencode"; return 0; fi
    if [[ -n "${IDE_SESSION_ID:-}" ]]; then printf '%s\n' "pi_agent"; return 0; fi
    if [[ -n "${CURSOR_TRACE_ID:-}" || -n "${CURSOR_SESSION_ID:-}" ]]; then printf '%s\n' "cursor"; return 0; fi
    printf '%s\n' "harness_cli"
}

# Accumulate LLM token counters in runtime JSON for Prometheus export.
_skillopt_record_llm_runtime_metrics() {
    local coding_agent="$1"
    local model="$2"
    local source="$3"
    local prompt="$4"
    local completion="$5"
    local total="$6"

    [[ -f "${SKILLOPT_RUNTIME_DATA:-}" ]] || return 0
    local key="${coding_agent}|${model}|${source}"
    local updated
    updated="$(jq \
        --arg key "$key" \
        --arg ca "$coding_agent" \
        --arg model "$model" \
        --arg source "$source" \
        --argjson p "$prompt" \
        --argjson c "$completion" \
        --argjson t "$total" \
        '.llm_metrics = (.llm_metrics // {}) |
         .llm_metrics[$key] = {
            coding_agent: $ca,
            model: $model,
            source: $source,
            prompt_tokens: ((.llm_metrics[$key].prompt_tokens // 0) + $p),
            completion_tokens: ((.llm_metrics[$key].completion_tokens // 0) + $c),
            total_tokens: ((.llm_metrics[$key].total_tokens // 0) + $t)
         }' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null)" || return 0
    printf '%s\n' "$updated" > "$SKILLOPT_RUNTIME_DATA"
}

# Record one LLM generation on the active trace (Phase 2 TEL).
skillopt_record_llm_usage() {
    local usage_json="${1:-}"
    [[ -z "$usage_json" ]] && return 0
    [[ -z "${SKILLOPT_CURRENT_TRACE_ID:-}" ]] && return 0

    local trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
    [[ -f "$trace_file" ]] || return 0

    if ! printf '%s' "$usage_json" | jq -e 'type == "object"' >/dev/null 2>&1; then
        skillopt_log "WARN: record_llm_usage skipped — invalid JSON"
        return 0
    fi

    local coding_agent model prompt completion total source confidence role latency_raw gen_id ts
    coding_agent="$(printf '%s' "$usage_json" | jq -r '.coding_agent // empty')"
    [[ -z "$coding_agent" || "$coding_agent" == "null" ]] && coding_agent="$(skillopt_resolve_coding_agent)"
    model="$(printf '%s' "$usage_json" | jq -r '.model // "unknown"')"
    prompt="$(printf '%s' "$usage_json" | jq -r '.prompt_tokens // 0')"
    completion="$(printf '%s' "$usage_json" | jq -r '.completion_tokens // 0')"
    total="$(printf '%s' "$usage_json" | jq -r 'if .total_tokens != null then .total_tokens else ((.prompt_tokens // 0) + (.completion_tokens // 0)) end')"
    source="$(printf '%s' "$usage_json" | jq -r '.source // "harness_llm"')"
    confidence="$(printf '%s' "$usage_json" | jq -r '.attribution_confidence // "observed"')"
    role="$(printf '%s' "$usage_json" | jq -r '.role // "harness_llm"')"
    latency_raw="$(printf '%s' "$usage_json" | jq -r '.latency_ms // empty')"
    gen_id="gen-$(date +%s)-${RANDOM}"
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"

    local latency_json="null"
    if [[ -n "$latency_raw" && "$latency_raw" != "null" ]]; then
        latency_json="$latency_raw"
    fi

    local updated
    updated="$(jq \
        --arg gid "$gen_id" \
        --arg role "$role" \
        --arg ca "$coding_agent" \
        --arg model "$model" \
        --argjson prompt "$prompt" \
        --argjson completion "$completion" \
        --argjson total "$total" \
        --arg source "$source" \
        --arg conf "$confidence" \
        --arg ts "$ts" \
        --argjson latency "$latency_json" \
        '.llm_generations = (.llm_generations // []) + [{
            generation_id: $gid,
            role: $role,
            coding_agent: $ca,
            model: $model,
            prompt_tokens: $prompt,
            completion_tokens: $completion,
            total_tokens: $total,
            source: $source,
            attribution_confidence: $conf,
            timestamp: $ts,
            latency_ms: $latency
        }] |
        .llm_usage = {
            prompt_tokens: ((.llm_usage.prompt_tokens // 0) + $prompt),
            completion_tokens: ((.llm_usage.completion_tokens // 0) + $completion),
            total_tokens: ((.llm_usage.total_tokens // 0) + $total)
        }' "$trace_file" 2>/dev/null)" || {
        skillopt_log "WARN: record_llm_usage jq update failed"
        return 0
    }
    printf '%s\n' "$updated" > "$trace_file"

    _skillopt_record_llm_runtime_metrics "$coding_agent" "$model" "$source" "$prompt" "$completion" "$total"

    if skillopt_langfuse_required; then
        _skillopt_langfuse_create_generation \
            "$gen_id" "$SKILLOPT_CURRENT_TRACE_ID" "$role" "$model" "$ts" \
            "$prompt" "$completion" "$total" "$coding_agent" "$source" \
            "${SKILLOPT_CURRENT_FLOW_SPAN_ID:-}"
    fi

    skillopt_log "trace: llm_usage recorded gen=$gen_id model=$model total=$total"
}

# Load W3C traceparent helpers when present (X-13 TEL).
_skillopt_load_otel_traceparent_lib() {
    local lib="${_SKILLOPT_SKILLS_ROOT}/scripts/lib/otel-traceparent.sh"
    [[ -f "$lib" ]] || return 1
    # shellcheck source=/dev/null
    source "$lib"
}

# X-13: persist incoming W3C trace context on local trace (fail-open).
_skillopt_ingest_w3c_traceparent() {
    [[ -n "${SKILLOPT_CURRENT_TRACE_ID:-}" ]] || return 0
    local trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
    [[ -f "$trace_file" ]] || return 0

    _skillopt_load_otel_traceparent_lib || return 0

    local incoming="${TRACEPARENT:-}"
    if [[ -z "$incoming" ]]; then
        incoming="$(otel_traceparent_read_sidecar 2>/dev/null || true)"
    fi
    [[ -n "$incoming" ]] || return 0

    if ! otel_traceparent_validate "$incoming"; then
        skillopt_log "WARN: invalid TRACEPARENT; skipped w3c ingest"
        return 0
    fi

    otel_traceparent_parse "$incoming" || return 0

    local merged
    merged="$(jq -n \
        --arg incoming "$incoming" \
        --arg trace_id "$OTEL_TRACE_ID" \
        --arg parent_span_id "$OTEL_PARENT_SPAN_ID" \
        --arg flags "$OTEL_TRACE_FLAGS" \
        --arg tracestate "${TRACESTATE:-}" \
        '{
            incoming_traceparent: $incoming,
            trace_id: $trace_id,
            parent_span_id: $parent_span_id,
            trace_flags: $flags,
            tracestate: (if $tracestate == "" then null else $tracestate end)
        }' 2>/dev/null)" || merged=""
    [[ -n "$merged" && "$merged" != "null" ]] || return 0

    local updated
    updated="$(jq --argjson w3c "$merged" '.w3c_trace_context = $w3c' "$trace_file" 2>/dev/null)" || updated=""
    if [[ -n "$updated" ]]; then
        printf '%s\n' "$updated" > "$trace_file"
        skillopt_log "trace: w3c traceparent ingested trace_id=${OTEL_TRACE_ID}"
    fi
}

# Load agent turn helpers when present (X-14/X-15 TEL).
_skillopt_load_agent_turn_lib() {
    local lib="${_SKILLOPT_SKILLS_ROOT}/scripts/lib/agent-turn-usage.sh"
    [[ -f "$lib" ]] || return 1
    # shellcheck source=/dev/null
    source "$lib"
}

# Resolve agent turn JSON: env → per-turn file (X-15) → latest sidecar (+ w3c match).
_skillopt_resolve_agent_turn_raw() {
    local raw="${HARNESS_AGENT_TURN_USAGE:-${SKILLOPT_AGENT_TURN_USAGE:-}}"
    if [[ -n "$raw" ]]; then
        printf '%s' "$raw"
        return 0
    fi

    local turn_id="${HARNESS_AGENT_TURN_ID:-}"
    if [[ -z "$turn_id" ]] && _skillopt_load_agent_turn_lib 2>/dev/null; then
        turn_id="$(agent_turn_read_current_turn_id 2>/dev/null || true)"
    fi

    if [[ -n "$turn_id" ]] && _skillopt_load_agent_turn_lib 2>/dev/null; then
        local by_turn
        by_turn="$(agent_turn_read_turn_record "$turn_id" 2>/dev/null || true)"
        if [[ -n "$by_turn" ]]; then
            printf '%s' "$by_turn"
            return 0
        fi
    fi

    local sidecar="${_SKILLOPT_SKILLS_ROOT}/.runtime/token/context/agent-turn-latest.json"
    if [[ ! -f "$sidecar" ]]; then
        return 1
    fi
    local candidate
    candidate="$(cat "$sidecar" 2>/dev/null || true)"
    if [[ -n "${TRACEPARENT:-}" ]] && _skillopt_load_otel_traceparent_lib 2>/dev/null; then
        local sidecar_tp
        sidecar_tp="$(printf '%s' "$candidate" | jq -r '.w3c_traceparent // empty' 2>/dev/null || echo "")"
        if [[ -n "$sidecar_tp" ]]; then
            if otel_traceparent_same_trace "$TRACEPARENT" "$sidecar_tp"; then
                printf '%s' "$candidate"
                return 0
            fi
            skillopt_log "WARN: agent-turn sidecar w3c trace-id mismatch TRACEPARENT; skipped"
            return 1
        fi
    fi
    printf '%s' "$candidate"
}

# Parse IDE-reported agent turn usage (Phase 3 TEL). Fail-open on bad JSON.
# Phase 4: sidecar; X-13: TRACEPARENT correlation; X-14: cursor native without env; X-15: per-turn file.
_skillopt_ingest_agent_turn_usage() {
    local raw
    raw="$(_skillopt_resolve_agent_turn_raw 2>/dev/null || true)"
    [[ -n "$raw" ]] || return 0

    if ! printf '%s' "$raw" | jq -e 'type == "object"' >/dev/null 2>&1; then
        skillopt_log "WARN: HARNESS_AGENT_TURN_USAGE invalid JSON; skipped"
        return 0
    fi

    local normalized
    normalized="$(printf '%s' "$raw" | jq -c '{
        role: "agent_turn",
        coding_agent: (if (.coding_agent // "") == "" then null else .coding_agent end),
        model: (.model // "unknown"),
        prompt_tokens: (.prompt_tokens // 0),
        completion_tokens: (.completion_tokens // 0),
        total_tokens: (if .total_tokens != null then .total_tokens else ((.prompt_tokens // 0) + (.completion_tokens // 0)) end),
        source: (.source // "agent_turn"),
        attribution_confidence: (.attribution_confidence // "reported"),
        latency_ms: (.latency_ms // null),
        turn_id: (.turn_id // null)
    }' 2>/dev/null)" || {
        skillopt_log "WARN: HARNESS_AGENT_TURN_USAGE normalize failed; skipped"
        return 0
    }

    skillopt_record_llm_usage "$normalized"

    [[ -n "${SKILLOPT_CURRENT_TRACE_ID:-}" ]] || return 0
    local trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
    [[ -f "$trace_file" ]] || return 0

    local turn_id src conf
    turn_id="$(printf '%s' "$raw" | jq -r '.turn_id // empty' 2>/dev/null || echo "")"
    src="$(printf '%s' "$raw" | jq -r '.source // empty' 2>/dev/null || echo "")"
    conf="$(printf '%s' "$raw" | jq -r '.attribution_confidence // empty' 2>/dev/null || echo "")"
    if [[ -z "$turn_id" ]]; then
        turn_id="${HARNESS_AGENT_TURN_ID:-}"
    fi

    local trace_patch
    trace_patch="$(jq -n \
        --arg turn_id "$turn_id" \
        --arg src "$src" \
        --arg conf "$conf" \
        '{
            agent_turn_id: (if $turn_id == "" then null else $turn_id end),
            turn_attribution: {
                turn_id: (if $turn_id == "" then null else $turn_id end),
                source: (if $src == "" then "agent_turn" else $src end),
                attribution_confidence: (if $conf == "" then "reported" else $conf end)
            }
        }' 2>/dev/null)" || trace_patch=""
    if [[ -n "$trace_patch" && "$trace_patch" != "null" ]]; then
        local patched
        patched="$(jq --argjson ta "$trace_patch" '. * $ta' "$trace_file" 2>/dev/null)" || patched=""
        if [[ -n "$patched" ]]; then
            printf '%s\n' "$patched" > "$trace_file"
        fi
    fi

    local ctx
    ctx="$(printf '%s' "$raw" | jq -c '.context_metadata // empty' 2>/dev/null || echo "")"
    if [[ -n "$ctx" && "$ctx" != "null" && "$ctx" != "{}" ]]; then
        local merged
        merged="$(jq --argjson ctx "$ctx" '.context_metadata = ((.context_metadata // {}) + $ctx)' "$trace_file" 2>/dev/null)" || merged=""
        if [[ -n "$merged" ]]; then
            printf '%s\n' "$merged" > "$trace_file"
        fi
    elif ! jq -e 'has("context_metadata")' "$trace_file" >/dev/null 2>&1; then
        local seeded
        seeded="$(jq '.context_metadata = {}' "$trace_file" 2>/dev/null)" || seeded=""
        if [[ -n "$seeded" ]]; then
            printf '%s\n' "$seeded" > "$trace_file"
        fi
    fi
}

# Phase 4.5: ingest MCP context sidecar into trace.context_metadata.mcp (fail-open).
_skillopt_ingest_mcp_context() {
    [[ -n "${SKILLOPT_CURRENT_TRACE_ID:-}" ]] || return 0
    local trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
    [[ -f "$trace_file" ]] || return 0

    local sidecar="${_SKILLOPT_SKILLS_ROOT}/.runtime/token/context/mcp-context-latest.json"
    [[ -f "$sidecar" ]] || return 0

    local mcp_json
    mcp_json="$(cat "$sidecar" 2>/dev/null || true)"
    if ! printf '%s' "$mcp_json" | jq -e 'type == "object" and has("mcp_tools_loaded")' >/dev/null 2>&1; then
        skillopt_log "WARN: mcp-context sidecar invalid; skipped"
        return 0
    fi

    local merged
    merged="$(jq --argjson mcp "$mcp_json" \
        '.context_metadata = ((.context_metadata // {}) + {mcp: $mcp})' \
        "$trace_file" 2>/dev/null)" || merged=""
    if [[ -n "$merged" ]]; then
        printf '%s\n' "$merged" > "$trace_file"
        skillopt_log "trace: mcp context ingested tools_loaded=$(printf '%s' "$mcp_json" | jq -r '.mcp_tools_loaded | length')"
    fi
}

# Roll up completed trace llm_generations into Session JSON (Phase 3 TEL).
_skillopt_session_rollup_from_trace() {
    local trace_file="$1"
    [[ -f "$trace_file" ]] || return 0
    [[ -n "${SKILLOPT_SESSION_ID:-}" ]] || return 0

    local session_file="${_SKILLOPT_SESSIONS_DIR:-$_SKILLOPT_RUNTIME_ROOT}/skillopt-session-${SKILLOPT_SESSION_ID}.json"
    [[ -f "$session_file" ]] || return 0

    local updated
    updated="$(jq -s '
        def merge_gen($buckets; $g):
            ($g.coding_agent // "unknown") as $ca |
            ($g.model // "unknown") as $m |
            ($g.source // "unknown") as $src |
            ($buckets | map(
                if .coding_agent == $ca and .model == $m and .source == $src then
                    . + {
                        prompt_tokens: (.prompt_tokens + ($g.prompt_tokens // 0)),
                        completion_tokens: (.completion_tokens + ($g.completion_tokens // 0)),
                        total_tokens: (.total_tokens + ($g.total_tokens // 0))
                    }
                else .
                end
            )) as $updated |
            if ($updated | map(select(.coding_agent == $ca and .model == $m and .source == $src)) | length) > 0 then
                $updated
            else
                $buckets + [{
                    coding_agent: $ca,
                    model: $m,
                    source: $src,
                    prompt_tokens: ($g.prompt_tokens // 0),
                    completion_tokens: ($g.completion_tokens // 0),
                    total_tokens: ($g.total_tokens // 0)
                }]
            end;
        .[0] as $sess | .[1] as $trace |
        (($sess.llm_usage_by_agent_model // []) | reduce ($trace.llm_generations // [])[] as $g (.; merge_gen(.; $g))) as $buckets |
        {
            prompt_tokens: ([$buckets[].prompt_tokens] | add // 0),
            completion_tokens: ([$buckets[].completion_tokens] | add // 0),
            total_tokens: ([$buckets[].total_tokens] | add // 0)
        } as $total |
        $sess + {
            coding_agent: ($trace.coding_agent // $sess.coding_agent // "unknown"),
            agent_model: (
                ($trace.llm_generations // [] | map(select(.role == "agent_turn"))
                    | if length > 0 then .[-1].model else empty end)
                // $sess.agent_model // "unknown"
            ),
            llm_usage_by_agent_model: $buckets,
            llm_usage_total: $total,
            context_metadata: (($sess.context_metadata // {}) + ($trace.context_metadata // {}))
        }
    ' "$session_file" "$trace_file" 2>/dev/null)" || {
        skillopt_log "WARN: session llm rollup failed"
        return 0
    }

    [[ -n "$updated" ]] || {
        skillopt_log "WARN: session llm rollup produced empty output; session file unchanged"
        return 0
    }

    (umask 077 && printf '%s\n' "$updated" > "$session_file") 2>/dev/null || \
        printf '%s\n' "$updated" > "$session_file"
    skillopt_log "session: llm rollup total=$(printf '%s' "$updated" | jq -r '.llm_usage_total.total_tokens // 0')"
}

# ============================================================================
# Local-first tracing (Langfuse optional mirror)
# ============================================================================
#
# Every wrapper invocation writes `${SKILLS_ROOT}/.runtime/traces/<skill>/trace-*.json` (canonical).
# When SKILLOPT_LANGFUSE_ENABLED=true, the same trace is also mirrored to Langfuse HTTP.

skillopt_trace_required() {
    return 0
}

skillopt_langfuse_required() {
    [[ "$SKILLOPT_LANGFUSE_ENABLED" == "true" ]] && return 0
    return 1
}

skillopt_session_init() {
    # Priority 1: Explicit session ID from environment
    if [[ -n "${SKILLOPT_SESSION_ID:-}" ]]; then
        :
    
    # Priority 2: IDE environment variables
    elif [[ -n "${TRAE_SESSION_ID:-}" ]]; then
        SKILLOPT_SESSION_ID="sess-trae-${TRAE_SESSION_ID}"
    elif [[ -n "${CLAUDE_CONVERSATION_ID:-}" ]]; then
        SKILLOPT_SESSION_ID="sess-claude-${CLAUDE_CONVERSATION_ID}"
    elif [[ -n "${OPENCODE_SESSION_ID:-}" ]]; then
        SKILLOPT_SESSION_ID="sess-opencode-${OPENCODE_SESSION_ID}"
    elif [[ -n "${CODEBUDDY_SESSION_ID:-}" ]]; then
        SKILLOPT_SESSION_ID="sess-codebuddy-${CODEBUDDY_SESSION_ID}"
    elif [[ -n "${IDE_SESSION_ID:-}" ]]; then
        SKILLOPT_SESSION_ID="sess-ide-${IDE_SESSION_ID}"
    
    # Priority 3: Fallback (workdir hash + date)
    else
        local workdir_hash
        workdir_hash="$(printf '%s' "$(pwd):${USER:-unknown}:$$" | md5 2>/dev/null | cut -c1-8 || \
                        printf '%s' "$(pwd):${USER:-unknown}:$$" | md5sum 2>/dev/null | cut -c1-8 || \
                        echo "00000000")"
        local today
        today="$(date +%Y%m%d)"
        SKILLOPT_SESSION_ID="sess-${workdir_hash}-${today}"
        skillopt_log "session: fallback $SKILLOPT_SESSION_ID (workdir+date)"
    fi
    
    mkdir -p "$_SKILLOPT_TRACE_DIR" 2>/dev/null || true
    
    local sessions_dir="${_SKILLOPT_SESSIONS_DIR:-$_SKILLOPT_RUNTIME_ROOT}"
    mkdir -p "$sessions_dir" 2>/dev/null || true
    local session_file="${sessions_dir}/skillopt-session-${SKILLOPT_SESSION_ID}.json"
    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
    local session_coding_agent
    session_coding_agent="$(skillopt_resolve_coding_agent)"
    
    if [[ ! -f "$session_file" ]]; then
        # First time: create session
        (umask 077 && jq -n \
            --arg sid "$SKILLOPT_SESSION_ID" \
            --arg skill "$SKILLOPT_SKILL_TAG" \
            --arg workdir "$(pwd)" \
            --arg ts "$ts" \
            --arg coding_agent "$session_coding_agent" \
            '{
                session_id: $sid,
                skill: $skill,
                workdir: $workdir,
                created_at: $ts,
                last_active: $ts,
                trace_count: 0,
                status: "active",
                coding_agent: $coding_agent,
                agent_model: "unknown",
                llm_usage_total: {prompt_tokens: 0, completion_tokens: 0, total_tokens: 0},
                llm_usage_by_agent_model: [],
                context_metadata: {}
            }' > "$session_file") 2>/dev/null || jq -n \
            --arg sid "$SKILLOPT_SESSION_ID" \
            --arg skill "$SKILLOPT_SKILL_TAG" \
            --arg workdir "$(pwd)" \
            --arg ts "$ts" \
            --arg coding_agent "$session_coding_agent" \
            '{
                session_id: $sid,
                skill: $skill,
                workdir: $workdir,
                created_at: $ts,
                last_active: $ts,
                trace_count: 0,
                status: "active",
                coding_agent: $coding_agent,
                agent_model: "unknown",
                llm_usage_total: {prompt_tokens: 0, completion_tokens: 0, total_tokens: 0},
                llm_usage_by_agent_model: [],
                context_metadata: {}
            }' > "$session_file"
        
        if skillopt_langfuse_required; then
            _skillopt_langfuse_create_session "$SKILLOPT_SESSION_ID" "$ts"
        fi
        skillopt_log "session: created $SKILLOPT_SESSION_ID"
    else
        # Update last_active and trace_count; backfill TEL fields on legacy sessions
        local updated
        updated="$(jq --arg ts "$ts" --arg ca "$session_coding_agent" '
            .last_active = $ts |
            .trace_count = ((.trace_count // 0) + 1) |
            .coding_agent = (.coding_agent // $ca) |
            .agent_model = (.agent_model // "unknown") |
            .llm_usage_total = (.llm_usage_total // {prompt_tokens: 0, completion_tokens: 0, total_tokens: 0}) |
            .llm_usage_by_agent_model = (.llm_usage_by_agent_model // []) |
            .context_metadata = (.context_metadata // {})
        ' "$session_file")"
        (umask 077 && printf '%s\n' "$updated" > "$session_file") 2>/dev/null || \
            printf '%s\n' "$updated" > "$session_file"
    fi
}

# Extract resource_group_id + tags from CLI params via WT-1 parser.
# Always emits a resource_dimensions object (resource_group_id, tags, tags_raw,
# missing_dimensions, warning, suggestion) with field values being null/[]
# when absent. Never raises — any failure (missing parser file, python
# error, timeout) falls back to the empty schema.
_skillopt_extract_resource_dimensions() {
    local parser_py="${_SKILLOPT_SKILLS_ROOT}/alicloud-gcl-runner-ops/scripts/_extract_resource_dimensions.py"
    if [[ ! -f "$parser_py" ]]; then
        printf '%s' '{"resource_group_id": null, "tags": [], "tags_raw": null, "missing_dimensions": true, "warning": null, "suggestion": null}'
        return 0
    fi
    # Use python3 -c to avoid dependency on the script's own __main__ guard.
    # Pipe args via stdin as JSON to handle any param safely (incl. quotes).
    local args_json
    args_json="$(printf '%s\0' "$@" | python3 -c '
import json, sys
tokens = [t.decode("utf-8") for t in sys.stdin.buffer.read().split(b"\0") if t]
print(json.dumps(tokens))
')"
    python3 -c '
import json, sys
sys.path.insert(0, "'"$parser_py"'".rsplit("/", 1)[0])
from _extract_resource_dimensions import extract
tokens = json.loads(sys.argv[1])
result = extract(tokens)
# Always emit the full schema, even when fields are null.
out = {
    "resource_group_id": result.get("resource_group_id"),
    "tags": result.get("tags", []),
    "tags_raw": result.get("tags_raw"),
    "missing_dimensions": bool(result.get("missing_dimensions", True)),
    "warning": result.get("warning"),
    "suggestion": result.get("suggestion"),
}
print(json.dumps(out, ensure_ascii=False))
' "$args_json" 2>/dev/null || \
        printf '%s' '{"resource_group_id": null, "tags": [], "tags_raw": null, "missing_dimensions": true, "warning": null, "suggestion": null}'
}


# Start a new trace
skillopt_trace_start() {
    local product="$1"
    local action="$2"
    shift 2
    local params=("$@")

    local trace_id="trace-${SKILLOPT_SESSION_ID}-$(date +%s)-${RANDOM}"
    local flow_span_id="span-flow-$(date +%s)-${RANDOM}"
    SKILLOPT_CURRENT_TRACE_ID="$trace_id"
    SKILLOPT_CURRENT_FLOW_SPAN_ID="$flow_span_id"
    SKILLOPT_CURRENT_FLOW_SPAN_NAME="${product}.${action}"
    SKILLOPT_TRACE_START_TIME=$(date +%s%N)
    
    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
    
    local trace_file="${_SKILLOPT_TRACE_DIR}/${trace_id}.json"

    # Restrict trace file permissions (multi-user hosts may share skillops dir)
    (umask 077 && : > "$trace_file") 2>/dev/null || true

    # Build input JSON from params
    local input_json
    input_json="$(printf '%s\n' "${params[@]+"${params[@]}"}" | jq -R -s 'split("\n") | map(select(length > 0))')"
    local coding_agent
    coding_agent="$(skillopt_resolve_coding_agent)"

    # Extract resource_dimensions + missing_dimensions via WT-1 parser.
    # Failure → null defaults; never raises.
    local resource_dimensions_json
    resource_dimensions_json="$(_skillopt_extract_resource_dimensions "${params[@]+"${params[@]}"}")"
    # Promote missing_dimensions / warning / suggestion to TOP-LEVEL trace JSON
    # so Critic and log scanners can see them without descending into
    # resource_dimensions. Same values also remain in resource_dimensions
    # for backward-compatible nested access.
    local missing_dimensions warning_text suggestion_text
    missing_dimensions=$(printf '%s' "$resource_dimensions_json" | jq -r '.missing_dimensions')
    warning_text=$(printf '%s' "$resource_dimensions_json" | jq -r '.warning // ""')
    suggestion_text=$(printf '%s' "$resource_dimensions_json" | jq -r '.suggestion // ""')

    jq -n \
        --arg tid "$trace_id" \
        --arg sid "$SKILLOPT_SESSION_ID" \
        --arg skill "$SKILLOPT_SKILL_TAG" \
        --arg product "$product" \
        --arg action "$action" \
        --arg ts "$ts" \
        --arg params "$(printf '%s ' "${params[@]+"${params[@]}"}")" \
        --arg coding_agent "$coding_agent" \
        --arg warning "$warning_text" \
        --arg suggestion "$suggestion_text" \
        --argjson input "$input_json" \
        --argjson resource_dimensions "$resource_dimensions_json" \
        --argjson missing_dimensions "$missing_dimensions" \
        '{
            trace_id: $tid,
            session_id: $sid,
            skill: $skill,
            coding_agent: $coding_agent,
            product: $product,
            action: $action,
            params: $params,
            input: $input,
            resource_dimensions: $resource_dimensions,
            missing_dimensions: $missing_dimensions,
            warning: (if $warning == "" then null else $warning end),
            suggestion: (if $suggestion == "" then null else $suggestion end),
            start_time: $ts,
            status: "running",
            spans: [],
            llm_generations: [],
            llm_usage: {prompt_tokens: 0, completion_tokens: 0, total_tokens: 0}
        }' > "$trace_file"
    
    _skillopt_ingest_w3c_traceparent
    _skillopt_ingest_agent_turn_usage
    _skillopt_ingest_mcp_context

    if skillopt_langfuse_required; then
        local w3c_trace_id=""
        w3c_trace_id="$(jq -r '.w3c_trace_context.trace_id // empty' "$trace_file" 2>/dev/null || echo "")"
        _skillopt_langfuse_create_trace "$trace_id" "$SKILLOPT_SESSION_ID" \
            "$product" "$action" "$ts" "$input_json" "$w3c_trace_id"
        _skillopt_langfuse_create_span "$flow_span_id" "$trace_id" "${product}.${action}" "$ts"
    fi
    
    skillopt_log "trace: start $trace_id $product $action"
}

# Add a span to current trace
skillopt_trace_span() {
    local span_name="$1"
    local span_status="$2"
    local metadata="${3:-}"
    [[ -z "$metadata" ]] && metadata="{}"
    
    [[ -z "${SKILLOPT_CURRENT_TRACE_ID:-}" ]] && return 0
    
    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
    local span_id="span-${span_name}-$(date +%s)-${RANDOM}"
    
    local trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
    [[ ! -f "$trace_file" ]] && return 0
    
    local updated
    updated="$(jq \
        --arg sid "$span_id" \
        --arg name "$span_name" \
        --arg status "$span_status" \
        --arg ts "$ts" \
        --argjson meta "$metadata" \
        '.spans += [{
            span_id: $sid,
            name: $name,
            status: $status,
            timestamp: $ts,
            metadata: $meta
        }]' "$trace_file")"
    printf '%s\n' "$updated" > "$trace_file"
    
    if skillopt_langfuse_required; then
        _skillopt_langfuse_create_span "$span_id" "$SKILLOPT_CURRENT_TRACE_ID" \
            "$span_name" "$ts"
    fi
}

skillopt_trace_span_io() {
    local span_name="$1"
    local span_status="$2"
    local input_json="${3:-null}"
    local output_json="${4:-null}"
    local metadata="${5:-}"
    [[ -z "$metadata" ]] && metadata="{}"
    [[ -z "${SKILLOPT_CURRENT_TRACE_ID:-}" ]] && return 0

    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
    local span_id="span-${span_name}-$(date +%s)-${RANDOM}"
    local trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
    [[ ! -f "$trace_file" ]] && return 0

    local updated
    updated="$(jq --arg sid "$span_id" --arg name "$span_name" --arg status "$span_status" --arg ts "$ts" --argjson input "$input_json" --argjson output "$output_json" --argjson meta "$metadata" '.spans += [{span_id: $sid, name: $name, status: $status, timestamp: $ts, input: $input, output: $output, metadata: $meta}]' "$trace_file")" || return 0
    printf '%s\n' "$updated" > "$trace_file"
    if skillopt_langfuse_required; then
        python3 "${_SKILLOPT_RUNTIME_PY}" span-create \
            --span-id "$span_id" \
            --trace-id "$SKILLOPT_CURRENT_TRACE_ID" \
            --name "$span_name" \
            --timestamp "$ts" \
            --end-time "$ts" \
            --parent-id "${SKILLOPT_CURRENT_FLOW_SPAN_ID:-}" \
            --input-json "$input_json" \
            --output-json "$output_json" \
            --metadata-json "$metadata" \
            --status "$span_status" >/dev/null 2>&1 || true
    fi
}

# End current trace
skillopt_trace_end() {
    local status="$1"
    local error_code="${2:-}"
    local output="${3:-}"
    
    [[ -z "${SKILLOPT_CURRENT_TRACE_ID:-}" ]] && return 0
    
    local trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
    [[ ! -f "$trace_file" ]] && return 0
    
    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
    local end_time_ns
    end_time_ns=$(date +%s%N)
    local duration_ms=$(( (end_time_ns - ${SKILLOPT_TRACE_START_TIME:-0}) / 1000000 ))
    
    # Build output JSON (truncate if too large)
    local output_json="null"
    if [[ -n "$output" ]]; then
        # Truncate to 4000 chars to avoid oversized payloads
        local truncated="${output:0:4000}"
        # Try to parse as JSON first, fall back to string
        output_json="$(printf '%s' "$truncated" | jq '.' 2>/dev/null || printf '%s' "$truncated" | jq -Rs '.' 2>/dev/null || echo 'null')"
    fi
    
    local updated
    updated="$(jq \
        --arg status "$status" \
        --arg ts "$ts" \
        --arg ec "$error_code" \
        --argjson dur "$duration_ms" \
        --argjson output "$output_json" \
        '.status = $status | .end_time = $ts | .duration_ms = $dur | .error_code = $ec | .output = $output' \
        "$trace_file")"
    printf '%s\n' "$updated" > "$trace_file"
    
    if skillopt_langfuse_required; then
        _skillopt_langfuse_update_trace "$SKILLOPT_CURRENT_TRACE_ID" \
            "$status" "$ts" "$duration_ms" "$error_code" "$output_json"
    fi

    skillopt_log "trace: end ${SKILLOPT_CURRENT_TRACE_ID} status=$status duration=${duration_ms}ms"

    _skillopt_session_rollup_from_trace "$trace_file"

    # Append a lightweight Layer-1 memory entry so every wrapper invocation
    # is recorded even when GCL runner is not in the loop. Non-fatal.
    _skillopt_memory_store_lite "$status" "$error_code" "$duration_ms"

    if [[ "$status" != "success" ]]; then
        _skillopt_reflexion_store_lite "$status" "$error_code"
    fi

    SKILLOPT_CURRENT_TRACE_ID=""
    SKILLOPT_CURRENT_FLOW_SPAN_ID=""
    SKILLOPT_CURRENT_FLOW_SPAN_NAME=""
    SKILLOPT_TRACE_START_TIME=""
}

# Internal: Append a Layer-1 memory entry from a direct wrapper invocation.
# Calls gcl_memory.py store-lite so every aliyun CLI call leaves a memory trace
# even when GCL runner is not orchestrating. Non-fatal.
_skillopt_memory_store_lite() {
    local status="$1"
    local error_code="$2"
    local duration_ms="$3"

    [[ -z "${SKILLOPT_CURRENT_TRACE_ID:-}" ]] && return 0
    local trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
    [[ ! -f "$trace_file" ]] && return 0

    local gcl_memory_py="${_SKILLOPT_SKILLS_ROOT}/alicloud-gcl-runner-ops/scripts/gcl_memory.py"
    [[ ! -f "$gcl_memory_py" ]] && return 0

    # Reconstruct the full aliyun command from the trace file fields
    local product action params
    product=$(jq -r '.product // empty' "$trace_file" 2>/dev/null)
    action=$(jq -r '.action // empty' "$trace_file" 2>/dev/null)
    params=$(jq -r '.params // ""' "$trace_file" 2>/dev/null)

    # Validate extracted fields
    if [[ -z "$product" || -z "$action" ]]; then
        skillopt_log "WARN: memory_store_lite skipped - invalid trace format in $trace_file"
        return 0
    fi

    local cmd="aliyun ${product} ${action} ${params}"

    # Map status to gcl_memory convention
    local lite_status="success"
    if [[ "$status" != "success" ]]; then
        lite_status="failed"
    fi

    local exit_code=0
    if [[ "$status" != "success" ]]; then
        exit_code=1
    fi

    local lite_error="$error_code"
    if [[ -z "$lite_error" || "$lite_error" == exit_code_* ]]; then
        lite_error="$(jq -r '
            if (.output | type) == "object" then (.output.Code // .output.code // empty)
            elif (.output | type) == "string" then (
              try (.output | fromjson | .Code // .code // empty) catch empty
            )
            else empty end
        ' "$trace_file" 2>/dev/null || true)"
    fi

    # Pull RG/Tags/missing_dimensions from the trace JSON written by
    # skillopt_trace_start. Pass them through to store-lite so Layer 1
    # entries carry the same first-class index fields as the trace.
    local trace_rg trace_tags_json trace_missing
    trace_rg=$(jq -r '.resource_dimensions.resource_group_id // .resource_group_id // empty' "$trace_file" 2>/dev/null)
    trace_tags_json=$(jq -c '.resource_dimensions.tags // .tags // []' "$trace_file" 2>/dev/null || echo '[]')
    trace_missing=$(jq -r '.missing_dimensions // .resource_dimensions.missing_dimensions // empty' "$trace_file" 2>/dev/null)

    local store_lite_args=(
        "$gcl_memory_py" store-lite
        --skill "$SKILLOPT_SKILL_TAG"
        --operation "$action"
        --command "$cmd"
        --exit-code "$exit_code"
        --duration-ms "$duration_ms"
        --status "$lite_status"
        --execution-path "wrapper"
        --error-code "$lite_error"
        --memory-root "${_SKILLOPT_SKILLS_ROOT}/.runtime/memory"
    )
    if [[ -n "$trace_rg" ]]; then
        store_lite_args+=(--resource-group-id "$trace_rg")
    fi
    store_lite_args+=(--tags-json "$trace_tags_json")
    case "$trace_missing" in
        true)  store_lite_args+=(--missing-dimensions true) ;;
        false) store_lite_args+=(--missing-dimensions false) ;;
    esac

    python3 "${store_lite_args[@]}" >/dev/null 2>&1 || \
        skillopt_log "WARN: memory_store_lite failed"
}

# Plan B: selective Layer-2 write for allowlisted wrapper API failures. Non-fatal.
_skillopt_reflexion_store_lite() {
    local status="$1"
    local error_code="${2:-}"

    [[ "$status" == "success" ]] && return 0

    local trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
    [[ ! -f "$trace_file" ]] && return 0

    local gcl_reflexion_py="${_SKILLOPT_SKILLS_ROOT}/alicloud-gcl-runner-ops/scripts/gcl_reflexion.py"
    [[ ! -f "$gcl_reflexion_py" ]] && return 0

    # Pull RG/Tags/missing_dimensions from the trace JSON so the Layer-2 pattern
    # carries the same first-class context fields as Layer 1 (WT-3/WT-5).
    local trace_rg trace_tags_json trace_missing
    trace_rg=$(jq -r '.resource_dimensions.resource_group_id // .resource_group_id // empty' "$trace_file" 2>/dev/null || true)
    trace_tags_json=$(jq -c '.resource_dimensions.tags // .tags // []' "$trace_file" 2>/dev/null || echo '[]')
    trace_missing=$(jq -r '.missing_dimensions // .resource_dimensions.missing_dimensions // empty' "$trace_file" 2>/dev/null || true)

    local store_lite_args=(
        "$gcl_reflexion_py" store-wrapper-lite
        --skill "$SKILLOPT_SKILL_TAG"
        --trace-file "$trace_file"
        --reflexion-root "${_SKILLOPT_SKILLS_ROOT}/.runtime/reflexion"
    )
    if [[ -n "$trace_rg" ]]; then
        store_lite_args+=(--resource-group-id "$trace_rg")
    fi
    store_lite_args+=(--tags-json "$trace_tags_json")
    case "$trace_missing" in
        true)  store_lite_args+=(--missing-dimensions true) ;;
        false) store_lite_args+=(--missing-dimensions false) ;;
    esac

    python3 "${store_lite_args[@]}" >/dev/null 2>&1 || \
        skillopt_log "WARN: reflexion_store_lite failed"
}

# R2 memory pre-flight for wrapper path (Local-first). Non-fatal.
_skillopt_memory_preflight_r2() {
    local product="$1"
    local action="$2"

    [[ "${SKILLOPT_MEMORY_PREFLIGHT_ENABLED:-true}" == "true" ]] || return 0

    local preflight_py="${_SKILLOPT_SKILLS_ROOT}/alicloud-gcl-runner-ops/scripts/memory_preflight.py"
    [[ -f "$preflight_py" ]] || return 0

    local op="${action%% *}"
    local tmp
    tmp="$(mktemp "${TMPDIR:-/tmp}/skillopt-preflight.XXXXXX")"
    if ! python3 "$preflight_py" \
        --skill "$SKILLOPT_SKILL_TAG" \
        --operation "$op" \
        --skills-root "$_SKILLOPT_SKILLS_ROOT" \
        --format json > "$tmp" 2>/dev/null; then
        rm -f "$tmp"
        skillopt_log "WARN: memory_preflight_r2 failed"
        return 0
    fi

    local traps recent hints empty_flag
    traps="$(jq -r '.slots.known_traps // empty' "$tmp" 2>/dev/null | head -c 240)"
    recent="$(jq -r '.slots.recent_executions // empty' "$tmp" 2>/dev/null | head -c 180)"
    hints="$(jq -r '.slots.strategy_hints // empty' "$tmp" 2>/dev/null | head -c 180)"
    empty_flag="$(jq -r '.empty // true' "$tmp" 2>/dev/null)"
    skillopt_log "R2 preflight empty=${empty_flag} recent_len=${#recent} traps_len=${#traps} hints_len=${#hints}"

    if [[ -n "${SKILLOPT_CURRENT_TRACE_ID:-}" ]]; then
        local trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
        if [[ -f "$trace_file" ]]; then
            local updated
            updated="$(jq --slurpfile pf "$tmp" '.memory_preflight = $pf[0]' "$trace_file" 2>/dev/null)" || updated=""
            if [[ -n "$updated" ]]; then
                printf '%s\n' "$updated" > "$trace_file"
            fi
        fi
    fi
    rm -f "$tmp"
}

# Internal: Langfuse HTTP POST helper
_skillopt_langfuse_post() {
    local endpoint="$1"
    local payload="$2"
    [[ "$SKILLOPT_LANGFUSE_ENABLED" == "true" ]] || return 0
    [[ -z "$LANGFUSE_HOST" ]] && return 0
    [[ -z "$LANGFUSE_PUBLIC_KEY" ]] && return 0
    
    local auth
    auth="$(printf '%s' "${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}" | base64)"
    
    curl -s --max-time 5 --retry 2 --retry-delay 1 -X POST "${LANGFUSE_HOST}${endpoint}" \
        -H "Authorization: Basic ${auth}" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        >/dev/null 2>&1 &
}

# Internal: Create session in Langfuse
_skillopt_langfuse_create_session() {
    local session_id="$1"
    local ts="$2"
    
    _skillopt_langfuse_post "/api/public/sessions" "$(jq -n \
        --arg id "$session_id" \
        --arg skill "$SKILLOPT_SKILL_TAG" \
        '{id: $id, name: ("SkillOpt:" + $skill)}')"
}

# Internal: Create trace in Langfuse
_skillopt_langfuse_create_trace() {
    local trace_id="$1"
    local session_id="$2"
    local product="$3"
    local action="$4"
    local ts="$5"
    local input="$6"
    local w3c_trace_id="${7:-}"
    
    _skillopt_langfuse_post "/api/public/ingestion" "$(jq -n \
        --arg tid "$trace_id" \
        --arg sid "$session_id" \
        --arg name "${SKILLOPT_SKILL_TAG} ${product} ${action}" \
        --arg ts "$ts" \
        --arg skill "$SKILLOPT_SKILL_TAG" \
        --arg product "$product" \
        --arg action "$action" \
        --arg w3c_trace_id "$w3c_trace_id" \
        --arg app "$SKILLOPT_LANGFUSE_APP" \
        --argjson input "${input:-null}" \
        '{batch: [{
            id: $tid,
            type: "trace-create",
            timestamp: $ts,
            body: {
                id: $tid,
                sessionId: $sid,
                name: $name,
                input: $input,
                metadata: (
                    {app: $app, skill: $skill, product: $product, action: $action}
                    + (if $w3c_trace_id == "" then {} else {w3c_trace_id: $w3c_trace_id} end)
                )
            }
        }]}')"
}

# Internal: Create span in Langfuse
_skillopt_langfuse_create_span() {
    local span_id="$1"
    local trace_id="$2"
    local span_name="$3"
    local ts="$4"
    
    _skillopt_langfuse_post "/api/public/ingestion" "$(jq -n \
        --arg sid "$span_id" \
        --arg tid "$trace_id" \
        --arg name "$span_name" \
        --arg ts "$ts" \
        --arg parent "${SKILLOPT_CURRENT_FLOW_SPAN_ID:-}" \
        '{batch: [{
            id: $sid,
            type: "span-create",
            timestamp: $ts,
            body: ({
                id: $sid,
                traceId: $tid,
                name: $name,
                startTime: $ts
            } + (if ($parent != "" and $parent != $sid) then {parentObservationId: $parent} else {} end))
        }]}')"
}

_skillopt_langfuse_create_generation() {
    local generation_id="$1"
    local trace_id="$2"
    local name="$3"
    local model="$4"
    local timestamp="$5"
    local prompt_tokens="$6"
    local completion_tokens="$7"
    local total_tokens="$8"
    local coding_agent="$9"
    local source="${10}"
    local parent_id="${11:-}"

    local metadata
    metadata="$(jq -n \
        --arg skill "$SKILLOPT_SKILL_TAG" \
        --arg ca "$coding_agent" \
        --arg src "$source" \
        '{skill: $skill, coding_agent: $ca, source: $src}')"

    python3 "${_SKILLOPT_RUNTIME_PY}" generation-create \
        --generation-id "$generation_id" \
        --trace-id "$trace_id" \
        --name "$name" \
        --timestamp "$timestamp" \
        --model "$model" \
        --prompt-tokens "$prompt_tokens" \
        --completion-tokens "$completion_tokens" \
        --total-tokens "$total_tokens" \
        --parent-id "$parent_id" \
        --metadata-json "$metadata" >/dev/null 2>&1 || true
}

_skillopt_langfuse_create_judgement_span() {
    local trace_id="$1"
    local ts="$2"
    local level="$3"
    local status_message="$4"
    local status="$5"
    local duration_ms="$6"
    local error_code="$7"
    local span_id="span-judgement-$(date +%s)-${RANDOM}"
    
    _skillopt_langfuse_post "/api/public/ingestion" "$(jq -n \
        --arg sid "$span_id" \
        --arg tid "$trace_id" \
        --arg ts "$ts" \
        --arg level "$level" \
        --arg sm "$status_message" \
        --arg status "$status" \
        --arg parent "${SKILLOPT_CURRENT_FLOW_SPAN_ID:-}" \
        --argjson dur "$duration_ms" \
        --arg ec "$error_code" \
        '{batch: [{
            id: $sid,
            type: "span-create",
            timestamp: $ts,
            body: ({
                id: $sid,
                traceId: $tid,
                name: "skillopt.trace_judgement",
                startTime: $ts,
                endTime: $ts,
                level: $level,
                statusMessage: $sm,
                metadata: {
                    status: $status,
                    duration_ms: $dur,
                    error_code: $ec,
                    trace_display_severity: $level
                }
            } + (if $parent != "" then {parentObservationId: $parent} else {} end))
        }]}')"
}

# Internal: Update trace in Langfuse.
#
# Langfuse semantics:
#   - "trace-create" is an UPSERT; same trace id within 30 days merges fields.
#   - Upserts MUST repeat the original `timestamp` (startTime) so Langfuse does
#     not create a duplicate trace after 30d. Updates that change `timestamp`
#     to the end-time break the upsert merge and the Output field never lands
#     on the original trace.
#   - Body must include all retained fields (name, sessionId, input, output);
#     Langfuse treats absent fields as unchanged, but if the original create
#     did not include the same body fields, the merge can lose data.
#
# Bug fixed: Output column showed "undefined" because the upsert payload used
# the END timestamp and dropped name/sessionId/input, so Langfuse silently
# failed to merge the update onto the original trace record.
_skillopt_langfuse_update_trace() {
    local trace_id="$1"
    local status="$2"
    local ts="$3"
    local duration_ms="$4"
    local error_code="$5"
    local output="$6"
    local level="DEFAULT"
    local status_message=""
    if [[ "$status" == "failed" ]]; then
        level="ERROR"
        status_message="${error_code:-SkillOpt trace failed}"
    fi

    # Pull the original trace fields so the upsert body can repeat them.
    local trace_file="${_SKILLOPT_TRACE_DIR}/${trace_id}.json"
    local orig_timestamp="$ts"
    local orig_name="${SKILLOPT_CURRENT_FLOW_SPAN_NAME:-skillopt.flow}"
    local orig_session="$SKILLOPT_SESSION_ID"
    local orig_input="null"
    if [[ -f "$trace_file" ]]; then
        orig_timestamp="$(jq -r '.start_time // empty' "$trace_file" 2>/dev/null)"
        [[ -z "$orig_timestamp" ]] && orig_timestamp="$ts"
        orig_session="$(jq -r '.session_id // empty' "$trace_file" 2>/dev/null)"
        [[ -z "$orig_session" ]] && orig_session="$SKILLOPT_SESSION_ID"
        # Reconstruct name as <skill> <product> <action> if available
        local orig_product orig_action
        orig_product="$(jq -r '.product // empty' "$trace_file" 2>/dev/null)"
        orig_action="$(jq -r '.action // empty' "$trace_file" 2>/dev/null)"
        if [[ -n "$orig_product" && -n "$orig_action" ]]; then
            orig_name="${SKILLOPT_SKILL_TAG} ${orig_product} ${orig_action}"
        fi
        # Pass through original input so Langfuse doesn't drop it on merge
        if jq -e '.input' "$trace_file" >/dev/null 2>&1; then
            orig_input="$(jq -c '.input' "$trace_file" 2>/dev/null)"
            [[ -z "$orig_input" || "$orig_input" == "null" ]] && orig_input="null"
        fi
    fi

    _skillopt_langfuse_post "/api/public/ingestion" "$(jq -n \
        --arg tid "$trace_id" \
        --arg status "$status" \
        --arg ts "$orig_timestamp" \
        --arg name "$orig_name" \
        --arg sid "$orig_session" \
        --argjson dur "$duration_ms" \
        --arg ec "$error_code" \
        --arg level "$level" \
        --arg sm "$status_message" \
        --argjson output "${output:-null}" \
        --argjson input "$orig_input" \
        --arg app "$SKILLOPT_LANGFUSE_APP" \
        '{batch: [{
            id: ("upd-" + $tid),
            type: "trace-create",
            timestamp: $ts,
            body: {
                id: $tid,
                timestamp: $ts,
                name: $name,
                sessionId: $sid,
                input: $input,
                level: $level,
                statusMessage: $sm,
                output: $output,
                metadata: {
                    app: $app,
                    status: $status,
                    duration_ms: $dur,
                    error_code: $ec,
                    trace_display_severity: $level
                }
            }
        }]}')"
    if [[ -n "${SKILLOPT_CURRENT_FLOW_SPAN_ID:-}" ]]; then
        # Update (not recreate) the flow span so endTime/level/statusMessage land.
        _skillopt_langfuse_post "/api/public/ingestion" "$(jq -n \
            --arg sid "$SKILLOPT_CURRENT_FLOW_SPAN_ID" \
            --arg tid "$trace_id" \
            --arg name "${SKILLOPT_CURRENT_FLOW_SPAN_NAME:-skillopt.flow}" \
            --arg ts "$ts" \
            --arg level "$level" \
            --arg sm "$status_message" \
            --arg status "$status" \
            --argjson dur "$duration_ms" \
            --arg ec "$error_code" \
            '{batch: [{
                id: ("upd-" + $sid),
                type: "span-update",
                timestamp: $ts,
                body: {
                    id: $sid,
                    traceId: $tid,
                    name: $name,
                    endTime: $ts,
                    level: $level,
                    statusMessage: $sm,
                    metadata: {
                        status: $status,
                        duration_ms: $dur,
                        error_code: $ec,
                        trace_display_severity: $level,
                        span_role: "skillopt_flow"
                    }
                }
            }]}')"
    fi
    _skillopt_langfuse_create_judgement_span "$trace_id" "$ts" "$level" "$status_message" "$status" "$duration_ms" "$error_code"
}

skillopt_is_readonly_action() {
    local action="$1"
    case "$action" in
        Describe*|List*|Get*|Query*|ExecuteQuery|Search*|Check*)
            return 0 ;;
        *)
            return 1 ;;
    esac
}

skillopt_extract_error_code() {
    local output="$1"
    local code
    code="$(printf '%s' "$output" | jq -r '.Code // empty' 2>/dev/null || true)"
    if [[ -z "$code" ]]; then
        code="$(printf '%s' "$output" | \
            sed -n 's/.*Error code: *\([A-Za-z0-9_.]*\).*/\1/p' | head -1)"
    fi
    printf '%s' "$code"
}

# Run aliyun once; capture combined output in SKILLOPT_LAST_OUTPUT.
skillopt_run_aliyun() {
    local product="$1"; shift
    local action="$1"; shift
    local tmp_out
    tmp_out="$(mktemp "${TMPDIR:-/tmp}/skillopt-out.XXXXXX")"

    # P1 guard: refuse to run aliyun directly when a wrapper exists.
    # In test contexts (skillopt-core-lib.sh tests), set _SKILLOPT_SKIP_WRAPPER_CHECK=1.
    if ! require_skillopt_wrapper "$product" "$action"; then
        rm -f "$tmp_out"
        return 64
    fi

    local err_state
    if [[ -o errexit ]]; then err_state="set -e"; else err_state="set +e"; fi
    set +e
    aliyun "$product" "$action" "$@" >"$tmp_out" 2>&1
    local rc=$?
    $err_state
    SKILLOPT_LAST_OUTPUT="$(cat "$tmp_out")"
    rm -f "$tmp_out"
    return $rc
}

# ---------------------------------------------------------------------------
# Wrapper-First Pre-Execution Guard (P1 — AGENTS.md §15.8.1)
# ---------------------------------------------------------------------------
# Hard-coded protection against direct aliyun calls. When a product skill has
# a scripts/*-skillopt-wrapper.sh, this guard refuses to proceed and emits a
# actionable error message pointing to the wrapper invocation.
#
# Bypass is opt-in via _SKILLOPT_SKIP_WRAPPER_CHECK=1 (for tests only).
#
# Usage (in any script that calls aliyun directly):
#   require_skillopt_wrapper "ecs" || exit $?
#   aliyun ecs DeleteInstance --InstanceId i-bp1...   # ← only reached if wrapper missing
#
# Or as an assertion:
#   require_skillopt_wrapper "ecs" "DescribeInstances --RegionId cn-hangzhou"
# ---------------------------------------------------------------------------
require_skillopt_wrapper() {
    local product="$1"
    local action="${2:-<op>}"

    if [[ "${_SKILLOPT_SKIP_WRAPPER_CHECK:-0}" == "1" ]]; then
        return 0
    fi

    # Wrapper self-call exemption: when this guard is reached via skillopt_wrap,
    # we are already inside the recommended wrapper-first path
    # (alicloud-<product>-ops/scripts/<product>-skillopt-wrapper.sh -> skillopt_wrap -> here).
    # Inspect FUNCNAME for skillopt_wrap; that proves the call came from the wrapper entry.
    local fn
    for fn in "${FUNCNAME[@]:1}"; do
        if [[ "$fn" == "skillopt_wrap" || "$fn" == "harness_wrap" ]]; then
            return 0
        fi
    done

    # Locate skills root if not already known
    local skills_root="${_SKILLOPT_SKILLS_ROOT:-${ALIYUN_SKILLS_ROOT:-}}"
    if [[ -z "$skills_root" ]]; then
        # Best-effort detection: search up from CWD
        local d="$PWD"
        while [[ "$d" != "/" ]]; do
            if [[ -d "$d/alicloud-${product}-ops/scripts" ]]; then
                skills_root="$d"
                break
            fi
            d="$(dirname "$d")"
        done
    fi

    local wrapper_dir="${skills_root}/alicloud-${product}-ops/scripts"
    local harness_path="${wrapper_dir}/${product}-harness-wrapper.sh"
    local wrapper_path="${wrapper_dir}/${product}-skillopt-wrapper.sh"
    local suggest_path=""

    if [[ -f "$harness_path" ]]; then
        suggest_path="$harness_path"
    elif [[ -f "$wrapper_path" ]]; then
        suggest_path="$wrapper_path"
    fi

    if [[ -n "$suggest_path" ]]; then
        echo "[P0] WRAPPER REQUIRED: Runtime Harness wrapper exists at $suggest_path" >&2
        echo "     Direct aliyun call to '${product} ${action}' is FORBIDDEN (AGENTS.md §15.8)." >&2
        echo "" >&2
        echo "     Run via wrapper instead:" >&2
        echo "       cd alicloud-${product}-ops" >&2
        echo "       ./scripts/$(basename "$suggest_path") ${action}" >&2
        echo "" >&2
        echo "     To bypass (NOT recommended, for tests only):" >&2
        echo "       _SKILLOPT_SKIP_WRAPPER_CHECK=1 ..." >&2
        return 64  # EX_USAGE
    fi

    return 0
}

skillopt_update_runtime() {
    local ec="$1" failed="$2"
    local ts; ts="$(date +%s)"

    local base='{"total_calls":0,"total_failures":0,"total_repair_success":0,"error_rate":0,"query_count":0}'
    local current="$base"
    if [[ -f "$SKILLOPT_RUNTIME_DATA" ]]; then
        current="$(jq '.' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null || echo "$base")"
    fi

    local updated
    updated="$(printf '%s' "$current" | jq \
        --arg ts "$ts" \
        --arg ec "$ec" \
        --argjson failed "$failed" '
        .last_updated = ($ts | tonumber) |
        .last_error    = $ec |
        .total_calls   = ((.total_calls   // 0) + 1) |
        .total_failures = ((.total_failures // 0) + (if $failed == 1 then 1 else 0 end)) |
        .total_repair_success = ((.total_repair_success // 0) + (if $failed == 0 and $ec != "ok" then 1 else 0 end)) |
        .query_count   = ((.query_count   // 0) + 1) |
        .error_rate    = (if .total_calls > 0 then (.total_failures * 100.0 / .total_calls) else 0 end)
    ')"

    printf '%s\n' "$updated" > "$SKILLOPT_RUNTIME_DATA"
    
    # Export Prometheus metrics (if configured)
    skillopt_export_metrics 2>/dev/null || true
}

# Circuit breaker: check current state
# Returns: 0=open (allow), 1=closed (block), 2=half-open (probe)
skillopt_cb_check() {
    if [[ "$SKILLOPT_CB_ENABLED" != "true" ]]; then
        return 0
    fi

    local cb_state="closed"
    local cb_opened_at=0
    local cb_consecutive_failures=0

    if [[ -f "$SKILLOPT_RUNTIME_DATA" ]]; then
        cb_state="$(jq -r '.cb_state // "closed"' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null)"
        cb_opened_at="$(jq -r '.cb_opened_at // 0' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null)"
        cb_consecutive_failures="$(jq -r '.cb_consecutive_failures // 0' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null)"
    fi

    if [[ "$cb_state" == "open" ]]; then
        local now
        now="$(date +%s)"
        local elapsed=$((now - cb_opened_at))

        if [[ $elapsed -ge $SKILLOPT_CB_COOLDOWN ]]; then
            skillopt_log "cb: cooldown elapsed (${elapsed}s >= ${SKILLOPT_CB_COOLDOWN}s), transitioning to half-open"
            return 2  # half-open
        else
            local remaining=$((SKILLOPT_CB_COOLDOWN - elapsed))
            skillopt_log "cb: circuit open, ${remaining}s remaining before probe"
            return 1  # closed
        fi
    fi

    return 0  # open (allow)
}

# Circuit breaker: record a failure
skillopt_cb_record_failure() {
    if [[ "$SKILLOPT_CB_ENABLED" != "true" ]]; then
        return 0
    fi

    local current='{}'
    if [[ -f "$SKILLOPT_RUNTIME_DATA" ]]; then
        current="$(jq '.' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null || echo '{}')"
    fi

    local consecutive_failures
    consecutive_failures="$(printf '%s' "$current" | jq -r '.cb_consecutive_failures // 0')"
    consecutive_failures=$((consecutive_failures + 1))

    local now
    now="$(date +%s)"

    local updated
    if [[ $consecutive_failures -ge $SKILLOPT_CB_THRESHOLD ]]; then
        skillopt_log "cb: threshold reached ($consecutive_failures >= $SKILLOPT_CB_THRESHOLD), opening circuit"
        updated="$(printf '%s' "$current" | jq \
            --argjson ts "$now" \
            --argjson failures "$consecutive_failures" '
            .cb_state = "open" |
            .cb_opened_at = $ts |
            .cb_consecutive_failures = $failures
        ')"
    else
        updated="$(printf '%s' "$current" | jq \
            --argjson failures "$consecutive_failures" '
            .cb_consecutive_failures = $failures
        ')"
    fi

    printf '%s\n' "$updated" > "$SKILLOPT_RUNTIME_DATA"
}

# Circuit breaker: record a success (reset counter)
skillopt_cb_record_success() {
    if [[ "$SKILLOPT_CB_ENABLED" != "true" ]]; then
        return 0
    fi

    local current='{}'
    if [[ -f "$SKILLOPT_RUNTIME_DATA" ]]; then
        current="$(jq '.' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null || echo '{}')"
    fi

    local cb_state
    cb_state="$(printf '%s' "$current" | jq -r '.cb_state // "closed"')"

    local updated
    if [[ "$cb_state" == "half-open" ]]; then
        skillopt_log "cb: probe succeeded in half-open state, closing circuit"
        updated="$(printf '%s' "$current" | jq '
            .cb_state = "closed" |
            .cb_consecutive_failures = 0 |
            .cb_opened_at = 0
        ')"
    else
        updated="$(printf '%s' "$current" | jq '
            .cb_consecutive_failures = 0
        ')"
    fi

    printf '%s\n' "$updated" > "$SKILLOPT_RUNTIME_DATA"
}

# Circuit breaker: manual reset
skillopt_cb_reset() {
    if [[ "$SKILLOPT_CB_ENABLED" != "true" ]]; then
        return 0
    fi

    local current='{}'
    if [[ -f "$SKILLOPT_RUNTIME_DATA" ]]; then
        current="$(jq '.' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null || echo '{}')"
    fi

    local updated
    updated="$(printf '%s' "$current" | jq '
        .cb_state = "closed" |
        .cb_consecutive_failures = 0 |
        .cb_opened_at = 0
    ')"

    printf '%s\n' "$updated" > "$SKILLOPT_RUNTIME_DATA"
    skillopt_log "cb: manual reset performed"
}

# Operational summary report (--skillopt-report / SKILLOPT_REPORT=true)
skillopt_report() {
    local report_file="${1:-}"
    local runtime_data='{}'
    local log_file="$SKILLOPT_LOG_FILE"
    local report_title="${SKILLOPT_LOG_LABEL:-SkillOpt}"
    if [[ "$report_title" == *-SkillOpt ]]; then
        report_title="${report_title%-SkillOpt} SkillOpt"
    fi

    if [[ -f "$SKILLOPT_RUNTIME_DATA" ]]; then
        runtime_data="$(jq '.' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null || echo '{}')"
    fi

    local total_calls total_failures total_repair_success error_rate query_count
    total_calls="$(printf '%s' "$runtime_data" | jq -r '.total_calls // 0')"
    total_failures="$(printf '%s' "$runtime_data" | jq -r '.total_failures // 0')"
    total_repair_success="$(printf '%s' "$runtime_data" | jq -r '.total_repair_success // 0')"
    error_rate="$(printf '%s' "$runtime_data" | jq -r '.error_rate // 0')"
    query_count="$(printf '%s' "$runtime_data" | jq -r '.query_count // 0')"

    local last_updated last_error
    last_updated="$(printf '%s' "$runtime_data" | jq -r '.last_updated // empty')"
    last_error="$(printf '%s' "$runtime_data" | jq -r '.last_error // "none"')"

    local last_updated_human="N/A"
    if [[ -n "$last_updated" ]]; then
        if date -d "@$last_updated" &>/dev/null; then
            last_updated_human="$(date -d "@$last_updated" '+%Y-%m-%d %H:%M:%S %Z' 2>/dev/null || echo "N/A")"
        elif date -r "$last_updated" &>/dev/null; then
            last_updated_human="$(date -r "$last_updated" '+%Y-%m-%d %H:%M:%S %Z' 2>/dev/null || echo "N/A")"
        fi
    fi

    local repair_success_rate="0"
    if [[ "$total_failures" -gt 0 ]]; then
        repair_success_rate="$(awk "BEGIN { printf \"%.1f\", ($total_repair_success * 100.0 / $total_failures) }")"
    fi

    local health_status="🟢 Healthy"
    if awk "BEGIN { exit !($error_rate > 20) }" 2>/dev/null; then
        health_status="🔴 Critical (error_rate > 20%)"
    elif awk "BEGIN { exit !($error_rate > 5) }" 2>/dev/null; then
        health_status="🟡 Warning (error_rate > 5%)"
    fi

    local report_md
    report_md="$(cat <<REPORT_EOF
# ${report_title} 运营摘要

> 生成时间: $(date '+%Y-%m-%d %H:%M:%S %Z')

## 健康状态

| 指标 | 值 |
|:---|:---|
| 状态 | $health_status |
| 错误率 | ${error_rate}% |
| 最后更新 | $last_updated_human |
| 最后错误 | $last_error |

## 调用统计

| 指标 | 值 |
|:---|---:|
| 总调用次数 | $total_calls |
| 查询次数 | $query_count |
| 失败次数 | $total_failures |
| 自修复成功次数 | $total_repair_success |
| 自修复成功率 | ${repair_success_rate}% |

## 动态优化状态

| 参数 | 值 |
|:---|:---|
| SkillOpt 启用 | $SKILLOPT_ENABLED |
| 当前重试次数 | $SKILLOPT_RETRIES |
| 退避策略 | ${SKILLOPT_BACKOFF[*]} |

## 建议

REPORT_EOF
)"

    if awk "BEGIN { exit !($error_rate > 20) }" 2>/dev/null; then
        report_md+="$(cat <<REPORT_EOF
- 🔴 **错误率过高 (${error_rate}%)**：建议检查 API 权限、资源存在性、参数格式
- 检查 RAM 策略权限
- 确认监控的资源在目标 Region 存在
REPORT_EOF
)"
    elif awk "BEGIN { exit !($error_rate > 5) }" 2>/dev/null; then
        report_md+="$(cat <<REPORT_EOF
- 🟡 **错误率偏高 (${error_rate}%)**：建议关注近期错误日志
- 查看日志文件: \`$log_file\`
REPORT_EOF
)"
    else
        report_md+="$(cat <<REPORT_EOF
- 🟢 运行状态良好，无需特别关注
REPORT_EOF
)"
    fi

    if awk "BEGIN { exit !($query_count > 1000) }" 2>/dev/null; then
        report_md+="$(cat <<REPORT_EOF
- ⚠️ **查询量较高 (${query_count})**：已自动启用 Period 调优策略
REPORT_EOF
)"
    fi

    if [[ -f "$log_file" ]]; then
        local log_size
        log_size="$(wc -c < "$log_file" 2>/dev/null | tr -d ' ')"
        report_md+="$(cat <<REPORT_EOF

## 日志文件

- 路径: \`$log_file\`
- 大小: ${log_size} bytes
REPORT_EOF
)"
    fi

    report_md+="$(cat <<REPORT_EOF

---
*Runtime data: \`$SKILLOPT_RUNTIME_DATA\`*
REPORT_EOF
)"

    if [[ -n "$report_file" ]]; then
        printf '%s\n' "$report_md" > "$report_file"
        skillopt_log "report: written to $report_file"
    else
        printf '%s\n' "$report_md"
    fi
}

# Serialize SKILLOPT_PARAMS to JSON array (safe for jq --argjson; avoids jq --args flag injection)
skillopt_params_to_json() {
    if [[ ${#SKILLOPT_PARAMS[@]} -eq 0 ]]; then
        printf '[]'
        return 0
    fi
    printf '%s\n' "${SKILLOPT_PARAMS[@]+"${SKILLOPT_PARAMS[@]}"}" | jq -R -s 'split("\n") | map(select(length > 0))'
}

# Main entry: init → trace → optimize → execute → repair → metrics
# Product overlays supply skillopt_repair_error, skillopt_optimize_params;
# optional skillopt_check_and_poll_empty for propagation polling (e.g. cms).
skillopt_wrap() {
    local product="$1"; shift
    local action="$1";  shift

    skillopt_init "$@"

    skillopt_session_init
    skillopt_trace_start "$product" "$action" "${SKILLOPT_REMAINING[@]+"${SKILLOPT_REMAINING[@]}"}"
    _skillopt_memory_preflight_r2 "$product" "$action"

    if [[ "${SKILLOPT_REPORT:-false}" == "true" ]]; then
        skillopt_report
        skillopt_trace_end "success" "" ""
        return $?
    fi
    SKILLOPT_PARAMS=("${SKILLOPT_REMAINING[@]+"${SKILLOPT_REMAINING[@]}"}")

    if [[ "$SKILLOPT_ENABLED" == "true" ]]; then
        local optimization_input optimization_output optimization_meta
        local params_json optimized_params_json
        params_json="$(skillopt_params_to_json)"
        optimization_input="$(jq -n --arg product "$product" --arg action "$action" --argjson params "$params_json" '{product: $product, action: $action, params: $params}')"
        skillopt_optimize_params "$product" "$action"
        optimized_params_json="$(skillopt_params_to_json)"
        optimization_output="$(jq -n --arg product "$product" --arg action "$action" --argjson params "$optimized_params_json" '{product: $product, action: $action, optimized_params: $params}')"
        optimization_meta="$(jq -n --arg product "$product" --arg action "$action" '{product: $product, action: $action, span_role: "optimization"}')"
        skillopt_trace_span_io "optimization" "success" "$optimization_input" "$optimization_output" "$optimization_meta"
    fi

    if [[ "$SKILLOPT_ENABLED" != "true" ]]; then
        local rc=0
        skillopt_run_aliyun "$product" "$action" "${SKILLOPT_PARAMS[@]+"${SKILLOPT_PARAMS[@]}"}" || rc=$?
        printf '%s\n' "$SKILLOPT_LAST_OUTPUT"
        if [[ $rc -eq 0 ]]; then
            skillopt_trace_end "success" "" "$SKILLOPT_LAST_OUTPUT"
        else
            skillopt_trace_end "failed" "exit_code_$rc" "$SKILLOPT_LAST_OUTPUT"
        fi
        return $rc
    fi

    local cb_rc=0
    skillopt_cb_check || cb_rc=$?
    if [[ $cb_rc -eq 1 ]]; then
        local cb_opened_at now elapsed remaining cb_msg
        cb_opened_at="$(jq -r '.cb_opened_at // 0' "$SKILLOPT_RUNTIME_DATA" 2>/dev/null || echo "0")"
        now="$(date +%s)"
        elapsed=$((now - cb_opened_at))
        remaining=$((SKILLOPT_CB_COOLDOWN - elapsed))
        cb_msg="Circuit breaker OPEN: ${SKILLOPT_CB_THRESHOLD} consecutive failures detected. Cooldown ${remaining}s remaining. Use --harness-cb-disable to bypass."
        skillopt_log "wrap: $cb_msg"
        skillopt_trace_span "circuit_breaker" "failed" '{"reason":"circuit_open"}'
        skillopt_trace_end "failed" "CircuitBreakerOpen" "$cb_msg"
        printf '%s\n' "{\"error\":\"CircuitBreakerOpen\",\"message\":\"$cb_msg\"}" >&2
        return 1
    fi
    if [[ $cb_rc -eq 2 ]]; then
        skillopt_log "wrap: circuit in half-open state, allowing probe request"
    fi

    skillopt_run_aliyun "$product" "$action" "${SKILLOPT_PARAMS[@]+"${SKILLOPT_PARAMS[@]}"}"
    local exit_code=$?
    local captured_output="$SKILLOPT_LAST_OUTPUT"

    if [[ $exit_code -eq 0 ]]; then
        if declare -f skillopt_check_and_poll_empty >/dev/null 2>&1; then
            skillopt_check_and_poll_empty "$product" "$action" "$captured_output" "${SKILLOPT_PARAMS[@]+"${SKILLOPT_PARAMS[@]}"}"
            captured_output="$SKILLOPT_LAST_OUTPUT"
        fi
        printf '%s\n' "$captured_output"
        skillopt_update_runtime "ok" 0
        skillopt_cb_record_success
        skillopt_trace_end "success" "" "$captured_output"
        return 0
    fi

    local error_code
    error_code="$(skillopt_extract_error_code "$captured_output")"

    if [[ -n "$error_code" ]] && skillopt_is_readonly_action "$action"; then
        skillopt_log "wrap: exit=$exit_code error=$error_code → attempting repair"
        skillopt_trace_span "repair" "running" "{\"error_code\":\"$error_code\"}"
        skillopt_repair_error "$error_code" "$product" "$action" "${SKILLOPT_PARAMS[@]+"${SKILLOPT_PARAMS[@]}"}"
        exit_code=$?
        if [[ $exit_code -ne 0 ]]; then
            printf '%s\n' "$captured_output"
            skillopt_cb_record_failure
            skillopt_trace_span "repair" "failed"
            skillopt_trace_end "failed" "$error_code" "$captured_output"
        else
            skillopt_cb_record_success
            skillopt_trace_span "repair" "success"
            skillopt_trace_end "success" "" "$SKILLOPT_LAST_OUTPUT"
        fi
    else
        if [[ -n "$error_code" ]]; then
            skillopt_log "wrap: mutating action $action failed ($error_code); no auto-repair"
            skillopt_update_runtime "$error_code" 1
        else
            skillopt_update_runtime "unknown" 1
        fi
        printf '%s\n' "$captured_output"
        skillopt_cb_record_failure
        skillopt_trace_end "failed" "$error_code" "$captured_output"
    fi

    # P1: WRAPPER_BYPASS detection — GCL exit code 6 indicates a wrapper
    # compliance violation. Emit a dedicated ERROR-level Langfuse alert
    # observation so dashboard consumers can flag bypass events.
    if [[ $exit_code -eq 6 ]] || [[ "$error_code" == "WRAPPER_BYPASS" ]]; then
        _skillopt_langfuse_alert_wrapper_bypass "$SKILLOPT_CURRENT_TRACE_ID" \
            "$product" "$action" "$captured_output"
    fi

    return $exit_code
}

# Internal: emit a dedicated WRAPPER_BYPASS alert observation to Langfuse.
# This is in addition to the regular skillopt_trace_end "failed" event so
# bypass alerts can be filtered independently in Langfuse UI.
_skillopt_langfuse_alert_wrapper_bypass() {
    local trace_id="$1"
    local product="$2"
    local action="$3"
    local output="$4"

    [[ "$SKILLOPT_LANGFUSE_ENABLED" == "true" ]] || return 0
    [[ -n "$trace_id" ]] || return 0

    local span_id="alert-wrapper-bypass-$(date +%s)-${RANDOM}"
    local ts; ts="$(date -u +%Y-%m-%dT%H:%M:%S+0000)"

    _skillopt_log "ALERT: WRAPPER_BYPASS for ${product}.${action} — direct aliyun call detected"

    _skillopt_langfuse_post "/api/public/ingestion" "$(jq -n \
        --arg sid "$span_id" \
        --arg tid "$trace_id" \
        --arg ts "$ts" \
        --arg product "$product" \
        --arg action "$action" \
        '{batch: [{
            id: $sid,
            type: "span-create",
            timestamp: $ts,
            body: {
                id: $sid,
                traceId: $tid,
                name: "skillopt.WRAPPER_BYPASS",
                startTime: $ts,
                endTime: $ts,
                level: "ERROR",
                statusMessage: ("WRAPPER_BYPASS: direct aliyun " + $product + " " + $action + " call detected; AGENTS.md §15.8 violation"),
                metadata: {
                    alert_type: "WRAPPER_BYPASS",
                    product: $product,
                    action: $action,
                    severity: "ERROR",
                    trace_display_severity: "ERROR",
                    policy: "AGENTS.md §15.8",
                    recommendation: "Re-run via alicloud-${product}-ops/scripts/${product}-skillopt-wrapper.sh"
                }
            }
        }]}')"
}

# PR-2: canonical alias for skillopt_wrap (Runtime Harness naming)
harness_wrap() {
    skillopt_wrap "$@"
}

if [[ -n "${BASH_VERSION:-}" ]]; then
    export -f skillopt_init skillopt_log skillopt_is_readonly_action \
              skillopt_extract_error_code skillopt_run_aliyun skillopt_update_runtime skillopt_report \
              skillopt_cb_check skillopt_cb_record_failure skillopt_cb_record_success skillopt_cb_reset \
              skillopt_session_init skillopt_trace_start skillopt_trace_span skillopt_trace_span_io skillopt_trace_end \
              skillopt_resolve_coding_agent skillopt_record_llm_usage \
              skillopt_params_to_json skillopt_wrap harness_wrap
fi

