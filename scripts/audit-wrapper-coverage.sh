#!/bin/bash
# scripts/audit-wrapper-coverage.sh
#
# Runtime audit (layer 2 closure): scan emitted trace files and report any trace
# that did NOT go through the Runtime Harness wrapper -- i.e. traces missing the
# invocation block, or whose invocation.entrypoint != "wrapper".
#
# Every aliyun call should be observable and, when routed through the wrapper,
# carry invocation.entrypoint == "wrapper". Bypassed ("direct") calls are emitted
# by skillopt_run_aliyun's guard-refusal path and are surfaced here so CI can
# fail the build (or an operator can inspect which commands escaped the wrapper).
#
# Usage:
#   scripts/audit-wrapper-coverage.sh [TRACE_DIR]
#   TRACE_DIR defaults to ${SKILLS_DIR:-.}/.runtime/traces
#
# Exit codes:
#   0  all scanned traces went through the wrapper
#   1  one or more traces are not via wrapper (direct / missing invocation)
#   2  jq missing or other environment error

set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq is required but not found in PATH" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CROSSCHECK=0
TRACE_DIR=""
for a in "$@"; do
    case "$a" in
        --crosscheck-actiontrail) CROSSCHECK=1 ;;
        *) TRACE_DIR="$a" ;;
    esac
done

if [[ -z "$TRACE_DIR" ]]; then
    TRACE_DIR="${SKILLS_DIR:-$REPO_ROOT}/.runtime/traces"
fi

echo "=== audit-wrapper-coverage.sh ==="
echo "Trace dir: $TRACE_DIR"
echo

if [[ ! -d "$TRACE_DIR" ]]; then
    echo "WARN: trace dir not found -- nothing to audit."
    exit 0
fi

traces=()
while IFS= read -r f; do
    [[ -n "$f" ]] && traces+=("$f")
done < <(find "$TRACE_DIR" -type f -name 'trace-*.json' 2>/dev/null | sort -u)

total=${#traces[@]}

if [[ $total -eq 0 ]]; then
    echo "OK: no traces found to audit"
    exit 0
fi

bad=0
bad_list=()
for f in "${traces[@]}"; do
    entrypoint="$(jq -r '.invocation.entrypoint // empty' "$f" 2>/dev/null || true)"
    if [[ -z "$entrypoint" || "$entrypoint" != "wrapper" ]]; then
        tid="$(jq -r '.trace_id // empty' "$f" 2>/dev/null || true)"
        raw="$(jq -r '.invocation.raw_command // empty' "$f" 2>/dev/null || true)"
        echo "NON-WRAPPER: ${tid} entrypoint=${entrypoint:-missing} raw_command=${raw:-none}"
        bad_list+=("$f")
        bad=$((bad + 1))
    fi
done

echo
echo "Scanned: $total trace files"

if [[ $bad -gt 0 ]]; then
    echo "FAIL: $bad trace(s) not via wrapper"
    if [[ $CROSSCHECK -eq 1 ]]; then
        crosscheck_bin="$REPO_ROOT/scripts/gcl-actiontrail-crosscheck"
        if [[ -x "$crosscheck_bin" ]]; then
            echo "Running actiontrail crosscheck on direct traces..."
            "$crosscheck_bin" "${bad_list[@]}" || true
        else
            echo "WARN: --crosscheck-actiontrail set but $crosscheck_bin not found"
        fi
    fi
    exit 1
fi

echo "OK: all traces via wrapper"
exit 0
