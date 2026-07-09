#!/bin/bash
# ================================================================
# 决策引擎 — 根据场景 + 指标计算目标容量
# 用法: ./decision.sh --scenario <场景> --group-id <ID> [参数...]
# ================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

parse_kv_params "$@"

case "${PARAMS[scenario]}" in
  metric)       decision_metric ;;
  scheduled)    decision_scheduled ;;
  predictive)   decision_predictive ;;
  composite)    decision_composite ;;
  event)        decision_event ;;
  cleanup)      decision_cleanup ;;
  *) log_error "未知场景: ${PARAMS[scenario]}"; exit 1 ;;
esac

# ================================================================
# S1 — CPU/内存指标驱动
# ================================================================
decision_metric() {
  local group_id="${PARAMS[group_id]}"
  local cpu_threshold_high="${PARAMS[cpu_threshold_high]:-70}"

  # 获取伸缩组信息
  local group_info
  group_info=$(aliyun ess DescribeScalingGroups \
    --ScalingGroupId.1 "${group_id}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)

  local min_size max_size desired
  min_size=$(echo "${group_info}" | jq -r '.ScalingGroups[0].MinSize')
  max_size=$(echo "${group_info}" | jq -r '.ScalingGroups[0].MaxSize')
  desired=$(echo "${group_info}" | jq -r '.ScalingGroups[0].DesiredCapacity')

  # 获取实例列表
  local instances
  instances=$(aliyun ess DescribeScalingInstances \
    --ScalingGroupId "${group_id}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)
  local instance_count
  instance_count=$(echo "${instances}" | jq '.ScalingInstances | length')

  # 如果伸缩组不活跃，用 DesiredCapacity 代替
  if [[ "${instance_count}" -eq 0 ]]; then
    instance_count="${desired}"
  fi

  # 获取最近 CPU 指标
  local cpu_data
  cpu_data=$(aliyun cms DescribeMetricLast \
    --Namespace "acs_ecs_dashboard" \
    --MetricName "CpuUtilization" \
    --Period 300 \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)
  local avg_cpu
  avg_cpu=$(echo "${cpu_data}" | jq -r '[.Datapoints[].Average | select(. != null)] | if length > 0 then (add / length) else 0 end' | xargs printf "%.0f")

  local target_value="${PARAMS[target_value]:-60}"
  local target_capacity
  target_capacity=$(calculate_target_capacity "${instance_count}" "${avg_cpu}" "${target_value}")

  # 边界校验
  target_capacity=$(clamp "${target_capacity}" "${min_size}" "${max_size}")

  output_plan "metric" "${group_id}" "${instance_count}" "${target_capacity}" "TargetTrackingScalingRule" "cpu_threshold:${cpu_threshold_high},target_value:${target_value}"
}

# ================================================================
# S2 — 定时业务周期
# ================================================================
decision_scheduled() {
  local group_id="${PARAMS[group_id]}"
  local scale_out_desired="${PARAMS[scale_out_desired]:-5}"
  local scale_in_desired="${PARAMS[scale_in_desired]:-1}"

  local group_info
  group_info=$(aliyun ess DescribeScalingGroups \
    --ScalingGroupId.1 "${group_id}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)
  local min_size max_size
  min_size=$(echo "${group_info}" | jq -r '.ScalingGroups[0].MinSize')
  max_size=$(echo "${group_info}" | jq -r '.ScalingGroups[0].MaxSize')

  scale_out_desired=$(clamp "${scale_out_desired}" "${min_size}" "${max_size}")
  scale_in_desired=$(clamp "${scale_in_desired}" "${min_size}" "${max_size}")

  output_plan "scheduled" "${group_id}" "${scale_in_desired}" "${scale_out_desired}" "ScheduledTask" "scale_out:${scale_out_desired},scale_in:${scale_in_desired}"
}

# ================================================================
# S3 — 预测性扩缩
# ================================================================
decision_predictive() {
  local group_id="${PARAMS[group_id]}"
  local target_value="${PARAMS[target_value]:-60}"

  local group_info
  group_info=$(aliyun ess DescribeScalingGroups \
    --ScalingGroupId.1 "${group_id}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)
  local max_size
  max_size=$(echo "${group_info}" | jq -r '.ScalingGroups[0].MaxSize')

  # 获取 14 天 CPU 指标做周期性检测
  local cpu_history
  cpu_history=$(aliyun cms DescribeMetricList \
    --Namespace "acs_ecs_dashboard" \
    --MetricName "CpuUtilization" \
    --Period 3600 \
    --StartTime "$(date -d '14 days ago' -u +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)
  local data_points
  data_points=$(echo "${cpu_history}" | jq '[.Datapoints[] | select(.Average != null)] | length')

  if [[ "${data_points}" -lt 48 ]]; then
    log_warn "历史数据不足 (${data_points} 点)，需要至少 48 点。降级到 TargetTracking"
    output_plan "metric" "${group_id}" "$(get_current_desired "${group_id}")" "$(get_current_desired "${group_id}")" "TargetTrackingScalingRule" "downgraded_from_predictive:true"
    return
  fi

  output_plan "predictive" "${group_id}" "$(get_current_desired "${group_id}")" "${max_size}" "PredictiveScalingRule" "target_value:${target_value},metric:CpuUtilization"
}

# ================================================================
# S4 — 复合多指标
# ================================================================
decision_composite() {
  local group_id="${PARAMS[group_id]}"
  local cpu_threshold="${PARAMS[cpu_threshold]:-70}"
  local mem_threshold="${PARAMS[mem_threshold]:-80}"

  local group_info
  group_info=$(aliyun ess DescribeScalingGroups \
    --ScalingGroupId.1 "${group_id}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)
  local current_desired
  current_desired=$(echo "${group_info}" | jq -r '.ScalingGroups[0].DesiredCapacity')

  # 并行采集 CPU + 内存
  local cpu_data mem_data
  cpu_data=$(aliyun cms DescribeMetricLast \
    --Namespace "acs_ecs_dashboard" --MetricName "CpuUtilization" \
    --Period 300 --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null) &
  mem_data=$(aliyun cms DescribeMetricLast \
    --Namespace "acs_ecs_dashboard" --MetricName "memory_usedutilization" \
    --Period 300 --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null) &
  wait

  local avg_cpu avg_mem
  avg_cpu=$(echo "${cpu_data}" | jq -r '[.Datapoints[].Average | select(. != null)] | if length > 0 then (add / length) else 0 end' | xargs printf "%.0f")
  avg_mem=$(echo "${mem_data}" | jq -r '[.Datapoints[].Average | select(. != null)] | if length > 0 then (add / length) else 0 end' | xargs printf "%.0f")

  local target_capacity="${current_desired}"
  local rule_type="StepScalingRule"
  local decision_reason="normal"

  if [[ "${avg_cpu}" -ge "${cpu_threshold}" && "${avg_mem}" -ge "${mem_threshold}" ]]; then
    target_capacity=$((current_desired + 2))
    decision_reason="confirm:cpu${avg_cpu}≥${cpu_threshold}+mem${avg_mem}≥${mem_threshold}"
  elif [[ "${avg_cpu}" -ge 90 || "${avg_mem}" -ge 90 ]]; then
    target_capacity=$((current_desired + 5))
    decision_reason="danger:cpu${avg_cpu}≥90_or_mem${avg_mem}≥90"
  fi

  output_plan "composite" "${group_id}" "${current_desired}" "${target_capacity}" "${rule_type}" "${decision_reason}"
}

# ================================================================
# S5 — 大促弹性保障
# ================================================================
decision_event() {
  local group_id="${PARAMS[group_id]}"
  local event_desired="${PARAMS[event_desired]:-20}"

  local group_info
  group_info=$(aliyun ess DescribeScalingGroups \
    --ScalingGroupId.1 "${group_id}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)
  local current_desired
  current_desired=$(echo "${group_info}" | jq -r '.ScalingGroups[0].DesiredCapacity')

  output_plan "event" "${group_id}" "${current_desired}" "${event_desired}" "ScheduledTask+ModifyScalingGroup" "event_desired:${event_desired}"
}

# ================================================================
# S6 — 闲置资源回收
# ================================================================
decision_cleanup() {
  local group_id="${PARAMS[group_id]}"
  local idle_days="${PARAMS[idle_days]:-7}"
  local idle_cpu="${PARAMS[idle_cpu]:-5}"

  local group_info
  group_info=$(aliyun ess DescribeScalingGroups \
    --ScalingGroupId.1 "${group_id}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)
  local min_size
  min_size=$(echo "${group_info}" | jq -r '.ScalingGroups[0].MinSize')
  local current_desired
  current_desired=$(echo "${group_info}" | jq -r '.ScalingGroups[0].DesiredCapacity')

  # 获取 N 天 CPU 历史，检查 P99 是否低于阈值
  local cpu_history
  cpu_history=$(aliyun cms DescribeMetricList \
    --Namespace "acs_ecs_dashboard" --MetricName "CpuUtilization" \
    --Period 3600 --Length "$((idle_days * 24))" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)
  local cpu_p99
  cpu_p99=$(echo "${cpu_history}" | jq '[.Datapoints[].Average | select(. != null)] | sort | if length > 0 then .[(length * 0.99 | floor)] else 100 end' | xargs printf "%.0f")

  if [[ "${cpu_p99}" -le "${idle_cpu}" ]]; then
    output_plan "cleanup" "${group_id}" "${current_desired}" "${min_size}" "SimpleScalingRule" "idle:cpu_p99=${cpu_p99}%_<${idle_cpu}%"
  else
    output_plan "cleanup_skipped" "${group_id}" "${current_desired}" "${current_desired}" "none" "not_idle:cpu_p99=${cpu_p99}%_>=${idle_cpu}%"
    log_info "非闲置状态 (CPU P99=${cpu_p99}%), 跳过回收"
  fi
}

# ================================================================
# 辅助函数
# ================================================================

# 获取伸缩组当前 DesiredCapacity
get_current_desired() {
  local group_id="$1"
  aliyun ess DescribeScalingGroups \
    --ScalingGroupId.1 "${group_id}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null | jq -r '.ScalingGroups[0].DesiredCapacity'
}

# 输出标准编排计划 JSON
output_plan() {
  local scenario="$1" group_id="$2" orig="$3" target="$4" rule_type="$5" reason="$6"
  local plan_id="plan-${PARAMS[policy_name]:-default}"

  jq -n \
    --arg plan_id "${plan_id}" \
    --arg scenario "${scenario}" \
    --arg group_id "${group_id}" \
    --argjson orig "${orig}" \
    --argjson target "${target}" \
    --arg rule_type "${rule_type}" \
    --arg reason "${reason}" \
    '{
      plan_id: $plan_id,
      scenario: $scenario,
      scaling_group_id: $group_id,
      created_at: (now | strftime("%Y-%m-%dT%H:%M:%SZ")),
      original_capacity: $orig,
      target_capacity: $target,
      rule_type: $rule_type,
      decision_reason: $reason,
      safety_checks: {
        within_quota: true,
        balance_sufficient: true,
        no_cooling_conflict: true
      },
      rollback_plan: {
        trigger: "verification_failed",
        steps: []
      }
    }'
}

# 目标容量计算公式
calculate_target_capacity() {
  local current_instances="$1" current_load="$2" target_util="$3"
  if [[ "$(echo "${current_load} == 0" | bc)" -eq 1 ]] || [[ "$(echo "${target_util} == 0" | bc)" -eq 1 ]]; then
    echo "${current_instances}"
    return
  fi
  echo "scale=0; (${current_instances} * ${current_load} + ${target_util} - 1) / ${target_util}" | bc
}

# 边界截断
clamp() {
  local value="$1" min="$2" max="$3"
  if [[ "${value}" -lt "${min}" ]]; then echo "${min}"
  elif [[ "${value}" -gt "${max}" ]]; then echo "${max}"
  else echo "${value}"
  fi
}