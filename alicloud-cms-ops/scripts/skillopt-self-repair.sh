#!/bin/bash
# Legacy entry point — delegates to cms-harness-wrapper.sh with SkillOpt enabled.
# Prefer: ./cms-harness-wrapper.sh <action> --skillopt-enable [params...]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${#}" -lt 1 ]]; then
    echo "Usage: $0 <CMS-action> [aliyun-params...]" >&2
    echo "       $0 cms <CMS-action> [aliyun-params...]  # legacy form" >&2
    echo "Example: $0 DescribeMetricList --Namespace acs_ecs_dashboard --MetricName CPUUtilization" >&2
    exit 1
fi

if [[ "${1:-}" == "cms" ]]; then
    shift
fi

exec "$SCRIPT_DIR/cms-harness-wrapper.sh" "$@" --skillopt-enable
