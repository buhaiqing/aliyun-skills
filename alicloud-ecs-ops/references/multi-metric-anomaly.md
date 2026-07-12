# 多指标异常巡检

## 异常模式

| 模式 | 检测条件 | 严重度 | 自动操作 |
|------|----------|--------|----------|
| CPU-Memory 双高 | CPU > 90% AND Memory > 85% 持续5分钟 | Critical | Auto-scale / 重启 |
| 磁盘-IO 瓶颈 | DiskUsage > 90% AND IOPS > 80% | High | 扩容/升级SSD |
| 突变检测 | 指标变化率 > 阈值/分钟 | Medium | 告警/日志分析 |
| 网络流量突增 | NetworkIn/Out > 3x baseline 持续3分钟 | Medium | 流量分析/DDoS检查 |

## CLI 数据采集

```bash
INSTANCE_ID="{{user.instance_id}}"
START_TIME="$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%MZ 2>/dev/null || date -u -v-10M +%Y-%m-%dT%H:%MZ 2>/dev/null)"
END_TIME="$(date -u +%Y-%m-%dT%H:%MZ)"

aliyun cms DescribeMetricList --Namespace acs_ecs_dashboard --MetricName CPUUtilization --Dimensions '[{"instanceId":"'$INSTANCE_ID'"}]' --StartTime "$START_TIME" --EndTime "$END_TIME" --Period 60
aliyun cms DescribeMetricList --Namespace acs_ecs_dashboard --MetricName memory_usedutilization --Dimensions '[{"instanceId":"'$INSTANCE_ID'"}]' --StartTime "$START_TIME" --EndTime "$END_TIME" --Period 60
aliyun cms DescribeMetricList --Namespace acs_ecs_dashboard --MetricName DiskUsage --Dimensions '[{"instanceId":"'$INSTANCE_ID'"}]' --StartTime "$START_TIME" --EndTime "$END_TIME" --Period 60
```

## 恢复操作

| 模式 | 自动恢复 | 手动恢复 |
|------|----------|----------|
| CPU-Memory 双高 | 触发Auto Scaling | 重启/优化进程 |
| 磁盘-IO 瓶颈 | 扩容/升级SSD | 清理/归档 |
| 网络流量突增 | 启用DDoS防护 | 审查流量来源 |