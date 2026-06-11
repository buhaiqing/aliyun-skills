# ACK Intelligent Inspection

Execute a comprehensive health check for an ACK cluster. Combines cluster state, node health, CMS metrics, and addon status into a scored report.

> **重要提示:** 执行巡检前请先完成 [前置检查](inspection-access-patterns.md)，确认集群访问方式和权限。

## 前置检查 (Pre-flight Checks)

### 快速检查清单

| 检查项 | 命令 | 通过标准 | 失败处理 |
|--------|------|---------|---------|
| 集群状态 | `aliyun cs DescribeClusterDetail --ClusterId {{user.cluster_id}}` | `state == "running"` | HALT，提示集群非运行状态 |
| 网络可达 | 检查 `master_url.api_server_endpoint` | 有公网端点或确认内网环境 | 切换 Cloud Assistant 方案 |
| RBAC 权限 | `aliyun cs DescribeUserClusterNamespaces --ClusterId {{user.cluster_id}}` | HTTP 200 | 提示授权命令 |

### 前置检查脚本

```bash
#!/bin/bash
# ack-inspection-preflight.sh
# Usage: ./ack-inspection-preflight.sh <ClusterId> [RegionId]

CLUSTER_ID="$1"
REGION="${2:-${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}}"

echo "=== ACK 巡检前置检查 ==="
echo "ClusterId: $CLUSTER_ID"
echo "Region: $REGION"
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. 检查集群状态
echo "[1/3] 检查集群状态..."
CLUSTER_DETAIL=$(aliyun cs DescribeClusterDetail --ClusterId $CLUSTER_ID 2>&1)
if [ $? -ne 0 ]; then
    echo -e "${RED}✗ 集群不存在或查询失败${NC}"
    echo "错误: $CLUSTER_DETAIL"
    exit 1
fi

CLUSTER_STATE=$(echo "$CLUSTER_DETAIL" | jq -r '.state')
CLUSTER_NAME=$(echo "$CLUSTER_DETAIL" | jq -r '.name')
if [ "$CLUSTER_STATE" != "running" ]; then
    echo -e "${RED}✗ 集群状态异常: $CLUSTER_STATE${NC}"
    echo "集群名称: $CLUSTER_NAME"
    echo "请等待集群运行后再巡检"
    exit 1
fi
echo -e "${GREEN}✓ 集群状态正常: $CLUSTER_STATE${NC}"
echo "  集群名称: $CLUSTER_NAME"

# 2. 检查 API 端点
echo ""
echo "[2/3] 检查 API 端点..."
MASTER_URL=$(echo "$CLUSTER_DETAIL" | jq -r '.master_url')
PUBLIC_ENDPOINT=$(echo "$MASTER_URL" | jq -r '.api_server_endpoint // empty')
PRIVATE_ENDPOINT=$(echo "$MASTER_URL" | jq -r '.intranet_api_server_endpoint // empty')

if [ -n "$PUBLIC_ENDPOINT" ]; then
    echo -e "${GREEN}✓ 发现公网端点${NC}"
    echo "  公网地址: $PUBLIC_ENDPOINT"
    echo "  建议方案: 使用标准 kubeconfig"
else
    echo -e "${YELLOW}⚠ 无公网端点${NC}"
    echo "  内网地址: $PRIVATE_ENDPOINT"
    echo "  建议方案: 使用 Cloud Assistant 在节点上执行 kubectl"
fi

# 3. 检查 RBAC 权限
echo ""
echo "[3/3] 检查 RBAC 权限..."
RBAC_CHECK=$(aliyun cs DescribeUserClusterNamespaces --ClusterId $CLUSTER_ID 2>&1)
if echo "$RBAC_CHECK" | grep -q "Forbidden"; then
    echo -e "${RED}✗ RBAC 权限不足${NC}"
    echo "错误: $RBAC_CHECK"
    echo ""
    echo "授权命令:"
    echo "  aliyun cs GrantPermissions --ClusterId $CLUSTER_ID"
    exit 1
fi
echo -e "${GREEN}✓ RBAC 权限正常${NC}"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "前置检查通过，可以继续执行巡检"
echo "═══════════════════════════════════════════════════════════"
exit 0
```

### 网络不可达时的降级方案

当集群仅有内网端点且当前环境无法访问时，使用 Cloud Assistant 方案：

```bash
#!/bin/bash
# ack-inspection-cloud-assistant.sh
# 通过 Cloud Assistant 在节点上执行巡检命令

CLUSTER_ID="$1"
REGION="${2:-${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}}"

# 获取第一个 Worker 节点
NODE_ID=$(aliyun cs GET /clusters/$CLUSTER_ID/nodes | jq -r '.nodes[0].instance_id')

if [ -z "$NODE_ID" ]; then
    echo "错误: 无法获取节点信息"
    exit 1
fi

echo "使用节点 $NODE_ID 执行巡检..."

# 在节点上执行 kubectl 命令
aliyun ecs RunCommand \
  --RegionId $REGION \
  --InstanceId $NODE_ID \
  --CommandContent 'kubectl get pods --all-namespaces -o wide' \
  --Type RunShellScript \
  --Timeout 60
```

## CLI Script

### 标准巡检脚本（公网/内网可达环境）

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