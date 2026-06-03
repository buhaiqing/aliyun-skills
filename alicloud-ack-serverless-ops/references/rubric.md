---
name: alicloud-ack-serverless-ops-rubric
description: >-
  GCL rubric for `alicloud-ack-serverless-ops` (ASK cluster). Phase 5,
  recommended, max_iter=3. Leaner than ACK (ASK has no node pools).
license: MIT
metadata:
  skill: alicloud-ack-serverless-ops
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