# Local Token Session Report — SPEC

> **关联实现**: `scripts/token_rollup.py` 新增 `local-token-report` 子命令
> **对标**: `langfuse-token-report` 输出格式，便于本地 vs 远程逐 session 对账

## 1. 背景与目标

本地 `token_rollup.py` 按 trace 维度聚合 token，输出 `global / by_skill / by_agent_model` 层级。
`langfuse-token-report` 按 `session_id` 聚合远程 Langfuse 数据，输出 session 维度表格。

两者维度不同，无法直接对账。本命令为本地 trace 数据补齐 session 维度聚合，输出格式与 `langfuse-token-report` 完全对齐。

## 2. 命令接口

```bash
# Makefile
make local-token-report SINCE_DAYS=7          # 最近7天，按session聚合
make local-token-report SINCE_MINUTES=120     # 最近2小时
make local-token-report SINCE_DAYS=30 FORMAT=json OUTPUT=report.json  # JSON输出到文件

# 直接调用
python3 scripts/token_rollup.py local-token-report --since-days 7
python3 scripts/token_rollup.py local-token-report --since-days 7 --format json --output /tmp/report.json
python3 scripts/token_rollup.py local-token-report --since-minutes 120
```

### 参数

|参数|说明|默认|
|---|---|---|
|`--since-days N`|时间窗口（天）|7|
|`--since-minutes N`|时间窗口（分钟），优先于 --since-days|无（默认用 --since-days）|
|`--repo-root`|仓库根目录|自动检测|
|`--format table\|json`|输出格式|`table`|
|`--output FILE`|JSON时输出到文件|stdout|

### 行为

1. 读取 `.runtime/token/cache/normalized-records.jsonl`（token_rollup 缓存）
2. 按 `session_id` 分组聚合
3. 输出与 `langfuse-token-report` 完全对齐的报表格式
4. 若缓存不存在，先运行 rollup 生成缓存

## 3. 输出格式

### 3.1 JSON 输出（与 langfuse-token-report 完全对齐）

```json
{
  "version": "<ROLLUP_VERSION>",
  "source": "local",
  "period": { "from": "ISO8601", "to": "ISO8601", "days": N },
  "summary": {
    "total_sessions": N,
    "traces_in_sessions": N,
    "total_prompt_tokens": N,
    "total_completion_tokens": N,
    "total_tokens": N
  },
  "sessions": [
    {
      "session_id": "sess-xxx",
      "user_id": "...",
      "trace_count": N,
      "skill_count": N,
      "skills": ["alicloud-ecs-ops", ...],
      "prompt_tokens": N,
      "completion_tokens": N,
      "total_tokens": N,
      "first_trace_at": "ISO8601",
      "last_trace_at": "ISO8601"
    },
    ...
  ]
}
```

### 3.2 Table 输出

```
=== Local Token Session Report ===
Period: 2026-07-23 → 2026-07-30 (7 days)
Total Sessions: 35   Traces: 566   Total Tokens: 0
-----------------------------------------------------------------------------------------
Session ID                           Traces     Prompt  Completion      Total User
-----------------------------------------------------------------------------------------
(no-session)                            250          0           0          0 langfuse-repor
sess-xxx                                 12          0           0          0 bohaiqing
...
```

## 4. 聚合维度与计算

|字段|来源|
|---|---|
|`session_id`|record.session_id，无则 `"(no-session)"`|
|`user_id`|首条 record.user_id|
|`trace_count`|该 session 的 record 数量|
|`skill_count`|去重 skill 数量|
|`skills`|去重 skill 集合（sorted）|
|`prompt_tokens`|sum(record.llm_usage.prompt_tokens)|
|`completion_tokens`|sum(record.llm_usage.completion_tokens)|
|`total_tokens`|sum(record.llm_usage.total_tokens)|
|`first_trace_at`|该 session 最早 record.timestamp|
|`last_trace_at`|该 session 最晚 record.timestamp|

## 5. 数据源

- **优先**: `.runtime/token/cache/normalized-records.jsonl`
- **降级**: 若缓存不存在，运行 `rollup_apply(full=True)` 生成缓存后聚合

## 6. 错误处理

- 缓存为空：`{"sessions": [], "summary": {...}}`，表格输出空表格
- 文件不存在：先尝试 rollup；rollup 失败则报错退出

## 7. 测试用例

使用当前 566 条真实数据（35 sessions，token 全 0）验证：

```bash
make local-token-report SINCE_DAYS=7
# 预期：35 sessions，566 traces，token 全 0

make local-token-report SINCE_MINUTES=120
# 预期：近2小时内的 session 聚合，token 全 0

make local-token-report SINCE_DAYS=7 FORMAT=json OUTPUT=/tmp/local_report.json
# 预期：JSON 结构完整，与 langfuse-token-report 的 JSON 字段完全对齐
```
