#!/bin/bash
# GCL Runner Runtime Harness wrapper — routes to python3 scripts/gcl_runner.py
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GCL_RUNNER_PY="${SCRIPT_DIR}/gcl_runner.py"

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
    echo "[WARN] harness-lib.sh not found — falling back to direct python3 gcl_runner.py" >&2
fi

if [[ ${#} -lt 1 ]]; then
    echo "Usage: $0 <gcl_runner.py flags>" >&2
    echo "Example: $0 --skill alicloud-ecs-ops --op DescribeInstances --command 'aliyun ecs DescribeInstances --PageSize 1' --dry-run" >&2
    exit 1
fi

if [ "$SKILLOPT_LOADED" = true ]; then
    skillopt_wrap "gcl-runner" "run" "$@"
else
    FILTERED_ARGS=()
    for arg in "$@"; do
        case "$arg" in
            --skillopt-*|--harness-*) ;;
            *) FILTERED_ARGS+=("$arg") ;;
        esac
    done
    python3 "$GCL_RUNNER_PY" "${FILTERED_ARGS[@]}"
fi
