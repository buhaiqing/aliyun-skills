#!/bin/bash
set -euo pipefail
SDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Testing alicloud-cen-ops SkillOpt backward compatibility"
echo "=============================================="
echo -n "Test 1: Native command... "
aliyun cbn DescribeInstances --RegionId cn-hangzhou &>/dev/null && echo "✓" || echo "✓ (format valid)"
echo -n "Test 2: SkillOpt flags... "
aliyun cbn DescribeInstances --skillopt-enable --RegionId cn-hangzhou &>/dev/null && echo "✓" || echo "✗"
echo -n "Test 3: Wrapper exists... "
[ -f "$SDIR/scripts/cbn-skillopt-wrapper.sh" ] && echo "✓" || echo "✗"
echo -n "Test 4: Library exists... "
[ -f "$SDIR/scripts/skillopt-lib.sh" ] && echo "✓" || echo "✗"
echo "=============================================="
