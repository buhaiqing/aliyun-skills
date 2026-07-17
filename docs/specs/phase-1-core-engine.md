# Phase 1 SPEC — 核心诊断引擎 + 双模式接入

> **版本**: v1.0
> **状态**: 设计中
> **最后更新**: 2026-07-17
> **关联**: [架构总览](../ARCHITECTURE.md) | [Phase 1 PLAN](../plans/phase-1-plan.md)

---

## 1. 目标与成功标准

### 1.1 一句话目标

构建一个**自主诊断引擎**，能接收告警/工单/自然语言描述，自动选择诊断路径、并行执行检查、交叉分析根因、输出结构化诊断报告，并通过 REST API 和 MCP Server 两种方式对外提供服务。

### 1.2 可验证的成功标准

| # | 标准 | 验证方式 |
|---|------|----------|
| S1 | 从接收到告警到输出诊断结果，耗时 < 30 秒（不含 LLM 调用） | 集成测试，计时 |
| S2 | Top 20 常见运维现象（CPU 高、连接数高、慢 SQL、磁盘满、内存高、OOM 等）有对应诊断模板 | 模板文件计数 |
| S3 | 诊断模板覆盖的产品 ≥ 10 个（RDS、ECS、Redis、SLB、ACK、OSS、MongoDB、Elasticsearch、PolarDB、FC） | 模板文件计数 |
| S4 | 并行诊断步骤正确 fan-out / fan-in，无数据竞争 | 单元测试 |
| S5 | REST API 和 MCP Server 共享同一套核心引擎，诊断结果一致 | 集成测试：同一输入，两种接入方式输出相同 |
| S6 | 每次诊断执行过 GCL 质量门禁，Safety=0 时 ABORT | GCL trace 记录 |
| S7 | 诊断过程全程可追溯（Langfuse Trace + 本地 JSON trace） | trace 文件存在且完整 |
| S8 | 每步执行结果写入 Memory Layer 1，失败模式写入 Layer 2 | .runtime/memory/ 和 reflexion.json 更新 |

---

## 2. 核心诊断引擎

### 2.1 整体数据流

```
Input (任意文本 / 结构化 JSON)
  │
  ▼
┌─────────────────┐
│  IntentParser    │  提取：产品、资源 ID、现象、严重级别
└────────┬────────┘
         │  Intent { products, resources, symptoms, severity }
         ▼
┌─────────────────┐
│ ContextEnricher  │  补充：资源标签、负责人、关联服务、最近变更
└────────┬────────┘
         │  EnrichedContext { + tags, owner, related_services, recent_changes }
         ▼
┌─────────────────┐
│  TaskPlanner     │  匹配诊断模板 → 生成 DAG 执行计划
└────────┬────────┘
         │  Plan { steps[], dependencies }
         ▼
┌─────────────────┐
│ ExecutionEngine  │  并行/串行调度 Skill 执行 → 过 GCL 门禁
└────────┬────────┘
         │  StepResults[{ output, gcl_trace }]
         ▼
┌─────────────────┐
│RootCauseAnalyzer │  交叉分析 → 因果链推导 → 置信度评分
└────────┬────────┘
         │  Diagnosis { root_cause, confidence, evidence, suggestions }
         ▼
┌─────────────────┐
│  OutputAdapter   │  格式化为诊断报告 / 回写工单 / IM 推送 / CI 回调
└─────────────────┘
```

### 2.2 IntentParser（意图解析器）

**输入**：任意文本（告警标题+描述、工单内容、自然语言问题）

**输出**：结构化 Intent

```python
@dataclass
class Intent:
    products: list[str]           # 涉及产品: ["rds", "ecs", "redis"]
    resource_ids: list[str]       # 资源 ID: ["rm-xxx", "i-yyy"]
    symptoms: list[Symptom]       # 现象列表
    severity: Severity            # critical | warning | info
    raw_text: str                 # 原始输入（保留用于上下文）
    confidence: float             # 解析置信度 0-1

@dataclass
class Symptom:
    category: str                 # cpu_high | connection_high | slow_sql | disk_full | ...
    target: str                   # 作用对象: "rds" | "rm-xxx"
    description: str              # 现象描述
    indicators: dict[str, float]  # 量化指标: {"cpu": 95.2, "duration": "15m"}
```

**解析策略**（不依赖 LLM，用规则 + 正则）：

| 输入特征 | 解析方式 | 示例 |
|----------|----------|------|
| 资源 ID 正则 | `rm-[a-z0-9]+` → RDS, `i-[a-z0-9]+` → ECS | "rm-xxx 有问题" → products=[rds], resources=[rm-xxx] |
| 产品关键词 | 词典匹配 | "RDS"、"ECS"、"Redis"、"SLB" |
| 现象关键词 | 词典 + 同义词 | "连接数高" = "connection_high", "慢" = "slow_sql" |
| 严重级别 | 关键词匹配 | "critical"、"P1"、"紧急" → critical |
| 量化指标 | 数字 + 单位提取 | "CPU 95%" → indicators={"cpu": 95.0} |

**现象词典（第一期覆盖）**：

```yaml
symptoms:
  cpu_high:
    keywords: ["CPU高", "CPU 100%", "cpu使用率高", "CPU飙升", "CPU utilization"]
    default_products: ["ecs", "rds", "redis"]
  connection_high:
    keywords: ["连接数高", "连接数满", "too many connections", "connection exceeded"]
    default_products: ["rds", "redis"]
  slow_sql:
    keywords: ["慢SQL", "慢查询", "slow query", "查询慢", "SQL执行慢"]
    default_products: ["rds", "polar-mysql", "polar-postgresql"]
  disk_full:
    keywords: ["磁盘满", "磁盘空间不足", "disk full", "存储空间不足"]
    default_products: ["rds", "ecs", "redis", "mongodb"]
  memory_high:
    keywords: ["内存高", "内存使用率高", "OOM", "内存溢出", "memory usage"]
    default_products: ["ecs", "redis", "rds"]
  network_latency:
    keywords: ["延迟高", "超时", "timeout", "响应慢", "latency"]
    default_products: ["slb", "alb", "rds", "ecs"]
  pod_crash:
    keywords: ["Pod重启", "Pod CrashLoop", "容器异常", "pod pending"]
    default_products: ["ack", "eci"]
  cache_miss:
    keywords: ["缓存命中率低", "cache miss", "缓存穿透"]
    default_products: ["redis"]
  ssl_expiry:
    keywords: ["证书过期", "SSL过期", "TLS过期", "certificate expired"]
    default_products: ["slb", "alb", "cdn"]
  cost_spike:
    keywords: ["费用异常", "成本飙升", "账单异常", "cost anomaly"]
    default_products: ["billing"]
```

### 2.3 ContextEnricher（上下文富化器）

**输入**：Intent

**输出**：EnrichedContext（补充了运行时上下文）

```python
@dataclass
class EnrichedContext:
    intent: Intent
    resource_tags: dict[str, dict]        # 资源标签 {"rm-xxx": {"env": "production", "service": "order"}}
    resource_owners: dict[str, str]       # 资源负责人 {"rm-xxx": "zhangsan"}
    related_services: dict[str, list]     # 关联服务 {"rm-xxx": ["order-service", "payment-service"]}
    recent_changes: dict[str, list]       # 最近变更 {"rm-xxx": [{"time": "...", "type": "config_change", "detail": "..."}]}
    region: str                           # 地域
```

**富化数据源**：

| 数据 | 来源 | 获取方式 |
|------|------|----------|
| 资源标签 | 阿里云 Tag API | `aliyun tag ListTagResources` |
| 资源详情 | 各产品 Describe API | `aliyun rds DescribeDBInstanceAttribute` |
| 负责人 | CMDB / 资源标签 `owner` | Tag 中约定 `owner=zhangsan` |
| 关联服务 | 资源标签 `service` | Tag 中约定 `service=order-service` |
| 最近变更 | ActionTrail | `aliyun actiontrail LookupEvents` 近 24h |
| 地域 | Intent 推断 或 `ALIBABA_CLOUD_REGION_ID` | 环境变量 或 资源 ID 前缀 |

**失败策略**：富化失败不阻断诊断，缺失信息标记为 `unknown`，诊断报告注明"信息不完整"。

### 2.4 TaskPlanner（任务规划器）

**输入**：EnrichedContext

**输出**：执行计划（DAG）

```python
@dataclass
class Plan:
    steps: list[Step]
    template_name: str               # 匹配的诊断模板名
    template_version: str

@dataclass
class Step:
    id: str                          # 步骤 ID
    skill: str                       # 目标 Skill: "alicloud-rds-ops"
    operation: str                   # 操作名: "DescribeDBInstancePerformance"
    params: dict                     # 参数
    depends_on: list[str]            # 依赖的步骤 ID 列表
    parallel_group: str | None       # 并行组（同组并行执行）
    timeout: int                     # 超时秒数，默认 30
    on_failure: str                  # skip | abort | retry
    output_mapping: dict             # 输出映射: {"connection_trend": "$.PerformanceKeys..."}
```

**诊断模板匹配逻辑**：

1. 用 `Intent.symptoms` 的 category 查找模板库
2. 用 `Intent.products` 过滤适用的模板
3. 多个模板匹配时，取 specificity 最高的（症状+产品最精确匹配）
4. 无模板匹配时，进入通用诊断模式（按产品逐一检查基础指标）

**诊断模板示例**：

```yaml
# diagnostic_templates/rds_connection_high.yaml
name: RDS 连接数过高诊断
version: "1.0"
match:
  symptoms: ["connection_high"]
  products: ["rds"]
specificity: 10  # 越高越优先

steps:
  - id: check_connection_trend
    skill: alicloud-rds-ops
    operation: DescribeDBInstancePerformance
    params:
      DBInstanceId: "{{context.resource_ids[0]}}"
      Key: "ConnectionUsage"
      StartTime: "{{context.time_range.start}}"
      EndTime: "{{context.time_range.end}}"
    parallel_group: group1
    timeout: 15

  - id: check_slow_sql
    skill: alicloud-das-ops
    operation: GetSlowLogs
    params:
      InstanceId: "{{context.resource_ids[0]}}"
      StartTime: "{{context.time_range.start}}"
      EndTime: "{{context.time_range.end}}"
    parallel_group: group1
    timeout: 15

  - id: check_instance_spec
    skill: alicloud-rds-ops
    operation: DescribeDBInstanceAttribute
    params:
      DBInstanceId: "{{context.resource_ids[0]}}"
    parallel_group: group1
    timeout: 10

  - id: check_security_group
    skill: alicloud-ecs-ops
    operation: DescribeSecurityGroupAttribute
    params:
      SecurityGroupId: "{{context.related_sg_id}}"
    depends_on: [check_instance_spec]
    timeout: 10

  - id: root_cause_analysis
    type: inference
    depends_on: [check_connection_trend, check_slow_sql, check_instance_spec, check_security_group]
    rules:
      - condition: "slow_sql_count > 5 AND connection_trend > 80"
        conclusion: "慢 SQL 堆积导致连接数上升"
        confidence_add: 0.3
      - condition: "max_connections < connection_trend * 1.2"
        conclusion: "实例规格连接数上限不足"
        confidence_add: 0.3
      - condition: "security_group_has_anomaly_ip"
        conclusion: "异常 IP 访问导致连接数异常"
        confidence_add: 0.2
```

### 2.5 ExecutionEngine（执行引擎）

**输入**：Plan

**输出**：StepResults + Trace

**核心逻辑**：

```python
async def execute(plan: Plan, context: EnrichedContext) -> ExecutionResult:
    results = {}
    
    # 按拓扑排序执行
    for batch in plan.topological_batches():
        # 同批次内并行
        tasks = []
        for step in batch:
            tasks.append(execute_step(step, context, results))
        
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for step, result in zip(batch, batch_results):
            if isinstance(result, Exception):
                handle_step_failure(step, result)
            else:
                results[step.id] = result
    
    return ExecutionResult(steps=results, trace=build_trace(plan, results))
```

**关键约束**：
- 每个 Step 执行前过 GCL 门禁（复用 `gcl_runner.py`）
- Safety=0 → 标记步骤为 `blocked`，不执行，通知用户
- 同 parallel_group 的步骤并行执行（asyncio.gather）
- depends_on 依赖的步骤必须全部完成且非失败
- 单个步骤超时不影响其他并行步骤
- 所有步骤结果写入 Memory Layer 1

### 2.6 RootCauseAnalyzer（根因分析器）

**输入**：StepResults

**输出**：Diagnosis

```python
@dataclass
class Diagnosis:
    root_cause: str                  # 根因描述
    confidence: float                # 置信度 0-1
    causal_chain: list[str]          # 因果链: ["慢 SQL 堆积", "连接池耗尽", "CPU 飙升"]
    evidence: list[Evidence]         # 证据列表
    suggestions: list[Suggestion]    # 建议方案
    impact_assessment: str | None    # 影响评估

@dataclass
class Evidence:
    type: str                        # chart | sql | config | log | metric
    title: str
    data: dict
    source_step: str                 # 来源步骤 ID

@dataclass
class Suggestion:
    action: str                      # 操作描述
    category: str                    # immediate | short_term | long_term
    command: str | None              # 可执行的命令
    risk: str                        # low | medium | high
    reversible: bool                 # 是否可逆
```

**根因推理规则引擎**（Phase 1 用规则，不用 LLM）：

```yaml
# 推理规则按诊断模板组织，每个模板有多条规则
rules:
  - name: slow_sql_causes_connection_spike
    conditions:
      - step: check_slow_sql
        field: count
        op: ">"
        value: 5
      - step: check_connection_trend
        field: max_value
        op: ">"
        value: 80
    conclusion: "慢 SQL 堆积导致数据库连接数上升，应用线程阻塞等待数据库响应"
    confidence: 0.7
    suggestions:
      - action: "优化慢 SQL（添加索引 / 改写查询）"
        category: short_term
      - action: "临时增加最大连接数"
        category: immediate
        risk: low

  - name: undersized_instance
    conditions:
      - step: check_instance_spec
        field: max_connections
        op: "<"
        value: "{{check_connection_trend.max_value}} * 1.2"
    conclusion: "实例规格（{{check_instance_spec.spec}}）最大连接数（{{check_instance_spec.max_connections}}）不足以支撑当前负载"
    confidence: 0.6
    suggestions:
      - action: "升级 RDS 实例规格"
        category: short_term
        risk: medium
```

**置信度计算**：
- 基础分：0.5
- 每条匹配的规则 +0.1 ~ +0.3（由规则定义）
- 证据链完整（所有依赖步骤成功） +0.1
- Memory 中有相同模式的历史记录 +0.1
- 上限 0.95（永远不为 1.0，保留不确定性）

---

## 3. Tool Registry（工具注册中心）

### 3.1 设计目标

将 53 个 `alicloud-*-ops` Skill 统一注册为可发现、可调用的 Tool，供 TaskPlanner 和外部 MCP 客户端查询。

### 3.2 Schema 定义

```python
@dataclass
class ToolSchema:
    name: str                        # "rds_describe_instance_performance"
    skill: str                       # "alicloud-rds-ops"
    operation: str                   # "DescribeDBInstancePerformance"
    description: str                 # 一句话描述
    products: list[str]              # 关联产品
    capabilities: list[str]          # 能力维度: ["monitoring", "diagnosis", "lifecycle"]
    input_schema: dict               # JSON Schema 格式的参数定义
    output_schema: dict              # 输出格式
    risk_level: str                  # read | safe_write | destructive
    wrapper_path: str                # harness-wrapper.sh 路径
    gcl_required: bool               # 是否需要 GCL 门禁
    diagnostic_keywords: list[str]   # 诊断关键词: ["连接数", "CPU", "慢SQL"]
```

### 3.3 注册来源

| 来源 | 解析方式 | 示例 |
|------|----------|------|
| SKILL.md frontmatter | YAML 解析 name, description | 每个 Skill 的基础元数据 |
| SKILL.md `## Variables` | 正则提取 `{{user.*}}` → input_schema | 参数定义 |
| SKILL.md `## Execution` | 正则提取 CLI 命令 → operation | 操作名 |
| references/api-sdk-usage.md | 正则提取 API 名 + 参数 | 完整 API 列表 |
| SKILL-MATRIX.md | 表格解析 → capabilities | 能力维度 |
| harness-wrapper.sh | 文件存在性检查 → wrapper_path | 执行路径 |

### 3.4 索引方式

```python
class ToolRegistry:
    def get_tool(name: str) -> ToolSchema: ...
    def list_by_product(product: str) -> list[ToolSchema]: ...
    def list_by_capability(capability: str) -> list[ToolSchema]: ...
    def list_by_keyword(keyword: str) -> list[ToolSchema]: ...
    def search_diagnostic(symptoms: list[str], products: list[str]) -> list[ToolSchema]: ...
    def to_openai_tools() -> list[dict]: ...       # OpenAI Function Calling 格式
    def to_anthropic_tools() -> list[dict]: ...    # Anthropic Tool Use 格式
    def to_mcp_tools() -> list[dict]: ...          # MCP tools/list 格式
```

---

## 4. 诊断模板库

### 4.1 模板结构

```yaml
# diagnostic_templates/{product}_{symptom}.yaml
name: RDS 连接数过高诊断
version: "1.0"
match:
  symptoms: ["connection_high"]
  products: ["rds"]
specificity: 10

# 诊断步骤
steps: [...]

# 根因推理规则
root_cause_rules: [...]

# 输出模板
output:
  report_template: "rds_connection_high_report.md.j2"
  notification_channels: ["wecom", "jira_comment"]
```

### 4.2 Phase 1 覆盖的诊断模板（Top 20）

| # | 模板文件 | 现象 | 涉及产品 |
|---|----------|------|----------|
| 1 | `rds_connection_high.yaml` | RDS 连接数高 | RDS, DAS, ECS |
| 2 | `rds_slow_sql.yaml` | RDS 慢 SQL 增多 | RDS, DAS |
| 3 | `rds_disk_full.yaml` | RDS 磁盘满 | RDS, DAS |
| 4 | `rds_cpu_high.yaml` | RDS CPU 高 | RDS, DAS, ECS |
| 5 | `ecs_cpu_high.yaml` | ECS CPU 高 | ECS, CMS |
| 6 | `ecs_memory_high.yaml` | ECS 内存高/OOM | ECS, CMS |
| 7 | `ecs_disk_full.yaml` | ECS 磁盘满 | ECS |
| 8 | `redis_memory_high.yaml` | Redis 内存高 | Redis |
| 9 | `redis_connection_high.yaml` | Redis 连接数高 | Redis |
| 10 | `redis_cache_miss.yaml` | Redis 缓存命中率低 | Redis |
| 11 | `slb_latency_high.yaml` | SLB 延迟高 | SLB, ECS, RDS |
| 12 | `slb_5xx.yaml` | SLB 5xx 错误增多 | SLB, ECS, SLS |
| 13 | `ack_pod_crash.yaml` | ACK Pod 异常 | ACK, SLS |
| 14 | `ack_node_pressure.yaml` | ACK 节点压力 | ACK, ECS |
| 15 | `oss_access_denied.yaml` | OSS 访问异常 | OSS, RAM |
| 16 | `mongodb_connection_high.yaml` | MongoDB 连接数高 | MongoDB |
| 17 | `elasticsearch_cluster_red.yaml` | ES 集群 Red | Elasticsearch |
| 18 | `polar_mysql_slow_query.yaml` | PolarDB 慢查询 | PolarDB MySQL, DAS |
| 19 | `fc_timeout.yaml` | 函数计算超时 | FC, SLS |
| 20 | `generic_resource_anomaly.yaml` | 通用资源异常（兜底） | 按资源 ID 推断产品 |

---

## 5. REST API 层

### 5.1 端点设计

| 方法 | 路径 | 说明 | 同步/异步 |
|------|------|------|-----------|
| `POST` | `/api/v1/diagnose` | 统一诊断入口 | 异步（202 + task_id） |
| `GET` | `/api/v1/tasks/{task_id}` | 查询任务状态 | 同步 |
| `GET` | `/api/v1/tasks/{task_id}/result` | 获取诊断结果 | 同步 |
| `POST` | `/api/v1/tasks/{task_id}/cancel` | 取消任务 | 同步 |
| `POST` | `/api/v1/check` | 健康检查（CI/CD） | 同步 |
| `GET` | `/api/v1/patrol/{scope}` | 触发巡检 | 异步 |
| `GET` | `/api/v1/health` | 服务健康状态 | 同步 |
| `GET` | `/api/v1/tools` | 查看可用能力清单 | 同步 |

### 5.2 核心端点详细规格

#### POST /api/v1/diagnose

```json
// Request
{
  "source": "alert | ticket | chat | manual",
  "source_id": "alert-001",
  "raw_input": {
    "title": "RDS rm-xxx 连接数过高",
    "description": "连接数持续 85% 超过 15 分钟",
    "severity": "critical"
  },
  "context_hints": {
    "region": "cn-hangzhou",
    "resources": ["rm-xxx"],
    "tags": {"env": "production"}
  },
  "callbacks": {
    "on_complete": {
      "type": "webhook",
      "url": "https://jira.internal/hooks/agent-runtime",
      "method": "POST",
      "headers": {"Authorization": "Bearer xxx"}
    },
    "on_hitl_required": {
      "type": "wecom",
      "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
    }
  }
}

// Response (202 Accepted)
{
  "task_id": "task-20260717-abc123",
  "status": "accepted",
  "estimated_duration": "30s",
  "poll_url": "/api/v1/tasks/task-20260717-abc123"
}
```

#### GET /api/v1/tasks/{task_id}/result

```json
// Response (任务完成后)
{
  "task_id": "task-20260717-abc123",
  "status": "completed",
  "created_at": "2026-07-17T03:00:00Z",
  "completed_at": "2026-07-17T03:00:28Z",
  "duration_seconds": 28.3,
  "result": {
    "root_cause": "慢 SQL `SELECT * FROM orders WHERE status='pending'` 缺少索引导致连接堆积，应用连接池 maxActive=200 超过 RDS 规格支持的 150",
    "confidence": 0.92,
    "causal_chain": [
      "慢 SQL 执行时间 > 3s",
      "连接池连接无法释放",
      "数据库连接数达到上限 85%"
    ],
    "evidence": [
      {
        "type": "metric",
        "title": "RDS 连接数趋势",
        "data": {"max": 85.2, "avg": 72.1, "duration": "15m"},
        "source_step": "check_connection_trend"
      },
      {
        "type": "sql",
        "title": "慢 SQL Top 1",
        "data": {"sql": "SELECT * FROM orders WHERE status='pending'", "avg_time": "3.2s", "rows_examined": 500000},
        "source_step": "check_slow_sql"
      }
    ],
    "suggestions": [
      {
        "action": "添加索引: CREATE INDEX idx_orders_status ON orders(status)",
        "category": "immediate",
        "risk": "low",
        "reversible": true
      },
      {
        "action": "降低应用连接池 maxActive 从 200 到 120",
        "category": "short_term",
        "risk": "medium",
        "reversible": true
      }
    ],
    "impact_assessment": "约 500 用户订单页面超时，持续 15 分钟",
    "hitl_required": false
  },
  "trace_id": "langfuse-trace-abc123",
  "token_usage": 4520
}
```

#### POST /api/v1/check（CI/CD 健康检查）

```json
// Request
{
  "source": "ci-cd",
  "pipeline_id": "pipeline-123",
  "service": "order-service",
  "version": "abc1234",
  "checks": ["post_deploy_health"],
  "baseline_duration": "30m"
}

// Response (200 OK — 同步)
{
  "status": "pass",
  "checks": [
    {"name": "slb_health", "status": "pass", "detail": "所有后端正常"},
    {"name": "error_rate", "status": "pass", "detail": "5xx 比例 0.02% (< 0.1%)"},
    {"name": "latency_baseline", "status": "warn", "detail": "P99 延迟 +25% (50ms → 62ms)"},
    {"name": "slow_sql", "status": "pass", "detail": "慢 SQL 数量无变化"}
  ],
  "summary": "3 pass, 1 warn, 0 fail — 建议人工确认延迟变化后继续"
}
```

### 5.3 认证

- Header: `Authorization: Bearer <API_KEY>`
- API Key 通过环境变量 `AGENT_RUNTIME_API_KEY` 配置
- 可选：HMAC 签名（Phase 2）

---

## 6. MCP Server 层

### 6.1 暴露的 Tools

```python
MCP_TOOLS = [
    {
        "name": "diagnose",
        "description": "阿里云资源智能诊断。输入问题描述或资源ID，自动执行多维度检查并返回根因分析。支持 RDS/ECS/Redis/SLB/ACK 等产品。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "诊断请求。例如: 'RDS rm-xxx 连接数高，持续15分钟' 或 '订单服务响应慢，帮我排查'"
                },
                "resources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选：明确指定要检查的资源 ID 列表"
                },
                "region": {
                    "type": "string",
                    "description": "可选：指定地域，默认从环境变量读取"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "run_patrol",
        "description": "运行日常巡检：检查资源到期时间、容量趋势、安全基线、成本异常。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["production", "staging", "all"],
                    "default": "production"
                },
                "checks": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["resource_expiry", "capacity_trend", "security_baseline", "cost_anomaly", "backup_status"]},
                    "description": "可选：指定巡检项，默认全部"
                }
            }
        }
    },
    {
        "name": "post_deploy_check",
        "description": "发版后健康检查：对比发版前后的 SLB 延迟、错误率、慢 SQL、资源使用率等关键指标。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "服务名称"},
                "version": {"type": "string", "description": "发版版本号（Git commit SHA）"},
                "baseline_duration": {"type": "string", "default": "30m", "description": "基线对比时间窗口，如 30m, 1h"}
            },
            "required": ["service"]
        }
    }
]
```

### 6.2 流式输出（SSE）

```json
// MCP Client 连接后，调用 diagnose tool 时的 SSE 事件流：

{"type": "progress", "step": "intent_parsing", "status": "running", "message": "正在解析意图..."}
{"type": "progress", "step": "intent_parsing", "status": "done", "result": {"products": ["rds"], "symptoms": ["connection_high"], "severity": "critical"}}

{"type": "progress", "step": "context_enrichment", "status": "running", "message": "正在补充资源上下文..."}
{"type": "progress", "step": "context_enrichment", "status": "done", "result": {"owner": "zhangsan", "service": "order-service"}}

{"type": "progress", "step": "planning", "status": "running", "message": "匹配诊断模板: rds_connection_high"}
{"type": "progress", "step": "planning", "status": "done", "result": {"template": "rds_connection_high", "steps": 5}}

{"type": "progress", "step": "check_connection_trend", "status": "running", "message": "正在查询 RDS 连接数趋势..."}
{"type": "progress", "step": "check_slow_sql", "status": "running", "message": "正在分析慢 SQL..."}
{"type": "progress", "step": "check_instance_spec", "status": "running", "message": "正在获取实例规格..."}

{"type": "progress", "step": "check_connection_trend", "status": "done", "result": {"max": 85.2, "avg": 72.1}}
{"type": "progress", "step": "check_slow_sql", "status": "done", "result": {"count": 3, "top_sql": "SELECT * FROM orders WHERE status='pending'"}}
{"type": "progress", "step": "check_instance_spec", "status": "done", "result": {"spec": "rds.mysql.s2.large", "max_connections": 150}}

{"type": "progress", "step": "root_cause", "status": "running", "message": "正在交叉分析根因..."}
{"type": "result", "status": "done", "result": {"root_cause": "...", "confidence": 0.92, "suggestions": [...]}}
```

### 6.3 渐进式加载

| 阶段 | 加载内容 | Token 估算 |
|------|----------|-----------|
| 初始化 | 3 个 tool 的 name + description | ~300 tokens |
| LLM 选择 tool | 该 tool 的完整 inputSchema | ~200 tokens |
| 执行中 | 按需加载具体 Skill 的 SKILL.md | < 5,000 tokens/skill |
| 执行中 | 按需加载 references/ | 按需 |

---

## 7. Session Context（会话上下文）

### 7.1 设计目标

跨多次 API 调用 / MCP tool 调用保持诊断上下文，支持：
- 暂停/恢复诊断
- 多轮对话中逐步补充信息
- 同一会话内的资源共享

### 7.2 状态模型

```python
@dataclass
class Session:
    session_id: str                  # UUID
    created_at: datetime
    updated_at: datetime
    status: str                      # active | paused | completed | expired
    context: EnrichedContext         # 累积的上下文
    history: list[Exchange]          # 交互历史

@dataclass
class Exchange:
    role: str                        # user | agent
    content: str
    timestamp: datetime
    intent: Intent | None
    diagnosis: Diagnosis | None
```

### 7.3 存储

- 本地文件：`.runtime/sessions/{session_id}.json`
- TTL：默认 24 小时，可配置
- 不引入外部数据库

---

## 8. 输出适配层

### 8.1 输出通道

| 通道 | 触发条件 | 格式 |
|------|----------|------|
| **诊断报告** | 所有诊断完成 | Markdown 结构化报告 |
| **工单回写** | source=ticket 且配置了 callback | Jira API（评论 + 状态更新） |
| **IM 推送** | 配置了 wecom/dingtalk webhook | 卡片消息（摘要 + 详情链接） |
| **CI 回调** | source=ci-cd | JSON（pass/warn/fail + 详情） |
| **Webhook** | 配置了自定义 callback URL | JSON POST |

### 8.2 诊断报告模板

```markdown
# 诊断报告: RDS rm-xxx 连接数过高

**诊断时间**: 2026-07-17 03:00:28
**严重级别**: 🔴 Critical
**置信度**: 92%

---

## 根因

慢 SQL `SELECT * FROM orders WHERE status='pending'` 缺少索引，导致每次查询扫描 50 万行数据，平均耗时 3.2s。应用连接池配置 maxActive=200，但 RDS 实例规格仅支持 150 最大连接数。慢 SQL 占用连接不释放 → 连接池耗尽 → 新请求等待 → 数据库连接数达到 85%。

## 因果链

1. 慢 SQL 执行时间 > 3s → 数据库连接长时间占用
2. 连接池 200 > 实例上限 150 → 连接排队
3. 15 分钟内连接数从 60% 升至 85%

## 证据

| 维度 | 数据 | 来源 |
|------|------|------|
| 连接数趋势 | 峰值 85.2%，持续 15 分钟 | RDS 监控 |
| 慢 SQL Top 1 | `SELECT * FROM orders WHERE status='pending'` 平均 3.2s | DAS 慢日志 |
| 实例规格 | rds.mysql.s2.large, 最大连接数 150 | RDS 实例信息 |

## 建议

| 优先级 | 操作 | 风险 | 可逆 |
|--------|------|------|------|
| 🔴 立即 | 添加索引: `CREATE INDEX idx_orders_status ON orders(status)` | 低 | 是 |
| 🟡 短期 | 降低连接池 maxActive 200 → 120 | 中 | 是 |
| 🟢 长期 | 升级实例规格至 rds.mysql.c1.large | 中 | 否 |

## 影响评估

约 500 用户订单页面超时，持续 15 分钟。预估损失 ¥12,000。

---

*诊断耗时: 28.3s | Trace: langfuse-trace-abc123*
```

---

## 9. 与现有系统的集成

### 9.1 复用清单

| 现有组件 | 复用方式 |
|----------|----------|
| SKILL.md × 53 | Tool Registry 的数据源 |
| harness-wrapper.sh × 39 | ExecutionEngine 的执行入口 |
| gcl_runner.py | 每个 Step 执行前的 GCL 门禁 |
| harness-core-lib.sh | Langfuse trace、metrics |
| .runtime/memory/ | Memory Layer 1（执行记录） |
| .runtime/reflexion/ | Memory Layer 2（失败模式） |
| .runtime/traces/ | 本地 trace 存储 |
| scripts/validate_all_skills.py | Tool Registry 的数据校验 |

### 9.2 不修改的

- SKILL.md 格式不变
- harness-wrapper.sh 接口不变
- gcl_runner.py CLI 接口不变
- 现有目录结构不变

---

## 10. 非功能需求

| 需求 | 标准 |
|------|------|
| **可用性** | REST API 和 MCP Server 各自独立启动，一个挂不影响另一个 |
| **性能** | 单次诊断（不含 LLM）< 30 秒；并行步骤最大 5 个 |
| **可靠性** | 单个 Step 失败不阻断其他并行 Step；富化失败降级继续 |
| **可观测性** | 每次诊断：Langfuse Trace + 本地 JSON trace + token 用量 |
| **安全性** | GCL 门禁每步执行；凭证不泄露；API Key 认证 |
| **兼容性** | Python 3.10+；macOS / Linux |
