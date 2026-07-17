# Phase 1 PLAN — 核心诊断引擎 + 双模式接入

> **版本**: v1.0
> **状态**: 设计中
> **最后更新**: 2026-07-17
> **关联**: [架构总览](../ARCHITECTURE.md) | [Phase 1 SPEC](../specs/phase-1-core-engine.md)

---

## 1. 任务总览

### 1.1 一句话目标

在 3 个月内，从 0 到 1 构建一个可工作的 Agent Runtime：能接收告警/工单/自然语言，自动诊断、给出根因，并通过 REST API 和 MCP Server 对外服务。

### 1.2 任务清单

| # | 任务 | 预估工时 | 依赖 | 优先级 |
|---|------|----------|------|--------|
| T1 | Tool Registry + Skill Schema 解析 | 5 天 | 无 | P0 |
| T2 | IntentParser + 现象词典 | 5 天 | 无 | P0 |
| T3 | ContextEnricher | 3 天 | T1 | P1 |
| T4 | 诊断模板引擎 + Top 10 模板 | 7 天 | T1, T2 | P0 |
| T5 | ExecutionEngine + GCL 集成 | 7 天 | T1, T4 | P0 |
| T6 | RootCauseAnalyzer + 推理规则引擎 | 5 天 | T5 | P1 |
| T7 | Session Context | 3 天 | T5 | P2 |
| T8 | 输出适配层（报告/IM/工单/CI） | 5 天 | T6 | P1 |
| T9 | REST API 层 | 5 天 | T5, T6 | P0 |
| T10 | MCP Server 层 | 5 天 | T5, T6 | P0 |
| T11 | 集成测试 + E2E 验证 | 5 天 | T9, T10 | P0 |
| T12 | 文档 + 示例 | 3 天 | T9, T10 | P2 |

**总计**: 约 58 人天（3 人月，按 20 天/月）

---

## 2. 任务详细分解

### T1: Tool Registry + Skill Schema 解析

**目标**：将 53 个 Skill 统一注册为可查询的 Tool Schema。

**子任务**：
- [ ] T1.1 设计 ToolSchema 数据模型（Python dataclass）
- [ ] T1.2 实现 SKILL.md 解析器（frontmatter + Variables + Execution）
- [ ] T1.3 实现 SKILL-MATRIX.md 解析器（capability 维度）
- [ ] T1.4 实现 wrapper 存在性检测
- [ ] T1.5 实现多维度索引（by product / by capability / by keyword）
- [ ] T1.6 实现 Schema 导出（OpenAI / Anthropic / MCP 格式）
- [ ] T1.7 编写单元测试（覆盖所有 53 个 Skill）

**验证标准**：
```bash
# 所有 Skill 解析成功，无异常
python3 -m pytest agent_runtime/core/tests/test_registry.py -v

# 查询能力
python3 -c "
from agent_runtime.core.registry import ToolRegistry
r = ToolRegistry('.')
assert len(r.list_by_product('rds')) >= 3
assert len(r.list_by_capability('monitoring')) >= 10
assert len(r.list_by_keyword('连接数')) >= 2
print('OK')
"
```

**涉及文件**：
- `agent_runtime/core/registry.py`（新增）
- `agent_runtime/core/schema.py`（新增）
- `agent_runtime/core/tests/test_registry.py`（新增）

---

### T2: IntentParser + 现象词典

**目标**：从任意文本中提取产品、资源 ID、现象、严重级别。

**子任务**：
- [ ] T2.1 定义 Intent / Symptom 数据模型
- [ ] T2.2 实现产品识别（关键词 + 资源 ID 正则）
- [ ] T2.3 实现现象分类（现象词典匹配）
- [ ] T2.4 实现严重级别识别
- [ ] T2.5 实现量化指标提取（数字 + 单位）
- [ ] T2.6 编写现象词典（覆盖 20 种常见现象）
- [ ] T2.7 编写单元测试

**验证标准**：
```bash
python3 -c "
from agent_runtime.core.intent_parser import IntentParser
p = IntentParser()

# 测试告警输入
intent = p.parse('RDS rm-xxx 连接数 85%，持续 15 分钟，P1 紧急')
assert intent.products == ['rds']
assert intent.resource_ids == ['rm-xxx']
assert 'connection_high' in [s.category for s in intent.symptoms]
assert intent.severity == Severity.CRITICAL

# 测试自然语言输入
intent = p.parse('订单服务最近响应很慢，帮我看看')
assert 'network_latency' in [s.category for s in intent.symptoms]

print('OK')
"
```

**涉及文件**：
- `agent_runtime/core/intent_parser.py`（新增）
- `agent_runtime/core/symptom_dict.yaml`（新增，现象词典）
- `agent_runtime/core/tests/test_intent_parser.py`（新增）

---

### T3: ContextEnricher

**目标**：为 Intent 补充运行时上下文（标签、负责人、关联服务、最近变更）。

**子任务**：
- [ ] T3.1 实现资源标签查询（aliyun tag API）
- [ ] T3.2 实现资源详情查询（各产品 Describe API）
- [ ] T3.3 实现最近变更查询（ActionTrail LookupEvents）
- [ ] T3.4 实现失败降级策略（富化失败不阻断诊断）
- [ ] T3.5 编写单元测试（mock API 响应）

**验证标准**：
```bash
python3 -m pytest agent_runtime/core/tests/test_context_enricher.py -v

# 确认富化失败不抛异常
python3 -c "
from agent_runtime.core.context_enricher import ContextEnricher
# 模拟 API 不可用
enricher = ContextEnricher(api_available=False)
result = enricher.enrich(intent)
assert result.resource_owners == {}  # 降级为空
assert result.region is not None     # region 必须有
print('OK')
"
```

**涉及文件**：
- `agent_runtime/core/context_enricher.py`（新增）
- `agent_runtime/core/tests/test_context_enricher.py`（新增）

---

### T4: 诊断模板引擎 + Top 10 模板

**目标**：实现诊断模板的加载、匹配、实例化，并编写 Top 10 模板。

**子任务**：
- [ ] T4.1 设计诊断模板 YAML Schema
- [ ] T4.2 实现模板加载器（从 diagnostic_templates/ 目录加载）
- [ ] T4.3 实现模板匹配算法（symptom + product + specificity 评分）
- [ ] T4.4 实现模板实例化（占位符替换 → DAG Plan）
- [ ] T4.5 编写 Top 10 诊断模板
  - [ ] rds_connection_high.yaml
  - [ ] rds_slow_sql.yaml
  - [ ] rds_cpu_high.yaml
  - [ ] ecs_cpu_high.yaml
  - [ ] ecs_memory_high.yaml
  - [ ] redis_memory_high.yaml
  - [ ] slb_latency_high.yaml
  - [ ] ack_pod_crash.yaml
  - [ ] mongodb_connection_high.yaml
  - [ ] generic_resource_anomaly.yaml（兜底）
- [ ] T4.6 编写单元测试

**验证标准**：
```bash
# 模板加载
python3 -c "
from agent_runtime.core.task_planner import TaskPlanner
p = TaskPlanner('diagnostic_templates/')
templates = p.list_templates()
assert len(templates) >= 10
print(f'{len(templates)} templates loaded')
"

# 模板匹配
python3 -c "
plan = p.plan(intent)  # intent 来自 T2
assert plan.template_name is not None
assert len(plan.steps) >= 3
print(f'Matched: {plan.template_name}, {len(plan.steps)} steps')
"
```

**涉及文件**：
- `agent_runtime/core/task_planner.py`（新增）
- `diagnostic_templates/*.yaml`（新增，10 个模板文件）
- `agent_runtime/core/tests/test_task_planner.py`（新增）

---

### T5: ExecutionEngine + GCL 集成

**目标**：按 DAG 计划调度 Skill 执行，并行/串行，过 GCL 门禁。

**子任务**：
- [ ] T5.1 实现 DAG 拓扑排序（识别并行组）
- [ ] T5.2 实现 asyncio 并行执行（同组 fan-out）
- [ ] T5.3 集成 gcl_runner.py（每个 Step 执行前过 GCL）
- [ ] T5.4 集成 harness-wrapper.sh（执行入口）
- [ ] T5.5 实现超时控制
- [ ] T5.6 实现失败策略（skip / abort / retry）
- [ ] T5.7 实现 Memory Layer 1 写入
- [ ] T5.8 实现 Langfuse Trace 集成
- [ ] T5.9 编写单元测试 + 集成测试

**验证标准**：
```bash
# 单元测试
python3 -m pytest agent_runtime/core/tests/test_execution_engine.py -v

# 集成测试（dry-run 模式，不实际调用云 API）
python3 -m pytest agent_runtime/core/tests/test_execution_engine_integration.py -v

# 验证并行执行
# 同 parallel_group 的步骤应同时启动（时间戳差值 < 1s）
```

**涉及文件**：
- `agent_runtime/core/execution_engine.py`（新增）
- `agent_runtime/core/gcl_gate.py`（新增，封装 gcl_runner.py）
- `agent_runtime/core/tests/test_execution_engine.py`（新增）

---

### T6: RootCauseAnalyzer + 推理规则引擎

**目标**：交叉分析多步骤结果，推导因果链，计算置信度。

**子任务**：
- [ ] T6.1 实现推理规则引擎（YAML 规则 → Python 条件评估）
- [ ] T6.2 实现置信度计算模型
- [ ] T6.3 实现证据链组装
- [ ] T6.4 实现建议生成
- [ ] T6.5 为 Top 10 模板编写推理规则
- [ ] T6.6 编写单元测试

**验证标准**：
```bash
python3 -m pytest agent_runtime/core/tests/test_root_cause.py -v

# 验证推理结果
python3 -c "
result = analyzer.analyze(step_results)
assert result.confidence > 0.5
assert len(result.causal_chain) > 0
assert len(result.evidence) > 0
assert len(result.suggestions) > 0
print(f'Root cause: {result.root_cause}')
print(f'Confidence: {result.confidence}')
"
```

**涉及文件**：
- `agent_runtime/core/root_cause.py`（新增）
- `agent_runtime/core/inference_engine.py`（新增）
- `agent_runtime/core/tests/test_root_cause.py`（新增）

---

### T7: Session Context

**目标**：跨多次 API 调用保持诊断上下文，支持暂停/恢复。

**子任务**：
- [ ] T7.1 实现 Session 数据模型
- [ ] T7.2 实现 Session 持久化（文件 JSON）
- [ ] T7.3 实现 Session TTL 管理
- [ ] T7.4 编写单元测试

**验证标准**：
```bash
python3 -m pytest agent_runtime/core/tests/test_session.py -v

# 验证会话持久化
python3 -c "
session = SessionStore.create()
session.context = some_context
SessionStore.save(session)

loaded = SessionStore.load(session.session_id)
assert loaded.context == some_context
print('OK')
"
```

**涉及文件**：
- `agent_runtime/core/session.py`（新增）
- `agent_runtime/core/tests/test_session.py`（新增）

---

### T8: 输出适配层

**目标**：将诊断结果格式化为报告、回写工单、推送 IM、CI 回调。

**子任务**：
- [ ] T8.1 实现诊断报告模板（Jinja2 → Markdown）
- [ ] T8.2 实现工单回写适配器（Jira API）
- [ ] T8.3 实现 IM 推送适配器（企微/钉钉 Webhook）
- [ ] T8.4 实现 CI 回调适配器（JSON exit code）
- [ ] T8.5 实现 Webhook 回调管理
- [ ] T8.6 编写单元测试

**验证标准**：
```bash
python3 -m pytest agent_runtime/core/tests/test_output.py -v

# 验证报告生成
python3 -c "
report = OutputAdapter.to_report(diagnosis)
assert '根因' in report
assert '建议' in report
print(report[:200])
"
```

**涉及文件**：
- `agent_runtime/core/output_adapter.py`（新增）
- `agent_runtime/core/templates/report.md.j2`（新增）
- `agent_runtime/core/callbacks.py`（新增）
- `agent_runtime/core/tests/test_output.py`（新增）

---

### T9: REST API 层

**目标**：实现 REST API 端点，对外提供诊断服务。

**子任务**：
- [ ] T9.1 FastAPI 应用骨架
- [ ] T9.2 实现 POST /api/v1/diagnose（异步）
- [ ] T9.3 实现 GET /api/v1/tasks/{task_id}
- [ ] T9.4 实现 GET /api/v1/tasks/{task_id}/result
- [ ] T9.5 实现 POST /api/v1/check（同步）
- [ ] T9.6 实现 GET /api/v1/health
- [ ] T9.7 实现 GET /api/v1/tools
- [ ] T9.8 实现 API Key 认证
- [ ] T9.9 实现异步任务管理（内存队列）
- [ ] T9.10 实现回调触发（任务完成时）
- [ ] T9.11 编写集成测试

**验证标准**：
```bash
# 启动服务
agent-runtime serve --mode rest --port 8080 &

# 健康检查
curl http://localhost:8080/api/v1/health
# {"status": "ok"}

# 诊断请求
curl -X POST http://localhost:8080/api/v1/diagnose \
  -H "Authorization: Bearer test-key" \
  -H "Content-Type: application/json" \
  -d '{"source":"manual","raw_input":{"title":"RDS rm-xxx CPU高"}}'
# {"task_id": "...", "status": "accepted"}

# 查询结果
curl http://localhost:8080/api/v1/tasks/{task_id}/result
# {"status": "completed", "result": {...}}

kill %1
```

**涉及文件**：
- `agent_runtime/rest/server.py`（新增）
- `agent_runtime/rest/routes/*.py`（新增）
- `agent_runtime/rest/tests/test_api.py`（新增）

---

### T10: MCP Server 层

**目标**：实现 MCP Server，暴露 tools 给 LLM Agent。

**子任务**：
- [ ] T10.1 FastMCP Server 骨架
- [ ] T10.2 实现 `diagnose` tool
- [ ] T10.3 实现 `run_patrol` tool
- [ ] T10.4 实现 `post_deploy_check` tool
- [ ] T10.5 实现 SSE 流式输出
- [ ] T10.6 实现渐进式加载（Tool Registry → MCP tools）
- [ ] T10.7 编写集成测试

**验证标准**：
```bash
# 启动 MCP Server
agent-runtime serve --mode mcp --port 5000 &

# 验证 tools/list
curl -X POST http://localhost:5000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
# 返回 3 个 tool

# 验证 tool 调用
curl -X POST http://localhost:5000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"diagnose","arguments":{"query":"RDS rm-xxx 慢"}},"id":2}'
# SSE 流式返回诊断过程

kill %1
```

**涉及文件**：
- `agent_runtime/mcp/server.py`（新增）
- `agent_runtime/mcp/tools.py`（新增）
- `agent_runtime/mcp/streaming.py`（新增）
- `agent_runtime/mcp/tests/test_mcp.py`（新增）

---

### T11: 集成测试 + E2E 验证

**目标**：端到端验证整个诊断流程。

**子任务**：
- [ ] T11.1 编写 E2E 测试用例（告警 → 诊断 → 结果）
- [ ] T11.2 编写 E2E 测试用例（工单 → 诊断 → 回写）
- [ ] T11.3 编写 E2E 测试用例（对话 → 诊断 → 报告）
- [ ] T11.4 编写 E2E 测试用例（CI/CD → 健康检查）
- [ ] T11.5 验证 REST API 和 MCP Server 诊断结果一致性
- [ ] T11.6 验证并行执行正确性
- [ ] T11.7 验证 GCL 门禁正常工作
- [ ] T11.8 验证 Memory 写入
- [ ] T11.9 验证 Langfuse Trace 写入
- [ ] T11.10 性能测试（诊断耗时 < 30s）

**验证标准**：
```bash
# 全量 E2E 测试
python3 -m pytest tests/e2e/ -v

# 性能测试
python3 -m pytest tests/e2e/test_performance.py -v
# assert duration < 30

# 一致性测试
python3 tests/e2e/test_dual_mode_consistency.py
# REST 和 MCP 诊断结果一致
```

**涉及文件**：
- `tests/e2e/*.py`（新增）

---

### T12: 文档 + 示例

**目标**：编写用户文档和使用示例。

**子任务**：
- [ ] T12.1 更新 ARCHITECTURE.md（Phase 1 完成后标记状态）
- [ ] T12.2 编写快速开始指南
- [ ] T12.3 编写 REST API 文档（OpenAPI 自动生成 + 补充说明）
- [ ] T12.4 编写 MCP Server 接入指南（Claude Code / Cursor 配置示例）
- [ ] T12.5 编写诊断模板编写指南
- [ ] T12.6 编写 5 个常见场景的 Worked Example

**涉及文件**：
- `docs/quickstart.md`（新增）
- `docs/mcp-integration.md`（新增）
- `docs/diagnostic-template-guide.md`（新增）

---

## 3. 依赖关系图

```
T1 (Registry) ────┬──▶ T3 (Context) ──────────────────────────────┐
                  │                                                  │
                  ├──▶ T4 (Templates) ──▶ T5 (Engine) ──▶ T6 (RCA) ─┤
                  │                         │            │           │
T2 (Intent) ─────┘                         │            │           │
                                            │            │           │
                                            ▼            ▼           ▼
                                     T7 (Session)  T8 (Output) ──────┤
                                                                      │
                                            ┌─────────────────────────┘
                                            ▼
                                     T9 (REST API) ──┐
                                                      ├──▶ T11 (Tests)
                                     T10 (MCP) ──────┘
                                                              │
                                                              ▼
                                                       T12 (Docs)
```

**并行开发建议**：
- Week 1-2: T1 + T2 并行（无依赖）
- Week 2-3: T3 + T4 并行（依赖 T1, T2 完成）
- Week 3-5: T5（核心，需要 T1, T4 完成）
- Week 5-6: T6 + T7 + T8 并行（依赖 T5）
- Week 6-8: T9 + T10 并行（依赖 T5, T6）
- Week 8-10: T11（依赖 T9, T10）
- Week 10-12: T12 + 修复 + 缓冲

---

## 4. 风险与缓解

| 风险 | 影响 | 概率 | 缓解 |
|------|------|------|------|
| harness-wrapper.sh 接口不稳定 | T5 集成失败 | 低 | 已有 39 个 wrapper，接口成熟 |
| 诊断模板覆盖不足 | 匹配不到模板时降级为通用模式 | 中 | T4 包含兜底模板 |
| GCL runner 性能瓶颈 | 每步都过 GCL，总耗时过长 | 中 | 只读操作跳过 GCL（已有分类） |
| 阿里云 API 限流 | 并行步骤触发限流 | 低 | 控制最大并行度 ≤ 5 |
| 富化数据源不可用 | 标签/变更信息缺失 | 中 | 降级策略：缺失信息标记 unknown |
| Token 消耗过高 | LLM Agent 使用 MCP 时消耗大 | 低 | 渐进式加载 + tool description 精简 |

---

## 5. 技术栈确认

| 组件 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | 3.10+ |
| REST 框架 | FastAPI | latest |
| ASGI 服务器 | uvicorn | latest |
| MCP 框架 | FastMCP | latest |
| 模板引擎 | Jinja2 | latest |
| 测试框架 | pytest | latest |
| 代码质量 | ruff | latest |
| 配置格式 | YAML | — |
| 异步 | asyncio (stdlib) | — |

---

## 6. 里程碑

| 里程碑 | 时间 | 交付物 | 验证方式 |
|--------|------|--------|----------|
| M1: 引擎可用 | Week 6 | IntentParser + TaskPlanner + ExecutionEngine + 5 个模板 | 单元测试全部通过 + dry-run E2E |
| M2: 双模式可用 | Week 9 | REST API + MCP Server | curl 可调用 diagnose |
| M3: 交付就绪 | Week 12 | Top 10 模板 + E2E 测试 + 文档 | E2E 全绿 + 性能达标 |
