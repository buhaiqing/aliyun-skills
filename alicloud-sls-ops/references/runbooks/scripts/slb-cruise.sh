#!/usr/bin/env bash
#===============================================================================
# SLB 七层访问日志巡检 - 并行优化版
# 通用模板，不绑定具体 Project/Logstore，AI 根据上下文适配
#===============================================================================
set -euo pipefail

#-------------------------------------------------------------------------------
# 参数解析（可被 AI 通过环境变量覆盖）
#-------------------------------------------------------------------------------
DAYS="${DAYS:-7}"
PROJECT="${SLS_PROJECT:-}"
STORES="${SLS_STORES:-}"          # 逗号分隔，AI 发现后填充
THRESH_ERR="${THRESH_ERR:-5}"    # 错误率阈值 %
THRESH_RT="${THRESH_RT:-500}"     # RT 阈值 ms

# 临时目录（自动清理）
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

#-------------------------------------------------------------------------------
# Phase 0: 时间计算（macOS/Linux 兼容）
#-------------------------------------------------------------------------------
FROM_TS=$(date -u -v-${DAYS}d +%s 2>/dev/null || date -u -d "${DAYS} days ago" +%s)
TO_TS=$(date -u +%s)
FROM_HUMAN=$(date -u -r $FROM_TS "+%Y-%m-%d %H:%M:%S")
TO_HUMAN=$(date -u -r $TO_TS "+%Y-%m-%d %H:%M:%S")

echo "[PREP] 时间范围: $FROM_HUMAN ~ $TO_HUMAN ($DAYS 天)"
echo "[PREP] Project: ${PROJECT:-未指定，将自动发现}"

#-------------------------------------------------------------------------------
# Phase 0.5: 自动发现目标（PROJECT/STORES 未指定时）
#-------------------------------------------------------------------------------
discover_targets() {
  echo "[DISCOVER] 扫描 SLS Projects..."
  
  if [[ -z "$PROJECT" ]]; then
    # 发现包含 slb/log/access 关键词的 project
    PROJECT=$(aliyun sls ListProject 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
for p in d.get('projects', []):
    name = p['projectName']
    # 扩展匹配关键词
    if any(k in name.lower() for k in ['slb', 'log', 'access', 'http']):
        print(name)
" | head -1)
  fi
  
  if [[ -z "$PROJECT" ]] || [[ "$PROJECT" == "None" ]]; then
    echo "[ERROR] 无法自动发现 SLB 日志 Project，请设置 SLS_PROJECT"
    exit 1
  fi
  
  echo "[DISCOVER] 使用 Project: $PROJECT"
  
  if [[ -z "$STORES" ]]; then
    # 列出所有 logstore，采样确认是否为 SLB 访问日志
    STORES=$(aliyun sls GET /logstores --project "$PROJECT" 2>/dev/null | python3 -c "
import sys, json, subprocess
d = json.load(sys.stdin)
stores = d.get('logstores', [])
print(','.join(stores))
")
  fi
  
  echo "[DISCOVER] Logstores: $STORES"
}

discover_targets

#-------------------------------------------------------------------------------
# Phase 1: SQL 模板（SLB 七层访问日志特征字段）
#-------------------------------------------------------------------------------
# 每日聚合
SQL_DAILY='* | SELECT 
  date_trunc('\''day'\'', __time__) as day,
  count(1) as total,
  round(avg(request_time)*1000, 2) as avg_rt,
  round(max(request_time), 3) as max_rt,
  sum(case when status >= 500 then 1 else 0 end) as errors_5xx,
  round(sum(case when status >= 500 then 1 else 0 end)*100.0/count(1), 3) as err_pct
GROUP BY day ORDER BY day'

# 状态码分布
SQL_STATUS='* | SELECT status, count(1) as cnt
GROUP BY status ORDER BY cnt DESC LIMIT 20'

# 慢请求采样
SQL_SLOW='request_time > 1 | SELECT 
  status,
  count(1) as slow_cnt,
  round(min(request_time), 3) as min_rt,
  round(max(request_time), 3) as max_rt,
  approx_distinct(client_ip) as uniq_ips
GROUP BY status ORDER BY slow_cnt DESC LIMIT 10'

#-------------------------------------------------------------------------------
# Phase 2: 并行查询
#-------------------------------------------------------------------------------
echo "[PHASE1] 并行查询 $STORES..."

run_query() {
  local proj=$1 store=$2 sql=$3 out=$4
  aliyun sls GetLogs \
    --project "$proj" \
    --logstore "$store" \
    --from $FROM_TS --to $TO_TS \
    --query "$sql" --line 1 \
    > "$out" 2>&1 &
  echo $!
}

PIDS=()

for STORE in $(echo "$STORES" | tr ',' ' '); do
  run_query "$PROJECT" "$STORE" "$SQL_DAILY"  "$TMP_DIR/${STORE}-daily.json" &
  PIDS+=($!)
  run_query "$PROJECT" "$STORE" "$SQL_STATUS" "$TMP_DIR/${STORE}-status.json" &
  PIDS+=($!)
  run_query "$PROJECT" "$STORE" "$SQL_SLOW"   "$TMP_DIR/${STORE}-slow.json" &
  PIDS+=($!)
done

echo "[PHASE1] 等待 ${#PIDS[@]} 个并行任务..."
for pid in "${PIDS[@]}"; do
  wait $pid 2>/dev/null || true
done

#-------------------------------------------------------------------------------
# Phase 3: 解析与报告
#-------------------------------------------------------------------------------
echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║  SLB 访问日志巡检报告  |  $FROM_HUMAN ~ $TO_HUMAN        ║"
echo "╚════════════════════════════════════════════════════════════════════╝"

parse_json() {
  local f=$1
  [[ -s "$f" ]] && python3 -c "
import sys, json
try:
    d = json.load(open('$f'))
    rows = d if isinstance(d, list) else d.get('data', d.get('logs', []))
    for r in rows: print(json.dumps(r))
except: pass
" 2>/dev/null
}

detect_anomaly() {
  local name=$1 file=$2 ret=0
  local max_err=$(parse_json "$file" | python3 -c "
import sys, json
max_e = 0.0
for line in sys.stdin:
    try:
        r = json.loads(line.strip())
        e = float(r.get('err_pct', 0))
        if e > max_e: max_e = e
    except: pass
print(round(max_e, 2))
" 2>/dev/null)
  
  local flag="✅"
  # Fix: use [[ ]] instead of (( )) to avoid set -e exit on 0 comparison
  if [[ $(echo "$max_err > $THRESH_ERR * 2" | bc -l 2>/dev/null || echo 0) == 1 ]]; then
    flag="🔴"; ret=2
  elif [[ $(echo "$max_err > $THRESH_ERR" | bc -l 2>/dev/null || echo 0) == 1 ]]; then
    flag="🟡"; ret=1
  fi
  echo "$flag [$name] 错误率: ${max_err}% (阈值: ${THRESH_ERR}%)"
  return $ret
}

# 输出每个 Logstore 的结果
echo ""
for STORE in $(echo "$STORES" | tr ',' ' '); do
  echo "━━━ $STORE ━━━"
  
  # 每日统计
  echo ""
  echo "  每日趋势:"
  parse_json "$TMP_DIR/${STORE}-daily.json" | python3 -c "
import sys, json
print('  日期                 总量           平均RT     最大RT       5xx        错误率')
print('  ' + '-'*70)
for line in sys.stdin:
    try:
        r = json.loads(line.strip())
        day = r.get('day','')[:19]
        total = int(float(r.get('total',0)))
        avg_rt = r.get('avg_rt','-')
        max_rt = r.get('max_rt','-')
        err5 = int(float(r.get('errors_5xx',0)))
        err_pct = r.get('err_pct','0')
        flag = '🔴' if float(err_pct)>10 else '🟡' if float(err_pct)>1 else ' '
        print(f'  {day}  {total:>10,}  {avg_rt:>7}ms  {max_rt:>8}s  {err5:>9,}  {err_pct:>6}%  {flag}')
    except: pass
"
  
  # 状态码 Top 5
  echo ""
  echo "  状态码 Top 5:"
  parse_json "$TMP_DIR/${STORE}-status.json" | head -5 | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        r = json.loads(line.strip())
        s = r.get('status','-')
        c = int(float(r.get('cnt',0)))
        flag = '🔴' if str(s).startswith('5') else '🟡' if str(s).startswith('4') else ''
        print(f'    {s:>5}: {c:>12,}  {flag}')
    except: pass
"
  
  # 异常检测
  detect_anomaly "$STORE" "$TMP_DIR/${STORE}-daily.json"
done

echo ""
echo "[DONE] 巡检完成"
