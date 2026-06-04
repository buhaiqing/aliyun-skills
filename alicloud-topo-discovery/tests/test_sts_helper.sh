#!/bin/bash
# Smoke tests for sts-helper.sh (mocked, no real credentials).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/../scripts" && pwd)"
PASS=0
FAIL=0

test_name() {
    echo -n "[TEST] $1 ... "
}

pass() {
    echo "PASS"
    ((PASS++))
}

fail() {
    echo "FAIL: $1"
    ((FAIL++))
}

# Test 1: No --role-arn exits 0 (normal path)
test_name "no --role-arn exits 0"
bash -c "
    source $SCRIPT_DIR/sts-helper.sh
    exit \$?
" 2>/dev/null && pass || fail "expected exit 0"

# Test 2: Invalid ARN format exits 12
test_name "invalid ARN format exits 12"
env -i \
    ALIBABA_CLOUD_ACCESS_KEY_ID="AK" \
    ALIBABA_CLOUD_ACCESS_KEY_SECRET="SK" \
    bash -c "
    source $SCRIPT_DIR/sts-helper.sh --role-arn 'not-an-arn'
    exit \$?
" 2>/dev/null && fail "expected exit 12" || {
    [[ $? -eq 12 ]] && pass || fail "expected 12, got $?"
}

# Test 3: Missing AK exits 11
test_name "missing AK exits 11"
env -i \
    bash -c "
    source $SCRIPT_DIR/sts-helper.sh --role-arn 'arn:acs:ram::1234:role/Test'
    exit \$?
" 2>/dev/null && fail "expected exit 11" || {
    [[ $? -eq 11 ]] && pass || fail "expected 11, got $?"
}

# Test 4: --session-name and --duration accepted
test_name "--session-name and --duration accepted"
env -i \
    ALIBABA_CLOUD_ACCESS_KEY_ID="AK" \
    ALIBABA_CLOUD_ACCESS_KEY_SECRET="SK" \
    bash -c "
    source $SCRIPT_DIR/sts-helper.sh \
        --role-arn 'arn:acs:ram::1234:role/Test' \
        --session-name 'my-session' \
        --duration 7200
    exit \$?
" 2>/dev/null && fail "expected sts failure (no actual API)" || {
    # sts call should fail since this is a real test environment,
    # but we verify the parsing worked by checking exit code 10 (API failure)
    [[ $? -eq 10 ]] && pass || fail "expected 10 (API), got $?"
}

echo
echo "=== Results: $PASS passed, $FAIL failed ==="
exit $FAIL