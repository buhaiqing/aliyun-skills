# CLI 安装异常诊断与自愈指南

> 覆盖 `aliyun` CLI 安装全生命周期的异常检测、根因分析、自动修复，以及降级策略。

---

## 一、异常检测体系架构

```
┌─────────────────────────────────────────────────────────┐
│               CLI 安装异常检测引擎                          │
├───────────────┬───────────────┬───────────────┬──────────┤
│  环境检测层    │  依赖检测层    │  网络检测层    │ 权限检测层│
├───────────────┼───────────────┼───────────────┼──────────┤
│ · OS 兼容性   │ · Go 运行时   │ · 公网连通性  │ · 文件权限│
│ · Shell 类型  │ · SDK 包      │ · 镜像加速器 │ · 目录权限│
│ · PATH 配置   │ · 版本冲突    │ · 代理设置   │ · RAM 权限│
│ · 架构检测    │ · 构建工具    │ · DNS 解析   │ · sudo 权限│
│ · 包管理器    │ · 编译器      │ · 限速检测   │ · 磁盘权限│
└───────────────┴───────────────┴───────────────┴──────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                 智能分析引擎（根因定位）                     │
├─────────────────────────────────────────────────────────┤
│  1. 异常识别 → 2. 模式匹配 → 3. 根因判定 → 4. 影响评估     │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                 自动治愈引擎                                │
├─────────────────────────────────────────────────────────┤
│  自愈策略  →  降级策略  →  回滚策略  →  上报策略           │
└─────────────────────────────────────────────────────────┘
```

---

## 二、环境检测层（Level 1）

### 2.1 完整环境诊断脚本

```bash
#!/bin/bash
# cms-env-diagnosis.sh
# 执行全面的环境检测，输出结构化诊断报告

set -e

echo '{"diag_type":"env_check","timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","checks":['

# Check 1: OS Type
OS_TYPE=$(uname -s)
OS_ARCH=$(uname -m)
echo '{"check":"os_compatibility","status":"'"$([ "$OS_TYPE" = "Linux" ] || [ "$OS_TYPE" = "Darwin" ] && echo 'PASS' || echo 'FAIL')"'","detail":"'"${OS_TYPE}/${OS_ARCH}"'","hint":"'"$([ "$OS_TYPE" = "Linux" ] || [ "$OS_TYPE" = "Darwin" ] || echo 'Unsupported OS. Use Linux (x86_64/aarch64) or macOS (x86_64/arm64)')"'"},'

# Check 2: Shell Type
SHELL_TYPE=$(basename "${SHELL:-unknown}")
echo '{"check":"shell_compatibility","status":"PASS","detail":"'"${SHELL_TYPE}"'"},'

# Check 3: Package manager
PM=""
if command -v brew &>/dev/null; then PM="homebrew"
elif command -v apt &>/dev/null; then PM="apt"
elif command -v yum &>/dev/null; then PM="yum"
elif command -v dnf &>/dev/null; then PM="dnf"
elif command -v apk &>/dev/null; then PM="apk"
else PM="none"
fi
echo '{"check":"package_manager","status":"'"$([ "$PM" != "none" ] && echo 'PASS' || echo 'WARN')"'","detail":"'"${PM}"'","hint":"'"$([ "$PM" = "none" ] && echo 'No package manager found. Use manual install from https://aliyuncli.alicdn.com/install.sh')"'"},'

# Check 4: Architecture compatibility
ARCH_SUPPORTED="PASS"
INSTALL_SCRIPT_SUPPORTED="true"
case "$OS_ARCH" in
  x86_64|amd64) ARCH_FMT="amd64" ;;
  aarch64|arm64) ARCH_FMT="arm64" ;;
  *) ARCH_SUPPORTED="WARN"; INSTALL_SCRIPT_SUPPORTED="false"; ARCH_FMT="$OS_ARCH" ;;
esac
echo '{"check":"arch_compatibility","status":"'"${ARCH_SUPPORTED}"'","detail":"'"${ARCH_FMT}"'","hint":"'"$([ "$ARCH_SUPPORTED" != "PASS" ] && echo 'Non-standard architecture. CLI install script may not support this arch. Try manual binary download.')"'"},'

# Check 5: PATH writability
echo '{"check":"path_writable","status":"'"$(test -w "$(dirname "$(which aliyun 2>/dev/null || echo '/usr/local/bin')")" 2>/dev/null && echo 'PASS' || echo 'WARN')"'","detail":"'$(dirname "$(which aliyun 2>/dev/null || echo '/usr/local/bin')")'","hint":"'"$(test -w "$(dirname "$(which aliyun 2>/dev/null || echo '/usr/local/bin')")" 2>/dev/null || echo 'Need sudo or use ~/.local/bin')"'"},'

# Check 6: curl/wget availability
echo '{"check":"download_tool","status":"'"$(command -v curl &>/dev/null && echo 'PASS' || command -v wget &>/dev/null && echo 'PASS' || echo 'FAIL')"'","detail":"'"$(command -v curl &>/dev/null && echo 'curl' || command -v wget &>/dev/null && echo 'wget' || echo 'none')"'","hint":"'"$(command -v curl &>/dev/null || command -v wget &>/dev/null || echo 'Install curl: brew install curl / apt install curl / yum install curl')"'"},'

# Check 7: Disk space for temp
TEMP_SPACE=$(df -k /tmp 2>/dev/null | awk 'NR==2 {print $4}' || echo 0)
echo '{"check":"disk_space","status":"'"$([ "${TEMP_SPACE:-0}" -gt 51200 ] && echo 'PASS' || echo 'WARN')"'","detail":"'"${TEMP_SPACE:-0} KB available"'" ,"hint":"'"$([ "${TEMP_SPACE:-0}" -le 51200 ] && echo 'Low disk space (<50MB). Clean /tmp before install.')"'"},'

# Check 8: macOS specific - Xcode CLI tools
if [ "$OS_TYPE" = "Darwin" ]; then
  XCODE_CHECK=$(xcode-select -p 2>/dev/null && echo 'installed' || echo 'missing')
  echo '{"check":"xcode_cli_tools","status":"'"$([ "$XCODE_CHECK" = "installed" ] && echo 'PASS' || echo 'WARN')"'","detail":"'${XCODE_CHECK}'","hint":"'"$([ "$XCODE_CHECK" != "installed" ] && echo 'Run: xcode-select --install')"'"}'
else
  echo '{"check":"xcode_cli_tools","status":"SKIP","detail":"not_macos"}'
fi

echo ']}'
```

### 2.2 各检测项的异常类型

| 检测项 | 异常码 | 严重程度 | 影响范围 |
|--------|--------|----------|----------|
| OS 不兼容 | `ENV_OS_INCOMPATIBLE` | CRITICAL | 无法安装 CLI |
| 架构不支持 | `ENV_ARCH_UNSUPPORTED` | WARNING | 安装脚本可能失败 |
| 包管理器缺失 | `ENV_PM_MISSING` | WARNING | 需手动/脚本安装 |
| PATH 不可写 | `ENV_PATH_NOT_WRITABLE` | WARNING | 安装后 CLI 不可用 |
| 下载工具缺失 | `ENV_DOWNLOAD_TOOL_MISSING` | CRITICAL | 无法下载安装包 |
| 磁盘空间不足 | `ENV_DISK_SPACE_LOW` | WARNING | 安装过程可能失败 |
| Xcode 工具缺失 | `ENV_XCODE_MISSING` | WARNING | macOS 上 Go 编译失败 |

---

## 三、依赖检测层（Level 2）

### 3.1 Go 运行时检测

```bash
#!/bin/bash
# cms-go-diagnosis.sh

echo '{"diag_type":"go_check","timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","checks":['

# Check 1: Go installed
GO_EXISTS=$(command -v go &>/dev/null && echo 'yes' || echo 'no')
GO_VERSION=$(go version 2>/dev/null || echo 'not_found')
echo '{"check":"go_installed","status":"'"$([ "$GO_EXISTS" = "yes" ] && echo 'PASS' || echo 'FAIL')"'","detail":"'"${GO_VERSION}"'","hint":"'"$([ "$GO_EXISTS" != "yes" ] && echo 'Install Go 1.21+: https://go.dev/dl/')"'"},'

# Check 2: Go version requirement (minimum 1.21 for JIT SDK fallback)
if [ "$GO_EXISTS" = "yes" ]; then
  GO_MAJOR=$(go version | sed -E 's/.*go([0-9]+)\..*/\1/')
  GO_MINOR=$(go version | sed -E 's/.*go[0-9]+\.([0-9]+).*/\1/')
  if [ "$GO_MAJOR" -gt 1 ] || ([ "$GO_MAJOR" -eq 1 ] && [ "$GO_MINOR" -ge 21 ]); then
    GO_VERSION_OK="PASS"
  else
    GO_VERSION_OK="FAIL"
  fi
  GO_JIT_OK="FAIL"
  if [ "$GO_MAJOR" -gt 1 ] || ([ "$GO_MAJOR" -eq 1 ] && [ "$GO_MINOR" -ge 24 ]); then
    GO_JIT_OK="PASS"
  fi
else
  GO_VERSION_OK="SKIP"
  GO_JIT_OK="SKIP"
fi
echo '{"check":"go_version_minimum","status":"'"${GO_VERSION_OK}"'","detail":"minimum: 1.21","hint":"'"$([ "$GO_VERSION_OK" = "FAIL" ] && echo 'Upgrade Go to 1.21+: https://go.dev/dl/')"'"},'
echo '{"check":"go_version_jit","status":"'"${GO_JIT_OK}"'","detail":"jit_recommended: 1.24+","hint":"'"$([ "$GO_JIT_OK" = "FAIL" ] && [ "$GO_EXISTS" = "yes" ] && echo 'JIT SDK fallback requires Go 1.24+. Upgrade recommended.')"'"},'

# Check 3: GOPATH/bin in PATH
if [ "$GO_EXISTS" = "yes" ]; then
  GOPATH_BIN="$(go env GOPATH 2>/dev/null)/bin"
  GOPATH_IN_PATH=$(echo "$PATH" | tr ':' '\n' | grep -q "$GOPATH_BIN" && echo 'yes' || echo 'no')
  echo '{"check":"gopath_in_path","status":"'"$([ "$GOPATH_IN_PATH" = "yes" ] && echo 'PASS' || echo 'WARN')"'","detail":"'"$GOPATH_BIN"'","hint":"'"$([ "$GOPATH_IN_PATH" != "yes" ] && echo 'Add to ~/.zshrc or ~/.bashrc: export PATH=\$PATH:'$GOPATH_BIN)"'"},'
fi

# Check 4: Go proxy configured
if [ "$GO_EXISTS" = "yes" ]; then
  GO_PROXY=$(go env GOPROXY 2>/dev/null || echo 'none')
  echo '{"check":"go_proxy","status":"PASS","detail":"'"${GO_PROXY}"'","hint":"'"$([ "$GO_PROXY" = "none" ] || [ "$GO_PROXY" = "direct" ] && echo 'Consider setting GOPROXY=https://goproxy.cn,direct for faster downloads in China region.')"'"},'
fi

# Check 5: GCC/build tools
BUILD_TOOLS="missing"
command -v gcc &>/dev/null && BUILD_TOOLS="gcc"
command -v clang &>/dev/null && BUILD_TOOLS="clang"
echo '{"check":"build_tools","status":"'"$([ "$BUILD_TOOLS" != "missing" ] && echo 'PASS' || echo 'WARN')"'","detail":"'"${BUILD_TOOLS}"'","hint":"'"$([ "$BUILD_TOOLS" = "missing" ] && echo 'Some Go packages may need C compiler. Install: xcode-select --install (macOS) or gcc (Linux).')"'"},'

# Close
echo '{"check":"go_module_cache","status":"PASS","detail":"'$(go env GOMODCACHE 2>/dev/null || echo 'unknown')'"}'
echo ']}'
```

### 3.2 SDK 依赖验证

```bash
#!/bin/bash
# cms-sdk-verify.sh
# 验证 CMS SDK 包的可安装性

echo '{"diag_type":"sdk_check","timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","packages":['

# Temp workspace
WORKSPACE=$(mktemp -d)
trap 'rm -rf "$WORKSPACE"' EXIT

cd "$WORKSPACE"
go mod init verify-cms-sdk 2>/dev/null

# Check darabonba-openapi
echo '{"package":"darabonba-openapi/v2","check":"resolve","status":"'"$(GOFLAGS=-mod=mod go list -m github.com/alibabacloud-go/darabonba-openapi/v2@latest &>/dev/null && echo 'PASS' || echo 'FAIL')"'","hint":"'"$(go list -m github.com/alibabacloud-go/darabonba-openapi/v2@latest 2>&1 | head -1 || echo 'Package resolution failed. Check network and proxy.')"'"},'

# Check cms-20190101
echo '{"package":"cms-20190101/v7","check":"resolve","status":"'"$(GOFLAGS=-mod=mod go list -m github.com/alibabacloud-go/cms-20190101/v7@latest &>/dev/null && echo 'PASS' || echo 'FAIL')"'","hint":"'"$(go list -m github.com/alibabacloud-go/cms-20190101/v7@latest 2>&1 | head -1 || echo 'CMS SDK resolution failed.')"'"},'

# Check tea
echo '{"package":"tea","check":"resolve","status":"'"$(GOFLAGS=-mod=mod go list -m github.com/alibabacloud-go/tea@latest &>/dev/null && echo 'PASS' || echo 'FAIL')"'","hint":"'"$(go list -m github.com/alibabacloud-go/tea@latest 2>&1 | head -1 || echo 'Tea package resolution failed.')"'"},'

# Check cms-2024-03-30 (advanced)
echo '{"package":"cms-2024-03-30/v2","check":"resolve","status":"'"$(GOFLAGS=-mod=mod go list -m github.com/alibabacloud-go/cms-2024-03-30/v2@latest &>/dev/null && echo 'PASS' || echo 'FAIL')"'","hint":"'"$(go list -m github.com/alibabacloud-go/cms-2024-03-30/v2@latest 2>&1 | head -1 || echo 'CMS 2.0 SDK resolution failed (optional package).')"'"}'

echo ']}'
```

### 3.3 依赖异常类型

| 检测项 | 异常码 | 严重程度 | 影响范围 |
|--------|--------|----------|----------|
| Go 未安装 | `DEP_GO_MISSING` | CRITICAL | JIT SDK 回退不可用 |
| Go 版本过低 | `DEP_GO_VERSION` | CRITICAL | 无法编译 SDK 脚本 |
| Go JIT 版本不足 | `DEP_GO_JIT` | WARNING | 部分高级功能受限 |
| GOPATH/bin 未在 PATH | `DEP_GOPATH_PATH` | WARNING | go install 后不可用 |
| SDK 包解析失败 | `DEP_SDK_RESOLVE` | CRITICAL | 无法拉取 SDK 依赖 |
| 构建工具缺失 | `DEP_BUILD_TOOLS` | WARNING | CGO 依赖包编译失败 |
| Go 代理不可达 | `DEP_GO_PROXY` | WARNING | 国外源下载慢 |

---

## 四、网络检测层（Level 3）

### 4.1 网络连通性诊断脚本

```bash
#!/bin/bash
# cms-network-diagnosis.sh

echo '{"diag_type":"network_check","timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","checks":['

# Check 1: DNS resolution
echo '{"check":"dns_resolution","status":"'"$(host metrics.aliyuncs.com &>/dev/null && echo 'PASS' || nslookup metrics.aliyuncs.com &>/dev/null && echo 'PASS' || echo 'FAIL')"'","detail":"metrics.aliyuncs.com","hint":"'"$(host metrics.aliyuncs.com &>/dev/null || nslookup metrics.aliyuncs.com &>/dev/null || echo 'DNS resolution failed. Check /etc/resolv.conf or network config.')"'"},'

# Check 2: CMS API endpoint connectivity
CMS_HTTP_CODE=$(curl -o /dev/null -s -w "%{http_code}" --connect-timeout 5 "https://metrics.aliyuncs.com" 2>/dev/null || echo 'timeout')
echo '{"check":"cms_endpoint","status":"'"$([ "$CMS_HTTP_CODE" != "timeout" ] && [ "$CMS_HTTP_CODE" != "000" ] && echo 'PASS' || echo 'FAIL')"'","detail":"HTTP:'${CMS_HTTP_CODE}'","hint":"'"$([ "$CMS_HTTP_CODE" = "timeout" ] || [ "$CMS_HTTP_CODE" = "000" ] && echo 'CMS endpoint unreachable. Check firewall, VPC, or use internal endpoint.')"'"},'

# Check 3: CLI download server
ALIYUN_CLI_CODE=$(curl -o /dev/null -s -w "%{http_code}" --connect-timeout 5 "https://aliyuncli.alicdn.com/install.sh" 2>/dev/null || echo 'timeout')
echo '{"check":"cli_download_server","status":"'"$([ "$ALIYUN_CLI_CODE" = "200" ] && echo 'PASS' || echo 'FAIL')"'","detail":"HTTP:'${ALIYUN_CLI_CODE}'","hint":"'"$([ "$ALIYUN_CLI_CODE" != "200" ] && echo 'CLI download server unreachable. Try mirror: https://aliyuncli.alicdn.com/install.sh or manual download.')"'"},'

# Check 4: GitHub/GitLab (Go mod proxy fallback)
GITHUB_CODE=$(curl -o /dev/null -s -w "%{http_code}" --connect-timeout 5 "https://github.com" 2>/dev/null || echo 'timeout')
echo '{"check":"github_reachability","status":"'"$([ "$GITHUB_CODE" != "timeout" ] && echo 'PASS' || echo 'WARN')"'","detail":"HTTP:'${GITHUB_CODE}'","hint":"'"$([ "$GITHUB_CODE" = "timeout" ] && echo 'GitHub unreachable. Go proxy may fail for direct dependencies. Set GOPROXY=https://goproxy.cn,direct')"'"},'

# Check 5: Proxy detection
echo '{"check":"proxy_detection","status":"PASS","detail":"http_proxy:'${http_proxy:-none}' https_proxy:'${https_proxy:-none}'","hint":"'"$([ -n "$http_proxy" ] || [ -n "$https_proxy" ] && echo 'Proxy detected. Ensure proxy supports Go module downloads and HTTPS.')"'"},'

# Check 6: Alibaba Cloud internal endpoint (VPC)
INTERNAL_CODE=$(curl -o /dev/null -s -w "%{http_code}" --connect-timeout 3 "https://metrics-intra.aliyuncs.com" 2>/dev/null || echo 'timeout')
echo '{"check":"internal_endpoint","status":"'"$([ "$INTERNAL_CODE" != "timeout" ] && echo 'PASS' || echo 'INFO')"'","detail":"HTTP:'${INTERNAL_CODE}'","hint":"'"$([ "$INTERNAL_CODE" != "timeout" ] && echo 'Running inside Alibaba Cloud VPC. Use internal endpoint for better performance.')"'"},'

# Check 7: Download speed test
SPEED_START=$(date +%s%N)
SPEED_SIZE=$(curl -o /dev/null -s -w "%{size_download}" --connect-timeout 5 --max-time 5 "https://aliyuncli.alicdn.com/install.sh" 2>/dev/null || echo '0')
SPEED_END=$(date +%s%N)
SPEED_DURATION=$(( (SPEED_END - SPEED_START) / 1000000 ))
if [ "${SPEED_SIZE}" -gt 0 ] && [ "${SPEED_DURATION}" -gt 0 ]; then
  SPEED_KBPS=$(( SPEED_SIZE * 1000 / SPEED_DURATION ))
  SPEED_STATUS="PASS"
  [ "$SPEED_KBPS" -lt 50 ] && SPEED_STATUS="WARN"
  [ "$SPEED_KBPS" -lt 10 ] && SPEED_STATUS="FAIL"
else
  SPEED_KBPS=0
  SPEED_STATUS="SKIP"
fi
echo '{"check":"download_speed","status":"'"${SPEED_STATUS}"'","detail":"'${SPEED_KBPS}' KB/s","hint":"'"$([ "$SPEED_STATUS" = "WARN" ] && echo 'Slow download speed. Consider using proxy or mirror.')"'"}'

echo ']}'
```

### 4.2 网络异常类型

| 检测项 | 异常码 | 严重程度 | 影响范围 |
|--------|--------|----------|----------|
| DNS 解析失败 | `NET_DNS_FAILURE` | CRITICAL | CLI 安装/API 调用全部失败 |
| CMS 端点不可达 | `NET_CMS_ENDPOINT` | CRITICAL | 无法执行任何 CMS 操作 |
| CLI 下载源不可达 | `NET_CLI_SOURCE` | CRITICAL | 无法安装/更新 CLI |
| GitHub 不可达 | `NET_GITHUB` | WARNING | Go 依赖拉取失败 |
| 代理配置问题 | `NET_PROXY_ISSUE` | WARNING | HTTPS/Go mod 可能不通过代理 |
| 下载速度慢 | `NET_SPEED_SLOW` | WARNING | 安装超时 |
| VPC 内部端点可用 | `NET_VPC_ENDPOINT` | INFO | 可切换内网端点提升性能 |

### 4.3 中国区网络优化方案

```bash
# 方案 A: 使用 Go 代理加速（推荐）
export GOPROXY=https://goproxy.cn,direct

# 方案 B: 使用阿里云 CLI 镜像
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"

# 方案 C: 直接下载二进制（离线安装）
# Linux amd64
curl -o /tmp/aliyun-cli-linux-amd64.tgz \
  "https://aliyuncli.alicdn.com/aliyun-cli-linux-amd64.tgz"

# macOS arm64 (Apple Silicon)
curl -o /tmp/aliyun-cli-macos-arm64.tgz \
  "https://aliyuncli.alicdn.com/aliyun-cli-macos-arm64.tgz"

# macOS amd64 (Intel)
curl -o /tmp/aliyun-cli-macosx-amd64.tgz \
  "https://aliyuncli.alicdn.com/aliyun-cli-macosx-amd64.tgz"
```

---

## 五、权限检测层（Level 4）

### 5.1 权限诊断脚本

```bash
#!/bin/bash
# cms-permission-diagnosis.sh

echo '{"diag_type":"permission_check","timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","checks":['

# Check 1: Credential existence
echo '{"check":"ak_id_exists","status":"'"$(test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo 'PASS' || echo 'FAIL')"'","detail":"<masked>","hint":"'"$(test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" || echo 'Set env: export ALIBABA_CLOUD_ACCESS_KEY_ID=<your-ak-id>')"'"},'
echo '{"check":"ak_secret_exists","status":"'"$(test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo 'PASS' || echo 'FAIL')"'","detail":"<masked>","hint":"'"$(test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" || echo 'Set env: export ALIBABA_CLOUD_ACCESS_KEY_SECRET=<your-ak-secret>')"'"},'
echo '{"check":"region_exists","status":"'"$(test -n "$ALIBABA_CLOUD_REGION_ID" && echo 'PASS' || echo 'FAIL')"'","detail":"'${ALIBABA_CLOUD_REGION_ID:-unset}'","hint":"'"$(test -n "$ALIBABA_CLOUD_REGION_ID" || echo 'Set env: export ALIBABA_CLOUD_REGION_ID=cn-hangzhou')"'"},'

# Check 2: Credential validity (dry-run API call)
if [ -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" ] && [ -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" ]; then
  VALIDITY_CHECK=$(aliyun cms DescribeProjectMeta --RegionId "${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}" 2>&1 | head -5)
  if echo "$VALIDITY_CHECK" | grep -q '"Code": "200"'; then
    CRED_STATUS="PASS"
    CRED_DETAIL="valid"
    CRED_HINT="ok"
  elif echo "$VALIDITY_CHECK" | grep -qi 'Forbidden'; then
    CRED_STATUS="FAIL"
    CRED_DETAIL="forbidden"
    CRED_HINT="RAM policy missing. Attach AliyunCloudMonitorReadOnlyAccess or full access."
  elif echo "$VALIDITY_CHECK" | grep -qi 'InvalidAccessKeyId\|InvalidAccessKeySecret\|SignatureDoesNotMatch'; then
    CRED_STATUS="FAIL"
    CRED_DETAIL="invalid"
    CRED_HINT="AccessKey is invalid or expired. Generate new AK at RAM console."
  elif echo "$VALIDITY_CHECK" | grep -qi 'throttling\|flow control'; then
    CRED_STATUS="WARN"
    CRED_DETAIL="throttled"
    CRED_HINT="Rate limited. Wait and retry."
  else
    CRED_STATUS="WARN"
    CRED_DETAIL="unknown"
    CRED_HINT="Unexpected response. Check network and credentials."
  fi
else
  CRED_STATUS="SKIP"
  CRED_DETAIL="env_missing"
  CRED_HINT="Set credentials first."
fi
echo '{"check":"credential_validity","status":"'"${CRED_STATUS}"'","detail":"'"${CRED_DETAIL}"'","hint":"'"${CRED_HINT}"'"},'

# Check 3: CLI binary permission
CLI_PATH=$(which aliyun 2>/dev/null || echo 'not_installed')
if [ "$CLI_PATH" != "not_installed" ]; then
  CLI_EXECUTABLE=$(test -x "$CLI_PATH" && echo 'yes' || echo 'no')
  echo '{"check":"cli_executable","status":"'"$([ "$CLI_EXECUTABLE" = "yes" ] && echo 'PASS' || echo 'FAIL')"'","detail":"'${CLI_PATH}'","hint":"'"$([ "$CLI_EXECUTABLE" != "yes" ] && echo 'Fix: chmod +x '${CLI_PATH})"'"}'
else
  echo '{"check":"cli_executable","status":"SKIP","detail":"cli_not_installed"}'
fi

echo ']}'
```

### 5.2 权限异常类型

| 检测项 | 异常码 | 严重程度 | 影响范围 |
|--------|--------|----------|----------|
| AK ID 未设置 | `PERM_AK_ID_MISSING` | CRITICAL | 所有 API 调用失败 |
| AK Secret 未设置 | `PERM_AK_SECRET_MISSING` | CRITICAL | 所有 API 调用失败 |
| Region 未设置 | `PERM_REGION_MISSING` | WARNING | API 调用可能默认 Region |
| AK 无效/过期 | `PERM_AK_INVALID` | CRITICAL | 所有 API 调用失败 |
| RAM 权限不足 | `PERM_RAM_FORBIDDEN` | CRITICAL | 按操作类型受限 |
| CLI 不可执行 | `PERM_CLI_NOT_EXEC` | CRITICAL | CLI 不可用 |
| AK 被限流 | `PERM_AK_THROTTLED` | WARNING | 临时不可用 |

---

## 六、智能分析引擎

### 6.1 异常关联分析

```bash
#!/bin/bash
# cms-anomaly-analyzer.sh
# 综合所有检测结果，执行关联分析和根因判定

analyze_root_cause() {
  local env_result="$1"    # 环境检测 JSON
  local dep_result="$2"    # 依赖检测 JSON
  local net_result="$3"    # 网络检测 JSON
  local perm_result="$4"   # 权限检测 JSON

  echo '{"analysis_type":"root_cause","timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","findings":['

  local findings=()

  # 规则 1: DNS + 端点同时失败 → 网络故障（根因）
  if echo "$net_result" | grep -q '"dns_resolution".*"FAIL"' && \
     echo "$net_result" | grep -q '"cms_endpoint".*"FAIL"'; then
    findings+=('{"pattern":"NET_ROOT_DNS","root_cause":"DNS resolution failure","impact":"ALL_OPERATIONS","confidence":0.95,"evidence":["DNS resolution failed for metrics.aliyuncs.com","CMS endpoint unreachable"],"remedy":"Check /etc/resolv.conf, network connectivity, or corporate firewall policy.","auto_fix":"sudo sh -c \"echo \\\"nameserver 8.8.8.8\\\" >> /etc/resolv.conf\""}')
  fi

  # 规则 2: CLI 源不可达 + GitHub 不可达 → 网络隔离环境（根因）
  if echo "$net_result" | grep -q '"cli_download_server".*"FAIL"' && \
     echo "$net_result" | grep -q '"github_reachability".*"WARN"'; then
    findings+=('{"pattern":"NET_ROOT_ISOLATED","root_cause":"Network isolation (firewall/proxy)","impact":"CLI_INSTALL_FAILED,SDK_DOWNLOAD_FAILED","confidence":0.90,"evidence":["CLI download server unreachable","GitHub unreachable"],"remedy":"Use internal mirror, configure proxy, or offline install.","auto_fix":"export GOPROXY=https://goproxy.cn,direct; export http_proxy=<proxy>; export https_proxy=<proxy>"}')
  fi

  # 规则 3: AK 存在 + API 返回 Forbidden → RAM 权限不足（根因）
  if echo "$perm_result" | grep -q '"ak_id_exists".*"PASS"' && \
     echo "$perm_result" | grep -q '"credential_validity".*"FAIL".*"forbidden"'; then
    findings+=('{"pattern":"PERM_ROOT_RAM","root_cause":"RAM policy insufficient","impact":"API_CALLS_FORBIDDEN","confidence":0.95,"evidence":["AK credentials are set","API returns Forbidden"],"remedy":"Attach AliyunCloudMonitorReadOnlyAccess or AliyunCloudMonitorFullAccess policy.","auto_fix":"Contact RAM admin to attach CMS policy; verify: aliyun ram ListPoliciesForUser --UserName <user>"}')
  fi

  # 规则 4: Go 未安装 + SDK 解析失败 → 编译环境缺失（根因）
  if echo "$dep_result" | grep -q '"go_installed".*"FAIL"' && \
     echo "$dep_result" | grep -q '"cms-20190101".*"FAIL"'; then
    findings+=('{"pattern":"DEP_ROOT_GO_MISSING","root_cause":"Go runtime not installed","impact":"JIT_SDK_FALLBACK_UNAVAILABLE","confidence":0.95,"evidence":["Go command not found","SDK package resolution failed"],"remedy":"Install Go 1.21+ from https://go.dev/dl/","auto_fix":"Use brew install go (macOS) or apt install golang-go (Linux) or download from https://go.dev/dl/"}')
  fi

  # 规则 5: 环境检测多 WARN → 综合环境问题
  WARN_COUNT=$(echo "$env_result" | grep -c '"WARN"' 2>/dev/null || echo 0)
  if [ "$WARN_COUNT" -ge 3 ]; then
    findings+=('{"pattern":"ENV_ROOT_MULTI_WARN","root_cause":"Multiple environment issues detected","impact":"INSTALL_MAY_FAIL","confidence":0.70,"evidence":["'"${WARN_COUNT}"' environment warnings"],"remedy":"Resolve each warning by priority. Start with OS compatibility and PATH.","auto_fix":"Review each env check hint and apply fixes sequentially."}')
  fi

  # 规则 6: 磁盘空间不足 + 下载工具缺失 → 安装环境不完整
  if echo "$env_result" | grep -q '"disk_space".*"WARN"' && \
     echo "$env_result" | grep -q '"download_tool".*"FAIL"'; then
    findings+=('{"pattern":"ENV_ROOT_INSTALL_ENV","root_cause":"Incomplete installation environment","impact":"CLI_INSTALL_FAILED","confidence":0.85,"evidence":["Low disk space","No download tool"],"remedy":"Free disk space and install curl/wget.","auto_fix":"rm -rf /tmp/* && brew install curl (macOS) or apt install curl (Linux)"}')
  fi

  # 规则 7: CMS 端点可达 + Credential 无效 → AK 问题（根因）
  if echo "$net_result" | grep -q '"cms_endpoint".*"PASS"' && \
     echo "$perm_result" | grep -q '"credential_validity".*"FAIL".*"invalid"'; then
    findings+=('{"pattern":"PERM_ROOT_AK_INVALID","root_cause":"AccessKey is invalid or expired","impact":"ALL_API_CALLS_FAIL","confidence":0.95,"evidence":["CMS endpoint reachable","API returns InvalidAccessKeyId or SignatureDoesNotMatch"],"remedy":"Generate new AccessKey in RAM console.","auto_fix":"Go to RAM console -> Users -> Create AccessKey. Then update environment variables."}')
  fi

  # 规则 8: 网络下载速度慢 + CLI 源可达 → 带宽问题
  if echo "$net_result" | grep -q '"download_speed".*"WARN"' && \
     echo "$net_result" | grep -q '"cli_download_server".*"PASS"'; then
    findings+=('{"pattern":"NET_ROOT_SLOW_BANDWIDTH","root_cause":"Low network bandwidth","impact":"INSTALL_TIMEOUT","confidence":0.80,"evidence":["CLI server reachable but slow download","Download speed < 50KB/s"],"remedy":"Use proxy or mirror for faster download.","auto_fix":"export GOPROXY=https://goproxy.cn,direct; or use offline binary download."}')
  fi

  # 如果没有匹配的规则
  if [ ${#findings[@]} -eq 0 ]; then
    echo '{"pattern":"NO_MATCH","root_cause":"No known pattern matched","impact":"UNKNOWN","confidence":0,"evidence":[],"remedy":"Run full diagnostic and review individual check results."}'
  else
    # 输出所有匹配的发现
    local first=true
    for f in "${findings[@]}"; do
      $first || echo ','
      echo -n "$f"
      first=false
    done
  fi

  echo ']}'
}

# 综合诊断入口
full_diagnosis() {
  echo "{"
  echo '"diagnosis_id":"'$(uuidgen 2>/dev/null || date +%s)'",'
  echo '"timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'",'
  echo '"environment_check":'
  cms-env-diagnosis.sh
  echo ','
  echo '"dependency_check":'
  cms-go-diagnosis.sh
  echo ','
  echo '"network_check":'
  cms-network-diagnosis.sh
  echo ','
  echo '"permission_check":'
  cms-permission-diagnosis.sh
  echo ','
  echo '"root_cause_analysis":'
  analyze_root_cause \
    "$(cms-env-diagnosis.sh 2>/dev/null)" \
    "$(cms-go-diagnosis.sh 2>/dev/null)" \
    "$(cms-network-diagnosis.sh 2>/dev/null)" \
    "$(cms-permission-diagnosis.sh 2>/dev/null)"
  echo '}'
}
```

### 6.2 异常影响评估矩阵

| 检测结果组合 | 影响级别 | 可操作降级策略 |
|-------------|----------|---------------|
| CLI 可用 + SDK 可用 | FULL | 全功能模式 |
| CLI 可用 + SDK 不可用 | NORMAL | CLI-only 模式 |
| CLI 不可用 + SDK 可用 | DEGRADED | SDK-only 模式 |
| CLI 不可用 + AK 无效 | CRIPPLED | 需人工介入 |
| 网络完全不可达 | DOWN | 离线模式（使用缓存） |
| 仅 CLI 安装失败 | DEGRADED | 使用 JIT SDK 替代 |
| 所有通道失败 | BLOCKED | 上报错误，无法继续 |

---

## 七、自动治愈引擎

### 7.1 自愈脚本

```bash
#!/bin/bash
# cms-auto-heal.sh
# 自动检测并修复 CLI 安装环境问题

set -e

heal_missing_cli() {
  echo "[HEAL] Attempting to install aliyun CLI..."

  # 检测架构
  local os_arch
  case "$(uname -m)" in
    x86_64|amd64) os_arch="amd64" ;;
    aarch64|arm64) os_arch="arm64" ;;
    *) echo "[HEAL_FAIL] Unsupported architecture: $(uname -m)"; return 1 ;;
  esac

  # 检测 OS
  case "$(uname -s)" in
    Linux)
      echo "[HEAL] Installing aliyun CLI on Linux (${os_arch})..."
      if command -v curl &>/dev/null; then
        /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
      elif command -v wget &>/dev/null; then
        /bin/bash -c "$(wget -qO- https://aliyuncli.alicdn.com/install.sh)"
      else
        echo "[HEAL_FAIL] No curl or wget available"
        return 1
      fi
      ;;
    Darwin)
      echo "[HEAL] Installing aliyun CLI on macOS (${os_arch})..."
      if command -v brew &>/dev/null; then
        brew install aliyun-cli
      elif command -v curl &>/dev/null; then
        /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
      else
        echo "[HEAL_FAIL] No brew or curl available"
        return 1
      fi
      ;;
    *)
      echo "[HEAL_FAIL] Unsupported OS: $(uname -s)"
      return 1
      ;;
  esac

  # 验证安装
  if command -v aliyun &>/dev/null; then
    echo "[HEAL_SUCCESS] aliyun CLI installed: $(aliyun version)"
    return 0
  else
    echo "[HEAL_FAIL] CLI installation verification failed"
    return 1
  fi
}

heal_missing_go() {
  echo "[HEAL] Attempting to install Go runtime..."

  # Fetch latest Go stable version dynamically
  GO_VERSION=$(curl -sL "https://go.dev/dl/?mode=json" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['version'])" 2>/dev/null || echo "go1.24.0")

  case "$(uname -s)" in
    Linux)
      echo "[HEAL] Installing Go ${GO_VERSION} on Linux..."
      curl -fsSL "https://go.dev/dl/${GO_VERSION}.linux-${os_arch}.tar.gz" -o /tmp/go.tar.gz
      tar -C /usr/local -xzf /tmp/go.tar.gz
      export PATH=$PATH:/usr/local/go/bin
      echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
      ;;
    Darwin)
      echo "[HEAL] Installing Go on macOS..."
      if command -v brew &>/dev/null; then
        brew install go
      else
        echo "[HEAL] Installing Go ${GO_VERSION} on macOS..."
        curl -fsSL "https://go.dev/dl/${GO_VERSION}.darwin-${os_arch}.tar.gz" -o /tmp/go.tar.gz
        tar -C /usr/local -xzf /tmp/go.tar.gz
        export PATH=$PATH:/usr/local/go/bin
      fi
      ;;
  esac

  if command -v go &>/dev/null; then
    echo "[HEAL_SUCCESS] Go installed: $(go version)"
    return 0
  else
    echo "[HEAL_FAIL] Go installation failed"
    return 1
  fi
}

heal_sdk_deps() {
  local workspace="/tmp/aliyun-sdk-workspace"
  echo "[HEAL] Verifying SDK dependencies in ${workspace}..."

  mkdir -p "$workspace"
  cd "$workspace"

  if [ ! -f "go.mod" ]; then
    go mod init sdk-script 2>/dev/null
  fi

  local packages=(
    "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    "github.com/alibabacloud-go/cms-20190101/v7/client"
  )

  local all_ok=true
  for pkg in "${packages[@]}"; do
    echo "[HEAL] Resolving ${pkg}..."
    if go get "$pkg" 2>/dev/null; then
      echo "[HEAL_OK] ${pkg} resolved"
    else
      echo "[HEAL_FAIL] ${pkg} resolution failed"
      all_ok=false
    fi
  done

  if $all_ok; then
    go mod tidy 2>/dev/null
    echo "[HEAL_SUCCESS] All SDK dependencies resolved"
    return 0
  else
    echo "[HEAL_PARTIAL] Some SDK deps failed. Functionality may be limited."
    return 1
  fi
}

heal_proxy_config() {
  echo "[HEAL] Configuring optimal Go proxy for China region..."
  export GOPROXY=https://goproxy.cn,direct
  if [ -f ~/.zshrc ]; then
    if ! grep -q "GOPROXY" ~/.zshrc; then
      echo 'export GOPROXY=https://goproxy.cn,direct' >> ~/.zshrc
    fi
  elif [ -f ~/.bashrc ]; then
    if ! grep -q "GOPROXY" ~/.bashrc; then
      echo 'export GOPROXY=https://goproxy.cn,direct' >> ~/.bashrc
    fi
  fi
  echo "[HEAL_SUCCESS] Go proxy configured: ${GOPROXY}"
}

heal_env_vars() {
  echo "[HEAL] Checking and prompting for environment variables..."

  local missing=()
  [ -z "$ALIBABA_CLOUD_ACCESS_KEY_ID" ] && missing+=("ALIBABA_CLOUD_ACCESS_KEY_ID")
  [ -z "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" ] && missing+=("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
  [ -z "$ALIBABA_CLOUD_REGION_ID" ] && missing+=("ALIBABA_CLOUD_REGION_ID")

  if [ ${#missing[@]} -eq 0 ]; then
    echo "[HEAL_OK] All environment variables are set"
    return 0
  fi

  echo "[HEAL_WARN] Missing env vars: ${missing[*]}"
  echo "[HEAL_HINT] Set them before proceeding:"
  for var in "${missing[@]}"; do
    echo "  export ${var}=<your-value>"
  done
  return 1
}

# 自愈主入口
heal_all() {
  echo "=========================================="
  echo "  CMS Environment Auto-Heal"
  echo "=========================================="
  echo ""

  local steps=(
    "heal_env_vars:Environment variables"
    "heal_missing_cli:aliyun CLI"
    "heal_missing_go:Go runtime"
    "heal_proxy_config:Go proxy"
    "heal_sdk_deps:SDK dependencies"
  )

  local success_count=0
  local total_count=${#steps[@]}
  local fail_list=()

  for step in "${steps[@]}"; do
    local func="${step%%:*}"
    local desc="${step##*:}"
    echo ""
    echo "--- Step: ${desc} ---"
    if $func; then
      ((success_count++))
    else
      fail_list+=("$desc")
    fi
  done

  echo ""
  echo "=========================================="
  echo "  Heal Summary"
  echo "=========================================="
  echo "  Success: ${success_count}/${total_count}"
  if [ ${#fail_list[@]} -gt 0 ]; then
    echo "  Failed: ${fail_list[*]}"
    echo "  Status: DEGRADED (manual intervention required)"
  else
    echo "  Status: HEALTHY"
  fi
  echo "=========================================="
}
```

### 7.2 降级策略矩阵

| 异常场景 | 降级策略 | 降级后能力 | 用户体验 |
|---------|---------|-----------|---------|
| CLI 未安装 | 切换到 JIT Go SDK | 全功能（依赖 Go 编译） | 首次调用延迟增加（约 30s） |
| CLI 未安装，Go 可用 | 使用 JIT SDK 并缓存二进制 | 全功能 | 首次调用后正常 |
| CLI 未安装，Go 不可用 | 提示用户手动安装 | 受限（仅提供 API 文档指导） | 用户手动操作 |
| SDK 依赖解析失败 | 重试 3 次 → 切换缓存目录 → 切换 Go Proxy | 全功能（重试成功） | 延迟增加 |
| 所有 Go Proxy 失败 | 降级为 CLI-only 模式 | CLI 覆盖的操作 | 功能受限 |
| AK 无效/过期 | 提示用户重新生成 AK | 不可用 | 用户手动操作 |
| 网络不可达 | 使用本地缓存数据（如有） | 只读查询缓存 | 数据非实时 |
| DNS 故障 | 添加 hosts 映射 → 切换 DNS | 全功能（修复成功） | 修复后正常 |
| 下载速度慢 | 使用离线二进制安装 | 全功能 | 安装过程较慢 |
| 磁盘空间不足 | 清理 /tmp 后重试 | 全功能 | 稍微延迟 |
| RAM 权限不足 | 提示用户权限需求，提供 RAM 策略模板 | 受限操作 | 用户手动授权 |

### 7.3 降级执行流程

```
执行操作前检测
    │
    ├── CLI 可用？──→ 使用 CLI 执行（Primary Path）
    │
    ├── CLI 不可用，Go 可用？──→ 使用 JIT Go SDK（Degraded Path 1）
    │                              │
    │                              ├── SDK 编译成功？──→ 执行操作
    │                              │
    │                              └── SDK 编译失败？──→ 检查 Go Proxy → 重试
    │
    ├── CLI 不可用，Go 不可用？──→ 提示用户手动安装（Degraded Path 2）
    │                              │
    │                              ├── 用户确认安装？──→ 执行自动安装脚本
    │                              │
    │                              └── 用户拒绝安装？──→ 提供 OpenAPI 文档指导
    │
    └── 全部不可用？──→ 上报完整诊断报告，建议人工介入
```

---

## 八、完整诊断执行示例

### 8.1 单命令全量诊断

```bash
# 一键执行全量诊断
curl -fsSL https://raw.githubusercontent.com/.../cms-full-diagnosis.sh | bash

# 或本地执行
bash cms-full-diagnosis.sh > /tmp/cms-diagnosis.json
```

### 8.2 诊断报告示例输出

```json
{
  "diagnosis_id": "diag-20260514-abc123",
  "timestamp": "2026-05-14T10:00:00Z",
  "summary": {
    "status": "DEGRADED",
    "total_checks": 28,
    "passed": 22,
    "warnings": 4,
    "failures": 2,
    "critical": 1
  },
  "root_cause": {
    "pattern": "PERM_ROOT_RAM",
    "confidence": 0.95,
    "impact": "API_CALLS_FORBIDDEN",
    "auto_fix_available": false
  },
  "remediation": [
    {
      "priority": "CRITICAL",
      "action": "RAM policy missing",
      "command": "Attach AliyunCloudMonitorReadOnlyAccess policy via RAM console",
      "automated": false
    },
    {
      "priority": "WARNING",
      "action": "Go version outdated (1.18)",
      "command": "Upgrade to 1.21+ for SDK compatibility",
      "automated": "export PATH=/usr/local/go/bin:$PATH (if upgraded)"
    }
  ],
  "heal_attempts": [
    {"action": "heal_env_vars", "result": "ok"},
    {"action": "heal_missing_cli", "result": "skipped (CLI exists)"},
    {"action": "heal_proxy_config", "result": "ok"},
    {"action": "heal_sdk_deps", "result": "ok"}
  ]
}
```

### 8.3 SKILL 集成使用

在 SKILL.md 的 **Pre-flight Checks** 阶段，Agent 应当：

```
如果 CLI 命令失败 → 执行 CLI 安装诊断：
  1. 运行 cms-env-diagnosis.sh 检查环境
  2. 运行 cms-network-diagnosis.sh 检查网络
  3. 运行 cms-permission-diagnosis.sh 检查权限
  4. 运行 cms-anomaly-analyzer.sh 进行根因分析
  5. 根据根因分析结果执行自动治愈
  6. 如果治愈成功，继续执行操作
  7. 如果治愈失败，执行降级策略
```

---

## 九、异常处理决策树

```
安装/调用失败
    │
    ├── 检查 CLI 是否存在
    │   ├── 不存在 → 自动安装
    │   │   ├── 成功 → 继续
    │   │   └── 失败 → 诊断原因
    │   │       ├── 网络问题 → heal_proxy → 重试
    │   │       ├── 权限问题 → sudo/修复 → 重试
    │   │       └── 环境问题 → 提供手动安装指南
    │   │
    │   └── 存在 → 检查 CLI 版本
    │       ├── 版本过旧 → 升级 CLI
    │       └── 版本正常 → 检查凭据
    │
    ├── 检查凭据
    │   ├── 未设置 → 提示用户设置
    │   ├── 已设置但无效 → 提示更新 AK
    │   └── 已设置有效 → 检查网络
    │
    ├── 检查网络
    │   ├── DNS 故障 → 修复 DNS → 重试
    │   ├── 端点不可达 → 检查防火墙 → 重试
    │   └── 网络正常 → 检查 API
    │
    ├── 检查 API 响应
    │   ├── 限流 → 等待重试
    │   ├── 权限不足 → 提供 RAM 策略
    │   └── 参数错误 → 验证参数
    │
    └── 全部检查通过 → 上报未知错误
```

---

## 十、引用

- [Alibaba Cloud CLI 安装文档](https://help.aliyun.com/zh/cli/install-and-configure)
- [Go 下载页面](https://go.dev/dl/)
- [Go Proxy 中国](https://goproxy.cn/)
- [RAM 访问控制文档](https://help.aliyun.com/zh/ram/)