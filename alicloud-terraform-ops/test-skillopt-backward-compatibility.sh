#!/bin/bash
set -euo pipefail
SDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ALIYUN_SKILLS_ROOT="${ALIYUN_SKILLS_ROOT:-$(git -C "$SDIR" rev-parse --show-toplevel 2>/dev/null || dirname "$SDIR")}"

echo "Testing alicloud-terraform-ops SkillOpt backward compatibility"
echo "=============================================="
echo -n "Test 1: No aliyun terraform product (IaC via terraform CLI)... "
if aliyun terraform GetProvider &>/dev/null; then
  echo "✓ (CLI unexpectedly available)"
else
  echo "✓ (expected — use terraform binary + Python scripts)"
fi
echo -n "Test 2: Harness wrapper bash syntax... "
bash -n "$SDIR/scripts/terraform-harness-wrapper.sh" && echo "✓" || echo "✗"
echo -n "Test 2b: Legacy skillopt shim delegates... "
grep -q 'terraform-harness-wrapper.sh' "$SDIR/scripts/terraform-skillopt-wrapper.sh" && echo "✓" || echo "✗"
echo -n "Test 3: Harness wrapper exists... "
[ -f "$SDIR/scripts/terraform-harness-wrapper.sh" ] && echo "✓" || echo "✗"
echo -n "Test 3b: Legacy skillopt shim exists... "
[ -f "$SDIR/scripts/terraform-skillopt-wrapper.sh" ] && echo "✓" || echo "✗"
echo -n "Test 4: harness-lib.sh exists... "
[ -f "$SDIR/scripts/harness-lib.sh" ] && echo "✓" || echo "✗"
echo -n "Test 4b: legacy skillopt-lib.sh symlink... "
[ -L "$SDIR/scripts/skillopt-lib.sh" ] && echo "✓" || echo "✗"
echo -n "Test 5: Sources shared core... "
grep -qE 'skillopt-core-lib\.sh|harness-core-lib\.sh' "$SDIR/scripts/harness-lib.sh" && echo "✓" || echo "✗"
echo -n "Test 6: SKILLOPT_SKILL_TAG... "
grep -q 'SKILLOPT_SKILL_TAG="alicloud-terraform-ops"' "$SDIR/scripts/harness-lib.sh" && echo "✓" || echo "✗"
echo -n "Test 7: Integration doc exists... "
[ -f "$SDIR/references/skillopt-integration.md" ] && echo "✓" || echo "✗"
[ -f "$SDIR/references/skillopt-lib.sh" ] && echo "✗ (stale references/ copy)" || true
echo "=============================================="
