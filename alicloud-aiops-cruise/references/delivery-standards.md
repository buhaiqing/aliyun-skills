---
name: delivery-standards
version: "1.0.0"
parent: alicloud-aiops-cruise
status: mandatory
---

# 巡检交付产物标准

> **每次巡检执行完成后，必须输出以下三份交付物。缺少任何一份视为交付不完整。**

---

## 1. Markdown 报告（给人看——运维负责人）

### 文件路径
`audit-results/reports/cruise-{customer}-{date}.md`

### 必须包含的章节

| 章节 | 内容 | 是否必选项 |
|------|------|-----------|
| 报告元信息 | 报告ID、客户名、时间、区域、窗口 | 必选 |
| 总体评分 | 整体健康度 + 安全/容量/异常 评分 | 必选 |
| 服务摘要 | 各产品资源数量 + 核心指标状态（PASS/WARNING/CRITICAL） | 必选 |
| 拓扑关系图 | ASCII 树形图 + Mermaid 图，叠加健康状态 | 必选 |
| Critical 问题清单 | 每个问题含：实例ID、指标值、阈值、Z-Score、推理规则、修复步骤 | 必选 |
| Warning 问题清单 | 同上，级别为 Warning | 必选 |
| 异常评分摘要 | 资源/指标/当前值/基线μ/Z-Score 表格 | 必选 |
| 优化建议（按优先级） | 建议 + 优先级标签 + CLI 命令 | 必选 |
| 审计追踪 | JSON 报告路径、执行耗时、runbook 版本 | 必选 |

### 报告格式规范

```markdown
═══════════════════════════════════════════════════════
  [SCAN] 全链路 AIOps 深度巡检报告
═══════════════════════════════════════════════════════
  报告ID: cruise-{customer}-{timestamp}
  客户: {customer} | 时间: {datetime} | 窗口: {start} -> {end}
  区域: {region} | 模式: {mode}
═══════════════════════════════════════════════════════

[STATS] 总体评分
  整体健康度: {overall_score}/1.0 | {overall_level}
  安全水位:   {safety_score}/1.0 | {safety_level}
  容量水位:   {capacity_score}/1.0 | {capacity_level}
  异常评分:   {anomaly_score}/1.0 | {anomaly_level}

─────── 服务摘要 ───────
  {service_summary_table}

[ART] 拓扑关系图
  {topology_ascii_or_mermaid}

Critical 问题清单
  {critical_findings_section}

Warning 问题清单
  {warning_findings_section}

[STATS] 异常评分摘要（动态基线）
  {anomaly_scores_table}

[PIN] 优化建议（按优先级）
  {optimization_suggestions}

═══════════════════════════════════════════════════════
  审计追踪
═══════════════════════════════════════════════════════
  JSON报告: audit-results/json/cruise-{customer}-{date}.json
  执行耗时: {duration}s | runbook: v{version} | GCL: {gcl_result}
```

---

## 2. 评分看板（给人看——IT 管理者/客户）

### 文件路径
`audit-results/dashboards/cruise-{customer}-{date}.md`

### 必须包含的内容

| 指标 | 说明 | 计算方式 |
|------|------|---------|
| 整体健康度 | 综合评分 (0-100) | 加权平均: 可用性×0.3 + 安全×0.2 + 性能×0.2 + 容量×0.15 + 成本×0.15 |
| 可用性评分 | 服务可用状态 | (正常资源数 / 总资源数) × 100 |
| 安全评分 | 安全合规状态 | 无高危规则=100, 每项高危-10 |
| 性能评分 | 性能瓶颈状态 | Critical=0, Warning=50, 正常=100 的加权平均 |
| 容量评分 | 容量余量状态 | 同上, 按容量阈值判定 |
| 成本评分 | 资源利用率 | 低利用率资源占比反向评分 |
| 周趋势 | 相比上周的变化 | [UP] 上升 / [DOWN] 下降 / -> 持平 |
| 上月故障数 | 上月 Incident 数量 | 从 Incident DB 读取 |
| 平均修复时间 | MTTR | 从 Incident DB 计算 |

### 格式规范

```markdown
══════════════════════════════════════
  AIOps 健康看板 - {customer}
══════════════════════════════════════
  报告期间: {date_range}
══════════════════════════════════════

  整体健康度: {score}/100  {trend_icon}
    可用性:  {availability}%  {status_icon}
    安全:    {security}%    {status_icon}
    性能:    {performance}%  {status_icon}
    容量:    {capacity}%    {status_icon}
    成本:    {cost}%        {status_icon}

  本周趋势: {trend_text} (上周 {last_week}->本周 {this_week})
  上月故障: {incident_count} 次，平均修复时间 {mttr}min
  本月预估: {monthly_forecast}
```

---

## 3. JSON 结构化报告（给机器——自动化系统/GCL 审计）

### 文件路径
`audit-results/json/cruise-{customer}-{date}.json`

### 必须包含的字段

```json
{
  "report_id": "cruise-{customer}-{YYYYMMDD}",
  "customer": "string",
  "timestamp": "ISO8601",
  "scenario": "daily_check | emergency | capacity | pre_launch",
  "runbook_version": "semver",
  "region": "string",
  "mode": "standard | deep",
  "execution_duration_seconds": 0,
  "gcl_result": "pass | warning | fail | abort",

  "resource_stats": {
    "ecs": 0, "slb": 0, "rds": 0, "redis": 0, "nat": 0, "eip": 0, "vpc": 0
  },

  "scores": {
    "overall": 0.0,
    "availability": 0.0,
    "security": 0.0,
    "performance": 0.0,
    "capacity": 0.0,
    "cost": 0.0
  },

  "incidents": [
    {
      "incident_id": "uuid",
      "schema_version": "1.0.0",
      "customer": "string",
      "timestamp": "ISO8601",
      "run_id": "uuid",
      "level": "CRITICAL | WARNING | INFO",
      "score": 0.0,
      "resource_type": "ECS|SLB|RDS|Redis|NAT|EIP|SG|ACK|OTHER",
      "resource_id": "string",
      "resource_name": "string | null",
      "region": "string",
      "rule_id": "string",
      "rule_version": "semver",
      "title": "string",
      "dedup_key": "string | null",
      "metric": "string | null",
      "current_value": 0.0,
      "threshold_critical": 0.0,
      "threshold_warning": 0.0,
      "baseline_mean": 0.0,
      "baseline_std": 0.0,
      "z_score": 0.0,
      "impact": "string",
      "suggestion": "string",
      "fix_commands": ["string"],
      "status": "open | acknowledged | in_progress | resolved | suppressed",
      "assignee": "string | null",
      "ttl_hours": 168,
      "parent_incident_id": "uuid | null",
      "related_incidents": ["uuid"],
      "trace": {
        "runbook_id": "string",
        "runbook_version": "semver",
        "scenario": "daily_check | emergency | capacity | pre_launch",
        "commands_executed": [{"command": "string", "params": {}, "response_excerpt": "string", "duration_ms": 0}],
        "total_api_calls": 0,
        "detection_method": "z-score | percentile | stl | static-threshold | hybrid",
        "report_path": "string"
      },
      "tags": ["string"],
      "metadata": {}
    }
  ],

  "critical_findings": [
    {
      "title": "string",
      "instance_id": "string",
      "instance_name": "string",
      "resource_type": "ECS|SLB|RDS|Redis|NAT|EIP|SG",
      "metric": "string",
      "current_value": 0.0,
      "threshold_critical": 0.0,
      "threshold_warning": 0.0,
      "baseline_mean": 0.0,
      "baseline_std": 0.0,
      "z_score": 0.0,
      "level": "CRITICAL|WARNING",
      "rule_id": "string",
      "impact": "string",
      "suggestion": "string",
      "fix_commands": ["string"]
    }
  ],

  "warning_findings": [],

  "anomaly_scores": [
    {
      "instance_id": "string",
      "metric": "string",
      "current_value": 0.0,
      "baseline_mean": 0.0,
      "baseline_std": 0.0,
      "z_score": 0.0,
      "level": "CRITICAL|WARNING|INFO|NORMAL",
      "method": "z-score|percentile|stl|prophet"
    }
  ],

  "trace": {
    "commands_executed": ["string"],
    "total_api_calls": 0,
    "cache_hits": 0,
    "cache_misses": 0
  }
}
```

---

## 4. 交付检查清单

每次巡检执行完成后，**必须**确认以下三项都存在：

| # | 交付物 | 路径 | 检查方式 |
|---|--------|------|---------|
| 1 | Markdown 报告 | `audit-results/reports/` | `test -s` 文件存在且 > 0 |
| 2 | 评分看板 | `audit-results/dashboards/` | `test -s` 且包含"整体健康度"关键字 |
| 3 | JSON 结构化报告 | `audit-results/json/` | `python3 -c "import json; json.load(open(path))"` 可解析 |

> 缺失任何一项 -> 标记为"交付不完整"，GCL 自动 FAIL。