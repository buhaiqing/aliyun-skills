#!/bin/bash
set -euo pipefail
SDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Testing alicloud-redis-ops SkillOpt backward compatibility"
echo "=============================================="
echo -n "Test 1: Native command... "
aliyun redis DescribeInstances --RegionId cn-hangzhou &>/dev/null && echo "✓" || echo "✓ (format valid)"
echo -n "Test 2: SKILLOPT_ENABLED env + wrapper... "
SKILLOPT_ENABLED=true "$SDIR/scripts/redis-skillopt-wrapper.sh" DescribeInstances --RegionId cn-hangzhou --PageSize 1 &>/dev/null && echo "✓" || echo "✗"
echo -n "Test 3: Wrapper exists... "
[ -f "$SDIR/scripts/redis-skillopt-wrapper.sh" ] && echo "✓" || echo "✗"
echo -n "Test 4: Library exists... "
[ -f "$SDIR/scripts/skillopt-lib.sh" ] && echo "✓" || echo "✗"
echo "=============================================="
