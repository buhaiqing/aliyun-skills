# ACK Resource Optimization Analysis

Analyze cluster resource utilization, identify waste, and generate optimization recommendations.

## CLI Script

```bash
#!/bin/bash
# ack-resource-optimization.sh
# Usage: ./ack-resource-optimization.sh <ClusterId> <RegionId>

CLUSTER_ID="$1"
REGION="$2"

echo "=== ACK Resource Optimization Analysis ==="

# 1. Get node metrics from CMS
START=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo ""
echo "### Node Resource Utilization (7-day average) ###"

NODES=$(aliyun cs GET /clusters/$CLUSTER_ID/nodes | jq -r '.nodes[] | .instance_id')

for NODE_ID in $NODES; do
  CPU=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName cpu.utilization \
    --Dimensions "[{\"instanceId\":\"$NODE_ID\"}]" \
    --Period 86400 \
    --StartTime "$START" \
    --EndTime "$END" \
    --output cols=Average rows=Datapoints[0].Average 2>/dev/null || echo "N/A")
  
  MEM=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName memory.utilization \
    --Dimensions "[{\"instanceId\":\"$NODE_ID\"}]" \
    --Period 86400 \
    --StartTime "$START" \
    --EndTime "$END" \
    --output cols=Average rows=Datapoints[0].Average 2>/dev/null || echo "N/A")
  
  echo "Node: $NODE_ID | CPU: ${CPU}% | Memory: ${MEM}%"
  
  if [ "${CPU}" != "N/A" ] && [ $(echo "${CPU} < 10" | bc) -eq 1 ]; then
    echo "  ⚠️  IDLE NODE: CPU < 10% for 7 days - Consider downsizing"
  fi
done

# 2. Pod resource request vs usage analysis
echo ""
echo "### Pod Resource Over-provisioning ###"
aliyun cs GET /k8s/$CLUSTER_ID/user_config > /tmp/kubeconfig-$CLUSTER_ID
export KUBECONFIG=/tmp/kubeconfig-$CLUSTER_ID

kubectl top pods -A --sort-by=cpu | head -20
kubectl get pods -A -o custom-columns='NAMESPACE:.metadata.namespace,POD:.metadata.name,CPU_REQ:.spec.containers[*].resources.requests.cpu,MEM_REQ:.spec.containers[*].resources.requests.memory' | head -30

# 3. PVC utilization analysis
echo ""
echo "### PVC Storage Utilization ###"
kubectl get pvc -A -o custom-columns='NAMESPACE:.metadata.namespace,PVC:.metadata.name,STATUS:.status.phase,CAPACITY:.spec.resources.requests.storage'

echo ""
echo "=== Optimization Recommendations ==="
echo "1. Review idle nodes for downsizing or removal"
echo "2. Adjust Pod resource requests to match actual usage"
echo "3. Resize PVCs that are over-provisioned"
```

## Output

```json
{
  "analysis_time": "2026-05-26T10:00:00Z",
  "cluster_id": "c-xxx",
  "optimization_score": 65,
  "idle_resources": [
    {"type": "node", "id": "i-xxx", "cpu_avg": "8%", "recommendation": "downsize or remove"}
  ],
  "over_provisioned_pods": [
    {"namespace": "default", "pod": "web-app", "cpu_request": "4", "cpu_usage": "1.2", "waste_ratio": "70%"}
  ],
  "storage_over_provisioned": [
    {"namespace": "data", "pvc": "data-pvc", "capacity": "500Gi", "usage_estimate": "100Gi"}
  ],
  "estimated_monthly_savings": "¥2,400",
  "actions": [
    "Remove 2 idle nodes → Save ¥800/month",
    "Reduce Pod CPU requests → Save ¥600/month",
    "Resize PVCs → Save ¥1,000/month"
  ]
}
```