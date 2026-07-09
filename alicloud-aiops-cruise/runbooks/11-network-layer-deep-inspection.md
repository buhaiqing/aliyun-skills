# Runbook 11: 网络层深度巡检与异常检测

> **场景编号**: 11  
> **场景名称**: 网络层深度巡检  
> **风险等级**: 中  
> **执行时间**: 15-25min  
> **适用时机**: 周度巡检 / 网络故障排查 / 大促前预检

## 概述

本 Runbook 提供阿里云网络层组件的深度巡检能力，重点覆盖**公网出入带宽**的用量检测和异常分析：

- **EIP** (弹性公网IP) - **重点：公网出入带宽用量、带宽使用率、带宽异常检测**
- **SLB/CLB** (传统负载均衡) - HTTP状态码、RT、QPS、连接数
- **ALB** (应用型负载均衡) - L7 指标、后端健康
- **NAT** (NAT网关) - SNAT连接数、端口使用率、带宽

---

## 前置条件

```bash
# 1. 环境变量检查
echo "ALIBABA_CLOUD_ACCESS_KEY_ID: ${ALIBABA_CLOUD_ACCESS_KEY_ID:-(unset)}"
echo "ALIBABA_CLOUD_REGION_ID: ${ALIBABA_CLOUD_REGION_ID:-(unset)}"

# 2. 依赖工具检查
command -v jq >/dev/null 2>&1 || { echo "jq is required but not installed."; exit 1; }
command -v bc >/dev/null 2>&1 || echo "[WARN] bc not installed, floating point comparisons may fail"

# 3. 时间窗口设置 (最近6小时)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START_TIME=$(date -u -d '6 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-6H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)
```

---

## Phase 1: 拓扑发现与资源清单 (预计 3min)

### Step 1.1: 扫描网络层资源

```bash
echo "=============================================="
echo "Phase 1: 网络层资源发现"
echo "=============================================="

REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"

# 扫描 EIP
echo "[DIAG] 扫描 EIP..."
EIP_LIST=$(aliyun vpc DescribeEipAddresses --RegionId "$REGION" --PageSize 100 2>/dev/null)
EIP_COUNT=$(echo "$EIP_LIST" | jq '.EipAddresses.EipAddress | length // 0')
echo "[RESULT] EIP 数量: $EIP_COUNT"

# 扫描 SLB
echo "[DIAG] 扫描 SLB..."
SLB_LIST=$(aliyun slb DescribeLoadBalancers --RegionId "$REGION" --PageSize 100 2>/dev/null)
SLB_COUNT=$(echo "$SLB_LIST" | jq '.LoadBalancers.LoadBalancer | length // 0')
echo "[RESULT] SLB 数量: $SLB_COUNT"

# 扫描 ALB
echo "[DIAG] 扫描 ALB..."
ALB_LIST=$(aliyun alb ListLoadBalancers --RegionId "$REGION" --MaxResults 100 2>/dev/null)
ALB_COUNT=$(echo "$ALB_LIST" | jq '.LoadBalancers | length // 0')
echo "[RESULT] ALB 数量: $ALB_COUNT"

# 扫描 NAT
echo "[DIAG] 扫描 NAT..."
NAT_LIST=$(aliyun vpc DescribeNatGateways --RegionId "$REGION" 2>/dev/null)
NAT_COUNT=$(echo "$NAT_LIST" | jq '.NatGateways.NatGateway | length // 0')
echo "[RESULT] NAT 数量: $NAT_COUNT"

echo ""
echo "=============================================="
echo "网络层资源汇总"
echo "=============================================="
echo "| 组件 | 数量 |"
echo "|-------|------|"
echo "| EIP  | $EIP_COUNT |"
echo "| SLB  | $SLB_COUNT |"
echo "| ALB  | $ALB_COUNT |"
echo "| NAT  | $NAT_COUNT |"
```

---

## Phase 2: EIP 公网带宽深度监控 (预计 8min)

> **核心重点**: 本 Phase 重点检测 EIP 的公网出入带宽使用情况，包括：
> - 带宽配置信息 (带宽值、计费方式、ISP)
> - 公网出入带宽实际使用率
> - 带宽异常检测 (超限、低利用率、数据泄露风险)
> - 带宽趋势分析 (6小时)
> - 带宽容量评估

### Step 2.1: EIP 带宽配置信息汇总

```bash
echo ""
echo "=============================================="
echo "Phase 2.1: EIP 公网带宽配置信息"
echo "=============================================="

echo ""
echo "### 2.1.1 EIP 带宽配置汇总"
echo "| AllocationId | 带宽配置 | 计费方式 | ISP | 绑定对象 | 绑定类型 |"
echo "|-------------|---------|---------|-----|----------|----------|"

for EIP_ID in $(echo "$EIP_LIST" | jq -r '.EipAddresses.EipAddress[].AllocationId'); do
  EIP_DETAIL=$(echo "$EIP_LIST" | jq -r ".EipAddresses.EipAddress[] | select(.AllocationId==\"$EIP_ID\")")
  BANDWIDTH=$(echo "$EIP_DETAIL" | jq -r '.Bandwidth // "0"')
  ISP=$(echo "$EIP_DETAIL" | jq -r '.ISP // "BGP"')
  CHARGE_TYPE=$(echo "$EIP_DETAIL" | jq -r '.InternetChargeType // "PayByBandwidth"')
  INSTANCE_ID=$(echo "$EIP_DETAIL" | jq -r '.InstanceId // ""')
  INSTANCE_TYPE=$(echo "$EIP_DETAIL" | jq -r '.InstanceType // ""')
  
  if [[ -z "$INSTANCE_ID" ]]; then
    BIND_INFO="未绑定"
    BIND_TYPE="-"
  else
    BIND_INFO="$INSTANCE_ID"
    BIND_TYPE="$INSTANCE_TYPE"
  fi
  
  echo "| $EIP_ID | ${BANDWIDTH}Mbps | $CHARGE_TYPE | $ISP | $BIND_INFO | $BIND_TYPE |"
done
```

### Step 2.2: EIP 公网出入带宽用量详情

```bash
echo ""
echo "=============================================="
echo "Phase 2.2: EIP 公网出入带宽用量检测"
echo "=============================================="

echo ""
echo "### 2.2.1 公网出入带宽使用率详情 (最近6小时峰值)"
echo "| AllocationId | 配置带宽 | 入带宽使用率% | 出带宽使用率% | 入流量(Mbps) | 出流量(Mbps) | 入PPS | 出PPS | 状态 |"
echo "|-------------|---------|-------------|-------------|-------------|-------------|-------|-------|------|"

for EIP_ID in $(echo "$EIP_LIST" | jq -r '.EipAddresses.EipAddress[].AllocationId'); do
  EIP_DETAIL=$(echo "$EIP_LIST" | jq -r ".EipAddresses.EipAddress[] | select(.AllocationId==\"$EIP_ID\")")
  BANDWIDTH=$(echo "$EIP_DETAIL" | jq -r '.Bandwidth // "0"')
  
  # 入方向带宽使用率 (峰值)
  IN_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_in.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Maximum] | max // -1')
  
  # 出方向带宽使用率 (峰值)
  OUT_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_out.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Maximum] | max // -1')
  
  # 入方向流量 (Mbps)
  IN_TRAFFIC=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_in.rate \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 出方向流量 (Mbps)
  OUT_TRAFFIC=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_out.rate \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # PPS
  IN_PPS=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_in.pps \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  OUT_PPS=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_out.pps \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 状态评估
  EIP_STATUS="正常"
  if (( $(echo "$IN_PCT > 80 || $OUT_PCT > 80" | bc -l 2>/dev/null || echo 0) )); then
    EIP_STATUS="带宽告警"
  fi
  if (( $(echo "$IN_PCT >= 100 || $OUT_PCT >= 100" | bc -l 2>/dev/null || echo 0) )); then
    EIP_STATUS="带宽满载"
  fi
  
  echo "| $EIP_ID | ${BANDWIDTH}Mbps | ${IN_PCT}% | ${OUT_PCT}% | ${IN_TRAFFIC} | ${OUT_TRAFFIC} | ${IN_PPS} | ${OUT_PPS} | $EIP_STATUS |"
done
```

### Step 2.3: EIP 公网带宽异常检测

```bash
echo ""
echo "### 2.3.1 公网带宽异常检测规则"
echo ""
echo "[DIAG] 开始检测 EIP 公网带宽异常..."

EIP_BANDWIDTH_ALERTS_COUNT=0

for EIP_ID in $(echo "$EIP_LIST" | jq -r '.EipAddresses.EipAddress[].AllocationId'); do
  EIP_DETAIL=$(echo "$EIP_LIST" | jq -r ".EipAddresses.EipAddress[] | select(.AllocationId==\"$EIP_ID\")")
  BANDWIDTH=$(echo "$EIP_DETAIL" | jq -r '.Bandwidth // "0"')
  CHARGE_TYPE=$(echo "$EIP_DETAIL" | jq -r '.InternetChargeType // "PayByBandwidth"')
  
  # 获取带宽使用率
  IN_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_in.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Maximum] | max // -1')
  
  OUT_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_out.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Maximum] | max // -1')
  
  # 获取丢包率
  IN_DROP=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName indrop_rate \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | max // 0')
  
  OUT_DROP=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName outdrop_rate \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | max // 0')
  
  ALERTS=""
  
  # ========== 异常检测规则 ==========
  
  # 规则1: 入带宽使用率超过80%告警
  if (( $(echo "$IN_PCT > 80" | bc -l 2>/dev/null || echo 0) )); then
    ALERTS="${ALERTS}[WARN-入带宽使用率${IN_PCT}%>80%] "
  fi
  
  # 规则2: 出带宽使用率超过80%告警
  if (( $(echo "$OUT_PCT > 80" | bc -l 2>/dev/null || echo 0) )); then
    ALERTS="${ALERTS}[WARN-出带宽使用率${OUT_PCT}%>80%] "
  fi
  
  # 规则3: 带宽使用率超过100% (带宽满载/超限)
  if (( $(echo "$IN_PCT >= 100" | bc -l 2>/dev/null || echo 0) )); then
    ALERTS="${ALERTS}[CRITICAL-入带宽超限(${IN_PCT}%)] "
  fi
  if (( $(echo "$OUT_PCT >= 100" | bc -l 2>/dev/null || echo 0) )); then
    ALERTS="${ALERTS}[CRITICAL-出带宽超限(${OUT_PCT}%)] "
  fi
  
  # 规则4: 按流量计费检测异常高峰 (费用风险)
  if [[ "$CHARGE_TYPE" == "PayByTraffic" ]]; then
    if (( $(echo "$IN_PCT > 70" | bc -l 2>/dev/null || echo 0) )); then
      ALERTS="${ALERTS}[WARN-按流量计费入带宽(${IN_PCT}%)较高,注意费用] "
    fi
  fi
  
  # 规则5: 出方向带宽异常高 (可能有数据泄露风险)
  if (( $(echo "$OUT_PCT > $IN_PCT * 2" | bc -l 2>/dev/null || echo 0) )) && \
     (( $(echo "$OUT_PCT > 50" | bc -l 2>/dev/null || echo 0) )); then
    ALERTS="${ALERTS}[CRITICAL-出带宽(${OUT_PCT}%)>入带宽(${IN_PCT}%)2倍,疑似数据泄露] "
  fi
  
  # 规则6: 入方向丢包 (网络质量问题)
  if (( $(echo "$IN_DROP > 0.1" | bc -l 2>/dev/null || echo 0) )); then
    ALERTS="${ALERTS}[CRITICAL-入方向丢包率${IN_DROP}%>0.1%] "
  fi
  
  # 规则7: 出方向丢包 (网络质量问题)
  if (( $(echo "$OUT_DROP > 0.1" | bc -l 2>/dev/null || echo 0) )); then
    ALERTS="${ALERTS}[CRITICAL-出方向丢包率${OUT_DROP}%>0.1%] "
  fi
  
  # 规则8: 带宽使用率过低 (成本优化)
  if (( $(echo "$IN_PCT >= 0 && $IN_PCT < 10 && $OUT_PCT >= 0 && $OUT_PCT < 10" | bc -l 2>/dev/null || echo 0) )); then
    ALERTS="${ALERTS}[INFO-带宽使用率<10%,建议降配节省成本] "
  fi
  
  # 输出告警
  if [[ -n "$ALERTS" ]]; then
    EIP_BANDWIDTH_ALERTS_COUNT=$((EIP_BANDWIDTH_ALERTS_COUNT + 1))
    echo "[ALERT] EIP $EIP_ID (${BANDWIDTH}Mbps, $CHARGE_TYPE): $ALERTS"
  fi
done

echo ""
echo "[RESULT] EIP 公网带宽异常检测完成, 发现 $EIP_BANDWIDTH_ALERTS_COUNT 个异常项"
```

### Step 2.4: EIP 公网带宽趋势分析

```bash
echo ""
echo "### 2.4.1 EIP 公网带宽趋势分析 (最近6小时)"

echo ""
echo "| AllocationId | 配置带宽 | 入带宽峰值% | 出带宽峰值% | 峰值时间 | 趋势 | 建议 |"
echo "|-------------|---------|-----------|-----------|---------|------|------|"

for EIP_ID in $(echo "$EIP_LIST" | jq -r '.EipAddresses.EipAddress[].AllocationId'); do
  EIP_DETAIL=$(echo "$EIP_LIST" | jq -r ".EipAddresses.EipAddress[] | select(.AllocationId==\"$EIP_ID\")")
  BANDWIDTH=$(echo "$EIP_DETAIL" | jq -r '.Bandwidth // "0"')
  
  # 获取6小时数据点
  IN_DATA=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_in.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 3600 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | .[] | select(.Maximum > 0) | {ts: .Timestamp, val: .Maximum}')
  
  OUT_DATA=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_out.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 3600 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | .[] | select(.Maximum > 0) | {ts: .Timestamp, val: .Maximum}')
  
  # 计算峰值
  IN_PEAK=$(echo "$IN_DATA" | jq -s '[.[] | .val] | max // 0')
  OUT_PEAK=$(echo "$OUT_DATA" | jq -s '[.[] | .val] | max // 0')
  
  # 峰值时间
  IN_PEAK_TS=$(echo "$IN_DATA" | jq -s 'map(select(.val == '"$IN_PEAK"')) | .[0].ts // empty')
  OUT_PEAK_TS=$(echo "$OUT_DATA" | jq -s 'map(select(.val == '"$OUT_PEAK"')) | .[0].ts // empty')
  
  # 趋势判断
  TREND="稳定"
  SUGGESTION="-"
  
  MAX_PEAK=$(echo "$IN_PEAK $OUT_PEAK" | awk '{print ($1 > $2 ? $1 : $2)}')
  
  if (( $(echo "$MAX_PEAK > 80" | bc -l 2>/dev/null || echo 0) )); then
    TREND="高位运行"
    SUGGESTION="考虑扩容或分散流量"
  elif (( $(echo "$MAX_PEAK > 50" | bc -l 2>/dev/null || echo 0) )); then
    TREND="中位运行"
    SUGGESTION="正常范围"
  else
    TREND="低位运行"
    SUGGESTION="可降配节省成本"
  fi
  
  echo "| $EIP_ID | ${BANDWIDTH}Mbps | ${IN_PEAK}% | ${OUT_PEAK}% | 入:$IN_PEAK_TS 出:$OUT_PEAK_TS | $TREND | $SUGGESTION |"
done
```

### Step 2.5: EIP 带宽容量评估

```bash
echo ""
echo "### 2.5.1 EIP 带宽容量评估与优化建议"

echo ""
echo "| AllocationId | 带宽配置 | 计费方式 | 峰值利用率% | 剩余容量% | 容量状态 | 优化建议 |"
echo "|-------------|---------|---------|-----------|----------|----------|----------|"

for EIP_ID in $(echo "$EIP_LIST" | jq -r '.EipAddresses.EipAddress[].AllocationId'); do
  EIP_DETAIL=$(echo "$EIP_LIST" | jq -r ".EipAddresses.EipAddress[] | select(.AllocationId==\"$EIP_ID\")")
  BANDWIDTH=$(echo "$EIP_DETAIL" | jq -r '.Bandwidth // "0"')
  CHARGE_TYPE=$(echo "$EIP_DETAIL" | jq -r '.InternetChargeType // "PayByBandwidth"')
  
  IN_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_in.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Maximum] | max // -1')
  
  OUT_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_out.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Maximum] | max // -1')
  
  PEAK_PCT=$(echo "$IN_PCT $OUT_PCT" | awk '{print ($1 > $2 ? $1 : $2)}')
  REMAIN=$(echo "scale=0; 100 - $PEAK_PCT" | bc -l 2>/dev/null || echo "100")
  
  CAP_STATUS="充足"
  OPTIMIZE="无需优化"
  
  if (( $(echo "$PEAK_PCT > 80" | bc -l 2>/dev/null || echo 0) )); then
    CAP_STATUS="紧张"
    OPTIMIZE="立即扩容或分散流量"
  elif (( $(echo "$PEAK_PCT > 50" | bc -l 2>/dev/null || echo 0) )); then
    CAP_STATUS="良好"
    OPTIMIZE="容量足够"
  else
    CAP_STATUS="过剩"
    OPTIMIZE="考虑降配节省成本"
  fi
  
  echo "| $EIP_ID | ${BANDWIDTH}Mbps | $CHARGE_TYPE | ${PEAK_PCT}% | ${REMAIN}% | $CAP_STATUS | $OPTIMIZE |"
done
```

---

## Phase 3: SLB/CLB 深度监控 (预计 4min)

### Step 3.1: SLB 健康与性能监控

```bash
echo ""
echo "=============================================="
echo "Phase 3: SLB/CLB 深度巡检"
echo "=============================================="

echo ""
echo "### 3.1.1 SLB 健康与性能指标"
echo "| LoadBalancerId | 名称 | 规格 | 后端健康 | 活跃连接 | 新建连接 | 5xx率% | RT(ms) | QPS | 丢弃连接 | 状态 |"
echo "|----------------|------|------|-----------|----------|----------|--------|--------|-----|-----------|------|"

for LB_ID in $(echo "$SLB_LIST" | jq -r '.LoadBalancers.LoadBalancer[].LoadBalancerId'); do
  LB_DETAIL=$(aliyun slb DescribeLoadBalancerAttribute --LoadBalancerId "$LB_ID" 2>/dev/null)
  LB_NAME=$(echo "$LB_DETAIL" | jq -r '.LoadBalancerName // "N/A"')
  LB_SPEC=$(echo "$LB_DETAIL" | jq -r '.LoadBalancerSpec // "slb.s1.small"')
  
  # 后端健康数
  UNHEALTHY=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName UnhealthyServerCount \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  # 连接数
  ACTIVE_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceActiveConnection \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  NEW_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceNewConnection \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # HTTP 状态码
  HTTP_2XX=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceStatusCode2xx \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add // 0')
  
  HTTP_4XX=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceStatusCode4xx \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add // 0')
  
  HTTP_5XX=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceStatusCode5xx \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add // 0')
  
  # 响应时间
  RT_AVG=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceRt \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # QPS
  QPS=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceQps \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 丢连接
  DROP_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName DropConnection \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add // 0')
  
  # 计算 5xx 率
  TOTAL_HTTP=$((HTTP_2XX + HTTP_4XX + HTTP_5XX))
  if [[ $TOTAL_HTTP -gt 0 ]]; then
    HTTP_5XX_PCT=$(echo "scale=2; $HTTP_5XX * 100 / $TOTAL_HTTP" | bc 2>/dev/null || echo "0")
  else
    HTTP_5XX_PCT="0"
  fi
  
  # 状态评估
  SLB_STATUS="正常"
  SLB_ALERTS=""
  
  if [[ "$UNHEALTHY" -gt 0 ]]; then
    SLB_STATUS="后端异常"
    SLB_ALERTS="${SLB_ALERTS}[WARN-后端不健康=$UNHEALTHY] "
  fi
  
  if (( $(echo "$HTTP_5XX_PCT > 1" | bc -l 2>/dev/null || echo 0) )); then
    SLB_STATUS="5xx高"
    SLB_ALERTS="${SLB_ALERTS}[WARN-5xx率=${HTTP_5XX_PCT}%] "
  fi
  
  if (( $(echo "$RT_AVG > 1000" | bc -l 2>/dev/null || echo 0) )); then
    SLB_STATUS="延迟高"
    SLB_ALERTS="${SLB_ALERTS}[WARN-RT=${RT_AVG}ms] "
  fi
  
  if [[ "$DROP_CONN" -gt 0 ]]; then
    SLB_STATUS="丢连接"
    SLB_ALERTS="${SLB_ALERTS}[WARN-丢弃连接=$DROP_CONN] "
  fi
  
  echo "| $LB_ID | $LB_NAME | $LB_SPEC | $UNHEALTHY | $ACTIVE_CONN | $NEW_CONN | $HTTP_5XX_PCT | $RT_AVG | $QPS | $DROP_CONN | $SLB_STATUS |"
  
  [[ -n "$SLB_ALERTS" ]] && echo "[ALERT] SLB $LB_ID $SLB_ALERTS"
done
```

---

## Phase 4: ALB 深度监控 (预计 3min)

### Step 4.1: ALB 健康与性能监控

```bash
echo ""
echo "=============================================="
echo "Phase 4: ALB 深度巡检"
echo "=============================================="

echo ""
echo "### 4.1.1 ALB 健康与性能指标"
echo "| LoadBalancerId | 名称 | 状态 | 活跃连接 | 拒绝连接 | 5xx率% | RT(ms) | QPS | 不健康后端 | 状态 |"
echo "|----------------|------|------|----------|----------|--------|--------|-----|-------------|------|"

for ALB_ID in $(echo "$ALB_LIST" | jq -r '.[].LoadBalancerId'); do
  ALB_DETAIL=$(aliyun alb GetLoadBalancerAttribute --LoadBalancerId "$ALB_ID" 2>/dev/null)
  ALB_NAME=$(echo "$ALB_DETAIL" | jq -r '.LoadBalancer.LoadBalancerName // "N/A"')
  ALB_STATUS=$(echo "$ALB_DETAIL" | jq -r '.LoadBalancer.LoadBalancerStatus // "Unknown"')
  
  # 连接数
  ACTIVE_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName ActiveConnection \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  REJECTED_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName RejectedConnection \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Sum] | add // 0')
  
  # HTTP 状态码
  HTTP_2XX=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName HTTPCode2XX \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Sum] | add // 0')
  
  HTTP_4XX=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName HTTPCode4XX \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Sum] | add // 0')
  
  HTTP_5XX=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName HTTPCode5XX \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Sum] | add // 0')
  
  # 响应时间
  RT=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName ResponseLatency \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # QPS
  QPS=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName QPS \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 后端健康
  UNHEALTHY=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName UnhealthyServerCount \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  # 计算 5xx 率
  TOTAL_HTTP=$((HTTP_2XX + HTTP_4XX + HTTP_5XX))
  if [[ $TOTAL_HTTP -gt 0 ]]; then
    HTTP_5XX_PCT=$(echo "scale=2; $HTTP_5XX * 100 / $TOTAL_HTTP" | bc 2>/dev/null || echo "0")
  else
    HTTP_5XX_PCT="0"
  fi
  
  # 状态评估
  ALB_STATUS_DISPLAY="正常"
  ALB_ALERTS=""
  
  if [[ "$ALB_STATUS" != "Active" ]]; then
    ALB_STATUS_DISPLAY="实例异常"
    ALB_ALERTS="${ALB_ALERTS}[CRITICAL-ALB状态=$ALB_STATUS] "
  fi
  
  if [[ "$REJECTED_CONN" -gt 0 ]]; then
    ALB_STATUS_DISPLAY="拒绝连接"
    ALB_ALERTS="${ALB_ALERTS}[WARN-拒绝连接=$REJECTED_CONN] "
  fi
  
  if (( $(echo "$HTTP_5XX_PCT > 1" | bc -l 2>/dev/null || echo 0) )); then
    ALB_STATUS_DISPLAY="5xx高"
    ALB_ALERTS="${ALB_ALERTS}[WARN-5xx率=${HTTP_5XX_PCT}%] "
  fi
  
  if (( $(echo "$RT > 1000" | bc -l 2>/dev/null || echo 0) )); then
    ALB_STATUS_DISPLAY="延迟高"
    ALB_ALERTS="${ALB_ALERTS}[WARN-RT=${RT}ms] "
  fi
  
  echo "| $ALB_ID | $ALB_NAME | $ALB_STATUS | $ACTIVE_CONN | $REJECTED_CONN | $HTTP_5XX_PCT | $RT | $QPS | $UNHEALTHY | $ALB_STATUS_DISPLAY |"
  
  [[ -n "$ALB_ALERTS" ]] && echo "[ALERT] ALB $ALB_ID $ALB_ALERTS"
done
```

---

## Phase 5: NAT 网关深度监控 (预计 3min)

### Step 5.1: NAT 健康与性能监控

```bash
echo ""
echo "=============================================="
echo "Phase 5: NAT 网关深度巡检"
echo "=============================================="

echo ""
echo "### 5.1.1 NAT 网关健康与性能指标"
echo "| NatGatewayId | 名称 | 规格 | SNAT连接 | 端口分配失败 | 带宽% | 活跃会话 | 端口使用率% | 状态 |"
echo "|--------------|------|------|----------|--------------|-------|----------|-------------|------|"

for NAT_ID in $(echo "$NAT_LIST" | jq -r '.NatGateways.NatGateway[].NatGatewayId'); do
  NAT_DETAIL=$(echo "$NAT_LIST" | jq -r ".NatGateways.NatGateway[] | select(.NatGatewayId==\"$NAT_ID\")")
  NAT_NAME=$(echo "$NAT_DETAIL" | jq -r '.Name // "N/A"')
  NAT_SPEC=$(echo "$NAT_DETAIL" | jq -r '.Spec // "Small"')
  
  # SNAT 连接数
  SNAT_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName SnatConnection \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  # 端口分配失败
  DROP_FAIL=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName EniPacketsDropPortAllocationFail \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Sum] | add // 0')
  
  # 带宽使用率
  IN_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName InRatePercent \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  OUT_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName OutRatePercent \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 活跃会话
  ACTIVE_SESSION=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName ActiveConnection \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 端口使用
  NAT_API=$(aliyun vpc DescribeNatGateways --RegionId "$REGION" --NatGatewayId "$NAT_ID" 2>/dev/null)
  PORT_USED=$(echo "$NAT_API" | jq -r '.NatGateways.NatGateway[0].UsedPortsCount // 0')
  
  PORT_LIMIT=$(case $NAT_SPEC in
    Small) echo 55000 ;;
    Medium) echo 110000 ;;
    Large) echo 220000 ;;
    XLarge) echo 440000 ;;
    *) echo 55000 ;;
  esac)
  
  PORT_USAGE_PCT=$(echo "scale=2; $PORT_USED * 100 / $PORT_LIMIT" | bc 2>/dev/null || echo "0")
  
  # 状态评估
  NAT_STATUS="正常"
  NAT_ALERTS=""
  
  if [[ "$DROP_FAIL" -gt 0 ]]; then
    NAT_STATUS="端口耗尽"
    NAT_ALERTS="${NAT_ALERTS}[CRITICAL-端口分配失败=$DROP_FAIL] "
  fi
  
  if (( $(echo "$PORT_USAGE_PCT > 80" | bc -l 2>/dev/null || echo 0) )); then
    NAT_STATUS="端口告急"
    NAT_ALERTS="${NAT_ALERTS}[WARN-端口使用率=${PORT_USAGE_PCT}%] "
  fi
  
  BANDWIDTH_PCT=$(echo "scale=0; ($IN_PCT > $OUT_PCT ? $IN_PCT : $OUT_PCT)" | bc 2>/dev/null || echo "0")
  
  echo "| $NAT_ID | $NAT_NAME | $NAT_SPEC | $SNAT_CONN | $DROP_FAIL | $BANDWIDTH_PCT% | $ACTIVE_SESSION | $PORT_USAGE_PCT | $NAT_STATUS |"
  
  [[ -n "$NAT_ALERTS" ]] && echo "[ALERT] NAT $NAT_ID $NAT_ALERTS"
done
```

---

## Phase 6: 根因定位分析 (预计 3min)

### Step 6.1: 关联分析规则

```bash
echo ""
echo "=============================================="
echo "Phase 6: 根因定位分析"
echo "=============================================="

echo ""
echo "### 6.1.1 网络层故障根因定位规则"
echo ""

# 规则1: SLB 健康检查失败 + ECS 正常 = 安全组/ACL 问题
echo "[DIAG] 规则1: 检查 SLB 健康检查失败场景..."
if [[ "$UNHEALTHY" -gt 0 ]]; then
  echo "[ANALYSIS] SLB $LB_ID 后端不健康数=$UNHEALTHY"
  echo "  可能原因:"
  echo "    1. 安全组规则阻止了 SLB 到 ECS 的健康检查"
  echo "    2. ECS 端口未监听或应用未启动"
  echo "    3. 网络 ACL 阻止了健康检查流量"
  echo "  排查建议:"
  echo "    - 检查 ECS 安全组入方向允许 SLB 网段"
  echo "    - 检查 ECS 端口 netstat -tlnp | grep <port>"
fi

# 规则2: EIP 高 PPS + 低带宽 = DDoS 或攻击
echo ""
echo "[DIAG] 规则2: 检查 EIP 异常流量模式..."
for EIP_ID in $(echo "$EIP_LIST" | jq -r '.EipAddresses.EipAddress[].AllocationId'); do
  IN_PPS=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_in.pps \
    --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  if (( $(echo "$IN_PPS > 100000" | bc -l 2>/dev/null || echo 0) )); then
    echo "[ANALYSIS] EIP $EIP_ID PPS=$IN_PPS (异常)"
    echo "  可能原因:"
    echo "    1. DDoS 攻击或流量突发"
    echo "    2. 正常业务流量突增"
    echo "  排查建议:"
    echo "    - 检查云防火墙流量日志"
    echo "    - 检查是否有异常 IP 来源"
  fi
done

# 规则3: NAT 端口分配失败 = SNAT 端口耗尽
echo ""
echo "[DIAG] 规则3: 检查 NAT SNAT 端口耗尽..."
for NAT_ID in $(echo "$NAT_LIST" | jq -r '.NatGateways.NatGateway[].NatGatewayId'); do
  DROP_FAIL=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName EniPacketsDropPortAllocationFail \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 3600 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    2>/dev/null | jq '.Datapoints | fromjson | [.[].Sum] | add // 0')
  
  if [[ "$DROP_FAIL" -gt 0 ]]; then
    echo "[ANALYSIS] NAT $NAT_ID 端口分配失败=$DROP_FAIL"
    echo "  根因: SNAT 连接数超过网关规格上限"
    echo "  影响: 部分出站流量被丢弃，导致请求超时"
    echo "  解决方案:"
    echo "    1. 升级 NAT 网关规格 (Small -> Medium -> Large)"
    echo "    2. 部署多个 NAT 网关分散流量"
  fi
done
```

---

## Phase 7: 巡检报告生成 (预计 2min)

### Step 7.1: 生成巡检报告

```bash
echo ""
echo "=============================================="
echo "Phase 7: 生成巡检报告"
echo "=============================================="

echo ""
echo "=============================================="
echo "网络层巡检报告"
echo "=============================================="
echo "巡检时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "巡检区域: $REGION"
echo "巡检时段: $START_TIME ~ $END_TIME"
echo ""
echo "## 资源概览"
echo "| 组件 | 数量 |"
echo "|------|------|"
echo "| EIP  | $EIP_COUNT |"
echo "| SLB  | $SLB_COUNT |"
echo "| ALB  | $ALB_COUNT |"
echo "| NAT  | $NAT_COUNT |"
echo ""
echo "## EIP 公网带宽巡检汇总"
echo "| 指标 | 数值 |"
echo "|------|------|"
echo "| EIP 带宽异常数 | $EIP_BANDWIDTH_ALERTS_COUNT |"
echo ""
echo "## 详细告警"
echo "```"
grep "\[ALERT\]" <<< ""
echo "```"
echo ""
echo "=============================================="
echo "巡检完成"
echo "=============================================="
```

---

## 附录: CloudMonitor 命名空间速查

| 产品 | 命名空间 | 关键指标 |
|------|---------|---------|
| EIP | `acs_vpc_eip` | net_in.rate_percentage, net_out.rate_percentage, net_in.rate, net_out.rate, net_in.pps, indrop_rate |
| SLB/CLB | `acs_slb_dashboard` | UnhealthyServerCount, InstanceActiveConnection, InstanceStatusCode5xx, InstanceRt, InstanceQps |
| ALB | `acs_alb` | ActiveConnection, HTTPCode5XX, ResponseLatency, QPS, UnhealthyServerCount |
| NAT | `acs_nat_gateway` | SnatConnection, EniPacketsDropPortAllocationFail, InRatePercent, ActiveConnection |

---

## 执行时间估算

| Phase | 步骤 | 预计时间 |
|------|------|---------|
| Phase 1 | 拓扑发现 | 3min |
| Phase 2.1-2.5 | EIP 公网带宽深度巡检 | 8min |
| Phase 3 | SLB 深度巡检 | 4min |
| Phase 4 | ALB 深度巡检 | 3min |
| Phase 5 | NAT 深度巡检 | 3min |
| Phase 6 | 根因定位 | 3min |
| Phase 7 | 报告生成 | 2min |
| **总计** | | **26min** |
