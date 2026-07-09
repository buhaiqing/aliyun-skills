#!/usr/bin/env bash
# Cursor postToolUse / afterMCPExecution — refresh MCP context sidecar for harness.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export ALIYUN_SKILLS_ROOT="${ALIYUN_SKILLS_ROOT:-$ROOT}"
export MCP_CONTEXT_WRITE_SIDECAR=1

input="$(cat)"
hook_dir="$(mktemp -d)"
trap 'rm -rf "$hook_dir"' EXIT
printf '%s' "$input" > "${hook_dir}/hook-post-tool-use.json"

# Best-effort: scan fixture-like hook only; live loaded set comes from mcps/ on probe runs.
bash "${ROOT}/scripts/mcp-context/collect-cursor.sh" --fixture-dir "$hook_dir" >/dev/null 2>&1 || true
exit 0
