#!/bin/bash
# CMS Runtime Harness wrapper
# Graceful fallback: sources harness-lib.sh if available, falls back to direct aliyun CLI.
# Usage: cms-harness-wrapper.sh [cms|cms2] <CMS-subcommand> [aliyun-params...] [--skillopt-* flags]
# Example:
#   ./cms-harness-wrapper.sh DescribeMetricList --skillopt-enable \
#       --Namespace acs_ecs_dashboard --MetricName CPUUtilization \
#       --Dimensions '[{"instanceId":"i-abc123"}]'

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SKILLOPT_LOADED=false
if [ -f "$SCRIPT_DIR/harness-lib.sh" ]; then
    # shellcheck source=harness-lib.sh
    source "$SCRIPT_DIR/harness-lib.sh"
    SKILLOPT_LOADED=true
elif [ -f "$SCRIPT_DIR/skillopt-lib.sh" ]; then
    # shellcheck source=skillopt-lib.sh
    source "$SCRIPT_DIR/skillopt-lib.sh"
    SKILLOPT_LOADED=true
else
    echo "[WARN] harness-lib.sh not found at $SCRIPT_DIR — falling back to direct aliyun CLI" >&2
fi

CMS_PRODUCT="cms"
if [[ $# -gt 0 && ("$1" == "cms" || "$1" == "cms2") ]]; then
    CMS_PRODUCT="$1"
    shift
fi

if [[ "${#}" -lt 1 ]]; then
    cat >&2 <<'EOF'
Usage: cms-harness-wrapper.sh [cms|cms2] <CMS-subcommand> [aliyun-params...] [--skillopt-* flags]

Runtime Harness / SkillOpt flags (stripped before calling aliyun):
  --skillopt-enable          Enable self-repair and dynamic optimization (default: off)
  --skillopt-disable         Disable Runtime Harness self-repair
  --skillopt-report          Output Markdown operations summary (no CLI call)
  --skillopt-log-file PATH   Override log file path
  --skillopt-retries N       Max repair retries (default: 3)
  --skillopt-backoff "1 2 4" Backoff seconds between retries

Example:
  ./cms-harness-wrapper.sh DescribeMetricList --skillopt-enable \
      --Namespace acs_ecs_dashboard --MetricName CPUUtilization --Period 60 \
      --Dimensions '[{"instanceId":"i-abc123"}]'

  # Wrap cms2 commands
  ./cms-harness-wrapper.sh cms2 DescribeMetricList --skillopt-enable \
      --Namespace acs_ecs_dashboard --MetricName CPUUtilization --Period 60 \
      --Dimensions '[{"instanceId":"i-abc123"}]'

  # Generate operations report
  ./cms-harness-wrapper.sh report --skillopt-report
EOF
    exit 1
fi

CMS_SUBCMD="$1"; shift

if [ "$SKILLOPT_LOADED" = true ]; then
    skillopt_wrap "$CMS_PRODUCT" "$CMS_SUBCMD" "$@"
else
    FILTERED_ARGS=()
    for arg in "$@"; do
        case "$arg" in
            --skillopt-*|--harness-*) ;;
            *) FILTERED_ARGS+=("$arg") ;;
        esac
    done
    aliyun "$CMS_PRODUCT" "$CMS_SUBCMD" "${FILTERED_ARGS[@]}"
fi
