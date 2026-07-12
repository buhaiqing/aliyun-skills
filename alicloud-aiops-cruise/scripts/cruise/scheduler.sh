#!/usr/bin/env bash
#
# cruise/scheduler.sh — D1 自动化资源优化巡航调度器
#
# 职责:
#   编排巡航流水线: perceive → fusion → root_cause → 报告
#   生成融合巡航报告 + Markdown 摘要
#   TTL 清理: 保留最近 28 天 (4 周) 的报告
#
# 用法:
#   bash scheduler.sh                          # 默认: --core
#   bash scheduler.sh --all                    # 全部 7 个感知 Agent
#   bash scheduler.sh --core                   # infra+cost+security (默认)
#   bash scheduler.sh --dry-run                # 仅打印计划
#   bash scheduler.sh --dry-run --all          # 打印全部 Agent 计划
#   bash scheduler.sh --cleanup                # 清理超过 28 天的报告
#
# 流水线:
#   perceive (__init__.sh) → fusion (fusion_report.sh)
#     → root_cause (root_cause_engine.sh) → 报告整合 → Markdown 摘要

set -euo pipefail

# ── 路径解析 ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
export SKILLS_DIR="$(cd "${AIOPS_DIR}/.." && pwd)"

# shellcheck source=../../lib/runtime_root.sh
source "${AIOPS_DIR}/scripts/lib/runtime_root.sh"
aiops_runtime_init "alicloud-aiops-cruise"

PERCEIVE_DIR="${AIOPS_DIR}/scripts/agents/perceive"
FUSION_SCRIPT="${AIOPS_DIR}/scripts/agents/fusion/fusion_report.sh"
ROOT_CAUSE_SCRIPT="${AIOPS_DIR}/scripts/agents/fusion/root_cause_engine.sh"
CORRELATION_RULES="${AIOPS_DIR}/scripts/agents/fusion/correlation-rules.json"
REPORTS_DIR="${AIOPS_DIR}/docs/cruise-reports"

DATE_TAG="$(date +%Y%m%d)"
TS_START="$(date '+%H:%M:%S')"
CRUISE_WORK_DIR="${RUNTIME_AUDIT_DIR}/cruise/$(date +%Y%m%dT%H%M%S)"
CRUISE_REPORT="${CRUISE_WORK_DIR}/cruise-report-weekly-${DATE_TAG}.json"
MD_REPORT="${REPORTS_DIR}/cruise-weekly-${DATE_TAG}.md"
LOG_FILE="${RUNTIME_TMP_DIR}/cruise-scheduler-${DATE_TAG}.log"

# ── 参数 ──
MODE="core"
DRY_RUN=false
CLEANUP=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all) MODE="all"; shift ;;
        --core) MODE="core"; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --cleanup) CLEANUP=true; shift ;;
        *) echo "[ERROR] 未知参数: $1"; exit 2 ;;
    esac
done

# ponytail: single log file per run, add rotated logs when runs exceed 100

# ── 清理模式 (D1.3) ──
if $CLEANUP; then
    echo "[Scheduler] 清理超过 28 天的 cruise 报告..."
    if [[ ! -d "${REPORTS_DIR}" ]]; then
        echo "[Scheduler]   无报告目录, 跳过"
        exit 0
    fi
    deleted=0
    while IFS= read -r -d '' f; do
        rm "$f"
        echo "[Scheduler]   [DEL] ${f}"
        deleted=$((deleted + 1))
    done < <(find "${REPORTS_DIR}" -maxdepth 1 -name 'cruise-weekly-*.md' -mtime +28 -print0 2>/dev/null || true)
    echo "[Scheduler]   删除 ${deleted} 个文件"
    exit 0
fi

# ── Dry-run 模式 ──
dry_run_plan() {
    local mode="$1"
    echo "==================== Cruise Scheduler (dry-run) ===================="
    echo "  模式: ${mode}"
    echo ""
    echo "  Step 1 — Perceive (${mode} agents):"
    echo ""
    if [[ "$mode" == "all" ]]; then
        echo "    bash ${PERCEIVE_DIR}/__init__.sh"
        echo "      --mode all"
        echo "      --output-dir ${CRUISE_WORK_DIR}"
        echo ""
        echo "    Agents:"
        echo "      - infra/healthcruise.sh  (全链路健康巡检)"
        echo "      - infra/toposcan.sh      (拓扑发现)"
        echo "      - infra/configdrift.sh   (配置漂移检测)"
        echo "      - cost/costwatch.sh      (成本监察)"
        echo "      - security/securityscan.sh (安全扫描)"
        echo "      - security/audittrail.sh  (操作审计)"
        echo "      - advisor/advisorscan.sh  (顾问建议)"
    else
        echo "    bash ${PERCEIVE_DIR}/__init__.sh"
        echo "      --mode infra"
        echo "      --output-dir ${CRUISE_WORK_DIR}"
        echo "    Agents: healthcruise, toposcan, configdrift"
        echo ""
        echo "    bash ${PERCEIVE_DIR}/__init__.sh"
        echo "      --mode cost"
        echo "      --output-dir ${CRUISE_WORK_DIR}"
        echo "    Agents: costwatch"
        echo ""
        echo "    bash ${PERCEIVE_DIR}/__init__.sh"
        echo "      --mode security"
        echo "      --output-dir ${CRUISE_WORK_DIR}"
        echo "    Agents: securityscan, audittrail"
    fi
    echo ""
    echo "  Step 2 — Fusion:"
    echo "    bash ${FUSION_SCRIPT}"
    echo "      --input-dir ${CRUISE_WORK_DIR}"
    echo ""
    echo "  Step 3 — Root Cause:"
    echo "    bash ${ROOT_CAUSE_SCRIPT}"
    echo "      --report <fusion-report-*.json>"
    echo "      --rules ${CORRELATION_RULES}"
    echo ""
    echo "  Step 4 — Report:"
    echo "    Cruise report:     ${CRUISE_REPORT}"
    echo "    Markdown summary:  ${MD_REPORT}"
    echo ""
    echo "  Step 5 — TTL cleanup (28 days):"
    echo "    find ${REPORTS_DIR} -name 'cruise-weekly-*.md' -mtime +28 -delete"
    echo ""
    echo "===================================================================="
}

if $DRY_RUN; then
    dry_run_plan "$MODE"
    exit 0
fi

# ── 主流程 ──

exec 3>&1 4>&2 >"${LOG_FILE}" 2>&1
# ponytail: single log file; rotate in a cron wrapper if runs exceed 100

echo "==================== Cruise Scheduler ===================="
echo "  模式: ${MODE}"
echo "  工作目录: ${CRUISE_WORK_DIR}"
echo "  报告目录: ${REPORTS_DIR}"
echo "  日志: ${LOG_FILE}"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

mkdir -p "${CRUISE_WORK_DIR}" "${REPORTS_DIR}"

# ── Step 1: Perceive ──
echo "────────────────── Step 1/5: Perceive ──────────────────"

if [[ "$MODE" == "all" ]]; then
    bash "${PERCEIVE_DIR}/__init__.sh" --mode all --output-dir "${CRUISE_WORK_DIR}"
    PERCEIVE_RC=$?
else
    # --core: infra + cost + security, same output dir, each __init__.sh writes to it
    for pmode in infra cost security; do
        echo "[Scheduler]   ▶ perceive mode: ${pmode}"
        bash "${PERCEIVE_DIR}/__init__.sh" --mode "${pmode}" --output-dir "${CRUISE_WORK_DIR}" || true
    done
    PERCEIVE_RC=0
fi

agent_count=$(find "${CRUISE_WORK_DIR}" -maxdepth 1 -name '*.json' ! -name 'perceive-summary.json' ! -name 'fusion-report-*' ! -name 'root-cause-*' 2>/dev/null | wc -l | tr -d ' ')
echo "[Scheduler]   Perceive 完成: ${agent_count} agent 输出"

# ── Step 2: Fusion ──
echo ""
echo "────────────────── Step 2/5: Fusion ──────────────────"

FUSION_OUTPUT=""
if [[ -f "${FUSION_SCRIPT}" ]]; then
    echo "[Scheduler]   ▶ fusion_report.sh --input-dir ${CRUISE_WORK_DIR}"
    bash "${FUSION_SCRIPT}" --input-dir "${CRUISE_WORK_DIR}"
    FUSION_RC=$?
    FUSION_OUTPUT=$(find "${CRUISE_WORK_DIR}" -maxdepth 1 -name 'fusion-report-*.json' -print -quit)
else
    echo "[Scheduler]   [WARN] fusion_report.sh 不存在: ${FUSION_SCRIPT}"
    FUSION_RC=1
fi

echo "[Scheduler]   Fusion 输出: ${FUSION_OUTPUT:-none}"

# ── Step 3: Root Cause ──
echo ""
echo "────────────────── Step 3/5: Root Cause ──────────────────"

RC_OUTPUT=""
if [[ -f "$FUSION_OUTPUT" ]] && [[ -f "${ROOT_CAUSE_SCRIPT}" ]]; then
    echo "[Scheduler]   ▶ root_cause_engine.sh --report ${FUSION_OUTPUT}"
    bash "${ROOT_CAUSE_SCRIPT}" --report "${FUSION_OUTPUT}"
    RC_RC=$?
    RC_OUTPUT=$(find "${CRUISE_WORK_DIR}" -maxdepth 1 -name 'root-cause-*.json' -print -quit)
elif [[ ! -f "${ROOT_CAUSE_SCRIPT}" ]]; then
    echo "[Scheduler]   [WARN] root_cause_engine.sh 不存在: ${ROOT_CAUSE_SCRIPT}"
    RC_RC=1
else
    echo "[Scheduler]   融合报告为空, 跳过根因分析"
    RC_RC=1
fi

echo "[Scheduler]   Root Cause 输出: ${RC_OUTPUT:-none}"

# ── Step 4: 巡航报告整合 (D1.1) ──
echo ""
echo "────────────────── Step 4/5: 巡航报告整合 ──────────────────"

# 读取融合报告的 findings 统计
FUSION_STATS="{}"
if [[ -f "$FUSION_OUTPUT" ]]; then
    if jq empty "$FUSION_OUTPUT" 2>/dev/null; then
        FUSION_STATS=$(jq '{total_raw:.total_findings_raw, total_deduped:.total_findings_deduped}' "$FUSION_OUTPUT")
    fi
fi

# 读取根因分析结果统计
RC_STATS="{}"
if [[ -f "$RC_OUTPUT" ]]; then
    if jq empty "$RC_OUTPUT" 2>/dev/null; then
        RC_STATS=$(jq '{root_cause_count:(.root_causes|length), status:.status}' "$RC_OUTPUT")
    fi
fi

# 组装最终巡航报告
jq -n \
    --arg date_tag "${DATE_TAG}" \
    --arg ts "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
    --arg mode "${MODE}" \
    --argjson fusion "${FUSION_STATS}" \
    --argjson root_cause "${RC_STATS}" \
    '{
        "pipeline":"cruise",
        "version":"1.0.0",
        "date_tag":$date_tag,
        "timestamp":$ts,
        "mode":$mode,
        "perceive_agents":'"${agent_count}"',
        "fusion": $fusion,
        "root_cause": $root_cause,
        "work_dir": "'"${CRUISE_WORK_DIR}"'",
        "markdown_summary": "'"${MD_REPORT}"'"
    }' > "${CRUISE_REPORT}"

echo "[Scheduler]  巡航报告: ${CRUISE_REPORT}"

# ── Step 5: Markdown 摘要 (D1.2) ──
echo ""
echo "────────────────── Step 5/5: Markdown 摘要 ──────────────────"

if [[ -f "$FUSION_OUTPUT" ]] && jq empty "$FUSION_OUTPUT" 2>/dev/null; then
    # 总览统计
    total_raw=$(jq -r '.total_findings_raw // "0"' "$FUSION_OUTPUT")
    total_dedup=$(jq -r '.total_findings_deduped // "0"' "$FUSION_OUTPUT")

    # 严重性分布
    sev_breakdown=$(jq -r '[.findings|group_by(.severity)[]|{s:.[0].severity,c:length}]|sort_by(.s)|map("\(.s): \(.c)")|join(", ")' "$FUSION_OUTPUT" 2>/dev/null || echo "")

    # 各严重性数量
    critical_count=$(jq -r '[.findings[] | select(.severity=="CRITICAL")] | length' "$FUSION_OUTPUT" 2>/dev/null || echo 0)
    high_count=$(jq -r '[.findings[] | select(.severity=="HIGH")] | length' "$FUSION_OUTPUT" 2>/dev/null || echo 0)
    medium_count=$(jq -r '[.findings[] | select(.severity=="MEDIUM")] | length' "$FUSION_OUTPUT" 2>/dev/null || echo 0)

    # 根因统计
    rc_count=$(jq -r '.root_cause_count // "0"' "$RC_OUTPUT" 2>/dev/null || echo 0)

    # Agent 状态
    agent_status_line=$(find "${CRUISE_WORK_DIR}" -maxdepth 1 -name '*.json' ! -name 'perceive-summary.json' ! -name 'fusion-report-*' ! -name 'root-cause-*' -exec jq -r '.status // "completed"' {} \; 2>/dev/null | sort | uniq -c | awk '{printf "%sx%s ", $2, $1}' | paste -sd ',' - 2>/dev/null || echo "")

    # Top 5 critical/high findings
    top5=$(jq -r '[.findings[] | select(.severity=="CRITICAL" or .severity=="HIGH")] | sort_by(.severity) | .[:5] | .[] | "* **\(.severity)** [\(.domain)] \(.description) — \(.resource_id // "N/A")"' "$FUSION_OUTPUT" 2>/dev/null || true)
    top5_count=$(echo "$top5" | grep -c '^\*' 2>/dev/null || echo 0)

    cat > "${MD_REPORT}" <<MDEOF
# Cruise Weekly Report — ${DATE_TAG}

**Generated**: $(date -u '+%Y-%m-%d %H:%M:%S UTC') | **Mode**: ${MODE}

## Summary

| Metric | Value |
|--------|-------|
| Total Findings (raw) | ${total_raw} |
| Total Findings (deduped) | ${total_dedup} |
| Root Causes Analyzed | ${rc_count} |
| Agents Run | ${agent_count} |
| Agent Status | ${agent_status_line:-N/A} |

## Severity Breakdown

| Severity | Count |
|----------|-------|
| CRITICAL | ${critical_count} |
| HIGH | ${high_count} |
| MEDIUM | ${medium_count} |
| Other | $(( total_dedup - critical_count - high_count - medium_count )) |

$(if [[ -n "$sev_breakdown" ]]; then echo "**Full**: ${sev_breakdown}"; fi)

## Top Findings

$(if [[ "$top5_count" -gt 0 ]]; then echo "${top5}"; else echo "_No critical or high findings._"; fi)

## Next Steps

- Review detailed findings in the fusion report.
- Address root causes identified by the root cause engine.
- Schedule follow-up cruise if critical items remain.
MDEOF

    echo "[Scheduler]  Markdown 摘要: ${MD_REPORT}"
else
    cat > "${MD_REPORT}" <<MDEOF
# Cruise Weekly Report — ${DATE_TAG}

**Generated**: $(date -u '+%Y-%m-%d %H:%M:%S UTC') | **Mode**: ${MODE}
**Status**: No findings recorded.

_No data from perceive agents or fusion pipeline._
MDEOF
    echo "[Scheduler]   Markdown 摘要 (空): ${MD_REPORT}"
fi

# ── TTL 清理 (D1.3) ──
echo ""
echo "────────────────── TTL: 清理超过 28 天的报告 ──────────────────"

if [[ -d "${REPORTS_DIR}" ]]; then
    cleanup_count=0
    while IFS= read -r -d '' f; do
        rm "$f"
        echo "[Scheduler]   [TTL] ${f}"
        cleanup_count=$((cleanup_count + 1))
    done < <(find "${REPORTS_DIR}" -maxdepth 1 -name 'cruise-weekly-*.md' -mtime +28 -print0 2>/dev/null || true)
    if [[ $cleanup_count -gt 0 ]]; then
        echo "[Scheduler]   清理 ${cleanup_count} 个过期报告"
    else
        echo "[Scheduler]   无过期报告"
    fi
fi

# ── 完成 ──
echo ""
echo "==================== Cruise Scheduler 完成 ===================="
echo "  巡航报告: ${CRUISE_REPORT}"
echo "  Markdown: ${MD_REPORT}"
echo "  工作目录: ${CRUISE_WORK_DIR}"
echo "================================================================"

# 恢复 stdout/stderr 并输出摘要
exec 1>&3 2>&4 3>&- 4>&-
echo "[Cruise] 完成 — 模式: ${MODE}, 报告: ${MD_REPORT}"