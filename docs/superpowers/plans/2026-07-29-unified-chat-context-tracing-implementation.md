# PLAN: 统一 Chat Context 追踪 — 实施计划

| 字段 | 值 |
|---|---|
| **Plan ID** | PLAN-2026-07-29-chat-context |
| **Date** | 2026-07-29 |
| **Related SPEC** | [SPEC-2026-07-29-chat-context](../specs/2026-07-29-unified-chat-context-tracing-design.md) |
| **Related ADR** | [ADR-001](../../architecture/ADR-001-unified-chat-context-tracing.md) |
| **Status** | Completed (2026-07-29) — 17 commits · 455+ tests passing · GCL PASS |

> 本计划遵循 [AGENTS.md §4 Iron Rule](../../AGENTS.md):SPEC → PLAN → IMPLEMENT(TDD + GCL)。
> 任何 step 失败,回到上一 step 修复;不可跳过 step。

---

## 0. 前置条件

- [x] ADR-001 v2 已写入并冻结
- [ ] SPEC.md 已批准(本次 spec review 通过后)
- [ ] 本 PLAN 已批准
- [ ] Python 3.10+ 环境(`python3 --version`)
- [ ] 当前 `alicloud-terraform-ops` 与 `alicloud-aiops-ml` 测试全绿
- [ ] 已 git worktree 隔离开发分支(`feature/chat-context-tracing`)

---

## 1. 实施总览

### 1.1 任务清单(按依赖顺序)

| 阶段 | 任务 | 验证手段 | 预计 LOC |
|---|---|---|---|
| **P0** | 建 `alicloud-gcl-runner-ops/scripts/alicloud_shared/` 包骨架（重命名自原 `alicloud-shared-runtime/`） | 包 import 成功 | ~30 |
| **P1** | TDD: `ChatContext` dataclass + `redact_raw()` | 单元测试全绿 | ~60 |
| **P2** | TDD: ContextVar + `bind()` / `current()` | 单元测试全绿 | ~30 |
| **P3** | TDD: 适配器注册表 + `normalize_cli()` 默认 | 单元测试全绿 | ~50 |
| **P4** | TDD: 4 个 adapter(wecom / feishu / dingtalk / http) | 单元测试全绿 | ~100 |
| **P5** | TDD: `bind_from_env()` helper | 单元测试全绿 | ~20 |
| **P6** | TDD: `subprocess_utils.safe_subprocess_env()` | 单元测试全绿 | ~20 |
| **P7** | TDD: `ExecutionTrace` 加字段 + `new()` 工厂 | 现有测试全绿 + 新测试 | ~30 |
| **P8** | TDD: `TraceRun` 加字段 + `new()` 工厂 | 现有测试全绿 + 新测试 | ~30 |
| **P9** | TDD: `wizard_cli.py` 集成(`bind_from_env` + 透传) | wizard 现有测试全绿 | ~20 |
| **P10** | 每个 skill `main()` 加 `bind_from_env()` | 现有测试全绿 + 集成测试 | ~10 × N |
| **P11** | ARCHITECTURE.md 联动更新 | 链接有效 + 章节引用 | ~10 |
| **P12** | GCL 评审 + 合并到主分支 | GCL 通过 | — |

**总计**:~440 LOC 新代码 + 现有代码 0 改动(只加字段)。

### 1.2 TDD 纪律(强制)

每个 TDD step 必须遵循:

```
RED     → 写一个失败的测试,运行确认失败
GREEN   → 写最少代码让测试通过,运行确认通过
REFACTOR → 清理代码,测试保持绿
```

**禁止**:
- 跳过 RED 直接写实现
- 同时写多个 step 的实现
- "测试以后再补"

---

## 2. 分阶段详细计划

### P0: 包骨架

**目标**:`alicloud-gcl-runner-ops/scripts/alicloud_shared/` 可被 import。

**文件**:
- `alicloud-gcl-runner-ops/scripts/alicloud_shared/__init__.py`
- `alicloud-gcl-runner-ops/scripts/alicloud_shared/chat_context.py`
- `alicloud-gcl-runner-ops/scripts/alicloud_shared/adapters/__init__.py`
- `alicloud-gcl-runner-ops/scripts/alicloud_shared/subprocess_utils.py`
- `alicloud-gcl-runner-ops/tests/alicloud_shared/`（测试目录）

**验证**:
```bash
cd alicloud-gcl-runner-ops
python3 -c "import sys; sys.path.insert(0, 'scripts'); from alicloud_shared.chat_context import ChatContext"
```

**Gate**:全部占位模块可 import 无报错。

---

### P1: `ChatContext` + `redact_raw`

**RED**:写 `tests/test_chat_context.py` 测试:
- `ChatContext` 字段定义正确(frozen,所有字段必填)
- `redact_raw({"authorization": "x", "foo": "y"})` 返回 `{"foo": "y"}`
- `redact_raw` 大小写不敏感(同时匹配 `Authorization` 和 `authorization`)

**GREEN**:实现 `ChatContext` dataclass + `redact_raw()` 函数。

**REFACTOR**:抽常量 `RAW_REDACT_KEYS` 到模块顶部。

**验证**:`pytest tests/test_chat_context.py -v` 全绿。

---

### P2: ContextVar + bind / current

**RED**:测试:
- `bind(ctx)` 后 `current()` 返回该 ctx
- 默认状态 `current()` 返回 None
- 嵌套 `bind(ctx1); bind(ctx2); current() == ctx2`(覆盖语义)
- ContextVar 在不同线程独立(token 测试)

**GREEN**:实现 `ContextVar[ChatContext | None]` + `bind()` / `current()` 函数。

**REFACTOR**:无。

**验证**:pytest 全绿。

---

### P3: 适配器注册表 + `normalize_cli`

**RED**:测试:
- `register_adapter("foo", fn)` 后 `normalize("foo", payload)` 调用 `fn(payload)`
- 未注册的 platform 调用 `normalize()` 走 `normalize_cli(source=platform)` 默认
- `normalize_cli()` 返回 `user_id=os.environ.get("USER","anonymous")` 或 `anonymous`

**GREEN**:实现注册表 + 默认 `normalize_cli()`。

**REFACTOR**:无。

**验证**:pytest 全绿。

---

### P4: 4 个 Adapter(TDD 逐个)

**RED**:对每个 adapter 写测试,先 RED。

#### P4.1 `normalize_wecom(body)`

测试:
- 群聊:`{"chattype": "group", "chatid": "oc_abc", "from": {"userid": "u1"}}` → `session_id="oc_abc"`
- 单聊无 chatid:`{"chattype": "single", "from": {"userid": "u1"}}` → `session_id="synth-p2p-u1-{ts}"`
- `raw` 字段走 `redact_raw`

#### P4.2 `normalize_feishu(event)`

测试:
- `event["sender"]["sender_id"]["open_id"]` 作为 user_id
- `event["chat_id"]` 作为 session_id(单聊/群聊都有)
- `chat_type` 透传 event["chat_type"]

#### P4.3 `normalize_dingtalk(data)`

测试:
- `senderStaffId` 作为 user_id(假设已解密,见 §6 加密契约)
- `chatId` 作为 session_id
- `chatType == "1"` → `"p2p"`, `"2"` → `"group"`

#### P4.4 `normalize_http(headers, body, caller_id)`

测试:
- `headers["X-Chat-User-Id"]` 优先,缺失 → `caller_id` 兜底
- `body["session_id"]` 为 `"api:default"` → 走 fallback `http-{caller_id}-{ts}`
- `raw["headers"]` 走 `redact_raw`(Authorization 不应出现)

**GREEN**:逐个实现。

**REFACTOR**:统一 error handling(`KeyError` → 返回 normalize_cli fallback)。

**验证**:每个 adapter 单独跑 `pytest tests/test_adapters_<platform>.py -v` 全绿。

---

### P5: `bind_from_env()`

**RED**:测试:
- 无 `CHAT_PLATFORM` env → 不 bind,返回 None(静默降级)
- 有 `CHAT_PLATFORM=wecom` + 其他 CHAT_* → bind 完整 ChatContext
- 缺 `CHAT_USER_ID` → user_id="anonymous"

**GREEN**:实现 `bind_from_env()`。

**REFACTOR**:抽出 env var 名为常量。

**验证**:pytest 全绿。

---

### P6: `subprocess_utils.safe_subprocess_env`

**RED**:测试:
- `safe_subprocess_env()` 在父进程 `CHAT_PLATFORM=wecom` 时返回 `{"CHAT_PLATFORM": "wecom"}`
- `safe_subprocess_env({"OTHER": "x"})` 合并父 env + extra
- 显式覆盖:`safe_subprocess_env({"CHAT_PLATFORM": "feishu"})` 后 `CHAT_PLATFORM="feishu"`

**GREEN**:实现 `safe_subprocess_env(extra)` 函数。

**REFACTOR**:无。

**验证**:pytest 全绿。

---

### P7: `ExecutionTrace` 扩展

**RED**:测试 `alicloud-terraform-ops/scripts/test_execution_trace.py`:
- `ExecutionTrace.new(operation="test")` 自动从 `current()` 取 user_id / session_id / platform
- 旧 trace JSON(无 user_id/platform 字段)`from_dict()` 不抛错,字段=None
- `to_dict()` 输出包含新字段

**GREEN**:
- `ExecutionTrace` 加字段:`user_id: str | None = None`,`platform: str | None = None`,`chat_type: str | None = None`
- 实现 `ExecutionTrace.new()` 类方法
- `to_dict()` 包含新字段

**REFACTOR**:检查是否影响其他字段。

**验证**:
```bash
cd alicloud-terraform-ops
pytest scripts/test_execution_trace.py -v
```
全绿 + 新测试通过。

---

### P8: `TraceRun` 扩展

**RED**:测试 `alicloud-aiops-ml/test_trace_logger.py`:
- `TraceRun.new()` 自动从 `current()` 取 user_id / session_id / platform
- 旧 JSON 兼容
- `to_dict()` 包含新字段

**GREEN**:同 P7,作用于 `TraceRun`。

**REFACTOR**:无。

**验证**:
```bash
cd alicloud-aiops-ml
pytest test_trace_logger.py -v
```

---

### P9: `wizard_cli.py` 集成

**RED**:测试 `alicloud-terraform-ops/scripts/test_wizard_cli.py`(若无则新建):
- `WizardRunner.run_nl2cl` 启动时调 `bind_from_env()`
- `WizardSession.session_id` == `persist_dry_run_trace` 的 session_id
- `WizardSession.user_id` 来自 ChatContext 或 CLI fallback

**GREEN**:
- `run_nl2hcl` / `run_import` / `resume` 入口加 `bind_from_env()`
- `WizardSession.__init__` 从 `current()` 读 user_id / session_id
- `persist_dry_run_trace(...)` 调用加 `user_id=user_id, platform=platform` 参数

**REFACTOR**:抽 `bind_from_env()` 调用到 `WizardRunner.__init__`。

**验证**:`pytest scripts/test_wizard_cli.py -v` 全绿。

---

### P10: 每个 skill `main()` 加 `bind_from_env()`

**扫描**:`grep -r "def main" alicloud-*/scripts/*.py | wc -l` 得 skill 数量 N。

**批量修改**:提供 codemod 脚本(临时):

```python
# scripts/add_bind_from_env.py
"""在每个 skill main() 第一行加 bind_from_env()。"""
import re
from pathlib import Path

HEADER = """from alicloud_shared.chat_context import bind_from_env
bind_from_env()
"""

# 在每个 main() 函数体开头插入
for path in Path("alicloud-*-ops").rglob("scripts/*.py"):
    text = path.read_text()
    # 找到 def main(: 下一个非空行前插入
    if "def main(" in text and "bind_from_env()" not in text:
        # ... (具体替换逻辑)
        pass
```

**手动确认**:codemod 跑完后逐个 skill 跑测试。

**Gate**:
```bash
pytest alicloud-terraform-ops/scripts/test_*.py -v
pytest alicloud-aiops-ml/test_*.py -v
```
全部通过。

---

### P11: ARCHITECTURE.md 联动

**动作**:
1. 在 `ARCHITECTURE.md` §接入适配层 加引用:`> Trace schema 详见 [SPEC-2026-07-29-chat-context](../superpowers/specs/2026-07-29-unified-chat-context-tracing-design.md)`
2. §可观测性 加一行:平台字段(platform / user_id / session_id)并入 Langfuse Trace
3. §双模式接入 加澄清:"本仓库 REST API" 与 "Nanobot OpenAI API" 是两个独立契约

**验证**:
- 链接 anchor 跳转正确(AGENTS.md §18.6 DL-R1 slug 规则)
- `grep -c "SPEC-2026-07-29-chat-context" ARCHITECTURE.md` ≥ 1

---

### P12: GCL 评审 + 合并

**流程**(per AGENTS.md §12 / `.claude/rules/gcl-rules.md`):
1. **Pre-flight**: `python3 scripts/check_gcl_trigger.py "<变更描述>" <files>` 退出码 = 1(必须 GCL)
2. **Worktree**: `git worktree add ../aliyun-skills-impl -b feature/chat-context-tracing`
3. **Multi-sub-Agent GCL**:Generator 经济模型 + 2 个 Critic 旗舰模型并行评审
4. **合并**:评审通过后 `git checkout main && git merge feature/chat-context-tracing --no-ff`
5. **Worktree 清理**: `git worktree remove ../aliyun-skills-impl`

**Gate**:GCL 通过 + 主分支 pytest 全绿。

---

## 3. 风险与回滚

| 风险 | 触发条件 | 回滚动作 |
|---|---|---|
| 现有测试因 schema 变更大面积失败 | P7 / P8 后回归测试红 | 暂存变更,逐个适配 |
| `bind_from_env()` 引入性能开销 | 调用频次 10000+ /s 时 | 评估:加 `@lru_cache` 或只在 trace 时读 |
| WizardSession 与 ExecutionTrace session_id 不一致 | P9 测试失败 | 修复 wizard 入口绑定逻辑 |
| Nanobot 集成跨团队协调失败 | 暂不在本仓库范围 | 由 Nanobot 团队独立跟进,接口契约已在 SPEC §5.4 |

---

## 4. 完成标准(Definition of Done)

- [x] P0-P12 全部 step 通过
- [x] 所有单元测试 + 集成测试全绿(455+ tests passing)
- [x] GCL 评审通过(2 个 Critic 签字)
- [x] ARCHITECTURE.md 联动更新已 commit
- [x] worktree 已合并到 main 并清理
- [x] 没有遗留 uncommitted 变更
- [x] ADR-001 / SPEC / PLAN 三文档保持同步

---

## 5. 不在范围内

- Nanobot 端入口实现(WeCom WS / Feishu Webhook / DingTalk Stream / HTTP API handler)
- Trace 上报到 Langfuse(Phase 3)
- user_id 脱敏 / 合规审计增强
- 多租户隔离

---

## 6. 参考资料

- [SPEC-2026-07-29-chat-context](../specs/2026-07-29-unified-chat-context-tracing-design.md)
- [ADR-001 Unified Chat Context Tracing](../../architecture/ADR-001-unified-chat-context-tracing.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [AGENTS.md §4 Mandatory Development Workflow](../../AGENTS.md)
- [AGENTS.md §12 Generator-Critic-Loop](../../AGENTS.md)
- [`.claude/rules/gcl-rules.md`](../../../.claude/rules/gcl-rules.md)
- [`.claude/rules/git-worktree.md`](../../../.claude/rules/git-worktree.md)