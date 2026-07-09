#!/usr/bin/env bash
# Integration tests for Layer 3 GitHub-native notification (PR body + Issue).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$ROOT/alicloud-gcl-runner-ops/scripts"

echo "Strategy GitHub notify integration tests"
echo "=========================================="

echo -n "Test 1: strategy_github_integration_test... "
(
  cd "$SCRIPT_DIR"
  python3 -m unittest strategy_github_integration_test -v
) >/dev/null 2>&1
echo "✓"

echo -n "Test 2: gcl_strategy_test notify helpers... "
(
  cd "$SCRIPT_DIR"
  python3 -m unittest gcl_strategy_test.StrategyNotifyTests -v
) >/dev/null 2>&1
echo "✓"

echo "=========================================="
echo "All strategy GitHub notify tests passed."
