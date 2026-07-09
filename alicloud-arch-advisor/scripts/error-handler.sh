#!/bin/bash
# alicloud-arch-advisor - Error Handling Module
# Structured error classification and recovery guidance
# Usage: source error-handler.sh && handle_error <type> <message>

# ---------------------------------------------------------------------------
# Error Type Definitions
# ---------------------------------------------------------------------------

# Error categories
readonly ERR_CREDENTIAL="CREDENTIAL_ERROR"
readonly ERR_QUOTA="QUOTA_EXCEEDED"
readonly ERR_NETWORK="NETWORK_TIMEOUT"
readonly ERR_PERMISSION="PERMISSION_DENIED"
readonly ERR_API_RATE="API_RATE_LIMIT"
readonly ERR_INVALID_PARAM="INVALID_PARAMETER"
readonly ERR_RESOURCE_NOT_FOUND="RESOURCE_NOT_FOUND"
readonly ERR_DEPENDENCY="DEPENDENCY_MISSING"
readonly ERR_CONFIG="CONFIGURATION_ERROR"
readonly ERR_INTERNAL="INTERNAL_ERROR"
readonly ERR_VALIDATION="VALIDATION_FAILED"
readonly ERR_TIMEOUT="OPERATION_TIMEOUT"

# ---------------------------------------------------------------------------
# Error Message Library
# ---------------------------------------------------------------------------

# Get human-readable error description
# Usage: get_error_description <error_type>
get_error_description() {
    local err_type="$1"
    case "$err_type" in
        "$ERR_CREDENTIAL")      echo "凭证无效或缺失" ;;
        "$ERR_QUOTA")           echo "资源配额超限" ;;
        "$ERR_NETWORK")         echo "网络连接超时" ;;
        "$ERR_PERMISSION")      echo "权限不足" ;;
        "$ERR_API_RATE")        echo "API 调用频率超限" ;;
        "$ERR_INVALID_PARAM")   echo "无效的参数" ;;
        "$ERR_RESOURCE_NOT_FOUND") echo "资源未找到" ;;
        "$ERR_DEPENDENCY")      echo "依赖工具缺失" ;;
        "$ERR_CONFIG")          echo "配置错误" ;;
        "$ERR_INTERNAL")        echo "内部错误" ;;
        "$ERR_VALIDATION")      echo "输入验证失败" ;;
        "$ERR_TIMEOUT")         echo "操作超时" ;;
        *)                      echo "未知错误" ;;
    esac
}

# Get recovery action for error type
# Usage: get_error_recovery <error_type>
get_error_recovery() {
    local err_type="$1"
    case "$err_type" in
        "$ERR_CREDENTIAL")
            echo "1. 设置环境变量: export ALIBABA_CLOUD_ACCESS_KEY_ID=<your_key_id>
2. 设置: export ALIBABA_CLOUD_ACCESS_KEY_SECRET=<your_secret>
3. 或使用 aliyun configure 命令配置
4. 验证: aliyun sts GetCallerIdentity"
            ;;
        "$ERR_QUOTA")
            echo "1. 在阿里云控制台提交配额提升申请
2. 减少并发请求数 (--resource-group 限定范围)
3. 等待配额刷新 (通常 1 小时)
4. 联系阿里云技术支持"
            ;;
        "$ERR_NETWORK")
            echo "1. 检查网络连接: ping aliyun.com
2. 检查代理设置: echo \$HTTP_PROXY
3. 重试操作 (最多 3 次)
4. 使用 --region 切换地域"
            ;;
        "$ERR_PERMISSION")
            echo "1. 检查 RAM 角色权限: aliyun ram ListPolicies
2. 附加 AliyunAdvisorFullAccess 策略
3. 或使用有权限的 AccessKey
4. 跨账号模式: 检查 AssumeRole 配置"
            ;;
        "$ERR_API_RATE")
            echo "1. 降低请求频率: 添加 sleep 间隔
2. 启用客户端限流
3. 联系阿里云提高 QPS 限额
4. 分批处理资源"
            ;;
        "$ERR_INVALID_PARAM")
            echo "1. 检查参数格式: --region cn-hangzhou
2. 验证资源 ID 格式: i-xxx, sg-xxx
3. 查看帮助: ./assess.sh --help"
            ;;
        "$ERR_RESOURCE_NOT_FOUND")
            echo "1. 验证资源 ID 是否正确
2. 确认资源地域 (可能跨地域)
3. 检查资源是否已被删除
4. 确认 RAM 角色有 List 权限"
            ;;
        "$ERR_DEPENDENCY")
            echo "1. 安装 aliyun CLI: https://github.com/aliyun/aliyun-cli
2. 安装 jq: brew install jq (macOS) 或 apt install jq (Linux)
3. 使用 --mock 模式跳过依赖检查"
            ;;
        "$ERR_CONFIG")
            echo "1. 检查 .env 文件配置
2. 验证 ALIBABA_CLOUD_REGION 设置
3. 确认 ALIBABA_CLOUD_ACCOUNT_ID 正确
4. 查看示例: assets/example-config.yaml"
            ;;
        "$ERR_VALIDATION")
            echo "1. 检查输入参数是否符合要求
2. DAU 必须是正整数
3. 场景名称必须从预定义列表中选择
4. 地域代码必须有效 (cn-hangzhou, cn-shanghai 等)"
            ;;
        "$ERR_TIMEOUT")
            echo "1. 增加超时时间: 修改 GLOBAL_TIMEOUT
2. 缩小扫描范围: --resource-group 或 --tags
3. 排除故障地域
4. 联系网络管理员"
            ;;
        *)
            echo "1. 查看日志文件: \$OUTPUT_DIR/
2. 重试操作
3. 提交 Issue: 附上完整日志"
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Error Handler Function
# ---------------------------------------------------------------------------

# Handle error with structured output
# Usage: handle_error <error_type> <message> [exit_code]
#   error_type: One of ERR_* constants
#   message: Specific error message
#   exit_code: Optional exit code (default: 1)
handle_error() {
    local err_type="$1"
    local message="$2"
    local exit_code="${3:-1}"

    local desc recovery
    desc=$(get_error_description "$err_type")
    recovery=$(get_error_recovery "$err_type")

    # Structured error output
    echo "" >&2
    echo "╔══════════════════════════════════════════════════════════╗" >&2
    echo "║                    ❌ 错误 (Error)                       ║" >&2
    echo "╚══════════════════════════════════════════════════════════╝" >&2
    echo "" >&2
    echo -e "${RED}[${err_type}]${NC} ${desc}" >&2
    echo "" >&2
    echo -e "${YELLOW}详细信息:${NC} ${message}" >&2
    echo "" >&2
    echo -e "${BLUE}恢复建议:${NC}" >&2
    echo "$recovery" >&2
    echo "" >&2

    # Optionally exit
    if [[ "$exit_code" -gt 0 ]]; then
        exit "$exit_code"
    fi
}

# Handle warning (non-fatal)
# Usage: handle_warning <error_type> <message>
handle_warning() {
    local err_type="$1"
    local message="$2"

    local desc recovery
    desc=$(get_error_description "$err_type")
    recovery=$(get_error_recovery "$err_type")

    echo "" >&2
    echo -e "${YELLOW}⚠️  [${err_type}]${NC} ${desc}" >&2
    echo -e "   ${message}" >&2
    echo -e "   ${BLUE}建议:${NC} $(echo "$recovery" | head -1)" >&2
    echo "" >&2
}

# Classify error from output
# Usage: classify_error <error_output>
# Returns: Error type string
classify_error() {
    local output="$1"

    # Check for credential errors
    if echo "$output" | grep -qiE "InvalidAccessKeyId|InvalidSecurityToken|SignatureDoesNotMatch"; then
        echo "$ERR_CREDENTIAL"
    # Check for quota errors
    elif echo "$output" | grep -qiE "QuotaExceeded|ResourceQuota|LimitExceeded"; then
        echo "$ERR_QUOTA"
    # Check for network errors
    elif echo "$output" | grep -qiE "timeout|connection refused|network unreachable"; then
        echo "$ERR_NETWORK"
    # Check for permission errors
    elif echo "$output" | grep -qiE "ForbiddenAccess|NoPermission|AccessDenied|Unauthorized"; then
        echo "$ERR_PERMISSION"
    # Check for API rate limit
    elif echo "$output" | grep -qiE "Throttling|TooManyRequests|RequestRate"; then
        echo "$ERR_API_RATE"
    # Check for resource not found
    elif echo "$output" | grep -qiE "InvalidInstance.NotFound|ResourceNotFound|not found"; then
        echo "$ERR_RESOURCE_NOT_FOUND"
    # Check for invalid parameters
    elif echo "$output" | grep -qiE "InvalidParameter|InvalidFormat|Malformed"; then
        echo "$ERR_INVALID_PARAM"
    else
        echo "$ERR_INTERNAL"
    fi
}

# Retry operation with exponential backoff
# Usage: retry_operation <max_attempts> <initial_delay> <command...>
# Returns: Last command's exit code
retry_operation() {
    local max_attempts="$1"
    local initial_delay="$2"
    shift 2

    local attempt=1
    local delay=$initial_delay

    while [[ $attempt -le $max_attempts ]]; do
        if "$@"; then
            return 0
        fi

        local exit_code=$?
        log_warn "Attempt $attempt/$max_attempts failed (exit: $exit_code)"

        if [[ $attempt -lt $max_attempts ]]; then
            log_info "Retrying in ${delay}s..."
            sleep "$delay"
            delay=$((delay * 2))  # Exponential backoff
        fi

        attempt=$((attempt + 1))
    done

    log_error "All $max_attempts attempts failed"
    return $exit_code
}

# Safe command execution with error handling
# Usage: safe_exec <description> <command...>
# Returns: Exit code of command
safe_exec() {
    local description="$1"
    shift

    local output
    local exit_code

    log_info "Executing: $description"
    output=$("$@" 2>&1)
    exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
        local err_type
        err_type=$(classify_error "$output")
        handle_warning "$err_type" "$description failed: $output"
    else
        log_success "$description completed"
    fi

    return $exit_code
}

# Export functions
export -f get_error_description
export -f get_error_recovery
export -f handle_error
export -f handle_warning
export -f classify_error
export -f retry_operation
export -f safe_exec
