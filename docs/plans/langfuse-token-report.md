# PLAN: 实现 Langfuse Token 报表

> **关联 SPEC**: [langfuse-token-report.md](./langfuse-token-report.md)
> **实施日期**: 2026-07-30

---

## 任务分解

### Phase 1: 脚本实现（TDD 优先）

#### Task 1.1: 骨架与凭证加载
- 创建 `scripts/langfuse_token_report.py`
- 实现 `load_credentials()` 函数：从 `.env` 或环境变量读取
- **RED**: 测试缺少凭证时返回 `[BLOCKED:no-credentials]` 退出码 1
- **GREEN**: 实现凭证加载
- **REFACTOR**: 复用 `test-langfuse-reporting.sh` 的加载模式

#### Task 1.2: Langfuse API 客户端
- 实现 `LangfuseClient` 类：
  - `fetch_traces(start, end, page, limit)` 方法
  - 内置分页迭代（自动处理 `meta.totalPages`）
  - HTTP Basic Auth
  - 重试逻辑：3 次指数退避
- **RED**: 测试认证失败返回错误码 3
- **GREEN**: 实现拉取逻辑
- **REFACTOR**: 抽出 base64 编码逻辑

#### Task 1.3: 聚合逻辑
- 实现 `aggregate_by_session(traces)` 函数
- 仅保留 `metadata.has_llm_usage=true` 的 trace
- 按 `metadata.session_id` 聚合 prompt/completion/total
- 计算 trace_count, skill_count, first/last trace time
- **RED**: 测试空输入、空 token、跨 session 聚合
- **GREEN**: 实现聚合

#### Task 1.4: 输出渲染
- 实现 `_render_table(report)` 函数
- 实现 `_render_json(report)` 函数
- 实现 `cmd_pull(args)` 主入口
- **RED**: 测试表格 / JSON 输出格式
- **GREEN**: 实现输出

#### Task 1.5: 单 sessionID 详情命令
- 实现 `cmd_session(args)` 函数
- 拉取该 sessionID 的所有 trace
- 输出明细列表
- **RED/GREEN**: TDD

### Phase 2: Makefile 集成

#### Task 2.1: 添加 Makefile 入口
- 在 `Makefile` 增加 `langfuse-token-report` 指令
- 支持 `SINCE_DAYS` 参数
- 从 `.env` 加载凭证（与 `test-langfuse-reporting.sh` 一致）

### Phase 3: 测试

#### Task 3.1: 单元测试
- 创建 `scripts/test_langfuse_token_report.py`
- 覆盖：凭证加载、聚合逻辑、输出渲染、错误处理
- 使用 `urllib.request` mock 而非真实网络

#### Task 3.2: 集成测试
- 真实拉取 Langfuse 数据（需要凭证）
- 验证输出与本地数据一致

### Phase 4: 文档

#### Task 4.1: 用户手册
- 在 `docs/chat-context-tracing-user-guide.md` 增加 4.6 节：
  - `make langfuse-token-report` 用法
  - CLI 参数说明
- 在 `scripts/test-langfuse-reporting.sh` 注释中互相引用

#### Task 4.2: 设计文档
- 在 `harness-session-trace-system-design.md` 增加决策 7：
  - 决策：双数据源（本地 + Langfuse）
  - 理由：覆盖不同场景

---

## 风险与依赖

| 风险 | 缓解 |
|------|------|
| Langfuse API rate limit | 内置重试 + 指数退避 |
| 用户缺失凭证 | `[BLOCKED:no-credentials]` 优雅降级 |
| 网络不可达 | 重试 3 次后失败退出码 2 |
| 元数据缺失 session_id | 归类为 `(no-session)` 桶，不丢失 |

---

## 验证清单

- [ ] 单元测试通过
- [ ] `make langfuse-token-report SINCE_DAYS=1` 在有凭证环境成功拉取
- [ ] 缺失凭证时输出 `BLOCKED:no-credentials` 而不报错
- [ ] 表格输出对齐美观（< 100 session）
- [ ] JSON 输出符合 Spec §3.2
