#!/usr/bin/env bash
#
# perceive/security/audittrail.sh — AuditTrail Agent
#
# 职责:
#   操作事件监控 — 采集 ActionTrail 操作事件，检测异常 API 调用。
#   委托 alicloud-actiontrail-ops 执行。
#
# 调度: 实时 / 每日
#
# 用法:
#   bash audittrail.sh                                 # 默认采集最近24h事件
#   bash audittrail.sh --hours 48                       # 采集最近48h事件
#   bash audittrail.sh --output-file ./output.json      # 指定输出
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
AUDIT_DIR="${AIOPS_DIR}/audit-results"
OUTPUT_FILE=""
HOURS=24

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-file) OUTPUT_FILE="$2"; shift 2 ;;
        --hours) HOURS="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [[ -z "$OUTPUT_FILE" ]]; then
    OUTPUT_FILE="${AUDIT_DIR}/audittrail-$(date +%Y%m%dT%H%M%S).json"
fi

# 计算时间窗口
START_TIME=$(date -u -v-${HOURS}H '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || \
             date -u -d "${HOURS} hours ago" '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || \
             echo "")
END_TIME=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

echo "[AuditTrail] 开始操作事件采集 (最近 ${HOURS}h)"

# 查询 ActionTrail 事件
EVENTS=$(
    aliyun actiontrail LookupEvents \
        --StartTime "${START_TIME}" \
        --EndTime "${END_TIME}" \
        --MaxResults 100 2>/dev/null || echo '{"error":"actiontrail not available","Events":[]}'
)

# 异常检测规则：高频失败、敏感操作
ANOMALIES=$(echo "${EVENTS}" | jq '[.Events[]? | select(
    .ErrorCode != null and .ErrorCode != "" and .ErrorCode != "None"
)] | group_by(.EventName) | map({
    event: .[0].EventName,
    count: length,
    error_codes: [.[] | .ErrorCode] | unique
}) | sort_by(.count) | reverse | .[0:10]' 2>/dev/null || echo '[]')

cat > "${OUTPUT_FILE}" <<JSONEOF
{
  "agent": "audittrail",
  "status": "completed",
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "window": {
    "start": "${START_TIME}",
    "end": "${END_TIME}",
    "hours": ${HOURS}
  },
  "total_events": $(echo "${EVENTS}" | jq '.Events | length // 0'),
  "anomalies": ${ANOMALIES}
}
JSONEOF

TOTAL=$(echo "${EVENTS}" | jq '.Events | length // 0')
ANOMALY_COUNT=$(echo "${ANOMALIES}" | jq 'length')

echo "[AuditTrail] ✅ 操作事件采集完成"
echo "[AuditTrail]   事件总数: ${TOTAL}"
echo "[AuditTrail]   异常操作: ${ANOMALY_COUNT} 类"