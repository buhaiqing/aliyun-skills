# ADR-002: 固化工作流引擎 + 预授权白名单（Level 4 P0 基础）

| 字段 | 值 |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-08-06 (v1 初稿) |
| **Deciders** | Skills 平台架构组 |
| **Supersedes** | — |
| **Related** | [ARCHITECTURE.md](../ARCHITECTURE.md) §双引擎架构、[TODO.md](../TODO.md) Level 3 → 4、[aiops-cruise/references/pre-approved-whitelist.md](../../alicloud-aiops-cruise/references/pre-approved-whitelist.md)、[aiops-cruise/TODO/sprint-12-dual-engine.md](../../alicloud-aiops-cruise/TODO/sprint-12-dual-engine.md) |

> **本 ADR 在 ARCHITECTURE.md 中的位置**: 本决策定义了 Level 4 主动自治的 P0 基础能力——「固化工作流引擎」(workflow-runner) 与「预授权操作白名单」(pre-approved-whitelist) 的设计契约与职责分工。落地前需复核 ARCHITECTURE.md 中「双引擎架构」章节是否需要同步更新引用。

---

## 1. Context（背景）

### 1.1 现状

Level 3 已完成（Phase A-D 全 ✅），核心能力：

- **反馈闭环**：Reflexion 自动填充 + Pre-flight 强制注入 + TTL 维护
- **事前预判**：Risk Score 预评分 + 动态 max_iter + Pass-Rate 异常检测
- **跨维度融合**：AIOps 7 感知 Agent 融合 + 根因推理 + 行动建议编排
- **主动运营**：每周自动巡航 + 变配预检 + 风险预警工单化

**Level 3 的边界**：所有执行路径最终都回到「建议 + 人工确认」。即使是 RDS 清理 binlog 这类极低风险操作，也必须等用户逐条确认（见 `pre-approved-whitelist.md` §一）。

### 1.2 进入 Level 4 的核心缺口

| 缺口 | Level 3 现状 | Level 4 要求 |
|------|-------------|-------------|
| **固化执行** | 巡检依赖 Agent 调 Bash，凌晨无人时无法自触发 | 固化工作流引擎，毫秒级响应，无 LLM 推理 |
| **自动执行** | 所有写操作 `[SUGGESTED]` 需确认 | 白名单内 L0/L1 操作自动执行（秒级 MTTR） |
| **闭环验证** | 建议输出即结束 | 执行后自动验证 + 失败回滚 |
| **调度路由** | 手动触发 | cruise-orchestrator 自动选 runbook + agent 兜底 |

### 1.3 已有基础

| 资产 | 状态 | 说明 |
|------|------|------|
| `pre-approved-whitelist.md` v1.0 | ✅ 已落地 | W-01/W-02/W-03 白名单矩阵 + 分级 + 复审 + 审计 |
| Sprint 12 双引擎设计 | ✅ 设计完成 | Stage 2 D1 幂等加固 PASS；Stage 3 D1 组件待实现 |
| 4 个 runbook Python 脚本 | ✅ PASS | 固化工作流的输入源 |
| 缓存层 + Incident Schema | ✅ PASS | 固化引擎内置 cache 依赖 |

### 1.4 核心约束

- **安全铁律不可破**：白名单外操作必须 HITL 确认（AGENTS.md §8.1）
- **可观测强制**：每次自动执行必须写 trace + 审计日志
- **可回滚强制**：每个白名单项必须有 undo 指令
- **幂等可重入**：固化工作流并发执行不得重复操作（file lock）
- **零 LLM 依赖**：固化引擎热路径不得调用 LLM（成本 + 延迟）

---

## 2. Decision（决策）

采用 **「固化工作流引擎 + 预授权白名单」双基石架构**，作为 Level 4 主动自治的 P0 基础。

### 2.1 架构关系

```text
┌─────────────────────────────────────────────────────────────┐
│                    cruise-orchestrator.py                    │
│              (主调度器: cron/event → 选 runbook)              │
└───────────────┬─────────────────────────────────────────────┘
                │
    ┌───────────┴────────────┐
    │                        │
┌───▼──────────────┐  ┌──────▼───────────┐
│ workflow-runner  │  │  agent-fallback  │
│ (固化工作流引擎) │  │  (弹性兜底)      │
│ 90% 场景         │  │  10% 异常        │
│ 无 LLM 推理      │  │  LLM + 工具调用  │
└───────┬─────────┘  └──────┬───────────┘
        │                    │
        ▼                    │
┌──────────────────┐         │
│ pre-approved-     │◄────────┘
│ whitelist 校验    │  (兜底执行也须命中白名单)
│ (L0/L1 自动执行)  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 审计日志 + trace  │
│ (强制可观测)      │
└──────────────────┘
```

### 2.2 固化工作流引擎（workflow-runner）

**职责**：

- 加载预编译 DAG（runbook 步骤图），零 LLM 延迟（目标 < 1s）
- 串行/并行调度步骤，file lock 防并发重入
- 每步执行后调用白名单校验；命中 L0/L1 自动执行，否则转 agent-fallback
- 执行后自动验证（验证命令），失败触发回滚

**关键设计**：

| 项 | 决策 |
|----|------|
| DAG 来源 | runbook Python 脚本的 `--dry-run` 输出预编译为 JSON |
| 并发控制 | `.lock` 文件（同 runbook 同时间仅一个实例） |
| 缓存 | 内置内存缓存层（Sprint 12 策略 C 演进） |
| 回滚 | 每步 `undo` 指令在 DAG 中声明 |
| 升级 | 连续失败 / 未知输入 → `agent-fallback.py` |

### 2.3 预授权白名单（pre-approved-whitelist）

**已有 v1.0 矩阵**，本 ADR 确认其作为 Level 4 自动执行的**唯一准入依据**：

| 级别 | 标签 | 自动执行 | 通知 |
|------|------|---------|------|
| L0 | `[AUTO-QUIET]` | ✅ 自动（只读诊断） | 不通知 |
| L1 | `[AUTO-NOTIFY]` | ✅ 自动（清理类） | 钉钉 @oncall |
| L2 | `[AUTO-CONFIRM]` | ⏸ 等待期确认 | 通知 + 二次确认 |
| L3 | `[MANUAL]` | ❌ 禁止 | — |

**强制规则**：任何 `[AUTO-*]` 标签操作必须命中白名单矩阵，且触发对应审计日志（AGENTS.md Safety = 0）。

### 2.4 组件清单（P0 交付物）

| # | 组件 | 文件 | 职责 |
|---|------|------|------|
| C1 | cruise-orchestrator | `runbooks/scripts/cruise-orchestrator.py` | 主调度，cron/event 接入 |
| C2 | workflow-runner | `runbooks/scripts/workflow-runner.py` | 固化 DAG 执行，无 LLM |
| C3 | agent-fallback | `runbooks/scripts/agent-fallback.py` | 异常场景 LLM 兜底 |
| C4 | runbook-dispatcher | `runbooks/scripts/runbook-dispatcher.py` | runbook 选择路由 |
| C5 | cron-template | `references/cron-template.yaml` | Cron 配置模板 |
| C6 | 白名单校验器 | 集成进 workflow-runner | L0/L1 自动执行判定 |

---

## 3. Consequences（影响）

### 3.1 正向

- MTTR 从「发现→等用户→确认→执行」压缩到秒级（L0/L1 白名单内）
- 凌晨无人时段巡检自触发（固化引擎 + Cron）
- 90% 场景零 LLM 成本（固化引擎热路径）
- 安全铁律通过白名单矩阵强制执行（不依赖 Agent 自觉）

### 3.2 负向 / 风险

| 风险 | 缓解 |
|------|------|
| 固化 DAG 偏离实际 runbook | 每次 runbook 变更须重新预编译 DAG + 回归测试 |
| 白名单操作误执行 | 季度复审 + 紧急下线机制（pre-approved-whitelist.md §五） |
| 并发重入导致重复操作 | file lock + 幂等检查 |
| 固化引擎无法处理新场景 | agent-fallback 兜底 + 模式沉淀回固化 |

### 3.3 后续演进

- **P1**：HITL 审批卡片（IM 推送 + 超时拒绝）
- **P2**：事件总线（EventBridge + 函数计算）
- **P3**：Incident DB 跨事件学习

---

## 4. 决策记录

| 日期 | 决策 | 说明 |
|------|------|------|
| 2026-08-06 | ADR-002 v1 提出 | 固化工作流引擎 + 预授权白名单作为 Level 4 P0 基础 |

---

## 5. 参考

- [ARCHITECTURE.md](../ARCHITECTURE.md) — 双引擎架构总览
- [TODO.md](../TODO.md) — Level 3 → 4 智能进化计划
- [aiops-cruise/references/pre-approved-whitelist.md](../../alicloud-aiops-cruise/references/pre-approved-whitelist.md) — 白名单矩阵 v1.0
- [aiops-cruise/TODO/sprint-12-dual-engine.md](../../alicloud-aiops-cruise/TODO/sprint-12-dual-engine.md) — 双引擎设计
- [AGENTS.md](../../AGENTS.md) — §8.1 破坏性操作硬规则
