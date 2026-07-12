# Monitoring CloudMonitor (CMS)

## Self-Monitoring

CloudMonitor itself can be monitored to ensure the monitoring pipeline is healthy.

### Key Health Indicators

| Indicator | Check Method | Healthy State |
|-----------|-------------|---------------|
| API availability | `aliyun cms DescribeProjectMeta` | `Success: true` |
| Metric collection | `DescribeMetricLast` on known resource | Datapoint within last 5 minutes |
| Alarm rule count | `DescribeMetricAlarmList` | Count matches expected |
| Quota usage | Track API call count | < 80% of 1M/month |

### Health Check Script

```bash
#!/bin/bash
# cms-self-check.sh

REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"

echo "=== CMS Self-Health Check ==="

# 1. API availability
echo "1. API Availability:"
aliyun cms DescribeProjectMeta --RegionId "$REGION" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ API reachable"
else
    echo "   ❌ API unreachable"
fi

# 2. List alarm rules
echo -e "\n2. Alarm Rules:"
COUNT=$(aliyun cms DescribeMetricAlarmList --RegionId "$REGION" --PageSize 1 2>/dev/null | jq -r '.Total // 0')
echo "   Total alarm rules: $COUNT"

# 3. Contact groups
echo -e "\n3. Contact Groups:"
aliyun cms DescribeContactGroupList --RegionId "$REGION" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Contact groups accessible"
else
    echo "   ❌ Cannot list contact groups"
fi

echo -e "\n=== Check Complete ==="
```

## Key Metrics for Common Products

### ECS Metrics

| Metric | Namespace | Description | Typical Threshold |
|--------|-----------|-------------|-------------------|
| CPUUtilization | acs_ecs_dashboard | CPU usage % | > 80% warning, > 95% critical |
| memory_usedutilization | acs_ecs_dashboard | Memory usage % | > 80% warning |
| DiskUsage | acs_ecs_dashboard | Disk usage % | > 80% warning, > 90% critical |
| InternetInRate | acs_ecs_dashboard | Network in bps | Baseline + 3σ |
| InternetOutRate | acs_ecs_dashboard | Network out bps | Baseline + 3σ |
| LoadAverage | acs_ecs_dashboard | 1-min load avg | > vCPU count |

### RDS Metrics

| Metric | Namespace | Description | Typical Threshold |
|--------|-----------|-------------|-------------------|
| CpuUsage | acs_rds_dashboard | CPU usage % | > 80% warning |
| MemoryUsage | acs_rds_dashboard | Memory usage % | > 80% warning |
| DiskUsage | acs_rds_dashboard | Disk usage % | > 80% warning |
| IOPSUsage | acs_rds_dashboard | IOPS usage % | > 80% warning |
| ConnectionUsage | acs_rds_dashboard | Connection usage % | > 80% warning |

### SLB Metrics

| Metric | Namespace | Description | Typical Threshold |
|--------|-----------|-------------|-------------------|
| DropConnection | acs_slb_dashboard | Dropped connections | > 0 critical |
| DropPacketRX | acs_slb_dashboard | Dropped inbound packets | > 0 warning |
| DropPacketTX | acs_slb_dashboard | Dropped outbound packets | > 0 warning |
| InstanceActiveConnection | acs_slb_dashboard | Active connections | Baseline + 3σ |

## Alert Example: ECS High CPU

```bash
# Create alarm rule for ECS CPU
aliyun cms PutMetricAlarm \
  --RegionId cn-hangzhou \
  --AlarmName "ECS-CPU-Critical" \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"i-abcdefgh1234567890"}]' \
  --Statistics Average \
  --ComparisonOperator ">=" \
  --Threshold 95 \
  --Period 300 \
  --EvaluationCount 3 \
  --ContactGroups '["ops-oncall"]' \
  --EffectiveInterval "00:00-23:59" \
  --SilenceTime 3600
```

## Alert Example: RDS Connection Limit

```bash
# Create alarm rule for RDS connections
aliyun cms PutMetricAlarm \
  --RegionId cn-hangzhou \
  --AlarmName "RDS-Connection-Warning" \
  --Namespace acs_rds_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions '[{"instanceId":"rm-abcdefgh1234567890"}]' \
  --Statistics Average \
  --ComparisonOperator ">=" \
  --Threshold 80 \
  --Period 300 \
  --EvaluationCount 2 \
  --ContactGroups '["dba-oncall"]' \
  --EffectiveInterval "00:00-23:59"
```

## Dashboard Monitoring

### Using DescribeMetricList for Trending

```bash
# Query CPU trend for last 24 hours
aliyun cms DescribeMetricList \
  --RegionId cn-hangzhou \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Period 300 \
  --StartTime "$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --Dimensions '[{"instanceId":"i-xxx"}]' \
  --output cols=Average,timestamp rows=Datapoints[].{Average:Average,timestamp:timestamp}
```

## References

- [CMS Metric Reference](https://help.aliyun.com/document_detail/163515.html)
- [ECS Metrics](https://help.aliyun.com/document_detail/25482.html)
- [RDS Metrics](https://help.aliyun.com/document_detail/26316.html)
