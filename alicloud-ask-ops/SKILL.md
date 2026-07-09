---
name: alicloud-ask-ops
description: >-
  Use this skill when the user needs to set up, manage, or troubleshoot an
  Alibaba Cloud Serverless Kubernetes (ASK) cluster — tasks like "create a
  Serverless K8s cluster", "ASK cluster kubeconfig", "按 Pod 弹性 K8s",
  "无服务器 K8s", "ECI-backed K8s", or "help me deploy a Serverless
  Kubernetes cluster" even without naming ASK explicitly. **ASK is identified
  by `cluster_type=ManagedKubernetes` + `profile=Serverless`** in the
  OpenAPI. Catches lifecycle, kubeconfig retrieval, addon management, ECI
  quota checks, and HPA/CronHPA-driven scaling. Does NOT handle
  node-pool-based clusters (ManagedKubernetes without `profile=Serverless` /
  Kubernetes) — those belong to `alicloud-ack-ops`. Does NOT handle ECI pods
  outside the ASK context — delegate to [`alicloud-eci-ops`](../alicloud-eci-ops/SKILL.md).
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+
  runtime (for JIT SDK fallback), valid API credentials, network access to
  Alibaba Cloud CS endpoints.
metadata:
  author: alicloud
  version: "1.1.0"
  last_updated: "2026-06-18"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "CS-2015-12-15 (ASK: cluster_type=ManagedKubernetes + profile=Serverless) / https://www.alibabacloud.com/help/en/ack"
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun help cs` and meta JSON. The `cs` product exposes
    `POST /clusters` (with `cluster_type=ManagedKubernetes` + `profile=Serverless`
    for ASK), `GET /clusters`, `GET /clusters/{id}`, `DELETE /clusters/{id}`,
    `GET /k8s/{id}/user_config` (DescribeClusterUserKubeconfig), and
    `POST /clusters/{id}/tags` (ModifyClusterTags). Some advanced
    fields (e.g. `cluster_spec` Pro variants) may require JIT Go SDK
    fallback or first-use CLI self-check.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

# Alibaba Cloud ACK Serverless (ASK) Operations Skill

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path (control plane) | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/ask-skillopt-wrapper.sh` for all cs control-plane CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun cs` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. | [SkillOpt](references/skillopt-integration.md) |
| Credentials | Read `{env.*}` from environment; wrapper auto-loads repo/skill `.env` — never ask user to paste secrets | [Integration](references/integration.md) |
| GCL | All write operations MUST pass GCL adversarial review before execution | [GCL Rubric](references/rubric.md) |



> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/ask-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun cs ...` 命令在执行时应替换为 `./scripts/ask-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun cs` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。
## ✅ OpenAPI 验证状态 (VERIFIED 2026-06-02)

> **Status: 已通过** `https://api.aliyun.com/meta/v1/products/CS/versions/2015-12-15/api-docs.json`
> + `aliyun cs CreateCluster --help` + `aliyun cs DescribeClusterUserKubeconfig --help`
> 验证。详见 [`references/openapi-verify-checklist.md`](references/openapi-verify-checklist.md)
> 和 [`references/api-sdk-usage.md`](references/api-sdk-usage.md)。
>
> **重大修正（修正训练知识错误）：**
> - ⚠️ **ASK 不是 `cluster_type=Ask`**，而是 `cluster_type=ManagedKubernetes` + `profile=Serverless`
> - 输入字段是 `vpcid`（无分隔符），不是 `vpc_id`
> - `pod_vswitch_ids` 在 OpenAPI spec 中**已废弃**；使用 `vswitch_ids`
> - `container_cidr` 仅 Flannel 模式需要；**Terway 模式（ASK 默认）不要传**
> - Kubeconfig 操作名是 `DescribeClusterUserKubeconfig`（**小写 `k`**）
> - Addons 在 CreateCluster 时**可以**传入（数组，每项含 `name` / `config` / `version` / `disabled`）
> - 标签更新 API 是 `ModifyClusterTags` (`POST /clusters/{id}/tags`)
> - 配 ECI 配额请用 `aliyun eci ListUsage --RegionId <region>`（不是 `DescribeContainerGroupQuota`——那个不存在）

---

## Overview

Alibaba Cloud Container Service for **Serverless Kubernetes (ASK)** provides a
fully-managed Kubernetes control plane where **Pods run directly on Elastic
Container Instance (ECI)** — there are **no worker nodes, no node pools, no
cluster autoscaler** to manage. The user only manages the cluster object itself
plus standard K8s workloads (Deployment/StatefulSet/Job/HPA/CronHPA).

This skill is an **operational runbook** for agents: explicit scope, credential
rules, pre-flight checks, **dual-path execution** (official **`aliyun` CLI**
primary, **JIT Go SDK** fallback), response validation, and failure recovery.

**Execution surface — CLI-primary with JIT Go SDK fallback:**
- **Primary:** `aliyun cs POST /clusters --body '{...cluster_type: "ManagedKubernetes", profile: "Serverless"...}'`
  — static Go binary, covers ASK CRUD, describe, kubeconfig, addon.
- **Fallback:** JIT Go SDK (`github.com/alibabacloud-go/cs-20151215/v4/client`)
  for advanced fields (`container_cidr` vs `pod_vswitch_ids`, profile tuning)
  and any field whose name isn't verifiable from the OpenAPI verify checklist.
- **Console click-paths** are not an agent execution surface in `SKILL.md`.

**Core resources managed by this skill:**
- **ASK Cluster** — serverless cluster object, identified by `cluster_id`.
  In DescribeClusters response: `cluster_type=ManagedKubernetes` +
  `profile=Serverless`.
- **ECI Pod** — workload unit, billed per vCPU×sec, memory×sec, GPU×sec.
- **Addon (ASK-compatible subset)** — e.g. `nginx-ingress-controller`,
  `ack-virtual-node`, `arms-prometheus`. **Node-level DaemonSets
  (`logtail-ds`, etc.) behave differently on ECI and may not apply.**

**Out of scope (explicit delegation):**
- **ManagedKubernetes / Kubernetes clusters** → [`alicloud-ack-ops`](../alicloud-ack-ops/SKILL.md)
- **Raw ECI ContainerGroup operations outside K8s context** → [`alicloud-eci-ops`](../alicloud-eci-ops/SKILL.md)
- **VPC / VSwitch / NAT Gateway / SLB underlying resources** → their own skills

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "ASK", "Serverless Kubernetes", "容器服务 Serverless K8s",
  "无服务器 K8s", "ECI 集群", "按 Pod 弹性", "按 vCPU 秒计费 K8s"
- Task involves lifecycle of a cluster with `cluster_type=ManagedKubernetes` +
  `profile=Serverless` (ASK): create, describe, list, modify (tags /
  deletion_protection), delete
- Task keywords: `ask cluster`, `serverless kubernetes`, `eci pod`, `virtual node`,
  `kubeconfig ask`, `按 pod 弹性`, `vpc 内 eci 容器组`, `ask`
- User asks to deploy workloads onto a cluster that has **no nodes**
  (the ECI-backed Serverless model)
- User asks for **HPA / CronHPA / KEDA** scaling — the *only* scaling
  mechanism in ASK

### SHOULD NOT Use This Skill When

- Cluster is `ManagedKubernetes` or `Kubernetes` (node-based) → delegate to
  [`alicloud-ack-ops`](../alicloud-ack-ops/SKILL.md)
- Task is about **bare ECI ContainerGroup** (not via ASK) → delegate to
  [`alicloud-eci-ops`](../alicloud-eci-ops/SKILL.md)
- Task is about **VPC / VSwitch / NAT / SLB** underlying networking only →
  `alicloud-vpc-ops`, `alicloud-nat-ops`, `alicloud-slb-ops`
- Task is purely billing / account management → `alicloud-billing-ops`
- Task is RAM / permission model only → `alicloud-ram-ops`
- User insists on **console-only** flows with no API → state limitation;
  do not invent undocumented HTTP steps

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
| `{{user.vpc_id}}` | VPC for cluster (also where ECI Pods live) | Ask; validate via VPC skill if needed |
| `{{user.vswitch_ids}}` | VSwitch(s) for ECI Pod ENI allocation | Ask; comma-separated list |
| `{{user.nat_gateway_id}}` | NAT for Pod egress (optional) | Ask only if Pods need internet |
| `{{user.profile}}` | ECI Profile (default `"default"`) | Default if not specified |
| `{{output.cluster_id}}` | From last CreateCluster response | Parse `cluster_id` from response |
| `{{output.api_server_endpoint}}` | Public/internal K8s API URL | Parse `$.api_server.endpoint` |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`**
> MUST be collected interactively when missing.

> **凭据安全（强制）：** 参考
> [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, response
  shapes. ASK uses the same `CS-2015-12-15` API version as
  ManagedKubernetes — distinguished by `cluster_type=ManagedKubernetes` +
  `profile=Serverless`.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per
  spec. ASK-specific common errors: `ErrorClusterNotFound`,
  `ErrorClusterState`, `ErrorCheckAcl`, `QuotaExceeded.Cluster`,
  `QuotaExceeded.Vcpu` (ECI), `QuotaExceeded.Memory` (ECI).
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** `client_token` can be used for CreateCluster.

### Response Field Table (ASK-Specific)

> **⚠️ Field names verified against training knowledge (cutoff 2026-01).**
> Re-verify with `aliyun cs GET /clusters/{id}` on a real cluster before
> declaring fields "missing" in production runs.

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateCluster | `$.cluster_id` | string | New ASK cluster ID |
| DescribeClusters | `$.clusters[].cluster_id` | array | Cluster IDs (mix of Ask + others) |
| DescribeClusters | `$.clusters[].cluster_type` | enum | `"ManagedKubernetes"` for ASK clusters |
| DescribeClusters | `$.clusters[].profile` | string | `"Serverless"` for ASK clusters |
| DescribeClusterDetail | `$.state` | string | Lifecycle state |
| DescribeClusterDetail | `$.current_version` | string | K8s version (managed by ACK; not user-upgradable) |
| DescribeClusterDetail | `$.api_server.endpoint` | string | Public or internal K8s API endpoint |
| DescribeClusterDetail | `$.vpc_id` / `$.vswitch_ids` | string / array | Network binding |
| DescribeClusterDetail | `$.profile` | string | ECI Profile name (ASK-specific) |
| DescribeClusterDetail | `$.deletion_protection` | boolean | Cluster delete lock |
| DescribeClusterDetail | `$.private_zone_enabled` | boolean | PrivateZone DNS |
| DescribeClusterDetail | `$.endpoint_public_access_enabled` | boolean | Public API server access |
| GetKubeconfig | body of GET response | YAML | K8s kubeconfig (treat as secret) |

### Expected State Transitions (ASK Cluster)

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateCluster | — | `running` | 30s | 1800s (30min) |
| DeleteCluster | any stable state | absent / 404 | 30s | 1800s (30min) |
| Modify (tags / deletion_protection) | `running` | `running` | 5s | 60s |

> **Note:** ASK control plane is fully managed. **DO NOT** call
> `PUT /clusters/{id}/upgrade` — there is no UpgradeCluster for ASK.

### Explicitly Unsupported Operations (ASK)

| Operation | Reason | Agent Action |
|-----------|--------|--------------|
| `PUT /clusters/{id}/upgrade` | Control plane is Alibaba-managed | Reject; advise creating new cluster if K8s version bump is needed |
| `POST /clusters/{id}/nodes` | No worker nodes to scale | Reject; advise HPA / CronHPA / KEDA instead |
| `POST /clusters/{id}/nodepools` | No node pool concept | Reject |
| `GET /clusters/{id}/nodes` | No nodes | Returns empty array; do not interpret as error |
| `GET /clusters/{id}/nodepools` | No node pools | Returns empty array; do not interpret as error |

## Quick Start

### What This Skill Does
This skill creates, describes, deletes, and manages Alibaba Cloud Serverless
Kubernetes (ASK) clusters via `aliyun cs ...` (primary) or JIT Go SDK (fallback).
It also handles kubeconfig retrieval, ECI profile consideration, and ECI
quota pre-flight checks.

### Prerequisites
- [ ] `aliyun` CLI installed (or Go runtime for JIT fallback)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`
- [ ] VPC + VSwitch exist in the target region
- [ ] **⚠️** Run the [OpenAPI verify checklist](#⚠️-openapi-验证清单-read-before-execute--必读)
      at the top of this file before first CreateCluster

### Verify Setup
```bash
aliyun version
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo "✅ AK set"
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "✅ SK set (length only)"
aliyun cs GET /clusters --RegionId "$ALIBABA_CLOUD_REGION_ID" | head -20
```

### Your First Command
```bash
# List existing ASK clusters in region
aliyun cs GET /clusters --RegionId $ALIBABA_CLOUD_REGION_ID \
  --output cols=cluster_id,name,cluster_type,state \
  rows=clusters[?cluster_type=='ManagedKubernetes' && profile=='Serverless'].{cluster_id:cluster_id,name:name,cluster_type:cluster_type,state:state}
```

> **Note:** Filter by `profile=Serverless` identifies ASK clusters.

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| Create ASK cluster | Create a new `cluster_type=ManagedKubernetes + profile=Serverless` cluster | Medium | Low |
| Describe / List cluster | View cluster details or list all | Low | None |
| Get kubeconfig | Retrieve K8s kubeconfig (secret!) | Low | Medium — secret handling |
| Modify cluster | Update tags / deletion_protection | Low | Medium — deletion_protection flip can lock cluster |
| Delete cluster | Remove ASK cluster (irreversible) | Low | **High** — destroys all ECI Pods |
| Manage ASK-compatible addons | Install/list ASK-safe addons | Medium | Low |
| **NOT supported** | UpgradeCluster, ScaleOut, NodePool, Node list | — | — |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-02 | Initial ASK skill split from `alicloud-ack-ops`. Covers `cluster_type=ManagedKubernetes + profile=Serverless` lifecycle, kubeconfig, addon subset, ECI quota pre-flight. |
| 1.1.0 | 2026-06-18 | **Renamed** from `alicloud-ack-serverless-ops` → `alicloud-ask-ops` to align with the user-facing product name (ASK = Serverless Kubernetes) and existing internal references. CLI command remains `cs`; wrapper renamed to `ask-skillopt-wrapper.sh`. All cross-skill references and GCL mapping tables updated. |

---


## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI primary / SDK fallback) → Validate
→ Recover**. Do not skip phases.

### Operation: Create ASK Cluster

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI / deps | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys | HALT; user configures env |
| Region | `aliyun cs DescribeClusters --RegionId {{user.region}}` (dry list) | HTTP 200 | Suggest valid region |
| VPC / VSwitch | Validate `{{user.vpc_id}}` and `{{user.vswitch_ids}}` exist | Found | Delegate to VPC skill or ask |
| ECI quota | `aliyun eci ListUsage --body '{"RegionId":"{{user.region}}"}'` | Sufficient vCPU / memory | HALT; user raises ECI quota |
| NAT Gateway | If Pods need internet, ensure NAT exists in VPC | Found | Delegate to NAT skill or ask |
| ECI Profile | `{{user.profile}}` (default `"default"`) | Exists | Verify; use `default` unless user has custom profile |

#### Execution — CLI (`aliyun cs`) (Primary Path)

> **⚠️** Before first use, run `aliyun cs CreateCluster --help` to verify the
> exact body field names. The fields below are based on training knowledge
> (cutoff 2026-01) and the most common ASK patterns; minor field renames
> are possible.

```bash
# Create a Serverless Kubernetes (ASK) cluster — minimal example
aliyun cs POST /clusters \
  --body "{
    \"cluster_type\": \"ManagedKubernetes\",
    \"profile\": \"Serverless\",
    \"name\": \"{{user.cluster_name}}\",
    \"region_id\": \"{{user.region}}\",
    \"vpcid\": \"{{user.vpc_id}}\",
    \"vswitch_ids\": [{{user.vswitch_ids}}],
    \"service_cidr\": \"172.16.0.0/16\",
    \"deletion_protection\": true,
    \"snat_entry\": true,
    \"tags\": [
      {\"key\": \"env\", \"value\": \"prod\"},
      {\"key\": \"owner\", \"value\": \"platform\"}
    ]
  }"
```

> **Required fields (verified):** `name`, `region_id`, `vpcid` (note: input
> field is `vpcid`, **not** `vpc_id`), `vswitch_ids`.
> **Cluster identity (must set together for ASK):** `cluster_type=
> "ManagedKubernetes"` + `profile="Serverless"`. **Do NOT** use
> `cluster_type="Ask"` (outdated; will fail with `InvalidParameter`).
> **Optional but recommended:** `cluster_spec="ack.standard"` (default) or
> Pro variants, `deletion_protection=true`, `snat_entry=true` (for Pod
> internet), `is_enterprise_security_group=true` (default, for Terway).
> **For Terway (default in ASK):** pass `vswitch_ids` only; do **NOT** pass
> `container_cidr` (Terway uses VSwitch ENIs). `pod_vswitch_ids` is
> **DEPRECATED** in the OpenAPI spec.

> **For Pod-to-Internet egress:** ECI Pods share the VPC's NAT Gateway.
> Set `snat_entry=true` to auto-create NAT + SNAT, **OR** pre-create NAT
> in the same VPC (use `alicloud-nat-ops`).

> **Idempotency:** Pass `client_token` (unique string per request) to
> prevent duplicate cluster creation on retry.

> **JSON body from file:** For complex requests, write body to a file:
> `aliyun cs POST /clusters --body file:///tmp/ask-cluster.json`

#### Execution — JIT Go SDK (Fallback Path)

When CLI does not support a specific field, or for advanced ECI profile
tuning:

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

1. Extract `{{output.cluster_id}}` from response (`$.cluster_id`).
2. Poll until `state == "running"`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)（60×30s → running）
```

3. On success, report `cluster_id`, `state`, and `api_server_endpoint`.
4. On terminal failure (`failed`, `deleting`, timeout), go to
   **Failure Recovery**.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` / 400 | 0–1 | — | Fix args from OpenAPI verify checklist; retry once if safe |
| `QuotaExceeded.Cluster` | 0 | — | HALT; user raises cluster quota |
| `QuotaExceeded.Vcpu` / ECI | 0 | — | HALT; user raises ECI vCPU quota |
| `QuotaExceeded.Memory` / ECI | 0 | — | HALT; user raises ECI memory quota |
| `InsufficientBalance` | 0 | — | HALT |
| `ErrorCheckAcl` / RAM | 0 | — | Delegate to RAM skill or user fixes policy |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 10s, 20s, 40s | Retry; then HALT with `RequestId` |

---

### Operation: Describe ASK Cluster

#### Execution — CLI

```bash
# Describe single cluster
aliyun cs GET /clusters/{{user.cluster_id}}

# Filter only Ask clusters in a region
aliyun cs GET /clusters --RegionId {{user.region}} \
  --output cols=cluster_id,name,cluster_type,state,current_version \
  rows=clusters[?cluster_type=='Ask'].{cluster_id:cluster_id,name:name,cluster_type:cluster_type,state:state,current_version:current_version}
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Cluster ID | `$.cluster_id` | Plain text |
| Name | `$.name` | Plain text |
| Cluster Type | `$.cluster_type` / `$.profile` | Will be `"ManagedKubernetes"` + `"Serverless"` for ASK |
| State | `$.state` | `running`, `initial`, `failed`, `deleting` |
| Region | `$.region_id` | Plain text |
| K8s Version | `$.current_version` | e.g. `1.28.3-aliyun.1` — **read-only**, Alibaba-managed |
| API Server Endpoint | `$.api_server.endpoint` | Public or internal; depends on `endpoint_public_access_enabled` |
| VPC ID | `$.vpc_id` | Plain text |
| VSwitches | `$.vswitch_ids` | Array |
| ECI Profile | `$.profile` | ASK-specific; used for ECI scheduling |
| Deletion Protection | `$.deletion_protection` | `true` blocks DeleteCluster |
| Created At | `$.created` | ISO 8601 |

---

### Operation: Get ASK kubeconfig

#### Execution — CLI

```bash
# Public endpoint kubeconfig (works only if endpoint_public_access_enabled=true)
aliyun cs GET /k8s/{{user.cluster_id}}/user_config

# Internal endpoint kubeconfig (VPC-only access; default for ASK)
aliyun cs GET /k8s/{{user.cluster_id}}/user_config \
  --PrivateIpAddress true
```

#### Present to User

Save output to `~/.kube/config` or custom path:

```bash
aliyun cs GET /k8s/{{user.cluster_id}}/user_config > ~/.kube/ask-{{user.cluster_id}}
export KUBECONFIG=~/.kube/ask-{{user.cluster_id}}
kubectl get nodes
```

> **⚠️ Kubeconfig contains a client certificate and is a secret.** Mask
> the file when sharing; chmod 600; do not commit to git.

> **kubectl `get nodes` will show ONE virtual node** (virtual-kubelet)
> even though ECI Pods run on different underlying instances. This is
> normal for ASK — see [Core Concepts](references/core-concepts.md).

#### Validation

```bash
# Confirm API server reachable and cluster is healthy
kubectl get --raw=/healthz
kubectl get nodes
kubectl get ns
```

---

### Operation: Modify ASK Cluster

Supported modifications: `tags`, `deletion_protection`. (K8s version, VPC,
VSwitch, profile are **immutable** after creation — to change them, delete
and recreate.)

#### Pre-flight

- Confirm cluster `state == "running"`.
- For `deletion_protection = true`: user must explicitly confirm the lock.

#### Execution — CLI

```bash
# Update tags
aliyun cs POST /clusters/{{user.cluster_id}}/tags \
  --body '{
    "tags": [
      {"key": "env", "value": "staging"}
    ]
  }'

# Enable deletion protection
aliyun cs POST /clusters/{{user.cluster_id}}/deletion_protection \
  --body '{"deletion_protection": true}'

# Disable deletion protection (user must confirm)
aliyun cs POST /clusters/{{user.cluster_id}}/deletion_protection \
  --body '{"deletion_protection": false}'
```

> **Note:** Exact endpoint paths and field names may vary; verify with
> `aliyun cs POST --help` and the OpenAPI verify checklist.

---

### Operation: Manage Addon (ASK-Compatible Subset)

#### Pre-flight

- Confirm cluster `state == "running"`.
- **Verify addon is ASK-compatible.** Node-level DaemonSets (e.g.
  `logtail-ds`, `node-problem-detector`) have different / unsupported
  behavior on ECI.

#### ASK-Compatible Addon Cheat Sheet

| Addon | ASK Safe? | Notes |
|-------|-----------|-------|
| `nginx-ingress-controller` | ✅ | Deployed as Deployment, not DaemonSet |
| `ack-virtual-node` | ✅ (pre-installed) | Required for ECI scheduling |
| `arms-prometheus` | ✅ | Scrapes ECI Pods via virtual-kubelet |
| `logtail-ds` | ⚠️ | DaemonSet — may not schedule on ECI; consider `logtail-eci` variant |
| `node-problem-detector` | ❌ | No node to monitor |
| `terway-eniip` | ✅ | Default CNI in ASK |
| `csi-plugin` | ✅ | Disk CSI works for ECI Pods |
| `metric-server` | ✅ | HPA requires this |
| `cluster-autoscaler` | ❌ | No node pool to scale; use HPA/CronHPA/KEDA |
| `ack-kubernetes-cronhpa` | ✅ | ASK's main scaling mechanism |

#### Execution — CLI

```bash
# List installed addons
aliyun cs GET /clusters/{{user.cluster_id}}/addons

# Install addon (verify addon name in output above)
aliyun cs POST /clusters/{{user.cluster_id}}/addons \
  --body '{
    "name": "nginx-ingress-controller",
    "version": "v1.10.0"
  }'
```

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

---

### Operation: Delete ASK Cluster

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of cluster
  `{{user.cluster_name}}` (`{{user.cluster_id}}`).
- **MUST** warn user: all ECI Pods, PVs (data may persist on underlying
  disks), and any auto-created SLBs will be destroyed.
- **MUST** check `$.deletion_protection` — if `true`, refuse until user
  disables it.
- **MUST** confirm any user ECI ContainerGroups / PVCs data is backed up
  (PVC underlying cloud disks survive by default; ConfigMaps/Secrets do not).

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

Poll `GET /clusters/{{user.cluster_id}}` until **404** or
`state == "deleted"` (max wait 1800s). If 404, confirm deletion to user.

#### Failure Recovery

| Error pattern | Action |
|---------------|--------|
| `ErrorClusterNotFound` | Already deleted; confirm to user |
| `ErrorClusterState` (not stable) | Wait for cluster to reach stable state; retry |
| `DeletionProtection` | Refuse; ask user to disable deletion_protection first |
| `DependencyResourceExist` (resources still bound) | Ask user to release SLB, PVCs, or other dependencies |

---

## K8s 资源诊断 (K8s Resource Diagnosis)

ASK 是 K8s 集群，标准 K8s 诊断流程（Pod / Service / Ingress / PVC）同样适用。
诊断工具用 `kubectl`，需先获取 kubeconfig。

> **重要差异：** 在 ASK 上 `kubectl get nodes` 只显示**一个虚拟节点**
> (virtual-kubelet 注入)，不要按节点级资源思维判断"集群过载"。
> 用 Pod 维度的指标和 CMS 的 `acs_eci_dashboard` 命名空间做容量分析。

| 诊断场景 | 关键命令 | 关注点 |
|---------|---------|--------|
| Pod Pending | `kubectl describe pod` | 看 Events 里的 `FailedScheduling` 原因（**多半是 ECI 配额/规格**） |
| Pod CrashLoopBackOff | `kubectl logs --previous` | 应用层错误；ECI 日志走 `aliyun sls` 聚合 |
| Service 无 Endpoints | `kubectl get endpoints` | Pod 未 Ready 或 Selector 不匹配 |
| 节点过载 | ❌ **不适用**（无节点） | 用 `kubectl top pods` + ECI 配额 |
| HPA 不生效 | `kubectl get hpa` | 检查 metric-server、ECI 配额、profile |

详细诊断 playbook 见
[`../alicloud-ack-ops/references/troubleshooting.md`](../alicloud-ack-ops/references/troubleshooting.md)
**并补充 ASK 特有的差异**（ECI 配额、virtual-kubelet 行为）— 本 skill 不
复制粘贴该文件，由 Agent 按需跳转阅读。

---

## 跨 Skill 委托协议 (Cross-Skill Delegation)

| 委托场景 | 目标 Skill | 委托信息 |
|----------|------------|----------|
| **ECI vCPU/内存配额不足** | [`alicloud-eci-ops`](../alicloud-eci-ops/SKILL.md) | Region、ECI Profile、Pod spec |
| **Pod 需要访问公网但无 NAT** | `alicloud-nat-ops` | VPC ID、需要 SNAT 的 VSwitch |
| **API server 公网访问配错** | `alicloud-slb-ops` (when present) | 集群 ID、endpoint_public_access_enabled 期望值 |
| **VSwitch 选错 / 不够** | `alicloud-vpc-ops` | VPC ID、需要新增的 VSwitch 列表 |
| **ACR 镜像拉取失败** | `alicloud-acr-ops` (when present) | Image URL、Registry 域名 |
| **SLS 日志聚合** | `alicloud-sls-ops` (when present) | Project、Logstore、ECI 容器组 ID |
| **节点级 K8s 集群 (Managed/Dedicated)** | [`alicloud-ack-ops`](../alicloud-ack-ops/SKILL.md) | 集群 ID、cluster_type 期望为 `ManagedKubernetes`/`Kubernetes` |

---

## Prerequisites

1. **Install `aliyun` CLI** (primary):
   ```bash
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   ```

2. **Bootstrap Go runtime** (JIT SDK fallback): 参见
   [`../alicloud-ack-ops/references/integration.md`](../alicloud-ack-ops/references/integration.md)
   (复用相同的 self-healing 流程)

3. **Configure Credentials**:
   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```
   > **IMPORTANT:** Mask SK in console output:
   > `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"`.

4. **Verify**:
   ```bash
   aliyun cs GET /clusters --RegionId $ALIBABA_CLOUD_REGION_ID
   ```

> **Security:** Never commit credentials. All credentials use `{{env.*}}`
> placeholders — never real values.

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's
[Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).
Reference this section for security, stability, cost, efficiency, and
performance guidance specific to ASK.

### 安全 (Security)

| Area | Guidance |
|------|----------|
| **IAM** | Require: `cs:CreateCluster`, `cs:Describe*`, `cs:DeleteCluster`, `cs:ModifyCluster*` scoped to ASK cluster resources. **Avoid** `cs:*` wildcard. |
| **Credentials** | Use `{{env.*}}` only. Kubeconfig contains client cert — chmod 600, never commit. |
| **Network** | Default `endpoint_public_access_enabled=false` (VPC-only). Use PrivateZone for service discovery. Restrict security group ingress on ECI ENIs. |
| **Workload Security** | Enable PSS / OPA Gatekeeper. Restrict privileged containers. ECI does **not** support hostNetwork / hostPID. |

### 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | Multi-AZ VSwitches for ECI Pods. HPA + CronHPA for elastic scaling. PodDisruptionBudget for stateful workloads. |
| **面向精细的运维管控** | Monitor cluster API server latency, ECI Pod OOM events, HPA scaling events. |
| **面向风险的应急快恢** | ECI Pods are ephemeral — use external persistence (RDS, OSS) for state. **RTO:** cluster recreation in ~3-5 min, ECI Pod scheduling ~30s. **RPO:** 0 for stateless; external DB for stateful. |

#### DR Runbook
```
Phase 1: Verify — Check cluster API health, ECI Pod readiness, ECI quota
Phase 2: Restore — Recreate cluster (if needed), reapply manifests,
          workloads auto-schedule to new ECI Pods
Phase 3: Validate — Pod scheduling, service connectivity, application health
```

### 成本 (Cost)

| Billing | Best For | Savings |
|---------|----------|---------|
| **ECI on-demand (vCPU×sec)** | Variable workloads, dev/test, batch | Avoids idle-node waste |
| **ECI Savings Plans** | Stable 24/7 baseline | Up to 60% vs on-demand |
| **ECI Spot** | Fault-tolerant batch | Up to 90% vs on-demand |

**Waste:** Idle ECI Pods with CPU < 5% for 30 min → reduce replicas or
tighten HPA. No concept of "idle node" — cost is per Pod.

> **Cost allocation:** `kubectl top pods` + ECI pricing → per-namespace
> cost. See [FinOps Operations](#finops-operations) below.

### 效率 (Efficiency)

- **Auto-scaling:** HPA + CronHPA / KEDA — the **only** scaling mechanism.
- **GitOps:** Cluster state managed via Helm/ArgoCD/Flux.
- **CI/CD:** JSON output by default, compatible with pipelines.

### 性能 (Performance)

| Metric | CMS Namespace | Scale Up (HPA target) | Scale Down | Window |
|--------|--------------|----------------------|------------|--------|
| `container.cpu.usage` (Pod) | `acs_eci_dashboard` | > 70% | < 30% | 5 min |
| `container.memory.usage` (Pod) | `acs_eci_dashboard` | > 80% | < 50% | 5 min |
| `pod.status.ready` | `acs_k8s_dashboard` | ready_ratio < 0.9 | — | 1 min |
| `eci.vcpu.usage` (account-level) | `acs_eci_dashboard` | > 80% | — | 5 min |

**Key guidance:** Set HPA `requests` accurately (not `limits`) — ECI
sizes Pods to `requests`. Set `priorityClassName` for critical workloads
to win ECI scheduling under quota pressure.

---

## FinOps Operations (成本优化运维)

### Operation: Namespace Cost Allocation

```bash
#!/bin/bash
# ask-namespace-cost-allocation.sh
# Usage: ./ask-namespace-cost-allocation.sh <ClusterId> <EciVcpuPerHour> <EciMemGbPerHour>

CLUSTER_ID="$1"
VCPU_COST="$2"  # e.g., ¥0.05/hour
MEM_COST="$3"    # e.g., ¥0.01/GB/hour

aliyun cs GET /k8s/$CLUSTER_ID/user_config > /tmp/kubeconfig
export KUBECONFIG=/tmp/kubeconfig

echo "=== Namespace Resource Usage (real-time) ==="
kubectl top pods -A --sort-by=memory

echo ""
echo "=== Estimated Cost by Namespace (assuming current usage) ==="
kubectl get pods -A -o json | jq -r '
  .items[] |
  {
    ns: .metadata.namespace,
    pod: .metadata.name,
    cpu: .spec.containers[].resources.requests.cpu,
    mem: .spec.containers[].resources.requests.memory
  }
' | head -30

echo ""
echo "Note: Real cost = sum over time of (cpu_request * vcpu_price) + (mem_request * mem_price)"
```

### Operation: Idle ECI Pod Detection

ASK 没有"空闲节点"，但有"空闲 Pod"：

| Resource | Idle Criterion | Action |
|----------|---------------|--------|
| Pod | Running but `kubectl top` shows CPU < 5% for 30 min | Tighten HPA `minReplicas`; check if workload is still needed |
| Namespace | No Pods scheduled for 7 days | Delete namespace (with confirmation) |
| HPA | `currentReplicas` > `desiredReplicas` for 1h | Check HPA config; possibly over-provisioned |

---

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [CLI Usage](references/cli-usage.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [Troubleshooting](references/troubleshooting.md)
- [Monitoring](references/monitoring.md)
- [Integration](references/integration.md)
- [OpenAPI Verify Checklist](references/openapi-verify-checklist.md) — **必读**
- [Polling Patterns](references/polling-patterns.md) — ASK cluster state 轮询模板
- [Well-Architected Assessment](references/well-architected-assessment.md)

## Operational Best Practices

- **Least privilege:** RAM policies scoped to ASK cluster actions; avoid
  `cs:*` wildcard. Separate ECI access for debugging.
- **Availability:** Use multi-AZ VSwitches for ECI Pod ENIs. Always
  configure HPA with sensible `minReplicas` ≥ 2 for production.
- **Cost:** Use ECI Savings Plans for stable baselines. Set HPA
  `requests` accurately. Use CronHPA for predictable diurnal patterns.
- **Security:** Rotate cluster certificates (managed by ACK). Use
  private API server endpoints. Enable audit logging. Kubeconfig
  chmod 600.
- **Pod Security:** Enable PSS / OPA Gatekeeper. Restrict privileged
  containers (ECI does not support hostNetwork/hostPID).
- **Network Policy:** Use Calico / Terway network policies. ECI ENIs
  respect security group rules.

---

## Quality Gate (GCL)

Phase 5 rollout for `recommended` skills per [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Recommended** (Phase 5, `max_iter=3`) |
| Most-scrutinized | `DeleteCluster` (check + disable DeletionProtection first; backup kubeconfig) |

### Changelog
1.0.0 | 2026-06-04 | Phase 5 `recommended` rollout for ask-ops.

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only`, the skill MUST provide
  `assets/code-snippets/`. **DOES NOT APPLY** — 本 skill 为 `dual-path`，
  CLI/SDK 已覆盖，无需 code snippets.
