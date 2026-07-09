# 三层记忆优化策略 — Memory Architecture

> **架构关系**：记忆与 SkillOpt 可观测性的分工、双轨数据流与消费闭环见 [memory-observability-relationship.md](./memory-observability-relationship.md)。

## 各层解决的问题与价值

GCL 每次执行都会产生 trace，但 trace 本身是**单次、孤立、难检索**的。三层记忆从「原始记录 → 可复用模式 → 策略洞察」逐级抽象，分别解决不同粒度的问题：

| 层 | 核心问题 | 没有这一层会怎样 | 价值点 |
|----|----------|------------------|--------|
| **Layer 1 — Execution Memory** | **「这次 / 最近几次执行到底发生了什么？」** | Agent 每次 pre-flight 从零开始；无法引用同 skill、同 operation 的近期 PASS/FAIL、迭代次数、rubric 得分；排障只能翻散落的 `gcl-trace-*.json` | **可检索的执行索引**：按 `(skill, operation)` 存 JSONL，支持 `memory_retrieve(top_k)` 快速拉最近 N 次结果；为 pre-flight 注入「近期上下文」提供事实基础；TTL 清理控制存储成本 |
| **Layer 2 — Reflexion Memory** | **「同类错误为什么反复出现？下次怎么少踩坑？」** | 失败只留在单次 trace 里，跨 session 无法积累；Agent 重复犯 CLI 参数、权限、Region 等相同错误；团队知识无法沉淀为可读的 failure-patterns | **结构化失败模式 + 频率统计**：从 trace 提取**七类** pattern（含 `max_iter` / `near_miss`），dedup 递增 `count`；生成 `docs/failure-patterns.md` 供人类/AI 预读；高频模式可晋升到 H Detector / pre-flight 提示，实现**跨 session 的 Reflexion 学习** |
| **Layer 3 — Strategy Memory** | **「跨 skill、跨时间的趋势是什么？参数和策略该怎么调？」** | 只能看单 skill 近期记录或单点失败模式，看不到「哪个 skill 失败率最高」「哪些参数组合更稳」「错误模式之间是否有关联」；无法产出主动的优化建议与预防策略 | **策略级聚合与建议**（MVP）：聚合 Layer 1 时序 + Layer 2 模式 + Git 信号；**Local weekly** 写 baseline；GHA 仅 git review |

**递进关系**：Layer 1 回答「发生了什么」→ Layer 2 回答「什么模式在重复」→ Layer 3 回答「整体该怎么改」。下层是上层的数据源；上层不能替代下层（策略不能没有原始 trace 和模式统计）。

**Agent 使用口诀**（Local-first — R2 经 `memory_preflight.py` / `gcl_runner.py` 注入 trace + Generator prompt）：
- 执行前查 **Layer 1**：同 operation 最近是否 FAIL、迭代几次？→ `{{recent_executions}}`
- 执行前读 **Layer 2**：有没有已知的同类坑？→ `{{known_traps}}`
- 执行前看 **Layer 3 策略**：该 skill 是否处于高风险期？→ `{{strategy_hints}}`（读 committed `docs/strategy-baseline.json`）
- 入口：`make doctor DOCTOR_SKILL=...` 或 `gcl_runner.py`（自动）；**不依赖 GHA 上的 runtime 数据**

---

## Local-first 原则

> **Runtime 数据在本地产生、本地聚合；仓库只 commit 经审阅的衍生产物。GHA 仅作 Git 治理与可选发布通道，不是 Layer 1/2 的主数据源。**

### 数据源

| 数据 | 权威来源 | 是否 commit |
|------|----------|-------------|
| Layer 1 JSONL | 本地 `.runtime/memory/`（GCL + wrapper） | ❌ gitignore |
| Layer 2 store | 本地 `.runtime/reflexion/reflexion.json` | ❌ gitignore |
| Layer 2 报告 | `docs/failure-patterns.md` | ✅ 本地 weekly 审阅后提交 |
| Layer 3 baseline | `docs/strategy-baseline.json` | ✅ 同上 |
| Layer 3 rollup | `docs/runtime-rollup.json` | ✅ 同上（仅当有本地 Layer 1 时更新） |
| Git 信号 | 仓库 git 历史 | GHA / 本地均可采集 |

### 各层职责（Local-first）

| 层 | 写入（谁 / 在哪） | 读取（谁 / 在哪） | Weekly 维护 |
|----|-------------------|-------------------|-------------|
| **Layer 1** | 每次 GCL / wrapper 调用 → 本地 `.runtime/memory/` | `memory_preflight.py` / `make doctor`；`gcl_runner` 注入 trace | `make memory-maintain-apply`（本地） |
| **Layer 2** | GCL 终态 → 本地 `reflexion.json` | R2 `{{known_traps}}`；人类可读 `failure-patterns.md` | 本地 maintain + report；审阅后 commit md |
| **Layer 3** | 本地 `make doctor-weekly-apply` 聚合 L1/L2 + Git | R2 `{{strategy_hints}}` 读 committed baseline | **维护者本地**跑 weekly；审阅后 commit docs |

### 谁跑 weekly

| 步骤 | 执行者 | 命令 |
|------|--------|------|
| Layer 1/2 TTL + report | 开发者 / Agent（本地） | `make memory-maintain-apply`（含本地 trace TTL，默认 7 天） |
| Layer 3 全量聚合 | **维护者（本地，有 `.runtime/` 的机器）** | `make doctor-weekly-apply` |
| 提交衍生产物 | 维护者人工 PR | commit `docs/strategy-*.json/md`、`docs/failure-patterns.md`、`docs/runtime-rollup.json` |
| Git 信号周报 | GHA（可选） | `.github/workflows/doctor-weekly.yml` — **git-only 分支** |

### GHA 边界

| GHA **做** | GHA **不做** |
|------------|--------------|
| `git_collect.py` — 7d commit / bugfix 热点 | 假装扫描 Layer 1（checkout 无 `.runtime/memory` 时） |
| `gcl_strategy.py weekly` — Git + 已 committed baseline/L2 报告 | `rollup` / memory maintain（无本地 JSONL 时 **跳过**） |
| 条件 PR：`chore(doctor): weekly git review` | 依赖 Actions cache 积累 runtime memory |
| 有 artifact 上传时的 PR（罕见）：含 rollup + failure-patterns | 替代本地 `doctor-weekly-apply` |

### Baseline 写权限边界（强制）

| 产物 | Local `make doctor-weekly-apply` | GHA `doctor-weekly.yml` |
|------|----------------------------------|-------------------------|
| `docs/strategy-baseline.json` | ✅ **唯一写入方**（`weekly --apply`） | ❌ **禁止**（使用 `weekly --git-only --apply`） |
| `docs/strategy-baseline-history.jsonl` | ✅ append | ❌ 禁止 |
| `docs/strategy-report.md` | ✅ 全量报告 | ❌ 不写入 |
| `docs/strategy-git-review.md` | 可选本地预览 | ✅ GHA PR 产物（Git 信号摘要） |
| `docs/runtime-rollup.json` | ✅ 有 Layer 1 时 | ⚠️ 仅当 checkout 带 `.runtime/memory` 时 PR |
| `docs/failure-patterns.md` | ✅ 本地 reflexion report 后 commit | ⚠️ 同上 |
| `.runtime/doctor/work/git_weekly_snapshot.json` | — | ✅  ephemeral notify 输入（gitignored work dir） |

GHA 通知链读取 work snapshot，**不回写** committed baseline。

### Wrapper 路径 R2（SkillOpt）

每次 `skillopt_wrap()` 在 trace 启动后调用 `memory_preflight.py`（非致命）：

- 环境变量：`SKILLOPT_MEMORY_PREFLIGHT_ENABLED`（默认 `true`）
- stderr：`[SkillOpt] R2 preflight empty=... traps_len=...`
- 本地 trace JSON：合并 `memory_preflight` 字段（每次 wrapper 调用均写本地 trace）

与 `gcl_runner.py` 共用同一 R2 检索逻辑；Layer 3 仍读 **committed** baseline。

### 本地 Trace（SkillOpt · Local-first）

| 属性 | 值 |
|------|-----|
| **Canonical 存储** | `${SKILLS_DIR}/.runtime/traces/<skill-tag>/trace-*.json`（legacy：`alicloud-*/.runtime/traces/` 只读兼容） |
| **写入时机** | **每次** `skillopt_wrap()` — 与 Langfuse / Judge 开关无关 |
| **Langfuse** | `SKILLOPT_LANGFUSE_ENABLED=true` 时**额外** HTTP 镜像同一份 trace（optional mirror） |
| **Layer 1 联动** | `trace_end` → `memory_store_lite`（含失败时 `error_code`）→ `.runtime/memory/{skill}/{op}.jsonl` |
| **Layer 2 联动（B）** | 失败 + Allowlist → `_skillopt_reflexion_store_lite` → `store-wrapper-lite` |
| **R2 合并** | `_skillopt_memory_preflight_r2()` 写入 trace 的 `memory_preflight` 字段 |
| **TTL** | 默认 **7 天**（`TRACE_KEEP_DAYS`）；与 logs 同级 retention |
| **清理入口** | `make memory-maintain-apply` · `runtime_cleanup.py --traces-only` · 全量 `--retain` 第 4 步 |

```bash
# 预览 / 执行 trace TTL（默认 7d）
make memory-maintain
make memory-maintain-apply
TRACE_KEEP_DAYS=14 make memory-maintain-apply
python3 alicloud-aiops-cruise/scripts/lib/runtime_cleanup.py --traces-only --apply
```

Workflow 细节： [`.github/workflows/doctor-weekly.yml`](../.github/workflows/doctor-weekly.yml) ·  setup：[`doctor-review-setup.md`](doctor-review-setup.md)

### P0 消费闭环（Local 路径）

1. **检索**：`memory_preflight.py` 统一 Layer 1–3（本地 L1/L2 + committed L3）。
2. **注入**：`gcl_runner.py` 在 `run_loop()` 前检索，写入 `trace["memory_preflight"]` 与 `trace["generator_prompt_with_memory"]`（仅 `` ```text `` 正文 + 三插槽替换，无 Markdown 表格噪声）。
3. **Wrapper**：`skillopt_wrap()` → **始终**写本地 trace → `trace_end` → `memory_store_lite`（Layer 1，`error_code` 供 C 聚合）；Allowlist 失败 → plan **B** 写 Layer 2；R2 preflight 合并进 trace；Langfuse 仅 optional mirror（见上节）。
4. **模板**：所有含 `references/prompt-templates.md` 的 GCL skill 在 §1 Generator `` ```text `` 块已含三插槽（`{{known_traps}}` / `{{recent_executions}}` / `{{strategy_hints}}`）。
5. **验证**：`make doctor` · `gcl_memory_e2e_test.py` · `gcl_runner_test.py` MemoryPreflightGeneratorTests。

---

## 概述

GCL（Generator-Critic-Loop）系统的记忆层分为三层，从原始执行记录到跨 session 趋势分析，逐层抽象：

```
┌──────────────────────────────────────────────────────────────────┐
│                    Layer 3: Strategy Memory                        │
│  跨 skill 趋势聚合 · 参数优化建议 · 运维策略学习                    │
│  MVP — Local weekly · runtime-rollup.json · R2 strategy_hints      │
└───────────────────────────┬──────────────────────────────────────┘
                            │ 聚合、分析
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Layer 2: Reflexion Memory                       │
│  结构化失败模式 · 频率统计 · dedup                                 │
│  .runtime/reflexion/reflexion.json  ← 持久化存储                   │
│  docs/failure-patterns.md           ← 人类/AI 可读报告             │
│  gcl_reflexion.py                   ← 代码层                      │
└───────────────────────────┬──────────────────────────────────────┘
                            │ 提取失败模式
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Layer 1: Execution Memory                       │
│  原始 GCL trace 索引 · JSONL 格式 · 按 (skill, operation) 分文件   │
│  .runtime/memory/{skill}/{operation}.jsonl                         │
│  gcl_memory.py                   ← 代码层                          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Layer 1 — Execution Memory（执行记忆）

| 属性 | 值 |
|------|-------|
| **状态** | ✅ 已实现 |
| **代码** | `alicloud-gcl-runner-ops/scripts/gcl_memory.py` |
| **测试** | `gcl_memory_test.py` — 84 测试 |
| **R2 检索** | `memory_preflight.py` → `memory_retrieve()` |
| **存储** | `.runtime/memory/{skill}/{operation}.jsonl` |
| **保留** | TTL 30 天（可通过 `MEMORY_KEEP_DAYS` / `--memory-keep-days` 自定义） |
| **集成** | `gcl_runner.py main()` 中 `persist_trace()` 后自动调用 |

### 函数

| 函数 | 用途 | 详细文档 |
|------|------|----------|
| `memory_store(trace, trace_path)` | 索引 GCL trace 到 JSONL 文件 | — |
| `memory_retrieve(skill, operation, top_k, memory_root)` | 查询最近执行记录 | 见下文查询规范 |
| `memory_maintain(memory_root, keep_days, apply)` | 按 TTL 清理过期条目 | — |

### 查询规范

`memory_retrieve()` 是 Layer 1 的主要查询接口，供 Agent 和下游工具使用：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skill` | str | **必选** | 如 `alicloud-ecs-ops` |
| `operation` | str \| None | `None` | 按操作筛选；为 `None` 时聚合该 skill 下所有操作 |
| `top_k` | int | `5` | 返回最近 N 条记录，按 timestamp 降序 |
| `memory_root` | str \| Path \| None | `.runtime/memory/` | 覆盖存储根目录 |

**返回结构**（最优先，空列表=无记录）：
```python
[
  {
    "timestamp": "2026-06-20T12:00:00Z",   # ISO 8601
    "skill": "alicloud-ecs-ops",
    "operation": "DeleteInstance",
    "trace_path": ".runtime/audit/gcl-runner-ops/gcl-trace-...json",
    "gcl_status": "PASS",
    "iterations": 3,
    "rubric_pass": True,
    "scores": {"correctness": 1.0, ...},
    "failure_pattern": None,
  }
]
```

**消费方式**（R2 — 推荐统一入口）：
```bash
python3 alicloud-gcl-runner-ops/scripts/memory_preflight.py \
  --skill alicloud-ecs-ops --operation DeleteInstance --format slots
```

底层 API（平台内部）：
```python
from gcl_memory import memory_retrieve
recent = memory_retrieve("alicloud-ecs-ops", top_k=3)
```

**Schema 定义** 见 [`gcl-spec.md §16.3`](gcl-spec.md#163-entry-schema)。

---

## Layer 2 — Reflexion Memory（模式记忆）

| 属性 | 值 |
|------|-------|
| **状态** | ✅ 已实现 |
| **代码** | `alicloud-gcl-runner-ops/scripts/gcl_reflexion.py` |
| **测试** | `gcl_reflexion_test.py` — 75+ 测试；E2E-M1: `gcl_memory_e2e_test.py` |
| **存储** | `.runtime/reflexion/reflexion.json`（JSON 聚合存储） |
| **报告** | `docs/failure-patterns.md`（本地 weekly + 审阅后 commit） |
| **集成** | `gcl_runner.py`（GCL 终态）；wrapper plan **B** + `promote-from-memory` plan **C**；R2 检索经 `memory_preflight.py` |

### 函数

| 函数 | 用途 | 详细文档 |
|------|------|----------|
| `reflexion_extract(trace)` | 从 trace 中提取结构化失败模式 | — |
| `reflexion_store(pattern, root)` | 存储模式（dedup 递增 count） | — |
| `reflexion_report(root, output_path, sort_by)` | 生成 `docs/failure-patterns.md` | 支持 `--sort-by count\|weighted` |
| `success_report(root, output_path, sort_by)` | 生成 `docs/success-patterns.md`（R4） | `gcl_reflexion.py success-report` |
| `success_store(pattern, root)` / `success_retrieve(...)` | R4 hard-won PASS 存取 | `success_patterns.json` |
| `reflexion_retrieve(skill, operation, top_k)` | R2 pre-flight 检索已知失败模式（R5.3 三层 tier） | — |
| `normalize_error_pattern(error, command?)` | R5.1 错误归一化 → `normalized_key` | `cross-skill-patterns.md` |
| `reflexion_aggregate_generalized(...)` | R5.2 跨 skill 聚合 → `generalized_cli` | `aggregate-generalized` CLI |
| `remediation_apply_from_trace(trace)` | R6 修正确认（opportunities + PASS streak） | `remediation-tracking.md` |
| `remediation_confirm_window_k(pattern)` | R6.2 动态确认窗口 K（2–5） | — |
| `reflexion_maintain(root, min_count, decay_days, apply)` | 裁剪低频率及过期模式 | 自适应窗口见 `gcl-spec.md §15.X` |
| `reflexion_store_wrapper_lite(skill, trace_path)` | B：Allowlist wrapper 失败即时写 L2 | `store-wrapper-lite` CLI |
| `reflexion_promote_from_memory(memory_root, …)` | C：从 L1 聚合 promote / reconcile | `make memory-maintain-apply` |

### 捕获范围（Layer 2）

| GCL 终态 | 模式类别 | 说明 |
|----------|----------|------|
| `SAFETY_FAIL` | `cli_parameter` / `runtime` | safety=0 |
| `MAX_ITER` | `max_iter` | 维度 <0.5 才入库（噪声过滤） |
| `PASS`（near-miss） | `near_miss` | 某维度得分 <0.8 |

另有 `skill_generation` / `cross_skill` / `token_efficiency` 三类来自离线/生成器信号。

**Wrapper 失败 → Layer 2（B + C，2026-06）**

| 路径 | 时机 | 行为 |
|------|------|------|
| **B — 热路径** | `skillopt_trace_end` 失败且 error 在 Allowlist | `store-wrapper-lite` → `reflexion_store()` 递增 count |
| **C — 离线** | `make memory-maintain-apply` | `promote-from-memory` 扫描 L1（`source=skillopt-wrapper`、失败、`error_code` 合法）；`count ≥ 3` 才 promote；`l1_count > l2_count` 时 reconcile（防 B/C 双计数） |

Allowlist：`InvalidParameter` / `Forbidden` / `ResourceNotFound` / `QuotaExceeded` 等；Denylist：`Throttling` / `CircuitBreakerOpen` / `exit_code_*` 等。

L1 `memory_store_lite` 写入 `error_code`（从 trace 或 API `Code` 解析），供 C 聚合。

```
Wrapper trace_end (failed, allowlisted)
       │
       └──► store-wrapper-lite → reflexion_store()     ← plan B

GCL trace (SAFETY_FAIL | MAX_ITER | PASS near-miss)
       │
       └──► extract_failure_pattern() → reflexion_extract() → reflexion_store()

       ▼
.runtime/reflexion/reflexion.json
       │
       ├── promote-from-memory  ← plan C（make memory-maintain-apply）
       ├── reflexion_maintain()  ← make memory-maintain-apply（本地）
       └── reflexion_report()    ← docs/failure-patterns.md（`GCL_REFLEXION_REPORT_ON_MAINTAIN=true` 或 weekly）
```

**裁剪规则** · **失败类别** · **Schema** 详见 [`gcl-spec.md §15`](gcl-spec.md#15-reflexion-integration-layer-2--failure-pattern-memory)。

### R4 — Success Patterns（正向参考）

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 4.1–4.6 完成（2026-06-18） |
| **设计** | [`alicloud-gcl-runner-ops/references/success-patterns.md`](../alicloud-gcl-runner-ops/references/success-patterns.md) |
| **存储** | `.runtime/reflexion/success_patterns.json` |
| **人类报告** | `docs/success-patterns.md`（`gcl_reflexion.py success-report`） |
| **检索插槽** | `{{success_patterns}}` via `memory_preflight.py` → `success_retrieve()` |

与 Layer 2 失败模式互补：仅捕获 **hard-won PASS**（多轮恢复、trap 上下文后成功等），跳过 ordinary PASS。

### R5 — Cross-Skill Generalization（跨产品 CLI 陷阱）

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 5.1–5.4 完成（2026-06-21） |
| **设计** | [`cross-skill-patterns.md`](../alicloud-gcl-runner-ops/references/cross-skill-patterns.md) |
| **存储** | `reflexion.json` → `generalized_cli[]`（派生，可重建） |
| **检索** | tier 0 skill 专属 → tier 1 `generalized_cli` → tier 2 编排 `cross_skill` |
| **维护** | `make memory-maintain-apply` 末尾自动 `aggregate-generalized --apply` |

≥3 个 skill 共享同一 `normalized_key`（如 `MissingParam:InstanceId`）时聚合为一条跨产品参考，避免 ecs/rds/redis 各存一行重复教训。

### R6 — Remediation Tracking（修正确认）

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 6.1–6.4 完成（2026-06-21） |
| **设计** | [`remediation-tracking.md`](../alicloud-gcl-runner-ops/references/remediation-tracking.md) |
| **Schema** | `remediated` / `remediated_at` / `total_opportunities` / `recent_failures` / `consecutive_successes` |
| **闭环** | preflight 注入 trap → PASS 连续 K 次 → `remediated=True`；失败复发 → 反标记 |
| **检索** | 已确认陷阱得分 ×0.35；`format_known_traps` 标注 `remediated=yes` |

依赖 R4（正向 PASS 基线）与 R2（`known_traps` 注入反馈）。`gcl_runner.py` 终态调用 `remediation_apply_from_trace()`。

---

## Layer 3 — Strategy Memory（策略记忆 — Weekly Offline Review）

| 属性 | 值 |
|------|-------|
| **状态** | ✅ 已实现（MVP + R2 检索 + runtime rollup） |
| **代码** | `gcl_strategy.py`, `git_collect.py`, `strategy_github_notify.py`, `strategy_notify.py`, `strategy_synthesize.py` |
| **测试** | `gcl_strategy_test.py` + `strategy_github_integration_test.py` |
| **调度** | 本地 `make doctor-weekly-apply`（主）· GHA [`.github/workflows/doctor-weekly.yml`](../.github/workflows/doctor-weekly.yml)（Git 信号 + 可选 PR，**非 runtime 主路径**） |
| **存储** | `docs/strategy-baseline.json`（committed 基线）+ `docs/strategy-report.md`（周报） |
| **中间文件** | `.runtime/doctor/work/`（gitignored） |

**执行频次原则**：Layer 3 **不在** GCL / wrapper 热路径运行；仅 weekly batch，避免日频聚合导致过拟合。

### 目标

Layer 3 聚合 **Git 变更信号（Artifact evolution）** 与 **Layer 1/2 运行时信号**，产出跨周策略审查：

| 能力 | 输入 | 输出 |
|------|------|------|
| Git 热点分析 | 7d commits / bugfix | `hot_skills`、主题聚类 |
| 跨 skill 趋势 | Layer 1 JSONL（本地或 artifact） | failure_rate、risk_score |
| 模式晋升候选 | `failure-patterns.md` 高频行 | H Detector 候选 |
| 条件通知 | `actionable_items` | 有可行动项时开 GitHub Issue + PR 通知 |
| Pre-flight 只读 | `strategy-baseline.json` | `strategy_retrieve()` → R2 `{{strategy_hints}}`（✅ 经 `memory_preflight.py` / `gcl_runner.py` 注入 trace） |

### 函数

| 函数 / CLI | 用途 |
|------------|------|
| `git_collect.py` | 扫描 7d Git 提交，输出 `git_signals.json` |
| `gcl_strategy.py weekly --apply` | 聚合 + diff 基线 + 写 baseline/report |
| `gcl_strategy.py retrieve --skill ...` | R2 只读检索 |
| `strategy_synthesize.py` | 可选 LLM / 启发式规则提案 |
| `strategy_github_notify.py` | PR 正文（完整 report + AI Brief）+ 有 actionable 时开 Issue |
| `gcl_strategy.py rollup --apply` | 构建 `docs/runtime-rollup.json`（Local / 罕见 GHA artifact） |
| `gcl_strategy.py weekly --git-only --apply` | GHA 专用：写 `docs/strategy-git-review.md` + work snapshot；**不写 baseline** |
| `memory_preflight.py` | R2 统一检索 → `{{known_traps}}` / `{{strategy_hints}}` / `{{recent_executions}}` |

### Weekly 流程

**Local-first（主路径 — 维护者本地，有 `.runtime/` 时）：**

```
make memory-maintain-apply          ← Layer 1/2 TTL
make doctor-weekly-apply            ← rollup + git_collect + weekly --apply + report
  → 审阅 docs/strategy-*.md/json、failure-patterns.md、runtime-rollup.json
  → 人工 commit / PR
```

**GHA（辅路径 — Git 信号 + 可选 PR，无 `.runtime/memory` 时为 git-only）：**

```
doctor-weekly.yml (cron / workflow_dispatch)
  → detect .runtime/memory (*.jsonl)
  → [if memory] maintain L1/L2 · reflexion report · rollup
  → git_collect.py
  → gcl_strategy.py weekly --apply
  → strategy_synthesize · strategy_github_notify · create-pull-request
     title: chore(doctor): weekly git review
```

**GitHub Actions + Issue 数据流图**（Mermaid 总览、逐步表、Issue 分支）：见 [`docs/doctor-review-setup.md`](doctor-review-setup.md#github-actions--issue-数据流)。

**GitHub 通知**：Watch 仓库即可收 PR/Issue 邮件；PR body 含完整 report + 折叠 AI Brief；Issue 为 AI-first 结构（JSON 队列 + AI Brief）。

### 防过拟合 guardrails

| 规则 | 值 |
|------|-----|
| 统计窗口 | 7 天（与 cron 对齐） |
| 最小样本 | `STRATEGY_MIN_SAMPLES=10` |
| failure_rate 环比阈值 | ≥ 10% 才 actionable |
| bugfix 热点阈值 | 同 skill ≥ 3 bugfix / 7d |
| 首次运行 | 无基线时不产生 trend delta actionable |

---

## 三层联动流程

每次 GCL 执行完成后，三层数据流如下：

```
gcl_runner.py main()                    skillopt_wrap() → trace_end
       │                                        │
       ├── memory_store() → L1 JSONL           ├── memory_store_lite() → L1 (+ error_code)
       └── reflexion_* (GCL 终态)              └── store-wrapper-lite (B, allowlist)
       
make memory-maintain-apply:
       ├── memory_maintain()     → prune Layer 1 (TTL 30d)              ← Layer 1
       ├── trace TTL cleanup     → trace-*.json + skillopt-session-* (7d) ← Local trace
       ├── reflexion_maintain()  → prune Layer 2 (count + decay)         ← Layer 2
       ├── promote-from-memory   → L1 failed wrapper → L2 reconcile (C)  ← Layer 2
       ├── success-report        → docs/success-patterns.md (R4)           ← Layer 2+
       ├── aggregate-generalized → rebuild generalized_cli (R5)          ← Layer 2
       └── reflexion_report()    → docs/failure-patterns.md (doctor-weekly-apply)
       入口: 本地 `make memory-maintain-apply` · `make doctor-weekly-apply`（含上列 + rollup + baseline）
       
独立调度（weekly — Local-first）：
       ├── gcl_strategy rollup   → docs/runtime-rollup.json   ← 仅本地有 Layer 1 时
       └── gcl_strategy weekly   → baseline/report            ← make doctor-weekly-apply
       **首次本地 weekly 已完成** (2026-06-21): baseline + rollup + failure-patterns committed (`6415886`)
       GHA: git-only PR when checkout 无 .runtime/memory
```

## 观测性日志架构

所有三层的核心操作都输出结构化日志，供 Agent 自动解析。

| 层 | 函数 | 日志格式 | 关键事件 |
|----|------|----------|----------|
| Layer 1 | `memory_store()` | `event=memory_store result=success\|failed` | 存储结果与 trace 文件名 |
| Layer 2 | `reflexion_extract()` | `event=reflexion_extract decision=... pattern=found\|skipped` | 是否提取到失败模式及其原因 |
| Layer 2 | `reflexion_store()` | `event=reflexion_store result=success\|failed\|skipped` | 存储成功/失败/跳过，category |
| Layer 2 | `reflexion_store_wrapper_lite()` | `event=store_wrapper_lite result=success` | plan B wrapper 热路径 |
| Layer 2 | `reflexion_promote_from_memory()` | `[REFLEXION] promote-from-memory ...` | plan C 离线 reconcile |
| Layer 2 | `reflexion_maintain()` | `event=<prune\|maintain>` with per-category detail | 自适应窗口、prune 原因 |
| Layer 2 | `remediation_apply_from_trace` | `event=remediation_confirm` / `remediation_unmark` | R6 confirm / relapse |
| Layer 2 | `reflexion_aggregate_generalized` | `event=aggregate_generalized` | R5 cross-skill rebuild |

日志格式统一为 `[HH:MM:SS] [GCL-RUNNER\|REFLEXION] event=name key=value [...]`，
所有字段用 `key=value` 对编码，AI 无需正则即可提取结构化信息。

## 质量门

Layer 1 / Layer 2 的详细质量门定义在 [`gcl-spec.md §16.7`](gcl-spec.md#167-quality-gates) 和 [`§15`](gcl-spec.md#15-reflexion-integration-layer-2--failure-pattern-memory) 中。以下为跨层和额外的 Gate：

| 检查 | 标准 | 级别 |
|------|------|------|
| **E2E-M1** | `memory_store` → `reflexion_store` → `reflexion_report` 端到端集成测试存在（覆盖完整数据流） | P0 |
| **LOG-M1** | 所有 `_log()` 输出格式一致；`check_log_lint.py` 在 CI `gcl-test` job 强制执行 | P1 ✅ |
| **L3-M1** | `gcl_strategy_test.py` ≥15 tests；weekly job 不触发热路径；notify skip 当无 actionable | P0 |
