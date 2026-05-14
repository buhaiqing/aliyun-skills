# Enhanced Self-Healing Framework for CLI Installation

> **Purpose:** 定义增强的CLI安装异常处理和自愈能力框架，确保在各种异常场景下都能自动恢复或提供明确的降级路径。
> **Version:** 1.0.0
> **Last Updated:** 2026-05-14
> **Status:** MANDATORY — 所有生成的Skill必须遵循此自愈框架

---

## 1. 核心设计原则

### 1.1 自愈能力成熟度模型

| 等级 | 名称 | 特征 | 目标 |
|------|------|------|------|
| L1 | 基础重试 | 固定次数重试，无错误分类 | 当前状态 |
| L2 | 智能重试 | 错误分类，针对性重试策略 | 立即实现 |
| L3 | 多路径自愈 | 多种自愈路径，自动选择最优方案 | 短期目标 |
| L4 | 预防性自愈 | 预检异常，提前规避 | 中期目标 |
| L5 | 自学习自愈 | 历史数据分析，优化自愈策略 | 长期目标 |

### 1.2 自愈决策树原则

```
[异常发生]
    │
    ├── Step 1: 错误分类
    │   网络异常 / 权限异常 / 资源异常 / 配置异常 / 未知异常
    │
    ├── Step 2: 选择自愈路径
    │   根据错误类型选择对应的自愈策略
    │
    ├── Step 3: 执行自愈
    │   尝试自愈操作，记录结果
    │
    ├── Step 4: 验证自愈效果
    │   检查异常是否已解决
    │
    ├── Step 5: 自愈失败处理
    │   尝试下一级自愈路径或降级
    │
    └── Step 6: 用户指导
        提供明确的错误信息和修复建议
```

---

## 2. 错误分类体系

### 2.1 CLI安装错误分类

| 错误类别 | 错误代码 | 典型场景 | 自愈策略 |
|----------|---------|---------|---------|
| **网络异常** | `NET_TIMEOUT` | curl下载超时 | 切换镜像源，增加超时时间 |
| | `NET_DNS_FAIL` | DNS解析失败 | 使用IP直连或备用域名 |
| | `NET_CONNECTION_REFUSED` | 连接被拒绝 | 检查防火墙，切换网络 |
| | `NET_SSL_ERROR` | SSL证书错误 | 更新CA证书，使用--insecure |
| **权限异常** | `PERM_WRITE_FAIL` | 写入/usr/local/bin失败 | 使用用户目录，提示sudo |
| | `PERM_EXEC_FAIL` | 执行权限不足 | chmod +x，提示sudo |
| | `PERM_DIR_CREATE_FAIL` | 创建目录失败 | 使用/tmp目录，提示权限问题 |
| **资源异常** | `RES_DISK_FULL` | 磁盘空间不足 | 清理临时文件，提示用户 |
| | `RES_BINARY_CORRUPT` | 下载文件损坏 | 删除重新下载，校验完整性 |
| | `RES_VERSION_INCOMPATIBLE` | 版本不兼容 | 下载兼容版本 |
| **配置异常** | `CONF_PATH_NOT_FOUND` | PATH未包含安装路径 | 自动添加PATH，提示用户 |
| | `CONF_ENV_VAR_MISSING` | 环境变量缺失 | 设置临时环境变量 |
| **未知异常** | `UNKNOWN_ERROR` | 未分类错误 | 记录详细信息，提供诊断建议 |

### 2.2 Go Runtime JIT下载错误分类

| 错误类别 | 错误代码 | 典型场景 | 自愈策略 |
|----------|---------|---------|---------|
| **下载异常** | `GO_DOWNLOAD_FAIL` | Go runtime下载失败 | 切换镜像源，使用国内镜像 |
| | `GO_DOWNLOAD_INCOMPLETE` | 下载不完整 | 校验文件大小，重新下载 |
| | `GO_DOWNLOAD_TIMEOUT` | 下载超时 | 增加超时时间，使用更快的镜像 |
| **解压异常** | `GO_EXTRACT_FAIL` | tar解压失败 | 检查文件完整性，重新下载 |
| | `GO_EXTRACT_CORRUPT` | 解压后文件损坏 | 删除重新下载解压 |
| **版本异常** | `GO_VERSION_MISMATCH` | 版本不匹配 | 下载指定版本 |
| | `GO_VERSION_INCOMPATIBLE` | 版本不兼容 | 下载兼容版本(1.21+) |
| **环境异常** | `GO_PATH_SETUP_FAIL` | PATH设置失败 | 使用绝对路径调用 |
| | `GO_WORKSPACE_INIT_FAIL` | 工作空间初始化失败 | 清理重新初始化 |

### 2.3 依赖下载错误分类

| 错误类别 | 错误代码 | 典型场景 | 自愈策略 |
|----------|---------|---------|---------|
| **网络异常** | `DEP_NET_TIMEOUT` | go get超时 | 切换GOPROXY，增加超时 |
| | `DEP_NET_PROXY_FAIL` | 代理失败 | 切换镜像源 |
| **版本异常** | `DEP_VERSION_NOT_FOUND` | 版本不存在 | 使用最新稳定版本 |
| | `DEP_VERSION_INCOMPATIBLE` | 版本冲突 | 解决依赖冲突 |
| **权限异常** | `DEP_WRITE_FAIL` | 写入GOMODCACHE失败 | 使用/tmp目录 |
| **编译异常** | `DEP_BUILD_FAIL` | 编译失败 | 检查Go版本，清理缓存 |

---

## 3. 增强的自愈流程

### 3.1 CLI安装增强自愈流程

#### Phase 1: 预检阶段 (新增)

```bash
# 预检1: 检查网络连通性
echo "=== Pre-flight Check: Network Connectivity ==="
if ! curl -fsSL --connect-timeout 5 https://aliyuncli.alicdn.com/ > /dev/null 2>&1; then
    echo "⚠️  Network connectivity check failed"
    echo "Attempting alternative CDN endpoints..."
    
    # 尝试备用CDN
    ALT_CDN_ENDPOINTS=(
        "https://cli.aliyun.com/"
        "https://aliyun-cli.oss-cn-hangzhou.aliyuncs.com/"
    )
    
    for endpoint in "${ALT_CDN_ENDPOINTS[@]}"; do
        if curl -fsSL --connect-timeout 5 "$endpoint" > /dev/null 2>&1; then
            echo "✅ Alternative endpoint available: $endpoint"
            CDN_ENDPOINT="$endpoint"
            break
        fi
    done
    
    if [ -z "$CDN_ENDPOINT" ]; then
        echo "❌ All CDN endpoints unreachable. Network issue detected."
        echo "Self-healing suggestion: Check firewall/proxy settings or use offline installation"
        # 记录错误代码
        ERROR_CODE="NET_CONNECTION_REFUSED"
        # 进入降级路径
        proceed_to_fallback_path
    fi
fi

# 预检2: 检查磁盘空间
echo "=== Pre-flight Check: Disk Space ==="
REQUIRED_SPACE_MB=50
AVAILABLE_SPACE_KB=$(df -k /tmp | awk 'NR==2 {print $4}')
AVAILABLE_SPACE_MB=$((AVAILABLE_SPACE_KB / 1024))

if [ "$AVAILABLE_SPACE_MB" -lt "$REQUIRED_SPACE_MB" ]; then
    echo "⚠️  Insufficient disk space: ${AVAILABLE_SPACE_MB}MB available, ${REQUIRED_SPACE_MB}MB required"
    echo "Attempting self-healing: Cleaning temporary files..."
    
    # 自愈操作: 清理临时文件
    rm -rf /tmp/aliyun-cli-* /tmp/go-* /tmp/aliyun-sdk-* 2>/dev/null || true
    
    # 重新检查空间
    AVAILABLE_SPACE_KB=$(df -k /tmp | awk 'NR==2 {print $4}')
    AVAILABLE_SPACE_MB=$((AVAILABLE_SPACE_KB / 1024))
    
    if [ "$AVAILABLE_SPACE_MB" -lt "$REQUIRED_SPACE_MB" ]; then
        echo "❌ Self-healing failed: Still insufficient disk space"
        ERROR_CODE="RES_DISK_FULL"
        echo "User action required: Free up disk space or use alternative installation path"
        proceed_to_user_guidance
    fi
fi

# 预检3: 检查安装路径权限
echo "=== Pre-flight Check: Installation Path Permissions ==="
INSTALL_PATH="/usr/local/bin"
if [ ! -w "$INSTALL_PATH" ]; then
    echo "⚠️  No write permission to $INSTALL_PATH"
    echo "Self-healing: Using alternative installation path..."
    
    # 自愈操作: 使用用户目录
    USER_BIN="$HOME/.local/bin"
    mkdir -p "$USER_BIN"
    
    if [ -w "$USER_BIN" ]; then
        echo "✅ Alternative path available: $USER_BIN"
        INSTALL_PATH="$USER_BIN"
        
        # 添加到PATH
        if [[ ":$PATH:" != *":$USER_BIN:"* ]]; then
            export PATH="$USER_BIN:$PATH"
            echo "✅ Added $USER_BIN to PATH (temporary)"
            echo "⚠️  Permanent PATH update required: Add 'export PATH=\"$USER_BIN:\$PATH\"' to ~/.bashrc or ~/.zshrc"
        fi
    else
        echo "❌ Self-healing failed: No writable installation path"
        ERROR_CODE="PERM_WRITE_FAIL"
        echo "User action required: Run with sudo or specify writable installation path"
        proceed_to_user_guidance
    fi
fi

# 预检4: 检查系统兼容性
echo "=== Pre-flight Check: System Compatibility ==="
OS=$(uname -s)
ARCH=$(uname -m)

if [ "$OS" != "Darwin" ] && [ "$OS" != "Linux" ]; then
    echo "❌ Unsupported OS: $OS (supported: macOS, Linux)"
    ERROR_CODE="RES_VERSION_INCOMPATIBLE"
    proceed_to_fallback_path
fi

# 架构映射
if [ "$ARCH" = "x86_64" ]; then
    ARCH_SUFFIX="amd64"
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    ARCH_SUFFIX="arm64"
else
    echo "❌ Unsupported architecture: $ARCH"
    ERROR_CODE="RES_VERSION_INCOMPATIBLE"
    proceed_to_fallback_path
fi

echo "✅ System compatible: $OS $ARCH_SUFFIX"
```

#### Phase 2: 智能下载阶段 (增强)

```bash
# 智能下载: 多镜像源 + 完整性校验 + 失败自愈
download_aliyun_cli() {
    local attempt=1
    local max_attempts=5
    local mirrors=(
        "https://aliyuncli.alicdn.com/install.sh"
        "https://cli.aliyun.com/install.sh"
        "https://aliyun-cli.oss-cn-hangzhou.aliyuncs.com/install.sh"
    )
    
    while [ $attempt -le $max_attempts ]; do
        echo "=== Download Attempt $attempt/$max_attempts ==="
        
        for mirror in "${mirrors[@]}"; do
            echo "Trying mirror: $mirror"
            
            # 下载安装脚本
            if curl -fsSL --connect-timeout 10 --max-time 60 "$mirror" -o /tmp/install-aliyun.sh; then
                # 校验文件完整性
                if [ -f /tmp/install-aliyun.sh ] && [ -s /tmp/install-aliyun.sh ]; then
                    # 检查是否是有效的shell脚本
                    if head -1 /tmp/install-aliyun.sh | grep -q "^#!"; then
                        echo "✅ Download successful and file integrity verified"
                        return 0
                    else
                        echo "⚠️  Downloaded file is not a valid shell script"
                        rm -f /tmp/install-aliyun.sh
                        ERROR_CODE="RES_BINARY_CORRUPT"
                    fi
                else
                    echo "⚠️  Downloaded file is empty or missing"
                    ERROR_CODE="GO_DOWNLOAD_INCOMPLETE"
                fi
            else
                echo "⚠️  Download failed from $mirror"
                ERROR_CODE="NET_TIMEOUT"
            fi
        done
        
        # 自愈策略: 根据错误类型调整
        if [ "$ERROR_CODE" = "NET_TIMEOUT" ]; then
            echo "Self-healing: Increasing timeout and retrying..."
            sleep $((attempt * 2))
        elif [ "$ERROR_CODE" = "RES_BINARY_CORRUPT" ]; then
            echo "Self-healing: Clearing cache and retrying..."
            rm -rf /tmp/aliyun-cli-* /tmp/install-aliyun.sh
        fi
        
        attempt=$((attempt + 1))
    done
    
    echo "❌ All download attempts failed after $max_attempts retries"
    return 1
}

# 执行下载
if ! download_aliyun_cli; then
    echo "Proceeding to JIT Go SDK fallback path..."
    proceed_to_go_sdk_fallback
fi
```

#### Phase 3: 安装执行阶段 (增强)

```bash
# 执行安装脚本
echo "=== Executing Installation Script ==="

# 设置安装路径(如果预检阶段修改了)
if [ "$INSTALL_PATH" != "/usr/local/bin" ]; then
    export ALIYUN_INSTALL_PATH="$INSTALL_PATH"
fi

# 执行安装
if bash /tmp/install-aliyun.sh; then
    echo "✅ Installation script executed successfully"
else
    echo "⚠️  Installation script execution failed"
    
    # 自愈: 手动安装
    echo "Self-healing: Attempting manual installation..."
    
    # 手动下载binary
    BINARY_URL="https://aliyuncli.alicdn.com/aliyun-cli-${OS}-${ARCH_SUFFIX}-latest.tgz"
    
    if curl -fsSL "$BINARY_URL" -o /tmp/aliyun-cli.tgz; then
        # 解压
        if tar -xzf /tmp/aliyun-cli.tgz -C /tmp; then
            # 移动到安装路径
            if mv /tmp/aliyun "$INSTALL_PATH/aliyun"; then
                chmod +x "$INSTALL_PATH/aliyun"
                echo "✅ Manual installation successful"
            else
                echo "❌ Failed to move binary to $INSTALL_PATH"
                ERROR_CODE="PERM_WRITE_FAIL"
                proceed_to_user_guidance
            fi
        else
            echo "❌ Failed to extract binary"
            ERROR_CODE="GO_EXTRACT_FAIL"
            proceed_to_user_guidance
        fi
    else
        echo "❌ Failed to download binary"
        ERROR_CODE="NET_TIMEOUT"
        proceed_to_go_sdk_fallback
    fi
fi
```

#### Phase 4: 安装验证阶段 (增强)

```bash
# 验证安装
echo "=== Verifying Installation ==="

# 检查binary是否存在
if [ ! -f "$INSTALL_PATH/aliyun" ]; then
    echo "❌ Binary not found at $INSTALL_PATH/aliyun"
    ERROR_CODE="RES_BINARY_CORRUPT"
    proceed_to_user_guidance
fi

# 检查执行权限
if [ ! -x "$INSTALL_PATH/aliyun" ]; then
    echo "⚠️  Binary lacks execute permission"
    echo "Self-healing: Adding execute permission..."
    chmod +x "$INSTALL_PATH/aliyun" || {
        echo "❌ Failed to add execute permission"
        ERROR_CODE="PERM_EXEC_FAIL"
        proceed_to_user_guidance
    }
fi

# 检查PATH
if ! command -v aliyun &> /dev/null; then
    echo "⚠️  aliyun not in PATH"
    echo "Self-healing: Adding to PATH..."
    
    export PATH="$INSTALL_PATH:$PATH"
    
    if command -v aliyun &> /dev/null; then
        echo "✅ Added to PATH (temporary)"
        echo "⚠️  Permanent PATH update required"
    else
        echo "❌ Failed to add to PATH"
        ERROR_CODE="CONF_PATH_NOT_FOUND"
        proceed_to_user_guidance
    fi
fi

# 功能验证
echo "=== Functional Verification ==="
if aliyun version; then
    echo "✅ aliyun CLI installed and functional"
    
    # 记录安装信息
    echo "Installation Summary:"
    echo "  - Path: $INSTALL_PATH/aliyun"
    echo "  - Version: $(aliyun version)"
    echo "  - OS: $OS"
    echo "  - Architecture: $ARCH_SUFFIX"
    
    return 0
else
    echo "❌ aliyun version check failed"
    ERROR_CODE="RES_BINARY_CORRUPT"
    
    # 自愈: 重新安装
    echo "Self-healing: Reinstalling..."
    rm -f "$INSTALL_PATH/aliyun"
    proceed_to_cli_install_retry
fi
```

### 3.2 Go Runtime JIT下载增强自愈流程

```bash
# Go Runtime JIT下载增强流程
bootstrap_go_runtime_enhanced() {
    echo "=== Go Runtime Bootstrap (Enhanced Self-Healing) ==="
    
    # 预检: 检查是否已有Go runtime
    if command -v go &> /dev/null; then
        GO_VERSION=$(go version | awk '{print $3}')
        GO_MAJOR=$(echo "$GO_VERSION" | sed 's/go//' | cut -d. -f1)
        GO_MINOR=$(echo "$GO_VERSION" | sed 's/go//' | cut -d. -f2)
        
        if [ "$GO_MAJOR" -ge 1 ] && [ "$GO_MINOR" -ge 21 ]; then
            echo "✅ Compatible Go runtime already installed: $GO_VERSION"
            return 0
        else
            echo "⚠️  Installed Go version $GO_VERSION is too old (minimum: go1.21)"
            echo "Self-healing: JIT downloading newer version..."
        fi
    fi
    
    # 检测系统
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    
    # 架构映射
    if [ "$ARCH" = "x86_64" ]; then ARCH="amd64"; fi
    if [ "$ARCH" = "aarch64" ]; then ARCH="arm64"; fi
    
    # Go版本选择策略
    GO_VERSIONS=(
        "go1.24.0"  # 最新稳定版
        "go1.23.0"  # 备用版本
        "go1.22.0"  # 备用版本
        "go1.21.0"  # 最小兼容版本
    )
    
    # 镜像源列表
    GO_MIRRORS=(
        "https://go.dev/dl"
        "https://dl.google.com/go"
        "https://mirrors.aliyun.com/golang"  # 国内镜像
        "https://golang.google.cn/dl"        # 国内镜像
    )
    
    # 下载尝试
    for go_version in "${GO_VERSIONS[@]}"; do
        echo "Attempting to download $go_version..."
        
        for mirror in "${GO_MIRRORS[@]}"; do
            GO_URL="${mirror}/${go_version}.${OS}-${ARCH}.tar.gz"
            echo "Trying mirror: $GO_URL"
            
            # 下载
            if curl -fsSL --connect-timeout 15 --max-time 120 "$GO_URL" -o /tmp/go-runtime.tar.gz; then
                # 校验文件大小(Go runtime约150MB)
                FILE_SIZE=$(stat -f%z /tmp/go-runtime.tar.gz 2>/dev/null || stat -c%s /tmp/go-runtime.tar.gz 2>/dev/null)
                EXPECTED_SIZE_MIN=100000000  # 100MB
                
                if [ "$FILE_SIZE" -gt "$EXPECTED_SIZE_MIN" ]; then
                    echo "✅ Download successful, file size: $FILE_SIZE bytes"
                    
                    # 解压
                    mkdir -p /tmp/go-runtime
                    if tar -xzf /tmp/go-runtime.tar.gz -C /tmp/go-runtime; then
                        # 验证解压结果
                        if [ -f "/tmp/go-runtime/go/bin/go" ]; then
                            # 设置环境变量
                            export PATH="/tmp/go-runtime/go/bin:$PATH"
                            export GOPATH="/tmp/go-workspace"
                            export GOCACHE="/tmp/go-cache"
                            export GOMODCACHE="/tmp/go-modcache"
                            export GOPROXY="https://goproxy.cn,direct"
                            
                            # 验证Go版本
                            ACTUAL_VERSION=$(go version | awk '{print $3}')
                            echo "✅ Go runtime installed: $ACTUAL_VERSION"
                            
                            # 清理下载文件
                            rm -f /tmp/go-runtime.tar.gz
                            
                            return 0
                        else
                            echo "⚠️  Extracted binary not found"
                            rm -rf /tmp/go-runtime /tmp/go-runtime.tar.gz
                        fi
                    else
                        echo "⚠️  Extraction failed"
                        rm -f /tmp/go-runtime.tar.gz
                    fi
                else
                    echo "⚠️  Downloaded file too small ($FILE_SIZE bytes), likely incomplete"
                    rm -f /tmp/go-runtime.tar.gz
                fi
            else
                echo "⚠️  Download failed from $mirror"
            fi
        done
        
        echo "Failed to download $go_version from all mirrors"
    done
    
    echo "❌ Go runtime download failed after trying all versions and mirrors"
    ERROR_CODE="GO_DOWNLOAD_FAIL"
    return 1
}

# Go工作空间初始化增强
init_go_workspace_enhanced() {
    echo "=== Go Workspace Initialization (Enhanced) ==="
    
    WORKSPACE_DIR="/tmp/aliyun-sdk-workspace"
    
    # 清理旧工作空间(如果存在)
    if [ -d "$WORKSPACE_DIR" ]; then
        echo "⚠️  Existing workspace found, cleaning..."
        rm -rf "$WORKSPACE_DIR"
    fi
    
    # 创建工作空间
    mkdir -p "$WORKSPACE_DIR"
    cd "$WORKSPACE_DIR"
    
    # 初始化Go module
    if go mod init sdk-script; then
        echo "✅ Go module initialized"
    else
        echo "⚠️  Go module init failed"
        
        # 自愈: 清理缓存重新初始化
        echo "Self-healing: Clearing Go cache..."
        go clean -modcache
        rm -rf "$WORKSPACE_DIR"
        
        mkdir -p "$WORKSPACE_DIR"
        cd "$WORKSPACE_DIR"
        
        if go mod init sdk-script; then
            echo "✅ Go module initialized after self-healing"
        else
            echo "❌ Go module init failed after retry"
            ERROR_CODE="GO_WORKSPACE_INIT_FAIL"
            return 1
        fi
    fi
    
    return 0
}

# SDK依赖下载增强
download_sdk_dependencies_enhanced() {
    echo "=== SDK Dependencies Download (Enhanced) ==="
    
    # 核心依赖列表
    CORE_DEPS=(
        "github.com/alibabacloud-go/darabonba-openapi/v2/client"
        "github.com/alibabacloud-go/tea"
        "github.com/alibabacloud-go/tea-utils/v2/service"
    )
    
    # GOPROXY镜像列表
    GOPROXY_MIRRORS=(
        "https://goproxy.cn,direct"
        "https://goproxy.io,direct"
        "https://proxy.golang.org,direct"
        "direct"
    )
    
    # 尝试不同的GOPROXY
    for proxy in "${GOPROXY_MIRRORS[@]}"; do
        echo "Trying GOPROXY: $proxy"
        export GOPROXY="$proxy"
        
        SUCCESS=true
        
        for dep in "${CORE_DEPS[@]}"; do
            echo "Downloading: $dep"
            
            # 增加超时时间
            if timeout 120 go get "$dep"; then
                echo "✅ Downloaded: $dep"
            else
                echo "⚠️  Failed to download: $dep"
                SUCCESS=false
                break
            fi
        done
        
        if [ "$SUCCESS" = true ]; then
            echo "✅ All dependencies downloaded successfully"
            return 0
        fi
        
        # 自愈: 清理缓存
        echo "Self-healing: Clearing module cache..."
        go clean -modcache
    done
    
    echo "❌ Failed to download dependencies from all GOPROXY mirrors"
    ERROR_CODE="DEP_NET_TIMEOUT"
    return 1
}
```

---

## 4. 降级路径和用户指导

### 4.1 降级路径决策树

```
[CLI安装失败]
    │
    ├── 尝试自愈(最多5次)
    │   │
    │   ├── 自愈成功 → 继续执行
    │   │
    │   └── 自愈失败 → 进入降级路径
    │       │
    │       ├── 降级路径1: JIT Go SDK模式
    │       │   │
    │       │   ├── Go runtime可用 → 使用Go SDK
    │       │   │
    │       │   ├── Go runtime不可用 → JIT下载Go
    │       │   │   │
    │       │   │   ├── JIT下载成功 → 使用Go SDK
    │       │   │   │
    │       │   │   └── JIT下载失败 → 进入降级路径2
    │       │   │
    │       │   └── Go SDK依赖下载失败 → 进入降级路径2
    │       │
    │       ├── 降级路径2: 控制台手动操作
    │       │   提供控制台链接和操作步骤
    │       │
    │       └── 降级路径3: 用户手动修复
    │           提供详细的错误信息和修复建议
```

### 4.2 用户指导模板

```markdown
## ❌ Installation Failed — Self-Healing Exhausted

### Error Summary
- **Error Code:** {{error_code}}
- **Error Category:** {{error_category}}
- **Failed Component:** {{failed_component}}
- **Attempted Self-Healing:** {{self_healing_attempts}} attempts

### What Happened
{{detailed_error_explanation}}

### Root Cause Analysis
{{root_cause_analysis}}

### Recommended Actions

#### Option 1: Manual Installation (Recommended)
```bash
# Step 1: Download CLI manually
curl -fsSL https://aliyuncli.alicdn.com/aliyun-cli-latest.tgz -o /tmp/aliyun-cli.tgz

# Step 2: Extract
tar -xzf /tmp/aliyun-cli.tgz -C /tmp

# Step 3: Install (may require sudo)
sudo mv /tmp/aliyun /usr/local/bin/
sudo chmod +x /usr/local/bin/aliyun

# Step 4: Verify
aliyun version
```

#### Option 2: Use JIT Go SDK Mode
```bash
# The Agent will automatically use Go SDK fallback
# Ensure Go runtime is available or will be JIT downloaded
```

#### Option 3: Use Alibaba Cloud Console
- Console URL: https://ecs.console.aliyun.com/
- Manual operation guide: {{console_guide_url}}

### Diagnostic Information
- **OS:** {{os}}
- **Architecture:** {{arch}}
- **Network:** {{network_status}}
- **Disk Space:** {{disk_space}}
- **Permissions:** {{permission_status}}
- **Request ID:** {{request_id}} (for support escalation)

### Support Escalation
If the issue persists after following recommended actions:
1. Collect diagnostic information above
2. Create a support ticket: https://workorder.console.aliyun.com/
3. Include Request ID: {{request_id}}
```

---

## 5. 健康检查和状态验证

### 5.1 安装后健康检查

```bash
# 健康检查脚本
health_check_aliyun_cli() {
    echo "=== Aliyun CLI Health Check ==="
    
    HEALTH_SCORE=0
    MAX_SCORE=10
    
    # Check 1: Binary exists (2 points)
    if [ -f "$INSTALL_PATH/aliyun" ]; then
        echo "✅ Binary exists"
        HEALTH_SCORE=$((HEALTH_SCORE + 2))
    else
        echo "❌ Binary missing"
    fi
    
    # Check 2: Execute permission (2 points)
    if [ -x "$INSTALL_PATH/aliyun" ]; then
        echo "✅ Execute permission present"
        HEALTH_SCORE=$((HEALTH_SCORE + 2))
    else
        echo "❌ Execute permission missing"
    fi
    
    # Check 3: In PATH (2 points)
    if command -v aliyun &> /dev/null; then
        echo "✅ In PATH"
        HEALTH_SCORE=$((HEALTH_SCORE + 2))
    else
        echo "❌ Not in PATH"
    fi
    
    # Check 4: Version command works (2 points)
    if aliyun version &> /dev/null; then
        echo "✅ Version command works"
        HEALTH_SCORE=$((HEALTH_SCORE + 2))
    else
        echo "❌ Version command failed"
    fi
    
    # Check 5: Basic API call works (2 points)
    if aliyun ecs DescribeRegions --output cols=RegionId rows=Regions.Region[] &> /dev/null; then
        echo "✅ Basic API call works"
        HEALTH_SCORE=$((HEALTH_SCORE + 2))
    else
        echo "⚠️  Basic API call failed (may be credential issue)"
    fi
    
    echo "Health Score: $HEALTH_SCORE/$MAX_SCORE"
    
    if [ "$HEALTH_SCORE" -ge 8 ]; then
        echo "✅ Health check passed (score ≥ 8)"
        return 0
    elif [ "$HEALTH_SCORE" -ge 6 ]; then
        echo "⚠️  Health check partially passed (score 6-7)"
        echo "Recommendation: Check credentials and network connectivity"
        return 0
    else
        echo "❌ Health check failed (score < 6)"
        echo "Recommendation: Reinstall or use fallback path"
        return 1
    fi
}
```

### 5.2 Go Runtime健康检查

```bash
health_check_go_runtime() {
    echo "=== Go Runtime Health Check ==="
    
    HEALTH_SCORE=0
    MAX_SCORE=8
    
    # Check 1: Go binary exists (2 points)
    if [ -f "/tmp/go-runtime/go/bin/go" ]; then
        echo "✅ Go binary exists"
        HEALTH_SCORE=$((HEALTH_SCORE + 2))
    else
        echo "❌ Go binary missing"
    fi
    
    # Check 2: Go version compatible (2 points)
    if command -v go &> /dev/null; then
        GO_VERSION=$(go version | awk '{print $3}')
        GO_MAJOR=$(echo "$GO_VERSION" | sed 's/go//' | cut -d. -f1)
        GO_MINOR=$(echo "$GO_VERSION" | sed 's/go//' | cut -d. -f2)
        
        if [ "$GO_MAJOR" -ge 1 ] && [ "$GO_MINOR" -ge 21 ]; then
            echo "✅ Go version compatible: $GO_VERSION"
            HEALTH_SCORE=$((HEALTH_SCORE + 2))
        else
            echo "❌ Go version incompatible: $GO_VERSION"
        fi
    else
        echo "❌ Go not in PATH"
    fi
    
    # Check 3: Workspace initialized (2 points)
    if [ -f "/tmp/aliyun-sdk-workspace/go.mod" ]; then
        echo "✅ Workspace initialized"
        HEALTH_SCORE=$((HEALTH_SCORE + 2))
    else
        echo "❌ Workspace not initialized"
    fi
    
    # Check 4: Dependencies available (2 points)
    if [ -d "/tmp/go-modcache/github.com/alibabacloud-go" ]; then
        echo "✅ SDK dependencies available"
        HEALTH_SCORE=$((HEALTH_SCORE + 2))
    else
        echo "⚠️  SDK dependencies not cached"
    fi
    
    echo "Health Score: $HEALTH_SCORE/$MAX_SCORE"
    
    if [ "$HEALTH_SCORE" -ge 6 ]; then
        echo "✅ Go runtime health check passed"
        return 0
    else
        echo "❌ Go runtime health check failed"
        return 1
    fi
}
```

---

## 6. 自愈效果追踪和优化

### 6.1 自愈效果指标

| 指标 | 目标值 | 测量方法 |
|------|--------|---------|
| 自愈成功率 | > 80% | 成功自愈次数 / 总异常次数 |
| 平均自愈时间 | < 30s | 从异常发生到自愈完成的时间 |
| 用户干预率 | < 20% | 需要用户手动干预的异常比例 |
| 降级路径使用率 | < 10% | 进入降级路径的异常比例 |
| 误判率 | < 5% | 错误分类错误的次数 / 总分类次数 |

### 6.2 自愈日志记录

```bash
# 自愈日志记录函数
log_self_healing_event() {
    local event_type="$1"
    local error_code="$2"
    local self_healing_action="$3"
    local result="$4"
    local duration="$5"
    
    LOG_FILE="/tmp/aliyun-self-healing.log"
    
    echo "$(date -Iseconds) | $event_type | $error_code | $self_healing_action | $result | $duration" >> "$LOG_FILE"
}

# 使用示例
log_self_healing_event "CLI_INSTALL" "NET_TIMEOUT" "MIRROR_SWITCH" "SUCCESS" "15s"
log_self_healing_event "GO_DOWNLOAD" "GO_DOWNLOAD_FAIL" "VERSION_FALLBACK" "SUCCESS" "45s"
log_self_healing_event "DEP_DOWNLOAD" "DEP_NET_TIMEOUT" "PROXY_SWITCH" "FAIL" "120s"
```

---

## 7. 实施优先级

### 7.1 立即实施 (P0)

1. **增强CLI安装预检阶段** — 添加网络、磁盘、权限预检
2. **实现智能错误分类** — 建立完整的错误代码体系
3. **增强下载健壮性** — 多镜像源、完整性校验、失败自愈
4. **实现健康检查机制** — 安装后验证和状态追踪

### 7.2 短期实施 (P1)

1. **优化Go runtime JIT下载** — 多版本、多镜像、完整性校验
2. **增强依赖下载容错** — 多GOPROXY、超时控制、缓存清理
3. **实现降级路径决策树** — 自动选择最优降级方案
4. **标准化用户指导模板** — 提供清晰的错误信息和修复建议

### 7.3 中期实施 (P2)

1. **实现自愈效果追踪** — 记录自愈日志，分析成功率
2. **建立自愈知识库** — 常见异常模式和自愈策略
3. **实现预防性自愈** — 基于历史数据预测异常
4. **优化自愈策略** — 基于成功率数据调整策略

---

## 8. 合规性检查清单

- [ ] 所有CLI安装路径包含预检阶段
- [ ] 错误分类覆盖所有已知异常类型
- [ ] 每个错误类型有对应的自愈策略
- [ ] 自愈失败后有明确的降级路径
- [ ] 用户指导包含详细的错误信息和修复建议
- [ ] 安装后执行健康检查
- [ ] 自愈事件记录到日志
- [ ] 自愈成功率可追踪和测量

---

*This framework is mandatory for all generated skills. Update quarterly based on self-healing effectiveness data.*