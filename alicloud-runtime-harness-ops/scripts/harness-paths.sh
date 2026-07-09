#!/bin/bash
# Resolve alicloud-runtime-harness-ops shared paths (Strategy B PR-8 canonical).
# Legacy overlays may source via alicloud-skillopt-ops/scripts/skillopt-paths.sh (shim).

: "${_SKILLOPT_SKILL_ROOT:?_SKILLOPT_SKILL_ROOT must be set}"

if [[ -z "${_SKILLOPT_SKILLS_ROOT:-}" ]]; then
    if [[ -n "${ALIYUN_SKILLS_ROOT:-}" ]]; then
        _SKILLOPT_SKILLS_ROOT="$ALIYUN_SKILLS_ROOT"
    else
        _SKILLOPT_SKILLS_ROOT="$(git -C "$_SKILLOPT_SKILL_ROOT" rev-parse --show-toplevel 2>/dev/null || true)"
    fi
    if [[ -z "$_SKILLOPT_SKILLS_ROOT" ]]; then
        _SKILLOPT_SKILLS_ROOT="$(dirname "$_SKILLOPT_SKILL_ROOT")"
    elif [[ ! -d "${_SKILLOPT_SKILLS_ROOT}/alicloud-runtime-harness-ops" \
         && ! -d "${_SKILLOPT_SKILLS_ROOT}/alicloud-skillopt-ops" ]]; then
        _SKILLOPT_SKILLS_ROOT="$(dirname "$_SKILLOPT_SKILL_ROOT")"
    fi
fi

if [[ -n "${HARNESS_SHARED_ROOT:-}" && -f "${HARNESS_SHARED_ROOT}/scripts/harness-core-lib.sh" ]]; then
    _HARNESS_SHARED_ROOT="$HARNESS_SHARED_ROOT"
elif [[ -f "${_SKILLOPT_SKILLS_ROOT}/alicloud-runtime-harness-ops/scripts/harness-core-lib.sh" ]]; then
    _HARNESS_SHARED_ROOT="${_SKILLOPT_SKILLS_ROOT}/alicloud-runtime-harness-ops"
else
    _HARNESS_SHARED_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

_HARNESS_RUNTIME_PY="${_HARNESS_SHARED_ROOT}/scripts/harness_runtime.py"
_SKILLOPT_RUNTIME_PY="${_HARNESS_RUNTIME_PY}"
_SKILLOPT_SHARED_ROOT="${_SKILLOPT_SHARED_ROOT:-${_SKILLOPT_SKILLS_ROOT}/alicloud-skillopt-ops}"

if [[ ! -f "$_HARNESS_RUNTIME_PY" ]]; then
    echo "ERROR: Runtime Harness runtime not found: $_HARNESS_RUNTIME_PY" >&2
    return 1 2>/dev/null || exit 1
fi

# Resolve repo-centralized observability paths (AGENTS.md §13).
# Override/test: ALIBABA_CLOUD_RUNTIME_DIR keeps flat layout under a custom dir.
_skillopt_init_runtime_paths() {
    if [[ -n "${ALIBABA_CLOUD_RUNTIME_DIR:-}" ]]; then
        _SKILLOPT_RUNTIME_ROOT="$ALIBABA_CLOUD_RUNTIME_DIR"
        _SKILLOPT_TRACE_DIR="${_SKILLOPT_TRACE_DIR:-${_SKILLOPT_RUNTIME_ROOT}/traces}"
        _SKILLOPT_SESSIONS_DIR="${_SKILLOPT_SESSIONS_DIR:-${_SKILLOPT_RUNTIME_ROOT}}"
        _SKILLOPT_LOGS_DIR="${_SKILLOPT_LOGS_DIR:-${_SKILLOPT_RUNTIME_ROOT}}"
        _SKILLOPT_METRICS_DATA_DIR="${_SKILLOPT_METRICS_DATA_DIR:-${_SKILLOPT_RUNTIME_ROOT}}"
        return 0
    fi

    if [[ -n "${ALIYUN_SKILLS_RUNTIME_ROOT:-}" ]]; then
        _SKILLOPT_RUNTIME_ROOT="$ALIYUN_SKILLS_RUNTIME_ROOT"
    else
        _SKILLOPT_RUNTIME_ROOT="${_SKILLOPT_SKILLS_ROOT}/.runtime"
    fi

    local skill_tag="${SKILLOPT_SKILL_TAG:-unknown-skill}"
    _SKILLOPT_TRACE_DIR="${_SKILLOPT_TRACE_DIR:-${_SKILLOPT_RUNTIME_ROOT}/traces/${skill_tag}}"
    _SKILLOPT_SESSIONS_DIR="${_SKILLOPT_SESSIONS_DIR:-${_SKILLOPT_RUNTIME_ROOT}/sessions/${skill_tag}}"
    _SKILLOPT_LOGS_DIR="${_SKILLOPT_LOGS_DIR:-${_SKILLOPT_RUNTIME_ROOT}/logs/${skill_tag}}"
    _SKILLOPT_METRICS_DATA_DIR="${_SKILLOPT_METRICS_DATA_DIR:-${_SKILLOPT_RUNTIME_ROOT}/metrics/${skill_tag}}"
}

_skillopt_init_runtime_paths
