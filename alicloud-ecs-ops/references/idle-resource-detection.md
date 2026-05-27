# 闲置资源检测

## 检测维度

| 维度 | 数据源 | 阈值 | 说明 |
|------|--------|------|------|
| 无API调用 | ActionTrail | 30天无ECS API调用 | 排除自动化管理的实例 |
| 无登录 | ActionTrail登录日志 | 30天无SSH/RDP登录 | 排除有运维登录的实例 |
| 无流量 | CloudMonitor InternetOutRate | 30天平均出流量 < 1MB | 排除有定期任务的实例 |
| 无CPU活动 | CloudMonitor CPUUtilization | 30天CPU使用率 < 1% | 排除后台任务的实例 |

## 分类

| 分类 | 条件 | 建议操作 |
|------|------|----------|
| 活跃实例 | 满足任一活跃条件 | 保留 |
| 低频实例 | 30天无API但有登录或有流量 | 降配或检查用途 |
| 疑似闲置 | 30天无登录+无流量+无API | 下线回收 |
| 确定闲置 | 90天无任何活动 | 强制下线回收 |

## CLI 检测

```bash
# 检查流量和CPU
aliyun cms DescribeMetricList --Namespace acs_ecs_dashboard --MetricName InternetOutRate --Dimensions '[{"instanceId":"{{instance_id}}"}]' --StartTime "$(date -u -v-30D +%Y-%m-%dT%H:%MZ)" --EndTime "$(date -u +%Y-%m-%dT%H:%MZ)" --Period 86400 --Aggregate Average
aliyun cms DescribeMetricList --Namespace acs_ecs_dashboard --MetricName CPUUtilization --Dimensions '[{"instanceId":"{{instance_id}}"}]' --StartTime "$(date -u -v-30D +%Y-%m-%dT%H:%MZ)" --EndTime "$(date -u +%Y-%m-%dT%H:%MZ)" --Period 86400 --Aggregate Average

# 检查ActionTrail事件
aliyun actiontrail DescribeTrails --RegionId "{{user.region}}"
```

## 集成点

- **ActionTrail**: 需启用并投递到SLS/OSS
- **CloudMonitor**: 查询流量和CPU指标
- **MNS**: 闲置告警通知