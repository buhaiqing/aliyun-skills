---
template_id: "deep-report"
phase: "Phase 2+3: 深度巡检 + 推理报告"
---

# 🔍 全链路深度巡检报告

**报告ID:** `{{report_id}}`
**区域:** {{regions}} | **时间:** {{timestamp}} | **窗口:** {{metric_window}}
**扫描资源:** {{resource_count}}个 | **场景:** {{scenario}}

---

## 📊 总体评分

| 维度 | 评分 | 判定 | 说明 |
|---|---|---|---|
| **整体健康度** | {{overall_score}}/1.0 | {{overall_severity}} | {{overall_summary}} |
| **安全水位** | {{safety_score}}/1.0 | {{safety_severity}} | {{safety_summary}} |
| **容量水位** | {{capacity_score}}/1.0 | {{capacity_severity}} | {{capacity_summary}} |

---

## 🔴 Critical 问题（{{critical_count}} 项）— 需立即处理

{% for issue in critical_issues %}
### #{{loop.index}} {{issue.title}}

```
┌─ 诊断链 ─────────────────────────────────────────────────
│ Phase1 拓扑发现 → 扫描到 {{issue.scope}} 个资源
│ Phase2 数据采集 → {{issue.collected_metric}} = {{issue.value}}
│ Phase3 阈值判定 → {{issue.value}} > {{issue.threshold}} → 🔴 CRITICAL
│ 规则匹配: {{issue.rule_id}}
│ 根因分析: {{issue.root_cause}}
└───────────────────────────────────────────────────────────

┌─ 实例信息 ───────────────────────────────────────────────
│ ID:   {{issue.instance_id}}
│ 名称: {{issue.instance_name}}
│ 规格: {{issue.instance_spec}}
└───────────────────────────────────────────────────────────

┌─ 修复步骤 ───────────────────────────────────────────────
{% for step in issue.repair_steps %}
│ Step {{loop.index}}: {{step.title}}
│   {{step.command if step.command else step.description}}
{% endfor %}
└───────────────────────────────────────────────────────────
```

{% endfor %}

---

## 🟡 Warning 问题（{{warning_count}} 项）— 计划处理

{% for issue in warning_issues %}
### #{{loop.index}} {{issue.title}}

```
┌─ 诊断链 ─────────────────────────────────────────────────
│ 实例:  {{issue.instance_id}} ({{issue.instance_name}})
│ 指标:  {{issue.metric}} = {{issue.value}}（阈值: {{issue.threshold}}）
│ 级别:  🟡 WARNING → 需计划处理
└───────────────────────────────────────────────────────────

┌─ 建议操作 ───────────────────────────────────────────────
│ {{issue.suggestion}}
└───────────────────────────────────────────────────────────
```
{% endfor %}

---

## ✅ 正常资源摘要

| 类型 | 总量 | 正常 | 异常 |
|---|---|---|---|
{% for summary in resource_summary %}
| {{summary.type}} | {{summary.total}} | ✅ {{summary.healthy}} | {{summary.unhealthy}} |
{% endfor %}

---

## 🔗 链路关联推理

{% for inference in chain_inferences %}
### {{inference.icon}} {{inference.pattern}}

| 属性 | 内容 |
|---|---|
| **规则** | `{{inference.rule_id}}` |
| **现象组合** | {{inference.symptoms \| join("; ")}} |
| **推理结论** | {{inference.reasoning}} |
| **修复指引** | 见 `references/inference-rules.md#{{inference.rule_id.lower()}}` 的修复步骤 |
{% endfor %}

---

## 📌 按优先级排序的优化建议

{% for rec in top_recommendations %}
{{loop.index}}. **{{"🔴" if rec.level == "critical" else "🟡" if rec.level == "warning" else "🔵"}} [{{rec.level|upper}}] {{rec.title}}**
   - 实例: `{{rec.instance_id}}`
   - 详情: {{rec.detail}}
   ↓ 修复路径:
{% for step in rec.repair_steps %}
     {{loop.index}}. {{step}}
{% endfor %}
{% endfor %}

---

## 审计追踪

| 字段 | 内容 |
|---|---|
| **报告ID** | `{{report_id}}` |
| **JSON** | `audit-results/{{report_id}}.json` |
| **执行耗时** | {{execution_duration}} |
| **Runbook** | v{{runbook_version}} |
| **模式** | {{execution_mode}} |
| **Go 零件** | {{"启用 (DAS)" if das_enabled else "未使用"}} |
| **CloudAssistant** | {{"启用" if cloud_assistant_enabled else "未使用"}} |