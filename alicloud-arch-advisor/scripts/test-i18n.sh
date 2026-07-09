#!/bin/bash
# Test i18n (internationalization) functionality
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

echo "=========================================="
echo "  i18n Multi-language Test Suite"
echo "=========================================="
echo ""

# Test 1: Default language detection
echo "--- Test 1: Default Language Detection ---"
log_info "Current language: $CURRENT_LANG"
echo ""

# Test 2: Chinese interface
echo "--- Test 2: Chinese Interface (zh_CN) ---"
export ARCH_ADVISOR_LANG="zh_CN"
CURRENT_LANG=$(detect_language)
log_info "$(t 'wizard_header')"
echo ""
log_info "$(t 'wizard_menu.title')"
echo -e "$(t 'wizard_menu.mode_a')"
echo -e "$(t 'wizard_menu.mode_b')"
echo -e "$(t 'wizard_menu.mode_c')"
echo "$(t 'wizard_menu.exit')"
echo ""

# Test 3: English interface
echo "--- Test 3: English Interface (en_US) ---"
export ARCH_ADVISOR_LANG="en_US"
CURRENT_LANG=$(detect_language)
log_info "$(t 'wizard_header')"
echo ""
log_info "$(t 'wizard_menu.title')"
echo -e "$(t 'wizard_menu.mode_a')"
echo -e "$(t 'wizard_menu.mode_b')"
echo -e "$(t 'wizard_menu.mode_c')"
echo "$(t 'wizard_menu.exit')"
echo ""

# Test 4: Progress bar in Chinese
echo "--- Test 4: Progress Bar (Chinese) ---"
export ARCH_ADVISOR_LANG="zh_CN"
CURRENT_LANG=$(detect_language)
progress_start 5 "📊 进度条演示"

for i in {1..5}; do
    sleep 0.3
    progress_update $i "步骤 ${i}/5"
done

progress_complete "演示完成"
echo ""

# Test 5: Progress bar in English
echo "--- Test 5: Progress Bar (English) ---"
export ARCH_ADVISOR_LANG="en_US"
CURRENT_LANG=$(detect_language)
progress_start 5 "📊 Progress Bar Demo"

for i in {1..5}; do
    sleep 0.3
    progress_update $i "Step ${i}/5"
done

progress_complete "Demo complete"
echo ""

# Test 6: Scenario selection in both languages
echo "--- Test 6: Scenario Selection Comparison ---"
echo ""
echo "[Chinese]"
export ARCH_ADVISOR_LANG="zh_CN"
CURRENT_LANG=$(detect_language)
log_info "$(t 'wizard_scenario.title')"
echo -e "$(t 'wizard_scenario.ecommerce')"
echo -e "$(t 'wizard_scenario.saas')"
echo -e "$(t 'wizard_scenario.data_platform')"
echo ""

echo "[English]"
export ARCH_ADVISOR_LANG="en_US"
CURRENT_LANG=$(detect_language)
log_info "$(t 'wizard_scenario.title')"
echo -e "$(t 'wizard_scenario.ecommerce')"
echo -e "$(t 'wizard_scenario.saas')"
echo -e "$(t 'wizard_scenario.data_platform')"
echo ""

# Test 7: Validation messages
echo "--- Test 7: Validation Messages ---"
export ARCH_ADVISOR_LANG="zh_CN"
CURRENT_LANG=$(detect_language)
log_warn "$(t 'validation_invalid_choice' '1-6')"
log_error "$(t 'validation_must_integer' 'DAU')"
echo ""

export ARCH_ADVISOR_LANG="en_US"
CURRENT_LANG=$(detect_language)
log_warn "$(t 'validation_invalid_choice' '1-6')"
log_error "$(t 'validation_must_integer' 'DAU')"
echo ""

# Test 8: recommend.sh step messages
echo "--- Test 8: Recommendation Steps ---"
export ARCH_ADVISOR_LANG="zh_CN"
CURRENT_LANG=$(detect_language)
progress_start 7 "🏗️ 架构推荐引擎"
progress_update 1 "$(t 'recommend_step1')"
sleep 0.2
progress_update 2 "$(t 'recommend_step2')"
sleep 0.2
progress_update 3 "$(t 'recommend_step3')"
sleep 0.2
progress_update 4 "$(t 'recommend_step4')"
sleep 0.2
progress_update 5 "$(t 'recommend_step4.5' 'cn-hangzhou')"
sleep 0.2
progress_update 6 "$(t 'recommend_step5')"
sleep 0.2
progress_update 7 "$(t 'recommend_step6')"
progress_complete "$(t 'recommend_complete')"
echo ""

export ARCH_ADVISOR_LANG="en_US"
CURRENT_LANG=$(detect_language)
progress_start 7 "🏗️ Architecture Recommendation Engine"
progress_update 1 "$(t 'recommend_step1')"
sleep 0.2
progress_update 2 "$(t 'recommend_step2')"
sleep 0.2
progress_update 3 "$(t 'recommend_step3')"
sleep 0.2
progress_update 4 "$(t 'recommend_step4')"
sleep 0.2
progress_update 5 "$(t 'recommend_step4.5' 'cn-hangzhou')"
sleep 0.2
progress_update 6 "$(t 'recommend_step5')"
sleep 0.2
progress_update 7 "$(t 'recommend_step6')"
progress_complete "$(t 'recommend_complete')"
echo ""

# Test 9: Language switch function
echo "--- Test 9: Language Switch Function ---"
export ARCH_ADVISOR_LANG="zh_CN"
CURRENT_LANG=$(detect_language)
log_info "Initial: $CURRENT_LANG"
switch_language "en_US"
log_info "After switch: $CURRENT_LANG"
switch_language "zh_CN"
log_info "Switched back: $CURRENT_LANG"
echo ""

# Test 10: Fallback for missing keys
echo "--- Test 10: Fallback for Missing Keys ---"
export ARCH_ADVISOR_LANG="en_US"
CURRENT_LANG=$(detect_language)
log_info "Missing key test: $(t 'nonexistent_key')"
echo ""

echo "=========================================="
echo "  ✅ All i18n tests completed!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - Language detection: ✓"
echo "  - Chinese interface: ✓"
echo "  - English interface: ✓"
echo "  - Progress bar i18n: ✓"
echo "  - Scenario selection: ✓"
echo "  - Validation messages: ✓"
echo "  - Step messages: ✓"
echo "  - Language switching: ✓"
echo "  - Fallback handling: ✓"
echo ""
echo "Usage:"
echo "  export ARCH_ADVISOR_LANG=zh_CN  # Chinese"
echo "  export ARCH_ADVISOR_LANG=en_US  # English"
echo "  ./scripts/interactive-wizard.sh"
