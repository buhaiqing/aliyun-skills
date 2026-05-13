# API & SDK — CloudMonitor (CMS)

## OpenAPI

- **Spec:** [Cms/2019-01-01](https://api.aliyun.com/api/Cms/2019-01-01)
- **Base path:** `metrics.aliyuncs.com`
- **Style:** RPC (Action + Parameters)
- **Advanced API:** [Cms/2024-03-30](https://api.aliyun.com/api/Cms/2024-03-30) (ROA style, CloudMonitor 2.0)

## SDK Operations Map

| Goal | API OperationId | SDK Method | CLI Support |
|------|-----------------|------------|-------------|
| Query metric data | DescribeMetricList | `client.DescribeMetricList()` | ✅ `aliyun cms DescribeMetricList` |
| Query latest metric | DescribeMetricLast | `client.DescribeMetricLast()` | ✅ `aliyun cms DescribeMetricLast` |
| Query metric data (alt) | DescribeMetricData | `client.DescribeMetricData()` | ✅ `aliyun cms DescribeMetricData` |
| Query top N metrics | DescribeMetricTop | `client.DescribeMetricTop()` | ✅ `aliyun cms DescribeMetricTop` |
| Create/update alarm | PutMetricAlarm | `client.PutMetricAlarm()` | ✅ `aliyun cms PutMetricAlarm` |
| List alarm rules | DescribeMetricAlarmList | `client.DescribeMetricAlarmList()` | ✅ `aliyun cms DescribeMetricAlarmList` |
| Delete alarm rule | DeleteMetricAlarm | `client.DeleteMetricAlarm()` | ✅ `aliyun cms DeleteMetricAlarm` |
| List metric metadata | DescribeMetricMetaList | `client.DescribeMetricMetaList()` | ✅ `aliyun cms DescribeMetricMetaList` |
| List supported products | DescribeProjectMeta | `client.DescribeProjectMeta()` | ✅ `aliyun cms DescribeProjectMeta` |
| Create monitor group | CreateMonitorGroup | `client.CreateMonitorGroup()` | ✅ `aliyun cms CreateMonitorGroup` |
| List monitor groups | DescribeMonitorGroups | `client.DescribeMonitorGroups()` | ✅ `aliyun cms DescribeMonitorGroups` |
| Delete monitor group | DeleteMonitorGroup | `client.DeleteMonitorGroup()` | ✅ `aliyun cms DeleteMonitorGroup` |
| Add group instances | CreateMonitorGroupInstances | `client.CreateMonitorGroupInstances()` | ✅ `aliyun cms CreateMonitorGroupInstances` |
| Remove group instances | DeleteMonitorGroupInstances | `client.DeleteMonitorGroupInstances()` | ✅ `aliyun cms DeleteMonitorGroupInstances` |
| Publish custom metric | PutCustomMetric | `client.PutCustomMetric()` | ✅ `aliyun cms PutCustomMetric` |
| List contact groups | DescribeContactGroupList | `client.DescribeContactGroupList()` | ✅ `aliyun cms DescribeContactGroupList` |
| Create contact group | PutContactGroup | `client.PutContactGroup()` | ✅ `aliyun cms PutContactGroup` |
| Delete contact group | DeleteContactGroup | `client.DeleteContactGroup()` | ✅ `aliyun cms DeleteContactGroup` |
| Advanced query (2.0) | ExecuteQuery | `client.ExecuteQuery()` | ❌ SDK-only |

## Request / Response Notes

### DescribeMetricList

**Required fields:**
- `RegionId`
- `Namespace`
- `MetricName`

**Optional fields:**
- `Period` — 15, 60, 300, 900, 3600
- `StartTime` / `EndTime` — ISO 8601 format
- `Dimensions` — JSON array string
- `Statistics` — Average, Minimum, Maximum, Value

**Response:**
```json
{
  "Success": true,
  "Code": "200",
  "Datapoints": [
    {
      "timestamp": 1715673600000,
      "Average": 45.2,
      "Minimum": 40.1,
      "Maximum": 50.3
    }
  ],
  "Period": "60"
}
```

### PutMetricAlarm

**Required fields:**
- `RegionId`
- `AlarmName`
- `Namespace`
- `MetricName`
- `Statistics`
- `ComparisonOperator`
- `Threshold`
- `Period`

**Optional fields:**
- `Dimensions` — JSON object string (not array)
- `EvaluationCount` — default 3
- `ContactGroups` — JSON array string
- `AlarmActions` — JSON array of MNS topic ARNs
- `EffectiveInterval` — "HH:MM-HH:MM"

**Response:**
```json
{
  "Success": true,
  "Code": "200"
}
```

### Pagination

List APIs support pagination:
- `PageSize` — default 10, max 100
- `PageNumber` — starts at 1

## SDK Package Installation

```bash
# Primary API (Cms/2019-01-01)
go get github.com/alibabacloud-go/cms-20190101/v7/client

# Advanced API (Cms/2024-03-30)
go get github.com/alibabacloud-go/cms-2024-03-30/v2/client

# Common dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea/tea
```

## References

- [OpenAPI Portal — CMS](https://api.aliyun.com/api/Cms/2019-01-01)
- [Alibaba Cloud Go SDK](https://github.com/alibabacloud-go/cms-20190101)
