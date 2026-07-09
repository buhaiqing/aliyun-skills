#!/usr/bin/env bash
# TEL Phase 4.5 — MCP context_metadata.mcp_* helpers (loaded / invoked / utilization).

mcp_context_skills_root() {
    if [[ -n "${ALIYUN_SKILLS_ROOT:-}" ]]; then
        printf '%s' "$ALIYUN_SKILLS_ROOT"
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

mcp_context_dir() {
    local root
    root="$(mcp_context_skills_root)"
    [[ -n "$root" ]] || return 1
    printf '%s/.runtime/token/context' "$root"
}

mcp_context_sidecar_path() {
    local ctx
    ctx="$(mcp_context_dir)" || return 1
    printf '%s/mcp-context-latest.json' "$ctx"
}

mcp_context_write_sidecar() {
    local json="$1"
    local ctx path
    ctx="$(mcp_context_dir)" || return 1
    path="$(mcp_context_sidecar_path)" || return 1
    mkdir -p "$ctx" 2>/dev/null || return 1
    chmod 700 "$ctx" 2>/dev/null || true
    (umask 077 && printf '%s\n' "$json" > "$path") 2>/dev/null || printf '%s\n' "$json" > "$path"
}

mcp_context_read_sidecar() {
    local path
    path="$(mcp_context_sidecar_path)" || return 1
    [[ -f "$path" ]] || return 1
    cat "$path"
}

# Merge tool id arrays (unique, stable sort).
mcp_context_merge_tool_ids() {
    local a="${1:-[]}"
    local b="${2:-[]}"
    jq -c -n --argjson a "$a" --argjson b "$b" '
        (($a + $b) | map(select(type == "string" and length > 0)) | unique | sort)
    ' 2>/dev/null
}

mcp_context_compute_utilization() {
    local loaded_json="${1:-[]}"
    local invoked_json="${2:-[]}"
    jq -n --argjson loaded "$loaded_json" --argjson invoked "$invoked_json" '
        if ($loaded | length) == 0 then 0
        else (($invoked | length) / ($loaded | length))
        end
    ' 2>/dev/null
}

# Rough schema token estimate: chars(description+name+inputSchema) / 4 per tool descriptor file.
mcp_context_estimate_schema_tokens_from_files() {
    local total=0
    local f chars
    for f in "$@"; do
        [[ -f "$f" ]] || continue
        chars="$(jq -r '[.name, .description, (.inputSchema // {})] | map(tostring) | join(" ") | length' "$f" 2>/dev/null || echo 0)"
        total=$((total + chars / 4))
    done
    printf '%s' "$total"
}

mcp_context_waste_tokens() {
    local loaded_json="$1"
    local loaded_files_json="$2"
    jq -n --argjson loaded "$loaded_json" --argjson invoked "${3:-[]}" --argjson files "$loaded_files_json" '
        def key($p): ($p | split("/") | if length >= 2 then "\(.[0])/\(.[1])" else $p end);
        ($loaded | map(key(.))) as $lk |
        ($invoked | map(key(.))) as $ik |
        ($lk - $ik) as $unused |
        if ($unused | length) == 0 then 0
        else
          [ $files[] | select(.id as $id | ($unused | index($id)) != null) | .tokens ] | add // 0
        end
    ' 2>/dev/null
}

mcp_context_build_metadata() {
    local platform="$1"
    local loaded_json="$2"
    local invoked_json="$3"
    local waste_tokens="${4:-0}"
    local confidence="${5:-estimated}"
    local flags_json="${6:-"{}"}"
    local util
    util="$(mcp_context_compute_utilization "$loaded_json" "$invoked_json")"
    jq -n \
        --arg platform "$platform" \
        --argjson loaded "$loaded_json" \
        --argjson invoked "$invoked_json" \
        --argjson util "$util" \
        --argjson waste "$waste_tokens" \
        --arg conf "$confidence" \
        --argjson flags "$flags_json" \
        '{
            mcp_tools_loaded: $loaded,
            mcp_tools_invoked: $invoked,
            mcp_tool_utilization: $util,
            mcp_schema_waste_tokens: ($waste | if type == "number" then . else 0 end),
            attribution_confidence: $conf,
            platform: $platform,
            capability_flags: $flags
        }'
}

mcp_context_wrap_for_trace() {
    local meta_json="$1"
    jq -n --argjson mcp "$meta_json" '{context_metadata: {mcp: $mcp}}'
}

# L0 test helper — required fields present and utilization in [0,1].
mcp_context_assert_valid() {
    local json="$1"
    local label="${2:-mcp-context}"
    jq -e '
        (.mcp_tools_loaded | type) == "array" and
        (.mcp_tools_invoked | type) == "array" and
        (.mcp_tool_utilization | type) == "number" and
        .mcp_tool_utilization >= 0 and .mcp_tool_utilization <= 1 and
        (.mcp_schema_waste_tokens | type) == "number" and
        (.attribution_confidence | type) == "string" and
        (.attribution_confidence | length) > 0
    ' <<< "$json" >/dev/null 2>&1 || {
        echo "invalid $label: $json" >&2
        return 1
    }
}
