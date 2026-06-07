---
name: alicloud-ack-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-ack-ops`. Phase 5, recommended,
  max_iter=3.
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
    - rubric.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# ACK GCL Prompt Templates (Phase 5 — recommended)

Generator and Critic templates. See rubric for per-op sub-rules.

## Generator (excerpt)

```text
- `DeleteCluster`: must backup kubeconfig, verify no DeletionProtection,
  require explicit user confirmation. Record cluster_id + cluster_name.
- `DeleteNodePool`: require confirmation that non-critical workloads exist.
- `UpgradeCluster` major version: backup kubeconfig + maintenance window.
```

## Critic (excerpt)

```text
- `DeleteCluster`: independently re-query `DescribeClusterDetail` to verify
  cluster is gone (404). Check trace for kubeconfig backup.
- `DeleteNodePool`: re-query `DescribeClusterNodePools`. Safety 0 if deleted
  pool was the only active pool for a critical workload.
```

## Changelog
1.0.0 | 2026-06-04 | ACK GCL prompt templates (Phase 5, recommended).