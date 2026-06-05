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
│   ├── idempotency-checklist.md         # If retries/automation required
│   └── advanced/                        # Optional — lazy-loaded by Advanced Analytics section
│       ├── aiops-*.md                   #   AIOps: anomaly detection, prediction, auto-remediation
│       ├── finops-*.md                  #   FinOps: cost analysis, optimization
│       └── sql-execution.md             #   Security-Sensitive: SQL file execution (requires user confirmation)
├── assets/
│   ├── example-config.yaml
│   └── eval_queries.json                # MANDATORY — trigger accuracy eval queries
└── scripts/                             # Optional — only redis-ops, topo-discovery have these
```

**`advanced/` 链接规则**：advanced/ 内文件引用父目录 references/ 中的文件时，必须使用 `../` 相对路径（如 `[CLI Usage](../cli-usage.md)`）。

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

### 10.1 Token Efficiency Requirements (P0 — 强制)

> 在保持 Agent 可执行性的前提下，最小化每个 Skill 的 Token 消耗。完整定义见 `alicloud-skill-generator/SKILL.md` §Token Efficiency Requirements。

| 规则 | 要点 | 节省 |
|------|------|------|
| **TE-1** API 查询 > 静态表格 | 用 `aliyun` 命令获取版本/配额，不硬编码 | ~200-500/文件 |
| **TE-2** 省略不必要 docstring | Go SDK 用 `#` 注释代替函数级 docstring | ~100-200/函数 |
| **TE-3** 紧凑错误表 | 每行 1 个错误码，≤3 列 | ~300-500/文件 |
| **TE-4** JSON paths 集中声明 | 文件顶部统一声明，不重复 | ~50-100/文件 |
| **TE-5** YAML anchors | `example-config.yaml` 用 `&anchor` 消除重复 | ~200-400/文件 |
| **TE-6** 消除跨文件重复 | SKILL.md 已有完整流程，references 不重复 | 因 Skill 而异 |
| **TE-7** 专业内容分层 | AIOps/FinOps 等深度分析放 `references/advanced/`；SQL 执行等安全敏感操作单独标注并要求显式确认 | ~3,000-8,000/文件 |

**不可压缩的内容**：Agent 可执行命令本身（参数、JSON paths）、错误恢复逻辑、安全门、Credential 规则、跨技能编排链。

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
| C6 | Token Efficiency | **必检项**：TE-1~TE-7 是否全部满足（见 §10.1）？未满足则 **BLOCK** |

### Token Efficiency 验证（C6 子项 — 严格检查）

C6 不是建议项，是 **MUST PASS** 门禁。逐条验证：

| TE 规则 | 检查方法 | 不通过则 |
|---------|---------|---------|
| TE-1 | 检查 references/ 中是否有硬编码的版本号/配额数字 | 替换为 `aliyun` 查询命令 |
| TE-2 | 检查 Go SDK 代码块是否有函数级 docstring | 删除 docstring，改用 `#` 行注释 |
| TE-3 | 检查错误表是否超过 3 列 | 合并列，每行 1 个错误码 |
| TE-4 | 检查 JSON path 是否在文件顶部集中声明 | 移至文件顶部统一声明 |
| TE-5 | 检查 example-config.yaml 是否有重复字段 | 用 YAML anchors 消除 |
| TE-6 | 检查 SKILL.md 与 references/ 是否有内容重复 | 删除 references 中的重复 |
| TE-7 | 检查 AIOps/FinOps 是否在 `references/advanced/`；SQL 执行是否标注为 Security-Sensitive | 移至 `advanced/` + 添加 Advanced Analytics 节 + Security-Sensitive 子节 |

**发现任一违规 → 立即修复 → 重新检查直到全部通过。**

### Round 2: Content & Functional Check (内容验证)

| # | 检查项 | 检查内容 |
|---|--------|----------|
| F1 | CLI 命令验证 | `aliyun {product} help` 是否确认该产品存在？命令参数是否匹配真实 API？ |
| F2 | OpenAPI 精度 | 所有 operationId、字段名、JSON path 是否可追溯到 OpenAPI 或官方文档？ |
| F3 | 错误处理 | 错误码 ≥ 10 个？每个错误有 recovery action？重试和 HALT 边界清晰？ |
| F4 | 安全门 | 所有删除/销毁操作是否都有显式确认步骤？凭证是否在所有执行路径中被掩码？ |
| F5 | 引用完整性 | **MUST PASS**：`references/`、`advanced/` 和 `assets/` 中的所有文件链接是否有效？无死链？**验证方法**：对所有 `.md` 文件执行链接扫描（见下方 §11.1）。**发现断裂 → BLOCK，不得声称完成** |
| F6 | 内容去重 | **MUST PASS**：SKILL.md 与 references/ 之间是否存在重复内容？同一信息是否在多处维护？重复 → 删除 references 中的副本，保留 SKILL.md 中的权威版本 |
| F7 | 跨 skill 委托 | 涉及其他产品的操作是否注明了委托路径而不是重复完整流程？ |

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

### 11.1 Link Validation (MANDATORY — 链接验证)

> **规则：每次文档有链接变更后，必须执行链接有效性检查。**

#### 触发条件

以下情况必须执行链接验证：
- 新增或删除 `.md` 文件
- 移动文件到不同目录（如移至 `advanced/`）
- 修改文件中的任何 markdown 链接

#### 验证方法

```bash
# 验证单个 skill 的所有链接
for f in alicloud-{product}-ops/**/*.md; do
  grep -oE '\[.*?\]\(([^)#]+\.md[^)]*)\)' "$f" | while read -r match; do
    target=$(echo "$match" | grep -oE '\(([^)]+)\)' | tr -d '()')
    # 移除锚点
    target=$(echo "$target" | sed 's/#.*//')
    if [ -n "$target" ]; then
      # 跳过外部链接
      echo "$target" | grep -q "^http" && continue
      # 解析相对路径
      dir=$(dirname "$f")
      resolved="$dir/$target"
      if [ ! -f "$resolved" ]; then
        echo "BROKEN: $f → $target"
      fi
    fi
  done
done
```

#### 验证范围

| 文件类型 | 检查内容 |
|---------|---------|
| `SKILL.md` | 所有指向 `references/`、`advanced/`、`assets/` 的链接 |
| `references/*.md` | 所有指向同级文件的链接 |
| `references/advanced/*.md` | 所有指向父目录 `../` 的链接 |
| `assets/*.md` | 所有指向 `references/` 的链接 |

#### 失败处理

发现断裂链接 → **立即修复** → 重新验证直到全部通过。

---

### 11.2 Content Deduplication (MANDATORY — 内容去重)

> **规则：SKILL.md 与 references/ 之间不得存在重复内容。**

#### 原则

- **SKILL.md = 权威来源**：执行概览、变量约定、Pre-flight Checks 表格
- **references/ = 详细实现**：完整脚本、错误码表、日志解读
- **同一信息只维护一处**：如果 SKILL.md 已有完整流程，references/ 中不得重复

#### 检查方法

```bash
# 检查 SKILL.md 与 references/ 是否有重复段落
# 1. 提取 SKILL.md 中的代码块
grep -oP '```bash\n.*?\n```' alicloud-{product}-ops/SKILL.md > /tmp/skill_code.txt
# 2. 提取 references/ 中的代码块
grep -rl '```bash' alicloud-{product}-ops/references/ | xargs grep -oP '```bash\n.*?\n```' > /tmp/ref_code.txt
# 3. 比较是否有相同代码块
diff /tmp/skill_code.txt /tmp/ref_code.txt
```

#### 失败处理

发现重复 → **删除 references/ 中的副本**，保留 SKILL.md 中的权威版本 → 重新验证

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
| `README.md` / `README_CN.md` | 项目概述、CLI 安装、凭证配置（英文版 / 中文版） |
| `REQUIREMENTS.md` | 各 Skill 功能需求详情、架构设计、技术规范 |
| `alicloud-skill-generator/SKILL.md` | **Meta Skill 生成器** — 生成新 skill 的完整工作流、P0/P1 检查清单、Token Efficiency 规则 |
| `alicloud-skill-generator/references/governance-and-adversarial-review.md` | 治理与对抗性审查 — 合并前的安全/弹性/UX 审查场景（24+ 场景） |
| `alicloud-skill-generator/references/alicloud-skill-template.md` | SKILL.md 的 canonical 模板 |
| `alicloud-skill-generator/references/aiops-best-practices.md` | §11 多轮自我复盘与批判性反思规范（故障诊断场景的 3 轮复盘） |
| `alicloud-skill-generator/references/execution-environment.md` | CLI 安装、Go JIT 下载、凭证配置 |
| `alicloud-skill-generator/references/user-experience-spec.md` | 所有 Skill 的 UX 合规要求 |
| [`docs/gcl-spec.md`](docs/gcl-spec.md) | **GCL 完整实现规范** — 角色、rubric、loop flow、trace schema、prompt template、anti-patterns、rollout roadmap |
| `AGENTS.md` §12 GCL | GCL 摘要入口 — 完整实现在 `docs/gcl-spec.md` |
| `CLAUDE.md` | 入口文件（内容为 `@AGENTS.md`） |

> **规范冲突时，`alicloud-skill-generator/SKILL.md` 和 `references/` 下的文档为 authoritative 来源。** AGENTS.md 是这些规范的摘要，而非替代。

---

## 12. Generator-Critic-Loop (GCL) — Adversarial Quality Gate

> **完整实现规范**：[`docs/gcl-spec.md`](docs/gcl-spec.md)

**核心概念**：在每次执行云操作时，强制走 Generator ↔ Critic 对抗回路，用量化 rubric 评分。与 §11 互补——§11 审查 skill 编写质量，§12 审查 skill 运行时执行质量。

### 角色

| Role | 职责 | 禁止 |
|---|---|---|
| **Generator (G)** | 执行云操作 | 修改 rubric、自评 |
| **Critic (C)** | 独立审计 G 的输出 | 调用 `aliyun`/SDK、修改资源 |
| **Orchestrator (O)** | 循环控制、终止判定 | 自行执行或评分 |

### Rubric 维度（≥5 个）

| Dimension | 含义 | Safety=0 时 |
|---|---|---|
| **Correctness** | 资源 ID/状态/配置匹配请求 | — |
| **Safety** | 破坏性操作已确认或有保护 | **立即 ABORT** |
| **Idempotency** | 重复调用不产生副作用 | — |
| **Traceability** | 输出可审计（命令、参数、响应） | — |
| **Spec Compliance** | 符合 core-concepts.md 约束 | — |

### 终止条件（首次命中即停止）

| Condition | 行为 |
|---|---|
| **PASS** | 所有维度达标 → 返回 G 的结果 |
| **MAX_ITER** | 达到 max_iter → 返回 best-so-far + 未解决问题 |
| **SAFETY_FAIL** | Safety=0 → **ABORT**，不返回部分结果 |

### Skill 分类（GCL Level + max_iter）

| Skill | GCL | max_iter | 关键风险操作 |
|---|---|---|---|
| `alicloud-ecs-ops` | required | 2 | delete/stop/reboot |
| `alicloud-redis-ops` | required | 2 | FLUSHALL / instance delete / backup delete |
| `alicloud-rds-ops` | required | 2 | DROP / DELETE / TRUNCATE / instance delete |
| `alicloud-polar-mysql-ops` | required | 2 | DDL via Data API / cluster delete |
| `alicloud-polar-postgresql-ops` | required | 2 | DDL / cluster delete |
| `alicloud-polar-oracle-ops` | required | 2 | DDL / cluster delete |
| `alicloud-polar-pg-ops` | required | 2 | DDL / cluster delete |
| `alicloud-mongodb-ops` | required | 2 | dropDatabase / instance delete |
| `alicloud-elasticsearch-ops` | required | 2 | delete index / cluster / `_delete_by_query` |
| `alicloud-ram-ops` | required | 2 | detach policy / delete user / rotate AccessKey |
| `alicloud-kms-ops` | required | 2 | schedule key deletion (irreversible) |
| `alicloud-eip-ops` | required | 2 | release EIP |
| `alicloud-dts-ops` | required | 2 | delete / reset / stop DTS job |
| `alicloud-vpc-ops` | required | 2 | delete VPC / vSwitch / NAT / SG |
| `alicloud-nat-ops` | required | 2 | delete NAT gateway / SNAT / DNAT |
| `alicloud-waf-ops` | required | 2 | delete domain / access control / defense rule |
| `alicloud-sls-ops` | required | 2 | delete logstore / index / alert / dashboard |
| `alicloud-slb-ops` | recommended | 3 | listener / backend server delete |
| `alicloud-ack-ops` | recommended | 3 | delete node / cluster / namespace |
| `alicloud-ack-serverless-ops` | recommended | 3 | delete cluster / application |
| `alicloud-fc-ops` | recommended | 3 | delete function / service / trigger |
| `alicloud-eci-ops` | recommended | 3 | delete container group |
| `alicloud-cms-ops` | recommended | 3 | alarm rule delete |
| `alicloud-resourcemanager-ops` | recommended | 3 | resource folder / account move |
| `alicloud-agentrun-ops` | recommended | 3 | delete agent / application |
| `alicloud-actiontrail-ops` | optional | 5 | read-only audit |
| `alicloud-billing-ops` | optional | 5 | read-only billing |
| `alicloud-das-ops` | optional | 5 | mostly read-only diagnostics |
| `alicloud-sas-ops` | optional | 5 | mostly read-only security posture |
| `alicloud-topo-discovery` | optional | 5 | read-only |
| `alicloud-skill-generator` | optional | 3 | meta operation |

**Anti-Patterns (banned)**: Shared context G+C、Subjective scoring、Unbounded loop、Critic sees user request、Silently downgrade on Safety fail、Trace not persisted、Critic mutates resources、Trace leaks secrets。

**Trace 审计**：每次 GCL 运行 MUST 持久化 JSON trace 到 `./audit-results/gcl-trace-*.json`（gitignored）。
