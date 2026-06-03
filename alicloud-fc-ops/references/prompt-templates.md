---
name: alicloud-fc-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-fc-ops`. Phase 5, recommended.
license: MIT
metadata:
  skill: alicloud-fc-ops
  api: FC 2023-03-30
  cli_applicability: dual-path
  gcl_classification: recommended
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---

# FC GCL Prompt Templates (Phase 5 — recommended)

## Generator (excerpt)

```text
- `DeleteFunction`: MUST verify no active triggers first (`ListTriggers`).
  Backup function config (`GetFunction` → store last-modified).
- `DeleteService`: MUST verify no functions inside (`ListFunctions` empty).
  MUST list all functions that will be cascaded (≥ user notification).
- `DeleteTrigger`: require user to confirm trigger ARN.
- All `{{user.*}}` resolved interactively.
```

## Critic (excerpt)

```text
- `DeleteFunction`: independently re-query `ListTriggers` and `GetFunction`.
  Active triggers OR function still exists → Safety = 0.
- `DeleteService`: re-query `ListFunctions`. Non-empty → Safety = 0.
- Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
```

## Changelog
1.0.0 | 2026-06-04 | FC GCL prompt templates (Phase 5, recommended).