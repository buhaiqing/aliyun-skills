# CLI Usage Guide for alicloud-cms-ops

## Overview

This document provides detailed CLI usage patterns for CloudMonitor (CMS)
operations. The `aliyun` CLI supports CMS core operations via the `cms`
command namespace.

## CLI Coverage

### Supported Operations (Verified)

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| DescribeMetricList | `aliyun cms DescribeMetricList` | Query time-series metric data |
| DescribeMetricLast | `aliyun cms DescribeMetricLast` | Query latest metric data point |
| DescribeMetricData | `aliyun cms DescribeMetricData` | Query metric data (alternative) |
| DescribeMetricTop | `aliyun cms DescribeMetricTop` | Query top N metric values |
| PutMetricAlarm | `aliyun cms PutMetricAlarm` | Create/update alarm rule |
| DescribeMetricAlarmList | `aliyun cms DescribeMetricAlarmList` | List alarm rules |
| DeleteMetricAlarm | `aliyun cms DeleteMetricAlarm` | Delete alarm rule(s) |
| DescribeMetricMetaList | `aliyun cms DescribeMetricMetaList` | List available metrics |
| DescribeProjectMeta | `aliyun cms DescribeProjectMeta` | List supported products |
| CreateMonitorGroup | `aliyun cms CreateMonitorGroup` | Create monitor group |
| DescribeMonitorGroups | `aliyun cms DescribeMonitorGroups` | List monitor groups |
| DeleteMonitorGroup | `aliyun cms DeleteMonitorGroup` | Delete monitor group |
| PutMonitorGroupDynamicRule | `aliyun cms PutMonitorGroupDynamicRule` | Create dynamic group rule |
| DescribeMonitorGroupInstances | `aliyun cms DescribeMonitorGroupInstances` | List group instances |
| CreateMonitorGroupInstances | `aliyun cms CreateMonitorGroupInstances` | Add instances to group |
| DeleteMonitorGroupInstances | `aliyun cms DeleteMonitorGroupInstances` | Remove instances from group |
| PutCustomMetric | `aliyun cms PutCustomMetric` | Publish custom metric |
| DescribeCustomMetric | `aliyun cms DescribeCustomMetric` | Query custom metrics |
| DescribeContactGroupList | `aliyun cms DescribeContactGroupList` | List contact groups |
| PutContactGroup | `aliyun cms PutContactGroup` | Create/update contact group |
| DeleteContactGroup | `aliyun cms DeleteContactGroup` | Delete contact group |
| DescribeContactList | `aliyun cms DescribeContactList` | List contacts |
| PutContact | `aliyun cms PutContact` | Create/update contact |
| DeleteContact | `aliyun cms DeleteContact` | Delete contact |

### SDK-Only Operations (CLI Coverage Gaps)

| Operation | Reason | SDK Package |
|-----------|--------|-------------|
| ExecuteQuery | CloudMonitor 2.0 ROA API | `cms-2024-03-30` |
| ContextStore operations | CloudMonitor 2.0 advanced | `cms-2024-03-30` |
| MemoryStore operations | CloudMonitor 2.0 advanced | `cms-2024-03-30` |
| Subscription operations | CloudMonitor 2.0 advanced | `cms-2024-03-30` |

## Common Patterns

### Authentication

```bash
# Via environment variables (preferred)
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-ak-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-ak-secret"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"

# Via CLI profile
aliyun configure --profile cms-profile
aliyun cms DescribeMetricList --profile cms-profile ...
```

### Output Filtering

```bash
# JSON output (default)
aliyun cms DescribeMetricList ...

# Table output with specific columns
aliyun cms DescribeMetricAlarmList ... \
  --output cols=AlarmName,Namespace,MetricName,State rows=AlarmList.Alarm[]

# JMESPath filter
aliyun cms DescribeMetricList ... \
  --output json \
  --filter "Datapoints[?Average > `80`]"
```

### Pagination

```bash
# Auto-pagination with --pager
aliyun cms DescribeMetricAlarmList --pager

# Manual pagination
aliyun cms DescribeMetricAlarmList --PageSize 100 --PageNumber 1
aliyun cms DescribeMetricAlarmList --PageSize 100 --PageNumber 2
```

### Time Range Patterns

```bash
# Last hour
aliyun cms DescribeMetricList \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Specific time range
aliyun cms DescribeMetricList \
  --StartTime "2026-05-14T00:00:00Z" \
  --EndTime "2026-05-14T23:59:59Z"

# Linux (GNU date)
aliyun cms DescribeMetricList \
  --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

## Examples

### Example 1: Query ECS CPU Usage

```bash
aliyun cms DescribeMetricList \
  --RegionId cn-hangzhou \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Period 60 \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --Dimensions '[{"instanceId":"i-abcdefgh1234567890"}]'
```

### Example 2: Create CPU Alarm Rule

```bash
aliyun cms PutMetricAlarm \
  --RegionId cn-hangzhou \
  --AlarmName "ECS-High-CPU" \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"i-abcdefgh1234567890"}]' \
  --Statistics Average \
  --ComparisonOperator ">=" \
  --Threshold 80 \
  --Period 300 \
  --EvaluationCount 3 \
  --ContactGroups '["ops-team"]' \
  --EffectiveInterval "00:00-23:59"
```

### Example 3: List All Alarm Rules

```bash
aliyun cms DescribeMetricAlarmList \
  --RegionId cn-hangzhou \
  --PageSize 50 \
  --PageNumber 1
```

### Example 4: Query Available Metrics for ECS

```bash
aliyun cms DescribeMetricMetaList \
  --RegionId cn-hangzhou \
  --Namespace acs_ecs_dashboard
```

### Example 5: Publish Custom Metric

```bash
aliyun cms PutCustomMetric \
  --RegionId cn-hangzhou \
  --MetricList '[{"metricName":"custom_app_latency","namespace":"acs_custom","dimensions":{"service":"api-gateway"},"value":120,"timestamp":$(date +%s)000}]'
```

## Error Handling

| Error | CLI Output | Action |
|-------|-----------|--------|
| `Throttling.User` | `Request was denied due to user flow control` | Wait 5s, retry |
| `InvalidParameter` | `The specified parameter is invalid` | Check parameter values |
| `ResourceNotFound` | `The specified resource is not found` | Verify resource ID |
| `Forbidden` | `User not authorized` | Check RAM permissions |

## References

- [Alibaba Cloud CLI Documentation](https://help.aliyun.com/zh/cli/)
- [CMS CLI Integration Example](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/cli-integration-example)
- [OpenAPI Portal - CMS](https://api.aliyun.com/api/Cms/2019-01-01)
