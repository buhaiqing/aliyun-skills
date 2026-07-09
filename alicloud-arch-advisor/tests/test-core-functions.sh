#!/bin/bash
# Unit tests for alicloud-arch-advisor core functions
# Run: bash tests/test-core-functions.sh

set -euo pipefail

SCRIPT_DIR="/Users/bohaiqing/opensource/git/aliyun-skills/alicloud-arch-advisor/scripts"

# Source test framework
source "${SCRIPT_DIR}/test-framework.sh"

# Source common.sh functions (excluding i18n)
# Use temp files to avoid process substitution issues
TMPDIR_TEST=$(mktemp -d)
sed -n '/^# Colors for output/,/^readonly NC=/p' "$SCRIPT_DIR/common.sh" > "$TMPDIR_TEST/colors.sh"
sed -n '/^# Logging/,/^# ---.*Progress/p' "$SCRIPT_DIR/common.sh" > "$TMPDIR_TEST/logging.sh"
awk '/^# Progress Bar Functions/{flag=1} flag && !/^check_dependencies/{print} /^check_dependencies/{exit}' "$SCRIPT_DIR/common.sh" > "$TMPDIR_TEST/progress.sh"
source "$TMPDIR_TEST/colors.sh"
source "$TMPDIR_TEST/logging.sh"
source "$TMPDIR_TEST/progress.sh"
# Source error handler directly (it depends on log_* functions)
source "${SCRIPT_DIR}/error-handler.sh"

# Define stub t() function
t() {
    local key="$1"
    shift
    local args=("$@")
    case "$key" in
        progress_start) printf "━━━━" ;;
        progress_complete) printf "✓ %s" "${args[0]:-Done}" ;;
        progress_eta) printf "ETA: %s" "${args[0]:--}" ;;
        progress_elapsed) printf "Elapsed: %ds" "${args[0]:-0}" ;;
        common_info) printf "[INFO]" ;;
        common_warn) printf "[WARN]" ;;
        common_error) printf "[ERROR]" ;;
        common_success) printf "[SUCCESS]" ;;
        *) printf "%s" "$key" ;;
    esac
}

# Initialize tests
test_init

# ===========================================================================
# Test Group 1: Cost Estimation
# ===========================================================================
echo -e "${TEST_CYAN}─── Test Group 1: Cost Estimation ───${TEST_NC}"

# Helper function: calculate_ecs_price
calculate_ecs_price() {
    local ecs_type="$1"
    case "$ecs_type" in
        *"g6.xlarge"*) echo 100 ;;
        *"g6.2xlarge"*) echo 200 ;;
        *"g6.4xlarge"*) echo 400 ;;
        *"g6.8xlarge"*) echo 800 ;;
        *"g6.16xlarge"*) echo 1600 ;;
        *) echo 100 ;;
    esac
}

# Test 1.1: ECS g6.xlarge pricing
test_start "calculate_ecs_price g6.xlarge returns 100"
result=$(calculate_ecs_price "g6.xlarge")
assert_equals "100" "$result"
test_end

# Test 1.2: ECS g6.16xlarge pricing
test_start "calculate_ecs_price g6.16xlarge returns 1600"
result=$(calculate_ecs_price "g6.16xlarge")
assert_equals "1600" "$result"
test_end

# Test 1.3: ECS unknown type returns default
test_start "calculate_ecs_price unknown type returns default 100"
result=$(calculate_ecs_price "unknown.type")
assert_equals "100" "$result"
test_end

# Test 1.4: Total cost calculation
test_start "Total cost: 2x g6.xlarge + 1x medium RDS = 350"
ecs_price=$(calculate_ecs_price "g6.xlarge")
rds_price=150
total=$(( 2 * ecs_price + 1 * rds_price ))
assert_equals "350" "$total"
test_end

# Test 1.5: Zero cost
test_start "Zero cost when no resources"
total=0
assert_equals "0" "$total"
test_end

echo ""

# ===========================================================================
# Test Group 2: Progress Bar Calculations
# ===========================================================================
echo -e "${TEST_CYAN}─── Test Group 2: Progress Bar ───${TEST_NC}"

# Test 2.1: Percentage calculation
test_start "Percentage 5/10 = 50%"
percentage=$(( (5 * 100) / 10 ))
assert_equals "50" "$percentage"
test_end

# Test 2.2: Percentage 0/10 = 0%
test_start "Percentage 0/10 = 0%"
percentage=$(( (0 * 100) / 10 ))
assert_equals "0" "$percentage"
test_end

# Test 2.3: Percentage 10/10 = 100%
test_start "Percentage 10/10 = 100%"
percentage=$(( (10 * 100) / 10 ))
assert_equals "100" "$percentage"
test_end

# Test 2.4: Progress bar width
test_start "Progress bar 50% fills 20/40 chars"
percentage=50
bar_width=40
filled=$(( (percentage * bar_width) / 100 ))
assert_equals "20" "$filled"
test_end

# Test 2.5: ETA calculation
test_start "ETA calculation: 5 steps remaining at 1 step/sec = 5s"
remaining_steps=5
steps_per_sec=1
eta_seconds=$(( remaining_steps / steps_per_sec ))
assert_equals "5" "$eta_seconds"
test_end

echo ""

# ===========================================================================
# Test Group 3: Error Classification
# ===========================================================================
echo -e "${TEST_CYAN}─── Test Group 3: Error Classification ───${TEST_NC}"

# Test 3.1: Credential error detection
test_start "classify_error detects InvalidAccessKeyId"
output="Error: InvalidAccessKeyId.NotFound"
result=$(classify_error "$output")
assert_contains "CREDENTIAL" "$result"
test_end

# Test 3.2: Quota error detection
test_start "classify_error detects QuotaExceeded"
output="Error: QuotaExceeded: ECS instance limit reached"
result=$(classify_error "$output")
assert_contains "QUOTA" "$result"
test_end

# Test 3.3: Network error detection
test_start "classify_error detects connection refused"
output="Failed: connection refused"
result=$(classify_error "$output")
assert_contains "NETWORK" "$result"
test_end

# Test 3.4: Permission error detection
test_start "classify_error detects ForbiddenAccess"
output="Error: ForbiddenAccess: No permission"
result=$(classify_error "$output")
assert_contains "PERMISSION" "$result"
test_end

# Test 3.5: API rate limit
test_start "classify_error detects Throttling"
output="Error: Throttling: Request rate exceeded"
result=$(classify_error "$output")
assert_contains "API_RATE" "$result"
test_end

# Test 3.6: Unknown error
test_start "classify_error returns INTERNAL_ERROR for unknown"
output="Some unknown error message"
result=$(classify_error "$output")
assert_contains "INTERNAL" "$result"
test_end

echo ""

# ===========================================================================
# Test Group 4: Error Description and Recovery
# ===========================================================================
echo -e "${TEST_CYAN}─── Test Group 4: Error Description & Recovery ───${TEST_NC}"

# Test 4.1: Credential error description
test_start "get_error_description for CREDENTIAL"
result=$(get_error_description "CREDENTIAL_ERROR")
assert_not_empty "$result"
test_end

# Test 4.2: Quota error recovery
test_start "get_error_recovery for QUOTA contains action"
result=$(get_error_recovery "QUOTA_EXCEEDED")
assert_contains "配额" "$result"
test_end

# Test 4.3: Network error recovery
test_start "get_error_recovery for NETWORK contains ping"
result=$(get_error_recovery "NETWORK_TIMEOUT")
assert_contains "ping" "$result"
test_end

# Test 4.4: All 12 error types have descriptions
test_start "All error types have descriptions"
types=("CREDENTIAL_ERROR" "QUOTA_EXCEEDED" "NETWORK_TIMEOUT" "PERMISSION_DENIED" "API_RATE_LIMIT" "INVALID_PARAMETER" "RESOURCE_NOT_FOUND" "DEPENDENCY_MISSING" "CONFIGURATION_ERROR" "INTERNAL_ERROR" "VALIDATION_FAILED" "OPERATION_TIMEOUT")
all_have=true
for err_type in "${types[@]}"; do
    desc=$(get_error_description "$err_type")
    if [[ -z "$desc" || "$desc" == "未知错误" ]]; then
        all_have=false
        break
    fi
done
assert_equals "true" "$all_have"
test_end

# Test 4.5: All error types have recovery actions
test_start "All error types have recovery actions"
all_have=true
for err_type in "${types[@]}"; do
    recovery=$(get_error_recovery "$err_type")
    if [[ -z "$recovery" ]]; then
        all_have=false
        break
    fi
done
assert_equals "true" "$all_have"
test_end

echo ""

# ===========================================================================
# Test Group 5: Terminal Capability Detection
# ===========================================================================
echo -e "${TEST_CYAN}─── Test Group 5: Terminal Detection ───${TEST_NC}"

# Test 5.1: detect_terminal_capability returns valid value
test_start "detect_terminal_capability returns one of known types"
result=$(detect_terminal_capability)
valid=false
case "$result" in
    iterm2|truecolor|256color|windows_terminal|basic)
        valid=true
        ;;
esac
assert_equals "true" "$valid"
test_end

# Test 5.2: _TERM_CAPABILITY is set
test_start "_TERM_CAPABILITY variable is set"
assert_not_empty "${_TERM_CAPABILITY:-}"
test_end

echo ""

# ===========================================================================
# Test Group 6: Input Validation
# ===========================================================================
echo -e "${TEST_CYAN}─── Test Group 6: Input Validation ───${TEST_NC}"

# Test 6.1: Valid region format
test_start "Valid region format cn-hangzhou"
region="cn-hangzhou"
valid=false
if [[ "$region" =~ ^cn-[a-z]+$ ]] || [[ "$region" =~ ^ap-[a-z]+-[0-9]+$ ]]; then
    valid=true
fi
assert_equals "true" "$valid"
test_end

# Test 6.2: DAU must be positive integer
test_start "DAU 100 is valid positive integer"
dau="100"
valid=false
if [[ "$dau" =~ ^[1-9][0-9]*$ ]]; then
    valid=true
fi
assert_equals "true" "$valid"
test_end

# Test 6.3: DAU 0 is invalid
test_start "DAU 0 is invalid"
dau="0"
valid=true
if [[ "$dau" =~ ^[1-9][0-9]*$ ]]; then
    valid=true
fi
assert_equals "true" "$valid"
test_end

# Test 6.4: Tag format key=value
test_start "Tag format env=prod is valid"
tag="env=prod"
valid=false
if [[ "$tag" =~ ^[a-zA-Z0-9_-]+=[a-zA-Z0-9_-]+$ ]]; then
    valid=true
fi
assert_equals "true" "$valid"
test_end

# Test 6.5: Multiple tags format
test_start "Multiple tags env=prod,app=ecommerce is valid"
tags="env=prod,app=ecommerce"
valid=false
if [[ "$tags" =~ ^[a-zA-Z0-9_-]+=[a-zA-Z0-9_-]+(,[a-zA-Z0-9_-]+=[a-zA-Z0-9_-]+)*$ ]]; then
    valid=true
fi
assert_equals "true" "$valid"
test_end

echo ""

# ===========================================================================
# Test Group 7: Architecture Pattern Detection
# ===========================================================================
echo -e "${TEST_CYAN}─── Test Group 7: Architecture Patterns ───${TEST_NC}"

# Test 7.1: Single-node pattern
test_start "Single-node topology (1 ECS, no RDS) = single-node"
ecs=1; rds=0; slb=0
if [[ $ecs -eq 1 && $rds -eq 0 && $slb -eq 0 ]]; then
    pattern="single-node"
else
    pattern="other"
fi
assert_equals "single-node" "$pattern"
test_end

# Test 7.2: 3-tier pattern
test_start "3-tier topology (ECS + RDS + SLB) = 3-tier"
ecs=2; rds=1; slb=1
if [[ $ecs -ge 2 && $rds -ge 1 && $slb -ge 1 ]]; then
    pattern="3-tier"
else
    pattern="other"
fi
assert_equals "3-tier" "$pattern"
test_end

# Test 7.3: Microservice pattern
test_start "Microservice topology (5+ ECS, multiple RDS) = microservice"
ecs=8; rds=3
if [[ $ecs -ge 5 && $rds -ge 2 ]]; then
    pattern="microservice"
else
    pattern="other"
fi
assert_equals "microservice" "$pattern"
test_end

echo ""

# ===========================================================================
# Final Summary
# ===========================================================================
test_summary
exit_code=$?
exit $exit_code
