---
name: alicloud-ack-serverless-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-ack-serverless-ops`. Phase 5,
  recommended.
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
    - rubric.md
---

# ASK GCL Prompt Templates (Phase 5 — recommended)

## Generator/ Critic

Inherits ACK patterns (see `alicloud-ack-ops/references/prompt-templates.md`).
Key ASK-specifics:

- `DeleteCluster`: only destructive op. MUST backup kubeconfig.
- `DeletionProtection` gate: if the cluster has `deletion_protection=true`,
  the Generator MUST first call `ModifyCluster --DeletionProtection false`.
- Critic: independently re-query `DescribeClusterDetail` to verify cluster
  is absent AND `DeletionProtection` was toggled if applicable.

## Changelog
1.0.0 | 2026-06-04 | ASK GCL prompt templates (Phase 5, recommended).