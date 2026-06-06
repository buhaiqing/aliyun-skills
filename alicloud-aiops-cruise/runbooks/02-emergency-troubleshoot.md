---
runbook_id: "02"
scenario: "故障应急排查"
version: "1.0.0"
last_updated: "2026-06-06"
trigger: "告警触发 / 用户报障（慢/不可用）"
risk_level: "高"
execution_time_estimate: "3-8 分钟"
---

> **脚本**: [`runbooks/scripts/emergency-troubleshoot.py`](scripts/emergency-troubleshoot.py) — 全自动执行本 runbook

# 故障应急排查

## 1. 场景描述

用户报障（慢/不可用）或收到告警时，从 SLB 入口开始逐层下钻，快速定位根因。

### 🚨 安全铁律

| 红线 | 要求 |
|---|---|
| **任何资源的删除/停止/规格变更** | ❌ 不允许自动执行，报告只出建议 |
| **输出 AK/SK** | ❌ 必须掩码为 `AKID****SKRET` |
| **安全组规则增删** | ❌ 不允许自动执行 |

**底线**：本 skill 是纯读（Read-Only）巡检，不执行任何写操作。所有建议需用户确认后执行。

### 🧠 提示知识力

> **故障排查和日常巡检的本质区别**：
>
> 日常巡检问的是"有什么不正常的？"（开放式扫描），故障排查问的是"为什么用户觉得慢？"（定向追踪）。
>
> 故障排查的关键是**决策树**——不是全量采集，而是每查一步就决定下一步查什么。如果 SLB 健康检查正常就不查网络连通性，如果 ECS 正常就不查 ECS 层。
>
> **故障排查的黄金法则**：先确定"异常在哪个层"（入口？计算？数据？网络？），再深入那一层。而不是每层都全量采集。

### 适用条件

- 有明确的异常时间窗口（告警时间或用户报障时间）
- 用户的阿里云资源已打标签

---

## 2. 执行流程

### Phase 1: 快速拓扑

```bash
# 只扫核心链路资源，跳过非关键详情
CUSTOMER="{{user.customer_name}}"
REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
TIMESTAMP="{{user.reported_time}}"  # 告警时间或用户报障时间

# 快速定位客户资源（限时 30s）
RC_RESULT=$(timeout 30 aliyun resourcecenter SearchResources \
  --Filter.1.Key "TagKey" --Filter.1.Value "customer" \
  --Filter.2.Key "TagValue" --Filter.2.Value "$CUSTOMER" \
  | jq '.Resources[]')

# 提取关键资源 ID
ECS_IDS=$(echo "$RC_RESULT" | jq -r 'select(.ResourceType=="ACS::ECS::Instance") | .ResourceId')
SLB_IDS=$(echo "$RC_RESULT" | jq -r 'select(.ResourceType=="ACS::SLB::LoadBalancer") | .ResourceId')
RDS_IDS=$(echo "$RC_RESULT" | jq -r 'select(.ResourceType=="ACS::RDS::DBInstance") | .ResourceId')
REDIS_IDS=$(echo "$RC_RESULT" | jq -r 'select(.ResourceType=="ACS::Redis::Instance") | .ResourceId')
NAT_IDS=$(echo "$RC_RESULT" | jq -r 'select(.ResourceType=="ACS::VPC::NatGateway") | .ResourceId')

echo "[INFO] 扫描到 ECS:$(echo "$ECS_IDS" | wc -l) SLB:$(echo "$SLB_IDS" | wc -l) RDS:$(echo "$RDS_IDS" | wc -l) Redis:$(echo "$REDIS_IDS" | wc -l) NAT:$(echo "$NAT_IDS" | wc -l)"
```

### Phase 2: 逐层排查（决策树）

```yaml
步骤:
  S1: 查告警历史（确定异常窗口） → 如果告警触发，直接取告警时间 ±30min
  S2: SLB 健康检查 → 异常? → 查网络/ECS
  S3: ECS CPU/内存 → 异常? → 查进程/DAS
  S4: RDS/Redis → 异常? → DAS 慢查询
  S5: NAT → 异常? → SNAT 端口
  S6: 全链路正常 → 查应用日志/外部依赖
```

#### Step S1: 异常窗口确定 + 告警历史

```bash
# 如有明确告警时间
ALERT_TIME="{{user.reported_time}}"
WINDOW_START=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$ALERT_TIME" "+%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)")
echo "[DIAG] 异常窗口: $WINDOW_START → 当前"

# 查询 ActionTrail 近期操作（看是否有人改过配置）
aliyun actiontrail LookupEvents \
  --StartTime "$(date -u -v-6H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --MaxResults 50 | jq '.Events[] | {EventTime, EventName, UserIdentity, ResourceName}'
```

#### Step S2: SLB 健康检查

```bash
# 查 SLB 健康检查失败率（过去 1h 内）
for LB_ID in $SLB_IDS; do
  UNHEALTHY_PCT=$(aliyun slb DescribeHealthStatus \
    --RegionId "$REGION" \
    --LoadBalancerId "$LB_ID" \
    | jq '[.BackendServers.BackendServer[] | select(.ServerHealthStatus != "normal")] | length')
  
  TOTAL_BACKENDS=$(aliyun slb DescribeVServerGroups \
    --RegionId "$REGION" \
    --LoadBalancerId "$LB_ID" \
    | jq '[.VServerGroups.VServerGroup[].VServerGroupId] | length')
  
  echo "[DIAG] SLB $LB_ID: 异常后端 $UNHEALTHY_PCT / $TOTAL_BACKENDS"
  
  if [ "$UNHEALTHY_PCT" -gt 0 ]; then
    echo "[WARN] SLB 健康检查异常 → 走 SLB-ECS 推理分支"
  fi
done
```

#### Step S3: ECS 层排查

```bash
for INST_ID in $ECS_IDS; do
  # 快速查 CPU/内存（过去 30min 峰值）
  CPU_PEAK=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 60 \
    --StartTime "$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    | jq '.Datapoints | fromjson | [.[].Average] | max // 0')
  
  # 磁盘 IOPS（过去 30min 峰值）
  IOPS_PEAK=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName DiskReadIOPS \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 60 \
    --StartTime "$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  echo "[DIAG] ECS $INST_ID: CPU峰值=${CPU_PEAK}% IOPS峰值=$IOPS_PEAK"
  
  # 如果 CPU 或 IOPS 异常，立即 CloudAssistant 进 VM 排查
  if [ "$(echo "$CPU_PEAK > 70" | bc -l 2>/dev/null)" = "1" ] || [ "$(echo "$IOPS_PEAK > 5000" | bc -l 2>/dev/null)" = "1" ]; then
    echo "[WARN] ECS $INST_ID 异常 → 进入 CloudAssistant 内检测"
    # ... (内检测脚本见 01-daily-health-check.md Step 2.7)
  fi
done
```

#### Step S4: 数据库层排查

```bash
# RDS 快速检查
for DB_ID in $RDS_IDS; do
  RDS_CPU_PEAK=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName CpuUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 60 \
    --StartTime "$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  echo "[DIAG] RDS $DB_ID: CPU峰值=${RDS_CPU_PEAK}%"
  
  # CPU > 70% → 启动 DAS 慢查询诊断
  if [ "$(echo "$RDS_CPU_PEAK > 70" | bc -l 2>/dev/null)" = "1" ]; then
    echo "[WARN] RDS $DB_ID CPU高 → 建议启动 DAS 慢查询诊断"
    # 动态生成 DAS Go snippet → go run（见 assets/code-snippets/das_slow_query.go）
  fi
done

# Redis 快速检查
for REDIS_ID in $REDIS_IDS; do
  REDIS_MEM=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName memory_usage \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 60 \
    --StartTime "$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  REDIS_HIT=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName UsedConnection \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 60 \
    --StartTime "$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 100')
  
  echo "[DIAG] Redis $REDIS_ID: 内存=${REDIS_MEM}% 命中率=${REDIS_HIT}%"
done
```

#### Step S5: NAT 层排查

```bash
for NAT_ID in $NAT_IDS; do
  SNAT_PEAK=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName SnatConnection \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 60 \
    --StartTime "$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  echo "[DIAG] NAT $NAT_ID: SNAT峰值=$SNAT_PEAK"
done
```

### Phase 3: 根因报告

```markdown
═══════════════════════════════════════
  故障排查报告
═══════════════════════════════════════
  客户: {{user.customer_name}}
  时间: {{user.reported_time}}
  报障: "{{user.user_complaint}}"
═══════════════════════════════════════

🔍 链路追踪
  SLB:  ✔ 健康检查正常 (0/5 异常)
    ↓
  ECS:  ⚠ CPU峰值 85%（阈值70%）→ 查进程
    ↓
  RDS:  ✔ CPU 32% | 连接正常
    ↓
  Redis: ✔ 内存 55% | 命中率 95%
    ↓
  NAT:  ✔ SNAT 正常

📌 根因结论
  ECS i-xxx CPU 异常飙高（峰值85%），导致应用响应变慢。
  CPU 飙升与 ActionTrail 发现的数据备份任务时间吻合。
  建议：
  1. 将数据备份任务迁移到业务低峰期
  2. 如持续出现，考虑升配 ECS 或拆分任务

📋 操作事件
  ActionTrail 发现近期配置变更：
  - 2026-06-06T08:00:00Z CreateSnapshot → 触发数据备份
```

## 3. 决策树

```
用户报障/告警
├── ActionTrail 近期有配置变更?
│   ├── 是 → 变更回滚或修复
│   └── 否 → 继续排查
├── SLB 健康检查失败 > 0?
│   ├── 是 → 查安全组规则 + ECS 端口监听 + 网络 ACL
│   └── 否 → 查 ECS 层
├── ECS CPU > 70% 或 IOPS > 规格 70%?
│   ├── 是 → CloudAssistant 进 VM 查 TOP 进程
│   └── 否 → 查 RDS/Redis 层
├── RDS CPU > 70% 或 慢查询 > 100/min?
│   ├── 是 → DAS 慢 SQL 明细 → 加索引/改SQL
│   └── 否 → 查 Redis 层
├── Redis 命中率 < 90%?
│   ├── 是 → 查热key/大key
│   └── 否 → 查 NAT 层
├── NAT SNAT > 80% 规格?
│   ├── 是 → 端口耗尽 → 升配或加 NAT
│   └── 否 → 查外部依赖
└── 全链路正常 → 非阿里云资源问题 → 查应用日志/第三方
```

## 4. Changelog

| 版本 | 日期 | 变更内容 |
|---|---|---|
| 1.0.0 | 2026-06-06 | 初始版本 |