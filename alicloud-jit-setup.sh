#!/bin/bash
# alicloud-jit-setup.sh - JIT Go SDK 一键部署（跨平台 macOS/Linux/Windows）
# 用法：./alicloud-jit-setup.sh [product] [operation] [env-file]

set -o pipefail

# ========== 参数处理 ==========
PRODUCT=${1:-ecs}
OPERATION=${2:-DescribeRegions}
ENV_FILE=${3:-.env}
GOPROXY="${GOPROXY:-https://goproxy.cn,direct}"
GO_VERSION="${GO_VERSION:-1.24.0}"

# 全局路径
WORKSPACE="/tmp/aliyun-sdk-workspace-${PRODUCT}"
GO_RUNTIME="/tmp/go-runtime"

# SDK 包名获取函数
get_sdk_package() {
    case "$1" in
        ecs)     echo "github.com/alibabacloud-go/ecs-20140526/v4/client";;
        rds)     echo "github.com/alibabacloud-go/rds-20140815/v2/client";;
        polardb) echo "github.com/alibabacloud-go/polardb-20220530/v3/client";;
        vpc)     echo "github.com/alibabacloud-go/vpc-20160428/v3/client";;
        slb)     echo "github.com/alibabacloud-go/slb-20140515/v4/client";;
        redis)   echo "github.com/alibabacloud-go/r-redis/20150101/client";;
        *)       echo "github.com/alibabacloud-go/$1-00000101/client";;
    esac
}

# ========== 跨平台检测 ==========
detect_platform() {
    KERNEL=$(uname -s 2>/dev/null || echo "unknown")
    ARCH=$(uname -m 2>/dev/null || echo "unknown")
    
    case "${KERNEL}" in
        Darwin)
            PLATFORM="macos"
            GO_OS_ARCH="darwin-${ARCH}"
            ;;
        Linux*)
            PLATFORM="linux"
            GO_OS_ARCH="linux-${ARCH}"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            PLATFORM="windows"
            GO_OS_ARCH="windows-amd64"
            ;;
        *)
            PLATFORM="unknown"
            GO_OS_ARCH=""
            ;;
    esac
    echo "检测到平台: ${PLATFORM} (${KERNEL} ${ARCH})"
}

# ========== 颜色定义 ==========
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_step()  { echo -e "${BLUE}[→]${NC} $1"; }

# ========== Step 1: 检查 aliyun CLI ==========
check_aliyun_cli() {
    log_step "检查 aliyun CLI..."
    if command -v aliyun &> /dev/null; then
        CLI_VERSION=$(aliyun version 2>&1 || echo "未知版本")
        log_info "aliyun CLI 已安装: ${CLI_VERSION}"
        return 0
    fi

    log_warn "aliyun CLI 未安装，开始安装..."
    if command -v brew &> /dev/null; then
        log_info "使用 Homebrew 安装..."
        brew install aliyun-cli 2>/dev/null || true
    else
        log_info "下载官方安装包 (macOS universal)..."
        curl -fsSL https://aliyuncli.alicdn.com/aliyun-cli-macosx-latest-universal.tgz | tar -xz
        mkdir -p ~/.alicloud/bin
        mv -f aliyun ~/.alicloud/bin/ 2>/dev/null || sudo mv aliyun /usr/local/bin/ 2>/dev/null || true
    fi

    if command -v aliyun &> /dev/null; then
        log_info "aliyun CLI 安装成功"
    else
        log_warn "aliyun CLI 安装需要 sudo 权限，请手动执行: sudo mv aliyun /usr/local/bin/"
    fi
}

# ========== Step 2: 安装 Go runtime ==========
setup_go_runtime() {
    log_step "检查 Go runtime..."
    if command -v go &> /dev/null; then
        GO_VERSION=$(go version | awk '{print $3}')
        log_info "Go runtime 已安装: ${GO_VERSION}"
        return 0
    fi

    log_warn "Go runtime 未找到，开始 JIT 安装..."
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    [[ "$ARCH" == "x86_64" ]] && ARCH="amd64"
    [[ "$ARCH" == "aarch64" ]] && ARCH="arm64"

    GO_VERSION="go1.24.0"
    GO_URL="https://go.dev/dl/${GO_VERSION}.${OS}-${ARCH}.tar.gz"

    log_info "下载 ${GO_VERSION} (${OS}-${ARCH}, ~150MB)..."
    mkdir -p ${GO_RUNTIME}
    curl -fsSL "$GO_URL" | tar -xz -C ${GO_RUNTIME}

    export PATH="${GO_RUNTIME}/go/bin:$PATH"
    export GOPATH="/tmp/go-workspace"
    export GOCACHE="/tmp/go-cache"
    export GOMODCACHE="/tmp/go-modcache"

    log_info "Go runtime 安装成功: $(go version)"
}

# ========== Step 3: 配置环境变量 ==========
setup_environment() {
    log_step "配置环境变量..."
    export GOPROXY="${GOPROXY}"
    log_info "Go Module Proxy: ${GOPROXY}"

    # 加载 .env 文件
    if [[ -f "${ENV_FILE}" ]]; then
        log_info "加载 .env 文件: ${ENV_FILE}"
        set -a
        source "${ENV_FILE}"
        set +a
    else
        log_warn ".env 文件不存在: ${ENV_FILE}，使用 shell 环境变量"
    fi

    # 验证凭证
    if [[ -z "$ALIBABA_CLOUD_ACCESS_KEY_ID" || -z "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" ]]; then
        log_error "缺少凭证: ALIBABA_CLOUD_ACCESS_KEY_ID 或 ALIBABA_CLOUD_ACCESS_KEY_SECRET"
        exit 1
    fi

    REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
    log_info "Region: ${REGION}"
    log_info "AK: ${ALIBABA_CLOUD_ACCESS_KEY_ID:0:8}..."
}

# ========== Step 4: 创建 Go workspace ==========
setup_workspace() {
    log_step "创建 Go workspace..."
    mkdir -p "${WORKSPACE}"
    cd "${WORKSPACE}"

    # 初始化 go.mod
    if [[ ! -f go.mod ]]; then
        go mod init "alicloud-${PRODUCT}-ops" 2>/dev/null || true
    fi

    # 获取核心依赖
    log_info "获取核心依赖..."
    go get github.com/joho/godotenv
    go get github.com/alibabacloud-go/darabonba-openapi/v2/client
    go get github.com/alibabacloud-go/tea
    go get github.com/alibabacloud-go/tea-utils/v2/service

    # 获取产品 SDK
    SDK_PACKAGE=$(get_sdk_package "${PRODUCT}")
    log_info "获取 ${PRODUCT} SDK: ${SDK_PACKAGE}"

    go mod tidy

    log_info "Go workspace 创建成功"
}

# ========== Step 5: 生成 Go 脚本 ==========
generate_script() {
    log_step "生成 ${PRODUCT} ${OPERATION} Go 脚本..."

    REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
    SDK_PACKAGE=$(get_sdk_package "${PRODUCT}")

    # 从 SDK 包路径提取产品别名（如 ecs-20140526 -> ecs）
    PRODUCT_ALIAS=$(echo "$SDK_PACKAGE" | sed 's|.*/\([a-z]*\)-[0-9]*/.*|\1|')

    cd "${WORKSPACE}"

    cat > main.go << GOEOF
package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/joho/godotenv"
	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	productClient "${SDK_PACKAGE}"
)

func main() {
	_ = godotenv.Load()

	ak := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
	sk := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
	region := os.Getenv("ALIBABA_CLOUD_REGION_ID")

	if ak == "" || sk == "" {
		fmt.Println("错误: 缺少 Alibaba Cloud 凭证")
		os.Exit(1)
	}
	if region == "" {
		region = "cn-hangzhou"
	}

	config := &openapi.Config{
		AccessKeyId:     tea.String(ak),
		AccessKeySecret: tea.String(sk),
		Endpoint:        tea.String("${PRODUCT_ALIAS}." + region + ".aliyuncs.com"),
	}

	client, err := productClient.NewClient(config)
	if err != nil {
		fmt.Printf("错误: SDK 客户端初始化失败: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Region: %s  Product: ${PRODUCT_ALIAS}\n", region)
	request := &productClient.${OPERATION}Request{}

	response, err := client.${OPERATION}(request)
	if err != nil {
		fmt.Printf("错误: API 调用失败: %v\n", err)
		os.Exit(1)
	}

	out, _ := json.MarshalIndent(response, "", "  ")
	fmt.Println(string(out))
}
GOEOF

    go mod tidy
    log_info "脚本已生成: ${WORKSPACE}/main.go"
}

# ========== Step 6: 执行验证 ==========
run_verification() {
    log_step "执行 ${PRODUCT} ${OPERATION} 验证..."
    cd "${WORKSPACE}"
    go run main.go
}

# ========== 主流程 ==========
main() {
    detect_platform
    echo
    echo "========================================"
    echo "  阿里云 JIT Go SDK 环境一键部署"
    echo "========================================"
    echo
    echo "产品:    ${PRODUCT}"
    echo "操作:    ${OPERATION}"
    echo "环境文件: ${ENV_FILE}"
    echo

    check_aliyun_cli
    echo
    setup_go_runtime
    echo
    setup_environment
    echo
    setup_workspace
    echo
    generate_script
    echo
    run_verification || {
        log_warn "API 调用失败，但环境已就绪"
        log_info "可手动执行: cd ${WORKSPACE} && go run main.go"
    }

    echo
    echo "========================================"
    log_info "JIT Go SDK 环境部署完成!"
    log_info "Workspace: ${WORKSPACE}"
    echo "========================================"
}

main "$@"
