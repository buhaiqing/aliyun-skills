#!/bin/bash
# Redis Runtime Harness wrapper
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/harness-lib.sh"

PRODUCT="r-kvstore"
if [[ ${#} -gt 0 && ("$1" == "redis" || "$1" == "redis2" || "$1" == "r-kvstore") ]]; then
    PRODUCT="$1"
    [[ "$PRODUCT" == "redis" ]] && PRODUCT="r-kvstore"
    shift
fi

if [[ "${#}" -lt 1 ]]; then
    echo "Usage: $0 [product] <subcommand> [params]" >&2
    exit 1
fi

SUBCMD="$1"; shift
skillopt_wrap "$PRODUCT" "$SUBCMD" "$@"
