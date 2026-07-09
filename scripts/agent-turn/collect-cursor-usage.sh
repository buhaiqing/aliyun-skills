#!/usr/bin/env bash
# Cursor native agent turn usage collector (TEL X-14).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../lib/agent-turn-usage.sh
source "${ROOT}/scripts/lib/agent-turn-usage.sh"

FIXTURE=""
PROBE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fixture) FIXTURE="$2"; shift 2 ;;
        --probe) PROBE=true; shift ;;
        -h|--help)
            echo "Usage: $0 --fixture PATH | --probe"
            exit 0
            ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

if $PROBE; then
    echo '{"mode":"probe","available":false,"reason":"cursor_native_usage_requires_hook_stdin"}' | jq .
    exit 0
fi

[[ -n "$FIXTURE" && -f "$FIXTURE" ]] || {
    echo "ERROR: --fixture PATH required" >&2
    exit 1
}

raw="$(cat "$FIXTURE")"
parsed="$(agent_turn_parse_cursor_stdin "$raw")" || {
    echo "ERROR: fixture not parseable as Cursor native/generic usage" >&2
    exit 1
}

normalized="$(agent_turn_normalize_json "$parsed")" || exit 1
printf '%s\n' "$normalized" | jq .
