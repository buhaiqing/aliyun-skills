# Aliyun Skills — Agent Guide

This repository is a Skills Farm for Alibaba Cloud operations — structured, AI-agent-parseable runbooks for cloud resource management.

Every section here is high-signal: agents must follow these patterns or they will produce broken or inconsistent skills.

---

## 1. Repo Layout

```
aliyun-skills/
├── alicloud-[product]-ops/       # One directory per Alibaba Cloud product
│   ├── SKILL.md                  # What to do (triggers, pre-flight, variables, execution overview)
│   ├── references/               # How to do (detailed CLI/SDK scripts, troubleshooting, monitoring)
│   │   ├── rubric.md             # MANDATORY (per skill) when skill is GCL `required`/`recommended` — see §12.3
│   │   └── prompt-templates.md   # MANDATORY (per skill) when skill is GCL `required`/`recommended` — see §12.7
│   ├── assets/                   # Example configs, eval queries
│   │   └── code-snippets/        # SDK-only skills: standalone `go run`-able Go scripts
│   └── scripts/                  # (rare — only redis-ops, topo-discovery)
├── alicloud-skill-generator/     # Meta-skill: generate new skills from OpenAPI specs
│   └── references/
│       ├── gcl-rollout-spec.md        # §12.11 Phase 2 — how to generate GCL files for a new skill
│       └── gcl-orchestrator-agent.md  # §12.11 Phase 2 — `pi-subagents` agent definition wrapping gcl_runner.py
├── scripts/                      # §12.11 Phase 2 — cross-skill GCL runner
│   ├── gcl_runner.py             # Python 3.10+ standalone CLI; zero external deps
│   ├── gcl_runner_test.py        # unittest suite (60 tests, pure stdlib)
│   └── README.md                 # usage guide
├── audit-results/                # §12.6 — GCL trace storage (GITIGNORED; ephemeral)
├── alicloud-jit-setup.sh         # JIT Go SDK bootstrap (single script)
├── REQUIREMENTS.md               # Full requirements, architecture, technical specs
├── .env.example                  # Template for ALIBABA_CLOUD_ACCESS_KEY_* vars
├── docker-compose.yaml           # Docker sandbox profiles (dev/runtime/interactive)
└── Dockerfile                    # Go 1.24 + Python 3.10 base image
```

**Canonical skill directory structure** (from `alicloud-skill-generator`):

```
alicloud-[product]-ops/
├── SKILL.md
├── references/
│   ├── core-concepts.md                 # Architecture, limits, quotas, dependencies
│   ├── api-sdk-usage.md                 # Operation map, request/response, pagination
│   ├── cli-usage.md                     # `aliyun` CLI command map (omit for sdk-only)
│   ├── troubleshooting.md               # Error codes (≥10), diagnostics, recovery
│   ├── integration.md                   # Go bootstrap, env vars, credential rules
│   ├── monitoring.md                    # CMS metrics, dashboards, alarms (if applicable)
│   ├── well-architected-assessment.md   # MANDATORY — five-pillar assessment
│   └── idempotency-checklist.md         # If retries/automation required
├── assets/
│   ├── example-config.yaml
│   └── eval_queries.json                # MANDATORY — trigger accuracy eval queries
└── scripts/                             # Optional — only redis-ops, topo-discovery have these
```

**Note**: Only `alicloud-redis-ops` and `alicloud-topo-discovery` have `scripts/`. `alicloud-elasticsearch-ops` also has `operations/` and `reports/` dirs. New skills follow the canonical structure above.

## 2. Content Separation Rule (MANDATORY)

**SKILL.md 只描述 What to do，How to do 放置在 references/\***

| 文件 | 职责 | 内容 |
|------|------|------|
| `SKILL.md` | What | 触发条件、Pre-flight Checks、变量约定、执行概览、链接到 references/ |
| `references/*.md` | How | 完整命令、脚本、退出码表、日志解读、故障恢复 |

```markdown
<!-- SKILL.md — 对的做法 -->
#### Execution
完整脚本见 [references/redis-cli-execution.md](references/redis-cli-execution.md)

| Step | 操作 | 说明 |
|------|------|------|
| 1 | `aliyun r-kvstore describe-instance-attribute` | 获取连接地址 |
| 2 | `aliyun ecs RunCommand` | 幂等检查 redis-cli |

<!-- 错误做法：在 SKILL.md 中内联 500 行脚本 -->
```

## 3. Operation Design Pattern

每个操作必须包含以下节（按顺序）：

### Pre-flight Checks
```markdown
| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| {前提} | {验证命令} | {正常值} | HALT — {人工动作} |
```

### 变量约定
```markdown
| 变量 | 含义 | 来源 |
|------|------|------|
| `{{user.xxx}}` | 用户输入 | 问一次，复用 |
| `{{env.xxx}}` | 环境变量 | NEVER 问用户，缺了就 HALT |
| `{{output.xxx}}` | 上一步输出 | 解析 API 返回值 |
```

### Execution → Post-execution Validation → Failure Recovery

每个操作的 CLI 脚本必须包含 **结构化诊断日志**（见 §4）。

## 4. Diagnostic Logging Standard (MANDATORY for data-plane ops)

所有通过 Cloud Assistant 或其他远程执行的脚本，日志格式必须一致：

```
[HH:MM:SS] [PHASE] key=value
```

### 日志阶段前缀

| PHASE | 含义 | 示例 |
|-------|------|------|
| `DIAG` | 诊断信息/环境快照 | `[DIAG] PHASE=env-snapshot`, `[DIAG] OS=Ubuntu 22.04` |
| `INSTALL` | 安装过程 | `[INSTALL] pkg_manager=apt`, `[INSTALL] exit code 0` |
| `EXEC` | 正在执行的命令 | `[EXEC] redis-cli -h host -p 6379 DEL key` |
| `RESULT` | 关键结果键值对 | `[RESULT] INSTALL=SUCCESS`, `[RESULT] NETWORK=REACHABLE` |
| `WARN` | 警告 | `[WARN] redis-cli not found, installing...` |
| `ERROR` | 错误分类 | `[ERROR] TYPE=AUTH_FAILED FIX=Check password` |
| `SUMMARY` | 最终摘要 | `[SUMMARY] Result: (integer) 1` |

### 错误分类规范（ERROR TYPE）

```
[ERROR] TYPE={大类} FIX={一句话建议}
```

内置错误类型（以 Redis 为例）：

| ERROR TYPE | 含义 | FIX |
|------------|------|-----|
| `AUTH_FAILED` | 需要密码但未提供 | Check redis password |
| `WRONG_PASSWORD` | 密码错误 | Verify credentials |
| `CLUSTER_MOVED` | 集群模式下 Key 不在本节点 | Use redis-cli -c |
| `CONNECTION_REFUSED` | 端口不可达 | Port closed or instance down |
| `TIMEOUT` | 连接超时 | Network latency or congestion |
| `UNKNOWN_COMMAND` | 命令语法错误 | Check syntax |

其他产品可以扩展自己的 TYPE 列表，但 FIX 必须提供可操作的人工指引。

### 退出码规范

| ExitCode | 含义 | Agent 动作 | 人工介入 |
|:--------:|------|-----------|:--------:|
| 0 | 成功 | 读取 SUMMARY 回传 | ❌ |
| 10-19 | 环境检查失败 | 自动触发修复（如安装） | ❌ |
| 20-29 | 安装失败 | 输出 `[DIAG] disk/mem/network` | ✅ |
| 30-39 | 网络问题 | 输出 DNS/连接诊断 | ✅ |
| 40-49 | 命令执行失败 | 输出 `[ERROR] TYPE=... FIX=...` | ✅ |

## 5. Idempotent Provisioning Pattern

对于需要在目标机器上预置工具的操作，必须遵循幂等模式：

```bash
# 1. 探测
if ! command -v redis-cli &>/dev/null; then
  # 2. 仅在缺失时安装
  apt-get install -y redis-tools
fi
# 3. 执行（不关心安装与否）
redis-cli -h host DEL key
```

不要在无判断的情况下每次执行安装。探测结果用 DIAG/RESULT 日志输出。

## 6. Cross-Skill Composition

当一个 Skill 需要另一个 Skill 的基础能力时（如 redis-ops 需要 ecs-ops 的 RunCommand）：

**推荐：在 SKILL.md 中内联必要命令，在注释中注明依赖。**

```markdown
# Execution — CLI  (uses aliyun ecs RunCommand; see alicloud-ecs-ops for advanced usage)
aliyun ecs RunCommand --RegionId ... --CommandContent "..."
```

**不推荐：形式化 import/require 另一个 skill**（Agent 可能未同时加载两个 skill）。内联是更可靠的模式。

## 7. Data Plane vs Control Plane

| Plane | 能力范围 | 使用通道 | 代表操作 |
|-------|---------|---------|---------|
| **Control Plane** | 实例生命周期、配置管理 | `aliyun {product}` API | Create/Delete/Describe/Modify 实例 |
| **Data Plane** | 数据读写、命令执行 | `redis-cli` / SDK 直连 | DEL, GET, SET, TTL, EVAL |

当现有 API 无法覆盖 Data Plane 操作时，使用 **Cloud Assistant + CLI 客户端** 间接实现：

```
redis-ops 编排层 → ecs-ops RunCommand → 目标 ECS 执行 redis-cli
```

## 8. Security Constraints

- **凭证永不输出**：`ALIBABA_CLOUD_ACCESS_KEY_SECRET` 在日志中必须替换为 `****`。JIT Go SDK 脚本中的 `config` 结构体、`fmt.Println(config)` 或 `log.Printf("%+v", ...)` 均可能泄漏凭证——禁止此类输出。
- **密码通过环境变量传递**：使用 `REDISCLI_AUTH` 而非 `-a <password>`，避免暴露在 `ps aux` 或命令历史中。
- **删除操作必须确认（MUST obtain explicit confirmation）**：在 Pre-flight Checks 表中包含操作确认行，要求用户显式提供资源标识符。

## 9. Quick Reference — Developer Commands

```bash
# Markdown linting
npx markdownlint-cli2 "alicloud-*/SKILL.md"

# Docker sandbox profiles (see docker-compose.yaml)
docker compose --profile dev up -d      # Development environment
docker compose --profile runtime up -d  # Minimal runtime
docker compose --profile interactive run interactive  # Interactive sandbox

# Generate new skill (use meta-skill)
"Generate alicloud-xyz-ops for product XYZ with operations: create, describe, modify, delete"

# JIT Go SDK setup (single script, runs 'go run' with alibabacloud-go SDKs)
./alicloud-jit-setup.sh
```

`pyproject.toml` declares `markdownlint-cli2` as the only Python dependency (uses `hatchling` build, Python 3.10).

## 10. Quality Gates

每个 Skill 必须通过以下五道质量门：

1. **Clear Boundaries**: SHOULD/SHOULD NOT triggers with delegation rules; trigger description optimized per agentskills.io guidelines (< 1024 chars)
2. **Structured I/O**: `{{env.*}}` (never ask user), `{{user.*}}` (ask once reuse), `{{output.*}}` (parse from API responses)
3. **Explicit Steps**: Pre-flight → Execute → Validate → Recover for **each** critical operation
4. **Failure Strategies**: Error taxonomy (≥10 product-specific codes), HALT vs retry logic, credential vs quota vs business error separation
5. **Single Responsibility**: One product, one primary resource; cross-product delegation documented, not duplicated

Additionally, every skill MUST include a **Well-Architected Framework** table (five pillars: Security, Stability, Cost, Efficiency, Performance) and pass the **P0/P1 checklist** defined in `alicloud-skill-generator/SKILL.md`.

## 11. Post-Update Self-Review (MANDATORY — 更新后必做)

> **规则：每次 skill 有更新后，都自动加入 2 轮自我复盘，主动修复复盘中发现的所有问题。**

每次修改 `alicloud-[product]-ops/` 下任何文件（SKILL.md、references/*、assets/*）后，在声明完成前必须执行以下 2 轮自我复盘：

### Round 1: Structural Check (结构合规)

对照 `alicloud-skill-generator/SKILL.md` 的 [P0 — MUST PASS 检查清单](alicloud-skill-generator/SKILL.md#p0--must-pass) 逐条检查修改后的 skill。**重点关注：**

| # | 检查项 | 检查内容 |
|---|--------|----------|
| C1 | Frontmatter | `name`, `description`, `license`, `compatibility`, `metadata` 是否完整？`description` 是否 < 1024 字符？ |
| C2 | Trigger & Scope | `SHOULD Use` / `SHOULD NOT Use` 是否存在？触发条件是否精确？ |
| C3 | Variables | `{{env.*}}` vs `{{user.*}}` 是否正确分类？是否有硬编码的密钥？ |
| C4 | Five Core Standards | 五道质量门表格是否存在并填写完整？ |
| C5 | Well-Architected | 五支柱表格是否存在？ |
| C6 | Token Efficiency | TE-1~TE-6 是否已应用（集中 JSON paths、紧凑错误表、省略不必要 docstring 等）？ |

**发现任一违规 → 立即修复 → 重新检查直到全部通过。**

### Round 2: Content & Functional Check (内容验证)

| # | 检查项 | 检查内容 |
|---|--------|----------|
| F1 | CLI 命令验证 | `aliyun {product} help` 是否确认该产品存在？命令参数是否匹配真实 API？ |
| F2 | OpenAPI 精度 | 所有 operationId、字段名、JSON path 是否可追溯到 OpenAPI 或官方文档？ |
| F3 | 错误处理 | 错误码 ≥ 10 个？每个错误有 recovery action？重试和 HALT 边界清晰？ |
| F4 | 安全门 | 所有删除/销毁操作是否都有显式确认步骤？凭证是否在所有执行路径中被掩码？ |
| F5 | 引用完整性 | `references/` 和 `assets/` 中的所有文件链接是否有效？无死链？ |
| F6 | 跨 skill 委托 | 涉及其他产品的操作是否注明了委托路径而不是重复完整流程？ |

**发现问题 → 逐一修复 → 确认所有问题已解决后方可结束。**

### Self-Review Record (复盘记录)

每次复盘完成后，在当前 session 中输出简要记录：

```
## 复盘记录
### Round 1: 结构合规
- [发现/无问题] {检查项}: {描述}
- 修复: {做了什么}

### Round 2: 内容验证
- [发现/无问题] {检查项}: {描述}
- 修复: {做了什么}
```

此记录不需要写入文件，但必须在本次 session 内可见，作为完成自我复盘的凭证。

---

### Implementation Notes (实施说明)

- 本规则适用于 **所有类型** 的更新：新增 operation、修复 bug、更新 API 版本、修改 reference 文件、优化 description。
- 不适用于 **纯格式化** 修改（如 markdown linting 修复、空白修正）——此时仅需确认 lint 通过。
- Round 1 和 Round 2 是独立的——即使 Round 1 全通过，也必须执行 Round 2。
- 所有修复必须在本 session 内完成，不得推迟到后续 session。

---

## Key References

| 文档 | 说明 |
|------|------|
| `README.md` | 项目概述、CLI 安装、凭证配置 |
| `REQUIREMENTS.md` | 各 Skill 功能需求详情、架构设计、技术规范 |
| `alicloud-skill-generator/SKILL.md` | **Meta Skill 生成器** — 生成新 skill 的完整工作流、P0/P1 检查清单、Token Efficiency 规则 |
| `alicloud-skill-generator/references/governance-and-adversarial-review.md` | 治理与对抗性审查 — 合并前的安全/弹性/UX 审查场景（24+ 场景） |
| `alicloud-skill-generator/references/alicloud-skill-template.md` | SKILL.md 的 canonical 模板 |
| `alicloud-skill-generator/references/aiops-best-practices.md` | §11 多轮自我复盘与批判性反思规范（故障诊断场景的 3 轮复盘） |
| `alicloud-skill-generator/references/execution-environment.md` | CLI 安装、Go JIT 下载、凭证配置 |
| `alicloud-skill-generator/references/user-experience-spec.md` | 所有 Skill 的 UX 合规要求 |
| `AGENTS.md` §12 GCL | **Generator-Critic-Loop** — 运行时对抗式质量门（pilot: `alicloud-ecs-ops`），与 §11 静态复盘互补 |
| `CLAUDE.md` | 入口文件（内容为 `@AGENTS.md`） |

> **规范冲突时，`alicloud-skill-generator/SKILL.md` 和 `references/` 下的文档为 authoritative 来源。** AGENTS.md 是这些规范的摘要，而非替代。

---

## 12. Generator-Critic-Loop (GCL) — Adversarial Quality Gate

> **概念来源：** Inspired by GAN's Generator/Discriminator idea, but deliberately **not** a real GAN.
> Naming: **GCL (Generator-Critic-Loop)** to avoid misleading reviewers and LLM trainees.
>
> **本章节与 Aliyun 现有 `§11 Post-Update Self-Review` 互补**：
> - §11 = **Static review at skill-authoring time**（人/Agent 在改完 SKILL.md 后自检）
> - §12 = **Runtime review at skill-execution time**（GCL 在每次执行云操作时强制走对抗回路）
> 两者覆盖不同生命周期：前者审查 runbook 的质量，后者审查 runbook 被实际调用时的执行质量。

### 12.1 Purpose

Apply an adversarial **Generator ↔ Critic** loop with a quantitative rubric to every **runtime** skill execution.
Most valuable in **high-side-effect cloud operations** (delete, stop, restore, RAM/KMS/DDL) where a single
mistake is unrecoverable. This complements the static P0/P1 checklist in `alicloud-skill-generator/SKILL.md` by
catching what static review cannot — wrong arguments, missing pre-checks, silent partial failures, etc.

| GAN (real) | GCL (this spec) |
|---|---|
| Discriminator learns sample distribution | Critic scores an **explicit rubric** |
| No termination condition | Must terminate: **PASS / MAX_ITER / SAFETY_FAIL** |
| G and D train in parallel | G and C run **sequentially** |
| Goal: "fool the D" | Goal: "pass the rubric threshold" |

### 12.2 Roles

| Role | Job | Input | Output | Forbidden |
|---|---|---|---|---|
| **Generator (G)** | Execute the cloud operation | user request + previous Critic feedback | result + execution trace | modifying the rubric; self-scoring |
| **Critic (C)** | Independently audit G's output | G's result + trace + rubric | scores + suggestions | calling `aliyun` / SDK / mutating anything |
| **Orchestrator (O)** | Loop control, termination, final return | context + C scores + budget | continue / final result | executing or scoring on its own |

**Hard constraint:** G and C MUST live in **isolated prompt contexts** (preferably isolated sessions
or sub-agents, e.g. `pi-subagents`). A shared context is a "pseudo-GCL" and is explicitly banned — see §12.9.

### 12.3 Rubric (mandatory per skill)

Each `SKILL.md` MUST declare its skill-specific rubric under `## Quality Gate (GCL)`, **referencing**
`references/rubric.md` (which holds the full dimension table and scoring details — to keep `SKILL.md` terse
per §2 Content Separation Rule). Minimum 5 dimensions, identical to JD Cloud GCL for cross-farm consistency:

| Dimension | Meaning | Scale | Default threshold |
|---|---|---|---|
| **Correctness** | Resource id / state / config actually matches the request | 0 / 0.5 / 1 | ≥ 0.5 (1.0 required for `delete` / `stop` / RAM / KMS / DDL) |
| **Safety** | Destructive op (`delete` / `stop` / `restore` / RAM / KMS / DDL) was confirmed or guarded | 0 / 1 | = 1 |
| **Idempotency** | Retrying the same call will not cause duplicate side-effects | 0 / 0.5 / 1 | ≥ 0.5 |
| **Traceability** | Output is auditable: command, params, raw response, errors all captured | 0 / 0.5 / 1 | ≥ 0.5 |
| **Spec Compliance** | Conforms to the skill's `core-concepts.md` constraints (quotas, regions, dependencies) | 0 / 0.5 / 1 | ≥ 0.5 |

**Safety = 0 → ABORT immediately, regardless of total score.** This is a hard non-negotiable gate.

**Aliyun-specific extension dimensions** (optional per skill):

| Dimension | When to add | Example |
|---|---|---|
| **Region Compliance** | cross-region operations | `--RegionId` matches the user's declared region in `{{user.region_id}}` |
| **Credential Hygiene** | long-running or multi-step ops | `ALIBABA_CLOUD_ACCESS_KEY_SECRET` never appears in any log line |
| **Well-Architected** | cost / security / stability-sensitive ops | operation does not violate a relevant WA pillar (e.g. disable deletion protection in prod) |

### 12.4 Loop Flow

```
User Request
     │
     ▼
[0] Pre-flight (Orchestrator)
    - resolve env.* and user.* variables
    - pick skill, load its rubric from references/rubric.md
    - check §8 Security Constraints (no plaintext credentials in scope)
     │
     ▼
[1] Generate (G) ───────────────────────┐
    - run `aliyun` / Go SDK             │
    - capture trace (command, args,     │
      exit_code, raw response, errors)  │
     │                                  │
     ▼                                  │
[2] Critique (C)                       │
    - isolated prompt context           │
    - score every rubric dimension      │
    - emit ≤ 3 actionable suggestions   │
     │                                  │
     ▼                                  │
[3] Decide (Orchestrator)              │
    - Safety=0  → ABORT (no partial)    │
    - all pass  → RETURN                │
    - else & iter<max → inject          │
       suggestions into G               │
    - else → RETURN best + unresolved   │
       rubric items                     │
     └──────────────────────────────────┘
```

### 12.5 Termination (first match wins)

| Condition | Behavior |
|---|---|
| **PASS** | Every rubric dimension meets its threshold → return G's result |
| **MAX_ITER** | Reached `max_iterations` (default per skill class — see §12.8) → return **best-so-far** + unresolved rubric items |
| **SAFETY_FAIL** | Safety = 0 → **ABORT**; never return partial or "best-effort" output |

### 12.6 Trace & Audit (mandatory)

Every GCL run MUST persist a JSON trace under `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json`:

```json
{
  "skill": "alicloud-ecs-ops",
  "request": "<sanitized user request>",
  "rubric_version": "v1",
  "iterations": [
    {
      "iter": 1,
      "generator": { "command": "aliyun ecs DeleteInstance ...", "args": {...}, "exit_code": 0, "result_excerpt": "..." },
      "critic": {
        "scores": {
          "correctness": 1, "safety": 1, "idempotency": 0.5,
          "traceability": 1, "spec_compliance": 1
        },
        "suggestions": ["..."],
        "blocking": false
      },
      "decision": "RETRY"
    }
  ],
  "final": { "status": "PASS", "iter": 2, "output": "..." }
}
```

**Sanitization rule (mandatory):** the `request` field MUST NOT contain `ALIBABA_CLOUD_ACCESS_KEY_SECRET`,
Redis/RDS passwords, KMS plaintext key material, RAM user passwords, or any other secret enumerated in §8.
Use `<masked>` or redacted tokens before writing to disk.

**Directory:** add `./audit-results/` to `.gitignore` (or treat traces as ephemeral; do not commit).

### 12.7 Prompt Templates (mandatory per skill)

Each pilot/required skill MUST contain two references:

- `references/rubric.md` — the full dimension table, scoring rules, and **per-operation safety sub-rules** (e.g. for `alicloud-rds-ops`, what counts as "DDL" and what confirmation is required).
- `references/prompt-templates.md` — **Generator Prompt Template** and **Critic Prompt Template**, each declaring its `{{...}}` placeholders.

Placeholders MUST follow the repository-wide convention (see §3 Operation Design Pattern):
`{{env.*}}` / `{{user.*}}` / `output.*`. Bare `{...}` placeholders are NOT allowed in skill prompt templates.

**Critic prompt must hide the raw user request** to prevent "answer-aligned" rubber-stamping.
Recommended skeleton:

```text
You are an independent Alibaba Cloud operation auditor.
You will see one execution result and its trace. Score it STRICTLY against the rubric below.
Do NOT consider the original user request — judge only what was actually done.

rubric: {{output.rubric}}
generator_output: {{output.generator_output}}
trace: {{output.trace}}

Return strict JSON:
{
  "scores": { "correctness": 0|0.5|1, "safety": 0|0.5|1, "idempotency": 0|0.5|1,
              "traceability": 0|0.5|1, "spec_compliance": 0|0.5|1 },
  "suggestions": ["≤ 3 concrete, executable improvements"],
  "blocking": true|false
}
```

### 12.8 Per-Skill Defaults (Aliyun product mapping)

GCL is **only required** on high-side-effect skills. Default `max_iter` is **2** for required skills
(balances safety against latency cost). Read-only / meta skills are **optional** with higher `max_iter`.

| Skill | GCL | Default max_iter | Notes |
|---|---|---|---|
| `alicloud-ecs-ops` | **required** | 2 | delete/stop/reboot are destructive |
| `alicloud-redis-ops` | **required** | 2 | FLUSHALL / instance delete / backup delete |
| `alicloud-rds-ops` | **required** | 2 | DROP / DELETE / TRUNCATE / instance delete |
| `alicloud-polar-mysql-ops` | **required** | 2 | DDL via Data API / cluster delete |
| `alicloud-polar-postgresql-ops` | **required** | 2 | DDL / cluster delete |
| `alicloud-polar-oracle-ops` | **required** | 2 | DDL / cluster delete |
| `alicloud-polar-pg-ops` | **required** | 2 | DDL / cluster delete |
| `alicloud-mongodb-ops` | **required** | 2 | dropDatabase / instance delete |
| `alicloud-elasticsearch-ops` | **required** | 2 | delete index / cluster / `_delete_by_query` |
| `alicloud-ram-ops` | **required** | 2 | detach policy / delete user / rotate AccessKey |
| `alicloud-kms-ops` | **required** | 2 | schedule key deletion is irreversible |
| `alicloud-eip-ops` | **required** | 2 | release EIP can break production |
| `alicloud-dts-ops` | **required** | 2 | delete / reset / stop DTS job (irreversible data flow loss) |
| `alicloud-vpc-ops` | **required** | 2 | delete VPC / vSwitch / NAT / SG |
| `alicloud-nat-ops` | **required** | 2 | delete NAT gateway / SNAT / DNAT |
| `alicloud-slb-ops` | recommended | 3 | listener / backend server delete |
| `alicloud-ack-ops` | recommended | 3 | delete node / cluster / namespace |
| `alicloud-ack-serverless-ops` | recommended | 3 | delete cluster / application |
| `alicloud-fc-ops` | recommended | 3 | delete function / service / trigger |
| `alicloud-eci-ops` | recommended | 3 | delete container group |
| `alicloud-cms-ops` | recommended | 3 | alarm rule delete |
| `alicloud-actiontrail-ops` | optional | 5 | read-only audit |
| `alicloud-billing-ops` | optional | 5 | read-only billing |
| `alicloud-das-ops` | optional | 5 | mostly read-only diagnostics |
| `alicloud-sas-ops` | optional | 5 | mostly read-only security posture |
| `alicloud-resourcemanager-ops` | recommended | 3 | resource folder / account move |
| `alicloud-agentrun-ops` | recommended | 3 | delete agent / application |
| `alicloud-topo-discovery` | optional | 5 | read-only |
| `alicloud-skill-generator` | optional | 3 | meta operation (no cloud mutation) |

Each skill may override `max_iter` in its own `SKILL.md` (under `## Quality Gate (GCL)`), with a written
justification (e.g. `alicloud-elasticsearch-ops` may set 3 because `_delete_by_query` retried scans
are common and a second pass is cheap).

### 12.9 Anti-Patterns (banned)

- ❌ **Shared context G+C** — defeats independence → banned (use `pi-subagents` fork context or equivalent)
- ❌ **Subjective scoring** — Critic must use the rubric, not "vibes" → banned
- ❌ **Unbounded loop** — always hard-cap iterations → banned
- ❌ **Critic sees the user request** — encourages rubber-stamping → banned
- ❌ **Silently downgrade on Safety fail** — must ABORT visibly with full trace → banned
- ❌ **Trace not persisted** — no post-mortem possible → banned
- ❌ **Critic mutates resources** — Critic is read-only by definition → banned
- ❌ **Trace leaks secrets** — `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, Redis/RDS passwords, etc. must be sanitized
  per §12.6 → banned

### 12.10 Relationship with §11 Self-Review

| Aspect | §11 Post-Update Self-Review | §12 GCL |
|---|---|---|
| When | After a `SKILL.md` / `references/*` is **edited** | During **runtime execution** of that skill |
| Who | The author Agent (single context) | Generator + Critic (isolated contexts) + Orchestrator |
| Input | The diff / new content | A live user request + skill rubric |
| Output | Self-review record (in-session only) | Persisted JSON trace under `./audit-results/` |
| Failure mode caught | Wrong frontmatter, missing sections, broken links | Wrong arguments, missing pre-checks, silent partial failures, missed idempotency |
| Cadence | Per skill update | Per execution |

**Both gates are mandatory for the skills marked "required" in §12.8** — a skill can be §11-compliant
(structurally sound) yet §12-failing (dangerous at runtime). The two together close the static-vs-runtime
quality gap.

### 12.11 Rollout Roadmap

- **Phase 1** ✅ — GCL spec added to `AGENTS.md`; piloted on `alicloud-ecs-ops` and extended to **14 `required` skills** (ECS, Redis, RDS, RAM, KMS, EIP, **DTS**, VPC, NAT, MongoDB, ES, PolarDB×4). Each has `references/rubric.md` + `references/prompt-templates.md` + `## Quality Gate (GCL)` section. `alicloud-skill-generator` P0 checklist updated with 4 GCL + 2 GCL-P1 mandatory items; `references/gcl-rollout-spec.md` added.
- **Phase 2** ✅ — `scripts/gcl_runner.py` (mechanical regex-based Critic, subprocess Generator, JSON trace per §12.6); `scripts/gcl_runner_test.py` (60 unit tests, ~0.02s). `scripts/README.md` + `alicloud-skill-generator/references/gcl-orchestrator-agent.md` (pi-subagents integration).
- **Phase 3-A** ✅ — LLM-based Critic (designed; not yet implemented; `critique()` interface is forward-compatible).
- **Phase 3-B** ✅ — `scripts/gcl_cms_alarm_setup.py` (idempotent alarm creation; reads `crosscheck-report-*.json`; creates/updates 5 phantom alarms: GCL-Phantom-Pass, GCL-Phantom-Fail, GCL-Resource-Mismatch, GCL-Api-Errors, GCL-Timing-Anomaly; dry-run mode). `alicloud-cms-ops/references/rubric.md` enhanced from Phase 5 lean to Phase 3-B full (added §2 Phantom Alarm Schema, §4-5 worked examples). `alicloud-cms-ops/references/prompt-templates.md` enhanced (added Phantom alarm Generator/Critic rules + cross-skill delegation). `alicloud-cms-ops/references/gcl-cms-alarm-guide.md` (architecture, thresholds, cron integration, alert response playbook, dashboard). `alicloud-cms-ops/SKILL.md` bumped 2.1.0 → 2.2.0.
- **Phase 3-C** ✅ — **`scripts/gcl_actiontrail_crosscheck.py`** (cloud-side audit; `LookupEvents` re-verifies each `gcl-trace-*.json`; catches `PHANTOM_PASS` / `PHANTOM_FAIL` / `RESOURCE_MISMATCH` / `TIMING_ANOMALY`). `scripts/gcl_actiontrail_crosscheck_test.py` (25 unit tests). `alicloud-skill-generator/references/gcl-actiontrail-crosscheck-spec.md`. `alicloud-actiontrail-ops/SKILL.md` bumped 1.0.0 → 1.1.0 with a lightweight `## Quality Gate (GCL)` cross-checker role section.
- **Phase 4** ✅ — wire rubric pass-rate to `alicloud-cms-ops` alarms (real incidents refine thresholds). `scripts/gcl_passrate_reporter.py` (aggregates GCL traces → per-skill + per-dimension pass-rates → `aliyun cms PutCustomMetric` to `acs_custom_gcl` namespace). `scripts/gcl_cms_alarm_setup.py` extended with 3 pass-rate alarms: GCL-Safety-Fail-Rate (P1), GCL-Correctness-Drop (P2), GCL-Traceability-Gap (P3). `alicloud-cms-ops/references/gcl-passrate-metrics-guide.md` (architecture, cron pipeline, alarm thresholds, dashboard). `AGENTS.md` §12.8: DTS added as 14th `required` skill.
- **Phase 5** ✅ — GCL rollout extended to all 8 `recommended` skills (SLB, ACK, ASK, FC, ECI, CMS, ResourceManager, AgentRun). Each gets lean `references/rubric.md` + `references/prompt-templates.md` + `## Quality Gate (GCL)` section with `max_iter=3`. Meta / read-only skills (`ActionTrail`, `Billing`, `DAS`) remain `optional` per §12.8.

### 12.12 Aliyun-Specific Differences vs. JD Cloud GCL

| Aspect | JD Cloud GCL | Aliyun GCL (this doc) |
|---|---|---|
| Primary CLI | `jdc` (Python 3.10, INI config only) | `aliyun` (Go static binary, env-var creds) |
| Credential path | `~/.jdc/config` | env: `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` |
| Meta-skill | `jdcloud-skill-generator` | `alicloud-skill-generator` |
| Destructive workload map | VM, Redis, MySQL, PG, Mongo, ES, IAM, KMS, EIP | ECS, Redis, RDS, PolarDB×4, Mongo, ES, RAM, KMS, EIP, VPC, NAT, … |
| Optional / read-only map | audit / tag / alert intelligence | actiontrail, billing, das, sas, topo-discovery, skill-generator |
| Pilot | `jdcloud-vm-ops` | `alicloud-ecs-ops` |

The semantic model (roles, rubric dimensions, termination, anti-patterns) is **identical** by design,
so future cross-farm tooling (e.g. a shared `scripts/gcl_runner.py`) can be reused with minimal adaptation.

### 12.13 Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-04 | Initial GCL specification added to `AGENTS.md`. Ported from `jdcloud-skills/AGENTS.md` with Aliyun adaptations: `aliyun` CLI, env-var credentials, Aliyun product mapping in §12.8, alignment with §11 Self-Review via §12.10. Pilot scoped to `alicloud-ecs-ops`. |
| 1.1.0 | 2026-06-04 | **§12.11 Phase 2 shipped**: `scripts/gcl_runner.py` (mechanical regex-based Critic, subprocess Generator, JSON trace persistence per §12.6); `scripts/gcl_runner_test.py` (60 pure-stdlib `unittest` tests); `scripts/README.md`; `alicloud-skill-generator/references/gcl-orchestrator-agent.md` (pi-subagents agent spec). Added 4 P0 + 2 P1 GCL checks to `alicloud-skill-generator/SKILL.md` checklist; added `references/gcl-rollout-spec.md`. GCL rollout extended to 8 additional skills (VPC, NAT, MongoDB, ES, 4×PolarDB). |
| 1.2.0 | 2026-06-04 | **§12.11 Phase 3-C shipped**: `scripts/gcl_actiontrail_crosscheck.py` (cloud-side audit; re-verifies each `gcl-trace-*.json` against `aliyun actiontrail LookupEvents`; catches `PHANTOM_PASS` / `PHANTOM_FAIL` / `RESOURCE_MISMATCH` / `TIMING_ANOMALY`); `scripts/gcl_actiontrail_crosscheck_test.py` (25 unit tests). `alicloud-skill-generator/references/gcl-actiontrail-crosscheck-spec.md` (architecture, CLI usage, exit codes, report schema, limitations, "adding a new service" guide). `alicloud-actiontrail-ops/SKILL.md` bumped 1.0.0 → 1.1.0 with a lightweight `## Quality Gate (GCL)` cross-checker role section (ActionTrail remains `optional` per §12.8). `alicloud-skill-generator/SKILL.md` Reference Directory +1 entry. `scripts/README.md` extended. §12.11 Roadmap updated to reflect actual progress (Phase 1, 2, 3-A, 3-C shipped; 3-B, 4, 5 pending). |
| **1.3.0** | 2026-06-04 | **§12.11 Phase 5 shipped**: GCL rollout extended to all 8 `recommended` skills (SLB, ACK, ASK, FC, ECI, CMS, ResourceManager, AgentRun). Each gets lean `references/rubric.md` + `references/prompt-templates.md` + `## Quality Gate (GCL)` section with `max_iter=3`. Total Phase 5 artifacts: 16 new files (~14 KB rubric + ~10 KB prompt templates across 8 skills). `AGENTS.md` §12.11 Roadmap: Phase 5 status → ✅ (all `required` + all `recommended` skills now have GCL). Remaining: `optional` skills (ActionTrail, Billing, DAS) — intentionally excluded per §12.8 classification. |
| **1.4.0** | 2026-06-04 | **§12.11 Phase 3-B shipped**: `scripts/gcl_cms_alarm_setup.py` (idempotent alarm creation for 5 phantom metrics: GCL-Phantom-Pass/Fail/Resource-Mismatch/Api-Errors/Timing-Anomaly; dry-run mode). `alicloud-cms-ops/references/rubric.md` enhanced to full Phase 3-B role (added §2 Phantom Alarm Schema with JSON path table + alarm thresholds + template CLI). `alicloud-cms-ops/references/prompt-templates.md` enhanced (Phantom alarm Generator/Critic rules + cross-skill delegation). `alicloud-cms-ops/references/gcl-cms-alarm-guide.md` (architecture, cron integration, alert response playbook, dashboard). `alicloud-cms-ops/SKILL.md` bumped 2.1.0 → 2.2.0. |
