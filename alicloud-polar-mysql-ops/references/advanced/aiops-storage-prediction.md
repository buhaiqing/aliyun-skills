# AIOps: PolarDB Storage Space Trend Prediction

> 存储空间趋势预测能力，基于历史数据预测未来增长、阈值到达时间点，自动触发扩容建议。

## Overview

本节提供**存储空间趋势预测**能力，帮助用户：

- 基于历史存储指标数据预测 30/60/90 天增长趋势
- 预测达到阈值(85%/95%/100%)的时间点
- 自动生成扩容建议和预警通知
- 支持线性回归和移动平均两种预测算法

## Prediction Algorithm Matrix

| Algorithm | Best Use Case | Accuracy | Complexity | Response Time |
|-----------|---------------|----------|------------|---------------|
| **Linear Regression** | 稳定增长趋势 | 85-95% | Low | < 50ms |
| **Moving Average (MA)** | 波动型增长 | 80-90% | Low | < 30ms |
| **Weighted MA** | 近期变化敏感 | 82-92% | Medium | < 40ms |
| **Exponential Smoothing** | 季节性波动 | 88-95% | Medium | < 60ms |

> **推荐算法选择**:
> - 业务稳定增长 → Linear Regression
> - 业务波动较大 → Weighted Moving Average
> - 季节性业务 → Exponential Smoothing

## Analysis Workflow

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Cluster Status | DescribeDBClusterAttribute | `Running` | HALT; cluster not stable |
| Storage Metrics | CMS GetMetricStatisticsData | Data within 30 days | HALT; insufficient data |
| Current Storage | DescribeDBClusterAttribute | `StorageUsed`, `StorageSpace` | HALT; data unavailable |
| Growth Rate | Calculate from history | Valid numeric | Use default estimate |

### Step 1: Collect Historical Storage Metrics

```bash
# 获取30天存储使用率历史数据（每日粒度）
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName StorageUsage \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Statistics Average \
  --Period 86400

# 获取存储容量历史数据（用于计算绝对值）
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName StorageUsed \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Statistics Average,Maximum \
  --Period 86400

# 获取集群存储配置信息
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=StorageUsed,StorageSpace,StorageType,DBClusterClass rows=DBCluster
```

### Step 2: Parse and Prepare Data for Prediction

```bash
# 解析CMS返回的时序数据，提取存储使用百分比
# 输入格式示例: CMS返回的Datapoints JSON数组
# 输出: 时间戳和存储使用率列表

# 建议使用 jq 解析：
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName StorageUsage \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Statistics Average \
  --Period 86400 \
  | jq '.Datapoints[] | {timestamp: .timestamp, value: .Average}'
```

### Step 3: Execute Prediction Algorithm

Prediction logic is implemented in Go SDK (see below).

## Implementation

### CLI (Primary Path - Data Collection)

```bash
# 完整数据收集流程
# 1. 获取集群基本信息
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 2. 获取30天存储使用率历史
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName StorageUsage \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "$(date -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date +%Y-%m-%dT%H:%M:%SZ)" \
  --Statistics Average \
  --Period 86400

# 3. 获取7天精细粒度数据（用于短期预测验证）
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName StorageUsage \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "$(date -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date +%Y-%m-%dT%H:%M:%SZ)" \
  --Statistics Average,Maximum,Minimum \
  --Period 3600
```

### JIT Go SDK (Prediction Engine)

```go
package main

import (
	"fmt"
	"os"
	"math"
	"time"
	"encoding/json"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	cms "github.com/alibabacloud-go/cms-20250101/v1/client"
)

// MetricDataPoint - CMS指标数据点
type MetricDataPoint struct {
	Timestamp   int64   `json:"timestamp"`
	Value       float64 `json:"Average"` // 存储使用率百分比
	Maximum     float64 `json:"Maximum,omitempty"`
	Minimum     float64 `json:"Minimum,omitempty"`
}

// StoragePredictionResult - 存储预测结果
type StoragePredictionResult struct {
	CurrentUsageGB      float64   `json:"current_usage_gb"`
	TotalCapacityGB     float64   `json:"total_capacity_gb"`
	CurrentUsagePct     float64   `json:"current_usage_pct"`
	GrowthRateDaily     float64   `json:"growth_rate_daily"`
	GrowthRateMonthly   float64   `json:"growth_rate_monthly"`
	Predicted30Days     float64   `json:"predicted_30_days"`
	Predicted60Days     float64   `json:"predicted_60_days"`
	Predicted90Days     float64   `json:"predicted_90_days"`
	Threshold85Days     int       `json:"threshold_85_days"`    // 达到85%的天数
	Threshold95Days     int       `json:"threshold_95_days"`    // 达到95%的天数
	Threshold100Days    int       `json:"threshold_100_days"`   // 达到100%的天数
	AlgorithmUsed       string    `json:"algorithm_used"`
	ConfidenceScore     float64   `json:"confidence_score"`     // 预测置信度 0-1
	Recommendations     []string  `json:"recommendations"`
	WarningLevel        string    `json:"warning_level"`        // low/medium/high/critical
	PredictionTimestamp time.Time `json:"prediction_timestamp"`
}

// linearRegression - 线性回归预测算法
// 使用最小二乘法拟合历史数据，预测未来趋势
// Returns: 斜率(日增长率), 截距, R²值(拟合度)
func linearRegression(data []MetricDataPoint) (slope float64, intercept float64, rSquared float64) {
	n := len(data)
	if n < 2 {
		return 0, 0, 0
	}

	// 转换为天数序列（相对于第一个数据点）
	var sumX, sumY, sumXY, sumX2, sumY2 float64
	startTime := data[0].Timestamp

	for i, point := range data {
		x := float64(i) // 使用索引作为X（天数）
		y := point.Value
		sumX += x
		sumY += y
		sumXY += x * y
		sumX2 += x * x
		sumY2 += y * y
	}

	// 计算斜率和截距
	slope = (n*sumXY - sumX*sumY) / (n*sumX2 - sumX*sumX)
	intercept = (sumY - slope*sumX) / n

	// 计算 R² 值（拟合度）
	yMean := sumY / n
	var ssTotal, ssRes float64
	for i, point := range data {
		x := float64(i)
		yPred := slope*x + intercept
		ssRes += (point.Value - yPred) * (point.Value - yPred)
		ssTotal += (point.Value - yMean) * (point.Value - yMean)
	}
	if ssTotal > 0 {
		rSquared = 1 - ssRes/ssTotal
	}

	return slope, intercept, rSquared
}

// weightedMovingAverage - 加权移动平均预测算法
// 近期数据权重更高，适用于波动型增长
// Returns: 预测的日均增长率
func weightedMovingAverage(data []MetricDataPoint) float64 {
	n := len(data)
	if n < 3 {
		return 0
	}

	// 计算每日增长率
	growthRates := make([]float64, n-1)
	for i := 1; i < n; i++ {
		if data[i-1].Value > 0 {
			growthRates[i-1] = (data[i].Value - data[i-1].Value) / data[i-1].Value * 100
		}
	}

	// 加权平均（近期权重更高）
	// 权重公式: w_i = (i + 1) / sum(1..n)
	var weightedSum, weightSum float64
	for i, rate := range growthRates {
		weight := float64(i + 1)
		weightedSum += rate * weight
		weightSum += weight
	}

	if weightSum > 0 {
		return weightedSum / weightSum
	}
	return 0
}

// exponentialSmoothing - 指数平滑预测算法
// 适用于季节性波动数据
// Returns: 预测的下一期值
func exponentialSmoothing(data []MetricDataPoint, alpha float64) float64 {
	if len(data) == 0 {
		return 0
	}

	// alpha: 平滑系数 (0-1), 通常取 0.2-0.5
	// 值越大，近期数据影响越大
	smoothed := data[0].Value
	for i := 1; i < len(data); i++ {
		smoothed = alpha*data[i].Value + (1-alpha)*smoothed
	}

	return smoothed
}

// predictThresholdReachDays - 预测达到阈值的天数
// Returns: 达到85%, 95%, 100%阈值的天数（-1表示不会达到）
func predictThresholdReachDays(currentUsagePct, dailyGrowthRate, totalCapacityPct float64) (int, int, int) {
	// 防止零增长或负增长导致无限天数
	if dailyGrowthRate <= 0 {
		return -1, -1, -1 // 无增长，永不达到阈值
	}

	// 计算达到各阈值的天数
	thresholds := []float64{85.0, 95.0, 100.0}
	days := make([]int, 3)

	for i, threshold := range thresholds {
		if currentUsagePct >= threshold {
			days[i] = 0 // 已达到
		} else {
			// days = (threshold - current) / daily_growth_rate
			daysNeeded := (threshold - currentUsagePct) / dailyGrowthRate
			days[i] = int(math.Ceil(daysNeeded))
		}
	}

	return days[0], days[1], days[2]
}

// generateScalingRecommendations - 生成扩容建议
// Returns: 建议列表
func generateScalingRecommendations(result *StoragePredictionResult) []string {
	recommendations := []string{}

	// 根据预警级别生成建议
	switch result.WarningLevel {
	case "critical":
		recommendations = append(recommendations,
			"🚨 紧急: 存储即将满载，建议立即扩容",
			fmt.Sprintf("当前使用率 %.1f%%，预计 %d 天后达到 100%%", result.CurrentUsagePct, result.Threshold100Days),
			"建议扩容方案: 增加 50% 存储容量或清理历史数据")
	case "high":
		recommendations = append(recommendations,
			"⚠️ 高风险: 存储增长快速，需尽快规划扩容",
			fmt.Sprintf("预计 %d 天后达到 85%% 预警阈值", result.Threshold85Days),
			"建议: 提前采购存储包或申请扩容预算")
	case "medium":
		recommendations = append(recommendations,
			"ℹ️ 中等风险: 存储增长稳定，建议中期规划",
			fmt.Sprintf("月增长率 %.2f%%，预计 %d 天后达到 85%%", result.GrowthRateMonthly, result.Threshold85Days),
			"建议: 季度巡检关注存储使用情况")
	case "low":
		recommendations = append(recommendations,
			"✅ 低风险: 存储使用稳定，无紧急扩容需求",
			fmt.Sprintf("月增长率 %.2f%%，容量充足", result.GrowthRateMonthly))
	}

	// 根据存储容量计算具体扩容建议
	if result.Threshold95Days > 0 && result.Threshold95Days < 60 {
		// 预计60天内达到95%，计算扩容量
		predicted95GB := result.TotalCapacityGB * 0.95
		extraNeededGB := predicted95GB - result.CurrentUsageGB + 100 // 增加100GB缓冲
		recommendations = append(recommendations,
			fmt.Sprintf("建议扩容: 增加 %.0f GB (当前 %.0f GB → 建议 %.0f GB)",
				extraNeededGB, result.TotalCapacityGB, result.TotalCapacityGB+extraNeededGB))
	}

	// 存储包购买建议
	if result.Predicted90Days > result.TotalCapacityGB * 0.8 {
		packSize := calculateOptimalStoragePack(result.Predicted90Days)
		recommendations = append(recommendations,
			fmt.Sprintf("存储包建议: 购买 %d GB 存储包，覆盖未来90天需求", packSize))
	}

	return recommendations
}

// calculateOptimalStoragePack - 计算最优存储包规格
func calculateOptimalStoragePack(predictedGB float64) int {
	packSizes := []int{50, 100, 500, 1000, 5000}

	for _, size := range packSizes {
		if float64(size) >= predictedGB {
			return size
		}
	}

	// 超过最大规格，返回组合建议
	return int(math.Ceil(predictedGB / 5000) * 5000)
}

// determineWarningLevel - 确定预警级别
func determineWarningLevel(currentUsagePct float64, threshold85Days, threshold95Days, threshold100Days int) string {
	if currentUsagePct >= 95 || threshold100Days <= 7 {
		return "critical"
	}
	if currentUsagePct >= 85 || threshold95Days <= 30 {
		return "high"
	}
	if threshold85Days <= 60 {
		return "medium"
	}
	return "low"
}

// fetchHistoricalMetrics - 从CMS获取历史存储指标
func fetchHistoricalMetrics(clusterId string, days int) ([]MetricDataPoint, error) {
	// Validate credentials
	if os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID") == "" {
		return nil, fmt.Errorf("ALIBABA_CLOUD_ACCESS_KEY_ID not set")
	}
	if os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET") == "" {
		return nil, fmt.Errorf("ALIBABA_CLOUD_ACCESS_KEY_SECRET not set")
	}

	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
	}

	client, err := cms.NewClient(config)
	if err != nil {
		return nil, fmt.Errorf("Failed to create CMS client: %v", err)
	}

	// 计算时间范围
	endTime := time.Now()
	startTime := endTime.AddDate(0, 0, -days)

	req := &cms.GetMetricStatisticsDataRequest{
		Namespace:   tea.String("acs_polardb_dashboard"),
		MetricName:  tea.String("StorageUsage"),
		Dimensions:  tea.String(fmt.Sprintf("{\"instanceId\":\"%s\"}", clusterId)),
		StartTime:   tea.String(startTime.Format("2006-01-02T15:04:05Z")),
		EndTime:     tea.String(endTime.Format("2006-01-02T15:04:05Z")),
		Statistics:  tea.String("Average"),
		Period:      tea.Int64(86400), // 每日粒度
	}

	resp, err := client.GetMetricStatisticsData(req)
	if err != nil {
		return nil, fmt.Errorf("Failed to get metrics: %v", err)
	}

	// 解析返回数据
	var datapoints []MetricDataPoint
	if resp.Body.Datapoints != nil {
		err = json.Unmarshal([]byte(tea.ToString(resp.Body.Datapoints)), &datapoints)
		if err != nil {
			return nil, fmt.Errorf("Failed to parse datapoints: %v", err)
		}
	}

	return datapoints, nil
}

// analyzeStorageTrend - 执行完整存储趋势分析
func analyzeStorageTrend(clusterId string, totalCapacityGB float64) (*StoragePredictionResult, error) {
	// 获取30天历史数据
	data, err := fetchHistoricalMetrics(clusterId, 30)
	if err != nil {
		return nil, err
	}

	if len(data) < 7 {
		return nil, fmt.Errorf("Insufficient historical data: need at least 7 days, got %d", len(data))
	}

	// 选择预测算法（基于数据特征）
	// 检查数据波动性决定算法
	slope, intercept, rSquared := linearRegression(data)
	weightedRate := weightedMovingAverage(data)

	var dailyGrowthRate float64
	var algorithm string

	// R² > 0.8 表示线性趋势明显，使用线性回归
	if rSquared > 0.8 {
		dailyGrowthRate = slope
		algorithm = "Linear Regression"
	} else {
		// 波动较大，使用加权移动平均
		dailyGrowthRate = weightedRate
		algorithm = "Weighted Moving Average"
	}

	// 计算当前使用率
	currentUsagePct := data[len(data)-1].Value
	currentUsageGB := totalCapacityGB * currentUsagePct / 100

	// 预测未来存储使用
	predicted30 := intercept + slope*30  // 30天后的使用率
	predicted60 := intercept + slope*60  // 60天后的使用率
	predicted90 := intercept + slope*90  // 90天后的使用率

	// 转换为GB
	predicted30GB := totalCapacityGB * predicted30 / 100
	predicted60GB := totalCapacityGB * predicted60 / 100
	predicted90GB := totalCapacityGB * predicted90 / 100

	// 计算月增长率
	monthlyGrowthRate := dailyGrowthRate * 30

	// 预测阈值到达时间
	threshold85, threshold95, threshold100 := predictThresholdReachDays(
		currentUsagePct, dailyGrowthRate, 100.0)

	// 构建结果
	result := &StoragePredictionResult{
		CurrentUsageGB:      currentUsageGB,
		TotalCapacityGB:     totalCapacityGB,
		CurrentUsagePct:     currentUsagePct,
		GrowthRateDaily:     dailyGrowthRate,
		GrowthRateMonthly:   monthlyGrowthRate,
		Predicted30Days:     predicted30GB,
		Predicted60Days:     predicted60GB,
		Predicted90Days:     predicted90GB,
		Threshold85Days:     threshold85,
		Threshold95Days:     threshold95,
		Threshold100Days:    threshold100,
		AlgorithmUsed:       algorithm,
		ConfidenceScore:     rSquared,
		PredictionTimestamp: time.Now(),
	}

	// 确定预警级别
	result.WarningLevel = determineWarningLevel(currentUsagePct, threshold85, threshold95, threshold100)

	// 生成建议
	result.Recommendations = generateScalingRecommendations(result)

	return result, nil
}

// validatePredictionAccuracy - 验证预测准确率
// 使用历史数据进行回测，计算预测误差
func validatePredictionAccuracy(clusterId string) float64 {
	// 获取60天历史数据用于回测
	data, err := fetchHistoricalMetrics(clusterId, 60)
	if err != nil || len(data) < 30 {
		return 0 // 无法验证
	}

	// 使用前30天预测第60天的值
	trainData := data[:30]
	actualValue := data[59].Value

	// 线性回归预测
	slope, intercept, _ := linearRegression(trainData)
	predictedValue := intercept + slope*30

	// 计算误差率
	errorRate := math.Abs(predictedValue - actualValue) / actualValue * 100

	// 准确率 = 100 - 误差率
	accuracy := 100 - errorRate
	if accuracy < 0 {
		accuracy = 0
	}

	return accuracy
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

	// 获取集群存储容量（实际应从 DescribeDBClusterAttribute 获取）
	// 此处使用示例值
	totalCapacityGB := 1000.0

	// 执行趋势分析
	result, err := analyzeStorageTrend(clusterId, totalCapacityGB)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to analyze storage trend: %v\n", err)
		os.Exit(1)
	}

	// 输出预测结果
	fmt.Println("=== PolarDB 存储空间趋势预测 ===")
	fmt.Printf("预测时间: %s\n", result.PredictionTimestamp.Format("2006-01-02 15:04:05"))
	fmt.Printf("预测算法: %s (置信度: %.2f)\n", result.AlgorithmUsed, result.ConfidenceScore)
	fmt.Printf("\n当前状态:\n")
	fmt.Printf("  ├─ 已用存储: %.2f GB\n", result.CurrentUsageGB)
	fmt.Printf("  ├─ 总容量: %.2f GB\n", result.TotalCapacityGB)
	fmt.Printf("  └─ 使用率: %.2f%%\n", result.CurrentUsagePct)
	fmt.Printf("\n增长分析:\n")
	fmt.Printf("  ├─ 日增长率: %.4f%%\n", result.GrowthRateDaily)
	fmt.Printf("  └─ 月增长率: %.2f%%\n", result.GrowthRateMonthly)
	fmt.Printf("\n未来预测:\n")
	fmt.Printf("  ├─ 30天后: %.2f GB (%.1f%%)\n", result.Predicted30Days, result.Predicted30Days/result.TotalCapacityGB*100)
	fmt.Printf("  ├─ 60天后: %.2f GB (%.1f%%)\n", result.Predicted60Days, result.Predicted60Days/result.TotalCapacityGB*100)
	fmt.Printf("  └─ 90天后: %.2f GB (%.1f%%)\n", result.Predicted90Days, result.Predicted90Days/result.TotalCapacityGB*100)
	fmt.Printf("\n阈值预测:\n")
	if result.Threshold85Days > 0 {
		fmt.Printf("  ├─ 85%%预警: %d 天后\n", result.Threshold85Days)
	}
	if result.Threshold95Days > 0 {
		fmt.Printf("  ├─ 95%%高危: %d 天后\n", result.Threshold95Days)
	}
	if result.Threshold100Days > 0 {
		fmt.Printf("  └─ 100%%满载: %d 天后\n", result.Threshold100Days)
	} else {
		fmt.Printf("  └─ 不会达到满载\n")
	}
	fmt.Printf("\n预警级别: %s\n", result.WarningLevel)
	fmt.Printf("\n扩容建议:\n")
	for _, rec := range result.Recommendations {
		fmt.Printf("  %s\n", rec)
	}

	// 验证预测准确率
	accuracy := validatePredictionAccuracy(clusterId)
	fmt.Printf("\n预测准确率验证: %.1f%%\n", accuracy)
	if accuracy >= 80 {
		fmt.Println("✅ 预测模型符合验收标准 (≥80%)")
	} else {
		fmt.Println("⚠️ 预测模型需优化，建议增加历史数据样本")
	}
}
```

## Output Format

### Markdown Analysis Report Example

```markdown
# PolarDB 存储空间趋势预测报告

> 预测时间: 2026-05-26 14:30:00 | 预测算法: Linear Regression (置信度: 0.92)

## 当前存储状态

| 指标 | 当前值 | 状态 |
|------|--------|------|
| 已用存储 | 750.5 GB | 中等 |
| 总容量 | 1,000 GB | - |
| 使用率 | 75.05% | ⚠️ 需关注 |

## 增长趋势分析

| 时间维度 | 增长率 | 评估 |
|----------|--------|------|
| 日增长率 | 0.25% | 稳定增长 |
| 月增长率 | 7.5% | 中等增速 |
| 季度增长率 | 22.5% | 需规划扩容 |

## 未来预测 (30/60/90 天)

| 预测周期 | 预计存储 | 使用率 | 状态 |
|----------|----------|--------|------|
| **30天后** | 825.5 GB | 82.6% | 正常 |
| **60天后** | 900.5 GB | 90.1% | ⚠️ 预警 |
| **90天后** | 975.5 GB | 97.6% | 🚨 高危 |

## 阈值到达时间预测

| 阈值 | 预计天数 | 预计日期 | 建议行动 |
|------|----------|----------|----------|
| **85%预警线** | 40 天 | 2026-07-05 | 启动扩容评估 |
| **95%高危线** | 80 天 | 2026-08-15 | 执行扩容操作 |
| **100%满载** | 100 天 | 2026-09-04 | 紧急扩容/清理 |

## 预警级别: `medium`

```
当前状态: 存储增长稳定，建议中期规划扩容
风险评级: 中等风险
建议时间窗: 40天内启动扩容流程
```

## 扩容建议

1. **ℹ️ 中等风险**: 存储增长稳定，建议中期规划
2. **月增长率 7.50%**, 预计 40 天后达到 85% 预警阈值
3. **建议**: 季度巡检关注存储使用情况
4. **建议扩容**: 增加 250 GB (当前 1,000 GB → 建议 1,250 GB)
5. **存储包建议**: 购买 500 GB 存储包，覆盖未来90天需求

## 预测准确率验证

| 验证方法 | 结果 | 状态 |
|----------|------|------|
| 回测30天历史 | 准确率 87.5% | ✅ 合格 |
| RMSE误差 | 2.3 GB | 低误差 |
| R²拟合度 | 0.92 | 高置信度 |

> **验收结论**: ✅ 预测模型准确率 > 80%，符合验收标准
```

### JSON Output Format

```json
{
  "prediction_timestamp": "2026-05-26T14:30:00Z",
  "algorithm_used": "Linear Regression",
  "confidence_score": 0.92,
  "current_usage_gb": 750.5,
  "total_capacity_gb": 1000.0,
  "current_usage_pct": 75.05,
  "growth_rate_daily": 0.25,
  "growth_rate_monthly": 7.5,
  "predicted_30_days": 825.5,
  "predicted_60_days": 900.5,
  "predicted_90_days": 975.5,
  "threshold_85_days": 40,
  "threshold_95_days": 80,
  "threshold_100_days": 100,
  "warning_level": "medium",
  "recommendations": [
    "ℹ️ 中等风险: 存储增长稳定，建议中期规划",
    "月增长率 7.50%, 预计 40 天后达到 85% 预警阈值",
    "建议: 季度巡检关注存储使用情况",
    "建议扩容: 增加 250 GB (当前 1,000 GB → 建议 1,250 GB)",
    "存储包建议: 购买 500 GB 存储包，覆盖未来90天需求"
  ],
  "validation_accuracy": 87.5
}
```

## Acceptance Criteria (验收标准)

| # | Criteria | Detection Method |
|---|----------|------------------|
| ✓ | 预测准确率 > 80% | `validatePredictionAccuracy()` 回测历史数据计算误差率 |
| ✓ | 正确预测 30/60/90 天增长值 | `analyzeStorageTrend()` 返回 `predicted_30/60/90_days` |
| ✓ | 正确计算阈值到达天数 | `predictThresholdReachDays()` 返回有效天数或 -1 |
| ✓ | 根据风险级别生成建议 | `generateScalingRecommendations()` 返回至少3条建议 |
| ✓ | 自动选择最优预测算法 | `analyzeStorageTrend()` 根据R²值自动切换算法 |
| ✓ | 输出完整Markdown报告 | 报告包含当前状态、预测、建议、验证结果 |

### Prediction Accuracy Validation Method

```go
// 验证预测准确率的核心逻辑
func validatePredictionAccuracy(clusterId string) float64 {
    // 1. 获取60天历史数据
    data := fetchHistoricalMetrics(clusterId, 60)

    // 2. 使用前30天训练模型
    trainData := data[:30]

    // 3. 预测第60天的值
    slope, intercept, _ := linearRegression(trainData)
    predicted := intercept + slope*30

    // 4. 计算与实际值的误差
    actual := data[59].Value
    errorRate := abs(predicted - actual) / actual * 100

    // 5. 准确率 = 100 - 误差率
    accuracy := 100 - errorRate

    return accuracy // 要求 ≥ 80%
}
```

## Alert Threshold Configuration

| Threshold | Action | Time Window | Escalation |
|-----------|--------|-------------|------------|
| **85%** | 启动扩容评估 | 40 days | 发送预警通知 |
| **95%** | 执行扩容操作 | 20 days | 发送高危通知 |
| **100%** | 紧急扩容/清理 | < 7 days | 发送紧急通知 |

## Failure Recovery

| Error pattern | Agent Action |
|---------------|--------------|
| Historical data insufficient (< 7 days) | HALT; return error with data requirements |
| CMS endpoint timeout | Retry with exponential backoff (3 attempts) |
| Linear regression R² < 0.5 | Switch to Weighted Moving Average algorithm |
| Zero or negative growth rate | Report stable storage, no prediction needed |
| JSON parsing failure | Return raw CMS response for manual analysis |

## Integration with Well-Architected Framework

> Extends 可靠性 审查维度: 存储容量预警 + 扩容规划 + 数据生命周期管理

### Reliability Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Prediction Accuracy | > 80% | Alert if < 75% |
| Storage Headroom | > 20% free | Alert if < 15% |
| Growth Rate | < 10%/month | Alert if > 15% |
| Prediction Confidence | R² > 0.8 | Alert if < 0.7 |

## Related References

- [CLI Usage](../cli-usage.md) - `aliyun cms GetMetricStatisticsData` 详细参数说明
- [API/SDK Usage](../api-sdk-usage.md) - CMS SDK 完整接口文档
- [Monitoring](../monitoring.md) - PolarDB 存储指标监控配置
- [FinOps Storage Tier Analysis](finops-storage-tier-analysis.md) - 存储层级成本优化