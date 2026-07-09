#!/usr/bin/env bash
# TEL Phase 4 — shared helpers for IDE agent turn usage → HARNESS_AGENT_TURN_USAGE / sidecar.
# Sourced by hook templates and simulate-ide-agent-turn.sh (not executed directly).

agent_turn_skills_root() {
    if [[ -n "${ALIYUN_SKILLS_ROOT:-}" ]]; then
        printf '%s' "$ALIYUN_SKILLS_ROOT"
        return 0
    fi
    if [[ -n "${HARNESS_SKILLS_ROOT:-}" ]]; then
        printf '%s' "$HARNESS_SKILLS_ROOT"
        return 0
    fi
    local here root
    here="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    if [[ -f "${here}/alicloud-runtime-harness-ops/scripts/harness-core-lib.sh" ]]; then
        printf '%s' "$here"
        return 0
    fi
    root="$(git -C "$here" rev-parse --show-toplevel 2>/dev/null || true)"
    [[ -n "$root" ]] && printf '%s' "$root"
}

agent_turn_context_dir() {
    local root
    root="$(agent_turn_skills_root)"
    [[ -n "$root" ]] || return 1
    printf '%s/.runtime/token/context' "$root"
}

agent_turn_sidecar_path() {
    local ctx
    ctx="$(agent_turn_context_dir)" || return 1
    printf '%s/agent-turn-latest.json' "$ctx"
}

agent_turn_by_turn_dir() {
    local ctx
    ctx="$(agent_turn_context_dir)" || return 1
    printf '%s/agent-turn-by-turn' "$ctx"
}

agent_turn_current_turn_id_path() {
    local ctx
    ctx="$(agent_turn_context_dir)" || return 1
    printf '%s/current-turn-id.txt' "$ctx"
}

# Safe filename for per-turn sidecar (X-15).
agent_turn_sanitize_turn_id() {
    local raw="$1"
    local safe
    safe="$(printf '%s' "$raw" | tr -c 'A-Za-z0-9._-' '_' | head -c 128)"
    [[ -n "$safe" ]] || return 1
    printf '%s' "$safe"
}

agent_turn_turn_record_path() {
    local turn_id="$1"
    local dir safe
    dir="$(agent_turn_by_turn_dir)" || return 1
    safe="$(agent_turn_sanitize_turn_id "$turn_id")" || return 1
    printf '%s/%s.json' "$dir" "$safe"
}

agent_turn_write_current_turn_id() {
    local turn_id="$1"
    local ctx path
    ctx="$(agent_turn_context_dir)" || return 1
    path="$(agent_turn_current_turn_id_path)" || return 1
    mkdir -p "$ctx" 2>/dev/null || return 1
    (umask 077 && printf '%s\n' "$turn_id" > "$path") 2>/dev/null || printf '%s\n' "$turn_id" > "$path"
}

agent_turn_read_current_turn_id() {
    local path
    path="$(agent_turn_current_turn_id_path)" || return 1
    [[ -f "$path" ]] || return 1
    tr -d '[:space:]' < "$path"
}

# X-15: persist per-turn record + latest + current-turn-id pointer.
agent_turn_write_turn_record() {
    local json="$1"
    local normalized turn_id path dir
    normalized="$(agent_turn_normalize_json "$json")" || return 1
    [[ -n "$normalized" && "$normalized" != "null" ]] || return 1
    turn_id="$(printf '%s' "$normalized" | jq -r '.turn_id // empty' 2>/dev/null || echo "")"
    [[ -n "$turn_id" ]] || return 1
    dir="$(agent_turn_by_turn_dir)" || return 1
    path="$(agent_turn_turn_record_path "$turn_id")" || return 1
    mkdir -p "$dir" 2>/dev/null || return 1
    chmod 700 "$dir" 2>/dev/null || true
    (umask 077 && printf '%s\n' "$normalized" > "$path") 2>/dev/null || printf '%s\n' "$normalized" > "$path"
    agent_turn_write_sidecar "$normalized"
    agent_turn_write_current_turn_id "$turn_id"
}

agent_turn_read_turn_record() {
    local turn_id="$1"
    local path
    path="$(agent_turn_turn_record_path "$turn_id")" || return 1
    [[ -f "$path" ]] || return 1
    cat "$path"
}

# True when sidecar/record came from Cursor native API (X-14 — skip usage env injection).
agent_turn_is_cursor_native_source() {
    local json="$1"
    local src conf
    src="$(printf '%s' "$json" | jq -r '.source // empty' 2>/dev/null || echo "")"
    conf="$(printf '%s' "$json" | jq -r '.attribution_confidence // empty' 2>/dev/null || echo "")"
    [[ "$src" == "cursor_native_api" || "$conf" == "native" ]]
}

# Write canonical usage JSON for harness trace_start (umask 077).
agent_turn_write_sidecar() {
    local json="$1"
    local ctx path
    ctx="$(agent_turn_context_dir)" || return 1
    path="$(agent_turn_sidecar_path)" || return 1
    mkdir -p "$ctx" 2>/dev/null || return 1
    chmod 700 "$ctx" 2>/dev/null || true
    (umask 077 && printf '%s\n' "$json" > "$path") 2>/dev/null || printf '%s\n' "$json" > "$path"
}

agent_turn_read_sidecar() {
    local path
    path="$(agent_turn_sidecar_path)" || return 1
    [[ -f "$path" ]] || return 1
    cat "$path"
}

# Normalize hook / fixture payload to HARNESS_AGENT_TURN_USAGE schema.
agent_turn_normalize_json() {
    local raw="$1"
    printf '%s' "$raw" | jq -c '{
        turn_id: (.turn_id // .id // null),
        coding_agent: (
            if (.coding_agent // "") != "" then .coding_agent
            elif (.agent // "") != "" then .agent
            else empty end
        ),
        model: (.model // .llm_model // "unknown"),
        prompt_tokens: (.prompt_tokens // .input_tokens // .usage.prompt_tokens // 0),
        completion_tokens: (.completion_tokens // .output_tokens // .usage.completion_tokens // 0),
        total_tokens: (
            if .total_tokens != null then .total_tokens
            elif .usage.total_tokens != null then .usage.total_tokens
            else ((.prompt_tokens // .input_tokens // .usage.prompt_tokens // 0)
                + (.completion_tokens // .output_tokens // .usage.completion_tokens // 0))
            end
        ),
        source: (.source // "agent_turn"),
        attribution_confidence: (.attribution_confidence // "reported"),
        latency_ms: (.latency_ms // null),
        context_metadata: (.context_metadata // {}),
        w3c_traceparent: (.w3c_traceparent // null)
    }' 2>/dev/null
}

# X-14: Cursor afterAgentResponse native tokenUsage (generation_id → turn_id).
agent_turn_parse_cursor_native_stdin() {
    local input="${1:-}"
    [[ -n "$input" ]] || input="$(cat)"
    printf '%s' "$input" | jq -c '
        select(
            (.tokenUsage != null)
            or (.composer_token_usage != null)
        )
        | {
            turn_id: (.turn_id // .generation_id // .conversation_id // null),
            coding_agent: "cursor",
            model: (.model // .response.model // "unknown"),
            prompt_tokens: (
                .tokenUsage.inputTokens
                // .composer_token_usage.input_tokens
                // .usage.prompt_tokens
                // .usage.input_tokens
                // 0
            ),
            completion_tokens: (
                .tokenUsage.outputTokens
                // .composer_token_usage.output_tokens
                // .usage.completion_tokens
                // .usage.output_tokens
                // 0
            ),
            total_tokens: (
                .tokenUsage.totalTokens
                // .composer_token_usage.total_tokens
                // .usage.total_tokens
                // null
            ),
            source: "cursor_native_api",
            attribution_confidence: "native",
            context_metadata: ((.context_metadata // {}) + {cursor_native: true})
        }
    ' 2>/dev/null
}

# Best-effort: native API first, then generic Cursor hook parse.
agent_turn_parse_cursor_stdin() {
    local input="${1:-}"
    local parsed
    parsed="$(agent_turn_parse_cursor_native_stdin "$input" 2>/dev/null || true)"
    if [[ -n "$parsed" && "$parsed" != "null" ]]; then
        printf '%s' "$parsed"
        return 0
    fi
    agent_turn_parse_cursor_hook_stdin "$input"
}

agent_turn_export_env() {
    local json="$1"
    local normalized
    normalized="$(agent_turn_normalize_json "$json")" || return 1
    [[ -n "$normalized" && "$normalized" != "null" ]] || return 1
    export HARNESS_AGENT_TURN_USAGE="$normalized"
    printf '%s' "$normalized"
}

# Cursor afterAgentResponse / stop — best-effort parse (fail-open).
# Prefer X-14 native tokenUsage when present.
agent_turn_parse_cursor_hook_stdin() {
    local input="${1:-}"
    [[ -n "$input" ]] || input="$(cat)"
    printf '%s' "$input" | jq -c '
        {
            turn_id: (.turn_id // .conversation_id // .session_id // null),
            coding_agent: "cursor",
            model: (.model // .response.model // .usage.model // "unknown"),
            prompt_tokens: (.usage.prompt_tokens // .usage.input_tokens // .prompt_tokens // 0),
            completion_tokens: (.usage.completion_tokens // .usage.output_tokens // .completion_tokens // 0),
            total_tokens: (.usage.total_tokens // .total_tokens // null),
            context_metadata: (.context_metadata // {})
        }
    ' 2>/dev/null
}

# Claude Code PreToolUse / SessionStart — best-effort parse (fail-open).
agent_turn_parse_claude_hook_stdin() {
    local input="${1:-}"
    [[ -n "$input" ]] || input="$(cat)"
    printf '%s' "$input" | jq -c '
        {
            turn_id: (.session_id // .conversation_id // null),
            coding_agent: "claude_code",
            model: (.model // "unknown"),
            prompt_tokens: (.usage.input_tokens // .usage.prompt_tokens // .prompt_tokens // 0),
            completion_tokens: (.usage.output_tokens // .usage.completion_tokens // .completion_tokens // 0),
            total_tokens: (.usage.total_tokens // .total_tokens // null),
            context_metadata: (.context_metadata // {})
        }
    ' 2>/dev/null
}

agent_turn_resolve_session_id() {
    local platform="${1:-cursor}"
    local input="${2:-}"
    [[ -n "$input" ]] || input="$(cat)"
    local sid
    sid="$(printf '%s' "$input" | jq -r '.session_id // .conversation_id // .conversationId // empty' 2>/dev/null)"
    if [[ -z "$sid" ]]; then
        case "$platform" in
            cursor) sid="${CURSOR_SESSION_ID:-${CURSOR_CONVERSATION_ID:-}}" ;;
            claude_code) sid="${CLAUDE_CONVERSATION_ID:-}" ;;
        esac
    fi
    [[ -n "$sid" ]] || return 1
    printf 'sess-%s-%s' "$platform" "$sid"
}
