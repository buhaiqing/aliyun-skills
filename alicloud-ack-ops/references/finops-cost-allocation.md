# ACK Cost Allocation by Namespace

Calculate per-namespace resource consumption and cost split for ACK clusters.

## Cost Formula

```
Namespace_Cost = Σ(Pod_CPU_Request / Node_CPU_Total × Node_Hourly_Cost)
              + Σ(Pod_Memory_Request / Node_Memory_Total × Node_Hourly_Cost)
              + Σ(PVC_Size × Disk_Price_GB_Month / Month_Days)
```

## CLI Script

```bash
#!/bin/bash
# ack-cost-allocation.sh
# Usage: ./ack-cost-allocation.sh <ClusterId> <NodeHourlyCost> <DiskPriceGB>

CLUSTER_ID="$1"
NODE_COST="$2"  # e.g., ¥1.5/hour
DISK_COST="$3"  # e.g., ¥0.35/GB/month

aliyun cs GET /k8s/$CLUSTER_ID/user_config > /tmp/kubeconfig
export KUBECONFIG=/tmp/kubeconfig

echo "=== Namespace Cost Allocation ==="
echo "Node Hourly Cost: ¥$NODE_COST"
echo "Disk Cost: ¥$DISK_COST/GB/month"

kubectl get pods -A -o json | jq -r '
  .items[] | 
  {ns: .metadata.namespace,
   cpu_req: .spec.containers[].resources.requests.cpu,
   mem_req: .spec.containers[].resources.requests.memory} | 
  group_by(.ns) | 
  map({namespace: .[0].ns, total_pods: length})' > /tmp/ns-stats.json

echo ""
echo "### Resource Requests by Namespace ###"
kubectl top pods -A | awk 'NR>1 {ns[$1]++; cpu[$1]+=$2; mem[$1]+=$3} END {for (n in ns) print n, ns[n], cpu[n], mem[n]}'

echo ""
echo "### PVC Usage by Namespace ###"
kubectl get pvc -A -o custom-columns='NAMESPACE:.metadata.namespace,PVC:.metadata.name,CAPACITY:.spec.resources.requests.storage' | awk 'NR>1 {ns[$1]++; cap[$1]+=$2} END {for (n in ns) print n, ns[n], cap[n]}'

echo ""
echo "Note: For precise cost calculation, integrate with billing data via alicloud-billing-ops"
```