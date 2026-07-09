#!/bin/bash

#=============================================================================
# Enhanced Pre-flight Check for Alibaba Cloud WAF Operations
#
# Design principles:
#   1. IDEMPOTENT - Safe to run multiple times, clean stale state before retry
#   2. SELF-HEALING - Auto-fix common issues (stale dirs, missing plugins)
#   3. STRUCTURED OUTPUT - JSON + env vars for downstream consumption
#   4. PARAMETER-AGNOSTIC - Detects CLI parameter naming (--region vs --RegionId)
#   5. GRACEFUL DEGRADATION - Each check is independent; failure in one doesn't block others
#
# Exit codes:
#   0 = PASS - CLI path recommended
#   1 = FAIL - Critical issues, cannot proceed
#   2 = WARNING - SDK fallback recommended
#=============================================================================

# --- Output file (machine-readable) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULT_FILE="${PRESULT_FILE:-$SCRIPT_DIR/preflight-result.json}"
ENV_EXPORT_FILE="${PRESULT_ENV_FILE:-$SCRIPT_DIR/preflight-env.sh}"

# --- Color ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- Result accumulator ---
OVERALL_STATUS="PASS"
ISSUES=()
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNED=0

# --- Detected capabilities (populated during checks) ---
DETECTED_SHELL=""
DETECTED_CLI_PARAM_STYLE=""
DETECTED_CLI_PLUGIN_INSTALLED=false
DETECTED_CLI_WORKING=false
DETECTED_SDK_AVAILABLE=false
DETECTED_CREDENTIALS_VALID=false
DETECTED_ENDPOINT_REACHABLE=false
DETECTED_ENV_FILE=""
DETECTED_OS=""
DETECTED_ARCH=""
DETECTED_WAF_INSTANCE_EXISTS=false
DETECTED_REGION_VALID=false

# --- WAF-specific: Supported regions ---
WAF_SUPPORTED_REGIONS=(
    "cn-hangzhou"
    "cn-shanghai"
    "cn-qingdao"
    "cn-beijing"
    "cn-zhangjiakou"
    "cn-huhehaote"
    "cn-shenzhen"
    "cn-chengdu"
    "cn-hongkong"
    "ap-southeast-1"
    "ap-southeast-2"
    "ap-southeast-3"
    "ap-southeast-5"
    "us-west-1"
    "us-east-1"
    "eu-central-1"
)

#=============================================================================
# Utility functions
#=============================================================================

add_issue() {
    local severity="$1" issue="$2" suggestion="$3"
    ISSUES+=("$severity|$issue|$suggestion")
    if [ "$severity" = "CRITICAL" ]; then
        OVERALL_STATUS="FAIL"
    elif [ "$severity" = "WARNING" ] && [ "$OVERALL_STATUS" != "FAIL" ]; then
        OVERALL_STATUS="WARNING"
    fi
}

print_status() {
    local status="$1" message="$2"
    case "$status" in
        PASS) echo -e "${GREEN}[✓]${NC} $message"; CHECKS_PASSED=$((CHECKS_PASSED + 1)) ;;
        FAIL) echo -e "${RED}[✗]${NC} $message"; CHECKS_FAILED=$((CHECKS_FAILED + 1)) ;;
        WARN) echo -e "${YELLOW}[!]${NC} $message"; CHECKS_WARNED=$((CHECKS_WARNED + 1)) ;;
        INFO) echo -e "${BLUE}[i]${NC} $message" ;;
    esac
}

section() {
    echo ""
    echo -e "${BLUE}[$1] $2${NC}"
    echo "-----------------------------------"
}

version_ge() {
    local v1=$(echo "$1" | sed 's/^v//' | sed 's/^go//')
    local v2=$(echo "$2" | sed 's/^v//' | sed 's/^go//')
    [ "$(printf '%s\n' "$v1" "$v2" | sort -V | tail -1)" = "$v1" ]
}

#=============================================================================
# JSON output helpers (avoids nested $() in heredocs)
#=============================================================================

build_issues_json() {
    local first=true
    for issue in "${ISSUES[@]}"; do
        local severity=$(echo "$issue" | cut -d'|' -f1)
        local problem=$(echo "$issue" | cut -d'|' -f2)
        local suggestion=$(echo "$issue" | cut -d'|' -f3)
        local comma=""
        $first && first=false || comma=","
        local problem_escaped
        problem_escaped=$(printf '%s' "$problem" | sed 's/"/\\"/g')
        local suggestion_escaped
        suggestion_escaped=$(printf '%s' "$suggestion" | sed 's/"/\\"/g')
        echo "${comma}{\"severity\":\"$severity\",\"issue\":\"$problem_escaped\",\"suggestion\":\"$suggestion_escaped\"}"
    done
}

write_result_json() {
    local rec_path="sdk-fallback"
    [ "$OVERALL_STATUS" = "FAIL" ] && rec_path="none"
    [ "$OVERALL_STATUS" = "PASS" ] && rec_path="cli"

    local issues_json
    issues_json=$(build_issues_json)

    cat > "$RESULT_FILE" <<JSONEOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "overall_status": "$OVERALL_STATUS",
  "summary": {
    "passed": $CHECKS_PASSED,
    "failed": $CHECKS_FAILED,
    "warnings": $CHECKS_WARNED
  },
  "capabilities": {
    "cli_installed": ${DETECTED_CLI_WORKING:-false},
    "plugin_installed": ${DETECTED_CLI_PLUGIN_INSTALLED:-false},
    "cli_param_style": "${DETECTED_CLI_PARAM_STYLE:-unknown}",
    "sdk_available": ${DETECTED_SDK_AVAILABLE:-false},
    "credentials_valid": ${DETECTED_CREDENTIALS_VALID:-false},
    "endpoint_reachable": ${DETECTED_ENDPOINT_REACHABLE:-false},
    "waf_instance_exists": ${DETECTED_WAF_INSTANCE_EXISTS:-false},
    "region_valid": ${DETECTED_REGION_VALID:-false}
  },
  "environment": {
    "shell": "${DETECTED_SHELL:-unknown}",
    "os": "${DETECTED_OS:-unknown}",
    "arch": "${DETECTED_ARCH:-unknown}",
    "env_file": "${DETECTED_ENV_FILE:-}"
  },
  "issues": [$issues_json],
  "recommended_path": "$rec_path",
  "note": "Source scripts/preflight-env.sh to export detected capabilities into your environment"
}
JSONEOF
    print_status "INFO" "Result written to: $RESULT_FILE"
}

write_env_export() {
    local rec_path="sdk-fallback"
    [ "$OVERALL_STATUS" = "FAIL" ] && rec_path="none"
    [ "$OVERALL_STATUS" = "PASS" ] && rec_path="cli"

    local cli_arg_region="--region"
    [ "$DETECTED_CLI_PARAM_STYLE" = "camelcase" ] && cli_arg_region="--RegionId"

    cat > "$ENV_EXPORT_FILE" <<ENVEOF
# Pre-flight detected capabilities
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Usage: source "$ENV_EXPORT_FILE"

export PREFLIGHT_STATUS="$OVERALL_STATUS"
export PREFLIGHT_CLI_WORKING="$DETECTED_CLI_WORKING"
export PREFLIGHT_CLI_PLUGIN_INSTALLED="$DETECTED_CLI_PLUGIN_INSTALLED"
export PREFLIGHT_CLI_PARAM_STYLE="$DETECTED_CLI_PARAM_STYLE"
export PREFLIGHT_CLI_ARG_REGION="$cli_arg_region"
export PREFLIGHT_SDK_AVAILABLE="$DETECTED_SDK_AVAILABLE"
export PREFLIGHT_CREDENTIALS_VALID="$DETECTED_CREDENTIALS_VALID"
export PREFLIGHT_SHELL="$DETECTED_SHELL"
export PREFLIGHT_RECOMMENDED_PATH="$rec_path"
export PREFLIGHT_WAF_INSTANCE_EXISTS="$DETECTED_WAF_INSTANCE_EXISTS"
export PREFLIGHT_REGION_VALID="$DETECTED_REGION_VALID"
ENVEOF
    print_status "INFO" "Env export written to: $ENV_EXPORT_FILE"
}

#=============================================================================
# Check 1: Environment Detection
#=============================================================================
section "1" "Environment Detection"

IS_CI=false
for ci_var in CI GITHUB_ACTIONS GITLAB_CI TRAVIS CIRCLECI; do
    [ -n "${!ci_var}" ] && IS_CI=true && break
done
$IS_CI && print_status "INFO" "Running in CI environment" || print_status "INFO" "Running in local environment"

DETECTED_OS=$(uname -s)
DETECTED_ARCH=$(uname -m)
print_status "INFO" "Operating System: $DETECTED_OS ($DETECTED_ARCH)"

DETECTED_SHELL=$(basename "${SHELL:-unknown}" 2>/dev/null || echo "unknown")
print_status "INFO" "Current shell: $DETECTED_SHELL"

if [ "$DETECTED_SHELL" = "zsh" ]; then
    print_status "WARN" "zsh detected - wrap CLI output expressions in quotes to avoid glob interpretation"
    add_issue "WARNING" "zsh shell may interpret [] as glob patterns" "Quote CLI --output arguments: --output 'cols=... rows=...'"
fi

#=============================================================================
# Check 2: Aliyun CLI Binary
#=============================================================================
section "2" "Aliyun CLI Binary"

CLI_VERSION=""
if command -v aliyun &>/dev/null; then
    CLI_VERSION=$(aliyun version 2>&1 | head -1 || echo "unknown")
    print_status "PASS" "Aliyun CLI installed: $CLI_VERSION"
else
    print_status "FAIL" "Aliyun CLI not found"
    add_issue "CRITICAL" "Aliyun CLI binary not found" "Install: /bin/bash -c \"\$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)\""
fi

#=============================================================================
# Check 3: CLI Plugin Installation (idempotent, self-healing)
#=============================================================================
section "3" "CLI Plugin (aliyun-cli-waf-openapi)"

PLUGIN_DIR="$HOME/.aliyun/plugins"
PLUGIN_NAME="aliyun-cli-waf-openapi"
PLUGIN_PATH="$PLUGIN_DIR/$PLUGIN_NAME"

is_stale_plugin_dir() {
    [ -d "$PLUGIN_PATH" ] && [ -z "$(ls -A "$PLUGIN_PATH" 2>/dev/null | grep -v '^\._')" ]
}

plugin_has_binary() {
    [ -f "$PLUGIN_PATH/$PLUGIN_NAME" ] && [ -x "$PLUGIN_PATH/$PLUGIN_NAME" ]
}

plugin_works() {
    local test_output
    test_output=$(aliyun waf-openapi DescribeInstanceInfo --region "$ALIBABA_CLOUD_REGION_ID" --version 2021-10-01 --force 2>&1 || true)
    ! echo "$test_output" | grep -qE "Plugin.*required.*not installed|is not a valid built-in product|not found"
}

if is_stale_plugin_dir; then
    print_status "WARN" "Stale/empty plugin directory detected: $PLUGIN_PATH"
    print_status "INFO" "Attempting cleanup..."
    if chmod -R u+w "$PLUGIN_PATH" 2>/dev/null && \
       xattr -cr "$PLUGIN_PATH" 2>/dev/null && \
       rm -rf "$PLUGIN_PATH" 2>/dev/null; then
        print_status "PASS" "Stale plugin directory cleaned successfully"
    else
        print_status "WARN" "Could not remove stale directory, deferring to plugin install"
        add_issue "WARNING" "Stale plugin directory with extended attributes" "Will retry via 'aliyun plugin install' which can sometimes overwrite"
    fi
fi

if plugin_works; then
    DETECTED_CLI_PLUGIN_INSTALLED=true
    DETECTED_CLI_WORKING=true
    print_status "PASS" "WAF plugin installed and verified (DescribeInstanceInfo SUCCESS)"
else
    print_status "WARN" "WAF plugin not working or not installed"
    DETECTED_CLI_PLUGIN_INSTALLED=false

    install_ok=false
    install_attempts=0
    max_install_attempts=2

    while [ $install_attempts -lt $max_install_attempts ] && ! $install_ok; do
        install_attempts=$((install_attempts + 1))
        print_status "INFO" "Installation attempt $install_attempts/$max_install_attempts..."

        install_output=$(aliyun plugin install --names "$PLUGIN_NAME" 2>&1 || true)

        if echo "$install_output" | grep -qE "installed successfully|Downloading"; then
            install_ok=true
            print_status "PASS" "Plugin installed successfully (attempt $install_attempts)"
        else
            print_status "WARN" "Standard install failed, trying --enable-pre fallback..."
            install_output=$(aliyun plugin install --names "$PLUGIN_NAME" --enable-pre 2>&1 || true)
            if echo "$install_output" | grep -qE "installed successfully|Downloading"; then
                install_ok=true
                print_status "PASS" "Plugin installed via --enable-pre fallback (attempt $install_attempts)"
            fi
        fi

        if $install_ok; then
            if plugin_works; then
                DETECTED_CLI_PLUGIN_INSTALLED=true
                DETECTED_CLI_WORKING=true
                print_status "PASS" "Plugin verified after installation"
            else
                print_status "WARN" "Plugin installed but verification failed"
                add_issue "WARNING" "Plugin installed but not functioning" "Try: aliyun plugin install --names $PLUGIN_NAME --enable-pre"
            fi
        elif [ $install_attempts -lt $max_install_attempts ]; then
            print_status "INFO" "Retrying installation after delay..."
            sleep 2
        fi
    done

    if ! $install_ok; then
        print_status "FAIL" "Plugin installation failed after $max_install_attempts attempts"
        add_issue "WARNING" "Cannot install aliyun-cli-waf-openapi plugin" "Use SDK fallback path: go run scripts/sdk-fallback.go"
    fi
fi

#=============================================================================
# Check 4: CLI Parameter Style Detection
#=============================================================================
section "4" "CLI Parameter Style Detection"

if $DETECTED_CLI_WORKING; then
    region_test=$(aliyun waf-openapi DescribeInstanceInfo --region "$ALIBABA_CLOUD_REGION_ID" --version 2021-10-01 --force 2>&1 || true)

    if echo "$region_test" | grep -qE "unknown flag|Error:"; then
        DETECTED_CLI_PARAM_STYLE="camelcase"
        print_status "INFO" "CLI parameter style: --RegionId (camelCase, per OpenAPI spec)"
    else
        DETECTED_CLI_PARAM_STYLE="long-hyphen"
        print_status "INFO" "CLI parameter style: --region (long-hyphen, simplified)"
    fi

    print_status "PASS" "Use PREFLIGHT_CLI_ARG_REGION env var for portable parameter naming"
else
    print_status "WARN" "CLI not working, skipping parameter style detection"
    DETECTED_CLI_PARAM_STYLE="unknown"
fi

#=============================================================================
# Check 5: Region Validation (WAF-specific)
#=============================================================================
section "5" "Region Validation (WAF)"

if [ -n "$ALIBABA_CLOUD_REGION_ID" ]; then
    DETECTED_REGION_VALID=false
    for region in "${WAF_SUPPORTED_REGIONS[@]}"; do
        if [ "$region" = "$ALIBABA_CLOUD_REGION_ID" ]; then
            DETECTED_REGION_VALID=true
            break
        fi
    done

    if $DETECTED_REGION_VALID; then
        print_status "PASS" "Region $ALIBABA_CLOUD_REGION_ID is supported by WAF"
    else
        print_status "FAIL" "Region $ALIBABA_CLOUD_REGION_ID is NOT supported by WAF"
        add_issue "CRITICAL" "Region not supported by WAF" "Use one of: ${WAF_SUPPORTED_REGIONS[*]}"
    fi
else
    print_status "WARN" "ALIBABA_CLOUD_REGION_ID not set, skipping region validation"
    add_issue "WARNING" "Region not set" "Set ALIBABA_CLOUD_REGION_ID to a WAF-supported region"
fi

#=============================================================================
# Check 6: Credentials (with API-level validation)
#=============================================================================
section "6" "Credentials"

ENV_CANDIDATES=(
    "$PWD/.env"
    "$SCRIPT_DIR/../.env"
    "$PROJECT_DIR/.env"
)

for candidate in "${ENV_CANDIDATES[@]}"; do
    if [ -f "$candidate" ]; then
        DETECTED_ENV_FILE="$candidate"
        print_status "INFO" "Found .env file: $candidate"
        set -a
        source "$candidate" 2>/dev/null || true
        set +a
        print_status "PASS" ".env file loaded successfully"
        break
    fi
done

if [ -z "$DETECTED_ENV_FILE" ]; then
    print_status "INFO" "No .env file found in: ${ENV_CANDIDATES[*]}"
fi

creds_ok=true
if [ -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" ]; then
    print_status "PASS" "ALIBABA_CLOUD_ACCESS_KEY_ID is set (length: ${#ALIBABA_CLOUD_ACCESS_KEY_ID})"
else
    print_status "FAIL" "ALIBABA_CLOUD_ACCESS_KEY_ID is NOT set"
    add_issue "CRITICAL" "Access Key ID missing" "Set env var or create .env file"
    creds_ok=false
fi

if [ -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" ]; then
    print_status "PASS" "ALIBABA_CLOUD_ACCESS_KEY_SECRET is set"
else
    print_status "FAIL" "ALIBABA_CLOUD_ACCESS_KEY_SECRET is NOT set"
    add_issue "CRITICAL" "Access Key Secret missing" "Set env var or create .env file"
    creds_ok=false
fi

if [ -n "$ALIBABA_CLOUD_REGION_ID" ]; then
    print_status "PASS" "ALIBABA_CLOUD_REGION_ID is set: $ALIBABA_CLOUD_REGION_ID"
else
    print_status "FAIL" "ALIBABA_CLOUD_REGION_ID is NOT set"
    add_issue "CRITICAL" "Region ID missing" "Set ALIBABA_CLOUD_REGION_ID"
    creds_ok=false
fi

if $creds_ok && $DETECTED_CLI_WORKING && $DETECTED_REGION_VALID; then
    api_args=""
    [ "$DETECTED_CLI_PARAM_STYLE" = "camelcase" ] && api_args="--RegionId" || api_args="--region"
    validate_output=$(aliyun waf-openapi DescribeInstanceInfo $api_args "$ALIBABA_CLOUD_REGION_ID" --version 2021-10-01 --force 2>&1 || true)

    if ! echo "$validate_output" | grep -qiE "error|traceid|unknown|unable"; then
        DETECTED_CREDENTIALS_VALID=true
        print_status "PASS" "API credential validation: SUCCESS (DescribeInstanceInfo returned)"
        
        # Check if WAF instance exists
        if echo "$validate_output" | grep -qE "InstanceId"; then
            DETECTED_WAF_INSTANCE_EXISTS=true
            print_status "PASS" "WAF instance exists"
        else
            print_status "WARN" "WAF instance may not exist or no permission to access"
            add_issue "WARNING" "WAF instance not found or no access" "Create WAF instance in console or check RAM permissions"
        fi
    else
        DETECTED_CREDENTIALS_VALID=false
        print_status "FAIL" "API credential validation: FAILED (DescribeInstanceInfo error)"
        add_issue "CRITICAL" "Credentials present but API call failed" "Check RAM permissions and key validity"
    fi
elif $creds_ok && ! $DETECTED_CLI_WORKING; then
    print_status "WARN" "CLI not available; credential API validation skipped (will use SDK fallback)"
fi

#=============================================================================
# Check 7: Go Runtime (SDK Fallback)
#=============================================================================
section "7" "Go Runtime (SDK Fallback)"

if command -v go &>/dev/null; then
    GO_VERSION=$(go version 2>&1 | awk '{print $3}' || echo "unknown")
    print_status "PASS" "Go runtime installed: $GO_VERSION"

    go_major=$(echo "$GO_VERSION" | sed -n 's/go\([0-9]*\).*/\1/p')
    go_minor=$(echo "$GO_VERSION" | sed -n 's/go[0-9]*\.\([0-9]*\).*/\1/p')

    if [ -n "$go_major" ] && [ -n "$go_minor" ] && version_ge "$go_major.$go_minor" "1.21"; then
        print_status "PASS" "Go version meets minimum requirement (1.21+)"
        DETECTED_SDK_AVAILABLE=true
    else
        print_status "WARN" "Go version $GO_VERSION may not meet minimum requirement (1.21+)"
        add_issue "WARNING" "Go version too old for SDK" "Upgrade to Go 1.21+ for SDK fallback"
        DETECTED_SDK_AVAILABLE=false
    fi

    if $DETECTED_SDK_AVAILABLE && [ -f "$SCRIPT_DIR/sdk-fallback.go" ] && [ -f "$SCRIPT_DIR/go.mod" ]; then
        if pushd "$SCRIPT_DIR" >/dev/null 2>&1; then
            compile_check=$(go build -o /dev/null sdk-fallback.go 2>&1 || true)
            if [ -z "$compile_check" ]; then
                print_status "PASS" "sdk-fallback.go compiles successfully"
            else
                print_status "WARN" "sdk-fallback.go has compilation issues: $(echo "$compile_check" | head -1)"
                add_issue "WARNING" "SDK fallback code may not compile" "Run: cd $SCRIPT_DIR && go mod tidy && go build sdk-fallback.go"
            fi
            popd >/dev/null 2>&1
        fi
    fi
else
    print_status "WARN" "Go runtime not installed (SDK fallback unavailable)"
    add_issue "WARNING" "Go not installed" "Install Go 1.21+ for SDK fallback capability"
    DETECTED_SDK_AVAILABLE=false
fi

#=============================================================================
# Check 8: Network Connectivity
#=============================================================================
section "8" "Network Connectivity"

ENDPOINT="wafopenapi.aliyuncs.com"
if ping -c 1 -W 2 "$ENDPOINT" &>/dev/null; then
    DETECTED_ENDPOINT_REACHABLE=true
    print_status "PASS" "Can reach $ENDPOINT"
else
    DETECTED_ENDPOINT_REACHABLE=false
    print_status "WARN" "Cannot reach $ENDPOINT (may be firewall/proxy)"
    add_issue "WARNING" "Cannot reach Alibaba Cloud endpoint" "Check firewall/proxy settings, or use private VPC endpoint"
fi

#=============================================================================
# Check 9: CLI Config File
#=============================================================================
section "9" "CLI Config"

CLI_CONFIG="$HOME/.aliyun/config.json"
if [ -f "$CLI_CONFIG" ]; then
    print_status "INFO" "CLI config file exists: $CLI_CONFIG"
    config_region=$(grep -o '"region"[[:space:]]*:[[:space:]]*"[^"]*"' "$CLI_CONFIG" 2>/dev/null | head -1 | cut -d'"' -f4 || echo "")
    if [ -n "$config_region" ]; then
        print_status "INFO" "CLI config default region: $config_region"
        if [ -z "$ALIBABA_CLOUD_REGION_ID" ]; then
            print_status "WARN" "Using CLI config region as fallback: $config_region"
            export ALIBABA_CLOUD_REGION_ID="$config_region"
        fi
    fi
else
    print_status "INFO" "No CLI config file found"
fi

#=============================================================================
# Summary
#=============================================================================
echo ""
echo -e "${BLUE}[10] Summary${NC}"
echo "==================================="

case "$OVERALL_STATUS" in
    PASS)
        echo -e "${GREEN}Overall Status: PASS${NC}"
        echo -e "${GREEN}All checks passed. CLI path is recommended.${NC}"
        ;;
    WARNING)
        echo -e "${YELLOW}Overall Status: WARNING${NC}"
        echo -e "${YELLOW}Some checks have warnings. SDK fallback recommended.${NC}"
        ;;
    FAIL)
        echo -e "${RED}Overall Status: FAIL${NC}"
        echo -e "${RED}Critical issues detected. Cannot proceed.${NC}"
        ;;
esac

echo ""
if [ ${#ISSUES[@]} -gt 0 ]; then
    echo "Issues Found:"
    echo "-------------"
    for issue in "${ISSUES[@]}"; do
        severity=$(echo "$issue" | cut -d'|' -f1)
        problem=$(echo "$issue" | cut -d'|' -f2)
        suggestion=$(echo "$issue" | cut -d'|' -f3)
        if [ "$severity" = "CRITICAL" ]; then
            echo -e "${RED}[CRITICAL]${NC} $problem"
        else
            echo -e "${YELLOW}[WARNING]${NC} $problem"
        fi
        echo "  -> $suggestion"
        echo ""
    done
fi

echo "Recommended Execution Path:"
echo "---------------------------"
case "$OVERALL_STATUS" in
    PASS)
        echo -e "${GREEN}✓ CLI (Primary):       aliyun waf-openapi <command> --version 2021-10-01 --force${NC}"
        echo -e "${GREEN}✓ SDK Fallback:        go run scripts/sdk-fallback.go${NC}"
        echo -e "${GREEN}✓ Source capabilities: source $ENV_EXPORT_FILE${NC}"
        ;;
    WARNING)
        echo -e "${YELLOW}◆ SDK Fallback (Recommended): go run scripts/sdk-fallback.go${NC}"
        echo -e "${YELLOW}◆ CLI (if available):         aliyun waf-openapi <command> --version 2021-10-01 --force${NC}"
        echo -e "${YELLOW}◆ Source capabilities:        source $ENV_EXPORT_FILE${NC}"
        ;;
    FAIL)
        echo -e "${RED}✗ Cannot proceed. Fix critical issues first.${NC}"
        echo -e "${RED}✗ See issues above for resolution steps.${NC}"
        ;;
esac

#=============================================================================
# Write outputs
#=============================================================================
write_result_json
write_env_export

echo ""
echo "=== Pre-flight Check Complete ==="

if [ "$OVERALL_STATUS" = "FAIL" ]; then
    exit 1
elif [ "$OVERALL_STATUS" = "WARNING" ]; then
    exit 2
else
    exit 0
fi
