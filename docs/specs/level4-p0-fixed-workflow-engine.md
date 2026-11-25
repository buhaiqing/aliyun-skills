# Level 4 P0 SPEC — 固化工作流引擎 + 预授权白名单

> **版本**: v1.0
> **状态**: 设计中
> **最后更新**: 2026-08-06
> **关联**: [ADR-002](../architecture/ADR-002-fixed-workflow-engine.md) | [PLAN](level4-p0-fixed-workflow-engine-plan.md) | [ARCHITECTURE.md](../ARCHITECTURE.md)

---

## 1. 目标与成功标准

### 1.1 一句话目标

在 Level 3 主动运营基础上，落地「固化工作流引擎」让高频已知场景毫秒级自动执行，并通过「预授权白名单」在 SRE 安全铁律内实现 L0/L1 操作的零人工确认自动执行，将 MTTR 从「发现→等用户→确认→执行」压缩到秒级。

### 1.2 可验证的成功标准

| # | 标准 | 验证方式 |
|---|------|----------|
| S1 | 固化工作流引擎单次执行延迟 < 1s（不含被调 CLI/SDK 网络耗时） | 集成测试计时 |
| S2 | 90% 已知 runbook 场景走固化引擎，不触发 LLM 推理 | trace 中 `engine=fixed` 占比 ≥ 90% |
| S3 | L0/L1 白名单操作自动执行，无人工确认阻断 | 自动化测试：W-01/W-02/W-03 命中即执行 |
| S4 | 白名单外操作（L2/L3）强制转 HITL 或 agent-fallback，不静默执行 | 安全测试：注入 L3 操作必须 ABORT |
| S5 | 每次自动执行写审计日志 + trace，字段完整 | 审计 JSONL 包含 whitelist_id + git_commit |
| S6 | 固化引擎并发重入安全（同 runbook 同时间仅一个实例） | 并发测试：2 进程同时触发同 runbook 不重复执行 |
| S7 | 执行后自动验证 + 失败回滚 | 注入故障：回滚命令被调用 |
| S8 | Cron 定时触发巡检，无人值守 | 模拟 cron 触发，输出报告到 `docs/cruise-reports/` |

---

## 2. 固化工作流引擎

### 2.1 整体数据流

```text
cron / event
  │
  ▼
┌─────────────────────┐
│ cruise-orchestrator │  接收触发 → 选 runbook → 路由
└─────────┬───────────┘
          │ runbook_id + params
          ▼
┌─────────────────────┐
│ runbook-dispatcher  │  查 DAG 缓存 → 命中则加载，未命中则编译
└─────────┬───────────┘
          │ DAG { steps[], deps[], undo[] }
          ▼
┌─────────────────────┐
│ workflow-runner     │  串行/并行调度 → 每步白名单校验
└───┬────────────┬────┘
    │ L0/L1       │ L2/L3 / 未知
    ▼             ▼
自动执行       agent-fallback (LLM 兜底)
    │             │
    ▼             ▼
┌─────────────────────┐
│ 验证 + 回滚          │  执行验证命令 → 失败调 undo
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 审计 + trace         │  写 JSONL + Langfuse
└─────────────────────┘
```

### 2.2 DAG 格式

```json
{
  "runbook_id": "rds-disk-cleanup",
  "version": "1.0.0",
  "steps": [
    {
      "id": "check_disk",
      "type": "describe",
      "cli": "aliyun rds DescribeBinlogFiles",
      "deps": [],
      "whitelist_id": null
    },
    {
      "id": "clean_binlog",
      "type": "exec",
      "cli": "CALL mysql.rds_cycle_binlog()",
      "deps": ["check_disk"],
      "whitelist_id": "W-02",
      "undo": "N/A (业务无感重新生成)"
    }
  ],
  "verify": "aliyun rds DescribeBinlogFiles --check-cleaned",
  "lock_key": "rds-disk-cleanup"
}
```

### 2.3 组件职责

| 组件 | 输入 | 输出 | 约束 |
|------|------|------|------|
| cruise-orchestrator | cron/event JSON | runbook_id + params | 必须有客户/标签筛选（严禁全账号） |
| runbook-dispatcher | runbook_id | DAG 对象 | 缓存命中 < 10ms，未命中编译 < 100ms |
| workflow-runner | DAG + params | StepResults[] | 零 LLM 调用；file lock 防重入 |
| agent-fallback | 失败/未知上下文 | 诊断报告 + 建议 | 仅兜底，不自动执行 L2/L3 |

---

## 3. 预授权白名单集成

### 3.1 校验流程

```text
workflow-runner 每步执行前:
  1. 查 step.whitelist_id
  2. 命中白名单矩阵:
     - L0/L1 → 自动执行 + 通知
     - L2 → 转 HITL 等待确认
     - L3 → ABORT (Safety=0)
  3. 未命中 → ABORT (Safety=0)
  4. 执行后写审计日志
```

### 3.2 白名单矩阵（引用 v1.0）

| ID | 操作 | 级别 | 自动执行条件 |
|----|------|------|-------------|
| W-01 | ECS 内只读诊断命令 | L0 | 命令前缀在白名单清单内 |
| W-02 | RDS 清理 binlog | L1 | 磁盘 > 85% AND binlog > 50% |
| W-03 | Redis maxmemory-policy=allkeys-lru | L1 | 内存 > 80% AND 逐出 > 0 |

---

## 4. 非目标（Out of Scope）

| 项 | 原因 |
|----|------|
| HITL 审批卡片（IM 推送） | P1 待做 |
| 事件总线（EventBridge+FC） | P2 待做 |
| Incident DB 跨事件学习 | P3 待做 |
| L2 自动执行（升配类） | 首批不纳入，需更多 L1 实战数据 |

---

## 5. 依赖与前置条件

| 依赖 | 状态 | 说明 |
|------|------|------|
| `pre-approved-whitelist.md` v1.0 | ✅ | 白名单矩阵已落地 |
| 4 个 runbook Python 脚本 | ✅ | 固化 DAG 输入源 |
| 缓存层（Sprint 8） | ✅ | 固化引擎内置 cache 基础 |
| Incident Schema v1.0.0 | ✅ | finding 结构约束 |
| GCL 门禁 | ✅ | 每次执行过 GCL |

---

## 6. 安全与合规

- 所有自动执行必须满足 AGENTS.md §8.1 破坏性操作硬规则
- 白名单外操作默认拒绝（不静默执行）
- 审计日志保留 ≥ 90 天（合规追溯）
- 凭证通过 `{{env.*}}` 注入，不落盘
