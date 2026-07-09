#!/usr/bin/env bash
# Cursor MCP context collector — mcps/**/tools/*.json (loaded) + hook JSON (invoked).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../lib/mcp-context-common.sh
source "${ROOT}/scripts/lib/mcp-context-common.sh"

MODE="fixture"
FIXTURE_DIR=""
PROBE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fixture-dir) FIXTURE_DIR="$2"; MODE="fixture"; shift 2 ;;
        --probe) PROBE=true; MODE="probe"; shift ;;
        -h|--help)
            echo "Usage: $0 --fixture-dir DIR | --probe"
            exit 0
            ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

scan_loaded_from_mcps() {
    local base="$1"
    local -a ids=()
    local -a file_meta=()
    local f server tool id tokens
    [[ -d "$base/mcps" ]] || { echo '{"loaded":[],"files":[]}'; return 0; }
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        server="$(basename "$(dirname "$(dirname "$f")")")"
        tool="$(basename "$f" .json)"
        id="${server}/${tool}"
        ids+=("$id")
        tokens=$(( $(wc -c < "$f" | tr -d ' ') / 4 ))
        file_meta+=("$(jq -n --arg id "$id" --argjson t "$tokens" '{id:$id,tokens:$t}')")
    done < <(find "$base/mcps" -type f -path '*/tools/*.json' 2>/dev/null | sort)
    local loaded_json files_json
    loaded_json="$(printf '%s\n' "${ids[@]+"${ids[@]}"}" | jq -R -s 'split("\n") | map(select(length>0))')"
    files_json="$(printf '%s\n' "${file_meta[@]+"${file_meta[@]}"}" | jq -s '.')"
    jq -n --argjson loaded "$loaded_json" --argjson files "$files_json" '{loaded:$loaded,files:$files}'
}

parse_invoked_hooks() {
    local base="$1"
    local -a files=()
    local hook
    for hook in "$base"/hook-*.json "$base"/*hook*.json; do
        [[ -f "$hook" ]] && files+=("$hook")
    done
    if [[ ${#files[@]} -eq 0 ]]; then
        echo '[]'
        return 0
    fi
    jq -s '
        def tool_id:
            if ((.tool_name // .tool // .name // "") | test("/")) then
                (.tool_name // .tool // .name)
                | if test("^MCP:") then sub("^MCP:[[:space:]]*"; "") else . end
            elif (.mcp_server // "") != "" and ((.tool_name // .tool // .name // "") | length) > 0 then
                "\(.mcp_server)/\(.tool_name // .tool)"
            else empty end;
        [.[] | tool_id] | map(select(length > 0)) | unique | sort
    ' "${files[@]}" 2>/dev/null || echo '[]'
}

if $PROBE; then
    cursor_mcps="${CURSOR_MCP_PROJECT_DIR:-${HOME}/.cursor/projects}"
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    if compgen -G "${cursor_mcps}/*/mcps/*/tools/*.json" >/dev/null 2>&1; then
        mkdir -p "$tmp/mcps"
        # shellcheck disable=SC2086
        cp -R "$(dirname "$(dirname "$(echo ${cursor_mcps}/*/mcps/*/tools/*.json | awk '{print $1}')")")" "$tmp/mcps/" 2>/dev/null || true
        loaded="$(scan_loaded_from_mcps "$tmp" | jq -c '.loaded')"
        files_meta="$(scan_loaded_from_mcps "$tmp" | jq -c '.files')"
        invoked='[]'
        conf="estimated"
    else
        echo "SKIP: no Cursor mcps/ descriptors on host" >&2
        exit 0
    fi
elif [[ -n "$FIXTURE_DIR" && -d "$FIXTURE_DIR" ]]; then
    _scan="$(scan_loaded_from_mcps "$FIXTURE_DIR")"
    loaded="$(jq -c '.loaded' <<< "$_scan")"
    files_meta="$(jq -c '.files' <<< "$_scan")"
    invoked="$(parse_invoked_hooks "$FIXTURE_DIR")"
    if [[ "$(jq 'length' <<< "$loaded")" -gt 0 && "$(jq 'length' <<< "$invoked")" -gt 0 ]]; then
        conf="mixed"
    elif [[ "$(jq 'length' <<< "$invoked")" -gt 0 ]]; then
        conf="observed"
    else
        conf="estimated"
    fi
else
    echo "ERROR: --fixture-dir or --probe required" >&2
    exit 1
fi

waste="$(jq -n --argjson loaded "$loaded" --argjson invoked "$invoked" --argjson files "$files_meta" '
    ($loaded - $invoked) as $unused |
    if ($unused | length) == 0 then 0
    else [ $files[] | select(.id as $i | ($unused | index($i)) != null) | .tokens ] | add // 0
    end
')"

meta="$(mcp_context_build_metadata "cursor" "$loaded" "$invoked" "$waste" "$conf" '{}')"
mcp_context_assert_valid "$meta" "cursor"

if [[ "${MCP_CONTEXT_WRITE_SIDECAR:-}" == "1" ]]; then
    mcp_context_write_sidecar "$meta"
fi

printf '%s\n' "$meta"
