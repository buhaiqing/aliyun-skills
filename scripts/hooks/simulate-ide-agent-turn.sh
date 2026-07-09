#!/usr/bin/env bash
# Simulate IDE hook reporting agent turn usage (TEL Phase 4 — no real IDE required).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../lib/agent-turn-usage.sh
source "${ROOT}/scripts/lib/agent-turn-usage.sh"

usage() {
    cat <<'EOF'
Usage: simulate-ide-agent-turn.sh [--export-env | --write-sidecar] [JSON_FILE|-]

Writes HARNESS_AGENT_TURN_USAGE and/or .runtime/token/context/agent-turn-latest.json
from fixture JSON (default: built-in cursor sample).

Examples:
  eval "$(bash scripts/hooks/simulate-ide-agent-turn.sh --export-env)"
  bash scripts/hooks/simulate-ide-agent-turn.sh --write-sidecar fixtures/agent-turn-cursor.json
EOF
}

MODE="both"
FIXTURE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --export-env) MODE="env"; shift ;;
        --write-sidecar) MODE="sidecar"; shift ;;
        --both) MODE="both"; shift ;;
        -h|--help) usage; exit 0 ;;
        -) FIXTURE="-"; shift ;;
        *) FIXTURE="$1"; shift ;;
    esac
done

export ALIYUN_SKILLS_ROOT="${ALIYUN_SKILLS_ROOT:-$ROOT}"

raw=""
if [[ "$FIXTURE" == "-" ]]; then
    raw="$(cat)"
elif [[ -n "$FIXTURE" && -f "$FIXTURE" ]]; then
    raw="$(cat "$FIXTURE")"
else
    raw='{"turn_id":"turn-sim-1","coding_agent":"cursor","model":"claude-sonnet-4","prompt_tokens":8800,"completion_tokens":420,"total_tokens":9220}'
fi

normalized="$(agent_turn_normalize_json "$raw")" || {
    echo "ERROR: invalid agent turn JSON" >&2
    exit 1
}

case "$MODE" in
    env)
        agent_turn_export_env "$normalized" >/dev/null
        printf 'export HARNESS_AGENT_TURN_USAGE=%q\n' "$normalized"
        ;;
    sidecar)
        agent_turn_write_sidecar "$normalized"
        echo "wrote $(agent_turn_sidecar_path)"
        ;;
    both)
        agent_turn_write_sidecar "$normalized"
        printf 'export HARNESS_AGENT_TURN_USAGE=%q\n' "$normalized"
        ;;
esac
