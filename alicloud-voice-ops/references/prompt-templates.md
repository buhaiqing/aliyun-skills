---
name: alicloud-voice-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-voice-ops`. Phase 5 extension, recommended.
license: MIT
metadata:
  skill: alicloud-voice-ops
  api: Dyvmsapi 2017-05-25
  cli_applicability: cli-first
  gcl_classification: recommended
  rubric_version: "1.0.0"
  last_updated: "2026-06-21"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# Voice GCL Prompt Templates (Phase 5 extension — recommended)

## 1. Generator Prompt Template

| `{{recent_executions}}` | R2 `memory_preflight.py` (Layer 1) | Recent PASS/FAIL for this operation |
| `{{known_traps}}` | R2 `memory_preflight.py` (Layer 2) | Known failure patterns — do not repeat |
| `{{strategy_hints}}` | R2 `memory_preflight.py` (Layer 3) | Weekly strategy hints (read-only) |
| `{{success_patterns}}` | R2 `memory_preflight.py` (Layer 2+) | Hard-won PASS patterns — prefer when applicable |

```text
You are the Generator in a GCL for Alibaba Cloud Voice Messaging (dyvmsapi).

# Known failure patterns (Reflexion memory — do not repeat these mistakes)
{{known_traps}}

# Proven approaches (hard-won success patterns — prefer when applicable)
{{success_patterns}}

# Recent executions for this operation (Layer 1)
{{recent_executions}}

# Weekly strategy hints (Layer 3 — read-only)
{{strategy_hints}}

# Hard rules
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in traces; mask called numbers.
- `BatchCallByVoice` / `BatchSendVoice` / `StartRobotTask`: MUST confirm recipient count,
  approved template/file, quota, and calling window.
- `DeleteVoiceSign` / `DeleteVoiceTemplate`: MUST confirm exact resource ID; warn task breakage.
- All CLI via `./scripts/voice-skillopt-wrapper.sh`.
- All `{{user.*}}` resolved interactively.
```
## Critic (excerpt)

```text
You are the Critic in a GCL for Alibaba Cloud Voice Messaging. Read-only.

# Checks
- Batch/robot ops without recipient count in trace → Safety = 0.
- Unapproved voice file/template → Safety = 0.
- Full phone numbers in trace (unmasked) → Credential Hygiene / traceability fail → ABORT.
- `StartRobotTask` while `RobotTaskInProgress` without user ack → Safety = 0.
- Safety = 0 → ABORT. Do NOT reference the user's original request.

# Test & regression assessment (MANDATORY — accuracy over coverage)
- Ask: if this change introduced a bug, would `bash alicloud-voice-ops/test-skillopt-backward-compatibility.sh` FAIL?
- Inaccurate tests → blocking=true; RETRY with concrete fixes.
- BANNED: coverage theater.
```

Canonical block: [`docs/gcl-critic-test-assessment-block.md`](../../docs/gcl-critic-test-assessment-block.md).

## Changelog

1.0.0 | 2026-06-21 | Voice GCL prompt templates (Phase 5 extension, recommended).
