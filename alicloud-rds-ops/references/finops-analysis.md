# FinOps 成本优化 — Alibaba Cloud RDS

> **Purpose:** 实例利用率分析、资源浪费识别、预留实例优化、成本预警，实现 RDS 成本可见、可控、可优化。

---

## 1. 实例利用率评估

### 1.1 低利用率识别标准

| Utilization Level | CPU Avg (7d) | IOPS Avg (7d) | Connections Avg (7d) | Savings Potential | Recommended Action |
|-------------------|--------------|---------------|----------------------|-------------------|-------------------|
| **严重浪费** | < 10% | < 50% | < 20% | 60-80% | 降级 2档规格 或 合并实例 |
| **轻度浪费** | 10-30% | 50-70% | 20-40% | 30-50% | 降级 1档规格 |
| **正常利用** | 30-70% | 70-85% | 40-80% | 0% | 保持，监控 |
| **利用率吃紧** | 70-85% | 85-95% | 80-95% | — | 准备升级计划 |
| **过载风险** | > 85% | > 95% | > 95% | — | 紧急升级 |

### 1.2 FinOps Cruise Workflow

```bash
#!/bin/bash
# RDS FinOps 利用率审计
REGION="{{user.region}}"

echo "=== RDS FinOps Utilization Audit ==="
echo ""

# 1. 获取所有实例列表
echo "[Step 1] Fetching all RDS instances..."
INSTANCES=$(aliyun rds DescribeDBInstances --RegionId "$REGION" \
  --output cols=DBInstanceId,DBInstanceClass,DBInstanceStorage,Engine,EngineVersion rows=Items.DBInstance[].{DBInstanceId,DBInstanceClass,DBInstanceStorage,Engine,EngineVersion})

echo "$INSTANCES"
echo ""

# 2. 遍历每个实例计算利用率
echo "[Step 2] Calculating utilization for each instance..."

# 时间窗口：过去 7 天
if date -v-7d +%Y-%m-%dT%H:%M:%SZ >/dev/null 2>&1; then
  START_TIME="$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)"
else
  START_TIME="$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)"
fi
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# 对每个实例获取性能数据
for INSTANCE_ID in $(echo "$INSTANCES" | awk '{print $1}'); do
  echo "--- Instance: $INSTANCE_ID ---"
  
  # CPU 使用率
  CPU_DATA=$(aliyun rds DescribeDBInstancePerformance \
    --DBInstanceId "$INSTANCE_ID" --RegionId "$REGION" \
    --Key MySQL_CPUUsage --StartTime "$START_TIME" --EndTime "$END_TIME" \
    --output cols=Value rows=PerformanceKeys.PerformanceKey[0].Values.PerformanceValue[])
  
  # 计算 CPU 平均值（需要处理多值）
  # 实际实现建议用 jq 或 Python 处理
  
  # 存储使用率
  STORAGE_USAGE=$(aliyun rds DescribeResourceUsage \
    --DBInstanceId "$INSTANCE_ID" --RegionId "$REGION" \
    --output cols=DiskUsed rows=DiskUsed)
  
  # 存储容量
  STORAGE_CAP=$(aliyun rds DescribeDBInstanceAttribute \
    --DBInstanceId "$INSTANCE_ID" --RegionId "$REGION" \
    --output cols=DBInstanceStorage rows=Items.DBInstanceAttribute[0].DBInstanceStorage)
  
  echo "CPU Data: $CPU_DATA"
  echo "Storage Used: $STORAGE_USAGE MB / Capacity: $STORAGE_CAP GB"
  echo ""
done

# 3. 生成利用率报告
echo "[Step 3] Generating utilization report..."
# 建议用 Python/JMESPath 处理数据并生成报告

echo "=== FinOps Audit Complete ==="
```

### 1.3 利用率计算公式

```python
# CPU 利用率计算
cpu_avg_7d = sum(cpu_values) / len(cpu_values)

# 存储利用率计算
storage_utilization = DiskUsed / (DBInstanceStorage * 1024) * 100  # MB to GB

# IOPS 利用率计算
iops_avg_7d = sum(iops_values) / len(iops_values)
iops_utilization = iops_avg_7d / MaxIOPS * 100

# 连接利用率计算
conn_avg_7d = sum(connections_values) / len(connections_values)
conn_utilization = conn_avg_7d / max_connections * 100

# 综合利用率
overall_utilization = (cpu_avg_7d + iops_utilization + conn_utilization) / 3
```

---

## 2. 存储成本优化

### 2.1 存储使用分析

| Check | Threshold | Issue | Recommendation |
|-------|-----------|-------|----------------|
| 存储利用率 < 30% | < 30% | 存储浪费 | 缩容存储至实际使用量的 2倍 |
| 存储 > 数据量 2倍 | > 200% | 空间浪费 | 检查表碎片，执行 OPTIMIZE TABLE |
| LogSize > 20% of total | > 20% | 日志占用过高 | 检查 binlog 保留期，清理日志 |
| BackupSize 增长快 | 突增 | 备份成本增加 | 评估备份策略，减少保留期 |

### 2.2 存储成本检查 CLI

```bash
#!/bin/bash
# RDS 存储成本分析
DB_INSTANCE_ID="{{user.db_instance_id}}"
REGION="{{user.region}}"

echo "=== RDS Storage Cost Analysis ==="

# 获取资源使用详情
aliyun rds DescribeResourceUsage --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION"

# 计算存储利用率
DISK_USED=$(aliyun rds DescribeResourceUsage --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --output cols=DiskUsed rows=DiskUsed)

DATA_SIZE=$(aliyun rds DescribeResourceUsage --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --output cols=DataSize rows=DataSize)

LOG_SIZE=$(aliyun rds DescribeResourceUsage --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --output cols=LogSize rows=LogSize)

STORAGE_CAP=$(aliyun rds DescribeDBInstanceAttribute --DBInstanceId "$DB_INSTANCE_ID" --RegionId "$REGION" \
  --output cols=DBInstanceStorage rows=Items.DBInstanceAttribute[0].DBInstanceStorage)

echo "Disk Used: ${DISK_USED} MB"
echo "Data Size: ${DATA_SIZE} MB"
echo "Log Size: ${LOG_SIZE} MB"
echo "Storage Capacity: ${STORAGE_CAP} GB"

# 计算利用率
UTIL=$(echo "$DISK_USED / ($STORAGE_CAP * 1024) * 100" | bc)
echo "Storage Utilization: ${UTIL}%"

# 数据/存储比率
DATA_RATIO=$(echo "$DATA_SIZE / ($STORAGE_CAP * 1024) * 100" | bc)
echo "Data/Storage Ratio: ${DATA_RATIO}%"

# 判断是否浪费
if [ "$UTIL" -lt 30 ]; then
  echo "⚠️ WARNING: Storage utilization < 30%, consider shrinking storage."
fi

if [ "$DATA_RATIO" -lt 50 ]; then
  echo "⚠️ WARNING: Data ratio < 50%, check for fragmentation or unnecessary logs."
fi
```

### 2.3 存储类型成本对比

| Storage Type | Performance | Cost Ratio | Use Case |
|--------------|-------------|------------|----------|
| **cloud_ssd** | Standard | 1.0x | 开发/测试环境 |
| **cloud_essd** | Enhanced | 1.3-1.5x | 生产环境（推荐） |
| **local_ssd** | Highest | 1.5-2.0x | 高性能 OLTP |

**优化建议**:
- 开发环境 → SSD
- 生产环境 → ESSD PL1
- 高性能需求 → ESSD PL2/PL3 或 Local SSD

---

## 3. 预留实例优化

### 3.1 预留建议算法

| Running Duration | Stability | Recommendation | Savings |
|------------------|-----------|----------------|---------|
| < 30 days | Unstable | 按量付费 | N/A |
| 30-180 days | Moderately stable | 包月 | 30-40% |
| > 180 days | Stable | 包年 | 60-80% |
| > 365 days | Highly stable | 包3年 | 70-85% |

### 3.2 成本计算公式

```python
# 按量付费月成本
monthly_on_demand = instance_hourly_rate * 24 * 30

# 包年成本
yearly_reserved = instance_yearly_price

# 月度预留成本
monthly_reserved = yearly_reserved / 12

# 节省比例
savings_ratio = (monthly_on_demand - monthly_reserved) / monthly_on_demand * 100

# 实际计算示例
# MySQL rds.mysql.s2.large
# 按量: ¥0.8/小时 × 24 × 30 = ¥576/月
# 包年: ¥2400/年 = ¥200/月
# 节省: (576 - 200) / 576 = 65%
```

### 3.3 预留覆盖率分析

```bash
#!/bin/bash
# RDS 预留覆盖率分析
REGION="{{user.region}}"

echo "=== RDS Reserved Instance Coverage Analysis ==="

# 获取所有实例及其付费类型
aliyun rds DescribeDBInstances --RegionId "$REGION" \
  --output cols=DBInstanceId,DBInstanceClass,PayType rows=Items.DBInstance[].{DBInstanceId,DBInstanceClass,PayType}

# 计算预留覆盖率
# Postpaid = 按量付费 (需优化)
# Prepaid = 包年包月 (已预留)

echo ""
echo "Coverage Calculation:"
echo "- Total Instances: N"
echo "- Prepaid Instances: M"
echo "- Coverage Rate: M/N * 100%"
echo ""
echo "Recommendation:"
echo "- If coverage < 50%: Increase reserved instances"
echo "- If coverage > 80%: Good optimization"
```

### 3.4 预留即将到期预警

| Days to Expiry | Alert Level | Action |
|-----------------|-------------|--------|
| 30 days | P2 | 准备续费决策 |
| 14 days | P1 | 发起续费流程 |
| 7 days | P0 | 紧急续费或转为按量 |
| Expired | Critical | 实例可能被锁定 |

---

## 4. 资源浪费识别

### 4.1 闲置实例检测

| Detection Rule | Condition | Confidence | Action |
|----------------|-----------|------------|--------|
| 无连接实例 | Connections_avg_7d = 0 | 100% | 归档或删除 |
| 极低 CPU | CPU_avg_30d < 5% | 95% | 降级或删除 |
| 无活跃数据库 | DescribeDatabases = empty | 100% | 删除实例 |
| 开发环境闲置 | Tag: env=dev + CPU < 10% | 90% | 停止或降级 |

### 4.2 低连接利用率检测

```bash
#!/bin/bash
# 低连接利用率检测
DB_INSTANCE_ID="{{user.db_instance_id}}"

# 获取 max_connections
MAX_CONN=$(aliyun rds DescribeParameters --DBInstanceId "$DB_INSTANCE_ID" \
  --output cols=ParameterValue rows=RunningParameters.DBInstanceParameter[?ParameterName=='max_connections'].ParameterValue)

# 获取平均连接数（过去 7 天）
# 需要处理 DescribeDBInstancePerformance 返回的多值数据

# 计算利用率
CONN_UTIL=$(echo "$AVG_CONN / $MAX_CONN * 100" | bc)

if [ "$CONN_UTIL" -lt 20 ]; then
  echo "⚠️ Low connection utilization: ${CONN_UTIL}%"
  echo "Recommendation: Reduce max_connections or downgrade instance"
fi
```

### 4.3 低 IOPS 利用率检测

| IOPS Avg (7d) | Max IOPS | Utilization | Recommendation |
|---------------|----------|-------------|----------------|
| < 100 | 1000+ | < 10% | 严重浪费，降级存储类型 |
| 100-300 | 1000+ | 10-30% | 轻度浪费，评估需求 |
| 300-700 | 1000+ | 30-70% | 正常使用 |
| > 700 | 1000+ | > 70% | 需监控升级 |

---

## 5. 成本预警规则

### 5.1 月度成本预警

```json
{
  "RuleName": "RDS-Monthly-Cost-Budget",
  "Metric": "MonthlyRDSCost",
  "Namespace": "acs_billing",
  "Thresholds": [
    {"Level": "P2", "Threshold": "Budget * 0.8", "Action": "Review report"},
    {"Level": "P1", "Threshold": "Budget * 1.0", "Action": "Cost optimization"},
    {"Level": "P0", "Threshold": "Budget * 1.5", "Action": "Emergency review"}
  ],
  "ContactGroups": ["finops-team"]
}
```

### 5.2 单实例成本异常预警

```json
{
  "RuleName": "RDS-Instance-Cost-Anomaly",
  "Metric": "InstanceDailyCost",
  "AnomalyDetection": {
    "Method": "BaselineDeviation",
    "BaselineWindow": "30 days",
    "Threshold": "3σ"
  },
  "Action": "GenerateCostAnalysisReport"
}
```

### 5.3 预留到期预警

```json
{
  "RuleName": "RDS-Reserved-Expiry",
  "Metric": "PrepaidInstanceExpiryDays",
  "Thresholds": [
    {"Level": "P2", "Threshold": 30, "Action": "Prepare renewal"},
    {"Level": "P1", "Threshold": 14, "Action": "Initiate renewal"},
    {"Level": "P0", "Threshold": 7, "Action": "Emergency renewal"}
  ]
}
```

---

## 6. 节省计算方法

### 6.1 降级节省计算

```python
# 降级节省公式
current_monthly_cost = current_instance_class_rate * 24 * 30
target_monthly_cost = target_instance_class_rate * 24 * 30
downgrade_savings = current_monthly_cost - target_monthly_cost
downgrade_savings_ratio = downgrade_savings / current_monthly_cost * 100

# 示例
# Current: rds.mysql.s3.xlarge (¥2.0/hour)
# Target: rds.mysql.s2.large (¥0.8/hour)
# Savings = (2.0 - 0.8) × 24 × 30 = ¥864/月 = 60%
```

### 6.2 预留节省计算

```python
# 预留节省公式
on_demand_annual_cost = hourly_rate * 24 * 365
reserved_annual_cost = yearly_reserved_price
reserved_savings = on_demand_annual_cost - reserved_annual_cost
reserved_savings_ratio = reserved_savings / on_demand_annual_cost * 100

# 示例
# Hourly: ¥2.0/hour
# On-demand annual: ¥2.0 × 24 × 365 = ¥17,520
# Reserved annual: ¥4,800 (包年价格)
# Savings = ¥17,520 - ¥4,800 = ¥12,720/年 = 72%
```

### 6.3 合计节省潜力

```python
# 合计节省潜力
total_savings_potential = (
    sum(downgrade_savings for all wasteful_instances) +
    sum(reserved_savings for all convertible_instances) +
    sum(storage_savings for all over_provisioned_storage) +
    sum(deletion_savings for all idle_instances)
)

# 输出节省报告
print(f"降级节省潜力: ¥{downgrade_total}/月")
print(f"预留节省潜力: ¥{reserved_total}/年")
print(f"存储节省潜力: ¥{storage_total}/月")
print(f"闲置实例删除节省: ¥{idle_total}/月")
print(f"合计节省潜力: ¥{total_savings_potential}/月")
```

---

## 7. FinOps 工作流触发词

| User Input | Workflow | Output |
|------------|----------|--------|
| "分析 RDS 成本" | Full FinOps Audit | §1 + §2 + §3 + §6 |
| "检查利用率" | Utilization Audit | §1 |
| "识别浪费实例" | Waste Detection | §4 |
| "预留实例建议" | Reserved Analysis | §3 |
| "存储成本优化" | Storage Analysis | §2 |
| "成本预警配置" | Cost Alert Setup | §5 |
| "计算节省潜力" | Savings Calculation | §6 |

---

## 8. FinOps Agent 执行指南

### 8.1 FinOps Cruise 执行顺序

| Step | Operation | Purpose | Output |
|------|-----------|---------|--------|
| 1 | DescribeDBInstances | 获取实例列表 | 实例 ID + 规格 + 付费类型 |
| 2 | DescribeDBInstancePerformance | 获取 7 天性能数据 | CPU/IOPS/Connections 趋势 |
| 3 | DescribeResourceUsage | 获取存储数据 | DiskUsed/DataSize/LogSize |
| 4 | Calculate Utilization | 计算利用率 | 每实例利用率百分比 |
| 5 | Identify Waste | 识别浪费 | 低利用率实例列表 |
| 6 | Calculate Savings | 计算节省 | 潜在节省金额 |
| 7 | Generate Report | 生成报告 | FinOps 优化建议报告 |

### 8.2 FinOps 报告模板

```markdown
## RDS FinOps 成本优化报告

### 执行摘要
- 分析实例数: {{total_instances}}
- 严重浪费实例: {{critical_waste_count}} (节省潜力: ¥{{critical_savings}}/月)
- 轻度浪费实例: {{light_waste_count}} (节省潜力: ¥{{light_savings}}/月)
- 预留覆盖率: {{reserved_coverage}}%
- 合计节省潜力: ¥{{total_savings}}/月

### 低利用率实例详情

| Instance ID | Class | CPU Avg | IOPS Avg | Storage Util | Savings | Recommendation |
|-------------|-------|---------|----------|--------------|---------|----------------|
| {{instance_1}} | {{class}} | {{cpu}} | {{iops}} | {{storage}} | ¥{{savings}} | {{action}} |

### 预留优化建议

| Instance ID | Running Days | Current PayType | Recommended | Annual Savings |
|-------------|--------------|-----------------|-------------|----------------|
| {{instance_1}} | {{days}} | {{paytype}} | {{recommendation}} | ¥{{savings}} |

### 即时优化建议

1. **P0 - 立即执行**: 删除闲置实例 {{idle_instances}}
2. **P1 - 本周执行**: 降级低利用率实例 {{downgrade_instances}}
3. **P2 - 本月执行**: 包年购买稳定实例 {{reserved_instances}}

### 验证命令
```bash
# 验证利用率
aliyun rds DescribeDBInstancePerformance --DBInstanceId "{{instance_id}}" --Key MySQL_CPUUsage
```
```

---

## 9. 与 Well-Architected Framework 集成

### 9.1 成本支柱评估

| Assessment Area | Current Score | Target | Action |
|-----------------|---------------|--------|--------|
| 资源利用率 | {{utilization_score}} | > 70% | FinOps Audit |
| 预留覆盖率 | {{reserved_score}} | > 50% | Reserved Analysis |
| 存储优化 | {{storage_score}} | > 80% | Storage Analysis |
| 成本可见性 | {{visibility_score}} | 100% | Billing Integration |

### 9.2 FinOps 持续改进循环

```
FinOps 循环
│
├─ Inform (了解)
│  ├─ 成本可见性 → Billing Dashboard
│  └─ 利用率分析 → FinOps Cruise
│
├─ Optimize (优化)
│  ├─ Right-sizing → 降级浪费实例
│  ├─ Reserved → 包年包月转换
│  └─ Storage → 存储缩容/类型优化
│
├─ Operate (运营)
│  ├─ 成本预警 → CloudMonitor Rules
│  ├─ 预留管理 → 到期续费流程
│  └─ 定期审计 → 每周/每月 FinOps Audit
│
└─ Measure (度量)
   ├─ 成本趋势 → 月度成本报告
   ├─ 节省实现 → 已节省金额统计
   └─ 覆盖率 → 预留覆盖率跟踪
```