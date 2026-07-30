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

### 0.4 CodeGraph MCP — Code Understanding Priority (MANDATORY)

> **CodeGraph MCP 是代码理解的第一入口**。它提供结构化的符号索引、调用链分析和影响半径计算，
> 比传统的 grep/Glob/Read 组合更精确、更高效。**始终优先使用 CodeGraph MCP，grep 仅作 fallback。**

**可用工具**：

| 工具 | 用途 | 典型场景 |
|------|------|---------|
| `mcp__codegraph__sync` | 同步知识图谱到最新状态 | **每次代码修改后执行**，确保索引与磁盘一致 |
| `mcp__codegraph__search_code` | 按符号名/内容搜索 | "这个函数在哪里定义的？" |
| `mcp__codegraph__get_symbol_details` | 获取符号详情（定义、引用、调用链） | "谁调用了这个函数？影响范围多大？" |
| `mcp__codegraph__query_code` | 结构化查询代码关系 | "这个模块依赖哪些其他模块？" |

**使用规范**：

| # | Rule | Detail |
|---|------|-------|
| **CG1** | **CodeGraph MCP 优先** | 任何代码理解任务（查找定义、追踪引用、分析调用链、评估影响范围）**必须先尝试 CodeGraph MCP**，只有 CodeGraph 无法满足时才 fallback 到 grep/Glob/Read |
| **CG2** | **Sync before use** | 在查询 CodeGraph 之前，**必须先执行 `mcp__codegraph__sync`** 同步索引，确保查询结果反映最新代码状态 |
| **CG3** | **Grep 作为 fallback** | 以下情况使用 grep/Glob/Read：CodeGraph MCP 不可用/超时、搜索结果为空（可能索引未覆盖）、需要文本正则匹配（非结构化搜索）、需要读取文件完整内容进行编辑 |
| **CG4** | **Change → Sync → Verify** | 每次代码修改后必须：1) `mcp__codegraph__sync` 更新索引 → 2) 用 CodeGraph 验证修改的一致性（引用未断裂、符号未丢失） |

**决策流程**：Sync → CodeGraph MCP 查询 → 成功则用结果，失败则 fallback Grep/Glob/Read。

**禁止项（Anti-patterns）**：
- ❌ 跳过 CodeGraph Sync，直接用 grep 搜索代码
- ❌ CodeGraph 返回空结果后不 fallback 到 grep，直接声称"符号不存在"
- ❌ 修改代码后不执行 Sync，导致后续 CodeGraph 查询返回过期数据
- ❌ 把 CodeGraph 用于文本正则匹配（它不是搜索引擎，是结构化知识图谱）

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

### 4.4 Enforcement

| If You See | Action |
|------------|--------|
| Task starts with code, no Spec/Plan | STOP. Return to SPEC. Do not proceed. |
| Spec exists but Plan skipped | STOP. Write PLAN. Do not write code. |
| "This is small, no need for Spec/Plan" | Still required. Exceptions only: < 5 line typo/comment fixes (see §git-worktree exception). |
| Test written after code | Delete code. TDD restart. |

**This rule overrides default agent heuristics (priority tier 5) and any "just do it" impulse. Only explicit user waiver in-session can bypass it, and the waiver MUST be logged in the task trace.**

---

## 5. Idempotent Provisioning

Probe → install only if missing → execute. Use `command -v` checks before installation commands.

---

## 6. Security Constraints

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
pip install -r alicloud-gcl-runner-ops/requirements.txt   # pyyaml + pytest
python3 -m unittest discover -s alicloud-gcl-runner-ops/scripts
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

完整规范：[`docs/gcl-spec.md`](docs/gcl-spec.md) (roles/rubric/loop/trace) · 速查：[`docs/generator-critic-loop.md`](docs/generator-critic-loop.md)

---

## 13. Runtime Artifacts Policy

| Rule | Requirement |
|------|-------------|
| **R1** | Execution-time outputs MUST live under `${SKILLS_DIR}/.runtime/` or gitignored path |
| **R2** | **Do NOT** `git add` runtime artifacts. If user asks, STOP, list paths + risks, wait for explicit confirmation |
| **R3** | Committed content = templates only (e.g. `environments/*.example`) |

**Layout** (`${SKILLS_DIR}/.runtime/`): `audit/ · traces/ · sessions/ · logs/ · metrics/ · memory/ · reflexion/ · token/`

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

STOP → READ error → `--help` → FIX format → RETRY

### 14.3 Cross-Platform Date Compatibility (MANDATORY)

Always use dual-branch fallback pattern:

```bash
# 1-hour offset (Linux | macOS)
$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)
```

---

## 15. Runtime Harness Integration (MANDATORY for new skills)

**Terminology**: **Runtime Harness** is canonical (wrapper-first CLI, traces, optional self-repair). Legacy paths use `skillopt_*` — see [docs/runtime-harness-glossary.md](docs/runtime-harness-glossary.md).

**速查清单** (skill 作者必备)：[`docs/runtime-harness-quickref.md`](docs/runtime-harness-quickref.md) — 文件、Q1-Q6 质量门、Wrapper-First P0 规则、输出捕获。

**完整规范**：[`docs/harness-integration-guide.md`](docs/harness-integration-guide.md) — Langfuse L1-L11、生产级加固、错误模式库。

**当前已集成 skills**：40 个产品 skill 已有完整 Harness 集成 (`ack, ask, actiontrail, alb, advisor, agentrun, bailian, billing, cen, cms, das, dns, dts, eci, ecs, eip, elasticsearch, ess, fc, kms, mongodb, nas, nat, oss, polar-mysql, polar-oracle, polar-postgresql, pts, ram, rds, redis, resourcemanager, sas, slb, sls, sms, terraform, voice, vpc, waf`)。

**Framework entry**：[`alicloud-runtime-harness-ops`](alicloud-runtime-harness-ops/SKILL.md)

---

## 15.8 Wrapper-First 强制一致性（🔴 MANDATORY）

> 关联 SPEC：[docs/spec-invocation-tracking.md](docs/spec-invocation-tracking.md)
> 目标：所有对 `aliyun` / 产品 CLI 的调用都必须走 Wrapper，且产出可观测 trace（含 `invocation` 来源块）；绕过 Wrapper 的调用必须**可见、可追踪、合并前被拦截**。

### 强制规则

1. **单点收口**：所有 `aliyun` 执行（含 lib 内部调用、wrapper fallback）都必须经 `skillopt_run_aliyun`，不得裸调 `aliyun`。
2. **Trace 含 `invocation` 来源块**：Wrapper 路径 trace 的顶层必须含
   ```json
   "invocation": {
     "entrypoint": "wrapper",
     "wrapper": "<product>-harness-wrapper.sh",
     "wrapper_version": "<SKILLOPT_HARNESS_LIB_VERSION>",
     "raw_command": null
   }
   ```
   绕过 Wrapper（被 `require_skillopt_wrapper` 守卫拒绝）的调用由 `skillopt_run_aliyun` 发射 `entrypoint: "direct"` trace（`invocation.raw_command` = 原始命令行），仍返回 64 拒绝。测试上下文（`_SKILLOPT_SKIP_WRAPPER_CHECK=1`）豁免。
3. **每个产品 Skill 必须声明 wrapper-first 且存在 wrapper 脚本**：SKILL.md 须含 `EXECUTION MANDATORY RULE` 块并同时引用 `harness-wrapper` 与 `skillopt-wrapper`；`scripts/` 下须存在 `*-harness-wrapper.sh`。该约束由 `scripts/validate-wrapper-first-docs.sh` 在合并前强制（基线扫描时全部产品 skill 已全绿；该脚本动态统计，新增产品 skill 自动纳入校验）。
4. **库目录豁免**：`alicloud-runtime-harness-ops` 与 `alicloud-skillopt-ops` 是提供 Harness 的库，自身不该有产品 wrapper，门禁跳过这两个目录。

### 数据契约（trace-*.json 顶层）

```json
"invocation": {
  "entrypoint": "wrapper" | "direct",
  "wrapper": "string | null",
  "wrapper_version": "string | null",
  "raw_command": "string | null"
}
```

### 闭环

- 运行时：绕过 Wrapper 的调用 → `direct` trace 落同一存储（`.runtime/traces/`）。
- 静态门禁：`scripts/validate-wrapper-first-docs.sh` 校验每个产品 Skill 的声明 + wrapper 脚本存在性。
- 审计：`scripts/audit-wrapper-coverage.sh <trace_dir>` 扫描 trace，捞出 `entrypoint != "wrapper"` 或缺失 `invocation` 者并 `exit 1`（CI 闭环）。

### Agent 执行自查清单（MANDATORY）

每次执行包含 `aliyun` 的 Bash 命令前，Agent 必须执行以下自查：

| # | 检查项 | 要求 |
|---|--------|------|
| 1 | 命令是否以 `aliyun <product>` 开头？ | 是 → 必须走 wrapper |
| 2 | 是否存在 `alicloud-<product>-ops/scripts/<product>-harness-wrapper.sh`？ | 存在 → **必须**使用 |
| 3 | 是否存在 `alicloud-<product>-ops/scripts/<product>-skillopt-wrapper.sh`？ | 存在且无 harness wrapper → 使用 |
| 4 | 两个 wrapper 都不存在？ | 才允许直接 `aliyun` |

**快速执行模板**：`cd alicloud-<product>-ops && ./scripts/<product>-harness-wrapper.sh <action> [params]`

**或使用辅助脚本**（自动解析产品名并走 wrapper）：`bash scripts/check-wrapper.sh aliyun <product> <action> [params]`

**禁止的借口**："只读操作不需要 wrapper"、"直接调更快"、"之前 wrapper 失败过"。

如需绕过（仅限测试）：设置 `_SKILLOPT_SKIP_WRAPPER_CHECK=1` 环境变量。

---
## 16. Execution Memory & Reflexion (Layers 1-2)

Every GCL trace is indexed into JSONL execution memory; failure patterns are deduped into a reflexion store. Full specs: [§16](docs/gcl-spec.md#16-memory-index--execution-memory-layer) / [§15](docs/gcl-spec.md#15-reflexion-layer-2).

| Layer | Functions | Non-fatal |
|-------|-----------|-----------|
| **L1 Memory** | `memory_store`/`retrieve`/`maintain` | `[WARN]` on failure |
| **L2 Reflexion** | `reflexion_extract`/`store`/`retrieve`/`report`/`maintain` | `[WARN]` on failure |

**Ownership**: Product skills own runbook/GCL gates; shared runtime owns store/persist/maintain; repo tooling owns reports/summaries. Product skills **MUST NOT** document memory/Reflexion workflows.

**L2 categories**: `cli_parameter` / `skill_generation` / `cross_skill` / `runtime` / `token_efficiency`. Budget: `docs/failure-patterns.md` ≤ 200 lines.
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

> 6 轮迭代的实战经验。本项目未来添加 Python 工具模块时必读。

| # | 规则 | 要旨 | 反模式 |
|---|------|------|--------|
| **FM-R1** | 数值 RED 测试 4 不变性 | 对称性 + 对角线 + vs 朴素参考 + 边界 | `atol=1e-7` 放过浮点噪声破坏对称性 |
| **FM-R2** | 接口破坏声明 | 默认值+DeprecationWarning，或 commit 写 BREAKING CHANGE | 静默加必填参数，无标记无测试 |
| **FM-R3** | 性能测试绝对上界 | `elapsed < 2.0`，不用相对比较 | 用"新比旧快"断言，CI 抖动假阳性 |
| **FM-R4** | except Exception 必 logging | `logger.warning(...)` + 记录 failures；全失败时 re-raise | 裸 `except Exception: pass`（吞 Ctrl+C） |
| **FM-R5** | 向量化 4 步协议 | 基线→RED→实现→量化对比 | 无基线直接优化 |
| **FM-R6** | 优化后删 dead code | grep 确认只有测试 import 则删除 | 保留旧函数，漂移 + 歧义 |
| **FM-R7** | review 轮次 ROI | ≥2 轮（功能+安全/性能）；>3 轮 ROI 递减 | 跳过 review |
| **FM-R8** | code-reviewer fallback | 调用→失败→自审→二轮 | 跳过直接 ship |
