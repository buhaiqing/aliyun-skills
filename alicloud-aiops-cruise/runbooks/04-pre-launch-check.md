---
runbook_id: "04"
scenario: "大促前全链路预检"
version: "1.0.0"
last_updated: "2026-06-06"
trigger: "人工触发（大促前 3-7 天）"
risk_level: "高"
execution_time_estimate: "10-20 分钟"
---

> **脚本**: [`runbooks/scripts/pre-launch-check.py`](scripts/pre-launch-check.py) — 全自动执行本 runbook

# 大促前全链路预检

## 1. 场景描述

### 🚨 安全铁律

| 红线 | 要求 |
|---|---|
| **任何资源的删除/停止/规格变更** | ❌ 不允许自动执行，报告只出建议 |
| **输出 AK/SK** | ❌ 必须掩码为 `AKID****SKRET` |
| **安全组规则增删** | ❌ 不允许自动执行 |

**底线**：本 skill 是纯读（Read-Only）巡检，不执行任何写操作。所有建议需用户确认后执行。

在大促/高峰流量前，对全链路做压力前置检查，确保所有资源有余量应对 2-3 倍日常流量。与容量规划的区别：容量规划看**趋势**，大促预检做**压力模拟**。

---

## 2. 执行流程

### Phase 1: 拓扑发现

同日常巡检（快扫）。额外采集最近 30 天业务高峰期的指标作为流量基线。

### Phase 2: 基线采集 + 压力模拟

```bash
CUSTOMER="{{user.customer_name}}"
REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
MULTIPLIER="{{user.traffic_multiplier}}"  # 默认 3.0

# 采集最近 30 天日间高峰（10:00-11:00, 14:00-16:00）的峰值作为基线
echo "[DIAG] 开始采集流量基线（最近 30 天日间高峰）..."

# ECS 峰值
for INST_ID in $(aliyun ecs DescribeInstances --RegionId "$REGION" --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" | jq -r '.Instances.Instance[].InstanceId'); do
  INST_TYPE=$(aliyun ecs DescribeInstances --RegionId "$REGION" --InstanceIds "[\"$INST_ID\"]" | jq -r '.Instances.Instance[0].InstanceType')
  
  # ECS CPU 峰值
  CPU_BASELINE=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 3600 \
    --StartTime "$(date -u -v-30d +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  # 规格上限（简化：从实例类型推断）
  # 完整规格速查见 references/threshold-definitions.md
  
  STRESS=$(echo "$CPU_BASELINE * $MULTIPLIER" | bc -l)
  
  echo "[DIAG] ECS $INST_ID($INST_TYPE): 基线CPU峰值=${CPU_BASELINE}% ×${MULTIPLIER}=${STRESS}%"
  
  if [ "$(echo "$STRESS > 80" | bc -l 2>/dev/null)" = "1" ]; then
    echo "[WARN] ⚠️ $INST_ID 压力模拟 CPU 将达 ${STRESS}%（超 80%）→ 建议升配"
  else
    echo "[OK] ✅ $INST_ID 余量充足"
  fi
done

# SLB 并发峰值
for LB_ID in $(aliyun slb DescribeLoadBalancers --RegionId "$REGION" --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" | jq -r '.LoadBalancers.LoadBalancer[].LoadBalancerId'); do
  CONN_BASELINE=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName ActiveConnection \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 3600 \
    --StartTime "$(date -u -v-30d +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  # SLB 规格上限从 threshold-definitions 查
  MAX_CONN=50000  # 默认性能保障型1的 50000
  STRESS_CONN=$(echo "$CONN_BASELINE * $MULTIPLIER" | bc -l | xargs printf "%.0f")
  
  echo "[DIAG] SLB $LB_ID: 基线并发=${CONN_BASELINE} ×${MULTIPLIER}=${STRESS_CONN} 规格上限=${MAX_CONN}"
  
  if [ "$STRESS_CONN" -gt "$MAX_CONN" ]; then
    echo "[WARN] ⚠️ SLB $LB_ID 压力模拟并发=$STRESS_CONN > 上限$MAX_CONN → 建议升配SLB规格"
  fi
done

# RDS 峰值
for DB_ID in $(aliyun rds DescribeDBInstances --RegionId "$REGION" --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" | jq -r '.Items.DBInstance[].DBInstanceId'); do
  RDS_CPU_BASELINE=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName CpuUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 3600 \
    --StartTime "$(date -u -v-30d +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  STRESS_RDS_CPU=$(echo "$RDS_CPU_BASELINE * $MULTIPLIER" | bc -l)
  
  echo "[DIAG] RDS $DB_ID: 基线CPU峰值=${RDS_CPU_BASELINE}% ×${MULTIPLIER}=${STRESS_RDS_CPU}%"
done

# Redis 峰值
for REDIS_ID in $(aliyun r-kvstore DescribeInstances --RegionId "$REGION" --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" | jq -r '.Instances.KVStoreInstance[].InstanceId'); do
  REDIS_MEM_BASELINE=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName memory_usage \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 3600 \
    --StartTime "$(date -u -v-30d +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  STRESS_MEM=$(echo "$REDIS_MEM_BASELINE * $MULTIPLIER" | bc -l)
  
  echo "[DIAG] Redis $REDIS_ID: 基线内存峰值=${REDIS_MEM_BASELINE}% ×${MULTIPLIER}=${STRESS_MEM}%"
done
```

### Phase 3: 报告

```markdown
═══════════════════════════════════════
  大促前全链路预检报告
═══════════════════════════════════════
  客户: $CUSTOMER
  预估流量: ${MULTIPLIER}x 日常峰值
  基线周期: 最近 30 天日间高峰
═══════════════════════════════════════

## ✅ 余量充足
  ECS CPU:  基线 25% ×3 = 75% < 80% → 合格
  磁盘 IOPS: 基线 3115 ×3 = 9345 < 50000 → 合格
  Redis:    基线 45% ×3 = 135% → ⚠️ 超 85%

## ⚠️ 建议升配
  SLB 并发:  基线 3500 ×3 = 10500 > 上限 5000 → 建议升配 SLB 规格
  RDS CPU:  基线 68% ×3 = 204% > 85% → 建议升配或读写分离
  Redis:    基线 45% ×3 = 135% > 85% → 建议升配规格

## 📋 升配优先级（推荐）
  1. SLB 升配（入口层，最先受影响）
  2. RDS 升配或开启只读实例（数据层最易瓶颈）
  3. Redis 升配（缓存层）