# Agent Runtime — 架构总览

> **版本**: v1.0
> **状态**: Phase 1 设计完成，Phase 2/3 预留框架
> **最后更新**: 2026-07-17
>
> **复利工程**：本文档是项目架构的唯一权威入口。所有架构决策、文档模板、设计模式均在此集中管理。详见 [AGENTS.md §0.3 复利工程](../AGENTS.md#03-复利工程--compound-engineering-最高优先级)。

---

## 一句话说清楚

**Agent Runtime 是阿里云智能运维的"自动驾驶"引擎。**

把资深 SRE 排查问题的经验（先看监控、再看日志、交叉分析、定位根因），变成一套自动执行的诊断流水线。告警来了自动查、工单来了自动分析、人问一句话自动给结论——**从"人驱动工具"变成"工具驱动人"**。

---

## 为什么需要 Agent Runtime？

### 一个真实的凌晨 3 点

```
03:00  手机响了 — RDS 连接数告警
03:02  爬起来打开电脑，登录云控制台
03:05  查 RDS 监控：连接数确实 85%
03:08  查慢 SQL：发现 3 条可疑查询
03:12  查 ECS 应用日志：没有异常
03:15  查 Redis 缓存命中率：正常
03:18  回头看慢 SQL 执行计划：缺少索引
03:20  确认根因：昨晚发版引入的 N+1 查询
03:22  通知开发回滚
03:25  连接数恢复正常

总耗时：25 分钟。这 25 分钟里，500 个用户看到了超时页面。
```

### 有了 Agent Runtime 之后

```
03:00  告警触发 → Webhook 推送到 Agent Runtime
03:00  Agent Runtime 自动启动诊断：
       ├─ 查 RDS 连接数趋势（5s）
       ├─ 查慢 SQL 列表（3s）        ← 三个并行
       ├─ 查 ECS 应用日志（8s）
       ├─ 查 Redis 缓存命中率（2s）
       └─ 交叉分析 → 定位根因（2s）
03:00  诊断完成：根因 = 慢 SQL 缺少索引，置信度 92%
03:00  推送结果到企业微信：
       "RDS rm-xxx 连接数告警已自动诊断完成
        根因：慢 SQL `SELECT * FROM orders WHERE status='pending'` 缺少索引
        建议：执行 CREATE INDEX idx_orders_status ON orders(status)
        影响：500 用户订单页超时，持续 5 分钟
        是否执行？[确认] [拒绝]"

总耗时：不到 1 分钟。在用户还没感知到问题的时候，根因已经找到了。
```

---

## 当前 vs 目标

| | 当前（Skills Farm） | 目标（Agent Runtime） |
|---|---|---|
| **怎么用** | "帮我查 RDS 连接数" → "再查慢 SQL" → "再看看规格" → 来回 10 轮 | 一句话："RDS rm-xxx 连接数高，帮我看看" |
| **谁来决策** | 人脑：判断下一步该查什么 | 引擎：自动匹配诊断模板，自主编排 |
| **谁来编排** | prompt engineering，依赖 LLM 能力 | 声明式诊断模板 + 确定性 DAG 执行 |
| **怎么接入** | 只能对话窗口（人主动问） | REST API（系统推） + MCP Server（LLM 调） |
| **怎么通知** | 对话窗口里看结果 | 工单回写、IM 推送、CI 回调、电话告警 |
| **从失败中学** | 靠人记住"上次怎么查的" | Reflexion Memory 自动积累诊断经验 |

---

## 架构全景图

```
                            ┌──────────────────────┐
                            │     接入适配层          │
                            │  (Input Adapters)     │
                            ├────┬────┬────┬────────┤
                            │工单│告警│对话│CI/CD   │
                            └────┴────┴────┴────────┘
                                     │
                            ┌────────┴────────┐
                            │   REST API :8080 │  ← 系统集成
                            │   MCP Server     │  ← LLM Agent
                            └────────┬────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────┐
│                          Agent Runtime Core                              │
│                                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────────┐    │
│  │ IntentParser │──▶│ContextEnricher│──▶│      TaskPlanner          │    │
│  │ 意图解析      │   │ 上下文富化     │   │  生成诊断 DAG 计划        │    │
│  └──────────────┘   └──────────────┘   └────────────┬─────────────┘    │
│                                                      │                  │
│                                                      ▼                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     ExecutionEngine (执行引擎)                     │   │
│  │                                                                   │   │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────┐  ┌─────────────┐  │   │
│  │  │ToolRegistry│  │ParallelRun │  │ GCL Gate  │  │RootCause    │  │   │
│  │  │Skill→Tool  │  │ fan-out/in │  │ 质量门禁   │  │ 根因分析     │  │   │
│  │  └────────────┘  └────────────┘  └──────────┘  └─────────────┘  │   │
│  │                                                                   │   │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────┐                   │   │
│  │  │SessionStore│  │Memory(L1/2)│  │HITL Mgr  │                   │   │
│  │  │会话状态     │  │记忆/反思    │  │人工审批   │                   │   │
│  │  └────────────┘  └────────────┘  └──────────┘                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                      │                                   │
│                                      ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     输出适配层 (Output Adapters)                   │   │
│  │                                                                   │   │
│  │  诊断报告(MD)  回写工单(Jira)  IM推送(企微/钉钉)  CI回调(Webhook) │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │              可观测性 (贯穿全链路)                                  │   │
│  │  Langfuse Trace → Token 用量 → 执行耗时 → 成功率                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

### 核心组件说明

| 组件 | 职责 | 一句话 |
|------|------|--------|
| **IntentParser** | 从任意文本中提取：产品、资源 ID、现象、严重级别 | "这句话在说什么问题" |
| **ContextEnricher** | 补充缺失信息：资源标签、负责人、关联服务、最近变更 | "这个问题还涉及什么" |
| **TaskPlanner** | 根据现象匹配诊断模板，生成 DAG 执行计划 | "该按什么顺序查" |
| **ExecutionEngine** | 按 DAG 调度 Skill 执行，并行/串行，过 GCL 门禁 | "动手查" |
| **RootCauseAnalyzer** | 交叉分析多维度结果，推导因果链 + 置信度 | "根因是什么" |
| **ToolRegistry** | 53 个 Skill 的统一注册与发现 | "有什么能力可用" |
| **SessionStore** | 跨步骤保持上下文，支持暂停/恢复 | "上次查到哪了" |
| **Memory** | Layer 1 执行记录 + Layer 2 失败模式 | "以前遇到过类似问题" |
| **HITL Manager** | 破坏性操作审批，超时自动拒绝 | "这个操作需要人确认" |

---

## 双模式接入

```
                     ┌─────────────────────────┐
                     │     Agent Runtime Core   │
                     │     (核心引擎，共用)       │
                     └───────────┬─────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │                                     │
     ┌────────┴────────┐                  ┌────────┴────────┐
     │   REST API      │                  │   MCP Server    │
     │   :8080         │                  │   :5000 (SSE)   │
     ├─────────────────┤                  ├─────────────────┤
     │ 给"系统"用的     │                  │ 给"LLM Agent"用  │
     │                 │                  │                 │
     │ 工单 Webhook     │                  │ Claude Code     │
     │ 告警 Webhook     │                  │ Cursor          │
     │ CI/CD 回调       │                  │ CodeBuddy       │
     │ 定时任务触发     │                  │ 任何 MCP 客户端  │
     │                 │                  │                 │
     │ 异步 + 回调      │                  │ 流式 SSE 推送    │
     └─────────────────┘                  └─────────────────┘
```

| 场景 | 用什么 | 为什么 |
|------|--------|--------|
| 告警系统发来一条告警 | REST API | 系统对系统，异步回调 |
| 工单系统创建一张工单 | REST API | 系统对系统，诊断结果回写工单 |
| CI/CD 发版后触发检查 | REST API | 同步返回 pass/fail |
| 人在对话窗口问问题 | MCP Server | LLM Agent 调用 MCP tools |
| 定时巡检 | REST API | Cron 触发，结果推送 IM |

---

## 演进路线图

```
Phase 1（当前）          Phase 2（预留）            Phase 3（预留）
能自主干活               更安全 + 更主动            对外服务
───────────────         ─────────────────         ─────────────
核心诊断引擎             HITL 审批工作流             Agent Builder
+ REST API               + 主动巡检引擎              + 多租户
+ MCP Server             + 事件总线                  + Marketplace
+ 诊断模板库
+ Tool Registry

3 个月                   3 个月                      6 个月
```

---

## Phase 1：能自主干活

### 做完后的效果

> **一句话**：告警来了自动诊断、工单来了自动分析、人问一句话就能得到结论。
>
> **核心指标**：平均故障定位时间（MTTD）从 30 分钟 → 3 分钟，**缩短 90%**。

**三大场景，一个引擎**：

| 场景 | 接入方式 | 现在 | Phase 1 做完后 |
|------|----------|------|---------------|
| 告警来了 | CMS Webhook → REST API | 人收到告警 → 登录控制台 → 手动排查 → 平均 30 分钟 | 告警触发 → 自动并行诊断 → 3 分钟内 IM 推送根因 + 建议 |
| 工单来了 | Jira Webhook → REST API | 用户描述问题 → 运维逐一排查 → 来回沟通 → 平均 2 小时 | 工单创建 → 自动识别资源+现象 → 诊断 → 回写结论到工单 |
| 人问了 | LLM Agent → MCP Server | "帮我查 XX" → "再查 YY" → "再看看 ZZ" → 来回 10 轮 | "RDS 慢了帮我看看" → 自动多维度检查 → 一次给出完整诊断报告 |

**用户能直接感受到的变化**：

- 凌晨告警不再需要爬起来开电脑 — 手机上看诊断结果，点一下确认或拒绝
- 工单不再需要"先分给一线，一线查不出转二线" — 工单创建时自动附带诊断结论
- 日常排查不再需要"我告诉你查什么" — 描述现象，自动完成全链路诊断

### 交付物

| 模块 | 说明 |
|------|------|
| **核心诊断引擎** | IntentParser + ContextEnricher + TaskPlanner + ExecutionEngine + RootCauseAnalyzer |
| **Tool Registry** | 53 个 Skill → 统一 Tool Schema，按产品/现象/能力维度索引 |
| **诊断模板库** | 覆盖 Top 20 常见运维现象的声明式诊断模板 |
| **REST API** | `/diagnose`、`/tasks`、`/check`、`/patrol`、`/hitl` |
| **MCP Server** | SSE 模式，暴露 `diagnose`、`run_patrol`、`post_deploy_check` tools |
| **Session Context** | 跨步骤状态保持，支持暂停/恢复 |
| **输出适配** | 诊断报告模板 + 工单回写 + IM 推送 + CI 回调 |

### 不做的（留给 Phase 2/3）

- 不做 Human-in-the-Loop 审批工作流（Phase 2）
- 不做主动巡检引擎（Phase 2）
- 不做事件总线（Phase 2）
- 不做 Agent Builder 低代码（Phase 3）
- 不做多租户（Phase 3）

---

## Phase 2：更安全 + 更主动（预留）

### 做完后的效果

> **一句话**：破坏性操作需审批才执行，问题在用户发现前就主动通知。

**场景对比**：

| | Phase 1 | Phase 2 做完后 |
|---|---|---|
| **安全** | 诊断出问题给出建议，人手动执行 | 破坏性操作（删实例、改配置）自动推送审批卡片到 IM，超时自动拒绝 |
| **巡检** | 需要人主动说"帮我巡检一下" | 每天自动巡检，有问题主动推送到 IM，不用人问 |
| **协作** | 单个任务独立执行 | 事件驱动：告警 → 诊断 → 发现需扩容 → 触发审批 → 执行 → 验证闭环 |

### 预留交付物

| 模块 | 说明 |
|------|------|
| HITL 审批工作流 | IM 推送审批卡片，超时自动拒绝，全链路审计 |
| 主动巡检引擎 | Cron 驱动，资源到期/容量趋势/安全基线/成本异常 |
| Event Bus | 事件驱动架构，告警→诊断→审批→执行自动串联 |

---

## Phase 3：对外服务（预留）

### 做完后的效果

> **一句话**：非开发人员也能通过界面构建诊断流程，外部系统通过 API 集成。

### 预留交付物

| 模块 | 说明 |
|------|------|
| Agent Service API | 完整 REST + WebSocket API，支持 CI/CD 和监控系统集成 |
| Agent Builder | 低代码可视化构建诊断 Workflow |
| 多租户 + RBAC | 团队隔离，角色权限 |
| Marketplace | Skill + Workflow 分享复用 |

---

## 技术选型

| 层 | 技术 | 理由 |
|----|------|------|
| **核心引擎** | Python 3.10+ | 与现有 gcl_runner.py 技术栈一致，团队熟悉 |
| **REST API** | FastAPI + uvicorn | 异步支持好，自动 OpenAPI 文档 |
| **MCP Server** | FastMCP | 官方推荐，SSE 流式支持好 |
| **诊断模板** | YAML | 声明式，可读性强，Git 友好 |
| **Tool Registry** | 内存 + JSON 缓存 | 53 个 Skill，不需要数据库 |
| **Session Store** | 文件 + JSON | Local-first，与现有 .runtime/ 一致 |
| **Memory** | JSONL（复用现有） | Layer 1/2 已就绪，不需改动 |
| **配置管理** | YAML + 环境变量 | 与现有模式一致 |

---

## 与现有系统的关系

```
现有 aliyun-skills                    新增 Agent Runtime
══════════════════                    ════════════════════
                                   
SKILL.md × 53        ──读取──▶     Tool Registry
harness-wrapper.sh   ──调用──▶     ExecutionEngine
gcl_runner.py        ──嵌入──▶     GCL Gate
harness-core-lib.sh  ──复用──▶     追踪/指标
.runtime/memory/     ──复用──▶     Memory L1/L2
.runtime/reflexion/  ──复用──▶     Reflexion Memory

不替代任何现有组件，在现有基础上新增编排层和接入层。
```

---

## 相关文档

> **ARCHITECTURE.md 是本项目的统一架构入口**。以下文档是各子系统的详细规范，从本文档按需跳转即可。

### 新架构设计（Agent Runtime）

| 文档 | 说明 |
|------|------|
| [Phase 1 SPEC](specs/phase-1-core-engine.md) | 核心诊断引擎 + 双模式接入详细规格 |
| [Phase 1 PLAN](plans/phase-1-plan.md) | 任务分解 + 依赖 + 验证标准 |

### 现有子系统（保留，Agent Runtime 复用）

| 文档 | 说明 |
|------|------|
| [GCL Spec](gcl-spec.md) | Generator-Critic-Loop 质量门禁完整规范 |
| [Harness Integration Guide](harness-integration-guide.md) | Runtime Harness 集成指南（wrapper、trace、metrics） |
| [Harness Session & Trace Design](harness-session-trace-system-design.md) | Session/Trace 系统设计 |
| [Harness Observability Architecture](harness-observability-architecture.md) | Runtime Harness 可观测性架构 |
| [Memory Strategy](memory-strategy.md) | 三层记忆架构（L1 执行记忆 / L2 反思记忆 / L3 策略记忆） |
| [Memory & Observability Relationship](memory-observability-relationship.md) | 记忆与可观测性系统关系 |
| [Token Efficiency Strategy](token-efficiency-strategy.md) | Token 效率优化策略 |
| [Diagnostic Logging Standard](diagnostic-logging-standard.md) | 诊断日志规范 |
| [CLI Usage Patterns](cli-usage-patterns.md) | 阿里云 CLI 参数格式规范 |
| [Post-Update Self-Review](post-update-self-review.md) | Skill 更新后自查规范 |
| [Runtime Harness Glossary](runtime-harness-glossary.md) | Runtime Harness 术语表 |
