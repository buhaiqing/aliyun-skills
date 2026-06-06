# Sprint 12: 双引擎架构 (Stage 2 D1 + Stage 3 D1)

> **业务价值**: 巡检从"Agent 调 Bash"升级为"固化工作流自触发 + 弹性 Agent 兜底", 解决"凌晨 3 点谁来跑巡检"问题
> **依赖**: 4 个 runbook Python 脚本 ✅ + 缓存层 ✅ + Incident Schema ✅ + 动态基线 ✅
> **状态**: ⬜ **实施阶段**
> **关联验收项**: Stage 2 D1 (幂等加固) + Stage 3 D1 (双引擎调度)

---

## 一、目标拆解

### 1.1 Stage 2 D1 阶段 (先做)

> **4 个 runbook 全部脚本化 + 幂等加固完成**

当前状态:
- [x] 4 个 runbook 已有 Python 脚本 (daily-health-check / emergency-troubleshoot / capacity-planning / pre-launch-check)
- [ ] **幂等加固** ⬜ 重点: 重复跑能保证 side-effect = 0

#### 幂等性缺口分析

| 脚本 | 当前幂等状态 | 缺口 |
|------|-------------|------|
| daily-health-check | 部分幂等 (报告覆盖) | 缓存/API 重用, 副作用: 写文件+写 `.need_escalation` |
| emergency-troubleshoot | 弱幂等 (无 side-effect 防护) | ActionTrail 查询读操作, OK |
| capacity-planning | 幂等 (读) | — |
| pre-launch-check | 弱幂等 (写 `.need_escalation`) | — |

**幂等加固清单**:
1. `.need_escalation` 文件用 append + 时间戳, 不覆盖
2. 报告文件名带 timestamp, 不冲突
3. 缓存清理时**只清本 runbook 的 cache key**
4. **重入检查**: 同一 runbook 同一时间只允许一个实例 (file lock)

### 1.2 Stage 3 D1 阶段

> **固化工作流自触发 + 弹性 Agent 兜底 + 调度器自动路由**

#### 双引擎架构

```
                ┌──────────────────────────────────────┐
                │  Cruise Orchestrator (调度器)         │
                │  - cron / event trigger              │
                │  - 根据场景选 runbook                 │
                └──────────────┬───────────────────────┘
                               │
                ┌──────────────┴───────────────────────┐
                │                                      │
        ┌───────▼────────┐                  ┌──────────▼─────────┐
        │ 固化工作流引擎  │                  │  弹性 Agent 引擎   │
        │ (workflow-runner)│                 │  (agent-fallback) │
        │                │                  │                    │
        │ - 90% 场景     │                  │ - 10% 异常场景     │
        │ - 毫秒级响应   │                  │ - 智能分析 + 自愈  │
        │ - 无 LLM 推理  │                  │ - 兜底 + 解释      │
        └───────┬────────┘                  └──────────┬─────────┘
                │                                      │
                └──────────────┬───────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ 4 个 runbook Python  │
                    │ (现有脚本)          │
                    └─────────────────────┘
```

#### 关键组件

| 组件 | 职责 | 实现位置 |
|------|------|---------|
| `cruise-orchestrator.py` | 主调度器, 接收 cron/event, 选 runbook | `runbooks/scripts/` |
| `workflow-runner.py` | 固化工作流引擎, 不经过 LLM | `runbooks/scripts/` |
| `agent-fallback.py` | 弹性 Agent, 异常兜底 | `runbooks/scripts/` |
| `runbook-dispatcher.py` | runbook 选择路由 | `runbooks/scripts/` |
| `.lock` 文件 | 重入检查, 防止并发 | 写工作目录 |
| `cron-template` | cron 配置模板 | `references/` |

#### 触发场景

| 场景 | 触发器 | 走引擎 | 响应延迟 |
|------|--------|--------|---------|
| 每日健康巡检 | cron 0 9 * * * | 固化 | < 1s |
| 容量预测 (周报) | cron 0 9 * * 0 | 固化 | < 1s |
| 大促前预检 (双11 前 7 天) | cron 0 9 1,10 11 * | 固化 | < 1s |
| 5xx 告警 | CMS webhook | Agent 兜底 | < 30s |
| 用户提问 "我数据库慢" | 钉钉/企微 webhook | Agent 兜底 | < 60s |
| 巡检发现 5+ critical | event bus | Agent 兜底 (升级) | < 5s |

---

## 二、Task List

### Stage 2 D1 (本次实施)

- [ ] **12.1** 4 runbook 幂等加固
  - [ ] 12.1.1 daily-health-check: 写文件加 timestamp, 重入检查
  - [ ] 12.1.2 emergency-troubleshoot: 重入检查 + ActionTrail 时间窗口
  - [ ] 12.1.3 capacity-planning: 重入检查
  - [ ] 12.1.4 pre-launch-check: 写文件加 timestamp, 重入检查
- [ ] **12.2** 写 `lib_idempotent.py` 公共幂等工具
  - [ ] `acquire_lock(name, timeout=300)` - 文件锁
  - [ ] `release_lock(name)` - 释放锁
  - [ ] `is_locked(name)` - 检查是否被锁
  - [ ] `safe_append(path, line)` - append + timestamp
- [ ] **12.3** 质量门 (5/5 PASS)
  - [ ] 同一脚本连跑 3 次, 结果完全一致
  - [ ] 并发跑 2 个, 一个成功一个 LOCKED
  - [ ] `cruise-*.md` 文件名带时间戳不冲突
  - [ ] `.need_escalation` 用 append 不覆盖
  - [ ] cleanup 脚本保留 7 天历史

### Stage 3 D1 (后续 Sprint 13)

- [ ] **13.1** cruise-orchestrator.py
- [ ] **13.2** workflow-runner.py
- [ ] **13.3** agent-fallback.py
- [ ] **13.4** runbook-dispatcher.py
- [ ] **13.5** cron-template

---

## 三、关键决策

### D7 (2026-06-07): 双引擎分工

**固化工作流 (90% 场景)**:
- 已知 runbook, 已知输入, 已知输出
- 不需要 LLM 推理
- 毫秒级响应

**弹性 Agent (10% 异常场景)**:
- 5xx 告警、根因分析、新场景
- 需要 LLM 推理 + 工具调用
- 秒级响应

**判定标准**:
- 触发是**已知 cron** → 固化
- 触发是**未知 event** (5xx 告警/用户提问) → Agent
- 巡检发现 **3+ critical** → Agent 升级分析

### D8 (2026-06-07): 幂等性是关键

**没有幂等 → 重复跑 = 数据污染**:
- 报告覆盖: 历史不可追溯
- 写文件覆盖: `.need_escalation` 丢失
- 重入并发: race condition
- 缓存误清: hit_rate 暴跌

**File Lock 实现**:
```bash
# Lock 文件: /tmp/cruise-{runbook}-{customer}.lock
# 包含: PID + start_time + hostname
# TTL: 10 分钟自动过期
```

---

## 四、变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-06-07 | Sprint 12 调研: 双引擎架构 + 幂等加固 |
