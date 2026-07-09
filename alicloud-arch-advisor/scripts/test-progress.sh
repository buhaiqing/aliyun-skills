#!/bin/bash
# Test progress bar functionality
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

echo "=== Progress Bar Demo ==="
echo ""

# Demo 1: Simple progress
log_info "Demo 1: Basic progress tracking"
progress_start 5 "📊 Simple Progress Demo"

for i in {1..5}; do
    sleep 0.5
    progress_update $i "Step ${i} of 5"
done

progress_complete "Demo 1 complete"

# Demo 2: Simulated work with varying durations
log_info "Demo 2: Variable duration steps"
progress_start 4 "⚙️  Variable Duration Demo"

progress_update 1 "Initializing..."
sleep 1

progress_update 2 "Processing data (this takes longer)..."
sleep 2

progress_update 3 "Generating report..."
sleep 1

progress_update 4 "Finalizing..."
sleep 0.5

progress_complete "Demo 2 complete"

# Demo 3: Quick operations
log_info "Demo 3: Rapid operations"
progress_start 10 "🚀 Fast Operations"

for i in {1..10}; do
    sleep 0.1
    progress_update $i "Operation ${i}"
done

progress_complete "All demos completed successfully"

echo ""
log_success "Progress bar test finished!"
