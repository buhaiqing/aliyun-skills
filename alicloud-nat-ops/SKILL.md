---
name: alicloud-nat-ops
description: >-
  Use this skill to manage the full lifecycle of Alibaba Cloud NAT Gateway
  and its SNAT/DNAT/FULLNAT entries — create, describe, modify, delete NAT
  Gateways (Enhanced or VPC type), create/delete SNAT entries for outbound
  internet access, create/delete DNAT entries (ForwardEntry) for inbound
  port mapping, manage FULLNAT for bidirectional NAT. Diagnose NAT connectivity
  issues, quota exceeded, and dependency violations. Reach for this skill when
  the user needs network address translation, reports "SNAT not working", "DNAT
  port mapping failed", "private instances can't access internet", or wants to
  deploy, configure, troubleshoot, or monitor Alibaba Cloud NAT Gateways — even
  if they just say "NAT网关", "SNAT", "DNAT", "地址转换", "端口映射" without
  naming the product explicitly. Keywords: NAT Gateway, 弹性NAT, 增强型NAT,
  SNAT, DNAT, FULLNAT, CreateNatGateway, CreateSnatEntry, CreateForwardEntry,
  DeleteNatGateway. Do NOT use for EIP allocation/management, VPC/vSwitch
  creation, compute (ECS), databases (RDS), load balancing (SLB/ALB),
  containers (ACK), billing/accounting, or RAM-only tasks.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.1.0"
  last_updated: "2026-06-04"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "VPC 2016-04-28 / https://help.aliyun.com/zh/vpc/developer-reference/api-vpc-2016-04-28-overview"
  cli_applicability: cli-first
  cli_support_evidence: "Confirmed via `aliyun help vpc | grep -i nat` — NAT operations (CreateNatGateway, DescribeNatGateways, DeleteNatGateway, CreateSnatEntry, DeleteSnatEntry, CreateForwardEntry, DeleteForwardEntry, etc.) are fully supported by the official aliyun CLI."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud NAT Operations Skill

## Overview

Alibaba Cloud NAT (Network Address Translation) Gateway enables private instances in VPCs to access the internet (SNAT) or be accessed from the internet (DNAT). This skill is an **operational runbook** for agents: explicit scope, credential rules, pre-flight checks, **cli-first execution** (official **`aliyun` CLI** as primary path, **JIT Go SDK** as fallback), response validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: cli-first`:** Official `aliyun` fully supports NAT. CLI is the **primary** execution path for all operations. JIT Go SDK is the **fallback** only when CLI lacks support for a specific edge-case operation.

### Quick Start

不知道从哪里开始？直接看 [Prompt Examples](references/prompt-examples.md)，里面有 30+ 条自然语言提示词示例，覆盖 NAT 网关创建、SNAT/DNAT 配置、NAT 释放、端口映射、故障诊断等场景，复制即用。

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud NAT" OR "NAT网关" OR "SNAT" OR "DNAT" OR "Network Address Translation"
- Task involves CRUD or lifecycle operations on **NAT Gateway** (create, describe, modify, delete)
- Task involves **SNAT entries** (create, describe, delete) for outbound internet access
- Task involves **DNAT entries / ForwardTable** (create, describe, delete) for inbound port mapping
- Task involves **FULLNAT entries** (create, describe, delete) for bidirectional NAT
- Task involves **NAT Gateway billing modification** (PayBySpec ↔ PayByActualUsage)
- Task involves **NAT quota management** (check limits, SNAT/DNAT entry counts)
- Task keywords: NAT, NAT Gateway, SNAT, DNAT, FULLNAT, 弹性NAT, 增强型NAT, 地址转换, 端口映射, CreateNatGateway, CreateSnatEntry, CreateForwardEntry, SNAT表, DNAT表
- User asks to deploy, configure, troubleshoot, or monitor NAT resources **via API, SDK, CLI, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops` (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when present)
- Task is about **EIP allocation/management** → delegate to: `alicloud-eip-ops`
- Task is about **VPC/vSwitch creation** → delegate to: `alicloud-vpc-ops` (when present)
- Task is about **ECS instances** → delegate to: `alicloud-ecs-ops`
- Task is about **RDS / databases** → delegate to: `alicloud-rds-ops` (when present)
- Task is about **SLB / load balancing** → delegate to: `alicloud-slb-ops`

### Delegation Rules

- If creating NAT Gateway, first verify VPC and vSwitch exist via `alicloud-vpc-ops`.
- If NAT Gateway needs EIPs for SNAT/DNAT source IPs, allocate EIPs via `alicloud-eip-ops` first.
- After NAT Gateway is created, use this skill for SNAT/DNAT entry management.
- SNAT/DNAT rules target ECS instances in vSwitches — to verify target resources, use `alicloud-ecs-ops`.

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.nat_gateway_id}}` | User-supplied NAT Gateway ID | Ask once; reuse |
| `{{user.nat_name}}` | User-supplied NAT Gateway name | Ask once; reuse |
| `{{user.vpc_id}}` | User-supplied VPC ID | Ask once; reuse |
| `{{user.vswitch_id}}` | User-supplied VSwitch ID | Ask once; reuse |
| `{{user.snat_table_id}}` | User-supplied SNAT Table ID | Ask once; reuse |
| `{{user.snat_entry_id}}` | User-supplied SNAT Entry ID | Ask once; reuse |
| `{{user.forward_table_id}}` | User-supplied Forward Table ID | Ask once; reuse |
| `{{user.forward_entry_id}}` | User-supplied DNAT Entry ID | Ask once; reuse |
| `{{user.source_cidr}}` | SNAT source CIDR | Ask once; reuse |
| `{{user.eip_id}}` | User-supplied EIP Allocation ID | Ask once; reuse |

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateNatGateway | `$.NatGatewayId` | string | New NAT Gateway ID |
| DescribeNatGateways | `$.NatGateways.NatGateway[].NatGatewayId` | array | NAT Gateway IDs |
| DescribeNatGateways | `$.NatGateways.NatGateway[].Status` | array | Status: Creating/Available/Modifying/Deleting |
| CreateSnatEntry | `$.SnatTableId` | string | SNAT Table ID (gateway-level) |
| DescribeSnatTableEntries | `$.SnatTableEntries.SnatTableEntry[].SnatEntryId` | array | SNAT Entry IDs |
| CreateForwardEntry | `$.ForwardTableId` | string | Forward Table ID (gateway-level) |
| DescribeForwardTableEntries | `$.ForwardTableEntries.ForwardTableEntry[].ForwardEntryId` | array | DNAT Entry IDs |
| DeleteNatGateway | `$.RequestId` | string | Request ID |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateNatGateway | `Creating` | `Available` | 5s | 300s |
| DeleteNatGateway | any | (absent) | 5s | 300s |
| CreateSnatEntry | — | `Available` | 2s | 60s |
| CreateForwardEntry | — | `Available` | 2s | 60s |

## Quick Start

### What This Skill Does

This skill enables you to create, manage, and release Alibaba Cloud NAT Gateways and their SNAT/DNAT entries using the `aliyun` CLI (primary) or JIT Go SDK (fallback).

### Prerequisites

- [ ] `aliyun` CLI installed (or Go runtime for JIT fallback)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`
- [ ] VPC and VSwitch exist (pre-requisites for NAT Gateway)

### Verify Setup

```bash
# Check CLI and credentials
aliyun vpc DescribeNatGateways --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --PageSize 1
```

### Your First Command

```bash
# Example: List all NAT Gateways
aliyun vpc DescribeNatGateways --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --output cols=NatGatewayId,Name,Status,Spec,VpcId rows=NatGateways.NatGateway[].{NatGatewayId:NatGatewayId,Name:Name,Status:Status,Spec:Spec,VpcId:VpcId}
```

### Next Steps

- [Core Concepts](references/core-concepts.md) — Understand NAT Gateway architecture and types
- [Common Operations](#execution-flows) — Create NAT, configure SNAT/DNAT, release
- [Troubleshooting](references/troubleshooting.md) — Fix SNAT/DNAT failures

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| Create NAT Gateway | Create enhanced NAT or VPC NAT gateway | Medium | Low |
| Describe | View NAT Gateway details | Low | None |
| Modify | Change NAT Gateway attributes or billing | Low | Low |
| Delete | Remove NAT Gateway | Low | **High** — irreversible |
| Create SNAT | Create SNAT entry for outbound access | Medium | Low |
| Create DNAT (ForwardEntry) | Create DNAT entry for inbound port mapping | Medium | Medium |
| Create FULLNAT | Create FULLNAT entry for bidirectional NAT | Medium | Low |
| List | View all SNAT/DNAT entries | Low | None |



## Execution Flows (Agent-Readable)

### Operation: Create NAT Gateway

**When to use:**
- You need private ECS instances to access the internet (outbound via SNAT)
- You need to expose private instances via port mapping (inbound via DNAT)
- Enhanced NAT Gateway (recommended) or VPC NAT gateway

**What you need:**
- VPC ID
- VSwitch ID (must be in the same VPC — Required for Enhanced NAT)
- NAT type: `Enhanced` (recommended) or `Normal`
- Billing method: `PayBySpec` (fixed spec) or `PayByActualUsage` (usage-based)

**What to expect:**
- NAT Gateway provisioning takes ~1-2 minutes
- Enters `Available` state when ready

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI availability | `aliyun vpc DescribeRegions` | Exit code 0 | HALT; install CLI |
| VPC exists | `aliyun vpc DescribeVpcs --VpcId {{user.vpc_id}}` | VPC found, Status=Available | HALT; create VPC |
| VSwitch exists | `aliyun vpc DescribeVSwitches --VSwitchId {{user.vswitch_id}}` | VSwitch found, Status=Available | HALT; create VSwitch |
| VSwitch in VPC | VSwitch.VpcId == VpcId | Match | HALT; use correct VSwitch |
| NAT quota | DescribeNatGateways + TotalCount | Under NAT Gateway quota | HALT; request quota increase |

#### Execution — CLI

```bash
# Create Enhanced NAT Gateway
aliyun vpc CreateNatGateway \
  --RegionId "{{user.region}}" \
  --VpcId "{{user.vpc_id}}" \
  --NatType "Enhanced" \
  --VSwitchId "{{user.vswitch_id}}" \
  --Name "{{user.nat_name}}" \
  --BillingMethod "PayBySpec"
```

#### Post-execution Validation

1. Capture `{{output.nat_gateway_id}}` from response `$.NatGatewayId`.
2. Poll until `Available`:

```bash
aliyun vpc DescribeNatGateways \
  --RegionId "{{user.region}}" \
  --NatGatewayId "{{output.nat_gateway_id}}" \
  --waiter expr='NatGateways.NatGateway[0].Status' to=Available timeout=300 interval=5
```

### Operation: Create SNAT Entry

**When to use:**
- You need instances in a vSwitch/CIDR to access the internet via NAT
- You want to use specific EIPs as the SNAT source IP

**What you need:**
- NAT Gateway ID (must be `Available`)
- EIP Allocation ID for SNAT source
- Source CIDR or vSwitch ID

**What to expect:**
- SNAT entry created within seconds
- Instances in source range can now reach internet via the EIP

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| NAT Gateway Available | DescribeNatGateways | Status=`Available` | HALT; wait for NAT creation |
| EIP exists and Available | `aliyun vpc DescribeEipAddresses --AllocationId {{user.eip_id}}` | Status=Available or InUse on same NAT | Verify/allocate EIP via `alicloud-eip-ops` |
| Source CIDR is valid | Validate CIDR format | Valid subnet CIDR | Fix CIDR format |

#### Execution

```bash
# Create SNAT entry for a CIDR
aliyun vpc CreateSnatEntry \
  --RegionId "{{user.region}}" \
  --NatGatewayId "{{user.nat_gateway_id}}" \
  --SnatIp "{{user.eip_address}}" \
  --SourceCIDR "{{user.source_cidr}}" \
  --SnatEntryName "{{user.snat_entry_name}}"
```

#### Post-execution Validation

```bash
aliyun vpc DescribeSnatTableEntries \
  --RegionId "{{user.region}}" \
  --NatGatewayId "{{user.nat_gateway_id}}"
```

### Operation: Create DNAT Entry (Forward Entry)

**When to use:**
- You need to expose a private port to the internet (e.g., port 80, 443, SSH)
- You want to map an external port on an EIP to an internal port on an ECS

**What you need:**
- NAT Gateway ID (Available)
- EIP address for external IP
- Internal IP (private ECS IP)
- Protocol (TCP/UDP/Any)
- External port and Internal port

**What to expect:**
- DNAT entry created within seconds
- External traffic to EIP:port is forwarded to internal_ip:internal_port

#### Execution

```bash
# Create DNAT entry (TCP port mapping)
aliyun vpc CreateForwardEntry \
  --RegionId "{{user.region}}" \
  --NatGatewayId "{{user.nat_gateway_id}}" \
  --IpProtocol "TCP" \
  --ExternalIp "{{user.external_ip}}" \
  --ExternalPort "{{user.external_port}}" \
  --InternalIp "{{user.internal_ip}}" \
  --InternalPort "{{user.internal_port}}" \
  --ForwardEntryName "{{user.forward_entry_name}}"
```

#### Post-execution Validation

```bash
aliyun vpc DescribeForwardTableEntries \
  --RegionId "{{user.region}}" \
  --NatGatewayId "{{user.nat_gateway_id}}"
```

### Operation: Delete NAT Gateway

#### Pre-flight (Safety Gate)

- **MUST** delete ALL SNAT entries first.
- **MUST** delete ALL DNAT entries first.
- **MUST** unbind ALL associated EIPs first.
- **MUST** obtain explicit confirmation: irreversible delete.
- Check dependencies:

```bash
# Check SNAT entries
aliyun vpc DescribeSnatTableEntries --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}
# Check DNAT entries
aliyun vpc DescribeForwardTableEntries --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}
```

#### Execution

```bash
aliyun vpc DeleteNatGateway \
  --RegionId "{{user.region}}" \
  --NatGatewayId "{{user.nat_gateway_id}}"
```

### Operation: List Resources

```bash
# List all NAT Gateways
aliyun vpc DescribeNatGateways --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=NatGatewayId,Name,Status,Spec,VpcId rows=NatGateways.NatGateway[].{NatGatewayId:NatGatewayId,Name:Name,Status:Status,Spec:Spec,VpcId:VpcId}

# List SNAT entries for a NAT Gateway
aliyun vpc DescribeSnatTableEntries --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" --NatGatewayId "{{user.nat_gateway_id}}" \
  --output cols=SnatEntryId,SnatIp,SourceCIDR rows=SnatTableEntries.SnatTableEntry[].{SnatEntryId:SnatEntryId,SnatIp:SnatIp,SourceCIDR:SourceCIDR}

# List DNAT entries for a NAT Gateway
aliyun vpc DescribeForwardTableEntries --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" --NatGatewayId "{{user.nat_gateway_id}}" \
  --output cols=ForwardEntryId,IpProtocol,ExternalIp:ExternalPort rows=ForwardTableEntries.ForwardTableEntry[].{ForwardEntryId:ForwardEntryId,IpProtocol:IpProtocol,ExternalIpIpPort:ExternalIp":"ExternalPort}
```

## Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action | UX Feedback |
|---------------|-------------|---------|--------------|-------------|
| `InvalidParameter` | 0–1 | — | Fix args; retry once | `[ERROR] InvalidParameter. Check parameters against API spec.` |
| `InvalidVpcId.NotFound` | 0 | — | HALT | `[ERROR] VPC not found. Verify VpcId.` |
| `InvalidVSwitchId.NotFound` | 0 | — | HALT | `[ERROR] VSwitch not found. Verify VSwitchId.` |
| `QuotaExceeded.NatGateway` | 0 | — | HALT | `[ERROR] NAT Gateway quota reached. Delete unused or request increase.` |
| `QuotaExceeded.SnatEntry` | 0 | — | HALT | `[ERROR] SNAT entry quota reached (200 per NAT Gateway). Delete unused entries.` |
| `DependencyViolation.SnatEntryExists` | 0 | — | HALT | `[ERROR] Delete all SNAT entries before deleting NAT Gateway.` |
| `DependencyViolation.ForwardEntryExists` | 0 | — | HALT | `[ERROR] Delete all DNAT entries before deleting NAT Gateway.` |
| `InvalidEipStatus.InUseByOtherNat` | 0 | — | HALT | `[ERROR] EIP is bound to another NAT Gateway. Unbind first.` |
| `InsufficientBalance` | 0 | — | HALT | `[ERROR] Insufficient balance. Recharge account.` |
| `Forbidden.RAMUser` | 0 | — | HALT | `[ERROR] RAM user lacks permissions. Add AliyunNATFullAccess policy.` |
| `Throttling` / 429 | 3 | exponential | Back off | `⚠️ Rate limit. Retrying in {backoff}s...` |
| `InternalError` / 5xx | 3 | 2s,4s,8s | Retry; then HALT | `[ERROR] InternalError. Retry or escalate.` |

## Prerequisites

见 [执行环境配置](../alicloud-skill-generator/references/execution-environment.md)

**Go SDK:** `github.com/alibabacloud-go/vpc-20160428/v3/client`

---

## Advanced Analytics

以下深度分析文档仅在用户明确需要时加载，**不要在常规操作中读取**：

| 场景 | 文档 |
|------|------|
| 成本优化、资源分析 | [advanced/finops-optimization.md](references/advanced/finops-optimization.md) |

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to NAT Gateway.

### 安全 (Security)

| Area | Guidance | Detail Reference |
|------|----------|-----------------|
| **IAM (最小权限)** | Require scoped RAM policies; NEVER use `AliyunNATFullAccess` in production | [Security Enhancement §1](references/security-enhancement.md#1-ram-policy-templates-least-privilege) |
| **DNAT Exposure Audit** | Audit DNAT entries for high-risk ports (22/3306/6379/3389/27017) | [Security Enhancement §2](references/security-enhancement.md#2-dnat-exposure-audit) |
| **SNAT Scope Audit** | SNAT source CIDR must NOT be 0.0.0.0/0 | [Security Enhancement §3](references/security-enhancement.md#3-snat-security-assessment) |
| **Network Security** | DNAT bypasses security groups; add explicit inbound rules on target ECS | [Security Enhancement §4](references/security-enhancement.md#4-network-security-hardening) |
| **Credential Security** | `{{env.*}}` only. Must mask credentials to `****` (first 4 chars + `****`) when outputting to console, logs, or error messages. Never print secrets. STS preferred for automation | [Security Enhancement §5](references/security-enhancement.md#5-credential-security) |
| **Audit Trail** | Delegate to `alicloud-actiontrail-ops` for NAT operation audit | [Security Enhancement §6](references/security-enhancement.md#6-audit--compliance) |
| **Incident Response** | 5-phase runbook: Detect → Contain → Investigate → Recover → Post-Incident | [Security Enhancement §7](references/security-enhancement.md#7-security-incident-response) |

**Security P0 Checklist:**
- [ ] No high-risk ports (22/3306/6379/3389/27017) exposed via DNAT
- [ ] RAM policy scoped to NAT Gateway operations only (not `*`)
- [ ] Credential masking enforced (never print `ALIBABA_CLOUD_ACCESS_KEY_SECRET`)
- [ ] SNAT source CIDR is not 0.0.0.0/0
- [ ] DNAT entries have corresponding security group rules on target ECS

### 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | Enhanced NAT Gateway is AZ-scoped. Deploy in multiple vSwitches across AZs for HA |
| **面向精细的运维管控** | Monitor NAT CU utilization. Upgrade spec if CU exceeds 80% consistently |
| **面向风险的应急快恢** | **RTO:** < 5 min for EIP unbind/rebind. **RPO:** N/A (stateless) |

### 成本 (Cost)

| Area | Guidance | Detail Reference |
|------|----------|-----------------|
| **Billing Mode Decision** | PayBySpec for steady traffic (> 60% CU); PayByActualUsage for bursty/low traffic | [FinOps Optimization §2](references/advanced/finops-optimization.md#2-billing-mode-decision-tree) |
| **Idle Resource Detection** | NAT with 0 SNAT + 0 DNAT for 7d = idle → delete. Orphaned EIPs → release | [FinOps Optimization §3](references/advanced/finops-optimization.md#3-idle-resource-detection) |
| **Right-Sizing** | Match spec to workload: Small (< 1K CU) → Medium (5K CU) → Large (10K CU) → XLarge (50K CU) | [FinOps Optimization §4](references/advanced/finops-optimization.md#4-right-sizing-guide) |
| **EIP Cost Optimization** | Common Bandwidth Package for 3+ EIPs saves 20-42%. Match billing mode to traffic pattern | [FinOps Optimization §5](references/advanced/finops-optimization.md#5-eip-cost-optimization) |
| **Cost Anomaly Detection** | NAT cost spike > 30% MoM, EIP count growing, bandwidth over-provisioned | [FinOps Optimization §6](references/advanced/finops-optimization.md#6-finops-inspection-workflow) |

**Cost P0 Checklist:**
- [ ] No idle NAT Gateways (0 SNAT + 0 DNAT for 7d)
- [ ] No orphaned EIPs (allocated but not associated for 7d)
- [ ] Billing mode matches traffic pattern (PayBySpec vs PayByActualUsage)
- [ ] NAT spec matches actual CU utilization (not over-provisioned)
- [ ] Multi-EIP NATs use Common Bandwidth Package (3+ EIPs)

**Quick Cost Reference:**

| Billing | Best For | Notes |
|---------|----------|-------|
| Enhanced NAT + PayBySpec | Steady workloads (> 60% CU) | Fixed hourly rate, predictable |
| Enhanced NAT + PayByActualUsage | Bursty/low traffic (< 30% CU) | Pay per CU, lower base cost |
| CBWP + multiple EIPs | 3+ EIPs on NAT | Saves 20-42% vs individual EIP bandwidth |

**Waste:** Idle NAT Gateways (no SNAT/DNAT rules for 7d) → delete. Underutilized specs → downgrade. Common Bandwidth Package for multiple EIPs saves up to 40%.

### 效率 (Efficiency)

- **Enhanced NAT preferred:** Better performance, more SNAT IPs, vSwitch-level SNAT
- **EIP Integration:** Coordinate with `alicloud-eip-ops` for EIP lifecycle management
- **CI/CD:** JSON output by default, compatible with pipelines

### 性能 (Performance)

| Metric | CMS Namespace | Scale Up | Scale Down |
|--------|--------------|----------|------------|
| NAT CU | `acs_nat_dashboard` | > 80% | < 40% |
| Bandwidth Usage | `acs_nat_dashboard` | > 80% | < 40% |
| SNAT Connection | `acs_nat_dashboard` | > 80% | < 50% |

**Key guidance:** One EIP ≈ 30K concurrent connections. Scale by adding multiple EIPs to SNAT pool. Enhanced NAT supports large-scale SNAT connections.

### 敏感级系统 (Sensitivity-Aware Operations)

NAT Gateway operations MUST be differentiated by system sensitivity level. Sensitive systems require stricter change controls, approval gates, and rollback plans.

| Sensitivity Level | Name | Change Control | Rollback | Detail Reference |
|-------------------|------|---------------|----------|-----------------|
| **L0** | 核心生产 | CAB Approval + Change Window | Mandatory snapshot + rollback plan | [Sensitivity-Aware §2-4](references/sensitivity-aware-operations.md#2-change-control-by-sensitivity-level) |
| **L1** | 生产 | Change Window + Notify | Snapshot recommended | [Sensitivity-Aware §2-4](references/sensitivity-aware-operations.md#2-change-control-by-sensitivity-level) |
| **L2** | 预发 | Notify team | Best effort | [Sensitivity-Aware §2](references/sensitivity-aware-operations.md#2-change-control-by-sensitivity-level) |
| **L3** | 开发/测试 | Auto | N/A | [Sensitivity-Aware §2](references/sensitivity-aware-operations.md#2-change-control-by-sensitivity-level) |

**L0/L1 关键规则:** 详见 [Sensitivity-Aware Operations](references/sensitivity-aware-operations.md) — 含变更窗口、配置快照、回滚计划、删除审批等要求

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Prompt Examples](references/prompt-examples.md)
- [FinOps Optimization](references/advanced/finops-optimization.md)
- [Security Enhancement](references/security-enhancement.md)
- [Sensitivity-Aware Operations](references/sensitivity-aware-operations.md)
- [Execution Environment Setup](../alicloud-skill-generator/references/execution-environment.md)
- [CLI Behavioral Reference](../alicloud-skill-generator/references/cli-behavior.md)

## Operational Best Practices

- **Enhanced NAT preferred:** Enhanced NAT Gateway offers better performance, more SNAT IPs, and supports vSwitch-level SNAT.
- **SNAT design:** Use SNAT for whole vSwitch (vSwitch-level SNAT) or fine-grained CIDR. One EIP = ~30K concurrent connections. Scale by adding multiple EIPs.
- **DNAT security:** Expose only needed ports. Don't open all TCP/UDP ports to the internet.
- **EIP management:** Allocate EIPs via `alicloud-eip-ops` before configuring SNAT/DNAT. Add EIPs to Common Bandwidth Plans for cost savings.
- **Monitoring:** Track NAT Gateway CU utilization and bandwidth. Upgrade spec if CU exceeds 80%.
- **Multi-AZ HA:** Enhanced NAT Gateway is AZ-scoped. For HA, deploy in multiple vSwitches across AZs.

---

## Quality Gate (GCL)

Eighth rollout of GCL per [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 1, eighth skill) |
| `max_iter` | 2 |
| Most-scrutinized | `DeleteNatGateway` (3-step cascade: SNAT + DNAT + EIP) |
| CIDR / port conflict | `Create SNAT` (no SourceCIDR overlap); `Create DNAT` (no 5-tuple conflict) |
| Production NAT | Deletion requires `maintenance_window_confirmed` |

### Changelog
1.0.0 | 2026-06-04 | Eighth rollout.

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `cli-first`，CLI/SDK 已覆盖，无需 code snippets.
