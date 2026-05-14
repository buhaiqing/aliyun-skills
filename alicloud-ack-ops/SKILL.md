---
name: alicloud-ack-ops
description: >-
  Deploy, scale, upgrade, and troubleshoot Alibaba Cloud ACK clusters and node
  pools via aliyun CLI or JIT Go SDK. Invoke when user mentions ACK,
  Kubernetes, 容器服务, K8s, or cluster lifecycle operations.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+
  runtime (for JIT SDK fallback), valid API credentials, network access to
  Alibaba Cloud CS endpoints.
metadata:
  author: alicloud
  version: "2.0.0"
  last_updated: "2026-05-14"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "CS-2015-12-15 / https://www.alibabacloud.com/help/en/ack"
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun help cs`. The `cs` product exposes cluster and node
    pool operations including DescribeClusters, DescribeClusterNodes,
    CreateCluster, DeleteCluster, ScaleOutCluster, and node pool APIs.
    Some addon and advanced networking APIs may require JIT Go SDK fallback.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

# Alibaba Cloud ACK Operations Skill

## Overview

Alibaba Cloud Container Service for Kubernetes (ACK) provides managed Kubernetes
clusters with automated operations, multi-AZ availability, and deep integration
with Alibaba Cloud infrastructure (SLB, NAS, OSS, RAM, VPC). This skill is an
**operational runbook** for agents: explicit scope, credential rules, pre-flight
checks, **dual-path execution** (official **`aliyun` CLI** primary, **JIT Go SDK**
fallback), response validation, and failure recovery.

**Execution surface — CLI-primary with JIT Go SDK fallback:**
- **Primary:** `aliyun cs <Operation>` — static Go binary, covers cluster CRUD,
  node pool operations, and scaling.
- **Fallback:** JIT Go SDK (`github.com/alibabacloud-go/cs-20151215/v4/client`)
  for APIs not exposed in CLI (e.g., some addon management, advanced network
  policies, or new API versions).
- **Console click-paths** are not an agent execution surface in `SKILL.md`.

**Core resources managed by this skill:**
- **Cluster** — the Kubernetes control plane and managed infrastructure.
- **Node Pool** — homogeneous groups of worker nodes with shared configuration.
- **Addon** — cluster components (e.g., ingress, metrics-server, logtail).

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "ACK", "Alibaba Cloud Kubernetes", "容器服务", "容器服务
  Kubernetes版", "K8s", or "Kubernetes cluster on Alibaba Cloud"
- Task involves CRUD or lifecycle operations on **Cluster** or **Node Pool**
  (create, describe, modify, delete, list, scale, upgrade)
- Task keywords: `cluster`, `node pool`, `worker node`, `managed kubernetes`,
  `pro kubernetes`, `ask` (Serverless Kubernetes), `addon`, `ingress`, `scaling`,
  `upgrade`, `kubeconfig`
- User asks to deploy, configure, troubleshoot, or monitor ACK **via API, SDK,
  CLI, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to:
  `alicloud-billing-ops` (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when
  present)
- Task is about **VPC / SLB / NAS / OSS** underlying resources but not ACK
  cluster lifecycle → delegate to: `alicloud-vpc-ops`, `alicloud-slb-ops`, etc.
- Task is about **ECI / Serverless** outside ACK context → delegate to:
  `alicloud-eci-ops` (when present)
- User insists on **console-only** flows with no API → state limitation; do not
  invent undocumented HTTP steps

### Delegation Rules

- If creating a cluster, ensure **VPC** and **VSwitch** exist first (via
  `alicloud-vpc-ops`); ACK requires `vpc_id` and `vswitch_ids`.
- If creating a public-facing cluster, **SLB** may be auto-created by ACK; do not
  manually manage ACK-managed SLBs unless explicitly required.
- Multi-product requests: handle each product with its skill; do not merge
  unrelated APIs into one ambiguous flow.

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.cluster_name}}` | User-supplied cluster name | Ask once; reuse |
| `{{user.cluster_id}}` | User-supplied or output cluster ID | Ask if not from previous output |
| `{{user.vpc_id}}` | VPC for cluster creation | Ask; validate via VPC skill if needed |
| `{{user.vswitch_ids}}` | VSwitches for cluster nodes | Ask; comma-separated list |
| `{{output.cluster_id}}` | From last CreateCluster response | Parse `cluster_id` from response |
| `{{output.node_pool_id}}` | From last CreateNodePool response | Parse `nodepool_id` from response |
| `{{user.node_pool_id}}` | User-supplied or output node pool ID | Ask if not from previous output |
| `{{user.key_pair}}` | ECS Key Pair for SSH access to nodes | Ask once; optional for password auth |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing.

> **Security Warning:** **NEVER** log, print, or expose
> `ALIBABA_CLOUD_ACCESS_KEY_SECRET` in console output, debug messages, or logs.
> When verification is needed, check existence only without printing the actual
> value. Use masked placeholders like `***` if logging credential status.

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response
  shapes. ACK uses the **CS-2015-12-15** API version.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec.
  Common ACK errors: `ErrorClusterNotFound`, `ErrorClusterState`,
  `ErrorCheckAcl`, `QuotaExceeded.Cluster`.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** `client_token` can be used for CreateCluster; document
  duplicate name behavior per API.

### Response Field Table (ACK-Specific)

| Operation | JSON Path (CLI/SDK) | Type | Description |
|-----------|---------------------|------|-------------|
| CreateCluster | `$.cluster_id` | string | New cluster ID |
| DescribeClusters | `$.clusters[].cluster_id` | array | Cluster IDs list |
| DescribeClusterDetail | `$.state` | string | Cluster lifecycle state |
| DescribeClusterNodes | `$.nodes[].instance_id` | array | Node ECS instance IDs |
| CreateNodePool | `$.nodepool_id` | string | New node pool ID |
| ScaleOutCluster | `$.task_id` | string | Async scaling task ID |

### Expected State Transitions (ACK Cluster)

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateCluster | — | `running` | 30s | 1800s (30min) |
| UpgradeCluster | `running` | `running` | 30s | 3600s (60min) |
| ScaleOutCluster | `running` | `running` | 30s | 1800s (30min) |
| DeleteCluster | any stable state | absent / 404 | 30s | 1800s (30min) |

> **Note:** ACK cluster operations are **long-running**. Always poll `state` via
> `DescribeClusters` or `DescribeClusterDetail` until terminal state.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-14 | Initial ACK skill with cluster and node pool operations |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI primary / SDK fallback) → Validate
→ Recover**. Do not skip phases.

### Operation: Create Cluster

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI / deps | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys | HALT; user configures env |
| Region | `aliyun cs DescribeClusters --RegionId {{user.region}}` (dry list) | HTTP 200 | Suggest valid region |
| VPC / VSwitch | Validate `{{user.vpc_id}}` and `{{user.vswitch_ids}}` exist | Found | Delegate to VPC skill or ask |
| Quota | `aliyun cs DescribeClusters` list length vs known quota | Sufficient | HALT; user raises quota |

#### Execution — CLI (`aliyun cs`) (Primary Path)

```bash
# Create a managed Kubernetes cluster (minimal example)
aliyun cs POST /clusters \
  --body "{
    \"cluster_type\": \"ManagedKubernetes\",
    \"name\": \"{{user.cluster_name}}\",
    \"region_id\": \"{{user.region}}\",
    \"vpc_id\": \"{{user.vpc_id}}\",
    \"vswitch_ids\": [{{user.vswitch_ids}}],
    \"worker_instance_types\": [\"ecs.g7.xlarge\"],
    \"num_of_nodes\": 2,
    \"key_pair\": \"{{user.key_pair}}\",
    \"service_cidr\": \"172.16.0.0/16\",
    \"pod_cidr\": \"10.0.0.0/8\"
  }"
```

> **Note:** ACK CreateCluster uses a **POST /clusters** REST-style API. The
> `aliyun` CLI supports this via `POST /clusters` or `aliyun cs CreateCluster`
> depending on CLI version. Verify with `aliyun help cs` before execution.

> **Required fields** (verify in OpenAPI): `cluster_type`, `name`, `region_id`,
> `vpc_id`, `vswitch_ids`, `worker_instance_types`, `num_of_nodes`.

> **Network plugin:** Default is Flannel (`pod_cidr` required). For Terway
> (ENI-based), omit `pod_cidr` and pass `addons` with `[{"name":"terway-eniip"}]`.
> See [Core Concepts](references/core-concepts.md) for CNI differences.

> **Idempotency:** Pass `client_token` (unique string per request) in the request
> body to prevent duplicate cluster creation on retry.

> **JSON body from file:** For complex requests, write body to a file and use:
> `aliyun cs POST /clusters --body file:///tmp/cluster.json`

#### Execution — JIT Go SDK (Fallback Path)

When CLI does not support a specific cluster parameter or new API version:

```go
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    cs "github.com/alibabacloud-go/cs-20151215/v4/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String(fmt.Sprintf("cs.%s.aliyuncs.com", os.Getenv("ALIBABA_CLOUD_REGION_ID"))),
    }

    client, err := cs.NewClient(config)
    if err != nil {
        panic(err)
    }

    request := &cs.CreateClusterRequest{
        ClusterType:         tea.String("ManagedKubernetes"),
        Name:                tea.String(os.Getenv("CLUSTER_NAME")),
        RegionId:            tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
        VpcId:               tea.String(os.Getenv("VPC_ID")),
        VswitchIds:          tea.StringSlice([]string{"vsw-xxx"}),
        WorkerInstanceTypes: tea.StringSlice([]string{"ecs.g7.xlarge"}),
        NumOfNodes:          tea.Int64(2),
        ServiceCidr:         tea.String("172.16.0.0/16"),
        PodCidr:             tea.String("10.0.0.0/8"),
    }

    response, err := client.CreateCluster(request)
    if err != nil {
        panic(err)
    }

    fmt.Println(tea.ToString(response.Body))
}
```

#### Post-execution Validation

1. Extract `{{output.cluster_id}}` from response (`$.cluster_id`).
2. Poll until `state == "running"`:

```bash
# CLI polling
for i in $(seq 1 60); do
  STATE=$(aliyun cs GET /clusters/{{output.cluster_id}} | jq -r '.state')
  [ "$STATE" = "running" ] && break
  echo "Cluster state: $STATE, waiting..."
  sleep 30
done
```

3. On success, report `cluster_id`, `state`, and `api_server_endpoint`.
4. On terminal failure (`failed`, `deleting`, timeout), go to **Failure Recovery**.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` / 400 | 0–1 | — | Fix args from OpenAPI; retry once if safe |
| `QuotaExceeded.Cluster` | 0 | — | HALT; user raises quota |
| `InsufficientBalance` | 0 | — | HALT |
| `ErrorCheckAcl` / RAM | 0 | — | Delegate to RAM skill or user fixes policy |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 10s, 20s, 40s | Retry; then HALT with `RequestId` |

### Operation: Describe Cluster

#### Execution — CLI

```bash
# Describe single cluster
aliyun cs GET /clusters/{{user.cluster_id}}

# List all clusters in region
aliyun cs GET /clusters --RegionId {{user.region}}
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Cluster ID | `$.cluster_id` | Plain text |
| Name | `$.name` | Plain text |
| State | `$.state` | e.g., `running`, `initial`, `failed`, `deleting` |
| Region | `$.region_id` | Plain text |
| Kubernetes Version | `$.current_version` | e.g., `1.28.3-aliyun.1` |
| API Server Endpoint | `$.api_server.endpoint` | Public or internal endpoint |
| VPC ID | `$.vpc_id` | Plain text |
| Created At | `$.created` | ISO 8601 |

### Operation: Scale Out Cluster (Add Nodes)

#### Pre-flight

- Confirm cluster `state == "running"`.
- Validate `{{user.vswitch_ids}}` and instance types.

#### Execution — CLI

```bash
# Method A: REST-style path (verify with `aliyun help cs`)
aliyun cs POST /clusters/{{user.cluster_id}}/nodes \
  --body "{
    \"count\": {{user.node_count}},
    \"vswitch_ids\": [{{user.vswitch_ids}}],
    \"instance_types\": [\"{{user.instance_type}}\"],
    \"key_pair\": \"{{user.key_pair}}\"
  }"

# Method B: RPC-style operation (if supported by CLI version)
# aliyun cs ScaleOutCluster \
#   --ClusterId {{user.cluster_id}} \
#   --Count {{user.node_count}} \
#   --VswitchIds {{user.vswitch_ids}}
```

#### Validation

Poll `DescribeClusterNodes` until new nodes reach `Ready` state (or ECS
`Running` and Kubernetes node Ready via `kubectl` if kubeconfig available).

### Operation: Create Node Pool

#### Execution — CLI

> **Field structure varies by API version.** Verify exact field names via
> `aliyun help cs CreateNodePool` or OpenAPI spec before execution.

```bash
aliyun cs POST /clusters/{{user.cluster_id}}/nodepools \
  --body "{
    \"name\": \"{{user.node_pool_name}}\",
    \"node_config\": {
      \"instance_types\": [\"ecs.g7.xlarge\"],
      \"vswitch_ids\": [{{user.vswitch_ids}}],
      \"key_pair\": \"{{user.key_pair}}\"
    },
    \"scaling_group\": {
      \"desired_size\": {{user.desired_size}},
      \"min_size\": {{user.min_size}},
      \"max_size\": {{user.max_size}}
    }
  }"
```

#### Validation

Extract `{{output.node_pool_id}}` from `$.nodepool_id`. Poll
`GET /clusters/{{user.cluster_id}}/nodepools/{{output.node_pool_id}}` until
`status.state == "active"` (or equivalent field per API version).

### Operation: Upgrade Cluster

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit user confirmation: upgrading Kubernetes version is
  **disruptive** to running workloads (control plane brief unavailability,
  node rolling restart).
- Confirm current version vs target version via `DescribeClusters`.

#### Execution — CLI

```bash
aliyun cs PUT /clusters/{{user.cluster_id}}/upgrade \
  --body "{
    \"version\": \"{{user.target_version}}\",
    \"upgrade_mode\": \"standard\"
  }"
```

#### Validation

Poll `GET /clusters/{{user.cluster_id}}` until `state == "running"` and
`current_version == {{user.target_version}}`. Max wait: 3600s.

### Operation: Get kubeconfig

#### Execution — CLI

```bash
# Public endpoint kubeconfig
aliyun cs GET /k8s/{{user.cluster_id}}/user_config

# Internal endpoint kubeconfig (VPC-only access)
aliyun cs GET /k8s/{{user.cluster_id}}/user_config \
  --PrivateIpAddress true
```

#### Present to User

Save output to `~/.kube/config` or custom path:

```bash
aliyun cs GET /k8s/{{user.cluster_id}}/user_config > ~/.kube/ack-{{user.cluster_id}}
export KUBECONFIG=~/.kube/ack-{{user.cluster_id}}
kubectl get nodes
```

---

### Operation: Modify Node Pool

#### Pre-flight

- Confirm cluster `state == "running"`.
- Confirm node pool exists: `GET /clusters/{id}/nodepools/{pool_id}`.

#### Execution — CLI

> **Note:** Modify operations may use `PUT` or `POST` depending on API version.
> Verify with `aliyun help cs`.

```bash
# Scale node pool (adjust desired size)
aliyun cs PUT /clusters/{{user.cluster_id}}/nodepools/{{user.node_pool_id}} \
  --body "{
    \"scaling_group\": {
      \"desired_size\": {{user.desired_size}}
    }
  }"

# Enable auto-scaling (if supported)
# aliyun cs PUT /clusters/{id}/nodepools/{pool_id} \
#   --body "{\"auto_scaling\": {\"enable\": true, \"min_size\": 1, \"max_size\": 10}}"
```

#### Validation

Poll `GET /clusters/{id}/nodepools/{pool_id}` until node count matches desired
size and `status.state == "active"`.

---

### Operation: Delete Node Pool

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of node pool
  `{{user.node_pool_name}}` (`{{user.node_pool_id}}`).
- **MUST** warn user: all nodes in the pool will be drained and destroyed.
- Confirm cluster has at least one other active node pool (to avoid losing all
  worker capacity).

#### Execution — CLI

```bash
aliyun cs DELETE /clusters/{{user.cluster_id}}/nodepools/{{user.node_pool_id}}
```

#### Post-execution Validation

Poll `GET /clusters/{id}/nodepools/{pool_id}` until **404** (max wait 900s).

#### Failure Recovery

| Error pattern | Action |
|---------------|--------|
| `ErrorNodePoolNotFound` | Already deleted; confirm to user |
| `ErrorClusterState` | Wait for cluster to reach `running`; retry |
| `LastNodePool` | Refuse deletion; warn user cluster will have no workers |

---

### Operation: Manage Addon

#### Pre-flight

- Confirm cluster `state == "running"`.
- Identify addon name and target version.

#### Execution — CLI

> **Note:** Addon management APIs may not be fully exposed in `aliyun` CLI.
> Verify with `aliyun help cs` or fall back to JIT Go SDK.

```bash
# List available addons (verify CLI support)
aliyun cs GET /clusters/{{user.cluster_id}}/addons

# Install or upgrade addon (verify exact API path)
# aliyun cs POST /clusters/{{user.cluster_id}}/addons \
#   --body "{
#     \"name\": \"{{user.addon_name}}\",
#     \"version\": \"{{user.addon_version}}\"
#   }"
```

#### JIT Go SDK Fallback

If CLI does not support addon operations:

```go
// Use cs-20151215/v4/client
// request := &cs.InstallAddonRequest{...}
// response, err := client.InstallAddon(request)
```

---

### Operation: Delete Cluster

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of cluster
  `{{user.cluster_name}}` (`{{user.cluster_id}}`).
- **MUST** warn user: all workloads, persistent volumes, and auto-created SLBs
  will be destroyed.
- **MUST NOT** proceed without clear user assent.

#### Execution — CLI

```bash
# Standard delete
aliyun cs DELETE /clusters/{{user.cluster_id}}

# Force delete (when resources are still bound; use with caution)
# aliyun cs DELETE /clusters/{{user.cluster_id}} --force true
```

> **Note:** Force delete may leave orphaned SLBs, disks, or PVCs. Prefer
> cleaning up resources first.

#### Post-execution Validation

Poll `GET /clusters/{{user.cluster_id}}` until **404** or `state == "deleted"`
(max wait 1800s). If 404, confirm deletion to user.

#### Failure Recovery

| Error pattern | Action |
|---------------|--------|
| `ErrorClusterNotFound` | Already deleted; confirm to user |
| `ErrorClusterState` (not stable) | Wait for cluster to reach stable state; retry |
| `DependencyResourceExist` (resources still bound) | Ask user to release SLB, PVCs, or other dependencies |

---

### Operation: Intelligent Inspection（智能巡检）

一键执行ACK集群的全面健康检查，整合集群状态 + 节点状态 + CMS指标。

#### 执行流程

1. 调用 `DescribeClusterDetail` 检查集群状态
2. 调用 `DescribeClusterNodes` 检查所有节点状态
3. 调用 `alicloud-cms-ops` 查询集群CPU/内存指标
4. 调用 `alicloud-ecs-ops` 检查异常节点的ECS状态
5. 综合评分并生成巡检报告

#### 巡检评分标准

| 维度 | 评分依据 | 权重 |
|------|---------|------|
| 集群状态 | running=100, 其他=0 | 25% |
| 节点Ready比例 | 100%=100, >90%=60, <90%=0 | 25% |
| 集群CPU使用率 | <70%=100, 70-85%=60, >85%=0 | 20% |
| 集群内存使用率 | <75%=100, 75-90%=60, >90%=0 | 20% |
| Addon状态 | 全部正常=100, 有异常=0 | 10% |

#### 执行 — CLI

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

#### 输出格式

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

## Prerequisites

1. **Install `aliyun` CLI** (primary execution path):

   ```bash
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   # Or: brew install aliyun-cli
   ```

2. **Bootstrap Go runtime** (for JIT SDK fallback):

   ```bash
   if ! command -v go &> /dev/null; then
       OS=$(uname -s | tr '[:upper:]' '[:lower:]')
       ARCH=$(uname -m)
       [ "$ARCH" = "x86_64" ] && ARCH="amd64"
       [ "$ARCH" = "aarch64" ] && ARCH="arm64"

       mkdir -p /tmp/go-runtime
       curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime

       export PATH="/tmp/go-runtime/go/bin:$PATH"
       export GOPATH="/tmp/go-workspace"
       export GOCACHE="/tmp/go-cache"
       export GOMODCACHE="/tmp/go-modcache"
       export GOPROXY="https://goproxy.cn,direct"
   fi

   go version
   ```

3. **Configure Credentials**:

   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```

4. **Verify Configuration**:

   ```bash
   aliyun cs GET /clusters
   ```

> **Security:** Never commit credentials. All credentials use `{{env.*}}`
> placeholders — never real values.

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [CLI Usage](references/cli-usage.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)

## Operational Best Practices

- **Least privilege:** RAM policies scoped to `cs:*` actions required for the
  task; avoid `cs:*` wildcard for production.
- **Availability:** Use multi-AZ VSwitches for worker nodes; enable auto-scaling
  node pools for workload resilience.
- **Cost:** Use Spot instances in non-critical node pools; right-size instance
  types; clean up unused clusters.
- **Security:** Rotate cluster certificates periodically; use private API server
  endpoints where possible; enable audit logging.
- **Pod Security:** Enable Pod Security Standards (PSS) or OPA Gatekeeper for
  workload isolation; restrict privileged containers.
- **Network Policy:** Use Calico or Terway network policies to segment traffic
  between namespaces.
