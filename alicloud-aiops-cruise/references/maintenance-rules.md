---
name: maintenance-rules
version: "1.0.0"
parent: alicloud-aiops-cruise
---

# 技能维护规范（MR-1 ~ MR-9）

> 本技能在开发和完善过程中必须遵守以下规则。Agent 在修改代码或文档前应先加载本文件。

## MR-1: TODO.md 同步（MANDATORY）

每次新增功能、修改能力、修复缺陷后，**必须同步更新 `TODO.md`** 中的对应状态：
- 已完成项: `[ ]` -> `[x]`
- 新增项: 追加到对应 Sprint 章节
- 已变更项: 更新描述和验证标准

违反后果：Post-Update Self-Review 的 F8 检查不通过，不得提交。

## MR-2: 规范文档先行

新增能力必须先产出规范文档（`references/` 下），再写业务逻辑。

## MR-3: 验证标准可复现

每条 TODO 项必须包含明确的验证命令或检查方式，确保持续集成可重复验证。

## MR-4: 质量门定期评审（MANDATORY）

> **质量门不是一次性设置——它需要持续的审视和优化。**
> 完整流程定义见 `references/quality-review-process.md`。

所有 Sprint 的质量门（TODO.md 中各 Sprint 的 Q 检查表）必须按以下节奏定期评审：

| 周期 | 范围 | 动作 |
|------|------|------|
| **每 Sprint** | 当前 Sprint 的所有质量门 | 标记完成前全部运行一遍，全部通过才可标记 [x] |
| **每周** | 所有活跃 Sprint 的质量门 | 周一检查是否有质量退化，误报率/漏报率是否超标 |
| **每月** | 全部质量门的趋势分析 | 生成趋势报告，决定哪些门需要调整/新增/淘汰 |

> 违反后果：质量门评审缺失的 Sprint 标记为"质量未确认"，后续 Sprint 发现质量退化时追溯负责人。

## MR-5: TODO/Sprint 文件拆分规范（MANDATORY）

> 每个 Sprint 独立文件存储于 `TODO/` 目录，`TODO.md` 仅作索引。

当新增 Sprint 时，**必须**：
1. 在 `TODO/` 目录下创建 `sprint-{编号}-{名称}.md`
2. 包含：业务价值、交付物、前置条件、任务清单、质量门
3. 在 `TODO.md` 索引表中添加一行引用

禁止将 Sprint 的任务细节直接写在 `TODO.md` 中。

## MR-6: 代码审查规范（MANDATORY）

> 以下文件类型在新增或修改后，**必须**触发 `code-reviewer` 技能自动评审：
> - `*.sh`（Shell 脚本）
> - `*.py`（Python 脚本）
> - `*.go`（Go 脚本/source）
> - `*/scripts/*`、`*/assets/code-snippets/*` 目录下任意文件
>
> 评审后发现的 P0/P1 问题必须全部修复后方可提交。

| 触发条件 | 审查范围 | 禁止行为 |
|----------|---------|---------|
| 新增 `*.sh` / `*.py` / `*.go` 文件 | 全量评审 | 未经 review 直接合并 |
| 修改 `runbooks/scripts/` / `assets/code-snippets/` 下文件 | diff 评审 | 仅修改不改 review |
| Sprint 完成前 | 该 Sprint 涉及的全部脚本 | 跳过审查标记完成 |

**基础代码质量要求**（LLM 生成时必须遵守）：

| 维度 | 要求 | 违规示例 | 正确做法 |
|------|------|---------|---------|
| **可重用性** | 公共函数提取到共享模块 (`_shared.py`), 4 个脚本零重复 | 每个脚本各自定义 `dig()` | `from _shared import dig` |
| **可读性** | 魔术数字->具名常量, 函数 ≤30 行, 复杂路径加注释 | `1,0,"w","c"` | `RG_YES, RG_NO, W, C` |
| **健壮性** | try 指定异常类型, 不吞噬 `KeyboardInterrupt` | `except: pass` | `except TimeoutExpired:` |
| **可测试性** | 纯函数与 IO 函数分离 | IO 混在业务逻辑中 | IO 单独封装到 `q()`, 业务用纯函数 |
| **安全性** | 无硬编码凭证, 无 shell injection | `f"aliyun {user_input}"` | `["aliyun", arg]` |
| **可维护性** | 语义化命名, 模块单一职责, 版本号随大版本更新 | `data`, `tmp`, `x` | `dps`, `metrics_data`, `anomalies` |
| **错误处理** | 所有异常必须处理, 不可见错误必记日志 | 静默失败 | `err("E020")` |

**评审标准**（源自 `code-reviewer` skill 的 P0/P1/P2 定义）：
- P0: Shell injection (`shell=True`), 硬编码凭证, bare `except:`, 裸 `subprocess.run(shell=True)`, `os.system()`, `eval()`
- P1: 重复逻辑块、魔术数字、不统一退出码、参数不一致、未使用的死代码
- P2: **串行阻塞 I/O 未并行化**（API 调用是 I/O 密集型，必须用 `ThreadPoolExecutor` 或 `asyncio` 并行）、缺失参数处理、路径硬编码、文档缺失
- P3: 风格问题（命名、注释）

**流程**: 修改脚本 -> `code-reviewer` 评审 -> 修复 P0/P1 -> 合并

违反后果：Post-Update Self-Review 的 F8 检查不通过，不得提交。

## MR-7: Lint 检测规范（MANDATORY）

> 所有脚本在新增或修改后，**必须**通过 Linter 检查方可提交。
> Linter 发现的 P0/P1 问题必须全部修复。

| 语言 | 工具 | 命令 | 违规级别 |
|------|------|------|---------|
| Python | **Ruff** | `ruff check --fix scripts/*.py` + `ruff format scripts/*.py` | P1 |
| Shell | **shellcheck** | `shellcheck scripts/*.sh` | P0 (注入风险) / P2 (其他) |
| Go | **golangci-lint** | `golangci-lint run assets/code-snippets/...` | P1 |
| Markdown | **markdownlint-cli2** | `npx markdownlint-cli2 "alicloud-*/runbooks/*.md"` | P3 |

已配置于 `pyproject.toml`：
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
```

**流程**：修改脚本 -> `ruff check --fix` -> `ruff format` -> `code-reviewer` 评审 -> 合并

违反后果：Post-Update Self-Review 的 F8 检查不通过，不得提交。

## MR-8: 文案规范 — 避免表情符号，使用纯文本（MANDATORY）

> 表情符号（emoji）在不同终端、Markdown 渲染器、日志系统或 CI 输出中表现不一致（如 PASS/FAIL 在某些系统显示为乱码或方框），
> 且增加 token 消耗。所有输出和文档统一使用纯文本标识。

| 场景 | 错误示例 | 正确示例 |
|------|---------|---------|
| 通过/失败状态 | `PASS` / `FAIL` | `PASS` / `FAIL` |
| 级别标识 | `CRITICAL` / `WARNING` / `SAFE` | `CRITICAL` / `WARNING` / `SAFE` |
| 章节标题图标 | `## [BACK] 历史回溯` | `## 历史回溯 (7d)` |
| 列表图标 | `### [LIST] SLS 审计事件` | `### SLS 审计事件` |
| 状态前缀 | `[WARN] 无法获取数据` | `[WARN] 无法获取数据` |
| 注释中的级别 | `# SAFE < 80%` | `# SAFE < 80%` |

**例外**：在交互式 CLI 的进度提示或用户直接交互的界面中，表情符号可以作为视觉辅助使用（如 `[LIST]` 配置向导），
但所有**输出报告**、**日志**、**文档注释**和**代码注释**必须使用纯文本。

违反后果：Post-Update Self-Review 的 F8 检查不通过，不得提交。

## MR-9: 写操作确认规范 — 任何变更操作必须经人工确认（MANDATORY）

> 本 Skill 是纯读（Read-Only）巡检，但在运行过程中或建议中可能会引用到需要执行变更的操作。
> 所有可能产生状态变更的操作（包括但不限于资源创建、删除、修改、启动/停止、升/降配、规则增删）
> **必须**通过用户确认后方可执行，禁止脚本或 Agent 自动发起写操作。

| 操作类型 | 示例 | 处理规则 |
|---------|------|---------|
| **巡检采集**（只读） | `DescribeMetricList`, `DescribeInstances`, `kubectl get` | PASS 自动执行，无需确认 |
| **组件安装** | `POST /clusters/{id}/components/install` | [LOCK] 输出安装命令，由用户确认后自行执行 |
| **资源创建/释放** | `CreateCluster`, `DeleteCluster` | [LOCK] 输出建议，由用户决定并执行 |
| **配置变更** | `ModifyDBInstanceSpec`, `RevokeSecurityGroup` | [LOCK] 输出建议，由用户决定并执行 |
| **数据操作** | `kubectl delete pod`, `kubectl drain node` | [LOCK] 输出建议，由用户决定并执行 |

**巡检建议中的命令标记**：

所有输出到巡检报告中的 CLI 命令必须明确标注执行等级（详细定义见 [`references/pre-approved-whitelist.md`](pre-approved-whitelist.md)）：

| 标记 | 级别 | 含义 | 触发条件 |
|------|------|------|---------|
| `[READONLY]` | L0-只读 | 安全的只读操作，可自动执行 | 任何场景 |
| `[SUGGESTED]` | L3 | 需要用户确认后执行 | 任何场景 |
| `[AUTO-QUIET]` | L0 | 预授权只读操作（CloudAssistant 诊断命令） | 命中白名单 W-01 + 命令前缀在 §四 允许清单 |
| `[AUTO-NOTIFY]` | L1 | 预授权低风险操作，执行后通知 | 命中白名单 W-02/W-03 + 前置条件满足 |
| `[AUTO-CONFIRM]` | L2 | 预授权中风险操作，需提前通知 + 二次确认 | 命中白名单 W-NN + 用户已订阅 |

**安全铁律**（不可覆盖）：

| 红线 | 违规后果 |
|------|---------|
| 巡检脚本中不允许出现非只读 API 调用 | Safety = 0，GCL 立即 ABORT |
| `kubectl delete` / `drain` / `cordon` / `taint` 等不允许在脚本中自动执行 | Safety = 0，GCL 立即 ABORT |
| 通过 CloudAssistant 执行的命令必须是只读 shell 命令 | Safety = 0，GCL 立即 ABORT |
| 任何写操作必须先输出建议 -> 用户确认 -> 用户自行执行 | Safety = 0，GCL 立即 ABORT |

**例外**：经预授权白名单（[`references/pre-approved-whitelist.md`](pre-approved-whitelist.md)）审核通过的操作，可纳入 `[AUTO-*]` 自动执行名单，
但白名单必须经安全团队审批、每季度复审、且每次执行落盘审计日志到 `audit-results/audit/whitelist-{YYYY-MM-DD}.jsonl`。

违反后果：Post-Update Self-Review 的 F8 检查不通过，不得提交。