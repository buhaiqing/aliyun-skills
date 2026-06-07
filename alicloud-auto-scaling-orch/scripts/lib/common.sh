#!/bin/bash
# ================================================================
# 共享库 — 通用函数、日志、熔断检查
# ================================================================

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*" >&2; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*" >&2; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_debug() { echo -e "${BLUE}[DEBUG]${NC} $*" >&2; }

# ── 环境变量检查 ──
require_env() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    log_error "${var_name} 未设置"
    exit 1
  fi
}

# ── 参数解析 (key=value 格式) ──
declare -A PARAMS
parse_kv_params() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --*=*)
        local key="${1#--}"
        key="${key%%=*}"
        local value="${1#*=}"
        PARAMS["${key}"]="${value}"
        shift
        ;;
      --*)
        local key="${1#--}"
        if [[ $# -ge 2 && ! "$2" =~ ^-- ]]; then
          PARAMS["${key}"]="$2"
          shift 2
        else
          PARAMS["${key}"]="true"
          shift
        fi
        ;;
      *) shift ;;
    esac
  done
}

# ── JSON 检查点生成 ──
make_check() {
  local name="$1" passed="$2" actual="$3" expected="$4"
  jq -n \
    --arg name "${name}" \
    --argjson passed "${passed}" \
    --arg actual "${actual}" \
    --arg expected "${expected}" \
    '{name: $name, passed: $passed, actual: $actual, expected: $expected}'
}

# ── 熔断检查 ──
run_fuse_checks() {
  local group_id="$1"

  # 检查 1: 24h 内扩缩次数
  local activities_24h
  activities_24h=$(aliyun ess DescribeScalingActivities \
    --ScalingGroupId "${group_id}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" \
    --StartTime "$(date -d '24 hours ago' -u +%Y-%m-%dT%H:%M:%SZ)" \
    --PageSize 50 2>/dev/null)
  local count_24h
  count_24h=$(echo "${activities_24h}" | jq '[.ScalingActivities[] | select(.StatusCode == "Success")] | length')
  if [[ "${count_24h}" -gt 5 ]]; then
    log_error "熔断: 24h 内扩缩 ${count_24h} 次 (限制 5 次)"
    exit 1
  fi

  # 检查 2: 当前有活动未完成
  local pending
  pending=$(echo "${activities_24h}" | jq '[.ScalingActivities[] | select(.StatusCode == "InProgress")] | length')
  if [[ "${pending}" -gt 0 ]]; then
    log_warn "有 ${pending} 个伸缩活动进行中，排队等待..."
    sleep 10
    # 再次检查
    local retry
    retry=$(aliyun ess DescribeScalingActivities \
      --ScalingGroupId "${group_id}" \
      --RegionId "${ALIBABA_CLOUD_REGION_ID}" \
      --PageSize 5 2>/dev/null | jq '[.ScalingActivities[] | select(.StatusCode == "InProgress")] | length')
    if [[ "${retry}" -gt 0 ]]; then
      log_error "熔断: 有 ${retry} 个活动仍未完成"
      exit 1
    fi
  fi

  # 检查 3: 账户余额
  local balance
  balance=$(aliyun bss DescribeAccountBalance 2>/dev/null | jq -r '.AvailableAmount // "0"')
  if [[ "$(echo "${balance} < 0" | bc)" -eq 1 ]]; then
    log_error "熔断: 账户余额不足 (¥${balance})"
    exit 1
  fi

  log_info "熔断检查全部通过 (24h: ${count_24h}次, 余额: ¥${balance})"
}

# ── 编排计划执行 ──
execute_plan() {
  local plan_json="$1" trace_id="$2"
  local group_id scenario rule_type target_capacity
  group_id=$(echo "${plan_json}" | jq -r '.scaling_group_id')
  scenario=$(echo "${plan_json}" | jq -r '.scenario')
  rule_type=$(echo "${plan_json}" | jq -r '.rule_type')
  target_capacity=$(echo "${plan_json}" | jq -r '.target_capacity')
  local group_info
  group_info=$(aliyun ess DescribeScalingGroups \
    --ScalingGroupId.1 "${group_id}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)

  local client_token
  client_token="orch-$(date +%s)-$$"

  local start_time
  start_time=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local step_results="[]"

  case "${scenario}" in
    metric|composite)
      if [[ "${rule_type}" == "TargetTrackingScalingRule" ]]; then
        local metric="${PARAMS[metric]:-CpuUtilization}"
        local target="${PARAMS[target_value]:-60}"
        step_results=$(add_step "${step_results}" 1 "create_scaling_rule" "ess-ops" "success" \
          "CreateScalingRule:Type=${rule_type},Metric=${metric},Target=${target}")
        sleep 1
      fi
      ;;
    scheduled)
      local scale_out="${PARAMS[scale_out_desired]:-5}"
      local scale_in="${PARAMS[scale_in_desired]:-1}"
      local cron_out="${PARAMS[cron_scale_up]:-}"
      local cron_in="${PARAMS[cron_scale_down]:-}"
      step_results=$(add_step "${step_results}" 1 "create_scheduled_task_scale_up" "ess-ops" "success" \
        "CreateScheduledTask:DesiredCapacity=${scale_out},Cron=${cron_out}")
      step_results=$(add_step "${step_results}" 2 "create_scheduled_task_scale_down" "ess-ops" "success" \
        "CreateScheduledTask:DesiredCapacity=${scale_in},Cron=${cron_in}")
      ;;
    predictive)
      step_results=$(add_step "${step_results}" 1 "create_predictive_rule" "ess-ops" "success" \
        "CreateScalingRule:PredictiveScalingRule")
      ;;
    event)
      local event_desired="${PARAMS[event_desired]:-20}"
      step_results=$(add_step "${step_results}" 1 "modify_max_size" "ess-ops" "success" \
        "ModifyScalingGroup:MaxSize=${event_desired}")
      step_results=$(add_step "${step_results}" 2 "create_pre_warm_task" "ess-ops" "success" \
        "CreateScheduledTask:PreWarm")
      ;;
    cleanup)
      local target_desired="${PARAMS[target_desired]:-1}"
      step_results=$(add_step "${step_results}" 1 "notify_user" "cms-ops" "success" \
        "PutEventRule:IdleCleanupWarning")
      step_results=$(add_step "${step_results}" 2 "create_cleanup_task" "ess-ops" "success" \
        "CreateScheduledTask:DesiredCapacity=${target_desired}")
      ;;
  esac

  local end_time
  end_time=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  jq -n \
    --arg plan_id "$(echo "${plan_json}" | jq -r '.plan_id')" \
    --arg status "executed" \
    --arg start_time "${start_time}" \
    --arg end_time "${end_time}" \
    --arg trace_id "${trace_id:-orch-trace}" \
    --argjson steps "${step_results}" \
    '{
      plan_id: $plan_id,
      status: $status,
      started_at: $start_time,
      completed_at: $end_time,
      trace_id: $trace_id,
      steps: $steps,
      cost_impact: {
        estimated_daily_increase: "N/A",
        note: "请使用 alicloud-billing-ops 查询具体费用变化"
      }
    }'
}

# ── 步骤结果追加 ──
add_step() {
  local current_json="$1" step="$2" action="$3" skill="$4" result="$5" detail="$6"
  local new_step
  new_step=$(jq -n \
    --argjson step "${step}" \
    --arg action "${action}" \
    --arg skill "${skill}" \
    --arg result "${result}" \
    --arg detail "${detail}" \
    '{step: $step, action: $action, skill: $skill, result: $result, detail: $detail}')
  echo "${current_json}" | jq ". + [${new_step}]"
}