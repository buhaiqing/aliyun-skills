---
name: alicloud-vpc-ops-rubric
description: >-
  GCL (Generator-Critic-Loop) rubric for `alicloud-vpc-ops` (VPC, vSwitch,
  NAT Gateway, EIP, route table, HaVip, network ACL). Phase 1 rollout,
  seventh skill. Paired with `prompt-templates.md`.
license: MIT
metadata:
  skill: alicloud-vpc-ops
  api: VPC 2016-04-28
  cli_applicability: cli-first
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - prompt-templates.md
---

# VPC GCL Rubric (Phase 1 Rollout — Seventh Skill)

VPC is the **network foundation** of the cloud account. A `DeleteVpc` failure
cascades to every vSwitch, NAT, ECS, RDS inside it. This rubric inherits
the 5+3-dim structure from `AGENTS.md` §12.3 and the prior pilots.

> **Hard rules:** Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
> **Dependency cascade rule:** `DeleteVpc` MUST verify zero dependents
> (vSwitches, NAT Gateways, HaVips, route entries) before issuing. Per
> `SKILL.md` "Delete VPC" Pre-flight "MUST NOT proceed unless VPC has
> **no** associated vSwitches, NAT Gateways, route rules, or other
> dependencies." The trace MUST record each `Describe*` dependency check.

## 1. Core Dimensions

### 1.1 Correctness — 1.0 required for `Delete*` / `Unassociate*` (post-execution `Describe*` follow-up).

### 1.2 Safety — per-op sub-rules:

| Operation | Sub-rule (Score 1) |
|---|---|
| `DeleteVpc` | (a) explicit user confirmation; (b) `DescribeVSwitches` returned empty for `VpcId`; (c) `DescribeNatGateways` returned empty; (d) `DescribeHaVips` returned empty; (e) route table empty; (f) NO cross-skill dependents (ECS, RDS, SLB, NAT all report `VpcId` mismatch) — record the cross-skill lookup in trace |
| `DeleteVSwitch` | (a) user confirmation; (b) `DescribeVSwitches` confirmed zero ECS / RDS / SLB ENIs in the vSwitch; (c) no NAT Gateway in the vSwitch |
| `DeleteNatGateway` | (a) user confirmation; (b) `DescribeSnatTableEntries` returned empty; (c) `DescribeForwardTableEntries` returned empty; (d) ALL EIPs unbound (`DescribeEipAddresses --NatGatewayId`); (e) 2-step unbind pattern from `alicloud-eip-ops` GCL honored |
| `ReleaseEipAddress` (VPC) | Delegate to `alicloud-eip-ops` GCL; require 2-step unbind + DNS audit + production-EIP marker |
| `AssociateEipAddress` / `UnassociateEipAddress` | Delegate to `alicloud-eip-ops` GCL; `InstanceType` cross-verification required |
| `Create SNAT Entry` / `Create DNAT Entry` | (a) user confirmation; (b) NAT Gateway is `Available`; (c) EIP is `Available`; (d) `SourceCIDR` / `DestinationCIDR` does NOT overlap with existing entries (overlap causes `InvalidSnatEntry.Duplicate`); (e) for DNAT: `InternalPort` / `ExternalPort` not in use by another entry on same NAT |
| `CreateVpc` / `CreateVSwitch` | (a) user confirmation; (b) `CidrBlock` is RFC1918 (10/8, 172.16/12, 192.168/16) for private VPC; (c) vSwitch `CidrBlock` is a subnet of the VPC's `CidrBlock` and does NOT overlap with existing vSwitches; (d) quota not exceeded |

### 1.3 Idempotency — `CreateVpc` must check `DescribeVpcs --VpcName` first (VpcName is unique per region). `Delete*` ops are natural idempotent.

### 1.4 Traceability — mandatory `dependency_cascade_trace` for `DeleteVpc` / `DeleteNatGateway` (the 4-5 `Describe*` calls before the destructive op).

### 1.5 Spec Compliance — RFC1918 CIDR; vSwitch CIDR is subnet of VPC; region matches `{{user.region}}`.

## 2. Aliyun-Specific Extensions

### 2.1 Region Compliance — VPC is regional. `--RegionId` must match.

### 2.2 Credential Hygiene — 6 patterns from `alicloud-eip-ops` + new: `--CidrBlock` is not a secret; NAT Gateway ID is not a secret. Standard sanitization.

### 2.3 Well-Architected — Security: VPC should not have `0.0.0.0/0` routes to IGW (delegate to SG audit). Stability: redundant NAT Gateways across AZs. Cost: avoid over-provisioned NAT bandwidth.

## 3. Termination Thresholds

Default per `AGENTS.md` §12.5. `max_iter=2`. Safety=0 or Credential Hygiene=0 → ABORT.

## 4. Worked Examples

### Example 1: `DeleteVpc` PASS (full dependency cascade)

```json
{
  "iter": 1,
  "generator": {
    "command": "aliyun vpc DeleteVpc --RegionId cn-hangzhou --VpcId vpc-bp1...",
    "exit_code": 0
  },
  "preflight": {
    "user_confirmation": "User confirmed: 'delete vpc-bp1... (legacy-vpc), all resources migrated.'",
    "dependency_cascade_trace": [
      {"step": 1, "command": "DescribeVSwitches", "result": "empty"},
      {"step": 2, "command": "DescribeNatGateways", "result": "empty"},
      {"step": 3, "command": "DescribeHaVips", "result": "empty"},
      {"step": 4, "command": "DescribeRouteTables", "result": "1 system route only"}
    ]
  },
  "critic": { "scores": { "correctness": 1, "safety": 1, "idempotency": 1,
    "traceability": 1, "spec_compliance": 1, "region_compliance": 1,
    "credential_hygiene": 1, "well_architected": 1 },
    "blocking": false },
  "decision": "PASS"
}
```

### Example 2: `DeleteVpc` with active vSwitch → SAFETY_FAIL

```json
{
  "iter": 1,
  "generator": { "command": "aliyun vpc DeleteVpc --VpcId vpc-bp1..." },
  "preflight": {
    "dependency_cascade_trace": [
      {"step": 1, "command": "DescribeVSwitches", "result": "2 vSwitches: vsw-bp1a, vsw-bp1b"}
    ]
  },
  "critic": {
    "scores": { "correctness": 0, "safety": 0, "idempotency": 1,
      "traceability": 1, "spec_compliance": 1, "region_compliance": 1,
      "credential_hygiene": 1, "well_architected": 0 },
    "suggestions": ["BLOCKED: VPC has 2 active vSwitches. Delete vSwitches first (DescribeVSwitches → DeleteVSwitch for each), then retry DeleteVpc."],
    "blocking": true
  },
  "decision": "ABORT_SAFETY"
}
```

## 5. Anti-Patterns
- ❌ `DeleteVpc` without dependency cascade
- ❌ `DeleteNatGateway` with active SNAT/DNAT entries
- ❌ `Create SNAT/DNAT` with overlapping CIDR
- ❌ CIDR outside RFC1918 for private VPC

## 6. Changelog
1.0.0 | 2026-06-04 | Initial VPC GCL rubric (Phase 1, seventh skill). Dependency-cascade pattern for `DeleteVpc` / `DeleteNatGateway`. Cross-skill delegation to `alicloud-eip-ops` for EIP ops.
