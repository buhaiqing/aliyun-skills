#!/bin/bash
# alicloud-arch-advisor - Internationalization (i18n) Module
# Supports Chinese (zh_CN) and English (en_US)
# Usage: source i18n.sh && t "key"

# Temporarily disable nounset for array initialization
set +u

# ---------------------------------------------------------------------------
# Language Detection
# ---------------------------------------------------------------------------
detect_language() {
    # Priority: 1. ARCH_ADVISOR_LANG env var, 2. LANG env var, 3. Default to zh_CN
    if [[ -n "${ARCH_ADVISOR_LANG:-}" ]]; then
        echo "$ARCH_ADVISOR_LANG"
    elif [[ "${LANG:-}" == *"zh_CN"* || "${LANG:-}" == *"zh-"* ]]; then
        echo "zh_CN"
    else
        echo "en_US"
    fi
}

CURRENT_LANG=$(detect_language)
export CURRENT_LANG

# ---------------------------------------------------------------------------
# Translation Dictionary
# ---------------------------------------------------------------------------
declare -A I18N_ZH_CN=(
    ["common_info"]="[信息]"
    ["common_warn"]="[警告]"
    ["common_error"]="[错误]"
    ["common_success"]="[成功]"
    
    # Progress Bar
    ["progress_start"]="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ["progress_complete"]="✓ %s (总耗时: %ds)"
    ["progress_eta"]="预计剩余: %s"
    ["progress_elapsed"]="已用时: %ds"
    
    # Interactive Wizard - Header
    ["wizard_header"]="╔══════════════════════════════════════════════════════════╗\n║     阿里云架构顾问 - 交互式向导 (Interactive Wizard)     ║\n╚══════════════════════════════════════════════════════════╝"
    ["wizard_menu_title"]="请选择您需要的服务:"
    ["wizard_menu_mode_a"]="1. 分析现有系统架构 (Mode A - Reverse Engineering)\n   适用场景：了解当前云资源布局、生成架构文档"
    ["wizard_menu_mode_b"]="2. 做一次 WAF 成熟度评估 (Mode B - Assessment)\n   适用场景：安全检查、架构评审、合规审计"
    ["wizard_menu_mode_c"]="3. 设计新系统架构方案 (Mode C - Recommendation)\n   适用场景：电商/游戏/SaaS 等新系统设计"
    ["wizard_menu_exit"]="0. 退出"
    
    # Interactive Wizard - Mode A/B Params
    ["wizard_param_region"]="阿里云地域"
    ["wizard_param_resource_group"]="资源组 ID (可选，直接回车跳过)"
    ["wizard_param_tags"]="标签过滤 (格式: key=value,key2=value2，可选)"
    ["wizard_param_vpc_id"]="VPC ID (可选，直接回车跳过)"
    ["wizard_param_pillars_title"]="请选择评估维度:"
    ["wizard_param_pillars_all"]="1. 全部维度 (security,reliability,performance,cost,efficiency)"
    ["wizard_param_pillars_security"]="2. 仅安全 (security)"
    ["wizard_param_pillars_reliability"]="3. 仅可靠性 (reliability)"
    ["wizard_param_pillars_performance"]="4. 仅性能 (performance)"
    ["wizard_param_pillars_cost"]="5. 仅成本 (cost)"
    ["wizard_param_pillars_efficiency"]="6. 仅效率 (efficiency)"
    ["wizard_param_pillars_custom"]="7. 自定义 (输入逗号分隔的维度)"
    ["wizard_param_output_format_title"]="输出格式:"
    ["wizard_param_output_format_md"]="1. Markdown (推荐)"
    ["wizard_param_output_format_json"]="2. JSON"
    ["wizard_confirm_title"]="=== 配置确认 ==="
    ["wizard_confirm_execute"]="确认执行？(y/n)"
    ["wizard_confirm_cancel"]="⚠ 已取消"
    
    # Interactive Wizard - Mode C Params
    ["wizard_scenario_title"]="请选择业务场景:"
    ["wizard_scenario_ecommerce"]="1. 电商平台 (ecommerce) - 高并发交易、商品搜索、订单处理"
    ["wizard_scenario_saas"]="2. SaaS 应用 (saas) - 多租户隔离、按需计费"
    ["wizard_scenario_data_platform"]="3. 数据平台 (data-platform) - 大数据分析、实时流计算"
    ["wizard_scenario_microservice"]="4. 微服务架构 (microservice) - 容器化、Service Mesh"
    ["wizard_scenario_serverless"]="5. Serverless 应用 (serverless) - 事件驱动、零运维"
    ["wizard_scenario_game"]="6. 游戏后端 (game) - 实时对战、高并发在线"
    ["wizard_param_dau"]="日活跃用户数 (DAU)"
    ["wizard_param_ha_title"]="高可用等级:"
    ["wizard_param_ha_single_az"]="1. 单可用区 (single-az) - 成本低，适合开发测试"
    ["wizard_param_ha_multi_az"]="2. 多可用区 (multi-az) - 推荐，自动故障切换"
    ["wizard_param_ha_multi_region"]="3. 多地域 (multi-region) - 最高可用，跨区域容灾"
    ["wizard_param_compliance_title"]="合规要求:"
    ["wizard_param_compliance_none"]="1. 无 (none)"
    ["wizard_param_compliance_pci"]="2. PCI DSS (支付卡行业数据安全标准)"
    ["wizard_param_compliance_hipaa"]="3. HIPAA (医疗健康信息)"
    ["wizard_param_compliance_gdpr"]="4. GDPR (欧盟通用数据保护条例)"
    ["wizard_param_budget"]="月预算上限 (USD，可选，直接回车跳过)"
    ["wizard_param_deploy_region"]="部署地域"
    
    # Execution Messages
    ["wizard_exec_mode_a"]=">>> 启动架构分析模式 (Mode A)"
    ["wizard_exec_mode_b"]=">>> 启动 WAF 评估模式 (Mode B)"
    ["wizard_exec_mode_c"]=">>> 启动架构方案推荐模式 (Mode C)"
    ["wizard_exec_running_analysis"]="正在执行架构分析..."
    ["wizard_exec_running_assessment"]="正在执行 WAF 评估..."
    ["wizard_exec_generating"]="正在生成架构方案..."
    ["wizard_exec_timeout"]="操作超时(30分钟)。请检查网络连接或稍后重试。"
    ["wizard_exec_failed"]="操作失败(退出码: %d)"
    ["wizard_exec_success_analysis"]="架构分析完成"
    ["wizard_exec_success_assessment"]="WAF 评估完成"
    ["wizard_exec_success_recommendation"]="架构方案生成完成"
    ["wizard_goodbye"]="感谢使用，再见！"
    
    # Validation
    "validation_invalid_choice"]="✗ 无效选择，请输入 %s"
    "validation_must_integer"]="✗ %s 必须是正整数"
    
    # recommend.sh Steps
    "recommend_step1"]="Checking dependencies..."
    "recommend_step2"]="Initializing recommendation report..."
    "recommend_step3"]="Validating scenario and loading template..."
    "recommend_step4"]="Customizing architecture template..."
    "recommend_step4.5"]="Validating component availability in %s..."
    "recommend_step5"]="Generating architecture blueprint..."
    "recommend_step6"]="Saving recommendation blueprint..."
    ["recommend_complete"]="Architecture recommendation generated successfully"
)

# Re-enable nounset
set -u

# Temporarily disable nounset for array initialization
set +u

declare -A I18N_EN_US=(
    ["common_info"]="[INFO]"
    ["common_warn"]="[WARN]"
    ["common_error"]="[ERROR]"
    ["common_success"]="[SUCCESS]"
    
    # Progress Bar
    ["progress_start"]="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ["progress_complete"]="✓ %s (Total: %ds)"
    ["progress_eta"]="ETA: %s"
    ["progress_elapsed"]="Elapsed: %ds"
    
    # Interactive Wizard - Header
    ["wizard_header"]="╔══════════════════════════════════════════════════════════╗\n║  Alibaba Cloud Architecture Advisor - Interactive Wizard   ║\n╚══════════════════════════════════════════════════════════╝"
    ["wizard_menu_title"]="Please select the service you need:"
    ["wizard_menu_mode_a"]="1. Analyze Existing Architecture (Mode A - Reverse Engineering)\n   Use case: Understand current cloud resource layout, generate architecture docs"
    ["wizard_menu_mode_b"]="2. Perform WAF Maturity Assessment (Mode B - Assessment)\n   Use case: Security audit, architecture review, compliance check"
    ["wizard_menu_mode_c"]="3. Design New Architecture Solution (Mode C - Recommendation)\n   Use case: E-commerce/Gaming/SaaS new system design"
    ["wizard_menu_exit"]="0. Exit"
    
    # Interactive Wizard - Mode A/B Params
    ["wizard_param_region"]="Alibaba Cloud Region"
    ["wizard_param_resource_group"]="Resource Group ID (optional, press Enter to skip)"
    ["wizard_param_tags"]="Tag Filter (format: key=value,key2=value2, optional)"
    ["wizard_param_vpc_id"]="VPC ID (optional, press Enter to skip)"
    ["wizard_param_pillars_title"]="Please select assessment dimensions:"
    ["wizard_param_pillars_all"]="1. All Dimensions (security,reliability,performance,cost,efficiency)"
    ["wizard_param_pillars_security"]="2. Security Only"
    ["wizard_param_pillars_reliability"]="3. Reliability Only"
    ["wizard_param_pillars_performance"]="4. Performance Only"
    ["wizard_param_pillars_cost"]="5. Cost Only"
    ["wizard_param_pillars_cost_2"]="5. Cost Only"
    ["wizard_param_pillars_efficiency"]="6. Efficiency Only"
    ["wizard_param_pillars_custom"]="7. Custom (enter comma-separated dimensions)"
    ["wizard_param_output_format_title"]="Output Format:"
    ["wizard_param_output_format_md"]="1. Markdown (Recommended)"
    ["wizard_param_output_format_json"]="2. JSON"
    ["wizard_confirm_title"]="=== Configuration Confirmation ==="
    ["wizard_confirm_execute"]="Confirm execution? (y/n)"
    ["wizard_confirm_cancel"]="⚠ Cancelled"
    
    # Interactive Wizard - Mode C Params
    ["wizard_scenario_title"]="Please select business scenario:"
    ["wizard_scenario_ecommerce"]="1. E-commerce Platform - High concurrency transactions, product search, order processing"
    ["wizard_scenario_saas"]="2. SaaS Application - Multi-tenant isolation, pay-as-you-go"
    ["wizard_scenario_data_platform"]="3. Data Platform - Big data analytics, real-time stream computing"
    ["wizard_scenario_microservice"]="4. Microservices Architecture - Containerized, Service Mesh"
    ["wizard_scenario_serverless"]="5. Serverless Application - Event-driven, zero operations"
    ["wizard_scenario_game"]="6. Game Backend - Real-time battles, high concurrency online"
    ["wizard_param_dau"]="Daily Active Users (DAU)"
    ["wizard_param_ha_title"]="High Availability Level:"
    ["wizard_param_ha_single_az"]="1. Single AZ - Low cost, suitable for dev/test"
    ["wizard_param_ha_multi_az"]="2. Multi-AZ - Recommended, automatic failover"
    ["wizard_param_ha_multi_region"]="3. Multi-Region - Highest availability, cross-region DR"
    ["wizard_param_compliance_title"]="Compliance Requirements:"
    ["wizard_param_compliance_none"]="1. None"
    ["wizard_param_compliance_pci"]="2. PCI DSS (Payment Card Industry Data Security Standard)"
    ["wizard_param_compliance_hipaa"]="3. HIPAA (Health Insurance Portability and Accountability Act)"
    ["wizard_param_compliance_gdpr"]="4. GDPR (General Data Protection Regulation)"
    ["wizard_param_budget"]="Monthly Budget Cap (USD, optional, press Enter to skip)"
    ["wizard_param_deploy_region"]="Deployment Region"
    
    # Execution Messages
    ["wizard_exec_mode_a"]=">>> Starting Architecture Analysis Mode (Mode A)"
    ["wizard_exec_mode_b"]=">>> Starting WAF Assessment Mode (Mode B)"
    ["wizard_exec_mode_c"]=">>> Starting Architecture Recommendation Mode (Mode C)"
    ["wizard_exec_running_analysis"]="Running architecture analysis..."
    ["wizard_exec_running_assessment"]="Running WAF assessment..."
    ["wizard_exec_generating"]="Generating architecture solution..."
    ["wizard_exec_timeout"]="Operation timed out (30 minutes). Please check network connection or retry later."
    ["wizard_exec_failed"]="Operation failed (exit code: %d)"
    ["wizard_exec_success_analysis"]="Architecture analysis completed"
    ["wizard_exec_success_assessment"]="WAF assessment completed"
    ["wizard_exec_success_recommendation"]="Architecture recommendation generated"
    ["wizard_goodbye"]="Thank you for using, goodbye!"
    
    # Validation
    "validation_invalid_choice"]="✗ Invalid choice, please enter %s"
    "validation_must_integer"]="✗ %s must be a positive integer"
    
    # recommend.sh Steps
    "recommend_step1"]="Checking dependencies..."
    "recommend_step2"]="Initializing recommendation report..."
    "recommend_step3"]="Validating scenario and loading template..."
    "recommend_step4"]="Customizing architecture template..."
    "recommend_step4.5"]="Validating component availability in %s..."
    "recommend_step5"]="Generating architecture blueprint..."
    "recommend_step6"]="Saving recommendation blueprint..."
    ["recommend_complete"]="Architecture recommendation generated successfully"
)

# Re-enable nounset
set -u

# ---------------------------------------------------------------------------
# Translation Function
# ---------------------------------------------------------------------------
t() {
    local key="$1"
    shift
    local args=("$@")
    
    local dict_name="I18N_${CURRENT_LANG}"
    
    # Use indirect reference safely
    local translation=""
    if [[ "${CURRENT_LANG}" == "zh_CN" ]]; then
        translation="${I18N_ZH_CN[$key]:-$key}"
    elif [[ "${CURRENT_LANG}" == "en_US" ]]; then
        translation="${I18N_EN_US[$key]:-$key}"
    else
        translation="$key"
    fi
    
    # Apply printf formatting if args provided
    if [[ ${#args[@]} -gt 0 ]]; then
        printf "$translation" "${args[@]}"
    else
        echo "$translation"
    fi
}

# ---------------------------------------------------------------------------
# Language Switch Function
# ---------------------------------------------------------------------------
switch_language() {
    local lang="$1"
    if [[ "$lang" == "zh_CN" || "$lang" == "en_US" ]]; then
        CURRENT_LANG="$lang"
        export CURRENT_LANG
        export ARCH_ADVISOR_LANG="$lang"
        log_info "$(t "common.info") Language switched to: $lang"
    else
        log_error "$(t "common.error") Unsupported language: $lang (use zh_CN or en_US)"
        return 1
    fi
}

# Export functions
export -f t
export -f switch_language
export -f detect_language
