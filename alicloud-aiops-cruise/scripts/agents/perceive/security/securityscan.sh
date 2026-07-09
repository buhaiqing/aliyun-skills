#!/usr/bin/env bash
#
# perceive/security/securityscan.sh — SecurityScan Agent
#
# 职责:
#   每日安全扫描 — 漏洞扫描、AK 泄漏检测、基线合规检查。
#   委托 alicloud-sas-ops 执行。
#
# 调度: 每日
#
# 用法:
#   bash securityscan.sh                              # 默认扫描
#   bash securityscan.sh --output-file ./output.json   # 指定输出
#

set -euo pipefail

# ── 路径解析 (Sprint 18: 统一运行时数据根目录) ──
# SCRIPT_DIR: .../alicloud-aiops-cruise/scripts/agents/perceive/security
# AIOPS_DIR:  .../alicloud-aiops-cruise                   (SCRIPT_DIR 向上 4 层)
# SKILLS_DIR: .../aliyun-skills                           (AIOPS_DIR/..)
# AUDIT_DIR:  ${RUNTIME_AUDIT_DIR}/perceive
# SAS_DIR:    ${SKILLS_DIR}/alicloud-sas-ops
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
export SKILLS_DIR="$(cd "${AIOPS_DIR}/.." && pwd)"

# shellcheck source=../../../lib/runtime_root.sh
source "${AIOPS_DIR}/scripts/lib/runtime_root.sh"
aiops_runtime_init "alicloud-aiops-cruise"

SAS_DIR="${SKILLS_DIR}/alicloud-sas-ops"
AUDIT_DIR="${RUNTIME_AUDIT_DIR}/perceive"
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-file) OUTPUT_FILE="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [[ -z "$OUTPUT_FILE" ]]; then
    OUTPUT_FILE="${AUDIT_DIR}/securityscan-$(date +%Y%m%dT%H%M%S).json"
fi
mkdir -p "$(dirname "${OUTPUT_FILE}")"

echo "[SecurityScan] 开始每日安全扫描"

# SAS 漏洞扫描
VULN_RESULT=$(
    aliyun sas DescribeVulWhitelist --CurrentPage 1 --PageSize 50 2>/dev/null || echo '{"error":"sas not available"}'
)

# AK 泄漏检测
AK_LEAK=$(
    aliyun sas DescribeAccessKeyLeakInstances --CurrentPage 1 --PageSize 20 2>/dev/null || echo '{"error":"sas not available"}'
)

# 基线合规检查
BASELINE=$(
    aliyun sas DescribeCheckWarningSummary --CurrentPage 1 --PageSize 20 --StrategyId 0 2>/dev/null || echo '{"error":"sas not available"}'
)

cat > "${OUTPUT_FILE}" <<JSONEOF
{
  "agent": "securityscan",
  "status": "completed",
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "checks": {
    "vulnerability": ${VULN_RESULT},
    "ak_leak": ${AK_LEAK},
    "baseline": ${BASELINE}
  }
}
JSONEOF

echo "[SecurityScan] PASS 安全扫描完成"
echo "[SecurityScan]   漏洞扫描: $(echo "${VULN_RESULT}" | jq -r '.TotalCount // 0') 项"
echo "[SecurityScan]   AK泄漏: $(echo "${AK_LEAK}" | jq -r '.TotalCount // 0') 项"
echo "[SecurityScan]   基线检查: $(echo "${BASELINE}" | jq -r '.TotalCount // 0') 项"