---
name: alicloud-aiops-cruise
version: "1.0.0"
metadata:
  description: >-
    阿里云全链路 AIOps 巡检 Skill — 从 EIP→SLB→ECS→RDS/Redis→NAT→安全组的端到端健康巡检、
    故障排查、容量规划和预检。Agent 通过 aliyun CLI 编排阿里云原生服务
    (CloudMonitor / DAS / CloudAssistant / ResourceCenter / ActionTrail / CloudFirewall)
    完成拓扑发现、指标采集、深度诊断和链路关联推理。
    纯读操作，不执行任何资源变更。
  cli_applicability: dual-path
  cli_version_locked: false
  sdk_version_locked: false
---

# 阿里云全链路 AIOps 巡检 — alicloud-aiops-cruise

> **一句话定位**：跨 EIP → SLB → ECS → RDS/Redis → NAT → 安全组的端到端链路巡检。
> 不做资源变更，只做发现、诊断、推理和报告。

## 提示知识力

| 知识点 | 说明 |
|---|---|
| **为什么叫 "Cruise" 而不是 "Check"？** | Cruise 是一次"巡航式穿透"—— 从入口 EIP 一路穿到后端数据层和出网层，逐跳检查链路中各节点的健康状态，而非孤立地查单个产品 |
| **和 topo-discovery 有什么区别？** | `topo-discovery` 做静态拓扑发现和 HCL 导出；`aiops-cruise` 做动态健康巡检（含监控、诊断、推理）。拓扑发现是链路巡检的"前置步骤"而非终点 |
| **和 cms-ops 有什么区别？** | `cms-ops` 查单个产品的监控指标；`aiops-cruise` 跨产品组合指标做链路关联推理（例如：SLB 健康检查失败 + ECS 正常 = 查网络连通性） |
| **巡检为什么是"纯读"？** | 巡检是发现问题的眼睛，不是解决问题的手。发现问题后出"建议"，具体变更通过对应的 ops skill（如 `alicloud-ecs-ops`）由用户确认后执行 — 这是安全边界 |
| **链路推理的价值** | 全链路巡检的价值不在于采集指标（CLI 都能做），而在于把分散的指标组合成一条"推理链"：A 现象 + B 现象 → 根因概率排序 → 可执行建议 |
| **标签 vs 资源组，怎么选？** | 标签灵活但依赖维护（可能漏打）；资源组是云资源管理的原生单位，更可靠。推荐优先使用**资源组（ResourceGroupId）**扫描，标签作为回退方案。详见 `references/execution-guide.md` 的资源组章节 |

## Trigger & Scope

### SHOULD Use

- 需要对指定客户（按标签）或业务系统做全链路健康检查
- 需要排查从公网入口到后端数据库的整条链路故障根因
- 需要做容量规划（30 天趋势预测）或大促前 3x 流量压力预检
- 需要安全合规审计（安全组开放端口 + Cloud Firewall 策略 + ActionTrail 操作事件）
- 需要了解某个业务系统的阿里云资源拓扑和健康全景

### SHOULD NOT Use

- 只查单个资源（如单台 ECS）→ 使用 `alicloud-ecs-ops` 或对应产品 ops skill
- 需要创建/修改/删除资源 → 使用对应产品的 ops skill
- 只查监控指标（不需要链路推理）→ 使用 `alicloud-cms-ops`
- 只做拓扑发现（不需要健康诊断）→ 使用 `alicloud-topo-discovery`
- 不涉及阿里云资源的巡检 → 不使用

### Cross-Skill References

| 需求 | 参考 Skill | 引用方式 |
|---|---|---|
| 监控指标采集 | `alicloud-cms-ops` | 复用 `--Namespace/MetricName/Period` 参数约定 |
| DAS 数据库诊断 | `alicloud-das-ops` | 复用 `assets/code-snippets/` 的 Go 零件 |
| CloudAssistant 内检测 | `alicloud-agentrun-ops` | 复用 RunCommand 交互模式 |
| 拓扑发现 | `alicloud-topo-discovery` | 用户需纯拓扑图时引导至此 |
| ECS 详细诊断 | `alicloud-ecs-analysis-aliyun` | 引用分析框架思路 |
| SLB 详细诊断 | `alicloud-slb-ops` | 引用 Describe* 命令模式 |

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | N/A | 只读操作，不触发 GCL 质量门禁 |

## Variable Convention

| 类型 | 含义 | 来源 | 示例 |
|---|---|---|---|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | AK ID | 运行时环境变量，NEVER ask user | — |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | AK Secret | 运行时环境变量，NEVER exposed | — |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | 默认区域 | 运行时环境变量 | `cn-hangzhou` |
| `{{user.customer_name}}` | 客户名/标签值 | 每次巡检时询问 | `烟台振华` |
| `{{user.scenario}}` | 巡检场景 | 用户选择 | `daily_check` |
| `{{user.enable_das}}` | 启用 DAS 深度诊断? | 用户确认 (Y/N) | `true` |
| `{{user.enable_cloud_assistant}}` | 启用内检测? | 用户确认 (Y/N) | `true` |
| `{{output.topology}}` | 拓扑发现结果 | ResourceCenter 输出解析 | JSON |
| `{{output.metrics}}` | 监控指标 | CloudMonitor 输出聚合 | JSON |
| `{{output.das_report}}` | DAS 诊断报告 | Go SDK 输出 | JSON |
| `{{output.chain_inference}}` | 链路推理结论 | Agent 推理结果 | Markdown |

## Safety Gates（安全铁律）

> **本 Skill 是纯读（Read-Only）巡检，不执行任何写操作。**

| 红线 | 要求 | 违规后果 |
|---|---|---|
| **任何资源的删除/释放** | 不允许自动执行 | Safety = 0，GCL 立即 ABORT |
| **任何资源的停止/关机/重启** | 不允许自动执行 | Safety = 0，GCL 立即 ABORT |
| **任何资源的规格变更/升配** | 不允许自动执行，报告只出建议 | Safety = 0，GCL 立即 ABORT |
| **安全组规则增删** | 不允许自动执行 | Safety = 0，GCL 立即 ABORT |
| **巡检报告含 AK/SK** | 必须掩码为 `AKID****SKRET` | 严重违规 |
| **Finding 数据结构** | 所有 finding 必须符合 [`references/incident-schema.md`](references/incident-schema.md) v1.0.0+（`level`、`rule_id`、`dedup_key` 必填） | GCL Traceability = 0 |
| **自动执行白名单** | 任何 `[AUTO-*]` 标签操作必须命中 [`references/pre-approved-whitelist.md`](references/pre-approved-whitelist.md) 矩阵，且触发对应审计日志 | Safety = 0 |
| **巡检触发** | 必须有客户/标签筛选，严禁扫全账号 | — |
| **默认资源组扫描** | 自动跳过 default/空资源组，除非用户明确要求全账号扫描 | Safety = 0，立即 HALT |
| **报告输出** | JSON 持久化到 `audit-results/` | — |

## Skill Maintenance Rules

> 技能开发/修改时的维护规范（MR-1 ~ MR-9）已抽取到独立文件，按需加载：
> [`references/maintenance-rules.md`](references/maintenance-rules.md)

| 规则 | 标题 | 加载方式 |
|------|------|---------|
| MR-1 | TODO.md 同步 | 每次修改后加载 |
| MR-2 | 规范文档先行 | 新增能力前加载 |
| MR-3 | 验证标准可复现 | 添加 TODO 项时加载 |
| MR-4 | 质量门定期评审 | 每 Sprint 加载 |
| MR-5 | TODO/Sprint 文件拆分规范 | 创建新 Sprint 时加载 |
| MR-6 | 代码审查规范 | 修改脚本前加载 |
| MR-7 | Lint 检测规范 | 修改脚本前加载 |
| MR-8 | 文案规范 — 避免表情符号 | 编写文本输出时加载 |
| MR-9 | 写操作确认规范 | 涉及变更操作时加载 |

## Pre-flight Interaction

```
 阿里云全链路 AIOps 巡检配置

1. 巡检范围（二选一）:
   [T] 按资源组扫描（推荐）— 输入资源组ID
       → 例: rg-acfmvyfsd4znnoi
       → 也可输入一个资源ID，自动反查所属资源组后扫描全组
   [L] 按标签扫描 — 输入标签键和标签值
       → 例: customer / 烟台振华

2. 巡检场景:
   [1] 日常健康巡检
   [2] 故障应急排查
   [3] 容量规划
   [4] 大促前预检

3. 巡检范围（可选，默认全链路）:
   [a] 全链路
   [b] 仅网络层（EIP->SLB->VPC）
   [c] 仅计算层（ECS->ACK）
   [d] 仅数据层（RDS->Redis->MongoDB）

4. 深度诊断选项:
   启用 DAS 数据库深度诊断? (Y/N，默认 Y)
   启用 CloudAssistant 内检测? (Y/N，默认 N)
```

## Execution Flow Overview

本 Skill 采用三阶段执行模式，具体步骤因场景而异（详见 runbooks/）。

### Phase 1: 嗅探 + 拓扑发现
核心命令: `aliyun resourcecenter SearchResources`, `aliyun vpc DescribeVpcs`, `aliyun slb DescribeLoadBalancers`
输出: 拓扑初判报告（Markdown）+ 待人工确认清单（如需）

### Phase 2: 深度采集 + 诊断
数据源: CloudMonitor (6h 指标 + 环比), DAS (慢查询), CloudAssistant (ECS 内检测), ActionTrail (操作事件)

### Phase 3: 推理 + 报告
Agent 对照 `references/inference-rules.md` 做链路关联推理。输出: Markdown + JSON。

## Quality Gate (GCL)

### Rubric Dimensions

| 维度 | 阈值 | 说明 |
|---|---|---|
| **Correctness** | >= 0.5 | 巡检结论与实际情况一致 |
| **Safety** | = 1 | 纯读操作，任何写操作为 0 |
| **Idempotency** | >= 0.8 | 相同输入在不同时间应产出一致结论 |
| **Traceability** | >= 0.8 | 报告含完整执行上下文 |
| **Spec Compliance** | >= 0.8 | 严格遵循 runbook 定义和阈值规范 |

GCL Prompt 见 `references/prompt-templates.md`。

## Runbook Index

| 编号 | 场景 | 风险等级 | 执行时间 | 适用时机 |
|---|---|---|---|---|
| 01 | 日常健康巡检 | 低 | 5-15min | 每 6h / 按需 |
| 02 | 故障应急排查 | 高 | 3-8min | 告警触发 / 用户报障 |
| 03 | 容量规划 | 中 | 5-10min | 每周 |
| 04 | 大促前预检 | 高 | 10-20min | 大促前 3 天 |

详细执行步骤见对应 runbook。

## Well-Architected Assessment

> 五支柱详细内容见 [`references/well-architected-assessment.md`](references/well-architected-assessment.md)

| 支柱 | 核心原则 |
|------|---------|
| **Security** | 最小权限 + `{{env.*}}` ONLY + 输出掩码 |
| **Stability** | 面向失败设计 + 配置漂移追踪 + 应急决策树 |
| **Cost** | Describe/List/Get 类 API 免费 |
| **Efficiency** | 并行采集 + 渐进式深度模式 |
| **Performance** | Phase 1 < 1min, Phase 2 < 5min, +Deep < 8min |

## Changelog

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0.0 | 2026-06-06 | 初始版本 |