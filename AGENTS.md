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

**Non-overridable floors**: §0.3 复利工程（Compound Engineering — 每次交付必须沉淀可复用模式）, §4 Development Workflow (Spec→Plan→Implement+TDD+GCL), §8 Security, §12 Safety=0 → ABORT, destructive confirmation, credential non-leakage.

### 0.2 Karpathy Guidelines (MANDATORY)

| # | Rule | Requirement |
|---|------|-------------|
| **K1** | Think before coding | State assumptions; ask when uncertain; surface tradeoffs |
| **K2** | Simplicity first | No speculative features, abstractions, or unrequested config |
| **K3** | Surgical changes | Touch only what the task requires; match existing style |
| **K4** | Goal-driven execution | Define verifiable success criteria; per-step checks; loop until verified |

Canonical skill: `karpathy-guidelines`.

**Banned**: "while I'm here I'll refactor…", "tests can come later", "this needs a general framework…"

### 0.3 复利工程 — Compound Engineering（🔴 最高优先级）

> **⛔ 这是本仓库最重要的工程原则，优先级等同于安全红线。**
>
> **核心理念**：每一次工作不是在"完成一个任务"，而是在"让整个系统变得更强"。当前任务的交付物是副产品，可复用的模式、模板、决策记录才是真正的产出。
>
> **为什么是最高优先级**：没有复利，团队永远在做重复劳动——每个新人从头摸索、每个类似问题从头讨论、每个架构决策丢失上下文。

**核心模式**（完整规范 + 决策表见 §18）：

| 模式 | 一句话 |
|------|--------|
| **场景驱动** | 从用户接入场景出发，先定义「做完后的效果」 |
| **价值量化** | 每阶段「一句话 + 具体数字」描述效果 |
| **统一入口** | `docs/ARCHITECTURE.md` 是唯一权威架构入口 |
| **废弃即删除** | 被替代的文档直接删除（git 历史可回溯） |
| **三层文档** | ARCHITECTURE → SPEC → PLAN，每层有明确读者 |
| **决策记录** | 关键设计决策记录在 ARCHITECTURE.md 的决策表中 |

**每完成一个任务，必须自问**：

- 方法/模板能不能下次直接复用？
- 决策有没有记录到决策表？
- 有没有废弃文档该删没删？
- 下次有人做类似的事，能否通过 ARCHITECTURE.md 快速找到所有上下文？

### 0.4 CodeGraph Integration (MANDATORY)

> CodeGraph (<https://github.com/colbymchenry/codegraph>) is the repository's symbol knowledge graph,
> indexing all symbols, edges, and file relationships in SQLite.

| # | Rule | Detail |
|---|------|-------|
| **CG1** | **CodeGraph first for code understanding** | Prefer `codegraph_explore` over grep/Read — one call returns symbol source + call chain + impact radius |
| **CG2** | **Sync after every change** | Run `codegraph sync` after any code add/modify/delete to keep the knowledge graph current |
| **CG3** | **Pass `projectPath` for sub-projects** | When querying a sub-project with its own `.codegraph/` (e.g. monorepo services), pass `projectPath` explicitly |

```bash
codegraph sync
```

### 0.5 Product Skill Mission

Each `alicloud-*-ops` skill is a **domain colleague** delivering through **Harness Engineering** — not a memory or learning subsystem.

| Pillar | Mission | Repo expression |
|--------|---------|-----------------|
| **Domain colleague** | Partner: product expertise + assembled context | `core-concepts.md`, Well-Architected, Pre-flight, `{{user.*}}` / `{{env.*}}` / `{{output.*}}`, UX transparency |
| **Harnessed delivery** | Explainable, observable outcomes | GCL rubric + `prompt-templates.md` (§12), wrapper-first ([quickref](docs/runtime-harness-quickref.md)), diagnostic logging |

**Collaboration posture** (bounded autonomy):

| Role | Behavior |
|------|----------|
| **Colleague** | Ask once, reuse variables; no credential leakage |
| **Partner** | Delegate cross-product via Delegation Rules; share `HARNESS_SESSION_ID`; single responsibility |
| **Subordinate** | HALT on pre-flight fail, missing creds, or rubric-exceeded risk; destructive ops require explicit confirmation (§8) |

**Non-goals**: Layer 1/2 memory indexing, Reflexion report generation, LLM evolution pipelines — platform-owned (§16.8).

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
│   ├── prompt-examples.md            # User-facing NL prompt examples (copy-paste)
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

## 2.1 references/ Naming & Placeholder Conventions (MANDATORY)

| Rule | Requirement |
|------|-------------|
| **R-N1 Prompt docs** | Two distinct files, do **not** mix them: `prompt-templates.md` = GCL Generator/Critic/Orchestrator templates (engine-internal); `prompt-examples.md` = user-facing natural-language prompt examples users can copy-paste. Never name a user doc `prompts.md`. |
| **R-N2 ASCII filenames** | `references/` filenames MUST be ASCII (no Chinese / full-width chars), e.g. `sg-secops-inspection.md` NOT `sg-secops巡检.md`. Non-ASCII names break Agent reads and script references. |
| **R-N3 Placeholder integrity** | Every `{{user.*}}` / `{{env.*}}` / `{{output.*}}` MUST have both braces. Pre-merge MUST `grep -nE '\{\{[^}]*$\|\{\{[^}]*\}?[^}]*$'` (or visually scan) to catch unclosed `{{user.check_id}` style typos — they produce broken commands at execution. |

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

## 4. Mandatory Development Workflow (STRICT — NON-NEGOTIABLE)

> **⛔ 最高优先级开发规范。所有 task 的开发都必须严格遵守以下流程，无例外。**
>
> 任何直接跳过 Spec / Plan 阶段的代码开发都是违规行为，必须中止并重来。

### 4.1 The Iron Rule: Spec → Plan → Implement

Every development task in this repo MUST proceed in exactly this order:

```text
┌─────────┐     ┌─────────┐     ┌──────────────┐
│   SPEC  │ ──▶ │  PLAN   │ ──▶ │  IMPLEMENT   │
│ (What & │     │ (How &  │     │ (TDD + GCL)  │
│  Why)   │     │  Steps) │     │              │
└─────────┘     └─────────┘     └──────────────┘
   MUST            MUST              ONLY HERE
  EXIST            EXIST            write code
```

**禁止项（Banned）：**

- ❌ 没有 Spec 就写 Plan
- ❌ 没有 Plan 就写实现代码（"先写代码再说" / "边写边想"）
- ❌ 把 Plan 和 Implement 合并跳过 Plan
- ❌ 用代码反推 Spec / Plan（事后补文档不算 Spec）

### 4.2 Phase Definitions

| Phase | Artifact | Must Answer | Gate |
|-------|----------|------------|------|
| **SPEC** | `SPEC.md` (or `.omo/plans/*` spec block) | What are we building & why? What problem? Success criteria? Scope boundaries (in/out)? | No artifact → no Plan |
| **PLAN** | `PLAN.md` (or `.omo/plans/*` plan block) | How? Step-by-step tasks, dependencies, verification checkpoints per step, risk assessment | No artifact → no code |
| **IMPLEMENT** | Code + tests | Execute the plan under TDD + GCL discipline | Tests green + GCL pass |

### 4.3 TDD During Implement (MANDATORY)

In the Implement phase, **TDD is non-negotiable** — see the Iron Law:

- **RED** → write a failing test first; run it; MUST fail.
- **GREEN** → write minimal code to pass; run; MUST pass.
- **REFACTOR** → clean up; tests stay green.
- Any production code written before its failing test MUST be deleted and restarted.

Combined with GCL (§12), every cloud operation also runs through the Generator ↔ Critic adversarial loop.

### 4.4 Superpowers Skill Binding

This workflow is realized through the Superpowers skill suite:

| Phase | Superpowers Skill |
|-------|-------------------|
| SPEC | `superpowers:writing-plans` (spec mode) / `superpowers:brainstorming` |
| PLAN | `superpowers:writing-plans` (plan mode) |
| IMPLEMENT | `superpowers:subagent-driven-development` + `superpowers:test-driven-development` + `superpowers:executing-plans` |

> When a task arrives, the default reflex is **NOT** "open the editor". It is **"write the Spec, get alignment, then Plan"**.

### 4.5 Enforcement

| If You See | Action |
|------------|--------|
| Task starts with code, no Spec/Plan | STOP. Return to SPEC. Do not proceed. |
| Spec exists but Plan skipped | STOP. Write PLAN. Do not write code. |
| "This is small, no need for Spec/Plan" | Still required. Exceptions only: < 5 line typo/comment fixes (see §git-worktree exception). |
| Test written after code | Delete code. TDD restart. |

**This rule overrides default agent heuristics (priority tier 5) and any "just do it" impulse. Only explicit user waiver in-session can bypass it, and the waiver MUST be logged in the task trace.**

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

### 8.1 Destructive Ops Hard Rule (MANDATORY — no exceptions)

> **任何破坏性 op 的执行都必须得到人工显式确认才能执行。这是强规则，要严格遵守。**

| 项 | 要求 |
|---|---|
| **范围** | 所有 `Delete*` / `Remove*` / `drop*` / `Release*` / `Flush*` / `TRUNCATE` / `destroy` / `shutdown*` / `deleteMany({})` / `updateMany({})` / `_delete_by_query` with `match_all` / `ossutil rm` / `ResetAccountPassword` 等可写不可逆或破坏数据的 op |
| **确认方式** | 必须**用户在当前会话中明确说**「同意执行 XX」/「确认」/「go」等，不能依赖上下文推断、过去会话状态、或任何间接信号 |
| **Trace 要求** | 必须在 trace 中包含 `user_confirmation` 字段，含用户原话或金句摘要 |
| **默认值** | **默认拒绝**——未拿到确认时 GCL 必须 ABORT，不允许静默执行 |
| **Agent 自主决断** | **禁止**：Agent 不得自主跳过确认步骤；不得用 "log as warning" 代替确认；不得用 dry-run 结果代替真实执行的确认 |

### 8.2 Worked Examples & Documentation Safety (MANDATORY)

> **任何 skill 的 Worked Examples / Usage Examples / 代码演示片段都不得包含破坏性 op 作为演示。** 这是文档层面的安全约束。

| 项 | 要求 |
|---|---|
| **Example 1（默认）** | 必须是**只读操作**（`Describe*` / `List*` / `Get*` / `GetBucket*`） |
| **Example 2（可选）** | 必须是**安全写操作**（`CreateAccount` / `CreateUser` / `CreateLoginProfile` / `CreateKey` / `AllocateEipAddress` 1Mbps 按量 / `CreateInstance` 最小 spec 立即释放） |
| **禁止** | Example 中出现 `Delete*` / `Remove*` / `drop*` / `Release*` / `Flush*` / `TRUNCATE` / `destroy` 等任何破坏性 op |
| **成本警示** | 任何"创建"类 Example 必须明确标注 spec / 计费方式 / 释放方法，避免默认规格产生高额账单 |
| **适用范围** | 所有 skill 的 SKILL.md / references/*.md / examples / snippets / test fixtures |
| **检測** | pre-merge self-review (R2 / F5) 必须扫所有 Example 段是否含破坏性 op；发现即 FAIL |
| **迁移成本** | 现有 Example 含破坏性 op 的 skill 列入 backlog，逐一迁移到「只读 + 安全写」二例结构 |

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

**详细规范**：

- 完整 check tables + Self-Review Record 模板：[`docs/post-update-self-review.md`](docs/post-update-self-review.md)
  - §11.0 Skill Capability Matrix Sync（MANDATORY） — `SKILL-MATRIX.md` 是单一事实源
  - §11.1 Regression Testing（MANDATORY） — RT-1–RT-6 agent checklist + Skill Change Critic Gate
- 双轨测试 + 凭证不可用处理：[`docs/dual-track-testing.md`](docs/dual-track-testing.md)

---

## Key References

| Document | Description |
|----------|-------------|
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | **统一架构入口** — Agent Runtime 演进路线图、Phase 1/2/3 规划 |
| `alicloud-skill-generator/SKILL.md` | Meta Skill generator — full workflow, P0/P1 checklist, Token Efficiency rules |
| `alicloud-skill-generator/references/alicloud-skill-template.md` | Canonical SKILL.md template |
| [`docs/gcl-spec.md`](docs/gcl-spec.md) | **GCL full spec** — roles, rubric, loop flow, trace schema, anti-patterns, §8 Per-Skill Defaults |
| [`docs/post-update-self-review.md`](docs/post-update-self-review.md) | Self-review spec — check tables, verification scripts, dedup procedures |
| [`docs/dual-track-testing.md`](docs/dual-track-testing.md) | Dual-track testing (Track 1 dry-run / Track 2 真实环境) + `[BLOCKED:no-credentials]` 处理 |
| [`docs/generator-critic-loop.md`](docs/generator-critic-loop.md) | GCL 速查清单 — roles / rubric / loop flow / termination |
| [`docs/harness-integration-guide.md`](docs/harness-integration-guide.md) | Runtime Harness integration — self-repair, Langfuse, §15.6 hardening rules, §15.7 Langfuse lessons |
| [`docs/token-efficiency-strategy.md`](docs/token-efficiency-strategy.md) | Always-loaded vs lazy-loaded methodology, audit checklist |

> **When specs conflict**: §0 (instruction priority, Karpathy, product mission) and repo-wide rules win for **agent behavior**. For **product skill authoring** field-level templates, `alicloud-skill-generator/SKILL.md` is authoritative.

---

## 12. Generator-Critic-Loop (GCL)

完整规范已下沉到 [`docs/generator-critic-loop.md`](docs/generator-critic-loop.md)。包含：

- **Roles**：G / H / C / O 四角色
- **Critic Test & Regression Assessment**（MANDATORY）
- **Rubric Dimensions**：≥5 维度（Correctness / Safety / Idempotency / Traceability / Spec Compliance）
- **Loop Flow**：H pre-check → G execute → C critique → O decide
- **Termination**：PASS / MAX_ITER / SAFETY_FAIL / HALLUCINATION_ABORT
- **Trace Audit**：每 run 必落盘 JSON，含脱敏
- **Skill Classification**：30+ skill 表，按 risk 分 required/recommended/optional
- **Anti-Patterns**：禁用模式清单

**完整规范**：[`docs/gcl-spec.md`](docs/gcl-spec.md)（含 trace schema、per-skill rubric 配置）

**速查入口**：[`docs/generator-critic-loop.md`](docs/generator-critic-loop.md)

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

**速查清单** (skill 作者必备)：[`docs/runtime-harness-quickref.md`](docs/runtime-harness-quickref.md) — 文件、Q1-Q6 质量门、Wrapper-First P0 规则、输出捕获。

**完整规范**：[`docs/harness-integration-guide.md`](docs/harness-integration-guide.md) — Langfuse L1-L11、生产级加固、错误模式库。

**当前已集成 skills**：40 个产品 skill 已有完整 Harness 集成 (`ack, ask, actiontrail, alb, advisor, agentrun, bailian, billing, cen, cms, das, dns, dts, eci, ecs, eip, elasticsearch, ess, fc, kms, mongodb, nas, nat, oss, polar-mysql, polar-oracle, polar-postgresql, pts, ram, rds, redis, resourcemanager, sas, slb, sls, sms, terraform, voice, vpc, waf`)。

**Framework entry**：[`alicloud-runtime-harness-ops`](alicloud-runtime-harness-ops/SKILL.md)

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

Extracts structured failure patterns from GCL traces into a deduped JSON store. Full spec: docs/gcl-spec.md §15

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

---

## 18. Compound Engineering（复利工程）

> **核心原则**：每次设计/开发不只解决当前问题，还要沉淀可复用的模式、模板和决策记录，让下一次同类工作更快更好。

### 18.1-§18.5 速查入口

完整规范已下沉到 [`docs/compound-engineering.md`](docs/compound-engineering.md)。包含：

- 5 种架构设计模式（场景驱动/价值量化/场景对比/双模式架构/向后兼容）
- 4 种文档治理模式（统一入口/废弃即删除/三层文档/引用而非重复）
- 关键设计决策表（6 项架构级决策）
- SPEC / PLAN 文档模板
- 复利检查清单（每次任务完成必过）

### 18.6 文档/配置引用校验（可复用经验）

> 修复"失效的相对链接"类任务时反复踩坑，沉淀为通用校验规范，避免下次重蹈。

**DL-R1 — GitHub 锚点 slug 算法（🔴 易错）**
Markdown 标题转 GitHub 锚点的规则：`lower` → 删除所有**非** `[字母|数字|空格|连字符]` 的字符（含 `.` `&` `(` `)` `/` `—` `：` `≥` `🔴` `（）`，但**保留 CJK/Unicode 字母**）→ 每个空格替换为一个 `-`。

- **关键陷阱**：`&`、`—`、`/` 等被**删除**而非折叠，其两侧的空格保留，因此会产生**双连字符** `--`。例如 `### 2.1 Critic Test & Regression Assessment (MANDATORY)` → `21-critic-test--regression-assessment-mandatory`；`# Generator-Critic-Loop (GCL) — Implementation Spec` → `generator-critic-loop-gcl--implementation-spec`。这两个 `--` 是**正确**的，不是 broken anchor。
- **反模式**：用"折叠为单 `-`"模型校验锚点，会误报大量 broken link。任何锚点校验脚本必须实现上面的精确算法，并跳过围栏代码块（` ``` ` / `~~~`）和 `{{...}}` 模板占位符。

**DL-R2 — 校验范围必须覆盖非 `.md` 表面**
"相对链接"不止出现在 `.md` → `.md`。`*.yaml` / `*.json` / `*.toml` / `*.sh` 中的文档引用（如 `example-config.yaml` 注释里的 `references/user-experience-spec.md`、wrapper 脚本里的 `SKILL.md` 路径）同样会失效。 scanners 若只扫 `.md`，会漏掉 `assets/example-config.yaml` 这类死链。校验脚本应同时遍历 yaml/yml/json/toml，并对 `.sh` 用"脚本目录 / 仓库根 / `$SKILL_DIR`(即 `alicloud-X-ops/` 根)"三向解析来判定是否真缺失。

**DL-R3 — 扇出验证会产生假阳性，必须以真值为准**
多 Agent 并行校验时，验证 Agent 若对目标系统规则（如上面 slug 算法、或路径基准目录）有错误心智模型，会报告大量"broken"。**落地前必须独立复算**：直接 `Path.resolve()` 解析真实路径、直接运行真实 slug 算法，而不是仅凭 Agent 断言动手修复——在假阳性上"修复"会反过来制造 broken link。

**DL-R4 — 路径深度基线**
相对路径基准目录 = 链接所在文件的目录。位于 `alicloud-X-ops/assets/`（比 skill 根深一层）的引用，到仓库根的 `alicloud-Y-ops/references/...` 需要 `../../`；位于 `alicloud-X-ops/SKILL.md`（skill 根）则只需 `../`。深度算错是常见的"看似修复实则仍 broken"来源。

### 18.7 FinOps/ML 模块开发复盘（`alicloud-aiops-ml` 试点沉淀）

> 6 轮迭代（a35b0af → 1c007be）的实战经验。本项目未来添加 Python 工具模块（尤其是涉及数值计算 / subprocess / 并发）时必读。

**FM-R1 — 数值算法的 RED 测试必须包含 4 项不变性**

向量化的距离/归一化/矩阵运算，RED 测试必须有：

- ✅ **对称性**：`A == A.T`（距离矩阵、协方差矩阵）
- ✅ **对角线**：`diag(A) == 0`（自距离为零）
- ✅ **vs 朴素 O(n²) 参考实现**：`np.testing.assert_allclose(..., atol=1e-10)` —— 朴素循环慢但正确，是数值正确性的 ground truth
- ✅ **边界**：empty / single element / identical / well-separated

反模式：用 `atol=1e-7` 觉得"够严"。浮点恒等式（如 `‖a-b‖² = ‖a‖² + ‖b‖² - 2a·b`）会产生 ~1e-16 负零误差，`np.sqrt(1e-16)` 给出 `1e-8` —— 会被 `atol=1e-7` 放过但破坏对角线对称性。

**FM-R2 — 接口破坏要么显式文档要么给默认值**

新增必填参数（如 `enrich_tags(..., account_id)`）的两种合规做法：

```python
# 选项 A：默认值 + DeprecationWarning（推荐，向后兼容）
def enrich_tags(resources, region, account_id=None):
    if account_id is None:
        warnings.warn("account_id required in next release", DeprecationWarning, stacklevel=2)
        account_id = os.environ.get("ALIBABA_CLOUD_ACCOUNT_ID", "")

# 选项 B：commit message 显式写 BREAKING CHANGE（破坏 OK，但必须声明）
# Commit message 必须含 "BREAKING CHANGE: ..." 段，便于 grep
```

反模式：静默把必填参数加到中间位置，无 commit 标记，无测试更新——调用方必崩但发现得很晚。

**FM-R3 — 性能测试用绝对上界，不用相对比较**

```python
# ✅ 绝对上界（CI 抖动不影响）
def test_vectorized_dbscan_completes_quickly():
    elapsed = measure_time(lambda: cluster_resources(resources, features))
    assert elapsed < 2.0, f"n=500 took {elapsed:.2f}s; expected <2s"

# ❌ 相对比较（CI 抖动会假阳性 / 假阴性）
def test_vectorized_dbscan_faster_than_legacy():
    assert new_elapsed < legacy_elapsed  # 新实现有 import overhead，n 小时反慢
```

**FM-R4 — `except Exception` 必须配套 logging + 文档意图**

```python
# ✅ 标准格式
try:
    results[name] = future.result()
except Exception as e:                    # 只捕 Exception，不吞 BaseException
    logger.warning("Collector %s failed for region=%s: %s", name, region, e)
    results[name] = []
    failures[name] = e                    # 记录失败供后续分析

if failures and len(failures) == len(collectors):
    raise RuntimeError(f"All collectors failed: {sorted(failures)}")  # 全失败时显式抛
```

反模式：裸 `except Exception: pass` —— 调试时找不到失败原因，`Ctrl+C` 也被吞（生产环境大坑）。**KeyboardInterrupt / SystemExit 自动传播**（它们是 BaseException 子类），无需额外处理。

**FM-R5 — 向量化性能优化的 4 步协议**

```
1. 基线测量：time.perf_counter() 实测原版耗时（必须有数，不是"感觉慢"）
2. RED 测试断言"绝对上界"：elapsed < 2.0（不用相对比较）
3. 实现：prefer O(n²) 算法 → numpy einsum/cdist/identity trick
4. 量化对比：新耗时 / 旧耗时 + 峰值内存
```

实测案例（`alicloud-aiops-ml/dbscan_cluster.py`）：

- DBSCAN n=1000: 5.92s → 0.11s (**52x**)
- 距离矩阵内存: 30.5MB → 23.0MB (**-25%**)

**FM-R6 — 优化后必须删除 dead code**

性能对比保留下来的旧函数（如 `_simple_dbscan`）如果不删：

- 维护负担：以后 bugfix 只改新版，旧版漂移
- 调用歧义：新人不知道该用哪个

判断标准：在主代码路径上 grep，确认只有测试文件 import。纯测试用 → 删除。

**FM-R7 — 4 轮 review 的共同规律**

`alicloud-aiops-ml` 经过 6 轮 review（3 轮 bug fix + 1 轮 perf + 2 轮 perf review），发现一个反直觉的模式：

> **每一轮 review 都只能找到「前面 round 引入的新 bug」**。Round 3 修复的 ARN 硬编码其实是 Round 1 重构时引入的；Round 4 的 H2 浮点噪声是 Round 4 自家向量化引入的。

结论：**N+1 轮 review 的价值递减但不为零**——至少还能捕获 self-introduced bug。建议任何 Python 工具模块至少做 2 轮 review（功能正确性 + 安全性/性能），超过 3 轮 ROI 递减。

**FM-R8 — `code-reviewer` agent 不可用时的 fallback 协议**

OpenCode 当前 session 没有 `code-reviewer` subagent_type。Fallback 流程：

1. 仍按 skill 协议调用一次（验证不可用）
2. 失败后**自己 review**，但保持输出格式统一：CRITICAL/HIGH/MEDIUM/LOW + file:line 引用 + fix 建议
3. 不要"为了通过"放过真问题
4. **触发第二轮**（自审）捕获第一轮漏掉的，特别是 self-introduced bug

反模式：跳过 review 直接 ship。
