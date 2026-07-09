---
name: alicloud-skillopt-ops
description: >-
  Legacy framework skill alias for Runtime Harness shared runtime (Strategy B PR-8).
  Implementation lives in alicloud-runtime-harness-ops; scripts here are backward-compatible
  shims. Prefer alicloud-runtime-harness-ops for documentation and delegation.
license: MIT
compatibility: >-
  Bash 4+, Python 3.10+ (via harness_runtime.py shim), jq, curl, optional Langfuse credentials.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-21"
  type: shared-framework-legacy-alias
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  environment:
    - ALIYUN_SKILLS_ROOT
    - HARNESS_SESSION_ID
    - HARNESS_LANGFUSE_ENABLED
---

> **Strategy B PR-8**: Legacy alias. Canonical framework skill:
> [`alicloud-runtime-harness-ops`](../alicloud-runtime-harness-ops/SKILL.md)
> (`harness-core-lib.sh`, `harness-paths.sh`, `harness_runtime.py`).

# Runtime Harness Shared Runtime (legacy alias)

Product overlays still `source` `scripts/skillopt-paths.sh` + `scripts/skillopt-core-lib.sh` from this directory; both delegate to `alicloud-runtime-harness-ops`.

## Legacy Scripts (shims)

| Script | Delegates to |
|--------|----------------|
| `scripts/skillopt-paths.sh` | `../alicloud-runtime-harness-ops/scripts/harness-paths.sh` |
| `scripts/skillopt-core-lib.sh` | `../alicloud-runtime-harness-ops/scripts/harness-core-lib.sh` |
| `scripts/skillopt_runtime.py` | symlink → `harness_runtime.py` |
| `test-skillopt-integration.sh` | `../alicloud-runtime-harness-ops/test-harness-integration.sh` |

See [`docs/runtime-harness-glossary.md`](../docs/runtime-harness-glossary.md).

---

<!-- Retained sections below for link stability; prefer Runtime Harness terminology in new docs. -->

# Alibaba Cloud SkillOpt Shared Runtime

Framework skill providing **shared Runtime Harness runtime** for all `alicloud-*-ops` product skills.

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| Shared core | Product `scripts/skillopt-lib.sh` **MUST** `source` shared core (legacy shims or canonical harness paths) | [Integration](references/integration.md) |
| Runtime Python | **Single** `harness_runtime.py` in `alicloud-runtime-harness-ops`; shims here MUST NOT duplicate | [Langfuse Protocol](references/langfuse-protocol.md) |
| Multi-skill session | Propagate `HARNESS_SESSION_ID` / `--harness-session-id` across product wrappers | [Observability](references/observability.md) |

## Trigger & Scope

| Scope | Description |
|-------|-------------|
| **SHOULD use** | Multi-skill Langfuse validation; configuring observability; understanding trace/session protocol; debugging missing spans |
| **SHOULD NOT use** | Direct `aliyun <product>` CRUD (use product skill); GCL loops (use `alicloud-gcl-runner-ops`) |

### Delegation Rules

| Source | Trigger | Context Passed |
|--------|---------|----------------|
| Any `alicloud-*-ops` | Multi-skill workflow needs shared Langfuse session | `SKILLOPT_SESSION_ID`, skill tags |
| Repo test scripts | `scripts/test-multi-skill-session.sh` | CMS + ECS + OSS shared session |

This skill **receives** delegation; it does not delegate product API work.

## Variable Convention

| Variable | Meaning | Source |
|----------|---------|--------|
| `{{env.ALIYUN_SKILLS_ROOT}}` | Repository root | `git rev-parse` or env |
| `{{env.SKILLOPT_SESSION_ID}}` | Shared trace session | Agent or `--skillopt-session-id` |
| `{{env.SKILLOPT_LANGFUSE_ENABLED}}` | Enable Langfuse ingestion | Env / wrapper flag |
| `{{env.SKILLOPT_METRICS_DIR}}` | Prometheus textfile directory | Env (optional) |

## Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Shared core exists | `test -f alicloud-runtime-harness-ops/scripts/harness-core-lib.sh` (legacy shim: `alicloud-skillopt-ops/scripts/skillopt-core-lib.sh`) | File present | HALT — clone/update repo |
| Paths resolve | `source scripts/skillopt-paths.sh` or `harness-paths.sh` from product lib | `_SKILLOPT_RUNTIME_PY` → `harness_runtime.py` | HALT — set `ALIYUN_SKILLS_ROOT` |
| Langfuse (if enabled) | `LANGFUSE_HOST`, keys set | All three present | HALT — configure `.env` |

## Execution Overview

| Step | Action | Reference |
|------|--------|-----------|
| 1 | Product wrapper calls `skillopt_wrap` in local overlay lib | Product `scripts/*-skillopt-wrapper.sh` |
| 2 | Overlay sources shared `skillopt-paths.sh` + `skillopt-core-lib.sh` | [Integration](references/integration.md) |
| 3 | Core handles trace/metrics/circuit-breaker; overlay handles product repair | `scripts/skillopt-core-lib.sh` |
| 4 | Langfuse span-create via shared `skillopt_runtime.py` | [Langfuse Protocol](references/langfuse-protocol.md) |

## Cross-Skill Delegation (Product Skills)

Add to product SKILL.md delegation table:

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| 可观测性 / Langfuse 多 skill 追踪 | `alicloud-runtime-harness-ops` (legacy: `alicloud-skillopt-ops`) | Session 传播、trace 规范、指标配置 |

## Reference Directory

| Document | Purpose |
|----------|---------|
| [references/core-concepts.md](references/core-concepts.md) | Architecture, lifecycle, dependencies |
| [references/api-sdk-usage.md](references/api-sdk-usage.md) | Shared runtime operations map |
| [references/troubleshooting.md](references/troubleshooting.md) | Error codes and diagnostics |
| [references/well-architected-assessment.md](references/well-architected-assessment.md) | Five-pillar assessment |
| [references/integration.md](references/integration.md) | Product overlay wiring |
| [references/langfuse-protocol.md](references/langfuse-protocol.md) | L1–L11 trace rules |
| [references/observability.md](references/observability.md) | Prometheus + JSON logs |
| [../docs/harness-integration-guide.md](../docs/harness-integration-guide.md) | Full SkillOpt guide |
