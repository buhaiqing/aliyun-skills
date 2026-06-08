---
runbook_id: "01"
scenario: "日常健康巡检"
version: "1.0.0"
last_updated: "2026-06-06"
trigger: "定时调度（每 6 小时）/ 人工触发"
risk_level: "低"
execution_time_estimate: "5-15 分钟（50 台资源以内）"
---

> **脚本**: [`runbooks/scripts/daily-health-check.py`](scripts/daily-health-check.py) — 全自动执行本 runbook

# 日常健康巡检

## 1. 场景描述

对指定客户（通过 `客户` 标签识别）在阿里云上的核心链路资源进行全链路健康检查。覆盖入口层（EIP）、分发层（SLB）、计算层（ECS）、数据层（RDS/Redis）、出网层（NAT）和安全层（安全组）。输出统一的健康评分和风险项。

### [ALERT] 安全铁律

| 红线 | 要求 |
|---|---|
| **任何资源的删除/停止/规格变更** | FAIL 不允许自动执行，报告只出建议 |
| **输出 AK/SK** | FAIL 必须掩码为 `AKID****SKRET` |
| **安全组规则增删** | FAIL 不允许自动执行 |

**底线**：本 skill 是纯读（Read-Only）巡检，不执行任何写操作。所有建议需用户确认后执行。

### [NOTE] 提示知识力

> **日常巡检 vs 故障排查的本质区别**：
> - 日常巡检是"基线对比"—— 和昨天/上周的自己比，发现趋势异常
> - 故障排查是"异常定位"—— 从入口到后端逐层排查，定位根因
>
> 日常巡检的核心价值不是"发现问题时报警"（CloudMonitor 告警已经做了），而是**发现趋势——在告警触发之前就发现异常增长**。所以环比（昨日同期、上周同期）是日常巡检的灵魂。

### 适用条件

- 资源已按 `客户` 标签归类（如 `标签键=customer, 标签值=烟台振华`）
- 阿里云 AK/SK 已配置且具有各产品读取权限 + CloudAssistant 执行权限
- 支持的阿里云区域：`cn-hangzhou`, `cn-shanghai`, `cn-beijing`, `cn-shenzhen`, `cn-qingdao`, `cn-zhangjiakou`, `cn-huhehaote`

### 不适用条件

- 资源未打标签 -> 需先执行人工确认流程或按资源组筛选
- 涉及跨账号资源 -> 使用 `--assume-role` 跨账号模式（TODO）

---

## 2. 执行流程

### Phase 0: 前置安全门

```bash
# 1. 凭证预检
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" || { echo "[ERROR] AK_ID 未设置"; exit 1; }
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" || { echo "[ERROR] AK_SK 未设置"; exit 1; }

# 2. CLI 可用性检查
command -v aliyun >/dev/null 2>&1 || { echo "[ERROR] aliyun CLI 未安装"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "[ERROR] jq 未安装"; exit 1; }

# 3. API 连通性检查（只读）
aliyun vpc DescribeRegions --RegionId "$ALIBABA_CLOUD_REGION_ID" >/dev/null 2>&1 \
  || { echo "[ERROR] API 连通性检查失败"; exit 1; }

# 4. 确认巡检范围
CUSTOMER="{{user.customer_name}}"
REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
echo "[INFO] 客户: $CUSTOMER | 区域: $REGION"
```

### Phase 1: 拓扑发现

> **核心思路**：支持两种扫描模式——**资源组**（推荐）或**标签**。资源组是阿里云原生的管理单位，比标签更可靠。
> 用户可输入一个资源ID，系统自动反查所属资源组，然后扫描该组下的所有资源。

#### Step 1.0: 混合扫描 — 资源组优先 + 标签补充 + 合并去重

> **核心策略**：资源组是主扫描单位（一个业务系统通常在一个 RG 内），标签是补充（跨 RG 的零散资源）。两者合并去重后得到最完整的链路视图。
> 用户只需提供**资源组ID**或**标签**（或两者都提供），系统自动执行双通道扫描。

```bash
# 用户输入
RG_ID="{{user.resource_group_id}}"        # 可选，如 rg-acfmvyfsd4znnoi
TAG_KEY="{{user.tag_key}}"               # 可选，如 customer
TAG_VALUE="{{user.tag_value}}"           # 可选，如 烟台振华
RESOURCE_ID="{{user.resource_id}}"        # 可选，从单个资源反查RG

# ── 自动反查：如果给的是资源ID，先找它所属的资源组 ──
if [ -n "$RESOURCE_ID" ] && [ -z "$RG_ID" ]; then
  case "${RESOURCE_ID:0:2}" in
    i-)  RG_ID=$(aliyun ecs DescribeInstances --RegionId "$REGION" \
           --InstanceIds "[\"$RESOURCE_ID\"]" | jq -r '.Instances.Instance[0].ResourceGroupId') ;;
    rm-|pgm-) RG_ID=$(aliyun rds DescribeDBInstances --RegionId "$REGION" \
           --DBInstanceId "$RESOURCE_ID" | jq -r '.Items.DBInstance[0].ResourceGroupId') ;;
    r-)  RG_ID=$(aliyun r-kvstore DescribeInstances --RegionId "$REGION" | jq -r \
           --arg id "$RESOURCE_ID" '.Instances.KVStoreInstance[] | select(.InstanceId==$id) | .ResourceGroupId') ;;
    lb-) RG_ID=$(aliyun slb DescribeLoadBalancers --RegionId "$REGION" | jq -r \
           --arg id "$RESOURCE_ID" '.LoadBalancers.LoadBalancer[] | select(.LoadBalancerId==$id) | .ResourceGroupId') ;;
    ngw-) RG_ID=$(aliyun vpc DescribeNatGateways --RegionId "$REGION" \
           --NatGatewayId "$RESOURCE_ID" | jq -r '.NatGateways.NatGateway[0].ResourceGroupId') ;;
    eip-) RG_ID=$(aliyun vpc DescribeEipAddresses --RegionId "$REGION" \
           --AllocationId "$RESOURCE_ID" | jq -r '.EipAddresses.EipAddress[0].ResourceGroupId') ;;
    vpc-) RG_ID=$(aliyun vpc DescribeVpcs --RegionId "$REGION" --VpcId "$RESOURCE_ID" \
           | jq -r '.Vpcs.Vpc[0].ResourceGroupId') ;;
  esac
  echo "[INFO] 由资源 $RESOURCE_ID 反查到资源组: $RG_ID"
fi

echo ""
echo "═══════════════════════════════════════"
echo "  扫描策略: 资源组优先 + 标签补充"
  # ── 资源组合法性校验 ──
  if [ -n "$RG_ID" ] && [ "$RG_ID" != "" ]; then
    if echo "$RG_ID" | grep -qiE "^(default|rg-default)"; then
      echo "  [WARN] 默认资源组($RG_ID)跳过，需用户明确要求全账号扫描"
      RG_ID=""
    else
      echo "  [PKG] 资源组: $RG_ID PASS (自定义资源组)"
    fi
  else
    echo "  [PKG] 资源组: (未提供或为空，跳过)"
  fi
echo "═══════════════════════════════════════"
[ -n "$RG_ID" ] && echo "  [PKG] 资源组: $RG_ID" || echo "  [PKG] 资源组: (未提供)"
[ -n "$TAG_KEY" ] && echo "  [TAG]️ 标签:   $TAG_KEY=$TAG_VALUE" || echo "  [TAG]️ 标签:   (未提供)"
```

#### Step 1.1: 双通道扫描 + 合并去重

> **通道A（资源组）**：按 ResourceGroupId 精确扫描，覆盖该 RG 下的全部资源。
> **通道B（标签）**：按标签模糊扫描，覆盖跨 RG 的零散资源。
> **合并**：两个通道的结果按资源ID去重，取并集。

```bash
# ── 通道A: 按资源组扫描（主通道） ──
if [ -n "$RG_ID" ]; then
  echo "[INFO] 通道A: 资源组 $RG_ID"
  
  # PASS 支持原生 --ResourceGroupId 过滤的产品
  ECS_LIST_RG=$(aliyun ecs DescribeInstances --RegionId "$REGION" \
    --ResourceGroupId "$RG_ID" --PageSize 100 | jq '.Instances.Instance')
  RDS_LIST_RG=$(aliyun rds DescribeDBInstances --RegionId "$REGION" \
    --ResourceGroupId "$RG_ID" --PageSize 100 | jq '.Items.DBInstance')
  NAT_LIST_RG=$(aliyun vpc DescribeNatGateways --RegionId "$REGION" \
    --ResourceGroupId "$RG_ID" | jq '.NatGateways.NatGateway')
  
  # [WARN] 不支持原生过滤的产品 -> 全量拉取后 jq 筛选
  SLB_LIST_RG=$(aliyun slb DescribeLoadBalancers --RegionId "$REGION" --PageSize 100 \
    | jq --arg rg "$RG_ID" '[.LoadBalancers.LoadBalancer[] | select(.ResourceGroupId == $rg)]')
  REDIS_LIST_RG=$(aliyun r-kvstore DescribeInstances --RegionId "$REGION" --PageSize 100 \
    | jq --arg rg "$RG_ID" '[.Instances.KVStoreInstance[] | select(.ResourceGroupId == $rg)]')
  VPC_LIST_RG=$(aliyun vpc DescribeVpcs --RegionId "$REGION" --PageSize 50 \
    | jq --arg rg "$RG_ID" '[.Vpcs.Vpc[] | select(.ResourceGroupId == $rg)]')
  SG_LIST_RG=$(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" --PageSize 50 \
    | jq --arg rg "$RG_ID" '[.SecurityGroups.SecurityGroup[] | select(.ResourceGroupId == $rg)]')
fi

# ── 通道B: 按标签扫描（补充通道） ──
if [ -n "$TAG_KEY" ]; then
  echo "[INFO] 通道B: 标签 $TAG_KEY=$TAG_VALUE"
  
  # ECS 按标签
  ECS_LIST_TAG=$(aliyun ecs DescribeInstances --RegionId "$REGION" \
    --Tag.1.Key "$TAG_KEY" --Tag.1.Value "$TAG_VALUE" --PageSize 100 | jq '.Instances.Instance')
  # SLB 按标签
  SLB_LIST_TAG=$(aliyun slb DescribeLoadBalancers --RegionId "$REGION" \
    --Tag.1.Key "$TAG_KEY" --Tag.1.Value "$TAG_VALUE" --PageSize 100 | jq '.LoadBalancers.LoadBalancer')
  # RDS 按标签
  RDS_LIST_TAG=$(aliyun rds DescribeDBInstances --RegionId "$REGION" \
    --Tag.1.Key "$TAG_KEY" --Tag.1.Value "$TAG_VALUE" --PageSize 100 | jq '.Items.DBInstance')
fi

# ── 合并去重（按 InstanceId 取并集） ──
echo "[INFO] 正在合并去重..."

# ECS 合并
if [ -n "$RG_ID" ] && [ -n "$TAG_KEY" ]; then
  ECS_LIST=$(jq -n --argjson a "$ECS_LIST_RG" --argjson b "$ECS_LIST_TAG" \
    '[($a + $b) | group_by(.InstanceId) | map(add)]')
elif [ -n "$RG_ID" ]; then
  ECS_LIST="$ECS_LIST_RG"
else
  ECS_LIST="$ECS_LIST_TAG"
fi

# SLB 合并
if [ -n "$RG_ID" ] && [ -n "$TAG_KEY" ]; then
  SLB_LIST=$(jq -n --argjson a "$SLB_LIST_RG" --argjson b "$SLB_LIST_TAG" \
    '[($a + $b) | group_by(.LoadBalancerId) | map(add)]')
elif [ -n "$RG_ID" ]; then
  SLB_LIST="$SLB_LIST_RG"
else
  SLB_LIST="$SLB_LIST_TAG"
fi

# RDS 合并
if [ -n "$RG_ID" ] && [ -n "$TAG_KEY" ]; then
  RDS_LIST=$(jq -n --argjson a "$RDS_LIST_RG" --argjson b "$RDS_LIST_TAG" \
    '[($a + $b) | group_by(.DBInstanceId) | map(add)]')
elif [ -n "$RG_ID" ]; then
  RDS_LIST="$RDS_LIST_RG"
else
  RDS_LIST="$RDS_LIST_TAG"
fi

# 统计
ECS_COUNT=$(echo "$ECS_LIST" | jq 'length')
SLB_COUNT=$(echo "$SLB_LIST" | jq 'length')
RDS_COUNT=$(echo "$RDS_LIST" | jq 'length')
REDIS_COUNT=$(echo "$REDIS_LIST_RG // []" | jq 'length')
VPC_COUNT=$(echo "$VPC_LIST_RG // []" | jq 'length')

echo "[RESULT] 合并后: ECS=$ECS_COUNT SLB=$SLB_COUNT RDS=$RDS_COUNT Redis=$REDIS_COUNT VPC=$VPC_COUNT"
```

```bash
# VPC 拓扑
aliyun vpc DescribeVpcs --RegionId "$REGION" --PageSize 50 | jq '.Vpcs.Vpc[]' &

# ECS 实例列表
ECS_LIST=$(aliyun ecs DescribeInstances \
  --RegionId "$REGION" \
  --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" \
  --PageSize 100 | jq '.Instances.Instance')
echo "$ECS_LIST" | jq -r '.[] | "\(.InstanceId) \(.InstanceName) \(.InstanceType)"'

# SLB 列表
SLB_LIST=$(aliyun slb DescribeLoadBalancers \
  --RegionId "$REGION" \
  --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" \
  --PageSize 100 | jq '.LoadBalancers.LoadBalancer[]')

# RDS 列表
RDS_LIST=$(aliyun rds DescribeDBInstances \
  --RegionId "$REGION" \
  --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" \
  --PageSize 100 | jq '.Items.DBInstance[]')

# Redis 列表
REDIS_LIST=$(aliyun r-kvstore DescribeInstances \
  --RegionId "$REGION" \
  --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" \
  --PageSize 100 | jq '.Instances.KVStoreInstance[]')

# NAT 网关列表
aliyun vpc DescribeNatGateways --RegionId "$REGION" --PageSize 50 | jq '.NatGateways.NatGateway[]' &

# 安全组列表
aliyun ecs DescribeSecurityGroups --RegionId "$REGION" --PageSize 50 | jq '.SecurityGroups.SecurityGroup[]' &

# 等待后台任务
wait
```

#### Step 1.3: 构建拓扑映射

```bash
# SLB -> ECS 后端映射
for LB_ID in $(echo "$SLB_LIST" | jq -r '.LoadBalancerId'); do
  BACKEND_SERVERS=$(aliyun slb DescribeVServerGroups \
    --RegionId "$REGION" \
    --LoadBalancerId "$LB_ID" | jq '.VServerGroups.VServerGroup[]')
  echo "SLB $LB_ID 后端: $(echo "$BACKEND_SERVERS")"
done

# EIP -> 关联资源映射
aliyun vpc DescribeEipAddresses --RegionId "$REGION" | jq '.EipAddresses.EipAddress[] | {EipAddress, InstanceId, InstanceType}'
```

#### Step 1.4: 输出拓扑初判

组装拓扑摘要输出：

```markdown
## [NET] 拓扑初判报告

**客户:** $CUSTOMER | **时间:** $(date -u +%Y-%m-%dT%H:%M:%SZ) | **区域:** $REGION

### VPC 网络
| VPC | 交换机数 | ECS | SLB | RDS | Redis | NAT |
|---|---|---|---|---|---|---|

### 链路结构
```
EIP -> SLB -> ECS -> RDS/Redis
                    NAT
                   
安全组: 防护所有资源
```

### 资源统计
| 类型 | 数量 |
|---|---|
| ECS | ${ECS_COUNT} |
| SLB | ${SLB_COUNT} |
| RDS | ${RDS_COUNT} |
| Redis | ${REDIS_COUNT} |
| NAT | ${NAT_COUNT} |
```

### Phase 2: 深度采集

> **核心思路**：对每个资源采集最近 6 小时的监控指标（5 分钟粒度）+ 昨日同期 + 上周同期。

#### Step 2.1: ECS 监控采集

```bash
# 通用时间计算
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START_TIME=$(date -u -v-6H +%Y-%m-%dT%H:%M:%SZ)
DAILY_BASELINE_START=$(date -u -v-30H +%Y-%m-%dT%H:%M:%SZ)
DAILY_BASELINE_END=$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)

for INST_ID in $(echo "$ECS_LIST" | jq -r '.[].InstanceId'); do
  INST_TYPE=$(echo "$ECS_LIST" | jq -r --arg id "$INST_ID" '.[] | select(.InstanceId==$id) | .InstanceType')
  
  # CPU
  CPU_CUR=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  CPU_BASELINE=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 300 \
    --StartTime "$DAILY_BASELINE_START" --EndTime "$DAILY_BASELINE_END" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 内存
  MEM_CUR=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName memory_usage \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 磁盘读IOPS（注意：DiskIOPS 不是有效指标，用 DiskReadIOPS/DiskWriteIOPS 替代）
  DISK_READ_IOPS=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName DiskReadIOPS \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  DISK_WRITE_IOPS=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName DiskWriteIOPS \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  # 网络带宽
  NET_IN=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName InternetInRate \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  NET_OUT=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName InternetOutRate \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  echo "[DIAG] ECS $INST_ID($INST_TYPE) CPU=$CPU_CUR% Mem=$MEM_CUR% IOPS=$DISK_IOPS IN=$NET_IN OUT=$NET_OUT baseline=$CPU_BASELINE%"
done
```

#### Step 2.2: EIP 入口带宽监控

> [WARN] 注意：EIP 的 CloudMonitor 指标命名空间为 `acs_vpc_eip`，指标名为 `net_in.rate_percentage`（入方向带宽使用率）、`net_out.rate_percentage`（出方向带宽使用率）。
> EIP 在没有流量时不产生监控数据点（返回空数组），这是正常行为。

```bash
# 查询所有 EIP（包括未绑定的）
for EIP in $(aliyun vpc DescribeEipAddresses --RegionId "$REGION" --PageSize 50 | jq -r '.EipAddresses.EipAddress[].AllocationId'); do
  BANDWIDTH=$(aliyun vpc DescribeEipAddresses --RegionId "$REGION" --AllocationId "$EIP" | jq -r '.EipAddresses.EipAddress[0].Bandwidth // "0"')
  INSTANCE_REF=$(aliyun vpc DescribeEipAddresses --RegionId "$REGION" --AllocationId "$EIP" | jq -r '.EipAddresses.EipAddress[0] | .InstanceId + "(" + .InstanceType + ")" // "未绑定"')
  
  # 入方向带宽使用率 (Datapoints 是 JSON 字符串，需 fromjson 解析)
  IN_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_in.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP\"}]" \
    --Period 3600 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // "无数据"')
  
  # 出方向带宽使用率
  OUT_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_out.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP\"}]" \
    --Period 3600 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // "无数据"')
  
  echo "[DIAG] EIP $EIP (${BANDWIDTH}Mbps, $INSTANCE_REF): IN使用率=$IN_PCT% OUT使用率=$OUT_PCT%"
done
```

#### Step 2.3: SLB 监控采集

```bash
for LB_ID in $(echo "$SLB_LIST" | jq -r '.LoadBalancerId'); do
  # 健康检查失败率
  UNHEALTHY=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName UnhealthyServerCount \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  # 并发连接
  ACTIVE_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName ActiveConnection \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 新建连接速率
  NEW_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName NewConnection \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  echo "[DIAG] SLB $LB_ID unhealthy=$UNHEALTHY activeConn=$ACTIVE_CONN newConn=$NEW_CONN"
done
```

#### Step 2.4: RDS 监控采集

```bash
for DB_ID in $(echo "$RDS_LIST" | jq -r '.[].DBInstanceId'); do
  # CPU
  RDS_CPU=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName CpuUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 连接数使用率
  RDS_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName ConnectionUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 磁盘使用率
  RDS_DISK=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName DiskUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  echo "[DIAG] RDS $DB_ID CPU=$RDS_CPU% Conn=$RDS_CONN% Disk=$RDS_DISK%"
done
```

#### Step 2.5: Redis 监控采集

```bash
for REDIS_ID in $(echo "$REDIS_LIST" | jq -r '.[].InstanceId'); do
  REDIS_MEM=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName memory_usage \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  # Redis 命中率（注意：部分Redis版本不暴露HitRate指标，此时返回空需跳过）
  REDIS_HIT=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName UsedConnection \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // "NODATA"')
  
  REDIS_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName UsedConnection \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  echo "[DIAG] Redis $REDIS_ID Mem=$REDIS_MEM% Hit=$REDIS_HIT% Conn=$REDIS_CONN"
done
```

#### Step 2.6: NAT 监控采集

> [WARN] 注意：NAT 的 `SnatConnection` 指标在低流量环境可能无数据（返回空数组），此时查 `EniSessionActiveConnection`（活跃连接数）作为替代。端口分配失败 `EniPacketsDropPortAllocationFail` > 0 说明出现过 SNAT 端口耗尽 —— 这是阿里云 NAT 网关最常见的故障模式。

```bash
for NAT_ID in $(aliyun vpc DescribeNatGateways --RegionId "$REGION" | jq -r '.NatGateways.NatGateway[].NatGatewayId'); do
  # NAT 规格（从 DescribeNatGateways 获取或手动指定）
  NAT_SPEC=$(aliyun vpc DescribeNatGateways --RegionId "$REGION" --NatGatewayId "$NAT_ID" | jq -r '.NatGateways.NatGateway[0].Spec // "Small"')
  
  # SNAT 连接数（最近 7 天峰值，因为 SNAT 变化慢）
  NAT_SNAT=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName SnatConnection \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 3600 \
    --StartTime "$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // "NODATA"')
  
  # NAT 端口分配失败（这是关键指标——>0 说明出现过端口耗尽）
  DROP_FAIL=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName EniPacketsDropPortAllocationFail \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 3600 \
    --StartTime "$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  if [ "$DROP_FAIL" != "0" ] && [ "$DROP_FAIL" != "0.0" ]; then
    echo "[CRITICAL] NAT $NAT_ID ($NAT_SPEC): 端口分配失败=$DROP_FAIL -> SNAT 端口耗尽风险！"
  else
    echo "[DIAG] NAT $NAT_ID ($NAT_SPEC): SNAT=$NAT_SNAT 端口分配失败=$DROP_FAIL"
  fi
done
```

#### Step 2.7: 安全组审计

```bash
# 检查高危规则：0.0.0.0/0 开放管理端口
for SG_ID in $(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" | jq -r '.SecurityGroups.SecurityGroup[].SecurityGroupId'); do
  DANGER=$(aliyun ecs DescribeSecurityGroupAttribute \
    --RegionId "$REGION" \
    --SecurityGroupId "$SG_ID" \
    | jq '[.Permissions.Permission[] | select(.SourceCidrIp == "0.0.0.0/0" and (.PortRange == "22/22" or .PortRange == "3389/3389" or .PortRange == "3306/3306" or .PortRange == "6379/6379" or .PortRange == "5432/5432"))] | length')
  
  if [ "$DANGER" -gt 0 ]; then
    echo "[WARN] 安全组 $SG_ID 存在高危规则（0.0.0.0/0 开放管理/数据库端口）"
  fi
done
```

#### Step 2.8: [可选] CloudAssistant 内检测

如果用户启用内检测，对 ECS 执行：

```bash
for INST_ID in $(echo "$ECS_LIST" | jq -r '.[].InstanceId'); do
  # 创建内检测脚本
  SCRIPT='#!/bin/bash
echo "=== TOP CPU ==="; ps aux --sort=-%cpu 2>/dev/null | head -5
echo "=== DISK ==="; df -h / 2>/dev/null
echo "=== MEMORY ==="; free -h 2>/dev/null
echo "=== LISTENING PORTS ==="; ss -tlnp 2>/dev/null
echo "=== LOAD ==="; uptime 2>/dev/null
echo "=== DOCKER ==="; docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || true'
  
  ENCODED_SCRIPT=$(echo "$SCRIPT" | base64)
  
  CMD_ID=$(aliyun ecs RunCommand \
    --RegionId "$REGION" \
    --Name "cruise-diag" \
    --CommandContent "$ENCODED_SCRIPT" \
    --Type RunShellScript \
    --InstanceId "[\"$INST_ID\"]" \
    --Timeout 30 | jq -r '.CommandId')
  
  sleep 5
  
  DIAG_RESULT=$(aliyun ecs DescribeInvocationResults \
    --RegionId "$REGION" \
    --InstanceId "$INST_ID" \
    --CommandId "$CMD_ID" | jq -r '.Invocation.InvocationResults.InvocationResult[0].Output // ""' | base64 -d 2>/dev/null)
  
  echo "[DIAG] ECS $INST_ID 内检测结果:"
  echo "$DIAG_RESULT"
done
```

#### Step 2.9: 动态基线异常评分

> 基于过去 7 天的历史数据，对每个资源的指标计算 Z-Score 异常评分。
> 完整规范见 `references/dynamic-baseline.md`。
> **固定阈值 vs 动态基线取最高等级**，两者互补而非替代。

```bash
# 基线窗口: 最近 7 天 (1h 粒度)
BASELINE_START=$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)
BASELINE_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# ── ECS CPU Z-Score ──
for INST_ID in $(echo "$ECS_LIST" | jq -r '.[].InstanceId'); do
  CPU_HISTORY=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Dimensions "[{\"instanceId\":\"$INST_ID\"}]" \
    --Period 3600 \
    --StartTime "$BASELINE_START" --EndTime "$BASELINE_END" \
    | jq '.Datapoints | fromjson | [.[].Average]')
  CPU_MEAN=$(echo "$CPU_HISTORY" | jq 'add / length // 0')
  CPU_STD=$(echo "$CPU_HISTORY" | jq --argjson m "$CPU_MEAN" '(map(. - $m | . * .) | add / length | sqrt) // 0')
  CPU_CURRENT=$(echo "$CPU_HISTORY" | jq '.[-1] // 0')
  if [ "$(echo "$CPU_STD > 0" | bc -l 2>/dev/null)" = "1" ]; then
    CPU_Z=$(echo "scale=2; ($CPU_CURRENT - $CPU_MEAN) / $CPU_STD" | bc -l 2>/dev/null || echo "0")
    if [ "$(echo "$CPU_Z > 3.0" | bc -l 2>/dev/null)" = "1" ]; then
      echo "[ANOMALY] ECS $INST_ID CPU Z-Score=${CPU_Z} CRITICAL"
    elif [ "$(echo "$CPU_Z > 2.0" | bc -l 2>/dev/null)" = "1" ]; then
      echo "[ANOMALY] ECS $INST_ID CPU Z-Score=${CPU_Z} WARNING"
    fi
  fi
done

# ── RDS CPU Z-Score ──
for DB_ID in $(echo "$RDS_LIST" | jq -r '.[].DBInstanceId'); do
  RDS_CPU_HISTORY=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName CpuUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 3600 \
    --StartTime "$BASELINE_START" --EndTime "$BASELINE_END" \
    | jq '.Datapoints | fromjson | [.[].Average]')
  RDS_MEAN=$(echo "$RDS_CPU_HISTORY" | jq 'add / length // 0')
  RDS_STD=$(echo "$RDS_CPU_HISTORY" | jq --argjson m "$RDS_MEAN" '(map(. - $m | . * .) | add / length | sqrt) // 0')
  RDS_CURRENT=$(echo "$RDS_CPU_HISTORY" | jq '.[-1] // 0')
  if [ "$(echo "$RDS_STD > 0" | bc -l 2>/dev/null)" = "1" ]; then
    RDS_Z=$(echo "scale=2; ($RDS_CURRENT - $RDS_MEAN) / $RDS_STD" | bc -l 2>/dev/null || echo "0")
    if [ "$(echo "$RDS_Z > 3.0" | bc -l 2>/dev/null)" = "1" ]; then
      echo "[ANOMALY] RDS $DB_ID CPU Z-Score=${RDS_Z} CRITICAL"
    fi
  fi
done
```

> **验证方式**: 在已有 7 天指标数据的 ECS 上运行巡检，检查 Step 2.9 是否输出 `[ANOMALY]` 标记。

### Phase 3: 推理 + 报告

#### Step 3.1: 逐资源水位判定

对照 `references/threshold-definitions.md` 对每个指标做 Warning/Critical/OK 判定：

```bash
# 判定函数 — Warning/Critical/OK
evaluate() {
  local metric=$1 value=$2 warn=$3 crit=$4
  if [ "$(echo "$value >= $crit" | bc -l 2>/dev/null)" = "1" ]; then echo "CRITICAL CRITICAL"
  elif [ "$(echo "$value >= $warn" | bc -l 2>/dev/null)" = "1" ]; then echo "WARNING WARNING"
  else echo "PASS OK"; fi
}
```

#### Step 3.2: 链路关联推理

Agent 对照 `references/inference-rules.md` 检查现象组合：

```markdown
## [LINK] 链路推理

| 现象组合 | 匹配规则 | 推理结论 | 建议 |
|---|---|---|---|
| SLB健康检查失败+ECS正常 | SLB-ECS-01 | 网络连通性问题 | 查安全组入方向规则 |
| ECS CPU>70%+内存>80% | ECS-01 | 资源双重瓶颈 | CloudAssistant查进程TOP |
| ... | ... | ... | ... |
```

#### Step 3.3: 容量预判（7 天趋势）

```markdown
## [UP] 容量趋势（最近 7 天）

| 资源 | 指标 | 趋势 | 预计达阈值日 | 建议 |
|---|---|---|---|---|
| i-xxx | 磁盘使用率 | UP 线性增长 | 2026-06-20 | 扩容磁盘或清理 |
| rm-xxx | 磁盘使用率 | UP 线性增长 | 2026-07-01 | DAS查空间分析 |
| r-xxx | 内存使用率 | -> 平稳 | 无风险 | — |
```

#### Step 3.4: 双格式报告输出

**Markdown（给人读）—— 要求：每个问题必须含 实例ID + 数值 + 阈值 + 级别：**

```markdown
═══════════════════════════════════════════════════════
  [SCAN] 全链路深度巡检报告
═══════════════════════════════════════════════════════
  报告ID: cruise-$CUSTOMER-$(date +%Y%m%dT%H%M%SZ)
  区域: $REGION | 时间: $(date) | 窗口: $START_TIME -> $END_TIME
═══════════════════════════════════════════════════════

[STATS] 总体评分
  整体健康度: ${OVERALL_SCORE:-0.00}/1.0 | ${OVERALL_SEVERITY:-PASS}
  安全水位:   ${SAFETY_SCORE:-1.0}/1.0 | ${SAFETY_SEVERITY:-PASS}
  容量水位:   ${CAPACITY_SCORE:-1.0}/1.0 | ${CAPACITY_SEVERITY:-PASS}

─────── 服务摘要 ───────
  EIP:   6个 | 最高带宽使用率 0.18%  PASS
  SLB:  11个 | 1个健康检查异常 WARNING
  ECS:  16台 | CPU平均 1~23%  PASS
  RDS:  13个 | 1个磁盘97.89%  CRITICAL
  Redis: 9个 | 内存均<20%  PASS
  NAT:   1个 | SNAT无数据  PASS

═══════════════════════════════════════════════════════
  Critical 问题清单
═══════════════════════════════════════════════════════

#1 RDS 磁盘使用率超标
  ┌─ 诊断链 ─────────────────────────────────────────────
  │ 实例: rm-bp180t670128318su (商业线-非生产-公共)
  │ 规格: rds.mysql.c1.large | 引擎: MySQL 8.0
  │ 指标: disk_usage = 97.89% (阈值: Warning 75% / Critical 90%)
  │ 规则: RDS-04 (磁盘 > 85% 且增长趋势 -> CRITICAL)
  │ 影响: 磁盘即将写满，数据库将自动转为只读模式
  └───────────────────────────────────────────────────────
  ┌─ 修复步骤 ────────────────────────────────────────────
  │ Step 1 (紧急): 确认能否立即扩容
  │   aliyun rds ModifyDBInstanceSpec --DBInstanceId rm-bp180t670128318su --DBInstanceStorage 500
  │   -> 不停服扩容，建议扩大到当前2倍
  │
  │ Step 2 (清理): DAS空间分析->清理binlog
  │   CALL mysql.rds_cycle_binlog();  -- 清理已消费binlog
  │   或缩短binlog保留时间: SET GLOBAL binlog_expire_logs_seconds=86400;
  │
  │ Step 3 (根因): 设置磁盘告警（避免再次发生）
  │   aliyun cms PutMetricAlarm --RuleName "rds-disk-warning" --Namespace acs_rds_dashboard
  │   --MetricName DiskUsage --Threshold 85 --Statistics Average --Period 300 --EvaluationCount 2
  │
  │ Step 4 (验证): 确认磁盘回落
  │   aliyun cms DescribeMetricList --Namespace acs_rds_dashboard --MetricName DiskUsage ...
  └───────────────────────────────────────────────────────

#2 安全组高危规则（共8个）
  ┌─ 诊断链 ─────────────────────────────────────────────
  │ 涉及安全组:
  │   sg-bp15gjk952xih6ieqrv7 (RumbaEvCall性能测试-20250228)
  │   sg-bp198qft2d1al3xvevm9 (鼎付通压测)
  │   sg-bp157gcce2s3w6hgto1n (振华-int)
  │   sg-bp1es4vnor02agn5bjo7 (DNET_Temp_all)
  │   sg-bp14jh80lqgrsdixcqpl (DNET_TEST_SSH)
  │   sg-bp159nyvdicnw4yx272b (Clone-From-sg-...)
  │   (共8个组，每组1+条规则)
  │ 规则类型: 0.0.0.0/0 开放端口 22/3389/3306/6379/5432
  │ 影响: SSH/RDP/数据库端口暴漏公网，暴力破解高风险
  │ 规则: SG-01/SG-02
  └───────────────────────────────────────────────────────
  ┌─ 修复步骤 ────────────────────────────────────────────
  │ Step 1: 逐安全组确认规则详情
  │   aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId $SG_ID
  │   -> 找到具体哪条 Permissions.Permission 是 0.0.0.0/0
  │
  │ Step 2: 判断是否需要公网访问
  │   ├─ 不需要 -> 删除规则（推荐）:
  │   │   aliyun ecs RevokeSecurityGroup --SecurityGroupId $SG_ID
  │   │   --SourceCidrIp 0.0.0.0/0 --PortRange 22/22 --IpProtocol tcp
  │   │
  │   ├─ 需要SSH/RDP -> 使用阿里云堡垒机
  │   │   └─ 删除0.0.0.0/0规则，仅放行堡垒机IP
  │   │
  │   ├─ 需要DB访问 -> 使用DMS
  │   │   └─ 删除0.0.0.0/0规则，仅放行DMS IP段
  │   │
  │   └─ 必须公网 -> 使用CloudFirewall统一管控
  │       └─ 通过CFW配置互联网边界防火墙策略
  │
  │ Step 3: 验证
  │   aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId $SG_ID
  │   -> 确认0.0.0.0/0规则已清除
  │
  │ 参考: references/inference-rules.md 中 SG-01/SG-02 的完整修复步骤
  └───────────────────────────────────────────────────────

═══════════════════════════════════════════════════════
  Warning 问题清单
═══════════════════════════════════════════════════════

#3 SLB 健康检查异常
  实例: lb-bp1bbyiyosm9jsptpfrnc (商业线-研发-H6-PolarDB-日常)
  指标: UnhealthyServerCount = 1
  影响: 一个后端服务无法响应健康检查
  规则: SLB-ECS-01 (健康检查失败 + ECS正常)
  建议: 查安全组入方向规则 / ECS内端口监听 / CLB->ECS网络ACL

#4 RDS 磁盘接近Warning
  实例: rm-bp1i73z4w465gth6a (支付压测租户库-essd盘)
  指标: disk_usage = 82.5% (阈值: 75% Warning)
  建议: 监控趋势，规划磁盘扩容或数据清理

═══════════════════════════════════════════════════════
  [PIN] 优化建议（按优先级）
═══════════════════════════════════════════════════════

1. CRITICAL [CRITICAL] RDS 磁盘扩容
   实例: rm-bp180t670128318su
   详情: 磁盘使用率 97.89%，预计3天内达100%
   紧急处理: 立即执行 DAS 空间分析 -> 扩容存储或清理binlog

2. CRITICAL [CRITICAL] 安全组高危规则整改
   涉及实例:
   - sg-bp15gjk952xih6ieqrv7 (RumbaEvCall性能测试)
   - sg-bp198qft2d1al3xvevm9 (鼎付通压测)
   - sg-bp157gcce2s3w6hgto1n (振华-int)
   - (共8个安全组)
   详情: 0.0.0.0/0 开放SSH/数据库端口
   紧急处理: 逐个排查并限制来源IP

3. WARNING [WARNING] SLB健康检查修复
   实例: lb-bp1bbyiyosm9jsptpfrnc (H6-PolarDB-日常)
   详情: UnhealthyServerCount=1
   建议: CloudAssistant进ECS查端口监听 + 安全组入方向

═══════════════════════════════════════════════════════
  审计追踪
═══════════════════════════════════════════════════════
  JSON: audit-results/cruise-$CUSTOMER-$(date +%Y%m%d).json
  耗时: $EXECUTION_DURATION | runbook: v1.0.0 | 模式: $MODE
```

**JSON（持久化到 `audit-results/`—— 每条发现含 instance_id + metric + value + threshold + level）：**

```bash
mkdir -p audit-results/
cat > "audit-results/cruise-${CUSTOMER}-$(date +%Y%m%d).json" << CRUISE_JSON
{
  "report_id": "cruise-${CUSTOMER}-$(date +%Y%m%dT%H%M%SZ)",
  "customer": "${CUSTOMER}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "scenario": "daily_health_check",
  "runbook_version": "1.0.0",
  "resource_stats": {
    "ecs": ${ECS_COUNT:-0},
    "slb": ${SLB_COUNT:-0},
    "rds": ${RDS_COUNT:-0},
    "redis": ${REDIS_COUNT:-0},
    "nat": ${NAT_COUNT:-0},
    "eip": ${EIP_COUNT:-0}
  },
  "critical_findings": [
    {
      "title": "RDS磁盘使用率超标",
      "instance_id": "rm-bp180t670128318su",
      "instance_name": "商业线-非生产-公共",
      "resource_type": "RDS",
      "metric": "disk_usage",
      "value": 97.89,
      "threshold_critical": 90,
      "threshold_warning": 75,
      "level": "CRITICAL",
      "rule_id": "RDS-04",
      "impact": "磁盘即将写满，数据库可能进入只读模式",
      "suggestion": "DAS空间分析 -> 清理binlog/归档/扩容"
    },
    {
      "title": "安全组高危规则",
      "instance_id": "sg-bp15gjk952xih6ieqrv7",
      "instance_name": "RumbaEvCall性能测试-20250228",
      "resource_type": "SecurityGroup",
      "metric": "0.0.0.0/0_port_22",
      "value": "存在",
      "level": "CRITICAL",
      "rule_id": "SG-01",
      "suggestion": "限制来源IP或迁移至CloudFirewall"
    }
  ],
  "warning_findings": []
}
CRUISE_JSON
echo "[RESULT] JSON报告已持久化到 audit-results/"
```

---

## 3. 阈值速查

> 完整阈值表见 `references/threshold-definitions.md`

| 服务 | 指标 | Warning | Critical |
|---|---|---|---|
| ECS | CPU 使用率 | > 70% | > 85% |
| ECS | 内存使用率 | > 80% | > 90% |
| ECS | 磁盘使用率 | > 75% | > 90% |
| ECS | IOPS / 规格上限 | > 70% | > 85% |
| ECS | 网络带宽 / 规格上限 | > 60% | > 80% |
| SLB | 健康检查失败率 | > 5% | > 20% |
| SLB | 并发连接 / 规格上限 | > 60% | > 80% |
| RDS | CPU 使用率 | > 75% | > 85% |
| RDS | 连接数 / 上限 | > 70% | > 85% |
| RDS | 磁盘使用率 | > 75% | > 90% |
| Redis | 内存使用率 | > 75% | > 85% |
| Redis | 命中率 | < 90% | < 80% |
| NAT | SNAT 连接 / 规格上限 | > 70% | > 85% |
| **NAT** | **端口分配失败计数** | — | **> 0 即 Critical** |
| **EIP** | **带宽使用率** | > 60% | > 80% |
| 安全组 | 0.0.0.0/0 开放 DB/管理端口 | — | 存在即 Critical |

---

## 4. 改进闭环

| 反馈来源 | 触发条件 | 改进动作 | 责任人 |
|---|---|---|---|
| 人工审阅 | 发现误报/漏报 | 更新阈值 + runbook 版本 | 运维负责人 |
| 巡检执行失败 | API 返回异常/超时 | 更新 CLI 参数或重试策略 | Agent 维护者 |
| 新资源接入 | 客户新增服务 | 新增 Analyzer + runbook | Agent 维护者 |
| 架构变更 | ECS 迁移 ACK | 更新推理规则 + 测试 | Agent 维护者 |

---

## 5. Changelog

| 版本 | 日期 | 变更内容 |
|---|---|---|
| 1.0.0 | 2026-06-06 | 初始版本，日常健康巡检完整流程 |