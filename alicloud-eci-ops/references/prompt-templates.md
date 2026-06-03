---
name: alicloud-eci-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-eci-ops`. Phase 5, recommended.
license: MIT
metadata:
  skill: alicloud-eci-ops
  api: ECI 2018-08-08
  cli_applicability: dual-path
  gcl_classification: recommended
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---

# ECI GCL Prompt Templates (Phase 5 — recommended)

## Generator (excerpt)

```text
- `DeleteContainerGroup`: require user confirmation + waiver or backup.
  Record Status before delete.
- `ExecContainerCommand`: log the command to trace. Block if command
  matches destructive patterns (rm -rf, dd, mkfs, fdisk).
- `UpdateContainerGroup` downscale: warn OOM risk.
```

## Critic (excerpt)

```text
- `DeleteContainerGroup`: independently re-query `DescribeContainerGroup`
  to verify group is absent. Check trace for waiver/backup.
- `ExecContainerCommand`: check trace for destructive patterns.
  If `rm\s+-rf\s*/` or equivalent → Safety = 0.
- Safety = 0 → ABORT.
```

## Changelog
1.0.0 | 2026-06-04 | ECI GCL prompt templates (Phase 5, recommended).