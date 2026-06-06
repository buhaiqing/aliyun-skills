---
name: alicloud-aiops-cruise
version: "1.0.0"
metadata:
  description: >-
    阿里云全链路 AIOps 巡检 Skill — 从 EIP→SLB→ECS→RDS/Redis→NAT→安全组的端到端健康巡检、
    故障排查、容量规划和预检。Agent 通过 aliyun CLI 编排阿里云原生服务
    (CloudMonitor / DAS / CloudAssistant / ResourceCenter / ActionTrail / CloudFirewall)
    完成拓扑发现、指标采集、深度诊断和链路关联推理。
    纯读操作，不执行任何资源变更。
  cli_applicability: dual-path
  cli_version_locked: false
  sdk_version_locked: false
---

# 阿里云全链路 AIOps 巡检 — alicloud-aiops-cruise

> **一句话定位**：跨 EIP → SLB → ECS → RDS/Redis → NAT → 安全组的端到端链路巡检。
> 不做资源变更，只做发现、诊断、推理和报告。

## 🧠 提示知识力

> 以下是本 Skill 的核心设计哲学，帮助理解它和现有技能的差异：

| 知识点 | 说明 |
|---|---|
| **为什么叫 "Cruise" 而不是 "Check"？** | Cruise 是一次"巡航式穿透"—— 从入口 EIP 一路穿到后端数据层和出网层，逐跳检查链路中各节点的健康状态，而非孤立地查单个产品 |
| **和 topo-discovery 有什么区别？** | `topo-discovery` 做静态拓扑发现和 HCL 导出；`aiops-cruise` 做动态健康巡检（含监控、诊断、推理）。拓扑发现是链路巡检的"前置步骤"而非终点 |
| **和 cms-ops 有什么区别？** | `cms-ops` 查单个产品的监控指标；`aiops-cruise` 跨产品组合指标做链路关联推理（例如：SLB 健康检查失败 + ECS 正常 = 查网络连通性） |
| **巡检为什么是"纯读"？** | 巡检是发现问题的眼睛，不是解决问题的手。发现问题后出"建议"，具体变更通过对应的 ops skill（如 `alicloud-ecs-ops`）由用户确认后执行 — 这是安全边界 |
| **链路推理的价值** | 全链路巡检的价值不在于采集指标（CLI 都能做），而在于把分散的指标组合成一条"推理链"：A 现象 + B 现象 → 根因概率排序 → 可执行建议 |
| **标签 vs 资源组，怎么选？** | 标签灵活但依赖维护（可能漏打）；资源组是云资源管理的原生单位，更可靠。推荐优先使用**资源组（ResourceGroupId）**扫描，标签作为回退方案。详见 `references/execution-guide.md` 的资源组章节 |

## Trigger & Scope

### SHOULD Use

- 需要对指定客户（按标签）或业务系统做全链路健康检查
- 需要排查从公网入口到后端数据库的整条链路故障根因
- 需要做容量规划（30 天趋势预测）或大促前 3x 流量压力预检
- 需要安全合规审计（安全组开放端口 + Cloud Firewall 策略 + ActionTrail 操作事件）
- 需要了解某个业务系统的阿里云资源拓扑和健康全景

### SHOULD NOT Use

- 只查单个资源（如单台 ECS）→ 使用 `alicloud-ecs-ops` 或对应产品 ops skill
- 需要创建/修改/删除资源 → 使用对应产品的 ops skill
- 只查监控指标（不需要链路推理）→ 使用 `alicloud-cms-ops`
- 只做拓扑发现（不需要健康诊断）→ 使用 `alicloud-topo-discovery`
- 不涉及阿里云资源的巡检 → 不使用

### Cross-Skill References

| 需求 | 参考 Skill | 引用方式 |
|---|---|---|
| 监控指标采集 | `alicloud-cms-ops` | 复用 `--Namespace/MetricName/Period` 参数约定 |
| DAS 数据库诊断 | `alicloud-das-ops` | 复用 `assets/code-snippets/` 的 Go 零件 |
| CloudAssistant 内检测 | `alicloud-agentrun-ops` | 复用 RunCommand 交互模式 |
| 拓扑发现 | `alicloud-topo-discovery` | 用户需纯拓扑图时引导至此 |
| ECS 详细诊断 | `alicloud-ecs-analysis-aliyun` | 引用分析框架思路 |
| SLB 详细诊断 | `alicloud-slb-ops` | 引用 Describe* 命令模式 |

## Variable Convention

| 类型 | 含义 | 来源 | 示例 |
|---|---|---|---|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | AK ID | 运行时环境变量，NEVER ask user | — |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | AK Secret | 运行时环境变量，NEVER exposed | — |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | 默认区域 | 运行时环境变量 | `cn-hangzhou` |
| `{{user.customer_name}}` | 客户名/标签值 | 每次巡检时询问 | `烟台振华` |
| `{{user.scenario}}` | 巡检场景 | 用户选择 | `daily_check` |
| `{{user.enable_das}}` | 启用 DAS 深度诊断? | 用户确认 (Y/N) | `true` |
| `{{user.enable_cloud_assistant}}` | 启用内检测? | 用户确认 (Y/N) | `true` |
| `{{output.topology}}` | 拓扑发现结果 | ResourceCenter 输出解析 | JSON |
| `{{output.metrics}}` | 监控指标 | CloudMonitor 输出聚合 | JSON |
| `{{output.das_report}}` | DAS 诊断报告 | Go SDK 输出 | JSON |
| `{{output.chain_inference}}` | 链路推理结论 | Agent 推理结果 | Markdown |

## 🚨 Safety Gates（安全铁律）

> **本 Skill 是纯读（Read-Only）巡检，不执行任何写操作。**

| 红线 | 要求 | 违规后果 |
|---|---|---|
| **任何资源的删除/释放** | ❌ 不允许自动执行 | Safety = 0，GCL 立即 ABORT |
| **任何资源的停止/关机/重启** | ❌ 不允许自动执行 | Safety = 0，GCL 立即 ABORT |
| **任何资源的规格变更/升配** | ❌ 不允许自动执行，报告只出建议 | Safety = 0，GCL 立即 ABORT |
| **安全组规则增删** | ❌ 不允许自动执行 | Safety = 0，GCL 立即 ABORT |
| **巡检报告含 AK/SK** | ❌ 必须掩码为 `AKID****SKRET` | 严重违规 |
| **巡检触发** | 必须有客户/标签筛选，严禁扫全账号 | — |
| **默认资源组扫描** | ❌ 自动跳过 default/空资源组，除非用户明确要求全账号扫描 | Safety = 0，立即 HALT |
| **报告输出** | JSON 持久化到 `audit-results/` | — |

## Skill Maintenance Rules（技能维护规范）

> 本技能在开发和完善过程中必须遵守以下规则。

### MR-1: TODO.md 同步（MANDATORY）

每次新增功能、修改能力、修复缺陷后，**必须同步更新 `TODO.md`** 中的对应状态：
- 已完成项: `[ ]` → `[x]`
- 新增项: 追加到对应 Sprint 章节
- 已变更项: 更新描述和验证标准

违反后果：Post-Update Self-Review 的 F8 检查不通过，不得提交。

### MR-2: 规范文档先行

新增能力必须先产出规范文档（`references/` 下），再写业务逻辑。

### MR-3: 验证标准可复现

每条 TODO 项必须包含明确的验证命令或检查方式，确保持续集成可重复验证。

### MR-4: 质量门定期评审（MANDATORY）

> **质量门不是一次性设置——它需要持续的审视和优化。**
> 完整流程定义见 `references/quality-review-process.md`。

所有 Sprint 的质量门（TODO.md 中各 Sprint 的 Q 检查表）必须按以下节奏定期评审：

| 周期 | 范围 | 动作 |
|------|------|------|
| **每 Sprint** | 当前 Sprint 的所有质量门 | 标记完成前全部运行一遍，全部通过才可标记 [x] |
| **每周** | 所有活跃 Sprint 的质量门 | 周一检查是否有质量退化，误报率/漏报率是否超标 |
| **每月** | 全部质量门的趋势分析 | 生成趋势报告，决定哪些门需要调整/新增/淘汰 |

> 违反后果：质量门评审缺失的 Sprint 标记为"质量未确认"，后续 Sprint 发现质量退化时追溯负责人。

### MR-5: TODO/Sprint 文件拆分规范（MANDATORY）

> 每个 Sprint 独立文件存储于 `TODO/` 目录，`TODO.md` 仅作索引。

当新增 Sprint 时，**必须**：
1. 在 `TODO/` 目录下创建 `sprint-{编号}-{名称}.md`
2. 包含：业务价值、交付物、前置条件、任务清单、质量门
3. 在 `TODO.md` 索引表中添加一行引用

禁止将 Sprint 的任务细节直接写在 `TODO.md` 中。

### MR-6: 代码审查规范（MANDATORY）

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
| **可读性** | 魔术数字→具名常量, 函数 ≤30 行, 复杂路径加注释 | `1,0,"w","c"` | `RG_YES, RG_NO, W, C` |
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

**流程**: 修改脚本 → `code-reviewer` 评审 → 修复 P0/P1 → 合并

违反后果：Post-Update Self-Review 的 F8 检查不通过，不得提交。

### MR-7: Lint 检测规范（MANDATORY）

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

**流程**：修改脚本 → `ruff check --fix` → `ruff format` → `code-reviewer` 评审 → 合并

违反后果：Post-Update Self-Review 的 F8 检查不通过，不得提交。

## Pre-flight Interaction

```
📋 阿里云全链路 AIOps 巡检配置

1. 巡检范围（二选一）:
   [T] 按资源组扫描（推荐）— 输入资源组ID
       → 例: rg-acfmvyfsd4znnoi
       → 也可输入一个资源ID，自动反查所属资源组后扫描全组
   [L] 按标签扫描 — 输入标签键和标签值
       → 例: customer / 烟台振华

2. 巡检场景:
   [1] 日常健康巡检
   [2] 故障应急排查
   [3] 容量规划
   [4] 大促前预检

3. 巡检范围（可选，默认全链路）:
   [a] 全链路
   [b] 仅网络层（EIP→SLB→VPC）
   [c] 仅计算层（ECS→ACK）
   [d] 仅数据层（RDS→Redis→MongoDB）

4. 深度诊断选项:
   启用 DAS 数据库深度诊断? (Y/N，默认 Y)
   启用 CloudAssistant 内检测? (Y/N，默认 N)
```

## Execution Flow Overview

本 Skill 采用三阶段执行模式，具体步骤因场景而异（详见 runbooks/）。

### Phase 1: 嗅探 + 拓扑发现

```
核心命令:
  aliyun resourcecenter SearchResources        # 跨产品资源搜索
  aliyun vpc DescribeVpcs / DescribeVSwitches  # VPC 拓扑
  aliyun slb DescribeLoadBalancers             # SLB 后端映射
```

输出：拓扑初判报告（Markdown）+ 待人工确认清单（如需）

### Phase 2: 深度采集 + 诊断

```
核心数据源:
  CloudMonitor: 6h 指标 + 昨日/上周环比     # aliyun cms DescribeMetricList
  DAS (JIT Go SDK): 慢查询 / 性能洞察       # go run das_slow_query.go
  CloudAssistant: 进 ECS 内查进程/端口/日志  # aliyun ecs RunCommand
  ActionTrail: 近期操作事件                  # aliyun actiontrail LookupEvents
```

### Phase 3: 推理 + 报告

```
Agent 对照 references/inference-rules.md 做链路关联推理:
  现象组合 → 匹配 pattern → 根因概率排序 → 建议

输出: Markdown(给人读) + JSON(持久化)
```

## Quality Gate (GCL)

### Rubric Dimensions

| 维度 | 阈值 | 说明 |
|---|---|---|
| **Correctness** | ≥ 0.5 | 巡检结论与实际情况一致 |
| **Safety** | = 1 | 纯读操作，任何写操作为 0 |
| **Idempotency** | ≥ 0.8 | 相同输入在不同时间应产出一致结论 |
| **Traceability** | ≥ 0.8 | 报告含完整执行上下文（命令、参数、响应） |
| **Spec Compliance** | ≥ 0.8 | 严格遵循 runbook 定义和阈值规范 |

### GCL Prompt

见 `references/prompt-templates.md`。

## Runbook Index

| 编号 | 场景 | 风险等级 | 执行时间 | 适用时机 |
|---|---|---|---|---|
| 01 | 日常健康巡检 | 低 | 5-15min | 每 6h / 按需 |
| 02 | 故障应急排查 | 高 | 3-8min | 告警触发 / 用户报障 |
| 03 | 容量规划 | 中 | 5-10min | 每周 |
| 04 | 大促前预检 | 高 | 10-20min | 大促前 3 天 |

详细执行步骤见对应 runbook。

## Well-Architected Assessment

### 安全 (Security)

| 方面 | 指导 |
|---|---|
| **IAM** | 最小权限原则，巡检仅需各产品只读权限 + CloudAssistant 执行权限 |
| **Credential** | `{{env.*}}` ONLY，输出掩码 |
| **数据敏感** | 资源 ID、IP、配置是敏感基础设施数据，限报告分发范围 |

### 稳定 (Stability)

| 方面 | 指导 |
|---|---|
| **面向失败** | 单个 Analyzer 失败不影响其他 Analyzer，部分结果仍有价值 |
| **运维管控** | 定期巡检可追踪配置漂移和容量变化 |
| **应急恢复** | 故障 runbook 的决策树帮助快速定位根因 |

### 成本 (Cost)

Describe/List/Get 类 API 免费，仅 CloudAssistant RunCommand 消耗少量执行费用。

### 效率 (Efficiency)

- **并行采集**：CLI 命令可后台并发执行（`& PID` + `wait`）
- **渐进式深度**：标准模式仅 CloudMonitor + CLI；深度模式按需开启 DAS / CloudAssistant

### 性能 (Performance)

| 操作 | API 调用数 | 预估时间 |
|---|---|---|
| Phase 1 拓扑发现 | ~5-8 次 | < 1min |
| Phase 2 标准采集 | ~15-25 次 | 2-5min |
| Phase 2 深度模式 (+DAS/+CloudAssistant) | +5-10 次 | +3-8min |

## Changelog

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0.0 | 2026-06-06 | 初始版本 |