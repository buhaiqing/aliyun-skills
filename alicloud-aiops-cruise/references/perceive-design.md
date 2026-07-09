# Perceive Layer — 感知 Agent 详细设计

> 所属 Skill: `alicloud-aiops-cruise` v1.1.0
> 位置: `scripts/agents/perceive/`
> 更新日期: 2026-06-07

---

## 1. 设计目标

感知层（Perceive Layer）是 Agentic System 的"眼睛和耳朵"，负责：

1. **数据采集** — 从阿里云各产品采集原始数据（拓扑、监控、成本、安全、事件）
2. **初步发现** — 识别异常信号（成本环比>30%、漏洞、配置漂移）
3. **标准化输出** — 将 Findings 按统一 Schema 输出，传给推理层（Reasoner）

**关键原则**：感知层只读，不执行任何变更操作。发现的问题通过 Finding 事件传递。

---

## 2. 组织结构

```
scripts/agents/perceive/       # 感知层统一入口
├── __init__.sh                # 统一调度入口 (Shell)
├── infra/                     # 基础设施巡检 (AIOps 核心链路)
│   ├── healthcruise.sh        # 委托 aiops-cruise runbooks/scripts/daily-health-check.py
│   ├── toposcan.sh            # 委托 alicloud-topo-discovery/scripts/topo-scan.sh
│   └── configdrift.sh         # 委托 alicloud-topo-discovery/scripts/baseline-manager.py
├── cost/                      # 成本监察
│   └── costwatch.sh           # 委托 aiops-cruise runbooks/scripts/cost-watch.py
├── security/                  # 安全监控
│   ├── securityscan.sh        # 委托 alicloud-sas-ops
│   └── audittrail.sh          # 委托 alicloud-actiontrail-ops
└── advisor/                   # 顾问建议
    └── advisorscan.sh         # 委托 alicloud-advisor-ops
```

分层依据：

| 目录 | 领域 | 调度周期 | 推理层对接 |
|------|------|:-------:|-----------|
| `infra/` | 基础设施运维 | 每 6h | AIOps Inference Agent + Network Diagnosis Agent |
| `cost/` | 成本管理 | 每日 | Cost Analysis Agent |
| `security/` | 安全监控 | 每日 | Security Analysis Agent |
| `advisor/` | 顾问建议 | 每日 | Architecture Review Agent |

---

## 3. Agent 详细规格

### 3.1 HealthCruise Agent

| 属性 | 值 |
|------|------|
| **路径** | `infra/healthcruise.sh` |
| **委托 Skill** | `aiops-cruise runbooks/scripts/daily-health-check.py` |
| **调度** | 每 6h（cron `0 */6 * * *`） |
| **安全等级** | SAFE 自动（纯读） |
| **输出 Schema** | `{"agent":"healthcruise","findings":[...],"topology":{...}}` |
| **依赖** | aliyun CLI, Python3, aliyun AK |

**扫描链路**: EIP -> SLB -> ECS -> RDS/Redis -> NAT -> 安全组

### 3.2 TopoScan Agent

| 属性 | 值 |
|------|------|
| **路径** | `infra/toposcan.sh` |
| **委托 Skill** | `alicloud-topo-discovery/scripts/topo-scan.sh` |
| **调度** | 每日（cron `0 2 * * *`）|
| **安全等级** | SAFE 自动（纯读）|
| **输出** | 资源清单 JSON + 拓扑图 |

### 3.3 ConfigDrift Agent

| 属性 | 值 |
|------|------|
| **路径** | `infra/configdrift.sh` |
| **委托 Skill** | `alicloud-topo-discovery/scripts/baseline-manager.py` |
| **调度** | 按需（TopoScan 后触发）|
| **安全等级** | SAFE 自动（纯读）|
| **输出** | 漂移项列表（新增/删除/变更资源）|

### 3.4 CostWatch Agent

| 属性 | 值 |
|------|------|
| **路径** | `cost/costwatch.sh` |
| **委托 Skill** | `aiops-cruise runbooks/scripts/cost-watch.py` |
| **调度** | 每日（cron `0 9 * * *`）|
| **安全等级** | SAFE 自动（纯读）|
| **检查项** | ① 成本环比异常 ② 资源到期预警 ③ RI/SP 覆盖率 ④ 预算跟踪 ⑤ 账户健康 |

### 3.5 SecurityScan Agent

| 属性 | 值 |
|------|------|
| **路径** | `security/securityscan.sh` |
| **委托 Skill** | `alicloud-sas-ops` |
| **调度** | 每日（cron `0 8 * * *`）|
| **安全等级** | SAFE 自动（纯读）|
| **检查项** | ① 漏洞扫描 ② AK 泄漏检测 ③ 基线合规检查 |

### 3.6 AuditTrail Agent

| 属性 | 值 |
|------|------|
| **路径** | `security/audittrail.sh` |
| **委托 Skill** | `alicloud-actiontrail-ops` |
| **调度** | 每日 + 实时事件 |
| **安全等级** | SAFE 自动（纯读）|
| **检查项** | 异常 API 调用检测（高频失败、异常操作） |

### 3.7 AdvisorScan Agent

| 属性 | 值 |
|------|------|
| **路径** | `advisor/advisorscan.sh` |
| **委托 Skill** | `alicloud-advisor-ops` |
| **调度** | 每日（cron `0 10 * * *`）|
| **安全等级** | SAFE 自动（纯读）|
| **检查项** | ① 健康检查建议 ② 成本优化建议 |

---

## 4. 调度与编排

### 4.1 统一入口 `__init__.sh`

```bash
# 全量执行（推荐 cron 调用）
bash scripts/agents/perceive/__init__.sh

# 仅基础设施巡检（每 6h）
bash scripts/agents/perceive/__init__.sh --mode infra

# 成本 + 安全 + 顾问（每日）
bash scripts/agents/perceive/__init__.sh --mode cost
bash scripts/agents/perceive/__init__.sh --mode security
bash scripts/agents/perceive/__init__.sh --mode advisor

# 查看结构
bash scripts/agents/perceive/__init__.sh --describe
```

### 4.2 推荐 cron 配置

```cron
# ── Perceive Layer 定时调度 ──

# 基础设施巡检 (每 6h)
0 */6 * * * cd /path/to/aliyun-skills/alicloud-aiops-cruise && \
  bash scripts/agents/perceive/__init__.sh --mode infra 2>&1 | logger -t perceive-infra

# 成本监察 (每日 9:00)
0 9 * * * cd /path/to/aliyun-skills/alicloud-aiops-cruise && \
  bash scripts/agents/perceive/__init__.sh --mode cost 2>&1 | logger -t perceive-cost

# 安全监控 (每日 8:00)
0 8 * * * cd /path/to/aliyun-skills/alicloud-aiops-cruise && \
  bash scripts/agents/perceive/__init__.sh --mode security 2>&1 | logger -t perceive-security

# 顾问建议 (每日 10:00)
0 10 * * * cd /path/to/aliyun-skills/alicloud-aiops-cruise && \
  bash scripts/agents/perceive/__init__.sh --mode advisor 2>&1 | logger -t perceive-advisor
```

### 4.3 Baseline Retention 调度 (Sprint 16)

```cron
# ── Baseline 累积 + 清理 ──

# 每日 02:00 — 累积新 baseline (topo-scan)
0 2 * * * cd /path/to/aliyun-skills/alicloud-topo-discovery/scripts && \
  python3 baseline-manager.py --output-dir /path/to/aliyun-skills/infra-baseline \
  --region ${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou} \
  2>&1 | logger -t baseline-collect

# 每周日 03:00 — 清理过期 baseline (>90 天)
0 3 * * 0 cd /path/to/aliyun-skills/alicloud-topo-discovery/scripts && \
  python3 baseline-manager.py --output-dir /path/to/aliyun-skills/infra-baseline \
  --apply-retention --retention-days 90 \
  2>&1 | logger -t baseline-cleanup

# 每周一 09:00 — 跑 configdrift 对比"上周 vs 现在"
0 9 * * 1 cd /path/to/aliyun-skills/alicloud-aiops-cruise && \
  bash scripts/agents/perceive/infra/configdrift.sh \
  --compare-with $(date -v-7d '+%Y-%m-%d' 2>/dev/null || date -d '7 days ago' '+%Y-%m-%d') \
  2>&1 | logger -t configdrift-weekly
```

> **注意**: `date -v-7d` 是 BSD/macOS 语法, Linux 用 `date -d '7 days ago'`。脚本会自动 fallback (见 `configdrift.sh`)。

---

## 5. 与 Reasoning 层的集成

感知层产出统一格式的 Finding 事件，由推理层消费：

```json
{
  "agent": "healthcruise",
  "findings": [
    {
      "rule_id": "ECS-HIGH-CPU-001",
      "resource_id": "i-abc123",
      "severity": "warning",
      "metric": "CPUUtilization",
      "value": 92.5,
      "threshold": 80
    }
  ]
}
```

推理层 Agent（AIOps Inference / Cost Analysis / Security Analysis / Architecture Review）读取这些 Findings 后做关联推理。

---

## 6. 变更日志

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-06-07 | 初始版本 — 定义 7 个感知 Agent 结构和规格 |