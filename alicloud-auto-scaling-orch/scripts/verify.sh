#!/bin/bash
# ================================================================
# 验证引擎 — 扩缩容后验证结果
# 用法: ./verify.sh --group-id <ID> --plan-json <JSON> [选项]
# ================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

parse_kv_params "$@"

GROUP_ID="${PARAMS[group_id]}"
PLAN_JSON="${PARAMS[plan_json]}"
TRACE_ID="${PARAMS[trace_id]:-trace-unknown}"
TARGET_CAPACITY=$(echo "${PLAN_JSON}" | jq -r '.target_capacity // empty')

# ── 验证检查项 ──
declare -a CHECKS=()

# 检查 1: 伸缩活动状态
check_activity() {
  local activities
  activities=$(aliyun ess DescribeScalingActivities \
    --ScalingGroupId "${GROUP_ID}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" \
    --PageNumber 1 --PageSize 3 2>/dev/null)
  local status
  status=$(echo "${activities}" | jq -r '.ScalingActivities[0].StatusCode // "unknown"')

  if [[ "${status}" == "Success" ]]; then
    CHECKS+=("$(make_check "activity_completed" true "${status}" "Success")")
  else
    CHECKS+=("$(make_check "activity_completed" false "${status}" "Success")")
  fi
}

# 检查 2: 实例数量
check_instance_count() {
  local instances
  instances=$(aliyun ess DescribeScalingInstances \
    --ScalingGroupId "${GROUP_ID}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)
  local count
  count=$(echo "${instances}" | jq '.ScalingInstances | length')

  if [[ "${count}" -eq "${TARGET_CAPACITY}" ]]; then
    CHECKS+=("$(make_check "instance_count" true "${count}" "${TARGET_CAPACITY}")")
  else
    CHECKS+=("$(make_check "instance_count" false "${count}" "${TARGET_CAPACITY}")")
  fi
}

# 检查 3: 实例健康状态
check_instance_health() {
  local instances
  instances=$(aliyun ess DescribeScalingInstances \
    --ScalingGroupId "${GROUP_ID}" \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)
  local unhealthy
  unhealthy=$(echo "${instances}" | jq '[.ScalingInstances[] | select(.HealthStatus != "Healthy")] | length')

  if [[ "${unhealthy}" -eq 0 ]]; then
    CHECKS+=("$(make_check "instance_health" true "0_unhealthy" "0_unhealthy")")
  else
    CHECKS+=("$(make_check "instance_health" false "${unhealthy}_unhealthy" "0_unhealthy")")
  fi
}

# 检查 4: CPU 回归
check_cpu_regression() {
  local cpu_data
  cpu_data=$(aliyun cms DescribeMetricLast \
    --Namespace "acs_ecs_dashboard" \
    --MetricName "CpuUtilization" \
    --Period 300 \
    --RegionId "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null)
  local avg_cpu
  avg_cpu=$(echo "${cpu_data}" | jq -r '[.Datapoints[].Average | select(. != null)] | if length > 0 then (add / length) else 0 end' | xargs printf "%.0f")

  if [[ -n "${avg_cpu}" ]] && [[ "${avg_cpu}" -lt 70 ]]; then
    CHECKS+=("$(make_check "cpu_regression" true "${avg_cpu}%" "<70%")")
  else
    CHECKS+=("$(make_check "cpu_regression" false "${avg_cpu}%" "<70%")")
  fi
}

# 执行验证
check_activity || true
check_instance_count || true
check_instance_health || true
check_cpu_regression || true

# ── 输出验证结果 ──
ALL_PASSED=true
for check in "${CHECKS[@]}"; do
  PASSED=$(echo "${check}" | jq -r '.passed')
  if [[ "${PASSED}" != "true" ]]; then
    ALL_PASSED=false
    break
  fi
done

STATUS="passed"
if [[ "${ALL_PASSED}" != "true" ]]; then
  STATUS="failed"
fi

jq -n \
  --arg status "${STATUS}" \
  --argjson checks "$(printf '%s\n' "${CHECKS[@]}" | jq -s '.')" \
  '{
    status: $status,
    checks: $checks,
    verified_at: (now | strftime("%Y-%m-%dT%H:%M:%SZ"))
  }'