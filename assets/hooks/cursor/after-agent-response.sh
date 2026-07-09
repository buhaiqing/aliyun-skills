#!/usr/bin/env bash
# Cursor afterAgentResponse — write agent turn usage sidecar for harness wrapper pickup.
# Fail-open: missing usage fields still allow the agent to continue.
set -euo pipefail

input="$(cat)"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck source=../../../scripts/lib/agent-turn-usage.sh
source "${ROOT}/scripts/lib/agent-turn-usage.sh"
# shellcheck source=../../../scripts/lib/otel-traceparent.sh
source "${ROOT}/scripts/lib/otel-traceparent.sh"

export ALIYUN_SKILLS_ROOT="${ALIYUN_SKILLS_ROOT:-$ROOT}"

parsed="$(agent_turn_parse_cursor_stdin "$input" 2>/dev/null || true)"
if [[ -z "$parsed" || "$parsed" == "null" ]]; then
    exit 0
fi

tp="$(otel_traceparent_resolve_incoming 2>/dev/null || true)"
if [[ -n "$tp" ]]; then
    parsed="$(printf '%s' "$parsed" | jq -c --arg tp "$tp" '. + {w3c_traceparent: $tp}' 2>/dev/null || printf '%s' "$parsed")"
fi

normalized="$(agent_turn_normalize_json "$parsed" 2>/dev/null || true)"
if [[ -n "$normalized" && "$normalized" != "null" ]]; then
    agent_turn_write_turn_record "$normalized" 2>/dev/null || agent_turn_write_sidecar "$normalized" 2>/dev/null || true
fi

exit 0
