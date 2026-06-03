---
name: alicloud-fc-ops-rubric
description: >-
  GCL rubric for `alicloud-fc-ops` (Function Compute — function, service,
  trigger, alias, provisioned concurrency). Phase 5, recommended, max_iter=3.
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
    - prompt-templates.md
---

# FC GCL Rubric (Phase 5 — recommended, max_iter=3)

> **Hard rules:** `DeleteFunction` is the most destructive FC op — all
> invocations in-flight will be lost. `DeleteService` deletes ALL
> functions inside it. Trace MUST show no active triggers before delete.

## 1. Per-Op Safety Sub-Rules

| Operation | Sub-rule (Score 1) |
|---|---|
| `DeleteFunction` | (a) user confirmation naming `{{user.function_name}}`; (b) no active triggers or async invocations (`ListTriggers` returns empty); (c) **final version/alias backup** (export function code URL or last-modified timestamp) |
| `DeleteService` | (a) user confirmation naming `{{user.service_name}}`; (b) `ListFunctions` returns empty (no functions inside the service); (c) warn all functions + triggers + aliases lost |
| `DeleteTrigger` | (a) user confirmation; (b) warn that triggering source (OSS/EventBridge/timer) will silently lose events |
| `UpdateFunction` (downscale provisioned concurrency) | (a) user confirmation; (b) warn that in-flight requests may drop |
| `DeleteProvisionConfig` | (a) user confirmation; (b) warn that cold starts will increase to default concurrency |

## 2. Detection Regex

| Regex | Risk | Examples |
|---|---|---|
| `DeleteFunction\b` | DESTRUCTIVE-MASS | `DeleteFunction` |
| `DeleteService\b` | DESTRUCTIVE-MASS | `DeleteService` |
| `DeleteTrigger\b` | DESTRUCTIVE-LIMITED | `DeleteTrigger` |

## 3. Changelog
1.0.0 | 2026-06-04 | FC GCL rubric (Phase 5, recommended).