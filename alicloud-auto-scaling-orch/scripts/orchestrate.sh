#!/bin/bash
# ================================================================
# alicloud-auto-scaling-orch — 弹性伸缩编排引擎入口
# 用法: ./orchestrate.sh --scenario <场景> [参数...]
# ================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="${SCRIPT_DIR}/lib"
source "${LIB_DIR}/common.sh"

# ── 默认值 ──
SCENARIO=""
SCALING_GROUP_ID=""
POLICY_NAME="orch-$(date +%Y%m%d%H%M%S)"
REPORT_FILE=""

# ── 参数解析 ──
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scenario)     SCENARIO="$2"; shift 2 ;;
    --group-id)     SCALING_GROUP_ID="$2"; shift 2 ;;
    --policy-name)  POLICY_NAME="$2"; shift 2 ;;
    --report-file)  REPORT_FILE="$2"; shift 2 ;;
    --help|-h)
      echo "用法: $0 --scenario <metric|scheduled|predictive|composite|event|cleanup> [选项]"
      echo "选项:"
      echo "  --group-id     <ID>     目标伸缩组 ID"
      echo "  --policy-name  <name>   策略名称 (默认: orch-日期)"
      echo "  --report-file  <path>   报告输出路径 (默认: stdout)"
      exit 0
      ;;
    *) log_error "未知参数: $1"; exit 1 ;;
  esac
done

# ── 校验 ──
require_env "ALIBABA_CLOUD_REGION_ID"
require_env "ALIBABA_CLOUD_ACCESS_KEY_ID"
require_env "ALIBABA_CLOUD_ACCESS_KEY_SECRET"

if [[ -z "${SCENARIO}" ]]; then
  log_error "必须指定 --scenario 参数"
  echo "可选值: metric, scheduled, predictive, composite, event, cleanup"
  exit 1
fi

# ── 决策引擎 ──
log_info "场景: ${SCENARIO}"
log_info "策略: ${POLICY_NAME}"

# 步骤 1: 熔断检查
run_fuse_checks "${SCALING_GROUP_ID}"

# 步骤 2: 生成编排计划
PLAN_JSON=$( "${SCRIPT_DIR}/decision.sh" \
  --scenario "${SCENARIO}" \
  --group-id "${SCALING_GROUP_ID}" \
  --policy-name "${POLICY_NAME}" \
  "$@" )
log_info "编排计划: $(echo "${PLAN_JSON}" | jq -c '{plan_id, scenario, original_capacity, target_capacity}')"

# 步骤 3: 按计划编排执行
TRACE_ID="trace-${POLICY_NAME}"
EXEC_SUMMARY=$(execute_plan "${PLAN_JSON}" "${TRACE_ID}")

# 步骤 4: 验证
VERIFY_JSON=$( "${SCRIPT_DIR}/verify.sh" \
  --group-id "${SCALING_GROUP_ID}" \
  --plan-json "${PLAN_JSON}" \
  --trace-id "${TRACE_ID}" )
log_info "验证状态: $(echo "${VERIFY_JSON}" | jq -r '.status')"

# 步骤 5: 生成报告
REPORT=$(cat <<REPORT_EOF
## 弹性伸缩编排报告

| 项目 | 值 |
|------|-----|
| 策略名称 | ${POLICY_NAME} |
| 场景 | ${SCENARIO} |
| 伸缩组 | ${SCALING_GROUP_ID} |
| 执行时间 | $(date -u +%Y-%m-%dT%H:%M:%SZ) |
| TraceID | ${TRACE_ID} |

### 执行结果
- 原容量: $(echo "${PLAN_JSON}" | jq -r '.original_capacity')
- 目标容量: $(echo "${PLAN_JSON}" | jq -r '.target_capacity')
- 状态: $(echo "${VERIFY_JSON}" | jq -r '.status')

### 验证检查
$(echo "${VERIFY_JSON}" | jq -r '.checks[] | "- \(.name): \(if .passed then "✅" else "❌" end) (实际: \(.actual // "N/A"), 期望: \(.expected // "N/A"))"')

### 成本影响
- 预估日增: $(echo "${EXEC_SUMMARY}" | jq -r '.cost_impact.estimated_daily_increase // "N/A"')
REPORT_EOF
)

if [[ -n "${REPORT_FILE}" ]]; then
  echo "${REPORT}" > "${REPORT_FILE}"
  log_info "报告已写入: ${REPORT_FILE}"
else
  echo "${REPORT}"
fi

log_info "编排完成"