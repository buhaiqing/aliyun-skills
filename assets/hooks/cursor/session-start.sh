#!/usr/bin/env bash
# Cursor sessionStart — propagate shared HARNESS_SESSION_ID + W3C traceparent root.
set -euo pipefail

input="$(cat)"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck source=../../../scripts/lib/agent-turn-usage.sh
source "${ROOT}/scripts/lib/agent-turn-usage.sh"
# shellcheck source=../../../scripts/lib/otel-traceparent.sh
source "${ROOT}/scripts/lib/otel-traceparent.sh"

export ALIYUN_SKILLS_ROOT="${ALIYUN_SKILLS_ROOT:-$ROOT}"
export HARNESS_CODING_AGENT="${HARNESS_CODING_AGENT:-cursor}"

sid="$(agent_turn_resolve_session_id cursor "$input" 2>/dev/null || true)"
if [[ -n "$sid" ]]; then
    export HARNESS_SESSION_ID="$sid"
    ctx="$(agent_turn_context_dir 2>/dev/null || true)"
    if [[ -n "$ctx" ]]; then
        mkdir -p "$ctx" 2>/dev/null || true
        umask 077
        printf '%s\n' "$sid" > "${ctx}/harness-session-id.txt" 2>/dev/null || true
    fi
fi

tp="$(otel_traceparent_resolve_incoming 2>/dev/null || true)"
if [[ -z "$tp" ]]; then
    tp="$(otel_traceparent_generate_root 2>/dev/null || true)"
fi
if [[ -n "$tp" ]]; then
    otel_traceparent_write_sidecar "$tp" 2>/dev/null || true
    export TRACEPARENT="$tp"
fi

# sessionStart: no blocking — allow session to continue
exit 0
