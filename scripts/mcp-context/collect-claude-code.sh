#!/usr/bin/env bash
# Claude Code MCP context — mcp-list fixture + PreToolUse hook JSON.
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

parse_mcp_list() {
    local file="$1"
    [[ -f "$file" ]] || { echo '[]'; return 0; }
    grep -E '^[[:space:]]*[^[:space:]#]+' "$file" | awk '{print $1}' | while read -r line; do
        [[ "$line" =~ / ]] && echo "$line"
    done | jq -R -s 'split("\n") | map(select(length>0)) | unique | sort'
}

parse_invoked() {
    local base="$1"
    local -a ids=()
    local f
    for f in "$base"/hook-*.json; do
        [[ -f "$f" ]] || continue
        while IFS= read -r id; do
            [[ -n "$id" ]] && ids+=("$id")
        done < <(jq -r '
            .tool_name // empty |
            if test("^mcp__") then sub("^mcp__"; "") | gsub("__"; "/") else . end
        ' "$f" 2>/dev/null)
    done
    printf '%s\n' "${ids[@]+"${ids[@]}"}" | jq -R -s 'split("\n") | map(select(length>0)) | unique | sort'
}

if $PROBE; then
    if ! command -v claude >/dev/null 2>&1; then
        echo "SKIP: claude CLI not installed" >&2
        exit 0
    fi
  tmp="$(mktemp)"
  if ! claude mcp list >"$tmp" 2>/dev/null; then
    echo "SKIP: claude mcp list failed" >&2
    rm -f "$tmp"
    exit 0
  fi
  loaded="$(parse_mcp_list "$tmp")"
  rm -f "$tmp"
  invoked='[]'
  conf="estimated"
elif [[ -n "$FIXTURE_DIR" ]]; then
    loaded="$(parse_mcp_list "$FIXTURE_DIR/mcp-list.txt")"
    invoked="$(parse_invoked "$FIXTURE_DIR")"
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

files_meta='[]'
waste=0
meta="$(mcp_context_build_metadata "claude_code" "$loaded" "$invoked" "$waste" "$conf" '{}')"
mcp_context_assert_valid "$meta" "claude_code"
[[ "${MCP_CONTEXT_WRITE_SIDECAR:-}" == "1" ]] && mcp_context_write_sidecar "$meta"
printf '%s\n' "$meta"
