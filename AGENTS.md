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
> **为什么是最高优先级**：没有复利，团队永远在做重复劳动——每个新人从头摸索、每个类似问题从头讨论、每个架构决策丢失上下文。复利工程让每一次工作都为下一次工作铺路。

| 模式 | 做法 | 反模式 |
|------|------|--------|
| **场景驱动设计** | 从用户接入场景出发（告警/工单/对话/CI），先定义"做完后的效果" | 从技术分层出发，先画架构图再想用户怎么用 |
| **价值量化** | 每个阶段用"一句话 + 具体数字"描述效果 | 模糊描述（"提升效率"、"优化体验"） |
| **场景对比** | 用"现在 vs 做完后"表格让价值一目了然 | 只描述目标状态 |
| **统一入口** | `docs/ARCHITECTURE.md` 是唯一权威架构入口 | 多个文档各自描述架构，互相矛盾 |
| **废弃即删除** | 被替代的文档直接删除，git 历史可回溯 | 标记 deprecated 堆积，越来越乱 |
| **三层文档** | ARCHITECTURE → SPEC → PLAN，每层有明确读者 | 一个文档包罗万象 |
| **决策记录** | 关键设计决策记录在 ARCHITECTURE.md 中，含理由 | 凭记忆做决策，换人就丢失上下文 |

**每完成一个任务，必须自问**：
- 这次的方法/模板能不能下次直接复用？
- 这次的决策有没有记录在 ARCHITECTURE.md 的决策表中？
- 有没有废弃文档该删没删？
- 下次有人做类似的事，能不能通过 ARCHITECTURE.md 快速找到所有上下文？

详细规范见 [§18 复利工程](#18-compound-engineering复利工程)。

### 0.4 CodeGraph Integration (MANDATORY)

> CodeGraph (https://github.com/colbymchenry/codegraph) 是本仓库的符号知识图谱，
> 通过 SQLite 索引了所有 symbol、边和文件关系。

| # | Rule | Detail |
|---|------|--------|
| **CG1** | **CodeGraph first for code understanding** | 需要理解代码时，优先使用 CodeGraph MCP 工具 (`codegraph_explore`)，而非 grep/Read 循环 — 一次调用即返回符号源码 + 调用链 + 影响半径 |
| **CG2** | **Sync after every change** | 每次代码变更（新增/修改/删除文件）后，必须运行 `codegraph sync` 重新索引，确保知识图谱反映最新代码 |
| **CG3** | **Pass projectPath for sub-projects** | 当需要查询有独立 `.codegraph/` 的子项目（如 monorepo 下的某个 service）时，通过 `projectPath` 参数指定 |

```bash
# Sync 命令
codegraph sync
```

### 0.4 Product Skill Mission

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
| **R-N3 Placeholder integrity** | Every `{{user.*}}` / `{{env.*}}` / `{{output.*}}` MUST have both braces. Pre-merge MUST `grep -nE '\{\{[^}]*$|\{\{[^}]*\}?[^}]*$'` (or visually scan) to catch unclosed `{{user.check_id}` style typos — they produce broken commands at execution. |

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
| **迁移成本** | 现有 Example 含破坏性 op 的 skill 列入 backlog，逐一迁移到「只读 + 安全写」二例结构

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

### 11.0 Skill Capability Matrix Sync (MANDATORY)

`SKILL-MATRIX.md` (repo root) is the single source of truth for "what each skill can do, by capability dimension". On **any** of the following, the matrix MUST be updated in the same commit:

- Add / remove / rename an `alicloud-*` skill directory
- A skill gains or loses a major capability dimension (lifecycle / monitoring / diagnosis / security / governance)

The matrix is the first thing a user reads to pick a skill — staleness there is a user-facing defect, not a doc nit.

### 11.1 Regression Testing (MANDATORY)

**Accuracy over coverage**: A test that would not fail when the change breaks is worse than no test.

| Change touches | Run (minimum) |
|----------------|---------------|
| Any SkillOpt skill | `bash alicloud-<product>-ops/test-skillopt-backward-compatibility.sh` |
| `alicloud-runtime-harness-ops/` | `export ALIYUN_SKILLS_ROOT="$PWD" && bash alicloud-runtime-harness-ops/test-harness-integration.sh` |
| `gcl_runner.py` | `cd alicloud-gcl-runner-ops/scripts && python3 -m unittest gcl_runner_test` |
| `SKILL.md` only (substantive) | `npx markdownlint-cli2 "alicloud-<product>-ops/SKILL.md"` |

Full suite table + agent checklist (RT-1–RT-6): [docs/post-update-self-review.md §11.1](docs/post-update-self-review.md#111-regression-testing-mandatory)

### 11.2 Dual-Track Testing (MANDATORY)

> **原则**：每个涉及云操作 / GCL / Reflexion / Memory 的功能点交付前，**必须**完成双轨测试，缺一不可。

| 轨道 | 目标 | 工具 | 通过条件 |
|------|------|------|----------|
| **Track 1: dry-run / 机制层** | 用最小代价跑通整个功能逻辑（路径、分支、store、注入） | `--dry-run` / unit test / 单元 fixture | 链路全绿，无路径分支跳过 |
| **Track 2: 真实环境 / 集成层** | 在真实凭证 + 真实 `aliyun` CLI 调用下，跑一次端到端集成 | 真实云账号 + `aliyun <product> <action>` + GCL runner | trace 落盘、memory_store / reflexion_store 真实触发 |

**禁止**：
- ❌ 只跑 dry-run 就宣称交付（机制 ≠ 集成）
- ❌ 只跑真实环境就宣称交付（路径覆盖 ≠ 真实数据）
- ❌ 跳过任一轨道（违反双轨原则，回归风险翻倍）

**优先级**：真实环境出现破坏性风险时，**先 Track 1 跑通，再 Track 2 用只读操作集成**（如 `Describe*` / `List*` / `Get*`），避免误删资源。

**典型场景举例**：
| 功能 | Track 1 | Track 2 |
|------|---------|---------|
| GCL pre-flight 注入 | `gcl_runner.py --dry-run --user-request "..."` 验链路 | 任意产品 skill 跑一次非 dry-run GCL，trace 中 `generator_prompt_with_memory` 含真实替换文本 |
| Reflexion memory 落盘 | `--dry-run` 验 `memory_store result=success` | 非 dry-run 跑失败命令（如 MAX_ITER）验 `reflexion_store result=success` |
| memory_preflight retrieval | `memory_preflight_test.py` 单测 | 跑一次 GCL，trace 含真实 `slots.known_traps` 内容 |

**例外**（仅以下情况可单轨）：
- 纯静态文档改动（不涉及代码）→ 只跑 lint
- 仅 stub / fixture 改动 → Track 1 即可

#### 11.2.1 凭证不可用时的处理（`[BLOCKED:no-credentials]`）

> **场景**：真实环境集成（Track 2）需要 `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET`，但当前会话拿不到有效凭证（例如离线开发、CI 无 secret、临时租户切换等）。

**判定凭证不可用的标准**（任一满足即触发）：

| # | 检查 | 命令 | 失败信号 |
|---|------|------|----------|
| 1 | 环境变量缺失 | `env \| grep -E '^ALIBABA_CLOUD_ACCESS_KEY_(ID\|SECRET)='` | 空输出 |
| 2 | CLI 未配置 profile | `aliyun configure list` | Profile 列表为空 / 标记 `Invalid` |
| 3 | CLI 探测调用失败 | `aliyun ecs DescribeRegions --RegionId cn-hangzhou` | exit code 非 0 / `InvalidAccessKeyId.NotFound` 等鉴权错误 |

**处理流程**：

1. **Track 1 必须全绿**——dry-run / 单测 / 路径分支全部覆盖。
2. **在交付物 / PR 描述 / trace 注释中显式标注**：
   ```
   [BLOCKED:no-credentials] Track 2 skipped — see env check output.
   Track 1 status: PASS (5/5 dry-run traces, all stores verified)
   ```
3. **列出 Track 2 待办**（让接手人知道怎么补）：
   ```bash
   # 恢复 Track 2 的最小复现步骤：
   export ALIBABA_CLOUD_ACCESS_KEY_ID=<valid_ak>
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET=<valid_sk>
   aliyun configure set --profile default --region cn-hangzhou
   # 重跑任意一个 GCL dry-run 改为非 dry-run
   python3 alicloud-gcl-runner-ops/scripts/gcl_runner.py \
     --skill alicloud-ecs-ops --op DescribeInstances \
     --command "aliyun ecs DescribeInstances --RegionId cn-hangzhou" \
     --output-dir .runtime/audit/gcl-runner-ops
   ```
4. **禁止掩盖**：不得在凭证缺失时编造"已集成验证"或伪造 trace。

**回退**：一旦凭证恢复，立即补 Track 2，并把 `[BLOCKED:no-credentials]` 标记替换为 `[INTEGRATED:verified <date>]`。

---

## Key References

| Document | Description |
|----------|-------------|
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | **统一架构入口** — Agent Runtime 演进路线图、Phase 1/2/3 规划 |
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

---

## 18. Compound Engineering（复利工程）

> **核心原则**：每次设计/开发不只解决当前问题，还要沉淀可复用的模式、模板和决策记录，让下一次同类工作更快更好。

### 18.1 架构设计模式

当进行架构设计（新系统、重大重构）时，遵循以下可复用模式：

| 模式 | 做法 | 反模式 |
|------|------|--------|
| **场景驱动** | 从用户接入场景出发（告警、工单、对话、CI/CD），先定义"做完后的效果"，再设计架构 | 从技术分层出发，先画架构图再想用户怎么用 |
| **价值量化** | 每个阶段用"一句话 + 一个具体数字"描述效果：MTTD 30分钟 → 3分钟 | "提升效率"、"优化体验"等模糊描述 |
| **场景对比** | 用"现在 vs 做完后"表格，让价值一目了然 | 只描述目标状态，不对比现状 |
| **双模式架构** | 对外服务同时提供 REST API（系统集成）和 MCP Server（LLM Agent），共享核心引擎 | 只做一种接入方式，后续再补 |
| **向后兼容** | 新系统在现有基础上新增编排层，不替代任何现有组件 | 推倒重来 |

### 18.2 文档治理模式

| 模式 | 做法 |
|------|------|
| **统一入口** | 架构设计以 `docs/ARCHITECTURE.md` 为唯一权威入口，子文档从它链接出去 |
| **废弃即删除** | 被替代的文档直接删除（不是标记 deprecated 然后堆积），git 历史可回溯 |
| **三层文档结构** | ARCHITECTURE.md（总览）→ SPEC（详细规格）→ PLAN（任务分解），每层有明确的读者和目的 |
| **引用而非重复** | AGENTS.md 引用 ARCHITECTURE.md，不重复架构内容；SPEC 引用 GCL spec，不重复 GCL 规范 |

### 18.3 关键设计决策记录

以下是本次架构设计中做出的关键决策，后续设计应参考：

| 决策 | 选择 | 理由 | 来源 |
|------|------|------|------|
| Agent 编排模式 | Supervisor（单 Agent 调度多 Skill） | 70% 生产采用率；多 Agent token 消耗是单 Agent 的 15x | [研究报告](docs/ARCHITECTURE.md) |
| 接入方式 | REST API + MCP Server 双模式 | REST 给系统用（告警/工单/CI），MCP 给 LLM Agent 用（对话） | [架构总览](docs/ARCHITECTURE.md) |
| 根因分析 | Phase 1 用规则引擎，不用 LLM | 确定性高、延迟低、成本可控；LLM 推理留给 Phase 2+ | [Phase 1 SPEC](docs/specs/phase-1-core-engine.md) |
| 意图解析 | 规则 + 正则 + 关键词词典，不用 LLM | 告警/工单输入结构化程度高，不需要 LLM；成本更低、延迟 < 100ms | [Phase 1 SPEC §2.2](docs/specs/phase-1-core-engine.md) |
| 开发顺序 | 先 REST API 再 MCP Server | REST API 用 curl 就能测，能独立验证核心引擎；MCP 本质是 REST 的协议适配层 | [Phase 1 PLAN](docs/plans/phase-1-plan.md) |
| 不做什么 | Phase 1 不做多 Agent、不做 HITL、不做沙箱 | 单 Agent + 多 Skill 覆盖 80% 场景；复杂特性留到 Phase 2/3 | [架构总览](docs/ARCHITECTURE.md) |

### 18.4 可复用的文档模板

以下模板已在实际设计过程中验证，可直接复用：

**SPEC 文档结构**（参考 `docs/specs/phase-1-core-engine.md`）：
```
1. 目标与成功标准（可验证的 S1-S8）
2. 核心引擎设计（数据流图 + 每个组件的输入/输出/策略）
3. 接口规格（REST API 端点 + MCP tools）
4. 集成方式（与现有系统的关系）
5. 非功能需求（性能/安全/可观测性）
```

**PLAN 文档结构**（参考 `docs/plans/phase-1-plan.md`）：
```
1. 任务总览（清单 + 工时 + 依赖 + 优先级）
2. 任务详细分解（每个任务的子任务 + 验证标准 + 涉及文件）
3. 依赖关系图（ASCII art 或 Mermaid）
4. 风险与缓解
5. 里程碑（时间 + 交付物 + 验证方式）
```

### 18.5 复利检查清单（🔴 每次完成任务后强制执行）

> **⛔ 这个检查清单不是"建议"——是"交付完成"的定义。未通过检查清单的任务不算完成。**

每次完成一个功能点/设计后，必须逐项确认：

- [ ] **决策记录**：这次做的关键决策有没有记录到 `docs/ARCHITECTURE.md` 的决策表中？含：选了什么、为什么、不选什么
- [ ] **模板沉淀**：这次用的方法/模板有没有可复用价值？有的话是否更新了 §18.4？
- [ ] **废弃清理**：有没有产生应该清理的废弃文档/代码？删掉，不要堆积（git 历史可回溯）
- [ ] **决策一致性**：有没有违反已记录的决策？如果有，必须更新决策记录说明原因
- [ ] **可追溯性**：新产生的文档是否从 `docs/ARCHITECTURE.md` 可追溯？
- [ ] **下一次更快**：如果有人要做类似的事，能不能通过 `ARCHITECTURE.md` → SPEC → PLAN 这条链路快速找到所有上下文？
