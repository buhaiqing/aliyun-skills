# AIOps: PolarDB PostgreSQL Connection Trend Prediction

> 连接数趋势预测能力，基于历史数据分析业务周期模式，预测高峰期连接数，提前预警连接瓶颈风险。

## Overview

本节提供**连接数趋势预测**能力，帮助用户：

- 分析业务周期模式（日/周/月周期识别）
- 预测高峰期连接数峰值
- 提前预警连接瓶颈（达到上限80%/90%/100%）
- 生成连接池优化建议和扩容规划

## Connection Metrics Reference

| Metric | Namespace | Unit | Description | Collection Period |
|--------|-----------|------|-------------|-------------------|
| **ConnectionUsage** | `acs_polardb_dashboard` | % | 连接利用率百分比 | 60s |
| **ActiveSessions** | `acs_polardb_dashboard` | count | 活跃会话数 | 60s |
| **TotalConnections** | `acs_polardb_dashboard` | count | 总连接数 | 60s |
| **MaxConnections** | `acs_polardb_dashboard` | count | 最大连接数限制 | 配置项 |

> **Note:** `ConnectionUsage = ActiveSessions / MaxConnections * 100`

## Business Cycle Detection Matrix

| Cycle Type | Detection Pattern | Typical Scenario | Prediction Window |
|------------|-------------------|------------------|-------------------|
| **Daily Cycle** | 24h周期，高峰在特定时段 | 电商/企业应用工作时段 | 每日高峰预测 |
| **Weekly Cycle** | 7天周期，工作日vs周末 | 企业应用周末低谷 | 周高峰预测 |
| **Monthly Cycle** | 30天周期，月末/月初高峰 | 财务结算/报表周期 | 月高峰预测 |
| **Event Cycle** | 非周期性突增 | 营销活动/促销 | 事件驱动预警 |

## Analysis Workflow

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Cluster Status | DescribeDBClusterAttribute | `Running` | HALT; cluster not stable |
| Connection Metrics | CMS GetMetricStatisticsData | Data within 14 days | HALT; insufficient data |
| Max Connections | DescribeDBClusterAttribute | Valid `max_connections` | Use default 5000 |
| Node Count | DescribeDBNodes | At least 1 writer node | HALT; no active nodes |

### Step 1: Collect Historical Connection Metrics

```bash
# 获取14天连接利用率历史数据（每小时粒度，用于周期分析）
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Statistics Average,Maximum,Minimum \
  --Period 3600 \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 获取活跃会话数历史数据（5分钟粒度，用于高峰分析）
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName ActiveSessions \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --Statistics Average,Maximum,Sum \
  --Period 300 \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 获取集群连接配置
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=DBClusterId,DBClusterClass,DBNodeNumber rows=DBCluster
```

### Step 2: Execute Prediction Algorithm

Prediction logic implemented in Go SDK with cycle detection algorithms.

## Implementation

### CLI (Primary Path)

```bash
# 完整数据收集流程
# 1. 获取集群基本信息和连接上限
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 2. 获取14天连接使用率历史（周期分析）
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "$(date -d '14 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date +%Y-%m-%dT%H:%M:%SZ)" \
  --Statistics Average,Maximum \
  --Period 3600

# 3. 获取最近24小时精细数据（高峰验证）
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "$(date -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date +%Y-%m-%dT%H:%M:%SZ)" \
  --Statistics Average,Maximum,Minimum \
  --Period 300
```

### JIT Go SDK (Prediction Engine)

```go
package main

import (
	"fmt"
	"math"
	"sort"
	"time"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	cms "github.com/alibabacloud-go/cms-20250101/v1/client"
)

// MetricDataPoint - CMS指标数据点
type MetricDataPoint struct {
	Timestamp int64   `json:"timestamp"`
	Value     float64 `json:"Average"`
	Maximum   float64 `json:"Maximum,omitempty"`
	Minimum   float64 `json:"Minimum,omitempty"`
}

// CycleType - 业务周期类型
type CycleType string

const (
	CycleDaily   CycleType = "daily"
	CycleWeekly  CycleType = "weekly"
	CycleMonthly CycleType = "monthly"
	CycleNone    CycleType = "none"
)

// CyclePattern - 周期模式检测结果
type CyclePattern struct {
	Type          CycleType
	PeakHour      int
	PeakDays      []int
	PeakHourValue float64
	OffPeakValue  float64
	Variance      float64
	Confidence    float64
}

// ConnectionPredictionResult - 连接预测结果
type ConnectionPredictionResult struct {
	MaxConnectionsLimit  int           `json:"max_connections_limit"`
	CurrentConnections   int           `json:"current_connections"`
	CurrentUsagePct      float64       `json:"current_usage_pct"`
	DetectedCycle        CyclePattern  `json:"detected_cycle"`
	PredictedPeakHour    int           `json:"predicted_peak_hour"`
	PredictedPeakValue   float64       `json:"predicted_peak_value"`
	PredictedPeakPct     float64       `json:"predicted_peak_pct"`
	Threshold80Risk      RiskLevel     `json:"threshold_80_risk"`
	Threshold90Risk      RiskLevel     `json:"threshold_90_risk"`
	Threshold100Risk     RiskLevel     `json:"threshold_100_risk"`
	NextPeakTime         time.Time     `json:"next_peak_time"`
	PredictionConfidence float64       `json:"prediction_confidence"`
	Recommendations      []string      `json:"recommendations"`
	WarningLevel         string        `json:"warning_level"`
	PredictionTimestamp  time.Time     `json:"prediction_timestamp"`
}

// RiskLevel - 风险等级评估
type RiskLevel struct {
	WillReach   bool   `json:"will_reach"`
	TimeToReach string `json:"time_to_reach"`
	HoursToPeak int    `json:"hours_to_peak"`
	Severity    string `json:"severity"`
}

// detectDailyCycle - 检测日周期模式
func detectDailyCycle(hourlyData []MetricDataPoint) *CyclePattern {
	if len(hourlyData) < 24 {
		return &CyclePattern{Type: CycleNone, Confidence: 0}
	}

	// 按小时分组统计
	hourStats := make(map[int][]float64)
	for _, point := range hourlyData {
		hour := int((point.Timestamp % 86400) / 3600)
		hourStats[hour] = append(hourStats[hour], point.Value)
	}

	// 计算每小时平均值
	hourAvg := make(map[int]float64)
	for hour, values := range hourStats {
		var sum float64
		for _, v := range values {
			sum += v
		}
		hourAvg[hour] = sum / float64(len(values))
	}

	// 找高峰和低谷时段
	var peakHour, offPeakHour int
	var peakValue, offPeakValue float64
	peakValue = -1
	offPeakValue = 1000000

	for hour, avg := range hourAvg {
		if avg > peakValue {
			peakValue = avg
			peakHour = hour
		}
		if avg < offPeakValue {
			offPeakValue = avg
			offPeakHour = hour
		}
	}

	// 计算波动幅度和置信度
	variance := peakValue - offPeakValue
	allValues := []float64{}
	for _, avg := range hourAvg {
		allValues = append(allValues, avg)
	}
	stdDev := calculateStdDev(allValues)
	mean := calculateMean(allValues)

	confidence := 0.0
	if mean > 0 && stdDev > 0 {
		coefOfVariation := stdDev / mean
		if coefOfVariation > 0.2 {
			confidence = math.Min(coefOfVariation/0.5, 1.0)
		}
	}

	return &CyclePattern{
		Type:          CycleDaily,
		PeakHour:      peakHour,
		PeakHourValue: peakValue,
		OffPeakValue:  offPeakValue,
		Variance:      variance,
		Confidence:    confidence,
	}
}

// detectWeeklyCycle - 检测周周期模式
func detectWeeklyCycle(dailyData []MetricDataPoint) *CyclePattern {
	if len(dailyData) < 7 {
		return &CyclePattern{Type: CycleNone, Confidence: 0}
	}

	// 按周几分组
	dayStats := make(map[int][]float64)
	for _, point := range dailyData {
		t := time.Unix(point.Timestamp, 0)
		dayOfWeek := int(t.Weekday())
		dayStats[dayOfWeek] = append(dayStats[dayOfWeek], point.Value)
	}

	// 计算每天平均值
	dayAvg := make(map[int]float64)
	for day, values := range dayStats {
		var sum float64
		for _, v := range values {
			sum += v
		}
		dayAvg[day] = sum / float64(len(values))
	}

	// 分析工作日vs周末模式
	workdayAvg := 0.0
	weekendAvg := 0.0
	workdayCount := 0
	weekendCount := 0

	for day, avg := range dayAvg {
		if day >= 1 && day <= 5 {
			workdayAvg += avg
			workdayCount++
		} else {
			weekendAvg += avg
			weekendCount++
		}
	}

	if workdayCount > 0 {
		workdayAvg /= float64(workdayCount)
	}
	if weekendCount > 0 {
		weekendAvg /= float64(weekendCount)
	}

	variance := workdayAvg - weekendAvg
	confidence := 0.0
	if workdayAvg > 0 {
		diffPct := math.Abs(variance) / workdayAvg
		if diffPct > 0.15 {
			confidence = math.Min(diffPct/0.3, 1.0)
		}
	}

	// 找高峰日
	peakDays := []int{}
	maxDayAvg := 0.0
	for day, avg := range dayAvg {
		if avg > maxDayAvg {
			maxDayAvg = avg
			peakDays = []int{day}
		} else if avg == maxDayAvg {
			peakDays = append(peakDays, day)
		}
	}

	// 转换为1-7格式
	peakDaysNormalized := []int{}
	for _, d := range peakDays {
		if d == 0 {
			peakDaysNormalized = append(peakDaysNormalized, 7)
		} else {
			peakDaysNormalized = append(peakDaysNormalized, d)
		}
	}

	return &CyclePattern{
		Type:          CycleWeekly,
		PeakDays:      peakDaysNormalized,
		PeakHourValue: maxDayAvg,
		OffPeakValue:  weekendAvg,
		Variance:      variance,
		Confidence:    confidence,
	}
}

// predictPeakConnection - 预测下一个高峰时段连接数
func predictPeakConnection(currentValue float64, cycle CyclePattern, historicalPeaks []float64) float64 {
	if len(historicalPeaks) == 0 {
		return currentValue * 1.2
	}

	var weightedSum float64
	var weightSum float64
	n := len(historicalPeaks)
	for i, peak := range historicalPeaks {
		weight := float64(n - i)
		weightedSum += peak * weight
		weightSum += weight
	}

	basePrediction := weightedSum / weightSum

	if cycle.OffPeakValue > 0 && cycle.Variance > 0 {
		ratioFromOffPeak := (currentValue - cycle.OffPeakValue) / cycle.Variance
		if ratioFromOffPeak < 0.3 {
			return basePrediction
		} else if ratioFromOffPeak > 0.7 {
			return basePrediction * 1.05
		}
	}

	return basePrediction
}

// assessThresholdRisk - 评估阈值风险
func assessThresholdRisk(predictedPeak float64, maxLimit int, thresholds []float64) []RiskLevel {
	risks := make([]RiskLevel, len(thresholds))

	for i, thresholdPct := range thresholds {
		thresholdValue := float64(maxLimit) * thresholdPct / 100
		willReach := predictedPeak >= thresholdValue

		severity := "low"
		if thresholdPct >= 100 {
			severity = "critical"
		} else if thresholdPct >= 90 {
			severity = "high"
		} else if thresholdPct >= 80 {
			severity = "medium"
		}

		risks[i] = RiskLevel{
			WillReach:   willReach,
			TimeToReach: "next_peak",
			HoursToPeak: 0,
			Severity:    severity,
		}
	}

	return risks
}

// calculateNextPeakTime - 计算下一个高峰时间
func calculateNextPeakTime(cycle CyclePattern, now time.Time) time.Time {
	if cycle.Type == CycleDaily {
		peakHour := cycle.PeakHour
		currentHour := now.Hour()

		peakTime := time.Date(now.Year(), now.Month(), now.Day(), peakHour, 0, 0, 0, now.Location())
		if currentHour >= peakHour {
			peakTime = peakTime.Add(24 * time.Hour)
		}
		return peakTime
	}

	if cycle.Type == CycleWeekly {
		currentDay := int(now.Weekday())
		if currentDay == 0 {
			currentDay = 7
		}

		minDiff := 7
		for _, peakDay := range cycle.PeakDays {
			diff := peakDay - currentDay
			if diff <= 0 {
				diff += 7
			}
			if diff < minDiff {
				minDiff = diff
			}
		}

		nextPeakDate := now.AddDate(0, 0, minDiff)
		peakHour := cycle.PeakHour
		if peakHour == 0 {
			peakHour = 10
		}
		return time.Date(nextPeakDate.Year(), nextPeakDate.Month(), nextPeakDate.Day(), peakHour, 0, 0, 0, now.Location())
	}

	return now.Add(24 * time.Hour)
}

// generateConnectionRecommendations - 生成连接优化建议
func generateConnectionRecommendations(result *ConnectionPredictionResult) []string {
	recommendations := []string{}

	switch result.WarningLevel {
	case "critical":
		recommendations = append(recommendations,
			"🚨 紧急: 连接数即将达到上限，立即采取措施",
			fmt.Sprintf("预测高峰连接数 %.0f，超过最大限制 %d", result.PredictedPeakValue, result.MaxConnectionsLimit),
			"建议立即执行: 增加max_connections配置或优化连接池")
	case "high":
		recommendations = append(recommendations,
			"⚠️ 高风险: 连接高峰将超过90%阈值",
			fmt.Sprintf("预测高峰时段 %s，连接利用率 %.1f%%", result.NextPeakTime.Format("2006-01-02 15:00"), result.PredictedPeakPct),
			"建议: 提前规划连接扩容或优化连接复用")
	case "medium":
		recommendations = append(recommendations,
			"ℹ️ 中等风险: 连接高峰接近80%阈值",
			fmt.Sprintf("业务周期: %s，高峰时段 %d:00", result.DetectedCycle.Type, result.DetectedCycle.PeakHour),
			"建议: 监控高峰时段连接情况，优化连接池配置")
	case "low":
		recommendations = append(recommendations,
			"✅ 低风险: 连接使用稳定，无瓶颈风险",
			fmt.Sprintf("当前连接数 %d，高峰预测 %.0f，容量充足", result.CurrentConnections, result.PredictedPeakValue))
	}

	if result.DetectedCycle.Type == CycleDaily && result.DetectedCycle.Confidence > 0.7 {
		recommendations = append(recommendations,
			fmt.Sprintf("日周期模式明显，高峰时段 %d:00-%d:00，建议提前预热连接池",
				result.DetectedCycle.PeakHour, result.DetectedCycle.PeakHour+2))
	}

	if result.PredictedPeakPct > 80 {
		suggestedMax := int(float64(result.MaxConnectionsLimit) * 1.2)
		recommendations = append(recommendations,
			fmt.Sprintf("建议调整max_connections: %d → %d (增加20%%)",
				result.MaxConnectionsLimit, suggestedMax))
	}

	return recommendations
}

// Helper functions
func calculateMean(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	var sum float64
	for _, v := range values {
		sum += v
	}
	return sum / float64(len(values))
}

func calculateStdDev(values []float64) float64 {
	if len(values) < 2 {
		return 0
	}
	mean := calculateMean(values)
	var variance float64
	for _, v := range values {
		variance += (v - mean) * (v - mean)
	}
	return math.Sqrt(variance / float64(len(values)))
}

func determineWarningLevel(predictedPeakPct float64) string {
	if predictedPeakPct >= 100 {
		return "critical"
	}
	if predictedPeakPct >= 90 {
		return "high"
	}
	if predictedPeakPct >= 80 {
		return "medium"
	}
	return "low"
}

// Main analysis function
func analyzeConnectionTrend(clusterId string, maxConnections int) (*ConnectionPredictionResult, error) {
	// Simplified - actual implementation would fetch from CMS
	data := []MetricDataPoint{} // Fetch from CMS

	if len(data) < 24 {
		return nil, fmt.Errorf("Insufficient data")
	}

	dailyCycle := detectDailyCycle(data)
	weeklyCycle := detectWeeklyCycle(data)

	var detectedCycle CyclePattern
	if dailyCycle.Confidence >= weeklyCycle.Confidence {
		detectedCycle = *dailyCycle
	} else {
		detectedCycle = *weeklyCycle
		if dailyCycle.Confidence > 0.5 {
			detectedCycle.PeakHour = dailyCycle.PeakHour
		}
	}

	currentData := data[len(data)-1]
	currentUsagePct := currentData.Value
	currentConnections := int(float64(maxConnections) * currentUsagePct / 100)

	historicalPeaks := []float64{}
	for _, point := range data {
		if point.Maximum > 0 {
			historicalPeaks = append(historicalPeaks, float64(maxConnections)*point.Maximum/100)
		}
	}
	if len(historicalPeaks) > 7 {
		historicalPeaks = historicalPeaks[len(historicalPeaks)-7:]
	}

	predictedPeakValue := predictPeakConnection(currentUsagePct, detectedCycle, historicalPeaks)
	predictedPeakPct := predictedPeakValue / float64(maxConnections) * 100

	nextPeakTime := calculateNextPeakTime(detectedCycle, time.Now())

	thresholds := []float64{80.0, 90.0, 100.0}
	risks := assessThresholdRisk(predictedPeakValue, maxConnections, thresholds)

	result := &ConnectionPredictionResult{
		MaxConnectionsLimit:   maxConnections,
		CurrentConnections:    currentConnections,
		CurrentUsagePct:       currentUsagePct,
		DetectedCycle:         detectedCycle,
		PredictedPeakHour:     detectedCycle.PeakHour,
		PredictedPeakValue:    predictedPeakValue,
		PredictedPeakPct:      predictedPeakPct,
		Threshold80Risk:       risks[0],
		Threshold90Risk:       risks[1],
		Threshold100Risk:      risks[2],
		NextPeakTime:          nextPeakTime,
		PredictionConfidence:  detectedCycle.Confidence,
		PredictionTimestamp:   time.Now(),
	}

	result.WarningLevel = determineWarningLevel(predictedPeakPct)
	result.Recommendations = generateConnectionRecommendations(result)

	return result, nil
}
```

## Output Format

### Markdown Analysis Report

```markdown
# PolarDB PostgreSQL 连接数趋势预测报告

> 预测时间: 2026-05-27 14:30:00 | 预测置信度: 0.88

## 当前连接状态

| 指标 | 当前值 | 状态 |
|------|--------|------|
| 当前连接数 | 2,850 | 中等 |
| 最大连接限制 | 5,000 | - |
| 当前利用率 | 57.0% | 正常 |

## 业务周期分析

| 周期类型 | 高峰时段 | 高峰平均值 | 低谷平均值 | 波动幅度 | 置信度 |
|----------|----------|------------|------------|----------|--------|
| **日周期** | 10:00-12:00 | 72.5% | 28.3% | 44.2% | 88% |
| **周周期** | 周一、周二 | 75.0% | 45.0% (周末) | 30.0% | 72% |

## 高峰连接预测

| 预测维度 | 预测值 | 利用率 | 时间 |
|----------|--------|--------|------|
| **下一个高峰** | 3,800 | 76.0% | 2026-05-28 10:00 |
| **本周高峰** | 4,200 | 84.0% | 2026-05-29 10:00 (周二) |

## 阈值风险评估

| 阈值 | 风险状态 | 预计时间 | 风险等级 |
|------|----------|----------|----------|
| **80%预警线** | ⚠️ 将达到 | 2026-05-28 10:00 | medium |
| **90%高危线** | ⚠️ 将达到 | 本周高峰时 | high |
| **100%上限** | ✅ 不会超过 | - | low |

## 预警级别: `medium`

## 优化建议

1. **ℹ️ 中等风险**: 连接高峰接近80%阈值
2. **业务周期**: daily，高峰时段 10:00
3. **建议**: 监控高峰时段连接情况，优化连接池配置
4. **日周期模式明显**, 高峰时段 10:00-12:00，建议提前预热连接池
```

## Acceptance Criteria

| # | Criteria | Detection Method |
|---|----------|------------------|
| ✓ | **周期模式检测准确率 > 80%** | `detectDailyCycle()` / `detectWeeklyCycle()` 返回 `Confidence > 0.8` |
| ✓ | **正确预测高峰时段** | `calculateNextPeakTime()` 返回合理时间点 |
| ✓ | **正确预测高峰连接数** | `predictPeakConnection()` 返回值误差 < 15% |
| ✓ | **阈值风险评估准确** | `assessThresholdRisk()` 正确识别 80%/90%/100% 风险 |

## Related References

- [AIOps Storage Prediction](aiops-storage-prediction.md) - 存储趋势预测
- [AIOps Anomaly Detection](aiops-anomaly-detection.md) - 异常检测联动
