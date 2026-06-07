---
name: alicloud-vpc-ops-prompt-templates
description: >-
  GCL (Generator-Critic-Loop) prompt templates for `alicloud-vpc-ops`. Phase 1
  rollout, seventh skill. Paired with `rubric.md`.
license: MIT
metadata:
  skill: alicloud-vpc-ops
  api: VPC 2016-04-28
  cli_applicability: cli-first
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# VPC GCL Prompt Templates (Phase 1 Rollout — Seventh Skill)

Inherits structure from `AGENTS.md` §12.7 and prior pilots. VPC-specific
additions: **dependency-cascade trace** for `DeleteVpc` / `DeleteNatGateway`;
**CIDR overlap pre-check** for `Create SNAT/DNAT`; **cross-skill delegation
to `alicloud-eip-ops`** for EIP operations.

> **Critic must run in an isolated context.** `{{user.request}}` is
> **deliberately absent** from the Critic template.

## Generator Template (excerpt — full structure mirrors EIP/Redis)

```text
You are the Generator in a GCL for Alibaba Cloud VPC.

# Hard rules
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any trace value.
- `DeleteVpc` MUST verify zero dependents (vSwitches, NAT Gateways, HaVips,
  route entries, cross-skill ECS/RDS/SLB ENIs) via `Describe*` calls BEFORE
  issuing. Record each step in `dependency_cascade_trace`. Missing any step
  → Safety = 0.
- `DeleteNatGateway` MUST delete ALL SNAT + DNAT entries AND unbind ALL EIPs
  first. Per `SKILL.md` "Delete NAT Gateway" Pre-flight.
- EIP operations (`AssociateEipAddress` / `UnassociateEipAddress` /
  `ReleaseEipAddress`) MUST delegate to `alicloud-eip-ops` GCL rules
  (2-step unbind, DNS audit, production-EIP marker, InstanceType cross-check).
- `Create SNAT/DNAT Entry` MUST verify no CIDR / port overlap with existing
  entries on the same NAT. Overlap → Safety = 0.
- All `{{user.*}}` placeholders MUST be resolved interactively.
```

## Critic Template (excerpt)

```text
You are the Critic in a GCL for Alibaba Cloud VPC. Read-only.

# Checks
- For `DeleteVpc`: independently re-query `DescribeVSwitches`,
  `DescribeNatGateways`, `DescribeHaVips`, `DescribeRouteTables` and
  verify the trace's `dependency_cascade_trace` covers all four. Any
  non-empty result → Safety = 0.
- For `DeleteNatGateway`: independently verify SNAT + DNAT entries are
  empty AND all EIPs unbound. EIP cleanup follows `alicloud-eip-ops` rules.
- For EIP ops: verify the trace delegates to `alicloud-eip-ops` rules
  (or, if the trace is self-contained, verify all EIP rules inline:
  2-step unbind, DNS audit, production marker, InstanceType cross-check).
- For `Create SNAT/DNAT`: independently re-query `DescribeSnatTableEntries`
  / `DescribeForwardTableEntries` to verify no CIDR / port overlap.
- Safety = 0 → `blocking: true`, ABORT.
- Credential Hygiene = 0 → ABORT.
- Suggestions ≤ 3, concrete, executable.
- Do NOT reference the user's original request.
```

## Anti-Patterns
- ❌ `DeleteVpc` without dependency cascade
- ❌ `DeleteNatGateway` with active entries
- ❌ EIP ops without `alicloud-eip-ops` GCL delegation
- ❌ CIDR overlap on SNAT/DNAT

## Changelog
1.0.0 | 2026-06-04 | Initial VPC GCL prompt templates (Phase 1, seventh skill).
