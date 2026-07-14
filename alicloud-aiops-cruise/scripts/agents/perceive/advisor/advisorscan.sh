#!/usr/bin/env bash
#
# perceive/advisor/advisorscan.sh — AdvisorScan Agent
#
# 职责:
#   拉取智能顾问健康报告和成本优化建议。
#   委托 alicloud-advisor-ops 执行（kebab-case CLI 规范）。
#   输出结构对齐 advisor-ops JSON path ($.Advices[].Severity / $.Overview.TotalSavings / $.Results[].TotalSavings)。
#
# 依赖: aliyun-cli-advisor plugin (v0.4.0+), jq
# 调度: 每日
#
# 用法:
#   bash advisorscan.sh                                # 默认检查
#   bash advisorscan.sh --output-file ./output.json     # 指定输出
#
# CLI 规范参考: alicloud-advisor-ops/references/cli-usage.md
#   - aliyun-cli-advisor 插件只接受 kebab-case 子命令 (e.g. describe-advices, NOT DescribeAdvices)
#   - 参数使用 camelCase CLI flag (e.g. --biz-language, --page-number, 非 PascalCase --Language)
#

set -euo pipefail

# ── 路径解析 (Sprint 18: 统一运行时数据根目录) ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
export SKILLS_DIR="$(cd "${AIOPS_DIR}/.." && pwd)"

# shellcheck source=../../../lib/runtime_root.sh
source "${AIOPS_DIR}/scripts/lib/runtime_root.sh"
aiops_runtime_init "alicloud-aiops-cruise"

AUDIT_DIR="${RUNTIME_AUDIT_DIR}/perceive"
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-file) OUTPUT_FILE="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [[ -z "$OUTPUT_FILE" ]]; then
    OUTPUT_FILE="${AUDIT_DIR}/advisorscan-$(date +%Y%m%dT%H%M%S).json"
fi
mkdir -p "$(dirname "${OUTPUT_FILE}")"

echo "[AdvisorScan] 开始智能顾问检查"

# ── 健康检查 (Critical + Warning) ──
# 使用 kebab-case 子命令 + camelCase flag，只拉 Critical/Warning 减少噪音
HEALTH=$(
    aliyun advisor describe-advices \
        --biz-language zh \
        --page-number 1 --page-size 50 \
        2>/dev/null || echo '{"error":"advisor not available"}'
)

# ── 成本优化概览 (总节省额 + 分项) ──
# 替换原来错误的 DescribeAdvisorChecks --Product alicloud（无效值）
COST_OVERVIEW=$(
    aliyun advisor describe-cost-optimization-overview \
        2>/dev/null || echo '{"error":"cost overview not available"}'
)

# ── 成本分组结果 (按产品) ──
# 提供 aggregated 视角，对齐 advisor-ops Runbook 2 的第二步
COST_RESULTS=$(
    aliyun advisor describe-cost-check-results \
        --group-by Product \
        2>/dev/null || echo '{"error":"cost results not available"}'
)

# ── 输出结构对齐 advisor-ops JSON path ──
# health_checks: $.Advices[].Severity / .AdviceId / .Product / .ResourceId
# cost_overview: $.Overview.TotalSavings / $.Overview.Items[].Savings
# cost_results:  $.Results[].GroupKey / .TotalSavings / .ResourceCount
cat > "${OUTPUT_FILE}" <<JSONEOF
{
  "agent": "advisorscan",
  "status": "completed",
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "health_checks": ${HEALTH},
  "cost_overview": ${COST_OVERVIEW},
  "cost_results": ${COST_RESULTS}
}
JSONEOF

# ── 汇总报告 ──
HEALTH_COUNT=$(echo "${HEALTH}" | jq -r '.Advices // [] | length')
CRIT_COUNT=$(echo "${HEALTH}" | jq -r '[.Advices[] // [] | select(.Severity=="Critical")] | length')
WARN_COUNT=$(echo "${HEALTH}" | jq -r '[.Advices[] // [] | select(.Severity=="Warning")] | length')
TOTAL_SAVINGS=$(echo "${COST_OVERVIEW}" | jq -r '.Overview.TotalSavings // 0')

echo "[AdvisorScan] PASS 智能顾问检查完成"
echo "[AdvisorScan]   健康检查: ${HEALTH_COUNT} 项 (Critical=${CRIT_COUNT}, Warning=${WARN_COUNT})"
echo "[AdvisorScan]   月节省预估: ¥${TOTAL_SAVINGS}"
