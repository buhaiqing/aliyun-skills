#!/usr/bin/env bash
# TEL Phase 5 — token_rollup.py smoke + fixture integration
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== token_rollup golden integration tests (G1-G6) ==="
python3 scripts/check_py310_compat.py scripts/token_rollup.py scripts/token_rollup_golden_test.py
(cd scripts && python3 -m unittest token_rollup_golden_test -v)
python3 scripts/token_rollup.py rollup --repo-root "$ROOT" --since-days 7
echo "=== token_rollup golden tests passed ==="
# NOTE: the broader `token_rollup_test` module has 9 pre-existing failures on
# unmodified HEAD (unrelated to wrapper/4-signal work). Those are tracked as a
# separate legacy issue; the golden suite above is the user-facing regression gate.
