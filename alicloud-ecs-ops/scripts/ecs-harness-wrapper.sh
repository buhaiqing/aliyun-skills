#!/bin/bash
# ECS Runtime Harness wrapper
# Graceful fallback: sources harness-lib.sh if available, falls back to direct aliyun CLI.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SKILLOPT_LOADED=false
if [ -f "$SCRIPT_DIR/harness-lib.sh" ]; then
    # shellcheck source=harness-lib.sh
    source "$SCRIPT_DIR/harness-lib.sh"
    SKILLOPT_LOADED=true
elif [ -f "$SCRIPT_DIR/skillopt-lib.sh" ]; then
    # shellcheck source=skillopt-lib.sh
    source "$SCRIPT_DIR/skillopt-lib.sh"
    SKILLOPT_LOADED=true
else
    echo "[WARN] harness-lib.sh not found at $SCRIPT_DIR — falling back to direct aliyun CLI" >&2
fi

PRODUCT="ecs"
if [[ ${#} -gt 0 && ("$1" == "ecs" || "$1" == "ecs2") ]]; then
    PRODUCT="$1"
    shift
fi

if [[ "${#}" -lt 1 ]]; then
    echo "Usage: $0 [product] <subcommand> [params]" >&2
    exit 1
fi

SUBCMD="$1"; shift

if [ "$SKILLOPT_LOADED" = true ]; then
    skillopt_wrap "$PRODUCT" "$SUBCMD" "$@"
else
    # Fallback used only when harness-lib.sh could not be sourced (last resort).
    # If the core lib was somehow sourced but skillopt_wrap is unavailable, route
    # through skillopt_run_aliyun so the call stays observable + guard-enforced;
    # otherwise call aliyun directly.
    FILTERED_ARGS=()
    for arg in "$@"; do
        case "$arg" in
            --skillopt-*|--harness-*) ;;
            *) FILTERED_ARGS+=("$arg") ;;
        esac
    done
    if declare -F skillopt_run_aliyun >/dev/null 2>&1; then
        skillopt_run_aliyun "$PRODUCT" "$SUBCMD" "${FILTERED_ARGS[@]}"
    else
        aliyun "$PRODUCT" "$SUBCMD" "${FILTERED_ARGS[@]}"
    fi
fi
