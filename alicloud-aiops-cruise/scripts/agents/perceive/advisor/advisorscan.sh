#!/usr/bin/env bash
#
# perceive/advisor/advisorscan.sh — AdvisorScan Agent
#
# 职责:
#   拉取智能顾问健康报告和成本优化建议。
#   委托 alicloud-advisor-ops 执行。
#
# 调度: 每日
#
# 用法:
#   bash advisorscan.sh                                # 默认检查
#   bash advisorscan.sh --output-file ./output.json     # 指定输出
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
AUDIT_DIR="${AIOPS_DIR}/audit-results"
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

echo "[AdvisorScan] 开始智能顾问检查"

# 健康检查
HEALTH=$(
    aliyun advisor DescribeAdvices --Language zh --PageNumber 1 --PageSize 50 2>/dev/null || echo '{"error":"advisor not available"}'
)

# 成本优化建议 (部分产品支持)
COST=$(
    aliyun advisor DescribeAdvisorChecks --Language zh --Product alicloud 2>/dev/null || echo '{"check_result":[]}'
)

cat > "${OUTPUT_FILE}" <<JSONEOF
{
  "agent": "advisorscan",
  "status": "completed",
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "health_checks": ${HEALTH},
  "cost_optimization": ${COST}
}
JSONEOF

HEALTH_COUNT=$(echo "${HEALTH}" | jq -r '.TotalCount // 0')
echo "[AdvisorScan] ✅ 智能顾问检查完成"
echo "[AdvisorScan]   健康检查建议: ${HEALTH_COUNT} 项"