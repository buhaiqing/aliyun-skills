---
name: alicloud-resourcemanager-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-resourcemanager-ops`. Phase 5, recommended.
license: MIT
metadata:
  skill: alicloud-resourcemanager-ops
  api: ResourceManager 2020-03-31
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

# Resource Manager GCL Prompt Templates (Phase 5 — recommended)

## Generator (excerpt)

```text
- `RemoveCloudAccount`: MUST list resource groups of the account first
  (`ListResourceGroups --AccountId`). Record in trace. Warn user that
  ALL resources under the account will be released — permanent.
- `DeleteFolder`: MUST verify folder is empty via `ListFolders --ParentFolderId`.
  Non-empty is an API error (cascading delete not supported).
- `DeleteResourceGroup`: warn that group structure is lost (resources survive).
- `DetachControlPolicy`: warn guardrail loss.
```

## Critic (excerpt)

```text
- `RemoveCloudAccount`: independently re-query `GetAccount` to verify
  account is removed. Check trace for resource-group backup. Check
  trace for the "ALL resources released" warning.
- `DeleteFolder`: re-query `ListFolders`. Folder still exists → Safety = 0.
- Safety = 0 → ABORT.
```

## Changelog
1.0.0 | 2026-06-04 | Resource Manager GCL prompt templates (Phase 5, recommended).