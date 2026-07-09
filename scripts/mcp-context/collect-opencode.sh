#!/usr/bin/env bash
# OpenCode MCP context — opencode.json mcp section + hook fixture.
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

parse_opencode_config() {
    local cfg="$1"
    [[ -f "$cfg" ]] || { echo '[]'; return 0; }
    jq -c '[.mcp // {} | to_entries[] | .key as $s | (.value.tools // [] | .[] | "\($s)/\(.)")] | unique | sort' "$cfg" 2>/dev/null || echo '[]'
}

parse_hook_invoked() {
    local base="$1"
    local f
    for f in "$base"/hook-*.json; do
        [[ -f "$f" ]] || continue
        jq -r '.tool // .name // empty | select(test("/"))' "$f" 2>/dev/null
    done | jq -R -s 'split("\n") | map(select(length>0)) | unique | sort'
}

flags='{"mcp_hook_unverified":true}'

if $PROBE; then
    if ! command -v opencode >/dev/null 2>&1; then
        echo "SKIP: opencode not installed" >&2; exit 0
    fi
    cfg="${OPENCODE_CONFIG:-$HOME/.config/opencode/opencode.json}"
    [[ -f "$cfg" ]] || { echo "SKIP: no opencode config at $cfg" >&2; exit 0; }
    loaded="$(parse_opencode_config "$cfg")"
    invoked='[]'
    conf="estimated"
elif [[ -n "$FIXTURE_DIR" ]]; then
    loaded="$(parse_opencode_config "$FIXTURE_DIR/opencode.json")"
    invoked="$(parse_hook_invoked "$FIXTURE_DIR")"
    if [[ "$(jq 'length' <<< "$invoked")" -gt 0 ]]; then conf="mixed"; else conf="estimated"; fi
else
    echo "ERROR: --fixture-dir or --probe" >&2; exit 1
fi

meta="$(mcp_context_build_metadata "opencode" "$loaded" "$invoked" 0 "$conf" "$flags")"
mcp_context_assert_valid "$meta" "opencode"
[[ "${MCP_CONTEXT_WRITE_SIDECAR:-}" == "1" ]] && mcp_context_write_sidecar "$meta"
printf '%s\n' "$meta"
