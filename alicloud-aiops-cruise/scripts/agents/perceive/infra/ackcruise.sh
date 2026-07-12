#!/usr/bin/env bash
#
# perceive/infra/ackcruise.sh — ACK Cruise Agent
#
# 职责:
#   对拓扑中发现的每个 ACK 集群执行 Intelligent Inspection（5 维度评分）：
#   集群状态 → 节点健康 → CMS 指标 → Addon 状态 → 综合评分。
#   引用 alicloud-ack-ops 的智能巡检流程，输出结构化 JSON 报告。
#
# 调度: 与 healthcruise/toposcan 并行执行（由 __init__.sh 编排）
#
# 用法:
#   bash ackcruise.sh                                          # 扫描全部 ACK 集群
#   bash ackcruise.sh --cluster-id c-xxx                       # 指定集群
#   bash ackcruise.sh --region cn-hangzhou                     # 指定区域
#   bash ackcruise.sh --output-file ./output.json              # 指定输出
#
# 输出:
#   JSON 报告含每个集群的 inspection: score/dimensions/recommendations
#

set -euo pipefail

# ── 路径解析 ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
export SKILLS_DIR="$(cd "${AIOPS_DIR}/.." && pwd)"

# shellcheck source=../../../lib/runtime_root.sh
source "${AIOPS_DIR}/scripts/lib/runtime_root.sh"
aiops_runtime_init "alicloud-aiops-cruise"

REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
CLUSTER_ID=""
OUTPUT_FILE=""
AUDIT_DIR="${RUNTIME_AUDIT_DIR}/perceive"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-file)
            if [[ $# -lt 2 || "$2" == --* ]]; then
                echo "[ACKCruise] ERROR: --output-file requires a value"
                exit 2
            fi
            OUTPUT_FILE="$2"; shift 2 ;;
        --cluster-id)
            if [[ $# -lt 2 || "$2" == --* ]]; then
                echo "[ACKCruise] ERROR: --cluster-id requires a value"
                exit 2
            fi
            CLUSTER_ID="$2"; shift 2 ;;
        --region)
            if [[ $# -lt 2 || "$2" == --* ]]; then
                echo "[ACKCruise] ERROR: --region requires a value"
                exit 2
            fi
            REGION="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [[ -z "$OUTPUT_FILE" ]]; then
    OUTPUT_FILE="${AUDIT_DIR}/ackcruise-$(date +%Y%m%dT%H%M%S).json"
fi
if [[ -z "$REGION" ]]; then
    REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
fi
mkdir -p "$(dirname "${OUTPUT_FILE}")"

echo "[ACKCruise] 开始 ACK 集群智能巡检: region=${REGION}"

# ── Pre-flight: 单集群模式先验证集群可访问 ──
if [[ -n "$CLUSTER_ID" ]]; then
    echo "[ACKCruise] Pre-flight: 验证集群 ${CLUSTER_ID} ..."
    _pf_detail=$(cs_get "/clusters/${CLUSTER_ID}" --region "$REGION" || echo "{}")
    _pf_state=$(echo "$_pf_detail" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('state',''))" 2>/dev/null || echo "")
    if [[ "$_pf_state" != "running" ]]; then
        echo "[ACKCruise] WARN: cluster=${CLUSTER_ID} state=${_pf_state} — 跳过非运行中集群"
        echo '{"agent":"ackcruise","status":"skipped","reason":"cluster not running","timestamp":"'"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"'"}' > "$OUTPUT_FILE"
        exit 0
    fi
    echo "[ACKCruise] Pre-flight PASS: 集群运行中"
fi

# ── SkillOpt Wrapper (M2: 使用 ack-harness-wrapper.sh 启用 auto-repair + 限速重试) ──
# 路径: 相对于 ackcruise.sh (infra/) -> scripts/agents/ -> scripts/ -> alicloud-aiops-cruise/ -> alicloud-ack-ops/scripts/
ACK_HARNESS_WRAPPER="${SKILLS_DIR}/alicloud-ack-ops/scripts/ack-harness-wrapper.sh"

# cs_get(): 优先走 SkillOpt wrapper，降级回直接 aliyun cs GET
# 用法: cs_get /clusters --region xxx
cs_get() {
    local path="$1"; shift
    if [[ -f "${ACK_HARNESS_WRAPPER}" ]]; then
        "${ACK_HARNESS_WRAPPER}" cs GET "${path}" "$@" 2>/dev/null
    else
        # Fallback: 直接调用 aliyun cs
        aliyun cs GET "${path}" "$@" 2>/dev/null
    fi
}

# ── 工具检查 ──
if ! command -v aliyun &>/dev/null; then
    echo "[ACKCruise] FAIL aliyun CLI 不可用"
    echo '{"agent":"ackcruise","status":"failed","reason":"aliyun CLI missing","timestamp":"'"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"'"}' > "$OUTPUT_FILE"
    exit 1
fi
if [[ -f "${ACK_HARNESS_WRAPPER}" ]]; then
    echo "[ACKCruise] 使用 SkillOpt auto-repair wrapper: ${ACK_HARNESS_WRAPPER}"
else
    echo "[ACKCruise] WARN: ack-harness-wrapper.sh 未找到，降级为直接 aliyun cs 调用"
fi

# ── 获取集群列表 ──
if [[ -z "$CLUSTER_ID" ]]; then
    echo "[ACKCruise] 扫描所有 ACK 集群..."
    CLUSTERS_RAW=$(cs_get /clusters --region "$REGION" || echo "[]")
    if [[ -z "$CLUSTERS_RAW" || "$CLUSTERS_RAW" == "[]" ]]; then
        echo "[ACKCruise] SKIP 当前区域无可巡检的 ACK 集群"
        echo '{"agent":"ackcruise","status":"skipped","reason":"no ACK clusters found in region","timestamp":"'"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"'"}' > "$OUTPUT_FILE"
        exit 0
    fi
    CLUSTER_IDS=$(echo "$CLUSTERS_RAW" | python3 -c "
import json,sys; data=json.load(sys.stdin)
clusters = data if isinstance(data, list) else data.get('clusters', [])
for c in clusters:
    cid = c.get('cluster_id','')
    state = c.get('state','')
    if cid and state == 'running':
        print(cid)
" 2>/dev/null || true)
else
    CLUSTER_IDS="$CLUSTER_ID"
fi

if [[ -z "$CLUSTER_IDS" ]]; then
    echo "[ACKCruise] SKIP 无运行中的 ACK 集群"
    echo '{"agent":"ackcruise","status":"skipped","reason":"no running ACK clusters","timestamp":"'"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"'"}' > "$OUTPUT_FILE"
    exit 0
fi

# ── 日期工具 ──
_now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
_15m_ago() {
    date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null ||
    date -u -v-15M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null
}

# ── 智能巡检：对单个集群执行 5 维度评分 ──
inspect_cluster() {
    local cid="$1"
    local region="$2"
    local score=0
    local dimensions="[]"
    local recommendations="[]"

    echo "[ACKCruise]   → 巡检集群: ${cid}"

    # 1. 集群状态 (25分)
    local detail
    detail=$(cs_get "/clusters/${cid}" --region "$region" || echo "{}")
    local state
    state=$(echo "$detail" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('state',''))" 2>/dev/null || echo "")
    local name
    name=$(echo "$detail" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('name',''))" 2>/dev/null || echo "")
    local cluster_version
    cluster_version=$(echo "$detail" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('current_version',''))" 2>/dev/null || echo "")

    local state_score=0
    local state_status="unknown"
    if [[ "$state" == "running" ]]; then
        state_score=100
        state_status="healthy"
        score=$((score + 25))
    else
        state_score=0
        state_status="critical"
    fi

    # 2. 节点健康 (25分)
    local nodes_json
    nodes_json=$(cs_get "/clusters/${cid}/nodes" --region "$region" || echo '{"nodes":[]}')
    local total_nodes ready_nodes
    total_nodes=$(echo "$nodes_json" | python3 -c "
import json,sys; d=json.load(sys.stdin)
nodes = d.get('nodes',[])
print(len(nodes))
" 2>/dev/null || echo "0")
    ready_nodes=$(echo "$nodes_json" | python3 -c "
import json,sys; d=json.load(sys.stdin)
nodes = d.get('nodes',[])
ready = [n for n in nodes if n.get('node_status','') == 'Ready']
print(len(ready))
" 2>/dev/null || echo "0")

    local node_score=0 node_status="unknown" node_ratio=0
    if [[ "$total_nodes" -gt 0 ]]; then
        node_ratio=$((ready_nodes * 100 / total_nodes))
        if [[ "$node_ratio" -eq 100 ]]; then
            node_score=100; node_status="healthy"; score=$((score + 25))
        elif [[ "$node_ratio" -ge 90 ]]; then
            node_score=60; node_status="warning"; score=$((score + 15))
        else
            node_score=0; node_status="critical"
        fi
    fi

    # 3. 集群 CPU 使用率 (20分)
    local cpu
    cpu=$(aliyun cms DescribeMetricList \
        --Namespace acs_k8s_dashboard --MetricName CpuUsage \
        --Dimensions "[{\"clusterId\":\"${cid}\"}]" \
        --Period 60 \
        --StartTime "$(_15m_ago)" \
        --EndTime "$(_now_iso)" \
        2>/dev/null \
        | python3 -c "
import json,sys; d=json.load(sys.stdin)
dps = d.get('Datapoints','[]')
if isinstance(dps, str):
    import json; dps=json.loads(dps)
vals=[p.get('Average',0) for p in dps if isinstance(p,dict)]
print(sum(vals)/len(vals) if vals else 'N/A')
" 2>/dev/null || echo "N/A")

    local cpu_score=0 cpu_status="unknown"
    if [[ "$cpu" != "N/A" ]]; then
        local cpu_int
        cpu_int=$(echo "$cpu" | python3 -c "print(int(float(input())))" 2>/dev/null || echo "0")
        if [[ "$cpu_int" -lt 70 ]]; then
            cpu_score=100; cpu_status="healthy"; score=$((score + 20))
        elif [[ "$cpu_int" -lt 85 ]]; then
            cpu_score=60; cpu_status="warning"; score=$((score + 10))
        else
            cpu_score=0; cpu_status="critical"
        fi
    fi

    # 4. 集群内存使用率 (20分)
    local mem
    mem=$(aliyun cms DescribeMetricList \
        --Namespace acs_k8s_dashboard --MetricName MemoryUsage \
        --Dimensions "[{\"clusterId\":\"${cid}\"}]" \
        --Period 60 \
        --StartTime "$(_15m_ago)" \
        --EndTime "$(_now_iso)" \
        2>/dev/null \
        | python3 -c "
import json,sys; d=json.load(sys.stdin)
dps = d.get('Datapoints','[]')
if isinstance(dps, str):
    import json; dps=json.loads(dps)
vals=[p.get('Average',0) for p in dps if isinstance(p,dict)]
print(sum(vals)/len(vals) if vals else 'N/A')
" 2>/dev/null || echo "N/A")

    local mem_score=0 mem_status="unknown"
    if [[ "$mem" != "N/A" ]]; then
        local mem_int
        mem_int=$(echo "$mem" | python3 -c "print(int(float(input())))" 2>/dev/null || echo "0")
        if [[ "$mem_int" -lt 75 ]]; then
            mem_score=100; mem_status="healthy"; score=$((score + 20))
        elif [[ "$mem_int" -lt 90 ]]; then
            mem_score=60; mem_status="warning"; score=$((score + 10))
        else
            mem_score=0; mem_status="critical"
        fi
    fi

    # 5. Addon 状态 (10分)
    local addons_json
    addons_json=$(cs_get "/clusters/${cid}/addons" --region "$region" || echo '{"addons":[]}')
    local addon_ok addon_total
    addon_ok=$(echo "$addons_json" | python3 -c "
import json,sys; d=json.load(sys.stdin)
addons = d.get('addons',[])
ok = [a for a in addons if a.get('state','') == 'active']
print(len(ok))
" 2>/dev/null || echo "0")
    addon_total=$(echo "$addons_json" | python3 -c "
import json,sys; d=json.load(sys.stdin)
addons = d.get('addons',[])
print(len(addons))
" 2>/dev/null || echo "0")

    local addon_score=0 addon_status="unknown"
    if [[ "$addon_total" -gt 0 ]]; then
        if [[ "$addon_ok" -eq "$addon_total" ]]; then
            addon_score=100; addon_status="healthy"; score=$((score + 10))
        else
            local addon_unhealthy=$((addon_total - addon_ok))
            addon_score=0; addon_status="critical"
            echo "[ACKCruise]   ⚠ Addon 异常: ${addon_unhealthy}/${addon_total}"
        fi
    fi

    # ── 构建输出 ──
    local overall_status="healthy"
    if [[ "$score" -lt 60 ]]; then
        overall_status="critical"
    elif [[ "$score" -lt 80 ]]; then
        overall_status="warning"
    fi

    dimensions=$(cat <<PYEOF | python3
import json
dims = [
    {"name":"集群状态","score":${state_score},"status":"${state_status}","value":"${state}"},
    {"name":"节点Ready比例","score":${node_score},"status":"${node_status}","value":"${ready_nodes}/${total_nodes}"},
    {"name":"集群CPU使用率","score":${cpu_score},"status":"${cpu_status}","value":"${cpu}%"},
    {"name":"集群内存使用率","score":${mem_score},"status":"${mem_status}","value":"${mem}%"},
    {"name":"Addon状态","score":${addon_score},"status":"${addon_status}","value":"${addon_ok}/${addon_total}"}
]
print(json.dumps(dims))
PYEOF
)

    local recs="[]"
    if [[ "$cpu_status" == "warning" || "$cpu_status" == "critical" ]]; then
        recs=$(echo "$recs" | python3 -c "
import json; r=json.loads(input())
r.append('集群CPU使用率${cpu}%超过阈值，建议扩容节点或优化工作负载调度')
print(json.dumps(r))
")
    fi
    if [[ "$mem_status" == "warning" || "$mem_status" == "critical" ]]; then
        recs=$(echo "$recs" | python3 -c "
import json; r=json.loads('$recs')
r.append('集群内存使用率${mem}%超过阈值，建议检查Pod内存Limit或扩容节点')
print(json.dumps(r))
")
    fi
    if [[ "$addon_status" == "critical" ]]; then
        local unhealthy_names
        unhealthy_names=$(echo "$addons_json" | python3 -c "
import json,sys; d=json.load(sys.stdin)
addons = d.get('addons',[])
bad=[a.get('name','') for a in addons if a.get('state','') != 'active']
print(','.join(bad))
" 2>/dev/null || echo "")
        recs=$(echo "$recs" | python3 -c "
import json; r=json.loads('$recs')
r.append('Addon组件异常: ${unhealthy_names}，请检查组件状态并修复')
print(json.dumps(r))
")
    fi
    if [[ "$node_status" != "healthy" && "$total_nodes" -gt 0 ]]; then
        recs=$(echo "$recs" | python3 -c "
import json; r=json.loads('$recs')
r.append('节点Ready比例${node_ratio}%，未达到100%，建议排查NotReady节点')
print(json.dumps(r))
")
    fi

    echo "$(cat <<PYEOF | python3
import json
print(json.dumps({
    "cluster_id": "${cid}",
    "cluster_name": "${name}",
    "cluster_version": "${cluster_version}",
    "region": "${region}",
    "inspection_time": "$(_now_iso)",
    "overall_score": ${score},
    "overall_status": "${overall_status}",
    "dimensions": ${dimensions},
    "recommendations": ${recs}
}, ensure_ascii=False))
PYEOF
)"
}

# ── 逐个巡检所有集群 ──
RESULTS="[]"
for cid in $CLUSTER_IDS; do
    cid_trim=$(echo "$cid" | xargs)
    [[ -z "$cid_trim" ]] && continue
    result=$(inspect_cluster "$cid_trim" "$REGION") || true
    RESULTS=$(echo "$RESULTS" | python3 -c "
import json,sys
results = json.loads(sys.stdin.read())
new_item = json.loads('''${result}''')
results.append(new_item)
print(json.dumps(results))
")
done

# ── 写入输出 ──
CLUSTER_COUNT=$(echo "$CLUSTER_IDS" | wc -l | tr -d ' ')
{
    echo '{'
    echo '  "agent": "ackcruise",'
    echo '  "status": "completed",'
    echo '  "timestamp": "'"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"'",'
    echo '  "cluster_count": '"${CLUSTER_COUNT}"','
    echo '  "inspections": '"${RESULTS}"
    echo '}'
} > "$OUTPUT_FILE"

echo "[ACKCruise] PASS 巡检完成: ${CLUSTER_COUNT} 个集群"