#!/usr/bin/env bash
# Pi Agent MCP context — extension getActiveTools fixture + tool_call events.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../lib/mcp-context-common.sh
source "${ROOT}/scripts/lib/mcp-context-common.sh"

FIXTURE_DIR=""
PROBE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fixture-dir) FIXTURE_DIR="$2"; shift 2 ;;
        --probe) PROBE=true; shift ;;
        *) echo "Unknown: $1" >&2; exit 1 ;;
    esac
done

parse_active_tools() {
    local f="$1"
    [[ -f "$f" ]] || { echo '[]'; return 0; }
    jq -c '[.tools // .activeTools // [] | .[] | if type == "string" then . else "\(.server // "pi")/\(.name // .id)" end] | unique | sort' "$f" 2>/dev/null || echo '[]'
}

parse_tool_calls() {
    local base="$1"
    local f
    for f in "$base"/tool-call-*.json "$base"/hook-*.json; do
        [[ -f "$f" ]] || continue
        jq -r '.tool // .name // empty | select(length>0)' "$f" 2>/dev/null
    done | jq -R -s 'split("\n") | map(select(length>0)) | unique | sort'
}

flags='{"native_mcp":false}'

if $PROBE; then
    if [[ -z "${PI_SESSION_ID:-}" ]]; then
        echo "SKIP: PI_SESSION_ID not set" >&2; exit 0
    fi
    loaded='[]'
    invoked='[]'
    conf="estimated"
elif [[ -n "$FIXTURE_DIR" ]]; then
    loaded="$(parse_active_tools "$FIXTURE_DIR/active-tools.json")"
    invoked="$(parse_tool_calls "$FIXTURE_DIR")"
    if [[ "$(jq 'length' <<< "$loaded")" -gt 0 && "$(jq 'length' <<< "$invoked")" -gt 0 ]]; then
        conf="mixed"
    elif [[ "$(jq 'length' <<< "$invoked")" -gt 0 ]]; then
        conf="observed"
    else
        conf="estimated"
    fi
else
    echo "ERROR: --fixture-dir or --probe" >&2; exit 1
fi

meta="$(mcp_context_build_metadata "pi" "$loaded" "$invoked" 0 "$conf" "$flags")"
mcp_context_assert_valid "$meta" "pi"
[[ "${MCP_CONTEXT_WRITE_SIDECAR:-}" == "1" ]] && mcp_context_write_sidecar "$meta"
printf '%s\n' "$meta"
