#!/usr/bin/env bash
#
# perceive/infra/toposcan.sh — TopoScan Agent
#
# 职责:
#   扫描 VPC/ECS/RDS/SLB 等资源，生成拓扑图 + 资源清单。
#   委托 alicloud-topo-discovery/scripts/topo-scan.sh 执行。
#
# 调度: 每日 / 按需
#
# 用法:
#   bash toposcan.sh                                    # 默认扫描
#   bash toposcan.sh --resource-group-id rg-xxx         # 指定资源组
#   bash toposcan.sh --output-file ./output.json         # 指定输出
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../../../" && pwd)"
SKILLS_DIR="$(cd "${AIOPS_DIR}/../../" && pwd)"
TOPO_DIR="${SKILLS_DIR}/alicloud-topo-discovery/scripts"
AUDIT_DIR="${AIOPS_DIR}/audit-results"
OUTPUT_FILE=""
RESOURCE_GROUP_ID=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-file) OUTPUT_FILE="$2"; shift 2 ;;
        --resource-group-id) RESOURCE_GROUP_ID="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [[ -z "$OUTPUT_FILE" ]]; then
    OUTPUT_FILE="${AUDIT_DIR}/toposcan-$(date +%Y%m%dT%H%M%S).json"
fi

echo "[TopoScan] 开始拓扑发现: resource_group=${RESOURCE_GROUP_ID:-全部}"

if [[ -f "${TOPO_DIR}/topo-scan.sh" ]]; then
    bash "${TOPO_DIR}/topo-scan.sh" \
        ${RESOURCE_GROUP_ID:+--resource-group-id "${RESOURCE_GROUP_ID}"} \
        --output-file "${OUTPUT_FILE}" 2>&1 | sed 's/^/  /'

    rc=${PIPESTATUS[0]}
    if [[ $rc -eq 0 ]]; then
        echo "[TopoScan] ✅ 拓扑发现完成"
        echo '{"agent":"toposcan","status":"completed","timestamp":"'"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"'","resources":[]}' > "${OUTPUT_FILE}"
    else
        echo "[TopoScan] ❌ 拓扑发现失败 (exit=$rc)"
        echo '{"agent":"toposcan","status":"failed","exit_code":'"${rc}"',"timestamp":"'"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"'"}' > "${OUTPUT_FILE}"
        exit $rc
    fi
else
    echo "[TopoScan] ⚠️  topo-discovery 尚未安装，跳过"
    echo '{"agent":"toposcan","status":"skipped","reason":"topo-discovery not installed","timestamp":"'"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"'"}' > "${OUTPUT_FILE}"
fi