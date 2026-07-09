#!/bin/bash
# AgentRun CLI - Sandbox 管理脚本
# 适用于: 终端交互、CI/CD 流水线

set -e

# ==================== 配置 ====================
export AGENTRUN_ACCESS_KEY_ID="${AGENTRUN_ACCESS_KEY_ID:-$ALIBABA_CLOUD_ACCESS_KEY_ID}"
export AGENTRUN_ACCESS_KEY_SECRET="${AGENTRUN_ACCESS_KEY_ID:-$ALIBABA_CLOUD_ACCESS_KEY_SECRET}"
export AGENTRUN_ACCOUNT_ID="${AGENTRUN_ACCOUNT_ID:-$ALIBABA_CLOUD_ACCOUNT_ID}"
export AGENTRUN_REGION="${AGENTRUN_REGION:-${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}}"

PROFILE_ARG=""
[[ -n "$AGENTRUN_PROFILE" ]] && PROFILE_ARG="--profile $AGENTRUN_PROFILE"

# ==================== 函数定义 ====================

# 创建 Sandbox
create_sandbox() {
    local template_name="${1:-my-template}"
    local wait_ready="${2:-true}"
    
    echo "[INFO] 创建 Sandbox (template=$template_name)"
    
    local output
    output=$(ar $PROFILE_ARG sandbox create \
        --template "$template_name" \
        --output json)
    
    local sandbox_id
    sandbox_id=$(echo "$output" | jq -r '.sandboxId')
    
    echo "[INFO] Sandbox 创建中: $sandbox_id"
    
    # 等待就绪
    if [[ "$wait_ready" == "true" ]]; then
        echo "[INFO] 等待 Sandbox 就绪..."
        ar $PROFILE_ARG sandbox get "$sandbox_id" --wait --output json
    fi
    
    echo "$sandbox_id"
}

# 查询 Sandbox
get_sandbox() {
    local sandbox_id="$1"
    
    if [[ -z "$sandbox_id" ]]; then
        echo "[ERROR] 请提供 Sandbox ID"
        exit 1
    fi
    
    ar $PROFILE_ARG sandbox get "$sandbox_id" --output json
}

# 列出 Sandboxes
list_sandboxes() {
    local status="${1:-}"
    local template="${2:-}"
    
    local filter_args=""
    [[ -n "$status" ]] && filter_args="$filter_args --status $status"
    [[ -n "$template" ]] && filter_args="$filter_args --template $template"
    
    ar $PROFILE_ARG sandbox list $filter_args --output table
}

# 停止 Sandbox
stop_sandbox() {
    local sandbox_id="$1"
    local wait="${2:-true}"
    
    if [[ -z "$sandbox_id" ]]; then
        echo "[ERROR] 请提供 Sandbox ID"
        exit 1
    fi
    
    echo "[INFO] 停止 Sandbox: $sandbox_id"
    
    local wait_arg=""
    [[ "$wait" == "true" ]] && wait_arg="--wait"
    
    ar $PROFILE_ARG sandbox stop "$sandbox_id" $wait_arg
}

# 删除 Sandbox（带确认）
delete_sandbox() {
    local sandbox_id="$1"
    local force="${2:-false}"
    
    if [[ -z "$sandbox_id" ]]; then
        echo "[ERROR] 请提供 Sandbox ID"
        exit 1
    fi
    
    # 获取 Sandbox 信息
    local status
    status=$(ar $PROFILE_ARG sandbox get "$sandbox_id" --output json 2>/dev/null | jq -r '.status' || echo "UNKNOWN")
    
    echo "[WARN] 即将删除 Sandbox: $sandbox_id (当前状态: $status)"
    echo "[WARN] 警告: 所有文件和状态将永久丢失！"
    
    if [[ "$force" != "true" ]]; then
        read -rp "确认删除? [y/N]: " confirm
        [[ "$confirm" != "y" && "$confirm" != "Y" ]] && exit 0
    fi
    
    # 如果正在运行，先停止
    if [[ "$status" == "READY" ]]; then
        echo "[INFO] 先停止 Sandbox..."
        ar $PROFILE_ARG sandbox stop "$sandbox_id" --wait
    fi
    
    echo "[INFO] 删除 Sandbox: $sandbox_id"
    ar $PROFILE_ARG sandbox delete "$sandbox_id" --yes
}

# 暂停 Sandbox (Deep Hibernation)
pause_sandbox() {
    local sandbox_id="$1"
    
    if [[ -z "$sandbox_id" ]]; then
        echo "[ERROR] 请提供 Sandbox ID"
        exit 1
    fi
    
    echo "[INFO] 暂停 Sandbox: $sandbox_id"
    ar $PROFILE_ARG sandbox pause "$sandbox_id"
    echo "[INFO] Sandbox 已暂停 (状态变为 HIBERNATED)"
}

# 恢复 Sandbox
resume_sandbox() {
    local sandbox_id="$1"
    local filesystem_only="${2:-false}"
    
    if [[ -z "$sandbox_id" ]]; then
        echo "[ERROR] 请提供 Sandbox ID"
        exit 1
    fi
    
    echo "[INFO] 恢复 Sandbox: $sandbox_id"
    
    local args=""
    [[ "$filesystem_only" == "true" ]] && args="--filesystem-only"
    
    ar $PROFILE_ARG sandbox resume "$sandbox_id" $args --wait
    echo "[INFO] Sandbox 已恢复"
}

# 获取 Sandbox 日志
get_logs() {
    local sandbox_id="$1"
    
    if [[ -z "$sandbox_id" ]]; then
        echo "[ERROR] 请提供 Sandbox ID"
        exit 1
    fi
    
    ar $PROFILE_ARG sandbox logs "$sandbox_id"
}

# ==================== 命令路由 ====================

case "${1:-}" in
    create)
        shift
        create_sandbox "$@"
        ;;
    get)
        shift
        get_sandbox "$@"
        ;;
    list)
        shift
        list_sandboxes "$@"
        ;;
    stop)
        shift
        stop_sandbox "$@"
        ;;
    delete)
        shift
        delete_sandbox "$@"
        ;;
    pause)
        shift
        pause_sandbox "$@"
        ;;
    resume)
        shift
        resume_sandbox "$@"
        ;;
    logs)
        shift
        get_logs "$@"
        ;;
    *)
        cat << 'EOF'
用法: $0 <command> [args...]

Commands:
  create <template> [wait]        创建 Sandbox
  get <sandbox_id>                查询 Sandbox
  list [status] [template]        列出 Sandboxes
  stop <sandbox_id> [wait]        停止 Sandbox
  delete <sandbox_id> [force]     删除 Sandbox
  pause <sandbox_id>              暂停 Sandbox (Deep Hibernation)
  resume <sandbox_id> [fs_only]   恢复 Sandbox
  logs <sandbox_id>               获取 Sandbox 日志

环境变量:
  AGENTRUN_ACCESS_KEY_*           阿里云凭证
  AGENTRUN_ACCOUNT_ID             阿里云账号 ID
  AGENTRUN_REGION                 区域 (默认: cn-hangzhou)
  AGENTRUN_PROFILE                CLI profile 名称

示例:
  # 创建并等待就绪
  $0 create my-template true
  
  # 列出所有运行中的 Sandbox
  $0 list READY
  
  # 暂停 Sandbox (节省成本)
  $0 pause 01ABC...
  
  # 恢复 Sandbox
  $0 resume 01ABC...
  
  # 强制删除
  $0 delete 01ABC... true

EOF
        exit 1
        ;;
esac
