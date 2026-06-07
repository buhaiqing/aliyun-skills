# Integration — 架构评审 Skill 集成指南

> 定义本 Skill 如何与依赖的下游数据源 Skill 集成，以及输出格式约定。

---

## 1. 集成架构

```
                    alicloud-arch-advisor (咨询层)
                             │
               ┌─────────────┼─────────────┬──────────────┐
               │             │             │              │
               ▼             ▼             ▼              ▼
      topo-discovery   advisor-ops     cms-ops      billing-ops
      ─────────────    ───────────    ─────────     ──────────
      资源拓扑发现      Advisor        监控指标       成本分析
      资源清单         巡检结果        利用率数据     账单数据
      依赖关系         风险检测        性能数据       花费趋势
```

---

## 2. 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|:----:|:------:|------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | 是 | — | RAM 用户 AccessKey ID。NEVER ask the user；HALT if unset |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | 是 | — | RAM 用户 AccessKey Secret。NEVER ask the user；NEVER log |
| `ALIBABA_CLOUD_REGION_ID` | 是 | `cn-hangzhou` | 默认地域 |
| `ALIYUN_SKILLS_ROOT` | 否 | 自动检测 | 仓库根路径，用于引用场景模板 |

---

## 3. 数据源依赖表

| 数据源 Skill | 依赖级别 | 获取内容 | 使用模式 | 降级策略 |
|-------------|:--------:|---------|:--------:|---------|
| `alicloud-topo-discovery` | **required** | 资源清单、网络拓扑、组件依赖关系 | A, B, C | 降级为用户自行描述架构 + low confidence |
| `alicloud-advisor-ops` | **recommended** | Advisor 巡检结果、安全/稳定/成本检查 | B | 跳过该 Skill 依赖部分，标注局限性 |
| `alicloud-cms-ops` | **recommended** | 资源利用率指标（CPU/内存/IOPS/QPS） | B (Performance) | 跳过 Performance 支柱指标部分 |
| `alicloud-billing-ops` | **optional** | 成本数据、花费趋势、付费模式 | B (Cost) | 跳过 Cost 支柱量化部分 |

### 3.1 topo-discovery 委托协议

| 委托操作 | 传递参数 | 预期返回 |
|---------|---------|---------|
| 获取全量资源 | `scope`, `account_id` | 资源 JSON 数组，含类型、ID、地域、标签 |
| 获取资源依赖 | `resource_ids[]` | 依赖关系图，含上下游关系 |
| 获取网络拓扑 | `vpc_id` | VPC、交换机、路由表、NAT、EIP 信息 |

### 3.2 advisor-ops 委托协议

| 委托操作 | 传递参数 | 预期返回 |
|---------|---------|---------|
| 获取 Security 建议 | `--filter Security` | 安全检查结果列表 |
| 获取 Cost 建议 | `DescribeCostOptimizationOverview` | 成本优化建议和预估节省 |
| 获取 Stability 建议 | `--filter Stability` | 稳定性检查结果列表 |

### 3.3 cms-ops 委托协议

| 委托操作 | 传递参数 | 预期返回 |
|---------|---------|---------|
| 获取 CPU 利用率 | `Namespace=acs_ecs_dashboard`, `MetricName=CpuUtilization` | 时序数据 |
| 获取内存利用率 | `Namespace=acs_ecs_dashboard`, `MetricName=MemoryUtilization` | 时序数据 |
| 获取 IOPS | `Namespace=acs_ecs_dashboard`, `MetricName=DiskIOPS` | 时序数据 |

---

## 4. 输出格式

### 4.1 架构拓扑 JSON

```json
{
  "architecture_id": "arch-20260607-001",
  "mode": "A",
  "generated_at": "2026-06-07T12:00:00Z",
  "data_sources": [
    { "skill": "topo-discovery", "timestamp": "2026-06-07T11:55:00Z", "request_id": "req-topo-001" },
    { "skill": "advisor-ops", "timestamp": "2026-06-07T11:56:00Z", "request_id": "req-adv-001" }
  ],
  "topology": {
    "pattern": "three-tier",
    "layers": [
      {
        "name": "presentation",
        "components": [
          { "type": "ALB", "id": "alb-bp1xxxx", "region": "cn-hangzhou", "properties": { "listeners": 2, "backend_servers": 4 } }
        ]
      },
      {
        "name": "application",
        "components": [
          { "type": "ECS", "id": "i-bp1yyyy", "region": "cn-hangzhou", "properties": { "spec": "ecs.g6.large", "os": "Alibaba Cloud Linux 3" } },
          { "type": "ECS", "id": "i-bp1zzzz", "region": "cn-hangzhou", "properties": { "spec": "ecs.g6.large", "os": "Alibaba Cloud Linux 3" } }
        ]
      },
      {
        "name": "data",
        "components": [
          { "type": "RDS", "id": "rm-bp1aaaa", "region": "cn-hangzhou", "properties": { "engine": "MySQL 8.0", "spec": "rds.mysql.s2.large", "ha": true } },
          { "type": "Redis", "id": "r-bp1bbbb", "region": "cn-hangzhou", "properties": { "version": "7.0", "spec": "redis.master.small.default" } }
        ]
      }
    ],
    "dependencies": [
      { "from": "alb-bp1xxxx", "to": "i-bp1yyyy", "type": "http" },
      { "from": "alb-bp1xxxx", "to": "i-bp1zzzz", "type": "http" },
      { "from": "i-bp1yyyy", "to": "rm-bp1aaaa", "type": "jdbc" },
      { "from": "i-bp1zzzz", "to": "rm-bp1aaaa", "type": "jdbc" },
      { "from": "i-bp1yyyy", "to": "r-bp1bbbb", "type": "redis" }
    ]
  }
}
```

### 4.2 WAF 评分 JSON

```json
{
  "report_id": "waf-20260607-001",
  "mode": "B",
  "generated_at": "2026-06-07T12:00:00Z",
  "data_sources": [
    { "skill": "topo-discovery", "timestamp": "2026-06-07T11:55:00Z" },
    { "skill": "advisor-ops", "timestamp": "2026-06-07T11:56:00Z" },
    { "skill": "cms-ops", "timestamp": "2026-06-07T11:57:00Z" }
  ],
  "waf_scores": {
    "security": { "score": 0.85, "checks_passed": 12, "checks_total": 15, "findings": 3 },
    "reliability": { "score": 0.70, "checks_passed": 7, "checks_total": 10, "findings": 3 },
    "performance": { "score": 0.60, "checks_passed": 6, "checks_total": 10, "findings": 4 },
    "cost": { "score": 0.75, "checks_passed": 9, "checks_total": 12, "findings": 3 },
    "efficiency": { "score": 0.65, "checks_passed": 5, "checks_total": 8, "findings": 3 }
  },
  "composite_score": 0.71,
  "findings": [
    {
      "id": "F-SEC-001",
      "priority": "P0",
      "pillar": "security",
      "title": "安全组 SSH 端口暴露到公网",
      "detail": "安全组 sg-bp1xxxx 的入方向规则允许 0.0.0.0/0 访问端口 22",
      "data_source": "advisor-ops (Ecs.SecurityGroup.OpenPort22)",
      "recommendation": "限制 SSH 访问源 IP 为特定管理网段",
      "effort": "low",
      "impact": "security"
    },
    {
      "id": "F-REL-001",
      "priority": "P1",
      "pillar": "reliability",
      "title": "RDS 实例为单节点部署",
      "detail": "RDS rm-bp1aaaa 为单节点基础版，不具备自动故障切换能力",
      "data_source": "topo-discovery (rm-bp1aaaa.properties.ha = false)",
      "recommendation": "升级到高可用版（双节点）",
      "effort": "medium",
      "impact": "availability"
    }
  ],
  "recommendations": [
    {
      "pillar": "reliability",
      "priority": "P1",
      "title": "RDS 升级至高可用版",
      "action": "通过 alicloud-rds-ops 执行 UpgradeDBInstanceEngineVersion 或创建新 HA 实例",
      "effort": "medium",
      "expected_benefit": "实现自动故障切换，RTO < 30s",
      "estimated_cost": "费用约为基础版的 2x"
    }
  ]
}
```

---

## 5. 报告 Markdown 模板

```markdown
# 架构评审报告

## 摘要
{一句话结论，含 composite score（Mode B）}

## 架构概览
{架构模式 + 组件列表 + 交互关系（文本模式）}

| 层 | 组件 | 规格 | 数量 | 地域 |
|---|------|------|:---:|:----:|
| 接入层 | ALB | ... | 1 | cn-hangzhou |
| 应用层 | ECS | ecs.g6.large | 2 | cn-hangzhou |
| 数据层 | RDS MySQL | 8.0, HA | 1 | cn-hangzhou |

## 依赖关系
{组件间交互关系描述}

## WAF 评估矩阵（Mode B）
| 支柱 | 评分 | P0+P1 发现数 | 关键发现 |
|:----:|:----:|:-----------:|---------|
| Security | 0.85 | 1 | SSH 暴露 |
| Reliability | 0.70 | 2 | RDS 单节点 |
| Performance | 0.60 | 1 | ECS 规格过低 |
| Cost | 0.75 | 1 | 闲置 EIP |
| Efficiency | 0.65 | 1 | 无 IaC |

## 风险发现

### P0 — 立即处理
- ...

### P1 — 本周处理
- ...

### P2 — 本月处理
- ...

## 改进建议
{按优先级排序，含预估工作量和影响}

## 数据源记录
| 数据 | 来源 | 采集时间 | RequestId |
|------|------|---------|-----------|
| 资源拓扑 | topo-discovery | 2026-06-07 11:55 | req-xxx |
| 巡检结果 | advisor-ops | 2026-06-07 11:56 | req-yyy |

## 局限性
{标注数据源不可用部分 + confidence 级别}
```

---

## 6. 跨 Skill 调试指南

### 6.1 委托链路追踪

每次委托调用必须记录：

```
[arch-advisor] → [topo-discovery] GetTopology
  TraceID: trace-20260607-001
  Request: {region: "cn-hangzhou", product: ["ECS", "RDS", "SLB"]}
  Response: {resources: [...], dependencies: [...]}
  Duration: 3.2s
  Status: success
```

### 6.2 常见委托失败

| 错误 | 可能原因 | 排查方法 |
|------|---------|---------|
| `topo-discovery` 返回空 | 凭证权限不足或无资源 | 检查 RAM 策略和账号下是否有资源 |
| `advisor-ops` 超时 | Advisor 服务暂时不可用 | 重试或跳过该数据源 |
| `cms-ops` 无数据 | Monitor 未开通或指标未被采集 | 跳过指标部分，基于配置做定性评估 |
| `billing-ops` 权限不足 | RAM 未授权 billing 查询 | 跳过成本量化分析 |

---

## 7. 验证集成

```bash
# 验证依赖 Skill 可用性
aliyun version

# 验证 topo-discovery (如果可用)
# 委托 topo-discovery 获取资源

# 验证 advisor-ops
aliyun advisor GetProductList

# 验证 cms-ops
aliyun cms DescribeMetricMetaList --Namespace acs_ecs_dashboard
```

---

## Changelog

| 版本 | 日期 | 变更 |
|:----|:----|------|
| 1.0.0 | 2026-06-07 | 初始版本：集成架构、委托协议、输出格式、调试指南 |