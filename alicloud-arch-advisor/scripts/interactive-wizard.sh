#!/bin/bash
# alicloud-arch-advisor - Interactive Wizard
# 交互式向导：引导用户完成架构分析、WAF 评估、方案推荐
# Usage: ./interactive-wizard.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSESS_SCRIPT="${SCRIPT_DIR}/assess.sh"
RECOMMEND_SCRIPT="${SCRIPT_DIR}/recommend.sh"
COMMON_SCRIPT="${SCRIPT_DIR}/common.sh"

# Source common functions (including progress bar)
source "$COMMON_SCRIPT"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
print_header() {
    echo -e "${CYAN}"
    t "wizard.header"
    echo -e "${NC}\n"
}

print_menu() {
    echo -e "${BLUE}$(t 'wizard_menu.title')${NC}\n"
    echo -e "  ${GREEN}1${NC}. $(t 'wizard_menu.mode_a')"
    echo ""
    echo -e "  ${GREEN}2${NC}. $(t 'wizard_menu.mode_b')"
    echo ""
    echo -e "  ${GREEN}3${NC}. $(t 'wizard_menu.mode_c')"
    echo ""
    echo -e "  ${YELLOW}0${NC}. $(t 'wizard_menu.exit')\n"
}

read_input() {
    local prompt="$1"
    local default="${2:-}"
    local input
    
    if [[ -n "$default" ]]; then
        read -p "${prompt} [默认: ${default}]: " input
        echo "${input:-$default}"
    else
        read -p "${prompt}: " input
        echo "$input"
    fi
}

validate_choice() {
    local choice="$1"
    if [[ ! "$choice" =~ ^[0-3]$ ]]; then
        echo -e "${RED}$(t 'validation_invalid_choice' "0-3")${NC}"
        return 1
    fi
    return 0
}

validate_number() {
    local value="$1"
    local field_name="$2"
    if [[ ! "$value" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}$(t 'validation_must_integer' "$field_name")${NC}"
        return 1
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Mode A/B parameter collection
# ---------------------------------------------------------------------------
collect_assessment_params() {
    local mode_name="$1"
    
    echo -e "\n${CYAN}=== ${mode_name} 参数配置 ===${NC}\n"
    
    # Region
    local region
    region=$(read_input "阿里云地域" "${ALICLOUD_REGION:-cn-hangzhou}")
    
    # Resource Group (optional)
    local resource_group
    resource_group=$(read_input "资源组 ID (可选，直接回车跳过)" "")
    
    # Tags (optional)
    local tags
    tags=$(read_input "标签过滤 (格式: key=value,key2=value2，可选)" "")
    
    # VPC ID (optional)
    local vpc_id
    vpc_id=$(read_input "VPC ID (可选，直接回车跳过)" "")
    
    # Pillars (for Mode B only)
    local pillars="all"
    if [[ "$mode_name" == *"WAF"* ]]; then
        echo -e "\n${BLUE}请选择评估维度:${NC}"
        echo "  1. 全部维度 (security,reliability,performance,cost,efficiency)"
        echo "  2. 仅安全 (security)"
        echo "  3. 仅可靠性 (reliability)"
        echo "  4. 仅性能 (performance)"
        echo "  5. 仅成本 (cost)"
        echo "  6. 仅效率 (efficiency)"
        echo "  7. 自定义 (输入逗号分隔的维度)"
        
        local pillar_choice
        pillar_choice=$(read_input "请选择 (1-7)" "1")
        
        case "$pillar_choice" in
            1) pillars="all" ;;
            2) pillars="security" ;;
            3) pillars="reliability" ;;
            4) pillars="performance" ;;
            5) pillars="cost" ;;
            6) pillars="efficiency" ;;
            7) pillars=$(read_input "请输入维度 (逗号分隔)" "security,reliability") ;;
            *) 
                echo -e "${YELLOW}⚠ 无效选择，使用全部维度${NC}"
                pillars="all"
                ;;
        esac
    fi
    
    # Output format
    local output_format
    echo -e "\n${BLUE}输出格式:${NC}"
    echo "  1. Markdown (推荐)"
    echo "  2. JSON"
    local format_choice
    format_choice=$(read_input "请选择 (1-2)" "1")
    output_format=$([[ "$format_choice" == "2" ]] && echo "json" || echo "markdown")
    
    # Confirm
    echo -e "\n${CYAN}=== 配置确认 ===${NC}"
    echo -e "地域: ${GREEN}${region}${NC}"
    [[ -n "$resource_group" ]] && echo -e "资源组: ${GREEN}${resource_group}${NC}"
    [[ -n "$tags" ]] && echo -e "标签: ${GREEN}${tags}${NC}"
    [[ -n "$vpc_id" ]] && echo -e "VPC ID: ${GREEN}${vpc_id}${NC}"
    [[ "$mode_name" == *"WAF"* ]] && echo -e "评估维度: ${GREEN}${pillars}${NC}"
    echo -e "输出格式: ${GREEN}${output_format}${NC}"
    
    local confirm
    confirm=$(read_input "确认执行？(y/n)" "y")
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo -e "${YELLOW}⚠ 已取消${NC}"
        return 1
    fi
    
    # Build command
    local cmd_args=("--region" "$region" "--output" "$output_format")
    [[ -n "$resource_group" ]] && cmd_args+=("--resource-group" "$resource_group")
    [[ -n "$tags" ]] && cmd_args+=("--tags" "$tags")
    [[ -n "$vpc_id" ]] && cmd_args+=("--vpc-id" "$vpc_id")
    [[ "$mode_name" == *"WAF"* ]] && cmd_args+=("--pillars" "$pillars")
    
    echo "${cmd_args[@]}"
}

# ---------------------------------------------------------------------------
# Mode C parameter collection
# ---------------------------------------------------------------------------
collect_recommendation_params() {
    echo -e "\n${CYAN}=== 架构方案推荐 - 需求收集 ===${NC}\n"
    
    # Scenario selection
    echo -e "${BLUE}请选择业务场景:${NC}"
    echo "  1. 电商平台 (ecommerce) - 高并发交易、商品搜索、订单处理"
    echo "  2. SaaS 应用 (saas) - 多租户隔离、按需计费"
    echo "  3. 数据平台 (data-platform) - 大数据分析、实时流计算"
    echo "  4. 微服务架构 (microservice) - 容器化、Service Mesh"
    echo "  5. Serverless 应用 (serverless) - 事件驱动、零运维"
    echo "  6. 游戏后端 (game) - 实时对战、高并发在线"
    echo ""
    
    local scenario_map=("ecommerce" "saas" "data-platform" "microservice" "serverless" "game")
    local scenario_choice
    scenario_choice=$(read_input "请选择 (1-6)" "1")
    
    if [[ ! "$scenario_choice" =~ ^[1-6]$ ]]; then
        echo -e "${RED}✗ 无效选择${NC}"
        return 1
    fi
    
    local scenario="${scenario_map[$((scenario_choice - 1))]}"
    echo -e "✓ 已选择: ${GREEN}${scenario}${NC}\n"
    
    # DAU
    local dau
    dau=$(read_input "日活跃用户数 (DAU)" "100000")
    if ! validate_number "$dau" "DAU"; then
        return 1
    fi
    
    # HA Level
    echo -e "\n${BLUE}高可用等级:${NC}"
    echo "  1. 单可用区 (single-az) - 成本低，适合开发测试"
    echo "  2. 多可用区 (multi-az) - 推荐，自动故障切换"
    echo "  3. 多地域 (multi-region) - 最高可用，跨区域容灾"
    echo ""
    
    local ha_map=("single-az" "multi-az" "multi-region")
    local ha_choice
    ha_choice=$(read_input "请选择 (1-3)" "2")
    
    if [[ ! "$ha_choice" =~ ^[1-3]$ ]]; then
        echo -e "${RED}✗ 无效选择${NC}"
        return 1
    fi
    
    local ha_level="${ha_map[$((ha_choice - 1))]}"
    
    # Compliance
    echo -e "\n${BLUE}合规要求:${NC}"
    echo "  1. 无 (none)"
    echo "  2. PCI DSS (支付卡行业数据安全标准)"
    echo "  3. HIPAA (医疗健康信息)"
    echo "  4. GDPR (欧盟通用数据保护条例)"
    echo ""
    
    local compliance_map=("none" "pci" "hipaa" "gdpr")
    local compliance_choice
    compliance_choice=$(read_input "请选择 (1-4)" "1")
    
    if [[ ! "$compliance_choice" =~ ^[1-4]$ ]]; then
        echo -e "${RED}✗ 无效选择${NC}"
        return 1
    fi
    
    local compliance="${compliance_map[$((compliance_choice - 1))]}"
    
    # Budget (optional)
    local budget
    budget=$(read_input "月预算上限 (USD，可选，直接回车跳过)" "")
    
    # Region
    local region
    region=$(read_input "部署地域" "${ALICLOUD_REGION:-cn-hangzhou}")
    
    # Confirm
    echo -e "\n${CYAN}=== 配置确认 ===${NC}"
    echo -e "业务场景: ${GREEN}${scenario}${NC}"
    echo -e "DAU: ${GREEN}${dau}${NC}"
    echo -e "HA 等级: ${GREEN}${ha_level}${NC}"
    echo -e "合规要求: ${GREEN}${compliance}${NC}"
    [[ -n "$budget" ]] && echo -e "月预算: ${GREEN}\$${budget}${NC}"
    echo -e "部署地域: ${GREEN}${region}${NC}"
    
    local confirm
    confirm=$(read_input "确认执行？(y/n)" "y")
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo -e "${YELLOW}⚠ 已取消${NC}"
        return 1
    fi
    
    # Build command
    local cmd_args=("--scenario" "$scenario" "--dau" "$dau" "--ha" "$ha_level" "--compliance" "$compliance" "--region" "$region")
    [[ -n "$budget" ]] && cmd_args+=("--budget" "$budget")
    
    echo "${cmd_args[@]}"
}

# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------
main() {
    print_header
    
    while true; do
        print_menu
        
        local choice
        choice=$(read_input "请输入选项 (0-3)" "")
        
        if ! validate_choice "$choice"; then
            continue
        fi
        
        case "$choice" in
            0)
                echo -e "\n${GREEN}$(t 'wizard_goodbye')${NC}\n"
                exit 0
                ;;
            1)
                # Mode A - Architecture Analysis
                echo -e "\n${GREEN}$(t 'wizard_exec.mode_a')${NC}"
                local params
                params=$(collect_assessment_params "架构分析") || continue
                
                echo -e "\n${BLUE}$(t 'wizard_exec.running_analysis')${NC}\n"
                if timeout 1800 bash "$ASSESS_SCRIPT" --reverse-eng true "${params}"; then
                    log_success "$(t 'wizard_exec.success.analysis')"
                else
                    local exit_code=$?
                    if [[ $exit_code -eq 124 ]]; then
                        log_error "$(t 'wizard_exec.timeout')"
                    else
                        log_error "$(t 'wizard_exec.failed' "$exit_code")"
                    fi
                fi
                ;;
            2)
                # Mode B - WAF Assessment
                echo -e "\n${GREEN}$(t 'wizard_exec.mode_b')${NC}"
                local params
                params=$(collect_assessment_params "WAF 成熟度评估") || continue
                
                echo -e "\n${BLUE}$(t 'wizard_exec.running_assessment')${NC}\n"
                if timeout 1800 bash "$ASSESS_SCRIPT" --reverse-eng false "${params}"; then
                    log_success "$(t 'wizard_exec.success.assessment')"
                else
                    local exit_code=$?
                    if [[ $exit_code -eq 124 ]]; then
                        log_error "$(t 'wizard_exec.timeout')"
                    else
                        log_error "$(t 'wizard_exec.failed' "$exit_code")"
                    fi
                fi
                ;;
            3)
                # Mode C - Recommendation
                echo -e "\n${GREEN}$(t 'wizard_exec.mode_c')${NC}"
                local params
                params=$(collect_recommendation_params) || continue
                
                echo -e "\n${BLUE}$(t 'wizard_exec.generating')${NC}\n"
                if timeout 1800 bash "$RECOMMEND_SCRIPT" "${params}"; then
                    log_success "$(t 'wizard_exec.success.recommendation')"
                else
                    local exit_code=$?
                    if [[ $exit_code -eq 124 ]]; then
                        log_error "$(t 'wizard_exec.timeout')"
                    else
                        log_error "$(t 'wizard_exec.failed' "$exit_code")"
                    fi
                fi
                ;;
        esac
        
        echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    done
}

# Run
main
