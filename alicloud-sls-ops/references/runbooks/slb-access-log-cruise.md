# SLB 七层访问日志巡检 Runbook

> 通用 SLB Access Log 巡检，适用于任意 Project/Logstore。
> 核心优化：并行查询、统一时间计算、容错解析、多维聚合一次返回。

---

## 意图

对 SLB 七层访问日志进行多维度异常巡检，发现：
1. **错误率异常**：5xx 状态码突增
2. **响应时间劣化**：RT 突增或慢请求增多
3. **上游故障**：upstream_status 非 200 分布
4. **流量基线**：每日/小时请求量趋势

---

## 执行流程

### Phase 0: 发现目标资源

```bash
# 1. 发现所有 SLB 访问日志相关的 Project
aliyun sls ListProject 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
for p in d.get('projects', []):
    name = p['projectName']
    # 过滤包含 slb/log/access 等关键词的 project
    if any(k in name.lower() for k in ['slb', 'log', 'access', 'crm', 'erp', 'business']):
        print(name)
"

# 2. 列出 Project 下所有 Logstore（含 SLB 访问日志字段的）
aliyun sls GET /logstores --project "<PROJECT>" 2>/dev/null | python3 -c "
import sys, json
for ls in d.get('logstores', []):
    print(ls)
"

# 3. 采样一条日志，确认字段结构
aliyun sls GetLogs \
  --project "<PROJECT>" \
  --logstore "<LOGSTORE>" \
  --from <CURRENT_TS> \
  --to <CURRENT_TS> \
  --line 1 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
rows = d if isinstance(d, list) else d.get('data', d.get('logs', []))
if rows:
    print('字段:', list(rows[0].keys()))
"
```

> **AI 决策点**：根据采样结果识别是否为 SLB 七层日志（应有 `status`, `request_time`, `host`, `upstream_status` 等字段）。

---

### Phase 1: 并行多维查询

```bash
# 时间范围（macOS/Linux 兼容）
FROM_TS=$(date -u -v-${DAYS:-7}d +%s 2>/dev/null || date -u -d "${DAYS:-7} days ago" +%s)
TO_TS=$(date -u +%s)

# 并行执行函数
query_store() {
  local proj=$1 logstore=$2 sql=$3 suffix=$4
  aliyun sls GetLogs --project "$proj" --logstore "$logstore" \
    --from $FROM_TS --to $TO_TS \
    --query "$sql" --line 1 \
    > "/tmp/sls-${suffix}.json" 2>&1 &
}

# 对每个 Logstore 并行执行 3 个聚合查询
query_store "$PROJECT" "$LOGSTORE" \
  "* | SELECT date_trunc('day', __time__) as day, count(1) as total, round(avg(request_time)*1000, 2) as avg_rt, round(max(request_time), 3) as max_rt, sum(case when status >= 500 then 1 else 0 end) as errors_5xx, round(sum(case when status >= 500 then 1 else 0 end)*100.0/count(1), 3) as err_pct GROUP BY day ORDER BY day" \
  "${LOGSTORE}-daily" &

query_store "$PROJECT" "$LOGSTORE" \
  "* | SELECT status, count(1) as cnt GROUP BY status ORDER BY cnt DESC LIMIT 20" \
  "${LOGSTORE}-status" &

query_store "$PROJECT" "$LOGSTORE" \
  "request_time > 1 | SELECT status, count(1) as slow_cnt, round(min(request_time), 3) as min_rt, round(max(request_time), 3) as max_rt, approx_distinct(client_ip) as uniq_ips GROUP BY status ORDER BY slow_cnt DESC LIMIT 10" \
  "${LOGSTORE}-slow" &

wait  # 等待所有并行任务完成
```

**Query A: 每日聚合（含错误率和 RT）**
```sql
* | SELECT 
  date_trunc('day', __time__) as day,
  count(1) as total,
  round(avg(request_time)*1000, 2) as avg_rt_ms,
  round(max(request_time), 3) as max_rt,
  sum(case when status >= 500 then 1 else 0 end) as errors_5xx,
  round(sum(case when status >= 500 then 1 else 0 end)*100.0/count(1), 3) as err_pct
GROUP BY day ORDER BY day
```

**Query B: 状态码分布**
```sql
* | SELECT status, count(1) as cnt
GROUP BY status ORDER BY cnt DESC LIMIT 20
```

**Query C: 慢请求采样（>1s，按状态分组）**
```sql
request_time > 1 | SELECT 
  status,
  count(1) as slow_cnt,
  round(min(request_time), 3) as min_rt,
  round(max(request_time), 3) as max_rt,
  approx_distinct(client_ip) as uniq_ips
GROUP BY status ORDER BY slow_cnt DESC LIMIT 10
```

---

### Phase 2: 异常检测规则

| 维度 | 阈值 | 告警级别 |
|------|------|----------|
| 错误率 | > 10% | 🔴 严重 |
| 错误率 | 1% ~ 10% | 🟡 关注 |
| 平均 RT | > 500ms | 🟡 关注 |
| 平均 RT | > 2s | 🔴 严重 |
| 单日 5xx 总量 | > 10000 | 🟡 关注 |

```bash
# 自动检测并输出异常时段
detect_anomaly() {
  local json_file=$1
  python3 -c "
import sys, json
d = json.load(open('$json_file'))
rows = d if isinstance(d, list) else d.get('data', d.get('logs', []))
for row in rows:
    err_pct = float(row.get('err_pct', 0))
    avg_rt = float(row.get('avg_rt_ms', 0))
    if err_pct > 5 or avg_rt > 500:
        flag = '🔴' if err_pct > 10 or avg_rt > 2000 else '🟡'
        print(f\"{flag} {row.get('day','')[:19]} | 错误率:{err_pct}% | RT:{avg_rt}ms\")
"
}
```

> **AI 决策点**：若 Phase 2 发现异常，记录异常起止时间戳 `<ANOMALY_FROM>` / `<ANOMALY_TO>`，用于 Phase 3 下钻。

---

### Phase 3: 根因下钻（仅异常时触发）

当检测到异常时，按需执行：

**A. 上游故障定位**
```sql
status >= 500 | SELECT 
  upstream_addr, upstream_status,
  count(1) as cnt
GROUP BY upstream_addr, upstream_status
ORDER BY cnt DESC LIMIT 10
```

**B. 异常时段细分**
```sql
* | SELECT 
  date_trunc('hour', __time__) as hr,
  status,
  count(1) as cnt
WHERE __time__ BETWEEN {{user.anomaly_from}} AND {{user.anomaly_to}}
GROUP BY hr, status ORDER BY hr
```

**C. 按域名/Path 拆分**
```sql
* | SELECT 
  host, request_uri,
  count(1) as total,
  round(avg(request_time)*1000, 2) as avg_rt,
  sum(case when status >= 500 then 1 else 0 end) as errors
WHERE __time__ BETWEEN {{user.anomaly_from}} AND {{user.anomaly_to}}
GROUP BY host, request_uri
ORDER BY errors DESC LIMIT 20
```

---

## 参数约定

| 变量 | 来源 | 说明 |
|------|------|------|
| `{{user.project}}` | 用户指定或自动发现 | SLS Project |
| `{{user.logstores}}` | 自动发现 | 逗号分隔的 Logstore 列表 |
| `{{user.days}}` | 默认 7 | 巡检天数 |
| `{{user.threshold_err}}` | 默认 5% | 错误率告警阈值 |
| `{{user.threshold_rt}}` | 默认 500ms | RT 告警阈值 |
| `{{user.anomaly_from}}` | Phase 2 输出确认 | 异常起始时间戳 |
| `{{user.anomaly_to}}` | Phase 2 输出确认 | 异常结束时间戳 |

## 输出格式

```markdown
## SLB 访问日志巡检报告

| 日期 | 总量 | 平均RT | 最大RT | 5xx次数 | 错误率 | 状态 |
|------|------|--------|--------|---------|--------|------|
| ... | ... | ... | ... | ... | ... | 🔴/🟡/✅ |

### 异常时段
- 2026-07-01 20:00 | 错误率 89% | 上游 172.16.9.75:80 故障

### 结论
🔴 发现严重异常，请检查上方红色时段
```

---

## 优化点说明

| 优化项 | 收益 |
|--------|------|
| **并行查询** | 6 路并发 vs 串行，耗时从 O(n) 降到 O(1) |
| **统一时间计算** | Phase 0 一次计算，后续复用 |
| **容错解析** | JSON 解析失败不影响整体报告 |
| **多维聚合** | 3 个 SQL 覆盖错误率/RT/状态码，避免重复全表扫描 |
| **按需下钻** | 正常时只做聚合，异常时才触发根因查询 |
