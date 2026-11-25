#!/usr/bin/env bash
# Big Key / Hot Key analysis for Alibaba Cloud Redis / Tair via Alibaba Cloud CLI (DAS API).
# Read-only analysis: no instance configuration or data is modified.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_ROOT/.." && pwd)"
DAS_WRAPPER="$REPO_ROOT/alicloud-das-ops/scripts/das-harness-wrapper.sh"

DAS_REGION="cn-shanghai"
DAS_ENDPOINT="${DAS_ENDPOINT:-das.cn-shanghai.aliyuncs.com}"
POLL_INTERVAL="${POLL_INTERVAL:-10}"
MAX_WAIT="${MAX_WAIT:-600}"

usage() {
  cat <<'EOF'
Usage:
  analyze-bigkeys-hotkeys.sh <InstanceId> [realtime|top|offline] [options]

Modes:
  realtime  DescribeHotBigKeys — current in-memory big/hot keys (default)
  top       DescribeTopBigKeys + DescribeTopHotKeys — history (<=4 days, window <=3h)
  offline   CreateCacheAnalysisJob + DescribeCacheAnalysisJob — full scan from backup

Options:
  --node-id <id>       Data shard id (optional)
  --start-ms <ms>      StartTime for top mode (Unix milliseconds)
  --end-ms <ms>        EndTime for top mode (Unix milliseconds)
  --region <region>    DAS service region (default: cn-shanghai)
  --endpoint <url>     DAS endpoint (default: das.cn-shanghai.aliyuncs.com)
  --poll-interval <s>  Offline poll interval (default: 10)
  --max-wait <s>       Offline max wait (default: 600)
  -h | --help          Show this help

Credentials are read from ALIBABA_CLOUD_ACCESS_KEY_ID / ALIBABA_CLOUD_ACCESS_KEY_SECRET.
EOF
}

[[ $# -ge 1 ]] || { usage >&2; exit 2; }
[[ "$1" == "-h" || "$1" == "--help" ]] && { usage; exit 0; }

INSTANCE_ID="$1"; shift
MODE="realtime"
if [[ $# -gt 0 && "$1" != --* ]]; then
  MODE="$1"; shift
fi
NODE_ID=""
START_MS=""
END_MS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --node-id)        NODE_ID="${2:?--node-id requires a value}"; shift 2 ;;
    --start-ms)       START_MS="${2:?--start-ms requires a value}"; shift 2 ;;
    --end-ms)         END_MS="${2:?--end-ms requires a value}"; shift 2 ;;
    --region)         DAS_REGION="${2:?--region requires a value}"; shift 2 ;;
    --endpoint)       DAS_ENDPOINT="${2:?--endpoint requires a value}"; shift 2 ;;
    --poll-interval)  POLL_INTERVAL="${2:?--poll-interval requires a value}"; shift 2 ;;
    --max-wait)       MAX_WAIT="${2:?--max-wait requires a value}"; shift 2 ;;
    -h|--help)        usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$MODE" in
  realtime|top|offline) ;;
  *) echo "Invalid mode: $MODE" >&2; usage >&2; exit 2 ;;
esac

command -v aliyun >/dev/null 2>&1 || { echo "ERROR: aliyun CLI not found" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found (needed for JSON normalization)" >&2; exit 1; }
[[ -n "${ALIBABA_CLOUD_ACCESS_KEY_ID:-}" && -n "${ALIBABA_CLOUD_ACCESS_KEY_SECRET:-}" ]] || {
  echo "ERROR: ALIBABA_CLOUD_ACCESS_KEY_ID / ALIBABA_CLOUD_ACCESS_KEY_SECRET must be set" >&2
  exit 1
}
if [[ "$MODE" == "top" ]]; then
  [[ -n "$START_MS" && -n "$END_MS" ]] || { echo "ERROR: top mode requires --start-ms and --end-ms" >&2; exit 2; }
fi

# DAS CLI: use the harness wrapper when available (self-repair + tracing), else native CLI.
# CamelCase API names work with the built-in CLI; kebab-case names require the aliyun-cli-das plugin.
das_call() {
  local api="$1"; shift
  if [[ -x "$DAS_WRAPPER" ]]; then
    "$DAS_WRAPPER" "$api" --RegionId "$DAS_REGION" --endpoint "$DAS_ENDPOINT" "$@"
  else
    aliyun das "$api" --RegionId "$DAS_REGION" --endpoint "$DAS_ENDPOINT" "$@"
  fi
}

das_call_node() {
  local api="$1"; shift
  if [[ -n "$NODE_ID" ]]; then
    das_call "$api" "$@" --NodeId "$NODE_ID"
  else
    das_call "$api" "$@"
  fi
}

raw_realtime=""
raw_top_big=""
raw_top_hot=""
raw_offline=""

case "$MODE" in
  realtime)
    raw_realtime="$(das_call_node DescribeHotBigKeys --InstanceId "$INSTANCE_ID")" || {
      echo "ERROR: DescribeHotBigKeys failed" >&2; exit 1; }
    ;;
  top)
    raw_top_big="$(das_call_node DescribeTopBigKeys --InstanceId "$INSTANCE_ID" --StartTime "$START_MS" --EndTime "$END_MS")" || {
      echo "ERROR: DescribeTopBigKeys failed" >&2; exit 1; }
    raw_top_hot="$(das_call_node DescribeTopHotKeys --InstanceId "$INSTANCE_ID" --StartTime "$START_MS" --EndTime "$END_MS")" || {
      echo "ERROR: DescribeTopHotKeys failed" >&2; exit 1; }
    ;;
  offline)
    raw_create="$(das_call_node CreateCacheAnalysisJob --InstanceId "$INSTANCE_ID")" || {
      echo "ERROR: CreateCacheAnalysisJob failed" >&2; exit 1; }
    JOB_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("Data",{}).get("JobId","") or "")' "$raw_create")" || {
      echo "ERROR: cannot parse JobId from CreateCacheAnalysisJob response" >&2; exit 1; }
    [[ -n "$JOB_ID" ]] || { echo "ERROR: JobId missing from CreateCacheAnalysisJob response" >&2; exit 1; }
    echo "[INFO] JobId=$JOB_ID" >&2
    waited=0
    while [[ $waited -le $MAX_WAIT ]]; do
      raw_offline="$(das_call DescribeCacheAnalysisJob --InstanceId "$INSTANCE_ID" --JobId "$JOB_ID")" || {
        echo "ERROR: DescribeCacheAnalysisJob failed" >&2; exit 1; }
      state="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("Data",{}).get("TaskState","") or "")' "$raw_offline")" || state=""
      echo "[INFO] TaskState=${state:-UNKNOWN} elapsed=${waited}s" >&2
      case "$state" in
        FINISHED|SUCCESS) break ;;
        FAILED)
          python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print("ERROR: job failed: " + str(d.get("Data",{}).get("Message", "")), file=sys.stderr)' "$raw_offline" || true
          exit 1 ;;
      esac
      sleep "$POLL_INTERVAL"
      waited=$((waited + POLL_INTERVAL))
    done
    if [[ $waited -gt $MAX_WAIT ]]; then
      echo "ERROR: job $JOB_ID did not finish within ${MAX_WAIT}s; query it later with DescribeCacheAnalysisJob" >&2
      exit 1
    fi
    ;;
esac

python3 - "$INSTANCE_ID" "$MODE" "$raw_realtime" "$raw_top_big" "$raw_top_hot" "$raw_offline" <<'PY'
import json, sys
from datetime import datetime, timezone

instance_id, mode, raw_rt, raw_big, raw_hot, raw_off = sys.argv[1:7]

def parse(raw):
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise SystemExit("ERROR: CLI response is not JSON: %s" % exc)
    if str(data.get("Code")) != "200" or str(data.get("Success")).lower() != "true":
        raise SystemExit("ERROR: DAS API failure: %s" % json.dumps(data, ensure_ascii=False)[:500])
    return data

def iso(ms):
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except Exception:
        return None

big_keys, hot_keys, requests = [], [], []

def record(data, api):
    if data:
        requests.append({"api": api, "request_id": data.get("RequestId")})

rt = parse(raw_rt)
record(rt, "DescribeHotBigKeys")
if rt:
    d = rt.get("Data") or {}
    for k in ((d.get("BigKeys") or {}).get("BigKey") or []):
        big_keys.append({"key": k.get("Key"), "type": k.get("KeyType"),
                         "elements": k.get("Size"), "db": k.get("Db"),
                         "node_id": k.get("NodeId"), "source": "realtime"})
    def add_hot(items, category=None):
        for k in items or []:
            hot_keys.append({"key": k.get("Key"), "type": k.get("KeyType"),
                             "qps": k.get("Hot"), "lfu": k.get("Lfu"),
                             "db": k.get("Db"), "node_id": k.get("NodeId"),
                             "category": category or k.get("Category") or "qps",
                             "source": "realtime"})
    add_hot((d.get("HotKeys") or {}).get("HotKey"))
    add_hot((d.get("HighTrafficKeys") or {}).get("HotKey"), "traffic")

tb = parse(raw_big)
record(tb, "DescribeTopBigKeys")
for k in ((tb or {}).get("Data", {}).get("BigKey") or []):
    big_keys.append({"key": k.get("Key"), "type": k.get("KeyType"),
                     "elements": k.get("Size"), "db": k.get("Db"),
                     "node_id": k.get("NodeId"), "source": "top"})

th = parse(raw_hot)
record(th, "DescribeTopHotKeys")
for k in ((th or {}).get("Data", {}).get("HotKey") or []):
    hot_keys.append({"key": k.get("Key"), "type": k.get("KeyType"),
                     "qps": k.get("Hot"), "lfu": k.get("Lfu"),
                     "db": k.get("Db"), "node_id": k.get("NodeId"),
                     "category": k.get("Category") or "qps",
                     "in_bytes": k.get("InBytes"), "out_bytes": k.get("OutBytes"),
                     "source": "top"})

off = parse(raw_off)
record(off, "DescribeCacheAnalysisJob")
if off:
    d = off.get("Data") or {}
    unavailable = {k: v for k, v in d.items() if k.endswith("Msg") and v}
    for section in ("BigKeys", "BigKeysOfNum", "UnexBigKeysOfBytes", "UnexBigKeysOfNum"):
        for k in ((d.get(section) or {}).get("KeyInfo") or []):
            big_keys.append({"key": k.get("Key"), "type": k.get("Type"),
                             "bytes": k.get("Bytes"), "elements": k.get("Count"),
                             "db": k.get("Db"), "encoding": k.get("Encoding"),
                             "expire_at": iso(k.get("ExpirationTimeMillis")),
                             "node_id": k.get("NodeId"), "source": section})
    if unavailable:
        requests.append({"unavailable_dimensions": unavailable})

def severity():
    max_bytes = max([k.get("bytes") or 0 for k in big_keys] or [0])
    max_elements = max([k.get("elements") or 0 for k in big_keys] or [0])
    if max_bytes >= 100 * 1024 or max_elements >= 50000:
        return "critical"
    if big_keys:
        return "warning"
    return "healthy"

def hot_severity():
    return "warning" if hot_keys else "healthy"

recommendations = []
if any((k.get("expire_at") is None and k.get("source") == "BigKeys") for k in big_keys):
    recommendations.append("存在无 TTL 的大 Key，建议评估设置过期时间（需用户确认具体 Key）")
if any((k.get("elements") or 0) >= 5000 for k in big_keys):
    recommendations.append("大 Key 元素数量较多，建议按业务维度拆分并避免 HGETALL/SMEMBERS 全量读取")
if hot_keys:
    recommendations.append("热 Key QPS 超过 3000，建议本地缓存、读写分离或 Key 打散；不要自动执行删除/配置变更")

result = {
    "analysis_type": "bigkey_hotkey",
    "resource_type": "redis",
    "resource_id": instance_id,
    "source": {"realtime": "DescribeHotBigKeys", "top": "DescribeTopBigKeys/DescribeTopHotKeys",
               "offline": "CreateCacheAnalysisJob/DescribeCacheAnalysisJob"}[mode],
    "analysis_time": datetime.now(tz=timezone.utc).isoformat(),
    "dimensions": [
        {"name": "大Key", "status": severity(), "count": len(big_keys)},
        {"name": "热Key", "status": hot_severity(), "count": len(hot_keys)},
    ],
    "big_keys": big_keys,
    "hot_keys": hot_keys,
    "requests": requests,
    "recommendations": recommendations,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
PY
