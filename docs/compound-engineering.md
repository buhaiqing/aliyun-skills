# Compound Engineering — 复利工程详细规范

> **Source**: extracted from `AGENTS.md §18.1-§18.5`. The AGENTS.md §0.3 has the
> summary; this file is the canonical full reference.

> **核心原则**：每次设计/开发不只解决当前问题，还要沉淀可复用的模式、模板和决策记录，让下一次同类工作更快更好。

---

## 1. 架构设计模式

当进行架构设计（新系统、重大重构）时，遵循以下可复用模式：

| 模式 | 做法 | 反模式 |
|------|------|--------|
| **场景驱动** | 从用户接入场景出发（告警、工单、对话、CI/CD），先定义"做完后的效果"，再设计架构 | 从技术分层出发，先画架构图再想用户怎么用 |
| **价值量化** | 每个阶段用"一句话 + 一个具体数字"描述效果：MTTD 30分钟 → 3分钟 | "提升效率"、"优化体验"等模糊描述 |
| **场景对比** | 用"现在 vs 做完后"表格，让价值一目了然 | 只描述目标状态，不对比现状 |
| **双模式架构** | 对外服务同时提供 REST API（系统集成）和 MCP Server（LLM Agent），共享核心引擎 | 只做一种接入方式，后续再补 |
| **向后兼容** | 新系统在现有基础上新增编排层，不替代任何现有组件 | 推倒重来 |

---

## 2. 文档治理模式

| 模式 | 做法 |
|------|------|
| **统一入口** | 架构设计以 `docs/ARCHITECTURE.md` 为唯一权威入口，子文档从它链接出去 |
| **废弃即删除** | 被替代的文档直接删除（不是标记 deprecated 然后堆积），git 历史可回溯 |
| **三层文档结构** | ARCHITECTURE.md（总览）→ SPEC（详细规格）→ PLAN（任务分解），每层有明确的读者和目的 |
| **引用而非重复** | AGENTS.md 引用 ARCHITECTURE.md，不重复架构内容；SPEC 引用 GCL spec，不重复 GCL 规范 |

---

## 3. 关键设计决策记录

以下是本次架构设计中做出的关键决策，后续设计应参考：

| 决策 | 选择 | 理由 | 来源 |
|------|------|------|------|
| Agent 编排模式 | Supervisor（单 Agent 调度多 Skill） | 70% 生产采用率；多 Agent token 消耗是单 Agent 的 15x | [研究报告](../ARCHITECTURE.md) |
| 接入方式 | REST API + MCP Server 双模式 | REST 给系统用（告警/工单/CI），MCP 给 LLM Agent 用（对话） | [架构总览](../ARCHITECTURE.md) |
| 根因分析 | Phase 1 用规则引擎，不用 LLM | 确定性高、延迟低、成本可控；LLM 推理留给 Phase 2+ | [Phase 1 SPEC](../specs/phase-1-core-engine.md) |
| 意图解析 | 规则 + 正则 + 关键词词典，不用 LLM | 告警/工单输入结构化程度高，不需要 LLM；成本更低、延迟 < 100ms | [Phase 1 SPEC §2.2](../specs/phase-1-core-engine.md) |
| 开发顺序 | 先 REST API 再 MCP Server | REST API 用 curl 就能测，能独立验证核心引擎；MCP 本质是 REST 的协议适配层 | [Phase 1 PLAN](../plans/phase-1-plan.md) |
| 不做什么 | Phase 1 不做多 Agent、不做 HITL、不做沙箱 | 单 Agent + 多 Skill 覆盖 80% 场景；复杂特性留到 Phase 2/3 | [架构总览](../ARCHITECTURE.md) |

---

## 4. 可复用的文档模板

以下模板已在实际设计过程中验证，可直接复用：

**SPEC 文档结构**（参考 `docs/specs/phase-1-core-engine.md`）：

```markdown
1. 目标与成功标准（可验证的 S1-S8）
2. 核心引擎设计（数据流图 + 每个组件的输入/输出/策略）
3. 接口规格（REST API 端点 + MCP tools）
4. 集成方式（与现有系统的关系）
5. 非功能需求（性能/安全/可观测性）
```

**PLAN 文档结构**（参考 `docs/plans/phase-1-plan.md`）：

```markdown
1. 任务总览（清单 + 工时 + 依赖 + 优先级）
2. 任务详细分解（每个任务的子任务 + 验证标准 + 涉及文件）
3. 依赖关系图（ASCII art 或 Mermaid）
4. 风险与缓解
5. 里程碑（时间 + 交付物 + 验证方式）
```

---

## 5. 复利检查清单（🔴 每次完成任务后强制执行）

> **⛔ 这个检查清单不是"建议"——是"交付完成"的定义。未通过检查清单的任务不算完成。**

每次完成一个功能点/设计后，必须逐项确认：

- [ ] **决策记录**：这次做的关键决策有没有记录到 `docs/ARCHITECTURE.md` 的决策表中？含：选了什么、为什么、不选什么
- [ ] **模板沉淀**：这次用的方法/模板有没有可复用价值？有的话是否更新到本文档第 4 节？
- [ ] **废弃清理**：有没有产生应该清理的废弃文档/代码？删掉，不要堆积（git 历史可回溯）
- [ ] **决策一致性**：有没有违反已记录的决策？如果有，必须更新决策记录说明原因
- [ ] **可追溯性**：新产生的文档是否从 `docs/ARCHITECTURE.md` 可追溯？
- [ ] **下一次更快**：如果有人要做类似的事，能不能通过 `ARCHITECTURE.md` → SPEC → PLAN 这条链路快速找到所有上下文？

---

## 6. 相关规则（仍保留在 AGENTS.md）

为了避免重复，下列规则仍保留在 AGENTS.md §18.6-§18.7：

- **DL-R1..DL-R4**（§18.6）：文档/配置引用校验，含 GitHub 锚点 slug 算法
- **FM-R1..FM-R8**（§18.7）：FinOps/ML 模块开发复盘（`alicloud-aiops-ml` 试点沉淀）

这两类规则**经常在 review / link 校验场景被频繁 grep**，放在 AGENTS.md 主文件中便于快速访问，不下沉到 references。