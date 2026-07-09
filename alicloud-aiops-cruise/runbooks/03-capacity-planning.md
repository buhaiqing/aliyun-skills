---
runbook_id: "03"
scenario: "容量规划检查"
version: "1.0.0"
last_updated: "2026-06-06"
trigger: "每周定时 / 人工触发"
risk_level: "中"
execution_time_estimate: "5-10 分钟"
---

> **脚本**: [`runbooks/scripts/capacity-planning.py`](scripts/capacity-planning.py) — 全自动执行本 runbook

# 容量规划检查

## 1. 场景描述

评估未来 30-90 天的资源是否充足，提前发现扩容需求。关注**趋势**而非瞬时状态。

### [ALERT] 安全铁律

| 红线 | 要求 |
|---|---|
| **任何资源的删除/停止/规格变更** | FAIL 不允许自动执行，报告只出建议 |
| **输出 AK/SK** | FAIL 必须掩码为 `AKID****SKRET` |
| **安全组规则增删** | FAIL 不允许自动执行 |

**底线**：本 skill 是纯读（Read-Only）巡检，不执行任何写操作。所有建议需用户确认后执行。

### [NOTE] 提示知识力

> **容量规划不是"现在够不够"，而是"什么时候不够"。**
>
> 日常巡检关注瞬时水位（CPU 现在 80% 就是 Warning），容量规划关注**增长率**（磁盘每周涨 5%，6 周后达 90% = Critical）。
>
> **核心公式**：`预估达阈值天数 = (阈值 - 当前值) / 日均增长率`
> Agent 可以用简单的线性回归估算，不需要复杂算法。
>
> **常见的容量陷阱：**
> - 磁盘容量：增长通常不是线性的（月底/季末有峰谷），但线性近似已经足够做预警
> - 内存：如果应用有内存泄漏，增长率会比线性更陡峭
> - IOPS：和业务请求量正相关，需要结合 SLB QPS 趋势一起看

---

## 2. 执行流程

### Phase 1: 拓扑发现

同日常巡检（`runbooks/01-daily-health-check.md Phase 1`），快扫快速结束。

### Phase 2: 采集 7 天指标

```bash
CUSTOMER="{{user.customer_name}}"
REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"

# 计算时间窗口（最近 7 天，1h 粒度）
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START_TIME=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)

# 为每个 ECS 采集 7 天磁盘趋势
for INST_ID in $(aliyun ecs DescribeInstances --RegionId "$REGION" --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" | jq -r '.Instances.Instance[].InstanceId'); do
  DISK_7D=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName DiskUsage \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 3600 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [{"time": .Timestamp, "value": .Average}]')
  
  # 计算日均增长率
  FIRST_VAL=$(echo "$DISK_7D" | jq '.[0].value // 0')
  LAST_VAL=$(echo "$DISK_7D" | jq '.[-1].value // 0')
  DAILY_GROWTH=$(echo "scale=2; ($LAST_VAL - $FIRST_VAL) / 7" | bc 2>/dev/null || echo "0")
  
  echo "[DIAG] ECS $INST_ID: 磁盘 7天前=$FIRST_VAL% -> 现在=$LAST_VAL% 日均增长=$DAILY_GROWTH%/天"
done

# RDS 磁盘趋势
for DB_ID in $(aliyun rds DescribeDBInstances --RegionId "$REGION" --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" | jq -r '.Items.DBInstanceInstance[].DBInstanceId'); do
  RDS_DISK_7D=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName DiskUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 3600 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [{"time": .Timestamp, "value": .Average}]')
  
  FIRST_VAL=$(echo "$RDS_DISK_7D" | jq '.[0].value // 0')
  LAST_VAL=$(echo "$RDS_DISK_7D" | jq '.[-1].value // 0')
  DAILY_GROWTH=$(echo "scale=2; ($LAST_VAL - $FIRST_VAL) / 7" | bc 2>/dev/null || echo "0")
  
  echo "[DIAG] RDS $DB_ID: 磁盘 7天前=$FIRST_VAL% -> 现在=$LAST_VAL% 日均增长=$DAILY_GROWTH%/天"
done

# Redis 内存趋势
for REDIS_ID in $(aliyun r-kvstore DescribeInstances --RegionId "$REGION" --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" | jq -r '.Instances.KVStoreInstance[].InstanceId'); do
  REDIS_MEM_7D=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName memory_usage \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 3600 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [{"time": .Timestamp, "value": .Average}]')
  
  FIRST_VAL=$(echo "$REDIS_MEM_7D" | jq '.[0].value // 0')
  LAST_VAL=$(echo "$REDIS_MEM_7D" | jq '.[-1].value // 0')
  DAILY_GROWTH=$(echo "scale=2; ($LAST_VAL - $FIRST_VAL) / 7" | bc 2>/dev/null || echo "0")
  
  echo "[DIAG] Redis $REDIS_ID: 内存 7天前=$FIRST_VAL% -> 现在=$LAST_VAL% 日均增长=$DAILY_GROWTH%/天"
done
```

### Phase 3: 容量预测

```bash
# 线性预测函数：预测达到阈值需要多少天
predict_days() {
  local current=$1 growth=$2 threshold=$3
  if [ "$(echo "$growth <= 0" | bc -l 2>/dev/null)" = "1" ]; then
    echo "无风险（平稳或下降）"
    return
  fi
  days_needed=$(echo "scale=0; ($threshold - $current) / $growth" | bc 2>/dev/null)
  if [ "$(echo "$days_needed < 30" | bc -l 2>/dev/null)" = "1" ]; then
    echo "[WARN] 将在 ${days_needed} 天后达阈值（$threshold%）"
  elif [ "$(echo "$days_needed < 90" | bc -l 2>/dev/null)" = "1" ]; then
    echo "[LIST] ${days_needed} 天后达阈值，建议规划"
  else
    echo "PASS 90 天内无风险"
  fi
}

predict_days 65 0.5 90  # 示例：磁盘 65%，日均增长0.5%，90%阈值
```

### Phase 4: FinOps 优化建议

```bash
# 检查是否存在低利用率资源
for INST_ID in $(aliyun ecs DescribeInstances --RegionId "$REGION" --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" | jq -r '.Instances.Instance[].InstanceId'); do
  CPU_7DAY_AVG=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 3600 \
    --StartTime "$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  INST_TYPE=$(aliyun ecs DescribeInstances --RegionId "$REGION" --InstanceIds "[\"$INST_ID\"]" | jq -r '.Instances.Instance[0].InstanceType')
  
  if [ "$(echo "$CPU_7DAY_AVG < 20" | bc -l 2>/dev/null)" = "1" ]; then
    echo "[INFO] FinOps: ECS $INST_ID ($INST_TYPE) 7天平均CPU=${CPU_7DAY_AVG}% < 20% -> 建议评估降配"
  fi
done
```

### 报告模板（Markdown）

```markdown
═══════════════════════════════════════
  容量规划报告
═══════════════════════════════════════
  客户: $CUSTOMER | 时间: $(date) | 周期: 最近 7 天
═══════════════════════════════════════

## [UP] 趋势预测

### 磁盘
| 资源 | 当前 | 增长率/天 | 预计达90%日 | 建议 |
|---|---|---|---|---|
| i-xxx (系统盘) | 65% | +0.5% | 2026-07-16 | 6月前扩容 |
| rm-xxx (数据盘) | 72% | +0.8% | 2026-07-01 | [WARN] 4周内需处理 |
| r-xxx (Redis) | 55% | 平稳 | 无风险 | — |

### IOPS
| 资源 | 当前/规格上限 | 增长率 | 预计达80%日 | 建议 |
|---|---|---|---|---|

##  FinOps 建议
| 资源 | 规格 | CPU 7天平均 | 建议 |
|---|---|---|---|
| i-yyy | ecs.g7.4xlarge | 12% | 降配至 ecs.g7.xlarge |