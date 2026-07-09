#!/usr/bin/env bash
#
# perceive/infra/healthcruise.sh — HealthCruise Agent
#
# 职责:
#   全链路健康巡检 — 从 EIP->SLB->ECS->RDS/Redis->NAT->安全组逐跳检查。
#   委托 aiops-cruise runbooks/scripts/daily-health-check.py 执行。
#
# 调度: 每 6h
#
# 用法:
#   bash healthcruise.sh                                  # 默认巡检
#   bash healthcruise.sh --customer demo                  # 指定客户
#   bash healthcruise.sh --output-file ./output.json       # 指定输出
#

set -euo pipefail

# ── 路径解析 (Sprint 18: 统一运行时数据根目录) ──
# SCRIPT_DIR: .../alicloud-aiops-cruise/scripts/agents/perceive/infra
# AIOPS_DIR:  .../alicloud-aiops-cruise                   (SCRIPT_DIR 向上 4 层)
# SKILLS_DIR: .../aliyun-skills                           (AIOPS_DIR/..)
# AUDIT_DIR:  ${RUNTIME_AUDIT_DIR}/perceive
# RUNBOOKS_DIR: ${AIOPS_DIR}/runbooks/scripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
export SKILLS_DIR="$(cd "${AIOPS_DIR}/.." && pwd)"

# shellcheck source=../../../lib/runtime_root.sh
source "${AIOPS_DIR}/scripts/lib/runtime_root.sh"
aiops_runtime_init "alicloud-aiops-cruise"

RUNBOOKS_DIR="${AIOPS_DIR}/runbooks/scripts"
AUDIT_DIR="${RUNTIME_AUDIT_DIR}/perceive"
OUTPUT_FILE=""
CUSTOMER="${ALIBABA_CLOUD_ACCOUNT_ID:-unknown}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-file) OUTPUT_FILE="$2"; shift 2 ;;
        --customer) CUSTOMER="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [[ -z "$OUTPUT_FILE" ]]; then
    OUTPUT_FILE="${AUDIT_DIR}/healthcruise-$(date +%Y%m%dT%H%M%S).json"
fi
mkdir -p "$(dirname "${OUTPUT_FILE}")"

echo "[HealthCruise] 开始全链路巡检: customer=${CUSTOMER}"

python3 "${RUNBOOKS_DIR}/daily-health-check.py" \
    --customer "${CUSTOMER}" \
    --output-dir "$(dirname "${OUTPUT_FILE}")" \
    --non-interactive 2>&1

rc=$?
if [[ $rc -eq 0 ]]; then
    echo "[HealthCruise] PASS 巡检完成"
    echo '{"agent":"healthcruise","status":"completed","timestamp":"'"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"'","customer":"'"${CUSTOMER}"'"}' > "${OUTPUT_FILE}"
else
    echo "[HealthCruise] FAIL 巡检失败 (exit=$rc)"
    echo '{"agent":"healthcruise","status":"failed","exit_code":'"${rc}"',"timestamp":"'"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"'"}' > "${OUTPUT_FILE}"
    exit $rc
fi