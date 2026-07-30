# SPEC: 统一 Chat Context 追踪(跨 IM 平台 + HTTP POST + CLI)

| 字段 | 值 |
|---|---|
| **Spec ID** | SPEC-2026-07-29-chat-context |
| **Date** | 2026-07-29 |
| **Status** | Implemented (2026-07-29) |
| **Related ADR** | [ADR-001 Unified Chat Context Tracing](../../architecture/ADR-001-unified-chat-context-tracing.md) |
| **Related ARCH** | [ARCHITECTURE.md](../../ARCHITECTURE.md) §接入适配层 / §输出适配层 / §可观测性 / §双模式接入 |
| **Author** | Skills 平台架构组 |

> 本 SPEC 是 [ADR-001](../../architecture/ADR-001-unified-chat-context-tracing.md) 的实现规格书。
> ADR 定义"做什么 & 为什么";本 SPEC 定义"验收边界 & 实现契约"。
> 冲突时以 ADR 为准。

---

## 1. 背景与目标

### 1.1 问题

阿里云运维 Skills 当前通过 Nanobot 接入 WeCom / 飞书 / 钉钉 / HTTP POST / CLI 多个通道,但:

- `ExecutionTrace` 与 `TraceRun` **没有** `user_id` / `platform` 字段
- wizard 的 `session_id` 是自造 `session-YYYYMMDD-HHMMSS`,**无法**与 IM 平台的真实 chat ID 对应
- 跨平台聚合分析缺统一维度
- WeCom 单聊场景**没有**原生 session_id,需业务侧合成

### 1.2 目标

| # | 目标 | 度量 |
|---|---|---|
| **G1** | Trace 包含 `user_id` / `session_id` / `platform` / `chat_type` 四字段 | 字段缺失率 = 0%(已 bind 时) |
| **G2** | Skill 业务代码**不感知**任何具体 IM 平台 | `grep -r "import wecom\|import lark\|import dingtalk" alicloud-*-ops/` 命中 = 0 |
| **G3** | 新增 IM 平台**只改 adapter 层**,不动 skill | 新平台 diff = `adapters/<platform>.py` + 1 行 register |
| **G4** | CLI / REST / HTTP POST 场景都能跑,**有合理默认值** | 无 bind 时不崩,字段降级 None |
| **G5** | 跨进程边界(Nanobot → skill)稳定传 ID | 进程间传播用 env var,见 §5 契约 |

### 1.3 非目标

- 不做 trace 数据上报到 Langfuse / 审计系统(属于 Phase 3)
- 不做 user_id 脱敏 / 哈希(留待合规需求)
- 不做 session TTL 自动归档
- 不改 Nanobot 自身的 session 抽象(借鉴语义,不复用对象)

---

## 2. 范围

### 2.1 In Scope

| 范围 | 说明 |
|---|---|
| 新增共享包 | `alicloud-gcl-runner-ops/scripts/alicloud_shared/` 含 `chat_context.py` + `adapters/` 子包（落点重命名自原 `alicloud-shared-runtime/`） |
| Trace schema 扩展 | `ExecutionTrace` / `TraceRun` 各加 3 字段:`user_id` / `platform` / `chat_type` |
| 工厂方法 | `ExecutionTrace.new()` / `TraceRun.new()` 自动从 contextvar 注入 |
| Wizard 集成 | `wizard_cli.py` 入口 bind CLI context,`persist_dry_run_trace` 透传 user_id / platform |
| 每个 skill 入口 | `main()` 开头加 `bind_from_env()` 调用 |
| 4 个 adapter | wecom / feishu / dingtalk / http(默认 CLI 在主模块) |
| 跨进程传播契约 | env var 协议(`CHAT_PLATFORM` / `CHAT_USER_ID` / `CHAT_SESSION_ID` / `CHAT_TYPE`) |

### 2.2 Out of Scope

- **Nanobot 入口实现**:WeCom WS handler / Feishu webhook / DingTalk Stream / HTTP API 处理器——由 Nanobot 仓库在本 SPEC 批准后单独实现(接口在本 SPEC §5 定义)
- **Trace 上报到 Langfuse**:Phase 3 工作,见 ADR-001 §5.3
- **改 ARCHITECTURE.md 正文**:本 SPEC 完成后由 ARCH owner 同步(见 §9 联动检查清单)

---

## 3. 核心概念与关系

### 3.1 三个 ID 的语义边界

```
user_id      → 谁(人或服务背后的人)
session_id   → 一次完整任务/对话(可跨多个 trace)
trace_id     → 单次 skill 执行(每次执行唯一)
```

**关系**:`trace ⊂ session ⊂ user`(反向不成立)

### 3.2 WizardSession 与 ExecutionTrace 的关系

**WizardSession** 是 wizard 流程的载体(`wizard_cli.py:85`),内含多个步骤(`WizardStep`)。每个 `WizardStep` 对应**一次或多次** skill 执行。

| 概念 | 粒度 | 数量关系 |
|---|---|---|
| WizardSession | 一次完整 wizard 交互 | 1 个 session |
| ExecutionTrace | 一次 skill 执行 | N 个 trace / 1 个 session(N ≥ 1) |

**契约**:`WizardSession.session_id == ChatContext.session_id`,二者绑定为同一个值。当 wizard 入口 bind chat context 时:

```python
# wizard_cli.py 入口
ctx = bind_from_env_or_default()  # 从 env 拿或降级 CLI
session = WizardSession(
    session_id=ctx.session_id,    # ✅ 与 ChatContext 一致
    user_id=ctx.user_id,
    ...
)
```

**结果**:wizard 内的每条 ExecutionTrace 写入 trace 时,`session_id` 字段 = WizardSession.session_id = ChatContext.session_id,三者完全对齐。

### 3.3 platform 与 chat_type 字段取值枚举

| 字段 | 取值 |
|---|---|
| `platform` | `"wecom"` \| `"feishu"` \| `"dingtalk"` \| `"http"` \| `"cli"` |
| `chat_type` | `"p2p"` \| `"group"` \| `"api"` \| `"n/a"` |

**约定**:`platform` 与 `chat_type` 是**封闭枚举**,新增值需更新本 SPEC + ADR。

---

## 4. 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Chat APP Adapter (平台专属)                        │
│    normalize_wecom / normalize_feishu / normalize_dingtalk │
│    normalize_http / normalize_cli (default)                  │
└────────────────┬────────────────────────────────────────────┘
                 ↓ ChatContext (frozen dataclass)
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: ChatContext (共享运行时)                            │
│    { user_id, session_id, platform, chat_type, raw }        │
│    ContextVar + bind() / current()                          │
└────────────────┬────────────────────────────────────────────┘
                 ↓ 自动注入
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Skill 业务逻辑                                     │
│    ExecutionTrace.new() / TraceRun.new() 工厂方法           │
│    bind_from_env() skill 入口 helper                        │
└────────────────┬────────────────────────────────────────────┘
                 ↓ 落盘格式跨平台一致
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Trace 落地 (JSON 落盘 / 上报 Langfuse)            │
└─────────────────────────────────────────────────────────────┘
```

详见 [ADR-001 §2.1](../../architecture/ADR-001-unified-chat-context-tracing.md#21-4-层职责)。

---

## 5. 约束与契约

### 5.1 跨进程传播契约(强制)

**Nanobot 调 skill 的 spawn 关系**:

```python
# nanobot 入口必须
env = os.environ.copy()
env["CHAT_PLATFORM"]   = ctx.platform
env["CHAT_USER_ID"]    = ctx.user_id
env["CHAT_SESSION_ID"] = ctx.session_id
env["CHAT_TYPE"]       = ctx.chat_type
subprocess.run([python, skill_path, ...], env=env)   # ✅ 必须传 env
```

**Skill 入口必须**:

```python
# skill.py main() 第一行
bind_from_env()  # 从 env var 读并 bind,缺失则静默降级
```

### 5.2 多级 subprocess 契约(强制)

任何 skill 内部 `subprocess.run()` 调下层 skill 时:

```python
# ✅ 正确:保留父进程 env
subprocess.run(cmd, env={**os.environ, "OTHER": value})

# ❌ 错误:覆盖掉 CHAT_* 系列
subprocess.run(cmd, env={"OTHER": value})  # CHAT_PLATFORM 等丢失
```

**实现位置**:`alicloud-gcl-runner-ops/scripts/alicloud_shared/subprocess_utils.py` 提供 `safe_subprocess_env()` 包装:

```python
def safe_subprocess_env(extra: dict | None = None) -> dict:
    """保留父进程 CHAT_* env,叠加 extra"""
    preserved = {k: v for k, v in os.environ.items() if k.startswith("CHAT_")}
    return {**preserved, **(extra or {})}
```

### 5.3 HTTP POST 调用方契约(强制)

调用 `POST /v1/chat/completions` 时:

| 必填字段 | 位置 | 说明 |
|---|---|---|
| `session_id` | body | **必填**,否则 Nanobot 默认 `"api:default"` 致 trace 混在一起 |
| `X-Chat-User-Id` | header | **强烈推荐**,标识服务背后的真人 |
| `Authorization` | header | Bearer Token(本地访问可省) |

**未传 `session_id` 的 fallback**:`normalize_http()` 自动生成 `http-{caller_id}-{timestamp}`,见 [ADR-001 §2.6](../../architecture/ADR-001-unified-chat-context-tracing.md#26-http-post-作为第-4-类通道)。

### 5.4 调用方契约:Nanobot 入口接口

Nanobot 端要实现的接口(本仓库不实现,但接口契约在此):

```python
def normalize_wecom(body: dict) -> ChatContext: ...
def normalize_feishu(event: dict) -> ChatContext: ...
def normalize_dingtalk(data: dict) -> ChatContext: ...
def normalize_http(headers: dict, body: dict, caller_id: str) -> ChatContext: ...
def normalize_cli() -> ChatContext: ...

def register_adapter(platform: str, fn: Callable) -> None: ...
def bind(ctx: ChatContext) -> None: ...
def current() -> ChatContext | None: ...
def bind_from_env() -> None: ...  # skill 入口用
```

---

## 6. 安全契约

### 6.1 raw 字段脱敏黑名单

`ChatContext.raw` **禁止**直接放原始 payload——adapter 层必须先 redact。**强制黑名单**:

```python
RAW_REDACT_KEYS = frozenset({
    "authorization", "x-auth-token", "cookie", "set-cookie",
    "access_token", "secret", "api_key", "apikey",
    "password", "pwd", "credential", "private_key",
})
```

**实现位置**:`alicloud-gcl-runner-ops/scripts/alicloud_shared/chat_context.py` 提供 `redact_raw(raw_dict)` 函数,所有 adapter **必须调用**后赋值给 `raw` 字段。

### 6.2 trace 落盘目录访问控制

trace JSON 写入 `alicloud-gcl-runner-ops/scripts/alicloud_shared/...` 或现有 `${SKILLS_DIR}/.runtime/audit/` 目录,**假定**该目录受 ACL 控制(仅运维账号可读)。**不在本 SPEC 范围**——由基础设施团队保证。

### 6.3 user_id 处理

- **不重编码**:跨平台 user_id 保留平台原始格式(便于审计回溯)
- **不脱敏**:当前不做 hash;若合规要求,通过 redact 黑名单扩展

---

## 7. 兼容性

### 7.1 向后兼容(读旧 trace)

旧 trace 文件**没有** `user_id` / `platform` / `chat_type` 字段。新代码读旧文件时:

- `from_dict()` / `TraceRun.from_dict()` 缺失字段 → 默认值 `None`(不抛错)
- `to_dict()` 输出新字段(值为 None)

### 7.2 向后兼容(不 bind)

Skill 在没 bind chat context 时(纯 CLI / 测试):

- 字段全部为 `None`
- **不抛错**
- trace 仍可写入(只是缺 user/session 信息)

### 7.3 env var 命名冲突预防

`CHAT_*` 前缀已避开常见系统 env var。如未来发现冲突,在 `bind_from_env()` 中加 `_CONFLICTING_VARS` 检查表。

---

## 8. 验收标准

| # | 标准 | 验证手段 |
|---|---|---|
| **AC-1** | 4 个 IM + HTTP + CLI 各跑一次,trace JSON 字段名一致(除 `platform` 与 `raw`) | 单元测试 + 集成测试 |
| **AC-2** | `grep -r "import wecom\|import lark\|import dingtalk" alicloud-*-ops/` 命中 = 0 | CI 检查脚本 |
| **AC-3** | 加 `normalize_slack()` 后跑通原有 trace 测试,**零 skill 改动** | TDD:先写 Slack adapter 测试,实现后跑 |
| **AC-4** | 不 bind context 直接跑 wizard,trace 字段全部 None | 单元测试 |
| **AC-5** | WeCom 单聊合成 session_id 含 `synth-p2p` 前缀或 `raw.session_synthesized=true` | 单元测试 |
| **AC-6** | Nanobot → skill subprocess 链路,skill 内 `os.environ["CHAT_PLATFORM"]` == Nanobot 入口设置值 | 集成测试 |
| **AC-7** | HTTP POST 调方不传 `session_id` 时,trace **不**出现 `session_id="api:default"` | 单元测试 |
| **AC-8** | `raw` 字段不含黑名单 key(authorization / cookie / secret 等) | 单元测试 + fuzz |
| **AC-9** | WizardSession.session_id == ExecutionTrace.session_id | 单元测试 |
| **AC-10** | 现有 trace 测试(terraform-ops test_execution_trace.py / aiops-ml test_trace_logger.py)全部通过 | 回归测试 |

---

## 9. 联动检查清单(落地时必做)

落地本 SPEC 时,必须同步处理:

| 项 | 责任方 | 动作 |
|---|---|---|
| [ARCHITECTURE.md](../../ARCHITECTURE.md) §接入适配层 | ARCH owner | 引用本 SPEC 作为 trace schema 来源 |
| [ARCHITECTURE.md](../../ARCHITECTURE.md) §可观测性 | ARCH owner | 平台字段并入 Langfuse Trace 维度 |
| [ARCHITECTURE.md](../../ARCHITECTURE.md) §双模式接入 | ARCH owner | 区分"Nanobot OpenAI API"与"本仓库 REST API" |
| Nanobot 入口(WS handler / Webhook / HTTP API) | Nanobot 团队 | 调用 `register_adapter` + `bind` + `env=` 注入 |
| 每个 skill `main()` | 本仓库 | 加 `bind_from_env()` 入口(详见 [PLAN.md](../plans/2026-07-29-unified-chat-context-tracing-implementation.md)) |

---

## 10. 风险与未决

| 风险 | 缓解 |
|---|---|
| 现有 skill 数量多(>50),加 `bind_from_env()` 工作量大 | 提供 codemod 脚本批量加;按优先级分批 |
| Nanobot 入口不在本仓库,集成依赖外部团队 | SPEC §5.4 明确接口契约;先在本仓库 mock 测试通过 |
| WeCom 单聊 session 合成时间窗(30 分钟)是启发式 | 在 adapter 配置文件中显式标注,业务方知情 |
| trace `raw` 字段体积可能膨胀 | adapter 层强制 redact + 截断(>1KB 截断) |

---

## 附录 A:文件清单

详见 [PLAN.md](../plans/2026-07-29-unified-chat-context-tracing-implementation.md) §文件清单。

## 附录 B:参考资料

- [ADR-001 Unified Chat Context Tracing](../../architecture/ADR-001-unified-chat-context-tracing.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [AGENTS.md §4 Mandatory Development Workflow](../../AGENTS.md)
- [AGENTS.md §15 Runtime Harness Integration](../../AGENTS.md)
- [HKUDS/nanobot](https://github.com/HKUDS/nanobot)