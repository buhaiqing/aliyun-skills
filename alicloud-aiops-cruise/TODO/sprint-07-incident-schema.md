# Sprint 7: Incident Schema 定义（P1）

> **状态**: PASS 1/1
> **业务价值**：将分散的巡检发现（critical_findings、warning_findings）统一为标准化的 Incident 数据结构，为 Sprint 9 (Incident 落地/可检索) 奠定数据基础。所有 runbook 输出一致，下游消费方（自动化工单、Post-Mortem 复盘、Sprint 11 ML 升级）有可依赖的契约
> **交付物**：`references/incident-schema.md`（JSON Schema 规范 + 字段语义 + 集成到 4 个 runbook 输出）
> **前置条件**：无（独立推进）
> **关联验收项**：S1-D5

---

## 一、Schema 设计原则

| 原则 | 说明 |
|------|------|
| **稳定性** | 字段集变化必须有版本号（v1.0.0 -> v1.1.0 不可破坏向后兼容） |
| **可追溯** | 每个 Incident 必须能从 `trace.commands_executed` 还原产生过程 |
| **可检索** | 必填字段覆盖 (customer, resource_type, level, rule_id, timestamp) 四维度，便于 O(1) 索引 |
| **可关联** | 必填字段 `dedup_key` 决定同源 Incident 是否合并 |
| **可消费** | 字段命名 snake_case，类型严格化（不接受 string 表达数字） |

---

## 二、任务清单

- [ ] **7.1** 设计 Incident 字段集：
  - [ ] 必填字段（id, customer, timestamp, scenario, level, resource_type, resource_id, rule_id, title, impact, suggestion, dedup_key）
  - [ ] 选填字段（metric, current_value, threshold, baseline_mean, baseline_std, z_score, fix_commands, ttl_hours, assignee, status）
  - [ ] 关联字段（run_id, parent_incident_id, related_incidents[], trace）
- [ ] **7.2** 定义 `level` 枚举：`CRITICAL | WARNING | INFO`（三档，与现有 delivery-standards.md 对齐）
- [ ] **7.3** 定义 `dedup_key` 生成规则：`{customer}:{resource_type}:{resource_id}:{rule_id}:{date_bucket}`（date_bucket=YYYY-MM-DD）
- [ ] **7.4** 定义 `rule_id` 命名规范：`<PRODUCT>-<NUMBER>`（如 `SLB-ECS-01`、`RDS-04`、`ACK-LIMITS-02`）
- [ ] **7.5** 提供完整 JSON Schema 草案（含 `$schema`, `required`, `properties`, `additionalProperties: false`）
- [ ] **7.6** 提供 1 个 filled 示例（覆盖 3 种 level）
- [ ] **7.7** 在 SKILL.md "Safety Gates" 章节添加 Incident 标准化引用
- [ ] **7.8** 在 `references/delivery-standards.md` JSON 报告结构中追加 `incidents` 字段（独立于 critical/warning 列表）
- [ ] **7.9** 跑一次 daily-health-check，验证新 schema 字段可被脚本输出（或写明"待 Sprint 9 集成"）
- [ ] **7.10** TODO.md / stage-status.json 同步（MR-1 强制）

---

## 三、质量门

| 编号 | 检查项 | 验证命令 | 阈值 |
|------|--------|----------|------|
| Q7.1 | JSON Schema 语法有效 | `python3 -c "import json; from jsonschema import validate; validate({}, json.load(open('references/incident-schema.json')))"` | 无错（json 语法通过即可，jsonschema 包可能缺） |
| Q7.2 | 必填字段完整性 | `grep -c '^\s*"[a-z_]*":\s*\{\s*"type"' references/incident-schema.md` | ≥ 12 |
| Q7.3 | level 枚举三档齐全 | `grep -E 'CRITICAL\|WARNING\|INFO' references/incident-schema.md` | 命中 |
| Q7.4 | dedup_key 规则有文档 | `grep -c 'dedup_key' references/incident-schema.md` | ≥ 3 |
| Q7.5 | 至少 1 个 filled 示例 | `grep -c '"rule_id"' references/incident-schema.md` | ≥ 3（每 level 1 个） |
| Q7.6 | delivery-standards.md 已引用 | `grep -c 'incidents' references/delivery-standards.md` | ≥ 1（新增字段） |
| Q7.7 | SKILL.md 已引用 | `grep -c 'incident-schema' SKILL.md` | ≥ 1 |
| Q7.8 | Ruff Lint（仅当新增 .py） | `ruff check references/*.py 2>/dev/null` | 0 错误 |
| Q7.9 | Markdown Lint | `npx markdownlint-cli2 "references/incident-schema.md"` | 0 错误 |
| Q7.10 | TODO.md 同步 | `grep -c 'Sprint 7.*7/' TODO.md` | ≥ 1 |

---

## 四、与现有文档的关系

| 现有文件 | 关系 |
|----------|------|
| `references/delivery-standards.md` | 在 JSON 报告结构中追加 `incidents` 数组字段，使用本 schema |
| `references/inference-rules.md` | 每个规则的 `rule_id` 即本 schema 中的 `rule_id`（如 `RDS-04`） |
| `references/rubric.md` | 新增 Traceability 维度子项：Incident 是否符合 schema |
| `SKILL.md` Safety Gates | 引用 schema 链接，约定"所有 finding 必须符合 incident-schema" |
| Sprint 9 (Incident 落地) | 依赖本 schema 作为持久化契约 |
| Sprint 11 (ML 升级) | 依赖本 schema 训练/推理 |

---

## 五、Sprint 完成判据

- 所有 10 个任务项 `[x]`
- 所有 10 个 Q 检查项 PASS
- TODO.md / stage-status.json 同步更新
- Post-Update Self-Review R1 + R2 全部 PASS
