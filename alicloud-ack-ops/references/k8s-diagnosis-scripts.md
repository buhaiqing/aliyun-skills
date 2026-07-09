# Kubernetes 资源诊断脚本

> 完整诊断脚本集，用于 Pod、Service、Ingress、Storage 的异常诊断。
> 这些脚本在 SKILL.md 的 Kubernetes 资源诊断流程中被引用。

---

## Pod Diagnosis

```bash
#!/bin/bash
# pod-diagnosis.sh
NAMESPACE="${1:-default}"
echo "=== Pod Diagnosis in namespace: $NAMESPACE ==="
echo ""

# Pod status summary
echo "[1] Pod Status Summary:"
kubectl get pods -n $NAMESPACE -o json | jq -r '.items[] | .status.phase' | sort | uniq -c
echo ""

# Abnormal pods
echo "[2] Abnormal Pods:"
kubectl get pods -n $NAMESPACE --field-selector=status.phase!=Running -o wide
echo ""

# CrashLoopBackOff
echo "[3] CrashLoopBackOff Pods:"
CRASH_PODS=$(kubectl get pods -n $NAMESPACE | grep CrashLoopBackOff | awk '{print $1}')
if [ -n "$CRASH_PODS" ]; then
  for POD in $CRASH_PODS; do
    echo "--- Pod: $POD ---"
    kubectl describe pod $POD -n $NAMESPACE | grep -A5 "Events:"
    kubectl logs $POD -n $NAMESPACE --tail=20 --previous 2>/dev/null || kubectl logs $POD -n $NAMESPACE --tail=20
  done
else
  echo "No CrashLoopBackOff pods found."
fi
echo ""

# Pending pods
echo "[4] Pending Pods:"
PENDING_PODS=$(kubectl get pods -n $NAMESPACE | grep Pending | awk '{print $1}')
if [ -n "$PENDING_PODS" ]; then
  for POD in $PENDING_PODS; do
    echo "--- Pod: $POD ---"
    kubectl describe pod $POD -n $NAMESPACE | grep -A10 "Events:"
  done
else
  echo "No Pending pods found."
fi
echo ""

# Evicted pods
echo "[5] Evicted Pods:"
EVICTED_PODS=$(kubectl get pods -n $NAMESPACE | grep Evicted | awk '{print $1}')
if [ -n "$EVICTED_PODS" ]; then
  echo "Found evicted pods, checking node conditions..."
  kubectl describe pod $EVICTED_PODS -n $NAMESPACE | grep -B5 -A5 "The node was low on"
else
  echo "No Evicted pods found."
fi
```

---

## Service Diagnosis

```bash
#!/bin/bash
# service-diagnosis.sh
NAMESPACE="${1:-default}"
SERVICE="${2:-}"
echo "=== Service Diagnosis in namespace: $NAMESPACE ==="
echo ""

# Service list
echo "[1] Services in namespace:"
kubectl get svc -n $NAMESPACE
echo ""

# Endpoints check
echo "[2] Endpoints status:"
kubectl get endpoints -n $NAMESPACE
echo ""

# Detailed diagnosis for specific service
if [ -n "$SERVICE" ]; then
  echo "[3] Detailed diagnosis for service: $SERVICE"
  kubectl describe svc $SERVICE -n $NAMESPACE

  # Endpoints details
  echo ""
  echo "--- Endpoints Details ---"
  kubectl describe endpoints $SERVICE -n $NAMESPACE

  # Backend pod check
  SELECTOR=$(kubectl get svc $SERVICE -n $NAMESPACE -o json | jq -r '.spec.selector')
  if [ -n "$SELECTOR" ] && [ "$SELECTOR" != "null" ]; then
    echo ""
    echo "--- Backend Pods (Selector: $SELECTOR) ---"
    kubectl get pods -n $NAMESPACE -l $(echo $SELECTOR | jq -r 'to_entries | map("\(.key)=\(.value)") | join(",")')

    NOT_READY=$(kubectl get pods -n $NAMESPACE -l $(echo $SELECTOR | jq -r 'to_entries | map("\(.key)=\(.value)") | join(",")') | grep -v Running | grep -v "1/1" || true)
    if [ -n "$NOT_READY" ]; then
      echo ""
      echo "WARNING: Some backend pods are not ready:"
      echo "$NOT_READY"
    fi
  else
    echo ""
    echo "WARNING: Service has no selector defined (ExternalName or manual endpoints)"
  fi
fi

# CoreDNS check
echo ""
echo "[4] CoreDNS status:"
kubectl get pods -n kube-system -l k8s-app=coredns
```

---

## Ingress Diagnosis

```bash
#!/bin/bash
# ingress-diagnosis.sh
NAMESPACE="${1:-default}"
echo "=== Ingress Diagnosis ==="
echo ""

# Ingress list
echo "[1] Ingress resources:"
kubectl get ingress -A
echo ""

# Ingress controller pods
echo "[2] Ingress Controller Pods:"
kubectl get pods -n kube-system | grep -E "nginx-ingress|ingress-controller"
echo ""

# Ingress controller logs (recent errors)
echo "[3] Ingress Controller recent errors:"
INGRESS_POD=$(kubectl get pods -n kube-system | grep nginx-ingress-controller | head -1 | awk '{print $1}')
if [ -n "$INGRESS_POD" ]; then
  kubectl logs $INGRESS_POD -n kube-system --tail=50 | grep -i error || echo "No errors in recent logs"
fi
echo ""

# Ingress details in namespace
if [ "$NAMESPACE" != "all" ]; then
  echo "[4] Ingress details in namespace $NAMESPACE:"
  kubectl get ingress -n $NAMESPACE -o wide

  for ING in $(kubectl get ingress -n $NAMESPACE -o json | jq -r '.items[].metadata.name'); do
    echo ""
    echo "--- Ingress: $ING ---"
    kubectl describe ingress $ING -n $NAMESPACE

    SERVICE=$(kubectl get ingress $ING -n $NAMESPACE -o json | jq -r '.spec.rules[].http.paths[].backend.service.name' | head -1)
    if [ -n "$SERVICE" ]; then
      echo ""
      echo "Backend Service: $SERVICE"
      kubectl get endpoints $SERVICE -n $NAMESPACE
    fi
  done
fi

# LoadBalancer services
echo ""
echo "[5] LoadBalancer Services:"
kubectl get svc -A -o json | jq -r '.items[] | select(.spec.type=="LoadBalancer") | "\(.metadata.namespace)/\(.metadata.name): \(.status.loadBalancer.ingress[0].ip // "pending")"'
```

---

## Storage Diagnosis

```bash
#!/bin/bash
# storage-diagnosis.sh
echo "=== Storage Diagnosis ==="
echo ""

# PVC status summary
echo "[1] PVC Status Summary:"
kubectl get pvc -A -o json | jq -r '.items[] | .status.phase' | sort | uniq -c
echo ""

# Pending PVCs
echo "[2] Pending PVCs:"
PENDING_PVC=$(kubectl get pvc -A | grep Pending)
if [ -n "$PENDING_PVC" ]; then
  echo "$PENDING_PVC"
  echo ""
  for LINE in "$PENDING_PVC"; do
    NS=$(echo $LINE | awk '{print $1}')
    PVC_NAME=$(echo $LINE | awk '{print $2}')
    echo "--- PVC: $PVC_NAME in $NS ---"
    kubectl describe pvc $PVC_NAME -n $NS | grep -A10 "Events:"
  done
else
  echo "No Pending PVCs found."
fi
echo ""

# PV status
echo "[3] PV Status:"
kubectl get pv | grep -v Bound || echo "All PVs are Bound."
echo ""

# StorageClass check
echo "[4] Available StorageClasses:"
kubectl get storageclass
echo ""

# CSI driver status
echo "[5] CSI Driver Pods:"
kubectl get pods -n kube-system | grep csi
echo ""

# CSI controller logs (errors)
CSI_POD=$(kubectl get pods -n kube-system | grep csi-controller | head -1 | awk '{print $1}')
if [ -n "$CSI_POD" ]; then
  echo "[6] CSI Controller recent errors:"
  kubectl logs $CSI_POD -n kube-system --tail=30 | grep -i error || echo "No errors in recent logs"
fi
```
