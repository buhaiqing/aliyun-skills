#!/usr/bin/env bash
# Refresh MCP sidecar from Cursor mcps/ descriptors (sessionStart or manual).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export ALIYUN_SKILLS_ROOT="${ALIYUN_SKILLS_ROOT:-$ROOT}"
export MCP_CONTEXT_WRITE_SIDECAR=1

bash "${ROOT}/scripts/mcp-context/collect-cursor.sh" --probe >/dev/null 2>&1 || true
exit 0
