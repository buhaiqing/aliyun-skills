# ACK 批量操作模板

> **Purpose:** 提供 ACK 集群批量操作的标准模板，支持并行查询多集群、多节点、多 Pod 状态。

## 多集群状态并行查询

### 使用场景
- 跨区域集群健康检查
- 多环境（开发/测试/生产）集群状态监控
- 大规模 ACK 资产盘点

### 查询模板

```bash
#!/bin/bash
# batch-cluster-status.sh
# Usage: ./batch-cluster-status.sh <region1> <region2> ...

REGIONS=("$@")
RESULTS_FILE="/tmp/cluster_status_$(date +%Y%m%d_%H%M%S).json"

echo "=== Batch Cluster Status Query ==="
echo "Regions: ${REGIONS[*]}"
echo ""

# 并行查询多个 Region 的集群
for REGION in "${REGIONS[@]}"; do
  (
    echo "Querying region: $REGION"
    aliyun cs GET /clusters --RegionId "$REGION" | jq -r --arg region "$REGION" '
      .clusters[] | {
        region: $region,
        cluster_id: .cluster_id,
        name: .name,
        state: .state,
        version: .current_version,
        node_count: .node_count,
        created: .created
      }'
  ) &
done

# 等待所有并行任务完成
wait

echo ""
echo "=== Query Complete ==="
echo "Results saved to: $RESULTS_FILE"
```

### 输出示例

```json
{
  "query_time": "2026-05-20T10:00:00Z",
  "regions": ["cn-hangzhou", "cn-beijing", "cn-shanghai"],
  "clusters": [
    {
      "region": "cn-hangzhou",
      "cluster_id": "c-xxx",
      "name": "prod-cluster",
      "state": "running",
      "version": "1.28.3-aliyun.1",
      "node_count": 10
    }
  ],
  "summary": {
    "total_clusters": 5,
    "running": 5,
    "failed": 0,
    "deleting": 0
  }
}
```

## 节点状态批量查询

### 使用场景
- 大规模节点健康检查
- 节点版本一致性验证
- 异常节点批量排查

### 查询模板

```bash
#!/bin/bash
# batch-node-status.sh
# Usage: ./batch-node-status.sh <cluster_id>

CLUSTER_ID="$1"
REGION="${2:-cn-hangzhou}"

echo "=== Batch Node Status Query ==="
echo "Cluster: $CLUSTER_ID"
echo "Region: $REGION"
echo ""

# 获取所有节点并并行查询详细信息
NODES=$(aliyun cs GET "/clusters/$CLUSTER_ID/nodes" | jq -r '.nodes[].instance_id')

for INSTANCE_ID in $NODES; do
  (
    NODE_INFO=$(aliyun cs GET "/clusters/$CLUSTER_ID/nodes" | jq --arg id "$INSTANCE_ID" '.nodes[] | select(.instance_id == $id)')
    ECS_INFO=$(aliyun ecs DescribeInstances --RegionId "$REGION" --InstanceIds "[\"$INSTANCE_ID\"]" 2>/dev/null | jq '.Instances.Instance[0] // empty')

    echo "$NODE_INFO" | jq --argjson ecs "$ECS_INFO" '{
      instance_id: .instance_id,
      node_status: .node_status,
      node_name: .node_name,
      instance_type: $ecs.InstanceType,
      cpu: $ecs.Cpu,
      memory: $ecs.Memory,
      public_ip: $ecs.PublicIpAddress.IpAddress[0],
      private_ip: $ecs.InnerIpAddress.IpAddress[0],
      creation_time: $ecs.CreationTime
    }'
  ) &
done

wait

echo ""
echo "=== Query Complete ==="
```

### 批量节点状态检查表

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| 节点 Ready 状态 | `kubectl get nodes` | 所有节点 Ready |
| 节点资源使用 | `kubectl top nodes` | CPU/Memory < 80% |
| 节点系统状态 | `aliyun ecs DescribeInstances` | Running |
| 节点 Kubelet 状态 | `systemctl status kubelet` | Active |
| 节点磁盘使用 | `df -h /var/lib/docker` | < 85% |

## Pod 状态并行查询

### 使用场景
- 全集群 Pod 健康扫描
- 异常 Pod 批量定位
- Pod 分布均衡性检查

### 查询模板

```bash
#!/bin/bash
# batch-pod-status.sh
# Usage: ./batch-pod-status.sh <cluster_id> [namespace]

CLUSTER_ID="$1"
NAMESPACE="${2:-all}"
KUBECONFIG_FILE="/tmp/ack-$CLUSTER_ID.conf"

echo "=== Batch Pod Status Query ==="
echo "Cluster: $CLUSTER_ID"
echo "Namespace: $NAMESPACE"
echo ""

# 获取 kubeconfig
aliyun cs GET "/k8s/$CLUSTER_ID/user_config" > "$KUBECONFIG_FILE"
export KUBECONFIG="$KUBECONFIG_FILE"

# 并行查询各 Namespace Pod 状态
if [ "$NAMESPACE" = "all" ]; then
  NAMESPACES=$(kubectl get ns -o json | jq -r '.items[].metadata.name')
else
  NAMESPACES="$NAMESPACE"
fi

for NS in $NAMESPACES; do
  (
    PODS=$(kubectl get pods -n "$NS" -o json 2>/dev/null | jq --arg ns "$NS" '
      .items[] | {
        namespace: $ns,
        name: .metadata.name,
        status: .status.phase,
        restarts: (.status.containerStatuses // [] | map(.restartCount) | add // 0),
        node: .spec.nodeName,
        age: .metadata.creationTimestamp
      }'
    )
    echo "$PODS"
  ) &
done

wait

# 清理临时文件
rm -f "$KUBECONFIG_FILE"

echo ""
echo "=== Query Complete ==="
```

### Pod 异常模式检测

```bash
#!/bin/bash
# pod-anomaly-detection.sh

CLUSTER_ID="$1"
KUBECONFIG_FILE="/tmp/ack-$CLUSTER_ID.conf"

aliyun cs GET "/k8s/$CLUSTER_ID/user_config" > "$KUBECONFIG_FILE"
export KUBECONFIG="$KUBECONFIG_FILE"

echo "=== Pod Anomaly Detection ==="

# 1. Pod 重启次数异常 (>5)
echo "[1] Pods with high restart count:"
kubectl get pods --all-namespaces -o json | jq -r '
  .items[] |
  select(.status.containerStatuses != null) |
  select([.status.containerStatuses[].restartCount] | max > 5) |
  "\(.metadata.namespace)/\(.metadata.name): \([.status.containerStatuses[].restartCount] | max) restarts"'

# 2. Pod Pending 状态超时 (>5min)
echo ""
echo "[2] Pods in Pending state:"
kubectl get pods --all-namespaces --field-selector status.phase=Pending -o json | jq -r '
  .items[] |
  select(.status.conditions != null) |
  "\(.metadata.namespace)/\(.metadata.name): \(.status.conditions[0].reason // \"N/A\")"'

# 3. Pod Not Ready
echo ""
echo "[3] Pods with containers not ready:"
kubectl get pods --all-namespaces -o json | jq -r '
  .items[] |
  select(.status.containerStatuses != null) |
  select([.status.containerStatuses[].ready] | all | not) |
  "\(.metadata.namespace)/\(.metadata.name): not ready"'

rm -f "$KUBECONFIG_FILE"
```

## 批量操作最佳实践

### 1. 并行度控制

```bash
# 使用 GNU Parallel 控制并发数
cat cluster_ids.txt | parallel -j 5 'aliyun cs GET /clusters/{}'

# 或使用 xargs
cat cluster_ids.txt | xargs -P 10 -I {} aliyun cs GET /clusters/{}
```

### 2. 错误处理与重试

```bash
# 批量操作带重试机制
for CLUSTER_ID in $(cat cluster_ids.txt); do
  for attempt in 1 2 3; do
    echo "Querying cluster $CLUSTER_ID (attempt $attempt)..."
    if aliyun cs GET "/clusters/$CLUSTER_ID" > "/tmp/cluster_$CLUSTER_ID.json" 2>/dev/null; then
      echo "Success"
      break
    fi
    sleep $((attempt * 2))
  done
done
```

### 3. 结果聚合与报告

```bash
# 合并所有查询结果
jq -s '{clusters: ., total: length, timestamp: now}' /tmp/cluster_*.json > batch_report.json

# 生成 Markdown 报告
cat batch_report.json | jq -r '
  "# Batch Query Report\n\n",
  "Generated: \(.timestamp)\n\n",
  "## Summary\n",
  "- Total Clusters: \(.total)\n\n",
  "## Details\n",
  (.clusters[] | "- **\(.name)**: \(.state) (\(.cluster_id))")
'
```

### 4. API 限流处理

```bash
# 批量操作时添加延迟避免限流
RATE_LIMIT=10  # requests per second
DELAY=$(echo "scale=3; 1/$RATE_LIMIT" | bc)

for CLUSTER_ID in $(cat cluster_ids.txt); do
  aliyun cs GET "/clusters/$CLUSTER_ID"
  sleep "$DELAY"
done
```

## 相关文档

- [CLI Usage](cli-usage.md) - aliyun CLI 使用指南
- [Observability Integration](observability.md) - 可观测性集成
- [Troubleshooting Guide](troubleshooting.md) - 故障排查指南
