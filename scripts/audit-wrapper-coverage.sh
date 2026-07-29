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
#   scripts/audit-wrapper-coverage.sh [--strict] [--crosscheck-actiontrail] TRACE_DIR
#
# TRACE_DIR is REQUIRED (no silent repo-wide default). CI MUST pass a FRESH
# trace dir captured for the run under audit -- not the shared/long-lived
# .runtime/traces -- otherwise pre-existing "direct" traces from prior runs
# would permanently fail the build (see MAJOR finding, review round 1).
#
# Modes:
#   default  scan TRACE_DIR; report non-wrapper traces; exit 1 only if a trace
#            is MISSING the invocation block (schema violation). "direct" traces
#            are reported as WARN (observable but intentional bypass) -- they are
#            the gap signal an operator inspects, not a hard CI failure.
#   --strict  exit 1 on ANY non-wrapper trace (missing OR entrypoint=="direct").
#            Use when you want zero bypass tolerance for the audited run.
#
# Exit codes:
#   0  all scanned traces went through the wrapper (or only "direct" in default mode)
#   1  one or more traces violated the wrapper contract (see mode above)
#   2  jq missing, TRACE_DIR missing, or other environment error

set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq is required but not found in PATH" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CROSSCHECK=0
STRICT=0
TRACE_DIR=""
for a in "$@"; do
    case "$a" in
        --crosscheck-actiontrail) CROSSCHECK=1 ;;
        --strict) STRICT=1 ;;
        *) TRACE_DIR="$a" ;;
    esac
done

if [[ -z "$TRACE_DIR" ]]; then
    echo "ERROR: TRACE_DIR is required. Pass a fresh trace dir for the run under audit." >&2
    echo "Usage: scripts/audit-wrapper-coverage.sh [--strict] [--crosscheck-actiontrail] TRACE_DIR" >&2
    exit 2
fi

echo "=== audit-wrapper-coverage.sh ==="
echo "Trace dir: $TRACE_DIR"
echo "Mode: $([[ $STRICT -eq 1 ]] && echo strict || echo default)"

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
missing=0
for f in "${traces[@]}"; do
    entrypoint="$(jq -r '.invocation.entrypoint // empty' "$f" 2>/dev/null || true)"
    tid="$(jq -r '.trace_id // empty' "$f" 2>/dev/null || true)"
    raw="$(jq -r '.invocation.raw_command // empty' "$f" 2>/dev/null || true)"
    if [[ -z "$entrypoint" ]]; then
        # Schema violation: trace without an invocation block. Always a hard fail.
        echo "MISSING-INVOCATION: ${tid:-$f} (no invocation block)"
        bad_list+=("$f")
        bad=$((bad + 1)); missing=$((missing + 1))
    elif [[ "$entrypoint" != "wrapper" ]]; then
        if [[ $STRICT -eq 1 ]]; then
            echo "NON-WRAPPER: ${tid} entrypoint=${entrypoint} raw_command=${raw:-none}"
            bad_list+=("$f")
            bad=$((bad + 1))
        else
            # Intentional bypass (direct) -- observable gap, not a hard CI fail.
            echo "WARN direct (gap signal): ${tid} entrypoint=${entrypoint} raw_command=${raw:-none}"
        fi
    fi
done

echo
echo "Scanned: $total trace files"

if [[ $bad -gt 0 ]]; then
    echo "FAIL: $bad trace(s) not via wrapper (missing invocation=$missing)"
    if [[ $CROSSCHECK -eq 1 ]]; then
        crosscheck_bin="$REPO_ROOT/scripts/gcl-actiontrail-crosscheck"
        if [[ -x "$crosscheck_bin" ]]; then
            echo "Running actiontrail crosscheck on direct traces..."
            "$crosscheck_bin" "${bad_list[@]}" || true
        else
            echo "WARN: --crosscheck-actiontrail set but $crosscheck_bin not found; skipping (optional feature)"
        fi
    fi
    exit 1
fi

if [[ $STRICT -eq 0 ]]; then
    echo "OK: no schema violations (direct traces reported as WARN -- use --strict to hard-fail)"
else
    echo "OK: all traces via wrapper"
fi
exit 0
