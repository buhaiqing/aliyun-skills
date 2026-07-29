#!/bin/bash
# scripts/test-wrapper-first-integration.sh
#
# Integration test (Generator GCL gate): invoke a REAL product wrapper and
# assert the produced trace carries all 4 mandatory signals:
#   trace_id, session_id, user_id, llm_usage{prompt,completion,total}
#
# The wrapper writes its trace file in skillopt_trace_start() BEFORE the
# credential-gated `aliyun` call (see harness-core-lib.sh: skillopt_wrap ->
# skillopt_trace_start at line 1960, then skillopt_run_aliyun at line 1984).
# Therefore a trace is produced even when `aliyun` is absent/unauthenticated.
#
# We run against an isolated temp copy of the repo so we never touch the
# real .runtime tree, and we drive the canonical ECS wrapper directly.
#
# Exit codes:
#   0  all 4 signals present
#   1  one or more signals missing / trace not produced
#   2  usage / environment error

set -uo pipefail

# ---------- locate repo ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

command -v jq >/dev/null 2>&1 || { echo "ERROR: jq is required but not found" >&2; exit 2; }

WRAPPER="$REPO_ROOT/alicloud-ecs-ops/scripts/ecs-harness-wrapper.sh"
[[ -f "$WRAPPER" ]] || { echo "ERROR: wrapper not found: $WRAPPER" >&2; exit 2; }

# ---------- isolated temp repo copy ----------
WORK="$(mktemp -d "${TMPDIR:-/tmp}/wrapper-first-int.XXXXXX")"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

# Copy only what the wrapper + shared core needs to resolve paths.
# harness-lib.sh resolves _SKILLOPT_SKILL_ROOT via its own dir, and the
# shared core via ALIYUN_SKILLS_ROOT, so we copy the two relevant skills.
mkdir -p "$WORK/alicloud-ecs-ops/scripts" "$WORK/alicloud-skillopt-ops/scripts" \
         "$WORK/alicloud-runtime-harness-ops/scripts" "$WORK/alicloud-gcl-runner-ops/scripts"

cp -R "$REPO_ROOT/alicloud-ecs-ops/scripts/."        "$WORK/alicloud-ecs-ops/scripts/"
cp -R "$REPO_ROOT/alicloud-skillopt-ops/scripts/."    "$WORK/alicloud-skillopt-ops/scripts/"
cp -R "$REPO_ROOT/alicloud-runtime-harness-ops/scripts/." "$WORK/alicloud-runtime-harness-ops/scripts/"
# gcl-runner scripts are referenced lazily (memory/reflexion) but ignored if missing.
[[ -d "$REPO_ROOT/alicloud-gcl-runner-ops/scripts" ]] && \
    cp -R "$REPO_ROOT/alicloud-gcl-runner-ops/scripts/." "$WORK/alicloud-gcl-runner-ops/scripts/" 2>/dev/null || true

# ---------- drive the wrapper ----------
export ALIYUN_SKILLS_ROOT="$WORK"
export HARNESS_SESSION_ID="integration-test-session"
export HARNESS_USER_ID="integration-test-user"
# Keep the trace under our isolated copy; disable Langfuse/cred-gated noise.
export SKILLOPT_LANGFUSE_ENABLED=false
export SKILLOPT_ENABLED=false
# Make `aliyun` a no-op that fails loudly so we PROVE the trace is written
# regardless of credentials. If a real aliyun exists on PATH it will simply
# fail (no creds) — either way the trace must already be on disk.
if ! command -v aliyun >/dev/null 2>&1; then
    aliyun() { echo "aliyun stub: would call $*" >&2; return 1; }
    export -f aliyun
fi

WRAPPER_COPY="$WORK/alicloud-ecs-ops/scripts/ecs-harness-wrapper.sh"
# Suppress the wrapper's aliyun payload from stdout (noisy); the trace file is
# what we assert on. A non-zero exit (no creds) is expected and harmless.
"$WRAPPER_COPY" DescribeInstances --RegionId cn-hangzhou >/dev/null 2>&1 || \
    echo "[note] wrapper exited non-zero (expected: no aliyun creds) — trace check continues" >&2

# ---------- find newest trace ----------
TRACE_DIR="$WORK/.runtime/traces/alicloud-ecs-ops"
if [[ ! -d "$TRACE_DIR" ]]; then
    echo "FAIL: trace directory not created: $TRACE_DIR" >&2
    exit 1
fi

TRACE_FILE="$(ls -t "$TRACE_DIR"/trace-*.json 2>/dev/null | head -n 1)"
if [[ -z "$TRACE_FILE" ]]; then
    echo "FAIL: no trace-*.json produced under $TRACE_DIR" >&2
    exit 1
fi
echo "==> trace produced: $TRACE_FILE"

# ---------- assert 4 signals ----------
fail=0

check() {
    local label="$1" ok="$2"
    if [[ "$ok" == true ]]; then
        echo "PASS: $label"
    else
        echo "FAIL: $label"
        fail=1
    fi
}

tid="$(jq -r '.trace_id // ""' "$TRACE_FILE")"
check "trace_id non-empty" "$([[ -n "$tid" ]] && echo true || echo false)"

sid="$(jq -r '.session_id // ""' "$TRACE_FILE")"
check "session_id non-empty" "$([[ -n "$sid" ]] && echo true || echo false)"

uid="$(jq -r '.user_id // ""' "$TRACE_FILE")"
check "user_id non-empty" "$([[ -n "$uid" ]] && echo true || echo false)"

lu="$(jq -c '.llm_usage // null' "$TRACE_FILE")"
if [[ "$lu" == "null" ]]; then
    check "llm_usage object present" false
else
    pt="$(jq -r '.llm_usage.prompt_tokens // -1' "$TRACE_FILE")"
    ct="$(jq -r '.llm_usage.completion_tokens // -1' "$TRACE_FILE")"
    tt="$(jq -r '.llm_usage.total_tokens // -1' "$TRACE_FILE")"
    if [[ "$pt" =~ ^[0-9]+$ && "$ct" =~ ^[0-9]+$ && "$tt" =~ ^[0-9]+$ ]]; then
        check "llm_usage{prompt=$pt,completion=$ct,total=$tt} present (>=0)" true
    else
        check "llm_usage numeric fields present" false
    fi
fi

if [[ "$fail" -ne 0 ]]; then
    echo "=== wrapper-first integration test FAILED ===" >&2
    exit 1
fi

echo "=== wrapper-first integration test PASSED (4/4 signals) ==="
exit 0
