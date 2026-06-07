---
runbook_id: "06"
scenario: "数据库连接风暴自愈"
version: "1.0.0"
last_updated: "2026-06-07"
trigger: "CMS 告警（活跃连接数 > 85%）/ DAS 连接数超限告警 / 人工触发"
risk_level: "高"
execution_time_estimate: "3-8 分钟"
---

> **脚本**: [`runbooks/scripts/connection-storm-selfheal.py`](scripts/connection-storm-selfheal.py) — 全自动执行本 runbook

# 数据库连接风暴自愈

## 1. 场景描述

当 RDS/PolarDB 活跃连接数超过 85% 阈值时，自动诊断连接风暴的根因（慢查询堆积 / 僵尸连接 / 连接池泄漏），执行 🟡 白名单内安全操作（Kill 空闲连接），并出具体修复建议。

### 🚨 安全铁律

| 红线 | 要求 |
|---|---|
| **任何资源的删除/停止/规格变更** | ❌ 不允许自动执行，报告只出建议 |
| **输出 AK/SK** | ❌ 必须掩码为 `AKID****SKRET` |
| **Kill 活跃事务连接** | 🔴 需人工确认，不自动执行 |
| **修改 max_connections** | 🔴 需人工确认，不自动执行 |
| **Kill 空闲/睡眠连接** | 🟡 [AUTO-NOTIFY] 白名单 W-01，自动执行后通知 |

### 🧠 提示知识力

> **连接风暴的三个典型场景：**
>
> 1. **慢查询堆积**（~45%）—— 突然的慢 SQL 让每个查询耗时变长，请求排队 → 连接数飙升 → CPU 也高
> 2. **僵尸连接**（~30%）—— 应用连接池未正确释放连接（CLOSE_WAIT 堆积），连接数缓慢爬升 → CPU 正常 → 持续 24h+ 后打满
> 3. **突发流量**（~25%）—— 业务高峰/QPS 骤增，连接数跟着涨 → 每个连接都活跃且正常 → 需要扩容
>
> **诊断关键**：看 CPU 和慢查询
> - CPU 高 + 慢查询多 → 场景 1 → 先 Kill 空闲连接释放资源 → 再查慢 SQL
> - CPU 正常 + 慢查询少 → 场景 2 → Kill 僵尸连接是唯一手段
> - CPU 正常 + 连接活跃 → 场景 3 → 评估扩容

### 适用条件

- RDS MySQL / PolarDB MySQL 实例
- DAS Pro 已开启（获取会话列表）
- 阿里云 AK/SK 已配置且有 CMS 只读 + DAS 只读 + Kill 会话权限

### 不适用条件

- SQL Server / MariaDB 实例
- 未开启 DAS Pro 的实例（无法获取会话详情）
- 需要 Kill 活跃事务 → 引导到 `05-slow-query-diagnosis` 深度诊断

---

## 2. 执行流程

### Phase 0: 前置安全门

```bash
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" || { echo "[ERROR] AK_ID 未设置"; exit 1; }
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" || { echo "[ERROR] AK_SK 未设置"; exit 1; }
command -v aliyun >/dev/null 2>&1 || { echo "[ERROR] aliyun CLI 未安装"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "[ERROR] jq 未安装"; exit 1; }

CUSTOMER="{{user.customer_name}}"
REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
ALERT_TIME="{{user.reported_time}}"
echo "[INFO] 客户: $CUSTOMER | 区域: $REGION"

WINDOW_START=$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)
WINDOW_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "[INFO] 诊断窗口: $WINDOW_START → $WINDOW_END"
```

### Phase 1: 实例扫描 + 连接指标采集

```bash
RG_ID="{{user.resource_group_id}}"
TAG_KEY="{{user.tag_key}}"
TAG_VALUE="{{user.tag_value}}"

# 扫描 RDS 实例
if [ -n "$RG_ID" ]; then
  RDS_INSTANCES=$(aliyun rds DescribeDBInstances --RegionId "$REGION" \
    --ResourceGroupId "$RG_ID" --PageSize 100 | jq '.Items.DBInstance')
elif [ -n "$TAG_KEY" ]; then
  RDS_INSTANCES=$(aliyun rds DescribeDBInstances --RegionId "$REGION" \
    --Tag.1.Key "$TAG_KEY" --Tag.1.Value "$TAG_VALUE" --PageSize 100 | jq '.Items.DBInstance')
else
  echo "[ERROR] 必须提供资源组ID或标签"; exit 1
fi

# CMS 获取连接指标，筛选连接数 > 70% 的可疑实例
SUSPECT_INSTANCES="[]"

for DB_ID in $(echo "$RDS_INSTANCES" | jq -r '.[].DBInstanceId // empty'); do
  CONN_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName ConnectionUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 300 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  CPU_PCT=$(aliyun cms DescribeMetricList \
    --Namespace acs_rds_dashboard \
    --MetricName CpuUsage \
    --Dimensions "[{\"instanceId\":\"$DB_ID\"}]" \
    --Period 300 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  MAX_CONN=$(aliyun rds DescribeDBInstanceAttribute \
    --RegionId "$REGION" --DBInstanceId "$DB_ID" \
    | jq -r '.Items.DBInstanceAttribute[0].MaxConnections // 100')

  echo "  RDS $DB_ID: 连接使用率=${CONN_PCT}% CPU=${CPU_PCT}% 最大连接=${MAX_CONN}"

  if [ "$(echo "$CONN_PCT > 70" | bc -l 2>/dev/null)" = "1" ]; then
    SUSPECT_INSTANCES=$(echo "$SUSPECT_INSTANCES" | jq --arg id "$DB_ID" \
      --arg conn "$CONN_PCT" --arg cpu "$CPU_PCT" --arg maxc "$MAX_CONN" \
      '. + [{"id": $id, "conn_pct": ($conn | tonumber), "cpu_pct": ($cpu | tonumber), "max_conn": ($maxc | tonumber)}]')
    echo "  → 标记为可疑实例"
  fi
done

SUSPECT_COUNT=$(echo "$SUSPECT_INSTANCES" | jq 'length')
echo "[INFO] 连接数超标实例: $SUSPECT_COUNT 个"
```

### Phase 2: 深度诊断 + 自动修复

#### Step 2.1: DAS 会话分析

```bash
DAS_CODE_SNIPPET="${SKILLS_DIR:-.}/assets/code-snippets/das_slow_query.go"

echo "$SUSPECT_INSTANCES" | jq -c '.[]' | while read -r INST; do
  DB_ID=$(echo "$INST" | jq -r '.id')
  CONN_PCT=$(echo "$INST" | jq -r '.conn_pct')
  CPU_PCT=$(echo "$INST" | jq -r '.cpu_pct')
  MAX_CONN=$(echo "$INST" | jq -r '.max_conn')

  echo ""
  echo "═══════════════════════════════════════"
  echo "  连接风暴诊断: $DB_ID"
  echo "═══════════════════════════════════════"

  # ── a) 获取会话列表 ──
  SESSIONS=$(go run "$DAS_CODE_SNIPPET" \
    --action get-sessions \
    --instance "$DB_ID" \
    --region "$REGION" 2>/dev/null)

  TOTAL_SESS=$(echo "$SESSIONS" | jq '.total // 0')
  ACTIVE_SESS=$(echo "$SESSIONS" | jq '[.sessions[] | select(.state == "running")] | length')
  SLEEP_SESS=$(echo "$SESSIONS" | jq '[.sessions[] | select(.state == "sleep")] | length')
  LOCK_WAIT=$(echo "$SESSIONS" | jq '[.sessions[] | select(.state == "locked")] | length')
  TXN_ACTIVE=$(echo "$SESSIONS" | jq '[.sessions[] | select(.state == "running" and .command == "Query")] | length')

  SLEEP_PCT=$(echo "scale=1; $SLEEP_SESS * 100 / $TOTAL_SESS" | bc 2>/dev/null || echo "0")

  echo "  [会话] 总计=$TOTAL_SESS 活跃=$ACTIVE_SESS 空闲=$SLEEP_SESS(${SLEEP_PCT}%) 锁等待=$LOCK_WAIT 事务中=$TXN_ACTIVE"

  # ── b) 根因分类 ──
  if [ "$(echo "$CPU_PCT > 75" | bc -l 2>/dev/null)" = "1" ] && [ "$(echo "$TXN_ACTIVE > 10" | bc -l 2>/dev/null)" = "1" ]; then
    STORM_TYPE="slow_query"
    echo "  🔴 根因: 慢查询堆积 — CPU ${CPU_PCT}%, 活跃事务 ${TXN_ACTIVE}"
    echo "  建议: 执行 05-slow-query-diagnosis 定位慢 SQL"
  elif [ "$(echo "$SLEEP_PCT > 60" | bc -l 2>/dev/null)" = "1" ]; then
    STORM_TYPE="zombie_connection"
    echo "  🔴 根因: 僵尸连接 — 空闲连接占比 ${SLEEP_PCT}%"
  elif [ "$(echo "$CPU_PCT < 50" | bc -l 2>/dev/null)" = "1" ] && [ "$(echo "$TXN_ACTIVE > 20" | bc -l 2>/dev/null)" = "1" ]; then
    STORM_TYPE="burst_traffic"
    echo "  🔴 根因: 突发流量 — CPU ${CPU_PCT}% 正常但活跃查询 ${TXN_ACTIVE}"
  else
    STORM_TYPE="unknown"
    echo "  🟡 混合模式 — 需综合判断"
  fi

  # ── c) [AUTO-NOTIFY] Kill 空闲连接（超过 30min 的睡眠连接）──
  if [ "$(echo "$SLEEP_SESS > 10" | bc -l 2>/dev/null)" = "1" ] && [ "$STORM_TYPE" != "burst_traffic" ]; then
    echo ""
    echo "  [AUTO-NOTIFY] Kill 空闲连接..."
    KILL_RESULT=$(go run "$DAS_CODE_SNIPPET" \
      --action kill-sleep-sessions \
      --instance "$DB_ID" \
      --region "$REGION" \
      --idle-seconds 1800 2>/dev/null)

    KILLED=$(echo "$KILL_RESULT" | jq -r '.killed_count // 0')
    echo "  [RESULT] Kill 完成，释放 $KILLED 个空闲连接"

    # 验证
    sleep 3
    POST_SESSIONS=$(go run "$DAS_CODE_SNIPPET" \
      --action get-sessions \
      --instance "$DB_ID" \
      --region "$REGION" 2>/dev/null)
    POST_CONN=$(echo "$POST_SESSIONS" | jq '.total // 0')
    echo "  [VERIFY] Kill 后连接数: $TOTAL_SESS → $POST_CONN (减少 $((TOTAL_SESS - POST_CONN)))"

    # 审计日志
    echo "  [AUDIT] whitelist_id=W-01 level=L1 resource=$DB_ID killed=$KILLED"
  fi

  # ── d) [SUGGESTED] 临时提升 max_connections ──
  if [ "$(echo "$CONN_PCT > 90" | bc -l 2>/dev/null)" = "1" ] && [ "$STORM_TYPE" != "zombie_connection" ]; then
    echo ""
    NEW_MAX=$(echo "$MAX_CONN * 1.5 / 1" | bc)
    echo "  [SUGGESTED] 临时提升 max_connections: $MAX_CONN → $NEW_MAX"
    echo "    aliyun rds ModifyDBInstanceSpec --DBInstanceId $DB_ID --MaxConnections $NEW_MAX"
    echo "    ⚠️ 需用户确认后执行"
  fi
done
```

#### Step 2.2: DAS 限流评估

```bash
# 对 CPU 高的场景评估 SQL 限流
if [ "$STORM_TYPE" = "slow_query" ]; then
  echo ""
  echo "── SQL 限流评估 ──"

  # 获取 TOP 慢 SQL 的限流关键字
  SQL_TEXT=$(echo "$SLOW_SQLS" | jq -r '.[0].sql_text // ""')
  if [ -n "$SQL_TEXT" ]; then
    LIMIT_KEYWORDS=$(go run "$DAS_CODE_SNIPPET" \
      --action get-limit-keywords \
      --instance "$DB_ID" \
      --region "$REGION" \
      --sql-text "$SQL_TEXT" 2>/dev/null)

    echo "  [SUGGESTED] 建议对以下 SQL 限流:"
    echo "    $SQL_TEXT"
    echo "    限流关键字: $(echo "$LIMIT_KEYWORDS" | jq -r '.keywords // "N/A"')"
    echo "    ⚠️ 需用户确认后执行，可能影响业务"
  fi
fi
```

### Phase 3: 报告

**Markdown:**

```markdown
═══════════════════════════════════════════════════════
  🌊 数据库连接风暴诊断报告
═══════════════════════════════════════════════════════
  报告ID: connection-storm-$CUSTOMER-$(date +%Y%m%dT%H%M%SZ)
  客户: $CUSTOMER | 区域: $REGION | 时间: $(date)
═══════════════════════════════════════════════════════

## 📊 总览

| 维度 | 结果 |
|------|------|
| 扫描实例数 | ${RDS_COUNT} |
| 连接超标实例 | ${SUSPECT_COUNT} |
| 已执行 Kill | ${KILLED_TOTAL:-0} 个空闲连接 |
| 🔴 Critical | ${CRITICAL_COUNT:-0} |
| 🟡 Warning | ${WARNING_COUNT:-0} |

## 🎯 根因诊断

### 实例: ${DB_ID}

| 指标 | 值 | 阈值 | 状态 |
|------|:---:|:----:|:----:|
| 连接使用率 | ${CONN_PCT}% | Warning 70% / Critical 85% | ${CONN_STATUS} |
| CPU 使用率 | ${CPU_PCT}% | Warning 75% / Critical 85% | ${CPU_STATUS} |
| 空闲连接占比 | ${SLEEP_PCT}% | Warning 50% / Critical 70% | ${SLEEP_STATUS} |
| 锁等待 | ${LOCK_WAIT} | > 0 即关注 | ${LOCK_STATUS} |

**根因分类**: ${STORM_TYPE_DESC}
  - 慢查询堆积: Kill 空闲 + 查慢 SQL
  - 僵尸连接: Kill 空闲 + 排查连接池
  - 突发流量: 评估扩容

### 自动操作记录

| 时间 | 操作 | 资源 | 结果 |
|------|------|------|------|
| $(date) | Kill 空闲连接(>30min) | ${DB_ID} | 释放 ${KILLED} 个 |

## 📋 修复建议

### 立即执行
1. [AUTO-NOTIFY] Kill 空闲连接 — ✅ 已自动执行
2. [SUGGESTED] Kill 锁等待事务
   命令: go run das_slow_query.go --action kill-session --instance ${DB_ID} --session-id ${SESSION_ID}
   风险: 事务回滚，影响该事务涉及的业务

### 根因修复
3. [SUGGESTED] 如为慢查询导致 → 执行 runbook 05 慢查询诊断
4. [SUGGESTED] 如为连接池泄漏 → 检查应用连接池配置
5. [SUGGESTED] 如为突发流量 → 评估升配或读写分离
```

**JSON:**

```json
{
  "report_id": "connection-storm-${CUSTOMER}-$(date +%Y%m%dT%H%M%SZ)",
  "scenario": "connection_storm_selfheal",
  "db_instances": [{
    "instance_id": "${DB_ID}",
    "conn_usage_pct": ${CONN_PCT},
    "cpu_pct": ${CPU_PCT},
    "storm_type": "${STORM_TYPE}",
    "total_sessions": ${TOTAL_SESS},
    "sleep_sessions": ${SLEEP_SESS},
    "killed_sessions": ${KILLED}
  }],
  "auto_actions": [{
    "whitelist_id": "W-01",
    "action": "kill_sleep_sessions",
    "resource": "${DB_ID}",
    "result": "killed ${KILLED} connections"
  }]
}
```

---

## 3. 阈值速查

| 指标 | Warning | Critical | 说明 |
|------|:-------:|:--------:|------|
| 连接数使用率 | > 70% | > 85% | 超过 85% 触发风暴响应 |
| CPU 使用率 | > 75% | > 85% | 配合连接数判断是否慢查询导致 |
| 空闲连接占比 | > 50% | > 70% | 占比高说明连接泄漏 |
| 锁等待数 | > 0 | > 5 | 锁竞争加剧连接堆积 |
| 活跃事务数 | > 10 | > 30 | 并发事务超过 vCPU 数 |

---

## 4. 改进闭环

| 反馈来源 | 触发条件 | 改进动作 | 责任人 |
|----------|---------|---------|--------|
| 误 Kill | Kill 了不应 Kill 的连接 | 缩短空闲判断时间(>30min→>60min) | 运维负责人 |
| 漏 Kill | Kill 后连接未回落 | 检查是否有遗漏的用户线程 | Agent 维护者 |
| 阈值不合理 | 连接数<70% 时触发告警 | 上调阈值或增加持续周期判断 | 运维负责人 |

---

## 5. Changelog

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 1.0.0 | 2026-06-07 | 初始版本 |