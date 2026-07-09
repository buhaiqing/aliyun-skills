#!/bin/bash
# Legacy skillopt wrapper (Strategy B PR-6) — delegates to canonical harness wrapper.
# Prefer: alb-harness-wrapper.sh
set -euo pipefail
_canonical="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/alb-harness-wrapper.sh"
if [[ ! -f "$_canonical" ]]; then
    echo "[ERROR] Harness wrapper missing: $_canonical" >&2
    exit 2
fi
exec "$_canonical" "$@"
