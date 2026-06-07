#!/usr/bin/env bash
#
# perceive/infra/configdrift.sh — ConfigDrift Agent
#
# 职责:
#   对比 Topo baseline 检测配置漂移。委托 baseline-manager.py --diff 执行实际工作。
#
# 调度: 按需（推荐在 toposcan 之后执行）
#
# 用法:
#   bash configdrift.sh --output-file ./output.json
#   bash configdrift.sh --region cn-hangzhou
#   bash configdrift.sh --resource-group-id rg-xxx
#   bash configdrift.sh --compare-with 2026-05-15     # 与指定历史 baseline 对比
#
# 输出:
#   JSON 报告写入 --output-file（含 drift_items 列表 + compared_with 字段）
#   详细日志写入 --output-file.log
#
# Baseline Retention 策略:
#   - 默认 retention_days=90（与 baseline-manager.py 一致）
#   - 每天 02:00 跑 toposcan 累积新 baseline，3 个月内可回溯拓扑演进
#   - apply_retention 阶段会清理过期 baseline（建议 weekly 触发）
#   - --diff 模式不主动 apply retention（避免误删）
#
# 修复记录:
#   BUG-001: 路径解析 — SKILLS_DIR/BASELINE_DIR/AUDIT_DIR 多走一层 ../
#   BUG-002: 参数传递 — 与 baseline-manager.py 接口对齐
#             (原: --baseline/--current/--output → 现: --output-dir/--region/--diff)
#   Sprint-16 T2: 透传 --compare-with 到 baseline-manager, JSON 增加 compared_with 字段

set -euo pipefail

# ── 路径解析（Sprint 18: 统一运行时数据根目录）──────────────
# SCRIPT_DIR:     .../alicloud-aiops-cruise/scripts/agents/perceive/infra
# AIOPS_DIR:      .../alicloud-aiops-cruise                  (SCRIPT_DIR 向上 4 层)
# SKILLS_DIR:     .../aliyun-skills                          (AIOPS_DIR/..)
# RUNTIME_ROOT:   ${ALIYUN_SKILLS_RUNTIME_ROOT:-${SKILLS_DIR}/.runtime}
# BASELINE_DIR:   ${RUNTIME_ROOT}/baseline
# AUDIT_DIR:      ${RUNTIME_ROOT}/audit/aiops-cruise/perceive
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../../../" && pwd)"
# 显式 export SKILLS_DIR, 避免 lib 内部 BASH_SOURCE 推断歧义
export SKILLS_DIR="$(cd "${AIOPS_DIR}/../" && pwd)"

# 加载共享 lib (Sprint 18)
# shellcheck source=../../../lib/runtime_root.sh
source "${AIOPS_DIR}/scripts/lib/runtime_root.sh"
aiops_runtime_init "alicloud-aiops-cruise"

# 兼容软链接 (Sprint 18 软链接过渡)
TOPO_DIR="${SKILLS_DIR}/alicloud-topo-discovery/scripts"
BASELINE_DIR="${RUNTIME_BASELINE_DIR}"
AUDIT_DIR="${RUNTIME_AUDIT_DIR}/perceive"

REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
RESOURCE_GROUP_ID=""
OUTPUT_FILE=""
COMPARE_WITH=""

# ── 参数解析 ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-file)       OUTPUT_FILE="$2"; shift 2 ;;
        --region)            REGION="$2"; shift 2 ;;
        --resource-group-id) RESOURCE_GROUP_ID="$2"; shift 2 ;;
        --compare-with)      COMPARE_WITH="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [[ -z "$OUTPUT_FILE" ]]; then
    OUTPUT_FILE="${AUDIT_DIR}/configdrift-$(date +%Y%m%dT%H%M%S).json"
fi
mkdir -p "$(dirname "${OUTPUT_FILE}")"

echo "[ConfigDrift] 开始配置漂移检测"
echo "  BASELINE_DIR: ${BASELINE_DIR}"
echo "  REGION: ${REGION}"
[[ -n "$RESOURCE_GROUP_ID" ]] && echo "  RESOURCE_GROUP_ID: ${RESOURCE_GROUP_ID}"
if [[ -n "$COMPARE_WITH" ]]; then
    echo "  COMPARE_WITH: ${COMPARE_WITH} (历史 baseline)"
else
    echo "  COMPARE_WITH: latest (默认)"
fi

# ── 前置检查 1: baseline 目录存在 ──
if [[ ! -d "${BASELINE_DIR}" ]]; then
    echo "[ConfigDrift] 未找到 baseline 目录: ${BASELINE_DIR}"
    echo "[ConfigDrift] 请先执行 toposcan.sh 建立 baseline"
    python3 - "${OUTPUT_FILE}" "${BASELINE_DIR}" <<'PYEOF'
import json
import sys
from datetime import datetime, timezone
output_file, baseline_dir = sys.argv[1], sys.argv[2]
report = {
    "agent": "configdrift",
    "status": "skipped",
    "reason": "baseline directory not found",
    "baseline_dir": baseline_dir,
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
with open(output_file, "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
PYEOF
    exit 0
fi

# ── 前置检查 2: baseline-manager.py 存在 ──
if [[ ! -f "${TOPO_DIR}/baseline-manager.py" ]]; then
    echo "[ConfigDrift] baseline-manager.py 不存在: ${TOPO_DIR}"
    python3 - "${OUTPUT_FILE}" <<'PYEOF'
import json
import sys
from datetime import datetime, timezone
output_file = sys.argv[1]
report = {
    "agent": "configdrift",
    "status": "failed",
    "reason": "baseline-manager.py not found",
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
with open(output_file, "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
PYEOF
    exit 1
fi

# ── 调用 baseline-manager.py --diff（修复 BUG-002）────────────
LOG_FILE="${OUTPUT_FILE%.json}.log"

DIFF_ARGS=(
    "--output-dir" "${BASELINE_DIR}"
    "--region" "${REGION}"
    "--diff"
)
if [[ -n "${RESOURCE_GROUP_ID}" ]]; then
    DIFF_ARGS+=("--resource-group-id" "${RESOURCE_GROUP_ID}")
fi
if [[ -n "${COMPARE_WITH}" ]]; then
    DIFF_ARGS+=("--compare-with" "${COMPARE_WITH}")
fi

set +e
python3 "${TOPO_DIR}/baseline-manager.py" "${DIFF_ARGS[@]}" 2>&1 | tee "${LOG_FILE}" | sed 's/^/  /'
rc=${PIPESTATUS[0]}
set -e

# ── 解析 log 提取漂移项并写 JSON 报告 ──
python3 - "${LOG_FILE}" "${OUTPUT_FILE}" "${BASELINE_DIR}" "${REGION}" "${RESOURCE_GROUP_ID}" "${rc}" "${COMPARE_WITH}" <<'PYEOF'
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

log_file, output_file, baseline_dir, region, rg_id, rc_str, compare_with = sys.argv[1:8]
rc = int(rc_str)

drift_items = []
status = "completed"
note = None
compared_with = compare_with or "latest"

try:
    log_text = Path(log_file).read_text()
except FileNotFoundError:
    log_text = ""

if rc != 0:
    status = "failed"
    note = f"baseline-manager.py exit={rc}"
elif "No previous baseline found" in log_text:
    note = "first run, no previous baseline to diff against"
elif "No drift detected" in log_text:
    note = "no drift detected"

# Try to extract the "vs <label>" token from baseline-manager stdout
m_vs = re.search(r"\(vs ([^)]+)\)", log_text)
if m_vs:
    compared_with = m_vs.group(1).strip()

for line in log_text.splitlines():
    m = re.match(r"\s*\[(ADDED|REMOVED)\]\s+(.+)", line)
    if m:
        drift_items.append({"type": m.group(1).lower(), "detail": m.group(2).strip()})

report = {
    "agent": "configdrift",
    "status": status,
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "region": region,
    "resource_group_id": rg_id or None,
    "baseline_dir": baseline_dir,
    "compared_with": compared_with,
    "drift_count": len(drift_items),
    "drift_items": drift_items,
    "log_file": log_file,
}
if note:
    report["note"] = note

with open(output_file, "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
PYEOF

# ── 输出总结 ──
drift_count=$(python3 -c "import json; print(json.load(open('${OUTPUT_FILE}'))['drift_count'])")
if [[ $rc -eq 0 ]]; then
    if [[ "$drift_count" -eq 0 ]]; then
        echo ""
        echo "[ConfigDrift] 漂移检测完成 (无漂移)"
    else
        echo ""
        echo "[ConfigDrift] 漂移检测完成 (发现 ${drift_count} 项漂移)"
    fi
    echo "[ConfigDrift] 报告: ${OUTPUT_FILE}"
else
    echo ""
    echo "[ConfigDrift] 漂移检测失败 (exit=$rc)"
    echo "[ConfigDrift] 报告: ${OUTPUT_FILE}"
    exit $rc
fi
