# AIOps: PolarDB Connection Trend Prediction

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

### Cycle Detection Algorithm

| Algorithm | Best Use Case | Accuracy | Detection Method |
|-----------|---------------|----------|------------------|
| **FFT Analysis** | 规律性周期 | 90-95% | 频域分析识别主频率 |
| **Autocorrelation** | 多重周期叠加 | 85-92% | 自相关函数周期检测 |
| **Peak Detection** | 单峰模式 | 80-88% | 统计峰值时间分布 |
| **Seasonal Decomposition** | 季节性趋势 | 88-95% | STL分解趋势+季节+残差 |

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

### Step 2: Analyze Business Cycle Patterns

```bash
# 按小时聚合分析日周期
# 提取每小时平均连接数，识别高峰时段
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "$(date -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date +%Y-%m-%dT%H:%M:%SZ)" \
  --Statistics Average,Maximum \
  --Period 3600 \
  | jq '.Datapoints[] | {hour: (.timestamp % 86400 / 3600), value: .Average}'
```

### Step 3: Predict Peak Connections and Threshold Breach

Prediction logic is implemented in Go SDK (see below).

## Implementation

### CLI (Primary Path - Data Collection)

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

# 4. 获取活跃会话峰值记录
aliyun cms GetMetricStatisticsData \
  --Namespace acs_polardb_dashboard \
  --MetricName ActiveSessions \
  --Dimensions '{"instanceId":"{{user.db_cluster_id}}"}' \
  --StartTime "$(date -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date +%Y-%m-%dT%H:%M:%SZ)" \
  --Statistics Maximum \
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
	"sort"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	cms "github.com/alibabacloud-go/cms-20250101/v1/client"
)

// ===== Data Structures =====

// MetricDataPoint - CMS指标数据点
type MetricDataPoint struct {
	Timestamp   int64   `json:"timestamp"`
	Value       float64 `json:"Average"`
	Maximum     float64 `json:"Maximum,omitempty"`
	Minimum     float64 `json:"Minimum,omitempty"`
}

// CycleType - 业务周期类型
type CycleType string

const (
	CycleDaily   CycleType = "daily"   // 日周期
	CycleWeekly  CycleType = "weekly"  // 周周期
	CycleMonthly CycleType = "monthly" // 月周期
	CycleNone    CycleType = "none"    // 无明显周期
)

// CyclePattern - 周期模式检测结果
type CyclePattern struct {
	Type           CycleType
	PeakHour       int       // 高峰时段（小时）
	PeakDays       []int     // 高峰日（周几，1-7）
	PeakHourValue  float64   // 高峰时段平均连接数
	OffPeakValue   float64   // 低谷时段平均连接数
	Variance       float64   // 周期内波动幅度
	Confidence     float64   // 周期检测置信度 0-1
}

// PeekHour getter for backward compatibility
func (c *CyclePattern) PeekHour() int {
	return c.PeakHour
}

// ConnectionPredictionResult - 连接预测结果
type ConnectionPredictionResult struct {
	MaxConnectionsLimit   int           `json:"max_connections_limit"`
	CurrentConnections    int           `json:"current_connections"`
	CurrentUsagePct       float64       `json:"current_usage_pct"`
	DetectedCycle         CyclePattern  `json:"detected_cycle"`
	PredictedPeakHour     int           `json:"predicted_peak_hour"`
	PredictedPeakValue    float64       `json:"predicted_peak_value"`
	PredictedPeakPct      float64       `json:"predicted_peak_pct"`
	Threshold80Risk       RiskLevel     `json:"threshold_80_risk"`
	Threshold90Risk       RiskLevel     `json:"threshold_90_risk"`
	Threshold100Risk      RiskLevel     `json:"threshold_100_risk"`
	NextPeakTime          time.Time     `json:"next_peak_time"`
	PredictionConfidence  float64       `json:"prediction_confidence"`
	Recommendations       []string      `json:"recommendations"`
	WarningLevel          string        `json:"warning_level"`  // low/medium/high/critical
	PredictionTimestamp   time.Time     `json:"prediction_timestamp"`
}

// RiskLevel - 风险等级评估
type RiskLevel struct {
	WillReach    bool    `json:"will_reach"`     // 是否会达到
	TimeToReach  string  `json:"time_to_reach"`  // 预计到达时间
	HoursToPeak  int     `json:"hours_to_peak"`  // 距离高峰小时数
	Severity     string  `json:"severity"`       // low/medium/high/critical
}

// NewRiskLevel - 创建风险等级实例
func NewRiskLevel(willReach bool, timeToReach string, severity string) RiskLevel {
	return RiskLevel{
		WillReach:   willReach,
		TimeToReach: timeToReach,
		HoursToPeak: 0, // 默认值，后续可计算
		Severity:    severity,
	}
}

// ===== Cycle Detection Algorithms =====

// detectDailyCycle - 检测日周期模式
// 分析24小时内连接数分布，识别高峰时段
func detectDailyCycle(hourlyData []MetricDataPoint) *CyclePattern {
	if len(hourlyData) < 24 {
		return &CyclePattern{Type: CycleNone, Confidence: 0}
	}

	// 按小时分组统计
	hourStats := make(map[int][]float64)
	for _, point := range hourlyData {
		// 计算小时（从timestamp）
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

	// 置信度：波动幅度相对于标准差的比例
	confidence := 0.0
	if mean > 0 && stdDev > 0 {
		coefOfVariation := stdDev / mean
		// 波动系数越大，周期性越明显
		if coefOfVariation > 0.2 {
			confidence = math.Min(coefOfVariation / 0.5, 1.0)
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
// 分析7天内连接数分布，识别工作日vs周末模式
func detectWeeklyCycle(dailyData []MetricDataPoint) *CyclePattern {
	if len(dailyData) < 7 {
		return &CyclePattern{Type: CycleNone, Confidence: 0}
	}

	// 按周几分组（0=周日, 1=周一, ..., 6=周六）
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

	// 找高峰日（工作日 vs 周末）
	workdayAvg := 0.0
	weekendAvg := 0.0
	workdayCount := 0
	weekendCount := 0

	for day, avg := range dayAvg {
		if day >= 1 && day <= 5 { // 周一到周五
			workdayAvg += avg
			workdayCount++
		} else { // 周末
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

	// 检测是否有明显的周模式
	variance := workdayAvg - weekendAvg
	confidence := 0.0
	if workdayAvg > 0 {
		diffPct := math.Abs(variance) / workdayAvg
		if diffPct > 0.15 { // 工作日和周末差异超过15%
			confidence = math.Min(diffPct / 0.3, 1.0)
		}
	}

	// 找具体高峰日
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

	// 转换为1-7格式（周一=1，周日=7）
	peakDaysNormalized := []int{}
	for _, d := range peakDays {
		if d == 0 {
			peakDaysNormalized = append(peakDaysNormalized, 7)
		} else {
			peakDaysNormalized = append(peakDaysNormalized, d)
		}
	}

	return &CyclePattern{
		Type:         CycleWeekly,
		PeakDays:     peakDaysNormalized,
		PeakHourValue: maxDayAvg,
		OffPeakValue: weekendAvg,
		Variance:     variance,
		Confidence:   confidence,
	}
}

// predictPeakConnection - 预测下一个高峰时段连接数
func predictPeakConnection(currentValue float64, cycle CyclePattern, historicalPeaks []float64) float64 {
	// 基于历史高峰值和周期模式预测
	if len(historicalPeaks) == 0 {
		return currentValue * 1.2 // 默认预测增加20%
	}

	// 使用历史高峰值的加权平均
	// 近期权重更高
	var weightedSum float64
	var weightSum float64
	n := len(historicalPeaks)
	for i, peak := range historicalPeaks {
		weight := float64(n - i) // 近期权重更高
		weightedSum += peak * weight
		weightSum += weight
	}

	basePrediction := weightedSum / weightSum

	// 根据当前值与低谷值的比例调整
	if cycle.OffPeakValue > 0 && cycle.Variance > 0 {
		// 如果当前接近低谷，预测高峰；如果当前接近高峰，保持
		ratioFromOffPeak := (currentValue - cycle.OffPeakValue) / cycle.Variance
		if ratioFromOffPeak < 0.3 {
			// 当前处于低谷期，预测高峰值
			return basePrediction
		} else if ratioFromOffPeak > 0.7 {
			// 当前已接近高峰，预测略高
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
			TimeToReach: "next_peak", // 下一个高峰时段
			HoursToPeak: 0,            // 后续由 calculateNextPeakTime 计算
			Severity:    severity,
		}
	}

	return risks
}

// calculateNextPeakTime - 计算下一个高峰时间
func calculateNextPeakTime(cycle CyclePattern, now time.Time) time.Time {
	if cycle.Type == CycleDaily {
		// 计算今天或明天的高峰时段
		peakHour := cycle.PeakHour
		currentHour := now.Hour()

		peakTime := time.Date(now.Year(), now.Month(), now.Day(), peakHour, 0, 0, 0, now.Location())
		if currentHour >= peakHour {
			// 已过今日高峰，预测明日高峰
			peakTime = peakTime.Add(24 * time.Hour)
		}
		return peakTime
	}

	if cycle.Type == CycleWeekly {
		// 计算下一个高峰日
		currentDay := int(now.Weekday())
		if currentDay == 0 {
			currentDay = 7
		}

		// 找最近的高峰日
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
			peakHour = 10 // 默认上午10点高峰
		}
		return time.Date(nextPeakDate.Year(), nextPeakDate.Month(), nextPeakDate.Day(), peakHour, 0, 0, 0, now.Location())
	}

	// 无周期，预测24小时后
	return now.Add(24 * time.Hour)
}

// generateConnectionRecommendations - 生成连接优化建议
func generateConnectionRecommendations(result *ConnectionPredictionResult) []string {
	recommendations := []string{}

	// 根据预警级别生成建议
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

	// 周期优化建议
	if result.DetectedCycle.Type == CycleDaily && result.DetectedCycle.Confidence > 0.7 {
		recommendations = append(recommendations,
			fmt.Sprintf("日周期模式明显，高峰时段 %d:00-%d:00，建议提前预热连接池",
				result.DetectedCycle.PeakHour, result.DetectedCycle.PeakHour+2))
	}

	if result.DetectedCycle.Type == CycleWeekly && len(result.DetectedCycle.PeakDays) > 0 {
		recommendations = append(recommendations,
			fmt.Sprintf("周周期模式，高峰日为周%d，建议工作日前做好连接准备",
				result.DetectedCycle.PeakDays[0]))
	}

	// 连接池配置建议
	if result.PredictedPeakPct > 80 {
		suggestedMax := int(float64(result.MaxConnectionsLimit) * 1.2)
		recommendations = append(recommendations,
			fmt.Sprintf("建议调整max_connections: %d → %d (增加20%%)",
				result.MaxConnectionsLimit, suggestedMax))
	}

	// 连接复用建议
	if result.CurrentUsagePct > 50 {
		recommendations = append(recommendations,
			"建议检查应用连接池配置，启用连接复用和超时回收",
			"建议设置连接池最大连接数略小于max_connections的80%")
	}

	return recommendations
}

// determineWarningLevel - 确定预警级别
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

// ===== Helper Functions =====

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

// fetchHistoricalConnectionMetrics - 从CMS获取历史连接指标
func fetchHistoricalConnectionMetrics(clusterId string, days int) ([]MetricDataPoint, error) {
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
		MetricName:  tea.String("ConnectionUsage"),
		Dimensions:  tea.String(fmt.Sprintf("{\"instanceId\":\"%s\"}", clusterId)),
		StartTime:   tea.String(startTime.Format("2006-01-02T15:04:05Z")),
		EndTime:     tea.String(endTime.Format("2006-01-02T15:04:05Z")),
		Statistics:  tea.String("Average,Maximum"),
		Period:      tea.Int64(3600), // 每小时粒度
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

	// 按时间排序
	sort.Slice(datapoints, func(i, j int) bool {
		return datapoints[i].Timestamp < datapoints[j].Timestamp
	})

	return datapoints, nil
}

// ===== Main Analysis Function =====

// analyzeConnectionTrend - 执行完整连接趋势分析
func analyzeConnectionTrend(clusterId string, maxConnections int) (*ConnectionPredictionResult, error) {
	// 获取14天历史数据
	data, err := fetchHistoricalConnectionMetrics(clusterId, 14)
	if err != nil {
		return nil, err
	}

	if len(data) < 24 {
		return nil, fmt.Errorf("Insufficient historical data: need at least 24 hours, got %d datapoints", len(data))
	}

	// ===== 周期检测 =====
	dailyCycle := detectDailyCycle(data)
	weeklyCycle := detectWeeklyCycle(data)

	// 选择置信度更高的周期
	var detectedCycle CyclePattern
	if dailyCycle.Confidence >= weeklyCycle.Confidence {
		detectedCycle = *dailyCycle
	} else {
		detectedCycle = *weeklyCycle
		// 保留日周期的高峰时段信息
		if dailyCycle.Confidence > 0.5 {
			detectedCycle.PeakHour = dailyCycle.PeekHour
		}
	}

	// 如果都没检测到周期
	if detectedCycle.Confidence < 0.3 {
		detectedCycle = CyclePattern{
			Type:       CycleNone,
			Confidence: 0,
			PeakHour:   10, // 默认上午10点
		}
	}

	// ===== 当前连接状态 =====
	currentData := data[len(data)-1]
	currentUsagePct := currentData.Value
	currentConnections := int(float64(maxConnections) * currentUsagePct / 100)

	// ===== 提取历史高峰值 =====
	historicalPeaks := []float64{}
	for _, point := range data {
		if point.Maximum > 0 {
			historicalPeaks = append(historicalPeaks, float64(maxConnections) * point.Maximum / 100)
		}
	}
	// 取最近7天的峰值
	if len(historicalPeaks) > 7 {
		historicalPeaks = historicalPeaks[len(historicalPeaks)-7:]
	}

	// ===== 预测高峰连接数 =====
	predictedPeakValue := predictPeakConnection(currentUsagePct, detectedCycle, historicalPeaks)
	predictedPeakPct := predictedPeakValue / float64(maxConnections) * 100

	// ===== 计算下一个高峰时间 =====
	nextPeakTime := calculateNextPeakTime(detectedCycle, time.Now())

	// ===== 评估阈值风险 =====
	thresholds := []float64{80.0, 90.0, 100.0}
	risks := assessThresholdRisk(predictedPeakValue, maxConnections, thresholds)

	// ===== 构建结果 =====
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

	// 确定预警级别
	result.WarningLevel = determineWarningLevel(predictedPeakPct)

	// 生成建议
	result.Recommendations = generateConnectionRecommendations(result)

	return result, nil
}

// validatePredictionAccuracy - 验证预测准确率
// 使用历史数据进行回测
func validatePredictionAccuracy(clusterId string) float64 {
	// 获取14天历史数据用于回测
	data, err := fetchHistoricalConnectionMetrics(clusterId, 14)
	if err != nil || len(data) < 168 { // 7天*24小时
		return 0 // 无法验证
	}

	// 使用前7天训练模型，预测第14天的峰值
	trainData := data[:168]  // 前7天
	testData := data[168:]   // 后7天

	// 检测周期
	dailyCycle := detectDailyCycle(trainData)

	// 找测试数据的实际高峰值
	var actualPeak float64
	for _, point := range testData {
		if point.Maximum > actualPeak {
			actualPeak = point.Maximum
		}
	}

	// 预测高峰值
	historicalPeaks := []float64{}
	for _, point := range trainData[len(trainData)-7:] {
		if point.Maximum > 0 {
			historicalPeaks = append(historicalPeaks, point.Maximum)
		}
	}
	predictedPeak := predictPeakConnection(trainData[len(trainData)-1].Value, *dailyCycle, historicalPeaks)

	// 计算误差率
	if actualPeak == 0 {
		return 0
	}
	errorRate := math.Abs(predictedPeak - actualPeak) / actualPeak * 100

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

	// 获取max_connections配置（实际应从 DescribeDBClusterAttribute 获取）
	// 此处使用示例值
	maxConnections := 5000

	// 执行趋势分析
	result, err := analyzeConnectionTrend(clusterId, maxConnections)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to analyze connection trend: %v\n", err)
		os.Exit(1)
	}

	// ===== 输出预测报告 =====
	fmt.Println("=== PolarDB 连接数趋势预测 ===")
	fmt.Printf("预测时间: %s\n", result.PredictionTimestamp.Format("2006-01-02 15:04:05"))
	fmt.Printf("预测置信度: %.2f\n", result.PredictionConfidence)
	fmt.Printf("\n当前连接状态:\n")
	fmt.Printf("  ├─ 当前连接数: %d\n", result.CurrentConnections)
	fmt.Printf("  ├─ 最大连接限制: %d\n", result.MaxConnectionsLimit)
	fmt.Printf("  └─ 当前利用率: %.2f%%\n", result.CurrentUsagePct)

	fmt.Printf("\n业务周期分析:\n")
	fmt.Printf("  ├─ 周期类型: %s\n", result.DetectedCycle.Type)
	if result.DetectedCycle.Type == CycleDaily {
		fmt.Printf("  ├─ 高峰时段: %d:00\n", result.DetectedCycle.PeakHour)
		fmt.Printf("  ├─ 高峰平均: %.1f%%\n", result.DetectedCycle.PeakHourValue)
		fmt.Printf("  ├─ 低谷平均: %.1f%%\n", result.DetectedCycle.OffPeakValue)
		fmt.Printf("  └─ 波动幅度: %.1f%%\n", result.DetectedCycle.Variance)
	}
	if result.DetectedCycle.Type == CycleWeekly {
		fmt.Printf("  ├─ 高峰日: 周%d\n", result.DetectedCycle.PeakDays[0])
	}

	fmt.Printf("\n高峰预测:\n")
	fmt.Printf("  ├─ 预测高峰连接数: %.0f\n", result.PredictedPeakValue)
	fmt.Printf("  ├─ 预测高峰利用率: %.1f%%\n", result.PredictedPeakPct)
	fmt.Printf("  ├─ 下一个高峰时间: %s\n", result.NextPeakTime.Format("2006-01-02 15:00"))

	fmt.Printf("\n阈值风险评估:\n")
	fmt.Printf("  ├─ 80%%阈值: %s (风险等级: %s)\n",
		boolStr(result.Threshold80Risk.WillReach, "将达到", "不会达到"),
		result.Threshold80Risk.Severity)
	fmt.Printf("  ├─ 90%%阈值: %s (风险等级: %s)\n",
		boolStr(result.Threshold90Risk.WillReach, "将达到", "不会达到"),
		result.Threshold90Risk.Severity)
	fmt.Printf("  └─ 100%%上限: %s (风险等级: %s)\n",
		boolStr(result.Threshold100Risk.WillReach, "将超过", "不会超过"),
		result.Threshold100Risk.Severity)

	fmt.Printf("\n预警级别: %s\n", result.WarningLevel)
	fmt.Printf("\n优化建议:\n")
	for i, rec := range result.Recommendations {
		fmt.Printf("  %d. %s\n", i+1, rec)
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

func boolStr(b bool, trueStr, falseStr string) string {
	if b {
		return trueStr
	}
	return falseStr
}
```

## Output Format

### Markdown Analysis Report Example

```markdown
# PolarDB 连接数趋势预测报告

> 预测时间: 2026-05-26 14:30:00 | 预测置信度: 0.88

## 当前连接状态

| 指标 | 当前值 | 状态 |
|------|--------|------|
| 当前连接数 | 2,850 | 中等 |
| 最大连接限制 | 5,000 | - |
| 当前利用率 | 57.0% | 正常 |

## 业务周期分析

### 检测到的周期模式

| 周期类型 | 高峰时段 | 高峰平均值 | 低谷平均值 | 波动幅度 | 置信度 |
|----------|----------|------------|------------|----------|--------|
| **日周期** | 10:00-12:00 | 72.5% | 28.3% | 44.2% | 88% |
| **周周期** | 周一、周二 | 75.0% | 45.0% (周末) | 30.0% | 72% |

### 周期特征描述

```
业务周期模式:
┌─────────────────────────────────────────────────────────────┐
│ 日周期: 早10点高峰，晚8点低谷                                  │
│     10:00 ████████████████████████ 72.5% (高峰)              │
│     14:00 ████████████████ 55.0% (回落)                      │
│     20:00 ████████ 28.3% (低谷)                              │
│                                                              │
│ 周周期: 工作日高，周末低                                       │
│     Mon-Tue ████████████████████████ 高峰                   │
│     Wed-Fri ████████████████ 中等                           │
│     Sat-Sun ████████ 低谷                                   │
└─────────────────────────────────────────────────────────────┘
```

## 高峰连接预测

| 预测维度 | 预测值 | 利用率 | 时间 |
|----------|--------|--------|------|
| **下一个高峰** | 3,800 | 76.0% | 2026-05-27 10:00 |
| **本周高峰** | 4,200 | 84.0% | 2026-05-28 10:00 (周二) |
| **峰值极值** | 4,500 | 90.0% | 历史最高预测 |

## 阈值风险评估

| 阈值 | 风险状态 | 预计时间 | 风险等级 | 建议行动 |
|------|----------|----------|----------|----------|
| **80%预警线** | ⚠️ 将达到 | 2026-05-28 10:00 | medium | 监控关注 |
| **90%高危线** | ⚠️ 将达到 | 本周高峰时 | high | 提前扩容 |
| **100%上限** | ✅ 不会超过 | - | low | 无需紧急处理 |

## 预警级别: `medium`

```
当前状态: 连接高峰接近80%阈值，建议中期规划
风险评级: 中等风险
建议时间窗: 下一个高峰时段前做好准备
```

## 优化建议

### 立即执行 (P0)
1. **ℹ️ 中等风险**: 连接高峰接近80%阈值
2. **业务周期**: daily，高峰时段 10:00
3. **建议**: 监控高峰时段连接情况，优化连接池配置

### 短期优化 (P1)
1. **日周期模式明显**, 高峰时段 10:00-12:00，建议提前预热连接池
2. **建议调整max_connections**: 5000 → 6000 (增加20%)
3. **建议检查应用连接池配置**, 启用连接复用和超时回收

### 长期规划 (P2)
1. 根据业务增长趋势，季度评估连接需求
2. 考虑读写分离分流连接压力
3. 监控连接峰值变化，动态调整配置

## 预测准确率验证

| 验证方法 | 结果 | 状态 |
|----------|------|------|
| 回测7天历史 | 准确率 85.2% | ✅ 合格 |
| 周期检测置信度 | 88% | 高置信度 |
| 误差范围 | ±3.5% | 低误差 |

> **验收结论**: ✅ 预测模型准确率 > 80%，符合验收标准
```

### JSON Output Format

```json
{
  "prediction_timestamp": "2026-05-26T14:30:00Z",
  "prediction_confidence": 0.88,
  "max_connections_limit": 5000,
  "current_connections": 2850,
  "current_usage_pct": 57.0,
  "detected_cycle": {
    "type": "daily",
    "peak_hour": 10,
    "peak_days": [1, 2],
    "peak_hour_value": 72.5,
    "off_peak_value": 28.3,
    "variance": 44.2,
    "confidence": 0.88
  },
  "predicted_peak_hour": 10,
  "predicted_peak_value": 3800,
  "predicted_peak_pct": 76.0,
  "threshold_80_risk": {
    "will_reach": true,
    "time_to_reach": "next_peak",
    "hours_to_peak": 4,
    "severity": "medium"
  },
  "threshold_90_risk": {
    "will_reach": true,
    "time_to_reach": "weekly_peak",
    "hours_to_peak": 48,
    "severity": "high"
  },
  "threshold_100_risk": {
    "will_reach": false,
    "time_to_reach": "none",
    "severity": "low"
  },
  "next_peak_time": "2026-05-27T10:00:00Z",
  "warning_level": "medium",
  "recommendations": [
    "ℹ️ 中等风险: 连接高峰接近80%阈值",
    "业务周期: daily，高峰时段 10:00",
    "建议: 监控高峰时段连接情况，优化连接池配置",
    "日周期模式明显，高峰时段 10:00-12:00，建议提前预热连接池",
    "建议调整max_connections: 5000 → 6000 (增加20%)",
    "建议检查应用连接池配置，启用连接复用和超时回收"
  ],
  "validation_accuracy": 85.2
}
```

## Acceptance Criteria (验收标准)

| # | Criteria | Detection Method |
|---|----------|------------------|
| ✓ | **周期模式检测准确率 > 80%** | `detectDailyCycle()` / `detectWeeklyCycle()` 返回 `Confidence > 0.8` |
| ✓ | **正确预测高峰时段** | `calculateNextPeakTime()` 返回合理时间点 |
| ✓ | **正确预测高峰连接数** | `predictPeakConnection()` 返回值误差 < 15% |
| ✓ | **阈值风险评估准确** | `assessThresholdRisk()` 正确识别 80%/90%/100% 风险 |
| ✓ | **根据风险级别生成建议** | `generateConnectionRecommendations()` 返回至少3条建议 |
| ✓ | **预测准确率验证 > 80%** | `validatePredictionAccuracy()` 回测结果 > 80% |

### Connection Prediction Accuracy Validation

```go
// 验证连接预测准确率的核心逻辑
func validatePredictionAccuracy(clusterId string) float64 {
    // 1. 获取14天历史数据
    data := fetchHistoricalConnectionMetrics(clusterId, 14)

    // 2. 使用前7天训练周期模型
    trainData := data[:168]  // 7天*24小时

    // 3. 检测周期模式
    cycle := detectDailyCycle(trainData)

    // 4. 预测后7天的峰值
    historicalPeaks := extractPeaks(trainData[168-24:])
    predictedPeak := predictPeakConnection(trainData[len(trainData)-1].Value, *cycle, historicalPeaks)

    // 5. 计算与实际峰值的误差
    actualPeak := findMaxPeak(data[168:])
    errorRate := abs(predictedPeak - actualPeak) / actualPeak * 100

    // 6. 准确率 = 100 - 误差率
    accuracy := 100 - errorRate

    return accuracy // 要求 ≥ 80%
}
```

## Alert Threshold Configuration

| Threshold | Action | Time Window | Escalation |
|-----------|--------|-------------|------------|
| **80%** | 启动连接池优化评估 | 下一个高峰前 | 发送预警通知 |
| **90%** | 执行连接扩容或限流 | 高峰时段前 | 发送高危通知 |
| **100%** | 紧急扩容/连接释放 | 立即 | 发送紧急通知 |

## Connection Pool Best Practices

### 推荐连接池配置

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| **max_connections** | 高峰预测值 × 1.2 | 预留20%缓冲 |
| **connection_pool_max** | max_connections × 0.8 | 连接池不超过数据库上限的80% |
| **connection_timeout** | 30s | 连接获取超时 |
| **idle_timeout** | 600s | 空闲连接回收时间 |
| **max_lifetime** | 1800s | 连接最大生命周期 |

### 高峰时段预热建议

```sql
-- 高峰前10分钟执行连接预热
-- 检查当前连接数
SHOW STATUS LIKE 'Threads_connected';

-- 检查最大连接限制
SHOW VARIABLES LIKE 'max_connections';

-- 检查活跃连接
SHOW PROCESSLIST;
```

## Failure Recovery

| Error pattern | Agent Action |
|---------------|--------------|
| Historical data insufficient (< 24 hours) | HALT; return error with data requirements |
| CMS endpoint timeout | Retry with exponential backoff (3 attempts) |
| Cycle confidence < 0.3 | Use default cycle pattern (daily 10:00 peak) |
| Zero or negative prediction | Use current value + 20% as fallback |
| JSON parsing failure | Return raw CMS response for manual analysis |

## Integration with Well-Architected Framework

> Extends **可靠性** 审查维度: 连接瓶颈预警 + 连接池优化 + 高峰时段规划

### Reliability Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Connection Prediction Accuracy | > 80% | Alert if < 75% |
| Peak Connection Headroom | > 20% buffer | Alert if predicted > 80% |
| Connection Pool Efficiency | > 70% reuse | Alert if idle < 30% |
| Cycle Detection Confidence | > 0.7 | Alert if < 0.5 |

## Related References

- [CLI Usage](cli-usage.md) - `aliyun cms GetMetricStatisticsData` 详细参数说明
- [API/SDK Usage](api-sdk-usage.md) - CMS SDK 完整接口文档
- [Monitoring](monitoring.md) - PolarDB 连接指标监控配置
- [AIOps Anomaly Detection](aiops-anomaly-detection.md) - 连接异常检测联动
- [AIOps Storage Prediction](aiops-storage-prediction.md) - 存储趋势预测模式参考