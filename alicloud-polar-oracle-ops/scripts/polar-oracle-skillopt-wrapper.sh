#!/bin/bash
# Legacy skillopt wrapper (Strategy B PR-6) — delegates to canonical harness wrapper.
# Prefer: polar-oracle-harness-wrapper.sh
set -euo pipefail
_canonical="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/polar-oracle-harness-wrapper.sh"
if [[ ! -f "$_canonical" ]]; then
    echo "[ERROR] Harness wrapper missing: $_canonical" >&2
    exit 2
fi
exec "$_canonical" "$@"
