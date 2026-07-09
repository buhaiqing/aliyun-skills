---
name: alicloud-ack-ops-rubric
description: >-
  GCL rubric for `alicloud-ack-ops` (ACK cluster — cluster lifecycle,
  node pool, node management). Phase 5, recommended, max_iter=3.
license: MIT
metadata:
  skill: alicloud-ack-ops
  api: CS 2015-12-15
  cli_applicability: dual-path
  gcl_classification: recommended
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - prompt-templates.md
---

# ACK GCL Rubric (Phase 5 — recommended, max_iter=3)

> **Hard rules:** `DeleteCluster` is irreversible — entire cluster + all
> workloads lost. The trace MUST show zero critical deployments migrated
> and a snapshot/kubeconfig backup BEFORE the delete.

## 1. Per-Op Safety Sub-Rules

| Operation | Sub-rule (Score 1) |
|---|---|
| `DeleteCluster` | (a) user confirmation naming `{{user.cluster_id}}` AND `{{user.cluster_name}}`; (b) `DeletionProtection` is false (if enabled, must disable first); (c) **backup kubeconfig** in same flow (`DescribeClusterUserKubeconfig`); (d) warn that all namespaces, deployments, services, PVCs will be lost; (e) for production cluster: confirm no active workloads via `kubectl` |
| `DeleteNodePool` | (a) user confirmation; (b) node pool is not the last pool with critical workloads; (c) warn that ECS instances in the pool will be released |
| `ScaleOutCluster` / `ModifyNodePool` (downscale) | (a) user confirmation; (b) remaining nodes have capacity for existing pods |
| `UpgradeCluster` (major version) | (a) user confirmation; (b) **backup kubeconfig**; (c) maintenance window confirmed |

## 2. Detection Regex / Hot-Spots

| Regex | Risk | Examples |
|---|---|---|
| `DeleteCluster\b` | DESTRUCTIVE-MASS | `aliyun cs DeleteCluster` |
| `DeleteNodePool\b` | DESTRUCTIVE-MASS | `aliyun cs DeleteNodePool` |
| `ScalingGroup.*downscale` | DESTRUCTIVE-LIMITED | node downscale |
| `kubeconfig.*backup` (missing) | WRITE-LIMITED | missing backup |


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


## 3. Changelog
1.0.0 | 2026-06-04 | ACK GCL rubric (Phase 5, recommended, max_iter=3).