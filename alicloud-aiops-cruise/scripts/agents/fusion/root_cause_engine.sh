#!/usr/bin/env bash
#
# fusion/root_cause_engine.sh -- C2 跨维度根因推理引擎
#
# 职责:
#   读取 fusion report JSON + correlation-rules.json, 匹配跨域关联规则,
#   输出根因分析结果.
#
# 用法:
#   bash root_cause_engine.sh --report <fusion-report.json>
#
# 输出:
#   root-cause-{timestamp}.json 到输出目录 / STDOUT
#
# 依赖:
#   - Bash 4+ (关联数组支持)
#   - jq (JSON 解析)

set -euo pipefail

# 全局 jq 自定义函数: severity 数值映射
JQ_SEVERITY_FN='def severity_level: {"CRITICAL":4, "HIGH":3, "MEDIUM":2, "LOW":1}[. // "LOW"] // 0;'

# ── 路径解析 ──
# SCRIPT_DIR: .../alicloud-aiops-cruise/scripts/agents/fusion
# AIOPS_DIR:  .../alicloud-aiops-cruise               (SCRIPT_DIR 向上 3 层)
# SKILLS_DIR: .../aliyun-skills                        (AIOPS_DIR/..)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
export SKILLS_DIR="$(cd "${AIOPS_DIR}/.." && pwd)"

# shellcheck source=../../../../scripts/lib/runtime_root.sh
source "${AIOPS_DIR}/scripts/lib/runtime_root.sh"
aiops_runtime_init "alicloud-aiops-cruise"

AUDIT_DIR="${RUNTIME_AUDIT_DIR}/fusion"
mkdir -p "${AUDIT_DIR}"

# ── 默认路径 ──
DEFAULT_RULES="${SCRIPT_DIR}/correlation-rules.json"
RULES_FILE="${DEFAULT_RULES}"
REPORT_FILE=""
OUTPUT_FILE=""

# ── severity 数值映射 (用于比较) ──
severity_level() {
    local val
    val="$(echo "$1" | tr '[:lower:]' '[:upper:]')"
    case "$val" in
        CRITICAL) echo 4 ;;
        HIGH)     echo 3 ;;
        MEDIUM)   echo 2 ;;
        LOW)      echo 1 ;;
        *)        echo 0 ;;
    esac
}

# ── 参数解析 ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --report)      REPORT_FILE="$2";    shift 2 ;;
        --rules)       RULES_FILE="$2";     shift 2 ;;
        --output-file) OUTPUT_FILE="$2";    shift 2 ;;
        --output-dir)  AUDIT_DIR="$2";      shift 2 ;;
        *) echo "[ERROR] 未知参数: $1"; exit 2 ;;
    esac
done

# ── 验证 ──
if [[ -z "$REPORT_FILE" ]]; then
    echo "[ERROR] --report <fusion-report.json> 必填"
    exit 2
fi

if [[ ! -f "$REPORT_FILE" ]]; then
    echo "[ERROR] 报告文件不存在: ${REPORT_FILE}"
    exit 2
fi

if [[ ! -f "$RULES_FILE" ]]; then
    echo "[ERROR] 规则文件不存在: ${RULES_FILE}"
    # ponytail: single lookup path, add --rules-dir when multi-tenancy arrives
    exit 2
fi

# 验证 JSON 格式
if ! jq empty "${RULES_FILE}" 2>/dev/null; then
    echo "[ERROR] 规则文件 JSON 格式无效: ${RULES_FILE}"
    exit 2
fi
if ! jq empty "${REPORT_FILE}" 2>/dev/null; then
    echo "[ERROR] 报告文件 JSON 格式无效: ${REPORT_FILE}"
    exit 2
fi

# 规则计数 (仅在 reload 时输出)
RULE_COUNT="$(jq '.rules | length' "${RULES_FILE}")"

# ── 读取 findings (兼容多种结构) ──
# 格式1: {"findings": [...]}
# 格式2: {"checks": {"name": {..., "findings": [...]}}}
# 格式3: 扁平 {"domain": ..., "severity": ..., "message": ...} (单条)
FINDINGS_JSON="$(jq '
    if .findings then
        .findings
    elif .checks then
        [.checks[] | select(.findings) | .findings[]] // [.checks[] | {domain: "unknown", severity: "LOW", message: (. // "no detail")}]
    elif .domain then
        [.]
    else
        [{"domain": "unknown", "severity": "LOW", "message": "no structured findings"}]
    end
' "${REPORT_FILE}" 2>/dev/null)" || {
    echo "[ERROR] 无法解析报告中的 findings"
    exit 2
}

FINDING_COUNT="$(echo "${FINDINGS_JSON}" | jq 'length')"
echo "[RootCause] 解析到 ${FINDING_COUNT} 条 findings"

# ── 空 findings 提前退出 ──
if [[ "${FINDING_COUNT}" -eq 0 ]]; then
    echo "[RootCause] 无 findings, 跳过分析"
    _empty_json=$(jq -n \
        --arg ts "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
        --argjson rl "${RULE_COUNT}" \
        '{"engine":"root_cause_engine","status":"completed","timestamp":$ts,"findings_count":0,"rules_loaded":$rl,"root_causes":[]}')
    if [[ -n "$OUTPUT_FILE" ]]; then
        echo "$_empty_json" > "$OUTPUT_FILE"
        echo "[RootCause] 输出: ${OUTPUT_FILE}"
    fi
    echo "$_empty_json" | jq '{engine, status, timestamp, findings_count, rules_loaded, root_cause_count: (.root_causes | length)}'
    exit 0
fi

# ── 逐规则匹配 ──
ROOT_CAUSES="["

RULE_INDEX=0
while [[ $RULE_INDEX -lt $RULE_COUNT ]]; do
    # 获取规则字段 (使用 jq 逐条提取, 避免一次性加载)
    RULE_JSON="$(jq ".rules[${RULE_INDEX}]" "${RULES_FILE}")"
    RULE_ID="$(echo "${RULE_JSON}" | jq -r '.rule_id')"
    RULE_DESC="$(echo "${RULE_JSON}" | jq -r '.description // ""')"
    ROOT_CAUSE_TEXT="$(echo "${RULE_JSON}" | jq -r '.root_cause // ""')"
    SUGGESTION="$(echo "${RULE_JSON}" | jq -r '.suggestion // ""')"
    CONFIDENCE="$(echo "${RULE_JSON}" | jq -r '.confidence // 0.5')"

    TRIGGER_DOMAIN="$(echo "${RULE_JSON}" | jq -r '.trigger.domain // ""')"
    TRIGGER_SEV="$(echo "${RULE_JSON}" | jq -r '.trigger.severity_min // ""')"
    TRIGGER_PATTERN="$(echo "${RULE_JSON}" | jq -r '.trigger.message_pattern // ""')"

    CORR_DOMAIN="$(echo "${RULE_JSON}" | jq -r '.correlated.domain // ""')"
    CORR_SEV="$(echo "${RULE_JSON}" | jq -r '.correlated.severity_min // ""')"
    CORR_PATTERN="$(echo "${RULE_JSON}" | jq -r '.correlated.message_pattern // ""')"

    # ── 匹配 trigger finding ──
    TRIGGER_JQFILTER="${JQ_SEVERITY_FN} [.[] | select("
    TRIGGER_CLAUSES=""
    [[ -n "$TRIGGER_DOMAIN" ]]  && TRIGGER_CLAUSES="${TRIGGER_CLAUSES} and (.domain == \"${TRIGGER_DOMAIN}\")"
    if [[ -n "$TRIGGER_SEV" ]]; then
        TS="$(severity_level "$TRIGGER_SEV")"
        TRIGGER_CLAUSES="${TRIGGER_CLAUSES} and ((.severity | severity_level) >= ${TS})"
    fi
    [[ -n "$TRIGGER_PATTERN" ]] && TRIGGER_CLAUSES="${TRIGGER_CLAUSES} and (.message | test(\$pat; \"i\"))"
    TRIGGER_CLAUSES="${TRIGGER_CLAUSES# and }"
    TRIGGER_JQFILTER="${TRIGGER_JQFILTER}${TRIGGER_CLAUSES})]"

    TRIGGER_MATCHES="$(echo "${FINDINGS_JSON}" | jq -c --arg pat "${TRIGGER_PATTERN}" "${TRIGGER_JQFILTER}")"
    TRIGGER_COUNT="$(echo "${TRIGGER_MATCHES}" | jq 'length')"

    if [[ "$TRIGGER_COUNT" -eq 0 ]]; then
        RULE_INDEX=$((RULE_INDEX + 1))
        continue
    fi

    # ── 匹配 correlated finding ──
    CORR_JQFILTER="${JQ_SEVERITY_FN} [.[] | select("
    CORR_CLAUSES=""
    [[ -n "$CORR_DOMAIN" ]]  && CORR_CLAUSES="${CORR_CLAUSES} and (.domain == \"${CORR_DOMAIN}\")"
    if [[ -n "$CORR_SEV" ]]; then
        CS="$(severity_level "$CORR_SEV")"
        CORR_CLAUSES="${CORR_CLAUSES} and ((.severity | severity_level) >= ${CS})"
    fi
    [[ -n "$CORR_PATTERN" ]] && CORR_CLAUSES="${CORR_CLAUSES} and (.message | test(\$cpat; \"i\"))"
    CORR_CLAUSES="${CORR_CLAUSES# and }"
    CORR_JQFILTER="${CORR_JQFILTER}${CORR_CLAUSES})]"

    CORR_MATCHES="$(echo "${FINDINGS_JSON}" | jq -c --arg cpat "${CORR_PATTERN}" "${CORR_JQFILTER}")"
    CORR_COUNT="$(echo "${CORR_MATCHES}" | jq 'length')"

    # ── 产出根因 (trigger 找到 且 correlated 找到) ──
    if [[ "$TRIGGER_COUNT" -gt 0 ]] && [[ "$CORR_COUNT" -gt 0 ]]; then
        echo "[RootCause] ${RULE_ID}: ${RULE_DESC} (trigger=${TRIGGER_COUNT}, correlated=${CORR_COUNT}, confidence=${CONFIDENCE})"

        if [[ "${ROOT_CAUSES}" != "[" ]]; then
            ROOT_CAUSES+=","
        fi

        TRIGGER_ITEM="$(echo "${TRIGGER_MATCHES}" | jq '.[0]')"

        ROOT_CAUSES+=$(
            jq -n \
                --arg rule_id "${RULE_ID}" \
                --arg rule_desc "${RULE_DESC}" \
                --arg root_cause "${ROOT_CAUSE_TEXT}" \
                --arg suggestion "${SUGGESTION}" \
                --argjson confidence "${CONFIDENCE}" \
                --argjson trigger_finding "${TRIGGER_ITEM}" \
                --argjson correlated_findings "${CORR_MATCHES}" \
                '{
                    "rule_id": $rule_id,
                    "description": $rule_desc,
                    "root_cause": $root_cause,
                    "confidence": $confidence,
                    "suggestion": $suggestion,
                    "trigger_finding": $trigger_finding,
                    "correlated_findings": $correlated_findings
                }'
        )
    fi

    RULE_INDEX=$((RULE_INDEX + 1))
done

ROOT_CAUSES+="]"

RC_COUNT="$(echo "${ROOT_CAUSES}" | jq 'length')"
echo "[RootCause] 分析完成: ${RC_COUNT} 条根因"

# ── 生成输出 JSON ──
RESULT_JSON=$(
    jq -n \
        --arg ts "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
        --argjson rules_loaded "${RULE_COUNT}" \
        --argjson findings_count "${FINDING_COUNT}" \
        --argjson root_causes "${ROOT_CAUSES}" \
        '{
            "engine": "root_cause_engine",
            "status": "completed",
            "timestamp": $ts,
            "findings_count": $findings_count,
            "rules_loaded": $rules_loaded,
            "root_causes": $root_causes
        }'
)

if [[ -z "$OUTPUT_FILE" ]]; then
    OUTPUT_FILE="${AUDIT_DIR}/root-cause-$(date +%Y%m%dT%H%M%S).json"
fi

mkdir -p "$(dirname "${OUTPUT_FILE}")"
echo "${RESULT_JSON}" > "${OUTPUT_FILE}"
echo "[RootCause] 输出: ${OUTPUT_FILE}"

# 同时输出到 STDOUT (简洁摘要)
echo "${RESULT_JSON}" | jq '{engine, status, timestamp, root_cause_count: (.root_causes | length)}'

exit 0
