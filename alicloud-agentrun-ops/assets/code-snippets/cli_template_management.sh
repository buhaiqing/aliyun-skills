#!/bin/bash
# AgentRun CLI - Template 管理脚本
# 适用于: 终端交互、CI/CD 流水线

set -e

# ==================== 配置 ====================
# 可通过环境变量覆盖默认值
export AGENTRUN_ACCESS_KEY_ID="${AGENTRUN_ACCESS_KEY_ID:-$ALIBABA_CLOUD_ACCESS_KEY_ID}"
export AGENTRUN_ACCESS_KEY_SECRET="${AGENTRUN_ACCESS_KEY_ID:-$ALIBABA_CLOUD_ACCESS_KEY_SECRET}"
export AGENTRUN_ACCOUNT_ID="${AGENTRUN_ACCOUNT_ID:-$ALIBABA_CLOUD_ACCOUNT_ID}"
export AGENTRUN_REGION="${AGENTRUN_REGION:-${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}}"

# 可选：指定 CLI profile
PROFILE_ARG=""
if [[ -n "$AGENTRUN_PROFILE" ]]; then
    PROFILE_ARG="--profile $AGENTRUN_PROFILE"
fi

# ==================== 函数定义 ====================

# 创建 Template
create_template() {
    local name="${1:-my-template}"
    local cpu="${2:-2}"
    local memory="${3:-4096}"
    local template_type="${4:-CodeInterpreter}"
    
    echo "[INFO] 创建 Template: $name"
    ar $PROFILE_ARG template create \
        --name "$name" \
        --cpu "$cpu" \
        --memory "$memory" \
        --template-type "$template_type" \
        --output json
}

# 查询 Template
get_template() {
    local name="$1"
    if [[ -z "$name" ]]; then
        echo "[ERROR] 请提供 Template 名称"
        exit 1
    fi
    
    echo "[INFO] 查询 Template: $name"
    ar $PROFILE_ARG template get "$name" --output json
}

# 列出所有 Templates
list_templates() {
    local status="${1:-READY}"
    
    echo "[INFO] 列出 Templates (status=$status)"
    ar $PROFILE_ARG template list \
        --status "$status" \
        --output table
}

# 更新 Template
update_template() {
    local name="$1"
    local cpu="${2:-}"
    local memory="${3:-}"
    
    if [[ -z "$name" ]]; then
        echo "[ERROR] 请提供 Template 名称"
        exit 1
    fi
    
    local update_args=""
    [[ -n "$cpu" ]] && update_args="$update_args --cpu $cpu"
    [[ -n "$memory" ]] && update_args="$update_args --memory $memory"
    
    echo "[INFO] 更新 Template: $name"
    ar $PROFILE_ARG template update "$name" $update_args --output json
}

# 删除 Template（带确认）
delete_template() {
    local name="$1"
    local force="${2:-false}"
    
    if [[ -z "$name" ]]; then
        echo "[ERROR] 请提供 Template 名称"
        exit 1
    fi
    
    # 检查是否有依赖的 Sandbox
    echo "[INFO] 检查依赖的 Sandboxes..."
    local dependent_count
    dependent_count=$(ar $PROFILE_ARG sandbox list --template "$name" --output json | jq '.items | length')
    
    if [[ "$dependent_count" -gt 0 ]]; then
        echo "[WARN] 发现 $dependent_count 个依赖的 Sandbox，请先删除它们"
        ar $PROFILE_ARG sandbox list --template "$name" --output table
        exit 1
    fi
    
    # 确认删除
    if [[ "$force" != "true" ]]; then
        read -rp "确认删除 Template '$name' 吗? [y/N]: " confirm
        [[ "$confirm" != "y" && "$confirm" != "Y" ]] && exit 0
    fi
    
    echo "[INFO] 删除 Template: $name"
    ar $PROFILE_ARG template delete "$name" --yes
}

# 导出 Template 为 YAML
export_template() {
    local name="$1"
    local output_file="${2:-${name}.yaml}"
    
    if [[ -z "$name" ]]; then
        echo "[ERROR] 请提供 Template 名称"
        exit 1
    fi
    
    echo "[INFO] 导出 Template '$name' 到 $output_file"
    ar $PROFILE_ARG template export "$name" --output yaml > "$output_file"
    echo "[INFO] 已导出到: $output_file"
}

# ==================== 命令路由 ====================

case "${1:-}" in
    create)
        shift
        create_template "$@"
        ;;
    get)
        shift
        get_template "$@"
        ;;
    list)
        shift
        list_templates "$@"
        ;;
    update)
        shift
        update_template "$@"
        ;;
    delete)
        shift
        delete_template "$@"
        ;;
    export)
        shift
        export_template "$@"
        ;;
    *)
        cat << 'EOF'
用法: $0 <command> [args...]

Commands:
  create <name> [cpu] [memory] [type]  创建 Template
  get <name>                           查询 Template
  list [status]                        列出 Templates (默认: READY)
  update <name> [cpu] [memory]         更新 Template
  delete <name> [force]                删除 Template
  export <name> [output_file]          导出为 YAML

环境变量:
  AGENTRUN_ACCESS_KEY_ID      AccessKey ID
  AGENTRUN_ACCESS_KEY_SECRET  AccessKey Secret
  AGENTRUN_ACCOUNT_ID         阿里云账号 ID
  AGENTRUN_REGION             区域 (默认: cn-hangzhou)
  AGENTRUN_PROFILE            CLI profile 名称

示例:
  # 创建 Template
  $0 create my-template 2 4096 CodeInterpreter
  
  # 列出所有 Templates
  $0 list
  
  # 删除 Template (带确认)
  $0 delete my-template
  
  # 强制删除 Template
  $0 delete my-template true

EOF
        exit 1
        ;;
esac
