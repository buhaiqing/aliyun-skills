# ACK 巡检访问模式与降级策略

> **反思来源:** 真实巡检场景中发现直接 API 访问受限，需要系统性访问策略。
> **核心原则:** "不要假设用户环境满足所有条件" —— 企业 ACK 集群默认只有内网端点（安全最佳实践）。

---

## 问题复盘

| 阶段 | 发生的错误 | 根本原因 | 用户影响 |
|------|-----------|---------|---------|
| 直接 kubectl | `dial tcp 172.16.x.x:6443: i/o timeout` | 未先确认网络可达性，集群只有内网端点 | 用户看到超时错误，无操作指引 |
| OpenAPI 查命名空间 | `RBAC 403 Forbidden` | 未先确认账号权限，直接调用 API | 用户看到权限错误，无授权指引 |
| 组件查询 | JSON 解析失败 | API 返回非预期格式，未做降级处理 | 巡检中断，无备选方案 |

---

## 访问路径决策树

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ACK 巡检访问路径决策树                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  开始巡检                                                                 │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────┐                                                    │
│  │ 检查集群状态     │ 失败 → HALT，提示集群非运行状态                      │
│  │ DescribeCluster │                                                    │
│  └────────┬────────┘                                                    │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │ 检查 API 端点    │                                                    │
│  │ master_url 公网? │                                                    │
│  └────────┬────────┘                                                    │
│           │                                                             │
│     ┌─────┴─────┐                                                       │
│     ▼         ▼                                                         │
│   有公网    仅内网                                                        │
│     │         │                                                         │
│     ▼         ▼                                                         │
│  使用标准   检查当前环境                                                   │
│  kubeconfig  │                                                          │
│              ▼                                                          │
│        ┌─────┴─────┐                                                     │
│        ▼         ▼                                                       │
│     内网/VPN   公网环境                                                   │
│        │         │                                                       │
│        ▼         ▼                                                       │
│     使用内网   降级至                                                     │
│     kubeconfig  Cloud Assistant                                          │
│              │                                                           │
│              ▼                                                           │
│        ┌─────────────┐                                                    │
│        │ 检查 RBAC   │ 失败 → 提示授权步骤                                 │
│        │ 权限        │                                                    │
│        └─────────────┘                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 前置检查清单 (Pre-flight Checks)

### 检查 1：集群状态

| 属性 | 说明 |
|------|------|
| **目的** | 确认集群处于可操作状态 |
| **命令** | `aliyun cs DescribeClusterDetail --ClusterId {{user.cluster_id}}` |
| **通过标准** | `state == "running"` |
| **失败处理** | HALT，提示"集群当前状态为 $STATE，请等待集群运行后再巡检" |

### 检查 2：网络可达性

| 属性 | 说明 |
|------|------|
| **目的** | 确认集群 API 端点可达性 |
| **命令** | `aliyun cs DescribeClusterDetail --ClusterId {{user.cluster_id}}` |
| **检查字段** | `master_url.api_server_endpoint` (公网) / `master_url.intranet_api_server_endpoint` (内网) |
| **通过标准** | 有公网端点，或确认当前环境可访问内网端点 |
| **失败处理** | 切换至 **Cloud Assistant 降级方案** |

### 检查 3：RBAC 权限

| 属性 | 说明 |
|------|------|
| **目的** | 确认当前账号有集群读取权限 |
| **预检命令** | `aliyun cs DescribeUserClusterNamespaces --ClusterId {{user.cluster_id}}` |
| **通过标准** | HTTP 200 |
| **失败处理** | 提示授权命令并 HALT |

---

## 优雅降级策略

当主方案失败时，按以下优先级自动切换备选方案：

| 优先级 | 方案 | 适用场景 | 限制 |
|--------|------|---------|------|
| **1** | kubectl + kubeconfig | 有公网端点或内网/VPN 环境 | 需要网络可达 |
| **2** | 阿里云 OpenAPI | 有 RBAC 权限，需查询集群元数据 | 部分资源（如 Pod/Service）无法通过 OpenAPI 查询 |
| **3** | Cloud Assistant 远程命令 | 网络不可达，但可访问 ECS 节点 | 需要在节点上安装 kubectl |
| **4** | 仅输出基础信息 | 以上均不可用 | 信息有限，需人工介入 |

### 降级方案详情

#### 方案 1: 标准 kubeconfig (主方案)

```bash
# 获取 kubeconfig
aliyun cs DescribeClusterUserKubeconfig \
  --ClusterId {{user.cluster_id}} \
  --TemporaryDurationMinutes 60

# 配置并验证
export KUBECONFIG=/tmp/ack-{{user.cluster_id}}.conf
kubectl version
```

**成功标准:** `kubectl version` 返回 client 和 server 版本

**失败标志:** `Unable to connect to the server: dial tcp ... i/o timeout`

---

#### 方案 2: 阿里云 OpenAPI (备选)

适用于查询集群元数据，**无法查询 Pod/Service 等 K8s 资源**。

```bash
# 可查询的集群信息
aliyun cs DescribeClusterDetail --ClusterId {{user.cluster_id}}          # 集群详情
aliyun cs GET /clusters/{{user.cluster_id}}/nodes                         # 节点列表
aliyun cs GET /clusters/{{user.cluster_id}}/addons                        # 插件状态
aliyun cs DescribeUserClusterNamespaces --ClusterId {{user.cluster_id}}   # 命名空间列表（需 RBAC）
```

**无法查询的内容:**
- Pod 列表和状态
- Service 详情
- Deployment/StatefulSet 状态
- Ingress 配置
- ConfigMap/Secret 内容

---

#### 方案 3: Cloud Assistant 远程命令 (降级方案)

当集群仅配置内网端点且当前环境无法访问时，通过 Cloud Assistant 在节点上执行 kubectl。

```bash
# Step 1: 获取节点实例 ID
aliyun cs GET /clusters/{{user.cluster_id}}/nodes | jq -r '.nodes[0].instance_id'

# Step 2: 通过 Cloud Assistant 执行 kubectl
aliyun ecs RunCommand \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --InstanceId i-bp1xxxxx \
  --CommandContent "kubectl get pods --all-namespaces --kubeconfig /root/.kube/config" \
  --Type RunShellScript
```

**前置条件:**
- 节点已安装 kubectl
- 节点已配置 kubeconfig（通常 ACK 节点默认配置）
- 当前账号有 ECS RunCommand 权限

---

#### 方案 4: 仅输出基础信息 (保底方案)

当所有方案均失败时，输出已获取的基础信息并明确告知限制：

```markdown
## 巡检结果（部分）

### ✅ 可获取信息
| 项目 | 值 |
|------|-----|
| 集群名称 | 恰货铺子-非生产 |
| 集群状态 | running |
| Kubernetes 版本 | 1.35.2-aliyun.1 |
| Worker 节点数 | 3 |
| 区域 | 杭州 (cn-hangzhou) |

### ❌ 无法获取的信息
- 命名空间列表（RBAC 权限不足）
- Pod 状态（集群无公网访问）
- Service 详情（集群无公网访问）

### 🔧 解决方案
1. **授权 RBAC 权限**: `aliyun cs GrantPermissions --ClusterId xxx`
2. **配置 VPN 访问**: 连接至 VPC 内网后重试
3. **使用 Cloud Assistant**: 在节点上执行 kubectl 命令
```

---

## 错误信息优化

将原始错误转换为可操作的用户指引：

| 原始错误 | 优化后提示 |
|---------|-----------|
| `dial tcp 172.16.x.x:6443: i/o timeout` | `⚠️ 该集群未开启公网API访问。可选方案：① 连接VPN后重试 ② 使用内网跳板机 ③ 通过 Cloud Assistant 在节点上执行` |
| `ForbiddenQueryClusterNamespace` | `⚠️ 当前账号缺少集群 RBAC 权限。授权命令：aliyun cs GrantPermissions --ClusterId xxx` |
| `ErrorClusterNotFound` | `⚠️ 集群不存在或已被删除。请确认 cluster_id 正确。` |
| `ErrorCheckAcl` | `⚠️ RAM 权限不足。请确认当前账号有 cs:DescribeCluster 权限。` |

---

## 前置检查脚本

### Bash 完整实现

```bash
#!/bin/bash
# ack-inspection-preflight.sh
# Usage: ./ack-inspection-preflight.sh <ClusterId>

CLUSTER_ID="$1"
REGION="${2:-${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}}"

echo "=== ACK 巡检前置检查 ==="
echo "ClusterId: $CLUSTER_ID"
echo "Region: $REGION"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PREFLIGHT_PASS=true
ACCESS_METHOD=""

# 1. 检查集群状态
echo "[1/3] 检查集群状态..."
CLUSTER_DETAIL=$(aliyun cs DescribeClusterDetail --ClusterId $CLUSTER_ID 2>&1)
if [ $? -ne 0 ]; then
    echo -e "${RED}✗ 集群不存在或查询失败${NC}"
    echo "错误信息: $CLUSTER_DETAIL"
    exit 1
fi

CLUSTER_STATE=$(echo "$CLUSTER_DETAIL" | jq -r '.state')
if [ "$CLUSTER_STATE" != "running" ]; then
    echo -e "${RED}✗ 集群状态异常: $CLUSTER_STATE${NC}"
    echo "请等待集群运行后再巡检"
    exit 1
fi
echo -e "${GREEN}✓ 集群状态正常: $CLUSTER_STATE${NC}"

# 2. 检查 API 端点
echo ""
echo "[2/3] 检查 API 端点..."
MASTER_URL=$(echo "$CLUSTER_DETAIL" | jq -r '.master_url')
PUBLIC_ENDPOINT=$(echo "$MASTER_URL" | jq -r '.api_server_endpoint // empty')
PRIVATE_ENDPOINT=$(echo "$MASTER_URL" | jq -r '.intranet_api_server_endpoint // empty')

if [ -n "$PUBLIC_ENDPOINT" ]; then
    echo -e "${GREEN}✓ 发现公网端点: $PUBLIC_ENDPOINT${NC}"
    ACCESS_METHOD="public_api"
else
    echo -e "${YELLOW}⚠ 无公网端点，仅有内网端点: $PRIVATE_ENDPOINT${NC}"
    echo "当前环境无法直接访问，将尝试 Cloud Assistant 方案"
    ACCESS_METHOD="cloud_assistant"
fi

# 3. 检查 RBAC 权限（如果有公网端点）
if [ "$ACCESS_METHOD" == "public_api" ]; then
    echo ""
    echo "[3/3] 检查 RBAC 权限..."
    
    # 获取临时 kubeconfig 测试连接
    KUBECONFIG_DATA=$(aliyun cs DescribeClusterUserKubeconfig \
        --ClusterId $CLUSTER_ID \
        --TemporaryDurationMinutes 10 2>&1)
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ 获取 kubeconfig 失败${NC}"
        echo "错误信息: $KUBECONFIG_DATA"
        ACCESS_METHOD="cloud_assistant"
    else
        # 测试连接
        echo "$KUBECONFIG_DATA" | jq -r '.config' > /tmp/ack-preflight-$CLUSTER_ID.conf
        export KUBECONFIG=/tmp/ack-preflight-$CLUSTER_ID.conf
        
        if kubectl get nodes &>/dev/null; then
            echo -e "${GREEN}✓ RBAC 权限正常，可访问集群${NC}"
        else
            echo -e "${YELLOW}⚠ 无法连接集群 API${NC}"
            echo "可能原因: 网络不通 / 证书问题"
            ACCESS_METHOD="cloud_assistant"
        fi
    fi
fi

# 输出结论
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "前置检查结果"
echo "═══════════════════════════════════════════════════════════"
if [ "$ACCESS_METHOD" == "public_api" ]; then
    echo -e "${GREEN}✓ 检查通过，将使用标准 kubeconfig 方案${NC}"
    echo "执行命令: export KUBECONFIG=/path/to/kubeconfig"
elif [ "$ACCESS_METHOD" == "cloud_assistant" ]; then
    echo -e "${YELLOW}⚠ 降级至 Cloud Assistant 方案${NC}"
    echo "原因: 集群无公网访问或权限不足"
    echo "备选命令: aliyun ecs RunCommand --InstanceId <节点ID> ..."
else
    echo -e "${RED}✗ 前置检查失败，无法继续巡检${NC}"
    exit 1
fi
echo "═══════════════════════════════════════════════════════════"

exit 0
```

---

## 集成到巡检流程

### 推荐巡检流程

```bash
#!/bin/bash
# 完整的 ACK 智能巡检流程（带前置检查）

CLUSTER_ID="$1"
REGION="$2"

# Phase 1: 前置检查
echo "=== Phase 1: 前置检查 ==="
./ack-inspection-preflight.sh $CLUSTER_ID $REGION
if [ $? -ne 0 ]; then
    echo "前置检查失败，巡检终止"
    exit 1
fi

# Phase 2: 执行巡检（根据检查结果选择方案）
echo ""
echo "=== Phase 2: 执行巡检 ==="
if [ "$ACCESS_METHOD" == "public_api" ]; then
    # 使用 kubectl 方案
    ./ack-intelligent-inspection-kubectl.sh $CLUSTER_ID $REGION
else
    # 使用 Cloud Assistant 方案
    ./ack-intelligent-inspection-ca.sh $CLUSTER_ID $REGION
fi

# Phase 3: 生成报告
echo ""
echo "=== Phase 3: 生成巡检报告 ==="
# ...
```

---

## 核心反思总结

> **"不要假设用户环境满足所有条件"**

- **阿里云 ACK 集群默认只有内网端点**（安全最佳实践）
- **子账号默认没有集群 RBAC 权限**（最小权限原则）
- **巡检工具应该「先探测、再执行、有降级、给指引」**

本次反思揭示了**企业 K8s 环境的典型限制**——巡检工具需要适配这种「受限访问」场景，而不是假设总能直连 API Server。

---

## 相关文档

- [智能巡检脚本](intelligent-inspection.md)
- [故障排查指南](troubleshooting.md)
- [CLI 使用说明](cli-usage.md)
