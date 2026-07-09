---
name: alicloud-ask-ops-rubric
description: >-
  GCL rubric for `alicloud-ask-ops` (ASK cluster). Phase 5,
  recommended, max_iter=3. Leaner than ACK (ASK has no node pools).
license: MIT
metadata:
  skill: alicloud-ask-ops
  api: CS 2015-12-15
  cli_applicability: dual-path
  gcl_classification: recommended
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - prompt-templates.md
    - ../../alicloud-ack-ops/references/rubric.md
---

# ASK GCL Rubric (Phase 5 — recommended, max_iter=3)

Inherits ACK rubric. ASK-specific deviations:
- No node pools → `DeleteNodePool` not applicable
- `DeleteCluster` is the primary destructive op
- ASK clusters have `deletion_protection` field in `DescribeClusterDetail`
- ASK workloads are per-Pod metered; no ECS node release

## 1. Per-Op Safety Sub-Rules

| Operation | Sub-rule (Score 1) |
|---|---|
| `DeleteCluster` | (a) user confirmation naming `{{user.cluster_id}}`; (b) `DeletionProtection` is false (must disable first if true); (c) backup kubeconfig in same flow; (d) warn all Pods + PVCs will be lost |
| `ModifyCluster` (downscale) | (a) user confirmation; (b) no active critical Pods would be evicted |

## 2. Changelog
1.0.0 | 2026-06-04 | ASK GCL rubric (Phase 5, recommended).


### Wrapper Compliance (per `AGENTS.md` §15.8 + GCL §3, §14.2.4)

**Definition:** Every `aliyun <product>` invocation against this skill
MUST be routed through `scripts/<product>-skillopt-wrapper.sh`, not
invoked as a bare CLI call. A direct call is a **silent bypass** that
strips self-repair, Langfuse tracing, and circuit-breaker protection.

| Score | Meaning |
|:-----:|---------|
| **1** | The command was routed through the skillopt wrapper (or a non-aliyun path: SDK / data-plane tool / no-wrapper skill) |
| **0** | The command is a direct `aliyun <product>` call while the skill's `scripts/*-skillopt-wrapper.sh` exists — **WRAPPER_BYPASS** |

**Trace field (added in GCL v1.8.0):** `iterations[].generator.execution_path`
records one of `wrapper` | `direct_aliyun` | `sdk_jit` | `data_plane` | `other`.
