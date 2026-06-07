#!/usr/bin/env bash
#
# perceive/cost/costwatch.sh — CostWatch Agent
#
# 职责:
#   每日成本监控 — 费用异常检测、资源到期预警、RI/SP 覆盖率、预算跟踪。
#   委托 aiops-cruise runbooks/scripts/cost-watch.py 执行。
#
# 调度: 每日
#
# 用法:
#   bash costwatch.sh                                        # 全部检查
#   bash costwatch.sh --budget 50000                         # 自定义预算
#   bash costwatch.sh --anomaly-only                         # 仅异常检测
#   bash costwatch.sh --output-file ./output.json             # 指定输出
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
RUNBOOKS_DIR="${AIOPS_DIR}/runbooks/scripts"
AUDIT_DIR="${AIOPS_DIR}/audit-results"
OUTPUT_FILE=""
BUDGET=""
ANOMALY_ONLY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-file) OUTPUT_FILE="$2"; shift 2 ;;
        --budget) BUDGET="$2"; shift 2 ;;
        --anomaly-only) ANOMALY_ONLY=true; shift ;;
        *) shift ;;
    esac
done

if [[ -z "$OUTPUT_FILE" ]]; then
    OUTPUT_FILE="${AUDIT_DIR}/costwatch-$(date +%Y%m%dT%H%M%S).json"
fi

echo "[CostWatch] 开始每日成本监控"

COST_ARGS=()
[[ -n "$BUDGET" ]] && COST_ARGS+=(--budget "${BUDGET}")
$ANOMALY_ONLY && COST_ARGS+=(--anomaly-only)
COST_ARGS+=(--output-dir "$(dirname "${OUTPUT_FILE}")")

python3 "${RUNBOOKS_DIR}/cost-watch.py" "${COST_ARGS[@]}" 2>&1

rc=$?
if [[ $rc -eq 0 ]]; then
    echo "[CostWatch] ✅ 成本监控完成"
    echo '{"agent":"costwatch","status":"completed","timestamp":"'"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"'"}' > "${OUTPUT_FILE}"
else
    echo "[CostWatch] ❌ 成本监控失败 (exit=$rc)"
    echo '{"agent":"costwatch","status":"failed","exit_code":'"${rc}"',"timestamp":"'"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"'"}' > "${OUTPUT_FILE}"
    exit $rc
fi