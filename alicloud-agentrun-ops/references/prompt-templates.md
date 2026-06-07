---
name: alicloud-agentrun-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-agentrun-ops`. Phase 5, recommended.
license: MIT
metadata:
  skill: alicloud-agentrun-ops
  api: AgentRun 2025-09-10
  cli_applicability: sdk-only
  gcl_classification: recommended
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# AgentRun GCL Prompt Templates (Phase 5 — recommended)

## Generator (excerpt)

```text
- `DeleteSandbox`: MUST check `Status` first. Running sandbox requires
  `PauseSandbox` first. Warn permanent state loss. Record backup of
  sandbox config (description, env vars).
- `DeleteTemplate`: MUST check dependent sandboxes via `ListSandboxes`
  or template metadata. Warn that existing sandboxes lose recreate ability.
- `ExecCommand`: block if command matches `rm -rf /`, `dd if=/dev/zero`,
  `mkfs`, `fdisk`, or `shutdown`. Record command in trace.
```

## Critic (excerpt)

```text
- `DeleteSandbox`: independently verify sandbox is absent via API.
  Check trace for Status check and waiver.
- `DeleteTemplate`: verify template is absent. Check trace for dependent
  sandbox check.
- `ExecCommand`: check command in trace for destructive patterns.
  `ExecCommand.*(rm\\s+-rf|dd\\s+if|mkfs|fdisk|shutdown)` → Safety = 0.
- Safety = 0 → ABORT.
```

## Changelog
1.0.0 | 2026-06-04 | AgentRun GCL prompt templates (Phase 5, recommended).