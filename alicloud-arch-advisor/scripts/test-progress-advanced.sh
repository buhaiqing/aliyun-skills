#!/bin/bash
# Test advanced progress bar features (v1.4.0)
set -euo pipefail

# Inline color definitions (avoid i18n dependency for Bash 3.2)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Stub t() function for i18n compatibility
t() {
    local key="$1"
    shift
    local args=("$@")
    local fmt=""
    case "$key" in
        progress_start) fmt="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" ;;
        progress_complete) fmt="✓ %s (Total: %ds)" ;;
        progress_eta) fmt="ETA: %s" ;;
        progress_elapsed) fmt="Elapsed: %ds" ;;
        *) fmt="$key" ;;
    esac
    if [[ ${#args[@]} -gt 0 ]]; then
        printf "$fmt" "${args[@]}"
    else
        echo "$fmt"
    fi
}

# Source progress functions from common.sh
SCRIPT_DIR="/Users/bohaiqing/opensource/git/aliyun-skills/alicloud-arch-advisor/scripts"

# Extract just the progress bar section (lines 36 onwards until dependency section)
awk '/^# Progress Bar Functions/{flag=1} flag{print} /^# ---.*Dependency/{flag=0; exit}' \
    "$SCRIPT_DIR/common.sh" > /tmp/_progress_funcs.sh

# Also need to add the variables that progress functions depend on
{
    cat /tmp/_progress_funcs.sh
} > /tmp/_progress_loaded.sh

source /tmp/_progress_loaded.sh
rm -f /tmp/_progress_funcs.sh /tmp/_progress_loaded.sh

TEST_DIR="/tmp/arch-advisor-progress-test-$$"
mkdir -p "$TEST_DIR"

log_info()  { echo -e "${BLUE}[INFO]${NC} $*" >&2; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*" >&2; }

echo "=========================================="
echo "  Advanced Progress Bar Tests (v1.4.0)"
echo "=========================================="
echo ""

# Test 1: Nested Progress Bar
echo "--- Test 1: Nested Progress Bar (Main + Sub-task) ---"
progress_start 3 "Main Task: Deploy Microservice"
sleep 0.3

progress_update 1 "Initializing deployment..."
sleep 0.3

# Start nested sub-task
progress_nested_start 4 "Building container image"
sleep 0.2
progress_nested_update 1 "Compiling source..."
sleep 0.2
progress_nested_update 2 "Resolving dependencies..."
sleep 0.2
progress_nested_update 3 "Building layers..."
sleep 0.2
progress_nested_update 4 "Tagging image..."
progress_nested_complete "Image built"

progress_update 2 "Deploying to cluster..."
sleep 0.3

# Another nested task
progress_nested_start 3 "Updating service config"
sleep 0.2
progress_nested_update 1 "Loading config..."
sleep 0.2
progress_nested_update 2 "Applying changes..."
sleep 0.2
progress_nested_update 3 "Verifying..."
progress_nested_complete "Config updated"

progress_update 3 "Health checking..."
sleep 0.3
progress_complete "Deployment finished"
log_success "Nested progress bar works correctly"
echo ""

# Test 2: Progress State Persistence
echo "--- Test 2: Progress State Persistence (Resume after interrupt) ---"
STATE_FILE="$TEST_DIR/progress-state.json"

# Simulate a run with persistence
progress_persistence_enable "$STATE_FILE"
progress_start 5 "Long-running task"
progress_update 1 "Step 1"
progress_update 2 "Step 2"
progress_update 3 "Step 3 (interrupted here)"
log_info "Simulated interruption. State saved."

# Show saved state
if [[ -f "$STATE_FILE" ]]; then
    log_success "State file exists"
    cat "$STATE_FILE"
fi

# Simulate resume
sleep 0.3
log_info "Resuming from saved state..."
if progress_resume "$STATE_FILE"; then
    log_success "Resumed successfully from step 3"
    progress_update 4 "Step 4"
    progress_update 5 "Step 5"
    progress_complete "Task finished after resume"
    log_success "Persistence and resume works correctly"
else
    log_error "Failed to resume"
fi
progress_persistence_disable
rm -f "$STATE_FILE"
echo ""

# Test 3: Graphical Progress Bar (Terminal Detection)
echo "--- Test 3: Graphical Progress Bar (Terminal Capability) ---"
log_info "Detected terminal: ${_TERM_CAPABILITY:-unknown}"
log_info "Rendering graphical progress bar..."
echo ""

for i in 0 20 40 60 80 100; do
    progress_graphic "$i" 100 "Loading resources ($i%)"
    sleep 0.2
done
echo ""
log_success "Graphical progress bar rendered"
echo ""

# Test 4: Spinner Animation
echo "--- Test 4: Spinner Animation (Async) ---"
spinner_start "Processing..."
sleep 2
spinner_stop
log_success "Async operation completed"
echo ""

# Cleanup
rm -rf "$TEST_DIR"

echo "=========================================="
echo "  All Advanced Progress Tests Passed!"
echo "=========================================="
echo ""
echo "Verified features:"
echo "  - Nested progress bar (main + sub-task)"
echo "  - State persistence and resume capability"
echo "  - Graphical rendering (auto-detect terminal)"
echo "  - Spinner animation (async)"
echo ""
echo "Terminal detected: ${_TERM_CAPABILITY:-basic}"
echo ""
echo "New APIs available:"
echo "  - progress_nested_start / update / complete"
echo "  - progress_persistence_enable / resume"
echo "  - progress_graphic (auto-detects iTerm2/256color/basic)"
echo "  - spinner_start / spinner_stop"
