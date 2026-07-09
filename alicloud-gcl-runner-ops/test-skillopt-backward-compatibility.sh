#!/bin/bash
set -euo pipefail
SDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Testing alicloud-gcl-runner-ops SkillOpt backward compatibility"
echo "=============================================="
echo -n "Test 1: Native gcl_runner.py --help... "
python3 "$SDIR/scripts/gcl_runner.py" --help &>/dev/null && echo "✓" || echo "✗"
echo -n "Test 2: SKILLOPT_ENABLED + wrapper --help... "
SKILLOPT_ENABLED=true "$SDIR/scripts/gcl-runner-skillopt-wrapper.sh" --help &>/dev/null && echo "✓" || echo "✗"
echo -n "Test 3: Wrapper exists... "
[ -f "$SDIR/scripts/gcl-runner-skillopt-wrapper.sh" ] && echo "✓" || echo "✗"
echo -n "Test 4: Library exists... "
[ -f "$SDIR/scripts/skillopt-lib.sh" ] && echo "✓" || echo "✗"
echo -n "Test 5: Sources shared core... "
grep -q 'skillopt-core-lib.sh' "$SDIR/scripts/skillopt-lib.sh" && echo "✓" || echo "✗"
echo -n "Test 6: Python runner override... "
grep -q 'gcl_runner.py' "$SDIR/scripts/skillopt-lib.sh" && echo "✓" || echo "✗"
[ -f "$SDIR/references/skillopt-lib.sh" ] && echo "✗ (stale references/ copy)" || true
echo "=============================================="
