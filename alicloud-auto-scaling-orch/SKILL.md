---
name: alicloud-auto-scaling-orch
description: >-
  跨产品弹性伸缩编排引擎 — 基于 CMS 监控指标、定时规则、预测模型和业务事件，
  自动决策并编排 alicloud-ess-ops / alicloud-slb-ops / alicloud-cms-ops 等下游
  Skill 执行端到端扩缩容操作。支持 6 种经典场景：CPU 指标驱动、定时业务周期、
  预测性扩缩、复合多指标、大促弹性保障、闲置回收。Agent 通过委托下游 Skill
  完成具体资源操作，自身承担"决策 + 编排 + 验证"的编排层职责。
  NOT for 单次手动执行 ESS 操作（使用 alicloud-ess-ops），NOT for 只读巡检
  （使用 alicloud-aiops-cruise），NOT for 单个资源的手动变配。
license: MIT
compatibility: >-
  aliyun CLI (Go binary) + Python 3.10+ for orchestration scripts, valid API
  credentials, network access to Alibaba Cloud endpoints. Requires downstream
  skills (ess-ops, cms-ops, slb-ops, ecs-ops) to be available in the skill farm.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-07"
  type: orchestration-framework
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  api_profile: "Cross-product orchestration — ESS 2014-08-28 / CMS 2019-01-01 / SLB 2014-05-15"
  cli_applicability: script-run
  cli_support_evidence: >-
    本 Skill 为编排层，不直接调用 OpenAPI，而是委托下游产品 Skill
    (ess-ops/cms-ops/slb-ops/ecs-ops) 执行具体操作。编排脚本使用 Python 实现，
    调用 aliyun CLI 或直接调用 OpenAPI。
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
  gcl_classification: required
  gcl_max_iter: 2
  token_budget_estimate: "~4000 tokens (SKILL.md only)"
  references_index:
    - path: "references/orchestration-flows.md"
      load_condition: "当需要执行具体扩缩容编排操作时"
    - path: "references/decision-engine.md"
      load_condition: "当需要理解扩缩容决策逻辑或自定义策略时"
    - path: "references/integration.md"
      load_condition: "当需要与下游 Skill 集成或调试时"
    - path: "references/troubleshooting.md"
      load_condition: "当扩缩容执行失败需要排查时"
    - path: "references/well-architected-assessment.md"
      load_condition: "当需要架构评估时"
    - path: "references/rubric.md"
      load_condition: "当需要 GCL 评分规则时"
    - path: "references/prompt-templates.md"
      load_condition: "当需要 GCL 提示模板时"
---

# Alibaba Cloud Auto Scaling Orchestration — alicloud-auto-scaling-orch

> **一句话定位**：弹性伸缩的"大脑"——负责决策何时扩缩、扩缩多少、编排哪些下游 Skill 执行、以及验证结果是否正确。不做单个产品的 CRUD，那是下游 Skill 的事。

## 五大核心标准

| # | 标准 | 本 Skill 如何实现 |
|---|------|-----------------|
| 1 | **清晰边界** | SHOULD/SHOULD NOT Use 精确条件 + 委托规则表 + 6 种场景分类 |
| 2 | **结构化 I/O** | `{{env.*}}` / `{{user.*}}` / `{{output.*}}` 三级占位符 + 场景参数模板 |
| 3 | **明确可执行步骤** | 每个场景：感知→决策→编排→执行→验证，5 步标准流程 |
| 4 | **完整失败策略** | 按场景分类错误码 + 回滚策略 + 熔断机制 |
| 5 | **绝对单一职责** | 只做编排决策，不做产品 CRUD。委托 ess-ops/cms-ops/slb-ops/ecs-ops |

---

## Trigger & Scope

### SHOULD Use

- 需要基于 **CMS 监控指标**（CPU/内存/连接数/QPS）自动扩缩容 ECS/ECI
- 需要按 **业务时间段**（如 9:00→18:00）定时扩缩容
- 需要基于 **历史指标预测** 未来负载，提前扩容
- 需要**复合多条件**（CPU > 70% 且内存 > 80%）触发扩缩
- 需要**大促/活动前**批量调整多个伸缩组的期望容量
- 需要自动**回收闲置资源**（基于低负载持续时长）
- 用户描述"自动扩缩"、"弹性伸缩策略"、"容量规划"、"应对突发流量"、"闲置回收"

### SHOULD NOT Use

- 只操作单个伸缩组的创建/修改/删除 → 委托 `alicloud-ess-ops`
- 只需要查看当前伸缩组状态 → 委托 `alicloud-ess-ops` (DescribeScalingGroups)
- 只需要查看监控指标，不做决策 → 委托 `alicloud-cms-ops`
- 只需要巡检+诊断，不需执行扩缩 → 委托 `alicloud-aiops-cruise`
- 手动调整单个 ECS 规格（非伸缩组管理） → 委托 `alicloud-ecs-ops`
- 不涉及阿里云资源的容量管理 → 不使用

### Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 扩缩容操作为写操作，委托 GCL 循环对抗性评审 |
| 伸缩组 CRUD | `alicloud-ess-ops` | 创建/修改/删除伸缩组、伸缩配置、伸缩规则 |
| ESS 规则执行 | `alicloud-ess-ops` | ExecuteScalingRule、CreateAlarm、CreateScheduledTask |
| 监控指标采集 | `alicloud-cms-ops` | DescribeMetricList、DescribeMetricLast 获取实时/历史指标 |
| CMS 告警创建 | `alicloud-cms-ops` | 创建基于指标的告警规则 |
| SLB 关联配置 | `alicloud-slb-ops` / `alicloud-alb-ops` | 扩缩后自动注册/注销后端服务器 |
| ECS 实例操作 | `alicloud-ecs-ops` | 非伸缩组管理的实例操作（如临时加机） |
| 拓扑与资源发现 | `alicloud-topo-discovery` | 发现自动扩缩的候选资源 |
| 成本分析 | `alicloud-billing-ops` | 扩缩容前后的成本对比分析 |

---

## Variable Convention

| 变量 | 类别 | 说明 |
|------|------|------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | 环境 (NEVER ask) | AK ID |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | 环境 (NEVER ask) | AK Secret |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | 环境 (NEVER ask) | 默认地域 |
| `{{user.scenario}}` | 用户选择 | 6 种场景之一: metric/scheduled/predictive/composite/event/cleanup |
| `{{user.scaling_group_id}}` | 用户输入 | 目标伸缩组 ID（可从 ess-ops DescribeScalingGroups 获取） |
| `{{user.policy_name}}` | 用户输入 | 策略名称，用于标识和追踪 |
| `{{user.cpu_threshold_high}}` | 用户输入 | CPU 扩容阈值（默认 70） |
| `{{user.cpu_threshold_low}}` | 用户输入 | CPU 缩容阈值（默认 30） |
| `{{user.mem_threshold_high}}` | 用户输入 | 内存扩容阈值（默认 80） |
| `{{user.mem_threshold_low}}` | 用户输入 | 内存缩容阈值（默认 40） |
| `{{user.scale_out_qty}}` | 用户输入 | 扩容台数（默认 1） |
| `{{user.scale_in_qty}}` | 用户输入 | 缩容台数（默认 1） |
| `{{user.max_capacity}}` | 用户输入 | 最大伸缩上限（默认 10） |
| `{{user.min_capacity}}` | 用户输入 | 最小伸缩下限（默认 1） |
| `{{user.schedule_cron}}` | 用户输入 | 定时 Cron 表达式 |
| `{{user.schedule_timezone}}` | 用户输入 | 定时时区（默认 Asia/Shanghai） |
| `{{user.event_start_time}}` | 用户输入 | 大促事件开始时间 |
| `{{user.event_end_time}}` | 用户输入 | 大促事件结束时间 |
| `{{user.event_scale_out_qty}}` | 用户输入 | 大促预扩容台数 |
| `{{user.idle_duration_days}}` | 用户输入 | 闲置判定天数（默认 7） |
| `{{user.idle_cpu_threshold}}` | 用户输入 | 闲置 CPU 阈值 %（默认 5） |
| `{{output.orchestration_plan}}` | 编排输出 | 编排计划 JSON（含步骤/依赖/回滚） |
| `{{output.execution_summary}}` | 编排输出 | 执行结果摘要 |
| `{{output.verification_result}}` | 编排输出 | 验证结果（通过/失败/异常） |

---

## 六大场景定义

本 Skill 预定义 **6 个经典弹性场景**，覆盖 90%+ 的自动扩缩容需求：

| # | 场景名称 | 触发方式 | 核心决策要素 | 典型配置 | 适用业务 |
|:-:|---------|---------|-------------|---------|---------|
| **S1** | CPU/内存指标驱动扩缩 | CMS 告警 | CPU > 70% 持续 5min → 扩容 | Simple/TargetTracking 规则 | Web/API 服务 |
| **S2** | 定时业务周期扩缩 | Cron 表达式 | 9:00 扩至 5 台 / 18:00 缩至 2 台 | ScheduledTask 规则 | 办公系统/日间业务 |
| **S3** | 预测性扩缩 | 历史指标 ML 预测 | 基于 14 天历史预测未来 2 天负载 | PredictiveScalingRule | 规律波动业务 |
| **S4** | 复合多指标扩缩 | CMS 多指标加权 | CPU > 70% AND 内存 > 80%，或任一达危险线 | StepScalingRule | 关键交易系统 |
| **S5** | 大促弹性保障 | 事件时间窗口 | 提前 2h 扩容至 N 台，结束后渐缩 | ScheduledTask + 手动确认 | 电商大促/活动 |
| **S6** | 闲置资源自动回收 | CMS 低负载持续 | CPU < 5% 持续 7 天 → 缩容至 MinSize | SimpleScalingRule(缩) | 开发/测试环境 |

---

## 编排标准流程（5 步法）

每个场景遵循统一的 5 步编排流程：

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1 — Perceive (感知)                                        │
│  委托 cms-ops 采集当前/历史指标，或解析用户输入的定时/事件参数         │
│  输出: 当前负载状态 + 历史趋势                                     │
│                                                                  │
│  Step 2 — Decide (决策)                                          │
│  根据场景规则 + 当前状态，计算目标容量、扩缩数量、执行时机              │
│  输出: 编排计划 (scaling_plan.json)                                │
│                                                                  │
│  Step 3 — Orchestrate (编排)                                      │
│  编排多个下游 Skill 按依赖顺序执行:                                 │
│    ├── 1. ess-ops: 创建/执行伸缩规则 / ScheduledTask              │
│    ├── 2. slb-ops: 注册/注销后端（如需）                           │
│    └── 3. cms-ops: 创建/更新告警阈值                              │
│  输出: 各步骤执行状态                                             │
│                                                                  │
│  Step 4 — Verify (验证)                                          │
│  委托 cms-ops 确认指标恢复到目标范围，ess-ops 确认伸缩活动完成        │
│  输出: 验证结果 (通过/回滚中/失败)                                  │
│                                                                  │
│  Step 5 — Report (报告)                                          │
│  生成扩缩容执行报告: 决策原因 / 执行摘要 / 成本影响 / 验证结论        │
│  输出: Markdown + JSON 双格式报告                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 场景详细规格

### S1 — CPU/内存指标驱动扩缩

**适合**：Web 服务、API 网关、应用服务器

| 参数 | 说明 | 默认值 | 可选值 |
|------|------|:-----:|-------|
| 扩容触发指标 | CPUUtilization | — | CPUUtilization, MemoryUtilization |
| 扩容阈值 | CPU > threshold 持续 duration | 70% / 5min | 50-90% / 1-15min |
| 缩容触发指标 | CPU < threshold 持续 duration | 30% / 10min | 10-50% / 5-30min |
| 扩容步长 | 每次增加 | 2 台 | 1-10 |
| 缩容步长 | 每次减少 | 1 台 | 1-5 |
| 冷却时间 | 执行后等待 | 300s | 60-600s |
| ESS 规则类型 | — | TargetTrackingScalingRule | Simple/Step/TargetTracking |

**编排流**：

```
1. cms-ops 创建 CPU 告警 (CPU > 70%, 5min)
2. ess-ops CreateScalingRule (TargetTracking, target=60%)
3. ess-ops 关联告警到伸缩规则
4. cms-ops 创建缩容告警 (CPU < 30%, 10min)
5. ess-ops CreateScalingRule (Simple, -1台)
6. slb-ops 确认后端服务器组最大连接数配置
7. 验证: cms-ops 检查 CPU 是否回归目标范围
```

---

### S2 — 定时业务周期扩缩

**适合**：办公系统（9-5 业务）、日间高频/夜间低频、工作日/周末不同规格

| 参数 | 说明 | 默认值 |
|------|------|:-----:|
| 扩容时间 | Cron 表达式 | `0 9 * * 1-5` (工作日 9:00) |
| 缩容时间 | Cron 表达式 | `0 18 * * 1-5` (工作日 18:00) |
| 扩容期望容量 | — | 5 |
| 缩容期望容量 | — | 1 |
| 时区 | — | Asia/Shanghai |

**编排流**：

```
1. ess-ops CreateScheduledTask (扩容: 9:00 → 期望容量 N)
2. ess-ops CreateScheduledTask (缩容: 18:00 → 期望容量 1)
3. 验证: ess-ops DescribeScheduledTasks 确认创建成功
```

---

### S3 — 预测性扩缩

**适合**：业务负载有规律波动（如电商日常流量波峰波谷）

| 参数 | 说明 | 默认值 |
|------|------|:-----:|
| 历史数据窗口 | 用于预测的天数 | 14 天 |
| 预测周期 | 预测未来时长 | 2 天 |
| 预测指标 | — | CPUUtilization |
| 目标值 | 预测目标利用率 | 60% |
| 最大容量 | 预测扩容上限 | 10 |

**编排流**：

```
1. cms-ops DescribeMetricList 获取 14 天 CPU 历史
2. 决策引擎分析历史模式 (周期性/趋势性/随机性)
3. ess-ops CreateScalingRule (PredictiveScalingRule, target=60%)
4. 验证: ess-ops DescribeScalingRules 确认创建
```

---

### S4 — 复合多指标扩缩

**适合**：关键交易系统、对稳定性要求高的业务

| 参数 | 说明 | 默认值 |
|------|------|:-----:|
| 主指标 A | 第一判断维度 | CPUUtilization |
| 辅指标 B | 第二判断维度 | MemoryUtilization |
| 模式 | 组合逻辑 | AND（全部满足才触发）|
| A 扩容阈值 | — | 70% |
| B 扩容阈值 | — | 80% |
| 危险线 | 任一指标超过则立即扩容 | 90% |

**决策矩阵**：

```
            内存 < 80%    内存 80-90%    内存 > 90%
CPU < 70%    [无操作]     [监控观察]     [❗危险→扩容]
CPU 70-85%   [监控观察]   [✅确认→扩容]  [❗危险→扩容]
CPU > 85%    [❗危险→扩容] [❗危险→扩容]  [🚨紧急→扩容+通知]
```

**编排流**：

```
1. cms-ops 创建复合告警 (CPU > 70% AND Mem > 80%)
2. ess-ops CreateScalingRule (StepScalingRule)
   ├── 正常区: 扩容 1 台
   ├── 危险区: 扩容 3 台
   └── 紧急区: 扩容 5 台 + 通知用户
3. cms-ops 创建危险线告警 (CPU > 90% OR Mem > 90%)
4. 验证: cms-ops 检查双指标是否均回归安全区
```

---

### S5 — 大促弹性保障

**适合**：电商大促、营销活动、发布会直播

| 参数 | 说明 | 默认值 |
|------|------|:-----:|
| 开始时间 | — | 用户指定 |
| 结束时间 | — | 用户指定 |
| 预扩容提前量 | 活动前提前扩容 | 2 小时 |
| 活动期容量 | 保底台数 | 10 |
| 后缩容策略 | 结束后渐缩还是立即缩 | Gradual（分批撤） |

**编排流**：

```
1. 决策引擎计算预扩容容量（基于历史峰值 × 安全系数 1.5）
2. ess-ops ModifyScalingGroup (MaxSize 临时提升)
3. ess-ops CreateScheduledTask (提前 2h 扩容至保底台数)
4. ess-ops CreateScheduledTask (结束后渐缩: 每 30min 缩 20%)
5. cms-ops 创建活动期专用告警 (阈值降低, 响应更快)
6. 通知用户: 大促弹性策略已就绪
7. 活动期间: cms-ops 实时监控 + 自动调整
8. 活动结束后: ess-ops 恢复原始 MaxSize
```

---

### S6 — 闲置资源自动回收

**适合**：开发/测试/预发布环境、周末低负载业务

| 参数 | 说明 | 默认值 |
|------|------|:-----:|
| 闲置判定 CPU 阈值 | CPU 持续低于此值 | 5% |
| 闲置判定天数 | 持续天数 | 7 天 |
| 缩容目标 | 缩至 | MinSize |
| 缩容前通知 | 提前通知 | 24h（通过 cms-ops 告警通知）|

**编排流**：

```
1. cms-ops DescribeMetricList 查 7 天 CPU 历史
2. 决策引擎判断是否为 "闲置" 模式
3. 创建 cms-ops 告警 (24h 通知 → 准备缩容)
4. ess-ops ModifyScalingGroup (MinSize=1 / 缩容)
5. 验证: ess-ops DescribeScalingInstances 确认实例数
6. 报告: 释放资源清单 + 预估节省金额
```

---

## 安全门设计

### 扩缩容安全分级

| 等级 | 操作类型 | 门禁要求 | 适用范围 |
|:----:|---------|---------|---------|
| 🟢 自动 | TargetTracking + Simple 规则执行 | 无额外确认 | S1, S2, S3 |
| 🟡 白名单 | 预审批策略内的扩缩操作 | Pre-Approved Whitelist | S4 (正常区), S6 |
| 🔴 需确认 | 大容量调整/跨阈值操作 | 用户明确确认 | S4 (危险/紧急区), S5 |
| ⛔ 禁止 | 无凭证修改/跨账号操作 | Safety=0 ABORT | 所有场景 |

### 熔断机制

每次扩缩操作实施前检查以下熔断条件：

| 熔断条件 | 检查方式 | 动作 |
|---------|---------|------|
| 24h 内扩缩次数 > 5 | 查询 ess-ops DescribeScalingActivities | 熔断 1h |
| 当前有扩缩活动未完成 | ess-ops 活动状态检查 | 排队等待 |
| 余额不足 | billing-ops 查询账户余额 | HALT + 通知 |
| 目标容量超出配额 | ess-ops DescribeLimitation | 调整计划 |
| 同组 1h 内扩缩方向反转 > 3 次 | 编排引擎记录分析 | 熔断 + 告警 |

---

## Pre-flight Interaction

```
 弹性伸缩编排配置

1. 选择场景:
   [1] CPU/内存指标驱动扩缩     (metric)
   [2] 定时业务周期扩缩          (scheduled)
   [3] 预测性扩缩               (predictive)
   [4] 复合多指标扩缩            (composite)
   [5] 大促弹性保障              (event)
   [6] 闲置资源自动回收           (cleanup)

2. 目标伸缩组:
   [a] 选择已有伸缩组 (输入 ID)
   [b] 自动检测候选资源 → topo-discovery 扫描
   [c] 创建新伸缩组 → 委托 ess-ops

3. 策略参数 (按场景提示):
   场景 S1: 扩容阈值 / 缩容阈值 / 扩缩步长 / 冷却时间
   场景 S2: 扩容时间 / 缩容时间 / 目标容量
   场景 S3: 历史天数 / 预测天数 / 目标利用率
   场景 S4: 主要指标 / 次要指标 / 组合模式
   场景 S5: 活动开始/结束时间 / 预扩容量 / 缩容策略
   场景 S6: 闲置阈值 / 判定天数 / 缩容目标

4. 安全确认 (高危操作):
   [Y] 确认执行 (高风险操作将等待用户二次确认)
```

---

## Quality Gate (GCL)

### GCL Classification

| 属性 | 值 |
|:----|:---|
| Classification | `required` |
| max_iter | 2 |
| 最严格审查操作 | S4 危险/紧急区、S5 大促扩缩、S6 闲置回收 |

### Rubric Dimensions

| 维度 | 阈值 | 说明 |
|------|:---:|------|
| **Correctness** | >= 0.7 | 决策逻辑与用户意图一致，扩缩数量在合理范围 |
| **Safety** | = 1.0 | 不越权操作，熔断检查全部通过 |
| **Idempotency** | >= 0.8 | 相同条件下多次执行产出相同决策 |
| **Traceability** | >= 0.8 | 报告含完整决策链 + 执行上下文 |
| **Spec Compliance** | >= 0.8 | 严格遵循场景定义和委托规则 |

---

## 参考文档索引

| 文档 | 用途 | 加载条件 |
|------|------|---------|
| [references/orchestration-flows.md](references/orchestration-flows.md) | 6 个场景的完整编排步骤和 CLI 命令 | 执行编排时 |
| [references/decision-engine.md](references/decision-engine.md) | 决策规则定义、指标采集逻辑、容量计算 | 设计策略时 |
| [references/integration.md](references/integration.md) | 下游 Skill 集成规范、委托路径 | 跨 Skill 调试时 |
| [references/troubleshooting.md](references/troubleshooting.md) | 错误码(≥12种)、诊断流程、恢复策略 | 排查失败时 |
| [references/well-architected-assessment.md](references/well-architected-assessment.md) | 五支柱评估 | 架构评估时 |
| [references/rubric.md](references/rubric.md) | GCL Rubric 评分细则 | GCL 评审时 |
| [references/prompt-templates.md](references/prompt-templates.md) | GCL Generator/Critic 提示模板 | GCL 评审时 |

---

## Well-Architected Framework Assessment

| 支柱 | 核心原则 |
|------|---------|
| **Security** | 最小权限委托 + `{{env.*}}` ONLY + 安全熔断 + Safety Gate 分级 |
| **Stability** | 5 步标准流程 + 缩容保护 + 熔断机制 + 回滚策略 |
| **Cost** | 闲置回收场景(S6)直接省钱 + 定时缩容(S2)避免浪费 + Predictive(S3)优化用量 |
| **Efficiency** | 自动化编排替代手动操作 + 6 场景覆盖 90%+ 需求 + 统一的 5 步法 |
| **Performance** | 决策 < 5s + 编排 < 30s + 验证 < 60s（不含 ESS 活动等待时间） |

---

## Changelog

| 版本 | 日期 | 变更 |
|:----|:----|------|
| 1.0.0 | 2026-06-07 | 初始版本：6 大场景定义 + 5 步编排流程 + 安全门 + GCL required |