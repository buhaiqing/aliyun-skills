#!/bin/bash
# Enhanced Pre-flight Check for Alibaba Cloud Redis/Tair Operations
# This script performs comprehensive environment validation before executing Redis operations

set -e

echo "=== Enhanced Pre-flight Check for Redis/Tair Operations ==="
echo ""

# Color codes for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track overall status
OVERALL_STATUS="PASS"
ISSUES=()

# Function to add issue
add_issue() {
    ISSUE="$1"
    SEVERITY="$2"
    SUGGESTION="$3"
    ISSUES+=("$SEVERITY|$ISSUE|$SUGGESTION")
    if [ "$SEVERITY" = "CRITICAL" ]; then
        OVERALL_STATUS="FAIL"
    elif [ "$SEVERITY" = "WARNING" ] && [ "$OVERALL_STATUS" != "FAIL" ]; then
        OVERALL_STATUS="WARNING"
    fi
}

# Function to print colored status
print_status() {
    STATUS="$1"
    MESSAGE="$2"
    if [ "$STATUS" = "PASS" ]; then
        echo -e "${GREEN}[✓]${NC} $MESSAGE"
    elif [ "$STATUS" = "FAIL" ]; then
        echo -e "${RED}[✗]${NC} $MESSAGE"
    elif [ "$STATUS" = "WARN" ]; then
        echo -e "${YELLOW}[!]${NC} $MESSAGE"
    elif [ "$STATUS" = "INFO" ]; then
        echo -e "${BLUE}[i]${NC} $MESSAGE"
    fi
}

# ============================================
# 1. Environment Detection
# ============================================
echo -e "${BLUE}[1] Environment Detection${NC}"
echo "-----------------------------------"

# Check if running in CI environment
IS_CI=false
if [ -n "$CI" ] || [ -n "$GITHUB_ACTIONS" ] || [ -n "$GITLAB_CI" ] || [ -n "$TRAVIS" ] || [ -n "$CIRCLECI" ]; then
    IS_CI=true
    print_status "INFO" "Running in CI environment"
else
    print_status "INFO" "Running in local environment"
fi

# Check operating system
OS=$(uname -s)
ARCH=$(uname -m)
print_status "INFO" "Operating System: $OS ($ARCH)"

# ============================================
# 2. Alibaba Cloud CLI Installation Check
# ============================================
echo ""
echo -e "${BLUE}[2] Alibaba Cloud CLI Installation${NC}"
echo "-----------------------------------"

if command -v aliyun &> /dev/null; then
    CLI_VERSION=$(aliyun version 2>&1 | head -n 1 || echo "unknown")
    print_status "PASS" "Alibaba Cloud CLI installed: $CLI_VERSION"
else
    print_status "FAIL" "Alibaba Cloud CLI not installed"
    add_issue "CRITICAL" "Alibaba Cloud CLI not found" "Install CLI: /bin/bash -c \"$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)\""
fi

# ============================================
# 3. CLI Plugin Installation Check (NEW!)
# ============================================
echo ""
echo -e "${BLUE}[3] CLI Plugin Installation Check${NC}"
echo "-----------------------------------"

if command -v aliyun &> /dev/null; then
    # Check if r-kvstore plugin is installed (more reliable check)
    # Try to execute a simple command to verify plugin is truly available
    PLUGIN_TEST=$(aliyun r-kvstore describe-regions 2>&1 || echo "")
    
    if echo "$PLUGIN_TEST" | grep -q "Plugin.*required.*not installed" || echo "$PLUGIN_TEST" | grep -q "is not a valid built-in product"; then
        print_status "FAIL" "Redis/Tair plugin (aliyun-cli-r-kvstore) not installed or not working"
        
        # Try to install plugin
        echo ""
        print_status "INFO" "Attempting to install Redis/Tair plugin..."
        
        # Check plugin directory permissions
        PLUGIN_DIR="$HOME/.aliyun/plugins"
        if [ -d "$PLUGIN_DIR" ]; then
            # Test write permission
            if [ -w "$PLUGIN_DIR" ]; then
                print_status "PASS" "Plugin directory has write permission"
                
                # Try installation
                INSTALL_OUTPUT=$(aliyun plugin install --names aliyun-cli-r-kvstore 2>&1 || echo "")
                if echo "$INSTALL_OUTPUT" | grep -q "Downloading" && ! echo "$INSTALL_OUTPUT" | grep -q "ERROR"; then
                    print_status "PASS" "Plugin installation successful"
                    
                    # Verify installation by testing command again
                    VERIFY_TEST=$(aliyun r-kvstore describe-regions 2>&1 || echo "")
                    if ! echo "$VERIFY_TEST" | grep -q "Plugin.*required.*not installed"; then
                        print_status "PASS" "Plugin verified and working"
                    else
                        print_status "FAIL" "Plugin installed but not working"
                        add_issue "CRITICAL" "Plugin installed but verification failed" "Use Go SDK fallback path"
                    fi
                else
                    print_status "FAIL" "Plugin installation failed"
                    add_issue "CRITICAL" "Plugin installation failed: $INSTALL_OUTPUT" "Try manual installation or use Go SDK fallback"
                fi
            else
                print_status "WARN" "Plugin directory lacks write permission (common in CI/restricted environments)"
                add_issue "WARNING" "Cannot install plugin due to permission restrictions" "Use Go SDK fallback path or fix permissions"
            fi
        else
            print_status "WARN" "Plugin directory does not exist"
            mkdir -p "$PLUGIN_DIR" 2>/dev/null || true
            if [ -d "$PLUGIN_DIR" ]; then
                print_status "PASS" "Plugin directory created"
                
                # Try installation after creating directory
                INSTALL_OUTPUT=$(aliyun plugin install --names aliyun-cli-r-kvstore 2>&1 || echo "")
                if echo "$INSTALL_OUTPUT" | grep -q "Downloading" && ! echo "$INSTALL_OUTPUT" | grep -q "ERROR"; then
                    print_status "PASS" "Plugin installation successful"
                else
                    add_issue "WARNING" "Cannot install plugin after creating directory" "Use Go SDK fallback path"
                fi
            else
                add_issue "WARNING" "Cannot create plugin directory" "Use Go SDK fallback path"
            fi
        fi
    else
        print_status "PASS" "Redis/Tair plugin installed and working"
    fi
fi

# ============================================
# 4. Credentials Check (Enhanced)
# ============================================
echo ""
echo -e "${BLUE}[4] Credentials Check${NC}"
echo "-----------------------------------"

# Check .env file first (NEW!)
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
    print_status "INFO" "Found .env file: $ENV_FILE"
    
    # Load .env file
    set -a
    source "$ENV_FILE" 2>/dev/null || true
    set +a
    print_status "PASS" ".env file loaded successfully"
else
    print_status "INFO" "No .env file found in current directory"
fi

# Check environment variables
if [ -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" ]; then
    print_status "PASS" "ALIBABA_CLOUD_ACCESS_KEY_ID is set (length: ${#ALIBABA_CLOUD_ACCESS_KEY_ID})"
else
    print_status "FAIL" "ALIBABA_CLOUD_ACCESS_KEY_ID is NOT set"
    add_issue "CRITICAL" "Access Key ID missing" "Set environment variable or create .env file"
fi

if [ -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" ]; then
    print_status "PASS" "ALIBABA_CLOUD_ACCESS_KEY_SECRET is set (masked for security)"
else
    print_status "FAIL" "ALIBABA_CLOUD_ACCESS_KEY_SECRET is NOT set"
    add_issue "CRITICAL" "Access Key Secret missing" "Set environment variable or create .env file"
fi

if [ -n "$ALIBABA_CLOUD_REGION_ID" ]; then
    print_status "PASS" "ALIBABA_CLOUD_REGION_ID is set: $ALIBABA_CLOUD_REGION_ID"
else
    print_status "WARN" "ALIBABA_CLOUD_REGION_ID is NOT set (will use default if available)"
    add_issue "WARNING" "Region ID not set" "Set ALIBABA_CLOUD_REGION_ID or specify region in commands"
fi

# Check CLI config file as fallback
CLI_CONFIG="$HOME/.aliyun/config.json"
if [ -f "$CLI_CONFIG" ]; then
    print_status "INFO" "CLI config file exists: $CLI_CONFIG"
    # Don't parse the file for security reasons, just acknowledge it exists
else
    print_status "INFO" "No CLI config file found"
fi

# ============================================
# 5. Go Runtime Check (Enhanced)
# ============================================
echo ""
echo -e "${BLUE}[5] Go Runtime Check (Fallback Path)${NC}"
echo "-----------------------------------"

if command -v go &> /dev/null; then
    GO_VERSION=$(go version 2>&1 | awk '{print $3}' || echo "unknown")
    print_status "PASS" "Go runtime installed: $GO_VERSION"
    
    # Check Go version compatibility (NEW!)
    GO_MAJOR=$(echo "$GO_VERSION" | sed -n 's/go\([0-9]*\).*/\1/p')
    GO_MINOR=$(echo "$GO_VERSION" | sed -n 's/go[0-9]*\.\([0-9]*\).*/\1/p')
    
    if [ "$GO_MAJOR" -ge 1 ] && [ "$GO_MINOR" -ge 21 ]; then
        print_status "PASS" "Go version meets minimum requirement (1.21+)"
    else
        print_status "WARN" "Go version may not meet minimum requirement (1.21+)"
        add_issue "WARNING" "Go version too old" "Upgrade Go to 1.21+ for SDK compatibility"
    fi
else
    print_status "WARN" "Go runtime not installed (SDK fallback unavailable)"
    add_issue "WARNING" "Go not installed" "Install Go 1.21+ for SDK fallback capability"
fi

# ============================================
# 6. Network Connectivity Check
# ============================================
echo ""
echo -e "${BLUE}[6] Network Connectivity Check${NC}"
echo "-----------------------------------"

# Test Alibaba Cloud endpoint connectivity
ENDPOINT="r-kvstore.aliyuncs.com"
if ping -c 1 -W 2 "$ENDPOINT" &> /dev/null; then
    print_status "PASS" "Can reach Alibaba Cloud endpoint: $ENDPOINT"
else
    print_status "WARN" "Cannot reach Alibaba Cloud endpoint (may be firewall/proxy issue)"
    add_issue "WARNING" "Network connectivity issue" "Check firewall/proxy settings"
fi

# ============================================
# 7. Summary and Recommendations
# ============================================
echo ""
echo -e "${BLUE}[7] Summary and Recommendations${NC}"
echo "==================================="

if [ "$OVERALL_STATUS" = "PASS" ]; then
    echo -e "${GREEN}Overall Status: PASS${NC}"
    echo -e "${GREEN}All pre-flight checks passed. Ready to execute Redis/Tair operations.${NC}"
elif [ "$OVERALL_STATUS" = "WARNING" ]; then
    echo -e "${YELLOW}Overall Status: WARNING${NC}"
    echo -e "${YELLOW}Some checks have warnings. Review recommendations below.${NC}"
else
    echo -e "${RED}Overall Status: FAIL${NC}"
    echo -e "${RED}Critical issues detected. Cannot proceed with operations.${NC}"
fi

echo ""

# Print issues and suggestions
if [ ${#ISSUES[@]} -gt 0 ]; then
    echo "Issues Found:"
    echo "-------------"
    for issue in "${ISSUES[@]}"; do
        SEVERITY=$(echo "$issue" | cut -d'|' -f1)
        PROBLEM=$(echo "$issue" | cut -d'|' -f2)
        SUGGESTION=$(echo "$issue" | cut -d'|' -f3)
        
        if [ "$SEVERITY" = "CRITICAL" ]; then
            echo -e "${RED}[CRITICAL]${NC} $PROBLEM"
        else
            echo -e "${YELLOW}[WARNING]${NC} $PROBLEM"
        fi
        echo "  Suggestion: $SUGGESTION"
        echo ""
    done
fi

# Execution path recommendation
echo "Recommended Execution Path:"
echo "---------------------------"
if [ "$OVERALL_STATUS" = "PASS" ]; then
    echo -e "${GREEN}✓ Use CLI (Primary Path): aliyun r-kvstore commands${NC}"
    echo -e "${GREEN}✓ SDK Fallback available if needed${NC}"
elif [ "$OVERALL_STATUS" = "WARNING" ]; then
    echo -e "${YELLOW}! CLI may have issues, SDK fallback recommended${NC}"
    echo -e "${YELLOW}! Or fix warnings before using CLI${NC}"
else
    echo -e "${RED}✗ CLI unavailable, must use SDK fallback${NC}"
    echo -e "${RED}✗ Or fix critical issues first${NC}"
fi

echo ""
echo "=== Pre-flight Check Complete ==="

# Return appropriate exit code
if [ "$OVERALL_STATUS" = "FAIL" ]; then
    exit 1
elif [ "$OVERALL_STATUS" = "WARNING" ]; then
    exit 2
else
    exit 0
fi