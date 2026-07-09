#!/bin/bash
# Legacy shim (Strategy B PR-8) — delegates to canonical harness-paths.sh.
# Prefer: alicloud-runtime-harness-ops/scripts/harness-paths.sh
_harness_shim_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_harness_canonical="${_harness_shim_dir}/../../alicloud-runtime-harness-ops/scripts/harness-paths.sh"
if [[ ! -f "$_harness_canonical" ]]; then
    echo "ERROR: Runtime Harness paths not found: $_harness_canonical" >&2
    return 1 2>/dev/null || exit 1
fi
# shellcheck source=/dev/null
source "$_harness_canonical"
