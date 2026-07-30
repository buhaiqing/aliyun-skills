# SPEC: 从 Langfuse 拉取指定时段各 sessionID 的 Token 消耗报表

> **状态**: Draft  
> **创建日期**: 2026-07-30  
> **适用范围**: 阿里云 Skills 项目的运营/账单场景

---

## 1. 背景与问题

当前 `scripts/token_rollup.py` 仅能从**本地** `.runtime/traces/` 目录读取 GCL trace 并统计 token 消耗。但有以下场景需要**远程** Langfuse 上的数据：

| 场景 | 本地数据 | Langfuse 数据 |
|------|----------|---------------|
| 单机 CLI 实时分析 | ✅ | ❌ |
| 跨机器聚合 | ❌ | ✅ |
| 跨 session 报表 | 部分 | ✅ |
| 账单核对/审计 | ❌ | ✅ |
| 长期存档 | ❌（TTL 7 天） | ✅ |

**问题**：运维/财务只能登录 Langfuse UI 手动查看，没有可复用的命令行报表与跨 sessionID 聚合能力。

---

## 2. 目标

提供 Makefile 指令 `make langfuse-token-report SINCE_DAYS=7`，从 Langfuse 拉取**指定时段**的 trace，按 **sessionID** 维度聚合 **prompt/completion/total token** 消耗，输出表格 + JSON 两种格式。

### 2.1 使用场景

```bash
# 最近 7 天各 sessionID 消耗
make langfuse-token-report SINCE_DAYS=7

# 指定起止日期
python3 scripts/langfuse_token_report.py pull \
    --from 2026-07-01 --to 2026-07-30 \
    --output report.json

# 单 sessionID 详情
python3 scripts/langfuse_token_report.py session \
    --session-id sess-claude-abc123
```

### 2.2 非目标（Out of Scope）

- 不实现 Langfuse **写入**（仍由 `gcl_runner.py` 完成）
- 不实现 Langfuse Dashboard 渲染（仅输出 CLI 表格）
- 不实现实时 streaming（一次性 HTTP 拉取 + 分页）
- 不实现成本核算（仅 token 计数）

---

## 3. 数据契约

### 3.1 输入（CLI 参数）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--since-days N` | int | 否 | 最近 N 天（默认 7） |
| `--from YYYY-MM-DD` | str | 否 | 起始日期（含），与 `--to` 配合 |
| `--to YYYY-MM-DD` | str | 否 | 结束日期（含），与 `--from` 配合 |
| `--output PATH` | path | 否 | 输出 JSON 文件（默认 stdout） |
| `--format` | enum | 否 | `table`（默认）/ `json` / `csv` |
| `--limit N` | int | 否 | 单次分页拉取（默认 100，最大 100） |

### 3.2 输出 Schema

**表格（默认）**：

```text
=== Langfuse Token Consumption Report ===
Period: 2026-07-23 → 2026-07-30 (7 days)
Total Sessions: 12   Total Tokens: 245,680
─────────────────────────────────────────────────────────────────────────────
Session ID                   Traces  Prompt    Completion  Total       User
─────────────────────────────────────────────────────────────────────────────
sess-claude-abc123             42    120,500    8,200      128,700    alice
sess-trae-xyz789                8     30,200    1,500       31,700    bob
...
─────────────────────────────────────────────────────────────────────────────
```

**JSON**：

```json
{
  "version": "1.0.0",
  "period": {"from": "2026-07-23", "to": "2026-07-30", "days": 7},
  "summary": {
    "total_sessions": 12,
    "total_traces": 150,
    "total_prompt_tokens": 180000,
    "total_completion_tokens": 56000,
    "total_tokens": 236000
  },
  "sessions": [
    {
      "session_id": "sess-claude-abc123",
      "user_id": "alice",
      "trace_count": 42,
      "skill_count": 8,
      "prompt_tokens": 120500,
      "completion_tokens": 8200,
      "total_tokens": 128700,
      "first_trace_at": "2026-07-23T10:15:00Z",
      "last_trace_at": "2026-07-30T16:42:00Z"
    }
  ]
}
```

### 3.3 错误契约

| 错误 | 退出码 | 提示 |
|------|--------|------|
| 缺少 Langfuse 凭证 | 1 | `[BLOCKED:no-credentials] LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY missing` |
| 网络错误 | 2 | `network error: <url>` |
| 凭证错误（401/403） | 3 | `auth error: <HTTP code>` |
| API 限流（429） | 4 | `rate limited, retry after <N>s` |
| 无效参数 | 5 | `invalid argument: <details>` |

---

## 4. 数据流

```text
CLI 参数
   ↓
[1] 解析时段（since_days 或 from/to）
   ↓
[2] 调用 Langfuse /api/public/traces?page=N&limit=100
   ↓ (循环分页)
[3] 仅保留 metadata.has_llm_usage=true 或 llm_usage.total_tokens>0
   ↓
[4] 按 metadata.session_id 聚合
   ↓
[5] 输出 表格/JSON/CSV
```

### 4.1 关键 Langfuse API

```http
GET /api/public/traces?page=1&limit=100
GET /api/public/traces/{traceId}  # 按需：获取 detail
```

响应结构（已采集）：
```json
{
  "data": [
    {
      "id": "trace-uuid",
      "timestamp": "2026-07-30T10:00:00Z",
      "name": "ecs gcl-runner",
      "metadata": {
        "session_id": "sess-...",
        "user_id": "alice",
        "skill": "alicloud-ecs-ops",
        "llm_usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100},
        "has_llm_usage": true
      }
    }
  ],
  "meta": {"page": 1, "totalPages": 5, "limit": 100}
}
```

---

## 5. 与现有模块的关系

| 模块 | 关系 |
|------|------|
| `token_rollup.py` | 互补：本地 trace 实时分析；本脚本远程 Langfuse 拉取 |
| `gcl_runner.py` | 数据源：本脚本依赖其上报的 `metadata.llm_usage` |
| `test-langfuse-reporting.sh` | 测试：复用凭证加载逻辑 |
| `Makefile` | 入口：`make langfuse-token-report` |

---

## 6. 成功标准

1. ✅ 拉取最近 7 天 Langfuse trace，输出按 sessionID 聚合的表格
2. ✅ 支持 `from/to` 自定义时段
3. ✅ 仅统计有 token 消耗的 trace（过滤 `has_llm_usage=true`）
4. ✅ 缺失凭证时优雅降级（`[BLOCKED:no-credentials]`）
5. ✅ 网络错误可重试（最多 3 次，指数退避）
6. ✅ Makefile 单一入口指令
7. ✅ 单元测试覆盖率 ≥ 80%
8. ✅ 文档同步更新（用户手册 + 设计文档）
