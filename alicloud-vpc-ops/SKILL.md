---
name: alicloud-vpc-ops
description: >-
  Use this skill to manage the full lifecycle of Alibaba Cloud VPC (Virtual
  Private Cloud) networking resources — create, describe, modify, delete VPCs,
  vSwitches, route tables, NAT gateways, EIPs, SNAT/DNAT entries, IPv6 gateways,
  VPN gateways, IPsec servers, customer gateways, network ACLs, DHCP options
  sets, and flow logs. Diagnose connectivity issues. Reach for this skill when
  the user needs network provisioning, reports "can't reach intranet", "EIP
  binding failed", "NAT gateway quota exceeded", "VPN tunnel down", or wants to
  deploy, configure, troubleshoot, or monitor Alibaba Cloud networking resources
  — even if they just say "专有网络", "VPC", "虚拟交换机", "弹性公网IP",
  "NAT网关", "VPN网关" without naming VPC explicitly. Keywords: VPC, vSwitch,
  RouteTable, NAT, EIP, SNAT, DNAT, VPN, IPsec, NetworkACL, DHCP, FlowLog,
  专有网络, 虚拟交换机, 弹性公网IP, NAT网关, VPN网关. Do NOT use for compute
  (ECS), databases (RDS/Redis), load balancing (SLB/ALB), containers (ACK),
  billing/accounting, or RAM-only tasks.
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
  cli_support_evidence: "Confirmed via `aliyun help vpc` — VPC (Virtual Private Cloud) API 2016-04-28 is fully supported by the official aliyun CLI. All core operations (VPC, vSwitch, NAT, EIP, RouteTable, VPN, NetworkACL) have matching CLI commands."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud VPC Operations Skill

## Overview

Alibaba Cloud VPC (Virtual Private Cloud) provides isolated network environments for cloud resources. This skill is an **operational runbook** for agents: explicit scope, credential rules, pre-flight checks, **cli-first execution** (official **`aliyun` CLI** as primary path, **JIT Go SDK** as fallback), response validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: cli-first`:** Official `aliyun` fully supports VPC. CLI is the **primary** execution path for all operations. JIT Go SDK is the **fallback** only when CLI lacks support for a specific edge-case operation.

### Quick Start

不知道从哪里开始？直接看 [Prompt Examples](references/prompt-examples.md)，里面有 30+ 条自然语言提示词示例，覆盖 VPC 创建、交换机管理、NAT 网关、弹性公网 IP、VPN 配置等场景，复制即用。

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud VPC" OR "专有网络" OR "Virtual Private Cloud" OR "VSwitch" OR "虚拟交换机"
- Task involves CRUD or lifecycle operations on **VPC** (create, describe, modify, delete, list)
- Task involves **vSwitch** (create, describe, modify, delete)
- Task involves **RouteTable** (describe, create, delete, associate, unassociate)
- Task involves **NAT Gateway** (create, describe, modify, delete)
- Task involves **EIP** (allocate, describe, release, associate, unassociate, modify)
- Task involves **SNAT/DNAT entries** (create, describe, delete)
- Task involves **VPN Gateway / IPsec** (create, describe, delete, configure IPsec server)
- Task involves **Customer Gateway** (create, describe, modify, delete)
- Task involves **Network ACL** (create, describe, delete, associate, unassociate, copy entries)
- Task involves **DHCP Options Set** (create, describe, associate to VPC, delete)
- Task involves **FlowLog** (create, activate, deactivate, describe, delete)
- Task involves **IPv6 Gateway/Egress** (create IPv6 gateway, describe, create egress-only rules)
- Task involves **HaVip** (create, describe, delete, associate, unassociate)
- Task involves **Common Bandwidth Package** (create, describe, add/remove EIPs)
- Task involves **BGP** (create BGP group/peer, describe, add/delete BGP network)
- Task keywords: VPC, 专有网络, 交换机, vSwitch, 路由表, route table, NAT网关, 弹性公网IP, EIP, SNAT, DNAT, VPN网关, IPsec, 网络ACL, DHCP, FlowLog, IPv6, HaVip, 共享带宽, BGP
- User asks to deploy, configure, troubleshoot, or monitor VPC resources **via API, SDK, CLI, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops` (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when present)
- Task is about **ECS instances / compute** → delegate to: `alicloud-ecs-ops`
- Task is about **RDS / databases** → delegate to: `alicloud-rds-ops` (when present)
- Task is about **Redis / caching** → delegate to: `alicloud-redis-ops`
- Task is about **SLB / load balancing** → delegate to: `alicloud-slb-ops`
- Task is about **ACK / containers** → delegate to: `alicloud-ack-ops`
- User insists on **console-only** flows with no API → state limitation; do not invent undocumented HTTP steps

### Delegation Rules

- If creating an ECS instance in a VPC, use `alicloud-ecs-ops` but first verify VPC and VSwitch exist using this skill.
- If attaching an EIP to an SLB, use `alicloud-slb-ops` but first verify EIP exists using this skill.
- If attaching an EIP to an ECS, use `alicloud-ecs-ops` but first verify EIP exists using this skill.
- Multi-product requests: handle each product with its skill; do not merge unrelated APIs into one ambiguous flow.

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.vpc_id}}` | User-supplied VPC ID | Ask once; reuse |
| `{{user.vpc_name}}` | User-supplied VPC name | Ask once; reuse |
| `{{user.vswitch_id}}` | User-supplied VSwitch ID | Ask once; reuse |
| `{{user.nat_gateway_id}}` | User-supplied NAT Gateway ID | Ask once; reuse |
| `{{user.eip_id}}` | User-supplied EIP ID | Ask once; reuse |
| `{{user.route_table_id}}` | User-supplied RouteTable ID | Ask once; reuse |
| `{{user.cidr_block}}` | User-supplied CIDR block | Ask once; reuse |
| `{{user.zone_id}}` | User-supplied zone ID | Ask once; reuse |
| `{{user.vpn_gateway_id}}` | User-supplied VPN Gateway ID | Ask once; reuse |
| `{{user.network_acl_id}}` | User-supplied Network ACL ID | Ask once; reuse |
| `{{output.resource_id}}` | From last API or CLI JSON response | Parse per verified CLI path for this operation |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field value (including `ALIBABA_CLOUD_ACCESS_KEY_ID`) in console output, debug messages, error messages, or logs. If credential information must be displayed for debugging or troubleshooting purposes, use the masking format: show only the first 4 characters followed by `****` (e.g., `abcd****`). This masking rule applies to ALL output channels: stdout, stderr, log files, debug traces, error messages, and diagnostic reports.

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** VPC APIs uses `ClientToken` for idempotent operations.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateVpc | `$.VpcId` | string | New VPC ID |
| DescribeVpcs | `$.Vpcs.Vpc[].VpcId` | array | VPC IDs list |
| CreateVSwitch | `$.VSwitchId` | string | New VSwitch ID |
| DescribeVSwitches | `$.VSwitches.VSwitch[].VSwitchId` | array | VSwitch IDs list |
| CreateNatGateway | `$.NatGatewayId` | string | New NAT Gateway ID |
| DescribeNatGateways | `$.NatGateways.NatGateway[].NatGatewayId` | array | NAT Gateway IDs |
| AllocateEipAddress | `$.AllocationId` | string | New EIP Allocation ID |
| DescribeEipAddresses | `$.EipAddresses.EipAddress[].AllocationId` | array | EIP Allocation IDs |
| CreateVpnGateway | `$.VpnGatewayId` | string | New VPN Gateway ID |
| DescribeVpnGateways | `$.VpnGateways.VpnGateway[].VpnGatewayId` | array | VPN Gateway IDs |
| CreateNetworkAcl | `$.NetworkAclId` | string | New Network ACL ID |
| DescribeNetworkAcls | `$.NetworkAcls.NetworkAcl[].NetworkAclId` | array | Network ACL IDs |
| CreateFlowLog | `$.FlowLogId` | string | New FlowLog ID |
| DescribeFlowLogs | `$.FlowLogs.FlowLog[].FlowLogId` | array | FlowLog IDs |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateVpc | — | `Available` | 5s | 300s |
| CreateVSwitch | — | `Available` | 5s | 300s |
| CreateNatGateway | `Creating` | `Available` | 5s | 300s |
| AllocateEipAddress | — | `Available` | 5s | 120s |
| AssociateEipAddress | `Associating` | `Associating` → bound | 5s | 120s |
| DeleteVpc | any stable state | absent | 5s | 300s |
| DeleteNatGateway | any stable state | absent | 5s | 300s |

## Quick Start

### What This Skill Does

This skill enables you to deploy, configure, troubleshoot, and monitor Alibaba Cloud VPC networking resources (VPC, vSwitch, NAT, EIP, RouteTable, VPN, NetworkACL, FlowLog, etc.) using the `aliyun` CLI (primary) or JIT Go SDK (fallback).

### Prerequisites

- [ ] `aliyun` CLI installed (or Go runtime for JIT fallback)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`

### Verify Setup

```bash
# Check CLI and credentials
aliyun vpc DescribeRegions
```

### Your First Command

```bash
# Example: List VPCs
aliyun vpc DescribeVpcs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}
```

### Next Steps

- [Core Concepts](references/core-concepts.md) — Understand VPC architecture
- [Common Operations](#execution-flows) — Create, manage, and delete networking resources
- [Troubleshooting](references/troubleshooting.md) — Fix common issues

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| Create VPC | Create a new VPC with CIDR block | Medium | Low |
| Create VSwitch | Create a vSwitch in a VPC | Medium | Low |
| Create NAT Gateway | Create enhanced NAT gateway or VPC NAT | Medium | Medium |
| Allocate EIP | Request elastic IP address | Low | Low |
| Create RouteTable | Create custom route table | Low | Low |
| Create VPN Gateway | Create VPN gateway for site-to-site | Medium | Medium |
| Create NetworkACL | Create network ACL for traffic control | Medium | Low |
| Describe | View resource details | Low | None |
| Modify | Change resource configuration | Medium | Medium |
| Delete | Remove a resource | Low | **High** — irreversible |
| List | View all resources | Low | None |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-16 | Initial VPC skill generation — VPC, vSwitch, NAT, EIP, RouteTable, VPN, NetworkACL, FlowLog, DHCP, HaVip, BGP |

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers and delegation rules |
| 2 | **Structured I/O** | Placeholder conventions (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) with type and source documented |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute → Validate → Recover, with numbered imperative steps |
| 4 | **Complete Failure Strategies** | Error taxonomy table with ≥ 12 VPC-specific codes; HALT vs retry per error type |
| 5 | **Absolute Single Responsibility** | One product (VPC), one primary resource model; cross-product delegation to other skills |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute → Validate → Recover**. Do not skip phases.

**Preference hint:** CLI is preferred for coverage and simplicity; Go SDK is used for operations CLI does not expose.

### Operation: Create VPC

**When to use:**
- You need a new isolated network environment for your cloud resources
- You want to define custom CIDR blocks (e.g., `172.16.0.0/12`, `192.168.0.0/16`, `10.0.0.0/8`)

**What you need:**
- Region ID
- VPC name (optional, will be auto-generated)
- IPv4 CIDR block (optional, defaults to `172.16.0.0/12`)

**What to expect:**
- A new VPC will be created and enter `Available` state
- Creation typically takes several seconds
- You will receive a VPC ID for downstream operations (vSwitch, NAT Gateway, etc.)

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI availability | `aliyun vpc DescribeRegions` | Exit code 0 | HALT; install CLI |
| Credentials | Environment variables set | Non-empty keys | HALT; configure credentials |
| Region validity | DescribeRegions response | Region present in response | Suggest valid regions |
| CIDR overlap | Review existing VPCs CIDRs | No overlapping CIDRs in same region | Suggest non-overlapping CIDR |
| Quota | DescribeVpcs + check TotalCount | Under VPC quota limit | HALT; user raises quota |

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
# Create VPC (JSON output by default)
aliyun vpc CreateVpc \
  --RegionId "{{user.region}}" \
  --VpcName "{{user.vpc_name}}" \
  --CidrBlock "{{user.cidr_block}}" \
  --Description "Created via alicloud-vpc-ops skill"
```

#### Post-execution Validation

1. Capture `{{output.vpc_id}}` from response `$.VpcId`.
2. Verify VPC is `Available`:

```bash
aliyun vpc DescribeVpcs \
  --RegionId "{{user.region}}" \
  --VpcId "{{output.vpc_id}}" \
  --output cols=VpcId,Status,CidrBlock rows=Vpcs.Vpc[].{VpcId:VpcId,Status:Status,CidrBlock:CidrBlock}
```

3. On success, report VPC ID, CIDR, and status to the user.
4. On terminal failure, go to **Failure Recovery**.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action | UX Feedback |
|---------------|-------------|---------|--------------|-------------|
| `InvalidCidrBlock` | 0 | — | HALT; suggest valid CIDR | `[ERROR] InvalidCidrBlock: The CIDR block is invalid. How to fix: Use one of 10.0.0.0/8, 172.16.0.0/12, or 192.168.0.0/16.` |
| `ResourceAlreadyExists` | 0 | — | Ask reuse vs new | `[ERROR] ResourceAlreadyExists: A VPC with this configuration already exists.` |
| `QuotaExceeded.Vpc` | 0 | — | HALT | `[ERROR] QuotaExceeded: VPC quota limit reached. How to fix: Delete unused VPCs or request quota increase.` |
| `DependencyViolation.HasRouteTable` | 0 | — | HALT | `[ERROR] DependencyViolation: VPC still has associated vSwitches/route tables. Delete them first.` |
| `Throttling` | 3 | exponential | Back off | `⚠️ Rate limit reached. Retrying in {backoff}s...` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT | `[ERROR] InternalError: Server-side error. Retry or escalate with RequestId.` |

### Operation: Create VSwitch

**When to use:**
- You need a subnet within a VPC to deploy ECS, RDS, or other resources
- You need resources in a specific availability zone

**What you need:**
- VPC ID
- Zone ID
- VSwitch name (optional)
- VSwitch CIDR (must be a subset of the VPC CIDR)

**What to expect:**
- A new vSwitch will be created within the VPC
- Creation typically takes several seconds

#### Execution

```bash
# Create VSwitch
aliyun vpc CreateVSwitch \
  --RegionId "{{user.region}}" \
  --VpcId "{{user.vpc_id}}" \
  --ZoneId "{{user.zone_id}}" \
  --VSwitchName "{{user.vswitch_name}}" \
  --CidrBlock "{{user.vswitch_cidr}}"
```

#### Post-execution Validation

1. Capture `{{output.vswitch_id}}` from response `$.VSwitchId`.
2. Verify:

```bash
aliyun vpc DescribeVSwitches \
  --RegionId "{{user.region}}" \
  --VSwitchId "{{output.vswitch_id}}" \
  --output cols=VSwitchId,Status,ZoneId,CidrBlock rows=VSwitches.VSwitch[].{VSwitchId:VSwitchId,Status:Status,ZoneId:ZoneId,CidrBlock:CidrBlock}
```

### Operation: Create NAT Gateway

**When to use:**
- You need instances without public IPs to access the internet (SNAT)
- You need to expose private instances to the internet via DNAT
- Enhanced NAT Gateway (recommended) or VPC NAT Gateway

**What you need:**
- VPC ID
- VSwitch ID (must be in the same VPC)
- NAT type (Enhanced / Normal)
- Billing method (PayBySpec / PayByActualUsage)

**What to expect:**
- NAT Gateway enters `Available` state after ~1-2 minutes

#### Execution

```bash
# Create Enhanced NAT Gateway
aliyun vpc CreateNatGateway \
  --RegionId "{{user.region}}" \
  --VpcId "{{user.vpc_id}}" \
  --NatType "Enhanced" \
  --VSwitchId "{{user.vswitch_id}}" \
  --Name "{{user.nat_name}}" \
  --BillingMethod "PayBySpec" \
  --NatGatewayChargeType "PayBySpec"
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

### Operation: Allocate EIP

**When to use:**
- You need a public IP address to bind to ECS, NAT Gateway, SLB, etc.
- You want independent IP lifecycle from compute instances

**What you need:**
- Region ID
- Bandwidth value (Mbps)
- ISP type (BGP / China Telecom / etc.)

**What to expect:**
- EIP allocated and available within seconds

#### Execution

```bash
# Allocate EIP
aliyun vpc AllocateEipAddress \
  --RegionId "{{user.region}}" \
  --Bandwidth "{{user.bandwidth}}" \
  --ISP "{{user.isp}}" \
  --Name "{{user.eip_name}}"
```

#### Post-execution Validation

1. Capture `{{output.eip_allocation_id}}` from response `$.AllocationId`.
2. Verify:

```bash
aliyun vpc DescribeEipAddresses \
  --RegionId "{{user.region}}" \
  --AllocationId "{{output.eip_allocation_id}}" \
  --output cols=AllocationId,Status,IpAddress rows=EipAddresses.EipAddress[].{AllocationId:AllocationId,Status:Status,IpAddress:IpAddress}
```

### Operation: AssociateEipAddress

#### Execution

```bash
# Bind EIP to a resource (ECS, NAT Gateway, SLB, etc.)
aliyun vpc AssociateEipAddress \
  --RegionId "{{user.region}}" \
  --AllocationId "{{user.eip_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --InstanceType "{{user.instance_type}}"
```

Available `InstanceType` values: `EcsInstance`, `Nat`, `SLBInstance`, `HaVip`, `NetworkInterface`, `Ngw`

#### Post-execution Validation

```bash
aliyun vpc DescribeEipAddresses \
  --RegionId "{{user.region}}" \
  --AllocationId "{{user.eip_id}}"
```

Verify `Status` transitions to `InUse` and `InstanceId` matches.

### Operation: Create SNAT Entry

#### Execution

```bash
# Create SNAT entry for VPC NAT Gateway
aliyun vpc CreateSnatEntry \
  --RegionId "{{user.region}}" \
  --NatGatewayId "{{user.nat_gateway_id}}" \
  --SourceCIDR "{{user.source_cidr}}" \
  --SnatTableId "{{user.snat_table_id}}" \
  --SnatEntryName "{{user.snat_entry_name}}"
```

### Operation: Create DNAT Entry (Forward Entry)

#### Execution

```bash
# Create DNAT entry for public access to private instance
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

### Operation: Describe VPC

#### Execution

```bash
# Describe specific VPC
aliyun vpc DescribeVpcs \
  --RegionId "{{user.region}}" \
  --VpcId "{{user.vpc_id}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| VPC ID | `$.Vpcs.Vpc[].VpcId` | Plain text |
| VPC Name | `$.Vpcs.Vpc[].VpcName` | Plain text |
| Status | `$.Vpcs.Vpc[].Status` | Human-readable state |
| CIDR Block | `$.Vpcs.Vpc[].CidrBlock` | IPv4 CIDR |
| IPv6 CIDR | `$.Vpcs.Vpc[].Ipv6CidrBlock` | If reserved |
| Created Time | `$.Vpcs.Vpc[].CreationTime` | ISO 8601 |
| Is Default | `$.Vpcs.Vpc[].IsDefault` | true/false |

### Operation: List Resources

```bash
# List all VPCs
aliyun vpc DescribeVpcs --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=VpcId,VpcName,Status,CidrBlock rows=Vpcs.Vpc[].{VpcId:VpcId,VpcName:VpcName,Status:Status,CidrBlock:CidrBlock}

# List all EIPs
aliyun vpc DescribeEipAddresses --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=AllocationId,IpAddress,Status,InstanceId rows=EipAddresses.EipAddress[].{AllocationId:AllocationId,IpAddress:IpAddress,Status:Status,InstanceId:InstanceId}

# List all NAT Gateways
aliyun vpc DescribeNatGateways --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=NatGatewayId,Name,Status,VpcId rows=NatGateways.NatGateway[].{NatGatewayId:NatGatewayId,Name:Name,Status:Status,VpcId:VpcId}

# List all VSwitches in a VPC
aliyun vpc DescribeVSwitches --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" --VpcId "{{user.vpc_id}}" \
  --output cols=VSwitchId,VSwitchName,Status,ZoneId,CidrBlock rows=VSwitches.VSwitch[].{VSwitchId:VSwitchId,VSwitchName:VSwitchName,Status:Status,ZoneId:ZoneId,CidrBlock:CidrBlock}
```

### Operation: Delete VPC

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of `{{user.vpc_name}}` (`{{user.vpc_id}}`).
- **MUST NOT** proceed unless VPC has **no** associated vSwitches, NAT Gateways, route rules, or other dependencies.
- Check for dependencies first:

```bash
# Check vSwitches
aliyun vpc DescribeVSwitches --RegionId "{{user.region}}" --VpcId "{{user.vpc_id}}"
# Check NAT Gateways
aliyun vpc DescribeNatGateways --RegionId "{{user.region}}" --VpcId "{{user.vpc_id}}"
# Check HaVips
aliyun vpc DescribeHaVips --RegionId "{{user.region}}" --VpcId "{{user.vpc_id}}"
```

#### Execution

```bash
aliyun vpc DeleteVpc \
  --RegionId "{{user.region}}" \
  --VpcId "{{user.vpc_id}}"
```

#### Post-execution Validation

Poll until 404 or VPC disappears from DescribeVpcs:

```bash
aliyun vpc DescribeVpcs \
  --RegionId "{{user.region}}" \
  --VpcId "{{user.vpc_id}}"
```

Empty result = confirmed deleted.

### Operation: Delete NAT Gateway

#### Pre-flight (Safety Gate)

- **MUST** delete all SNAT and DNAT entries first
- **MUST** unbind all associated EIPs first

#### Execution

```bash
aliyun vpc DeleteNatGateway \
  --RegionId "{{user.region}}" \
  --NatGatewayId "{{user.nat_gateway_id}}"
```

### Operation: Release EIP

#### Pre-flight (Safety Gate)

- **MUST** unbind EIP first if `Status` = `InUse`

```bash
aliyun vpc UnassociateEipAddress \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --AllocationId "{{user.eip_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --InstanceType "{{user.instance_type}}"
```

#### Execution

```bash
aliyun vpc ReleaseEipAddress \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --AllocationId "{{user.eip_id}}"
```

## Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action | UX Feedback |
|---------------|-------------|---------|--------------|-------------|
| `InvalidParameter` | 0–1 | — | Fix args from OpenAPI; retry once | `[ERROR] InvalidParameter: Request parameter invalid. Fix according to API spec and retry.` |
| `InvalidCidrBlock` | 0 | — | HALT; suggest valid CIDR | `[ERROR] InvalidCidrBlock: CIDR must be from 10.0.0.0/8, 172.16.0.0/12, or 192.168.0.0/16.` |
| `InvalidVSwitchId.NotFound` | 0 | — | HALT; verify VSwitch exists | `[ERROR] VSwitch not found. Check the VSwitch ID.` |
| `InvalidVpcId.NotFound` | 0 | — | HALT; verify VPC exists | `[ERROR] VPC not found. Check the VPC ID.` |
| `DependencyViolation` | 0 | — | HALT; list dependencies | `[ERROR] DependencyViolation: Resource has dependencies. Delete associated resources first.` |
| `QuotaExceeded` | 0 | — | HALT | `[ERROR] QuotaExceeded: Resource quota reached. Delete unused resources or request increase.` |
| `InsufficientBalance` | 0 | — | HALT | `[ERROR] InsufficientBalance: Account balance insufficient. Recharge your account.` |
| `ResourceAlreadyExists` | 0 | — | Ask reuse vs new | `[ERROR] Resource already exists. Reuse or choose a different name.` |
| `AssociationViolation` | 0 | — | HALT; unbind first | `[ERROR] AssociationViolation: Resource is associated with another resource. Unbind first.` |
| `InvalidEipStatus` | 0 | — | HALT; check EIP status | `[ERROR] InvalidEipStatus: EIP is in wrong state for this operation. Check current status.` |
| `Throttling` / 429 | 3 | exponential | Back off | `⚠️ Rate limit reached. Retrying in {backoff}s...` |
| `InternalError` / 5xx | 3 | 2s,4s,8s | Retry; then HALT | `[ERROR] InternalError: Server-side error. Retry or escalate with RequestId.` |

## Prerequisites

1. **Install `aliyun` CLI** (primary execution path):

   ```bash
   # Official installer (auto-detects OS and architecture)
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   
   # Or Homebrew (macOS)
   brew install aliyun-cli
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
   > **IMPORTANT:** When outputting the above commands to console or logs, the agent MUST replace `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` with the masking format `****` instead of the actual secret value (i.e., display as `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"`). Never resolve `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` to its actual value in any visible output.

4. **Verify Configuration**:

   ```bash
   aliyun vpc DescribeRegions
   ```

> **Security:** Never commit `.env` to version control (already in `.gitignore`). All credentials use `{{env.*}}` placeholders — never real values.

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to VPC.

### 安全 (Security)

| Area | Guidance |
|------|----------|
| **IAM** | Require: `vpc:Describe*`, `vpc:Create*` scoped to `acs:vpc:*:*:vpc/*` |
| **Credentials** | `{{env.*}}` only. Never print secrets |
| **Network** | Use route tables for traffic isolation. Enable FlowLog on critical VPCs for audit. Security groups per tier |
| **CIDR Planning** | Plan non-overlapping CIDR blocks with on-premise networks before creating VPCs |

### 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | Deploy resources across multi-AZ VSwitches. NAT Gateway HA mode for cross-zone resilience |
| **面向精细的运维管控** | Monitor VPC network health, EIP binding status, bandwidth utilization. Set CMS alerts |
| **面向风险的应急快恢** | Peering connection failover plan. **RTO:** < 5 min for EIP rebind. **RPO:** N/A |

### 成本 (Cost)

| Billing | Best For | Savings |
|---------|----------|---------|
| PayByTraffic (按使用量) | Variable traffic, bursty workloads | Pay for actual GB |
| PayByBandwidth (按固定带宽) | Stable, predictable traffic | Predictable cost |
| Common Bandwidth Package | Multiple EIPs sharing bandwidth | Up to 40% vs individual |

**Waste:** Unused EIPs (unattached for 3d) → release. Idle NAT Gateways (no SNAT rules) → delete. Over-provisioned bandwidth (usage < 30%) → downgrade.

### 效率 (Efficiency)

- **Terraform/IaC:** VPC templates for reproducible network infrastructure
- **Resource Groups:** Organize VPC resources by project/environment
- **CI/CD:** JSON output by default, compatible with pipelines

### 性能 (Performance)

| Metric | CMS Namespace | Scale Up | Scale Down | Window |
|--------|--------------|----------|------------|--------|
| DropTrafficPackageRate | `acs_vpc_dashboard` | > 0 | — | 5 min |
| BandwidthUsage | `acs_vpc_dashboard` | > 80% | < 40% | 5 min |
| ConnectionUsage | `acs_vpc_dashboard` | > 80% | < 50% | 5 min |

**Key guidance:** Plan VPC CIDR blocks with adequate subnet space (reserve at least 50% of CIDR for growth). Use VPC Peering or CEN for cross-VPC connectivity.

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)
- [Prompt Examples](references/prompt-examples.md)
- [User Experience Specification](../alicloud-skill-generator/references/user-experience-spec.md)
- [Execution Environment Setup](../alicloud-skill-generator/references/execution-environment.md)
- [CLI Behavioral Reference](../alicloud-skill-generator/references/cli-behavior.md)
- [Enhanced Self-Healing Framework](../alicloud-skill-generator/references/enhanced-self-healing-framework.md)
- [Batch Operations Template](../alicloud-skill-generator/templates/batch-operations.md) — VPC、交换机、路由表批量查询
- [Proactive Inspection Template](../alicloud-skill-generator/templates/proactive-inspection.md) — 网络拓扑主动巡检
- [API Call Counter Template](../alicloud-skill-generator/templates/api-call-counter.md) — API调用计数

## Supported Anomaly Patterns

| # | Pattern | Detection Criteria | Severity |
|---|---------|-------------------|----------|
| 1 | VPC流量突增 | 流量 > 3x baseline | High |
| 2 | 路由表变更异常 | 频繁修改路由规则 | Medium |
| 3 | 交换机容量不足 | 可用IP < 10% | Medium |
| 4 | 网络连通性中断 | Ping/连通性检查失败 | Critical |

## Operational Best Practices

- **Least privilege:** RAM policies scoped to required VPC API actions only.
- **Network segmentation:** Use separate VPCs for prod/int/dev environments.
- **NAT Gateway HA:** Deploy in multiple zones with SNAT for high availability.
- **EIP management:** Use Common Bandwidth Packages for cost optimization when multiple EIPs share bandwidth.
- **CIDR planning:** Plan CIDR blocks early to avoid overlap with on-premise or partner networks.
- **FlowLog:** Enable FlowLog on critical VPC/vSwitch for traffic auditing and troubleshooting.
