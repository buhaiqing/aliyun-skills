---
name: alicloud-ack-ops
description: >-
  Use this skill when the user needs to set up, manage, or troubleshoot a
  Kubernetes cluster on Alibaba Cloud (ACK). Catches tasks like "create a
  cluster", "add nodes", "upgrade K8s version", "集群健康检查", "节点 NotReady",
  "获取 kubeconfig" — even when the user just says "帮我弄个 K8s 集群" or "my
  Alibaba cluster is broken" without naming ACK. Does NOT handle VPC, SLB, ECS,
  RAM, or billing — those belong to their own skills.
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

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field value (including `ALIBABA_CLOUD_ACCESS_KEY_ID`) in console output, debug messages, error messages, or logs. If credential information must be displayed for debugging or troubleshooting purposes, use the masking format: show only the first 4 characters followed by `****` (e.g., `abcd****`). This masking rule applies to ALL output channels: stdout, stderr, log files, debug traces, error messages, and diagnostic reports.
>
> **Masking rules across all execution paths:**
> | Execution Path | Safe Pattern | Unsafe Pattern |
> |----------------|-------------|----------------|
> | Console output | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=abcd****` | Raw credential value in output |
> | Error messages | `Error: API call failed (credential omitted)` | Error containing raw credential value |
> | Log files | `[INFO] Credentials: Secret=abcd****` | `[INFO] AK Secret: LTAI5t...` |
> | Verification | `test -n "$var" && echo "Secret is set"` (existence check only) | `echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET` |
> | JIT Go SDK | env read via `os.Getenv(...)` is safe; never print `Config` struct | `fmt.Printf("Config: %+v", config)` |
> | Debug/verbose | `Debug mode may expose credentials (use with caution)` | Un-masked credential in debug output |
>
> **Credential verification MUST check existence only**, never echo the value. This applies to ALL execution flows (SDK, CLI, and debugging scripts).

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

## Kubernetes 资源诊断流程 (Kubernetes Resource Diagnosis)

以下诊断流程使用 `kubectl` 命令，需要先获取集群 kubeconfig。Agent 应确保 kubeconfig 已配置后再执行。

### Operation: Pod Diagnosis（Pod 诊断）

诊断 Pod 异常状态，包括 CrashLoopBackOff、Pending、Evicted、OOMKilled 等。

#### 前置条件

- kubeconfig 已配置：`export KUBECONFIG=~/.kube/ack-{{user.cluster_id}}`
- 验证连接：`kubectl cluster-info`

#### 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│                    Pod 异常诊断流程                          │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: 状态收集                                           │
│  ├── kubectl get pods -A --field-selector=status.phase!=Running │
│  ├── kubectl get pods -A \| grep -E "CrashLoop|Pending|Evicted" │
│  └── 统计异常 Pod 数量                                        │
│                                                              │
│  Phase 2: 详细诊断                                           │
│  ├── Pending → describe pod → 检查事件/资源请求               │
│  ├── CrashLoopBackOff → logs + describe → 检查退出原因        │
│  ├── Evicted → describe → 检查节点压力条件                    │
│  └── OOMKilled → describe → 检查内存 Limit                   │
│                                                              │
│  Phase 3: 根因分析                                           │
│  ├── 资源不足 → 扩容节点/调整 Request                         │
│  ├── 应用异常 → 检查日志/修复代码                             │
│  ├── 配置错误 → 检查配置文件                                  │
│  └── 镜像问题 → 检查镜像存在性                                │
│                                                              │
│  Phase 4: 修复验证                                           │
│  ├── 执行修复动作                                            │
│  ├── 验证 Pod 状态恢复                                       │
│  └── 记录修复结果                                            │
└─────────────────────────────────────────────────────────────┘
```

#### 执行 — kubectl

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

#### 常见 Pod 异常诊断表

| 状态 | 常见原因 | 修复方案 |
|------|---------|---------|
| **Pending** | 资源不足/节点选择器限制/污点 | 扩容节点池/调整 Request |
| **CrashLoopBackOff** | 应用异常/启动命令错误/配置错误 | 修复代码/修正启动命令/检查配置 |
| **Evicted** | 节点磁盘/内存/PID 压力 | 清理节点资源/扩容节点 |
| **OOMKilled** | 内存超限/内存泄漏 | 增加内存 Limit/修复内存泄漏 |
| **ImagePullBackOff** | 镜像不存在/认证失败/网络不通 | 修正镜像标签/配置 imagePullSecret |
| **CreateContainerConfigError** | ConfigMap/Secret 不存在 | 创建缺失的配置资源 |

---

### Operation: Service Diagnosis（Service 诊断）

诊断 Service 网络问题，包括 Endpoints 空缺、无法访问、DNS 解析异常等。

#### 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│                    Service 异常诊断流程                       │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: Service 状态检查                                   │
│  ├── kubectl get svc -A                                      │
│  ├── kubectl get endpoints -A                                │
│  └── 检查 Endpoints 是否为空                                  │
│                                                              │
│  Phase 2: 后端 Pod 检查                                      │
│  ├── 检查 Service Selector 与 Pod Label 匹配                 │
│  ├── 检查 Pod Ready 状态                                     │
│  └── 检查 Pod IP 地址                                        │
│                                                              │
│  Phase 3: 网络连通性测试                                     │
│  ├── ClusterIP Service: 内部 Pod 访问测试                    │
│  ├── NodePort Service: 节点端口访问测试                       │
│  └── LoadBalancer Service: SLB 状态检查                      │
│                                                              │
│  Phase 4: DNS 解析检查                                       │
│  ├── 检查 CoreDNS Pod 状态                                   │
│  ├── 测试 Service DNS 解析                                   │
│  └── 检查 Pod DNS 配置                                       │
└─────────────────────────────────────────────────────────────┘
```

#### 执行 — kubectl

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

#### 常见 Service 异常诊断表

| 问题 | 常见原因 | 修复方案 |
|------|---------|---------|
| **Endpoints 空** | Selector 与 Pod Label 不匹配/Pod 未 Ready | 修正 Selector/等待 Pod Ready |
| **ClusterIP 无法访问** | Pod 网络不通/iptables 异常 | 检查 CNI/重启 Pod |
| **NodePort 无法访问** | 节点防火墙/安全组限制 | 配置安全组规则 |
| **LoadBalancer 无法访问** | SLB 异常/后端健康检查失败 | 委托 `alicloud-slb-ops` |
| **DNS 解析失败** | CoreDNS 异常/Pod DNS 配置错误 | 重启 CoreDNS/修正 Pod DNS 配置 |

---

### Operation: Ingress Diagnosis（Ingress 诊断）

诊断 Ingress 路由问题，包括 502/503 错误、路由不匹配、证书问题等。

#### 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│                    Ingress 异常诊断流程                       │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: Ingress 状态检查                                   │
│  ├── kubectl get ingress -A                                  │
│  ├── 检查 Ingress Controller Pod 状态                        │
│  └── 检查 Ingress 资源配置                                   │
│                                                              │
│  Phase 2: 后端检查                                           │
│  ├── 检查 Ingress 关联的 Service                             │
│  ├── 检查 Service Endpoints                                  │
│  └── 检查后端 Pod 健康状态                                   │
│                                                              │
│  Phase 3: 路由验证                                           │
│  ├── 验证域名/路径匹配                                       │
│  ├── 检查 Ingress Controller 日志                            │
│  └── 检查 Nginx 配置                                         │
│                                                              │
│  Phase 4: SLB 检查（委托）                                   │
│  ├── 检查 SLB 后端服务器状态                                 │
│  ├── 检查健康检查配置                                        │
│  └── 委托 alicloud-slb-ops 处理                              │
└─────────────────────────────────────────────────────────────┘
```

#### 执行 — kubectl

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

#### 常见 Ingress 异常诊断表

| 问题 | 常见原因 | 修复方案 |
|------|---------|---------|
| **502 Bad Gateway** | 后端 Pod 不健康/Service 无 Endpoints | 修复后端应用/确保 Pod Ready |
| **503 Service Unavailable** | Ingress Controller 过载/后端不可用 | 扩容 Ingress Controller/修复后端 |
| **路由不匹配** | Ingress 路径/域名配置错误 | 修正 Ingress 配置 |
| **证书问题** | TLS Secret 不存在或过期 | 创建/更新 TLS Secret |
| **SLB 不可达** | SLB 后端健康检查失败 | 委托 `alicloud-slb-ops` |

---

### Operation: Storage Diagnosis（存储诊断）

诊断 PVC/PV 存储问题，包括 PVC Pending、挂载失败、扩容失败等。

#### 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│                    PVC/PV 异常诊断流程                        │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: PVC/PV 状态检查                                    │
│  ├── kubectl get pvc -A                                      │
│  ├── kubectl get pv                                          │
│  └── 识别 Pending PVC                                        │
│                                                              │
│  Phase 2: StorageClass 检查                                  │
│  ├── 检查 PVC 指定的 StorageClass 是否存在                   │
│  ├── 检查 StorageClass 配置                                  │
│  └── 检查 Provisioner 状态                                   │
│                                                              │
│  Phase 3: CSI 驱动检查                                       │
│  ├── kubectl get pods -n kube-system \| grep csi             │
│  ├── 检查 CSI Controller 日志                                │
│  └── 检查云盘 API 响应                                       │
│                                                              │
│  Phase 4: 云盘状态检查（委托）                                │
│  ├── 检查云盘是否存在                                        │
│  ├── 检查云盘状态和容量                                      │
│  └── 委托 alicloud-ecs-ops 处理云盘问题                      │
└─────────────────────────────────────────────────────────────┘
```

#### 执行 — kubectl

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

#### 常见 PVC/PV 异常诊断表

| 问题 | 常见原因 | 修复方案 |
|------|---------|---------|
| **PVC Pending** | StorageClass 不存在/PV 不足/可用区不匹配 | 创建 StorageClass/扩容 PV 配额 |
| **MountVolume 失败** | 云盘不存在/CSI 异常/挂载点冲突 | 恢复云盘/重启 CSI Pod |
| **Volume 扩容失败** | 云盘类型不支持在线扩容 | 使用 ESSD 云盘/手动扩容 |
| **云盘释放后 PVC 异常** | PV reclaimPolicy 为 Delete | 修改 reclaimPolicy 为 Retain |

---

### 跨 Skill 委托协议 (Cross-Skill Delegation)

当 Kubernetes 资源诊断发现底层云产品问题时，应按以下协议委托相关 Skill：

| 委托场景 | 目标 Skill | 委托信息 |
|----------|------------|---------|
| **节点 ECS 异常** | `alicloud-ecs-ops` | ECS InstanceId、异常现象 |
| **SLB 不可达** | `alicloud-slb-ops` | SLB LoadBalancerId、健康检查状态 |
| **VPC/ENI 问题** | `alicloud-vpc-ops` | VPC ID、ENI 配额不足现象 |
| **云盘/存储问题** | `alicloud-ecs-ops` | DiskId、挂载失败现象 |
| **RDS 连接问题** | `alicloud-rds-ops` | RDS InstanceId、连接数暴涨现象 |
| **OSS Bucket 问题** | `alicloud-oss-ops` | Bucket Name、访问失败现象 |

#### 委托示例

```
# 节点 ECS 异常委托
节点 i-ecs-xxx 状态异常，请委托 alicloud-ecs-ops 检查：
- InstanceId: i-ecs-xxx
- 异常现象: 状态 Stopped，无法启动
- 背景: ACK Node NotReady，kubelet 无法连接

# SLB 委托
Ingress 关联的 SLB lb-xxx 后端健康检查失败，请委托 alicloud-slb-ops：
- LoadBalancerId: lb-xxx
- 异常现象: 后端服务器状态异常
- 背景: Ingress 返回 502，Service 正常
```

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

1. **Install `aliyun` CLI** (primary):
   ```bash
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   ```

2. **Bootstrap Go runtime** (JIT SDK fallback): See [integration.md](references/integration.md) for full self-healing install. Quick start:
   ```bash
   if ! command -v go &> /dev/null; then
       OS=$(uname -s | tr '[:upper:]' '[:lower:]'); ARCH=$(uname -m)
       [ "$ARCH" = "x86_64" ] && ARCH="amd64"; [ "$ARCH" = "aarch64" ] && ARCH="arm64"
       curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
       export PATH="/tmp/go-runtime/go/bin:$PATH" GOMODCACHE="/tmp/go-modcache"
       export GOPROXY="https://goproxy.cn,direct"
   fi
   ```

3. **Configure Credentials**:
   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```
   > **IMPORTANT:** When outputting to console, use masking: `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"`.

4. **Verify**:
   ```bash
   aliyun cs GET /clusters
   ```

> **Security:** Never commit credentials. All credentials use `{{env.*}}` placeholders — never real values.

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to ACK.

### 安全 (Security)

| Area | Guidance |
|------|----------|
| **IAM** | Require: `cs:Describe*`, `CreateCluster` scoped to `acs:cs:*:*:cluster/*` |
| **Credentials** | Use `{{env.*}}` only. Use STS for temporary tokens on worker nodes |
| **Network** | Private API server endpoint. Enable network policies (Calico/Terway). Node pools in VPC |
| **Workload Security** | Enable PSS/OPA Gatekeeper. Restrict privileged containers. Enable audit logging |

### 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | Multi-AZ VSwitches for worker nodes. Auto-scaling node pools. Pod disruption budgets |
| **面向精细的运维管控** | Monitor cluster API server latency, node memory/CPU pressure, pod restart rates |
| **面向风险的应急快恢** | Snapshot etcd before upgrades. **RTO:** < 10 min for node failure. **RPO:** 0 (etcd backup) |

#### DR Runbook
```
Phase 1: Verify — Check cluster API health, node status, pod distribution
Phase 2: Restore — Replace unhealthy nodes or restore etcd from snapshot
Phase 3: Validate — Pod scheduling, service connectivity, application health
```

### 成本 (Cost)

| Billing | Best For | Savings |
|---------|----------|---------|
| 按量付费 ECS | Dev/test, volatile workloads | N/A |
| 包年包月 ECS | Stable production nodes | Up to 85% |
| Spot instances | Fault-tolerant/batch workloads | Up to 90% |

**Waste:** Nodes with CPU < 10% for 7d → downsize. Idle LoadBalancers → delete. Over-provisioned resource quotas → reduce.

---

## FinOps Operations (成本优化运维)

### Operation: Resource Optimization Analysis (资源优化分析)

分析集群资源利用率，识别浪费和优化机会。

#### 执行流程

1. 收集节点资源使用率指标 (CMS)
2. 分析 Pod 资源请求 vs 实际使用
3. 识别闲置节点 (CPU < 10% 持续 7天)
4. 识别过度配置的 Pod (请求 > 实际使用 50%)
5. 生成优化建议报告

#### 执行 — CLI

```bash
#!/bin/bash
# ack-resource-optimization.sh
# Usage: ./ack-resource-optimization.sh <ClusterId> <RegionId>

CLUSTER_ID="$1"
REGION="$2"

echo "=== ACK Resource Optimization Analysis ==="

# 1. Get node metrics from CMS
START=$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo ""
echo "### Node Resource Utilization (7-day average) ###"

# Get node list
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
  
  # Flag idle nodes
  if [ "${CPU}" != "N/A" ] && [ $(echo "${CPU} < 10" | bc) -eq 1 ]; then
    echo "  ⚠️  IDLE NODE: CPU < 10% for 7 days - Consider downsizing"
  fi
done

# 2. Pod resource request vs usage analysis (via kubeconfig)
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

#### 输出格式

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

---

### Operation: Idle Resource Detection (闲置资源检测)

识别集群中闲置的节点、Pod、PVC、SLB。

#### 闲置判定标准

| 资源类型 | 闲置判定标准 | 建议操作 |
|----------|-------------|----------|
| Node | CPU < 10% 持续 7天 | 缩容节点池或删除 |
| Pod | Running 但无流量 24小时 | 检查应用状态，停止 |
| PVC | Bound 但 Pod 无挂载 7天 | 检查使用，删除 |
| SLB | 无后端健康服务器 24小时 | 检查关联，删除 |

#### 执行 — CLI

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
    # Check if pod has recent logs
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
  # Check if any pod mounts this PVC
  MOUNTED=$(kubectl get pods -n $NS -o json | jq -r '.items[] | select(.spec.volumes[]?.persistentVolumeClaim?.claimName=="$NAME")' | wc -l)
  if [ "$MOUNTED" -eq 0 ]; then
    echo "PVC: $PVC - No pods mounting - Potentially idle"
  fi
done

# 4. Idle SLBs (delegate to alicloud-slb-ops)
echo ""
echo "### SLBs Associated with Cluster ###"
aliyun cs GET /clusters/$CLUSTER_ID | jq -r '.cluster_id'
echo "Note: For SLB idle detection, delegate to alicloud-slb-ops"
```

---

### Operation: Cost Allocation by Namespace (Namespace 成本分摊)

计算各 Namespace 的资源消耗和成本分摊。

#### 成本分摊公式

```
Namespace_Cost = Σ(Pod_CPU_Request / Node_CPU_Total × Node_Hourly_Cost) + Σ(Pod_Memory_Request / Node_Memory_Total × Node_Hourly_Cost) + Σ(PVC_Size × Disk_Price_GB_Month / Month_Days)
```

#### 执行 — CLI

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

# Get namespace resource requests
kubectl get pods -A -o json | jq -r '
  .items[] | 
  {
    ns: .metadata.namespace,
    cpu_req: .spec.containers[].resources.requests.cpu,
    mem_req: .spec.containers[].resources.requests.memory
  } | 
  group_by(.ns) | 
  map({namespace: .[0].ns, total_pods: length})
' > /tmp/ns-stats.json

echo ""
echo "### Resource Requests by Namespace ###"
kubectl top pods -A | awk 'NR>1 {ns[$1]++; cpu[$1]+=$2; mem[$1]+=$3} END {for (n in ns) print n, ns[n], cpu[n], mem[n]}'

echo ""
echo "### PVC Usage by Namespace ###"
kubectl get pvc -A -o custom-columns='NAMESPACE:.metadata.namespace,PVC:.metadata.name,CAPACITY:.spec.resources.requests.storage' | awk 'NR>1 {ns[$1]++; cap[$1]+=$2} END {for (n in ns) print n, ns[n], cap[n]}'

echo ""
echo "Note: For precise cost calculation, integrate with billing data via alicloud-billing-ops"
```

---

### Operation: Spot Instance Optimization (竞价实例优化)

分析竞价实例使用情况和优化建议。

#### 竞价实例最佳实践

| 场景 | 建议 | 风险控制 |
|------|------|----------|
| 批处理任务 | 使用 Spot | 多 AZ 分布 + 重试机制 |
| 无状态服务 | Spot + 按量混合 | 混合节点池配置 |
| 有状态服务 | 避免 Spot | 使用包年包月或按量 |
| 关键数据库 | 禁止 Spot | 专用节点池 |

#### 执行 — CLI

```bash
#!/bin/bash
# ack-spot-optimization.sh
# Usage: ./ack-spot-optimization.sh <ClusterId>

CLUSTER_ID="$1"
echo "=== ACK Spot Instance Optimization ==="

# Get node pools
echo ""
echo "### Node Pool Spot Instance Usage ###"
aliyun cs GET /clusters/$CLUSTER_ID/nodepools | jq '.nodepools[] | {name, nodepool_id, spot_strategy, instance_type, desired_size}'

# Check spot instances in cluster
echo ""
echo "### Spot Instances in Cluster ###"
aliyun cs GET /clusters/$CLUSTER_ID/nodes | jq '.nodes[] | select(.spot_strategy=="SpotAsPriceGo" or .spot_strategy=="SpotWithPriceLimit") | {instance_id, instance_type, spot_strategy}'

echo ""
echo "### Recommendations ###"
echo "1. Use Spot instances for batch/stateless workloads"
echo "2. Mix Spot + On-demand for resilience (e.g., 70% Spot + 30% On-demand)"
echo "3. Configure spot-autoscaler-addon for automatic spot instance management"
echo "4. Multi-AZ distribution to reduce spot interruption impact"
```

---

### Operation: Budget Alert Integration (预算告警集成)

配置集群成本预算告警。

#### 预算告警配置

```bash
# Budget threshold alerts via CloudMonitor
# Configure alert when cluster cost exceeds budget threshold

aliyun cms PutMetricRuleTargets \
  --RuleId "ack-cost-alert" \
  --Namespace "acs_user_dashboard" \
  --MetricName "cluster_monthly_cost" \
  --Threshold "500" \
  --ComparisonOperator "GreaterThanThreshold" \
  --Statistics "Average" \
  --Period "86400" \
  --ContactGroups "ops-team"
```

#### 成本告警规则建议

| 告警 | 阈值 | 严重等级 | 响应 |
|------|------|----------|------|
| 月度成本超标 | >80% 预算 | P2 | 审查资源使用，识别浪费 |
| 日成本激增 | >150% 基线 | P3 | 检查自动扩缩容活动 |
| 闲置资源累积 | >3个闲置节点 | P3 | 执行闲置资源清理 |

### 效率 (Efficiency)

- **Auto-scaling:** HPA for pods, cluster autoscaler for nodes
- **GitOps:** Cluster state managed via Helm/GitOps pipelines
- **CI/CD:** JSON output by default, compatible with pipelines

### 性能 (Performance)

| Metric | CMS Namespace | Scale Up | Scale Down | Window |
|--------|--------------|----------|------------|--------|
| cpu_utilization | `acs_k8s_dashboard` | > 80% | < 30% | 5 min |
| memory_utilization | `acs_k8s_dashboard` | > 85% | < 50% | 5 min |
| pod_status | `acs_k8s_dashboard` | Failed pods > 0 | — | 5 min |

**Key guidance:** Use managed node pools for automatic OS/container image updates. Set resource requests/limits per workload. Monitor `kubeapiserver` latency for API performance.

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
