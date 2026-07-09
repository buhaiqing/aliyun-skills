#!/bin/bash
# SkillOpt Wrapper
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
PRODUCT="fc"

if [[ ${#} -gt 0 && ("$1" == "$PRODUCT" || "$1" == "${PRODUCT}2") ]]; then
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
    FILTERED_ARGS=()
    for arg in "$@"; do
        case "$arg" in
            --skillopt-*|--harness-*) ;;
            *) FILTERED_ARGS+=("$arg") ;;
        esac
    done
    aliyun "$PRODUCT" "$SUBCMD" "${FILTERED_ARGS[@]}"
fi
