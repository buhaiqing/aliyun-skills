#!/bin/bash
# SAS Runtime Harness wrapper
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/harness-lib.sh"

PRODUCT="sas"
if [[ ${#} -gt 0 && ("$1" == "sas" || "$1" == "sas2") ]]; then
    PRODUCT="$1"
    shift
fi

if [[ "${#}" -lt 1 ]]; then
    echo "Usage: $0 [product] <subcommand> [params]" >&2
    exit 1
fi

SUBCMD="$1"; shift
skillopt_wrap "$PRODUCT" "$SUBCMD" "$@"
