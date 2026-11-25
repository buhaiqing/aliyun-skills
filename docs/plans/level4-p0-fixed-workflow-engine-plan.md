# Level 4 P0 PLAN — 固化工作流引擎 + 预授权白名单

> **版本**: v1.0
> **状态**: 设计中
> **最后更新**: 2026-08-06
> **关联**: [ADR-002](../architecture/ADR-002-fixed-workflow-engine.md) | [SPEC](../specs/level4-p0-fixed-workflow-engine.md)

---

## 1. 任务总览

### 1.1 一句话目标

实现固化工作流引擎（4 个 Python 组件 + 1 个 Cron 模板），将 Level 3 的「建议+确认」模式升级为「白名单内自动执行」，完成 Level 4 主动自治的 P0 基础。

### 1.2 任务清单

| # | 任务 | 预估工时 | 依赖 | 优先级 |
|---|------|----------|------|--------|
| T1 | runbook-dispatcher（DAG 编译 + 缓存） | 3 天 | 无 | P0 |
| T2 | workflow-runner（固化执行 + 白名单校验） | 5 天 | T1 | P0 |
| T3 | agent-fallback（异常兜底） | 3 天 | T2 | P0 |
| T4 | cruise-orchestrator（主调度 + Cron） | 3 天 | T2, T3 | P0 |
| T5 | cron-template.yaml | 1 天 | T4 | P0 |
| T6 | 白名单校验器集成 | 2 天 | T2 | P0 |
| T7 | 集成测试 + E2E 验证 | 3 天 | T1-T6 | P0 |
| T8 | 文档 + 示例 + ARCHITECTURE 同步 | 2 天 | T1-T7 | P1 |

**总计**: 约 22 人天

---

## 2. 任务详细分解

### T1: runbook-dispatcher（DAG 编译 + 缓存）

**目标**：将 runbook Python 脚本预编译为 DAG JSON，缓存加速加载。

**子任务**：

- [ ] T1.1 设计 DAG JSON schema（steps/deps/undo/whitelist_id）
- [ ] T1.2 实现 `--compile` 模式：调 runbook `--dry-run` 输出 → DAG
- [ ] T1.3 实现内存缓存层（key=runbook_id+version）
- [ ] T1.4 实现 cache miss 时自动编译 + 写入
- [ ] T1.5 单元测试：编译正确性 + 缓存命中率

**验证标准**：

```bash
python3 -m pytest runbooks/scripts/tests/test_dispatcher.py -v
# 缓存命中 < 10ms，未命中编译 < 100ms
```

### T2: workflow-runner（固化执行 + 白名单校验）

**目标**：无 LLM 推理调度 DAG，每步白名单校验，执行后验证+回滚。

**子任务**：

- [ ] T2.1 实现 DAG 加载（调 dispatcher）
- [ ] T2.2 实现串行/并行调度（deps 拓扑排序）
- [ ] T2.3 集成白名单校验器（L0/L1 自动，L2/L3 ABORT）
- [ ] T2.4 实现 file lock 防并发重入
- [ ] T2.5 实现执行后验证命令调用
- [ ] T2.6 实现失败回滚（调 undo 指令）
- [ ] T2.7 单元测试：拓扑排序 + 并发锁 + 回滚

**验证标准**：

```bash
python3 -m pytest runbooks/scripts/tests/test_runner.py -v
# 单次执行 < 1s（不含网络）
# 并发 2 进程同 runbook 不重复执行
```

### T3: agent-fallback（异常兜底）

**目标**：固化引擎无法处理时转 LLM 兜底，但不自动执行 L2/L3。

**子任务**：

- [ ] T3.1 实现升级判定（连续失败 / 未知输入 / DAG 缺失）
- [ ] T3.2 实现 LLM 诊断调用（复用 GCL 引擎）
- [ ] T3.3 实现兜底输出：诊断报告 + 建议（标记 requires_confirmation）
- [ ] T3.4 单元测试：升级判定逻辑

**验证标准**：

```bash
python3 -m pytest runbooks/scripts/tests/test_fallback.py -v
# L3 操作经 fallback 仍 ABORT，不自动执行
```

### T4: cruise-orchestrator（主调度 + Cron）

**目标**：接收 cron/event 触发，选 runbook，路由到 runner/fallback。

**子任务**：

- [ ] T4.1 实现 cron trigger 解析（读 cron-template.yaml）
- [ ] T4.2 实现 event trigger 解析（告警 JSON → runbook 选择）
- [ ] T4.3 实现 runbook 选择逻辑（标签/客户筛选）
- [ ] T4.4 实现路由：固化 → runner，异常 → fallback
- [ ] T4.5 实现全账号扫描 HALT（安全约束）
- [ ] T4.6 单元测试：触发解析 + 路由

**验证标准**：

```bash
python3 -m pytest runbooks/scripts/tests/test_orchestrator.py -v
# 模拟 cron 触发输出报告到 docs/cruise-reports/
# 全账号扫描请求立即 HALT
```

### T5: cron-template.yaml

**目标**：Cron 配置模板，定义巡检频率 + 客户筛选。

**子任务**：

- [ ] T5.1 编写 YAML 模板（含注释示例）
- [ ] T5.2 定义默认客户/标签筛选字段
- [ ] T5.3 集成到 cruise-orchestrator 读取逻辑

### T6: 白名单校验器集成

**目标**：将 `pre-approved-whitelist.md` 矩阵编码为可查询结构，供 runner 调用。

**子任务**：

- [ ] T6.1 解析白名单矩阵为 Python dict（whitelist_id → 规则）
- [ ] T6.2 实现 `check(operation) -> (level, auto_exec, notify)` 接口
- [ ] T6.3 集成进 workflow-runner 每步执行前
- [ ] T6.4 审计日志写入（JSONL + git_commit 字段）

**验证标准**：

```bash
python3 -m pytest runbooks/scripts/tests/test_whitelist.py -v
# W-01/W-02/W-03 命中自动执行
# L3 操作注入 → ABORT
```

### T7: 集成测试 + E2E 验证

**目标**：端到端验证固化引擎 + 白名单自动执行闭环。

**子任务**：

- [ ] T7.1 编写 E2E 测试：cron → orchestrator → runner → W-02 自动清理
- [ ] T7.2 编写安全测试：L3 操作注入 → 全链路 ABORT
- [ ] T7.3 编写并发测试：2 进程同 runbook → 单实例执行
- [ ] T7.4 编写回滚测试：注入故障 → undo 调用
- [ ] T7.5 性能测试：单执行 < 1s

### T8: 文档 + 示例 + ARCHITECTURE 同步

**目标**：补齐使用文档，同步架构引用。

**子任务**：

- [ ] T8.1 在 aiops-cruise SKILL.md 追加固化引擎执行流说明
- [ ] T8.2 编写 `references/cron-template-example.md` 使用文档
- [ ] T8.3 同步 ARCHITECTURE.md 双引擎章节引用 ADR-002
- [ ] T8.4 Post-Update Self-Review R1 + R2

---

## 3. 里程碑

| 里程碑 | 交付 | 验收 |
|--------|------|------|
| M1 (Day 5) | T1-T3 完成 | 固化引擎单跑通过单元测试 |
| M2 (Day 10) | T4-T6 完成 | 编排 + 白名单集成通过 |
| M3 (Day 15) | T7-T8 完成 | E2E + 文档 + Self-Review |

---

## 4. 风险与缓解

| 风险 | 缓解 |
|------|------|
| DAG 与 runbook 漂移 | T1 编译步骤每次 runbook 变更须重新生成 + 回归 |
| 白名单误操作 | 季度复审 + 紧急下线（pre-approved-whitelist.md §五） |
| 并发重入 | file lock + 幂等检查（T2.4） |
| 固化无法覆盖新场景 | agent-fallback 兜底 + 模式沉淀 |

---

## 5. 验收清单（与 SPEC S1-S8 对应）

- [ ] S1: 固化执行 < 1s
- [ ] S2: 90% 场景走固化引擎
- [ ] S3: L0/L1 自动执行无确认
- [ ] S4: 白名单外强制 HITL/ABORT
- [ ] S5: 审计 + trace 完整
- [ ] S6: 并发重入安全
- [ ] S7: 验证 + 回滚
- [ ] S8: Cron 无人值守
