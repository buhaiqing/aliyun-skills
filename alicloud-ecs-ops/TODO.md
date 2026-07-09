# TODO for alicloud-ecs-ops
## Post-Update Self-Review Checks
1. [x] Structural checks passed
2. [x] Content checks passed
3. [x] Token efficiency optimized — SKILL.md 瘦身：13 个轮询代码块 + Go SDK 引用统一移至 references/，1599→1528 行 (-4%)
4. [x] TODO.md synced — 记录本次 SKILL.md 瘦身变更
5. [x] Intent recognition P0 optimizations — `Intent-to-Operation Index` 反向索引 + `Multi-Skill Intent Patterns` 跨 skill 决策树，1528→1610 行 (+82 行 = 两个小节)
6. [x] Intent recognition P1 optimizations — frontmatter `keywords`/`negative_keywords` 结构化触发矩阵 + `### Intent Disambiguation` 消歧策略 + `assets/eval_queries.json` 扩到 24 条（8 正向 + 7 负向 + 3 多轮 + 3 指代 + 3 消歧）
7. [ ] Langfuse integration validated

## 2026-06-18 — SKILL.md Slimming (Content Separation)

✅ **1. Polling patterns → new references/polling-patterns.md**
   - 13 polling code blocks moved to new file with generic template + per-operation parameters table
   - SKILL.md now links to `references/polling-patterns.md`

✅ **2. Go SDK references unified → references/api-sdk-usage.md**
   - 31 `JIT Go SDK fallback` references unified to point to `references/api-sdk-usage.md#go-sdk-examples`
   - Go SDK Examples section added to api-sdk-usage.md

## 2026-06-22 — Intent Recognition P0 Optimizations

参考 Ask 模式下的 7 项建议，挑 P0 两项落地：

✅ **P0-1: Intent-to-Operation Index (Reverse Lookup)**
   - 在 `## Trigger & Scope` 与 `## Delegation Rules` 之间新增 `### Intent-to-Operation Index`
   - 把用户自然语言意图（"看下 ECS"、"安全组巡检"、"诊断"等）反向映射到 Operation 章节锚点
   - 覆盖 35 个意图 → 40 个 Operation 章节（补充了之前遗漏的 5 个：Create SG / Invoke Command / Stop Invocation / Describe Send File Results / Describe Cloud Assistant Status）
   - Python 脚本验证：36 个锚点全部命中真实 Operation 标题，无悬挂链接

✅ **P0-2: Multi-Skill Intent Patterns**
   - 在 `## Delegation Rules` 下新增 `### Multi-Skill Intent Patterns` 决策树
   - 定义 7 种复合意图的主/辅/可选 skill 路由 + `HARNESS_SESSION_ID` 传播约定
   - Routing policy 4 条规则：主失败整流、辅依赖主成功、可选显式触发、HALT 不重试
   - 末尾提供 verbatim shell 例子（"ECS 上的应用连不上 RDS"）

**未引入的变更**：
- 未修改 frontmatter / Trigger & Scope 主表（避免 K3 越界重构）
- 未改 Operation 章节（已是对称的，"诊断意图薄弱"判断在重新校准后撤回）
- 新增 10 个 MD013 line-length 错误（与 main 基线 237 个同类债务一致，K3 不顺手重构）

**Lint baseline 对比**：main = 237 → after change = 247 (+10，与既有债务同类)

## 2026-06-22 — Intent Recognition P1 Optimizations

承接 P0 的 7 项建议，本轮落地 P1 三项 + 1 项 P2 升级：

✅ **P1-#3: eval_queries.json 评测语料扩展**（共 +16 条）
   - `negative_queries` 7 条：RDS / SLB / VPC / ACK / Billing / RAM / Redis — 用于触发 precision/recall 双轴评测
   - `multi_turn` 3 组：ECS 顺序（instance → disk → SG）/ ECS→RDS 跨 skill / ECS→SLB 跨 skill
   - `anaphora` 3 条：指代消解（"它"/"那台机器"/"那条"），验证上下文保留能力
   - `disambiguation` 3 条：与新 `### Intent Disambiguation` 章节对齐（"弄好"/"看下"/"ECS 慢"）
   - 总评测 query: 24 条（8 正 + 7 负 + 3 多轮 + 3 指代 + 3 消歧）

✅ **P1-#6: ### Intent Disambiguation 章节**
   - 8 行决策表：每行包含 用户原话 / 候选操作 / 消歧信号 / 默认行为
   - 关键原则：含破坏性操作的歧义（Delete/Stop/Reboot/ReplaceSystemDisk/AuthorizeSecurityGroup w/ 0.0.0.0/0）默认**询问**，非破坏性歧义（Describe/Cost/Health）默认路由
   - 引用 [references/rubric.md §1.2](references/rubric.md) 作为 safety gate 兜底

✅ **#4: frontmatter keyword 结构化**（async v0）
   - 移除 description 段内的扁平 `Keywords: ...` 字符串（重复信息）
   - 新增顶层 `keywords:` (zh + en 两个子字段) + `negative_keywords:` 字段
   - 每个 surface 含 `surface` / `maps_to` / `note` 三元组；note 字段标注歧义点（"实例"/"主机"/"镜像"的多义性）
   - 当前为 ECS 单一 skill 的扩展，未触动 generator template（K3 不顺手重构）

**Lint baseline 对比**：P0 后 = 247 → P1 后 = 256 (+9，全部为 MD013 line-length；中文表格行与既有债务同类)
