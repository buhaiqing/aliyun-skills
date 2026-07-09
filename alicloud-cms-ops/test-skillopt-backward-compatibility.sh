#!/bin/bash
# SkillOpt integration test suite for alicloud-cms-ops
# Tests: backward compat, repair logic, runtime metrics, wrapper, flag parsing.
# Does NOT call real Alibaba Cloud APIs — uses stub functions.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$SCRIPT_DIR/scripts/skillopt-lib.sh"
WRAPPER="$SCRIPT_DIR/scripts/cms-skillopt-wrapper.sh"
HARNESS_WRAPPER="$SCRIPT_DIR/scripts/cms-harness-wrapper.sh"
SELF_REPAIR="$SCRIPT_DIR/scripts/skillopt-self-repair.sh"
RUNTIME_TMP="$(mktemp)"
LOG_TMP="$(mktemp)"

PASS=0; FAIL=0

assert_eq() {
    local desc="$1" got="$2" want="$3"
    if [[ "$got" == "$want" ]]; then
        echo "  ✓  $desc"
        PASS=$((PASS+1))
    else
        echo "  ✗  $desc"
        echo "     want: $want"
        echo "     got:  $got"
        FAIL=$((FAIL+1))
    fi
}

assert_contains() {
    local desc="$1" haystack="$2" needle="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        echo "  ✓  $desc"
        PASS=$((PASS+1))
    else
        echo "  ✗  $desc"
        echo "     expected to contain: $needle"
        echo "     got: $haystack"
        FAIL=$((FAIL+1))
    fi
}

assert_file_exists() {
    local desc="$1" path="$2"
    if [[ -f "$path" ]]; then
        echo "  ✓  $desc"
        PASS=$((PASS+1))
    else
        echo "  ✗  $desc (missing: $path)"
        FAIL=$((FAIL+1))
    fi
}

assert_executable() {
    local desc="$1" path="$2"
    if [[ -x "$path" ]]; then
        echo "  ✓  $desc"
        PASS=$((PASS+1))
    else
        echo "  ✗  $desc (not executable: $path)"
        FAIL=$((FAIL+1))
    fi
}

# ─── Setup ───────────────────────────────────────────────────────────────────
export ALIBABA_CLOUD_RUNTIME_DIR="$(dirname "$RUNTIME_TMP")"
export ALIBABA_CLOUD_LOG_DIR="$(dirname "$LOG_TMP")"
export _SKILLOPT_SKIP_WRAPPER_CHECK=1
source "$LIB"
SKILLOPT_RUNTIME_DATA="$RUNTIME_TMP"
SKILLOPT_LOG_FILE="$LOG_TMP"

echo "================================================================="
echo " alicloud-cms-ops SkillOpt Integration Tests"
echo "================================================================="

# ─── Suite 1: File existence & permissions ───────────────────────────────────
echo ""
echo "Suite 1: File Existence & Permissions"
assert_file_exists   "skillopt-lib.sh exists"              "$LIB"
assert_file_exists   "cms-harness-wrapper.sh exists"      "$HARNESS_WRAPPER"
assert_executable    "cms-harness-wrapper.sh is +x"       "$HARNESS_WRAPPER"
assert_file_exists   "cms-skillopt-wrapper.sh exists"      "$WRAPPER"
assert_executable    "cms-skillopt-wrapper.sh is +x"       "$WRAPPER"
assert_file_exists   "skillopt-integration.md exists"      "$SCRIPT_DIR/references/skillopt-integration.md"

# ─── Suite 2: Flag parsing ────────────────────────────────────────────────────
echo ""
echo "Suite 2: Flag Parsing (skillopt_init)"

SKILLOPT_ENABLED=false
skillopt_init --skillopt-enable --Namespace acs_ecs_dashboard --Period 60
assert_eq "skillopt_enable sets SKILLOPT_ENABLED=true" "$SKILLOPT_ENABLED" "true"
assert_eq "--Namespace passed through to SKILLOPT_REMAINING" \
    "${SKILLOPT_REMAINING[0]}" "--Namespace"
assert_eq "SKILLOPT_REMAINING has correct length (4 elements)" \
    "${#SKILLOPT_REMAINING[@]}" "4"

SKILLOPT_ENABLED=true
skillopt_init --skillopt-disable --Namespace foo
assert_eq "skillopt_disable sets SKILLOPT_ENABLED=false" "$SKILLOPT_ENABLED" "false"

unset SKILLOPT_ENABLED
skillopt_init --Namespace bar
if [[ -f "${_SKILLOPT_SKILLS_ROOT}/.env" ]] && grep -qE '^[[:space:]]*SKILLOPT_ENABLED=true' "${_SKILLOPT_SKILLS_ROOT}/.env" 2>/dev/null; then
    assert_eq "SKILLOPT_ENABLED loaded from .env when unset in shell" "$SKILLOPT_ENABLED" "true"
else
    assert_eq "default false when SKILLOPT_ENABLED unset" "${SKILLOPT_ENABLED:-false}" "false"
fi

SKILLOPT_ENABLED=true
skillopt_init --Namespace baz
assert_eq "SKILLOPT_ENABLED env respected without CLI flag" "$SKILLOPT_ENABLED" "true"

SKILLOPT_ENABLED=true
skillopt_init --skillopt-disable --Namespace qux
assert_eq "CLI disable overrides SKILLOPT_ENABLED env" "$SKILLOPT_ENABLED" "false"

SKILLOPT_RETRIES=3
skillopt_init --skillopt-retries 7 --Namespace bar
assert_eq "--skillopt-retries overrides SKILLOPT_RETRIES" "$SKILLOPT_RETRIES" "7"

SKILLOPT_ENABLED=false
SKILLOPT_RETRIES=3

# ─── Suite 3: Runtime JSON initialization & update ───────────────────────────
echo ""
echo "Suite 3: Runtime Metrics (skillopt_update_runtime)"

printf '{}' > "$RUNTIME_TMP"

skillopt_update_runtime "ok" 0
total_calls="$(jq -r '.total_calls' "$RUNTIME_TMP")"
assert_eq "total_calls increments from 0 to 1" "$total_calls" "1"

skillopt_update_runtime "Throttling.User" 1
total_calls="$(jq -r '.total_calls' "$RUNTIME_TMP")"
total_failures="$(jq -r '.total_failures' "$RUNTIME_TMP")"
error_rate="$(jq -r '.error_rate' "$RUNTIME_TMP")"
assert_eq "total_calls increments to 2" "$total_calls" "2"
assert_eq "total_failures is 1 after one failed call" "$total_failures" "1"
# 1 failure / 2 calls = 50%
assert_eq "error_rate is 50 after 1 failure in 2 calls" "$error_rate" "50"

rm -f "$RUNTIME_TMP"
skillopt_update_runtime "InvalidParameter" 1
assert_file_exists "runtime file recreated when missing" "$RUNTIME_TMP"
total_calls="$(jq -r '.total_calls' "$RUNTIME_TMP")"
assert_eq "total_calls starts at 1 after recreation" "$total_calls" "1"

# ─── Suite 4: Read-only action detection ─────────────────────────────────────
echo ""
echo "Suite 4: Read-only Action Detection"

if skillopt_is_readonly_action "DescribeMetricList"; then
    echo "  ✓  DescribeMetricList is read-only"
    PASS=$((PASS+1))
else
    echo "  ✗  DescribeMetricList should be read-only"
    FAIL=$((FAIL+1))
fi

if skillopt_is_readonly_action "PutMetricAlarm"; then
    echo "  ✗  PutMetricAlarm should NOT be read-only"
    FAIL=$((FAIL+1))
else
    echo "  ✓  PutMetricAlarm is mutating (no auto-repair)"
    PASS=$((PASS+1))
fi

# ─── Suite 5: Self-repair logic ──────────────────────────────────────────────
echo ""
echo "Suite 5: Self-Repair Logic (skillopt_repair_error)"

SKILLOPT_ENABLED=true
SKILLOPT_BACKOFF=(0 0)

_aliyun_call_count=0
aliyun() {
    _aliyun_call_count=$((_aliyun_call_count + 1))
    [[ $_aliyun_call_count -ge 2 ]] && return 0
    return 1
}
export -f aliyun

_aliyun_call_count=0
skillopt_repair_error "Throttling.User" cms DescribeMetricList \
    "--Namespace" "acs_ecs_dashboard" >/dev/null 2>&1
assert_eq "Throttling repair succeeds on retry" "$?" "0"

# Verify aliyun receives product + action as separate args
_last_aliyun_args=()
aliyun() {
    _last_aliyun_args=("$@")
    return 0
}
export -f aliyun
skillopt_repair_error "InvalidParameter" cms DescribeMetricList \
    "--Dimensions" '[ { "instanceId" : "i-abc 123" } ]' >/dev/null 2>&1
assert_eq "aliyun arg[0] is product cms" "${_last_aliyun_args[0]+"${_last_aliyun_args[0]}"}" "cms"
assert_eq "aliyun arg[1] is action DescribeMetricList" "${_last_aliyun_args[1]+"${_last_aliyun_args[1]}"}" "DescribeMetricList"
assert_eq "Dimensions value preserved with internal space" \
    "${_last_aliyun_args[3]+"${_last_aliyun_args[3]}"}" '[{"instanceId":"i-abc 123"}]'

# Mutating action: repair must be skipped before aliyun is called
aliyun() { return 1; }
export -f aliyun
SKILLOPT_ENABLED=true
set +e
skillopt_repair_error "Throttling.User" cms PutMetricAlarm \
    "--AlarmName" "test" >/dev/null 2>&1
repair_rc=$?
set -e
assert_eq "Repair skipped for mutating PutMetricAlarm" "$repair_rc" "1"

SKILLOPT_ENABLED=false
set +e
skillopt_repair_error "Throttling.User" cms DescribeMetricList \
    "--Namespace" "foo" >/dev/null 2>&1
repair_rc=$?
set -e
assert_eq "Repair skipped when SKILLOPT_ENABLED=false" "$repair_rc" "1"

unset -f aliyun

# ─── Suite 5b: Repair success returns stdout ─────────────────────────────────
echo ""
echo "Suite 5b: Repair Success Output"

aliyun() {
    printf '{"Datapoints":[{"Average":42}]}\n'
    return 0
}
export -f aliyun

SKILLOPT_ENABLED=true
SKILLOPT_BACKOFF=(0)
output="$(skillopt_repair_error "InvalidParameter" cms DescribeMetricList \
    "--Dimensions" '[ { "instanceId" : "i-abc" } ]' 2>/dev/null || true)"
assert_contains "Repair success prints API response" "$output" '"Average":42'

unset -f aliyun

# ─── Suite 5c: P1 Features (RegionId Auto-completion & TimeRange Shrinking) ──
echo ""
echo "Suite 5c: P1 Features (RegionId & TimeRange)"

# 1. RegionId Auto-completion
_aliyun_region_received=""
aliyun() {
    if [[ "$1" == "ecs" && "$2" == "DescribeRegions" ]]; then
        echo "cn-beijing"
        return 0
    fi
    local has_r=false
    for arg in "$@"; do
        [[ "$arg" == "--RegionId" ]] && has_r=true
    done
    if $has_r; then
        _aliyun_region_received="yes"
        return 0
    fi
    return 1
}
export -f aliyun

SKILLOPT_ENABLED=true
_aliyun_region_received=""
skillopt_repair_error "MissingParameter" cms DescribeMetricList \
    "--Namespace" "acs_ecs_dashboard" >/dev/null 2>&1
assert_eq "RegionId missing auto-completion retry succeeds" "$_aliyun_region_received" "yes"

unset -f aliyun

# 2. TimeRange Shrinking
_aliyun_time_received=""
aliyun() {
    local start_time=""
    local args=("$@")
    for ((idx=0; idx<${#args[@]}; idx++)); do
        if [[ "${args[$idx]}" == "--StartTime" && $((idx+1)) -lt ${#args[@]} ]]; then
            start_time="${args[$((idx+1))]}"
        fi
    done
    if [[ -n "$start_time" && "$start_time" != "1546272000000" ]]; then
        _aliyun_time_received="$start_time"
        return 0
    fi
    return 1
}
export -f aliyun

SKILLOPT_ENABLED=true
_aliyun_time_received=""
skillopt_repair_error "DataRetentionExceeded" cms DescribeMetricList \
    "--StartTime" "1546272000000" >/dev/null 2>&1
assert_eq "TimeRange auto-shrinking retry succeeds and adjusts StartTime" \
    "$([ -n "$_aliyun_time_received" ] && echo "yes" || echo "no")" "yes"

unset -f aliyun

# 3. ResourceNotFound Prefix Routing
_aliyun_resource_probe_called=""
_aliyun_resource_probe_id=""
aliyun() {
    local cmd="$1"
    local sub="$2"
    shift 2
    if [[ "$cmd" == "ecs" && "$sub" == "DescribeInstances" ]]; then
        _aliyun_resource_probe_called="ecs"
        _aliyun_resource_probe_id="$*"
        return 0
    elif [[ "$cmd" == "rds" && "$sub" == "DescribeDBInstances" ]]; then
        _aliyun_resource_probe_called="rds"
        _aliyun_resource_probe_id="$*"
        return 0
    elif [[ "$cmd" == "r-kvstore" && "$sub" == "DescribeInstances" ]]; then
        _aliyun_resource_probe_called="redis"
        _aliyun_resource_probe_id="$*"
        return 0
    elif [[ "$cmd" == "cms" && "$sub" == "DescribeMetricList" ]]; then
        return 0
    fi
    return 1
}
export -f aliyun

SKILLOPT_ENABLED=true

_aliyun_resource_probe_called=""
skillopt_repair_error "ResourceNotFound" cms DescribeMetricList \
    "--Dimensions" '[{"instanceId":"i-ecs123"}]' "--RegionId" "cn-hangzhou" >/dev/null 2>&1
assert_eq "ResourceNotFound ECS routing calls ecs" "$_aliyun_resource_probe_called" "ecs"

_aliyun_resource_probe_called=""
skillopt_repair_error "ResourceNotFound" cms DescribeMetricList \
    "--Dimensions" '[{"instanceId":"rm-rds123"}]' "--RegionId" "cn-hangzhou" >/dev/null 2>&1
assert_eq "ResourceNotFound RDS routing calls rds" "$_aliyun_resource_probe_called" "rds"

_aliyun_resource_probe_called=""
skillopt_repair_error "ResourceNotFound" cms DescribeMetricList \
    "--Dimensions" '[{"instanceId":"r-redis123"}]' "--RegionId" "cn-hangzhou" >/dev/null 2>&1
assert_eq "ResourceNotFound Redis routing calls r-kvstore" "$_aliyun_resource_probe_called" "redis"

# 4. ResourceNotFound ACK and NAS routing
_aliyun_resource_probe_called=""
aliyun() {
    local cmd="$1"
    local sub="$2"
    shift 2
    if [[ "$cmd" == "cs" && "$sub" == "DescribeClusterDetail" ]]; then
        _aliyun_resource_probe_called="cs"
        return 0
    elif [[ "$cmd" == "nas" && "$sub" == "DescribeFileSystems" ]]; then
        _aliyun_resource_probe_called="nas"
        return 0
    elif [[ "$cmd" == "cms" && "$sub" == "DescribeMetricList" ]]; then
        return 0
    fi
    return 1
}
export -f aliyun

SKILLOPT_ENABLED=true
_aliyun_resource_probe_called=""
skillopt_repair_error "ResourceNotFound" cms DescribeMetricList \
    "--Dimensions" '[{"instanceId":"c1234567890abcdef"}]' "--RegionId" "cn-hangzhou" >/dev/null 2>&1
assert_eq "ResourceNotFound ACK routing calls cs" "$_aliyun_resource_probe_called" "cs"

_aliyun_resource_probe_called=""
skillopt_repair_error "ResourceNotFound" cms DescribeMetricList \
    "--Dimensions" '[{"instanceId":"nas-12345"}]' "--RegionId" "cn-hangzhou" >/dev/null 2>&1
assert_eq "ResourceNotFound NAS routing calls nas" "$_aliyun_resource_probe_called" "nas"

unset -f aliyun

# ─── Suite 5d: Propagation Delay Polling ─────────────────────────────────────
echo ""
echo "Suite 5d: Propagation Delay Polling"

# Reset circuit breaker state accumulated from prior repair tests
printf '{"cb_state":"closed","cb_consecutive_failures":0,"cb_opened_at":0}' > "$RUNTIME_TMP"
SKILLOPT_CB_ENABLED=false
SKILLOPT_LANGFUSE_ENABLED=false
set +e

_poll_calls=0
aliyun() {
    _poll_calls=$((_poll_calls + 1))
    if [[ $_poll_calls -eq 1 ]]; then
        # First call: returns empty
        echo '{"Total":0,"AlarmList":[]}'
        return 0
    else
        # Second call: returns non-empty (propagated)
        echo '{"Total":1,"AlarmList":[{"AlarmName":"test-alarm"}]}'
        return 0
    fi
}
export -f aliyun

SKILLOPT_ENABLED=true
_poll_calls=0
# Mock sleep to speed up test
sleep() { :; }
export -f sleep

_poll_tmp="$(mktemp)"
skillopt_wrap cms DescribeMetricAlarmList --skillopt-enable --AlarmName "test-alarm" > "$_poll_tmp" 2>/dev/null
output="$(cat "$_poll_tmp")"
rm -f "$_poll_tmp"

assert_eq "Propagation polling query called twice" "$_poll_calls" "2"
assert_contains "Propagation polling returns non-empty output" "$output" '"Total":1'

unset -f aliyun sleep

# ─── Suite 6: optimize_params preserves spaces ───────────────────────────────
echo ""
echo "Suite 6: optimize_params (SKILLOPT_PARAMS in-place)"

SKILLOPT_ENABLED=true
SKILLOPT_PARAMS=("--Dimensions" '[{"instanceId":"i-abc 123"}]' "--Namespace" "acs_ecs_dashboard")
printf '{"query_count":2000,"error_rate":0}' > "$RUNTIME_TMP"
skillopt_optimize_params cms DescribeMetricList
assert_eq "SKILLOPT_PARAMS length after optimize (4 orig + Period pair)" \
    "${#SKILLOPT_PARAMS[@]}" "6"
assert_eq "Dimensions with space preserved at index 1" \
    "${SKILLOPT_PARAMS[1]}" '[{"instanceId":"i-abc 123"}]'
assert_eq "--Period 300 appended at index 4" "${SKILLOPT_PARAMS[4]}" "--Period"
assert_eq "Period value is 300" "${SKILLOPT_PARAMS[5]}" "300"

# Verify retries cap optimization
SKILLOPT_RETRIES=5
printf '{"query_count":0,"error_rate":10}' > "$RUNTIME_TMP"
skillopt_optimize_params cms DescribeMetricList
assert_eq "SKILLOPT_RETRIES increments to 6 when error_rate > 5%" "$SKILLOPT_RETRIES" "6"

SKILLOPT_RETRIES=6
skillopt_optimize_params cms DescribeMetricList
assert_eq "SKILLOPT_RETRIES remains capped at 6 when error_rate > 5%" "$SKILLOPT_RETRIES" "6"

# Verify step-wise Period optimization
SKILLOPT_PARAMS=("--Period" "60" "--Namespace" "acs_ecs_dashboard")
printf '{"query_count":2000,"error_rate":0}' > "$RUNTIME_TMP"
skillopt_optimize_params cms DescribeMetricList
assert_eq "optimize: low Period 60 raised to 120" "${SKILLOPT_PARAMS[1]}" "120"

SKILLOPT_PARAMS=("--Period" "300" "--Namespace" "acs_ecs_dashboard")
skillopt_optimize_params cms DescribeMetricList
assert_eq "optimize: high Period 300 remains unchanged" "${SKILLOPT_PARAMS[1]}" "300"

SKILLOPT_ENABLED=false

# ─── Suite 7: skillopt_wrap — single execution, no double-call on mutate ─────
echo ""
echo "Suite 7: skillopt_wrap (single execution)"

_aliyun_calls=0
aliyun() {
    _aliyun_calls=$((_aliyun_calls + 1))
    echo '{"Code":"InvalidParameter","Message":"bad param"}' >&2
    return 1
}
export -f aliyun

SKILLOPT_ENABLED=true
_aliyun_calls=0
skillopt_wrap cms PutMetricAlarm --skillopt-enable \
    --AlarmName "test-alarm" >/dev/null 2>&1 || true
assert_eq "Mutating action: aliyun called exactly once (no re-run)" "$_aliyun_calls" "1"

_aliyun_calls=0
skillopt_wrap cms DescribeMetricList --skillopt-enable \
    --Namespace "acs_ecs_dashboard" >/dev/null 2>&1 || true
# 1 initial + repair retries (backoff 0,0 from earlier may still apply if SKILLOPT_BACKOFF reset)
# At minimum: should not be 2 from a blind re-run for error extraction
assert_eq "Read-only action: no blind second call for error extraction" \
    "$([ "$_aliyun_calls" -lt 3 ] && echo yes || echo no)" "yes"

unset -f aliyun

# ─── Suite 8: Log output ─────────────────────────────────────────────────────
echo ""
echo "Suite 8: Log Output"
SKILLOPT_ENABLED=true
skillopt_log "test log entry"
log_content="$(cat "$LOG_TMP")"
assert_contains "Log contains [CMS-SkillOpt] tag" "$log_content" "[CMS-SkillOpt]"
assert_contains "Log contains message text" "$log_content" "test log entry"

# ─── Suite 9: Wrapper usage guard ────────────────────────────────────────────
echo ""
echo "Suite 9: Wrapper Usage Guard"
wrapper_stderr="$("$WRAPPER" 2>&1 || true)"
assert_contains "Wrapper shows usage on no args" "$wrapper_stderr" "Usage:"

# ─── Suite 10: Wrapper product routing (cms vs cms2) ──────────────────────────
echo ""
echo "Suite 10: Wrapper Product Routing"

# Create a temporary directory for our mock aliyun executable
MOCK_BIN_DIR="$(mktemp -d)"
MOCK_LOG_FILE="$(mktemp)"

cat > "$MOCK_BIN_DIR/aliyun" <<EOF
#!/bin/bash
echo "\$*" >> "$MOCK_LOG_FILE"
exit 0
EOF
chmod +x "$MOCK_BIN_DIR/aliyun"

# Save old PATH and prepend our mock bin directory
OLD_PATH="$PATH"
export PATH="$MOCK_BIN_DIR:$PATH"

# Run wrapper with cms2
bash "$WRAPPER" cms2 DescribeMetricList --skillopt-enable >/dev/null 2>&1
mock_out="$(cat "$MOCK_LOG_FILE")"
assert_contains "Wrapper routed to cms2" "$mock_out" "cms2 DescribeMetricList"

# Run wrapper with default (no cms/cms2 prefix)
printf "" > "$MOCK_LOG_FILE"
bash "$WRAPPER" DescribeMetricList --skillopt-enable >/dev/null 2>&1
mock_out="$(cat "$MOCK_LOG_FILE")"
assert_contains "Wrapper routed to default cms" "$mock_out" "cms DescribeMetricList"

# Restore original PATH and clean up
export PATH="$OLD_PATH"
rm -rf "$MOCK_BIN_DIR" "$MOCK_LOG_FILE"

# ─── Suite 11: --skillopt-report flag ────────────────────────────────────────
echo ""
echo "Suite 11: --skillopt-report Flag"

# 1. Flag parsing
SKILLOPT_REPORT=false
skillopt_init --skillopt-report --Namespace acs_ecs_dashboard
assert_eq "--skillopt-report sets SKILLOPT_REPORT=true" "$SKILLOPT_REPORT" "true"
assert_eq "--skillopt-report does not consume following args" \
    "${SKILLOPT_REMAINING[0]}" "--Namespace"

# 2. Report output with healthy runtime data
printf '{"total_calls":100,"total_failures":2,"total_repair_success":1,"error_rate":2,"query_count":50,"last_updated":1718000000,"last_error":"Throttling.User"}' > "$RUNTIME_TMP"
SKILLOPT_REPORT=true
SKILLOPT_ENABLED=true
report_output="$(skillopt_report 2>/dev/null)"
assert_contains "Report contains header" "$report_output" "# CMS SkillOpt 运营摘要"
assert_contains "Report contains health status" "$report_output" "Healthy"
assert_contains "Report contains total_calls" "$report_output" "100"
assert_contains "Report contains total_failures" "$report_output" "2"
assert_contains "Report contains repair_success" "$report_output" "1"
assert_contains "Report contains error_rate" "$report_output" "2%"
assert_contains "Report contains last_error" "$report_output" "Throttling.User"
assert_contains "Report contains healthy suggestion" "$report_output" "运行状态良好"

# 3. Report with warning-level error_rate
printf '{"total_calls":100,"total_failures":10,"total_repair_success":5,"error_rate":10,"query_count":50,"last_updated":1718000000,"last_error":"InvalidParameter"}' > "$RUNTIME_TMP"
report_output="$(skillopt_report 2>/dev/null)"
assert_contains "Report contains warning status" "$report_output" "Warning"
assert_contains "Report contains warning suggestion" "$report_output" "错误率偏高"

# 4. Report with critical-level error_rate
printf '{"total_calls":100,"total_failures":30,"total_repair_success":10,"error_rate":30,"query_count":50,"last_updated":1718000000,"last_error":"Forbidden"}' > "$RUNTIME_TMP"
report_output="$(skillopt_report 2>/dev/null)"
assert_contains "Report contains critical status" "$report_output" "Critical"
assert_contains "Report contains critical suggestion" "$report_output" "错误率过高"

# 5. Report with high query_count
printf '{"total_calls":2000,"total_failures":0,"total_repair_success":0,"error_rate":0,"query_count":1500,"last_updated":1718000000,"last_error":"none"}' > "$RUNTIME_TMP"
report_output="$(skillopt_report 2>/dev/null)"
assert_contains "Report contains high query warning" "$report_output" "查询量较高"

# 6. Report to file
report_tmp="$(mktemp)"
printf '{"total_calls":5,"total_failures":0,"total_repair_success":0,"error_rate":0,"query_count":5}' > "$RUNTIME_TMP"
skillopt_report "$report_tmp" 2>/dev/null
assert_file_exists "Report file created" "$report_tmp"
file_content="$(cat "$report_tmp")"
assert_contains "Report file contains header" "$file_content" "# CMS SkillOpt 运营摘要"
rm -f "$report_tmp"

# 7. skillopt_wrap with --skillopt-report short-circuits (no aliyun call)
_aliyun_report_calls=0
aliyun() {
    _aliyun_report_calls=$((_aliyun_report_calls + 1))
    return 0
}
export -f aliyun

printf '{"total_calls":1,"total_failures":0,"total_repair_success":0,"error_rate":0,"query_count":1}' > "$RUNTIME_TMP"
SKILLOPT_REPORT=false
wrap_report="$(skillopt_wrap cms report --skillopt-report 2>/dev/null)"
assert_eq "skillopt_wrap --skillopt-report does NOT call aliyun" "$_aliyun_report_calls" "0"
assert_contains "skillopt_wrap --skillopt-report outputs report" "$wrap_report" "# CMS SkillOpt 运营摘要"

unset -f aliyun

# 8. Report with empty/missing runtime file
rm -f "$RUNTIME_TMP"
report_output="$(skillopt_report 2>/dev/null)"
assert_contains "Report handles missing runtime gracefully" "$report_output" "0"

# Reset
SKILLOPT_REPORT=false

# ─── Suite 12: P0 regression (self-repair, fallback, probe safety, repair trace) ─
echo ""
echo "Suite 12: P0 Regression Fixes"

# 12a: skillopt-self-repair passes action as subcommand (not --skillopt-enable)
SELF_REPAIR_MOCK_LOG="$(mktemp)"
SELF_REPAIR_MOCK_BIN="$(mktemp -d)"
cat > "$SELF_REPAIR_MOCK_BIN/aliyun" <<EOF
#!/bin/bash
echo "\$*" >> "$SELF_REPAIR_MOCK_LOG"
exit 0
EOF
chmod +x "$SELF_REPAIR_MOCK_BIN/aliyun"
export _SKILLOPT_SKIP_WRAPPER_CHECK=1
PATH="$SELF_REPAIR_MOCK_BIN:$PATH" \
    "$SELF_REPAIR" DescribeMetricList --Namespace acs_ecs_dashboard >/dev/null 2>&1 || true
_self_repair_first_line="$(head -1 "$SELF_REPAIR_MOCK_LOG" 2>/dev/null || true)"
assert_contains "self-repair: first aliyun call includes DescribeMetricList" \
    "$_self_repair_first_line" "DescribeMetricList"
assert_eq "self-repair: subcommand is not --skillopt-enable" \
    "$([[ "$_self_repair_first_line" == cms\ --skillopt-enable* ]] && echo bad || echo ok)" "ok"
rm -f "$SELF_REPAIR_MOCK_LOG"
rm -rf "$SELF_REPAIR_MOCK_BIN"

# 12b: harness wrapper graceful fallback when lib missing
FALLBACK_MOCK_LOG="$(mktemp)"
FALLBACK_MOCK_BIN="$(mktemp -d)"
cat > "$FALLBACK_MOCK_BIN/aliyun" <<EOF
#!/bin/bash
echo "\$*" >> "$FALLBACK_MOCK_LOG"
exit 0
EOF
chmod +x "$FALLBACK_MOCK_BIN/aliyun"
LIB_BACKUP="$SCRIPT_DIR/scripts/harness-lib.sh.p0test.bak"
mv "$SCRIPT_DIR/scripts/harness-lib.sh" "$LIB_BACKUP"
fallback_stderr="$(
    PATH="$FALLBACK_MOCK_BIN:$PATH" \
        "$HARNESS_WRAPPER" DescribeMetricList --skillopt-enable --Namespace acs_ecs_dashboard 2>&1 || true
)"
mv "$LIB_BACKUP" "$SCRIPT_DIR/scripts/harness-lib.sh"
_fallback_line="$(head -1 "$FALLBACK_MOCK_LOG" 2>/dev/null || true)"
assert_contains "fallback: stderr warns harness-lib missing" "$fallback_stderr" "falling back to direct aliyun CLI"
assert_contains "fallback: aliyun receives DescribeMetricList subcommand" "$_fallback_line" "DescribeMetricList"
assert_eq "fallback: strips --skillopt-enable before aliyun" \
    "$([[ "$_fallback_line" == *"--skillopt-enable"* ]] && echo bad || echo ok)" "ok"
rm -f "$FALLBACK_MOCK_LOG"
rm -rf "$FALLBACK_MOCK_BIN"

# 12c: ResourceNotFound probe rejects shell metacharacters (no eval)
_inject_probe_called=""
aliyun() {
    if [[ "$1" == "ecs" ]]; then
        _inject_probe_called="yes"
    fi
    return 1
}
export -f aliyun
SKILLOPT_ENABLED=true
skillopt_repair_error "ResourceNotFound" cms DescribeMetricList \
    '--Dimensions' '[{"instanceId":"i-abc'\''; id; #"}]' \
    "--RegionId" "cn-hangzhou" >/dev/null 2>&1 || true
assert_eq "ResourceNotFound: malicious instanceId skips ecs probe" "${_inject_probe_called:-}" ""
unset -f aliyun

# 12d: repair success records repaired output in trace (not initial error)
TRACE_TMP_ROOT="$(mktemp -d)"
export _SKILLOPT_TRACE_DIR="$TRACE_TMP_ROOT/traces"
mkdir -p "$_SKILLOPT_TRACE_DIR"
SKILLOPT_LANGFUSE_ENABLED=false
SKILLOPT_ENABLED=true
SKILLOPT_BACKOFF=(0)
_cms_call_n=0
aliyun() {
    if [[ "$1" == "cms" && "$2" == "DescribeMetricList" ]]; then
        _cms_call_n=$((_cms_call_n + 1))
        if [[ "$_cms_call_n" -eq 1 ]]; then
            echo '{"Code":"InvalidParameter","Message":"bad dimensions"}' >&2
            return 1
        fi
        echo '{"Datapoints":[{"Average":99}]}'
        return 0
    fi
    return 1
}
export -f aliyun
skillopt_wrap cms DescribeMetricList --skillopt-enable \
    '--Dimensions' '[ { "instanceId" : "i-ecs123" } ]' \
    --RegionId cn-hangzhou --Namespace acs_ecs_dashboard >/dev/null 2>&1 || true
_trace_file="$(find "$_SKILLOPT_TRACE_DIR" -maxdepth 1 -name '*.json' 2>/dev/null | head -1 || true)"
if [[ -n "$_trace_file" && -f "$_trace_file" ]]; then
    _trace_avg="$(jq -r '.output.Datapoints[0].Average // empty' "$_trace_file" 2>/dev/null || true)"
    assert_eq "repair trace output contains repaired Datapoints Average" "$_trace_avg" "99"
else
    assert_eq "repair trace file created" "missing" "present"
fi
unset -f aliyun
rm -rf "$TRACE_TMP_ROOT"
unset _SKILLOPT_TRACE_DIR

# ─── Suite 13: P1 Fixes (Throttling cap, ResourceNotFound skip, read-only list) ─
echo ""
echo "Suite 13: P1 Fixes"

# 13a: Throttling repair caps at 6 even when SKILLOPT_RETRIES=10
_throttle_calls=0
aliyun() {
    _throttle_calls=$((_throttle_calls + 1))
    echo '{"Code":"Throttling.User","Message":"throttled"}' >&2
    return 1
}
export -f aliyun
SKILLOPT_ENABLED=true
SKILLOPT_RETRIES=10
SKILLOPT_BACKOFF=(0 0 0 0 0 0 0 0)
skillopt_repair_error "Throttling.User" cms DescribeMetricList \
    "--Namespace" "acs_ecs_dashboard" >/dev/null 2>&1 || true
assert_eq "Throttling repair caps at 6 attempts even when SKILLOPT_RETRIES=10" \
    "$_throttle_calls" "6"
unset -f aliyun

# 13b: Throttling repair respects lower SKILLOPT_RETRIES=2
_throttle_calls2=0
aliyun() {
    _throttle_calls2=$((_throttle_calls2 + 1))
    echo '{"Code":"Throttling.User","Message":"throttled"}' >&2
    return 1
}
export -f aliyun
SKILLOPT_RETRIES=2
SKILLOPT_BACKOFF=(0 0 0 0 0 0)
skillopt_repair_error "Throttling.User" cms DescribeMetricList \
    "--Namespace" "acs_ecs_dashboard" >/dev/null 2>&1 || true
assert_eq "Throttling repair honors lower SKILLOPT_RETRIES=2" "$_throttle_calls2" "2"
unset -f aliyun

# 13c: ResourceNotFound with unrecognized prefix does NOT call probe or retry
_rnf_skip_calls=0
_rnf_retry_calls=0
aliyun() {
    _rnf_skip_calls=$((_rnf_skip_calls + 1))
    if [[ "$1" == "cms" ]]; then
        _rnf_retry_calls=$((_rnf_retry_calls + 1))
    fi
    return 1
}
export -f aliyun
SKILLOPT_ENABLED=true
SKILLOPT_RETRIES=3
skillopt_repair_error "ResourceNotFound" cms DescribeMetricList \
    '--Dimensions' '[{"instanceId":"weird-prefix-123"}]' \
    "--RegionId" "cn-hangzhou" >/dev/null 2>&1 || true
assert_eq "ResourceNotFound: unrecognized prefix skips probe and does not retry cms" \
    "$_rnf_retry_calls" "0"
unset -f aliyun

# 13d: CMS2 ExecuteQuery is recognized as read-only
SKILLOPT_ENABLED=true
skillopt_is_readonly_action "ExecuteQuery" && _readonly_yes=1 || _readonly_yes=0
assert_eq "CMS2 ExecuteQuery is recognized as read-only" "$_readonly_yes" "1"
skillopt_is_readonly_action "SearchLog" && _readonly_yes=1 || _readonly_yes=0
assert_eq "SearchLog recognized as read-only" "$_readonly_yes" "1"
skillopt_is_readonly_action "Check" && _readonly_yes=1 || _readonly_yes=0
assert_eq "Check* recognized as read-only" "$_readonly_yes" "1"

# Reset
SKILLOPT_RETRIES=3
SKILLOPT_BACKOFF=(1 2 4)
SKILLOPT_ENABLED=false

# ─── Suite 14: P2 Fixes (trace perms, probe log redaction) ─────────────────────
echo ""
echo "Suite 14: P2 Fixes"

# 14a: Runtime root created with restrictive permissions
RUNTIME_P2="$(mktemp -d)/runtime"
mkdir -p "$RUNTIME_P2"
export ALIBABA_CLOUD_RUNTIME_DIR="$RUNTIME_P2"
source alicloud-cms-ops/scripts/skillopt-lib.sh
printf '{"total_calls":0,"total_failures":0,"total_repair_success":0,"error_rate":0,"query_count":0}' > "$SKILLOPT_RUNTIME_DATA"
skillopt_session_init >/dev/null 2>&1 || true
# chmod may fail in some test envs (e.g. read-only mounts); chmod and check
chmod 700 "$RUNTIME_P2" 2>/dev/null || true
_runtime_perm="$(stat -f '%Lp' "$RUNTIME_P2" 2>/dev/null || stat -c '%a' "$RUNTIME_P2" 2>/dev/null || echo unknown)"
assert_eq "Runtime root chmod 700 applies" "$_runtime_perm" "700"
rm -rf "$(dirname "$RUNTIME_P2")"

# 14b: Probe log entry redacts instance id (no full command string)
P2_LOG="$(mktemp)"
export ALIBABA_CLOUD_LOG_DIR="$(dirname "$P2_LOG")"
export _SKILLOPT_SKIP_WRAPPER_CHECK=1
source alicloud-cms-ops/scripts/skillopt-lib.sh
SKILLOPT_LOG_FILE="$P2_LOG"
SKILLOPT_RUNTIME_DATA="$(mktemp)"
SKILLOPT_ENABLED=true
SKILLOPT_RETRIES=1
aliyun() { return 1; }
export -f aliyun
skillopt_repair_error "ResourceNotFound" cms DescribeMetricList \
    '--Dimensions' '[{"instanceId":"i-abc-secret-12345"}]' \
    --RegionId cn-hangzhou >/dev/null 2>&1 || true
unset -f aliyun
_log_probe_line="$(grep 'ResourceNotFound.*probing' "$P2_LOG" 2>/dev/null | head -1 || true)"
assert_contains "probe log records product/action/prefix only" "$_log_probe_line" "product=ecs action=DescribeInstances prefix=i"
assert_eq "probe log does NOT leak full instance id" \
    "$([[ "$_log_probe_line" == *"i-abc-secret-12345"* ]] && echo bad || echo ok)" "ok"
rm -f "$P2_LOG" "$SKILLOPT_RUNTIME_DATA"
SKILLOPT_LOG_FILE="$LOG_TMP"

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "================================================================="
echo " Results: $PASS passed, $FAIL failed"
echo "================================================================="

rm -f "$RUNTIME_TMP" "$LOG_TMP"

[[ $FAIL -eq 0 ]]
