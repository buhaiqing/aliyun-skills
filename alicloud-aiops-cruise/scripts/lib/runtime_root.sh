#!/usr/bin/env bash
#
# scripts/lib/runtime_root.sh — 运行时数据根目录解析 (Sprint 18)
#
# 用法 (在调用脚本顶部 source):
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   source "${SCRIPT_DIR}/../lib/runtime_root.sh"   # 调整路径
#   aiops_runtime_init "alicloud-aiops-cruise"      # 初始化 RUNTIME_ROOT + 子目录
#
# 输出 (环境变量):
#   RUNTIME_ROOT                - 根目录 (env 覆盖或默认 .runtime/)
#   RUNTIME_BASELINE_DIR        - baseline 子目录
#   RUNTIME_AUDIT_DIR_<SKILL>   - audit 子目录
#   RUNTIME_CACHE_DIR           - 缓存子目录
#   RUNTIME_LOGS_DIR_<SKILL>    - 日志子目录
#   RUNTIME_TMP_DIR             - 临时子目录
#
# 优先级:
#   1. 环境变量 ALIYUN_SKILLS_RUNTIME_ROOT
#   2. ${SKILLS_DIR}/.runtime (默认)
#
# 跨平台: macOS/Linux 都支持; Windows 用户需用 WSL 或手动指定 RUNTIME_ROOT

set -euo pipefail

# ── 解析 RUNTIME_ROOT ──
aiops_runtime_resolve_root() {
    if [[ -n "${ALIYUN_SKILLS_RUNTIME_ROOT:-}" ]]; then
        echo "${ALIYUN_SKILLS_RUNTIME_ROOT}"
    elif [[ -n "${SKILLS_DIR:-}" ]]; then
        # 优先使用调用方 export 的 SKILLS_DIR
        # 这是推荐用法: 调用方知道自己的位置, 不依赖 lib 推断
        echo "${SKILLS_DIR}/.runtime"
    else
        # fallback: 用本 lib 自身位置推断 (skill 内部 .runtime)
        # 仅作最后兜底, 不推荐依赖
        local lib_dir
        lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        local skill_dir
        skill_dir="$(cd "${lib_dir}/../.." && pwd)"
        echo "${skill_dir}/.runtime"
    fi
}

# ── 初始化 (创建子目录) ──
# 用法: aiops_runtime_init <skill_short_name>
# 例:   aiops_runtime_init "alicloud-aiops-cruise"
aiops_runtime_init() {
    local skill_short="${1:-shared}"

    RUNTIME_ROOT="$(aiops_runtime_resolve_root)"

    # 兼容: skill_short 可能是 "alicloud-aiops-cruise" 或 "aiops-cruise"
    # 统一去掉 "alicloud-" 前缀
    local skill_key="${skill_short#alicloud-}"

    RUNTIME_BASELINE_DIR="${RUNTIME_ROOT}/baseline"
    RUNTIME_AUDIT_DIR="${RUNTIME_ROOT}/audit/${skill_key}"
    RUNTIME_CACHE_DIR="${RUNTIME_ROOT}/cache"
    RUNTIME_LOGS_DIR="${RUNTIME_ROOT}/logs/${skill_key}"
    RUNTIME_TMP_DIR="${RUNTIME_ROOT}/tmp"

    export RUNTIME_ROOT RUNTIME_BASELINE_DIR RUNTIME_AUDIT_DIR \
           RUNTIME_CACHE_DIR RUNTIME_LOGS_DIR RUNTIME_TMP_DIR

    # 创建子目录 (idempotent)
    mkdir -p "${RUNTIME_BASELINE_DIR}" \
             "${RUNTIME_AUDIT_DIR}" \
             "${RUNTIME_CACHE_DIR}" \
             "${RUNTIME_LOGS_DIR}" \
             "${RUNTIME_TMP_DIR}"
}

# ── 帮助函数 ──
aiops_runtime_help() {
    cat <<'EOF'
runtime_root.sh — 运行时数据根目录解析 (Sprint 18)

环境变量:
  ALIYUN_SKILLS_RUNTIME_ROOT  覆盖根目录 (默认: ${SKILLS_DIR}/.runtime)

子目录结构:
  .runtime/
  ├── baseline/   - 拓扑基线 (Sprint 16/17 用)
  ├── audit/<skill>/  - 巡检 / GCL 报告
  ├── cache/      - 跨 runbook 缓存
  ├── logs/<skill>/   - 运行日志
  └── tmp/        - 进程级临时

用法:
  source scripts/lib/runtime_root.sh
  aiops_runtime_init "alicloud-aiops-cruise"
  echo "RUNTIME_AUDIT_DIR=${RUNTIME_AUDIT_DIR}"
EOF
}

# 如果直接执行本脚本 (非 source), 打印帮助
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-}" in
        -h|--help|help|"") aiops_runtime_help ;;
        *) aiops_runtime_init "$@" ;;
    esac
fi
