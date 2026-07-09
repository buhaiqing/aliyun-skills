#!/usr/bin/env bash
# E2E: full Layer 3 weekly pipeline (strategy-weekly.yml parity) + cleanup audit.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$ROOT/alicloud-gcl-runner-ops/scripts"

echo "Layer 3 Weekly E2E"
echo "=================="

echo -n "Audit: no SMTP/email leftovers in Layer 3 scripts... "
AUDIT_FILES=(
  "$SCRIPT_DIR/strategy_notify.py"
  "$SCRIPT_DIR/strategy_github_notify.py"
  "$SCRIPT_DIR/gcl_strategy.py"
  "$ROOT/.github/workflows/strategy-weekly.yml"
  "$ROOT/docs/doctor-review-setup.md"
  "$ROOT/.env.example"
)
if rg -i 'smtplib|STRATEGY_SMTP|STRATEGY_NOTIFY_TO|send_email|missing_smtp|163_authorization' \
  "${AUDIT_FILES[@]}" -q 2>/dev/null; then
  echo "FAIL"
  rg -i 'smtplib|STRATEGY_SMTP|STRATEGY_NOTIFY_TO|send_email|missing_smtp|163_authorization' \
    "${AUDIT_FILES[@]}" || true
  exit 1
fi
echo "✓"

echo -n "Test 1: unit + integration suites... "
(
  cd "$SCRIPT_DIR"
  python3 -m unittest gcl_strategy_test strategy_github_integration_test -q
) >/dev/null 2>&1
echo "✓"

echo -n "Test 2: weekly pipeline E2E... "
(
  cd "$SCRIPT_DIR"
  python3 -m unittest strategy_weekly_e2e_test -v
) 
echo "✓"

echo "=================="
echo "E2E passed — GitHub notify pipeline verified; no SMTP remnants in Layer 3."
