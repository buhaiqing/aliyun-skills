---
name: aliyun-skills-agent-guide
description: >-
  Repo-level conventions and quality gates for aliyun-skills agent runbooks.
  Entry point: @AGENTS.md
---

# Aliyun Skills — Agent Guide

> Repo: `aliyun-skills/` — structured AI-agent-parseable runbooks for Alibaba Cloud.

---

## 0. Foundations

### 0.1 Instruction Priority (highest wins)

| # | Source | Notes |
|---|--------|-------|
| 1 | **User explicit instructions** | Direct request |
| 2 | **Karpathy Guidelines** (§0.2) | Behavioral baseline |
| 3 | **This file** | Repo conventions |
| 4 | **Loaded SKILL.md + references/** | Domain runbook |
| 5 | Default agent heuristics | Lowest |

**Non-overridable floors**: §8 Security, §12 Safety=0 → ABORT, destructive confirmation, credential non-leakage.

### 0.2 Karpathy Guidelines (MANDATORY)

| # | Rule | Requirement |
|---|------|-------------|
| **K1** | Think before coding | State assumptions; ask when uncertain; surface tradeoffs |
| **K2** | Simplicity first | No speculative features, abstractions, or unrequested config |
| **K3** | Surgical changes | Touch only what the task requires; match existing style |
| **K4** | Goal-driven execution | Define verifiable success criteria; per-step checks; loop until verified |

Canonical skill: `karpathy-guidelines`.

**Banned**: "while I'm here I'll refactor…", "tests can come later", "this needs a general framework…"

### 0.3 Product Skill Mission

Each `alicloud-*-ops` skill is a **domain colleague** delivering through **Harness Engineering** — not a memory or learning subsystem.

| Pillar | Mission | Repo expression |
|--------|---------|-----------------|
| **Domain colleague** | Partner: product expertise + assembled context | `core-concepts.md`, Well-Architected, Pre-flight / `{{user.*}}` / `{{env.*}}` / `{{output.*}}`, UX transparency |
| **Harnessed delivery** | Explainable, observable outcomes | GCL rubric + `prompt-templates.md` (§12), wrapper-first (§15.8), diagnostic logging |

**Collaboration posture** (bounded autonomy):

| Role | Behavior |
|------|----------|
| **Colleague** | Ask once, reuse variables; no credential leakage |
| **Partner** | Delegate cross-product via Delegation Rules; share `HARNESS_SESSION_ID`; single responsibility |
| **Subordinate** | HALT on pre-flight fail, missing creds, or rubric-exceeded risk; destructive ops require explicit confirmation (§8) |

**Non-goals**: Layer 1/2 memory indexing, Reflexion report generation, LLM evolution pipelines — these are platform-owned (§16.8).

---

## 1. Repo Layout (canonical)

```text
aliyun-[product]-ops/
├── SKILL.md                         # What to do
├── references/
│   ├── core-concepts.md             # Architecture, limits, quotas, dependencies
│   ├── api-sdk-usage.md             # Operation map, request/response, pagination
│   ├── cli-usage.md                 # `aliyun` CLI command map
│   ├── troubleshooting.md           # ≥10 error codes, diagnostics, recovery
│   ├── rubric.md                    # MANDATORY if GCL required/recommended
│   ├── prompt-templates.md          # MANDATORY if GCL required/recommended
│   ├── monitoring.md                # CMS metrics, dashboards, alarms
│   ├── well-architected-assessment.md
│   └── advanced/                    # Lazy-loaded: AIOps, FinOps, SQL execution
├── assets/
│   ├── example-config.yaml
│   └── eval_queries.json            # MANDATORY
└── scripts/                         # Optional (only redis-ops, topo-discovery)
```

**Note**: Only `redis-ops`, `topo-discovery`, `gcl-runner-ops` have `scripts/`.

---

## 2. Content Separation (MANDATORY)

| File | Responsibility |
|------|---------------|
| `SKILL.md` | What — triggers, pre-flight, variables, execution overview, links |
| `references/*.md` | How — full commands, exit codes, log interpretation, failure recovery |

---

## 3. Operation Pattern

Every operation needs: **Pre-flight Checks → Execute → Validate → Recover**

```text
| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| {precondition} | {verification command} | {normal value} | HALT — {human action} |
```

**Variable convention**:

| Variable | Meaning | Source |
|----------|---------|--------|
| `{{user.xxx}}` | User input | Ask once, reuse |
| `{{env.xxx}}` | Environment variable | NEVER ask; HALT if missing |
| `{{output.xxx}}` | Previous step output | Parse from API response |

**Diagnostic logs**: `[HH:MM:SS] [PHASE] key=value` with phases `DIAG`/`INSTALL`/`EXEC`/`RESULT`/`WARN`/`ERROR`/`SUMMARY`. Spec: [docs/diagnostic-logging-standard.md](docs/diagnostic-logging-standard.md).

---

## 5. Idempotent Provisioning

```bash
# Probe → install only if missing → execute
if ! command -v redis-cli &>/dev/null; then
  apt-get install -y redis-tools
fi
redis-cli -h host DEL key
```

---

## 6. Cross-Skill Composition

Inline necessary commands in SKILL.md. Document the dependency in comments. Do NOT formal import/require another skill.

```markdown
# Execution (uses aliyun ecs RunCommand; see alicloud-ecs-ops for advanced usage)
aliyun ecs RunCommand --RegionId ... --CommandContent "..."
```

---

## 7. Data Plane vs Control Plane

| Plane | Capability | Channel | Example Operations |
|-------|-----------|---------|-------------------|
| **Control Plane** | Instance lifecycle, config | `aliyun {product}` API | Create/Delete/Describe/Modify instances |
| **Data Plane** | Data read/write, command execution | `redis-cli` / SDK direct | DEL, GET, SET, TTL, EVAL |

Data-plane gap: `redis-ops` → `ecs-ops RunCommand` → target ECS executes `redis-cli`.

---

## 8. Security Constraints

- **Never output credentials**: Replace `ALIBABA_CLOUD_ACCESS_KEY_SECRET` in logs with `****`.
- **Passwords via env vars**: `REDISCLI_AUTH` instead of `-a <password>`.
- **Delete ops**: MUST obtain explicit user confirmation. Include a confirmation row in Pre-flight Checks.

---

## 9. Quick Reference

```bash
# Markdown linting
npx markdownlint-cli2 "alicloud-*/SKILL.md"

# Docker sandbox
docker compose --profile dev up -d        # Development
docker compose --profile runtime up -d    # Minimal runtime

# Generate new skill (use meta-skill)
"Generate alicloud-xyz-ops for product XYZ with operations: create, describe, modify, delete"

# JIT Go SDK
./alicloud-jit-setup.sh

# Python 3.10 baseline
python3 scripts/check_py310_compat.py
cd alicloud-gcl-runner-ops/scripts && python3 -m unittest gcl_runner_test -v
```

---

## 10. Quality Gates

Every Skill MUST pass:

1. **Clear Boundaries**: SHOULD/SHOULD NOT triggers with delegation rules (< 1024 chars)
2. **Structured I/O**: `{{env.*}}` (never ask user), `{{user.*}}` (ask once), `{{output.*}}` (parse from API)
3. **Explicit Steps**: Pre-flight → Execute → Validate → Recover
4. **Failure Strategies**: ≥10 product-specific error codes; HALT vs retry; credential vs quota vs business error separation
5. **Single Responsibility**: One product, one primary resource; delegation documented
6. **CLI Format**: RepeatList requires `.N` suffix; JSON arrays use `'["val"]'` — see §14

### 10.1 Token Efficiency (P0 — MANDATORY)

Minimize token consumption per Skill while preserving agent executability.

| Rule | Key Point |
|------|-----------|
| **TE-1** | API query > static table — no hardcoding |
| **TE-2** | Go SDK: `#` comment instead of function-level docstring |
| **TE-3** | Compact error tables: 1 code per row, ≤3 columns |
| **TE-4** | Centralized JSON paths at file top, don't repeat |
| **TE-5** | YAML anchors in `example-config.yaml` |
| **TE-6** | SKILL.md has full flow; references/ doesn't repeat |
| **TE-7** | AIOps/FinOps in `references/advanced/`; SQL execution marked Security-Sensitive |

> **Non-compressible**: Agent-executable commands, error recovery logic, safety gates, credential rules. See [docs/token-efficiency-strategy.md](docs/token-efficiency-strategy.md) for TE-A/B/C.

---

## 11. Post-Update Self-Review (MANDATORY)

After every skill update, auto-run 2 rounds of self-review and fix all issues.

| Round | Scope | Key Checks |
|-------|-------|-----------|
| **R1: Structural** | Frontmatter/Trigger/Variables/Token Efficiency | C1-C6, C6 MUST PASS |
| **R2: Content** | CLI validation/error codes/safety/link integrity/dedup/TODO.md/**regression** | F1-F9, F5/F6/F8/F9 MUST PASS |

其中 **F8 / F9** 为强制通过项：

| 编号 | 检查项 | 要求 |
|------|--------|------|
| **F8** | TODO.md 同步 | 每次更新必须同步更新 TODO.md |
| **F9** | 回归测试 | 行为/脚本变更后跑对应用例且通过；重构须先补测试再改代码 |

Full spec + check tables: [docs/post-update-self-review.md](docs/post-update-self-review.md)

### 11.1 Regression Testing (MANDATORY)

**Accuracy over coverage**: A test that would not fail when the change breaks is worse than no test.

| Change touches | Run (minimum) |
|----------------|---------------|
| Any SkillOpt skill | `bash alicloud-<product>-ops/test-skillopt-backward-compatibility.sh` |
| `alicloud-runtime-harness-ops/` | `export ALIYUN_SKILLS_ROOT="$PWD" && bash alicloud-runtime-harness-ops/test-harness-integration.sh` |
| `gcl_runner.py` | `cd alicloud-gcl-runner-ops/scripts && python3 -m unittest gcl_runner_test` |
| `SKILL.md` only (substantive) | `npx markdownlint-cli2 "alicloud-<product>-ops/SKILL.md"` |

Full suite table + agent checklist (RT-1–RT-6): [docs/post-update-self-review.md §11.1](docs/post-update-self-review.md#111-regression-testing-mandatory)

---

## Key References

| Document | Description |
|----------|-------------|
| `alicloud-skill-generator/SKILL.md` | Meta Skill generator — full workflow, P0/P1 checklist, Token Efficiency rules |
| `alicloud-skill-generator/references/alicloud-skill-template.md` | Canonical SKILL.md template |
| [`docs/gcl-spec.md`](docs/gcl-spec.md) | **GCL full spec** — roles, rubric, loop flow, trace schema, anti-patterns, §8 Per-Skill Defaults |
| [`docs/post-update-self-review.md`](docs/post-update-self-review.md) | Self-review spec — check tables, verification scripts, dedup procedures |
| [`docs/harness-integration-guide.md`](docs/harness-integration-guide.md) | Runtime Harness integration — self-repair, Langfuse, §15.6 hardening rules, §15.7 Langfuse lessons |
| [`docs/token-efficiency-strategy.md`](docs/token-efficiency-strategy.md) | Always-loaded vs lazy-loaded methodology, audit checklist |

> **When specs conflict**: §0 (instruction priority, Karpathy, product mission) and repo-wide rules win for **agent behavior**. For **product skill authoring** field-level templates, `alicloud-skill-generator/SKILL.md` is authoritative.

---

## 12. Generator-Critic-Loop (GCL)

Enforce Generator ↔ Critic adversarial loop on every cloud operation, scored against a quantified rubric.

**Full spec**: [`docs/gcl-spec.md`](docs/gcl-spec.md)

### 12.1 Roles

| Role | Responsibility | Banned |
|------|---------------|--------|
| **Generator (G)** | Execute the cloud operation | Modify rubric, self-score |
| **Hallucination Detector (H)** | Pre-execution structural validity check (v1.5.0) | Execute API calls, mutate G's output |
| **Critic (C)** | Independently audit G's output; assess test accuracy + regression need (§12.2) | Call `aliyun`/SDK, mutate resources |
| **Orchestrator (O)** | Loop control, termination decision | Execute or score |

### 12.2 Critic Test & Regression Assessment (MANDATORY)

| Assessment | Critic action | On failure |
|------------|---------------|------------|
| **Test accuracy** | Judge whether tests correctly exercise changed behavior. Ask: *if this broke, would tests fail?* | Set `blocking=true`, trigger **RETRY** |
| **Regression verification** | Decide smallest accurate suite for the change; require green runs | Skip only with zero-behavioral-delta rationale |

**Banned**: padding test count, chasing coverage %, or PASSing because a suite ran green while no test asserts the changed behavior.

### 12.3 Rubric Dimensions (≥5)

| Dimension | Meaning | Safety=0 |
|-----------|---------|----------|
| **Correctness** | Resource ID/state/config matches request | — |
| **Safety** | Destructive operations confirmed or protected | **Immediate ABORT** |
| **Idempotency** | Repeating the call has no side effects | — |
| **Traceability** | Output is auditable | — |
| **Spec Compliance** | Complies with core-concepts.md constraints | — |

### 12.4 Loop Flow

**H pre-check** (when enabled) → **G execute** → **C critique** → **O decide**

### 12.5 Termination Conditions (first match wins)

| Condition | Action |
|-----------|--------|
| **PASS** | All dimensions pass → return G's result |
| **MAX_ITER** | Reached max_iter → return best-so-far |
| **SAFETY_FAIL** | Safety=0 → **ABORT** |
| **HALLUCINATION_ABORT** | H detected unresolved → **ABORT** (v1.5.0) |

### 12.6 Trace Audit

Every GCL run MUST persist JSON trace to `./audit-results/gcl-trace-*.json` (gitignored). Credential fields MUST be masked per §8.

### 12.7 Skill Classification + Per-Skill Defaults

Full 30+ skill table: [docs/gcl-spec.md §8](docs/gcl-spec.md#8-per-skill-defaults)

| Level | max_iter | Key Risk |
|-------|:--------:|----------|
| **required** | 2 | Data destruction / instance deletion / irreversible |
| **recommended** | 3 | Resource deletion / config changes; batch messaging; bucket/FS delete |
| **optional** | 5 | Read-only audit / diagnostic |

### 12.8 Anti-Patterns (banned)

Shared context G+C, subjective scoring, unbounded loop, **Critic seeing user request**, silently downgrading on Safety fail, trace not persisted, Critic mutating resources, trace leaking secrets. Full list: [`docs/gcl-spec.md` §9](docs/gcl-spec.md#9-anti-patterns-banned).

### 12.9 Shared Runner & Rollout

Cross-skill: delegate via product `SKILL.md` **Delegation Rules** to [`alicloud-gcl-runner-ops`](alicloud-gcl-runner-ops/SKILL.md). New-skill GCL artifacts: [`alicloud-skill-generator/references/gcl-rollout-spec.md`](alicloud-skill-generator/references/gcl-rollout-spec.md).

---

## 13. Runtime Artifacts Policy

| Rule | Requirement |
|------|-------------|
| **R1** | Execution-time outputs MUST live under `${SKILLS_DIR}/.runtime/` or gitignored path |
| **R2** | **Do NOT** `git add` runtime artifacts. If user asks, STOP, list paths + risks, wait for explicit confirmation |
| **R3** | Committed content = templates only (e.g. `environments/*.example`) |

**Layout** (`${SKILLS_DIR}/.runtime/`):

```text
audit/ · traces/ · sessions/ · logs/ · metrics/ · memory/ · reflexion/ · token/
```

Cleanup: `make runtime-clean` (dry-run) / `make runtime-clean-apply` / `make memory-maintain-apply`

---

## 14. CLI Usage Protocol (MANDATORY)

Before executing ANY unfamiliar `aliyun` CLI command: verify parameter formats via `--help`. **Never guess.**

### 14.1 Alibaba Cloud CLI Parameter Conventions

| Pattern | Wrong ❌ | Correct ✅ |
|---------|---------|-----------|
| Single instance ID | `--InstanceId i-xxx` | `--InstanceId.1 i-xxx` |
| Multiple instance IDs | `--InstanceIds i-xxx,i-yyy` | `--InstanceIds '["i-xxx","i-yyy"]'` |
| Tag key-value | `--Tag.Key=env --Tag.Value=prod` | `--Tag.1.Key=env --Tag.1.Value=prod` |

Full reference: [docs/cli-usage-patterns.md](docs/cli-usage-patterns.md)

### 14.2 Error Recovery

1. **STOP** — Do not retry with guessed parameters
2. **READ** — Check error message for hints
3. **HELP** — `aliyun <product> <action> --help`
4. **FIX** — Correct format
5. **RETRY** — Execute with verified parameters

### 14.3 Cross-Platform Date Compatibility (MANDATORY)

Always use dual-branch fallback pattern:

```bash
# 1-hour offset (Linux | macOS)
$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)
```

Never hardcode single-platform `date -d` or `date -v`.

---

## 15. Runtime Harness Integration (MANDATORY for new skills)

**Terminology**: **Runtime Harness** is canonical (wrapper-first CLI, traces, optional self-repair). Legacy paths use `skillopt_*` — see [docs/runtime-harness-glossary.md](docs/runtime-harness-glossary.md).

**Full guide**: [`docs/harness-integration-guide.md`](docs/harness-integration-guide.md)

### 15.1 What It Does

| Capability | Description |
|-----------|-------------|
| **Auto-Repair** | Matches error codes (Throttling, InvalidParameter, NotFound, Forbidden, Timeout, QuotaExceeded) to product-specific fixes |
| **Pre-Execution Optimization** | Adjusts params based on historical runtime metrics |
| **Runtime Metrics** | Persists error rates and repair success counts |

### 15.2 Required Files

Every new `alicloud-*-ops` skill needs all 4:

| File | Purpose | Template |
|------|---------|----------|
| `scripts/harness-lib.sh` | Product overlay — auto-repair, error handlers (canonical) | [`alicloud-ecs-ops/scripts/harness-lib.sh`](alicloud-ecs-ops/scripts/harness-lib.sh) |
| `references/skillopt-integration.md` | Documentation | [`alicloud-ecs-ops/references/skillopt-integration.md`](alicloud-ecs-ops/references/skillopt-integration.md) |
| `scripts/[product]-harness-wrapper.sh` | **Preferred** wrapper entry | Generated by [`.scripts/gen-harness-shims.sh`](.scripts/gen-harness-shims.sh) |
| `scripts/[product]-skillopt-wrapper.sh` | Legacy wrapper shim | [`alicloud-ecs-ops/scripts/ecs-skillopt-wrapper.sh`](alicloud-ecs-ops/scripts/ecs-skillopt-wrapper.sh) |
| `test-skillopt-backward-compatibility.sh` | Backward compatibility test | [`alicloud-ecs-ops/test-skillopt-backward-compatibility.sh`](alicloud-ecs-ops/test-skillopt-backward-compatibility.sh) |

### 15.3 Product-Specific Customization

| Placeholder | Example (MongoDB) |
|-------------|-------------------|
| Log prefix tag | `[MongoDB-SkillOpt]` |
| JSON param list | `InstanceIds SecurityIpList Tag DBInstanceIds` |
| Resource check API | `aliyun dds DescribeDBInstances` |
| RAM policy action | `dds:*` |

### 15.4 Quality Gates

| Check | Criterion | Severity |
|-------|-----------|----------|
| Q1 | `scripts/harness-lib.sh` exists; `scripts/skillopt-lib.sh` symlink present; `references/skillopt-lib.sh` absent | P0 |
| Q2 | Wrappers source `"$SCRIPT_DIR/harness-lib.sh"` (not `../references/`) | P0 |
| Q3 | lib.sh complete, not truncated | P0 |
| Q4 | Wrapper uses real `"` | P0 |
| Q5 | RAM policy uses correct product action prefix | P0 |
| Q6 | Test script verifies native CLI still works | P0 |

### 15.5 Currently Integrated Skills

39 product skills have full Runtime Harness integration: **ack, ask, actiontrail, alb, advisor, agentrun, bailian, billing, cen, cms (hardened/v2.5.0), das, dts, eci, ecs, eip, elasticsearch, ess, fc, kms, mongodb, nas, nat, oss, polar-mysql, polar-oracle, polar-postgresql, pts, ram, rds, redis, resourcemanager, sas, slb, sls, sms, terraform, voice, vpc, waf**.

Full framework: [`alicloud-runtime-harness-ops`](alicloud-runtime-harness-ops/SKILL.md)

### 15.6 Production-Grade Hardening Standard

Five critical rules (see full spec + error patterns at [docs/harness-integration-guide.md §15.6](docs/harness-integration-guide.md#156-production-grade-hardening-standard)):

1. **Parameter Array Integrity**: Use shell arrays, not space-delimited strings
2. **Double-Execution Protection**: Never retry mutating actions (`Put*`, `Delete*`); use `skillopt_is_readonly_action()`
3. **Retries Cap**: Hard cap on dynamic retry optimization (e.g., max 6)
4. **Shell Strict Mode**: `${MY_ARRAY[@]+"${MY_ARRAY[@]}"}` for optional arrays
5. **Output Passthrough**: Capture + return `aliyun` output on successful repair

### 15.7 Langfuse Tracing Lessons

L1–L11 implementation checklist, B/C/D/E specs, multi-skill session ID validation standard: [docs/harness-integration-guide.md §15.7](docs/harness-integration-guide.md#157-langfuse-tracing-integration-lessons-mandatory-for-skillopt-updates)

### 15.8 Wrapper-First Execution Rule (MANDATORY)

> **⛔ P0 GLOBAL PRE-EXECUTION INTERCEPT — must run BEFORE any `aliyun` invocation**

When a user request involves any Alibaba Cloud product with a known wrapper (**oss, ecs, cms, rds, redis, slb, mongodb, vpc, ack**):

1. Check whether `scripts/*-harness-wrapper.sh` or `scripts/*-skillopt-wrapper.sh` exists
2. **If wrapper exists**: execute via wrapper — `cd alicloud-<product>-ops && ./scripts/<product>-harness-wrapper.sh <verb> [args]`
3. **Only if wrapper confirmed missing**: fall back to native `aliyun <product>` CLI

**Checklist** (every `aliyun` call):

| # | Check | Action |
|---|-------|--------|
| 1 | Did I just type `aliyun <product> ...`? | STOP — locate wrapper first |
| 2 | Does wrapper exist? | If yes: **must** use wrapper (prefer harness) |
| 3 | Running from repo root? | `cd` first |
| 4 | `HARNESS_SESSION_ID` set? | `export HARNESS_SESSION_ID="sess-$(uuidgen)"` |
| 5 | `ALIBABA_CLOUD_ACCESS_KEY_*` checked? | HALT if missing |

**Bypass exception**: wrapper confirmed missing + `skillopt-lib.sh` cannot be sourced. Log via `[SKILLOPT-WRAPPER] not found ...`

**Banned**: "read-only doesn't need wrapper", "faster to call aliyun directly", "wrapper failed before".

### 15.8.1 Pre-Execution Wrapper Check

```bash
product="${1#aliyun }" && product="${product%% *}"
harness_path="alicloud-${product}-ops/scripts/${product}-harness-wrapper.sh"
legacy_path="alicloud-${product}-ops/scripts/${product}-skillopt-wrapper.sh"
if [[ -f "$harness_path" ]]; then
  exec "${ALIYUN_SKILLS_ROOT}/$harness_path" "${@:2}"
elif [[ -f "$legacy_path" ]]; then
  exec "${ALIYUN_SKILLS_ROOT}/$legacy_path" "${@:2}"
else
  exec aliyun "$@"
fi
```

### 15.9 Output Capture Rule (MANDATORY)

When `SKILLOPT_ENABLED != "true"` (default), `skillopt_wrap()` MUST use `skillopt_run_aliyun()` which captures stdout/stderr to `SKILLOPT_LAST_OUTPUT`. Direct `aliyun` calls in the disabled branch cause empty Langfuse trace output.

```bash
if [[ "$SKILLOPT_ENABLED" != "true" ]]; then
    skillopt_run_aliyun "$product" "$action" "${SKILLOPT_PARAMS[@]+"${SKILLOPT_PARAMS[@]}"}" || rc=$?
    printf '%s\n' "$SKILLOPT_LAST_OUTPUT"
    skillopt_trace_end "$([[ $rc -eq 0 ]] && echo success || echo failed)" "exit_code_$rc" "$SKILLOPT_LAST_OUTPUT"
    return $rc
fi
```

**Audit**: `grep 'aliyun "$product"' skillopt_wrap()` in the disabled branch = bug.

---

## 16. Execution Memory Index

Every GCL trace is automatically indexed into a JSONL-based execution memory. Full spec: [docs/gcl-spec.md §16](docs/gcl-spec.md#16-memory-index--execution-memory-layer)

| Function | Purpose |
|----------|---------|
| `memory_store(trace)` | Index GCL trace into JSONL (skill, operation) |
| `memory_retrieve(skill, operation, top_k)` | Return most recent `top_k` entries |
| `memory_maintain(memory_root, keep_days, apply)` | Prune old entries; dry-run supported |

**Non-fatal guarantee**: Memory store failures log as `[WARN]` and never change runner exit code.

### 16.8 Platform Ownership — Product Skills Excluded

| Owner | Responsibility |
|-------|----------------|
| **Product skill** | Runbook, GCL gate artifacts, SkillOpt wrapper |
| **Shared runtime** | `memory_store`/`memory_store_lite`, trace persist, Reflexion extract/store, TTL maintain |
| **Repo / ops tooling** | `reflexion report`, memory maintain, offline LLM summarization |

Product skills **MUST NOT** document skill-owned memory/Reflexion/learning workflows as part of the skill contract.

---

## 17. Reflexion Memory (Layer 2)

Extracts structured failure patterns from GCL traces into a deduped JSON store. Full spec: [docs/gcl-spec.md §15](docs/gcl-spec.md#15-reflexion-memory)

| Function | Purpose |
|----------|---------|
| `reflexion_extract(trace)` | Extract failure pattern |
| `reflexion_store(pattern)` | Store deduped + count increment |
| `reflexion_retrieve(skill, op, top_k)` | R2 pre-flight traps |
| `reflexion_report()` | Regenerate `docs/failure-patterns.md` |
| `reflexion_maintain(apply)` | Prune patterns (count < 3 → removed) |

**Five failure categories**: `cli_parameter`, `skill_generation`, `cross_skill`, `runtime`, `token_efficiency`

**Non-fatal guarantee**: Same as Layer 1.

**Line budget**: `docs/failure-patterns.md` ≤ 200 lines.
