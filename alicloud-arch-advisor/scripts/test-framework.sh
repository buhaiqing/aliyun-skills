#!/bin/bash
# alicloud-arch-advisor - Unit Test Framework
# Lightweight Bash testing utility
# Usage: source test-framework.sh; test_init; test_xxx; test_summary

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Current test info
CURRENT_TEST=""
TEST_FAILED=false

# Colors
TEST_RED='\033[0;31m'
TEST_GREEN='\033[0;32m'
TEST_YELLOW='\033[1;33m'
TEST_BLUE='\033[0;34m'
TEST_CYAN='\033[0;36m'
TEST_NC='\033[0m'

# Initialize test framework
test_init() {
    TESTS_RUN=0
    TESTS_PASSED=0
    TESTS_FAILED=0
    TESTS_SKIPPED=0
    echo -e "${TEST_CYAN}════════════════════════════════════════════════════${TEST_NC}"
    echo -e "${TEST_CYAN}       alicloud-arch-advisor Unit Tests${TEST_CYAN}"
    echo -e "${TEST_CYAN}════════════════════════════════════════════════════${TEST_NC}"
    echo ""
}

# Start a test
# Usage: test_start "test_name"
test_start() {
    CURRENT_TEST="$1"
    TEST_FAILED=false
    echo -ne "${TEST_BLUE}  ▸ ${CURRENT_TEST}${TEST_NC} ... "
}

# Assertion: equal
# Usage: assert_equals "expected" "actual" [message]
assert_equals() {
    local expected="$1"
    local actual="$2"
    local message="${3:-}"

    if [[ "$expected" == "$actual" ]]; then
        return 0
    else
        TEST_FAILED=true
        echo ""
        echo -e "${TEST_RED}    ✗ FAILED${TEST_NC}"
        echo "    Expected: '$expected'"
        echo "    Actual:   '$actual'"
        [[ -n "$message" ]] && echo "    Message:  $message"
        return 1
    fi
}

# Assertion: not equal
# Usage: assert_not_equals "unexpected" "actual"
assert_not_equals() {
    local unexpected="$1"
    local actual="$2"

    if [[ "$unexpected" != "$actual" ]]; then
        return 0
    else
        TEST_FAILED=true
        echo ""
        echo -e "${TEST_RED}    ✗ FAILED${TEST_NC}"
        echo "    Unexpected: '$unexpected'"
        echo "    Actual:     '$actual'"
        return 1
    fi
}

# Assertion: contains
# Usage: assert_contains "substring" "string"
assert_contains() {
    local substring="$1"
    local string="$2"

    if [[ "$string" == *"$substring"* ]]; then
        return 0
    else
        TEST_FAILED=true
        echo ""
        echo -e "${TEST_RED}    ✗ FAILED${TEST_NC}"
        echo "    String:    '$string'"
        echo "    Should contain: '$substring'"
        return 1
    fi
}

# Assertion: not empty
# Usage: assert_not_empty "value" [message]
assert_not_empty() {
    local value="$1"
    local message="${2:-}"

    if [[ -n "$value" && "$value" != "null" ]]; then
        return 0
    else
        TEST_FAILED=false  # Don't set failed, just report
        echo ""
        echo -e "${TEST_YELLOW}    ⚠ EMPTY${TEST_NC}"
        [[ -n "$message" ]] && echo "    Message: $message"
        return 1
    fi
}

# Assertion: success (exit code 0)
# Usage: assert_success [message]
assert_success() {
    local message="${1:-Command should succeed}"

    if [[ $? -eq 0 ]]; then
        return 0
    else
        TEST_FAILED=true
        echo ""
        echo -e "${TEST_RED}    ✗ FAILED${TEST_NC}"
        echo "    Message: $message"
        return 1
    fi
}

# End a test
# Usage: test_end
test_end() {
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "$TEST_FAILED" == "true" ]]; then
        TESTS_FAILED=$((TESTS_FAILED + 1))
        # Error already printed
    else
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo -e "${TEST_GREEN}✓${TEST_NC}"
    fi
}

# Skip a test
# Usage: test_skip "reason"
test_skip() {
    local reason="$1"
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
    echo -e "${TEST_YELLOW}⊘ SKIP${TEST_NC} ($reason)"
}

# Print test summary
# Usage: test_summary
test_summary() {
    local pass_rate=0
    if [[ $TESTS_RUN -gt 0 ]]; then
        pass_rate=$(( (TESTS_PASSED * 100) / TESTS_RUN ))
    fi

    echo ""
    echo -e "${TEST_CYAN}════════════════════════════════════════════════════${TEST_NC}"
    echo -e "${TEST_CYAN}                   Test Summary${TEST_CYAN}"
    echo -e "${TEST_CYAN}════════════════════════════════════════════════════${TEST_NC}"
    echo ""
    echo -e "  Total:  ${TEST_BLUE}${TESTS_RUN}${TEST_NC}"
    echo -e "  Passed: ${TEST_GREEN}${TESTS_PASSED}${TEST_NC}"
    echo -e "  Failed: ${TEST_RED}${TESTS_FAILED}${TEST_NC}"
    echo -e "  Skipped: ${TEST_YELLOW}${TESTS_SKIPPED}${TEST_NC}"
    echo -e "  Pass rate: ${pass_rate}%"
    echo ""

    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "${TEST_GREEN}✅ All tests passed!${TEST_NC}"
        return 0
    else
        echo -e "${TEST_RED}❌ Some tests failed.${TEST_NC}"
        return 1
    fi
}

# Export functions
export -f test_init
export -f test_start
export -f assert_equals
export -f assert_not_equals
export -f assert_contains
export -f assert_not_empty
export -f assert_success
export -f test_end
export -f test_skip
export -f test_summary
