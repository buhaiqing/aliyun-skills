---
name: alicloud-slb-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-slb-ops`. Phase 5, recommended,
  max_iter=3.
license: MIT
metadata:
  skill: alicloud-slb-ops
  api: SLB 2014-05-15
  cli_applicability: cli-first
  gcl_classification: recommended
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---

# SLB GCL Prompt Templates (Phase 5 — recommended, max_iter=3)

## Generator (excerpt)

```text
You are the Generator in a GCL for Alibaba Cloud SLB.

# Hard rules
- `DeleteLoadBalancer` MUST cascade: `StopLoadBalancerListener` for each
  listener, `DeleteLoadBalancerListener` for each, `RemoveBackendServers`
  for each, then `DeleteLoadBalancer`. Record each step. Missing any step
  → Safety = 0.
- EIP operations delegate to `alicloud-eip-ops` GCL.
- `RemoveVServerGroupBackendServers` MUST verify ≥ 1 healthy backend
  survives (post-check `DescribeHealthStatus`).
- `ModifyLoadBalancerInternetSpec` downgrade requires bandwidth >= current traffic.
```

## Critic (excerpt)

```text
You are the Critic in a GCL for Alibaba Cloud SLB. Read-only.

# Checks
- For `DeleteLoadBalancer`: independently re-query `DescribeLoadBalancerListeners`
  and `DescribeHealthStatus`. Active listeners or 0 healthy backends → Safety = 0.
- For `RemoveVServerGroupBackendServers`: verify ≥ 1 healthy backend in trace.
- Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
- Suggestions ≤ 3.
```

## Changelog
1.0.0 | 2026-06-04 | SLB GCL prompt templates (Phase 5, recommended).