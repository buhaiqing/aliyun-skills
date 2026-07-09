#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT}/scripts/lib/mcp-context-common.sh"
source "${ROOT}/scripts/lib/mcp-context-test-lib.sh"

[[ "${1:-}" == "--probe" ]] && exec bash "${ROOT}/scripts/mcp-context/collect-opencode.sh" --probe

mcp_context_run_l1_suite "opencode" \
    "${ROOT}/scripts/mcp-context/collect-opencode.sh" \
    "${ROOT}/scripts/fixtures/mcp-context/opencode" \
    01-loaded-only 2 0 0 \
    02-invoked-only 0 1 0 \
    03-loaded-and-invoked 2 1 0.5 \
    04-empty-config 0 0 0
