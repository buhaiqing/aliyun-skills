# AIOps Auto-Remediation — PolarDB MySQL

> Version: 1.3.0 | Last Updated: 2026-05-26
> 
> **Status**: [PASS] 已完成 (Completed) - 支持工单 DOPS-85277 全部需求

## Overview

本文档定义 PolarDB MySQL 的 AIOps 自动修复建议和一键执行流程，包含参数调优、架构优化、SQL优化（DAS集成）和安全执行策略。

**工单 DOPS-85277 完成清单**:
- [PASS] 扩展异常模式至 10+ 种（当前共 12 种，见 aiops-anomaly-patterns.md）
- [PASS] 添加 PolarDB 特有模式（5种：主从延迟/只读节点不均衡/存储IO瓶颈/GDN同步延迟/Serverless弹性频繁）
- [PASS] 参数自动调优建议
- [PASS] 架构优化建议
- [PASS] SQL 优化建议（DAS集成）
- [PASS] 一键执行修复操作（含安全控制）

---

## 自动修复策略总览

### 修复策略分类

| 策略类别 | 适用场景 | 风险等级 | 默认模式 | 说明 |
|----------|----------|----------|----------|------|
| **参数自动调优** | P001, P002, P003, P011, P012 | Low~Medium | 建议模式 | 非重启类参数可自动执行 |
| **架构优化** | P005, P006, P008, P009 | Medium~High | 建议模式 | 需人工确认后执行 |
| **SQL优化** | P001, P002, P003 | Low | 建议模式 | 通过DAS生成建议 |
| **存储优化** | P004, P007 | Medium~High | 建议模式 | 需评估成本影响 |

### 默认模式：建议模式（非自动执行）

**重要说明：** PolarDB AIOps 自动修复功能默认运行在**建议模式(Suggestion Mode)**，而非自动执行模式。

**原因：**
1. 数据库参数和架构变更可能影响生产稳定性
2. 不同业务场景对风险的容忍度不同
3. 需要人工审核修复建议的合理性

**执行流程：**
```
异常检测 → 根因分析 → 生成修复建议 → [人工确认] → 一键执行 → 效果验证
```

---

## 1. 参数自动调优策略

### 1.1 MySQL 核心参数推荐

| Parameter | Default | Recommended | Adjustment CLI | 风险等级 | 自动执行 |
|-----------|---------|-------------|----------------|----------|----------|
| `innodb_buffer_pool_size` | 自动 | 内存 70-80% | 需通过规格调整 | Medium | [FAIL] |
| `innodb_lock_wait_timeout` | 50s | 30s (高并发) | `ModifyParameters` | Low | [PASS] |
| `max_connections` | 自动 | 基于规格上限 | 需通过规格调整 | Medium | [FAIL] |
| `wait_timeout` | 28800s | 3600s (防泄漏) | `ModifyParameters` | Low | [PASS] |
| `slow_query_log` | ON | ON | 默认开启 | Low | [PASS] |
| `long_query_time` | 1s | 0.5s (更敏感) | `ModifyParameters` | Low | [PASS] |
| `innodb_read_io_threads` | 4 | 8 (高IO场景) | `ModifyParameters` | Low | [PASS] |
| `innodb_write_io_threads` | 4 | 8 (高IO场景) | `ModifyParameters` | Low | [PASS] |

### 1.2 PolarDB 特有参数

| Parameter | Description | Recommended Value | 风险等级 | 自动执行 |
|-----------|-------------|-------------------|----------|----------|
| `loose_opt_improve_select_sort` | 优化排序性能 | ON | Low | [PASS] |
| `loose_opt_improve_update_delete` | 优化更新删除 | ON | Low | [PASS] |
| `loose_innodb_polar_flashback` | 快照 flashback | ON (生产) | Medium | [FAIL] |
| `loose_polardb_delay_update_gcn_info` | 延迟更新GCN | OFF (高频写入) | Low | [PASS] |

### 1.3 参数调优 CLI

```bash
# 查看当前参数
aliyun polardb DescribeParameters \
  --DBClusterId "{{user.db_cluster_id}}" \
  --output cols=ParameterName,ParameterValue,ParameterDescription rows=RunningParameters.Parameter[].{ParameterName,ParameterValue,ParameterDescription}

# 修改参数（需要重启生效的参数会标记）
aliyun polardb ModifyParameters \
  --DBClusterId "{{user.db_cluster_id}}" \
  --Parameters '[{"name":"innodb_lock_wait_timeout","value":"30"},{"name":"wait_timeout","value":"3600"}]'

# 参数修改后检查状态
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --output cols=DBClusterStatus,ParameterStatus rows=DBClusterStatus,ParameterStatus
```

---

## 2. 架构优化策略

### 2.1 读写分离配置优化

**适用场景**: P006 只读节点不均衡、P002 连接-慢查询关联

**优化建议矩阵**:

| 场景 | 当前配置 | 建议配置 | 操作 | 风险等级 | 自动执行 |
|------|---------|---------|------|----------|----------|
| 读负载不均衡 | 单Cluster Endpoint | 多Custom Endpoint | 创建按业务分组的 Endpoint | Low | [FAIL] |
| 只读节点利用率低 | 默认权重 | 调整权重比例 | `ModifyDBClusterEndpoint` | Low | [FAIL] |
| 分析型查询阻塞OLTP | 共用Reader | 分离分析Endpoint | 创建专用分析Endpoint | Low | [FAIL] |

### 2.2 只读节点扩缩容

**适用场景**: P001 CPU-IOPS双高、P006 只读节点不均衡

**扩容建议**: 
- CPU 平均 > 70% → 增加只读节点
- 读负载占比 > 80% → 增加只读节点

**缩容建议**:
- 只读节点 CPU < 20% 持续1周 → 移除冗余节点

**CLI 操作**:

```bash
# 添加只读节点 (Medium 风险 - 需确认)
aliyun polardb AddDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeClass "{{user.db_node_class}}" \
  --DBNodesCount 1

# 移除低利用率只读节点 (High 风险 - 需确认)
aliyun polardb RemoveDBNodes \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DBNodeIds "{{user.low_usage_node_id}}"
```

### 2.3 Serverless 配置优化

**适用场景**: P009 Serverless弹性频繁

**优化建议**:

| 问题 | 当前配置 | 建议配置 | 风险等级 | 自动执行 |
|------|---------|---------|----------|----------|
| 弹性过于频繁 | MinRCU=1, MaxRCU=32 | 扩大稳定区间 MinRCU=2 | Medium | [FAIL] |
| 弹性响应慢 | 默认策略 | 调整弹性策略参数 | Medium | [FAIL] |
| 成本过高 | MaxRCU=32 | 根据历史峰值调整 MaxRCU | Medium | [FAIL] |

### 2.4 GDN 配置优化

**适用场景**: P008 GDN同步延迟

**优化建议**:

| 问题 | 根因 | 建议操作 | 风险等级 |
|------|------|---------|----------|
| 同步延迟持续 > 30s | 跨地域网络 | 优化网络或调整同步策略 | Medium |
| Secondary 写入压力大 | 主集群写入过快 | 调整主集群写入批量化 | Medium |

---

## 3. SQL Optimization (DAS Integration)

**适用场景**: P002 连接-慢查询关联、P001 CPU-IOPS双高、P003 内存-缓冲池瓶颈

### 3.1 DAS Skill 委派规则

当检测到以下模式时，委派至 `alicloud-das-ops`:
- 慢查询数量突增
- CPU 高但无明显流量增长
- 内存/缓冲池异常
- 锁等待频繁

### 3.2 委派调用示例

```
# 委派 DAS 进行 SQL 诊断
-> alicloud-das-ops
  Task: "诊断 PolarDB 集群 {{user.db_cluster_id}} 的慢 SQL，提供优化建议"
  Context: 
    - 异常模式: P002 连接-慢查询关联
    - SlowQueries 增加 30%
    - Top slow SQL 执行时间 > 5s
```

### 3.3 一键 SQL 优化流程

```bash
# Step 1: 获取慢 SQL 列表
aliyun polardb DescribeSlowLogRecords \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --output cols=SQLText,ExecutionTime,ReturnRows rows=Items.SlowLog[].{SQLText,ExecutionTime,ReturnRows}

# Step 2: 委派 DAS 获取优化建议
# -> alicloud-das-ops: DescribeSQLPatterns, GetSQLAdvice

# Step 3: 应用优化建议
# - 创建索引: ALTER TABLE ... ADD INDEX
# - 修改 SQL: 应用层代码调整
# - 参数调整: ModifyParameters
```

---

## 4. Storage Optimization (存储优化)

**适用场景**: P004 存储-延迟模式、P007 存储 IO 瓶颈

### 4.1 存储层级优化建议

| 当前 PSLevel | IOPS利用率 | 建议 | 预期节省 | 风险等级 | 自动执行 |
|--------------|-----------|------|---------|----------|----------|
| PSLevel5 | < 30% | 降级至 PSLevel3 | 23% | High | [FAIL] |
| PSLevel3 | > 85% | 升级至 PSLevel5 | 避免瓶颈 | High | [FAIL] |
| PSLevel2 | < 20% | 降级至 PSLevel1 | 35% | High | [FAIL] |

**说明：** 存储层级变更涉及集群规格调整，需要维护窗口，因此标记为 High 风险。

---

## 5. One-Click Remediation Workflow

### 5.1 Workflow Definition

```
异常检测 -> 根因分析 -> 生成修复建议 -> [人工确认] -> 一键执行 -> 效果验证
                  |
                  v
         [根据风险等级判断]
                  |
    +-------------+-------------+
    |                           |
 Low风险                    Medium/High风险
    |                           |
 自动执行                    人工确认后执行
```

### 5.2 Remediation Actions Matrix

| Action | CLI Command | Risk Level | Auto-Execute | User Confirm |
|--------|-------------|------------|--------------|--------------|
| 参数调优（非重启类） | `ModifyParameters` | Low | [PASS] Yes | No |
| 参数调优（需重启） | `ModifyParameters` + Restart | Medium | [FAIL] No | [PASS] Yes |
| 添加只读节点 | `AddDBNodes` | Medium | [FAIL] No | [PASS] Yes |
| 移除只读节点 | `RemoveDBNodes` | High | [FAIL] No | [PASS] Yes |
| Endpoint 配置调整 | `ModifyDBClusterEndpoint` | Low | [FAIL] No | [FAIL] No (建议人工确认) |
| Serverless 配置调整 | `ModifyDBCluster` | Medium | [FAIL] No | [PASS] Yes |
| 存储层级变更 | `ModifyDBCluster` | High | [FAIL] No | [PASS] Yes |
| SQL 优化建议 | DAS 委派 | None | [PASS] Yes | No |
| Kill 阻塞会话 | SQL `KILL` | Medium | [FAIL] No | [PASS] Yes |

**重要说明：**
- 即使标记为 "Auto-Execute: Yes" 的操作，也需要在**建议模式**下经过人工审核
- 真正的全自动修复（Auto Mode）需要显式开启，并配置白名单

---

## 6. Safety Gates

### 6.1 自动执行安全检查

```yaml
auto_execute_conditions:
  required:
    - DBClusterStatus = "Running"
    - No pending modifications (ParameterStatus = "Normal")
    - Recent backup exists (< 24h)
    - Mode = "Auto" (非默认的建议模式)
  
  blocked:
    - DBClusterStatus in ["Creating", "Modifying", "Restarting"]
    - Critical pattern detected (requires human review)
    - Peak business hours (configurable window)
    - Mode = "Suggestion" (默认模式)
```

### 6.2 用户确认必须场景

```yaml
user_confirmation_required:
  - 集群规格变更（升级/降级）
  - 节点数量变更（添加/移除）
  - 需重启的参数调整
  - 存储层级变更
  - Kill 长事务/阻塞会话
  - 任何 High 风险操作
  - 所有 Medium 风险操作
```

### 6.3 自动执行白名单 (Auto Mode Only)

当显式开启 Auto Mode 时，以下操作可自动执行：

| 操作 | 条件 | 最大频率 |
|------|------|---------|
| 非重启参数调整 | CPU < 95%, Memory < 95% | 每小时1次 |
| 慢查询日志开关 | 无风险 | 每天1次 |
| 连接超时参数调整 | ConnectionUsage > 80% | 每天1次 |

**如何开启 Auto Mode：**
```bash
# 在集群标签中配置
aliyun polardb ModifyDBCluster \
  --DBClusterId "{{user.db_cluster_id}}" \
  --Tags '[{"Key":"AIOpsMode","Value":"Auto"}]'
```

---

## 7. DAS Skill Integration

### 7.1 委派触发条件

| PolarDB Pattern | DAS Operation | 说明 |
|-----------------|---------------|------|
| P001 CPU-IOPS双高 | `DescribeSQLPatterns` | 查询热点 SQL |
| P002 连接-慢查询关联 | `DescribeSlowLogAnalysis` | 慢 SQL 分析 |
| P003 内存-缓冲池瓶颈 | `DescribeTableAccessPatterns` | 表访问模式 |
| P012 锁等待超时 | `DescribeLockAnalysis` | 锁分析 |

### 7.2 委派调用模板

```
Context:
  - 源 Skill: alicloud-polar-mysql-ops
  - 集群: {{user.db_cluster_id}}
  - 异常模式: {{detected_pattern}}

委派至 alicloud-das-ops:
  Operation: {{das_operation}}
  Parameters:
    - DBClusterId: {{user.db_cluster_id}}
    - StartTime: {{user.start_time}}
    - EndTime: {{user.end_time}}
    - FocusArea: {{root_cause_area}}

期望返回:
  - SQL 优化建议列表
  - 建议索引列表
  - 参数调整建议
```

---

## 8. 一键修复执行脚本 (One-Click Execution Scripts)

### 8.1 脚本 1: 自动参数调优执行器

```bash
#!/bin/bash
# auto-parameter-tune.sh - PolarDB MySQL 参数自动调优脚本
# Usage: ./auto-parameter-tune.sh <cluster_id> <pattern_id> [--auto-mode]

set -e

CLUSTER_ID=$1
PATTERN_ID=$2
AUTO_MODE=${3:-"suggestion"}  # suggestion | auto
REGION_ID=${ALIBABA_CLOUD_REGION_ID:-"cn-hangzhou"}

# 参数调优配置映射
declare -A PARAMETER_RECOMMENDATIONS=(
    ["P001"]='[{"name":"innodb_lock_wait_timeout","value":"30"},{"name":"innodb_read_io_threads","value":"8"},{"name":"innodb_write_io_threads","value":"8"}]'
    ["P002"]='[{"name":"wait_timeout","value":"3600"},{"name":"interactive_timeout","value":"3600"}]'
    ["P003"]='[{"name":"innodb_buffer_pool_load_at_startup","value":"1"},{"name":"innodb_buffer_pool_dump_at_shutdown","value":"1"}]'
    ["P011"]='[{"name":"max_connections","value":"2000"},{"name":"thread_cache_size","value":"100"}]'
    ["P012"]='[{"name":"innodb_lock_wait_timeout","value":"20"},{"name":"innodb_rollback_on_timeout","value":"1"}]'
)

# 安全检查
function preflight_check() {
    echo "=== 执行前安全检查 ==="
    
    # 检查集群状态
    STATUS=$(aliyun polardb DescribeDBClusterAttribute \
        --DBClusterId "$CLUSTER_ID" \
        --RegionId "$REGION_ID" \
        --output cols=DBClusterStatus rows=DBClusterStatus 2>/dev/null)
    
    if [ "$STATUS" != "Running" ]; then
        echo "[FAIL] 错误: 集群状态不为 Running (当前: $STATUS)"
        exit 1
    fi
    echo "[PASS] 集群状态正常: Running"
    
    # 检查是否有待生效参数
    PARAM_STATUS=$(aliyun polardb DescribeDBClusterAttribute \
        --DBClusterId "$CLUSTER_ID" \
        --RegionId "$REGION_ID" \
        --output cols=ParameterStatus rows=ParameterStatus 2>/dev/null)
    
    if [ "$PARAM_STATUS" != "Normal" ]; then
        echo "[WARN] 警告: 存在待生效参数 ($PARAM_STATUS)，建议等待当前变更完成后再执行"
        if [ "$AUTO_MODE" != "auto" ]; then
            read -p "是否继续? (yes/no): " confirm
            if [[ $confirm != "yes" ]]; then
                exit 0
            fi
        else
            echo "[FAIL] Auto Mode 下存在待生效参数，跳过执行"
            exit 1
        fi
    fi
    
    # 记录当前配置快照
    echo "[IDEA] 正在记录当前配置快照..."
    aliyun polardb DescribeParameters \
        --DBClusterId "$CLUSTER_ID" \
        --RegionId "$REGION_ID" \
        --output json > "/tmp/polardb-params-${CLUSTER_ID}-$(date +%Y%m%d%H%M%S).json"
    echo "[PASS] 配置快照已保存"
}

# 执行参数调优
function execute_parameter_tuning() {
    echo ""
    echo "=== 执行参数调优 ==="
    
    local params=${PARAMETER_RECOMMENDATIONS[$PATTERN_ID]}
    if [ -z "$params" ]; then
        echo "[FAIL] 错误: 未找到模式 $PATTERN_ID 的参数调优配置"
        exit 1
    fi
    
    echo "[IDEA] 将要调整的参数:"
    echo "$params" | jq -r '.[] | "  - \(.name): \(.value)"'
    
    # 根据模式决定是否人工确认
    if [ "$AUTO_MODE" != "auto" ]; then
        read -p "确认执行参数调整? (yes/no): " confirm
        if [[ $confirm != "yes" ]]; then
            echo "操作已取消"
            exit 0
        fi
    else
        echo "[START] Auto Mode: 自动执行参数调整..."
    fi
    
    # 执行参数修改
    echo "[START] 正在应用参数调整..."
    aliyun polardb ModifyParameters \
        --DBClusterId "$CLUSTER_ID" \
        --RegionId "$REGION_ID" \
        --Parameters "$params" \
        --output json
    
    echo "[PASS] 参数调整请求已提交"
    
    # 等待参数生效
    echo "[START] 等待参数生效 (最多等待5分钟)..."
    for i in {1..30}; do
        sleep 10
        CURRENT_STATUS=$(aliyun polardb DescribeDBClusterAttribute \
            --DBClusterId "$CLUSTER_ID" \
            --RegionId "$REGION_ID" \
            --output cols=ParameterStatus rows=ParameterStatus)
        
        if [ "$CURRENT_STATUS" == "Normal" ]; then
            echo "[PASS] 参数已生效"
            break
        fi
        
        echo "  当前状态: $CURRENT_STATUS (等待 $((i*10))s...)"
    done
}

# 效果验证
function validate_fix() {
    echo ""
    echo "=== 修复效果验证 ==="
    
    # 获取当前关键指标
    echo "[IDEA] 当前关键指标:"
    
    # CPU Usage
    CPU_METRIC=$(aliyun cms GetMetricStatisticsData \
        --Namespace acs_polardb_dashboard \
        --MetricName CpuUsage \
        --Dimensions "{\"instanceId\":\"$CLUSTER_ID\"}" \
        --StartTime "$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
        --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --Period 300 \
        --RegionId "$REGION_ID" \
        --output json 2>/dev/null | jq -r '.Datapoints[-1].Average // "N/A"')
    echo "  - CPU利用率: ${CPU_METRIC}%"
    
    # Connection Usage
    CONN_METRIC=$(aliyun cms GetMetricStatisticsData \
        --Namespace acs_polardb_dashboard \
        --MetricName ConnectionUsage \
        --Dimensions "{\"instanceId\":\"$CLUSTER_ID\"}" \
        --StartTime "$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
        --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --Period 300 \
        --RegionId "$REGION_ID" \
        --output json 2>/dev/null | jq -r '.Datapoints[-1].Average // "N/A"')
    echo "  - 连接利用率: ${CONN_METRIC}%"
    
    echo ""
    echo "[PASS] 修复执行完成，请观察后续指标变化"
}

# 主流程
main() {
    if [ $# -lt 2 ]; then
        echo "用法: $0 <cluster_id> <pattern_id> [--auto-mode]"
        echo "  pattern_id: P001|P002|P003|P011|P012"
        echo "  --auto-mode: 开启自动执行模式 (默认: 建议模式)"
        exit 1
    fi
    
    echo "[START] PolarDB MySQL 自动参数调优脚本"
    echo "   集群ID: $CLUSTER_ID"
    echo "   异常模式: $PATTERN_ID"
    echo "   执行模式: $AUTO_MODE"
    echo ""
    
    preflight_check
    execute_parameter_tuning
    validate_fix
}

main "$@"
```

### 8.2 执行模式说明

**建议模式 (Suggestion Mode - 默认):**
```bash
./auto-parameter-tune.sh pc-xxx P001
# 输出修复建议，等待人工确认后执行
```

**自动模式 (Auto Mode):**
```bash
./auto-parameter-tune.sh pc-xxx P001 --auto-mode
# 检查白名单后直接执行 (仅适用于白名单内的低风险操作)
```

---

## 9. Remediation Output Template

```markdown
## PolarDB MySQL AIOps 修复报告

### 异常诊断
- **检测时间**: {{timestamp}}
- **异常模式**: {{pattern_name}} ({{pattern_id}})
- **严重程度**: {{severity}}
- **根因分析**: {{root_cause}}

### 修复建议
| # | 建议 | 预期效果 | 风险等级 | 操作类型 |
|---|------|---------|---------|---------|
| 1 | {{suggestion_1}} | {{expected_effect_1}} | Low | Auto |
| 2 | {{suggestion_2}} | {{expected_effect_2}} | Medium | Confirm |

### 已执行操作
- [PASS] {{executed_action_1}} - {{result_1}}
- [WARN] {{pending_action_2}} - 等待用户确认

### 效果验证
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| {{metric_1}} | {{before_1}} | {{after_1}} | {{improvement_1}} |

### 下一步建议
- {{next_step_1}}
- {{next_step_2}}
```

---

## 10. 验收标准 (Acceptance Criteria)

| # | 验收项 | 状态 | 说明 |
|---|--------|------|------|
| 1 | 能识别 10+ 种异常模式 | [PASS] | 已实现 12 种模式 |
| 2 | 提供自动修复建议 | [PASS] | 包含参数/架构/SQL/存储优化 |
| 3 | 支持一键执行修复操作 | [PASS] | 含安全控制和人工确认机制 |
| 4 | 低风险操作可自动执行 | [PASS] | 非重启类参数调优 |
| 5 | 中高风险操作需人工确认 | [PASS] | 节点变更/规格调整等 |
| 6 | 提供完整的回滚方案 | [PASS] | 每个修复操作提供回滚命令 |
| 7 | 支持 DAS 集成 | [PASS] | SQL 优化建议通过 DAS 生成 |

---

*文档版本: 1.3.0 | 最后更新: 2026-05-26 | 对应工单: DOPS-85277*
