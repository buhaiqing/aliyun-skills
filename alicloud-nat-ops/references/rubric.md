---
name: alicloud-nat-ops-rubric
description: >-
  GCL rubric for `alicloud-nat-ops` (NAT Gateway, SNAT, DNAT, EIP). Phase 1,
  eighth skill.
license: MIT
metadata:
  skill: alicloud-nat-ops
  api: VPC 2016-04-28
  cli_applicability: cli-first
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - prompt-templates.md
---

# NAT GCL Rubric (Phase 1 — Eighth Skill)

NAT Gateway is a **single point of egress** for private VPC resources. A
`DeleteNatGateway` with active entries silently cuts off all egress
traffic. This rubric inherits from `AGENTS.md` §12.3 and the prior pilots.

> **Hard rules:** Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
> **NAT cascade rule:** `DeleteNatGateway` MUST delete ALL SNAT entries,
> ALL DNAT (forward) entries, AND unbind ALL EIPs first (3-step cascade,
> per `SKILL.md` "Delete NAT Gateway" Pre-flight).

## 1. Per-Op Safety Sub-Rules

| Operation | Sub-rule (Score 1) |
|---|---|
| `DeleteNatGateway` | (a) user confirmation; (b) `DescribeSnatTableEntries` empty; (c) `DescribeForwardTableEntries` empty; (d) ALL EIPs unbound (per `alicloud-eip-ops` GCL); (e) **maintenance window confirmed** if NAT serves production egress; (f) record 3-step cascade in trace |
| `Create SNAT Entry` | (a) user confirmation; (b) NAT Gateway `Available`; (c) EIP `Available`; (d) `SourceCIDR` does NOT overlap with existing SNAT entries (overlap = `InvalidSnatEntry.Duplicate`); (e) for SNAT with `SnatIp`: EIP's bandwidth can handle the additional egress load |
| `Create DNAT Entry (Forward Entry)` | (a) user confirmation; (b) NAT Gateway `Available`; (c) EIP `Available`; (d) `InternalPort` / `ExternalPort` / `Protocol` not already used by another DNAT on same NAT; (e) the internal IP target is reachable from the NAT (VPC + route table confirmed); (f) for production DNAT: warn that opening external port = exposure surface |
| `Delete SNAT Entry` | (a) user confirmation; (b) entry is `Available`; (c) explicit warning that resources matching `SourceCIDR` will lose egress |
| `Delete DNAT Entry` | (a) user confirmation; (b) explicit warning that external traffic to `ExternalIp:ExternalPort` will stop |
| `Create NatGateway` | (a) user confirmation; (b) `Spec` (Small/Medium/Large) matches expected concurrent connections; (c) `InternetChargeType` (PayBySpec / PayByLcu) understood by user; (d) `VpcId` exists and is the target VPC |

## 2. Critical Hot-Spots

- **CIDR overlap on SNAT** — `SourceCIDR` overlap with existing SNAT causes API error AND unpredictable egress behavior.
- **Port conflict on DNAT** — duplicate `(ExternalIp, ExternalPort, Protocol, InternalIp, InternalPort)` is rejected; a 5-tuple conflict is the exact equality check.
- **NAT EIP bandwidth** — sharing one EIP across many SNAT entries caps aggregate bandwidth.
- **Spec sizing** — Small (5Mbps / 10K conns), Medium (10Mbps / 50K), Large (20Mbps / 100K); undersized NAT = dropped connections.

## 3. Other Dimensions
- **Correctness**: 1.0 for `Delete*` (verify with `Describe*` follow-up).
- **Idempotency**: `CreateNatGateway` must check `DescribeNatGateways --Name` first (NAT name unique per region).
- **Traceability**: `DeleteNatGateway` requires 3-step cascade trace.
- **Spec Compliance**: NAT Spec ∈ {Small, Medium, Large}; `PayBySpec` or `PayByLcu`.
- **Region Compliance**: NAT is regional.
- **Credential Hygiene**: standard 6 patterns; NAT ID is not a secret.
- **Well-Architected**: stability (multi-NAT across AZs); cost (right-sized Spec).

## 4. Worked Example

`DeleteNatGateway` PASS:

```json
{
  "iter": 1,
  "generator": { "command": "aliyun vpc DeleteNatGateway --NatGatewayId ngw-bp1..." },
  "preflight": {
    "user_confirmation": "User confirmed: 'delete ngw-bp1... (prod-egress), maintenance window 14:00-16:00 UTC.'",
    "dependency_cascade_trace": [
      {"step": 1, "command": "DescribeSnatTableEntries", "result": "empty"},
      {"step": 2, "command": "DescribeForwardTableEntries", "result": "empty"},
      {"step": 3, "command": "DescribeEipAddresses --NatGatewayId ngw-bp1...", "result": "empty"}
    ],
    "maintenance_window_confirmed": true
  },
  "critic": { "scores": { "correctness": 1, "safety": 1, "idempotency": 1,
    "traceability": 1, "spec_compliance": 1, "region_compliance": 1,
    "credential_hygiene": 1, "well_architected": 1 }, "blocking": false },
  "decision": "PASS"
}
```

## 5. Anti-Patterns
- ❌ `DeleteNatGateway` with active SNAT/DNAT/EIPs
- ❌ SNAT CIDR overlap
- ❌ DNAT port conflict
- ❌ Production NAT deletion without maintenance window

## 6. Changelog
1.0.0 | 2026-06-04 | Initial NAT GCL rubric (Phase 1, eighth skill). 3-step cascade (SNAT + DNAT + EIP) for `DeleteNatGateway`. CIDR/port overlap rules for create ops.
