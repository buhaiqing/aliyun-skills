---
runbook_id: "05"
scenario: "慢查询诊断与治理"
version: "1.0.0"
last_updated: "2026-06-07"
trigger: "CMS告警（慢查询突增 / RDS CPU > 75%）/ DAS 评分 < 60 / 人工触发"
risk_level: "中"
execution_time_estimate: "5-15 分钟（10 个 RDS 以内）"
---

> **脚本**: [`runbooks/scripts/slow-query-diagnosis.py`](scripts/slow-query-diagnosis.py) — 全自动执行本 runbook

# 慢查询诊断与治理

## 1. 场景描述

对指定客户（通过资源组/标签识别）的 RDS/PolarDB/MySQL 实例进行慢查询诊断。包含：慢 SQL 检索与根因分析、性能洞察（等待事件/TOP SQL）、会话管理（活跃连接/锁等待）、SQL 限流/并发控制建议、空间分析与自治事件回溯。

### [ALERT] 安全铁律

| 红线 | 要求 |
|---|---|
| **任何资源的删除/停止/规格变更** | FAIL 不允许自动执行，报告只出建议 |
| **输出 AK/SK** | FAIL 必须掩码为 `AKID****SKRET` |
| **安全组规则增删** | FAIL 不允许自动执行 |
| **Kill 会话** | WARNING 仅 Kill 空闲/睡眠连接，活跃事务 Kill 需确认 |
| **SQL 限流** | CRITICAL 仅出建议，不自动执行 |

**底线**：本 runbook 是纯读（Read-Only）诊断 + WARNING 白名单内有限操作。SQL 限流和 Kill 活跃事务需用户确认后通过 `alicloud-das-ops` 执行。

### [NOTE] 提示知识力

> **慢查询诊断的核心思路**：
>
> 慢查询的根因通常只有几种，按概率排序：
> 1. **索引缺失**（>60% 的慢查询根因）—— SQL 执行计划出现 `Using filesort` / `Using temporary`
> 2. **扫描行数过多** —— 无 WHERE 或 WHERE 无索引，全表扫描
> 3. **锁等待** —— 行锁/间隙锁竞争，`show processlist` 出现 `Waiting for table metadata lock`
> 4. **CPU/IO 资源瓶颈** —— 数据库规格不够，请求排队
> 5. **数据量膨胀** —— 表数据大到索引失效
>
> **诊断顺序**：先查 CMS 指标（CPU/连接/IOPS 确定异常窗口）-> 再查 DAS 慢 SQL（定位具体 SQL）-> 分析执行计划 -> 出修复建议。
>
> **DAS 与 CMS 的关系**：CMS 告诉你"有没有问题"，DAS 告诉你"哪里有问题"。

### 适用条件

- 资源已按 `客户` 标签或资源组归类
- 阿里云 AK/SK 已配置且有 CMS 只读 + DAS 只读权限
- 支持：RDS MySQL / PolarDB MySQL / PolarDB PostgreSQL
- 目标实例已开启 DAS Pro 或 SQL Audit（慢查询功能）

### 不适用条件

- SQL Server / MariaDB 实例（DAS API 不完全兼容）
- 未开启 SQL 审计日志的实例（无法获取慢 SQL 明细）
- 需要修改数据库配置 -> 通过 `alicloud-das-ops` 执行

---

## 2. 执行流程

### Phase 0: 前置安全门

```bash
# 1. 凭据预检
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" || { echo "[ERROR] AK_ID 未设置"; exit 1; }
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" || { echo "[ERROR] AK_SK 未设置"; exit 1; }

# 2. CLI + 工具可用性检查
command -v aliyun >/dev/null 2>&1 || { echo "[ERROR] aliyun CLI 未安装"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "[ERROR] jq 未安装"; exit 1; }
command -v go >/dev/null 2>&1 || { echo "[WARN] go 未安装 — DAS 深度诊断（JIT Go SDK）不可用"; }

# 3. API 连通性检查
aliyun rds DescribeRegions --RegionId "$REGION" >/dev/null 2>&1 \
  || { echo "[ERROR] RDS API 连通性检查失败"; exit 1; }

# 4. 确认诊断范围
CUSTOMER="{{user.customer_name}}"
REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
echo "[INFO] 客户: $CUSTOMER | 区域: $REGION"
```

### Phase 1: 拓扑发现 — 数据库实例扫描

> **核心思路**：扫描指定资源组/标签下的所有 RDS/PolarDB 实例，结合 CMS 指标快速筛选"可疑实例"（CPU > 50% / 连接数 > 60% / 慢查询 > 0），只对可疑实例进入深度诊断，避免全量扫描。

#### Step 1.1: 数据库实例列表扫描

```bash
# 用户输入
RG_ID="{{user.resource_group_id}}"        # 可选
TAG_KEY="{{user.tag_key}}"                # 可选
TAG_VALUE="{{user.tag_value}}"            # 可选

# ── 扫描 RDS 实例 ──
if [ -n "$RG_ID" ]; then
  RDS_INSTANCES=$(aliyun rds DescribeDBInstances --RegionId "$REGION" \
    --ResourceGroupId "$RG_ID" --PageSize 100 | jq '.Items.DBInstance')
elif [ -n "$TAG_KEY" ]; then
  RDS_INSTANCES=$(aliyun rds DescribeDBInstances --RegionId "$REGION" \
    --Tag.1.Key "$TAG_KEY" --Tag.1.Value "$TAG_VALUE" --PageSize 100 | jq '.Items.DBInstance')
else
  echo "[ERROR] 必须提供资源组ID或标签"; exit 1
fi

# ── 扫描 PolarDB 实例 ──
POLARDB_INSTANCES=$(aliyun polardb DescribeDBClusters --RegionId "$REGION" \
  --PageSize 100 | jq --arg rg "$RG_ID" '[.Items.DBCluster[] // select(.ResourceGroupId == $rg)]')

RDS_COUNT=$(echo "$RDS_INSTANCES" | jq 'length')
POLARDB_COUNT=$(echo "$POLARDB_INSTANCES" | jq 'length')
echo "[INFO] 扫描到 RDS: $RDS_COUNT 个, PolarDB: $POLARDB_COUNT 个"
```

#### Step 1.2: CMS 指标初筛 — 筛选可疑实例

```bash
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START_TIME=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)

SUSPECT_RDS="[]"  # 存可疑实例列表

for DB_ID in $(echo "$RDS_INSTANCES" | jq -r '.[].DBInstanceId // empty'); do
  # CPU 使用率
  RDS_CPU=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName CpuUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | max // 0')

  # 慢查询数
  SLOW_QUERY=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName SlowQueryCount \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  echo "[DIAG] RDS $DB_ID: CPU=${RDS_CPU}%, 慢查询=${SLOW_QUERY}/min"

  # 标记可疑：CPU > 50% 或 慢查询 > 5/min
  if [ "$(echo "$RDS_CPU > 50" | bc -l 2>/dev/null)" = "1" ] || \
     [ "$(echo "$SLOW_QUERY > 5" | bc -l 2>/dev/null)" = "1" ]; then
    SUSPECT_RDS=$(echo "$SUSPECT_RDS" | jq --arg id "$DB_ID" '. + [$id]')
    echo "  -> 标记为可疑实例"
  fi
done

SUSPECT_COUNT=$(echo "$SUSPECT_RDS" | jq 'length')
echo "[INFO] 可疑实例: $SUSPECT_COUNT 个"
```

### Phase 2: 深度诊断

> **核心思路**：对每个可疑实例，联动 CMS + DAS（JIT Go SDK）做四维诊断：
> 1. 慢 SQL 明细（DAS：SQL 样本 + 执行次数 + 平均耗时 + 扫描行数）
> 2. 性能洞察（DAS Pro：等待事件 / TOP SQL 时间线）
> 3. 会话分析（活跃连接 / 锁等待 / 空闲连接占比）
> 4. 空间分析（磁盘构成 / 最大表 TOP 10）

#### Step 2.1: 慢 SQL 明细检索（DAS JIT Go SDK）

```bash
# DAS 是 SDK-only（CLI 不支持），通过 JIT Go SDK 执行
# 代码片段: das_slow_query.go -> 接受 INSTANCE_ID + StartTime + EndTime -> 输出 JSON
# Go 代码已预生成在: assets/code-snippets/das_slow_query.go

DAS_CODE_SNIPPET="${SKILLS_DIR:-.}/assets/code-snippets/das_slow_query.go"

for DB_ID in $(echo "$SUSPECT_RDS" | jq -r '.[]'); do
  echo ""
  echo "═══════════════════════════════════════"
  echo "  DAS 深度诊断: $DB_ID"
  echo "═══════════════════════════════════════"

  # ── a) 生成诊断报告 ──
  # 调用 DAS CreateDiagnosticReport（通过 JIT Go SDK）
  DAS_REPORT_ID=$(go run "$DAS_CODE_SNIPPET" \
    --action create-report \
    --instance "$DB_ID" \
    --region "$REGION" \
    --start "$START_TIME" \
    --end "$END_TIME" 2>/dev/null | jq -r '.report_id // empty')

  if [ -n "$DAS_REPORT_ID" ]; then
    echo "[DIAG] DAS 诊断报告已创建: $DAS_REPORT_ID"
    sleep 3

    # ── b) 获取慢 SQL 样本 ──
    SLOW_SQLS=$(go run "$DAS_CODE_SNIPPET" \
      --action get-slow-sql \
      --instance "$DB_ID" \
      --region "$REGION" \
      --start "$START_TIME" \
      --end "$END_TIME" 2>/dev/null)

    echo "$SLOW_SQLS" | jq -r '.[] | "  [慢SQL] \(.sql_text[:80])... | 次数: \(.exec_count) | 平均耗时: \(.avg_lock_time_ms)ms | 扫描行: \(.scan_rows)"'
  fi

  # ── c) 获取 SQL 洞察统计（最近 1h）──
  SQL_STATS=$(go run "$DAS_CODE_SNIPPET" \
    --action get-sql-stats \
    --instance "$DB_ID" \
    --region "$REGION" \
    --start "$START_TIME" \
    --end "$END_TIME" 2>/dev/null)

  echo "[DIAG] SQL 洞察统计:"
  echo "$SQL_STATS" | jq -r '
    .items[] | select(.error_count > 0 or .avg_latency_ms > 1000) |
    "  [WARN] SQL: \(.sql_text[:60])... | 平均延迟: \(.avg_latency_ms)ms | 错误数: \(.error_count)"'
done
```

#### Step 2.2: 性能洞察（等待事件分析）

> **DAS Pro 功能**：对开启 DAS Pro 的实例，获取 PFS（Performance Insight）SQL 样本，
> 分析等待事件（io/table/innodb 等），定位数据库内部瓶颈。

```bash
for DB_ID in $(echo "$SUSPECT_RDS" | jq -r '.[]'); do
  echo ""
  echo "── DAS 性能洞察: $DB_ID ──"

  # 获取 PFS SQL 样本（需 DAS Pro）
  PFS_SAMPLES=$(go run "$DAS_CODE_SNIPPET" \
    --action get-pfs-samples \
    --instance "$DB_ID" \
    --region "$REGION" \
    --start "$START_TIME" \
    --end "$END_TIME" \
    --limit 20 2>/dev/null)

  # 按等待事件分组统计
  echo "$PFS_SAMPLES" | jq -r '
    group_by(.wait_event) | map({
      event: .[0].wait_event,
      count: length,
      total_latency: (map(.latency_ms) | add)
    }) | sort_by(-.total_latency) | .[:5][] |
    "  [等待事件] \(.event): \(.count) 次, 总等待 \(.total_latency)ms"'
done
```

#### Step 2.3: 会话分析（活跃连接 / 锁等待）

> 通过 DAS 获取当前会话列表，分析活跃连接、锁等待和空闲连接占比。
> Kill 空闲连接属于 WARNING 白名单 W-01（只读诊断命令）。

```bash
for DB_ID in $(echo "$SUSPECT_RDS" | jq -r '.[]'); do
  echo ""
  echo "── 会话分析: $DB_ID ──"

  # 获取会话列表
  SESSIONS=$(go run "$DAS_CODE_SNIPPET" \
    --action get-sessions \
    --instance "$DB_ID" \
    --region "$REGION" 2>/dev/null)

  TOTAL_SESS=$(echo "$SESSIONS" | jq '.total // 0')
  ACTIVE_SESS=$(echo "$SESSIONS" | jq '[.sessions[] | select(.state == "running")] | length')
  SLEEP_SESS=$(echo "$SESSIONS" | jq '[.sessions[] | select(.state == "sleep")] | length')
  LOCK_WAIT=$(echo "$SESSIONS" | jq '[.sessions[] | select(.state == "locked" or (.command == "Query" and .state == "sending data"))] | length')

  echo "  [会话] 总计: $TOTAL_SESS | 活跃: $ACTIVE_SESS | 空闲: $SLEEP_SESS | 锁等待: $LOCK_WAIT"

  # 锁等待 -> 检查死锁
  if [ "$LOCK_WAIT" -gt 0 ]; then
    DEADLOCK=$(go run "$DAS_CODE_SNIPPET" \
      --action get-deadlock \
      --instance "$DB_ID" \
      --region "$REGION" 2>/dev/null)

    DEADLOCK_TIME=$(echo "$DEADLOCK" | jq -r '.latest_deadlock_time // "无"')
    echo "  CRITICAL 检测到锁等待! 最近死锁时间: $DEADLOCK_TIME"
    echo "  [AUTO-NOTIFY] 建议 Kill 空闲会话释放连接:"
    echo "    go run $DAS_CODE_SNIPPET --action kill-sleep-sessions --instance $DB_ID"
  fi
done
```

#### Step 2.4: DAS 智能巡检评分

```bash
for DB_ID in $(echo "$SUSPECT_RDS" | jq -r '.[]'); do
  # DAS 智能评分（0-100）
  INSPECTION=$(go run "$DAS_CODE_SNIPPET" \
    --action get-inspection \
    --instance "$DB_ID" \
    --region "$REGION" 2>/dev/null)

  SCORE=$(echo "$INSPECTION" | jq -r '.score // "N/A"')
  echo "[DIAG] DAS 巡检评分: $DB_ID = $SCORE/100"

  if [ -n "$SCORE" ] && [ "$(echo "$SCORE < 60" | bc -l 2>/dev/null)" = "1" ]; then
    echo "  CRITICAL DAS 评分 < 60 -> 建议深度诊断"

    # 获取自治事件历史
    EVENTS=$(go run "$DAS_CODE_SNIPPET" \
      --action get-autonomous-events \
      --instance "$DB_ID" \
      --region "$REGION" \
      --days 7 2>/dev/null)

    echo "  最近自治事件:"
    echo "$EVENTS" | jq -r '.[:5][] | "    - \(.event_time): \(.event_type) - \(.event_content)"'
  fi
done
```

#### Step 2.5: 空间分析

> RDS 磁盘使用率 > 75% 时触发的空间分析，检查数据文件、日志文件、临时文件占比。

```bash
for DB_ID in $(echo "$SUSPECT_RDS" | jq -r '.[]'); do
  # CMS 查磁盘使用率
  DISK_USAGE=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName DiskUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 300 \
    --StartTime "$START_TIME" --EndTime "$END_TIME" \
    | jq '.Datapoints | fromjson | [.[].Average] | max // 0')

  if [ "$(echo "$DISK_USAGE > 75" | bc -l 2>/dev/null)" = "1" ]; then
    echo ""
    echo "── 空间分析: $DB_ID (磁盘使用率 $DISK_USAGE%) ──"

    # DAS 空间分析
    SPACE_INFO=$(go run "$DAS_CODE_SNIPPET" \
      --action get-space-summary \
      --instance "$DB_ID" \
      --region "$REGION" 2>/dev/null)

    echo "$SPACE_INFO" | jq -r '
      "  总空间: \(.total_gb)GB | 已用: \(.used_gb)GB | 数据: \(.data_gb)GB | 日志: \(.log_gb)GB | 临时: \(.tmp_gb)GB"'

    # 最大表 TOP 10
    echo "  最大表 TOP 5:"
    echo "$SPACE_INFO" | jq -r '.top_tables[:5][] | "    - \(.schema).\(.table): \(.size_gb)GB"'
  fi
done
```

### Phase 3: 推理 + 报告

#### Step 3.1: 慢查询根因推理

Agent 对照以下规则做根因推理：

| 现象组合 | 规则 | 推理结论 | 建议 |
|---|---|---|---|
| CPU > 75% + 慢查询 > 100/min | RDS-01 | 慢 SQL 导致 CPU 飙升 | 查 DAS 慢 SQL 明细 -> 加索引/改 SQL |
| CPU 正常 + 慢查询多 | RDS-03 | 慢 SQL 未直接影响 CPU | 检查索引命中率/表数据量 |
| 活跃连接 > 80% + 锁等待 > 0 | RDS-02 | 锁竞争导致连接堆积 | Kill 空闲会话/查死锁/优化事务 |
| 磁盘 > 85% | RDS-04 | 磁盘即将写满 | 扩容/清理 binlog/归档大表 |
| 连接数 > 80% + CPU 正常 | RDS-05 | 应用连接池配置过大或泄漏 | 检查连接池设置/Kill 空闲连接 |
| DAS 评分 < 60 + 自治事件多 | RDS-06 | 数据库"慢性病" | 综合评估是否需要升配或架构优化 |

#### Step 3.2: 慢 SQL 优化建议生成

```bash
# 对每个慢 SQL 生成优化建议
# 规则引擎：
# 1. 全表扫描（扫描行数 >> 返回行数）-> 加索引
# 2. Using filesort / Using temporary -> 优化 ORDER BY / GROUP BY
# 3. 大表 JOIN（表数据 > 1000 万行）-> 考虑分表/缓存
# 4. 锁等待严重 -> 检查事务隔离级别/索引设计
# 5. 重复执行相同慢 SQL -> 增加缓存层
```

#### Step 3.3: 双格式报告输出

**Markdown（给人读）：**

```markdown
═══════════════════════════════════════════════════════
   慢查询诊断报告
═══════════════════════════════════════════════════════
  报告ID: slowquery-$CUSTOMER-$(date +%Y%m%dT%H%M%SZ)
  客户: $CUSTOMER | 区域: $REGION | 时间: $(date)
  诊断窗口: $START_TIME -> $END_TIME
═══════════════════════════════════════════════════════

## [STATS] 总览

| 维度 | 结果 |
|------|------|
| 扫描实例数 | $RDS_COUNT |
| 可疑实例数 | $SUSPECT_COUNT |
| 已诊断实例 | $(echo "$SUSPECT_RDS" \| jq 'length') |
| Critical 问题 | ${CRITICAL_COUNT:-0} |
| Warning 问题 | ${WARNING_COUNT:-0} |

═══════════════════════════════════════════════════════
  Critical 问题清单
═══════════════════════════════════════════════════════

#1 RDS CPU 飙升 + 慢查询堆积
  ┌─ 诊断链 ─────────────────────────────────────────────
  │ 实例: ${DB_ID} (${DB_NAME})
  │ 规格: ${DB_CLASS} | 引擎: MySQL ${DB_VERSION}
  │ CPU: ${RDS_CPU}% (阈值: Warning 75% / Critical 85%)
  │ 慢查询: ${SLOW_QUERY}/min (阈值: Warning 10/min)
  │ DAS 评分: ${DAS_SCORE}/100
  │ 规则: RDS-01 (CPU + 慢查询 -> Critical)
  └───────────────────────────────────────────────────────

  ┌─ TOP 慢 SQL ─────────────────────────────────────────
  │ SQL1: SELECT * FROM orders WHERE status = 'pending'
  │       ORDER BY created_at DESC LIMIT 10
  │ 次数: 1523 | 平均耗时: 2340ms | 扫描行: 50 万
  │ 执行计划: Using filesort; Using where
  │ 优化建议: 在 `status + created_at` 上建联合索引
  │   CREATE INDEX idx_orders_status_created
  │   ON orders(status, created_at);
  │
  │ SQL2: SELECT o.*, u.name FROM orders o
  │       LEFT JOIN users u ON o.user_id = u.id
  │       WHERE o.created_at > '2026-06-01'
  │ 次数: 876 | 平均耗时: 1800ms | 扫描行: 120 万
  │ 执行计划: Using where; Using join buffer
  │ 优化建议: 在 `orders.created_at` 上建索引
  │   CREATE INDEX idx_orders_created_at ON orders(created_at);
  └───────────────────────────────────────────────────────

  ┌─ 修复优先级 ─────────────────────────────────────────
  │ P0: 创建索引 idx_orders_status_created（无风险）
  │      [AUTO-NOTIFY] CREATE INDEX ...
  │ P1: 创建索引 idx_orders_created_at（无风险）
  │      [SUGGESTED] CREATE INDEX ...
  │ P2: 检查是否需要将 orders 历史数据归档到 OSS
  └───────────────────────────────────────────────────────

#2 RDS 磁盘使用率超标
  ┌─ 诊断链 ─────────────────────────────────────────────
  │ 实例: ${DB_ID2}
  │ 磁盘使用率: ${DISK_USAGE}% (阈值: Warning 75% / Critical 90%)
  │ 规则: RDS-04 (磁盘 > 85% -> Critical)
  │ DAS 空间分析:
  │   总空间: 200GB | 已用: 185GB | 数据: 120GB | 日志: 50GB | 临时: 15GB
  └───────────────────────────────────────────────────────

  ┌─ 修复步骤 ────────────────────────────────────────────
  │ Step 1 (紧急): 清理 binlog
  │   [AUTO-NOTIFY] CALL mysql.rds_cycle_binlog();
  │
  │ Step 2 (长期): 扩容存储至 400GB
  │   [SUGGESTED] aliyun rds ModifyDBInstanceSpec --DBInstanceStorage 400
  │
  │ Step 3 (验证): 确认磁盘回落
  │   aliyun cms DescribeMetricList --Namespace acs_rds_dashboard
  │   --MetricName DiskUsage ...
  └───────────────────────────────────────────────────────

═══════════════════════════════════════════════════════
  Warning 问题清单
═══════════════════════════════════════════════════════

#3 RDS 连接数偏高
  实例: ${DB_ID3}
  活跃连接: ${ACTIVE_SESS} / 最大: ${MAX_CONN} (${CONN_PCT}%)
  空闲连接: ${SLEEP_SESS} (占比 ${SLEEP_PCT}%)
  建议: Kill 空闲连接或检查应用连接池
  [AUTO-NOTIFY] Kill 空闲连接: go run das_slow_query.go --action kill-sleep-sessions ...

═══════════════════════════════════════════════════════
  [PIN] 优化建议（按优先级）
═══════════════════════════════════════════════════════

1. CRITICAL [P0] ${DB_ID} — 创建联合索引
   SQL: CREATE INDEX idx_orders_status_created ON orders(status, created_at);
   预估效果: 消除 Using filesort，慢查询减少 80%

2. CRITICAL [P0] ${DB_ID2} — 清理 binlog / 扩容
   DAS 建议执行: CALL mysql.rds_cycle_binlog();

3. WARNING [P1] ${DB_ID} — Kill 空闲连接
   当前 ${SLEEP_SESS} 个空闲连接，建议 Kill 超过 30min 的睡眠连接

═══════════════════════════════════════════════════════
  审计追踪
═══════════════════════════════════════════════════════
  JSON: audit-results/slowquery-$CUSTOMER-$(date +%Y%m%d).json
  耗时: $EXECUTION_DURATION | runbook: v1.0.0
```

**JSON（持久化到 `audit-results/`）：**

```bash
mkdir -p audit-results/
cat > "audit-results/slowquery-${CUSTOMER}-$(date +%Y%m%d).json" << SLOW_JSON
{
  "report_id": "slowquery-${CUSTOMER}-$(date +%Y%m%dT%H%M%SZ)",
  "customer": "${CUSTOMER}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "scenario": "slow_query_diagnosis",
  "runbook_version": "1.0.0",
  "db_summary": {
    "total_instances": ${RDS_COUNT},
    "suspect_instances": ${SUSPECT_COUNT},
    "critical_findings": ${CRITICAL_COUNT:-0},
    "warning_findings": ${WARNING_COUNT:-0}
  },
  "slow_sqls": [
    {
      "instance_id": "${DB_ID}",
      "sql_text": "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC LIMIT ?",
      "exec_count": 1523,
      "avg_latency_ms": 2340,
      "scan_rows": 500000,
      "return_rows": 10,
      "sql_type": "SEL",
      "execute_plan": "Using filesort; Using where",
      "suggestion": "CREATE INDEX idx_orders_status_created ON orders(status, created_at)",
      "rule_id": "RDS-01",
      "level": "CRITICAL"
    }
  ],
  "critical_findings": [],
  "warning_findings": []
}
SLOW_JSON
echo "[RESULT] JSON报告已持久化到 audit-results/"
```

---

## 3. 阈值速查

| 服务 | 指标 | Warning | Critical | 说明 |
|------|------|:-------:|:--------:|------|
| RDS | CPU 使用率 | > 75% | > 85% | CPU 飙升通常伴随慢查询 |
| RDS | 慢查询数 | > 10/min | > 100/min | DAS Pro 可获取明细 |
| RDS | 连接数/上限 | > 70% | > 85% | 连接耗尽导致拒绝连接 |
| RDS | 磁盘使用率 | > 75% | > 90% | 超 95% 自动只读 |
| RDS | IOPS/规格上限 | > 70% | > 85% | IOPS 打满导致延迟 |
| RDS | DAS 智能评分 | < 70 | < 60 | 综合健康评分 |
| RDS | 活跃锁等待 | > 0 | > 5 | 锁竞争影响并发 |
| RDS | 空闲连接占比 | > 50% | > 70% | 连接泄漏迹象 |

---

## 4. 改进闭环

| 反馈来源 | 触发条件 | 改进动作 | 责任人 |
|----------|---------|---------|--------|
| 人工审阅 | 优化建议误判（如建议建的索引已存在） | 更新慢 SQL 分析规则 | 运维负责人 |
| 误报 | DAS API 返回空数据但 CMS 显示慢查询 | 增加 DAS Pro 检查前置条件 | Agent 维护者 |
| 新实例类型 | 新增 PolarDB PG 等实例 | 更新 JIT Go SDK snippet | Agent 维护者 |
| 漏报 | 用户反馈有慢查询但诊断未发现 | 增加 SQL 审计日志检查 | Agent 维护者 |
| 性能 | 诊断 20+ 实例超时 | 增加并行诊断 + 分批策略 | Agent 维护者 |

---

## 5. Changelog

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 1.0.0 | 2026-06-07 | 初始版本，慢查询诊断与治理完整流程 |