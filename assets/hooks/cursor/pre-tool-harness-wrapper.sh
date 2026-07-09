#!/usr/bin/env bash
# Cursor preToolUse (Shell) — prepend HARNESS_* + W3C TRACEPARENT before harness wrapper commands.
# Matcher in hooks.json.example should target *-harness-wrapper.sh / *-skillopt-wrapper.sh.
set -euo pipefail

input="$(cat)"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck source=../../../scripts/lib/agent-turn-usage.sh
source "${ROOT}/scripts/lib/agent-turn-usage.sh"
# shellcheck source=../../../scripts/lib/otel-traceparent.sh
source "${ROOT}/scripts/lib/otel-traceparent.sh"

export ALIYUN_SKILLS_ROOT="${ALIYUN_SKILLS_ROOT:-$ROOT}"

cmd="$(printf '%s' "$input" | jq -r '.command // .tool_input.command // empty' 2>/dev/null)"
if [[ -z "$cmd" ]]; then
    echo '{"permission":"allow"}'
    exit 0
fi

if ! printf '%s' "$cmd" | grep -qE '(harness-wrapper|skillopt-wrapper)\.sh'; then
    echo '{"permission":"allow"}'
    exit 0
fi

exports=()
exports+=("HARNESS_CODING_AGENT=${HARNESS_CODING_AGENT:-cursor}")

sid="${HARNESS_SESSION_ID:-}"
if [[ -z "$sid" ]]; then
    ctx="$(agent_turn_context_dir 2>/dev/null || true)"
    if [[ -n "$ctx" && -f "${ctx}/harness-session-id.txt" ]]; then
        sid="$(cat "${ctx}/harness-session-id.txt")"
    fi
fi
[[ -n "$sid" ]] && exports+=("HARNESS_SESSION_ID=${sid}")

# X-13: propagate W3C traceparent (child span for this CLI invocation).
incoming_tp="$(otel_traceparent_resolve_incoming 2>/dev/null || true)"
if [[ -n "$incoming_tp" ]]; then
    child_tp="$(otel_traceparent_child "$incoming_tp" 2>/dev/null || true)"
    if [[ -n "$child_tp" ]]; then
        exports+=("TRACEPARENT=${child_tp}")
        if [[ -n "${TRACESTATE:-}" ]]; then
            exports+=("TRACESTATE=${TRACESTATE}")
        fi
    fi
fi

# X-14/X-15: turn-id pointer + optional sidecar (skip usage env for cursor native).
sidecar="$(agent_turn_read_sidecar 2>/dev/null || true)"
turn_id="${HARNESS_AGENT_TURN_ID:-}"
if [[ -z "$turn_id" ]]; then
    turn_id="$(agent_turn_read_current_turn_id 2>/dev/null || true)"
fi
if [[ -n "$turn_id" ]]; then
    exports+=("HARNESS_AGENT_TURN_ID=${turn_id}")
fi

inject_usage_env=true
if [[ -n "$sidecar" ]] && agent_turn_is_cursor_native_source "$sidecar"; then
    inject_usage_env=false
fi
if [[ "${HARNESS_AGENT_TURN_NO_ENV:-}" == "1" ]]; then
    inject_usage_env=false
fi

if [[ "$inject_usage_env" == true && -n "$sidecar" ]]; then
  norm="$(agent_turn_normalize_json "$sidecar" 2>/dev/null || true)"
  if [[ -n "$norm" && "$norm" != "null" ]]; then
    exports+=("HARNESS_AGENT_TURN_USAGE=$(printf '%q' "$norm")")
  fi
fi

prefix=""
if [[ ${#exports[@]} -gt 0 ]]; then
    prefix="$(printf 'export %s; ' "${exports[@]}")"
fi

new_cmd="${prefix}${cmd}"
jq -n --arg cmd "$new_cmd" '{"permission":"allow","updated_input":{"command":$cmd}}'
exit 0
