# AIOps Best Practices — Alibaba Cloud Skill Generator

> **Purpose:** 定义所有具备监控/告警/诊断能力的 `alicloud-[product]-ops` Skill 必须遵循的 AIOps 最佳实践规范。本规范为 meta-skill 级别，不依赖任何具体产品 skill，仅定义模式、模板和合规标准，指导后续日常巡检分析、异常诊断、跨 Skill 协同和故障根因定位。
> **Version:** 1.0.0
> **Last Updated:** 2026-05-14
> **Status:** MANDATORY — 所有涉及监控告警和诊断的 Skill 必须实现本规范中的相关模式

---

## 目录

1. [核心原则](#1-核心原则)
2. [多指标关联巡检规范](#2-多指标关联巡检规范)
3. [告警驱动的跨 Skill 诊断规范](#3-告警驱动的跨-skill-诊断规范)
4. [跨 Skill 委托矩阵规范](#4-跨-skill-委托矩阵规范)
5. [主动巡检工作流规范](#5-主动巡检工作流规范)
6. [告警风暴处理规范](#6-告警风暴处理规范)
7. [故障模式知识库规范](#7-故障模式知识库规范)
8. [可观测性三位一体规范](#8-可观测性三位一体规范)
9. [诊断报告统一 Schema](#9-诊断报告统一-schema)
10. [提示词工程规范](#10-提示词工程规范)
11. [多轮自我复盘与批判性反思规范](#11-多轮自我复盘与批判性反思规范)
12. [合规性检查清单](#12-合规性检查清单)

---

## 1. 核心原则

### 1.1 AIOps 能力成熟度模型

| 等级 | 名称 | 特征 | 目标 Skill |
|------|------|------|-----------|
| L1 | 基础监控 | 单指标查询、静态阈值告警 | 所有 Ops Skill |
| L2 | 关联分析 | 多指标联合巡检、复合异常模式 | 具备 monitoring.md 的 Skill |
| L3 | 智能诊断 | 跨 Skill 委托、AI 诊断联动、决策树 | 监控类 Skill + 产品 Skill 协同 |
| L4 | 主动预防 | 主动巡检、趋势预测、知识库匹配 | 核心 P0 产品 Skill |
| L5 | 自治修复 | 自动修复、自学习、闭环优化 | 未来目标 |

### 1.2 AIOps 五步闭环

每个具备诊断能力的 Skill 必须遵循以下闭环：

```
[发现异常] → [验证确认] → [关联分析] → [根因定位] → [修复建议]
     ↑                                                      |
     └──────────────── 反馈优化 ─────────────────────────────┘
```

### 1.3 跨 Skill 协同原则

1. **单一职责**：每个 Skill 负责自己产品的诊断，不越界
2. **委托清晰**：通过委托矩阵明确定义跨 Skill 调用关系
3. **结果标准化**：所有 Skill 输出的诊断结果统一 Schema
4. **知识共享**：故障模式跨 Skill 可见，形成统一知识库
5. **失败容错**：委托的 Skill 不可用时，有明确的降级路径

---

## 2. 多指标关联巡检规范

### 2.1 必须支持的异常模式

任何具备监控能力的 Skill 必须在其 `monitoring.md` 或 `SKILL.md` 中定义至少以下异常模式：

| 模式类别 | 最少模式数 | 示例 |
|----------|-----------|------|
| 资源压力型 | ≥ 2 | CPU-Memory 双高、磁盘-IO 瓶颈 |
| 趋势异常型 | ≥ 1 | 内存泄漏趋势、指标单调上升 |
| 突变型 | ≥ 1 | CPU 突增、流量突降 |
| 关联异常型 | ≥ 1 | Load-CPU 不匹配、连接-CPU 背离 |

### 2.2 异常模式定义规范

每个异常模式必须包含以下字段：

```markdown
| Pattern | Metrics Involved | Detection Logic | Severity | Interpretation |
|---------|-----------------|-----------------|----------|----------------|
| [模式名] | [涉及指标列表] | [判定逻辑表达式] | Critical/Warning | [业务含义] |
```

### 2.3 实现要求

- **CLI 路径**：提供多指标批量查询脚本
- **SDK 路径**：提供 Go SDK 异常模式检测函数
- **输出**：返回匹配的异常模式列表及严重级别
- **委托**：Critical 级别自动触发跨 Skill 诊断

### 2.4 实现模板

生成的多指标巡检操作流（`SKILL.md` 中）必须包含以下结构：

```markdown
### Operation: Multi-Metric Anomaly Inspection

对指定资源执行多指标联合巡检，识别复合异常模式。

#### Supported Anomaly Patterns

| Pattern | Metrics Involved | Detection Logic | Severity |
|---------|-----------------|-----------------|----------|
| [根据产品定义至少 4 种模式] ||||

#### Pre-flight Checks
（资源存在性、指标可用性、时间范围、配额检查）

#### Execution — CLI (Multi-Call Sequence)
（提供批量采集脚本，按 namespace 区分指标集）

#### Execution — JIT Go SDK (Advanced Correlation)
（提供 detectAnomalyPattern 函数实现）

#### Recovery & Cross-Skill Delegation
（每种模式对应的委托 Skill 和 DAS 建议）
```

---

## 3. 告警驱动的跨 Skill 诊断规范

### 3.1 五步诊断决策树

每个具备诊断能力的 Skill 必须实现以下决策树：

```
[告警触发]
    │
    ├── Step 1: 验证告警有效性
    │   确认当前指标值是否确实超过阈值
    │   若为误报 → 检查告警规则配置
    │
    ├── Step 2: 检查资源状态
    │   委托对应产品 Skill 获取资源当前状态
    │
    ├── Step 3: 多指标关联分析
    │   查询相关指标，识别复合异常模式
    │
    ├── Step 4: 深度 AI 诊断（如适用）
    │   委托 DAS 或对应 AI 诊断 Skill
    │
    └── Step 5: 生成统一诊断报告
        汇总所有 Skill 发现，给出根因和修复建议
```

### 3.2 命名空间到 Skill 的路由表（模板）

每个诊断类 Skill 必须定义类似以下的路由规则。`alicloud-[product]-ops` 为生成的 Skill 占位符，实际生成时根据产品替换：

| 告警命名空间（模板） | 主诊断 Skill（模板） | 委托说明（模板） |
|---------------------|---------------------|-----------------|
| `acs_<compute>_dashboard` | `alicloud-<compute>-ops` | 可委托网络诊断 Skill 检查网络层 |
| `acs_<database>_dashboard` | `alicloud-<database>-ops` | 必须委托 AI 诊断 Skill 做深度诊断 |
| `acs_<lb>_dashboard` | `alicloud-<lb>-ops` | 可委托计算 Skill 检查后端健康 |
| `acs_<cache>_dashboard` | `alicloud-<cache>-ops` | 可选委托缓存分析能力 |
| `acs_<container>_dashboard` | `alicloud-<container>-ops` | 可委托计算 Skill 检查节点状态 |

> **生成规则：** 根据产品实际的 CMS namespace（如 `acs_ecs_dashboard`）和对应的 product skill 名称（如 `alicloud-ecs-ops`）填充上表。委托关系遵循"产品 A → 依赖产品 B 的 Skill"原则。

### 3.3 DAS 委托触发条件

| 触发条件 | 必须调用的 DAS 操作 |
|----------|-------------------|
| 数据库告警（RDS/PolarDB） | `GetInstanceInspections` + `CreateDiagnosticReport` |
| 连接相关告警 | `CreateLatestDeadLockAnalysis` + `GetQueryOptimizeData` |
| 性能下降 | `CreateDiagnosticReport` + `GetPfsSqlSamples` |
| 缓存/Redis 告警 | `CreateCacheAnalysisJob` |
| 疑似自治事件 | `GetAutonomousNotifyEventsInRange` |

---

## 4. 跨 Skill 委托矩阵规范

### 4.1 委托矩阵格式

每个具备跨 Skill 协同能力的 Skill 必须在 `integration.md` 中定义委托矩阵：

```markdown
| 告警类型 | 指标 | 主诊断 Skill | 次诊断 Skill | DAS 委托 |
|----------|------|-------------|-------------|----------|
| [告警名] | [指标] | [Skill] | [Skill 或 —] | Recommended/Optional |
```

### 4.2 委托协议

```
[告警触发]
    │
    ├── 1. 识别命名空间 + 指标
    ├── 2. 查矩阵确定主诊断 Skill
    ├── 3. 调用主 Skill 检查资源状态
    ├── 4. 若资源异常 → 调用次 Skill（如有定义）
    ├── 5. 若 DAS = "Recommended" → 始终调用 DAS
    ├── 6. 若 DAS = "Optional" 且严重级别 = Critical → 调用 DAS
    └── 7. 汇总所有输出生成统一报告
```

### 4.3 诊断结果关联

1. **时间关联**：检查异常是否在同一时间窗口（±5 分钟）
2. **资源关联**：检查资源间是否存在依赖关系
3. **指标关联**：检查同一资源的多个指标是否同步异常
4. **因果分析**：若资源 A 在 T1 故障，B 在 T2>T1 故障，调查 A 是否导致 B

---

## 5. 主动巡检工作流规范

### 5.1 五步巡检闭环

```
[Discovery] → [Metric Collection] → [Anomaly Detection] → [Cross-Skill Diagnosis] → [Report Generation]
```

### 5.2 各阶段要求

| 阶段 | 要求 | 产出 |
|------|------|------|
| Discovery | 列出监控组内所有资源 | 资源清单 |
| Metric Collection | 批量采集关键指标（建议 Period=300s 降低 API 调用） | 指标数据 |
| Anomaly Detection | 静态阈值 + 趋势斜率 + 同比环比 | 异常资源列表 |
| Cross-Skill Diagnosis | 对异常资源委托对应 Skill | 诊断发现 |
| Report Generation | 生成巡检报告 | 巡检报告 |

### 5.3 趋势检测算法

必须实现的检测算法：

1. **斜率计算**：线性回归斜率检测趋势方向
2. **加速检测**：比较前后半段斜率，判断是否加速恶化
3. **突变检测**：相邻数据点差值超过阈值

```go
func calculateSlope(points []DataPoint) float64 {
    n := float64(len(points))
    if n < 2 { return 0 }
    var sumX, sumY, sumXY, sumX2 float64
    for i, p := range points {
        x := float64(i); y := p.Average
        sumX += x; sumY += y; sumXY += x*y; sumX2 += x*x
    }
    return (n*sumXY - sumX*sumY) / (n*sumX2 - sumX*sumX)
}
```

---

## 6. 告警风暴处理规范

### 6.1 风暴检测标准

| 标准 | 阈值 | 动作 |
|------|------|------|
| 告警频率 | > 10 条/5 分钟 | 进入风暴模式 |
| 同资源告警 | > 3 条同一实例 | 聚合为单一事件 |
| 同命名空间 | > 50% 来自同一 namespace | 聚焦该产品诊断 |
| 级联模式 | 告警 A 触发后 2 分钟内告警 B 触发 | 标记 B 为 "可能由 A 导致" |

### 6.2 风暴处理流程

1. **检测**：监控 `DescribeMetricAlarmList` with State=ALARM
2. **聚合**：按 resource_id、namespace、时间窗口分组
3. **抑制**：聚合后仅保留主告警通知
4. **根资源识别**：找到时间最早的告警
5. **聚焦诊断**：委托根资源对应 Skill 深度诊断

---

## 7. 故障模式知识库规范

### 7.1 知识库结构

每个产品 Skill 应在 `references/knowledge-base.md` 中维护故障模式库：

```markdown
### Pattern: [产品]-[序号] — [故障名称]

| 属性 | 内容 |
|------|------|
| 触发指标 | [指标名] |
| 触发阈值 | [阈值] |
| 典型特征 | [描述] |
| 关联指标 | [相关指标及预期行为] |
| 根因 | [1. 原因A 2. 原因B ...] |
| 诊断步骤 | [1. 步骤A 2. 步骤B ...] |
| 修复方案 | [1. 临时方案 2. 长期方案] |
| 预防措施 | [1. 措施A 2. 措施B ...] |
```

### 7.2 知识库应用流程

1. **告警触发时**：根据 namespace + metric 查找对应 Pattern
2. **多指标关联时**：检查是否符合 Pattern 中的关联指标特征
3. **诊断时**：按 Pattern 的诊断步骤执行
4. **修复时**：优先执行临时措施，再实施长期方案
5. **复盘时**：对比实际故障与 Pattern，更新或新增

### 7.3 级联故障模式

知识库必须包含跨产品级联故障模式（如 ECS 过载→SLB 丢连接→RDS 连接堆积）

### 7.4 知识库维护

| 动作 | 触发条件 | 频率 |
|------|----------|------|
| 新增 Pattern | 发现新的重复故障模式 | 按需 |
| 更新 Pattern | 根因或修复方案变化 | 按需 |
| 验证 Pattern | 实际故障与 Pattern 匹配度检查 | 每季度 |

---

## 8. 可观测性三位一体规范

### 8.1 三层架构

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Metrics   │────▶│  Logs    │────▶│ Traces   │
│ (CMS)     │     │ (SLS)    │     │ (ARMS)   │
└──────────┘     └──────────┘     └──────────┘
      │                │                │
      └────────────────┼────────────────┘
                       ▼
              ┌────────────────┐
              │ Unified Report │
              └────────────────┘
```

### 8.2 Metrics → Logs 联动规则

| CMS 指标异常 | SLS 查询目标 | 目的 |
|-------------|-------------|------|
| CPUUtilization 突增 | 应用错误日志 | 确认错误爆发导致 CPU 飙升 |
| MemoryUsage 泄漏 | 应用内存日志 | 确认内存分配模式 |
| ConnectionUsage 高 | 数据库访问日志 | 确认连接泄漏来源 |
| DropConnection (SLB) | Nginx/Access 日志 | 确认被丢弃的请求详情 |

### 8.3 Metrics → Traces 联动规则

| CMS 指标异常 | ARMS Trace 目标 | 目的 |
|-------------|----------------|------|
| CPUUtilization 突增 | 应用 Trace | 定位热点方法 |
| 延迟增加 | RPC/HTTP Trace | 定位瓶颈服务 |
| 错误率增加 | Error Trace | 定位错误根因服务 |
| ConnectionUsage 高 | 数据库 Trace | 定位慢 SQL 和连接持有时间 |

### 8.4 降级策略

若 SLS/ARMS Skill 不可用：
1. 直接使用 `aliyun log` CLI
2. 直接使用 ARMS OpenAPI SDK
3. 提供控制台链接供人工排查

---

## 9. 诊断报告统一 Schema

### 9.1 报告字段规范

所有诊断报告必须包含以下字段：

| 字段 | 来源 | 说明 |
|------|------|------|
| `report_id` | 生成 | UUID v4 追踪标识 |
| `timestamp` | CMS | 告警触发时间 |
| `alarm_source` | CMS | 原始告警规则名 |
| `resource_id` | CMS | 实例 ID |
| `resource_status` | 产品 Skill | 当前资源状态 |
| `metric_value` | CMS | 告警时指标值 |
| `metric_trend` | CMS | 1h 趋势分析 |
| `anomaly_patterns` | 多指标巡检 | 检测到的异常模式列表 |
| `deep_diagnosis` | DAS | AI 诊断评分和发现 |
| `correlated_alarms` | CMS | 同一资源其他告警 |
| `correlated_events` | DAS | 自治事件 |
| `root_cause` | 综合 | 主要根因 |
| `recommendation` | 综合 | 可执行的修复建议 |
| `delegated_skills` | Agent | 已调用的 Skill 列表 |

### 9.2 报告输出格式

```markdown
## 诊断摘要
（一句话概括）

## 详细发现
（分点列出各 Skill 的发现）

## 根因判断
（明确根因，附置信度）

## 修复建议
（按优先级排列的可执行操作）

## 风险评估
（不修复的后果评估）
```

---

## 10. 提示词工程规范

### 10.1 提示词分类

每个具备 AIOps 能力的 Skill 必须提供以下类别的提示词：

| 类别 | 最少数量 | 说明 |
|------|---------|------|
| 指标查询类 | ≥ 3 | 单指标查询、趋势查询、多指标批量查询 |
| 告警管理类 | ≥ 3 | 创建、查询、检查、删除告警规则 |
| 多指标关联巡检类 | ≥ 2 | 执行巡检、分析关联性 |
| 告警驱动诊断类 | ≥ 3 | 根因诊断、跨 Skill 编排、级联故障 |
| 主动巡检类 | ≥ 2 | 定时巡检、报告生成 |
| 告警风暴处理类 | ≥ 2 | 风暴检测、聚合分析 |
| 知识库应用类 | ≥ 2 | 匹配故障模式、更新知识库 |
| 可观测性联动类 | ≥ 2 | Metrics→Logs、Metrics→Traces |
| 报告生成类 | ≥ 3 | 诊断报告、巡检报告、复盘报告 |

### 10.2 提示词设计原则

1. **变量占位符**：使用 `{{user.xxx}}` 和 `{{env.xxx}}` 标准占位符
2. **步骤清晰**：使用编号列表描述多步骤流程
3. **条件分支**：说明不同情况下的处理路径
4. **输出约束**：明确要求的输出格式

### 10.3 提示词存放位置

所有提示词统一存放在 `references/prompt-examples.md` 中。

---

## 11. 多轮自我复盘与批判性反思规范

### 11.1 适用场景

当执行故障根因定位（troubleshooting）时，Agent 必须执行多轮自我复盘：

- 第一轮诊断结果不满意（根因不明确、置信度低）
- 诊断路径与知识库 Pattern 不匹配
- 跨 Skill 委托返回矛盾结果
- 修复建议无法执行或风险过高

### 11.2 三轮复盘流程

```
[第一轮：初步诊断]
    │
    ├── 收集所有 Skill 输出
    ├── 按决策树执行标准诊断流程
    ├── 输出初步根因假设
    │
    ├── 不满意？→ [第二轮：批判性反思]
    │   ├── 质疑第一轮假设
    │   ├── 检查是否有遗漏的关联指标
    │   ├── 检查是否有遗漏的依赖资源
    │   ├── 对比知识库中相似但不同的 Pattern
    │   ├── 重新审视时间线（是否因果倒置）
    │   └── 输出修正后的根因假设
    │
    └── 仍不满意？→ [第三轮：深度审视]
        ├── 执行 Metrics→Logs→Traces 三位一体查询
        ├── 扩大时间窗口重新分析
        ├── 检查变更记录（配置变更、发布、扩缩容）
        ├── 输出最终根因判断及置信度
        └── 如仍不确定 → 明确标注不确定性并给出排查建议
```

### 11.3 每轮反思的批判性问题

Agent 在每轮反思时必须回答以下问题：

| # | 问题 | 目的 |
|---|------|------|
| 1 | 当前根因假设的证据链是否完整？有无薄弱环节？ | 检验逻辑严密性 |
| 2 | 是否有替代假设能更好地解释所有观察到的异常？ | 避免确认偏误 |
| 3 | 是否遗漏了可查询的关联指标或资源？ | 弥补信息缺口 |
| 4 | 时间序列上的因果关系是否正确？有无因果倒置？ | 验证时间逻辑 |
| 5 | 知识库中是否有相似但诊断路径不同的 Pattern？ | 借鉴历史经验 |
| 6 | 修复建议是否可执行？是否存在风险？ | 确保可操作性 |
| 7 | 本次诊断是否有值得沉淀为新 Pattern 的发现？ | 知识积累 |

### 11.4 复盘输出格式

```markdown
## 诊断复盘记录

### 第一轮诊断
- 根因假设：[假设描述]
- 置信度：[百分比]
- 不满意原因：[具体原因]

### 第二轮批判性反思
- 质疑点：[对第一轮的质疑]
- 新发现：[补充查询的发现]
- 修正假设：[修正后的根因]
- 置信度：[百分比]

### 第三轮深度审视（如需要）
- 新增查询：[三位一体查询结果]
- 最终判断：[最终根因]
- 置信度：[百分比]
- 不确定性说明：[如有]

### 知识库更新建议
- [是否新增/更新 Pattern]
```

---

## 12. 合规性检查清单

### 12.1 P0 — 必须通过（AIOps 能力）

任何涉及监控、告警、诊断的 Skill 必须满足：

- [ ] **多指标关联巡检**：定义 ≥ 4 种异常模式，含 CLI 和 SDK 实现
- [ ] **跨 Skill 诊断决策树**：至少包含 Verify → Check → Correlate → Diagnose → Report 五步
- [ ] **跨 Skill 委托矩阵**：在 `integration.md` 中定义完整的告警到 Skill 映射
- [ ] **主动巡检工作流**：定义 Discovery → Collection → Detection → Diagnosis → Report 闭环
- [ ] **告警风暴处理**：定义检测标准和聚合抑制策略
- [ ] **诊断报告 Schema**：遵循统一报告格式
- [ ] **DAS 联动**（数据库相关 Skill）：定义 DAS 委托触发条件和调用操作

### 12.2 P1 — 应该通过（知识沉淀）

- [ ] **故障模式知识库**：`references/knowledge-base.md` 包含 ≥ 5 个产品故障 Pattern
- [ ] **级联故障模式**：包含 ≥ 2 个跨产品级联故障 Pattern
- [ ] **可观测性联动**：`references/observability.md` 定义 Metrics→Logs→Traces 联动规则
- [ ] **提示词手册**：`references/prompt-examples.md` 包含 ≥ 20 个分类提示词
- [ ] **多轮复盘流程**：在 `troubleshooting.md` 或 `SKILL.md` 中定义复盘规范

### 12.3 P2 — 建议通过（持续优化）

- [ ] **诊断知识库维护流程**：定义新增/更新/验证 Pattern 的流程
- [ ] **趋势检测算法**：实现斜率、加速、突变检测
- [ ] **诊断置信度评分**：为每个根因判断提供置信度
- [ ] **诊断效果度量**：跟踪 MTTD/MTTL/MTTR 指标

---

*本规范为强制性规范。所有新生成或重大更新的涉及监控告警诊断的 Skill 必须通过 AIOps 合规性检查。生成时 Agent 应根据本规范的模式和模板，而非引用任何具体产品 Skill 的实现。*