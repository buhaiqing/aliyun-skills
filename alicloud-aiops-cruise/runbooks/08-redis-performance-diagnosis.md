---
runbook_id: "08"
scenario: "Redis/Tair 缓存性能诊断"
version: "1.0.0"
last_updated: "2026-06-07"
trigger: "CMS 告警（Redis 内存 > 80% / OOM / 逐出 > 0）/ DAS 缓存分析建议 / 人工触发"
risk_level: "中"
execution_time_estimate: "3-8 分钟"
---

> **脚本**: [`runbooks/scripts/redis-performance-diagnosis.py`](scripts/redis-performance-diagnosis.py) — 全自动执行本 runbook

# Redis/Tair 缓存性能诊断

## 1. 场景描述

当 Redis/Tair 内存使用率过高、出现逐出（eviction）或命中率下降时，通过 DAS 缓存分析检测大 key、诊断缓存模式，输出优化建议。覆盖：热 key、大 key、过期策略、内存碎片四个维度。

### [ALERT] 安全铁律

| 红线 | 要求 |
|---|---|
| **任何资源的删除/停止/规格变更** | FAIL 不允许自动执行，报告只出建议 |
| **输出 AK/SK** | FAIL 必须掩码为 `AKID****SKRET` |
| **修改 maxmemory-policy** | WARNING [AUTO-NOTIFY] 白名单 W-03，自动执行后通知 |
| **Redis 升配** | CRITICAL [SUGGESTED] 需用户确认 |
| **删除大 key** | CRITICAL 需人工确认，不自动执行 |

### [NOTE] 提示知识力

> **Redis 性能问题的四个维度及处理优先级：**
>
> 1. **大 key**（最常见）—— 单个 key 包含大量数据（大 List/Hash/Set > 1MB），导致慢查询、阻塞、内存不均
> 2. **热 key** —— 单个 key 被高频访问（> 1000 QPS），导致单分片 CPU 飙高
> 3. **过期策略** —— key 没有设置 TTL 或 TTL 过长，导致内存持续增长，触发 maxmemory-policy 逐出
> 4. **内存碎片** —— 频繁写入删除导致碎片率 > 1.5，实际内存 > used_memory
>
> **修复顺序**：大 key > 热 key > 过期策略 > 碎片
>
> **DAS 缓存分析的价值**：直接扫描 Redis 全部 key 的空间和类型分布，找出 TOP N 大 key，
> 是诊断 Redis 问题的第一选择——远优于人工 `redis-cli --bigkeys`（需直连、慢、阻塞）。

### 适用条件

- Redis / Tair (阿里云 Redis 企业版) 实例
- DAS Pro 已开启（缓存分析和慢查询功能）
- 实例状态为 Running

### 不适用条件

- 自建 Redis（不在阿里云内）
- 内存使用率正常且无逐出 -> 无需诊断
- 需要删除大 key -> 需用户确认后通过 `alicloud-das-ops` 执行

---

## 2. 执行流程

### Phase 0: 前置安全门

```bash
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" || { echo "[ERROR] AK_ID 未设置"; exit 1; }
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" || { echo "[ERROR] AK_SK 未设置"; exit 1; }
command -v aliyun >/dev/null 2>&1 || { echo "[ERROR] aliyun CLI 未安装"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "[ERROR] jq 未安装"; exit 1; }
command -v go >/dev/null 2>&1 || { echo "[WARN] go 未安装 — DAS 缓存分析不可用"; }

CUSTOMER="{{user.customer_name}}"
REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
echo "[INFO] 客户: $CUSTOMER | 区域: $REGION"

WINDOW_START=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)
WINDOW_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

### Phase 1: Redis 实例扫描 + CMS 指标初筛

```bash
RG_ID="{{user.resource_group_id}}"
TAG_KEY="{{user.tag_key}}"
TAG_VALUE="{{user.tag_value}}"

# 扫描 Redis 实例
if [ -n "$RG_ID" ]; then
  REDIS_LIST=$(aliyun r-kvstore DescribeInstances --RegionId "$REGION" \
    --PageSize 100 | jq --arg rg "$RG_ID" \
    '[.Instances.KVStoreInstance[] | select(.ResourceGroupId == $rg)]')
elif [ -n "$TAG_KEY" ]; then
  REDIS_LIST=$(aliyun r-kvstore DescribeInstances --RegionId "$REGION" \
    --Tag.1.Key "$TAG_KEY" --Tag.1.Value "$TAG_VALUE" --PageSize 100 \
    | jq '.Instances.KVStoreInstance')
else
  echo "[ERROR] 必须提供资源组ID或标签"; exit 1
fi

# CMS 指标初筛
SUSPECT_REDIS="[]"

for REDIS_ID in $(echo "$REDIS_LIST" | jq -r '.[].InstanceId // empty'); do
  REDIS_MEM=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName memory_usage \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 300 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  REDIS_EVICTED=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName EvictedKeys \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 300 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  # 命中率（部分版本不暴露，NODATA 时跳过）
  REDIS_HIT=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName HitRate \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 300 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Average] | add / length // -1')

  REDIS_CONN=$(aliyun cms DescribeMetricList \
    --Namespace acs_redis_dashboard \
    --MetricName UsedConnection \
    --Dimensions "[{\"instanceId\":\"$REDIS_ID\"}]" \
    --Period 300 \
    --StartTime "$WINDOW_START" --EndTime "$WINDOW_END" \
    | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0')

  INST_CLASS=$(echo "$REDIS_LIST" | jq -r --arg id "$REDIS_ID" \
    '.[] | select(.InstanceId == $id) | .InstanceClass // "unknown"')

  echo "  Redis $REDIS_ID ($INST_CLASS): 内存=${REDIS_MEM}% 逐出=${REDIS_EVICTED} 命中率=${REDIS_HIT}% 连接=${REDIS_CONN}"

  # 可疑判定：内存 > 75% 或 逐出 > 0
  if [ "$(echo "$REDIS_MEM > 75" | bc -l 2>/dev/null)" = "1" ] || [ "$REDIS_EVICTED" != "0" ]; then
    SUSPECT_REDIS=$(echo "$SUSPECT_REDIS" | jq --arg id "$REDIS_ID" \
      --arg mem "$REDIS_MEM" --arg evict "$REDIS_EVICTED" --arg hit "$REDIS_HIT" \
      '. + [{"id": $id, "mem_pct": ($mem | tonumber), "evicted": ($evict | tonumber), "hit_rate": $hit}]')
    echo "  -> 标记为可疑实例"
  else
    echo "  PASS 内存正常"
  fi
done

SUSPECT_COUNT=$(echo "$SUSPECT_REDIS" | jq 'length')
echo "[INFO] 内存超标实例: $SUSPECT_COUNT 个"
```

### Phase 2: 四维缓存诊断

#### Step 2.1: DAS 缓存分析 — 大 key 检测

```bash
DAS_CODE_SNIPPET="${SKILLS_DIR:-.}/assets/code-snippets/das_slow_query.go"

echo "$SUSPECT_REDIS" | jq -c '.[]' | while read -r INST; do
  REDIS_ID=$(echo "$INST" | jq -r '.id')
  MEM_PCT=$(echo "$INST" | jq -r '.mem_pct')
  EVICTED=$(echo "$INST" | jq -r '.evicted')

  echo ""
  echo "═══════════════════════════════════════"
  echo "  Redis 缓存诊断: $REDIS_ID"
  echo "═══════════════════════════════════════"

  # ── a) DAS 缓存分析：创建分析任务 ──
  echo "  [DIAG] 创建缓存分析任务..."

  CACHE_JOB=$(go run "$DAS_CODE_SNIPPET" \
    --action create-cache-analysis \
    --instance "$REDIS_ID" \
    --region "$REGION" 2>/dev/null)

  JOB_ID=$(echo "$CACHE_JOB" | jq -r '.job_id // empty')

  if [ -n "$JOB_ID" ]; then
    echo "  [DIAG] 分析任务已创建: $JOB_ID (等待 10s 完成)..."
    sleep 10

    # ── b) 获取分析结果 ──
    BIG_KEYS=$(go run "$DAS_CODE_SNIPPET" \
      --action get-cache-analysis-result \
      --instance "$REDIS_ID" \
      --region "$REGION" \
      --job-id "$JOB_ID" 2>/dev/null)

    echo ""
    echo "  [WARN] 大 key TOP 10:"
    echo "$BIG_KEYS" | jq -r '.big_keys[:10][] | "    [\(.key_type)] \(.key_name[:50]) = \(.size_bytes)B / \(.element_count) 个元素"'

    # 汇总各类型 key 分布
    echo ""
    echo "  [STATS] Key 类型分布:"
    echo "$BIG_KEYS" | jq -r '
      group_by(.key_type) | map({type: .[0].key_type, count: length, total_size: (map(.size_bytes) | add)}) |
      sort_by(-.total_size)[] |
      "    \(.type): \(.count) 个, 共 \(.total_size / 1024 / 1024 | floor)MB"'

    # 逐出 key 信息
    if [ "$(echo "$EVICTED > 0" | bc -l 2>/dev/null)" = "1" ]; then
      echo ""
      echo "  CRITICAL 检测到逐出事件 (evicted=$EVICTED)！"
    fi
  else
    echo "  [WARN] 缓存分析任务创建失败，可能未开启 DAS Pro"
  fi
done
```

#### Step 2.2: 命中率 + 连接分析

```bash
# ── c) 命中率诊断 ──
for REDIS_ID in $(echo "$SUSPECT_REDIS" | jq -r '.[].id'); do
  HIT_RATE=$(echo "$SUSPECT_REDIS" | jq -r --arg id "$REDIS_ID" \
    '.[] | select(.id == $id) | .hit_rate')

  echo ""
  echo "  ── 命中率诊断: $REDIS_ID ──"

  if [ "$HIT_RATE" != "-1" ]; then
    if [ "$(echo "$HIT_RATE < 80" | bc -l 2>/dev/null)" = "1" ]; then
      echo "  CRITICAL 命中率 ${HIT_RATE}% < 80% — 大量请求穿透到后端 DB"
      echo "  建议: 检查缓存命中逻辑 / 增加缓存 TTL / 扩大缓存容量"
    elif [ "$(echo "$HIT_RATE < 90" | bc -l 2>/dev/null)" = "1" ]; then
      echo "  WARNING 命中率 ${HIT_RATE}% < 90% — 偏低，需关注"
    else
      echo "  PASS 命中率 ${HIT_RATE}% — 正常"
    fi
  else
    echo "  ℹ️ 命中率指标不可用（部分版本不暴露）"
  fi
done
```

#### Step 2.3: [AUTO-NOTIFY] 逐出策略自动修复

```bash
# ── d) [AUTO-NOTIFY] 修改 maxmemory-policy（白名单 W-03） ──
for REDIS_ID in $(echo "$SUSPECT_REDIS" | jq -r '.[] | select(.evicted > 0) | .id'); do
  echo ""
  echo "  [AUTO-NOTIFY] 检查逐出策略 (白名单 W-03)..."

  # 获取当前配置
  CURRENT_POLICY=$(aliyun r-kvstore DescribeInstanceConfig \
    --RegionId "$REGION" \
    --InstanceId "$REDIS_ID" 2>/dev/null \
    | jq -r '.Config // empty' | grep -o '"maxmemory-policy":"[^"]*"' | cut -d'"' -f4)

  echo "  当前逐出策略: ${CURRENT_POLICY:-unknown}"

  # 如果是 noeviction（不逐出），改为 allkeys-lru 是标准的自愈操作
  if [ "$CURRENT_POLICY" = "noeviction" ] || [ -z "$CURRENT_POLICY" ]; then
    echo "  策略为 noeviction -> 内存满时写失败！"

    # [AUTO-NOTIFY] 自动修复
    UPDATE_RESULT=$(aliyun r-kvstore ModifyInstanceConfig \
      --RegionId "$REGION" \
      --InstanceId "$REDIS_ID" \
      --Config '{"maxmemory-policy":"allkeys-lru"}' 2>&1)

    if echo "$UPDATE_RESULT" | jq -e '.Success == true' >/dev/null 2>&1; then
      echo "  PASS [AUTO-NOTIFY] maxmemory-policy 已修改为 allkeys-lru"
      echo "  [AUDIT] whitelist_id=W-03 level=L1 resource=$REDIS_ID action=modify_maxmemory_policy"
    else
      echo "  [WARN] 自动修改失败: $UPDATE_RESULT"
      echo "  [SUGGESTED] 请手动修改逐出策略"
    fi
  elif [ "$CURRENT_POLICY" = "volatile-lru" ] || [ "$CURRENT_POLICY" = "allkeys-lru" ]; then
    echo "  PASS 逐出策略合理 (${CURRENT_POLICY})，无需变更"
  fi
done
```

#### Step 2.4: [SUGGESTED] 优化建议

```bash
# ── e) 综合优化建议 ──
for REDIS_ID in $(echo "$SUSPECT_REDIS" | jq -r '.[].id'); do
  MEM_PCT=$(echo "$INST" | jq -r '.mem_pct')

  echo ""
  echo "  ── 优化建议: $REDIS_ID ──"

  # 按严重度排序输出建议
  if [ "$(echo "$MEM_PCT > 85" | bc -l 2>/dev/null)" = "1" ]; then
    echo "  CRITICAL [P0] 内存使用率 ${MEM_PCT}% > 85% — 建议立即处理:"
    echo "      方案A: 升配 Redis 规格（最快最安全）"
    echo "        [SUGGESTED] aliyun r-kvstore ModifyInstanceSpec ..."
    echo "      方案B: 清理大 key 释放内存"
    echo "        [SUGGESTED] go run das_slow_query.go --action delete-big-keys ..."
    echo "      方案C: 增加应用层本地缓存（Caffeine/Guava），减少 Redis 压力"
  elif [ "$(echo "$MEM_PCT > 75" | bc -l 2>/dev/null)" = "1" ]; then
    echo "  WARNING [P1] 内存使用率 ${MEM_PCT}% > 75% — 建议纳入容量规划"
    echo "      监控内存趋势，如持续增长则升配或优化 key 设计"
  fi
done
```

### Phase 3: 报告

**Markdown:**

```markdown
═══════════════════════════════════════════════════════
  [PKG] Redis/Tair 缓存性能诊断报告
═══════════════════════════════════════════════════════
  报告ID: redis-perf-$CUSTOMER-$(date +%Y%m%dT%H%M%SZ)
  客户: $CUSTOMER | 区域: $REGION | 时间: $(date)
═══════════════════════════════════════════════════════

## [STATS] 总览

| 维度 | 结果 |
|------|------|
| 扫描实例 | ${REDIS_COUNT} |
| 可疑实例 | ${SUSPECT_COUNT} |
| DAS 缓存分析 | ${DAS_DONE:-N} 个 |
| 自动修复 (W-03) | ${W03_TRIGGERED:-0} 次 |

## [TARGET] 实例诊断详情

### ${REDIS_ID}
**状态**: 内存=${MEM_PCT}% | 逐出=${EVICTED} | 命中率=${HIT_RATE}%

**大 key TOP 5**:
1. [hash] order_cache -> 1.2GB / 850 万元素
2. [list] user_session -> 856MB / 200 万元素
3. [string] report_data_202606 -> 450MB

**优化建议**:
1. CRITICAL [P0] order_cache 是 hash 类型大 key，建议按日期分桶
2. WARNING [P1] user_session 可设置 TTL=86400 避免无限增长
3. ℹ️ 当前逐出策略已自动修复: noeviction -> allkeys-lru

═══════════════════════════════════════════════════════
  自动操作记录
═══════════════════════════════════════════════════════
| 时间 | 操作 | 资源 | 白名单 | 结果 |
|------|------|------|:------:|------|
| $(date) | 修改 maxmemory-policy | ${REDIS_ID} | W-03 | PASS allkeys-lru |
```

**JSON:**

```json
{
  "report_id": "redis-perf-${CUSTOMER}-$(date +%Y%m%dT%H%M%SZ)",
  "scenario": "redis_performance_diagnosis",
  "instances": [{
    "instance_id": "${REDIS_ID}",
    "memory_pct": ${MEM_PCT},
    "evicted_keys": ${EVICTED},
    "hit_rate": "${HIT_RATE}",
    "big_keys": [],
    "maxmemory_policy": "${CURRENT_POLICY}",
    "auto_actions": [{"whitelist_id": "W-03", "action": "modify_maxmemory_policy"}],
    "suggestions": []
  }]
}
```

---

## 3. 阈值速查

| 指标 | Warning | Critical | 说明 |
|------|:-------:|:--------:|------|
| 内存使用率 | > 75% | > 85% | 超过 85% OOM 风险高 |
| 逐出键数 (evicted_keys) | — | > 0 | 任何逐出都需关注 |
| 命中率 (HitRate) | < 90% | < 80% | 低于 80% 大量穿透到 DB |
| 连接数使用率 | > 70% | > 85% | 连接耗尽无法服务 |
| 内存碎片率 | > 1.5 | > 2.0 | 碎片超过 2 需重启或升配 |

---

## 4. 改进闭环

| 反馈来源 | 触发条件 | 改进动作 | 责任人 |
|----------|---------|---------|--------|
| 误报 | CMS 内存突刺触发但实际无问题 | 增加连续超过 5min 才触发 | Agent 维护者 |
| 漏报 | DAS 缓存分析失败但实际有大 key | 增加 redis-cli --bigkeys 回退 | Agent 维护者 |
| 误修复 | W-03 修改策略后效果不佳 | 增加 more-bit 等高级策略支持 | 运维负责人 |

---

## 5. Changelog

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 1.0.0 | 2026-06-07 | 初始版本 |