# 预测性容量分析

## 预测模型

| 模型 | 输入 | 输出 | 用途 |
|------|------|------|------|
| CPU趋势预测 | 30天历史 | 未来7天预测 | 提前扩容 |
| 磁盘容量预测 | 使用率趋势 | 磁盘满预警 | 提前扩容 |

## CLI 数据采集

```bash
# 采集30天CPU数据
aliyun cms DescribeMetricList --Namespace acs_ecs_dashboard --MetricName CPUUtilization --Dimensions '[{"instanceId":"{{instance_id}}"}]' --StartTime "$(date -u -d '30 days ago' +%Y-%m-%dT%H:%MZ 2>/dev/null || date -u -v-30D +%Y-%m-%dT%H:%MZ 2>/dev/null)" --EndTime "$(date -u +%Y-%m-%dT%H:%MZ)" --Period 3600 --Aggregate Average

# 线性回归推算增长趋势
# 增长率 = (最新值 - 30天前值) / 30
# 预测值 = 当前值 + (日均增长 × 预测天数)
```

## Auto-Scaling 集成

```bash
aliyun ess CreateScalingRule \
  --ScalingGroupId "ess-xxx" \
  --ScalingRuleType "Predictive" \
  --MetricName cpu --TargetValue 70 \
  --PredictionTimeZone "Asia/Shanghai"
```