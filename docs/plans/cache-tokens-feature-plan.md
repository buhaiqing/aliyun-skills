# Plan: LLM Cache Tokens 字段解析功能

## 1. 任务概述

**背景**：可观测 Trace 记录需要包含 Prompt Cache 消耗情况，便于分析 Token 成本和缓存命中率。

**目标**：在 `gcl_runner.py` 的 `parse_openai_llm_usage` 函数中新增 `cache_tokens` 和 `cache_hit_ratio` 字段解析，支持 5 个模型厂商。

**厂商支持**：
| 厂商 | provider 值 | cache_tokens 字段 |
|------|-------------|-------------------|
| 阿里云百炼 | `alibaba` | `usage.prompt_tokens_details.cached_tokens` |
| MiniMax | `minimax` | `usage.prompt_tokens_details.cached_tokens` (OpenAI) / `usage.cache_read_input_tokens` (Anthropic) |
| 智谱 AI | `zhipu` | `usage.prompt_tokens_details.cached_tokens` |
| DeepSeek | `deepseek` | `usage.prompt_cache_hit_tokens` |
| 豆包/火山方舟 | `volcengine` | `usage.prompt_tokens_details.cached_tokens` |

---

## 2. 涉及文件

| 文件 | 改动类型 |
|------|----------|
| `alicloud-gcl-runner-ops/scripts/gcl_runner.py` | 修改 `parse_openai_llm_usage` 函数 |
| `alicloud-gcl-runner-ops/scripts/gcl_runner_test.py` | 新增单元测试 |

---

## 3. 详细任务分解

### Task 1: 修改 `parse_openai_llm_usage` 函数

**文件**: `gcl_runner.py` line 1595-1616

**改动内容**:
1. 新增参数 `provider: str`
2. 解析 `cache_tokens`:
   - `deepseek` → `usage.prompt_cache_hit_tokens`
   - `minimax` + Anthropic 格式 → `usage.cache_read_input_tokens`
   - 其他 OpenAI 兼容厂商 → `usage.prompt_tokens_details.cached_tokens`
   - 不支持则返回 `None`
3. 计算 `cache_hit_ratio` = `cache_tokens / prompt_tokens`（仅当 cache_tokens 不为 None 时）

**验证**: 运行 `python3 -m unittest gcl_runner_test` 全量通过

### Task 2: 新增单元测试

**文件**: `gcl_runner_test.py`

**测试用例**:
| # | 测试名称 | 输入 | 期望输出 |
|---|----------|------|----------|
| 1 | `test_cache_tokens_alibaba` | 百炼 usage | `cache_tokens=800, cache_hit_ratio=0.533` |
| 2 | `test_cache_tokens_deepseek` | DeepSeek usage | `cache_tokens=800, cache_hit_ratio=0.533` |
| 3 | `test_cache_tokens_minimax_anthropic` | MiniMax Anthropic usage | `cache_tokens=800, cache_hit_ratio=0.533` |
| 4 | `test_cache_tokens_unsupported` | 不支持的厂商 | `cache_tokens=None, cache_hit_ratio=None` |
| 5 | `test_cache_tokens_zero_prompt` | prompt_tokens=0 | `cache_hit_ratio=None`（避免除零） |

### Task 3: 更新调用处

**文件**: `gcl_runner.py` line 1784

**改动**: `parse_openai_llm_usage` 调用时传入 `provider` 参数

---

## 4. 数据结构变更

**修改前**:
```python
{
    "model": "qwen-plus",
    "prompt_tokens": 1200,
    "completion_tokens": 300,
    "total_tokens": 1500,
}
```

**修改后**:
```python
{
    "model": "qwen-plus",
    "provider": "alibaba",
    "prompt_tokens": 1200,
    "completion_tokens": 300,
    "total_tokens": 1500,
    "cache_tokens": 800,
    "cache_hit_ratio": 0.667,
}
```

---

## 5. 依赖关系

```
Task 1 (修改 parse_openai_llm_usage)
    ↓
Task 3 (更新调用处) ──并行──▶ Task 2 (新增单元测试)
    ↓
全量测试验证
```

---

## 6. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| provider 参数传入错误 | 在函数内做防御性处理，未知厂商返回 None |
| 旧调用处遗漏 | 全局搜索 `parse_openai_llm_usage(` 确认所有调用点 |

---

## 7. 验证标准

- [ ] `python3 -m unittest gcl_runner_test` 全量通过
- [ ] 新增 5 个测试用例全部 PASS
- [ ] 向后兼容：不传 provider 时行为与之前一致
