#!/usr/bin/env bash
# TEL X-13 — W3C Trace Context (traceparent) helpers for IDE → harness wrapper propagation.
# https://www.w3.org/TR/trace-context/#traceparent-header-field-values
# Sourced by hook templates and harness bridge tests (not executed directly).

otel_traceparent_skills_root() {
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

otel_traceparent_context_dir() {
    local root
    root="$(otel_traceparent_skills_root)"
    [[ -n "$root" ]] || return 1
    printf '%s/.runtime/token/context' "$root"
}

otel_traceparent_sidecar_path() {
    local ctx
    ctx="$(otel_traceparent_context_dir)" || return 1
    printf '%s/traceparent-latest.txt' "$ctx"
}

otel_traceparent_random_hex() {
    local nbytes="$1"
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex "$nbytes" 2>/dev/null | tr '[:upper:]' '[:lower:]'
        return 0
    fi
    # Fallback: not cryptographically strong — tests/CI only
    LC_ALL=C tr -dc '0-9a-f' </dev/urandom 2>/dev/null | head -c $((nbytes * 2)) || true
}

otel_traceparent_generate_root() {
    local trace_id span_id
    trace_id="$(otel_traceparent_random_hex 16)"
    span_id="$(otel_traceparent_random_hex 8)"
    [[ ${#trace_id} -eq 32 && ${#span_id} -eq 16 ]] || return 1
    printf '00-%s-%s-01' "$trace_id" "$span_id"
}

# Returns 0 when value matches W3C traceparent grammar.
otel_traceparent_validate() {
    local value="${1:-}"
    [[ "$value" =~ ^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$ ]]
}

# Parse traceparent into shell-assignable vars: OTEL_TRACE_ID OTEL_PARENT_SPAN_ID OTEL_TRACE_FLAGS
otel_traceparent_parse() {
    local value="${1:-}"
    local version trace_id parent_id flags
    otel_traceparent_validate "$value" || return 1
    IFS='-' read -r version trace_id parent_id flags <<< "$value"
    OTEL_TRACE_ID="$trace_id"
    OTEL_PARENT_SPAN_ID="$parent_id"
    OTEL_TRACE_FLAGS="$flags"
    export OTEL_TRACE_ID OTEL_PARENT_SPAN_ID OTEL_TRACE_FLAGS
    return 0
}

# Child span: same trace-id, new parent-id (harness CLI span), preserve flags.
otel_traceparent_child() {
    local parent_tp="${1:-}"
    local new_span_id flags
    otel_traceparent_parse "$parent_tp" || return 1
    new_span_id="$(otel_traceparent_random_hex 8)"
    flags="${OTEL_TRACE_FLAGS:-01}"
    [[ ${#new_span_id} -eq 16 ]] || return 1
    printf '00-%s-%s-%s' "$OTEL_TRACE_ID" "$new_span_id" "$flags"
}

otel_traceparent_write_sidecar() {
    local value="$1"
    local ctx path
    otel_traceparent_validate "$value" || return 1
    ctx="$(otel_traceparent_context_dir)" || return 1
    path="$(otel_traceparent_sidecar_path)" || return 1
    mkdir -p "$ctx" 2>/dev/null || return 1
    chmod 700 "$ctx" 2>/dev/null || true
    (umask 077 && printf '%s\n' "$value" > "$path") 2>/dev/null || printf '%s\n' "$value" > "$path"
}

otel_traceparent_read_sidecar() {
    local path
    path="$(otel_traceparent_sidecar_path)" || return 1
    [[ -f "$path" ]] || return 1
    tr -d '[:space:]' < "$path"
}

# Priority: TRACEPARENT env → sidecar file.
otel_traceparent_resolve_incoming() {
    local tp="${TRACEPARENT:-}"
    if [[ -z "$tp" ]]; then
        tp="$(otel_traceparent_read_sidecar 2>/dev/null || true)"
    fi
    if otel_traceparent_validate "$tp"; then
        printf '%s' "$tp"
        return 0
    fi
    return 1
}

# Compare trace-ids (first 32 hex after version) — links agent turn sidecar to wrapper call.
otel_traceparent_same_trace() {
    local a="${1:-}" b="${2:-}"
    local ta tb
    otel_traceparent_parse "$a" || return 1
    ta="$OTEL_TRACE_ID"
    otel_traceparent_parse "$b" || return 1
    tb="$OTEL_TRACE_ID"
    [[ "$ta" == "$tb" ]]
}
