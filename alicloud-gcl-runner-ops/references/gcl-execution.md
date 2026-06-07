---
name: gcl-execution-reference
description: >-
  Integration guide for skills delegating GCL execution to alicloud-gcl-runner-ops.
  Documents how to invoke gcl_runner.py, interpret exit codes, and integrate with
  prompt-templates. Updated for shared-skill delegation (Phase 2).
license: MIT
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-07"
  parent: ../SKILL.md
  references:
    - ../../AGENTS.md
    - ../../docs/gcl-spec.md
    - ../scripts/gcl_runner.py
---

# GCL Runner Execution Guide

> Full GCL specification: [`AGENTS.md §12`](../../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate)
> and [`docs/gcl-spec.md`](../../docs/gcl-spec.md).

## Overview

`alicloud-gcl-runner-ops/scripts/gcl_runner.py` is a standalone Python 3.10+ CLI
that implements the GCL loop:

```
[0] Pre-flight   — load rubric, resolve env.* / user.*, sanitize secrets
[1] Generate     — invoke the command (subprocess) and capture trace
[1.5] H Gate     — hallucination detection (parameter existence, JSON structure, WAF)
[2] Critique     — re-classify output using rubric's regex hot-spots
[3] Decide       — apply termination rules from AGENTS.md §12.5
```

## Integration with a Delegating Skill

Each `required` / `recommended` skill delegating to `alicloud-gcl-runner-ops`
should update its `references/prompt-templates.md` to reference the shared runner.

### Generator Template — Delegation Pattern

Replace the Generator section's implementation note with:

```markdown
> **Executor**: GCL execution delegated to `alicloud-gcl-runner-ops`
> (`scripts/gcl_runner.py`). The shared runner loads this skill's
> `references/rubric.md`, invokes the command as a subprocess, applies
> rubric-based critique, and returns a structured trace. See
> [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md).
```

### Critic Template — Delegation Pattern

The Critic template remains skill-specific (rubric dimensions are per-skill),
but add a note:

```markdown
> **Critic engine**: Mechanical regex-based critic executed by
> `alicloud-gcl-runner-ops/scripts/gcl_runner.py`. The rubric's "Detection Regex"
> table is the score function. All regexes in `references/rubid.md` §{
section} are
> applied to (command + stdout + stderr).
```

## Cross-Check Integration

For cloud-side verification of GCL traces, skills may optionally invoke:

```bash
# ActionTrail cross-check (verifies GCL traces against cloud audit logs)
python3 ${ALIYUN_SKILLS_ROOT}/alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck.py \
  --trace-dir ${ALIYUN_SKILLS_ROOT}/audit-results/ \
  --report ${ALIYUN_SKILLS_ROOT}/audit-results/crosscheck-$(date +%Y%m%d).json

# CMS alarm setup for pass-rate monitoring
python3 ${ALIYUN_SKILLS_ROOT}/alicloud-gcl-runner-ops/scripts/gcl_cms_alarm_setup.py \
  --dry-run  # remove --dry-run for production

# Pass-rate reporting to CMS custom metrics
python3 ${ALIYUN_SKILLS_ROOT}/alicloud-gcl-runner-ops/scripts/gcl_passrate_reporter.py \
  --trace-dir ${ALIYUN_SKILLS_ROOT}/audit-results/ --since 7d
```

## Trace Format

Every GCL run persists a trace under `audit-results/gcl-trace-YYYYMMDD-HHMMSS-<rand6>.json`.

```json
{
  "meta": { "skill": "alicloud-ecs-ops", "op": "DeleteInstance", "timestamp": "..." },
  "preflight": { "status": "ok", "warnings": [] },
  "iterations": [
    {
      "iter": 1,
      "generator": { "command": "aliyun ecs DeleteInstance ...", "status": "ok" },
      "critic": {
        "dimensions": { "correctness": 1.0, "safety": 1.0, "idempotency": 0.8, "traceability": 1.0, "spec_compliance": 1.0 },
        "matched_regexes": [],
        "suggestions": ["Add --RegionId", "Add idempotency token"]
      }
    }
  ],
  "final": { "status": "PASS", "total_iter": 1, "exit_code": 0 }
}
```

## Integration Checklist for Delegating Skills

- [ ] `SKILL.md` has `## Delegation Rules` with GCL delegation to `alicloud-gcl-runner-ops`
- [ ] `references/rubric.md` exists (per-skill rubric with per-op sub-rules)
- [ ] `references/prompt-templates.md` references the shared runner (see above)
- [ ] The skill's `## Quality Gate (GCL)` section (if any) is aligned with shared runner