# Runtime Harness Langfuse Session & Trace 集成方案

> **版本**: v2.2  
> **状态**: 已落地并通过灰度 Skill 集成测试；Trace Judge 默认策略已确定（设计规格，runtime 尚未接入）  
> **最后更新**: 2026-06-17  
> **适用范围**: 当前 `skillopt-lib.sh` bash 体系  
>  
> ⚠️ **注意**：本文档中关于 Trace Judge（LLM/rule_engine）的默认开启、配置变量、判定流程等描述为**设计规格**，当前 `alicloud-runtime-harness-ops/scripts/harness-core-lib.sh` 与 `alicloud-skillopt-ops/scripts/skillopt-core-lib.sh` 暂未实现相关逻辑，仅保留 `skillopt.trace_judgement` span 的写入位置。

---

## 1. 概述

### 1.1 目标

在当前 Agent Skill 体系（`skillopt-lib.sh`）下，实现 Langfuse Session 和 Trace 管理，支持：

- 多 IDE 环境（Trae、CodeBuddy、Claude Code、Open Code、PI Agent 等）的多任务窗口隔离
- 每个 Session 下的技能调用追踪
- 与现有功能（自修复、熔断器、指标导出）无缝集成

### 1.2 当前落地状态

截至 2026-06-17，Session & Trace 方案已完成试点和灰度接入验证。

已完成接入并验证的 Skill：

| 类型 | Skill | 验证状态 |
|------|-------|----------|
| 监控 | `alicloud-cms-ops` | 已接入 |
| 计算 | `alicloud-ecs-ops` | 已接入 |
| 网络入口 | `alicloud-slb-ops` | 已接入 |
| 数据库 | `alicloud-rds-ops` | 已接入 |
| 缓存 | `alicloud-redis-ops` | 已接入 |
| 容器 | `alicloud-ack-ops` | 已接入，失败链路入库验证通过 |
| 数据库诊断 | `alicloud-das-ops` | 已接入，失败链路入库验证通过 |
| 网络入口 | `alicloud-alb-ops` | 已接入，成功链路入库验证通过 |
| 云网络 | `alicloud-cen-ops` | 已接入，成功链路入库验证通过 |

最新灰度集成测试：

```bash
bash scripts/test-langfuse-gray-skills.sh
```

验证结果：

```text
PASS=52, FAIL=0, TOTAL=52
```

验证覆盖：

- `scripts/skillopt-lib.sh` 路径规范
- wrapper 使用 `source "$SCRIPT_DIR/skillopt-lib.sh"`
- `bash -n` 语法检查
- `zsh source` 兼容检查
- 本地 trace 文件闭合
- Langfuse trace 直查
- 同一轮多 Skill 共用同一个 `SKILLOPT_SESSION_ID`
- trace-level input/output 非空

### 1.3 核心约束

| 约束 | 说明 |
|------|------|
| **纯 bash** | 不引入微服务、数据库、独立进程 |
| **嵌入现有流程** | 集成到 `skillopt_wrap()` 中 |
| **文件持久化** | 使用 `.runtime/` 目录存储 Session/Trace 状态 |
| **IDE 交互** | 通过环境变量接收 IDE 的 Session 上下文 |
| **同步上报，失败不阻断** | curl 同步发送到 Langfuse API；失败时静默忽略，不影响 Skill 主流程 |
| **Langfuse/Judge 解耦** | `SKILLOPT_LANGFUSE_ENABLED` 只控制远端 HTTP 镜像；`SKILLOPT_JUDGE_ENABLED` 只控制 judge metadata |
| **Local-first trace** | 每次 `skillopt_wrap()` **始终**写 `${SKILLS_DIR}/.runtime/traces/<skill-tag>/trace-*.json`；Langfuse 为 optional mirror |
| **Span 事实不可篡改** | Span 的 level/statusMessage/output/fact_* 只由运行时事实决定，LLM Judge 不允许改写 |
| **Judge 默认开启（设计规格，runtime 尚未接入）** | `SKILLOPT_JUDGE_ENABLED=true`、`SKILLOPT_JUDGE_MODE=llm`；LLM 不可用时降级到 rule_engine |
| **Trace TTL** | 默认 7 天（`TRACE_KEEP_DAYS`）；`make memory-maintain-apply` 与 logs 同级 retention |

### 1.4 依赖

仅使用现有 Runtime Harness 已声明的依赖：

| 依赖 | 用途 |
|------|------|
| `bash >= 4.x` | 核心逻辑 |
| `jq` | JSON 处理 |
| `curl` | Langfuse HTTP 上报 |
| `md5` / `md5sum` | 工作目录 hash（兜底 Session ID） |

---

## 2. 数据模型

### 2.1 层级关系

```
IDE 窗口 (Trae / Claude Code / Open Code / ...)
│
├── Session ID = f(IDE 环境变量 或 工作目录+日期)
│   └── 持久化: .runtime/sessions/<skill-tag>/skillopt-session-{session_id}.json
│
└── Trace ID = 每次 skillopt_wrap() 调用生成一个
    └── 持久化: .runtime/traces/<skill-tag>/{trace_id}.json
    │
    └── Span = 修复/优化/熔断等子操作
```

### 2.2 Session ID 生成规则

**优先级（从高到低）**：

| 优先级 | 来源 | 格式 | 示例 |
|--------|------|------|------|
| 1 | 显式环境变量 `SKILLOPT_SESSION_ID` | 用户自定义 | `sess-my-custom-id` |
| 2 | IDE 环境变量 | `sess-{ide}-{id}` | `sess-trae-task-abc123` |
| 3 | **兜底**：工作目录 hash + 日期 | `sess-{hash}-{date}` | `sess-a1b2c3d4-20260617` |

**Session ID 永远不为空**。

#### IDE 环境变量映射

| IDE | 环境变量 | 示例 Session ID |
|-----|---------|----------------|
| Trae | `TRAE_SESSION_ID` | `sess-trae-task-abc123` |
| Claude Code | `CLAUDE_CONVERSATION_ID` | `sess-claude-conv-xyz789` |
| Open Code | `OPENCODE_SESSION_ID` | `sess-opencode-session-def456` |
| CodeBuddy | `CODEBUDDY_SESSION_ID` | `sess-codebuddy-task-ghi012` |
| 通用 | `IDE_SESSION_ID` | `sess-ide-jkl345` |

#### 兜底方案：工作目录 hash + 日期

当没有任何 IDE 环境变量时，自动生成：

```bash
workdir_hash = md5($(pwd))[:8]    # 取前 8 位
today        = date +%Y%m%d       # 如 20260617
session_id   = "sess-${workdir_hash}-${today}"
```

**效果**：

```
Claude Code 对话 A（工作目录: /Users/xxx/project-a）:
  Session: sess-a1b2c3d4-20260617
  ├── Trace 1: CMS DescribeMetricList
  └── Trace 2: ECS DescribeInstances

Claude Code 对话 B（同一工作目录，同一天）:
  Session: sess-a1b2c3d4-20260617  ← 自动归到同一 Session
  └── Trace 1: RDS DescribeDBInstances

Claude Code 对话 C（不同工作目录: /Users/xxx/project-b）:
  Session: sess-e5f6g7h8-20260617  ← 不同 Session
  └── Trace 1: OSS GetBucketStat

第二天再调用:
  Session: sess-a1b2c3d4-20260618  ← 新的一天，新 Session
```

### 2.3 Trace ID 生成规则

每次 `skillopt_wrap()` 调用生成一个 Trace ID：

```bash
trace_id = "trace-{session_id}-{timestamp}-{RANDOM}"
```

示例：`trace-sess-a1b2c3d4-20260617-1718600000-12345`

### 2.4 Session 数据结构

```json
{
    "session_id": "sess-a1b2c3d4-20260617",
    "source": "fallback",
    "workdir": "/Users/xxx/project-a",
    "workdir_hash": "a1b2c3d4",
    "skill": "cms",
    "platform": "unknown",
    "created_at": "2026-06-17T10:00:00+0800",
    "last_active": "2026-06-17T10:15:00+0800",
    "trace_count": 5,
    "status": "active"
}
```

**Phase 3 TEL 扩展**（`skillopt-session-*.json`，2026-06）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `coding_agent` | string | Session 级默认 Agent（`skillopt_resolve_coding_agent()`） |
| `agent_model` | string | 最近 `agent_turn` 的 model；缺省 `"unknown"` |
| `llm_usage_total` | object | `{prompt_tokens, completion_tokens, total_tokens}` 跨 trace 累计 |
| `llm_usage_by_agent_model` | array | 按 `(coding_agent, model, source)` 分桶 |
| `context_metadata` | object | Phase 4.5 MCP 预留；默认 `{}` |

`trace_end` 时将 trace 的 `llm_generations[]` rollup 进 Session；`HARNESS_AGENT_TURN_USAGE`（legacy `SKILLOPT_AGENT_TURN_USAGE`）在 `trace_start` 注入 agent turn。Phase 4 IDE hook 亦可写入 sidecar `.runtime/token/context/agent-turn-latest.json`（env 优先）。

```json
{
    "session_id": "sess-a1b2c3d4-20260617",
    "coding_agent": "cursor",
    "agent_model": "claude-sonnet-4",
    "llm_usage_total": {"prompt_tokens": 120000, "completion_tokens": 8000, "total_tokens": 128000},
    "llm_usage_by_agent_model": [
        {"coding_agent": "cursor", "model": "claude-sonnet-4", "source": "agent_turn", "prompt_tokens": 110000, "completion_tokens": 7500, "total_tokens": 117500}
    ],
    "context_metadata": {}
}
```

### 2.5 Trace 数据结构

```json
{
    "trace_id": "trace-sess-a1b2c3d4-20260617-1718600000-12345",
    "session_id": "sess-a1b2c3d4-20260617",
    "product": "cms",
    "action": "DescribeMetricList",
    "params": "--Namespace acs_ecs_dashboard --MetricName CPUUtilization",
    "start_time": "2026-06-17T10:15:00+0800",
    "end_time": "2026-06-17T10:15:05+0800",
    "duration_ms": 5000,
    "status": "success",
    "error_code": "",
    "spans": [
        {
            "span_id": "span-cli-1718600001-23456",
            "name": "aliyun.cli",
            "level": "ERROR",
            "status_message": "Throttling.User: request was throttled",
            "status": "failed",
            "timestamp": "2026-06-17T10:15:01+0800",
            "metadata": {
                "record_type": "fact",
                "fact_source": "skillopt_runtime",
                "fact_status": "failed",
                "fact_status_source": "exit_code",
                "span_role": "aliyun_cli",
                "criticality": "critical",
                "attempt": 1,
                "exit_code": 1,
                "error_code": "Throttling.User",
                "error_type": "throttling_error"
            }
        },
        {
            "span_id": "judge-trace-sess-a1b2c3d4-20260617-1718600000-12345",
            "name": "skillopt.trace_judgement",
            "level": "WARNING",
            "statusMessage": "Trace repaired after initial throttling error",
            "status": "success",
            "timestamp": "2026-06-17T10:15:05+0800",
            "metadata": {
                "record_type": "trace_judgement",
                "trace_display_severity": "WARNING",
                "judge_effective_type": "rule_engine",
                "judge_fallback": true
            }
        }
    ],
    "metadata": {
        "record_type": "trace_summary",
        "fact_final_status": "success",
        "fact_has_error_span": true,
        "fact_error_span_count": 1,
        "fact_failed_critical_span_count": 0,
        "fact_repair_attempted": true,
        "fact_repair_success": true,
        "rule_final_outcome": "repaired_success",
        "rule_final_severity": "WARNING",
        "rule_should_mark_trace_error": false,
        "judge_enabled": true,
        "judge_configured_mode": "llm",
        "judge_type": "llm_as_a_judge",
        "judge_effective_type": "rule_engine",
        "judge_fallback": true,
        "judge_fallback_reason": "missing_judge_endpoint",
        "judge_policy_version": "skillopt-trace-judge-v1",
        "judge_final_outcome": "repaired_success",
        "judge_final_severity": "WARNING",
        "judge_should_mark_trace_error": false,
        "judge_overrode_rule": false,
        "trace_display_severity": "WARNING",
        "trace_display_severity_source": "rule_engine_fallback"
    }
}
```

### 2.6 Span 事实层与 Trace Judge 层

最终设计将链路信息拆为两层：

| 层级 | 职责 | 是否允许 LLM 修改 |
|------|------|------------------|
| Span | 忠实记录每个执行步骤的真实结果，例如 CLI exit code、错误码、原始 output、`level`、`statusMessage` | 不允许 |
| Trace fact/rule summary | 根据 Span 事实聚合出 `fact_*` 和 `rule_*` 字段 | 不允许 |
| Trace judge/display | 对 Trace 整体结果做 Judge 判定，写入 `judge_*` 和 `trace_display_*` | 只允许追加/覆盖 judge/display 字段 |

强约束：

- Span 的 `level/statusMessage/output/fact_*` 只能由运行时事实决定。
- LLM-as-a-Judge 不能修改 Span，不能覆盖 `fact_*`，不能覆盖 `rule_*`。
- LLM-as-a-Judge 只能写入 `judge_*` 字段。
- 最终用于 UI 聚合展示的 `trace_display_*` 必须标记来源：`rule_engine`、`llm_judge` 或 `rule_engine_fallback`。
- 当 LLM 不可用、超时或返回非法 JSON 时，必须 fail-open 降级为 rule_engine，并写入 `judge_fallback=true` 与 `judge_fallback_reason`。

### 2.7 状态语义定义：Span 事实状态 vs Trace 判定状态

#### 2.7.1 Span 级状态：忠实记录执行真实结果

Span 是事实记录层，只描述该步骤的真实执行结果，不做整体价值判断。任何 AI、LLM Judge、规则引擎都不得篡改 Span 的事实字段。

| Span 字段 | 来源 | 说明 |
|-----------|------|------|
| `level` | runtime | 根据该步骤真实结果设置，例如 CLI `exit_code != 0` 时为 `ERROR` |
| `statusMessage` | runtime | 该步骤的人类可读错误摘要，例如缺参、限流、权限不足 |
| `output` | runtime | 该步骤原始输出或截断后的证据 |
| `metadata.record_type` | runtime | 固定为 `fact` |
| `metadata.fact_status` | runtime | `success` / `failed` / `skipped` |
| `metadata.fact_status_source` | runtime | 事实来源，例如 `exit_code`、`http_status`、`runtime_check` |
| `metadata.error_code` | runtime | 原始错误码 |
| `metadata.error_type` | runtime | 归一化错误类型 |

示例：首次 CLI 调用失败，即使后续修复成功，该 Span 仍然保持 `ERROR`。

```json
{
  "name": "aliyun.cli",
  "level": "ERROR",
  "statusMessage": "Throttling.User: request was throttled",
  "metadata": {
    "record_type": "fact",
    "fact_status": "failed",
    "fact_status_source": "exit_code",
    "span_role": "aliyun_cli",
    "criticality": "critical",
    "attempt": 1,
    "exit_code": 1,
    "error_code": "Throttling.User",
    "error_type": "throttling_error"
  }
}
```

#### 2.7.2 Trace 级状态：整体结果判定

Trace 表示一次 Skill 调用的整体结果。它可以基于 Span 事实进行聚合和判定，但必须保留字段来源。

Trace metadata 分四组：

| 字段组 | 生成方 | 是否可被 LLM 覆盖 | 用途 |
|--------|--------|------------------|------|
| `fact_*` | runtime 聚合 | 不允许 | 汇总 Span 事实 |
| `rule_*` | deterministic rule engine | 不允许 | 可预测、可测试的默认判定 |
| `judge_*` | rule_engine 或 LLM-as-a-Judge | 只允许写 `judge_*` | 智能整体判定 |
| `trace_display_*` | final selector | 允许由 rule 或 LLM 选择，但必须标记来源 | UI/筛选使用的最终展示状态 |

判定顺序：

```text
Span runtime facts
  -> Trace fact_* summary
  -> rule_* deterministic judgment
  -> optional LLM-as-a-Judge writes judge_*
  -> trace_display_* selects final display severity/source
```

Langfuse 实际上报约定：

- Trace 对象使用 `metadata.trace_display_severity` 表达 Trace 级最终展示严重度。
- 当 Trace 级最终判定为错误时，`metadata.trace_display_severity` 必须为 `ERROR`。
- Langfuse 的 Trace retrieve API 不暴露 Trace 顶层 `level/statusMessage`；UI 可见的 `level/statusMessage` 应通过 observation 表达。
- 因此每次 Trace 结束时都应创建或更新一个 `skillopt.trace_judgement` observation：
  - `name="skillopt.trace_judgement"`
  - `level="ERROR"` 当 Trace 级最终判定为错误
  - `statusMessage` 必须非空，用于 UI 直接显示失败原因
  - `metadata.trace_display_severity` 与 Trace metadata 保持一致

#### 2.7.3 Rule 与 LLM 的关系

默认值：

```bash
SKILLOPT_JUDGE_ENABLED=true
SKILLOPT_JUDGE_MODE=llm
SKILLOPT_JUDGE_FAIL_OPEN=true
```

含义：

- 默认启用 Trace Judge。
- 默认优先使用 LLM-as-a-Judge。
- 若 `SKILLOPT_JUDGE_ENDPOINT` 为空、LLM 超时、不可用或返回非法 JSON，则降级到 rule_engine。
- 降级必须写入 `judge_fallback=true` 和 `judge_fallback_reason`。
- LLM 只能写 `judge_*`，不能覆盖 Span、`fact_*`、`rule_*`。

#### 2.7.4 Trace display 判定矩阵

| Span 事实 | Rule 判定 | LLM 可选判定 | `trace_display_*` 建议 |
|-----------|-----------|--------------|------------------------|
| 无 ERROR Span，主调用成功 | `success / DEFAULT` | 通常不覆盖 | `DEFAULT`，source=`rule_engine` |
| 有 ERROR Span，但修复成功 | `repaired_success / WARNING` | 可判定为 WARNING；若最终输出不可用可升为 ERROR | 默认 `WARNING`，source=`rule_engine` 或 `llm_judge` |
| 非关键 Span 失败，主调用成功 | `success_with_warnings / WARNING` | 可根据影响面调整 | 默认 `WARNING` |
| 关键 Span 失败且未修复 | `failed / ERROR` | 通常保持 ERROR | `ERROR` |
| 熔断器阻断执行 | `blocked / ERROR` | 通常保持 ERROR | `ERROR` |
| Rule 判 WARNING，但 LLM 认为输出不可用 | `WARNING` | `ERROR`，需记录 override 证据 | `ERROR`，source=`llm_judge` |

LLM 覆盖规则判定时必须写入：

```json
{
  "judge_overrode_rule": true,
  "judge_override_reason": "Final output is empty and unusable for the requested diagnostic task.",
  "judge_evidence": [
    "fact_final_output_empty=true",
    "fact_repair_success=true"
  ],
  "trace_display_severity": "ERROR",
  "trace_display_severity_source": "llm_judge"
}
```

---

## 3. 技术实现

### 3.1 配置变量

规划在 `skillopt-lib.sh` 头部新增（runtime 尚未接入）：

```bash
# Langfuse configuration
SKILLOPT_LANGFUSE_ENABLED="${SKILLOPT_LANGFUSE_ENABLED:-false}"
LANGFUSE_HOST="${LANGFUSE_HOST:-}"
LANGFUSE_PUBLIC_KEY="${LANGFUSE_PUBLIC_KEY:-}"
LANGFUSE_SECRET_KEY="${LANGFUSE_SECRET_KEY:-}"

# Trace Judge configuration
SKILLOPT_JUDGE_ENABLED="${SKILLOPT_JUDGE_ENABLED:-true}"
SKILLOPT_JUDGE_MODE="${SKILLOPT_JUDGE_MODE:-llm}"
SKILLOPT_JUDGE_FAIL_OPEN="${SKILLOPT_JUDGE_FAIL_OPEN:-true}"
SKILLOPT_JUDGE_POLICY_VERSION="${SKILLOPT_JUDGE_POLICY_VERSION:-skillopt-trace-judge-v1}"
SKILLOPT_JUDGE_MODEL="${SKILLOPT_JUDGE_MODEL:-}"
SKILLOPT_JUDGE_TIMEOUT="${SKILLOPT_JUDGE_TIMEOUT:-5}"
SKILLOPT_JUDGE_ENDPOINT="${SKILLOPT_JUDGE_ENDPOINT:-}"

# Session & Trace state
SKILLOPT_SESSION_ID="${SKILLOPT_SESSION_ID:-}"
_SKILLOPT_TRACE_DIR="${_SKILLOPT_RUNTIME_ROOT}/traces"
SKILLOPT_CURRENT_TRACE_ID=""
SKILLOPT_TRACE_START_TIME=""
```

### 3.2 Session 管理

```bash
# Local-first: every wrapper invocation writes session + trace files.
skillopt_trace_required() {
    return 0
}

skillopt_langfuse_required() {
    [[ "$SKILLOPT_LANGFUSE_ENABLED" == "true" ]] && return 0
    return 1
}

skillopt_session_init() {
    # 不再 gate；始终初始化 session 并 mkdir traces/

    # 优先级 1: 显式环境变量
    if [[ -n "${SKILLOPT_SESSION_ID:-}" ]]; then
        :

    # 优先级 2: IDE 环境变量
    elif [[ -n "${TRAE_SESSION_ID:-}" ]]; then
        SKILLOPT_SESSION_ID="sess-trae-${TRAE_SESSION_ID}"
    elif [[ -n "${CLAUDE_CONVERSATION_ID:-}" ]]; then
        SKILLOPT_SESSION_ID="sess-claude-${CLAUDE_CONVERSATION_ID}"
    elif [[ -n "${OPENCODE_SESSION_ID:-}" ]]; then
        SKILLOPT_SESSION_ID="sess-opencode-${OPENCODE_SESSION_ID}"
    elif [[ -n "${CODEBUDDY_SESSION_ID:-}" ]]; then
        SKILLOPT_SESSION_ID="sess-codebuddy-${CODEBUDDY_SESSION_ID}"
    elif [[ -n "${IDE_SESSION_ID:-}" ]]; then
        SKILLOPT_SESSION_ID="sess-ide-${IDE_SESSION_ID}"

    # 优先级 3: 兜底（工作目录 hash + 日期）
    else
        local workdir_hash
        workdir_hash="$(printf '%s' "$(pwd)" | md5 2>/dev/null | cut -c1-8 || \
                        printf '%s' "$(pwd)" | md5sum 2>/dev/null | cut -c1-8 || \
                        echo "00000000")"
        local today
        today="$(date +%Y%m%d)"
        SKILLOPT_SESSION_ID="sess-${workdir_hash}-${today}"
        skillopt_log "session: fallback $SKILLOPT_SESSION_ID (workdir+date)"
    fi

    mkdir -p "$_SKILLOPT_TRACE_DIR" 2>/dev/null || true

    local session_file="${_SKILLOPT_SESSIONS_DIR:-$_SKILLOPT_RUNTIME_ROOT}/skillopt-session-${SKILLOPT_SESSION_ID}.json"
    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"

    if [[ ! -f "$session_file" ]]; then
        # 首次创建
        jq -n \
            --arg sid "$SKILLOPT_SESSION_ID" \
            --arg skill "$SKILLOPT_SKILL_TAG" \
            --arg workdir "$(pwd)" \
            --arg ts "$ts" \
            '{
                session_id: $sid,
                skill: $skill,
                workdir: $workdir,
                created_at: $ts,
                last_active: $ts,
                trace_count: 0,
                status: "active"
            }' > "$session_file"

        _skillopt_langfuse_create_session "$SKILLOPT_SESSION_ID" "$ts"
        skillopt_log "session: created $SKILLOPT_SESSION_ID"
    else
        # 更新活跃时间
        local updated
        updated="$(jq --arg ts "$ts" '
            .last_active = $ts |
            .trace_count = ((.trace_count // 0) + 1)
        ' "$session_file")"
        printf '%s\n' "$updated" > "$session_file"
    fi
}
```

### 3.3 Trace 管理

> 示意伪代码；实现以 `skillopt-core-lib.sh` 为准：本地 trace **始终**写入，Langfuse 调用包在 `skillopt_langfuse_required` 内。

```bash
# 创建 Trace（在 skillopt_wrap 开始时调用）
skillopt_trace_start() {
    local product="$1"
    local action="$2"
    shift 2
    local params=("$@")

    local trace_id="trace-${SKILLOPT_SESSION_ID}-$(date +%s)-${RANDOM}"
    SKILLOPT_CURRENT_TRACE_ID="$trace_id"
    SKILLOPT_TRACE_START_TIME=$(date +%s%N)

    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"

    local trace_file="${_SKILLOPT_TRACE_DIR}/${trace_id}.json"
    jq -n \
        --arg tid "$trace_id" \
        --arg sid "$SKILLOPT_SESSION_ID" \
        --arg product "$product" \
        --arg action "$action" \
        --arg ts "$ts" \
        --arg params "$(printf '%s ' "${params[@]}")" \
        '{
            trace_id: $tid,
            session_id: $sid,
            product: $product,
            action: $action,
            params: $params,
            start_time: $ts,
            status: "running",
            spans: []
        }' > "$trace_file"

    if skillopt_langfuse_required; then
        _skillopt_langfuse_create_trace "$trace_id" "$SKILLOPT_SESSION_ID" \
            "$product" "$action" "$ts"
    fi

    skillopt_log "trace: start $trace_id $product $action"
}

# 添加 Span（修复、优化等子操作）
skillopt_trace_span() {
    local span_name="$1"
    local span_status="$2"
    local metadata="${3:-\{\}}"

    [[ -z "${SKILLOPT_CURRENT_TRACE_ID:-}" ]] && return 0

    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
    local span_id="span-${span_name}-$(date +%s)-${RANDOM}"

    local trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
    [[ ! -f "$trace_file" ]] && return 0

    local updated
    updated="$(jq \
        --arg sid "$span_id" \
        --arg name "$span_name" \
        --arg status "$span_status" \
        --arg ts "$ts" \
        --argjson meta "$metadata" \
        '.spans += [{
            span_id: $sid,
            name: $name,
            status: $status,
            timestamp: $ts,
            metadata: $meta
        }]' "$trace_file")"
    printf '%s\n' "$updated" > "$trace_file"

    if skillopt_langfuse_required; then
        _skillopt_langfuse_create_span "$span_id" "$SKILLOPT_CURRENT_TRACE_ID" \
            "$span_name" "$ts"
    fi
}

# 完成 Trace（在 skillopt_wrap 结束时调用）
skillopt_trace_end() {
    local status="$1"
    local error_code="${2:-}"

    [[ -z "${SKILLOPT_CURRENT_TRACE_ID:-}" ]] && return 0

    local trace_file="${_SKILLOPT_TRACE_DIR}/${SKILLOPT_CURRENT_TRACE_ID}.json"
    [[ ! -f "$trace_file" ]] && return 0

    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
    local end_time_ns
    end_time_ns=$(date +%s%N)
    local duration_ms=$(( (end_time_ns - ${SKILLOPT_TRACE_START_TIME:-0}) / 1000000 ))

    local updated
    updated="$(jq \
        --arg status "$status" \
        --arg ts "$ts" \
        --arg ec "$error_code" \
        --argjson dur "$duration_ms" \
        '.status = $status | .end_time = $ts | .duration_ms = $dur | .error_code = $ec' \
        "$trace_file")"
    printf '%s\n' "$updated" > "$trace_file"

    _skillopt_langfuse_update_trace "$SKILLOPT_CURRENT_TRACE_ID" \
        "$status" "$ts" "$duration_ms" "$error_code"

    skillopt_log "trace: end ${SKILLOPT_CURRENT_TRACE_ID} status=$status duration=${duration_ms}ms"

    SKILLOPT_CURRENT_TRACE_ID=""
    SKILLOPT_TRACE_START_TIME=""
}
```

### 3.4 Langfuse HTTP 上报

当前实现采用同步 HTTP 上报，但所有 curl 失败均被吞掉，不影响 Skill 主流程。

这样做的原因：

- bash wrapper 是短生命周期进程，后台 `curl &` 在进程退出时存在上报丢失风险；
- Langfuse ingestion 具备最终一致性，集成测试需要轮询等待 trace 可查；
- 同步 `curl ... || true` 可以保证上报请求已发出，同时仍满足“Langfuse 故障不阻断主流程”。

```bash
_skillopt_langfuse_auth() {
    printf '%s' "${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}" | base64
}

_skillopt_langfuse_post() {
    local endpoint="$1"
    local payload="$2"

    [[ -z "$LANGFUSE_HOST" ]] && return 0
    [[ -z "$LANGFUSE_PUBLIC_KEY" ]] && return 0

    local auth
    auth="$(_skillopt_langfuse_auth)"

    curl -s -X POST "${LANGFUSE_HOST}${endpoint}" \
        -H "Authorization: Basic ${auth}" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        >/dev/null 2>&1 || true
}

_skillopt_langfuse_create_session() {
    local session_id="$1"
    local ts="$2"

    _skillopt_langfuse_post "/api/public/sessions" "$(jq -n \
        --arg id "$session_id" \
        --arg skill "$SKILLOPT_SKILL_TAG" \
        '{id: $id, name: ("SkillOpt:" + $skill)}')"
}

_skillopt_langfuse_create_trace() {
    local trace_id="$1"
    local session_id="$2"
    local product="$3"
    local action="$4"
    local ts="$5"

    _skillopt_langfuse_post "/api/public/ingestion" "$(jq -n \
        --arg tid "$trace_id" \
        --arg sid "$session_id" \
        --arg name "${product} ${action}" \
        --arg ts "$ts" \
        --arg skill "$SKILLOPT_SKILL_TAG" \
        --arg product "$product" \
        --arg action "$action" \
        '{batch: [{
            type: "trace-create",
            body: {
                id: $tid,
                sessionId: $sid,
                name: $name,
                timestamp: $ts,
                metadata: {skill: $skill, product: $product, action: $action}
            }
        }]}')"
}

_skillopt_langfuse_create_span() {
    local span_id="$1"
    local trace_id="$2"
    local span_name="$3"
    local ts="$4"

    _skillopt_langfuse_post "/api/public/ingestion" "$(jq -n \
        --arg sid "$span_id" \
        --arg tid "$trace_id" \
        --arg name "$span_name" \
        --arg ts "$ts" \
        '{batch: [{
            type: "span-create",
            body: {
                id: $sid,
                traceId: $tid,
                name: $name,
                startTime: $ts
            }
        }]}')"
}

_skillopt_langfuse_update_trace() {
    local trace_id="$1"
    local status="$2"
    local ts="$3"
    local duration_ms="$4"
    local error_code="$5"

    _skillopt_langfuse_post "/api/public/ingestion" "$(jq -n \
        --arg tid "$trace_id" \
        --arg status "$status" \
        --arg ts "$ts" \
        --argjson dur "$duration_ms" \
        --arg ec "$error_code" \
        '{batch: [{
            type: "trace-create",
            body: {
                id: $tid,
                timestamp: $ts,
                metadata: {
                    status: $status,
                    duration_ms: $dur,
                    error_code: $ec
                }
            }
        }]}')"
}
```

### 3.5 集成到 skillopt_wrap()

```bash
skillopt_wrap() {
    local product="$1"; shift
    local action="$1";  shift

    skillopt_init "$@"

    if [[ "$SKILLOPT_REPORT" == "true" ]]; then
        skillopt_report
        return $?
    fi

    SKILLOPT_PARAMS=("${SKILLOPT_REMAINING[@]+"${SKILLOPT_REMAINING[@]}"}")

    # === Langfuse: Session 初始化 + Trace 开始 ===
    skillopt_session_init
    skillopt_trace_start "$product" "$action" "${SKILLOPT_PARAMS[@]}"

    if [[ "$SKILLOPT_ENABLED" == "true" ]]; then
        skillopt_trace_span "optimization" "running"
        skillopt_optimize_params "$product" "$action"
        skillopt_trace_span "optimization" "success"
    fi

    if [[ "$SKILLOPT_ENABLED" != "true" ]]; then
        aliyun "$product" "$action" "${SKILLOPT_PARAMS[@]+"${SKILLOPT_PARAMS[@]}"}"
        local rc=$?
        if [[ $rc -eq 0 ]]; then
            skillopt_trace_end "success"
        else
            skillopt_trace_end "failed" "exit_code_$rc"
        fi
        return $rc
    fi

    # 熔断器检查
    local cb_rc=0
    skillopt_cb_check || cb_rc=$?
    if [[ $cb_rc -eq 1 ]]; then
        skillopt_trace_span "circuit_breaker" "failed" '{"reason":"circuit_open"}'
        skillopt_trace_end "failed" "CircuitBreakerOpen"
        # ... 现有熔断器逻辑 ...
        return 1
    fi

    # 执行 API 调用
    skillopt_run_aliyun "$product" "$action" "${SKILLOPT_PARAMS[@]+"${SKILLOPT_PARAMS[@]}"}"
    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        skillopt_trace_end "success"
        # ... 现有成功逻辑 ...
        return 0
    fi

    # 修复流程
    local error_code
    error_code="$(skillopt_extract_error_code "$SKILLOPT_LAST_OUTPUT")"
    skillopt_trace_span "repair" "running" "{\"error_code\":\"$error_code\"}"

    skillopt_repair_error "$error_code" "$product" "$action" "${SKILLOPT_PARAMS[@]}"
    exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        skillopt_trace_span "repair" "success"
        skillopt_trace_end "success"
    else
        skillopt_trace_span "repair" "failed"
        skillopt_trace_end "failed" "$error_code"
    fi

    return $exit_code
}
```

---

## 4. 跨 IDE 兼容性

### 4.1 各 IDE 终端行为

| IDE | 终端模型 | 终端 Session ID 能否区分任务 | 推荐集成方式 |
|-----|---------|---------------------------|-------------|
| **Trae** | 每个任务窗口独立终端 | ✅ 能 | 设置 `TRAE_SESSION_ID` |
| **Claude Code** | 共享用户终端 | ❌ 不能 | 设置 `CLAUDE_CONVERSATION_ID` |
| **Open Code** | 共享用户终端 | ❌ 不能 | 设置 `OPENCODE_SESSION_ID` |
| **CodeBuddy** | 每个任务独立终端 | ✅ 能 | 设置 `CODEBUDDY_SESSION_ID` |
| **PI Agent** | 独立进程 | ✅ 能 | 设置 `IDE_SESSION_ID` |
| **无 IDE** | N/A | N/A | 兜底方案自动生效 |

### 4.2 IDE 集成方式

#### Trae

```bash
# Trae 为每个任务窗口自动设置
export TRAE_SESSION_ID="task-abc123"
```

#### Claude Code

```bash
# Claude Code 在调用 Skill 前注入
export CLAUDE_CONVERSATION_ID="conv-20260617-abc123"
```

#### Open Code

```bash
# Open Code 在 Agent 执行时注入
export OPENCODE_SESSION_ID="session-xyz789"
```

#### 无 IDE（CLI 直接使用）

```bash
# 无需任何配置，兜底方案自动生效
# Session ID = sess-{workdir_hash}-{date}
./scripts/cms-skillopt-wrapper.sh DescribeMetricList \
    --skillopt-enable \
    --skillopt-langfuse-enable \
    --Namespace acs_ecs_dashboard --MetricName CPUUtilization
```

### 4.3 实际效果

```
Trae 任务窗口 A（配置了 TRAE_SESSION_ID=task-aaa）:
┌─ Session: sess-trae-task-aaa ──────────────────┐
│  ├── Trace: CMS DescribeMetricList (success)   │
│  ├── Trace: ECS DescribeInstances (success)    │
│  └── Trace: RDS DescribeDBInstances (failed)   │
└────────────────────────────────────────────────┘

Claude Code 对话 B（未配置，工作目录: /Users/xxx/project-a）:
┌─ Session: sess-a1b2c3d4-20260617 ─────────────┐
│  ├── Trace: CMS DescribeMetricList (success)   │
│  └── Trace: ECS DescribeInstances (success)    │
└────────────────────────────────────────────────┘

CLI 直接使用（未配置，工作目录: /Users/xxx/project-b）:
┌─ Session: sess-e5f6g7h8-20260617 ─────────────┐
│  └── Trace: SLB DescribeLoadBalancers (success)│
└────────────────────────────────────────────────┘
```

---

## 5. 与现有功能的映射

```
skillopt_wrap() 执行流程:
│
├── skillopt_session_init()         ← Session 初始化
├── skillopt_trace_start()          ← Trace 开始
│
├── skillopt_optimize_params()      ← 参数优化
│   └── trace_span("optimization")
│
├── skillopt_cb_check()             ← 熔断器检查
│   └── trace_span("circuit_breaker")
│
├── skillopt_run_aliyun()           ← API 调用
│
├── skillopt_repair_error()         ← 自修复
│   └── trace_span("repair")
│
├── skillopt_check_and_poll_empty() ← 传播延迟轮询
│   └── trace_span("propagation_poll")
│
└── skillopt_trace_end()            ← Trace 结束
```

---

## 6. CLI 参数

新增命令行参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--skillopt-enable` | 启用自修复 / 参数优化 / 熔断器 | `false` |
| `--skillopt-disable` | 显式禁用自修复（优先级高于 env） | - |
| `--skillopt-langfuse-enable` | 启用 Langfuse 远端上报 | `false` |
| `--skillopt-langfuse-disable` | 显式禁用 Langfuse 远端上报 | - |
| `--skillopt-session-id ID` | 显式指定 Session ID | 自动推导 |

---

## 7. 环境变量

### 7.0 核心开关（正交）

两个开关相互独立，可任意组合。完整说明见 [harness-integration-guide.md §3.1](./harness-integration-guide.md#31-enable-flags-two-orthogonal-switches)。

| 变量 | 语义 | 默认值 | 优先级（高 → 低） |
|------|------|--------|-------------------|
| `SKILLOPT_ENABLED` | 控制自修复、参数优化、熔断器；`false` 时 `skillopt_wrap()` 只执行一次 `aliyun` 调用（仍捕获输出供 trace） | `false` | `--skillopt-disable` → `--skillopt-enable` → env / `.env` → `false` |
| `SKILLOPT_LANGFUSE_ENABLED` | **仅**控制 Langfuse 远端 HTTP **镜像**；不 gate 本地 trace 写入 | `false` | `--skillopt-langfuse-disable` → `--skillopt-langfuse-enable` → env / `.env` → `false` |
| `TRACE_KEEP_DAYS` | 本地 `trace-*.json` 与 `skillopt-session-*.json` TTL（与 logs 默认对齐） | `7` | env → `runtime_cleanup.py --traces-keep-days` |

`skillopt_trace_required()` **恒为 true**：每次 wrapper 调用写入本地 Session/Trace 文件。Langfuse 仅在 `skillopt_langfuse_required()` 为真时额外 HTTP 上报。

因此：默认（Langfuse 关）仍会生成本地 `.runtime/traces/<skill-tag>/*.json` 与 `.runtime/sessions/<skill-tag>/skillopt-session-*.json`，并触发 `memory_store_lite`（含失败时 `error_code`）；Allowlist 失败 additionally 触发 plan **B** → Layer 2（`store-wrapper-lite`）。开启 Langfuse 时在本地 canonical 之上追加远端镜像。

### 7.1 必须配置（启用 Langfuse 远端上报时）

| 变量 | 说明 | 示例 |
|------|------|------|
| `SKILLOPT_LANGFUSE_ENABLED` | 启用 Langfuse **远端 HTTP 上报**（与自修复开关正交） | `true` |
| `LANGFUSE_HOST` | Langfuse 服务地址 | `https://cloud.langfuse.com` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse Public Key | `pk-lf-xxxxx` |
| `LANGFUSE_SECRET_KEY` | Langfuse Secret Key | `sk-lf-xxxxx` |

**最小配置示例**：

```bash
export SKILLOPT_LANGFUSE_ENABLED="true"
export LANGFUSE_HOST="https://cloud.langfuse.com"
export LANGFUSE_PUBLIC_KEY="pk-lf-xxxxx"
export LANGFUSE_SECRET_KEY="sk-lf-xxxxx"

# 然后正常使用
./scripts/cms-skillopt-wrapper.sh DescribeMetricList \
    --skillopt-enable \
    --Namespace acs_ecs_dashboard --MetricName CPUUtilization
```

### 7.2 可选配置（Session ID 相关）

**优先级从高到低**，有任一即可，全部不配置则自动兜底：

| 变量 | 说明 | 来源 | 示例 |
|------|------|------|------|
| `SKILLOPT_SESSION_ID` | 显式指定 Session ID（最高优先级） | 用户手动 | `sess-my-custom-id` |
| `TRAE_SESSION_ID` | Trae 任务 ID | Trae IDE 自动设置 | `task-abc123` |
| `CLAUDE_CONVERSATION_ID` | Claude Code 对话 ID | Claude Code 注入 | `conv-xyz789` |
| `OPENCODE_SESSION_ID` | Open Code Session ID | Open Code 注入 | `session-def456` |
| `CODEBUDDY_SESSION_ID` | CodeBuddy Session ID | CodeBuddy 注入 | `task-ghi012` |
| `IDE_SESSION_ID` | 通用 IDE Session ID | 其他 IDE 注入 | `jkl345` |

### 7.3 Trace Judge 配置

> **PR-5（2026-06）**：产品 overlay 与 `.env.example` 已移除未接线的 `SKILLOPT_JUDGE_*` 配置。本节为**设计规格**；完整 LLM/rule_engine Judge 尚未接入 `skillopt-core-lib.sh`。Langfuse 失败路径仍会写入简化版 `skillopt.trace_judgement` span。

Trace Judge 默认开启，默认优先使用 LLM-as-a-Judge。Judge **不 gate** 本地 trace 创建；仅向本地 trace 追加 `judge_*` metadata。Langfuse 远端镜像仍由 `SKILLOPT_LANGFUSE_ENABLED` 单独控制。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SKILLOPT_JUDGE_ENABLED` | `true` | 是否生成 `judge_*` 判定字段 |
| `SKILLOPT_JUDGE_MODE` | `llm` | `llm` 表示优先 LLM-as-a-Judge；`rule` 表示只使用确定性规则 |
| `SKILLOPT_JUDGE_FAIL_OPEN` | `true` | LLM 不可用、超时或返回非法 JSON 时是否降级到 rule_engine |
| `SKILLOPT_JUDGE_POLICY_VERSION` | `skillopt-trace-judge-v1` | 判定策略版本，用于审计、回放和灰度 |
| `SKILLOPT_JUDGE_MODEL` | 空 | LLM Judge 使用的模型名；空值表示由 Judge 服务端决定 |
| `SKILLOPT_JUDGE_TIMEOUT` | `5` | LLM Judge 超时时间，单位秒 |
| `SKILLOPT_JUDGE_ENDPOINT` | 空 | LLM Judge HTTP 服务地址；为空时自动降级到 rule_engine |

配置模式和实际生效模式必须分开记录：

```json
{
  "judge_configured_mode": "llm",
  "judge_effective_type": "rule_engine",
  "judge_fallback": true,
  "judge_fallback_reason": "missing_judge_endpoint",
  "trace_display_severity_source": "rule_engine_fallback"
}
```

### 7.4 兜底机制

**如果以上 Session ID 环境变量均未配置**，系统自动生成：

```
Session ID = sess-{工作目录hash}-{日期}
示例: sess-a1b2c3d4-20260617
```

- 同项目同天的调用自动归为同一 Session
- 不同项目或不同天自动隔离
- **无需任何配置即可工作**

### 7.4 配置总结

| 类别 | 数量 | 说明 |
|------|------|------|
| **Langfuse 上报必需** | 4 个 | `SKILLOPT_LANGFUSE_ENABLED` + Langfuse 连接 3 项 |
| **Session 可选** | 6 个 | Session ID 相关，有任一即可，全无则自动兜底 |
| **Judge 可选覆盖** | 7 个 | Judge 默认已开启；仅在需要覆盖默认值或接入 LLM Judge 服务时配置 |
| **总计** | 17 个 | 最小远端上报配置只需 4 个环境变量；Judge 默认无需配置 |

---

## 8. 文件布局

```
${SKILLS_DIR}/.runtime/
├── sessions/<skill-tag>/
│   └── skillopt-session-{session_id}.json    ← Session 文件
├── logs/<skill-tag>/
│   └── cms-skillopt-20260617.log             ← 示例日志
├── metrics/<skill-tag>/
│   └── cms-skillopt-runtime.json             ← 运行时指标 JSON
└── traces/<skill-tag>/
    ├── trace-{trace_id_1}.json               ← Trace 文件
    ├── trace-{trace_id_2}.json
    └── ...
```

所有 `.runtime/` 内容已在 `.gitignore` 中。Legacy `alicloud-*/.runtime/` 已废弃。

---

## 9. 性能影响

| 操作 | 影响 | 说明 |
|------|------|------|
| Session 初始化 | < 5ms | 文件读写 + jq 处理 |
| Trace 创建 | < 5ms | 文件写入 |
| Span 添加 | < 5ms | 文件读写 + jq 处理 |
| Langfuse 上报 | 取决于网络 RTT | curl 同步发送；失败静默忽略，不阻断主流程 |
| 磁盘占用 | ~2KB/Trace | JSON 文件 |

---

## 10. 向后兼容

| 场景 | 行为 |
|------|------|
| `SKILLOPT_ENABLED=false`（默认） | 单次 `aliyun` 调用 + **始终**写本地 trace + Layer 1 `memory_store_lite`；Allowlist 失败 → Layer 2 plan **B** |
| `SKILLOPT_ENABLED=true` | 启用 repair/optimize/CB；本地 trace 仍始终写入 |
| `SKILLOPT_LANGFUSE_ENABLED=false`（默认） | 写本地 trace；不远端上报 |
| `SKILLOPT_LANGFUSE_ENABLED=true` 且 Langfuse 配置完整 | 写本地 trace + 远端 Langfuse 镜像 |
| `SKILLOPT_JUDGE_ENABLED=false` | 跳过 judge metadata；**仍**写本地 trace |
| 有 Langfuse 配置但 curl 失败 | 静默失败（`2>&1 || true`），不影响主流程 |
| `SKILLOPT_JUDGE_MODE=llm` 但 `SKILLOPT_JUDGE_ENDPOINT` 为空 | 降级到 rule_engine，写入 `judge_fallback=true` |
| LLM Judge 超时、不可用或返回非法 JSON | 降级到 rule_engine，CLI 主流程不受影响 |
| `.runtime/traces/` 目录不存在 | 自动创建 |

---

## 11. 测试验证

### 11.1 单元测试

```bash
# 测试 Session ID 生成
test_session_id_from_ide_env() {
    export TRAE_SESSION_ID="task-test-001"
    skillopt_session_init
    assert_eq "$SKILLOPT_SESSION_ID" "sess-trae-task-test-001"
}

test_session_id_fallback() {
    unset TRAE_SESSION_ID CLAUDE_CONVERSATION_ID OPENCODE_SESSION_ID
    unset CODEBUDDY_SESSION_ID IDE_SESSION_ID SKILLOPT_SESSION_ID
    skillopt_session_init
    assert_match "$SKILLOPT_SESSION_ID" "^sess-[a-f0-9]{8}-[0-9]{8}$"
}

# 测试 Trace 生命周期
test_trace_lifecycle() {
    skillopt_trace_start "cms" "DescribeMetricList" "--Namespace" "acs_ecs"
    assert_not_empty "$SKILLOPT_CURRENT_TRACE_ID"

    skillopt_trace_span "optimization" "success"
    skillopt_trace_end "success"
    assert_empty "$SKILLOPT_CURRENT_TRACE_ID"
}
```

### 11.2 集成测试

当前已沉淀灰度 Skill 集成测试脚本：

```bash
bash scripts/test-langfuse-gray-skills.sh
```

该测试覆盖：

- `alicloud-ack-ops`
- `alicloud-das-ops`
- `alicloud-alb-ops`
- `alicloud-cen-ops`

验证项包括：

- `scripts/skillopt-lib.sh` 存在
- `references/skillopt-lib.sh` 不存在
- wrapper 使用 `source "$SCRIPT_DIR/skillopt-lib.sh"`
- `bash -n` 语法检查通过
- `zsh source` 兼容检查通过
- wrapper 实际调用产生输出
- 本地 trace 状态闭合为 `success` 或 `failed`
- 本地 trace session 与共享 `SKILLOPT_SESSION_ID` 一致
- 本地 trace input/output 非空
- Langfuse trace 可通过 `/api/public/traces/{trace_id}` 直查
- Langfuse trace session/input/output 与本地 trace 一致

最近一次验证结果：

```text
Session: sess-gray-skills-it-1781658940
PASS=52, FAIL=0, TOTAL=52
```

---

## 12. 实施状态

| 阶段 | 内容 | 状态 |
|------|------|------|
| **Phase 1** | Session/Trace 核心函数 + skillopt_wrap 集成 | 已完成 |
| **Phase 2** | Langfuse HTTP 上报 + input/output 入库 | 已完成 |
| **Phase 3** | CMS/ECS/SLB 试点验证 | 已完成 |
| **Phase 4** | RDS/Redis 灰度接入 | 已完成 |
| **Phase 5** | ACK/DAS/ALB/CEN 灰度接入与集成测试 | 已完成 |
| **Phase 6** | 剩余 alicloud-*-ops 批量推广 | 待推进 |

当前标准集成测试入口：

```bash
bash scripts/test-langfuse-gray-skills.sh
```

---

## 13. 决策记录

### 决策 1: Session ID 兜底方案

**时间**: 2026-06-17  
**决策**: 采用"工作目录 hash + 日期"作为兜底  
**理由**:
- Claude Code / Open Code 共享终端，终端 Session ID 无法区分任务
- Session ID 永远不为空，确保 Langfuse 中始终有分组
- 同项目同天的调用自然归为一组，隔离粒度合理
- 无需任何配置即可工作

### 决策 2: 纯 bash 实现

**时间**: 2026-06-17  
**决策**: 在 `skillopt-lib.sh` 中直接实现，不引入微服务  
**理由**:
- 与现有 Runtime Harness 架构一致
- 零额外依赖（仅 curl + jq）
- 部署简单，无需独立服务
- 性能足够（< 5ms 开销）

### 决策 3: 同步上报，失败不阻断

**时间**: 2026-06-17  
**决策**: curl 同步发送，并使用 `|| true` 保证 Langfuse 故障不影响 Skill 主流程  
**理由**:
- bash wrapper 是短生命周期进程，后台 `curl &` 存在上报丢失风险
- 集成测试验证 Langfuse ingestion 存在最终一致性延迟，需要轮询直查
- 同步发送能保证请求发出，`|| true` 能保证上报失败不阻断主流程
- 已通过 `scripts/test-langfuse-gray-skills.sh` 验证 ACK/DAS/ALB/CEN 四个灰度 Skill

### 决策 4: Trace Judge 默认开启，默认优先 LLM

**时间**: 2026-06-17  
**决策**: `SKILLOPT_JUDGE_ENABLED=true`、`SKILLOPT_JUDGE_MODE=llm`、`SKILLOPT_JUDGE_FAIL_OPEN=true`  
**理由**:
- Span 必须忠实记录执行事实，不能由 AI 修改；Trace 级可以引入 Judge 做整体结果判定
- 默认启用 Judge 为本地 trace 追加整体判定 metadata（不 gate trace 创建）
- 默认优先 LLM-as-a-Judge，便于判断“局部 ERROR Span 但整体是否失败”的复杂场景
- LLM 不可用时 fail-open 降级到 rule_engine，确保运维 CLI 主流程不被外部智能服务影响
- metadata 必须同时保留 `fact_*`、`rule_*`、`judge_*`、`trace_display_*`，并标记判定来源

### 决策 5: Local-first trace — 始终写本地，Langfuse 可选镜像

**时间**: 2026-06-21  
**决策**: 每次 `skillopt_wrap()` 始终写 `${SKILLS_DIR}/.runtime/traces/<skill-tag>/trace-*.json`；`SKILLOPT_LANGFUSE_ENABLED` 仅触发远端 HTTP 镜像；TTL 默认 7 天（`TRACE_KEEP_DAYS`），纳入 `make memory-maintain-apply`  
**理由**:
- 与 Local-first 记忆架构一致：本地 canonical，远端可观测性为增强层
- 无 Langfuse 时仍闭合 Layer 1（`memory_store_lite` + `error_code`）、Layer 2 plan **B**（allowlisted failures）、R2 preflight 合并
- 与 logs retention 对齐，防止 `.runtime/traces/` 膨胀

---

**文档版本**: v2.3  
**最后更新**: 2026-06-21  
**维护者**: Runtime Harness Team
