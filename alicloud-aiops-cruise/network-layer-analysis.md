# aiops-cruise 网络层巡检能力评估与优化方案

**评估时间**: 2026-07-01  
**评估范围**: EIP / SLB(CLB) / ALB / NAT / 安全组  
**当前版本**: aiops-cruise v1.5.2

---

## 一、现状评估

### 1.1 已有能力

| 网络组件 | 基础监控 | 深度巡检 | 异常检测 | 所在位置 |
|---------|---------|---------|---------|---------|
| **EIP** | ✅ 带宽使用率 | ❌ | ❌ | `01-daily-health-check.md` Step 2.2 |
| **SLB/CLB** | ✅ 健康检查失败数、并发连接、新建连接 | ❌ | ❌ | `01-daily-health-check.md` Step 2.3 |
| **NAT** | ✅ SNAT连接数、端口分配失败 | ❌ | ❌ | `01-daily-health-check.md` Step 2.6 |
| **ALB** | ❌ | ❌ | ❌ | **完全缺失** |
| **安全组** | ⚠️ 仅ActionTrail审计 | ❌ | ❌ | `02-emergency-troubleshoot.md` |

### 1.2 关键缺失项

#### EIP 深度监控缺失
```yaml
缺失指标:
  - net_in.rate_percentage / net_out.rate_percentage  # 已有，但缺少阈值告警
  - net_in.pps / net_out.pps                          # PPS 包速率 - 缺失
  - outdrop_rate / indrop_rate                        # 丢包率 - 缺失
  - BandwidthLimitExceeded                            # 带宽超限 - 缺失
  - 异常流量模式检测 (突发/DDoS)                      # 缺失
```

#### SLB/CLB 深度监控缺失
```yaml
已有指标 (基础):
  - UnhealthyServerCount            # 健康检查失败数
  - ActiveConnection                # 并发连接数
  - NewConnection                   # 新建连接数

缺失指标 (关键):
  - InstanceStatusCode2xx/4xx/5xx   # HTTP状态码分布 - 缺失
  - InstanceRt                      # 平均响应时间 - 缺失
  - InstanceQps                     # 每秒查询数 - 缺失
  - InstanceDropConnection          # 丢弃连接数 - 缺失
  - InstanceDropPacket              # 丢弃包数 - 缺失
  - 证书过期检测                     # 缺失

注意: CloudMonitor 中 SLB 指标需要 Instance 前缀，如 InstanceActiveConnection
```

#### NAT 深度监控缺失
```yaml
已有指标 (基础):
  - SnatConnection                    # SNAT连接数
  - EniPacketsDropPortAllocationFail  # 端口分配失败 - 关键指标

缺失指标 (重要):
  - InRatePercent / OutRatePercent    # 网关带宽使用率 (非 net_in.rate_percentage)
  - ActiveConnection                  # 活跃连接数
  - MaxConnection                     # 最大连接数
  
注意: NAT 带宽指标为 InRatePercent/OutRatePercent
```

#### ALB 完全缺失
```yaml
ALB 需要补充的完整监控体系 (命名空间: acs_alb):
  实例层:
    - ActiveConnection            # 活跃连接数
    - MaxConnection               # 最大连接数
    - NewConnection               # 新建连接数
    - RejectedConnection          # 拒绝连接数
    
  HTTP 层:
    - HTTPCode2XX/3XX/4XX/5XX     # HTTP状态码 (区分大小写)
    - ResponseLatency             # 响应时间 (非 Rt)
    - QPS                         # QPS (大写)
    
  流量层:
    - InBytes / OutBytes          # 入出流量 (非 InTraffic/OutTraffic)
    
  后端层:
    - UnhealthyServerCount        # 不健康后端数

注意: ALB 命名空间为 acs_alb (非 acs_alb_dashboard)，指标名区分大小写
```

---

## 二、优化方案

### 2.1 增强 EIP 巡检 (runbooks/01-daily-health-check.md)

**在 Step 2.2 后补充:**

```bash
#### Step 2.2-ext: EIP 深度巡检与异常检测

for EIP in $(aliyun vpc DescribeEipAddresses --RegionId "$REGION" --PageSize 50 | jq -r '.EipAddresses.EipAddress[].AllocationId'); do
  EIP_DETAIL=$(aliyun vpc DescribeEipAddresses --RegionId "$REGION" --AllocationId "$EIP")
  BANDWIDTH=$(echo "$EIP_DETAIL" | jq -r '.EipAddresses.EipAddress[0].Bandwidth // "0"')
  INSTANCE_REF=$(echo "$EIP_DETAIL" | jq -r '.EipAddresses.EipAddress[0] | .InstanceId + "(" + .InstanceType + ")" // "未绑定"')
  INTERNET_CHARGE_TYPE=$(echo "$EIP_DETAIL" | jq -r '.EipAddresses.EipAddress[0].InternetChargeType // "PayByBandwidth"')
  
  # 基础带宽使用率
  IN_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_in.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP\"}]" \
    --Period 3600 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // -1')
  
  OUT_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_out.rate_percentage \
    --Dimensions "[{\"instanceId\":\"$EIP\"}]" \
    --Period 3600 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // -1')
  
  # === 新增: PPS 监控 (Packets Per Second) ===
  IN_PPS=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_in.pps \
    --Dimensions "[{\"instanceId\":\"$EIP\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  OUT_PPS=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName net_out.pps \
    --Dimensions "[{\"instanceId\":\"$EIP\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # === 新增: 丢包率监控 ===
  IN_DROP=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName indrop_rate \
    --Dimensions "[{\"instanceId\":\"$EIP\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | max // 0')
  
  OUT_DROP=$(aliyun cms DescribeMetricList \
    --Namespace acs_vpc_eip \
    --MetricName outdrop_rate \
    --Dimensions "[{\"instanceId\":\"$EIP\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | max // 0')
  
  echo "[DIAG] EIP $EIP (${BANDWIDTH}Mbps, $INSTANCE_REF): IN=${IN_PCT}% OUT=${OUT_PCT}% PPS(IN/OUT)=${IN_PPS}/${OUT_PPS} DROP(IN/OUT)=${IN_DROP}%/${OUT_DROP}%"
  
  # === 新增: 异常检测 ===
  ALERTS=""
  
  # 带宽使用率告警
  if (( $(echo "$IN_PCT > 80" | bc -l) )) || (( $(echo "$OUT_PCT > 80" | bc -l) )); then
    ALERTS="${ALERTS}[WARN-带宽使用率>80%] "
  fi
  
  # 带宽超限检测 (按量付费实例)
  if [[ "$INTERNET_CHARGE_TYPE" == "PayByTraffic" ]]; then
    if (( $(echo "$IN_PCT >= 100" | bc -l) )) || (( $(echo "$OUT_PCT >= 100" | bc -l) )); then
      ALERTS="${ALERTS}[CRITICAL-带宽超限] "
    fi
  fi
  
  # 丢包率告警 (>0.1% 为异常)
  if (( $(echo "$IN_DROP > 0.1" | bc -l) )) || (( $(echo "$OUT_DROP > 0.1" | bc -l) )); then
    ALERTS="${ALERTS}[WARN-丢包率>0.1%] "
  fi
  
  # 突发流量检测 (PPS > 100k 为异常)
  if (( $(echo "$IN_PPS > 100000" | bc -l) )) || (( $(echo "$OUT_PPS > 100000" | bc -l) )); then
    ALERTS="${ALERTS}[WARN-PPS突发>100k] "
  fi
  
  if [[ -n "$ALERTS" ]]; then
    echo "[ALERT] EIP $EIP $ALERTS"
  fi
done
```

### 2.2 增强 SLB/CLB 巡检 (runbooks/01-daily-health-check.md)

**替换 Step 2.3:**

```bash
#### Step 2.3: SLB 深度巡检与异常检测

for LB_ID in $(echo "$SLB_LIST" | jq -r '.LoadBalancerId'); do
  LB_DETAIL=$(aliyun slb DescribeLoadBalancerAttribute --LoadBalancerId "$LB_ID")
  LB_NAME=$(echo "$LB_DETAIL" | jq -r '.LoadBalancerName // "N/A"')
  LB_SPEC=$(echo "$LB_DETAIL" | jq -r '.LoadBalancerSpec // "slb.s1.small"')
  ADDRESS=$(echo "$LB_DETAIL" | jq -r '.Address')
  
  echo "[DIAG] 检查 SLB: $LB_ID ($LB_NAME, $LB_SPEC, $ADDRESS)"
  
  # === 基础指标 (已有) ===
  UNHEALTHY=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName UnhealthyServerCount \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  # 注意: SLB CloudMonitor 指标需要 Instance 前缀
  ACTIVE_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceActiveConnection \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  NEW_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceNewConnection \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # === 新增: HTTP 状态码分布 (仅 HTTP/HTTPS 监听) - Instance 前缀 ===
  HTTP_2XX=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceStatusCode2xx \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add // 0')
  
  HTTP_4XX=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceStatusCode4xx \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add // 0')
  
  HTTP_5XX=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceStatusCode5xx \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add // 0')
  
  # === 新增: 响应时间 - Instance 前缀 ===
  RT_AVG=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceRt \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  RT_MAX=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName MaxRt \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  # === 新增: 流量指标 ===
  IN_TRAFFIC=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InTraffic \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  OUT_TRAFFIC=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName OutTraffic \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # === 新增: 丢弃指标 ===
  DROP_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName DropConnection \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add // 0')
  
  DROP_PKT=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName DropPacket \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add // 0')
  
  # === 新增: QPS - Instance 前缀 ===
  QPS=$(aliyun cms DescribeMetricList \
    --Namespace acs_slb_dashboard \
    --MetricName InstanceQps \
    --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  echo "[DIAG] SLB $LB_ID: unhealthy=$UNHEALTHY activeConn=$ACTIVE_CONN newConn=$NEW_CONN"
  echo "[DIAG]   HTTP(2xx/4xx/5xx)=${HTTP_2XX}/${HTTP_4XX}/${HTTP_5XX} RT(avg/max)=${RT_AVG}ms/${RT_MAX}ms"
  echo "[DIAG]   Traffic(IN/OUT)=${IN_TRAFFIC}/${OUT_TRAFFIC} Drop(conn/pkt)=${DROP_CONN}/${DROP_PKT} QPS=$QPS"
  
  # === 新增: 异常检测 ===
  ALERTS=""
  
  # 健康检查失败告警
  if [[ "$UNHEALTHY" -gt 0 ]]; then
    ALERTS="${ALERTS}[WARN-后端不健康数=$UNHEALTHY] "
  fi
  
  # 5xx 错误告警 (>1% 为异常)
  TOTAL_HTTP=$((HTTP_2XX + HTTP_4XX + HTTP_5XX))
  if [[ $TOTAL_HTTP -gt 0 ]]; then
    HTTP_5XX_PCT=$(echo "scale=2; $HTTP_5XX * 100 / $TOTAL_HTTP" | bc)
    if (( $(echo "$HTTP_5XX_PCT > 1" | bc -l) )); then
      ALERTS="${ALERTS}[WARN-5xx率=${HTTP_5XX_PCT}%] "
    fi
  fi
  
  # 响应时间告警 (>1000ms 为异常)
  if (( $(echo "$RT_AVG > 1000" | bc -l) )); then
    ALERTS="${ALERTS}[WARN-平均响应时间>${RT_AVG}ms] "
  fi
  
  # 丢包/丢连接告警
  if [[ "$DROP_CONN" -gt 0 ]] || [[ "$DROP_PKT" -gt 0 ]]; then
    ALERTS="${ALERTS}[WARN-丢包/连接丢弃] "
  fi
  
  # 连接数规格检查
  SPEC_LIMIT=$(case $LB_SPEC in
    slb.s1.small) echo 5000 ;;
    slb.s2.small) echo 50000 ;;
    slb.s2.medium) echo 100000 ;;
    slb.s3.small) echo 200000 ;;
    slb.s3.medium) echo 500000 ;;
    slb.s3.large) echo 1000000 ;;
    *) echo 5000 ;;
  esac)
  
  if (( $(echo "$ACTIVE_CONN > $SPEC_LIMIT * 0.8" | bc -l) )); then
    ALERTS="${ALERTS}[WARN-连接数接近规格上限(${ACTIVE_CONN}/${SPEC_LIMIT})] "
  fi
  
  if [[ -n "$ALERTS" ]]; then
    echo "[ALERT] SLB $LB_ID $ALERTS"
  fi
done
```

### 2.3 增强 NAT 巡检 (runbooks/01-daily-health-check.md)

**替换 Step 2.6:**

```bash
#### Step 2.6: NAT 深度巡检与异常检测

for NAT_ID in $(aliyun vpc DescribeNatGateways --RegionId "$REGION" | jq -r '.NatGateways.NatGateway[].NatGatewayId'); do
  NAT_DETAIL=$(aliyun vpc DescribeNatGateways --RegionId "$REGION" --NatGatewayId "$NAT_ID")
  NAT_SPEC=$(echo "$NAT_DETAIL" | jq -r '.NatGateways.NatGateway[0].Spec // "Small"')
  NAT_NAME=$(echo "$NAT_DETAIL" | jq -r '.NatGateways.NatGateway[0].Name // "N/A"')
  
  echo "[DIAG] 检查 NAT: $NAT_ID ($NAT_NAME, Spec=$NAT_SPEC)"
  
  # === 基础指标 (已有) ===
  NAT_SNAT=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName SnatConnection \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 3600 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  DROP_FAIL=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName EniPacketsDropPortAllocationFail \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 3600 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Sum] | add // 0')
  
  # === 新增: 带宽监控 - InRatePercent/OutRatePercent ===
  NAT_IN_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName InRatePercent \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  NAT_OUT_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName OutRatePercent \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # === 新增: 活跃会话数 ===
  ACTIVE_SESSION=$(aliyun cms DescribeMetricList \
    --Namespace acs_nat_gateway \
    --MetricName ActiveConnection \
    --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 计算端口使用率 (Small=55000, Medium=110000, Large: 220000, XLarge: 440000)
  PORT_LIMIT=$(case $NAT_SPEC in
    Small) echo 55000 ;;
    Medium) echo 110000 ;;
    Large) echo 220000 ;;
    XLarge) echo 440000 ;;
    *) echo 55000 ;;
  esac)
  
  PORT_USAGE_PCT=$(echo "scale=2; $PORT_USED * 100 / $PORT_LIMIT" | bc)
  
  echo "[DIAG] NAT $NAT_ID ($NAT_SPEC): SNAT=$NAT_SNAT 端口分配失败=$DROP_FAIL"
  echo "[DIAG]   带宽(IN/OUT)=${NAT_IN_PCT}%/${NAT_OUT_PCT}% 活跃会话=$ACTIVE_SESSION"
  echo "[DIAG]   端口使用=${PORT_USED}/${PORT_LIMIT} (${PORT_USAGE_PCT}%)"
  
  # === 异常检测 (已有+新增) ===
  ALERTS=""
  
  # 端口分配失败 (关键指标)
  if [[ "$DROP_FAIL" -gt 0 ]]; then
    ALERTS="${ALERTS}[CRITICAL-SNAT端口耗尽风险] "
  fi
  
  # 端口使用率告警 (>80%)
  if (( $(echo "$PORT_USAGE_PCT > 80" | bc -l) )); then
    ALERTS="${ALERTS}[WARN-端口使用率>${PORT_USAGE_PCT}%] "
  fi
  
  # 带宽告警 (>80%)
  if (( $(echo "$NAT_IN_PCT > 80" | bc -l) )) || (( $(echo "$NAT_OUT_PCT > 80" | bc -l) )); then
    ALERTS="${ALERTS}[WARN-NAT带宽使用率>80%] "
  fi
  
  # 活跃会话异常 (根据规格判断)
  SESSION_LIMIT=$(case $NAT_SPEC in
    Small) echo 1000000 ;;
    Medium) echo 2000000 ;;
    Large) echo 4000000 ;;
    XLarge) echo 8000000 ;;
    *) echo 1000000 ;;
  esac)
  
  if (( $(echo "$ACTIVE_SESSION > $SESSION_LIMIT * 0.8" | bc -l) )); then
    ALERTS="${ALERTS}[WARN-活跃会话接近上限] "
  fi
  
  if [[ -n "$ALERTS" ]]; then
    echo "[ALERT] NAT $NAT_ID $ALERTS"
  fi
done
```

### 2.4 新增 ALB 完整巡检 (runbooks/01-daily-health-check.md)

**在 Step 2.6 后新增 Step 2.7:**

```bash
#### Step 2.7: ALB 深度巡检与异常检测

# 获取 ALB 列表
ALB_LIST=$(aliyun alb ListLoadBalancers --RegionId "$REGION" --MaxResults 100 2>/dev/null | jq '.LoadBalancers // []')
ALB_COUNT=$(echo "$ALB_LIST" | jq 'length')

echo "[DIAG] 发现 ALB 实例: $ALB_COUNT"

for ALB_ID in $(echo "$ALB_LIST" | jq -r '.[].LoadBalancerId'); do
  ALB_DETAIL=$(aliyun alb GetLoadBalancerAttribute --LoadBalancerId "$ALB_ID")
  ALB_NAME=$(echo "$ALB_DETAIL" | jq -r '.LoadBalancer.LoadBalancerName // "N/A"')
  ALB_STATUS=$(echo "$ALB_DETAIL" | jq -r '.LoadBalancer.LoadBalancerStatus // "Unknown"')
  DNS_NAME=$(echo "$ALB_DETAIL" | jq -r '.LoadBalancer.DNSName // "N/A"')
  
  echo "[DIAG] 检查 ALB: $ALB_ID ($ALB_NAME, Status=$ALB_STATUS, DNS=$DNS_NAME)"
  
  # 实例层指标
  ACTIVE_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName ActiveConnection \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  MAX_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName MaxConnection \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  NEW_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName NewConnection \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  REJECTED_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName RejectedConnection \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Sum] | add // 0')
  
  # HTTP 状态码 (区分大小写: HTTPCode2XX/4XX/5XX)
  HTTP_2XX=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName HTTPCode2XX \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Sum] | add // 0')
  
  HTTP_4XX=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName HTTPCode4XX \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Sum] | add // 0')
  
  HTTP_5XX=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName HTTPCode5XX \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Sum] | add // 0')
  
  # 响应时间 (ResponseLatency，非 Rt)
  RT=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName ResponseLatency \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # QPS (大写)
  QPS=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName QPS \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 流量 (InBytes/OutBytes，非 InTraffic/OutTraffic)
  IN_TRAFFIC=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName InBytes \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  OUT_TRAFFIC=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName OutBytes \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // 0')
  
  # 后端健康
  UNHEALTHY=$(aliyun cms DescribeMetricList \
    --Namespace acs_alb \
    --MetricName UnhealthyServerCount \
    --Dimensions "[{\"instanceId\":\"$ALB_ID\"}]" \
    --Period 300 --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')
  
  echo "[DIAG] ALB $ALB_ID: Status=$ALB_STATUS"
  echo "[DIAG]   Connection(active/max/new/rejected)=${ACTIVE_CONN}/${MAX_CONN}/${NEW_CONN}/${REJECTED_CONN}"
  echo "[DIAG]   HTTP(2xx/4xx/5xx)=${HTTP_2XX}/${HTTP_4XX}/${HTTP_5XX} RT/Upstream=${RT}ms/${UPSTREAM_RT}ms"
  echo "[DIAG]   Traffic(IN/OUT)=${IN_TRAFFIC}/${OUT_TRAFFIC} QPS=$QPS Unhealthy=$UNHEALTHY"
  
  # 异常检测
  ALERTS=""
  
  # 实例状态
  if [[ "$ALB_STATUS" != "Active" ]]; then
    ALERTS="${ALERTS}[CRITICAL-ALB状态异常=$ALB_STATUS] "
  fi
  
  # 拒绝连接
  if [[ "$REJECTED_CONN" -gt 0 ]]; then
    ALERTS="${ALERTS}[WARN-拒绝连接数=$REJECTED_CONN] "
  fi
  
  # 5xx 告警
  TOTAL_HTTP=$((HTTP_2XX + HTTP_4XX + HTTP_5XX))
  if [[ $TOTAL_HTTP -gt 0 ]]; then
    HTTP_5XX_PCT=$(echo "scale=2; $HTTP_5XX * 100 / $TOTAL_HTTP" | bc)
    if (( $(echo "$HTTP_5XX_PCT > 1" | bc -l) )); then
      ALERTS="${ALERTS}[WARN-后端5xx率=${HTTP_5XX_PCT}%] "
    fi
  fi
  
  # 响应时间
  if (( $(echo "$RT > 1000" | bc -l) )); then
    ALERTS="${ALERTS}[WARN-ALB响应时间>${RT}ms] "
  fi
  
  # 后端响应时间差 (ALB RT vs Upstream RT)
  if [[ -n "$RT" && -n "$UPSTREAM_RT" && "$RT" != "0" && "$UPSTREAM_RT" != "0" ]]; then
    RT_DIFF=$(echo "$RT - $UPSTREAM_RT" | bc)
    if (( $(echo "$RT_DIFF > 50" | bc -l) )); then
      ALERTS="${ALERTS}[WARN-ALB转发延迟>${RT_DIFF}ms] "
    fi
  fi
  
  # 后端不健康
  if [[ "$UNHEALTHY" -gt 0 ]]; then
    ALERTS="${ALERTS}[WARN-后端不健康数=$UNHEALTHY] "
  fi
  
  if [[ -n "$ALERTS" ]]; then
    echo "[ALERT] ALB $ALB_ID $ALERTS"
  fi
done
```

---

## 三、实施建议

### 3.1 实施优先级

| 优先级 | 内容 | 预计工作量 | 影响 |
|-------|------|-----------|------|
| **P0** | 新增 ALB 巡检 Step 2.7 | 4h | 填补空白，覆盖 L7 负载均衡 |
| **P0** | 增强 SLB 巡检 (HTTP/5xx/RT/QPS) | 2h | 提升 CLB 异常检测能力 |
| **P1** | 增强 EIP 巡检 (PPS/丢包率) | 1.5h | 入口层质量监控 |
| **P1** | 增强 NAT 巡检 (带宽/端口使用率) | 1.5h | 出网层稳定性保障 |
| **P2** | 证书过期检测 (SLB/ALB) | 2h | 安全基线 |

### 3.2 依赖条件

```bash
# 需要确保已安装 bc 用于浮点数计算
# macOS: brew install bc
# Linux: apt-get install bc 或 yum install bc

# 或在脚本中添加兼容性处理
if ! command -v bc &> /dev/null; then
  # 使用 awk 替代
  compare_gt() { awk "BEGIN{exit !($1 > $2)}"; }
else
  compare_gt() { (( $(echo "$1 > $2" | bc -l) )); }
fi
```

### 3.3 新增 Runbook 建议

考虑新增专门的网络层巡检 Runbook:

```
runbooks/
├── 11-network-layer-inspection.md    # 新增: 网络层专项巡检
```

内容覆盖:
- 全链路连通性测试 (VPC 内/跨 VPC/公网)
- 安全组规则审计 (开放端口/源 IP 范围)
- 网络 ACL 检查
- 路由表分析
- DNS 解析测试

---

## 四、CloudMonitor 命名空间速查

| 产品 | 命名空间 | 关键指标 |
|------|---------|---------|
| EIP | acs_vpc_eip | net_in.rate_percentage, net_out.rate_percentage, net_in.pps, indrop_rate |
| SLB/CLB | acs_slb_dashboard | UnhealthyServerCount, **Instance**ActiveConnection, **Instance**StatusCode2xx/4xx/5xx, **Instance**Rt, **Instance**Qps |
| ALB | **acs_alb** | ActiveConnection, **HTTPCode**2XX/4XX/5XX, **ResponseLatency**, **QPS** |
| NAT | acs_nat_gateway | SnatConnection, EniPacketsDropPortAllocationFail, **InRatePercent/OutRatePercent**, ActiveConnection |

---

## 五、总结

**当前 aiops-cruise 网络层巡检能力评分: 45/100**

| 维度 | 评分 | 说明 |
|------|------|------|
| EIP | 40/100 | 仅有基础带宽监控 |
| SLB/CLB | 50/100 | 有基础连接监控，缺少 HTTP 状态码/延迟/QPS |
| ALB | 0/100 | **完全缺失** |
| NAT | 50/100 | 有 SNAT 监控，缺少带宽/端口使用率 |

**优化后预期评分: 90/100**

实施本方案后，aiops-cruise 将具备完整的四层+七层网络负载均衡巡检能力，覆盖入口(EIP)->分发(CLB/ALB)->出网(NAT)全链路。
