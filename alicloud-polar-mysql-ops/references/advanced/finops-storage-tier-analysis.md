# FinOps: PolarDB Storage Tier (PSLevel) Cost Optimization

> 存储层级成本优化分析，用于识别不匹配的存储配置、提供存储包购买建议和数据分层策略。

## Overview

PolarDB MySQL 提供多种存储层级（PSLevel1-5），不同层级有不同的性能特征和成本。本节提供**存储层级**成本优化分析，帮助用户：

- 识别当前存储层级是否匹配业务需求
- 评估存储包购买的经济性
- 分析热/冷数据分布并提供分层策略

## Storage Tier Performance & Cost Matrix

| PSLevel | Performance Level | IOPS Baseline | Latency | Cost Factor | Best Use Case |
|---------|-------------------|---------------|---------|-------------|---------------|
| **PSLevel1** | 最高性能 | 50,000+ | < 1ms | 1.0x (基准) | 高并发交易系统、金融核心 |
| **PSLevel2** | 高性能 | 30,000-50,000 | 1-2ms | 0.85x | 电商订单、在线业务 |
| **PSLevel3** | 标准性能 | 15,000-30,000 | 2-5ms | 0.65x | 中等负载OLTP |
| **PSLevel4** | 经济型 | 5,000-15,000 | 5-10ms | 0.45x | 低负载业务、日志库 |
| **PSLevel5** | 节省型 | 2,000-5,000 | 10-20ms | 0.25x | 冷数据归档、历史库 |

> **Note:** Prices are approximate estimates based on Alibaba Cloud pricing (as of 2026-05). Actual costs vary by region. Verify current pricing via Alibaba Cloud console.

### Storage Cost Formula

```
月度存储成本 = StorageUsed(GB) × PSLevel单价 × 区域系数
```

### Storage Pack Savings Calculator

| Storage Pack Size | Monthly Cost | Effective GB Price | Savings vs On-Demand |
|-------------------|--------------|-------------------|----------------------|
| 50GB Pack | ~￥150 | ￥3.0/GB | 10-15% |
| 100GB Pack | ~￥280 | ￥2.8/GB | 15-20% |
| 500GB Pack | ~￥1,200 | ￥2.4/GB | 25-30% |
| 1TB Pack | ~￥2,200 | ￥2.2/GB | 35-40% |
| 5TB Pack | ~￥9,000 | ￥1.8/GB | 45-50% |

## Analysis Workflow

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Cluster Status | DescribeDBClusterAttribute | `Running` | HALT; cluster not stable |
| Storage Info | DescribeDBClusterAttribute | `StorageUsed`, `StorageSpace` | HALT; data unavailable |
| Current PSLevel | DescribeDBClusterAttribute | Valid PSLevel1-5 | Use default assumption |
| Metrics Available | DescribeDBClusterPerformance | IOPS/Latency data | Use estimation |

### Step 1: Get Current Storage Configuration

```bash
# Get cluster storage details
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=StorageUsed,StorageSpace,StorageType,DBClusterClass rows=DBCluster
```

### Step 2: Analyze Storage Utilization & Performance

```bash
# Get storage-related performance metrics
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName IopsUsage \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Statistics Average,Maximum \
  --Period 3600

# Get storage usage trend
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName StorageUsage \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Statistics Average \
  --Period 86400
```

### Step 3: Analyze Hot/Cold Data Distribution

```sql
-- 通过SQL查询分析数据分布（需要数据库连接）
-- 热数据识别：近期访问频率高的表
SELECT 
    table_schema,
    table_name,
    table_rows,
    ROUND(data_length/1024/1024, 2) AS data_size_mb,
    ROUND(index_length/1024/1024, 2) AS index_size_mb
FROM information_schema.tables
WHERE table_schema NOT IN ('mysql', 'information_schema', 'performance_schema')
ORDER BY data_length DESC
LIMIT 20;

-- 冷数据识别：创建时间超过6个月且无近期修改的表
-- 可通过 last_update_time 或业务元数据判断
```

## Implementation

### CLI (Primary Path)

```bash
# Comprehensive storage analysis workflow
# Step 1: Get cluster storage config
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# Step 2: Get performance metrics for tier suitability
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName IopsUsage,Latency \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"

# Step 3: Check available storage packs in region
aliyun bss DescribeProducts \
  --ProductCode polardb \
  --ProductType storage_pack
```

### JIT Go SDK (Fallback Path)

```go
package main

import (
    "fmt"
    "os"
    "math"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    polardb "github.com/alibabacloud-go/polardb-20220530/v3/client"
)

// StorageTierConfig - 存储层级配置参数
type StorageTierConfig struct {
    Level       int
    MaxIOPS     int
    MaxLatency  float64 // ms
    CostFactor  float64
    Name        string
}

// 预定义存储层级配置
var storageTiers = map[int]StorageTierConfig{
    1: {Level: 1, MaxIOPS: 50000, MaxLatency: 1.0, CostFactor: 1.0, Name: "最高性能"},
    2: {Level: 2, MaxIOPS: 30000, MaxLatency: 2.0, CostFactor: 0.85, Name: "高性能"},
    3: {Level: 3, MaxIOPS: 15000, MaxLatency: 5.0, CostFactor: 0.65, Name: "标准性能"},
    4: {Level: 4, MaxIOPS: 5000, MaxLatency: 10.0, CostFactor: 0.45, Name: "经济型"},
    5: {Level: 5, MaxIOPS: 2000, MaxLatency: 20.0, CostFactor: 0.25, Name: "节省型"},
}

// analyze_storage_tier_suitability - 分析当前存储层级适配度
// Returns: 当前层级是否匹配，建议层级，预期节省
func analyze_storage_tier_suitability(clusterId string, currentLevel int, avgIOPS int, avgLatency float64) map[string]interface{} {
    result := map[string]interface{}{
        "current_level": currentLevel,
        "avg_iops":      avgIOPS,
        "avg_latency":   avgLatency,
        "suitable":      true,
        "recommended":   currentLevel,
        "savings_pct":   0.0,
    }

    currentConfig := storageTiers[currentLevel]
    
    // 检查是否过度配置（实际使用远低于层级能力）
    if float64(avgIOPS) < float64(currentConfig.MaxIOPS) * 0.3 && avgLatency < currentConfig.MaxLatency * 0.5 {
        // 寻找更低层级是否能满足需求
        for level := currentLevel + 1; level <= 5; level++ {
            lowerConfig := storageTiers[level]
            if float64(avgIOPS) <= float64(lowerConfig.MaxIOPS) * 0.8 && avgLatency <= lowerConfig.MaxLatency {
                result["suitable"] = false
                result["recommended"] = level
                result["savings_pct"] = (currentConfig.CostFactor - lowerConfig.CostFactor) / currentConfig.CostFactor * 100
                break
            }
        }
    }
    
    // 检查是否配置不足（实际使用接近或超过层级能力）
    if float64(avgIOPS) > float64(currentConfig.MaxIOPS) * 0.85 || avgLatency > currentConfig.MaxLatency {
        for level := currentLevel - 1; level >= 1; level-- {
            higherConfig := storageTiers[level]
            if float64(avgIOPS) <= float64(higherConfig.MaxIOPS) * 0.9 {
                result["suitable"] = false
                result["recommended"] = level
                result["savings_pct"] = -(higherConfig.CostFactor - currentConfig.CostFactor) / currentConfig.CostFactor * 100
                result["reason"] = "性能瓶颈，建议升级"
                break
            }
        }
    }
    
    return result
}

// recommend_storage_pack - 推荐存储包购买方案
// Returns: 推荐的存储包规格和预期节省
func recommend_storage_pack(storageUsedGB float64, monthlyGrowthRate float64) map[string]interface{} {
    // 预测未来3个月存储需求
    predicted3Month := storageUsedGB * (1 + monthlyGrowthRate * 3)
    
    // 存储包规格（GB）
    packSizes := []int{50, 100, 500, 1000, 5000}
    packPrices := map[int]float64{50: 150, 100: 280, 500: 1200, 1000: 2200, 5000: 9000}
    onDemandPrice := 3.5 // ￥/GB/月 按量付费单价
    
    result := map[string]interface{}{
        "current_usage_gb":    storageUsedGB,
        "predicted_3month_gb": predicted3Month,
        "recommendation":      nil,
        "savings_monthly":     0.0,
    }
    
    // 选择最优存储包（覆盖当前+预测增长，且性价比最高）
    for _, size := range packSizes {
        if float64(size) >= predicted3Month {
            packCost := packPrices[size]
            onDemandCost := predicted3Month * onDemandPrice
            savings := onDemandCost - packCost
            if savings > 0 {
                result["recommendation"] = map[string]interface{}{
                    "pack_size_gb": size,
                    "pack_cost":    packCost,
                    "on_demand_cost": onDemandCost,
                }
                result["savings_monthly"] = savings
                break // 选择最小满足需求的规格
            }
        }
    }
    
    // 如果没有合适规格，推荐组合方案
    if result["recommendation"] == nil && predicted3Month > 5000 {
        result["recommendation"] = "建议购买多个5TB存储包组合使用"
        result["savings_monthly"] = predicted3Month * onDemandPrice - 9000 * math.Ceil(predicted3Month/5000)
    }
    
    return result
}

// analyze_data_distribution - 分析数据分布（热/冷数据）
// Returns: 热数据占比、冷数据占比、归档建议
func analyze_data_distribution(totalStorageGB float64, hotDataTables []map[string]interface{}, coldDataThresholdDays int) map[string]interface{} {
    // 零值检查：防止除零错误
    if totalStorageGB <= 0 {
        return map[string]interface{}{
            "hot_data_gb":           0.0,
            "hot_data_pct":          0.0,
            "cold_data_gb":          0.0,
            "cold_data_pct":         0.0,
            "tiering_recommendations": []string{"无存储数据，跳过分析"},
        }
    }
    
    hotDataSize := 0.0
    coldDataSize := 0.0
    
    for _, table := range hotDataTables {
        size, ok := table["data_size_mb"].(float64)
        if ok {
            hotDataSize += size / 1024 // MB to GB
        }
    }
    
    // 假设冷数据为总存储减去热数据
    coldDataSize = totalStorageGB - hotDataSize
    
    result := map[string]interface{}{
        "hot_data_gb":    hotDataSize,
        "hot_data_pct":   hotDataSize / totalStorageGB * 100,
        "cold_data_gb":   coldDataSize,
        "cold_data_pct":  coldDataSize / totalStorageGB * 100,
        "tiering_recommendations": []string{},
    }
    
    // 分层建议
    recommendations := []string{}
    if result["cold_data_pct"].(float64) > 30 {
        recommendations = append(recommendations,
            fmt.Sprintf("冷数据占比 %.1f%%，建议迁移至PSLevel5存储，可节省约 %.0f%% 成本",
                result["cold_data_pct"].(float64),
                (1.0 - storageTiers[5].CostFactor) * 100))
    }
    if hotDataSize < 50 && result["hot_data_pct"].(float64) < 20 {
        recommendations = append(recommendations,
            "热数据量小，考虑整体降级至PSLevel3-4")
    }
    
    result["tiering_recommendations"] = recommendations
    return result
}

func main() {
    // Validate credentials
    if os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID") == "" {
        fmt.Fprintln(os.Stderr, "ALIBABA_CLOUD_ACCESS_KEY_ID not set")
        os.Exit(1)
    }
    if os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET") == "" {
        fmt.Fprintln(os.Stderr, "ALIBABA_CLOUD_ACCESS_KEY_SECRET not set")
        os.Exit(1)
    }

    clusterId := os.Getenv("DB_CLUSTER_ID")
    if clusterId == "" {
        fmt.Fprintln(os.Stderr, "DB_CLUSTER_ID not set")
        os.Exit(1)
    }

    // ===== 示例分析参数 =====
    // 注意：以下参数为演示用途，实际部署时应从 API 动态获取：
    // - currentLevel: 从 DescribeDBClusterAttribute 获取 StorageType
    // - avgIOPS: 从 CMS GetMetricStatisticsData 获取 IopsUsage 平均值
    // - avgLatency: 从 CMS GetMetricStatisticsData 获取 Latency 平均值
    // - storageUsedGB: 从 DescribeDBClusterAttribute 获取 StorageUsed / 1024 / 1024 / 1024
    currentLevel := 2
    avgIOPS := 15000
    avgLatency := 3.5 // ms
    storageUsedGB := 800.0
    // ===== 示例参数结束 =====
    
    // 执行分析
    suitability := analyze_storage_tier_suitability(clusterId, currentLevel, avgIOPS, avgLatency)
    packRecommend := recommend_storage_pack(storageUsedGB, 0.05) // 5% 月增长率
    
    // 输出结果
    fmt.Println("=== PolarDB 存储层级成本分析 ===")
    fmt.Printf("当前层级: PSLevel%d\n", suitability["current_level"])
    fmt.Printf("适配状态: %v\n", suitability["suitable"])
    if !suitability["suitable"].(bool) {
        fmt.Printf("建议层级: PSLevel%d\n", suitability["recommended"])
        fmt.Printf("预期节省: %.1f%%\n", suitability["savings_pct"])
    }
    
    if packRecommend["recommendation"] != nil {
        fmt.Printf("\n存储包推荐: %v\n", packRecommend["recommendation"])
        fmt.Printf("月度节省: ￥%.2f\n", packRecommend["savings_monthly"])
    }
}
```

## Output Format

```
PolarDB 存储层级成本分析:
├── 当前配置
│   ├── 存储层级: PSLevel2 (高性能)
│   ├── 已用存储: 850GB / 1000GB
│   └── 平均IOPS: 12,000 / 容量50,000
│
├── 适配度分析
│   ├── ⚠️ 过度配置: 实际IOPS仅24%层级容量
│   ├── 建议降级: PSLevel3 (标准性能)
│   └── 预期节省: 23.5% (~￥200/月)
│
├── 存储包建议
│   ├── 当前按量付费: ￥850/月 (￥1.0/GB)
│   ├── 推荐购买: 1TB存储包 (￥2200)
│   └── 月度节省: ￥170/月 (20%)
│
├── 数据分层分析
│   ├── 热数据: 200GB (23%) - 近30天活跃表
│   ├── 冷数据: 650GB (77%) - 超180天未更新
│   └── 分层建议: 冷数据迁移至PSLevel5，节省65%
│
└── 综合优化方案
    ├── 立即执行: 降级至PSLevel3
    ├── 月度执行: 购买1TB存储包
    ├── 季度执行: 冷数据归档至PSLevel5
    └── 预计总节省: ￥420/月 (49%)
```

## Acceptance Criteria (验收标准)

| # | Criteria | Detection Method |
|---|----------|------------------|
| ✓ | 识别不匹配的存储层级配置 | `analyze_storage_tier_suitability()` 返回 `suitable=false` |
| ✓ | 提供存储包购买建议 | `recommend_storage_pack()` 返回有效推荐规格 |
| ✓ | 提供数据分层策略建议 | `analyze_data_distribution()` 返回分层建议列表 |
| ✓ | 计算预期成本节省百分比 | 所有分析函数返回 `savings_pct` 或 `savings_monthly` |

## Storage Tier Migration Procedure

### 降级存储层级 (降低成本)

```bash
# 警告: 存储层级变更可能影响性能，需在业务低峰期执行
aliyun polardb ModifyDBClusterStorageType \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StorageType PSLevel3 \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### 升级存储层级 (提升性能)

```bash
# 升级需确认集群状态稳定
aliyun polardb ModifyDBClusterStorageType \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StorageType PSLevel1 \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### 存储包购买流程

```bash
# 1. 查询可用存储包规格
aliyun bss DescribeProducts \
  --ProductCode polardb \
  --ProductType storage_pack \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 2. 创建存储包订单
aliyun bss CreateOrder \
  --ProductCode polardb \
  --ProductType storage_pack \
  --Specification "{{pack_size}}" \
  --Period 12 \
  --PayType Prepaid
```

## Data Archiving Strategy (数据归档策略)

### 冷数据识别标准

| Criterion | Threshold | Action |
|-----------|-----------|--------|
| 最后更新时间 | > 180天 | 标记为冷数据候选 |
| 访问频率 | < 10次/月 | 优先归档 |
| 表大小 | > 10GB | 分批归档 |
| 业务类型 | 日志/历史数据 | 强制归档 |

### 归档执行方案

1. **方案A: 表级迁移** - 创建新集群使用PSLevel5，迁移冷数据表
2. **方案B: 分区归档** - 使用表分区，将旧分区数据导出至低成本存储
3. **方案C: OSS归档** - 导出冷数据至OSS，配合生命周期管理

```bash
# 方案A: 创建PSLevel5归档集群
aliyun polardb CreateDBCluster \
  --DBType MySQL \
  --DBVersion 8.0 \
  --StorageType PSLevel5 \
  --StorageSpace "{{archive_storage_gb}}" \
  --DBClusterDescription "冷数据归档库"

# 方案C: 导出至OSS
aliyun polardb CreateDumpTask \
  --DBClusterId "{{user.db_cluster_id}}" \
  --Database "{{cold_database}}" \
  --OssBucket "{{archive_bucket}}" \
  --OssPath "archive/{{date}}"
```

## Failure Recovery

| Error pattern | Agent Action |
|---------------|--------------|
| Storage metrics unavailable | Use DescribeDBClusterAttribute storage fields as proxy |
| CMS endpoint timeout | Estimate IOPS based on node class baseline |
| Storage tier modification blocked | Check cluster status, wait for stable state |
| Storage pack purchase failed | Check account balance, recommend smaller pack |

## Integration with Well-Architected Framework

> Extends 成本 审查维度: 存储层级适配度 + 存储包使用率 + 数据分层效率

### 成本效率指标

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Storage Tier Utilization | IOPS > 30% capacity | Alert if < 30% (over-provisioned) |
| Storage Pack Coverage | > 80% of storage used | Alert if pack unused > 50GB |
| Cold Data Ratio | < 40% on high-tier storage | Alert if > 50% cold on PSLevel1-2 |
| Storage Growth Rate | < 10%/month | Alert if > 20% (scale planning needed) |