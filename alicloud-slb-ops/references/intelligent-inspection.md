### Operation: Intelligent Inspection（智能巡检）

一键执行SLB实例的全面健康检查，整合实例状态 + 监听状态 + 后端健康 + CMS指标。

#### 执行流程

1. 调用 `DescribeLoadBalancerAttribute` 检查实例状态
2. 调用 `DescribeLoadBalancerListeners` 检查所有监听状态
3. 调用 `DescribeHealthStatus` 检查所有后端服务器健康状态
4. 调用 `alicloud-cms-ops` 查询最近15分钟的丢包/延迟/5xx指标
5. 检查证书过期时间（如有HTTPS监听）
6. 综合评分并生成巡检报告

#### 巡检评分标准

| 维度 | 评分依据 | 权重 |
|------|---------|------|
| 实例状态 | active=100, 其他=0 | 20% |
| 监听状态 | 全部running=100, 部分异常=50, 全部异常=0 | 20% |
| 后端健康比例 | 100%=100, >80%=60, <80%=0 | 25% |
| 丢包率 | 0%=100, <1%=60, >1%=0 | 15% |
| 5xx错误率 | 0%=100, <1%=60, >1%=0 | 10% |
| 证书有效期 | >30天=100, 7-30天=60, <7天=0 | 10% |

#### 执行 — CLI

```bash
#!/bin/bash
# slb-intelligent-inspection.sh
# Usage: ./slb-intelligent-inspection.sh <LoadBalancerId> <RegionId>

LB_ID="$1"
REGION="$2"
SCORE=0

echo "=== SLB Intelligent Inspection ==="
echo "Load Balancer: $LB_ID"
echo "Region: $REGION"
echo ""

# 1. Instance status check
STATUS=$(aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId "$LB_ID" \
  --output cols=LoadBalancerStatus rows=LoadBalancerStatus)
echo "[1/6] Instance Status: $STATUS"
[ "$STATUS" = "active" ] && SCORE=$((SCORE + 20))

# 2. Listener status check
LISTENERS=$(aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "$LB_ID" \
  --output cols=Status rows=Listeners.Listener[].Status 2>/dev/null)
LISTENER_OK=$(echo "$LISTENERS" | grep -c "running" || true)
LISTENER_TOTAL=$(echo "$LISTENERS" | wc -l | tr -d ' ')
echo "[2/6] Listeners Running: $LISTENER_OK/$LISTENER_TOTAL"
if [ "$LISTENER_TOTAL" -gt 0 ]; then
  [ "$LISTENER_OK" -eq "$LISTENER_TOTAL" ] && SCORE=$((SCORE + 20))
  [ "$LISTENER_OK" -gt 0 ] && [ "$LISTENER_OK" -lt "$LISTENER_TOTAL" ] && SCORE=$((SCORE + 10))
fi

# 3. Backend health check (iterate all listeners)
echo "[3/6] Backend Health:"
PORTS=$(aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "$LB_ID" \
  --output cols=ListenerPort rows=Listeners.Listener[].ListenerPort 2>/dev/null)
ALL_HEALTHY=0
ALL_TOTAL=0
for port in $PORTS; do
  HEALTH=$(aliyun slb DescribeHealthStatus \
    --LoadBalancerId "$LB_ID" \
    --ListenerPort "$port" \
    --output cols=HealthStatus rows=BackendServers.BackendServer[].HealthStatus 2>/dev/null)
  PORT_HEALTHY=$(echo "$HEALTH" | grep -c "normal" || true)
  PORT_TOTAL=$(echo "$HEALTH" | wc -l | tr -d ' ')
  if [ "$PORT_TOTAL" -gt 0 ]; then
    ALL_HEALTHY=$((ALL_HEALTHY + PORT_HEALTHY))
    ALL_TOTAL=$((ALL_TOTAL + PORT_TOTAL))
    echo "  Port $port: $PORT_HEALTHY/$PORT_TOTAL healthy"
  fi
done
if [ "$ALL_TOTAL" -gt 0 ]; then
  HEALTH_RATIO=$((ALL_HEALTHY * 100 / ALL_TOTAL))
  [ "$HEALTH_RATIO" -eq 100 ] && SCORE=$((SCORE + 25))
  [ "$HEALTH_RATIO" -ge 80 ] && [ "$HEALTH_RATIO" -lt 100 ] && SCORE=$((SCORE + 15))
else
  echo "  No backends configured"
fi

# 4. Certificate expiry check
echo "[4/6] Certificate Check:"
CERT_IDS=$(aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "$LB_ID" \
  --output cols=ListenerPort,Protocol rows=Listeners.Listener[].{ListenerPort,Protocol} 2>/dev/null | grep -i "https" || true)
if [ -n "$CERT_IDS" ]; then
  aliyun slb DescribeServerCertificates \
    --RegionId "$REGION" \
    --output cols=ServerCertificateName,CommonName,ExpireTime \
    rows=ServerCertificates.ServerCertificate[].{ServerCertificateName,CommonName,ExpireTime} 2>/dev/null || echo "  No certificates found"
else
  echo "  No HTTPS listeners configured"
fi

# 5. CMS metrics (drop rate, 5xx)
echo "[5/6] CMS Metrics:"
START_TIME=$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
aliyun cms DescribeMetricList \
  --Namespace acs_slb \
  --MetricName InstanceDropConnection \
  --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" 2>/dev/null || echo "  Metrics N/A"

echo ""
echo "=== Inspection Score: $SCORE/100 ==="
if [ "$SCORE" -ge 80 ]; then
  echo "Status: HEALTHY"
elif [ "$SCORE" -ge 60 ]; then
  echo "Status: WARNING - Review recommended"
else
  echo "Status: CRITICAL - Immediate action required"
fi
```

#### 输出格式

```json
{
  "inspection_time": "2026-05-14T10:00:00Z",
  "resource_type": "slb",
  "resource_id": "lb-bp67acfmxazb4ph****",
  "overall_score": 85,
  "dimensions": [
    {"name": "实例状态", "score": 100, "status": "healthy"},
    {"name": "监听状态", "score": 100, "status": "healthy", "value": "3/3 running"},
    {"name": "后端健康比例", "score": 100, "status": "healthy", "value": "4/4"},
    {"name": "丢包率", "score": 100, "status": "healthy", "value": "0"},
    {"name": "5xx错误率", "score": 60, "status": "warning", "value": "0.5%"},
    {"name": "证书有效期", "score": 100, "status": "healthy", "value": ">30天"}
  ],
  "recommendations": [
    "5xx错误率0.5%超过警告阈值，建议检查后端服务器健康状态"
  ]
}
```