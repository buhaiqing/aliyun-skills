#!/usr/bin/env bash
# TEL Phase 5 — token_rollup.py smoke + fixture integration
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== token_rollup Phase 5 tests ==="
python3 scripts/check_py310_compat.py scripts/token_rollup.py scripts/token_rollup_test.py
(cd scripts && python3 -m unittest token_rollup_test -v)
python3 scripts/token_rollup.py rollup --repo-root "$ROOT" --since-days 7
echo "=== token_rollup tests passed ==="
