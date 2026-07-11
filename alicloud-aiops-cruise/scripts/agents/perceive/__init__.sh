#!/usr/bin/env bash
#
# perceive/__init__.sh — 感知层统一入口
#
# 职责:
#   作为 7 个感知 Agent 的调度入口，支持按子集执行。
#   接收 cron/Orchestrator 触发，分发到对应子 Agent。
#
# 用法:
#   bash __init__.sh                          # 执行全部感知 Agent
#   bash __init__.sh --mode infra             # 仅基础设施巡检
#   bash __init__.sh --mode cost              # 仅成本监察
#   bash __init__.sh --mode security          # 仅安全监控
#   bash __init__.sh --mode advisor           # 仅顾问检查
#   bash __init__.sh --mode healthcruise      # 仅全链路巡检
#   bash __init__.sh --describe               # 描述结构
#   bash __init__.sh --output-dir ./reports   # 指定报告输出目录
#   bash __init__.sh --fusion                  # 执行后自动融合报告
#
# 输出:
#   JSON 报告持久化到 output-dir/perceive-{timestamp}.json
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 加载共享 lib (Sprint 18: 运行时数据根目录) ──
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"  # agents/perceive/ -> scripts/agents/perceive/ -> scripts/agents/ -> scripts/ -> alicloud-aiops-cruise
# 显式 export SKILLS_DIR (alibaba-aiops-cruise/.. = aliyun-skills), 避免 lib 内部 BASH_SOURCE 推断歧义
export SKILLS_DIR="$(cd "${AIOPS_DIR}/.." && pwd)"
# shellcheck source=../../lib/runtime_root.sh
source "${AIOPS_DIR}/scripts/lib/runtime_root.sh"
aiops_runtime_init "alicloud-aiops-cruise"

REPORTS_DIR="${RUNTIME_AUDIT_DIR}/perceive"  # 修复 BUF-003: 原 ${SCRIPT_DIR}/../../../audit-results 少走一层
OUTPUT_DIR=""
MODE="all"
DESCRIBE=false
FUSION=false

# ── 解析参数 ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode) MODE="$2"; shift 2 ;;
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --describe) DESCRIBE=true; shift ;;
        --fusion) FUSION=true; shift ;;
        *) echo "[ERROR] 未知参数: $1"; exit 2 ;;
    esac
done

# ── 描述模式 ──
if $DESCRIBE; then
    cat <<'STRUCTURE'
Perceive Layer — 感知 Agent (7个)
===================================

位于: scripts/agents/perceive/
├── __init__.sh         # 统一入口 (本文件)
├── infra/              # 基础设施巡检 (AIOps 核心链路)
│   ├── healthcruise.sh # 全链路巡检 EIP->SLB->ECS->RDS/Redis->NAT->安全组 | 每6h
│   ├── toposcan.sh     # 拓扑发现 VPC/ECS/RDS/SLB 资源清单              | 每日/按需
│   └── configdrift.sh  # 配置漂移检测 对比 Topo baseline               | 按需
├── cost/               # 成本监察
│   └── costwatch.sh    # 费用异常检测/到期预警/RI覆盖率/预算跟踪        | 每日
├── security/           # 安全监控
│   ├── securityscan.sh # 漏洞扫描/AK泄漏检测/基线合规检查               | 每日
│   └── audittrail.sh   # 操作事件监控/异常 API 调用检测                  | 实时/每日
└── advisor/            # 顾问建议
    └── advisorscan.sh  # 健康报告 + 成本优化建议                         | 每日

调度周期:
  infra/*     -> 每 6h (高频)
  cost/*      -> 每日
  security/*  -> 每日
  advisor/*   -> 每日
STRUCTURE
    exit 0
fi

# ── 输出目录 ──
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="${REPORTS_DIR}/perceive-$(date +%Y%m%dT%H%M%S)"
fi
mkdir -p "$OUTPUT_DIR"

# ── 运行单个子 Agent ──
run_agent() {
    local agent_script="$1"
    local agent_name="$2"
    local output_file="${OUTPUT_DIR}/${agent_name}.json"

    echo "[$(date '+%H:%M:%S')] ▶ ${agent_name}..."

    if [[ ! -f "$agent_script" ]]; then
        echo "  [WARN]  脚本不存在: ${agent_script}"
        echo '{"agent":"'"${agent_name}"'","status":"skipped","reason":"script not found"}' > "$output_file"
        return 0
    fi

    bash "$agent_script" --output-file "$output_file" 2>&1 | sed 's/^/  /'
    local rc=${PIPESTATUS[0]}

    if [[ $rc -eq 0 ]]; then
        echo "  PASS ${agent_name} 完成"
    else
        echo "  FAIL ${agent_name} 失败 (exit=$rc)"
    fi
    return $rc
}

# ── 分发执行 ──
echo "=========================================="
echo "  Perceive Agent — 感知层"
echo "  模式: ${MODE}"
echo "  输出: ${OUTPUT_DIR}"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

declare -a AGENTS=()

case "$MODE" in
    all)
        AGENTS=(
            "infra/healthcruise.sh:healthcruise"
            "infra/toposcan.sh:toposcan"
            "infra/configdrift.sh:configdrift"
            "cost/costwatch.sh:costwatch"
            "security/securityscan.sh:securityscan"
            "security/audittrail.sh:audittrail"
            "advisor/advisorscan.sh:advisorscan"
        )
        ;;
    infra)
        AGENTS=(
            "infra/healthcruise.sh:healthcruise"
            "infra/toposcan.sh:toposcan"
            "infra/configdrift.sh:configdrift"
        )
        ;;
    cost)
        AGENTS=("cost/costwatch.sh:costwatch")
        ;;
    security)
        AGENTS=(
            "security/securityscan.sh:securityscan"
            "security/audittrail.sh:audittrail"
        )
        ;;
    advisor)
        AGENTS=("advisor/advisorscan.sh:advisorscan")
        ;;
    healthcruise|toposcan|configdrift|costwatch|securityscan|audittrail|advisorscan)
        # 修复 BUG-003: 单 agent 模式按 agent 所在的子目录分类 (修复原假设 ${MODE}/${MODE}.sh)
        # set +u 临时关闭 unset 检查, 避免关联数组在 case 分支内的边界问题
        set +u
        category="infra"  # default
        case "${MODE}" in
            healthcruise|toposcan|configdrift) category="infra" ;;
            costwatch)                          category="cost" ;;
            securityscan|audittrail)            category="security" ;;
            advisorscan)                        category="advisor" ;;
        esac
        set -u
        AGENTS=("${category}/${MODE}.sh:${MODE}")
        ;;
    *)
        echo "[ERROR] 未知模式: ${MODE}"
        echo "可用模式: all, infra, cost, security, advisor, healthcruise, toposcan, configdrift, costwatch, securityscan, audittrail, advisorscan"
        exit 2
        ;;
esac

# 并行执行基础设施巡检（互不依赖）
if [[ "$MODE" == "all" || "$MODE" == "infra" ]]; then
    echo "▶ 并行执行基础设施巡检..."
    pids=()
    run_agent "${SCRIPT_DIR}/infra/healthcruise.sh" "healthcruise" &
    pids+=($!)
    run_agent "${SCRIPT_DIR}/infra/toposcan.sh" "toposcan" &
    pids+=($!)
    wait "${pids[@]}"
    wait "${pids[@]}" 2>/dev/null || true
    # configdrift 依赖 toposcan 输出，串行
    run_agent "${SCRIPT_DIR}/infra/configdrift.sh" "configdrift"
fi

# 串行其他领域（各自独立）
for agent_entry in "${AGENTS[@]}"; do
    agent_script="${SCRIPT_DIR}/${agent_entry%%:*}"
    agent_name="${agent_entry##*:}"
    # 跳过已在 infra 并行块中执行过的
    case "$agent_name" in
        healthcruise|toposcan|configdrift)
            [[ "$MODE" == "all" || "$MODE" == "infra" ]] && continue
            ;;
    esac
    run_agent "$agent_script" "$agent_name"
done

# ── 生成汇总索引 ──
{
    echo "{"
    echo "  \"pipeline\": \"perceive\","
    echo "  \"timestamp\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\","
    echo "  \"mode\": \"${MODE}\","
    echo "  \"agents\": ["
    first=true
    for entry in "${AGENTS[@]}"; do
        agent_name="${entry##*:}"
        json_file="${OUTPUT_DIR}/${agent_name}.json"
        if [[ -f "$json_file" ]]; then
            $first || echo ","
            first=false
            echo -n "    $(cat "$json_file")"
        fi
    done
    echo ""
    echo "  ]"
    echo "}"
} > "${OUTPUT_DIR}/perceive-summary.json"

echo ""
echo "=========================================="
echo "  感知层执行完成"
echo "  摘要: ${OUTPUT_DIR}/perceive-summary.json"
echo "=========================================="

# ── 融合报告 (C1) ──
if $FUSION; then
    FUSION_SCRIPT="${SCRIPT_DIR}/../fusion/fusion_report.sh"
    if [[ -f "$FUSION_SCRIPT" ]]; then
        echo ""
        echo "=========================================="
        echo "  融合报告 (--fusion)"
        echo "=========================================="
        bash "$FUSION_SCRIPT" --input-dir "${OUTPUT_DIR}"
    else
        echo "[WARN] 融合报告脚本不存在: ${FUSION_SCRIPT}"
    fi
fi
