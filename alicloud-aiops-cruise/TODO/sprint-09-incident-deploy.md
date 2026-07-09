# Sprint 9: Incident 落地（P3）

> **状态**: PASS 6/6 (MVP)
> **业务价值**：将分散的巡检发现持久化为标准化的 Incident 记录，支持故障检索、历史回溯、趋势分析，为 Sprint 11 (ML 升级) 和 Sprint 12 (双引擎) 提供数据基础
> **交付物**：`references/incident-deploy.md` + `scripts/incident-store.py` + `.runtime/incidents/` 目录结构
> **前置条件**：Sprint 7 (Incident Schema PASS)
> **关联验收项**：S1-D5 (Incident Schema)

---

## 一、设计目标

### 1.1 问题背景

当前 4 个 runbook 输出 findings 到 stdout 和 JSON 报告，但：
- **无持久化**：每次运行覆盖上次结果，无法做趋势分析
- **无检索能力**：无法回答"上周有多少 RDS 磁盘告警"
- **无去重**：同一问题每天重复报告，导致告警疲劳
- **无关联**：跨 runbook 的同一根因问题无法关联

### 1.2 落地原则

| 原则 | 说明 |
|------|------|
| **去重优先** | 同一资源同一天同规则只生成 1 个 Incident |
| **可追溯** | 每个 Incident 保留完整的 `trace.commands_executed` |
| **可检索** | 按 (customer, resource_type, level, rule_id, date) 五维度索引 |
| **可扩展** | Schema 支持 Sprint 11 ML 输出的 `anomaly_score` 字段 |
| **零依赖** | 纯文件系统存储，不引入 SQLite/Redis |

---

## 二、存储设计

### 2.1 目录结构

```
.runtime/
└── incidents/
    └── {customer}/
        └── {date}/                    # YYYY-MM-DD
            ├── {resource_type}/       # ecs|rds|redis|slb|ack|nas|eip|nat|vpc|sg
            │   ├── {rule_id}_{resource_id}.json
            │   └── index.jsonl        # 当日该类型所有 incidents 索引
            └── daily-summary.json     # 当日聚合统计
```

### 2.2 文件格式

**单 Incident 文件** (`SLB-ECS-01_lbp1bxxxx.json`):
```json
{
  "id": "inc-20250606-7a8b9c",
  "customer": "hd123-crm-prod",
  "timestamp": "2026-06-06T14:32:01+08:00",
  "scenario": "daily-health",
  "level": "CRITICAL",
  "resource_type": "SLB",
  "resource_id": "lb-bp1bxxxx",
  "rule_id": "SLB-ECS-01",
  "title": "SLB后端ECS健康检查失败",
  "impact": "10/12 后端ECS unhealthy，业务可用性 83%",
  "suggestion": "检查ECS实例hd-ecs-web-03的进程和健康检查端口",
  "dedup_key": "hd123-crm-prod:SLB:lb-bp1bxxxx:SLB-ECS-01:2026-06-06",
  "metric": "UnhealthyBackendServerCount",
  "current_value": 10,
  "threshold": 0,
  "baseline_mean": null,
  "baseline_std": null,
  "z_score": null,
  "fix_commands": [
    "aliyun ecs DescribeInstances --InstanceIds '[\"i-bp1axxxx\"]'",
    "ssh root@1.2.3.4 'systemctl status nginx'"
  ],
  "ttl_hours": 24,
  "assignee": null,
  "status": "OPEN",
  "run_id": "run-20250606-143201-abc123",
  "parent_incident_id": null,
  "related_incidents": [],
  "trace": {
    "commands_executed": [...],
    "stdout_digest": "sha256:abc...",
    "stderr_digest": null
  }
}
```

**索引文件** (`index.jsonl`):
```jsonl
{"id": "inc-20250606-7a8b9c", "level": "CRITICAL", "rule_id": "SLB-ECS-01", "resource_id": "lb-bp1bxxxx", "title": "SLB后端ECS健康检查失败"}
{"id": "inc-20250606-8c9d0e", "level": "WARNING", "rule_id": "RDS-04", "resource_id": "rm-bp1yyyy", "title": "RDS磁盘使用率>95%"}
```

### 2.3 去重策略

```python
# dedup_key 生成规则
dedup_key = f"{customer}:{resource_type}:{resource_id}:{rule_id}:{date_bucket}"
# 示例: "hd123-crm-prod:SLB:lb-bp1bxxxx:SLB-ECS-01:2026-06-06"
```

去重逻辑：
1. 写之前检查 `dedup_key` 是否已存在
2. 存在则更新 `timestamp` 和 `trace`（刷新观察时间）
3. 不存在则新建 Incident

---

## 三、任务清单

- [x] **9.1** 创建 `scripts/incident-store.py` 核心模块
  - [x] `save_incident(incident: dict) -> str` 保存单条
  - [x] `get_incident(dedup_key: str) -> dict | None` 查询单条
  - [x] `list_incidents(customer, date, resource_type=None, level=None) -> list` 列表查询
  - [x] `update_incident(dedup_key, updates) -> bool` 更新状态
  - [x] `generate_dedup_key(customer, resource_type, resource_id, rule_id, date) -> str` 生成去重键
- [x] **9.2** 实现 `index.jsonl` 索引维护（追加写，无需重写整个文件）
- [x] **9.3** 实现 `daily-summary.json` 自动聚合（按 level/resource_type 统计）
- [x] **9.4** 在 4 个 runbook 中集成 `incident-store.py`
  - [x] `daily-health-check.py` 输出时自动 save_incident
  - [x] `emergency-troubleshoot.py` 输出时自动 save_incident
  - [x] `capacity-planning.py` 输出时自动 save_incident
  - [x] `pre-launch-check.py` 输出时自动 save_incident
- [x] **9.5** 提供 CLI 查询工具 `scripts/incident-query.py`
  - [x] 按日期范围查询
  - [x] 按 resource_type 过滤
  - [x] 按 level 过滤
  - [x] 输出 JSON/Table 格式
- [x] **9.6** 编写 `references/incident-deploy.md` 完整规范
- [x] **9.7** TODO.md / stage-status.json 同步

---

## 四、质量门

| 编号 | 检查项 | 验证命令 | 阈值 |
|------|--------|----------|------|
| Q9.1 | `incident-store.py` 存在 | `test -s scripts/incident-store.py` | 通过 |
| Q9.2 | `save_incident()` 函数存在 | `grep -c 'def save_incident' scripts/incident-store.py` | ≥ 1 |
| Q9.3 | 去重逻辑正确 | `grep -c 'dedup_key' scripts/incident-store.py` | ≥ 3 |
| Q9.4 | 索引文件生成 | `python3 scripts/incident-store.py --test-index` | 通过 |
| Q9.5 | 4 个 runbook 已集成 | `grep -c 'incident-store' runbooks/scripts/*.py` | ≥ 4 |
| Q9.6 | CLI 查询工具可用 | `python3 scripts/incident-query.py --help` | 返回帮助 |
| Q9.7 | `incident-deploy.md` 存在 | `test -s references/incident-deploy.md` | 通过 |
| Q9.8 | 存储目录创建 | `test -d .runtime/incidents` | 通过 |
| Q9.9 | Ruff Lint | `ruff check scripts/incident-store.py scripts/incident-query.py` | 0 错误 |
| Q9.10 | TODO.md 同步 | `grep -c 'Sprint 9.*9/' TODO.md` | ≥ 1 |

---

## 五、与现有文档的关系

| 现有文件 | 关系 |
|----------|------|
| `references/incident-schema.md` | 本 Sprint 存储的 Incident 必须符合该 Schema |
| `references/delivery-standards.md` | JSON 报告中的 `incidents` 字段即本 Sprint 的持久化输出 |
| `references/cache-strategy.md` | Sprint 8 缓存减少 Incident 落地时的 API 压力 |
| Sprint 7 (Incident Schema) | 前置依赖，提供字段定义和校验规则 |
| Sprint 11 (ML 升级) | 后续消费方，需要本 Sprint 的历史 Incident 数据做训练 |
| Sprint 12 (双引擎) | 后续消费方，需要本 Sprint 的检索能力做工单关联 |

---

## 六、Sprint 完成判据

- 所有 7 个任务项 `[x]`
- 所有 10 个 Q 检查项 PASS
- 4 个 runbook 运行后可在 `.runtime/incidents/` 看到生成的 Incident 文件
- `incident-query.py` 能正确查询历史 Incident
- TODO.md / stage-status.json 同步更新
- Post-Update Self-Review R1 + R2 全部 PASS

---

## 七、变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-06-06 | 初始版本，MVP 完成 |
