#!/usr/bin/env bash
# Unit smoke tests for scripts/skill-change-critic-gate.sh (stdlib + bash only)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GATE="$ROOT/scripts/skill-change-critic-gate.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pass=0
fail=0

assert() {
    local name="$1"
    shift
    if "$@"; then
        echo "  [PASS] $name"
        pass=$((pass + 1))
    else
        echo "  [FAIL] $name" >&2
        fail=$((fail + 1))
    fi
}

echo "=== skill-change-critic-gate.sh smoke tests ==="

assert "bash -n gate script" bash -n "$GATE"

assert "classify exits 0" bash -c "bash \"$GATE\" classify >/dev/null"

# Fixture: tests_accurate=false must fail verify (no --run needed)
BAD="$TMP/bad-verdict.json"
cat >"$BAD" <<'JSON'
{
  "tests_accurate": false,
  "accuracy_rationale": "tests would not catch regression",
  "accuracy_issues": ["missing assertion"],
  "regression_required": true,
  "regression_suites": ["bash -n scripts/skill-change-critic-gate.sh"],
  "regression_rationale": "gate script change"
}
JSON

assert "reject tests_accurate=false" bash -c "! bash \"$GATE\" verify --verdict \"$BAD\""

# Fixture: placeholder rationale must fail
PLACE="$TMP/placeholder.json"
cat >"$PLACE" <<'JSON'
{
  "tests_accurate": true,
  "accuracy_rationale": "REQUIRED: fill me",
  "accuracy_issues": [],
  "regression_required": false,
  "regression_suites": [],
  "regression_rationale": "zero behavioral delta for doc-only"
}
JSON

assert "reject placeholder accuracy_rationale" bash -c "! bash \"$GATE\" verify --verdict \"$PLACE\""

echo "=== Results: $pass passed, $fail failed ==="
[[ $fail -eq 0 ]]
