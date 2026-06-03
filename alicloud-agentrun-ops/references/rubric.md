---
name: alicloud-agentrun-ops-rubric
description: >-
  GCL rubric for `alicloud-agentrun-ops` (Sandbox Agent Run — sandbox,
  template lifecycle). Phase 5, recommended, max_iter=3. cli_applicability:
  sdk-only (REST API).
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
    - prompt-templates.md
---

# AgentRun GCL Rubric (Phase 5 — recommended, max_iter=3)

> **Hard rules:** `DeleteSandbox` is irreversible — all sandbox state,
> files, contexts, active connections are permanently lost.
> `DeleteTemplate` blocks creation of new sandboxes from it.
> Both require explicit user confirmation and dependency check.

## 1. Per-Op Safety Sub-Rules

| Operation | Sub-rule (Score 1) |
|---|---|
| `DeleteSandbox` | (a) user confirmation matching `{{user.sandbox_id}}`; (b) warn **permanent loss** of sandbox state, files, contexts; (c) check sandbox is not serving production API call (warn if `Status=Running`) |
| `DeleteTemplate` | (a) user confirmation matching `{{user.template_name}}`; (b) **check dependent sandboxes** — list sandboxes created from this template; warn they will lose ability to be recreated from template; (c) backup template content (record in trace) |
| `PauseSandbox` / `HibernateSandbox` | (a) user confirmation; (b) warn that active connections are dropped; (c) check no in-flight long-running computations (process list) |
| `ExecCommand` / `KillProcess` | (a) user confirmation; (b) log the command to trace; (c) block destructive patterns (`rm -rf /`, `kill -9` on system processes) |

## 2. Detection Regex

| Regex | Risk | Examples |
|---|---|---|
| `DeleteSandbox\b` | DESTRUCTIVE-MASS | sandbox delete |
| `DeleteTemplate\b` | DESTRUCTIVE-MASS | template delete |
| `ExecCommand.*(rm\s+-rf|dd\s+if|mkfs|fdisk|shutdown)` | FATAL | destructive exec |

## 3. Changelog
1.0.0 | 2026-06-04 | AgentRun GCL rubric (Phase 5, recommended).