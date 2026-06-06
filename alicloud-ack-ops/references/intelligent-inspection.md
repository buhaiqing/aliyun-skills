# ACK Intelligent Inspection

Execute a comprehensive health check for an ACK cluster. Combines cluster state, node health, CMS metrics, and addon status into a scored report.

## CLI Script

```bash
#!/bin/bash
# ack-intelligent-inspection.sh
# Usage: ./ack-intelligent-inspection.sh <ClusterId> <RegionId>

CLUSTER_ID="$1"
REGION="$2"
SCORE=0

echo "=== ACK Cluster Intelligent Inspection ==="
echo "Cluster: $CLUSTER_ID"
echo "Region: $REGION"
echo ""

# 1. Cluster state check
STATE=$(aliyun cs GET /clusters/$CLUSTER_ID | jq -r '.state')
echo "[1/5] Cluster State: $STATE"
[ "$STATE" = "running" ] && SCORE=$((SCORE + 25))

# 2. Node health check
NODES=$(aliyun cs GET /clusters/$CLUSTER_ID/nodes | jq -r '.nodes[] | .node_status')
TOTAL=$(echo "$NODES" | wc -l | tr -d ' ')
READY=$(echo "$NODES" | grep -c "Ready" || true)
if [ "$TOTAL" -gt 0 ]; then
  RATIO=$((READY * 100 / TOTAL))
  echo "[2/5] Nodes Ready: $READY/$TOTAL ($RATIO%)"
  [ "$RATIO" -eq 100 ] && SCORE=$((SCORE + 25))
  [ "$RATIO" -ge 90 ] && [ "$RATIO" -lt 100 ] && SCORE=$((SCORE + 15))
else
  echo "[2/5] Nodes: N/A"
fi

# 3. Cluster CPU usage
CPU=$(aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName CpuUsage \
  --Dimensions "[{\"clusterId\":\"$CLUSTER_ID\"}]" \
  --Period 60 \
  --StartTime "$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output cols=Average rows=Datapoints[0].Average 2>/dev/null || echo "N/A")
echo "[3/5] Cluster CPU: $CPU%"

# 4. Cluster memory usage
MEM=$(aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName MemoryUsage \
  --Dimensions "[{\"clusterId\":\"$CLUSTER_ID\"}]" \
  --Period 60 \
  --StartTime "$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output cols=Average rows=Datapoints[0].Average 2>/dev/null || echo "N/A")
echo "[4/5] Cluster Memory: $MEM%"

# 5. Addon status
ADDONS=$(aliyun cs GET /clusters/$CLUSTER_ID/addons | jq -r '.addons[] | .state')
ADDON_OK=$(echo "$ADDONS" | grep -c "active" || true)
ADDON_TOTAL=$(echo "$ADDONS" | wc -l | tr -d ' ')
echo "[5/5] Addons Active: $ADDON_OK/$ADDON_TOTAL"
[ "$ADDON_OK" -eq "$ADDON_TOTAL" ] && [ "$ADDON_TOTAL" -gt 0 ] && SCORE=$((SCORE + 10))

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

## Output Format

```json
{
  "inspection_time": "2026-05-14T10:00:00Z",
  "resource_type": "ack",
  "resource_id": "c-xxx",
  "overall_score": 85,
  "dimensions": [
    {"name": "集群状态", "score": 100, "status": "healthy"},
    {"name": "节点Ready比例", "score": 100, "status": "healthy", "value": "5/5"},
    {"name": "集群CPU使用率", "score": 80, "status": "warning", "value": "72%"},
    {"name": "集群内存使用率", "score": 60, "status": "critical", "value": "88%"},
    {"name": "Addon状态", "score": 100, "status": "healthy"}
  ],
  "recommendations": [
    "集群内存使用率88%超过警告阈值，建议扩容节点或优化调度",
    "集群CPU使用率72%超过警告阈值，建议检查工作负载"
  ]
}
```