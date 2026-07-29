# ADR-001: Unified Chat Context Tracing Across IM Platforms

| 字段 | 值 |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-29 (v1 初稿) → 2026-07-29 (v2 加入 HTTP POST 通道与跨进程传播机制) |
| **Deciders** | Skills 平台架构组 |
| **Supersedes** | — |
| **Related** | [ARCHITECTURE.md](../../ARCHITECTURE.md) §接入适配层、§输出适配层、§可观测性、§双模式接入 |

> **本 ADR 在 ARCHITECTURE.md 中的位置**:本决策定义了 ARCHITECTURE.md 中"接入适配层"(Input Adapters)对 IM 与 HTTP 来源的归一化要求,以及"可观测性"贯穿全链路的 trace schema 字段。本 ADR 是该高层架构在 trace 维度的细化,落地前需复核 ARCHITECTURE.md 中相关章节是否需要同步更新引用。

---

## 1. Context(背景)

### 1.1 现状

阿里云运维 Skills 当前通过 **Nanobot**([HKUDS/nanobot](https://github.com/HKUDS/nanobot)) 作为 agent runtime,面向企业内部用户提供 IM 接入。当前或计划接入的来源通道:

| 通道 | 类型 | 接入方式 |
|---|---|---|
| **企业微信**(WeCom) | IM | 智能机器人(WebSocket 长连接) |
| **飞书**(Feishu) | IM | 事件订阅(Webhook) |
| **钉钉**(DingTalk) | IM | Stream 模式(WebSocket) |
| **HTTP POST API** | 系统集成 | 调用方 `POST /v1/chat/completions`,Bearer Token 鉴权 |
| **命令行**(CLI) | 直接执行 | `python xxx.py` |
| **REST / MCP**(Agent Runtime 自有) | 系统级调用 | 见 [ARCHITECTURE.md §双模式接入](../../ARCHITECTURE.md#双模式接入) |

**注意**:HTTP POST API 与本仓库的 REST API/MCP Server 是两个不同概念——
- **本 ADR 涉及的 HTTP POST**:外部系统调 Nanobot 提供的 OpenAI 兼容接口(`POST /v1/chat/completions`)
- **ARCHITECTURE.md 中的 REST/MCP**:Nanobot/Agent Runtime 内部对外暴露的诊断 API(`/diagnose`、`/tasks` 等)

两者在 trace schema 上目标一致(都要 user/session/trace 三 ID),但通道来源与鉴权机制不同。

### 1.2 现有 Trace Schema 的不足

[`ExecutionTrace`](../../alicloud-terraform-ops/scripts/execution_trace.py) 与 [`TraceRun`](../../alicloud-aiops-ml/trace_logger.py) 目前记录的字段:

```python
trace_id           # ✅ 自动生成
session_id: str | None = None   # ⚠️ wizard_cli 自造 "session-YYYYMMDD-HHMMSS",无法与 IM 平台对齐
user_id: str | None = None      # ❌ ExecutionTrace 没有;wizard 只从 os.environ.get("USER") 拿
platform                          # ❌ 完全缺失
```

**结果**:
- IM 用户的真实身份(`from.userid`)从未进入 trace
- 群聊/单聊的会话边界与 wizard 自造的 `session-` 前缀 ID 无法对应
- 跨平台聚合分析时无 `platform` 字段可区分
- 单聊场景下 WeCom 无原生 session_id,需业务侧合成

### 1.3 三大平台回调字段对比

| 字段 | WeCom 智能机器人 | 飞书 | 钉钉 Stream |
|---|---|---|---|
| 用户标识 | `from.userid`(群聊可能加密) | `sender.sender_id.{open_id,union_id,user_id}` 三选一 | `senderId` / `senderStaffId`(加密) |
| 群聊 session | ✅ `chatid` | ✅ `chat_id` | ✅ `chatId` |
| **单聊 session** | **❌ 无,需合成** | ✅ `chat_id` | ✅ `chatId` |
| 消息 ID | `msgid` | `message_id` | `msgId` |
| 平台身份 | `aibotid` | `app_id` + `tenant_key` | `robotCode` |

**关键不变量**:三个 ID(`user_id`、`session_id`、`trace_id`)在不同平台上的来源不同,但**业务语义应当一致**。

### 1.4 核心约束

- **Skill 业务层不能感知平台**(违反会让每个 skill 都写一遍适配)
- **加新平台不能改 skill 代码**(只许改 adapter 层)
- **CLI / REST 场景无 IM 平台时也要能跑**(给个 default 降级)
- **session_id 在单聊场景下必须有定义**(不能是 `None`)
- **跨进程边界必须能传 ID**:Nanobot 调 skill 用 subprocess,ContextVar 跨进程失效,**必须用环境变量**(详见 §2.5)
- **HTTP POST 通道是契约而非平台**:调用方必须主动传 `session_id` 与用户标识 header,否则 trace 无法聚合

---

## 2. Decision(决策)

采用 **4 层架构 + 适配器注册表** 模式,在 Skill 与平台之间插入归一化层。

### 2.1 4 层职责

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Chat APP Adapter (平台专属)                        │
│    normalize_wecom / normalize_feishu / normalize_dingtalk │
│    + normalize_cli  (default)                                │
│    + 注册表:支持未来加 normalize_slack / normalize_email …  │
└────────────────┬────────────────────────────────────────────┘
                 ↓ ChatContext (frozen dataclass, 平台无关)
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: ChatContext (共享运行时,单点定义)                  │
│    { user_id, session_id, platform, chat_type, raw }        │
│    通过 ContextVar 进程内全链路传播                          │
└────────────────┬────────────────────────────────────────────┘
                 ↓ 自动注入
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Skill 业务逻辑                                     │
│    ExecutionTrace.new() / TraceRun.new() 工厂方法自动读 ctx │
│    业务代码零修改,只改 dataclass 字段 + 一个工厂方法         │
└────────────────┬────────────────────────────────────────────┘
                 ↓ 落盘格式跨平台一致
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Trace 落地 (JSON 落盘 / 上报 Langfuse)            │
│    trace_id / session_id / user_id / platform 全字段一致    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 三个 ID 的归一化规则

| ID | 来源 | 跨平台映射 |
|---|---|---|
| **user_id** | `from.userid` / `sender.sender_id.open_id` / `senderStaffId` / `$USER` | 平台归一化:统一以平台原始 ID 为准,**不重编码**(保留审计可追溯性) |
| **session_id** | `chatid` / `chat_id` / `chatId`;**WeCom 单聊例外**:`{userid}-{session_start_ts}` 合成 | 群聊 = 群 ID;单聊 WeCom = 合成,其他平台 = 原生 |
| **trace_id** | `trace-{uuid4.hex[:12]}` | **完全本地产生**,与平台无关 |

### 2.3 默认降级(CLI / REST / 未知平台)

`normalize_cli()` 是 default adapter,**永远存在**,负责 CLI / REST / 任何未注册平台的兜底:

```python
def normalize_cli(*, source: str = "cli") -> ChatContext:
    """CLI / REST / 未知平台的默认归一化"""
    return ChatContext(
        user_id=os.environ.get("USER", "anonymous"),
        session_id=f"cli-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{os.getpid()}",
        platform=source,                # "cli" | "rest" | "unknown"
        chat_type="n/a",
        raw={},
    )
```

**调用约定**:Skill 入口(`main()` / `cli()` / wizard 启动)必须**显式调用一次**`bind(default_or_platform_chat_context())`,没有 bind 时所有字段降级为 `None`,而不是崩。

### 2.4 适配器注册表(可扩展性)

```python
# alicloud-shared-runtime/chat_context.py
_ADAPTERS: dict[str, Callable[[dict], ChatContext]] = {}

def register_adapter(platform: str, fn: Callable[[dict], ChatContext]) -> None:
    """未来加 Slack/Discord/邮件: register_adapter("slack", normalize_slack)"""
    _ADAPTERS[platform] = fn

def normalize(platform: str, payload: dict) -> ChatContext:
    if platform not in _ADAPTERS:
        return normalize_cli(source=platform)   # unknown → default
    return _ADAPTERS[platform](payload)
```

**新增一个 Chat APP 只需要**:
1. 在 adapter 层写一个 15 行 `normalize_xxx()` 函数
2. 注册一次 `register_adapter("xxx", normalize_xxx)`
3. **零改动**:skill / trace / wizard / nanobot 入口(除了解析 raw payload 那一步)

### 2.5 跨进程传播机制(Cross-Process Propagation)

**关键问题**:Nanobot 调 skill 是 `subprocess.run(["python", "skill.py"], ...)`——**不是** import 进同一进程。`contextvars.ContextVar` 跨进程会失效,全局变量也失效。

**结论**:**进程间唯一可靠的传播通道是环境变量**。Nanobot 在 spawn 子进程前注入:

```python
# nanobot 入口(伪代码)
env = os.environ.copy()
env["CHAT_PLATFORM"]   = ctx.platform      # "wecom" | "feishu" | "dingtalk" | "http" | "cli"
env["CHAT_USER_ID"]    = ctx.user_id
env["CHAT_SESSION_ID"] = ctx.session_id
env["CHAT_TYPE"]       = ctx.chat_type     # "p2p" | "group" | "api" | "n/a"

subprocess.run(["python", skill_path, ...], env=env)
```

**Skill 入口处统一读取并 bind**(10 行):

```python
# skill.py 入口最开头(每个 skill 都要加)
import os
from alicloud_shared.chat_context import bind, ChatContext

def bind_from_env() -> None:
    platform = os.environ.get("CHAT_PLATFORM")
    if not platform:
        return  # CLI / REST 直调,无 nanobot 注入 → 不 bind,字段降级 None
    bind(ChatContext(
        platform=platform,
        user_id=os.environ.get("CHAT_USER_ID", "anonymous"),
        session_id=os.environ.get("CHAT_SESSION_ID", "unknown"),
        chat_type=os.environ.get("CHAT_TYPE", "n/a"),
        raw={},
    ))
```

**为什么选 env var 而非其他机制**:

| 机制 | 跨 subprocess 边界 | 评价 |
|---|---|---|
| `contextvars.ContextVar` | ❌ 进程隔离,失效 | 仅适合 nanobot 进程内的中间件 |
| 全局变量 / 单例 | ❌ 进程隔离,失效 | 同上 |
| CLI 参数 | ✅ 但污染 skill 接口 | 不推荐,每个 skill 都要加 `--platform` |
| **环境变量** | ✅ **subprocess 自动继承** | ✅ 推荐,零侵入 |
| stdin JSON | ✅ 但需要 skill 主动读 stdin | 可选,传 raw payload 用 |
| 临时文件 | ✅ 但 IO 开销 + 路径协调 | 不推荐 |

**约定**:未来加任何新的进程间调用层(MCP server → skill / Agent Runtime → skill),一律用相同 env var 协议。

### 2.6 HTTP POST 作为第 4 类通道

**Nanobot HTTP API 形态**(见 [HKUDS/nanobot OpenAI API 文档](https://github.com/HKUDS/nanobot/blob/main/docs/openai-api.md)):

```bash
POST /v1/chat/completions
Authorization: Bearer $NANOBOT_API_KEY      # 本地访问可省略
Content-Type: application/json

{
  "messages": [{"role": "user", "content": "查 RDS 连接数"}],
  "session_id": "incident-2026-0729-rm-bp11",   # 可选,默认 "api:default"
  "stream": false
}
```

**HTTP POST 与 IM 的关键差异**:

| 字段 | WeCom / Feishu / DingTalk | HTTP POST |
|---|---|---|
| **user_id 来源** | IM 原生字段,必有 | ⚠️ **调用方必须主动传**(OpenAI 协议无 user 字段) |
| **session_id 来源** | 群聊 = chatid;单聊 = 原生或合成 | ⚠️ **调用方必须主动传**;不传 → Nanobot 默认 `"api:default"`(所有未指定共享一个会话) |
| **trace_id** | skill 自产生 | 一致 |
| **鉴权** | 平台 SDK / 回调签名 | Bearer Token |
| **典型调用方** | 真人用户 | CI/CD、监控、告警系统、内部平台 |

**调用方契约**(必须文档化):

```bash
# 推荐:调用方在 header 里塞自定义字段,在 body 里传 session_id
curl http://nanobot:8900/v1/chat/completions \
  -H "Authorization: Bearer $NANOBOT_API_KEY" \
  -H "X-Chat-User-Id: ops-team-zhangsan" \      # 服务背后是谁
  -H "X-Chat-Source: alertmanager" \            # 谁在调(可选,审计用)
  -H "Content-Type: application/json" \
  -d '{
    "messages": [...],
    "session_id": "incident-rm-bp11-0729"        # 必填,否则 trace 无法聚合
  }'
```

**normalize_http adapter 设计**:

```python
# alicloud-shared-runtime/adapters/http_api.py
import time

def normalize_http(*, headers: dict, body: dict, caller_id: str) -> ChatContext:
    """HTTP POST /v1/chat/completions → ChatContext

    caller_id: 由 Bearer Token 反查得到的服务身份
    """
    user_id = (
        headers.get("X-Chat-User-Id")
        or headers.get("X-User-Id")
        or caller_id  # 兜底:用 API key 拥有方
    )

    # session_id 必填,默认 fallback 用 caller + 时间戳避免混在一起
    session_id = body.get("session_id")
    if not session_id or session_id == "api:default":
        session_id = f"http-{caller_id}-{int(time.time())}"

    return ChatContext(
        user_id=user_id,
        session_id=session_id,
        platform="http",                # ✅ 第 4 个 platform 值
        chat_type="api",                # ✅ 区分"人"vs"机"
        raw={"headers": dict(headers), "body_keys": list(body.keys())},
    )
```

**HTTP POST 场景下"用户"的双重含义**(必须明确文档):

| 维度 | 含义 | 例子 |
|---|---|---|
| **调用方**(机器/服务) | 由 Bearer Token 标识,代表"哪个系统在调" | `alertmanager`、`github-actions` |
| **背后真人**(用户) | 由 `X-Chat-User-Id` 标识,代表"谁授权这次调用" | `ops-team-zhangsan` |

**默认行为**:`user_id` 优先取 `X-Chat-User-Id`,缺失时 fallback 到 API key 拥有方——确保**任何 HTTP 调用都有 user 字段**,而不是 None。

---

## 3. Consequences(影响)

### 3.1 正面 ✅

| 收益 | 说明 |
|---|---|
| **Skill 层零平台依赖** | 业务代码永远不 `import wecom` / `import lark` / `import dingtalk` |
| **Trace 格式跨平台一致** | `trace_id` / `session_id` / `user_id` / `platform` 字段名与值域统一,聚合分析不需要 if-else |
| **新平台接入成本可控** | 增加一个 IM ≈ 15 行 adapter + 1 次 register;无 skill 改动 |
| **CLI / REST 兜底** | `normalize_cli()` 保证无 IM 时仍能跑,所有字段有合理默认值 |
| **WeCom 单聊痛点隔离** | 唯一需要合成 session_id 的地方被封装在 `normalize_wecom()` 内,其他层零感知 |
| **加密 userid 解密集中** | 三个平台的解密逻辑都在 adapter 层,避免 skill 层泄露加密处理细节 |
| **跨进程边界统一** | env var 协议一刀切,任何 spawn 关系(Nanobot → skill / Agent Runtime → skill / MCP → skill)走同一套 |
| **HTTP POST 显式契约** | 调用方必须传 session_id + 用户 header,避免默认 `api:default` 陷阱(详见 §2.6) |
| **agent runtime 维度可观测** | 与 ARCHITECTURE.md §可观测性 中"Langfuse Trace → Token 用量"维度对齐,新增 platform / user / session 三个聚合维度 |

### 3.2 负面 / 代价 ⚠️

| 代价 | 缓解 |
|---|---|
| 新增一个共享运行时包 `alicloud-shared-runtime` | 现有 skill 改 import 路径;一次性成本,后续所有 skill 受益 |
| WeCom 单聊 session 边界是启发式的(时间窗) | 在 adapter 层明确文档化"30 分钟空闲 = 新 session",业务方知情 |
| `platform` 字段暴露在 trace 数据中(轻微信息泄露) | 接受:trace 文件落盘已脱敏 secret,platform 是必要的审计维度 |
| nanobot 入口需要改成调用 `register_adapter` + `bind(chat_context)` | 由 nanobot 适配层一次性改造,skill 层无感 |
| 现有 wizard 的 `session-{ts}` 格式要被替换 | 一次性迁移,新格式即 `chatid` / 合成 ID,可读性更好 |
| **每个 skill 入口都要加 10 行 `bind_from_env()`** | 提供共享 helper,新 skill 强制 import;老 skill 一次性 patch |
| **HTTP POST 契约是"必须传"** | 调用方不传 → 走 fallback 临时 ID;调用方文档强制写"必传" |
| **trace 中 `raw` 字段可能含敏感 header**(如原始 Authorization) | adapter 层**显式 redact** 敏感字段后再放 raw;trace 落盘目录受 ACL 控制 |

### 3.3 中性 / 待定 🔄

| 项 | 说明 |
|---|---|
| 单聊时间窗阈值(默认 30 分钟) | 后续可按用户反馈调整,放 adapter 配置文件 |
| `user_id` 是否脱敏(只存 hash) | 当前不做,trace 落盘目录本身受访问控制;若合规要求可加 |
| 是否需要在 trace 记录 `aibotid` / `tenant_key` 等平台身份 | 当前 `raw` 字段携带但不进 `to_dict()`;后续可选择性提升 |

---

## 4. Alternatives Considered(备选方案)

### 4.1 ❌ 方案 A:每个 Skill 内置平台判断

```python
# 反例:alicloud-*-ops 里这么写
if platform == "wecom":
    user_id = wecom_payload["from"]["userid"]
elif platform == "feishu":
    user_id = feishu_payload["sender"]["sender_id"]["open_id"]
elif platform == "dingtalk":
    ...
```

**否决理由**:N 个 skill × M 个平台 = N×M 适配代码;每加一个平台所有 skill 都要改;违反单一职责。

### 4.2 ❌ 方案 B:不归一化,trace 里塞 raw payload

```python
@dataclass
class ExecutionTrace:
    raw_payload: dict   # 整个 IM 回调丢进来
```

**否决理由**:trace 体积爆炸;聚合查询要写 N 套解析;敏感字段(原始 token)泄露风险。

### 4.3 ⚠️ 方案 C:复用 nanobot 自带的 session 抽象

调研发现 nanobot 已有 session history / topics 概念,但**它管的是 agent loop 的对话历史,不直接对外暴露 session_id 字段**。

**决议**:**借鉴其语义(交互粒度 session),不复用其对象**——我们在 adapter 层自己定义 `ChatContext`,理由:
1. nanobot session 抽象与 trace schema 解耦较难,改它风险大
2. 我们需要 `platform` 字段做审计,nanobot 不提供
3. CLI / REST 场景下 nanobot 不在场,需要自己兜底

### 4.4 ✅ 方案 D:本 ADR 提出的 4 层架构

见 §2。

### 4.5 ⚠️ 方案 E:跳过 ChatContext 抽象,直接 env var 透传

```python
# nanobot 入口直接 setenv
env["WECOM_USER_ID"] = wecom_payload["from"]["userid"]
env["WECOM_SESSION_ID"] = wecom_payload.get("chatid") or synthesized
env["FEISHU_USER_ID"] = ""  # 不适用
# 每个平台一套 env var ...
```

**否决理由**:
1. **违反单一职责**:平台相关字段散落在 env 命名空间里,无统一 schema
2. **不可扩展**:加新平台要新增 N 个 env var 命名约定,容易冲突
3. **skill 层还是要写 if-else**:`if os.environ.get("WECOM_USER_ID")` vs `if os.environ.get("FEISHU_USER_ID")` —— 平台代码渗透到 skill
4. **没有 redact 层**:原始 payload 散落各处,敏感字段脱敏责任不集中

**结论**:ChatContext 抽象的成本(80 行)远小于绕过它的代价。

### 4.6 ✅ 方案 F:本 ADR v2 提出的 4 层架构 + env var 传播 + HTTP POST 通道

见 §2(含 §2.5 跨进程传播 + §2.6 HTTP POST 通道)。

---

## 5. Implementation Outline(实施大纲)

### 5.1 文件清单

| 路径 | 改动 | 行数估计 |
|---|---|---|
| `alicloud-shared-runtime/chat_context.py` **(新建)** | `ChatContext` dataclass + `ContextVar` + 适配器注册表 + `normalize_cli` + `bind_from_env()` | ~90 |
| `alicloud-shared-runtime/adapters/wecom.py` **(新建)** | `normalize_wecom()`(含单聊 session 合成) | ~30 |
| `alicloud-shared-runtime/adapters/feishu.py` **(新建)** | `normalize_feishu()` | ~15 |
| `alicloud-shared-runtime/adapters/dingtalk.py` **(新建)** | `normalize_dingtalk()` | ~20 |
| `alicloud-shared-runtime/adapters/http_api.py` **(新建)** | `normalize_http()`(第 4 类通道) | ~25 |
| `alicloud-shared-runtime/adapters/__init__.py` | `register_adapter(...)` 调用 4 个平台 | ~12 |
| `alicloud-terraform-ops/scripts/execution_trace.py` | 加 `user_id` / `platform` 字段 + `ExecutionTrace.new()` 工厂 | +15 / -0 |
| `alicloud-aiops-ml/trace_logger.py` | `TraceRun` 加同样 3 字段 + 工厂方法 | +15 / -0 |
| `alicloud-terraform-ops/scripts/wizard_cli.py` | 入口 bind CLI context,`persist_dry_run_trace` 透传 user_id / platform | +10 / -0 |
| 全部现有 skill 入口(alicloud-*-ops/scripts/*.py) | 每个 `main()` 开头加 `bind_from_env()` 调用 | +10 × N / -0 |
| Nanobot 入口(MCP / Webhook / HTTP API 处理器) | 调用 `register_adapter` + `bind(normalize(...))` + `env=` 注入到 subprocess | ~40 |

**总计**:~280 行新代码 + 每个 skill 入口 +10 行,业务逻辑零改动。

### 5.2 验证标准

| 项 | 标准 |
|---|---|
| **跨平台 trace 格式一致** | 三个 IM + HTTP POST + CLI 各跑一次,trace JSON 字段名与值域完全相同(除 `platform` 与 `raw`) |
| **Skill 无平台 import** | `grep -r "import wecom\|import lark\|import dingtalk" alicloud-*-ops/` 命中数 = 0 |
| **新平台扩展性** | 加 `normalize_slack()` 后,跑通原有 trace 测试,**零 skill 改动** |
| **CLI 降级** | 不 bind context 直接跑 wizard,trace 字段全部 `None` 而非崩 |
| **WeCom 单聊合成可识别** | trace 中 `session_id` 含 `synth-p2p` 前缀或独立 `raw.session_synthesized=true` |
| **跨进程传播** | Nanobot 调 skill,skill 内 `os.environ["CHAT_PLATFORM"]` 应等于 Nanobot 入口设置的 platform |
| **HTTP POST 契约** | 调用方传 `X-Chat-User-Id` 与 `session_id` 时,trace 字段被正确填充;不传时 fallback 到 caller_id + 时间戳 |
| **HTTP POST 默认陷阱** | 调用方不传 `session_id` 时,**不能**出现 session_id = `api:default` 的 trace |
| **env var 安全** | 原始 Authorization header **不进入** `ChatContext.raw`,仅 caller_id(已脱敏)进入 |

### 5.3 迁移路径

1. **Phase 1**(本 ADR 落地,无 Nanobot 依赖):
   - 建 `alicloud-shared-runtime/` 共享包
   - 加 `chat_context.py` + `normalize_cli()` + `bind_from_env()` 默认降级
   - 加 `normalize_wecom / feishu / dingtalk / http` 四个 adapter + 注册表
   - 现有 `ExecutionTrace` / `TraceRun` 加 `user_id` / `platform` 字段 + `new()` 工厂方法
   - wizard_cli 入口加 `bind_cli_context()`(CLI 场景独立可用,无需 Nanobot)
   - 每个 skill `main()` 开头加 `bind_from_env()`(向后兼容:无 env 时静默降级)

2. **Phase 2**(Nanobot 集成):
   - Nanobot 入口按平台分流:WeCom WS 消息 / 飞书 Webhook / 钉钉 Stream / HTTP POST `/v1/chat/completions`
   - 每个入口调用对应 `normalize_*()` → 写入 `env` → `subprocess.run(skill, env=...)`
   - HTTP POST 入口按 Bearer Token 反查 caller_id
   - 灰度验证 trace 跨平台字段一致

3. **Phase 3**(审计接入):
   - trace 上报到 Langfuse / 内部审计系统时带 `platform` / `user_id` / `session_id`
   - 按 `platform + session_id` 维度出 dashboard
   - 与 ARCHITECTURE.md §可观测性 中的"Token 用量 / 执行耗时 / 成功率"维度并列

### 5.4 ARCHITECTURE.md 联动检查清单

落地本 ADR 时,必须同步复核 [ARCHITECTURE.md](../../ARCHITECTURE.md) 的以下章节:

| ARCHITECTURE.md 章节 | 联动内容 |
|---|---|
| §接入适配层 | 增加 IM 与 HTTP POST 通道;引用本 ADR 作为 schema 来源 |
| §输出适配层 | 验证 trace schema 一致性(同 §1.2 字段集) |
| §可观测性 | 平台字段并入 Langfuse Trace;新增 `platform` / `user` 维度聚合 |
| §双模式接入 | 区分"本仓库 REST API"与"Nanobot HTTP POST",前者用 ARCHITECTURE.md 原契约,后者用本 ADR §2.6 |
| §核心组件说明 → SessionStore | session_id 命名约定与本 ADR §2.2 对齐 |

---

## 6. References(参考)

- [ARCHITECTURE.md](../../ARCHITECTURE.md) — 统一架构入口,Phase 1-3 演进路线(§接入适配层 / §输出适配层 / §可观测性 / §双模式接入 / §核心组件说明)
- [AGENTS.md §0.3 复利工程](../../AGENTS.md) — 文档治理与决策记录原则
- [AGENTS.md §15 Runtime Harness Integration](../../AGENTS.md) — 现有 trace 落盘规范
- [HKUDS/nanobot](https://github.com/HKUDS/nanobot) — Agent runtime,提供 IM 接入框架
- [HKUDS/nanobot · OpenAI API 文档](https://github.com/HKUDS/nanobot/blob/main/docs/openai-api.md) — `POST /v1/chat/completions` 协议、session_id 字段、Bearer Token 鉴权
- [企业微信智能机器人回调文档](https://developer.work.weixin.qq.com/document/path/101463) — WeCom 长连接消息格式
- [飞书消息接收事件](https://open.feishu.cn/document/server-docs/im-v1/message/events/receive) — Feishu event payload
- 钉钉机器人接收消息(同源 URL,Stream 模式)

---

## 7. 决策记录更新

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-07-29 | v1 | 初稿 Proposed;基于三轮 session/user/trace 设计讨论沉淀;定义 ChatContext 抽象 + 4 层架构 + 适配器注册表 |
| 2026-07-29 | v2 | (1) 增加 HTTP POST 作为第 4 类通道(`normalize_http`);(2) 显式定义跨进程传播机制(env var 协议);(3) 新增 §5.4 ARCHITECTURE.md 联动检查清单;(4) 扩展 §3 后果(跨进程统一 / HTTP 契约 / 安全脱敏);(5) §4.5 新增"绕过 ChatContext 直接 env var 透传"备选并否决 |
| 2026-07-29 | v3 → **Accepted** | 实施完成(PLAN P0-P11 全部 commit,455+ 回归测试全绿,GCL PASS)。状态从 Proposed → **Accepted**。 |