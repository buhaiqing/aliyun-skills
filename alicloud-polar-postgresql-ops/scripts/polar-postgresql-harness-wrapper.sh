#!/bin/bash
# Polar-PostgreSQL Runtime Harness wrapper
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
PRODUCT="polardb"
DBTYPE_DEFAULT="PostgreSQL"

# Accept optional leading product token for backward compatibility with prior naming
if [[ ${#} -gt 0 && ("$1" == "polar-postgresql" || "$1" == "polardb" || "$1" == "polardb2") ]]; then
    shift
fi

if [[ "${#}" -lt 1 ]]; then
    echo "Usage: $0 [product] <subcommand> [params]" >&2
    exit 1
fi

SUBCMD="$1"; shift

# The aliyun CLI only ships a single 'polardb' product that covers MySQL/PostgreSQL/Oracle;
# inject --DBType so this PostgreSQL-focused wrapper filters the correct engine.
if [[ -n "$DBTYPE_DEFAULT" ]] && [[ "$SUBCMD" == Describe* || "$SUBCMD" == List* ]]; then
    HAS_DBTYPE=0
    for arg in "$@"; do
        if [[ "$arg" == "--DBType" ]]; then
            HAS_DBTYPE=1
            break
        fi
    done
    if [[ $HAS_DBTYPE -eq 0 ]]; then
        set -- --DBType "$DBTYPE_DEFAULT" "$@"
    fi
fi

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
