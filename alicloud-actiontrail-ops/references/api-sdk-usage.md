# API & SDK — Alibaba Cloud ActionTrail (操作审计)

## OpenAPI

- **Product**: Actiontrail
- **Version**: 2020-07-06
- **Style**: RPC
- **Endpoint**: `actiontrail.[region_id].aliyuncs.com` (e.g., `actiontrail.cn-hangzhou.aliyuncs.com`)
- **Global Endpoint**: `actiontrail.aliyuncs.com`
- **Docs**: https://help.aliyun.com/zh/actiontrail/developer-reference/api-actiontrail-2020-07-06-overview
- **API Explorer**: https://api.aliyun.com/api/Actiontrail/2020-07-06

## SDK Operations Map

### Region Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| List regions | DescribeRegions | `DescribeRegions` | `aliyun actiontrail DescribeRegions` |

### Trail Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Create trail | CreateTrail | `CreateTrail` | `aliyun actiontrail CreateTrail` |
| Describe trails | DescribeTrails | `DescribeTrails` | `aliyun actiontrail DescribeTrails` |
| Get trail status | GetTrailStatus | `GetTrailStatus` | `aliyun actiontrail GetTrailStatus` |
| Update trail | UpdateTrail | `UpdateTrail` | `aliyun actiontrail UpdateTrail` |
| Delete trail | DeleteTrail | `DeleteTrail` | `aliyun actiontrail DeleteTrail` |
| Start logging | StartLogging | `StartLogging` | `aliyun actiontrail StartLogging` |
| Stop logging | StopLogging | `StopLogging` | `aliyun actiontrail StopLogging` |
| Get user trail count | DescribeUserTrailCount | `DescribeUserTrailCount` | `aliyun actiontrail DescribeUserTrailCount` |
| Get delivery metrics | DescribeTrailDeliveryMetricData | `DescribeTrailDeliveryMetricData` | `aliyun actiontrail DescribeTrailDeliveryMetricData` |

### Event Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Lookup events | LookupEvents | `LookupEvents` | `aliyun actiontrail LookupEvents` |

### Data Replenishment Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Create delivery job | CreateDeliveryHistoryJob | `CreateDeliveryHistoryJob` | `aliyun actiontrail CreateDeliveryHistoryJob` |
| Delete delivery job | DeleteDeliveryHistoryJob | `DeleteDeliveryHistoryJob` | `aliyun actiontrail DeleteDeliveryHistoryJob` |
| List delivery jobs | ListDeliveryHistoryJobs | `ListDeliveryHistoryJobs` | `aliyun actiontrail ListDeliveryHistoryJobs` |
| Get delivery job | GetDeliveryHistoryJob | `GetDeliveryHistoryJob` | `aliyun actiontrail GetDeliveryHistoryJob` |

### AccessKey Audit Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Get last used info | GetAccessKeyLastUsedInfo | `GetAccessKeyLastUsedInfo` | `aliyun actiontrail GetAccessKeyLastUsedInfo` |
| Get last used events | GetAccessKeyLastUsedEvents | `GetAccessKeyLastUsedEvents` | `aliyun actiontrail GetAccessKeyLastUsedEvents` |
| Get last used IPs | GetAccessKeyLastUsedIps | `GetAccessKeyLastUsedIps` | `aliyun actiontrail GetAccessKeyLastUsedIps` |
| Get last used products | GetAccessKeyLastUsedProducts | `GetAccessKeyLastUsedProducts` | `aliyun actiontrail GetAccessKeyLastUsedProducts` |
| Get last used resources | GetAccessKeyLastUsedResources | `GetAccessKeyLastUsedResources` | `aliyun actiontrail GetAccessKeyLastUsedResources` |

### Data Event Selector Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| List selectors | ListDataEventSelectors | `ListDataEventSelectors` | `aliyun actiontrail ListDataEventSelectors` |
| Get selector | GetDataEventSelector | `GetDataEventSelector` | `aliyun actiontrail GetDataEventSelector` |
| Put selector | PutDataEventSelector | `PutDataEventSelector` | `aliyun actiontrail PutDataEventSelector` |
| Delete selector | DeleteDataEventSelector | `DeleteDataEventSelector` | `aliyun actiontrail DeleteDataEventSelector` |

### Insight Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Enable insight | EnableInsight | `EnableInsight` | `aliyun actiontrail EnableInsight --InsightType <type>` |
| Disable insight | DisableInsight | `DisableInsight` | `aliyun actiontrail DisableInsight --InsightType <type>` |
| Get insight types | GetInsightTypes | `GetInsightTypes` | `aliyun actiontrail GetInsightTypes` |
| Get insight selectors | GetInsightSelectors | `GetInsightSelectors` | `aliyun actiontrail GetInsightSelectors` |
| Put insight selectors | PutInsightSelectors | `PutInsightSelectors` | `aliyun actiontrail PutInsightSelectors` |
| Get insight events count | GetInsightsEventsCount | `GetInsightsEventsCount` | `aliyun actiontrail GetInsightsEventsCount` |
| Lookup insight events | LookupInsightEvents | `LookupInsightEvents` | `aliyun actiontrail LookupInsightEvents --InsightType <type>` |

### Advanced Query Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Describe scenes | DescribeScenes | `DescribeScenes` | `aliyun actiontrail DescribeScenes` |
| Describe search templates | DescribeSearchTemplates | `DescribeSearchTemplates` | `aliyun actiontrail DescribeSearchTemplates` |
| Create advanced query template | CreateAdvancedQueryTemplate | `CreateAdvancedQueryTemplate` | `aliyun actiontrail CreateAdvancedQueryTemplate` |
| Delete advanced query template | DeleteAdvancedQueryTemplate | `DeleteAdvancedQueryTemplate` | `aliyun actiontrail DeleteAdvancedQueryTemplate` |
| Describe advanced query template | DescribeAdvancedQueryTemplate | `DescribeAdvancedQueryTemplate` | `aliyun actiontrail DescribeAdvancedQueryTemplate` |
| Update advanced query template | UpdateAdvancedQueryTemplate | `UpdateAdvancedQueryTemplate` | `aliyun actiontrail UpdateAdvancedQueryTemplate` |
| Get advanced query template | GetAdvancedQueryTemplate | `GetAdvancedQueryTemplate` | `aliyun actiontrail GetAdvancedQueryTemplate` |

### Global Events Storage Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Get storage region | GetGlobalEventsStorageRegion | `GetGlobalEventsStorageRegion` | `aliyun actiontrail GetGlobalEventsStorageRegion` |
| Update storage region | UpdateGlobalEventsStorageRegion | `UpdateGlobalEventsStorageRegion` | `aliyun actiontrail UpdateGlobalEventsStorageRegion` |

### Other Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Get governance metrics | GetGovernanceMetrics | `GetGovernanceMetrics` | `aliyun actiontrail GetGovernanceMetrics` |
| Describe user alert count | DescribeUserAlertCount | `DescribeUserAlertCount` | `aliyun actiontrail DescribeUserAlertCount` |
| Describe user log count | DescribeUserLogCount | `DescribeUserLogCount` | `aliyun actiontrail DescribeUserLogCount` |
| List data event services | ListDataEventServices | `ListDataEventServices` | `aliyun actiontrail ListDataEventServices` |
| Describe resource lifecycle events | DescribeResourceLifeCycleEvents | `DescribeResourceLifeCycleEvents` | `aliyun actiontrail DescribeResourceLifeCycleEvents` |

## Key Request Parameters

### CreateTrail

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| Name | string | Yes | Trail name (6-36 chars, lowercase start) |
| OssBucketName | string | No | OSS bucket for delivery |
| OssKeyPrefix | string | No | OSS key prefix |
| SlsProjectArn | string | No | SLS project ARN |
| SlsWriteRoleArn | string | No | SLS write role ARN |
| EventRW | string | No | Event type: Read, Write, All (default: All) |
| TrailRegion | string | No | Trail region (default: All regions) |
| IsOrganizationTrail | bool | No | Whether it's an organization trail |

### LookupEvents

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| StartTime | string | No | Start time (ISO 8601 UTC) |
| EndTime | string | No | End time (ISO 8601 UTC) |
| EventType | string | No | Event type filter |
| ServiceName | string | No | Cloud service name filter |
| EventName | string | No | Event name filter |
| User | string | No | User name filter |
| ResourceType | string | No | Resource type filter |
| ResourceName | string | No | Resource name filter |
| EventRW | string | No | Read/Write/All filter |
| EventAccessKeyId | string | No | AccessKey ID filter |
| MaxResults | int | No | Max results (0-50) |
| NextToken | string | No | Pagination token |

## Key Response Fields

### CreateTrail Response

```json
{
  "TrailName": "trail-test",
  "OssBucketName": "audit-log",
  "OssKeyPrefix": "at-product-account-audit-B",
  "EventRW": "All",
  "RequestId": "ACA7C814-12BC-4D81-A0D2-72071C9D6D2C"
}
```

### DescribeTrails Response

```json
{
  "TrailList": [
    {
      "TrailName": "trail-test",
      "OssBucketName": "audit-log",
      "Status": "Enable",
      "TrailRegion": "All",
      "EventRW": "All",
      "CreateTime": "2026-01-15T10:00:00Z",
      "UpdateTime": "2026-01-15T10:00:00Z"
    }
  ],
  "RequestId": "ACA7C814-12BC-4D81-A0D2-72071C9D6D2C"
}
```

### GetTrailStatus Response

```json
{
  "IsLogging": true,
  "LatestDeliveryTime": "2026-05-15T10:00:00Z",
  "LatestNotificationTime": "2026-05-15T10:00:00Z",
  "StartLoggingTime": "2026-01-15T10:00:00Z",
  "StopLoggingTime": "",
  "RequestId": "ACA7C814-12BC-4D81-A0D2-72071C9D6D2C"
}
```

### LookupEvents Response

```json
{
  "Events": [
    {
      "eventId": "96.227_1606286128938_****",
      "eventVersion": "1",
      "eventSource": "ecs.aliyuncs.com",
      "sourceIpAddress": "192.168.1.1",
      "userIdentity": {
        "accountId": "1234567890",
        "arn": "acs:ram::1234567890:user/admin",
        "principalId": "1234567890",
        "type": "ram-user",
        "userName": "admin"
      },
      "eventType": "ApiCall",
      "eventName": "CreateInstance",
      "acsRegion": "cn-hangzhou",
      "requestId": "C8A8B0B0-0B0A-4B0A-8B0A-0B0A8B0A8B0A",
      "eventTime": "2026-05-15T10:00:00Z"
    }
  ],
  "NextToken": "20",
  "RequestId": "FD79665A-CE8B-49D4-82E6-5EE2E0E791DD"
}
```

## Pagination

LookupEvents uses token-based pagination:

1. First call: omit `NextToken`
2. Response includes `NextToken` if more results exist
3. Subsequent calls: include `NextToken` from previous response
4. Repeat until `NextToken` is absent from response

## SDK Package

- **Go SDK**: `github.com/alibabacloud-go/actiontrail-20200706/v4/client`
- **Import path**: `actiontrail "github.com/alibabacloud-go/actiontrail-20200706/v4/client"`
- **Endpoint**: `actiontrail.aliyuncs.com` (global) or `actiontrail.[region].aliyuncs.com`