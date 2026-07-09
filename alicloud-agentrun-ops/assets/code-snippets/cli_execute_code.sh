#!/bin/bash
# AgentRun CLI - 代码执行和命令执行脚本
# 适用于: 终端交互、CI/CD 流水线、自动化测试

set -e

# ==================== 配置 ====================
export AGENTRUN_ACCESS_KEY_ID="${AGENTRUN_ACCESS_KEY_ID:-$ALIBABA_CLOUD_ACCESS_KEY_ID}"
export AGENTRUN_ACCESS_KEY_SECRET="${AGENTRUN_ACCESS_KEY_ID:-$ALIBABA_CLOUD_ACCESS_KEY_SECRET}"
export AGENTRUN_ACCOUNT_ID="${AGENTRUN_ACCOUNT_ID:-$ALIBABA_CLOUD_ACCOUNT_ID}"
export AGENTRUN_REGION="${AGENTRUN_REGION:-${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}}"

PROFILE_ARG=""
[[ -n "$AGENTRUN_PROFILE" ]] && PROFILE_ARG="--profile $AGENTRUN_PROFILE"

# 默认超时时间
DEFAULT_TIMEOUT=30

# ==================== 函数定义 ====================

# 执行代码
execute_code() {
    local sandbox_id="$1"
    local code="$2"
    local language="${3:-python}"
    local timeout="${4:-$DEFAULT_TIMEOUT}"
    
    if [[ -z "$sandbox_id" || -z "$code" ]]; then
        echo "[ERROR] 请提供 Sandbox ID 和代码"
        exit 1
    fi
    
    echo "[INFO] 在 Sandbox $sandbox_id 中执行 $language 代码 (timeout=${timeout}s)"
    
    # 使用 CLI 执行代码
    ar $PROFILE_ARG sandbox exec "$sandbox_id" \
        --language "$language" \
        --code "$code" \
        --timeout "$timeout" \
        --output json
}

# 从文件执行代码
execute_code_from_file() {
    local sandbox_id="$1"
    local file_path="$2"
    local language="${3:-}"
    local timeout="${4:-$DEFAULT_TIMEOUT}"
    
    if [[ -z "$sandbox_id" || -z "$file_path" ]]; then
        echo "[ERROR] 请提供 Sandbox ID 和文件路径"
        exit 1
    fi
    
    if [[ ! -f "$file_path" ]]; then
        echo "[ERROR] 文件不存在: $file_path"
        exit 1
    fi
    
    # 自动检测语言
    if [[ -z "$language" ]]; then
        case "${file_path##*.}" in
            py) language="python" ;;
            js) language="nodejs" ;;
            go) language="go" ;;
            sh) language="bash" ;;
            *) language="python" ;;
        esac
    fi
    
    echo "[INFO] 从文件执行 $language 代码: $file_path"
    
    ar $PROFILE_ARG sandbox exec "$sandbox_id" \
        --file "$file_path" \
        --language "$language" \
        --timeout "$timeout" \
        --output json
}

# 执行 shell 命令
run_command() {
    local sandbox_id="$1"
    local command="$2"
    local cwd="${3:-/home/user}"
    local timeout="${4:-$DEFAULT_TIMEOUT}"
    
    if [[ -z "$sandbox_id" || -z "$command" ]]; then
        echo "[ERROR] 请提供 Sandbox ID 和命令"
        exit 1
    fi
    
    echo "[INFO] 在 Sandbox $sandbox_id 中执行命令 (cwd=$cwd)"
    
    ar $PROFILE_ARG sandbox run "$sandbox_id" \
        --command "$command" \
        --cwd "$cwd" \
        --timeout "$timeout" \
        --output json
}

# 交互式 TTY 终端
start_tty() {
    local sandbox_id="$1"
    
    if [[ -z "$sandbox_id" ]]; then
        echo "[ERROR] 请提供 Sandbox ID"
        exit 1
    fi
    
    echo "[INFO] 连接到 Sandbox $sandbox_id 的交互式终端"
    echo "[INFO] 提示: 按 Ctrl+D 或输入 'exit' 退出"
    
    ar $PROFILE_ARG sandbox tty "$sandbox_id"
}

# 批量执行代码（从 JSON 文件）
batch_execute() {
    local sandbox_id="$1"
    local batch_file="$2"
    
    if [[ -z "$sandbox_id" || -z "$batch_file" ]]; then
        echo "[ERROR] 请提供 Sandbox ID 和批量执行文件"
        exit 1
    fi
    
    if [[ ! -f "$batch_file" ]]; then
        echo "[ERROR] 文件不存在: $batch_file"
        exit 1
    fi
    
    echo "[INFO] 批量执行代码: $batch_file"
    
    # 读取 JSON 文件并逐条执行
    local count
    count=$(jq '.tasks | length' "$batch_file")
    
    for ((i=0; i<count; i++)); do
        local code language timeout
        code=$(jq -r ".tasks[$i].code" "$batch_file")
        language=$(jq -r ".tasks[$i].language // \"python\"" "$batch_file")
        timeout=$(jq -r ".tasks[$i].timeout // $DEFAULT_TIMEOUT" "$batch_file")
        
        echo "[INFO] 执行任务 $((i+1))/$count: $language"
        execute_code "$sandbox_id" "$code" "$language" "$timeout"
        echo "---"
    done
}

# 执行并验证结果
execute_and_verify() {
    local sandbox_id="$1"
    local code="$2"
    local expected_output="$3"
    local language="${4:-python}"
    
    echo "[INFO] 执行并验证..."
    
    local result
    result=$(execute_code "$sandbox_id" "$code" "$language")
    
    local stdout
    stdout=$(echo "$result" | jq -r '.stdout // empty')
    
    if [[ "$stdout" == *"$expected_output"* ]]; then
        echo "[PASS] 验证通过"
        echo "$result"
        return 0
    else
        echo "[FAIL] 验证失败"
        echo "预期包含: $expected_output"
        echo "实际输出: $stdout"
        echo "$result"
        return 1
    fi
}

# ==================== 命令路由 ====================

case "${1:-}" in
    code)
        shift
        execute_code "$@"
        ;;
    file)
        shift
        execute_code_from_file "$@"
        ;;
    run)
        shift
        run_command "$@"
        ;;
    tty)
        shift
        start_tty "$@"
        ;;
    batch)
        shift
        batch_execute "$@"
        ;;
    verify)
        shift
        execute_and_verify "$@"
        ;;
    *)
        cat << 'EOF'
用法: $0 <command> [args...]

Commands:
  code <sandbox_id> <code> [lang] [timeout]     执行代码字符串
  file <sandbox_id> <file> [lang] [timeout]     从文件执行代码
  run <sandbox_id> <command> [cwd] [timeout]    执行 shell 命令
  tty <sandbox_id>                              交互式终端
  batch <sandbox_id> <batch.json>               批量执行 (JSON 格式)
  verify <sandbox_id> <code> <expected> [lang]  执行并验证输出

语言选项: python, nodejs, go, bash

示例:
  # 执行 Python 代码
  $0 code 01ABC... "print('Hello World')" python
  
  # 执行 JavaScript
  $0 code 01ABC... "console.log(1+1)" nodejs
  
  # 执行 shell 命令
  $0 run 01ABC... "ls -la" /home/user
  
  # 交互式终端
  $0 tty 01ABC...
  
  # 批量执行
  $0 batch 01ABC... tasks.json

批量执行文件格式 (tasks.json):
{
  "tasks": [
    {"code": "print(1)", "language": "python", "timeout": 30},
    {"code": "console.log(2)", "language": "nodejs"}
  ]
}

EOF
        exit 1
        ;;
esac
