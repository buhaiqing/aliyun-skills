#!/usr/bin/env bash
#
# fusion/fusion_report.sh — AIOps 融合报告层 (C1)
# 读取 perceive Agent 的 JSON 输出, 归一化异构 findings 为统一 schema, 去重后融合。
#
# 统一 schema: {domain, severity, resource_id, resource_type, description,
#               source_agent, timestamp, dedup_count}
# severity 归一化: CRITICAL/ERROR/HIGH/MEDIUM/WARNING/LOW/INFO
#
# 用法:
#   bash fusion_report.sh --input-dir <dir> [--output-file <path>]
#   bash fusion_report.sh --describe

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOPS_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
export SKILLS_DIR="$(cd "${AIOPS_DIR}/.." && pwd)"
source "${AIOPS_DIR}/scripts/lib/runtime_root.sh"
aiops_runtime_init "alicloud-aiops-cruise"

INPUT_DIR="" OUTPUT_FILE="" DESCRIBE=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --input-dir) INPUT_DIR="$2"; shift 2 ;;
        --output-file) OUTPUT_FILE="$2"; shift 2 ;;
        --describe) DESCRIBE=true; shift ;;
        *) echo "[ERROR] 未知参数: $1"; exit 2 ;;
    esac
done

if $DESCRIBE; then
    cat <<'STRUCTURE'
Fusion Report Layer (C1) — 融合 perceive 层 findings
  输入: perceive-{ts}/ 下所有 Agent JSON
  输出: fusion-report-{ts}.json
  字段: domain, severity, resource_id, resource_type, description, source_agent, timestamp, dedup_count
STRUCTURE
    exit 0
fi

[[ -z "$INPUT_DIR" ]] && echo "[ERROR] --input-dir 必填" && exit 2
[[ ! -d "$INPUT_DIR" ]] && echo "[ERROR] 目录不存在: ${INPUT_DIR}" && exit 2

TIMESTAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
[[ -z "$OUTPUT_FILE" ]] && OUTPUT_FILE="${INPUT_DIR}/fusion-report-${TIMESTAMP}.json"
mkdir -p "$(dirname "${OUTPUT_FILE}")"

# ── 遍历所有 JSON, 按 agent 类型提取 findings (jq -> json-lines) ──
echo "[Fusion] 开始融合: input=${INPUT_DIR}"

for json_file in "${INPUT_DIR}"/*.json; do
    [[ -f "$json_file" ]] || continue
    base_name="$(basename "$json_file" .json)"
    [[ "$base_name" == fusion-report-* || "$base_name" == "perceive-summary" ]] && continue

    agent_name="$(jq -r '.agent // ""' "$json_file" 2>/dev/null || true)"
    [[ -z "$agent_name" ]] && agent_name="$base_name"

    ts="$(jq -r '.timestamp // ""' "$json_file")"

    case "$agent_name" in
        healthcruise)
            jq -c '.findings[]? // .checks[]? // .results[]? // empty | {domain:"infra", severity:(.severity // .status // "INFO" | ascii_upcase), resource_id:(.resource_id // .instance_id // .id // ""), resource_type:(.resource_type // .type // .category // ""), description:(.message // .description // .summary // .check // .name // .issue // ""), source_agent:"healthcruise", timestamp:$ts}' --arg ts "$ts" "$json_file" 2>/dev/null || true
            ;;
        toposcan)
            jq -c '.resources[]? // .nodes[]? | {domain:"infra", severity:"INFO", resource_id:(.instance_id // .resource_id // .id // .name // ""), resource_type:(.resource_type // .type // .category // ""), description:("topology: " + (.instance_id // .resource_id // .id // .name // "unknown")), source_agent:"toposcan", timestamp:$ts}' --arg ts "$ts" "$json_file" 2>/dev/null || true
            ;;
        configdrift)
            jq -c '.drift_items[]? | {domain:"infra", severity:"MEDIUM", resource_id:"", resource_type:"config", description:("配置漂移: " + (.type // "unknown") + " " + (.detail // "")), source_agent:"configdrift", timestamp:$ts}' --arg ts "$ts" "$json_file" 2>/dev/null || true
            ;;
        costwatch)
            jq -c '.anomalies[]?, .expiring_resources[]?, .alerts[]?, .findings[]? | {domain:"cost", severity:(.severity // "MEDIUM" | ascii_upcase), resource_id:(.resource_id // .instance_id // .id // .service // ""), resource_type:(.resource_type // .type // .product // ""), description:(.message // .description // .alert // .name // ""), source_agent:"costwatch", timestamp:$ts}' --arg ts "$ts" "$json_file" 2>/dev/null || true
            ;;
        securityscan)
            jq -c '.vulnerabilities[]?, .findings[]?, .issues[]?, .scan_results[]? | {domain:"security", severity:(.severity // "HIGH" | ascii_upcase), resource_id:(.resource_id // .instance_id // .id // .name // ""), resource_type:(.resource_type // .type // .product // ""), description:(.message // .description // .title // .issue // .name // ""), source_agent:"securityscan", timestamp:$ts}' --arg ts "$ts" "$json_file" 2>/dev/null || true
            ;;
        audittrail)
            jq -c '.events[]?, .anomalies[]?, .findings[]? | {domain:"security", severity:(.severity // "MEDIUM" | ascii_upcase), resource_id:(.resource_id // .instance_id // .id // .event_name // ""), resource_type:(.resource_type // .type // .service // ""), description:(.message // .description // .event // .name // ""), source_agent:"audittrail", timestamp:$ts}' --arg ts "$ts" "$json_file" 2>/dev/null || true
            ;;
        advisorscan)
            jq -c '.health_checks.Advices[]? // .health_checks[]? | select(type=="object") | {domain:"advisor", severity:(.severity // "INFO" | ascii_upcase), resource_id:(.ResourceId // .resource_id // .id // ""), resource_type:(.Product // .resource_type // ""), description:(.Description // .detail // .title // .name // .AdviceCode // ""), source_agent:"advisorscan", timestamp:$ts}' --arg ts "$ts" "$json_file" 2>/dev/null || true
            jq -c '.cost_optimization.Advices[]? // .cost_optimization[]? | select(type=="object") | {domain:"advisor", severity:"MEDIUM", resource_id:(.ResourceId // .resource_id // .id // ""), resource_type:(.Product // .resource_type // ""), description:(.Description // .detail // .title // .name // .AdviceCode // ""), source_agent:"advisorscan", timestamp:$ts}' --arg ts "$ts" "$json_file" 2>/dev/null || true
            ;;
        *)
            echo "[Fusion]   [SKIP] ${json_file} (未知 agent: ${agent_name})"
            continue
            ;;
    esac
    echo "[Fusion]   处理: ${json_file} (agent=${agent_name})"
done > "${OUTPUT_FILE}.tmp.lines"

# ── 归一化严重性 + 聚合去重 ──
echo "[Fusion] 归一化 & 去重..."
python3 - "${OUTPUT_FILE}.tmp.lines" "${OUTPUT_FILE}" <<'PYEOF'
import json, sys
from collections import defaultdict
from datetime import datetime, timezone

SEV_MAP = {"CRITICAL":0,"CRITICAL_ERROR":0,"P0":0,"P1":0,"HIGH":1,"ERROR":1,"FAIL":1,"FAILED":1,"FAILURE":1,"P2":1,"MEDIUM":2,"WARN":2,"WARNING":2,"P3":2,"LOW":3,"P4":3,"P5":3,"INFO":4,"OK":4,"SUCCESS":4,"PASS":4,"COMPLETED":4}
SEV_LABELS = ["CRITICAL","HIGH","MEDIUM","LOW","INFO"]

lines_file, output_file = sys.argv[1], sys.argv[2]
findings = []
try:
    for line in open(lines_file):
        line = line.strip()
        if not line: continue
        try:
            rec = json.loads(line)
            if not rec.get("description"): continue
            sev_idx = SEV_MAP.get(rec.get("severity","LOW").upper(), 3)
            rec["severity"] = SEV_LABELS[sev_idx]
            rec.setdefault("domain","infra"); rec.setdefault("resource_id","")
            rec.setdefault("resource_type",""); rec.setdefault("source_agent","unknown")
            rec.setdefault("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
            findings.append(rec)
        except json.JSONDecodeError: continue
except FileNotFoundError: pass

groups = defaultdict(list)
for f in findings:
    groups[f"{f['resource_id']}|{f['description']}"].append(f)

merged = []
for key, group in groups.items():
    best = min(group, key=lambda x: SEV_MAP.get(x["severity"], 99))
    best["dedup_count"] = len(group)
    best["source_agent"] = ",".join(sorted(set(f["source_agent"] for f in group)))
    merged.append(best)

merged.sort(key=lambda x: (SEV_MAP.get(x["severity"], 99), x.get("timestamp","")))
report = {"pipeline":"fusion","version":"1.0.0","timestamp":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),"input_dir":lines_file.replace(".tmp.lines",""),"total_findings_raw":len(findings),"total_findings_deduped":len(merged),"findings":merged}
with open(output_file,"w") as f: json.dump(report,f,indent=2,ensure_ascii=False)
PYEOF

rm -f "${OUTPUT_FILE}.tmp.lines"

TOTAL="$(jq '.total_findings_raw // 0' "$OUTPUT_FILE")"
DEDUPED="$(jq '.total_findings_deduped // 0' "$OUTPUT_FILE")"
SEVERITY_BREAKDOWN="$(jq -r '[.findings|group_by(.severity)[]|{sev:.[0].severity,count:length}]|sort_by(.sev)|map("\(.sev): \(.count)")|join(", ")' "$OUTPUT_FILE")"
echo ""; echo "[Fusion] PASS 融合报告生成完成"
echo "[Fusion]   输出: ${OUTPUT_FILE}"
echo "[Fusion]   原始 findings: ${TOTAL}, 去重后: ${DEDUPED}"
echo "[Fusion]   严重性分布: ${SEVERITY_BREAKDOWN}"