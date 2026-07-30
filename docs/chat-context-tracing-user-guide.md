# 阿里云 Chat Context 追踪 - 用户手册

> 本手册介绍如何使用阿里云 Skills 项目中的 Chat Context 追踪功能，实现跨 IM 平台的统一用户会话追踪。

---

## 1. 概述

Chat Context（聊天上下文）追踪系统用于：

- **跨平台统一**：企业微信、飞书、钉钉等 IM 平台的会话统一追踪
- **用户身份关联**：将 IM 平台的用户身份（user_id）关联到 Skill 执行日志
- **会话聚合**：将同一用户的多次交互聚合到同一个 session
- **Langfuse 上报**：可选地将追踪数据上报到 Langfuse 可观测性平台

---

## 2. 核心概念

### 2.1 ChatContext 数据结构

```python
@dataclass(frozen=True)
class ChatContext:
    user_id: str | None       # 用户唯一标识（从 IM 平台获取）
    session_id: str | None   # 会话 ID（群聊 chatid / 单聊合成 ID）
    platform: str | None      # 平台来源：wecom / feishu / dingtalk / cli
    chat_type: str | None    # 会话类型：group / single
    raw: dict | None         # 原始平台回调数据（已脱敏）
```

### 2.2 关键字段映射

| 字段 | 企业微信 | 飞书 | 钉钉 | CLI (默认) |
|------|---------|------|------|------------|
| user_id | `from.userid` | `sender.open_id` | `senderId` | `os.environ["USER"]` |
| session_id | `chatid` | `chat_id` | `chatId` | `session-YYYYMMDD-HHMMSS` |
| platform | `wecom` | `feishu` | `dingtalk` | `cli` |
| chat_type | `group`/`single` | `group`/`single` | `group`/`single` | `cli` |

---

## 3. 快速开始

### 3.1 环境变量配置

在 `.env` 文件中配置 Langfuse（可选）：

```bash
# Langfuse 可观测性配置
SKILLOPT_LANGFUSE_ENABLED=true
LANGFUSE_HOST=https://hai-langfuse-int.hd123.com
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# 会话追踪（由 Agent Runtime 自动注入）
HARNESS_SESSION_ID=your-session-id
HARNESS_USER_ID=your-user-id
```

### 3.2 在 Skill 中使用

#### 方式一：自动绑定（推荐）

```python
from alicloud_shared.chat_context import bind, ChatContext

# Agent Runtime 自动注入，无需手动处理
bind(ChatContext(
    user_id="user-123",
    session_id="session-456",
    platform="wecom",
    chat_type="group"
))

# 后续代码自动获取上下文
from alicloud_shared.chat_context import get_current_ctx

ctx = get_current_ctx()
print(f"User: {ctx.user_id}, Session: {ctx.session_id}")
```

#### 方式二：CLI 模式（默认降级）

```python
# CLI 模式下自动使用默认上下文
from alicloud_shared.chat_context import get_current_ctx

ctx = get_current_ctx()
# 无 IM 平台时自动降级：
# - user_id = os.environ.get("USER", "unknown")
# - session_id = f"session-{datetime.now():%Y%m%d-%H%M%S}"
# - platform = "cli"
```

### 3.3 适配器注册

如需支持新的 IM 平台，注册适配器：

```python
from alicloud_shared.chat_context import register_adapter, normalize

def normalize_my_platform(payload: dict) -> ChatContext:
    """自定义平台适配器"""
    return ChatContext(
        user_id=payload.get("user", {}).get("id"),
        session_id=payload.get("conversation_id"),
        platform="my-platform",
        chat_type=payload.get("type", "single"),
        raw=payload
    )

# 注册适配器
register_adapter("my-platform", normalize_my_platform)

# 使用适配器
ctx = normalize("my-platform", webhook_payload)
```

---

## 4. Langfuse 上报

### 4.1 gcl_runner.py 自动上报

`gcl_runner.py` 在执行完成后自动将 trace 上报到 Langfuse：

```bash
SKILLOPT_LANGFUSE_ENABLED=true \
LANGFUSE_BASE_URL=https://hai-langfuse-int.hd123.com \
LANGFUSE_PUBLIC_KEY=pk-lf-xxx \
LANGFUSE_SECRET_KEY=sk-lf-xxx \
HARNESS_SESSION_ID=my-session \
HARNESS_USER_ID=my-user \
python3 alicloud-gcl-runner-ops/scripts/gcl_runner.py \
    --skill alicloud-ecs-ops \
    --op DescribeInstances \
    --command "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
```

输出示例：
```
[Langfuse] HOST=https://hai-langfuse-int.hd123.com Org=ops-alicloud Project=ops-alicloud
[03:45:47] [GCL-RUNNER] event=langfuse_report status=success trace_id=gcl-trace-20260730-034547
```

### 4.2 上报的 metadata 字段

| 字段 | 说明 |
|------|------|
| `skill` | Skill 名称，如 `alicloud-ecs-ops` |
| `status` | 执行状态：`PASS` / `FAIL` / `WRAPPER_BYPASS` |
| `user_id` | 用户标识（从环境变量或 IM 平台获取） |
| `session_id` | 会话标识 |
| `llm_usage` | **LLM Token 消耗汇总**（见下表） |
| `has_llm_usage` | **是否有 Token 消耗**（布尔值，用于过滤） |
| `command` | 执行的命令 |
| `exit_code` | 命令退出码 |
| `duration_ms` | 执行耗时（毫秒） |
| `rubric_scores` | GCL 评分结果 |

**llm_usage 字段结构**：

| 子字段 | 类型 | 说明 |
|--------|------|------|
| `prompt_tokens` | int | 提示词 token 数 |
| `completion_tokens` | int | 回答 token 数 |
| `total_tokens` | int | 总 token 数 |

**示例**（仅在 `has_llm_usage=true` 时 total_tokens > 0）：
```json
{
  "metadata": {
    "llm_usage": {
      "prompt_tokens": 1500,
      "completion_tokens": 200,
      "total_tokens": 1700
    },
    "has_llm_usage": true
  }
}
```

### 4.3 从 metadata 提取用户会话

Langfuse API 返回时，`user_id` 和 `session_id` 在顶层字段可能为空，需从 `metadata` 中提取：

```python
for t in traces:
    metadata = t.get("metadata", {})
    user_id = metadata.get("user_id", "")      # 从 metadata 提取
    session_id = metadata.get("session_id", "")  # 从 metadata 提取
    print(f"User: {user_id}, Session: {session_id}")
```

### 4.4 从 metadata 提取 LLM Token 消耗

Langfuse 上报时，Token 消耗在 `metadata.llm_usage` 中（仅当 `has_llm_usage=true` 且 `total_tokens > 0` 时有效）：

```python
import urllib.request
import base64

auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()
req = urllib.request.Request(
    f"{LF_HOST}/api/public/traces?limit=100",
    headers={"Authorization": f"Basic {auth}"}
)

with urllib.request.urlopen(req) as r:
    traces = json.loads(r.read())["data"]

for t in traces:
    metadata = t.get("metadata", {})
    llm_usage = metadata.get("llm_usage", {})
    if llm_usage.get("total_tokens", 0) > 0:
        print(f"Token消耗: prompt={llm_usage['prompt_tokens']}, "
              f"completion={llm_usage['completion_tokens']}, "
              f"total={llm_usage['total_tokens']}")
```

### 4.5 Langfuse UI 过滤有 Token 消耗的 Trace

在 Langfuse UI 的 **Traces** 页面：

1. 点击 **Add filter**
2. 选择 `metadata.has_llm_usage` → `=` → `true`
3. 或选择 `metadata.llm_usage.total_tokens` → `>` → `0`

即可过滤出所有调用了 LLM 的 GCL trace。

---

## 5. 集成测试

### 5.1 本地测试

```bash
# 方式一：通过 .env 加载凭证
LANGFUSE_ENV_FILE=.env bash scripts/test-langfuse-reporting.sh

# 方式二：直接设置环境变量
LANGFUSE_BASE_URL=https://hai-langfuse-int.hd123.com \
LANGFUSE_PUBLIC_KEY=pk-lf-xxx \
LANGFUSE_SECRET_KEY=sk-lf-xxx \
bash scripts/test-langfuse-reporting.sh
```

### 5.2 单元测试

```bash
python3 -m pytest \
    alicloud-gcl-runner-ops/tests/alicloud_shared/test_langfuse_trace_upload.py \
    -v
```

测试用例：
- `_print_langfuse_info()` - 禁用时不输出
- `_report_trace_to_langfuse()` - 上报功能验证

---

## 6. 故障排查

### 6.1 上报失败

| 症状 | 可能原因 | 解决方案 |
|------|----------|----------|
| `[BLOCKED:no-credentials]` | 缺少环境变量 | 检查 `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` |
| `HTTP 401` | 凭证错误 | 确认 `pk-xxx` 和 `sk-xxx` 正确 |
| `HTTP 404` | 项目 ID 不存在 | 检查 Langfuse 项目配置 |

### 6.2 会话关联失败

| 症状 | 可能原因 | 解决方案 |
|------|----------|----------|
| `user_id=None` | 环境变量未注入 | 检查 `HARNESS_USER_ID` 或 Agent Runtime 配置 |
| `session_id=None` | IM 平台无 session | 检查平台适配器是否正确合成 session_id |

### 6.3 调试模式

启用详细日志：

```bash
export SKILLOPT_LOG_FORMAT=json
export SKILLOPT_LANGFUSE_ENABLED=true
python3 alicloud-gcl-runner-ops/scripts/gcl_runner.py ...
```

---

## 7. 相关文档

| 文档 | 说明 |
|------|------|
| [ADR-001: Unified Chat Context Tracing](./architecture/ADR-001-unified-chat-context-tracing.md) | 架构决策记录 |
| [Runtime Harness Integration Guide](./harness-integration-guide.md) | Runtime Harness 集成指南 |
| [Langfuse Observability](./harness-integration-guide.md#langfuse) | Langfuse 可观测性配置 |

---

## 8. 更新历史

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-07-30 | v1.0 | 初始版本，涵盖 ChatContext 结构、Langfuse 上报、故障排查 |
