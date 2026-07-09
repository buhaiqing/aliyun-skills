---
runbook_id: "07"
scenario: "全链路性能瓶颈定位"
version: "1.0.0"
last_updated: "2026-06-07"
trigger: "用户报障（慢）/ aiops-cruise 巡检发现异常链路 / CMS 多级联告警 / 人工触发"
risk_level: "高"
execution_time_estimate: "5-12 分钟"
---

> **脚本**: [`runbooks/scripts/bottleneck-localization.py`](scripts/bottleneck-localization.py) — 全自动执行本 runbook

# 全链路性能瓶颈定位

## 1. 场景描述

当用户反馈"系统慢"或 aiops-cruise 巡检发现链路异常时，从 EIP（入口）到 RDS/Redis（数据层）逐层扫描各节点的性能水位，通过**延迟对比法**和**链路关联推理**定位瓶颈节点。

与日常巡检的区别：日常巡检问"有什么不正常"，瓶颈定位问**"最慢的那一跳在哪"**。

### [ALERT] 安全铁律

| 红线 | 要求 |
|---|---|
| **任何资源的删除/停止/规格变更** | FAIL 不允许自动执行，报告只出建议 |
| **输出 AK/SK** | FAIL 必须掩码为 `AKID****SKRET` |
| **安全组规则增删** | FAIL 不允许自动执行 |
| **CloudAssistant 内检测** | WARNING 自动执行只读命令（白名单 W-01） |

**底线**：本 runbook 是纯读（Read-Only）诊断。所有优化建议需用户确认后通过对应 ops skill 执行。

### [NOTE] 提示知识力

> **性能瓶颈定位的核心方法论：**
>
> 用户说"慢"时，99% 的根因在以下几层之一（按概率排序）：
> 1. **数据库层（~55%）**：慢 SQL -> CPU 打满 -> 请求排队 -> 系统响应慢
> 2. **计算层（~25%）**：ECS CPU/内存不足 -> 应用线程阻塞 -> 请求堆积
> 3. **缓存层（~10%）**：Redis 大 key/命中率低 -> 穿透到 DB -> DB 压力
> 4. **网络层（~8%）**：EIP 带宽打满 / NAT SNAT 端口耗尽 -> 丢包重传
> 5. **均衡层（~2%）**：SLB 并发连满 / 健康检查异常 -> 请求分配不均
>
> **定位策略：对比法**
> - 比较各层的响应延迟（P50/P95/P99）
> - 如果 DB 层最慢 -> 查 DB；如果 ECS 层最慢 -> 查 ECS
> - 不用全量采集，**哪层慢就深入哪层**
>
> **三个关键延迟指标：**
> - **入口（EIP->SLB）**：公网延迟，通常 < 50ms
> - **应用/计算（SLB->ECS）**：应用处理时间，通常 < 200ms
> - **数据层（ECS->RDS/Redis）**：SQL 执行时间，通常 < 50ms
> 如果应用层延迟占 80%+，根因在应用代码；如果数据层延迟占 60%+，根因在数据库。

### 适用条件

- 有明确的异常时间窗口（告警时间或用户报障时间）
- 资源已按标签/资源组归类
- 支持全阿里云产品：EIP -> SLB/ALB -> ECS/ACK -> RDS/Redis/PolarDB -> NAT

### 不适用条件

- 无明确异常窗口 -> 使用 `01-daily-health-check` 做主动扫描
- 问题在应用代码层（非阿里云基础设施）-> 建议接入 ARMS APM
- 只排查单个产品（如仅 RDS）-> `05-slow-query-diagnosis` 更合适
- **仅 ECS 网络层问题（带宽、延迟、丢包）不涉及全链路** -> 直接使用 `alicloud-ecs-ops/references/network-troubleshooting-and-tuning.md`，无需跑全链路瓶颈定位

---

## 2. 执行流程

### Phase 0: 前置安全门

```bash
# 1. 凭据预检
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" || { echo "[ERROR] AK_ID 未设置"; exit 1; }
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" || { echo "[ERROR] AK_SK 未设置"; exit 1; }
command -v aliyun >/dev/null 2>&1 || { echo "[ERROR] aliyun CLI 未安装"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "[ERROR] jq 未安装"; exit 1; }

# 2. 获取诊断范围
CUSTOMER="{{user.customer_name}}"
REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
ALERT_TIME="{{user.reported_time}}"  # 用户报障时间或告警触发时间
echo "[INFO] 客户: $CUSTOMER | 区域: $REGION | 异常窗口: $ALERT_TIME"

# 3. 计算时间窗口（异常时间 ±30min）
if [ -n "$ALERT_TIME" ]; then
  WINDOW_START=$(date -u -d "$ALERT_TIME - 30 minutes" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$ALERT_TIME" -v-30M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)
  WINDOW_END=$(date -u -d "$ALERT_TIME + 30 minutes" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$ALERT_TIME" -v+30M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)
else
  WINDOW_START=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)
  WINDOW_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
fi
echo "[INFO] 诊断窗口: $WINDOW_START -> $WINDOW_END"
```

### Phase 1: 拓扑发现 + 链路构建

> **核心思路**：快速扫描资源组/标签下的全链路资源，构建 `EIP->SLB/ALB->ECS->RDS/Redis->NAT` 的拓扑映射，输出链路节点清单供 Phase 2 逐层诊断。

```bash
# ── 扫描全链路资源 ──
RG_ID="{{user.resource_group_id}}"
TAG_KEY="{{user.tag_key}}"
TAG_VALUE="{{user.tag_value}}"

# 资源中心快速扫描（限时 30s）
RC_RESULT=$(timeout 30 aliyun resourcecenter SearchResources \
  --Filter.1.Key "TagKey" --Filter.1.Value "$TAG_KEY" \
  --Filter.2.Key "TagValue" --Filter.2.Value "$TAG_VALUE" \
  | jq '.Resources[]' 2>/dev/null)

# 提取各层资源 ID
ECS_IDS=$(echo "$RC_RESULT" | jq -r 'select(.ResourceType=="ACS::ECS::Instance") | .ResourceId // empty' | head -20)
SLB_IDS=$(echo "$RC_RESULT" | jq -r 'select(.ResourceType=="ACS::SLB::LoadBalancer") | .ResourceId // empty')
RDS_IDS=$(echo "$RC_RESULT" | jq -r 'select(.ResourceType=="ACS::RDS::DBInstance") | .ResourceId // empty')
REDIS_IDS=$(echo "$RC_RESULT" | jq -r 'select(.ResourceType=="ACS::Redis::Instance") | .ResourceId // empty')
EIP_IDS=$(aliyun vpc DescribeEipAddresses --RegionId "$REGION" | jq -r '.EipAddresses.EipAddress[].AllocationId // empty')
NAT_IDS=$(echo "$RC_RESULT" | jq -r 'select(.ResourceType=="ACS::VPC::NatGateway") | .ResourceId // empty')

# ── 构建 SLB -> ECS 后端映射 ──
echo ""
echo "═══ 链路拓扑 ═══"
for LB_ID in $SLB_IDS; do
  BACKENDS=$(aliyun slb DescribeVServerGroups \
    --RegionId "$REGION" \
    --LoadBalancerId "$LB_ID" 2>/dev/null \
    | jq -r '.VServerGroups.VServerGroup[].VServerGroupId // empty')

  for VG_ID in $BACKENDS; do
    SERVER_IDS=$(aliyun slb DescribeVServerGroupAttribute \
      --RegionId "$REGION" \
      --LoadBalancerId "$LB_ID" \
      --VServerGroupId "$VG_ID" 2>/dev/null \
      | jq -r '.BackendServers.BackendServer[].ServerId // empty')
    echo "  SLB $LB_ID -> ECS $(echo "$SERVER_IDS" | tr '\n' ',' | sed 's/,$//')"
  done
done

echo ""
echo "═══ 链路节点统计 ═══"
echo "  EIP:  $(echo "$EIP_IDS" | wc -l) 个"
echo "  SLB:  $(echo "$SLB_IDS" | wc -l) 个"
echo "  ECS:  $(echo "$ECS_IDS" | wc -l) 台"
echo "  RDS:  $(echo "$RDS_IDS" | wc -l) 个"
echo "  Redis: $(echo "$REDIS_IDS" | wc -l) 个"
echo "  NAT:  $(echo "$NAT_IDS" | wc -l) 个"
```

### Phase 2: 逐层延迟采集（瓶颈定位核心）

> **核心思路**：对每层采集异常窗口内的性能指标，用"延迟对比法"定位瓶颈。每层采集 3 个关键指标后立即判定该层是否异常——异常则深入诊断，正常则跳过到下一层。

#### Step 2.1: 入口层（EIP）— 带宽使用率

```bash
echo ""
echo "═══ Step 2.1: 入口层（EIP）═══"

for EIP_ID in $EIP_IDS; do
  # EIP 带宽使用率（异常窗口内峰值）
  IN_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_in.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // -1')

  OUT_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_out.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // -1')

  BANDWIDTH=$(aliyun vpc DescribeEipAddresses --RegionId "$REGION" \
    --AllocationId "$EIP_ID" | jq -r '.EipAddresses.EipAddress[0].Bandwidth // "?"')

  echo "  EIP $EIP_ID: IN使用率=$IN_PCT% OUT使用率=$OUT_PCT% (带宽=${BANDWIDTH}Mbps)"

  # 判定
  if [ "$IN_PCT" != "-1" ] && [ "$(echo "$IN_PCT > 80" | bc -l 2>/dev/null)" = "1" ]; then
    EIP_BOTTLENECK="YES"
    echo "  CRITICAL EIP 入带宽打满 -> 入口层瓶颈!"
  elif [ "$OUT_PCT" != "-1" ] && [ "$(echo "$OUT_PCT > 80" | bc -l 2>/dev/null)" = "1" ]; then
    EIP_BOTTLENECK="YES"
    echo "  CRITICAL EIP 出带宽打满 -> 出口层瓶颈!"
  else
    EIP_BOTTLENECK="NO"
    echo "  PASS EIP 带宽充足"
  fi
done
```

#### Step 2.2: 分发层（SLB/ALB）— 连接数 + 延迟

```bash
echo ""
echo "═══ Step 2.2: 分发层（SLB/ALB）═══"

for LB_ID in $SLB_IDS; do
  # 活跃连接数（异常窗口内峰值）
  ACTIVE_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName ActiveConnection \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  # 新建连接速率
  NEW_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName NewConnection \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  # 健康检查失败数
  UNHEALTHY=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName UnhealthyServerCount \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  echo "  SLB $LB_ID: 活跃连接=$ACTIVE_CONN 新建连接=$NEW_CONN/s 不健康后端=$UNHEALTHY"

  # 判定：连接数 > 50000 或 不健康 > 0 为异常
  if [ "$UNHEALTHY" != "0" ]; then
    SLB_BOTTLENECK="YES"
    echo "  CRITICAL SLB 健康检查异常 -> 分发层瓶颈!"
  elif [ "$(echo "$ACTIVE_CONN > 50000" | bc -l 2>/dev/null)" = "1" ]; then
    SLB_BOTTLENECK="YES"
    echo "  CRITICAL SLB 连接数过高 -> 分发层瓶颈!"
  else
    SLB_BOTTLENECK="NO"
    echo "  PASS SLB 状态正常"
  fi
done
```

#### Step 2.3: 计算层（ECS）— CPU/内存/网络/IOPS

```bash
echo ""
echo "═══ Step 2.3: 计算层（ECS）═══"

ECS_BOTTLENECK="NO"
ECS_HIGH_CPU=""
ECS_HIGH_MEM=""
ECS_HIGH_IOPS=""
ECS_CLOUD_ASSISTANT=""

for INST_ID in $ECS_IDS; do
  # CPU 使用率（异常窗口内峰值）
  CPU_PEAK=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  # 内存使用率
  MEM_PEAK=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName memory_usage \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  # 磁盘 IOPS（读+写峰值）
  IO_READ_PEAK=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName DiskReadIOPS \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  IO_WRITE_PEAK=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName DiskWriteIOPS \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  # 网络带宽（公网 + 内网）
  NET_INTERNET_OUT=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName InternetOutRate \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  NET_INTRANET_OUT=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName IntranetOutRate \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  # 获取实例带宽上限（Mbps -> bps 统一比较）
  INTERNET_BANDWIDTH=$(aliyun ecs DescribeInstances --RegionId "$REGION" \
    --InstanceIds "[\"$INST_ID\"]" | jq -r '.Instances.Instance[0].InternetMaxBandwidthOut // 0')
  # 内网基线需要查实例类型规格（简化：用 0.5 Gbps 作为通用 small 基线，实际应查 DescribeInstanceTypes）
  # 这里用 CloudMonitor 原始值直接对比经验阈值

  INST_TYPE=$(aliyun ecs DescribeInstances --RegionId "$REGION" \
    --InstanceIds "[\"$INST_ID\"]" | jq -r '.Instances.Instance[0].InstanceType // "unknown"')

  echo "  ECS $INST_ID ($INST_TYPE): CPU=${CPU_PEAK}% 内存=${MEM_PEAK}% IOPS=读${IO_READ_PEAK}/写${IO_WRITE_PEAK} 公网出=${NET_INTERNET_OUT}bps 内网出=${NET_INTRANET_OUT}bps"

  # 判定
  HAS_CPU_ISSUE=false
  HAS_MEM_ISSUE=false
  HAS_IO_ISSUE=false
  HAS_NET_ISSUE=false

  if [ "$(echo "$CPU_PEAK > 85" | bc -l 2>/dev/null)" = "1" ]; then
    ECS_BOTTLENECK="YES"; HAS_CPU_ISSUE=true
    ECS_HIGH_CPU="$ECS_HIGH_CPU $INST_ID(${CPU_PEAK}%)"
  elif [ "$(echo "$CPU_PEAK > 70" | bc -l 2>/dev/null)" = "1" ]; then
    HAS_CPU_ISSUE=true
    ECS_HIGH_CPU="$ECS_HIGH_CPU $INST_ID(${CPU_PEAK}%)"
  fi

  if [ "$(echo "$MEM_PEAK > 90" | bc -l 2>/dev/null)" = "1" ]; then
    ECS_BOTTLENECK="YES"; HAS_MEM_ISSUE=true
    ECS_HIGH_MEM="$ECS_HIGH_MEM $INST_ID(${MEM_PEAK}%)"
  fi

  TOTAL_IOPS=$(echo "$IO_READ_PEAK + $IO_WRITE_PEAK" | bc)
  if [ "$(echo "$TOTAL_IOPS > 50000" | bc -l 2>/dev/null)" = "1" ]; then
    HAS_IO_ISSUE=true
    ECS_HIGH_IOPS="$ECS_HIGH_IOPS $INST_ID(${TOTAL_IOPS})"
  fi

  # 网络带宽判定（公网 Mbps -> bps: * 1000 * 1000）
  INTERNET_BANDWIDTH_BPS=$(echo "$INTERNET_BANDWIDTH * 1000 * 1000" | bc)
  if [ "$(echo "$NET_INTERNET_OUT > $INTERNET_BANDWIDTH_BPS * 0.8" | bc -l 2>/dev/null)" = "1" ]; then
    ECS_BOTTLENECK="YES"; HAS_NET_ISSUE=true
    ECS_HIGH_NET="$ECS_HIGH_NET $INST_ID(公网${NET_INTERNET_OUT}bps/${INTERNET_BANDWIDTH}Mbps)"
    echo "  CRITICAL ECS $INST_ID 公网带宽打满 -> 计算层网络瓶颈!"
  elif [ "$(echo "$NET_INTRANET_OUT > 700000000" | bc -l 2>/dev/null)" = "1" ]; then
    # 700Mbps 作为通用 small 实例内网基线经验值，实际应查实例类型规格
    ECS_BOTTLENECK="YES"; HAS_NET_ISSUE=true
    ECS_HIGH_NET="$ECS_HIGH_NET $INST_ID(内网${NET_INTRANET_OUT}bps)"
    echo "  CRITICAL ECS $INST_ID 内网带宽过高 -> 计算层网络瓶颈!"
  fi

  # 异常 ECS -> 触发 CloudAssistant 内检测
  if [ "$HAS_CPU_ISSUE" = "true" ] || [ "$HAS_MEM_ISSUE" = "true" ]; then
    echo "  [WARN] ECS $INST_ID 异常 -> 启动 CloudAssistant 内检测"

    # [AUTO-QUIET] 只读诊断（白名单 W-01）
    # 若网络异常，追加网络层诊断命令（参考 alicloud-ecs-ops network-troubleshooting-and-tuning.md）
    NET_DIAG=""
    if [ "$HAS_NET_ISSUE" = "true" ]; then
      NET_DIAG='echo "=== NET IFACE ==="; ip addr show eth0 2>/dev/null
echo "=== NET ROUTE ==="; ip route 2>/dev/null
echo "=== NET DEV COUNTERS ==="; cat /proc/net/dev | grep eth0 2>/dev/null
echo "=== NET SOCKSTAT ==="; ss -s 2>/dev/null
echo "=== NET TCP RETRANS ==="; cat /proc/net/snmp 2>/dev/null | grep Tcp | tail -1 | awk "{print \"retrans=\"\$12}"
'
    fi

    DIAG_SCRIPT="#!/bin/bash
echo \"=== TOP CPU ===\"; ps aux --sort=-%cpu 2>/dev/null | head -8
echo \"=== TOP MEM ===\"; ps aux --sort=-%mem 2>/dev/null | head -8
echo \"=== DISK ===\"; df -h / 2>/dev/null
echo \"=== LOAD ===\"; uptime 2>/dev/null
echo \"=== NET CONN ===\"; ss -tan 2>/dev/null | awk '{print \$1}' | sort | uniq -c
echo \"=== DOCKER ===\"; docker ps --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null || true
$NET_DIAG"

    ENCODED_SCRIPT=$(echo "$DIAG_SCRIPT" | base64)
    CMD_ID=$(aliyun ecs RunCommand --RegionId "$REGION" \
      --Name "bottleneck-diag" \
      --CommandContent "$ENCODED_SCRIPT" \
      --Type RunShellScript \
      --InstanceId "[\"$INST_ID\"]" \
      --Timeout 30 | jq -r '.CommandId // empty')

    if [ -n "$CMD_ID" ]; then
      sleep 5
      DIAG_OUTPUT=$(aliyun ecs DescribeInvocationResults \
        --RegionId "$REGION" \
        --InstanceId "$INST_ID" \
        --CommandId "$CMD_ID" | jq -r '.Invocation.InvocationResults.InvocationResult[0].Output // ""' | base64 -d 2>/dev/null)
      ECS_CLOUD_ASSISTANT="$ECS_CLOUD_ASSISTANT\n--- ECS $INST_ID 内检测 ---\n$DIAG_OUTPUT"
    fi
  fi
done

if [ "$ECS_BOTTLENECK" = "NO" ]; then
  echo "  PASS ECS 层无瓶颈"
fi
```

#### Step 2.4: 数据层（RDS/PolarDB）— CPU/连接/慢查询

```bash
echo ""
echo "═══ Step 2.4: 数据层（RDS/PolarDB）═══"

RDS_BOTTLENECK="NO"
RDS_HIGH_CPU=""
RDS_SLOW_SQL=""

for DB_ID in $RDS_IDS; do
  # CPU 使用率（异常窗口内峰值）
  RDS_CPU=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName CpuUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  # 连接数使用率
  RDS_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName ConnectionUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')

  # 慢查询数（异常窗口内峰值）
  RDS_SLOW=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName SlowQueryCount \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  # IOPS 使用率
  RDS_IOPS=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName IOPSUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  DB_CLASS=$(aliyun rds DescribeDBInstances --RegionId "$REGION" \
    --DBInstanceId "$DB_ID" | jq -r '.Items.DBInstance[0].DBInstanceClass // "unknown"')

  echo "  RDS $DB_ID ($DB_CLASS): CPU=${RDS_CPU}% 连接=${RDS_CONN}% 慢查询=${RDS_SLOW}/min IOPS=${RDS_IOPS}%"

  # 判定
  if [ "$(echo "$RDS_CPU > 85" | bc -l 2>/dev/null)" = "1" ]; then
    RDS_BOTTLENECK="YES"
    RDS_HIGH_CPU="$RDS_HIGH_CPU $DB_ID(${RDS_CPU}%)"
    echo "  CRITICAL RDS CPU 打满 -> 数据层瓶颈!"
  elif [ "$(echo "$RDS_SLOW > 50" | bc -l 2>/dev/null)" = "1" ]; then
    RDS_BOTTLENECK="YES"
    RDS_SLOW_SQL="$RDS_SLOW_SQL $DB_ID(${RDS_SLOW}/min)"
    echo "  CRITICAL RDS 慢查询过多 -> 数据层瓶颈!"
  elif [ "$(echo "$RDS_CPU > 70" | bc -l 2>/dev/null)" = "1" ]; then
    echo "  WARNING RDS CPU 偏高 -> 建议执行 05-slow-query-diagnosis 深度诊断"
  else
    echo "  PASS RDS 状态正常"
  fi
done
```

#### Step 2.5: 缓存层（Redis）— 内存/命中率/大key

```bash
echo ""
echo "═══ Step 2.5: 缓存层（Redis）═══"

REDIS_BOTTLENECK="NO"

for REDIS_ID in $REDIS_IDS; do
  # 内存使用率
  REDIS_MEM=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName memory_usage \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  # 连接数
  REDIS_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName UsedConnection \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  # 逐出键数（evicted_keys > 0 说明内存不足）
  REDIS_EVICTED=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName EvictedKeys \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  echo "  Redis $REDIS_ID: 内存=${REDIS_MEM}% 连接=${REDIS_CONN} 逐出=${REDIS_EVICTED}"

  # 判定
  if [ "$(echo "$REDIS_MEM > 85" | bc -l 2>/dev/null)" = "1" ] || [ "$REDIS_EVICTED" != "0" ]; then
    REDIS_BOTTLENECK="YES"
    echo "  CRITICAL Redis 内存不足/逐出 -> 缓存层瓶颈! 建议执行 08-redis-performance-diagnosis"
  elif [ "$(echo "$REDIS_MEM > 75" | bc -l 2>/dev/null)" = "1" ]; then
    echo "  WARNING Redis 内存偏高 -> 关注大key"
  else
    echo "  PASS Redis 状态正常"
  fi
done
```

#### Step 2.6: 出网层（NAT）— SNAT 连接数

```bash
echo ""
echo "═══ Step 2.6: 出网层（NAT）═══"

NAT_BOTTLENECK="NO"

for NAT_ID in $NAT_IDS; do
  # SNAT 连接数（异常窗口内峰值）
  NAT_SNAT=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName SnatConnection \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // -1')

  # 端口分配失败
  NAT_DROP=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName EniPacketsDropPortAllocationFail \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 60 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  echo "  NAT $NAT_ID: SNAT=$NAT_SNAT 端口分配失败=$NAT_DROP"

  if [ "$NAT_DROP" != "0" ] && [ "$NAT_DROP" != "0.0" ]; then
    NAT_BOTTLENECK="YES"
    echo "  CRITICAL NAT 端口分配失败 -> 出网层瓶颈（SNAT 端口耗尽）!"
  else
    echo "  PASS NAT 状态正常"
  fi
done
```

### Phase 3: 链路关联推理 + 瓶颈判定

#### Step 3.1: 瓶颈归因决策树

```
用户报障"慢"
│
├── EIP 带宽打满 (>80%)?
│   └── PASS -> 入口层瓶颈 -> 建议升配带宽 / 限流
│   └── FAIL -> 查下一层
│
├── SLB 健康检查异常 OR 连接数过高?
│   └── PASS -> 分发层瓶颈 -> 查后端 ECS / 升配 SLB
│   └── FAIL -> 查下一层
│
├── ECS CPU > 85% OR 内存 > 90% OR 网络带宽 > 80%?
│   └── PASS -> 计算层瓶颈
│   │   ├── CPU 高 + 内存正常 = CPU 密集型
│   │   ├── 内存高 + CPU 正常 = 内存泄漏
│   │   ├── 公网带宽高 = EIP/带宽瓶颈 -> 建议升配带宽或 CDN  offload
│   │   ├── 内网带宽高 = 实例规格网络瓶颈 -> 建议升配实例类型或 RPC 压缩
│   │   └── 双高 = 规格不够 -> 建议升配或拆分
│   └── FAIL -> 查下一层
│
├── RDS CPU > 85% OR 慢查询 > 50/min?
│   └── PASS -> 数据层瓶颈
│   │   ├── CPU 高 + 慢查询多 = 慢 SQL 导致 (-> runbook 05)
│   │   └── CPU 正常 + 慢查询多 = 索引问题
│   └── FAIL -> 查下一层
│
├── Redis 内存 > 85% OR 逐出 > 0?
│   └── PASS -> 缓存层瓶颈 (-> runbook 08)
│   └── FAIL -> 查下一层
│
├── NAT 端口分配失败 > 0?
│   └── PASS -> 出网层瓶颈 -> 建议增加 SNAT IP 或升配
│   └── FAIL -> 查最后一层
│
└── 全链路正常 -> 非基础设施问题
    ├── 查 ActionTrail 近期配置变更
    ├── 查应用日志/ARMS APM
    └── 结论: "阿里云基础设施正常，建议查应用层"
```

#### Step 3.2: 生成瓶颈定位报告

```bash
# 综合判定主瓶颈
BOTTLENECK_LAYER="无"
BOTTLENECK_REASON=""

if [ "$EIP_BOTTLENECK" = "YES" ]; then
  BOTTLENECK_LAYER="入口层 (EIP)"
  BOTTLENECK_REASON="EIP 带宽使用率超过 80%"
elif [ "$SLB_BOTTLENECK" = "YES" ]; then
  BOTTLENECK_LAYER="分发层 (SLB)"
  BOTTLENECK_REASON="SLB 连接数过高或健康检查异常"
elif [ "$ECS_BOTTLENECK" = "YES" ]; then
  BOTTLENECK_LAYER="计算层 (ECS)"
  # 细化 ECS 瓶颈原因
  if [ -n "${ECS_HIGH_NET:-}" ]; then
    BOTTLENECK_REASON="ECS 网络带宽超限: $ECS_HIGH_NET"
  elif [ -n "${ECS_HIGH_CPU:-}" ]; then
    BOTTLENECK_REASON="ECS CPU/内存/IOPS 超限: CPU=$ECS_HIGH_CPU"
  else
    BOTTLENECK_REASON="ECS CPU/内存/IOPS 超限"
  fi
elif [ "$RDS_BOTTLENECK" = "YES" ]; then
  BOTTLENECK_LAYER="数据层 (RDS)"
  BOTTLENECK_REASON="RDS CPU 打满或慢查询堆积"
elif [ "$REDIS_BOTTLENECK" = "YES" ]; then
  BOTTLENECK_LAYER="缓存层 (Redis)"
  BOTTLENECK_REASON="Redis 内存不足或逐出"
elif [ "$NAT_BOTTLENECK" = "YES" ]; then
  BOTTLENECK_LAYER="出网层 (NAT)"
  BOTTLENECK_REASON="NAT SNAT 端口耗尽"
else
  BOTTLENECK_LAYER="无（全链路正常）"
  BOTTLENECK_REASON="全链路基础设施指标在安全阈值内，建议查应用层"
fi
```

**Markdown（给人读）：**

```markdown
═══════════════════════════════════════════════════════
  [SCAN] 全链路性能瓶颈定位报告
═══════════════════════════════════════════════════════
  报告ID: bottleneck-$CUSTOMER-$(date +%Y%m%dT%H%M%SZ)
  客户: $CUSTOMER | 区域: $REGION
  异常窗口: $WINDOW_START -> $WINDOW_END
═══════════════════════════════════════════════════════

## [STATS] 瓶颈定位结论

| 诊断维度 | 结果 |
|----------|------|
| [TARGET] 主瓶颈层 | **$BOTTLENECK_LAYER** |
| [LIST] 根因描述 | $BOTTLENECK_REASON |
| Critical 节点 | ${CRITICAL_NODES:-0} |
| Warning 节点 | ${WARNING_NODES:-0} |

═══════════════════════════════════════════════════════
  [NET] 链路逐层诊断
═══════════════════════════════════════════════════════

### 入口层 EIP -> 分发层 SLB
  EIP:   IN=${EIP_IN_PCT}% OUT=${EIP_OUT_PCT}%  |  状态: ${EIP_STATUS}
    DOWN
  SLB:   活跃连接=${SLB_ACTIVE_CONN}  新建连接=${SLB_NEW_CONN}/s  |  状态: ${SLB_STATUS}
    DOWN

### 分发层 SLB -> 计算层 ECS
  ECS TOP-5 CPU:
    i-xxx:  CPU=${CPU_PEAK}%  内存=${MEM_PEAK}%  IOPS=${TOTAL_IOPS}
    ...
    状态: ${ECS_STATUS}

    DOWN

### 计算层 ECS -> 数据层 RDS
  RDS TOP-3 CPU:
    rm-xxx: CPU=${RDS_CPU}%  连接=${RDS_CONN}%  慢查询=${RDS_SLOW}/min
    ...
    状态: ${RDS_STATUS}

    DOWN

### 缓存层 Redis
  Redis:  内存=${REDIS_MEM}%  连接=${REDIS_CONN}  逐出=${REDIS_EVICTED}
    状态: ${REDIS_STATUS}

    DOWN

### 出网层 NAT
  NAT:    SNAT连接=${NAT_SNAT}  端口分配失败=${NAT_DROP}
    状态: ${NAT_STATUS}

═══════════════════════════════════════════════════════
  [PIN] 优化建议（按优先级）
═══════════════════════════════════════════════════════

${OPTIMIZATION_SUGGESTIONS}

═══════════════════════════════════════════════════════
  审计追踪
═══════════════════════════════════════════════════════
  JSON: audit-results/bottleneck-$CUSTOMER-$(date +%Y%m%d).json
  耗时: $EXECUTION_DURATION | runbook: v1.0.0
```

**JSON（持久化到 `audit-results/`）：**

```bash
mkdir -p audit-results/
cat > "audit-results/bottleneck-${CUSTOMER}-$(date +%Y%m%d).json" << BTN_JSON
{
  "report_id": "bottleneck-${CUSTOMER}-$(date +%Y%m%dT%H%M%SZ)",
  "customer": "${CUSTOMER}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "scenario": "bottleneck_localization",
  "runbook_version": "1.0.0",
  "bottleneck_layer": "${BOTTLENECK_LAYER}",
  "bottleneck_reason": "${BOTTLENECK_REASON}",
  "layer_status": {
    "eip": {"status": "${EIP_STATUS}", "in_pct": "${EIP_IN_PCT}", "out_pct": "${EIP_OUT_PCT}"},
    "slb": {"status": "${SLB_STATUS}", "active_conn": "${SLB_ACTIVE_CONN}", "unhealthy": "${SLB_UNHEALTHY}"},
    "ecs": {"status": "${ECS_STATUS}", "high_cpu_instances": "${ECS_HIGH_CPU}", "high_mem_instances": "${ECS_HIGH_MEM}", "high_net_instances": "${ECS_HIGH_NET:-}"},
    "rds": {"status": "${RDS_STATUS}", "high_cpu": "${RDS_HIGH_CPU}", "slow_sql": "${RDS_SLOW_SQL}"},
    "redis": {"status": "${REDIS_STATUS}", "memory_pct": "${REDIS_MEM}", "evicted": "${REDIS_EVICTED}"},
    "nat": {"status": "${NAT_STATUS}", "snat": "${NAT_SNAT}", "drop": "${NAT_DROP}"}
  },
  "suggestions": []
}
BTN_JSON
echo "[RESULT] JSON报告已持久化到 audit-results/"
```

---

## 3. 阈值速查

| 层 | 指标 | Warning | Critical | 瓶颈影响 |
|----|------|:-------:|:--------:|---------|
| **EIP** | 带宽使用率 | > 60% | > 80% | 丢包、延迟增加 |
| **SLB** | 活跃连接/规格上限 | > 60% | > 80% | 新连接被拒绝 |
| **SLB** | 健康检查失败 | — | > 0 | 请求路由到不健康后端 |
| **ECS** | CPU 使用率 | > 70% | > 85% | 应用线程阻塞 |
| **ECS** | 内存使用率 | > 80% | > 90% | OOM 风险 |
| **ECS** | 公网带宽使用率 (`InternetOutRate` / `InternetMaxBandwidthOut`) | > 70% | > 90% | 出方向丢包、延迟增加 |
| **ECS** | 内网带宽使用率 (`IntranetOutRate` / 实例类型基线) | > 70% | > 90% | 跨服务调用超时 |
| **ECS** | 磁盘 IOPS/规格上限 | > 70% | > 85% | I/O 等待增加 |
| **RDS** | CPU 使用率 | > 75% | > 85% | SQL 执行超时 |
| **RDS** | 慢查询 | > 10/min | > 50/min | 请求堆积 |
| **RDS** | 连接数/上限 | > 70% | > 85% | 新连接被拒绝 |
| **Redis** | 内存使用率 | > 75% | > 85% | 逐出、OOM |
| **Redis** | 逐出键数 | — | > 0 | 缓存命中率下降 |
| **NAT** | 端口分配失败 | — | > 0 | SNAT 连接失败 |
| **NAT** | SNAT 连接/规格上限 | > 70% | > 85% | 出网连接失败 |

---

## 4. 改进闭环

| 反馈来源 | 触发条件 | 改进动作 | 责任人 |
|----------|---------|---------|--------|
| 人工审阅 | 瓶颈定位错误（判断了 A 层但实际是 B 层） | 更新推理规则优先级 | 运维负责人 |
| 漏报 | 全链路正常但用户仍然感觉慢 | 增加 ARMS APM 集成建议 | Agent 维护者 |
| 新资源类型 | ALB/NLB 等新负载均衡 | 增加 ALB/NLB 指标采集 | Agent 维护者 |
| 误报 | EIP 带宽突刺被误判为瓶颈 | 增加持续 5min 以上才标记 | Agent 维护者 |

---

## 5. Changelog

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 1.0.0 | 2026-06-07 | 初始版本，全链路性能瓶颈定位完整流程 |