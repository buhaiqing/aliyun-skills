#!/usr/bin/env bash
#
# fusion/ticket_generator.sh — D3 风险告警自动化工单 (Ticket) 生成器
#
# 职责:
#   读取融合报告 JSON 和可选的异常报告 JSON, 提取 CRITICAL/HIGH 级别
#   findings/anomalies, 生成标准化工单 JSON 到 .runtime/tickets/ 目录。
#
# 用法:
#   bash ticket_generator.sh --fusion-report <path> [--anomaly-report <path>] [options]
#
# 选项:
#   --fusion-report  <path>    融合报告 JSON (必填)
#   --anomaly-report <path>    异常分析报告 JSON (可选)
#   --output-dir     <path>    票证输出目录 (默认: .runtime/tickets/)
#   --dry-run                   仅预览, 不写入文件
#   --describe                  描述模式
#
# 依赖:
#   - jq (JSON 解析)
#   - git (获取当前 commit)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
export SKILLS_DIR="$(cd "${AIOPS_DIR}/.." && pwd)"
source "${AIOPS_DIR}/scripts/lib/runtime_root.sh"
aiops_runtime_init "alicloud-aiops-cruise"

# ── 默认路径 ──
FUSION_REPORT=""
ANOMALY_REPORT=""
OUTPUT_DIR="${RUNTIME_ROOT}/tickets"
DRY_RUN=false
DESCRIBE=false
JIRA_ENABLED=false
JIRA_DRY_RUN=false

# ── 映射 source_agent -> skill 函数 ──
# ponytail: case statement, load from config file if >20 products
map_skill() {
    local source_agent="$1"
    local domain="$2"
    local skill="alicloud-ecs-ops"

    if [[ -n "$source_agent" ]]; then
        case "$source_agent" in
            healthcruise) skill="alicloud-ecs-ops" ;;
            toposcan)     skill="alicloud-vpc-ops" ;;
            configdrift)  skill="alicloud-ecs-ops" ;;
            costwatch)    skill="alicloud-bss-ops" ;;
            securityscan) skill="alicloud-sas-ops" ;;
            audittrail)   skill="alicloud-actiontrail-ops" ;;
            advisorscan)  skill="alicloud-advisor-ops" ;;
            *)            skill="" ;;
        esac
    fi

    if [[ -z "$skill" && -n "$domain" ]]; then
        case "$domain" in
            infra)    skill="alicloud-ecs-ops" ;;
            cost)     skill="alicloud-bss-ops" ;;
            security) skill="alicloud-sas-ops" ;;
            advisor)  skill="alicloud-advisor-ops" ;;
            *)        skill="alicloud-ecs-ops" ;;
        esac
    fi

    echo "${skill:-alicloud-ecs-ops}"
}
while [[ $# -gt 0 ]]; do
    case "$1" in
        --fusion-report)  FUSION_REPORT="$2";  shift 2 ;;
        --anomaly-report) ANOMALY_REPORT="$2"; shift 2 ;;
        --output-dir)     OUTPUT_DIR="$2";     shift 2 ;;
        --dry-run)        DRY_RUN=true;        shift ;;
        --describe)       DESCRIBE=true;       shift ;;
        --jira)           JIRA_ENABLED=true;   shift ;;
        --jira-dry-run)   JIRA_ENABLED=true; JIRA_DRY_RUN=true; shift ;;
        *) echo "[ERROR] 未知参数: $1"; exit 2 ;;
    esac
done

if $DESCRIBE; then
    cat <<'STRUCTURE'
Ticket Generator (D3) — 风险告警自动工单生成
  输入: fusion-report.json (必填), anomaly-report.json (可选)
  输出: .runtime/tickets/ticket-{timestamp}-{seq}.json
  字段: ticket_id, severity, skill, finding, suggested_action, timestamp, git_commit
STRUCTURE
    exit 0
fi

# ── 前置检查 ──
[[ -z "$FUSION_REPORT" ]] && { echo "[ERROR] --fusion-report <path> 必填"; exit 2; }
[[ ! -f "$FUSION_REPORT" ]] && { echo "[ERROR] 融合报告文件不存在: ${FUSION_REPORT}"; exit 2; }
jq empty "$FUSION_REPORT" 2>/dev/null || { echo "[ERROR] 融合报告 JSON 格式无效: ${FUSION_REPORT}"; exit 2; }
if [[ -n "$ANOMALY_REPORT" ]]; then
    [[ ! -f "$ANOMALY_REPORT" ]] && { echo "[ERROR] 异常报告文件不存在: ${ANOMALY_REPORT}"; exit 2; }
    jq empty "$ANOMALY_REPORT" 2>/dev/null || { echo "[ERROR] 异常报告 JSON 格式无效: ${ANOMALY_REPORT}"; exit 2; }
fi

mkdir -p "$OUTPUT_DIR"

# ── 获取 git commit ──
GIT_COMMIT="$(git -C "${SKILLS_DIR}" rev-parse HEAD 2>/dev/null || echo "unknown")"

# ── 时间戳 (顺序递增用) ──
TIMESTAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
TIMESTAMP_FLAT="$(date -u '+%Y%m%dT%H%M%S')"

echo "[TicketGen] 开始生成工单..."
echo "[TicketGen]   融合报告: ${FUSION_REPORT}"
[[ -n "$ANOMALY_REPORT" ]] && echo "[TicketGen]   异常报告: ${ANOMALY_REPORT}"
echo "[TicketGen]   输出目录: ${OUTPUT_DIR}"
$DRY_RUN && echo "[TicketGen]   模式: DRY-RUN (不写入)"

SEQ=0

# ── 1. 从融合报告中提取 CRITICAL findings ──
echo "[TicketGen] ★ 提取 CRITICAL findings..."
while IFS=$'\t' read -r domain resource_id resource_type description severity source_agent ts; do
    [[ -z "$description" || "$description" == "null" ]] && continue

    skill="$(map_skill "$source_agent" "$domain")"
    SEQ=$((SEQ + 1))
    TICKET_ID="ticket-${TIMESTAMP_FLAT}-$(printf '%03d' $SEQ)"

    TICKET_JSON=$(jq -n \
        --arg ticket_id "$TICKET_ID" \
        --arg severity "$severity" \
        --arg skill "$skill" \
        --arg domain "$domain" \
        --arg description "$description" \
        --arg resource_id "$resource_id" \
        --arg resource_type "$resource_type" \
        --arg timestamp "$TIMESTAMP" \
        --arg git_commit "$GIT_COMMIT" \
        '{
            "ticket_id": $ticket_id,
            "severity": $severity,
            "skill": $skill,
            "finding": {
                "domain": $domain,
                "description": $description,
                "resource_id": $resource_id,
                "resource_type": $resource_type
            },
            "suggested_action": ("请检查 \($domain) 域: \($description)"),
            "timestamp": $timestamp,
            "git_commit": $git_commit
        }'
    )

    if $DRY_RUN; then
        echo "[TicketGen]   [DRY-RUN] ${TICKET_ID} (${severity}, ${skill}, ${resource_id})"
        echo "${TICKET_JSON}" | jq .
    else
        echo "${TICKET_JSON}" > "${OUTPUT_DIR}/${TICKET_ID}.json"
        echo "[TicketGen]   [+] ${TICKET_ID} (${severity}, ${skill}, ${resource_id})"
    fi
done < <(jq -r '.findings[]? | select(.severity == "CRITICAL") | [.domain, .resource_id, .resource_type, .description, .severity, (.source_agent // "unknown"), (.timestamp // "")] | @tsv' "$FUSION_REPORT" 2>/dev/null)

CRITICAL_COUNT="$SEQ"

# ── 2. 从异常报告中提取 HIGH anomalies (可选) ──
if [[ -n "$ANOMALY_REPORT" ]]; then
    echo "[TicketGen] ★ 提取 HIGH anomalies..."

    # 格式1: root_cause_engine 输出 (root_causes 数组)
    while IFS=$'\t' read -r rule_id root_cause_text suggestion trigger_domain trigger_resource_id trigger_description; do
        [[ -z "$root_cause_text" || "$root_cause_text" == "null" ]] && continue
        [[ -z "$trigger_domain" || "$trigger_domain" == "null" ]] && trigger_domain="unknown"
        [[ -z "$trigger_resource_id" || "$trigger_resource_id" == "null" ]] && trigger_resource_id=""
        [[ -z "$trigger_description" || "$trigger_description" == "null" ]] && trigger_description="$root_cause_text"
        [[ -z "$suggestion" || "$suggestion" == "null" ]] && suggestion=""

        SEQ=$((SEQ + 1))
        TICKET_ID="ticket-${TIMESTAMP_FLAT}-$(printf '%03d' $SEQ)"
        skill="$(map_skill "" "$trigger_domain")"

        TICKET_JSON=$(jq -n \
            --arg ticket_id "$TICKET_ID" \
            --arg severity "HIGH" \
            --arg skill "$skill" \
            --arg domain "$trigger_domain" \
            --arg description "$root_cause_text" \
            --arg resource_id "$trigger_resource_id" \
            --arg resource_type "" \
            --arg suggested_action "${suggestion:-请排查 $rule_id: $root_cause_text}" \
            --arg timestamp "$TIMESTAMP" \
            --arg git_commit "$GIT_COMMIT" \
            '{
                "ticket_id": $ticket_id,
                "severity": $severity,
                "skill": $skill,
                "finding": {
                    "domain": $domain,
                    "description": $description,
                    "resource_id": $resource_id,
                    "resource_type": $resource_type
                },
                "suggested_action": $suggested_action,
                "timestamp": $timestamp,
                "git_commit": $git_commit
            }'
        )

        if $DRY_RUN; then
            echo "[TicketGen]   [DRY-RUN] ${TICKET_ID} (HIGH, root_cause: ${rule_id})"
            echo "${TICKET_JSON}" | jq .
        else
            echo "${TICKET_JSON}" > "${OUTPUT_DIR}/${TICKET_ID}.json"
            echo "[TicketGen]   [+] ${TICKET_ID} (HIGH, root_cause: ${rule_id})"
        fi
    done < <(jq -r '.root_causes[]? | [.rule_id, (.root_cause // ""), (.suggestion // ""), (.trigger_finding.domain // ""), (.trigger_finding.resource_id // ""), (.trigger_finding.description // "")] | @tsv' "$ANOMALY_REPORT" 2>/dev/null)

    # 格式2: 通用 findings/anomalies/events 数组 (severity == HIGH)
    while IFS=$'\t' read -r domain resource_id resource_type description source_agent ts; do
        [[ -z "$description" || "$description" == "null" ]] && continue

        SEQ=$((SEQ + 1))
        TICKET_ID="ticket-${TIMESTAMP_FLAT}-$(printf '%03d' $SEQ)"
        skill="$(map_skill "$source_agent" "$domain")"

        TICKET_JSON=$(jq -n \
            --arg ticket_id "$TICKET_ID" \
            --arg severity "HIGH" \
            --arg skill "$skill" \
            --arg domain "$domain" \
            --arg description "$description" \
            --arg resource_id "$resource_id" \
            --arg resource_type "$resource_type" \
            --arg timestamp "$TIMESTAMP" \
            --arg git_commit "$GIT_COMMIT" \
            '{
                "ticket_id": $ticket_id,
                "severity": $severity,
                "skill": $skill,
                "finding": {
                    "domain": $domain,
                    "description": $description,
                    "resource_id": $resource_id,
                    "resource_type": $resource_type
                },
                "suggested_action": ("请检查 \($domain) 域: \($description)"),
                "timestamp": $timestamp,
                "git_commit": $git_commit
            }'
        )

        if $DRY_RUN; then
            echo "[TicketGen]   [DRY-RUN] ${TICKET_ID} (HIGH, ${skill}, ${resource_id})"
            echo "${TICKET_JSON}" | jq .
        else
            echo "${TICKET_JSON}" > "${OUTPUT_DIR}/${TICKET_ID}.json"
            echo "[TicketGen]   [+] ${TICKET_ID} (HIGH, ${skill}, ${resource_id})"
        fi
    done < <(jq -r '.findings[]?, .anomalies[]?, .events[]? | select(.severity == "HIGH") | [.domain // "", .resource_id // "", .resource_type // "", .description // (.message // .name // ""), .severity, (.source_agent // "unknown"), (.timestamp // "")] | @tsv' "$ANOMALY_REPORT" 2>/dev/null)
fi

ANOMALY_COUNT=$((SEQ - CRITICAL_COUNT))
TOTAL_COUNT="$SEQ"

echo ""
echo "[TicketGen] ✅ 工单生成完成"
echo "[TicketGen]   总计: ${TOTAL_COUNT} 张"
echo "[TicketGen]   CRITICAL: ${CRITICAL_COUNT} 张 (融合报告)"
echo "[TicketGen]   HIGH:     ${ANOMALY_COUNT} 张 (异常报告)"
echo "[TicketGen]   输出: ${OUTPUT_DIR}"

# ── Jira 集成: 通过 REST API 直接创建 issue（可选）──
# 配置方式: JIRA_URL / JIRA_EMAIL / JIRA_API_TOKEN / JIRA_PROJECT_KEY
# 未配置时静默跳过, 不影响主流程
if $JIRA_ENABLED; then
    _jira_url="${JIRA_URL:-}"
    _jira_email="${JIRA_EMAIL:-}"
    _jira_token="${JIRA_API_TOKEN:-}"
    _jira_project="${JIRA_PROJECT_KEY:-DOPS}"
    if [[ -z "$_jira_url" || -z "$_jira_email" || -z "$_jira_token" ]]; then
        echo "[TicketGen] ⚠️ Jira 配置不完整 (JIRA_URL/JIRA_EMAIL/JIRA_API_TOKEN), 跳过 Jira 集成"
    else
        _jira_created=0
        for _jf in "${OUTPUT_DIR}"/ticket-*.json; do
            [[ -f "$_jf" ]] || continue
            _severity="$(jq -r '.severity' "$_jf")"
            _summary="$(jq -r '[.skill, .finding.description] | join(": ")' "$_jf")"
            _desc="$(jq -r '.suggested_action // .finding.description' "$_jf")"
            _labels="$(jq -r '.finding.domain // "ops"' "$_jf")"
            _priority="Medium"
            case "$_severity" in CRITICAL) _priority="Highest" ;; HIGH) _priority="High" ;; MEDIUM) _priority="Medium" ;; *) _priority="Low" ;; esac

            _payload=$(jq -n \
                --arg project "$_jira_project" \
                --arg summary "${_summary:0:200}" \
                --arg desc "$_desc" \
                --arg priority "$_priority" \
                --arg labels "$_labels" \
                '{ "fields": { "project": {"key": $project}, "summary": $summary, "description": $desc, "priority": {"name": $priority}, "issuetype": {"name": "Task"}, "labels": [$labels] } }')

            if $JIRA_DRY_RUN; then
                echo "[TicketGen] 🔍 Jira DRY-RUN: 将创建 issue (project=${_jira_project}, severity=${_severity}, summary=${_summary:0:60})"
                echo "  Payload: $(echo "$_payload" | jq -c .)"
                continue
            fi

            _resp=$(curl -s -o /dev/null -w "%{http_code}" \
                -u "${_jira_email}:${_jira_token}" \
                -H "Content-Type: application/json" \
                -d "$_payload" \
                "${_jira_url}/rest/api/2/issue" 2>/dev/null || echo "000")

            if [[ "$_resp" == "201" ]]; then
                _jira_created=$((_jira_created + 1))
                echo "[TicketGen] ✅ Jira issue 创建成功: $(basename "$_jf") (201)"
            else
                echo "[TicketGen] ⚠️ Jira issue 创建失败: $(basename "$_jf") (HTTP ${_resp})"
            fi
        done
        if $JIRA_DRY_RUN; then
            echo "[TicketGen] 🔍 Jira DRY-RUN 完成: 共预览 ${_jira_created} 张工单"
        else
            echo "[TicketGen] 📋 Jira 同步完成: 已创建 ${_jira_created} 个 issue"
        fi
    fi
fi

exit 0