---
runbook_id: "09"
scenario: "弹性伸缩性能优化"
version: "1.0.0"
last_updated: "2026-06-07"
trigger: "aiops-cruise 容量巡检预测 7 天内资源不足 / CMS 持续高负载 / 人工触发"
risk_level: "中"
execution_time_estimate: "3-10 分钟"
---

> **脚本**: [`runbooks/scripts/auto-scaling-optimization.py`](scripts/auto-scaling-optimization.py) — 全自动执行本 runbook

# 弹性伸缩性能优化

## 1. 场景描述

当容量规划预测资源将在 7 天内不足，或 ECS/ACK 节点持续高负载时，采集性能趋势、评估扩容/缩容方案，联动 `auto-scaling-orch` 决策引擎生成扩缩容计划。**本 runbook 是评估决策层，只出建议不自动执行。**

### 🚨 安全铁律

| 红线 | 要求 |
|---|---|
| **任何资源的删除/停止/规格变更** | ❌ 不允许自动执行，报告只出建议 |
| **输出 AK/SK** | ❌ 必须掩码为 `AKID****SKRET` |
| **扩缩容执行** | 🔴 [SUGGESTED] 所有扩缩容操作需用户确认后执行 |
| **安全组规则增删** | ❌ 不允许自动执行 |
| **读取型操作** | 🟢 [AUTO-QUIET] 自动执行 |

### 🧠 提示知识力

> **弹性伸缩的核心原则：**
>
> 1. **扩容优先于缩容** —— 扩容风险低（最多多花点钱），缩容风险高（影响了就回不来）
> 2. **熔断机制** —— 24h 内扩缩超过 5 次应触发熔断，防止"震荡"
> 3. **目标利用率法** —— 不是 CPU > 80% 就扩，而是"目标利用率 = 60%"：
>    - 扩：`ceil(当前实例数 × 当前负载 / 目标利用率)`
>    - 缩：`floor(当前实例数 × 当前负载 / 目标利用率)`，且缩后仍有 1.5x 缓冲
>
> **与 auto-scaling-orch 的关系：**
> - `auto-scaling-orch` 是**执行层**，直接调用 ess-ops/ack-ops 执行扩缩容
> - 本 runbook 是**评估层**，做趋势分析 + 决策建议，输出 plan.json
> - 用户审批 plan.json 后，手动/自动委托 `auto-scaling-orch` 执行

### 适用条件

- ECS（弹性伸缩组 ESS）或 ACK（节点池）集群
- 有 7 天以上的 CMS 历史指标数据
- aliyun CLI 已配置且具有 CMS 只读权限

### 不适用条件

- 无历史数据的新建集群
- 无需扩容/缩容的正常负载
- 需要立即执行扩缩容 → 委托 `auto-scaling-orch` 或 `ess-ops`

---

## 2. 执行流程

### Phase 0: 前置安全门

```bash
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" || { echo "[ERROR] AK_ID 未设置"; exit 1; }
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" || { echo "[ERROR] AK_SK 未设置"; exit 1; }
command -v aliyun >/dev/null 2>&1 || { echo "[ERROR] aliyun CLI 未安装"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "[ERROR] jq 未安装"; exit 1; }

CUSTOMER="{{user.customer_name}}"
REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
echo "[INFO] 客户: $CUSTOMER | 区域: $REGION"

# 诊断窗口：30 天趋势 + 6h 实时
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
D7_START=$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)
D30_START=$(date -u -v-30d +%Y-%m-%dT%H:%M:%SZ)
H6_START=$(date -u -v-6H +%Y-%m-%dT%H:%M:%SZ)
echo "[INFO] 趋势窗口: 30d / 7d / 6h"
```

### Phase 1: 资源扫描 + 历史趋势采集

```bash
RG_ID="{{user.resource_group_id}}"
TAG_KEY="{{user.tag_key}}"
TAG_VALUE="{{user.tag_value}}"

# ── ECS 资源扫描 ──
if [ -n "$RG_ID" ]; then
  ECS_LIST=$(aliyun ecs DescribeInstances --RegionId "$REGION" \
    --ResourceGroupId "$RG_ID" --PageSize 100 | jq '.Instances.Instance')
  ESS_LIST=$(aliyun ess DescribeScalingGroups --RegionId "$REGION" \
    --PageSize 50 | jq --arg rg "$RG_ID" \
    '[.ScalingGroups.ScalingGroup[] | select(.ResourceGroupId == $rg)]')
elif [ -n "$TAG_KEY" ]; then
  ECS_LIST=$(aliyun ecs DescribeInstances --RegionId "$REGION" \
    --Tag.1.Key "$TAG_KEY" --Tag.1.Value "$TAG_VALUE" --PageSize 100 \
    | jq '.Instances.Instance')
  ESS_LIST="[]"
else
  echo "[ERROR] 必须提供资源组ID或标签"; exit 1
fi

ECS_COUNT=$(echo "$ECS_LIST" | jq 'length')
ESS_COUNT=$(echo "$ESS_LIST" | jq 'length')
echo "[INFO] ECS: $ECS_COUNT 台 | ESS 伸缩组: $ESS_COUNT 个"

# ── 采集 7 天 CPU 趋势（并行批量拉取）──
END_TS=$(date +%s)
echo "[INFO] 采集 7 天 CPU 趋势..."

for INST_ID in $(echo "$ECS_LIST" | jq -r '.[].InstanceId // empty'); do
  INST_TYPE=$(echo "$ECS_LIST" | jq -r --arg id "$INST_ID" \
    '.[] | select(.InstanceId == $id) | .InstanceType // "unknown"')
  INST_NAME=$(echo "$ECS_LIST" | jq -r --arg id "$INST_ID" \
    '.[] | select(.InstanceId == $id) | .InstanceName // $id')

  # 7 天 CPU 平均
  CPU_7D_AVG=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 3600 \
    --StartTime "$D7_START" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')

  # 7 天 CPU 峰值
  CPU_7D_PEAK=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 300 \
    --StartTime "$D7_START" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  # 内存 7 天平均
  MEM_7D_AVG=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName memory_usage \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 3600 \
    --StartTime "$D7_START" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')

  echo "  ECS $INST_NAME ($INST_TYPE): CPU 平均=${CPU_7D_AVG}% / 峰值=${CPU_7D_PEAK}% / 内存=${MEM_7D_AVG}%"

  # 存入趋势数据后续分析
done
```

#### Step 1.2: 30 天趋势预测（线性外推）

```bash
echo ""
echo "── 30 天趋势预测 ──"

for INST_ID in $(echo "$ECS_LIST" | jq -r '.[].InstanceId // empty'); do
  # 采集 30 天每天峰值 CPU，用于线性预测
  CPU_30D=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 86400 \
    --StartTime "$D30_START" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum]')

  POINTS=$(echo "$CPU_30D" | jq 'length')
  if [ "$POINTS" -lt 7 ]; then
    echo "  ECS $INST_ID: 数据不足 (${POINTS}点)，跳过预测"
    continue
  fi

  # 简单线性回归：取最近 7 个数据点计算趋势
  RECENT=$(echo "$CPU_30D" | jq '.[-7:]')
  FIRST=$(echo "$RECENT" | jq '.[0]')
  LAST=$(echo "$RECENT" | jq '.[-1]')
  DAILY_CHANGE=$(echo "scale=2; ($LAST - $FIRST) / 7" | bc 2>/dev/null || echo "0")

  if [ "$(echo "$DAILY_CHANGE > 0" | bc -l 2>/dev/null)" = "1" ]; then
    DAYS_TO_80=$(echo "scale=0; (80 - $LAST) / $DAILY_CHANGE" | bc 2>/dev/null || echo "永不")
    echo "  ECS $INST_ID: 最近7天 CPU $FIRST% → $LAST%, 日增 ${DAILY_CHANGE}%/天, 预计 ${DAYS_TO_80} 天后达 80%"
    
    if [ "$(echo "$DAYS_TO_80 < 7" | bc -l 2>/dev/null)" = "1" ]; then
      echo "  🔴 7 天内达阈值! 建议立即规划扩容"
    elif [ "$(echo "$DAYS_TO_80 < 30" | bc -l 2>/dev/null)" = "1" ]; then
      echo "  🟡 30 天内达阈值，建议纳入容量规划"
    fi
  elif [ "$(echo "$LAST < 20" | bc -l 2>/dev/null)" = "1" ] && [ "$(echo "$DAILY_CHANGE < 0" | bc -l 2>/dev/null)" = "1" ]; then
    echo "  ℹ️ ECS $INST_ID: 持续低负载 (CPU=${LAST}%), 建议评估缩容"
  else
    echo "  ✅ ECS $INST_ID: 负载平稳"
  fi
done
```

### Phase 2: 熔断检查 + 决策评估

#### Step 2.1: 熔断检查

```bash
echo ""
echo "═══ 熔断检查 ═══"

# 1. 检查 ESS 伸缩活动历史（24h 内扩缩次数）
for SG_ID in $(echo "$ESS_LIST" | jq -r '.[].ScalingGroupId // empty'); do
  SG_NAME=$(echo "$ESS_LIST" | jq -r --arg id "$SG_ID" \
    '.[] | select(.ScalingGroupId == $id) | .ScalingGroupName // $id')

  SCALING_ACTIVITIES=$(aliyun ess DescribeScalingActivities \
    --RegionId "$REGION" \
    --ScalingGroupId "$SG_ID" \
    --PageSize 50 2>/dev/null \
    | jq --arg h24 "$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)" \
    '[.ScalingActivities.ScalingActivity[] | select(.StartTime >= $h24)] | length')

  echo "  ESS $SG_NAME: 24h 内伸缩活动 ${SCALING_ACTIVITIES} 次"

  if [ "$SCALING_ACTIVITIES" -ge 5 ]; then
    echo "  🔴 触发熔断! 24h 内扩缩 5+ 次，建议暂停自动伸缩并排查震荡原因"
    FUSE_TRIGGERED="YES"
  fi

  # 2. 检查当前实例数 vs 最大实例数
  MIN_SIZE=$(echo "$ESS_LIST" | jq -r --arg id "$SG_ID" \
    '.[] | select(.ScalingGroupId == $id) | .MinSize // 0')
  MAX_SIZE=$(echo "$ESS_LIST" | jq -r --arg id "$SG_ID" \
    '.[] | select(.ScalingGroupId == $id) | .MaxSize // 0')
  CURRENT_CAPACITY=$(echo "$ESS_LIST" | jq -r --arg id "$SG_ID" \
    '.[] | select(.ScalingGroupId == $id) | .ActiveCapacity // 0')

  echo "  当前: ${CURRENT_CAPACITY} | 最小: ${MIN_SIZE} | 最大: ${MAX_SIZE}"
  
  if [ "$CURRENT_CAPACITY" -ge "$MAX_SIZE" ] && [ "$MAX_SIZE" -gt 0 ]; then
    echo "  🟡 已达最大实例数 $MAX_SIZE，扩容需先调整伸缩组上限"
    AT_MAX_CAPACITY="YES"
  fi
done

# 3. 检查余额（快速检查）
BALANCE=$(aliyun bssopenapi QueryAccountBalance 2>/dev/null \
  | jq -r '.Data.AvailableAmount // "0"')
echo "  账户余额: ¥${BALANCE}"
```

#### Step 2.2: 决策引擎 — 生成扩缩容计划

```bash
echo ""
echo "═══ 扩缩容评估计划 ═══"

SCALE_PLANS="[]"

for INST_ID in $(echo "$ECS_LIST" | jq -r '.[].InstanceId // empty'); do
  # 最近 1h CPU 峰值
  CPU_1H_PEAK=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 300 \
    --StartTime "$H6_START" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  INST_TYPE=$(echo "$ECS_LIST" | jq -r --arg id "$INST_ID" \
    '.[] | select(.InstanceId == $id) | .InstanceType // "unknown"')

  # 扩容条件：CPU > 75% 持续高负载
  if [ "$(echo "$CPU_1H_PEAK > 75" | bc -l 2>/dev/null)" = "1" ] && [ "$FUSE_TRIGGERED" != "YES" ]; then
    TARGET_UTIL=60  # 目标利用率 60%
    CURRENT_INSTANCES=$(echo "$ESS_LIST" | jq -r \
      '.[] | select(.ScalingGroupName != null) | .ActiveCapacity // 1')
    TARGET_COUNT=$(echo "scale=0; ($CURRENT_INSTANCES * $CPU_1H_PEAK / $TARGET_UTIL + 0.5) / 1" | bc)

    PLAN=$(cat <<PLAN_JSON
{
  "instance_id": "$INST_ID",
  "instance_type": "$INST_TYPE",
  "action": "scale_out",
  "reason": "CPU 峰值 ${CPU_1H_PEAK}% > 75%，目标利用率 ${TARGET_UTIL}%",
  "current_instances": ${CURRENT_INSTANCES},
  "target_instances": ${TARGET_COUNT},
  "increase": $((TARGET_COUNT - CURRENT_INSTANCES)),
  "estimated_cost_increase": "请参考 billing-ops 评估",
  "risk": "低",
  "auto_scaling_orch_scenario": "S1"
}
PLAN_JSON
)
    SCALE_PLANS=$(echo "$SCALE_PLANS" | jq --argjson plan "$PLAN" '. + [$plan]')
    echo "  🔴 [SCALE_OUT] $INST_TYPE CPU=$CPU_1H_PEAK% → 建议扩容: ${CURRENT_INSTANCES} → ${TARGET_COUNT} 台"

  # 缩容条件：CPU < 20% 持续低负载
  elif [ "$(echo "$CPU_1H_PEAK < 20" | bc -l 2>/dev/null)" = "1" ] && [ "$FUSE_TRIGGERED" != "YES" ]; then
    CURRENT_INSTANCES=$(echo "$ESS_LIST" | jq -r \
      '.[] | select(.ScalingGroupName != null) | .ActiveCapacity // 1')
    # 缩容后至少留 1.5x 缓冲
    SAFE_COUNT=$(echo "scale=0; ($CURRENT_INSTANCES * $CPU_1H_PEAK * 1.5 / 20 + 0.5) / 1" | bc)
    [ "$SAFE_COUNT" -lt 1 ] && SAFE_COUNT=1

    if [ "$SAFE_COUNT" -lt "$CURRENT_INSTANCES" ]; then
      PLAN=$(cat <<PLAN_JSON
{
  "instance_id": "$INST_ID",
  "instance_type": "$INST_TYPE",
  "action": "scale_in",
  "reason": "CPU 峰值 ${CPU_1H_PEAK}% < 20% 持续低负载",
  "current_instances": ${CURRENT_INSTANCES},
  "target_instances": ${SAFE_COUNT},
  "decrease": $((CURRENT_INSTANCES - SAFE_COUNT)),
  "estimated_cost_saving": "请参考 billing-ops 评估",
  "risk": "中",
  "auto_scaling_orch_scenario": "S6"
}
PLAN_JSON
)
      SCALE_PLANS=$(echo "$SCALE_PLANS" | jq --argjson plan "$PLAN" '. + [$plan]')
      echo "  🟢 [SCALE_IN] $INST_TYPE CPU=$CPU_1H_PEAK% → 建议缩容: ${CURRENT_INSTANCES} → ${SAFE_COUNT} 台"
    fi
  else
    echo "  ✅ $INST_TYPE: 负载正常 (CPU=${CPU_1H_PEAK}%)"
  fi
done

PLAN_COUNT=$(echo "$SCALE_PLANS" | jq 'length')
echo ""
echo "[INFO] 共生成 $PLAN_COUNT 个扩缩容计划"
```

### Phase 3: 报告

**Markdown:**

```markdown
═══════════════════════════════════════════════════════
  📈 弹性伸缩性能优化报告
═══════════════════════════════════════════════════════
  报告ID: scaling-opt-$CUSTOMER-$(date +%Y%m%dT%H%M%SZ)
  客户: $CUSTOMER | 区域: $REGION | 时间: $(date)
  窗口: 30d 趋势 + 6h 实时
═══════════════════════════════════════════════════════

## 📊 总览

| 维度 | 结果 |
|------|------|
| ECS 实例数 | ${ECS_COUNT} |
| ESS 伸缩组 | ${ESS_COUNT} |
| 熔断状态 | ${FUSE_TRIGGERED:-正常} |
| 已到最大容量 | ${AT_MAX_CAPACITY:-否} |
| 账户余额 | ¥${BALANCE} |

## 📋 扩缩容计划

| # | 实例 | 当前 CPU | 建议操作 | 当前→目标 | 对应场景 |
|:-:|:-----|:--------:|:--------:|:---------:|:--------:|
| 1 | ${INST_TYPE} | ${CPU_1H_PEAK}% | SCALE_OUT | ${CURRENT}→${TARGET} 台 | S1 CPU指标驱动 |

## 🔴 熔断与风险检查

${FUSE_CHECK_REPORT}

## 📌 执行建议

${EXECUTION_SUGGESTIONS}

## 💰 成本影响

- 扩容估算: 请运行 billing-ops 评估新增实例的费用
- 缩容估算: 请运行 billing-ops 评估释放实例的节省

═══════════════════════════════════════════════════════
  审计追踪
═══════════════════════════════════════════════════════
  JSON: audit-results/scaling-opt-$CUSTOMER-$(date +%Y%m%d).json
  耗时: $EXECUTION_DURATION | runbook: v1.0.0
```

**JSON:**

```json
{
  "report_id": "scaling-opt-${CUSTOMER}-$(date +%Y%m%dT%H%M%SZ)",
  "scenario": "auto_scaling_optimization",
  "runbook_version": "1.0.0",
  "resource_summary": {
    "ecs_count": ${ECS_COUNT},
    "ess_groups": ${ESS_COUNT}
  },
  "fuse_check": {
    "fuse_triggered": "${FUSE_TRIGGERED:-false}",
    "at_max_capacity": "${AT_MAX_CAPACITY:-false}",
    "balance": "${BALANCE}"
  },
  "scale_plans": ${SCALE_PLANS:-[]},
  "suggestions": []
}
```

---

## 3. 阈值速查

| 指标 | 触发扩容 | 触发缩容 | 说明 |
|------|:--------:|:--------:|------|
| CPU 使用率 | > 75% 持续 10min | < 20% 持续 30min | 主判定指标 |
| 内存使用率 | > 80% | < 40% | 辅助指标 |
| SLB 健康检查失败 | > 0 | — | 扩容的补充信号 |
| 每日扩缩次数 | — | — | ≥ 5 次/24h 触发熔断 |
| 余额 | < ¥500 | — | 余额不足暂停扩缩 |
| 最大实例数 | 达到上限无法扩容 | — | 需先调整伸缩组上限 |

---

## 4. 改进闭环

| 反馈来源 | 触发条件 | 改进动作 | 责任人 |
|----------|---------|---------|--------|
| 误判扩缩 | 扩容后负载未降 / 缩容后负载飙升 | 调整目标利用率 / 增加预热期 | 运维负责人 |
| 熔断误触 | 正常的业务高峰被熔断 | 提升熔断阈值(5次/24h→8次) | 运维负责人 |
| 漏判 | 新增 ACK 节点池未纳入评估 | 增加 ACK 节点池扫描 | Agent 维护者 |

---

## 5. Changelog

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 1.0.0 | 2026-06-07 | 初始版本 |