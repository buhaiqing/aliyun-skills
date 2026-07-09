---
name: alicloud-ack-ops
description: >-
  Use this skill when the user needs to set up, manage, or troubleshoot a
  Kubernetes cluster on Alibaba Cloud (ACK) of type `ManagedKubernetes` or
  `Kubernetes` (i.e. worker-node based). Catches tasks like "create a cluster",
  "add nodes", "upgrade K8s version", "集群健康检查", "节点 NotReady",
  "获取 kubeconfig" — even when the user just says "帮我弄个 K8s 集群" or "my
  Alibaba cluster is broken" without naming ACK. Does NOT handle Serverless
  Kubernetes (ASK, `cluster_type=Ask`) — that is in `alicloud-ask-ops`.
  Also does NOT handle VPC, SLB, ECS, RAM, or billing — those belong to their
  own skills.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+
  runtime (for JIT SDK fallback), valid API credentials, network access to
  Alibaba Cloud CS endpoints.
metadata:
  author: alicloud
  version: "2.1.1"
  last_updated: "2026-06-11"
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

**Core resources managed by this skill (ManagedKubernetes / Kubernetes only):**
- **Cluster** — the Kubernetes control plane and managed infrastructure.
- **Node Pool** — homogeneous groups of worker nodes with shared configuration.
- **Addon** — cluster components (e.g., ingress, metrics-server, logtail).

> **Out of scope:** ASK (Serverless Kubernetes, `cluster_type=Ask`) has **no
> nodes, no node pools, no node-level scaling** — see
> [`alicloud-ask-ops`](../alicloud-ask-ops/SKILL.md).

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/ack-skillopt-wrapper.sh` for all ACK CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun cs` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. For runtime enforcement, source the shared shim: `source ../../alicloud-skill-generator/scripts/skillopt-shim/aliyun-shim.sh`. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md), [Shim](file://../../alicloud-skill-generator/scripts/skillopt-shim/SHIM-README.md) |
| Credentials | Read `{{env.*}}` only from environment; never ask user to paste or print secrets | [Integration](references/integration.md) |
| GCL | All write operations MUST pass GCL adversarial review before execution | [GCL Rubric](references/rubric.md) |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "ACK", "Alibaba Cloud Kubernetes", "容器服务", "容器服务
  Kubernetes版", "K8s", or "Kubernetes cluster on Alibaba Cloud"
- Task involves CRUD or lifecycle operations on **Cluster** or **Node Pool**
  (create, describe, modify, delete, list, scale, upgrade)
- Task keywords: `cluster`, `node pool`, `worker node`, `managed kubernetes`,
  `pro kubernetes`, `addon`, `ingress`, `scaling`, `upgrade`, `kubeconfig`
  — **NOT** triggered by Serverless / ASK / `cluster_type=Ask` / 按 Pod 弹性 /
  无服务器 K8s / ECI Pod; those belong to `alicloud-ask-ops`
- User asks to deploy, configure, troubleshoot, or monitor ACK **via API, SDK,
  CLI, or automation**
- **集群巡检场景:** "检查K8s集群", "巡检ACK", "集群健康检查", "查看命名空间/Pod/Service",
  "kubectl无法连接", "集群访问不了", "没有权限访问集群", "403 Forbidden" — 触发后先执行
  [前置检查](references/inspection-access-patterns.md)确定访问方式，再选择标准巡检或降级方案

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to:
  `alicloud-billing-ops` (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when
  present)
- Task is about **VPC / SLB / NAS / OSS** underlying resources but not ACK
  cluster lifecycle → delegate to: `alicloud-vpc-ops`, `alicloud-slb-ops`, etc.
- Task is about **ECI / Serverless** outside ACK context → delegate to:
  [`alicloud-eci-ops`](../alicloud-eci-ops/SKILL.md)
- Cluster is **Serverless Kubernetes (ASK, `cluster_type=Ask`)** → delegate to:
  [`alicloud-ask-ops`](../alicloud-ask-ops/SKILL.md)
- User insists on **console-only** flows with no API → state limitation; do not
  invent undocumented HTTP steps

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

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

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

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
| 2.1.1 | 2026-06-11 | 新增巡检前置检查机制: ① 添加 inspection-access-patterns.md 文档 ② 更新 intelligent-inspection.md 增加前置检查脚本 ③ SKILL.md 增加巡检触发规则和前置检查操作章节 |
| 1.0.0 | 2026-05-14 | Initial ACK skill with cluster and node pool operations |

> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/ack-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun cs ...` 命令在执行时应替换为 `./scripts/ack-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun cs` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。

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

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

1. Extract `{{output.cluster_id}}` from response (`$.cluster_id`).
2. Poll until `state == "running"`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)（CreateCluster → running, 60×30s）
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

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

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
完整诊断脚本见 [references/k8s-diagnosis-scripts.md#pod-diagnosis](references/k8s-diagnosis-scripts.md#pod-diagnosis)

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
完整诊断脚本见 [references/k8s-diagnosis-scripts.md#service-diagnosis](references/k8s-diagnosis-scripts.md#service-diagnosis)

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
完整诊断脚本见 [references/k8s-diagnosis-scripts.md#ingress-diagnosis](references/k8s-diagnosis-scripts.md#ingress-diagnosis)

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
完整诊断脚本见 [references/k8s-diagnosis-scripts.md#storage-diagnosis](references/k8s-diagnosis-scripts.md#storage-diagnosis)

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

### Operation: Inspection Pre-flight Check（巡检前置检查）

在执行任何需要 kubectl 访问的巡检或诊断操作前，**必须**先执行前置检查，确认集群访问方式和权限。

> **为什么需要前置检查？**
> - 企业 ACK 集群默认只有内网端点（安全最佳实践）
> - 子账号默认没有集群 RBAC 权限（最小权限原则）
> - 避免因网络/权限问题导致巡检中断

#### Pre-flight Checks

| 检查项 | 方法 | 预期结果 | 失败处理 |
|--------|------|---------|---------|
| 集群状态 | `aliyun cs DescribeClusterDetail --ClusterId {{user.cluster_id}}` | `state == "running"` | HALT，提示集群非运行状态 |
| API 端点 | 检查 `master_url.api_server_endpoint` | 有公网端点或确认内网环境 | 降级至 Cloud Assistant 方案 |
| RBAC 权限 | `aliyun cs DescribeUserClusterNamespaces --ClusterId {{user.cluster_id}}` | HTTP 200 | 提示授权命令 |

#### Execution — CLI

完整前置检查脚本见 [references/inspection-access-patterns.md](references/inspection-access-patterns.md)

#### 降级方案决策

根据前置检查结果，自动选择执行方案：

| 检查结果 | 执行方案 | 参考文档 |
|---------|---------|---------|
| 有公网端点 + RBAC 正常 | 标准 kubectl 方案 | [intelligent-inspection.md](references/intelligent-inspection.md) |
| 仅内网端点 | Cloud Assistant 方案 | [inspection-access-patterns.md](references/inspection-access-patterns.md) |
| 权限不足 | 提示授权后 HALT | 本章节 |

#### Failure Recovery

| 错误模式 | 用户提示 |
|---------|---------|
| `i/o timeout` (连接内网端点) | "该集群未开启公网API访问。可选方案：① 连接VPN后重试 ② 使用 Cloud Assistant 在节点上执行" |
| `ForbiddenQueryClusterNamespace` | "当前账号缺少集群 RBAC 权限。授权命令：aliyun cs GrantPermissions --ClusterId xxx" |
| `ErrorClusterNotFound` | "集群不存在或已被删除。请确认 cluster_id 正确。" |

---

### Operation: Intelligent Inspection（智能巡检）

一键执行ACK集群的全面健康检查。整合集群状态 + 节点状态 + CMS 指标 + 综合评分。Full CLI script at [references/intelligent-inspection.md](references/intelligent-inspection.md).

**5-step workflow:** Cluster state check → Node health → CPU/metrics via CMS → Addon status → Scoring report.

**Scoring criteria:**

| 维度 | 评分依据 | 权重 |
|------|---------|------|
| 集群状态 | running=100, 其他=0 | 25% |
| 节点Ready比例 | 100%=100, >90%=60, <90%=0 | 25% |
| 集群CPU使用率 | <70%=100, 70-85%=60, >85%=0 | 20% |
| 集群内存使用率 | <75%=100, 75-90%=60, >90%=0 | 20% |
| Addon状态 | 全部正常=100, 有异常=0 | 10% |

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

## Well-Architected Assessment

Evaluated per Alibaba Cloud [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).

| Pillar | Key Guidance |
|--------|-------------|
| **Security** | IAM: `cs:Describe*`, `CreateCluster`. Private API server endpoint. Enable network policies + PSS/OPA Gatekeeper. Enable audit logging |
| **Stability** | Multi-AZ VSwitches. Auto-scaling node pools. Pod disruption budgets. Snapshot etcd before upgrades. RTO < 10min for node failure, RPO=0 |
| **Cost** | Postpaid dev/test, Prepaid up to 85% off, Spot up to 90%. Nodes with CPU < 10% for 7d → downsize. Idle LBs → delete |
| **Efficiency** | HPA + cluster autoscaler. Helm/GitOps pipelines. JSON output for CI/CD |
| **Performance** | cpu_utilization > 80% scale up, < 30% down. memory_utilization > 85% alert. Monitor kubeapiserver latency |

---

## FinOps Operations (成本优化运维)

Cost optimization workflows for ACK clusters. **Only load the specific reference when the user asks for that capability.**

| Operation | Purpose | Reference |
|-----------|---------|-----------|
| **Resource Optimization Analysis** | Analyze cluster resource utilization, identify waste, generate optimization recommendations | Full CLI script and examples at [references/finops-resource-optimization.md](references/finops-resource-optimization.md) |
| **Idle Resource Detection** | Identify idle nodes, pods, PVCs, and SLBs | Full spec at [references/finops-idle-detection.md](references/finops-idle-detection.md) |
| **Cost Allocation by Namespace** | Calculate per-namespace resource consumption and cost split | Full script at [references/finops-cost-allocation.md](references/finops-cost-allocation.md) |
| **Spot Instance Optimization** | Analyze spot instance usage and optimization suggestions | Full guide at [references/finops-spot-optimization.md](references/finops-spot-optimization.md) |
| **Budget Alert Integration** | Configure cluster budget threshold alerts | Full spec at [references/finops-budget-alert.md](references/finops-budget-alert.md) |

### Efficiency

- **Auto-scaling:** HPA for pods, cluster autoscaler for nodes
- **GitOps:** Cluster state managed via Helm/GitOps pipelines
- **CI/CD:** JSON output by default, compatible with pipelines

### Performance

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
- [Polling Patterns](references/polling-patterns.md) — 集群/nodepool 状态与删除轮询模板
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)
- [Inspection Access Patterns](references/inspection-access-patterns.md) — 巡检前置检查、访问模式与降级策略
- [Intelligent Inspection](references/intelligent-inspection.md) — 集群智能巡检脚本与评分标准
- [K8s Diagnosis Scripts](references/k8s-diagnosis-scripts.md) — Pod/Service/Ingress/Storage 诊断脚本

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

---

## Quality Gate (GCL)

Phase 5 rollout for `recommended` skills per [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Recommended** (Phase 5, `max_iter=3`) |
| Most-scrutinized | `DeleteCluster` (irreversible; backup kubeconfig + check DeletionProtection), `DeleteNodePool` (last pool with critical workloads) |

### Changelog
1.0.0 | 2026-06-04 | Phase 5 `recommended` rollout for ack-ops.

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `dual-path`，CLI/SDK 已覆盖，无需 code snippets.
