#!/usr/bin/env bash
# Orchestrator — five platform MCP context adapter tests (L0+L1).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ALIYUN_SKILLS_ROOT="${ALIYUN_SKILLS_ROOT:-$ROOT}"

echo "=== MCP context adapters (L0 schema + L1 fixtures) ==="
jq -e . "${ROOT}/scripts/lib/mcp-context-schema.json" >/dev/null
bash -n "${ROOT}/scripts/lib/mcp-context-common.sh"

for t in cursor claude-code opencode codebuddy pi; do
    echo "--- test-mcp-context-${t}.sh ---"
    bash "${ROOT}/scripts/test-mcp-context-${t}.sh"
done

echo "=== All MCP context adapter tests passed ==="
