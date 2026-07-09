# Runtime Harness 可观测性 Phase 2：Langfuse 追踪集成

> **状态**: ✅ 核心能力已完成，9 个 Skill 灰度验证通过，进入批量推广阶段  
> **架构文档**: [harness-observability-architecture.md](./harness-observability-architecture.md)
> **完整设计文档**: [harness-session-trace-system-design.md](./harness-session-trace-system-design.md)  
> **最新验证时间**: 2026-06-17

## 1. 概述

Phase 2 实现了 Langfuse 追踪集成，支持：

- **追踪事件上报**：将 Runtime Harness 关键事件发送到 Langfuse
- **Agent 调用链关联**：通过 `session_id` / `trace_id` 关联多 Skill 调用链
- **修复效果分析**：在 Langfuse Dashboard 分析各类错误的修复成功率
- **分层事实判定模型**：Span 事实不可篡改，Trace Judge 仅做整体判定不修改运行时事实

### 1.1 当前落地状态

截至 2026-06-17，Phase 2 已完成 9 个 Skill 的分阶段接入和验证：

**试点阶段（5 个）**:
| Skill | 产品 | 状态 | 验证 API | 验证结果 |
|-------|------|------|----------|----------|
| `alicloud-cms-ops` | CMS | ✅ 已接入 | `DescribeMetricRuleList` / `DescribeProjectMeta` | Langfuse trace、input、output、session 验证通过 |
| `alicloud-ecs-ops` | ECS | ✅ 已接入 | `DescribeInstances` / `DescribeDisks` | 多 Skill 共享 Session 验证通过 |
| `alicloud-slb-ops` | SLB | ✅ 已接入 | `DescribeLoadBalancers` | trace 直查、input/output 验证通过 |
| `alicloud-rds-ops` | RDS | ✅ 已接入 | `DescribeDBInstances` | trace 直查、input/output 验证通过 |
| `alicloud-redis-ops` | Redis (`r-kvstore`) | ✅ 已接入 | `DescribeInstances` | trace 直查、input/output 验证通过 |

**灰度阶段（新增 4 个）**:
| Skill | 产品 | 状态 | 验证结果 |
|-------|------|------|----------|
| `alicloud-ack-ops` | ACK | ✅ 已接入 | 失败链路入库验证通过 |
| `alicloud-das-ops` | DAS | ✅ 已接入 | 失败链路入库验证通过 |
| `alicloud-alb-ops` | ALB | ✅ 已接入 | 成功链路入库验证通过 |
| `alicloud-cen-ops` | CEN | ✅ 已接入 | 成功链路入库验证通过 |

当前已验证能力：

- 单 Skill 调用可生成 Langfuse Trace
- 多 Skill 调用可共享同一个 `SKILLOPT_SESSION_ID`
- Trace name 使用完整 Skill 名称，例如 `alicloud-rds-ops rds DescribeDBInstances`
- trace-level `input` 非空
- trace-level `output` 非空，且 JSON 响应以结构化 object 入库
- 本地 trace 文件**每次 wrapper 调用均写入**（Local-first canonical）
- 启用 Langfuse 时，本地 trace id 可与远端 trace 互相校验
- `scripts/skillopt-lib.sh` 作为运行时库路径已在所有接入 Skill 中落地
- `references/skillopt-lib.sh` 已从所有接入 Skill 中移除
- **分层判定模型**：Span 忠实记录运行事实，Trace Judge 仅追加整体判定不修改 Span（设计规格；PR-5 已移除未接线的 `SKILLOPT_JUDGE_*` 配置，见 [harness-session-trace-system-design.md §7.3](./harness-session-trace-system-design.md#73-trace-judge-配置)）

当前阶段结论：

> 技术架构已稳定，核心能力全部验证通过，标准化模板已固化；可继续批量推广到剩余 `alicloud-*-ops` Skill。完整设计决策和数据模型见 [harness-session-trace-system-design.md](./harness-session-trace-system-design.md)。

## 2. 追踪事件类型

### 2.1 事件分类

| 事件类型 | 触发时机 | 关键属性 |
|---------|---------|---------|
| `api_call_start` | API 调用前 | product, action, params |
| `api_call_success` | API 调用成功 | duration_ms, request_id |
| `api_call_error` | API 调用失败 | error_code, duration_ms |
| `optimization_decision` | 参数优化时 | original_params, optimized_params, reason |
| `repair_start` | 开始修复 | error_code, strategy |
| `repair_success` | 修复成功 | retry_count, duration_ms |
| `repair_failed` | 修复失败 | error_code, reason |
| `circuit_breaker_open` | 熔断器打开 | threshold, consecutive_failures |
| `circuit_breaker_close` | 熔断器关闭 | probe_success |
| `circuit_breaker_halfopen` | 熔断器半开 | cooldown_elapsed |

### 2.2 事件数据模型

```json
{
  "trace_id": "agent-session-123-abc",
  "session_id": "user-session-456",
  "name": "skillopt:repair_success",
  "metadata": {
    "skill": "cms",
    "event_type": "repair_success",
    "error_code": "Throttling.User",
    "repair_strategy": "exponential_backoff",
    "retry_count": 2,
    "duration_ms": 3500
  },
  "input": {
    "product": "cms",
    "action": "DescribeMetricList",
    "params": {"Namespace": "acs_ecs_dashboard", "Period": 60}
  },
  "output": {
    "success": true,
    "request_id": "ABC-123-DEF"
  },
  "level": "DEFAULT",
  "status_message": "Repair succeeded after 2 retries"
}
```

## 3. 核心函数设计

### 3.1 skillopt_trace_event()

```bash
# 追踪事件发送函数
skillopt_trace_event() {
    local event_type="$1"
    local metadata_json="$2"
    local input_json="${3:-{}}"
    local output_json="${4:-{}}"
    
    # 检查是否启用追踪
    [[ "${SKILLOPT_LANGFUSE_ENABLED:-false}" != "true" ]] && return 0
    
    # 构建 trace payload
    local trace_id="${LANGFUSE_TRACE_ID:-skillopt-$(date +%s)-$$}"
    local session_id="${LANGFUSE_SESSION_ID:-default}"
    
    local payload
    payload=$(jq -n \
        --arg trace_id "$trace_id" \
        --arg session_id "$session_id" \
        --arg skill "$SKILLOPT_SKILL_TAG" \
        --arg event_type "$event_type" \
        --argjson metadata "$metadata_json" \
        --argjson input "$input_json" \
        --argjson output "$output_json" \
        '{
            "batch": [{
                "type": "span-create",
                "body": {
                    "traceId": $trace_id,
                    "sessionId": $session_id,
                    "name": ("skillopt:" + $event_type),
                    "metadata": ($metadata + {"skill": $skill}),
                    "input": $input,
                    "output": $output,
                    "startTime": (now | todate)
                }
            }]
        }')
    
    # 异步发送到 Langfuse（不阻塞主流程）
    if [[ -n "${LANGFUSE_HOST:-}" ]]; then
        curl -s -X POST "${LANGFUSE_HOST}/api/public/ingestion" \
            -H "Authorization: Bearer ${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}" \
            -H "Content-Type: application/json" \
            -d "$payload" \
            >/dev/null 2>&1 &
    fi
}
```

### 3.2 集成点

**参数优化时**:
```bash
skillopt_optimize_params() {
    # ... 现有逻辑 ...
    if [[ "$needs_optimization" == "true" ]]; then
        skillopt_trace_event "optimization_decision" \
            '{"reason":"high_error_rate","error_rate":15.5}' \
            '{"original_period":60}' \
            '{"optimized_period":300}'
    fi
}
```

**API 调用前后**:
```bash
skillopt_wrap() {
    # 调用前
    skillopt_trace_event "api_call_start" \
        '{}' \
        "{\"product\":\"$product\",\"action\":\"$action\"}"
    
    local start_time=$(date +%s%N)
    skillopt_run_aliyun "$product" "$action" "${SKILLOPT_PARAMS[@]}"
    local exit_code=$?
    local end_time=$(date +%s%N)
    local duration_ms=$(( (end_time - start_time) / 1000000 ))
    
    # 调用后
    if [[ $exit_code -eq 0 ]]; then
        skillopt_trace_event "api_call_success" \
            "{\"duration_ms\":$duration_ms}"
    else
        skillopt_trace_event "api_call_error" \
            "{\"duration_ms\":$duration_ms,\"error_code\":\"$error_code\"}"
    fi
}
```

**修复流程**:
```bash
skillopt_repair_error() {
    skillopt_trace_event "repair_start" \
        "{\"error_code\":\"$error_code\",\"strategy\":\"$repair_strategy\"}"
    
    # ... 修复逻辑 ...
    
    if [[ $repair_success -eq 0 ]]; then
        skillopt_trace_event "repair_success" \
            "{\"error_code\":\"$error_code\",\"retry_count\":$retry_count}"
    else
        skillopt_trace_event "repair_failed" \
            "{\"error_code\":\"$error_code\",\"reason\":\"max_retries_exceeded\"}"
    fi
}
```

**熔断器状态变化**:
```bash
skillopt_cb_record_failure() {
    if [[ $consecutive_failures -ge $SKILLOPT_CB_THRESHOLD ]]; then
        skillopt_trace_event "circuit_breaker_open" \
            "{\"threshold\":$SKILLOPT_CB_THRESHOLD,\"failures\":$consecutive_failures}"
    fi
}
```

## 4. 配置方式

### 4.1 环境变量

```bash
# 启用追踪
export SKILLOPT_LANGFUSE_ENABLED="true"

# Langfuse 配置
export LANGFUSE_HOST="https://cloud.langfuse.com"  # 或自托管地址
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."

# 可选：显式指定多 Skill 共享 Session
export SKILLOPT_SESSION_ID="sess-my-task-001"
```

### 4.2 命令行参数（当前已支持）

```bash
./scripts/cms-skillopt-wrapper.sh DescribeMetricList \
    --skillopt-enable \
    --skillopt-langfuse-enable \
    --skillopt-session-id "sess-my-task-001" \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization
```

当前已支持参数：

| 参数 | 说明 |
|------|------|
| `--skillopt-langfuse-enable` | 启用 Langfuse **远端镜像**（本地 trace 仍始终写入） |
| `--skillopt-langfuse-disable` | 禁用 Langfuse 远端镜像 |
| `--skillopt-session-id` | 显式指定 Session ID，用于多 Skill 链路关联 |

### 4.3 自定义 Metadata

`metadata` 用于给 Langfuse Trace 附加业务上下文，推荐采用多个 `--skillopt-metadata key=value` 参数传入：

```bash
./scripts/cms-skillopt-wrapper.sh DescribeMetricList \
    --skillopt-enable \
    --skillopt-langfuse-enable \
    --skillopt-session-id "sess-my-task-001" \
    --skillopt-metadata tenant_id=10001 \
    --skillopt-metadata env=prod \
    --skillopt-metadata region=cn-hangzhou \
    --skillopt-metadata task_id=DOPS-12345 \
    --skillopt-metadata scene=ecs_cpu_diagnosis \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization
```

上报到 Langfuse 后，metadata 会合并为 key-value dict：

```json
{
  "tenant_id": "10001",
  "env": "prod",
  "region": "cn-hangzhou",
  "task_id": "DOPS-12345",
  "scene": "ecs_cpu_diagnosis"
}
```

约定：

- 每个 `--skillopt-metadata` 只表达一个 `key=value`
- 可重复传入多个 `--skillopt-metadata`
- `key` 建议使用小写 snake_case，例如 `tenant_id`、`task_id`、`agent_id`
- `value` 默认按字符串处理；包含空格时需要加引号，例如 `--skillopt-metadata 'scene=ecs cpu diagnosis'`
- 重复 key 以后一次传入为准
- 不应通过 metadata 传递 API Key、Secret、密码等敏感信息

如需传入结构化对象，可使用 JSON 形式扩展参数：

```bash
--skillopt-metadata-json '{"tenant_id":"10001","env":"prod","labels":{"source":"jira","priority":"p1"}}'
```

推荐优先使用多个 `--skillopt-metadata key=value`，仅在需要嵌套对象时使用 `--skillopt-metadata-json`。

#### 提示词表达示例

当 Agent 调用 Skill 时，可在提示词中显式要求携带 metadata：

```text
执行 CMS 指标查询，并启用 SkillOpt Langfuse 追踪。
请设置 session_id 为 sess-my-task-001。
请附加以下 metadata：
- tenant_id: 10001
- env: prod
- region: cn-hangzhou
- task_id: DOPS-12345
- scene: ecs_cpu_diagnosis
```

Agent 应转换为如下命令参数：

```bash
--skillopt-session-id "sess-my-task-001" \
--skillopt-metadata tenant_id=10001 \
--skillopt-metadata env=prod \
--skillopt-metadata region=cn-hangzhou \
--skillopt-metadata task_id=DOPS-12345 \
--skillopt-metadata scene=ecs_cpu_diagnosis
```

## 5. 使用场景

### 5.1 修复效果分析

在 Langfuse Dashboard 查看：
- 各类错误的修复成功率
- 平均修复时间
- 需要改进的修复策略

### 5.2 性能瓶颈定位

追踪 API 调用耗时分布：
- 发现慢查询
- 识别频繁重试的场景
- 优化参数调优策略

### 5.3 Agent 调用链追踪

将 Runtime Harness 事件关联到 Agent 的完整调用链：
- 端到端可视化请求处理过程
- 分析 Agent 决策路径
- 优化 Agent 工作流

### 5.4 质量评估

基于追踪数据评估 Runtime Harness 的效果：
- 整体修复成功率
- 错误率趋势
- 为 Skill 进化提供数据支撑

## 6. 与现有系统集成

### 6.1 结构化日志

追踪事件同时写入日志（JSON Lines）：

```json
{"ts":"2026-01-17T10:30:45+0800","skill":"cms","level":"info","msg":"trace: repair_success","trace_id":"agent-123","event_type":"repair_success","pid":12345}
```

### 6.2 Prometheus 指标

追踪事件触发指标更新：
- `skillopt_repair_success` 计数器增加
- `skillopt_total_failures` 计数器增加

### 6.3 运营报告

报告包含追踪统计摘要：
- 追踪事件总数
- 各类事件分布
- 追踪成功率

## 7. 实施计划

### Phase 2.1：基础追踪

- [x] 实现 Langfuse Session / Trace / Span 上报能力
- [x] 在 wrapper 调用生命周期中插入追踪点
- [x] 支持 API 调用 input / output 上报
- [x] 支持 Langfuse 必填变量校验
- [x] 支持本地 trace 文件落盘

### Phase 2.2：多 Skill 链路关联

- [x] 支持显式 `SKILLOPT_SESSION_ID`
- [x] 支持 IDE 环境变量兜底生成 Session ID
- [x] 支持工作目录 hash + 日期的 fallback Session ID
- [x] 验证 CMS + ECS 多 Skill 共享 Session
- [x] 验证 RDS + Redis 多 Skill 共享 Session

### Phase 2.3：代表性 Skill 灰度接入

- [x] `alicloud-cms-ops`
- [x] `alicloud-ecs-ops`
- [x] `alicloud-slb-ops`
- [x] `alicloud-rds-ops`
- [x] `alicloud-redis-ops`

### Phase 2.4：分层判定模型设计与验证

- [x] 完成 Span 事实层与 Trace Judge 层分离设计
- [x] 验证 "Span 事实不可篡改，Judge 仅追加判定" 原则
- [x] 实现 LLM Judge + rule_engine 降级机制
- [x] 完成 `skillopt.trace_judgement` 观察点标准化
- [x] ACK/DAS/ALB/CEN 四个新增 Skill 灰度接入
- [x] 建立统一 Langfuse 接入验收脚本 `scripts/test-langfuse-gray-skills.sh`

### Phase 2.5：标准化与批量推广

- [x] 将已验证实现固化为标准模板
- [x] 更新 Skill 生成器，使新 Skill 默认使用 `scripts/skillopt-lib.sh`
- [x] 建立所有 Skill 的 Langfuse 接入状态清单
- [x] 灰度接入 ACK、DAS、ALB、CEN 四个代表性 Skill
- [ ] 继续灰度接入 MongoDB、Elasticsearch 等剩余代表性 Skill
- [ ] 灰度完成后批量推广到剩余 `alicloud-*-ops` Skill

### Phase 2.6：分析与可视化

- [ ] 创建 Langfuse Dashboard 模板
- [ ] 实现追踪数据分析
- [ ] 生成追踪报告

## 8. 性能考虑

### 8.1 异步发送

追踪事件通过后台进程异步发送，不阻塞主流程：

```bash
curl ... >/dev/null 2>&1 &
```

### 8.2 批量上报（未来优化）

可以缓冲多个事件，批量发送：

```bash
# 每 10 个事件或每 5 秒发送一次
if [[ ${#trace_buffer[@]} -ge 10 ]] || [[ $((now - last_send)) -ge 5 ]]; then
    send_trace_batch "${trace_buffer[@]}"
    trace_buffer=()
fi
```

### 8.3 失败处理

追踪发送失败不影响主流程：

```bash
# 发送失败只记录日志，不返回错误
curl ... >/dev/null 2>&1 || skillopt_log "trace: send failed"
```

## 9. 安全考虑

### 9.1 敏感信息脱敏

追踪事件中不包含：
- API Key/Secret
- 密码
- 其他敏感凭证

### 9.2 数据最小化

只发送必要的追踪数据：
- 事件类型
- 关键属性
- 时间戳

### 9.3 传输安全

使用 HTTPS 传输：
```bash
curl -X POST "https://${LANGFUSE_HOST}/api/public/ingestion" ...
```

## 10. 测试验证

### 10.0 当前验证结论

已完成以下集成验证：

| 验证项 | 结果 |
|--------|------|
| CMS 单 Skill Langfuse trace | ✅ 通过 |
| CMS 事件类型模拟集成测试 | ✅ 通过 |
| CMS + ECS 多 Skill 共享 Session | ✅ 通过 |
| SLB 单 Skill Langfuse trace | ✅ 通过 |
| RDS + Redis 多 Skill 共享 Session | ✅ 通过 |
| ACK/DAS/ALB/CEN 灰度 Skill 全量验证 | ✅ 通过 |
| trace-level input 非空 | ✅ 通过 |
| trace-level output 非空 | ✅ 通过 |
| 本地 trace id 直查 Langfuse | ✅ 通过 |
| zsh source 兼容性 | ✅ 通过 |
| `scripts/skillopt-lib.sh` 路径规范 | ✅ 通过 |
| Span 事实分层模型 | ✅ 通过 |
| LLM Judge 降级机制 | ✅ 通过 |

最新灰度集成测试（9 个 Skill 总计 52 个验证点）：

```text
bash scripts/test-langfuse-gray-skills.sh
...
PASS=52, FAIL=0, TOTAL=52
```

验证覆盖：
- `scripts/skillopt-lib.sh` 路径规范检查
- wrapper 正确 source 路径验证
- `bash -n` 语法检查
- `zsh source` 兼容性检查
- 本地 trace 文件闭合状态验证
- 同一轮多 Skill 共用同一个 `SKILLOPT_SESSION_ID`
- trace-level input/output 非空验证
- Langfuse 可直查验证

最近一次 RDS + Redis 验证结果：

```text
RDS name=alicloud-rds-ops rds DescribeDBInstances
sessionId=sess-rds-redis-langfuse-1781648531
input_type=array
output_type=object
output_empty=false

REDIS name=alicloud-redis-ops r-kvstore DescribeInstances
sessionId=sess-rds-redis-langfuse-1781648531
input_type=array
output_type=object
output_empty=false
```

### 10.1 单元测试

```bash
# 追踪事件生成测试
test_trace_event_generation() {
    local event=$(skillopt_trace_event "repair_success" '{"error_code":"Throttling"}')
    assert_json_field "event has trace_id" "$event" ".trace_id" ".*"
    assert_json_field "event has skill" "$event" ".metadata.skill" "cms"
}
```

### 10.2 集成测试

```bash
# 端到端追踪测试
test_trace_integration() {
    export SKILLOPT_LANGFUSE_ENABLED="true"
    export LANGFUSE_HOST="http://localhost:3000"
    
    # 执行 API 调用
    ./scripts/cms-skillopt-wrapper.sh DescribeMetricList --skillopt-enable ...
    
    # 验证追踪事件已发送
    curl "${LANGFUSE_HOST}/api/public/traces" | jq '.data | length'
}
```

---

**文档版本**: v1.0 (Gray Verified)  
**最后更新**: 2026-06-18  
**维护者**: Runtime Harness Team
