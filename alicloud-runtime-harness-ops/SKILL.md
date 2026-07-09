---
name: alicloud-runtime-harness-ops
description: >-
  Canonical framework skill for Runtime Harness shared runtime — Langfuse distributed
  tracing, Prometheus metrics export, session/trace protocol, and multi-skill
  observability. Product skills source scripts/harness-core-lib.sh from here at runtime;
  agents delegate here for multi-skill trace orchestration. Legacy path alicloud-skillopt-ops
  remains as backward-compatible shim (Strategy B PR-8).
license: MIT
compatibility: >-
  Bash 4+, Python 3.10+ (scripts/harness_runtime.py), jq, curl, optional
  Langfuse credentials (LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY).
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-21"
  type: shared-framework
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  environment:
    - ALIYUN_SKILLS_ROOT
    - HARNESS_SESSION_ID
    - HARNESS_LANGFUSE_ENABLED
    - LANGFUSE_HOST
    - LANGFUSE_PUBLIC_KEY
    - LANGFUSE_SECRET_KEY
    - HARNESS_METRICS_DIR
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Runtime Harness Shared Runtime

Framework skill providing **shared Runtime Harness runtime** for all `alicloud-*-ops` product skills.

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| Shared core | Product `scripts/harness-lib.sh` **MUST** `source` `scripts/harness-paths.sh` + `scripts/harness-core-lib.sh` from this skill (legacy: `skillopt-lib.sh` shim) | [Integration](references/integration.md) |
| Runtime Python | **Single** `scripts/harness_runtime.py` lives here; product skills MUST NOT copy it | [Langfuse Protocol](references/langfuse-protocol.md) |
| Multi-skill session | Propagate `HARNESS_SESSION_ID` / `--harness-session-id` across product wrappers in one agent workflow | [Observability](references/observability.md) |

## Trigger & Scope

| Scope | Description |
|-------|-------------|
| **SHOULD use** | Multi-skill Langfuse validation; configuring observability; understanding trace/session protocol; debugging missing spans |
| **SHOULD NOT use** | Direct `aliyun <product>` CRUD (use product skill); GCL loops (use `alicloud-gcl-runner-ops`) |

## Canonical Scripts (PR-8)

| Script | Purpose |
|--------|---------|
| `scripts/harness-paths.sh` | Resolve shared framework paths |
| `scripts/harness-core-lib.sh` | Trace, metrics, circuit breaker, `skillopt_wrap` / `harness_wrap` |
| `scripts/harness_runtime.py` | Langfuse ingestion helpers |
| `test-harness-integration.sh` | Shared runtime integration tests |

## Legacy Compatibility

[`alicloud-skillopt-ops`](../alicloud-skillopt-ops/SKILL.md) retains thin shims (`skillopt-paths.sh`, `skillopt-core-lib.sh`, `skillopt_runtime.py` symlink) so existing product overlays need no change until PR-9.

See [`docs/runtime-harness-glossary.md`](../docs/runtime-harness-glossary.md).
