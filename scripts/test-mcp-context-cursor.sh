#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/mcp-context-common.sh
source "${ROOT}/scripts/lib/mcp-context-common.sh"
# shellcheck source=lib/mcp-context-test-lib.sh
source "${ROOT}/scripts/lib/mcp-context-test-lib.sh"

PROBE=false
[[ "${1:-}" == "--probe" ]] && PROBE=true

if $PROBE; then
    bash "${ROOT}/scripts/mcp-context/collect-cursor.sh" --probe
    exit 0
fi

mcp_context_run_l1_suite "cursor" \
    "${ROOT}/scripts/mcp-context/collect-cursor.sh" \
    "${ROOT}/scripts/fixtures/mcp-context/cursor" \
    01-loaded-only 2 0 0 \
    02-invoked-only 0 1 0 \
    03-loaded-and-invoked 2 1 0.5 \
    04-empty-config 0 0 0
