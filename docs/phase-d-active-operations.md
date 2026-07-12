# Phase D — 主动运营能力文档

> **归属**: Level 3→4 智能进化计划 (Gartner AI Maturity)
> **完整计划**: [`docs/intelligence-evolution-plan.md`](intelligence-evolution-plan.md)
> **状态**: 开发中（ultracode 工作流执行）

---

## 概述

Phase D 是智能进化的最后一阶段，核心跨越从 **"被动响应"** 到 **"主动运营"**。
结合 Phase A（反馈闭环）、Phase B（风险预判）、Phase C（智能融合），
形成完整的 **"发现 → 分析 → 预判 → 工单"** 闭环。

---

## D1 — 自动化资源优化巡航

### 能力

每周自动触发一次全链路 AIOps 巡航，无需人工介入。

| 组件 | 说明 |
|------|------|
| **调度器** | `scripts/cruise/scheduler.sh` — crontab 就绪，支持 `--dry-run` / `--core` / `--all` |
| **巡检范围** | HealthCruise（健康） + TopoScan（拓扑） + ConfigDrift（配置漂移） + CostWatch（成本） + SecurityScan（安全） + AuditTrail（审计） + AdvisorScan（顾问） |
| **后处理** | 自动触发 fusion_report.sh → root_cause_engine.sh |
| **输出** | `cruise-report-weekly-{date}.json` + Markdown 摘要（≤100 行） |
| **TTL** | 保留 4 周，超期自动清理 |

### 输出示例

```
docs/cruise-reports/
├── cruise-weekly-20260712.md      # Markdown 摘要（human/agent 可读）
└── cruise-weekly-20260712.json    # 原始数据
```

---

## D2 — 变配预检自动触发

### 能力

在 GCL 执行 write/delete 等高危操作前，自动触发 AIOps 健康检查。

| 场景 | 行为 |
|------|------|
| Risk Score ≥ 0.5 + AIOps 可用 | 自动触发目标链路健康检查 |
| 检查完成 | 结果注入 Generator prompt 作为 `{{preflight_health}}` |
| 发现 CRITICAL/HIGH | 输出 `[PREFLIGHT] WARNING` 日志，不阻止操作 |
| AIOps 不可用 | 静默跳过，不影响主流程 |

### 集成点

```
gcl_runner.py main() 
  │
  ├─ risk_scorer() → risk_score=0.575  (DeleteInstance)
  │
  └─ risk_score ≥ 0.5?
       ├─ Yes → aiopscruise_health_check(skill, op, command)
       │         └─ 调用 alicloud-aiops-cruise 目标资源健康检查
       │         └─ {{preflight_health}} → Generator prompt
       └─ No  → skip
```

---

## D3 — 风险预警自动工单化

### 能力

**全量覆盖**：CRITICAL/HIGH 级别的**所有巡检发现** + pass-rate 异常 → 自动生成标准化工单 JSON。
不限 ECS，覆盖 cruise 巡检涉及的所有资源类型和对应的 ops skill：

| 资源类型 | 对应 Skill | 典型场景 |
|----------|-----------|----------|
| ECS | `alicloud-ecs-ops` | 闲置/高负载/安全暴露 |
| RDS | `alicloud-rds-ops` | 连接数过高/慢 SQL |
| Redis | `alicloud-redis-ops` | 内存超限/无备份 |
| SLB | `alicloud-slb-ops` | 健康检查失败 |
| MongoDB | `alicloud-mongodb-ops` | 磁盘/连接异常 |
| Elasticsearch | `alicloud-elasticsearch-ops` | 节点/索引异常 |
| NAT/EIP/VPC | `alicloud-vpc-ops` | 带宽/策略冲突 |
| 安全组/CFW | `alicloud-ecs-ops` / 跨 skill | 端口过开放/策略不一致 |

| 数据源 | 触发条件 | 输出 |
|--------|----------|------|
| Fusion report | 存在 severity=CRITICAL 或 HIGH 的 finding | ticket JSON → `.runtime/tickets/` |
| 异常检测报告 | pass-rate 的 3σ/50% 下降 | ticket JSON → `.runtime/tickets/` |

### 工单 Schema

```json
{
  "ticket_id": "ticket-20260712T120000Z-001",
  "severity": "CRITICAL",
  "skill": "alicloud-ecs-ops",
  "finding": {
    "domain": "security",
    "description": "闲置 ECS 同时有安全暴露风险",
    "resource_id": "i-xxx"
  },
  "suggested_action": "下线或绑定 WAF",
  "timestamp": "2026-07-12T12:00:00Z",
  "git_commit": "abc123def456..."
}
```

### Jira 集成（内置）

`ticket_generator.sh` 内置 Jira 集成能力，无需第三方工具桥接。

| 模式 | 触发方式 | 说明 |
|------|----------|------|
| **JSON 输出** | 默认 | 工单 JSON 写入 `.runtime/tickets/`，供人工/其他工具消费 |
| **Jira 直接创建** | `--jira` 标志 | 通过配置的 Jira 端点直接创建 issue |
| **Jira dry-run** | `--jira-dry-run` | 预览将创建的 Jira issue 内容，不实际创建 |

### Jira 字段映射

| 工单字段 | Jira 字段 | 映射规则 |
|----------|-----------|----------|
| severity=CRITICAL | priority | Highest |
| severity=HIGH | priority | High |
| severity=MEDIUM | priority | Medium |
| severity=LOW | priority | Low |
| skill | components | 自动匹配到对应 ops skill component |
| finding.description | summary | 截取前 200 字符作为标题 |
| suggested_action | description | 完整建议内容 |
| finding.domain | labels | 自动打标，如 `security`、`cost`、`health` |
| timestamp | 创建时间 | 自动填充 |
| git_commit | 自定义字段 | 追溯版本 |

### Jira 配置

通过环境变量配置（无需硬编码）：
- `JIRA_URL` — Jira 实例地址
- `JIRA_EMAIL` — 认证邮箱
- `JIRA_API_TOKEN` — API token
- `JIRA_PROJECT_KEY` — 目标项目 key（如 DOPS）
- `JIRA_COMPONENT_MAP` — skill 到 component 的 JSON 映射表

未配置时降级为 JSON 输出模式，不影响主流程。

---

## 智能等级定位

```
Level 3 (Automated)      → 自动化执行 + 质量门禁
Level 3.5 (Phase A+B+C)  → 可预判 + 可学习 + 可推理
Level 4 (Phase D)        → 主动巡航 + 变配预检 + 自动工单
                            ↑ 当前目标
```

Phase D 完成后，系统将从 **"人等系统发现问题"** 变为 **"系统主动发现并推送给人的问题"**。