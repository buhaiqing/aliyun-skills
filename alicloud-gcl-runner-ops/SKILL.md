---
name: alicloud-gcl-runner-ops
description: >-
  Shared skill for the Generator-Critic-Loop (GCL) adversarial quality gate.
  Use when any alicloud-*-ops skill needs to run a GCL loop — pre-flight check,
  command generation, rubric-based critique, and termination decision — on a
  write/destructive operation. Other skills delegate GCL execution here rather
  than implementing inline GCL logic. Do NOT use for read-only operations, or
  for non-GCL tasks.
license: MIT
compatibility: >-
  Python 3.10+ (for scripts/gcl_runner.py), Official Alibaba Cloud CLI (`aliyun`,
  Go binary, no runtime), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.1.0"
  last_updated: "2026-06-21"
  type: shared-framework
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  environment:
    - GCL_CRITIC_MODE          # optional: mechanical|llm|hybrid (default: mechanical)
    - GCL_CRITIC_LLM_ENDPOINT  # required for llm/hybrid: OpenAI-compatible endpoint
    - GCL_CRITIC_LLM_API_KEY    # required for llm/hybrid: API key for endpoint
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud GCL Runner — Shared Quality Gate Skill

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/gcl-runner-skillopt-wrapper.sh` for all GCL Runner CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun gcl-runner` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md) |

This skill provides the **Generator-Critic-Loop (GCL)** adversarial quality gate
as defined in `AGENTS.md §12` and [`docs/gcl-spec.md`](../docs/gcl-spec.md). It is
a **shared framework skill**: other `alicloud-*-ops` skills delegate their GCL
execution here rather than implementing inline GCL logic.


> **EXECUTION MANDATORY RULE**: 所有 GCL runner 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/gcl-runner-skillopt-wrapper.sh` 运行。
> 以下所有 `python3 scripts/gcl_runner.py ...` 示例在执行时应替换为 `./scripts/gcl-runner-skillopt-wrapper.sh ...`（参数原样传递）。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun ` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。
## Trigger & Scope

| Scope | Description |
|-------|-------------|
| **SHOULD use** | Any `alicloud-*-ops` skill executing a write/destructive cloud operation that requires GCL quality gate before presenting results to the user |
| **SHOULD NOT use** | Read-only operations (Describe/List/Get); operations on skills without GCL classification (`optional` / read-only skills); non-cloud tasks |

### Delegation Rules

This skill **receives** delegation from other skills. It does **not** delegate
to other skills.

| Source Skill Type | Trigger | Context Passed |
|-------------------|---------|----------------|
| All `required` / `recommended` skills | Before executing a write/destructive operation: "Delegate GCL quality gate to alicloud-gcl-runner-ops" | `skill`, `op`, `command`, `user_request`, `max_iter` |
| `alicloud-skill-generator` | When validating generated skill content: "Run GCL on the generated commands" | `skill`, `op`, `command` |

## Variable Convention

| Variable | Meaning | Source |
|----------|---------|--------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Alibaba Cloud AccessKey | Environment (NEVER ask user) |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Alibaba Cloud AccessSecret | Environment (NEVER ask user, NEVER log) |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Default region | Environment (NEVER ask user) |
| `{{env.ALIYUN_SKILLS_ROOT}}` | Repository root | Environment or autodetected via `git rev-parse --show-toplevel` |
| `{{user.skill}}` | Target skill name (e.g. `alicloud-ecs-ops`) | Delegate context |
| `{{user.op}}` | Operation name (e.g. `DeleteInstance`) | Delegate context |
| `{{user.command}}` | Full CLI command to execute | Delegate context |
| `{{user.user_request}}` | Original natural-language request | Delegate context |
| `{{user.max_iter}}` | Maximum GCL iterations (default: 2) | Delegate context or interactive prompt |

## Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| `aliyun` CLI installed | `command -v aliyun` | Binary found | HALT — install `aliyun` CLI per `alicloud-skill-generator/references/execution-environment.md` |
| Python 3.10+ available | `python3 --version` | Version ≥ 3.10 | HALT — install Python 3.10+ |
| `gcl_runner.py` exists | `ls {{env.ALIYUN_SKILLS_ROOT}}/alicloud-gcl-runner-ops/scripts/gcl_runner.py` | File found | HALT — re-clone or check repo integrity |
| Target skill rubric exists | `ls {{env.ALIYUN_SKILLS_ROOT}}/{{user.skill}}/references/rubric.md` | File found | HALT — rubric missing, check skill structure |
| Credentials configured | `echo ${ALIBABA_CLOUD_ACCESS_KEY_ID:?}` | Non-empty | HALT — configure credentials per README_CN.md |
| LLM Critic endpoint configured (only if `GCL_CRITIC_MODE=llm\|hybrid`) | check `GCL_CRITIC_LLM_ENDPOINT` | Non-empty if LLM mode is enabled | HALT if `GCL_CRITIC_LLM_FAIL_OPEN=false`; else fall back to `mechanical` |
| LLM Critic API key configured (only if `GCL_CRITIC_MODE=llm\|hybrid`) | check `GCL_CRITIC_LLM_API_KEY` | Non-empty if LLM mode is enabled | WARNING logged if empty (endpoint may reject request); execution continues |

## Execution — CLI

```bash
# Locate the script (relative to repo root)
SCRIPT="${ALIYUN_SKILLS_ROOT:-$(git rev-parse --show-toplevel)}/alicloud-gcl-runner-ops/scripts/gcl_runner.py"

# Invoke the GCL runner
python3 "$SCRIPT" \
  --skill "{{user.skill}}" \
  --op "{{user.op}}" \
  --command "{{user.command}}" \
  --user-request "{{user.user_request}}" \
  --max-iter "{{user.max_iter:-2}}" \
  --output-dir "${ALIYUN_SKILLS_ROOT:-.}/audit-results"
```

### Exit Codes

| Code | Status | Meaning | Action |
|:----:|--------|---------|--------|
| 0 | `PASS` | All rubric dimensions ≥ threshold | Operation accepted |
| 1 | `MAX_ITER` | Reached max iterations; best-so-far returned | Inspect trace, refine command |
| 2 | `SAFETY_FAIL` | Safety = 0 (destructive match) | **ABORT** — user re-confirmation required |
| 3 | `USAGE_ERROR` | Bad CLI args / product mismatch | Fix invocation |
| 4 | `RUBRIC_ERROR` | Rubric file missing or unparseable | Check rubric.md |
| 5 | `HALLUCINATION_ABORT` | Hallucination detection triggered | Fix generated command/JSON |

### Dry-Run (Critic-Only Regression)

```bash
python3 "$SCRIPT" \
  --skill "{{user.skill}}" \
  --op "{{user.op}}" \
  --command "{{user.command}}" \
  --user-request "{{user.user_request}}" \
  --dry-run
```

## Execution — SDK (Go JIT)

For SDK-only skills or CLI fallback operations, use `gcl_actiontrail_crosscheck.py`
to verify GCL traces against cloud audit logs:

```bash
python3 "${ALIYUN_SKILLS_ROOT}/alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck.py" \
  --trace-dir "${ALIYUN_SKILLS_ROOT}/audit-results/" \
  --report "${ALIYUN_SKILLS_ROOT}/audit-results/crosscheck-$(date +%Y%m%d).json"
```

## Post-execution Validation

After the GCL runner completes:

1. **Check exit code** — any code ≠ 0 means the command was rejected or needs refinement
2. **Inspect trace** — `audit-results/gcl-trace-*.json` contains full iteration records
3. **ActionTrail cross-check** (optional) — run `gcl_actiontrail_crosscheck.py` for cloud-side verification
4. **Present result to user** — include trace path for audit trail

## Failure Recovery

| Failure | Diagnosis | Recovery |
|---------|-----------|----------|
| `SAFETY_FAIL` | Destructive regex matched command/rubric | Present trace to user; request explicit re-confirmation or safer alternative |
| `MAX_ITER` | Loop exhausted without passing all dimensions | Inspect `unresolved_rubric_items` in trace; fix command or update rubric |
| `USAGE_ERROR` | CLI arguments malformed | Fix `--skill`, `--command`, or product prefix |
| `RUBRIC_ERROR` | Rubric parse failure | Verify rubric.md exists and is well-formed frontmatter + body |
| `HALLUCINATION_ABORT` | Generated command/JSON failed structural check | Fix parameter names, JSON structure, or resource references |
| Credential missing | `ALIBABA_CLOUD_ACCESS_KEY_ID` not set | Configure credentials per README_CN.md |
| Python version < 3.10 | `gcl_runner.py` uses stdlib features | Install Python 3.10+ |

## Security Constraints

- **Never output credentials**: `gcl_runner.py` sanitizes secrets in traces; do not add additional output that could leak
- **SAFETY_FAIL is a hard block**: do NOT retry without explicit user re-confirmation
- **Passwords via env vars**: for data-plane operations (e.g. Redis `REDISCLI_AUTH`), use environment variables, not `-a <password>`

## Quality Gate (GCL)

This skill is the GCL runner itself. It does not have a separate rubric/prompt-templates
because it is the **executor** of the GCL — the rubric comes from the delegating skill.

See:
- [`scripts/README.md`](scripts/README.md) — full runner documentation
- [`references/gcl-execution.md`](references/gcl-execution.md) — integration guide for delegating skills
- [`docs/gcl-spec.md`](../docs/gcl-spec.md) — complete GCL specification

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-06-07 | Initial shared skill. Migrated from top-level `scripts/`; added SKILL.md, references, and delegation contract for all alicloud-*-ops skills. |