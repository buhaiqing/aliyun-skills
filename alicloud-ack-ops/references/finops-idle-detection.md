# ACK Idle Resource Detection

Identify idle nodes, pods, PVCs, and SLBs associated with an ACK cluster.

## Idle Criteria

| Resource | Idle Criteria | Action |
|----------|--------------|--------|
| Node | CPU < 10% for 7 days | Downsize node pool or delete |
| Pod | Running but no traffic for 24h | Check app status, stop |
| PVC | Bound but no pod mounting for 7d | Check usage, delete |
| SLB | No healthy backend for 24h | Check association, delete |

## CLI Script

```bash
#!/bin/bash
# ack-idle-resource-detection.sh
# Usage: ./ack-idle-resource-detection.sh <ClusterId>

CLUSTER_ID="$1"
echo "=== ACK Idle Resource Detection ==="

# 1. Idle nodes
echo ""
echo "### Idle Nodes (CPU < 10% for 7 days) ###"
aliyun cs GET /k8s/$CLUSTER_ID/user_config > /tmp/kubeconfig
export KUBECONFIG=/tmp/kubeconfig
kubectl top nodes --sort-by=cpu

# 2. Idle pods (no network traffic)
echo ""
echo "### Potentially Idle Pods ###"
kubectl get pods -A -o wide | awk '{print $1, $2, $7}' | while read NS POD IP; do
  if [ "$IP" != "<none>" ]; then
    LAST_LOG=$(kubectl logs $POD -n $NS --since=24h 2>/dev/null | wc -l)
    if [ "$LAST_LOG" -eq 0 ]; then
      echo "Pod: $NS/$POD - No logs in 24h - Potentially idle"
    fi
  fi
done

# 3. Idle PVCs
echo ""
echo "### Idle PVCs (Bound but unused) ###"
kubectl get pvc -A -o json | jq -r '.items[] | select(.status.phase=="Bound") | "\(.metadata.namespace)/\(.metadata.name)"' | while read PVC; do
  NS=$(echo $PVC | cut -d/ -f1)
  NAME=$(echo $PVC | cut -d/ -f2)
  MOUNTED=$(kubectl get pods -n $NS -o json | jq -r '.items[] | select(.spec.volumes[]?.persistentVolumeClaim?.claimName=="$NAME")' | wc -l)
  if [ "$MOUNTED" -eq 0 ]; then
    echo "PVC: $PVC - No pods mounting - Potentially idle"
  fi
done

# 4. Idle SLBs
echo ""
echo "### SLBs Associated with Cluster ###"
aliyun cs GET /clusters/$CLUSTER_ID | jq -r '.cluster_id'
echo "Note: For SLB idle detection, delegate to alicloud-slb-ops"
```