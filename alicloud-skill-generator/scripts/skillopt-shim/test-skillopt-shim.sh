#!/bin/bash
# test-skillopt-shim.sh — verify the aliyun-shim intercepts all registered products.
#
# This test does NOT make cloud calls. It invokes a non-existent subcommand
# for each registered product; the wrapper will fail (cloud call), but the
# shim's INTERCEPT log line is what we verify. This proves the routing layer
# works without depending on cloud credentials.
#
# IMPORTANT: We capture output to a file instead of using $(...) command
# substitution, because shell functions are NOT inherited by subshells.
# The shim's aliyun function is defined in THIS shell, not a subshell.
#
# Usage:  ./test-skillopt-shim.sh [product ...]   # default: all registered
# Exit:   0 on all-pass, 1 on any failure.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHIM_PATH="${SCRIPT_DIR}/aliyun-shim.sh"

if [[ ! -f "$SHIM_PATH" ]]; then
  echo "FATAL: shim not found at $SHIM_PATH" >&2
  exit 1
fi

# Use a per-test log file under .runtime so we don't clobber other logs.
REPO_ROOT="${PWD}"
LOG_FILE="${REPO_ROOT}/.runtime/skillopt-shim-test.log"
mkdir -p "$(dirname "$LOG_FILE")"

# IMPORTANT: env vars and source MUST be on separate lines — bash parses
# "VAR=value source script" as "VAR=value runs in source's subshell only".
# shellcheck source=aliyun-shim.sh
SKILLOPT_SHIM_LOG=1
SKILLOPT_SHIM_LOG_FILE="$LOG_FILE"
source "$SHIM_PATH"

# Default: test all products listed in the registry.
ALL_PRODUCTS=(oss ecs rds redis r-kvstore mongodb dds slb vpc ack cs cms)
PRODUCTS=("${@:-${ALL_PRODUCTS[@]}}")

# Verify a passthrough product (not in registry).
PASSTHROUGH_PRODUCTS=(sts ram)

pass=0
fail=0

# Helper: run aliyun in THIS shell, capture stdout+stderr to a file.
# Using a tempfile instead of $(...) because shell functions don't propagate
# to subshells — we need the aliyun function from the sourced shim.
_out_file="$(mktemp)"
_trap_handler() { rm -f "$_out_file"; }
trap _trap_handler EXIT

_run_aliyun() {
  local product="$1"; shift
  > "$_out_file" aliyun "$product" "$@" 2>&1 || true
}

echo "=== INTERCEPT tests (products with wrappers) ==="
for product in "${PRODUCTS[@]}"; do
  : > "$LOG_FILE"
  # Use a non-existent subcommand — wrapper will try to run it, fail, but
  # the shim's INTERCEPT log line is what we verify.
  _run_aliyun "$product" __shim_test_nonexistent__
  if grep -q "INTERCEPT.*product=$product" "$LOG_FILE" \
     && ! grep -q "BYPASS.*product=$product" "$LOG_FILE"; then
    printf '  [PASS] %s → INTERCEPT logged\n' "$product"
    pass=$((pass + 1))
  else
    printf '  [FAIL] %s — no INTERCEPT line in log (or BYPASS was hit instead)\n' "$product"
    fail=$((fail + 1))
  fi
done

echo
echo "=== PASSTHROUGH tests (products without wrappers) ==="
for product in "${PASSTHROUGH_PRODUCTS[@]}"; do
  : > "$LOG_FILE"
  # GetCallerIdentity is a valid STS API; we just check the log routing.
  _run_aliyun "$product" GetCallerIdentity
  if grep -q "PASSTHROUGH.*product=$product" "$LOG_FILE"; then
    printf '  [PASS] %s → PASSTHROUGH logged (no wrapper registered)\n' "$product"
    pass=$((pass + 1))
  else
    printf '  [FAIL] %s — expected PASSTHROUGH, got:\n%s\n' "$product" "$(cat "$_out_file")"
    fail=$((fail + 1))
  fi
done

echo
echo "=== Escape hatch test ==="
# command aliyun must NOT route through the shim.
: > "$LOG_FILE"
> "$_out_file" command aliyun --version 2>&1 || true
if [[ -s "$LOG_FILE" ]]; then
  printf '  [FAIL] command aliyun triggered shim logging (should be silent)\n'
  fail=$((fail + 1))
else
  printf '  [PASS] command aliyun bypasses the shim\n'
  pass=$((pass + 1))
fi

echo
echo "=== Flag-first invocations (documented limitation) ==="
# aliyun --profile prod oss ls must pass through (not intercepted).
: > "$LOG_FILE"
_run_aliyun --profile prod oss ls
if grep -qE "INTERCEPT.*product=oss" "$LOG_FILE"; then
  printf '  [FAIL] flag-first invocation was incorrectly intercepted\n'
  fail=$((fail + 1))
else
  printf '  [PASS] flag-first invocation correctly passes through (documented limit)\n'
  pass=$((pass + 1))
fi

echo
echo "=== Summary ==="
printf '  PASS: %d\n  FAIL: %d\n' "$pass" "$fail"

if [[ $fail -gt 0 ]]; then
  echo
  echo "Log contents (last test run):"
  cat "$LOG_FILE" || true
  exit 1
fi
