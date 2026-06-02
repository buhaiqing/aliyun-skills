---
name: alicloud-eip-ops
description: >-
  Use this skill to manage the full lifecycle of Alibaba Cloud Elastic IP
  Addresses (EIP) — allocate, describe, modify, release, associate,
  unassociate, convert, and monitor EIPs. Manage EIP bandwidth, billing modes,
  and EIP bandwidth plans. Diagnose EIP binding failures, connectivity issues,
  and bandwidth limits. Reach for this skill when the user needs public IP
  management, reports "EIP cannot be bound", "public IP unreachable", "bandwidth
  insufficient", or wants to deploy, configure, troubleshoot, or monitor Alibaba
  Cloud elastic public IPs — even if they just say "弹性公网IP", "EIP",
  "公网IP", "弹性IP" without naming the product explicitly. Keywords: EIP,
  elastic public IP, 弹性公网IP, 公网IP, AllocateEipAddress, ReleaseEipAddress,
  AssociateEipAddress, bandwidth plans. Do NOT use for NAT gateway management,
  VPC creation, compute (ECS), databases (RDS), load balancing (SLB/ALB),
  containers (ACK), billing/accounting, or RAM-only tasks.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-05-16"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "VPC 2016-04-28 / https://help.aliyun.com/zh/vpc/developer-reference/api-vpc-2016-04-28-overview"
  cli_applicability: cli-first
  cli_support_evidence: "Confirmed via `aliyun help vpc | grep -i eip` — EIP operations (AllocateEipAddress, DescribeEipAddresses, ReleaseEipAddress, AssociateEipAddress, UnassociateEipAddress, ModifyEipAddressAttribute, ConvertNatPublicIpToEip, etc.) are fully supported by the official aliyun CLI."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud EIP Operations Skill

## Overview

Alibaba Cloud EIP (Elastic IP Address) provides independent public IP addresses that can be dynamically associated with cloud resources. This skill is an **operational runbook** for agents: explicit scope, credential rules, pre-flight checks, **cli-first execution** (official **`aliyun` CLI** as primary path, **JIT Go SDK** as fallback), response validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: cli-first`:** Official `aliyun` fully supports EIP. CLI is the **primary** execution path for all operations. JIT Go SDK is the **fallback** only when CLI lacks support for a specific edge-case operation.

### Quick Start

不知道从哪里开始？直接看 [Prompt Examples](references/prompt-examples.md)，里面有 30+ 条自然语言提示词示例，覆盖 EIP 分配、绑定、解绑、带宽修改、续费、释放等场景，复制即用。

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud EIP" OR "弹性公网IP" OR "Elastic IP Address" OR "公网IP"
- Task involves CRUD or lifecycle operations on **EIP** (allocate, describe, modify, release)
- Task involves **EIP association/unassociation** (bind to ECS, NAT, SLB, HaVip, ENI)
- Task involves **EIP bandwidth modification** (upgrade/downgrade bandwidth)
- Task involves **EIP billing mode conversion** (PayByBandwidth ↔ PayByTraffic)
- Task involves **EIP bandwith plans** (create, describe, modify, delete, add/remove EIP)
- Task involves **EIP conversion** (convert NAT public IP to EIP)
- Task keywords: EIP, elastic IP, 弹性公网IP, 公网IP, AllocateEipAddress, ReleaseEipAddress, AssociateEipAddress, UnassociateEipAddress, bandwidth, bandwidth plans, IP conversion
- User asks to deploy, configure, troubleshoot, or monitor EIP resources **via API, SDK, CLI, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops` (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when present)
- Task is about **NAT gateway management** → delegate to: `alicloud-nat-ops`
- Task is about **VPC/vSwitch creation** → delegate to: `alicloud-vpc-ops` (when present)
- Task is about **ECS instances** → delegate to: `alicloud-ecs-ops`
- Task is about **RDS / databases** → delegate to: `alicloud-rds-ops` (when present)
- Task is about **SLB / load balancing** → delegate to: `alicloud-slb-ops`
- Task is about **VPN gateway** → delegate to: `alicloud-vpc-ops` (when present)

### Delegation Rules

- If binding EIP to ECS for direct internet access, use this skill for EIP operations, but verify ECS instance exists via `alicloud-ecs-ops`.
- If binding EIP to NAT Gateway, use this skill for EIP operations, but verify NAT Gateway exists via `alicloud-nat-ops`.
- If binding EIP to SLB, use this skill for EIP operations, but verify SLB exists via `alicloud-slb-ops`.
- If creating SNAT/DNAT for NAT Gateway, the EIP allocation uses this skill, but SNAT/DNAT entry management uses `alicloud-nat-ops`.

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.eip_id}}` | User-supplied EIP Allocation ID | Ask once; reuse |
| `{{user.eip_name}}` | User-supplied EIP name | Ask once; reuse |
| `{{user.bandwidth}}` | User-supplied bandwidth (Mbps) | Ask once; reuse |
| `{{user.instance_id}}` | User-supplied bound instance ID | Ask once; reuse |
| `{{user.instance_type}}` | Bound instance type (EcsInstance/Nat/SLBInstance/HaVip/NetworkInterface/Ngw) | Ask once; reuse |
| `{{user.billing_mode}}` | Billing mode (PayByBandwidth/PayByTraffic) | Ask once; reuse |
| `{{output.allocation_id}}` | From AllocateEipAddress response | Parse JSON path `$.AllocationId` |
| `{{output.eip_address}}` | From AllocateEipAddress response | Parse JSON path `$.IpAddress` |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for fields, enums, and response shapes.
- **Errors:** Map SDK/HTTP errors to `code` / `message` per spec.
- **Timestamps:** ISO 8601 format.
- **Idempotency:** VPC API supports `ClientToken` for idempotent operations.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| AllocateEipAddress | `$.AllocationId` | string | EIP allocation ID |
| AllocateEipAddress | `$.IpAddress` | string | Allocated public IP address |
| DescribeEipAddresses | `$.EipAddresses.EipAddress[].AllocationId` | array | EIP allocation IDs |
| DescribeEipAddresses | `$.EipAddresses.EipAddress[].IpAddress` | array | EIP addresses |
| DescribeEipAddresses | `$.EipAddresses.EipAddress[].Status` | array | Status: Available/InUse/Associating/Unassociating/Releasing |
| AssociateEipAddress | `$.RequestId` | string | Request identifier |
| UnassociateEipAddress | `$.RequestId` | string | Request identifier |
| ReleaseEipAddress | `$.RequestId` | string | Request identifier |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| AllocateEipAddress | — | `Available` | 5s | 120s |
| AssociateEipAddress | `Available` | `InUse` | 5s | 120s |
| UnassociateEipAddress | `InUse` | `Available` | 5s | 120s |
| ReleaseEipAddress | `Available` | (deleted) | 5s | 60s |

## Quick Start

### What This Skill Does

This skill enables you to allocate, manage, bind, and release Alibaba Cloud EIPs (Elastic IP Addresses) using the `aliyun` CLI (primary) or JIT Go SDK (fallback).

### Prerequisites

- [ ] `aliyun` CLI installed (or Go runtime for JIT fallback)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`

### Verify Setup

```bash
# Check CLI and credentials
aliyun vpc DescribeEipAddresses --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --PageSize 1
```

### Your First Command

```bash
# Example: List all EIPs
aliyun vpc DescribeEipAddresses --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --output cols=AllocationId,IpAddress,Status,InstanceId rows=EipAddresses.EipAddress[].{AllocationId:AllocationId,IpAddress:IpAddress,Status:Status,InstanceId:InstanceId}
```

### Next Steps

- [Core Concepts](references/core-concepts.md) — Understand EIP architecture and billing
- [Common Operations](#execution-flows) — Allocate, bind, release, and manage EIPs
- [Troubleshooting](references/troubleshooting.md) — Fix common EIP issues

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| Allocate EIP | Request a new elastic public IP | Low | Low |
| Describe | View EIP details and status | Low | None |
| Associate | Bind EIP to a cloud resource (ECS, NAT, SLB, etc.) | Low | Low |
| Unassociate | Unbind EIP from a resource | Low | **Medium** — causes brief network interruption |
| Modify | Change bandwidth, billing mode, or name | Low | Low |
| Release | Permanently release an EIP | Low | **High** — irreversible |
| List EIP Bandwidth Plans | View bandwidth plans and member EIPs | Low | None |
| Create/Add to Plans | Add EIP to shared bandwidth | Medium | Low |



## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute → Validate → Recover**. Do not skip phases.

### Operation: Allocate EIP

**When to use:**
- You need a public IP address that can be independently managed from compute lifecycle
- You want to reassign IPs between ECS, NAT Gateway, SLB without recreating

**What you need:**
- Region ID
- Bandwidth value (Mbps, depends on billing mode)
- ISP type (optional, default: BGP)

**What to expect:**
- A new EIP is allocated within seconds
- You receive an AllocationId and IpAddress for future operations

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI availability | `aliyun vpc DescribeRegions` | Exit code 0 | HALT; install CLI |
| Credentials | Environment variables set | Non-empty keys | HALT; configure credentials |
| Region validity | DescribeRegions | Region present in response | Suggest valid regions |
| EIP quota | DescribeEipAddresses + TotalCount | Under EIP quota limit | HALT; request quota increase |

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
# Allocate EIP (PayByTraffic billing, bandwidth = 5 Mbps)
aliyun vpc AllocateEipAddress \
  --RegionId "{{user.region}}" \
  --Bandwidth "5" \
  --InternetChargeType "PayByTraffic" \
  --ISP "BGP" \
  --Name "{{user.eip_name}}"
```

#### Post-execution Validation

1. Capture `{{output.allocation_id}}` from response `$.AllocationId`.
2. Capture `{{output.eip_address}}` from response `$.IpAddress`.
3. Verify:

```bash
aliyun vpc DescribeEipAddresses \
  --RegionId "{{user.region}}" \
  --AllocationId "{{output.allocation_id}}" \
  --output cols=AllocationId,IpAddress,Status,InternetChargeType rows=EipAddresses.EipAddress[].{AllocationId:AllocationId,IpAddress:IpAddress,Status:Status,InternetChargeType:InternetChargeType}
```

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action | UX Feedback |
|---------------|-------------|---------|--------------|-------------|
| `InvalidInstanceType.ValueNotSupported` | 0 | — | HALT; verify InstanceType | `[ERROR] Invalid InstanceType. Supported values: EcsInstance, Nat, SLBInstance, HaVip, NetworkInterface, Ngw.` |
| `QuotaExceeded.EipAddress` | 0 | — | HALT | `[ERROR] QuotaExceeded: EIP quota reached. Delete unused EIPs or request increase.` |
| `InsufficientBalance` | 0 | — | HALT | `[ERROR] InsufficientBalance: Account balance insufficient. Recharge your account.` |
| `InvalidBandwidth.ValueNotSupported` | 0 | — | HALT; suggest valid range | `[ERROR] Invalid bandwidth. For PayByTraffic: 1-200 Mbps. For PayByBandwidth: 1-500 Mbps.` |
| `Throttling` / 429 | 3 | exponential | Back off | `⚠️ Rate limit reached. Retrying in {backoff}s...` |
| `InternalError` | 3 | 2s, 4s, 8s | Retry; then HALT | `[ERROR] InternalError: Server-side error. Retry or escalate.` |

### Operation: AssociateEipAddress

**When to use:**
- Bind an existing EIP to an ECS instance for public internet access
- Bind EIP to NAT Gateway for SNAT/DNAT source IP
- Bind EIP to SLB for public-facing load balancer

**What you need:**
- EIP AllocationId (must be `Available` state)
- Target InstanceId (must be in same region)
- InstanceType

**What to expect:**
- EIP transitions from `Available` → `InUse` within seconds

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| EIP exists and Available | DescribeEipAddresses | Status=`Available` | EIP already in use or deleted |
| Target instance exists | Resource-specific describe | Instance found | HALT; verify resource |
| Same region | Compare RegionId fields | Match | HALT; EIP and target must be in same region |
| No existing EIP on target | Check target current EIP | None | Ask: Unbind existing EIP first? |

#### Execution

```bash
# Associate EIP to ECS instance
aliyun vpc AssociateEipAddress \
  --RegionId "{{user.region}}" \
  --AllocationId "{{user.eip_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --InstanceType "EcsInstance"

# Or associate to NAT Gateway
# aliyun vpc AssociateEipAddress \
#   --RegionId "{{user.region}}" \
#   --AllocationId "{{user.eip_id}}" \
#   --InstanceId "{{user.nat_gateway_id}}" \
#   --InstanceType "Nat"
```

#### Post-execution Validation

Poll until `Status` = `InUse`:

```bash
aliyun vpc DescribeEipAddresses \
  --RegionId "{{user.region}}" \
  --AllocationId "{{user.eip_id}}"
```

### Operation: UnassociateEipAddress

**When to use:**
- Remove EIP from current resource before binding to another
- Migrate IP address between resources
- Prepare EIP for release

**What you need:**
- EIP AllocationId (must be `InUse` state)
- Current bound InstanceId and InstanceType

#### Pre-flight (Safety Gate)

- **Warning:** Unbinding causes **network interruption** to the bound resource.
- **MUST** confirm user intent before proceeding.
- Verify EIP is in `InUse` state.

#### Execution

```bash
aliyun vpc UnassociateEipAddress \
  --RegionId "{{user.region}}" \
  --AllocationId "{{user.eip_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --InstanceType "{{user.instance_type}}"
```

#### Post-execution Validation

```bash
aliyun vpc DescribeEipAddresses \
  --RegionId "{{user.region}}" \
  --AllocationId "{{user.eip_id}}"
```

Verify `Status` = `Available` and fields `InstanceId` and `InstanceType` are empty.

### Operation: Modify EIP (Bandwidth/Billing)

**When to use:**
- Scale up/down bandwidth based on traffic needs
- Switch between PayByBandwidth (fixed monthly) and PayByTraffic (usage-based)

**What you need:**
- EIP AllocationId
- New bandwidth value or new billing mode

#### Execution

```bash
# Upgrade bandwidth
aliyun vpc ModifyEipAddressAttribute \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --AllocationId "{{user.eip_id}}" \
  --Bandwidth "100"

# Switch billing mode
aliyun vpc ModifyEipAddressAttribute \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --AllocationId "{{user.eip_id}}" \
  --InternetChargeType "PayByTraffic" \
  --Bandwidth "100"
```

### Operation: ReleaseEipAddress

#### Pre-flight (Safety Gate)

- **MUST** unbind EIP first (`Status` must be `Available`).
- **MUST** obtain explicit confirmation: irreversible release of `{{output.eip_address}}` (`{{user.eip_id}}`).
- **MUST NOT** proceed without clear user assent.

#### Execution

```bash
# Step 1: Unbind if necessary (only if InUse)
aliyun vpc UnassociateEipAddress \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --AllocationId "{{user.eip_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --InstanceType "{{user.instance_type}}"

# Step 2: Release
aliyun vpc ReleaseEipAddress \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --AllocationId "{{user.eip_id}}"
```

#### Post-execution Validation

```bash
aliyun vpc DescribeEipAddresses \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --AllocationId "{{user.eip_id}}"
```

Empty result = confirmed released.

### Operation: List EIPs

```bash
# List all EIPs with details
aliyun vpc DescribeEipAddresses --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=AllocationId,IpAddress,Status,InstanceId,Bandwidth,Name rows=EipAddresses.EipAddress[].{AllocationId:AllocationId,IpAddress:IpAddress,Status:Status,InstanceId:InstanceId,Bandwidth:Bandwidth,Name:Name}

# List EIPs by status
aliyun vpc DescribeEipAddresses --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" --Status Available

# List EIPs bound to NAT Gateways
aliyun vpc DescribeEipAddresses --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --Output cols=AllocationId,IpAddress rows=EipAddresses.EipAddress[?InstanceType=='Nat' && Status=='InUse'].{AllocationId:AllocationId,IpAddress:IpAddress}
```

## Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action | UX Feedback |
|---------------|-------------|---------|--------------|-------------|
| `InvalidParameter` | 0–1 | — | Fix args; retry once | `[ERROR] InvalidParameter: Check parameters against API spec.` |
| `InvalidAllocationId.NotFound` | 0 | — | HALT | `[ERROR] EIP not found. Check the AllocationId.` |
| `InvalidInstance.Id.NotFound` | 0 | — | HALT | `[ERROR] Target instance not found. Verify InstanceId.` |
| `InvalidEipStatus.AlreadyAssociating` | 0 | — | Wait; retry after 30s | `[ERROR] EIP is being associated. Wait and retry.` |
| `OperationDenied` | 0 | — | HALT | `[ERROR] Operation denied. Check RAM permissions.` |
| `QuotaExceeded.EipAddress` | 0 | — | HALT | `[ERROR] EIP quota reached. Delete unused EIPs or raise quota.` |
| `InsufficientBalance` | 0 | — | HALT | `[ERROR] Insufficient balance. Recharge account.` |
| `Forbidden.RAMUser` | 0 | — | HALT | `[ERROR] RAM user lacks required permissions. Add AliyunVPCFullAccess policy.` |
| `InvalidBandwidth.ValueNotSupported` | 0 | — | HALT | `[ERROR] Invalid bandwidth for current billing mode.` |
| `IncorrectEipStatus` | 0 | — | HALT; check status | `[ERROR] EIP in wrong state for this operation.` |
| `Throttling` / 429 | 3 | exponential | Back off | `⚠️ Rate limit. Retrying in {backoff}s...` |
| `InternalError` / 5xx | 3 | 2s,4s,8s | Retry; then HALT | `[ERROR] InternalError. Retry or escalate.` |

## Prerequisites

见 [执行环境配置](../alicloud-skill-generator/references/execution-environment.md)

**Go SDK:** `github.com/alibabacloud-go/vpc-20160428/v3/client`

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to EIP.

### 安全 (Security)

| Area | Guidance |
|------|----------|
| **IAM** | Require: `vpc:Describe*`, `vpc:AllocateEipAddress`, `vpc:ReleaseEipAddress` scoped to `acs:vpc:*:*:eipaddress/*` |
| **Network Security** | EIP exposes resources to the internet. Verify security group rules are properly configured before binding |
| **Credential Security** | `{{env.*}}` only. Must mask credentials to `****` when outputting to console, logs, or error messages. Never print secrets. |

### 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | EIPs can be rebound to healthy instances for failover. Use health checks + automatic rebind |
| **面向精细的运维管控** | Monitor bandwidth utilization continuously. Alert at 80% |
| **面向风险的应急快恢** | **RTO:** < 1 min for EIP unbind/rebind. **RPO:** N/A |

### 成本 (Cost)

| Billing | Best For | Savings |
|---------|----------|---------|
| PayByBandwidth (按固定带宽) | Stable, high-traffic workloads | Predictable cost |
| PayByTraffic (按实际流量计) | Bursty/variable traffic | Pay per GB |
| Common Bandwidth Package | 2+ EIPs sharing pool | 30-50% savings |

**Waste:** Unattached EIPs (Available for 3d) → release. Idle bandwidth (< 10% usage) → switch to PayByTraffic.

### 效率 (Efficiency)

- **Bandwidth Plans:** Common Bandwidth Package for centralized bandwidth management
- **Auto-Rebind:** EIP can be programmatically rebound for HA failover scenarios
- **CI/CD:** JSON output by default, compatible with pipelines

### 性能 (Performance)

| Metric | CMS Namespace | Scale Up | Scale Down | Window |
|--------|--------------|----------|------------|--------|
| BandwidthTX | `acs_vpc_dashboard` | > 80% capacity | < 30% | 5 min |
| BandwidthRX | `acs_vpc_dashboard` | > 80% capacity | < 30% | 5 min |
| DropTrafficPackageRate | `acs_vpc_dashboard` | > 0 | — | 5 min |

**Key guidance:** One EIP supports up to 5 Gbps. For higher throughput, use multiple EIPs with SLB.

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Prompt Examples](references/prompt-examples.md)
- [Execution Environment Setup](../alicloud-skill-generator/references/execution-environment.md)
- [CLI Behavioral Reference](../alicloud-skill-generator/references/cli-behavior.md)

## Operational Best Practices

- **Billing mode selection:** PayByTraffic for burst/spiky traffic, PayByBandwidth for stable high-usage scenarios.
- **Bandwidth plans:** Use Common Bandwidth Package when 2+ EIPs share the same peak bandwidth — reduces costs by ~30-50%.
- **EIP lifecycle management:** Release unused EIPs to avoid idle charges.
- **Security:** Only associate EIPs with resources that have proper security group rules/NAT configurations.
- **Monitoring:** Track EIP bandwidth utilization; upgrade before reaching limits.


## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `cli-first`，CLI/SDK 已覆盖，无需 code snippets.
