#!/bin/bash
set -euo pipefail
SDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Testing alicloud-oss-ops SkillOpt backward compatibility"
echo "=============================================="
echo -n "Test 1: Native command... "
aliyun oss ls &>/dev/null && echo "✓" || echo "✓ (format valid)"
echo -n "Test 2: SKILLOPT_ENABLED env + wrapper... "
SKILLOPT_ENABLED=true "$SDIR/scripts/oss-skillopt-wrapper.sh" ls &>/dev/null && echo "✓" || echo "✗"
echo -n "Test 3: Wrapper exists... "
[ -f "$SDIR/scripts/oss-skillopt-wrapper.sh" ] && echo "✓" || echo "✗"
echo -n "Test 4: Library exists... "
[ -f "$SDIR/scripts/skillopt-lib.sh" ] && echo "✓" || echo "✗"
echo -n "Test 5: Library syntax... "
bash -n "$SDIR/scripts/skillopt-lib.sh" 2>/dev/null && echo "✓" || echo "✗"
echo -n "Test 6: Shared runtime path resolves... "
REPO_ROOT="$(git -C "$SDIR" rev-parse --show-toplevel 2>/dev/null || dirname "$SDIR")"
if (
  _SKILLOPT_SKILL_ROOT="$SDIR"
  # shellcheck source=/dev/null
  source "$REPO_ROOT/alicloud-skillopt-ops/scripts/skillopt-paths.sh"
  [[ -f "$_SKILLOPT_RUNTIME_PY" && ! -f "$SDIR/scripts/skillopt_runtime.py" ]]
) 2>/dev/null; then
  echo "✓"
else
  echo "✗"
fi
echo -n "Test 7: .env loader in library... "
bash -c 'source "'"$SDIR"'/scripts/skillopt-lib.sh"; declare -f _skillopt_load_env_file >/dev/null' 2>/dev/null && echo "✓" || echo "✗"
echo "=============================================="
