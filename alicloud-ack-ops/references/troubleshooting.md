# Troubleshooting ACK

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `ErrorClusterNotFound` / 404 | Cluster does not exist | Verify `cluster_id`; may already be deleted |
| `ErrorClusterState` / 400 | Cluster not in valid state for operation | Wait for cluster to reach stable state (`running`) |
| `ErrorCheckAcl` / 403 | RAM permission denied | Delegate to RAM skill or user adds `cs:*` policy |
| `InvalidParameter` / 400 | Request validation failed | Align body with OpenAPI spec; check `vpc_id`, `vswitch_ids` |
| `QuotaExceeded.Cluster` / 400 | Cluster quota exceeded | HALT; user raises quota via console or ticket |
| `QuotaExceeded.Node` / 400 | Node quota exceeded | HALT; user raises quota |
| `InsufficientBalance` / 400 | Account balance insufficient | HALT |
| `DependencyResourceExist` / 400 | Resources still bound to cluster | Ask user to release SLB, PVCs, or other dependencies |
| `InternalError` / 500 | Server-side error | Retry with backoff; then HALT with `RequestId` |

---

## Symptom-to-Root-Cause Quick Reference

When user reports a problem, use this table to narrow down the investigation path.

| User Symptom | Most Likely Root Cause Category | First Check |
|--------------|----------------------------------|-------------|
| "Pod一直Pending" | 节点资源不足或PVC未就绪 | 节点资源 + PVC状态 |
| "Pod一直CrashLoopBackOff" | 应用配置错误或镜像问题 | Pod日志 + 事件 |
| "节点NotReady" | 节点负载过高或网络中断 | 节点状态 + ECS监控 |
| "服务访问超时" | SLB后端异常或网络策略 | SLB健康检查 + 网络策略 |
| "集群创建失败" | VPC/VSwitch配置错误或配额不足 | VPC验证 + 配额检查 |
| "节点扩容失败" | ECS配额不足或实例类型不可用 | 配额检查 + 可用区验证 |
| "Ingress不生效" | 配置错误或证书问题 | Ingress配置 + 证书检查 |
| "存储卷挂载失败" | NAS/OSS权限或网络问题 | 存储状态 + RAM权限 |
| "集群升级失败" | 版本兼容性或Addon冲突 | 版本检查 + Addon状态 |
| "DNS解析失败" | CoreDNS异常或网络策略 | CoreDNS Pod状态 + 配置 |
| "HPA不生效" | 指标采集异常或配置错误 | Metrics Server状态 + HPA配置 |
| "节点磁盘空间满" | 容器日志或镜像堆积 | 磁盘使用率 + 日志清理 |
| "网络策略不通" | Calico/Terway配置错误 | 网络插件状态 + 策略规则 |
| "PVC一直Pending" | 存储类不存在或配额不足 | StorageClass + PV状态 |

---

## Scenario-Based Diagnostic Playbooks

### Scenario 1: "Pod一直Pending" (Pod Stuck in Pending)

**Symptoms:** Pod remains in `Pending` state and cannot start.

**Diagnostic Flow (execute in order, stop when root cause found):**

```bash
# Step 1: Get kubeconfig and check pod details
aliyun cs GET /k8s/{{user.cluster_id}}/user_config > /tmp/ack-kubeconfig
export KUBECONFIG=/tmp/ack-kubeconfig

# Step 2: Check pod events for scheduling failures
kubectl describe pod {{user.pod_name}} -n {{user.namespace}} | grep -A10 Events

# Step 3: Check node resource availability
kubectl top nodes

# Step 4: Check PVC status (if pod uses volumes)
kubectl get pvc -n {{user.namespace}}
kubectl describe pvc {{user.pvc_name}} -n {{user.namespace}}

# Step 5: Check node conditions
kubectl get nodes -o wide
```

**Decision Tree:**
- Events show `Insufficient cpu` or `Insufficient memory` → Scale out node pool or reduce resource requests
- Events show `FailedScheduling` with node selector/affinity → Check node labels and affinity rules
- Events show `FailedAttachVolume` or `WaitingForPVC` → Check PVC and StorageClass
- Events show `0/1 nodes are available` → Check if nodes are `Ready`
- No events → Check if pod has `nodeName` set incorrectly

---

### Scenario 2: "Pod一直CrashLoopBackOff" (Pod CrashLooping)

**Symptoms:** Pod repeatedly crashes and restarts.

**Diagnostic Flow:**

```bash
# Step 1: Get kubeconfig
aliyun cs GET /k8s/{{user.cluster_id}}/user_config > /tmp/ack-kubeconfig
export KUBECONFIG=/tmp/ack-kubeconfig

# Step 2: Check pod logs
kubectl logs {{user.pod_name}} -n {{user.namespace}} --tail=100

# Step 3: Check previous instance logs (if restarted)
kubectl logs {{user.pod_name}} -n {{user.namespace}} --previous --tail=100

# Step 4: Check pod events
kubectl describe pod {{user.pod_name}} -n {{user.namespace}} | grep -A10 Events

# Step 5: Check resource limits
kubectl get pod {{user.pod_name}} -n {{user.namespace}} -o yaml | grep -A5 resources
```

**Decision Tree:**
- Logs show `OOMKilled` → Increase memory limits
- Logs show application error → Fix application configuration
- `CrashLoopBackOff` with `Error` exit code → Check application startup
- Liveness/Readiness probe failing → Check probe configuration and application health endpoint
- ConfigMap/Secret not found → Verify ConfigMap/Secret exists in namespace

---

### Scenario 3: "节点NotReady" (Node Not Ready)

**Symptoms:** One or more worker nodes show `NotReady` status.

**Diagnostic Flow:**

```bash
# Step 1: List nodes and identify NotReady nodes
kubectl get nodes -o wide

# Step 2: Check node conditions
kubectl describe node {{user.node_name}} | grep -A10 Conditions

# Step 3: Check ECS instance status (delegate to alicloud-ecs-ops)
aliyun ecs DescribeInstances \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.instance_id}}"]' \
  --output cols=InstanceId,Status rows=Instances.Instance[].{InstanceId,Status}

# Step 4: Check node disk usage via CMS
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName disk.utilization \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 5: Check kubelet status (if SSH access available)
# ssh {{user.node_ip}} "systemctl status kubelet"
```

**Decision Tree:**
- ECS instance `Status` != `Running` → ECS instance issue; delegate to `alicloud-ecs-ops`
- `DiskPressure` condition = True → Clean up disk space (images, logs)
- `MemoryPressure` condition = True → Reduce pod density or scale out
- `PIDPressure` condition = True → Reduce process count
- `NetworkUnavailable` condition = True → Check network plugin (Terway/Flannel)
- `KubeletHasSufficientMemory` = False → Node memory exhausted
- All conditions normal but node still `NotReady` → Check kubelet service; may need node restart

---

### Scenario 4: "服务访问超时" (Service Access Timeout)

**Symptoms:** Cannot access application through Service/Ingress.

**Diagnostic Flow:**

```bash
# Step 1: Check Service and Endpoints
kubectl get svc {{user.service_name}} -n {{user.namespace}}
kubectl get endpoints {{user.service_name}} -n {{user.namespace}}

# Step 2: Check backend pods
kubectl get pods -n {{user.namespace}} -l {{user.selector}}

# Step 3: Check SLB health (if using LoadBalancer type)
# Delegate to alicloud-slb-ops
aliyun slb DescribeHealthStatus \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}"

# Step 4: Check network policies
kubectl get networkpolicies -n {{user.namespace}}

# Step 5: Check Ingress configuration (if using Ingress)
kubectl get ingress {{user.ingress_name}} -n {{user.namespace}} -o yaml
```

**Decision Tree:**
- Endpoints list is empty → No matching pods for service selector
- Pods not `Running` → Check pod status (Scenario 1/2)
- SLB backend health = `abnormal` → Backend pod not responding; delegate to `alicloud-slb-ops`
- NetworkPolicy blocking ingress traffic → Adjust network policy rules
- Ingress configured but not working → Check Ingress controller pod and configuration

---

### Scenario 5: "集群创建失败" (Cluster Creation Failure)

**Symptoms:** Cluster creation fails or stuck in `initial` state.

**Diagnostic Flow:**

```bash
# Step 1: Check cluster state
aliyun cs GET /clusters/{{user.cluster_id}} | jq '{cluster_id, state, current_version}'

# Step 2: Verify VPC and VSwitch exist (delegate to alicloud-vpc-ops)
aliyun vpc DescribeVpcs --VpcId "{{user.vpc_id}}"
aliyun vpc DescribeVSwitches --VSwitchId "{{user.vswitch_id}}"

# Step 3: Check ECS quota
aliyun ecs DescribeAccountAttributes \
  --RegionId "{{user.region}}" \
  --AttributeName "max-security-group-count"

# Step 4: Check RAM role existence (delegate to alicloud-ram-ops)
aliyun ram GetRole --RoleName "AliyunCSDefaultRole"
```

**Decision Tree:**
- VPC/VSwitch not found → Create VPC/VSwitch first via `alicloud-vpc-ops`
- ECS quota exceeded → Raise quota or reduce node count
- RAM role `AliyunCSDefaultRole` missing → Create service-linked role via `alicloud-ram-ops`
- `ErrorCheckAcl` → RAM permission issue; delegate to `alicloud-ram-ops`
- `InsufficientBalance` → Add funds to account

---

## Cluster State Reference

| State | Meaning | Actionable? |
|-------|---------|-------------|
| `initial` | Creating | Wait |
| `running` | Healthy | Yes |
| `updating` | Upgrading or scaling | Wait |
| `failed` | Creation or operation failed | Check logs; may need to delete and recreate |
| `deleting` | Deleting | Wait |
| `deleted` | Deleted | N/A |

## Node Pool State Reference

| State | Meaning | Actionable? |
|-------|---------|-------------|
| `active` | Healthy | Yes |
| `scaling` | Scaling in progress | Wait |
| `updating` | Updating | Wait |
| `failed` | Failed | Check error message; may need to recreate |
| `deleting` | Deleting | Wait |

---

## One-Shot Diagnostic Scripts

### Script 1: Full ACK Cluster Health Check

```bash
#!/bin/bash
# ack-full-health-check.sh
# Usage: ./ack-full-health-check.sh <ClusterId> <RegionId>

CLUSTER_ID="$1"
REGION="$2"

echo "=== Cluster Status ==="
aliyun cs GET /clusters/$CLUSTER_ID | jq '{cluster_id, state, current_version, created}'

echo ""
echo "=== Node Status ==="
aliyun cs GET /clusters/$CLUSTER_ID/nodes | jq '.nodes[] | {instance_id, state, node_status, instance_type}'

echo ""
echo "=== Node Pools ==="
aliyun cs GET /clusters/$CLUSTER_ID/nodepools | jq '.nodepools[] | {nodepool_id, name, state, desired_size, current_size}'

echo ""
echo "=== Cluster Metrics (Last 15 min) ==="
START_TIME=$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName CpuUsage \
  --Dimensions "[{\"clusterId\":\"$CLUSTER_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Addons ==="
aliyun cs GET /clusters/$CLUSTER_ID/addons | jq '.addons[] | {name, version, state}'
```

### Script 2: Node Deep Inspection

```bash
#!/bin/bash
# ack-node-deep-inspect.sh
# Usage: ./ack-node-deep-inspect.sh <ClusterId> <NodeInstanceId> <RegionId>

CLUSTER_ID="$1"
INSTANCE_ID="$2"
REGION="$3"

echo "=== Node ECS Status ==="
aliyun ecs DescribeInstances \
  --RegionId "$REGION" \
  --InstanceIds "[\"$INSTANCE_ID\"]" \
  --output cols=InstanceId,Status,InstanceType,Cpu,Memory rows=Instances.Instance[0].{InstanceId,Status,InstanceType,Cpu,Memory}

echo ""
echo "=== Node Metrics (Last 15 min) ==="
START_TIME=$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName cpu.utilization \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName memory.utilization \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName disk.utilization \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"
```

---

## Diagnostic Order (Standard)

1. **Describe cluster** by ID: `aliyun cs GET /clusters/{cluster_id}`
2. **Check cluster state:** `$.state` should be `running` for most operations
3. **List nodes:** `aliyun cs GET /clusters/{cluster_id}/nodes` to check node health
4. **List node pools:** `aliyun cs GET /clusters/{cluster_id}/nodepools` to check pool state
5. **Check pod status:** Use kubeconfig and `kubectl get pods --all-namespaces`
6. **Check events:** `kubectl get events --all-namespaces --sort-by='.lastTimestamp'`
7. **Verify regional endpoint:** Ensure `RegionId` matches cluster region
8. **Cross-skill delegation:** If node issue → `alicloud-ecs-ops`; if SLB issue → `alicloud-slb-ops`; if RAM issue → `alicloud-ram-ops`