#!/bin/bash
# check-wrapper.sh — 自动解析 aliyun 命令并走 Runtime Harness Wrapper
#
# 用法:
#   bash scripts/check-wrapper.sh aliyun <product> <action> [params]
#   bash scripts/check-wrapper.sh aliyun r-kvstore DescribeInstances --RegionId cn-hangzhou
#
# 功能:
#   1. 从 aliyun 命令中提取产品名
#   2. 查找对应的 *-harness-wrapper.sh / *-skillopt-wrapper.sh
#   3. 存在 wrapper 则执行 wrapper
#   4. 不存在则 fallback 到原生 aliyun
#
set -eo pipefail

if [[ ${#} -lt 2 ]]; then
    echo "Usage: $0 aliyun <product> <action> [params...]" >&2
    echo "  e.g. $0 aliyun r-kvstore DescribeInstances --RegionId cn-hangzhou" >&2
    exit 1
fi

# 校验第一个参数必须是 "aliyun"
if [[ "$1" != "aliyun" ]]; then
    echo "[WRAPPER] Error: first argument must be 'aliyun', got '$1'" >&2
    exit 1
fi
shift

PRODUCT="$1"
shift

SKILLS_ROOT="${ALIYUN_SKILLS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# 产品名 → skill 目录名映射（POSIX 兼容，不使用 declare -A）
# aliyun CLI 的产品名与仓库目录名可能不同；wrapper 脚本名也可能不同
_product_to_dir() {
    case "$1" in
        r-kvstore) echo "redis" ;;
        bssopenapi) echo "billing" ;;
        cbn) echo "cen" ;;
        *) echo "$1" ;;
    esac
}
_product_to_wrapper() {
    case "$1" in
        eip|nat) echo "vpc" ;;           # EIP/NAT 共享 VPC wrapper
        polardb) echo "polardb-mysql" ;;  # PolarDB for MySQL
        *) echo "$(_product_to_dir "$1")" ;;
    esac
}
SKILL_DIR="$(_product_to_dir "$PRODUCT")"
WRAPPER_NAME="$(_product_to_wrapper "$PRODUCT")"

# 按优先级查找 wrapper
HARNESS_WRAPPER="$SKILLS_ROOT/alicloud-${SKILL_DIR}-ops/scripts/${WRAPPER_NAME}-harness-wrapper.sh"
SKILLOPT_WRAPPER="$SKILLS_ROOT/alicloud-${SKILL_DIR}-ops/scripts/${WRAPPER_NAME}-skillopt-wrapper.sh"

if [[ -f "$HARNESS_WRAPPER" ]]; then
    exec "$HARNESS_WRAPPER" "$@"
elif [[ -f "$SKILLOPT_WRAPPER" ]]; then
    exec "$SKILLOPT_WRAPPER" "$@"
fi

echo "[WRAPPER] Warning: no wrapper found for product '${PRODUCT}' (dir: alicloud-${SKILL_DIR}-ops, wrapper: ${WRAPPER_NAME}), falling back to native aliyun CLI" >&2
exec aliyun "$PRODUCT" "$@"
