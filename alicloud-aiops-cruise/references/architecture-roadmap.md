---
name: architecture-roadmap
version: "1.0.0"
parent: alicloud-aiops-cruise
status: draft
---

# AIOps 双引擎架构蓝图

> 本文件是本 Skill 的**目标架构蓝图**，非当前实现。描述"要建成什么"，而非"现在是什么"。
> 当前实现在 SKILL.md 和 runbooks/ 中描述，这里是演进方向。

---

## 一、核心愿景

首创 **"固化工作流 + 弹性 Agent" 双引擎**智能调度体系：

```
高频操作（重启/回滚/扩缩容）-> 固化工作流（低延迟、确定、幂等、可自动执行）
复杂故障（未知根因/多数据源）-> 弹性 Agent（LLM 动态规划、多轮推理、人工确认）
```

兼顾系统安全性与灵活性，不让 LLM 成为所有操作的瓶颈。

---

## 二、架构总览

```
外部触发 (告警/定时/人工)
         │
         ▼
┌────────────────────────────────────────────────────┐
│                智能调度器                            │
│  Intelligent Scheduler                              │
│                                                    │
│  输入: 事件类型 + 上下文 + 风险评级                  │
│  决策树:                                            │
│  ├─ 已知模式 + 低风险  -> 固化工作流引擎              │
│  ├─ 已知模式 + 高风险  -> 固化工作流 + 人工确认        │
│  ├─ 未知模式 + 任意    -> 弹性 Agent 引擎             │
│  └─ Agent 执行失败     -> escalate to human           │
└────────────┬────────────────────────────┬───────────┘
             │                            │
             ▼                            ▼
┌────────────────────────┐  ┌──────────────────────────────┐
│ 固化工作流引擎          │  │ 弹性 Agent 引擎               │
│ Hardened Workflow      │  │ Elastic Agent                │
│                        │  │                              │
│ • 预编译 DAG            │  │ • LLM 动态规划               │
│ • 无需 LLM 参与         │  │ • 工具调用 (CLI/API/SDK)     │
│ • 幂等 + 可重入         │  │ • 多数据源融合               │
│ • 运行时可观测           │  │ • 修复方案自动生成            │
│ • 失败可回滚             │  │ • 执行后 Post-mortem 记录    │
│                        │  │                              │
│ 延迟: < 1s             │  │ 延迟: 15-60s (含 LLM)        │
│ 安全: 预审计白名单       │  │ 安全: 每次操作需人工确认       │
│ 触发: EventBridge/定时   │  │ 触发: 调度器升级/人工        │
└────────────────────────┘  └──────────────────────────────┘
```

---

## 三、固化工作流引擎 需求

### 3.1 核心特性

| 特性 | 要求 | 验收标准 |
|------|------|---------|
| **零 LLM 延迟** | 工作流执行路径不经过任何 LLM 推理 | 从触发到执行完成 < 1s |
| **幂等执行** | 同一输入重复执行 N 次，效果 = 执行 1 次 | 运行时检查 + 执行前预检 |
| **预审计白名单** | 明确定义哪些操作可自动执行，哪些需确认 | 白名单必须经安全团队审核 |
| **事件驱动** | 支持 CloudMonitor 告警 -> 工作流自动触发 | EventBridge 事件 -> 函数计算 |
| **可观测** | 工作流执行状态、耗时、结果可追踪 | JSON trace 持久化 |
| **回滚** | 工作流执行失败时有预设回滚路径 | 每个步骤都有 undo 指令 |

### 3.2 预授权操作白名单框架

> 以下操作经过安全评估后，可纳入"自动执行白名单"。

| 操作 | 风险等级 | 自动执行条件 | 是否需要通知 |
|------|---------|-------------|------------|
| RDS 清理 binlog (`CALL mysql.rds_cycle_binlog()`) | 低 | 磁盘 > 85% 且 binlog 占用 > 50% | 执行后通知 |
| Redis 修改 maxmemory-policy | 低 | 内存 > 80% 且逐出次数 > 0 | 执行后通知 |
| ECS CloudAssistant 执行诊断脚本 | 极低 | 任何诊断场景 | 不需要 |
| RDS 存储空间扩容 | 中 | 磁盘 > 90% 且自动扩容未启用 | 确认后执行 |
| ECS 重启 | 中 | 内核参数修改/系统异常 | 确认后执行 |
| 安全组规则删除 | 高 | 0.0.0.0/0 暴露管理端口 | 需人工确认 |
| ECS 升配 | 高 | CPU > 85% 持续 30min | 需人工确认 |

### 3.3 工作流定义规范

```yaml
# 工作流定义示例 — RDS 磁盘清理
id: rds-disk-cleanup-v1
trigger:
  event: cloudmonitor.alert
  condition: metric == "DiskUsage" && value > 85 && resource_type == "RDS"
steps:
  - id: diagnose
    action: "aliyun cms DescribeMetricList --Namespace acs_rds_dashboard --MetricName DiskUsage"
    jq_filter: '.Datapoints | fromjson | [.[].Average] | max'
    timeout: 5s
  - id: analyze
    action: "python3 scripts/das_space_analysis.py --instance-id $INSTANCE_ID"
    timeout: 30s
    depends_on: [diagnose]
  - id: cleanup-binlog
    condition: "${analyze.binlog_ratio > 0.5}"
    action: "aliyun rds ModifyDBInstanceSpec --BinlogRetentionHours 24"
    timeout: 10s
    depends_on: [analyze]
  - id: verify
    action: "aliyun cms DescribeMetricList --Namespace acs_rds_dashboard --MetricName DiskUsage"
    timeout: 5s
    depends_on: [cleanup-binlog]
safety:
  max_retries: 2
  rollback: "aliyun rds ModifyDBInstanceSpec --BinlogRetentionHours 168"
  human_confirm: false  # 预授权
```

---

## 四、弹性 Agent 引擎 需求

### 4.1 核心特性

| 特性 | 要求 | 验收标准 |
|------|------|---------|
| **多数据源融合** | 同时查询 CloudMonitor + SLS + ARMS + ActionTrail | 一次排查至少关联 3 种数据源 |
| **动态规划** | LLM 自主决策"下一步查什么"，而非预设决策树 | 能处理未在 runbook 中定义的故障模式 |
| **工具调用** | Agent 可自主选择 CLI / SDK / API / 脚本 等工具 | 工具清单 ≥ 10 个 |
| **上下文记忆** | 多轮推理中保持排查上下文 | 中间结果不丢失，可回溯每一步 |
| **方案生成** | 根因找到后自动生成修复方案（含回滚） | 方案经人工确认后可一键执行 |
| **Incident DB** | 每次故障排查记录到 Incident Database | 支持事后检索和模式匹配 |

### 4.2 工具目录

| 工具名 | 用途 | 数据源 | 延迟 |
|--------|------|--------|------|
| cloudmonitor_query | 查询指标趋势 | CloudMonitor | 2-5s |
| sls_log_query | 查询应用日志关键词 | SLS (Log Service) | 3-10s |
| arms_trace_query | 查询调用链慢调用 | ARMS | 3-8s |
| actiontrail_query | 查询近期配置变更 | ActionTrail | 2-5s |
| das_slow_query | 数据库慢 SQL 分析 | DAS (Go SDK) | 5-15s |
| cloud_assistant_run | ECS 内执行诊断命令 | CloudAssistant | 5-15s |
| ecs_describe | ECS 详情/状态查询 | ECS API | 1-3s |
| rds_describe | RDS 详情/状态查询 | RDS API | 1-3s |
| incident_search | 检索历史相似故障 | Incident DB | 1-2s |
| topo_discovery | 获取当前资源拓扑 | topo-discovery | 5-10s |

### 4.3 排查流程模式

```
Phase 1: 全景扫描 (并行)
  -> 查 topo: 当前链路拓扑
  -> 查 cloudmonitor: 最近 1h 所有指标
  -> 查 actiontrail: 最近 6h 配置变更
  -> 查 incident: 历史相似故障

Phase 2: 定向深入 (LLM 决策)
  -> 根据 Phase 1 发现选择 1-2 个方向深入
  -> 例: 如果 SLB 健康检查失败 -> 查 ECS 端口 + 安全组
  -> 例: 如果 RDS CPU 高 -> 查 DAS 慢查询 + SLS 应用日志

Phase 3: 根因确认 + 方案
  -> 汇总所有发现，输出根因概率排序
  -> 生成修复方案（含回滚步骤）
  -> 等待人工确认后执行
```

---

## 五、智能调度器 需求

| 特性 | 要求 |
|------|------|
| **事件分类** | 自动将输入事件分为"已知模式 / 疑似已知 / 未知模式" |
| **风险评分** | 综合操作类型、影响范围、历史成功率给出 0-10 分 |
| **路由决策** | 低风险已知模式 -> 固化工作流；高风险/未知 -> 弹性Agent |
| **升级机制** | 工作流执行失败 -> 自动升级到 Agent；Agent 失败 -> 升级到人 |
| **可配置策略** | 允许用户配置风险偏好（激进/保守/自定义） |

---

## 六、Phase 路线图

```
Phase 1 (v1.0)          Phase 2 (v1.5)           Phase 3 (v2.0)
─────────────────────  ──────────────────────  ──────────────────────
  Rule-based 巡检          Runbook 脚本化          固化工作流 DAG
  单 LLM 驱动              预授权操作白名单         弹性 Agent 多数据源
  纯读/建议                并行执行加速             SLS + ARMS 集成
  GCL 品质门               结果缓存复用            Incident DB
                           事件触发 (ActionTrail)   智能调度器
                          动态基线异常评分

  <- 我们现在在这里                                   目标 ->
```

---

## 七、设计决策记录

### ADR-001: 工作流引擎选型

| 选项 | 优势 | 劣势 |
|------|------|------|
| Bash 脚本 + crontab | 零依赖，当前 CLI 生态 | 无状态管理、无可视化 |
| Argo Workflows (K8s) | DAG 原生、可观测 | 需要 K8s 集群 |
| Temporal | 企业级工作流引擎 | 部署运维成本高 |
| 阿里云 EventBridge + FC | 原生事件驱动、免运维 | 绑定阿里云生态 |

**倾向性**：Phase 2 先用 Bash 脚本（最低成本验证），Phase 3 评估 EventBridge + FC。

### ADR-002: 动态基线 ML 运行时

| 选项 | 优势 | 劣势 |
|------|------|------|
| jq + bc（当前方案） | 零依赖，随 CLI 运行 | 只能做简单 Z-Score |
| Python statsmodels | 支持时序分解、Prophet | 需要 Python 运行时 |
| 阿里云 DAS 智能评分 | 阿里云原生，无需开发 | 仅限 RDS |

**倾向性**：短期用 jq + bc 做 Z-Score（已实现），中期评估 DAS 智能评分接口。

### ADR-003: 安全模型

| 设计原则 | 说明 |
|---------|------|
| **默认拒绝** | 所有写操作默认需要人工确认，只有白名单内的才可自动执行 |
| **白名单审查** | 白名单每季度安全审计，新增条目需架构师 + 安全团队审批 |
| **操作可追溯** | 无论是工作流还是 Agent 执行，每条命令都记录 trace |
| **执行前预检** | 工作流执行前检查前置条件是否满足，不满足则 HALT |