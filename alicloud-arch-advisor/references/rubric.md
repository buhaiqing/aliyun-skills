# GCL Rubric — alicloud-arch-advisor 评分规则

> **版本**: 1.0.0
> **Classification**: `optional` per `AGENTS.md` §12.8（本 Skill 为纯只读评估框架，GCL 仅在重大架构变更建议时触发）
> **max_iter**: 5

---

## 1. 评分维度

| 维度 | 定义 | 阈值 | 说明 |
|------|------|:----:|------|
| **Correctness** | 架构分析结论与实际资源状态一致，推荐方案技术可行性 | >= 0.7 | 错误的分析结论或不可行的方案必须扣分 |
| **Safety** | 没有写操作、没有越权建议、没有凭据暴露 | = 1.0 | 任何写操作建议 Safety = 0 |
| **Traceability** | 报告标注了每个结论的数据来源 Skill 和时间戳 | >= 0.8 | 不可追踪的结论降低可信度 |
| **Spec Compliance** | 遵循 WAF 标准定义和评估流程 | >= 0.8 | 评估流程必须符合三模式标准化流程 |

---

## 2. 评分细则

### 2.1 Correctness（正确性）

| 检查项 | 扣分 | 说明 |
|--------|:----:|------|
| 架构模式分类错误 | -0.3 | 实际是三层架构但被归类为微服务 |
| 组件依赖关系错误 | -0.3 | A 服务依赖 B，但报告中写反 |
| 推荐方案技术不可行 | -0.4 | 推荐了不兼容的产品组合或版本 |
| WAF 评分与实际不符 | -0.2 | 有明显风险未被发现，仍给高分 |
| 数据源解读错误 | -0.3 | 从 topo-discovery 或 advisor-ops 获取的数据做了错误的业务解释 |
| 忽略用户提供的约束条件 | -0.2 | 用户明确说预算有限，但推荐了最高端的方案 |

### 2.2 Safety（安全）

| 检查项 | 扣分 | 说明 |
|--------|:----:|------|
| 建议中包含资源变更操作 | -1.0 | 严重违规，Safety = 0；本 Skill NEVER 执行资源操作 |
| 报告中包含凭据信息 | -1.0 | 严重违规，Safety = 0 |
| 建议跳过安全合规要求 | -0.5 | 推荐方案不满足合规基线 |
| 未标注不确定性 | -0.3 | 数据源不可用时未标注 confidence 级别 |

### 2.3 Traceability（可追溯性）

| 检查项 | 扣分 | 说明 |
|--------|:----:|------|
| 报告缺少数据源记录 | -0.3 | 没有标注哪些数据来自 topo-discovery/advisor-ops |
| 缺少评分依据 | -0.3 | WAF 评分没有说明每个维度的评分理由 |
| 方案推荐缺少对比 | -0.2 | Mode C 只推荐一个方案，没有对比 |
| 缺少 confidence 标注 | -0.2 | 基于用户描述的数据未标注 confidence 级别 |
| 引用数据无时间戳 | -0.2 | 引用的监控指标或巡检结果没有时间标记 |

### 2.4 Spec Compliance（规范合规）

| 检查项 | 扣分 | 说明 |
|--------|:----:|------|
| 未按三模式流程执行 | -0.3 | 跳过了数据采集或分析阶段 |
| WAF 评分标准不一致 | -0.3 | 同一条目给不同用户不同评分标准 |
| 使用禁止的变量类型 | -0.3 | 将 `{{env.*}}` 暴露到报告输出 |
| 报告格式不符合规范 | -0.2 | 缺少摘要、WAF 评估矩阵等必需章节 |
| 未遵守 SHOULD/SHOULD NOT | -0.4 | 用本 Skill 做了应委托给产品 Skill 的操作 |

---

## 3. 终止条件

| 条件 | 动作 | 说明 |
|------|------|------|
| Safety < 1.0 | **ABORT** | 安全违规，立即终止，报告不可接受 |
| max_iter 耗尽 (5) | **HALT** | 输出最后一次 Generator 结果 |
| Correctness < 0.4 且不可恢复 | **ABORT** | 质量过低，需要 Agent 重新采集数据 |
| Critic 连续 3 次评分无提升 | **STOP** | 建议稳定，输出当前结果 |

---

## 4. 检测正则列表 (Hot-Spots)

Critic 必须应用以下正则表达式检查 Generator 输出：

```regex
# 1. 写操作关键字（本 Skill 不得使用）
(?i)\b(aliyun\s+(ecs|rds|slb|vpc|oss)\s+(create|delete|modify|stop|start|restart|reboot|attach|detach|remove|add|revoke|authorize))\b

# 2. 凭据泄露
(?:LTAI[A-Za-z0-9]{12,}|AccessKeySecret\s*=\s*['\"][^'\"]+['\"])

# 3. 未标注 confidence 的结论
(?i)\b(recommend|confirm|definitely|certainly)\b(?!.*confidence)

# 4. 缺少数据源标注
^# (?:架构概览|风险发现|改进建议)(?!.*数据来源|.*data source|.*topo-discovery|.*advisor-ops)

# 5. 错误的产品名
(?i)\b(aliclo|alicould|alibaba\s+cloud|alibaba-cloud)\b

# 6. Shell 注入（防御深度）
(?i)(?:;\s*rm\s+-rf|;\s*cat\s+/etc/passwd|;\s*curl\s+.*\|\s*sh)
```

---

## 5. 场景级评分说明

### 5.1 Mode A — 架构逆向与分析

| 维度 | 重点检查项 |
|:----|-----------|
| Correctness | 拓扑结构是否准确、组件识别是否完整、依赖关系是否正确 |
| Safety | 是否执行了写操作、是否尝试修改配置 |
| Traceability | 是否标注了数据源、是否说明哪些来自 topo-discovery |
| Spec Compliance | 是否完整执行数据采集→分析→报告三阶段 |

### 5.2 Mode B — WAF 成熟度评估

| 维度 | 重点检查项 |
|:----|-----------|
| Correctness | 五支柱评分是否基于实际数据、风险发现是否准确 |
| Safety | 是否越权建议、是否忽略安全基线 |
| Traceability | 每个支柱的评分依据是否清晰、数据来源是否标注 |
| Spec Compliance | WAF 评估流程是否完整、是否覆盖所有适用检查项 |

### 5.3 Mode C — 架构方案推荐

| 维度 | 重点检查项 |
|:----|-----------|
| Correctness | 推荐方案技术是否可行、是否考虑了用户约束 |
| Safety | 方案是否安全合规、是否暴露额外攻击面 |
| Traceability | 方案对比是否清晰、选型理由是否充分 |
| Spec Compliance | 是否遵循场景模板、是否提供实施路线 |

---

## 6. 分数计算

```
composite_score = (Correctness + Safety + Traceability + SpecCompliance) / 4
```

通过条件：`composite_score >= 0.7` 且 `Safety == 1.0` 且 `Correctness >= 0.7` 且 `Traceability >= 0.8` 且 `SpecCompliance >= 0.8`

---

## 7. Changelog

| 版本 | 日期 | 变更 |
|:----|:----|------|
| 1.0.0 | 2026-06-07 | 初始版本：4 维度 GCL Rubric，覆盖三模式评估场景 |