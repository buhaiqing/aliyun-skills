#!/usr/bin/env bash
#
# 多 Skill 联动测试：CMS + ECS + OSS 共享 Session ID
# 模拟真实运维场景：查告警规则 → 查 ECS 实例 → 列 OSS Bucket
#
# Usage:
#   ./scripts/test-multi-skill-session.sh           # full — 需 .env 中 Langfuse + 阿里云 AK
#   ./scripts/test-multi-skill-session.sh --local # local — 仅验证本地 trace/session（无需 Langfuse）

set -euo pipefail

MODE="full"
if [[ "${1:-}" == "--local" ]]; then
    MODE="local"
elif [[ -n "${1:-}" ]]; then
    echo "Usage: $0 [--local]" >&2
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CMS_ROOT="${PROJECT_ROOT}/alicloud-cms-ops"
ECS_ROOT="${PROJECT_ROOT}/alicloud-ecs-ops"
OSS_ROOT="${PROJECT_ROOT}/alicloud-oss-ops"
ENV_FILE="${PROJECT_ROOT}/.env"

export ALIYUN_SKILLS_ROOT="$PROJECT_ROOT"
export HARNESS_ENABLED="${HARNESS_ENABLED:-true}"
export ALIBABA_CLOUD_REGION_ID="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"

echo "Project root: $PROJECT_ROOT"
echo "Mode: $MODE"
echo "ENV file: $ENV_FILE"

load_env_file() {
    local file="$1"
    [[ -f "$file" ]] || return 0
    echo "Loading $file ..."
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        key="${line%%=*}"
        value="${line#*=}"
        key="$(echo "$key" | xargs)"
        value="$(echo "$value" | xargs)"
        if [[ -n "$key" && -z "${!key:-}" ]]; then
            export "$key=$value"
        fi
    done < "$file"
}

bootstrap_aliyun_from_cli() {
    if [[ -n "${ALIBABA_CLOUD_ACCESS_KEY_ID:-}" && -n "${ALIBABA_CLOUD_ACCESS_KEY_SECRET:-}" ]]; then
        return 0
    fi
    local cfg="${HOME}/.aliyun/config.json"
    if [[ -f "$cfg" ]] && command -v jq >/dev/null 2>&1; then
        local ak sk
        ak="$(jq -r '.profiles[] | select(.name=="default") | .access_key_id // empty' "$cfg" 2>/dev/null)"
        sk="$(jq -r '.profiles[] | select(.name=="default") | .access_key_secret // empty' "$cfg" 2>/dev/null)"
        if [[ -n "$ak" && -n "$sk" && "$ak" != "null" ]]; then
            export ALIBABA_CLOUD_ACCESS_KEY_ID="$ak"
            export ALIBABA_CLOUD_ACCESS_KEY_SECRET="$sk"
            echo "Bootstrapped Alibaba Cloud credentials from ~/.aliyun/config.json (default profile)"
            return 0
        fi
    fi
    return 1
}

load_env_file "$ENV_FILE"
load_env_file "${PROJECT_ROOT}/.env.local"
bootstrap_aliyun_from_cli || true

# Repo-centralized observability (AGENTS §13): traces/sessions/logs/metrics under ${SKILLS_DIR}/.runtime/
unset ALIBABA_CLOUD_RUNTIME_DIR
RUNTIME_ROOT="${PROJECT_ROOT}/.runtime"
CMS_TRACES_DIR="${RUNTIME_ROOT}/traces/alicloud-cms-ops"
ECS_TRACES_DIR="${RUNTIME_ROOT}/traces/alicloud-ecs-ops"
OSS_TRACES_DIR="${RUNTIME_ROOT}/traces/alicloud-oss-ops"

for var in ALIBABA_CLOUD_ACCESS_KEY_ID ALIBABA_CLOUD_ACCESS_KEY_SECRET; do
    if [[ -z "${!var:-}" ]]; then
        echo "ERROR: $var is not set (add to .env or run: aliyun configure set)" >&2
        exit 1
    fi
done

if [[ "$MODE" == "full" ]]; then
    for var in LANGFUSE_HOST LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY; do
        if [[ -z "${!var:-}" ]]; then
            echo "ERROR: $var is not set — add to ${ENV_FILE} or run: $0 --local" >&2
            echo "Hint: cp .env.example .env and set Langfuse keys" >&2
            exit 1
        fi
    done
    export HARNESS_LANGFUSE_ENABLED="true"
else
    export HARNESS_LANGFUSE_ENABLED="${HARNESS_LANGFUSE_ENABLED:-false}"
fi

# 生成共享 Session ID
SHARED_SESSION="sess-multi-skill-test-$(date +%s)"
export HARNESS_SESSION_ID="$SHARED_SESSION"

AUTH=""
if [[ "$MODE" == "full" ]]; then
    AUTH=$(printf '%s' "${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}" | base64)
fi
PASS=0
FAIL=0
TOTAL=0

echo "============================================"
echo "  多 Skill 联动测试 (CMS + ECS + OSS)"
echo "  模式: $MODE"
echo "  共享 Session: $SHARED_SESSION"
if [[ "$MODE" == "full" ]]; then
    echo "  Langfuse: $LANGFUSE_HOST"
fi
echo "============================================"
echo

# ---- 场景 1: CMS 查询告警规则 ----
echo "=== 场景 1: CMS 查询告警规则 ==="
echo "执行: alicloud-cms-ops DescribeMetricRuleList --PageSize 3"

WRAPPER_EXTRA=()
if [[ "$MODE" == "full" ]]; then
    WRAPPER_EXTRA+=(--harness-langfuse-enable)
fi

CMS_OUTPUT=$("${CMS_ROOT}/scripts/cms-harness-wrapper.sh" \
    DescribeMetricRuleList \
    --harness-session-id "$SHARED_SESSION" \
    "${WRAPPER_EXTRA[@]+"${WRAPPER_EXTRA[@]}"}" \
    --PageSize 3 \
    2>"${TMPDIR:-/tmp}/skillopt-cms-$$.err") || true

TOTAL=$((TOTAL + 1))
if [[ -n "$CMS_OUTPUT" ]]; then
    PASS=$((PASS + 1))
    echo "  [PASS] CMS 返回数据 ($(echo "$CMS_OUTPUT" | wc -c | tr -d ' ') bytes)"
else
    FAIL=$((FAIL + 1))
    echo "  [FAIL] CMS 无返回数据"
fi
echo

# ---- 场景 2: ECS 查询实例列表 ----
echo "=== 场景 2: ECS 查询实例列表 ==="
echo "执行: alicloud-ecs-ops DescribeInstances --PageSize 3"

ECS_OUTPUT=$("${ECS_ROOT}/scripts/ecs-harness-wrapper.sh" \
    DescribeInstances \
    --harness-session-id "$SHARED_SESSION" \
    "${WRAPPER_EXTRA[@]+"${WRAPPER_EXTRA[@]}"}" \
    --PageSize 3 \
    2>"${TMPDIR:-/tmp}/skillopt-ecs-$$.err") || true

TOTAL=$((TOTAL + 1))
if [[ -n "$ECS_OUTPUT" ]]; then
    PASS=$((PASS + 1))
    echo "  [PASS] ECS 返回数据 ($(echo "$ECS_OUTPUT" | wc -c | tr -d ' ') bytes)"
else
    FAIL=$((FAIL + 1))
    echo "  [FAIL] ECS 无返回数据"
fi
echo

# ---- 场景 3: OSS 列举 Bucket（表格输出，验证多行 trace 编码） ----
echo "=== 场景 3: OSS 列举 Bucket ==="
echo "执行: alicloud-oss-ops ls"

OSS_OUTPUT=$("${OSS_ROOT}/scripts/oss-harness-wrapper.sh" \
    ls \
    --harness-session-id "$SHARED_SESSION" \
    "${WRAPPER_EXTRA[@]+"${WRAPPER_EXTRA[@]}"}" \
    2>"${TMPDIR:-/tmp}/skillopt-oss-$$.err") || true

TOTAL=$((TOTAL + 1))
if [[ -n "$OSS_OUTPUT" ]]; then
    PASS=$((PASS + 1))
    echo "  [PASS] OSS 返回数据 ($(echo "$OSS_OUTPUT" | wc -c | tr -d ' ') bytes)"
else
    FAIL=$((FAIL + 1))
    echo "  [FAIL] OSS 无返回数据"
fi
echo

# ---- 场景 4: CMS 查询监控数据 ----
echo "=== 场景 4: CMS 查询监控数据 ==="
echo "执行: alicloud-cms-ops DescribeProjectMeta --PageSize 3"

CMS_OUTPUT2=$("${CMS_ROOT}/scripts/cms-harness-wrapper.sh" \
    DescribeProjectMeta \
    --harness-session-id "$SHARED_SESSION" \
    "${WRAPPER_EXTRA[@]+"${WRAPPER_EXTRA[@]}"}" \
    --PageSize 3 \
    2>"${TMPDIR:-/tmp}/skillopt-cms2-$$.err") || true

TOTAL=$((TOTAL + 1))
if [[ -n "$CMS_OUTPUT2" ]]; then
    PASS=$((PASS + 1))
    echo "  [PASS] CMS 返回数据 ($(echo "$CMS_OUTPUT2" | wc -c | tr -d ' ') bytes)"
else
    FAIL=$((FAIL + 1))
    echo "  [FAIL] CMS 无返回数据"
fi
echo

# ---- 场景 5: ECS 查询磁盘信息 ----
echo "=== 场景 5: ECS 查询磁盘信息 ==="
echo "执行: alicloud-ecs-ops DescribeDisks --PageSize 3"

ECS_OUTPUT2=$("${ECS_ROOT}/scripts/ecs-harness-wrapper.sh" \
    DescribeDisks \
    --harness-session-id "$SHARED_SESSION" \
    "${WRAPPER_EXTRA[@]+"${WRAPPER_EXTRA[@]}"}" \
    --PageSize 3 \
    2>"${TMPDIR:-/tmp}/skillopt-ecs2-$$.err") || true

TOTAL=$((TOTAL + 1))
if [[ -n "$ECS_OUTPUT2" ]]; then
    PASS=$((PASS + 1))
    echo "  [PASS] ECS 返回数据 ($(echo "$ECS_OUTPUT2" | wc -c | tr -d ' ') bytes)"
else
    FAIL=$((FAIL + 1))
    echo "  [FAIL] ECS 无返回数据"
fi
echo

echo "============================================"
echo "  执行结果: $PASS/$TOTAL 通过"
echo "============================================"
echo

# 等待异步上报完成
if [[ "$MODE" == "full" ]]; then
    echo "等待 3 秒让 Langfuse 上报完成..."
    sleep 3
    echo
fi

# ---- 验证 Trace / Session ----
echo "=== 验证 Session 共享 ==="

TRACE_IDS=$(find "$CMS_TRACES_DIR" "$ECS_TRACES_DIR" "$OSS_TRACES_DIR" \
    -name "trace-${SHARED_SESSION}-*.json" 2>/dev/null | \
    xargs -n1 basename 2>/dev/null | sed 's/\.json$//' || true)

if [[ -z "$TRACE_IDS" ]]; then
    echo "  [FAIL] 本地未找到待验证的 Trace ID"
    exit 1
fi

if [[ "$MODE" == "full" ]]; then
    echo "=== 从 Langfuse 验证 Session 共享 ==="

    TRACES=""
    while read -r tid; do
        [[ -z "$tid" ]] && continue
        trace_json=$(curl -s -H "Authorization: Basic ${AUTH}" \
            "${LANGFUSE_HOST}/api/public/traces/${tid}")
        line=$(printf '%s' "$trace_json" | jq -r --arg sid "$SHARED_SESSION" \
            'if .id and .sessionId == $sid then "\(.id) | \(.name) | \(.timestamp)" else empty end')
        if [[ -n "$line" ]]; then
            TRACES+="$line"$'\n'
        fi
    done <<< "$TRACE_IDS"

    if [[ -z "$TRACES" ]]; then
        echo "  [FAIL] Langfuse 未找到共享 Session 的 Traces"
        exit 1
    fi

    TRACE_COUNT=$(printf '%s' "$TRACES" | sed '/^$/d' | wc -l | tr -d ' ')
    echo "  找到 $TRACE_COUNT 条 Traces:"
    printf '%s' "$TRACES" | sed '/^$/d' | while read -r line; do
        echo "    - $line"
    done
    echo

    CMS_TRACES=$(printf '%s' "$TRACES" | grep -c "alicloud-cms-ops" || true)
    ECS_TRACES=$(printf '%s' "$TRACES" | grep -c "alicloud-ecs-ops" || true)
    OSS_TRACES=$(printf '%s' "$TRACES" | grep -c "alicloud-oss-ops" || true)
else
    echo "=== 本地模式：从 trace 文件验证 Skill 分布 ==="
    CMS_TRACES=$(find "$CMS_TRACES_DIR" -name "trace-${SHARED_SESSION}-*.json" 2>/dev/null | wc -l | tr -d ' ')
    ECS_TRACES=$(find "$ECS_TRACES_DIR" -name "trace-${SHARED_SESSION}-*.json" 2>/dev/null | wc -l | tr -d ' ')
    OSS_TRACES=$(find "$OSS_TRACES_DIR" -name "trace-${SHARED_SESSION}-*.json" 2>/dev/null | wc -l | tr -d ' ')
fi

echo "=== Skill 分布验证 ==="
echo "  alicloud-cms-ops traces: $CMS_TRACES"
echo "  alicloud-ecs-ops traces: $ECS_TRACES"
echo "  alicloud-oss-ops traces: $OSS_TRACES"
echo

TOTAL=$((TOTAL + 1))
if [[ $CMS_TRACES -gt 0 && $ECS_TRACES -gt 0 && $OSS_TRACES -gt 0 ]]; then
    echo "  [PASS] Session 包含 CMS、ECS、OSS 三个 Skill 的 Traces"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] Session 未包含 CMS、ECS、OSS 三个 Skill 的 Traces"
    FAIL=$((FAIL + 1))
fi
echo

# 验证 Session 文件
echo "=== 本地 Session 文件验证 ==="
CMS_SESSION_FILE="${RUNTIME_ROOT}/sessions/alicloud-cms-ops/skillopt-session-${SHARED_SESSION}.json"
ECS_SESSION_FILE="${RUNTIME_ROOT}/sessions/alicloud-ecs-ops/skillopt-session-${SHARED_SESSION}.json"
OSS_SESSION_FILE="${RUNTIME_ROOT}/sessions/alicloud-oss-ops/skillopt-session-${SHARED_SESSION}.json"

for label in CMS ECS OSS; do
    var="${label}_SESSION_FILE"
    file="${!var}"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$file" ]]; then
        echo "  [PASS] ${label} Session 文件存在"
        echo "  内容: $(cat "$file" | jq -c '{skill, status, trace_count, llm_usage_total}')"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] ${label} Session 文件不存在"
        FAIL=$((FAIL + 1))
        continue
    fi
    TOTAL=$((TOTAL + 1))
    if jq -e 'has("llm_usage_total") and (.llm_usage_total | type) == "object"' "$file" >/dev/null 2>&1; then
        echo "  [PASS] ${label} Session 含 llm_usage_total (Phase 3 TEL)"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] ${label} Session 缺少 llm_usage_total"
        FAIL=$((FAIL + 1))
    fi
done
echo

# 验证 Trace 文件
echo "=== Trace 文件验证 ==="
CMS_TRACE_COUNT=$(find "$CMS_TRACES_DIR" -name "trace-${SHARED_SESSION}-*.json" 2>/dev/null | wc -l | tr -d ' ')
ECS_TRACE_COUNT=$(find "$ECS_TRACES_DIR" -name "trace-${SHARED_SESSION}-*.json" 2>/dev/null | wc -l | tr -d ' ')
OSS_TRACE_COUNT=$(find "$OSS_TRACES_DIR" -name "trace-${SHARED_SESSION}-*.json" 2>/dev/null | wc -l | tr -d ' ')

echo "  CMS Trace 文件数: $CMS_TRACE_COUNT"
echo "  ECS Trace 文件数: $ECS_TRACE_COUNT"
echo "  OSS Trace 文件数: $OSS_TRACE_COUNT"

TOTAL=$((TOTAL + 1))
if [[ $CMS_TRACE_COUNT -gt 0 && $ECS_TRACE_COUNT -gt 0 && $OSS_TRACE_COUNT -gt 0 ]]; then
    echo "  [PASS] CMS、ECS、OSS 都有本地 Trace 文件"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] 本地 Trace 文件不完整"
    FAIL=$((FAIL + 1))
fi
echo

# OSS 多行输出 trace 完整性（非 1-byte 损坏文件）
echo "=== OSS 多行 Trace 输出验证 ==="
OSS_TRACE_FILE=$(find "$OSS_TRACES_DIR" -name "trace-${SHARED_SESSION}-*.json" 2>/dev/null | head -1 || true)
TOTAL=$((TOTAL + 1))
if [[ -n "$OSS_TRACE_FILE" && $(wc -c < "$OSS_TRACE_FILE" | tr -d ' ') -gt 100 ]]; then
    OSS_TRACE_STATUS=$(jq -r '.status // empty' "$OSS_TRACE_FILE")
    OSS_OUTPUT_TYPE=$(jq -r '.output | type' "$OSS_TRACE_FILE")
    if [[ "$OSS_TRACE_STATUS" == "success" && "$OSS_OUTPUT_TYPE" == "string" ]]; then
        echo "  [PASS] OSS trace 文件完整 (status=$OSS_TRACE_STATUS, output_type=$OSS_OUTPUT_TYPE)"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] OSS trace 内容异常 (status=$OSS_TRACE_STATUS, output_type=$OSS_OUTPUT_TYPE)"
        FAIL=$((FAIL + 1))
    fi
else
    echo "  [FAIL] OSS trace 文件缺失或损坏"
    FAIL=$((FAIL + 1))
fi
echo

echo "============================================"
echo "  最终结果: $PASS/$TOTAL 通过, $FAIL 失败"
echo "============================================"
echo

if [[ $FAIL -eq 0 ]]; then
    if [[ "$MODE" == "full" ]]; then
        echo "多 Skill 联动测试成功！CMS + ECS + OSS Session ID 共享验证通过（含 Langfuse）。"
    else
        echo "多 Skill 本地联动测试成功！CMS + ECS + OSS Session ID 共享验证通过。"
        echo "下一步：配置 .env 中 Langfuse 后运行: $0"
    fi
    exit 0
else
    echo "有 $FAIL 项验证失败，请检查。"
    exit 1
fi
