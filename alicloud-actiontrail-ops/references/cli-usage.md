# CLI Usage — Alibaba Cloud ActionTrail (操作审计)

## Overview

The `aliyun` CLI fully supports ActionTrail operations. This reference provides
command patterns, examples, and coverage information.

## Command Structure

```bash
aliyun actiontrail <OperationName> --Parameter1 value1 --Parameter2 value2
```

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.TrailList[]?`
- Example:
```bash
aliyun actiontrail DescribeTrails | jq '{trails: [.TrailList[]? | {name: .TrailName, bucket: .BucketName}]}'
```

## CLI Operations Map

### Region Operations

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| DescribeRegions | `aliyun actiontrail DescribeRegions` | List supported regions |

### Trail Operations

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| CreateTrail | `aliyun actiontrail CreateTrail --Name <name> --OssBucketName <bucket>` | Create a trail |
| DescribeTrails | `aliyun actiontrail DescribeTrails` | List all trails |
| GetTrailStatus | `aliyun actiontrail GetTrailStatus --Name <name>` | Get trail status |
| UpdateTrail | `aliyun actiontrail UpdateTrail --Name <name> --OssBucketName <bucket>` | Update trail config |
| DeleteTrail | `aliyun actiontrail DeleteTrail --Name <name>` | Delete a trail |
| StartLogging | `aliyun actiontrail StartLogging --Name <name>` | Enable trail logging |
| StopLogging | `aliyun actiontrail StopLogging --Name <name>` | Disable trail logging |
| DescribeUserTrailCount | `aliyun actiontrail DescribeUserTrailCount` | Get trail count |
| DescribeTrailDeliveryMetricData | `aliyun actiontrail DescribeTrailDeliveryMetricData --TrailName <name>` | Get delivery metrics |

### Event Operations

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| LookupEvents | `aliyun actiontrail LookupEvents` | Search historical events |

### AccessKey Audit Operations

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| GetAccessKeyLastUsedInfo | `aliyun actiontrail GetAccessKeyLastUsedInfo --AccessKeyId <ak>` | Get AK last used info |
| GetAccessKeyLastUsedEvents | `aliyun actiontrail GetAccessKeyLastUsedEvents --AccessKeyId <ak>` | Get AK last used events |
| GetAccessKeyLastUsedIps | `aliyun actiontrail GetAccessKeyLastUsedIps --AccessKeyId <ak>` | Get AK last used IPs |
| GetAccessKeyLastUsedProducts | `aliyun actiontrail GetAccessKeyLastUsedProducts --AccessKeyId <ak>` | Get AK last used products |
| GetAccessKeyLastUsedResources | `aliyun actiontrail GetAccessKeyLastUsedResources --AccessKeyId <ak>` | Get AK last used resources |

### Insight Operations

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| EnableInsight | `aliyun actiontrail EnableInsight --InsightType <type>` | Enable insight (types: IpInsight, ApiCallRateInsight, ApiErrorRateInsight, AkInsight, PolicyChangeInsight, PasswordChangeInsight, TrailConcealmentInsight) |
| DisableInsight | `aliyun actiontrail DisableInsight --InsightType <type>` | Disable insight |
| GetInsightTypes | `aliyun actiontrail GetInsightTypes` | Get enabled insight types |
| LookupInsightEvents | `aliyun actiontrail LookupInsightEvents --InsightType <type>` | Query insight events |

### Data Replenishment Operations

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| CreateDeliveryHistoryJob | `aliyun actiontrail CreateDeliveryHistoryJob --TrailName <name>` | Create delivery job |
| ListDeliveryHistoryJobs | `aliyun actiontrail ListDeliveryHistoryJobs` | List delivery jobs |
| GetDeliveryHistoryJob | `aliyun actiontrail GetDeliveryHistoryJob --JobId <id>` | Get delivery job details |
| DeleteDeliveryHistoryJob | `aliyun actiontrail DeleteDeliveryHistoryJob --JobId <id>` | Delete delivery job |

### Data Event Selector Operations

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| ListDataEventSelectors | `aliyun actiontrail ListDataEventSelectors --TrailName <name>` | List selectors |
| GetDataEventSelector | `aliyun actiontrail GetDataEventSelector --TrailName <name>` | Get selector details |
| PutDataEventSelector | `aliyun actiontrail PutDataEventSelector --TrailName <name> --EventSelector <json>` | Set selector |
| DeleteDataEventSelector | `aliyun actiontrail DeleteDataEventSelector --TrailName <name>` | Delete selector |

### Global Events Storage Operations

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| GetGlobalEventsStorageRegion | `aliyun actiontrail GetGlobalEventsStorageRegion` | Get storage region |
| UpdateGlobalEventsStorageRegion | `aliyun actiontrail UpdateGlobalEventsStorageRegion --RegionId <region>` | Set storage region |

## Common CLI Examples

### Create a Trail with OSS Delivery

```bash
aliyun actiontrail CreateTrail \
  --Name my-audit-trail \
  --OssBucketName my-audit-bucket \
  --OssKeyPrefix audit-logs \
  --EventRW All
```

### Create a Trail with SLS Delivery

```bash
aliyun actiontrail CreateTrail \
  --Name my-sls-trail \
  --SlsProjectArn acs:log:cn-hangzhou:1234567890:project/my-sls-project \
  --EventRW Write
```

### Enable Trail Logging

```bash
aliyun actiontrail StartLogging --Name my-audit-trail
```

### Check Trail Status

```bash
aliyun actiontrail GetTrailStatus --Name my-audit-trail
```

### List All Trails

```bash
aliyun actiontrail DescribeTrails
```

### Search Events by Time Range

```bash
aliyun actiontrail LookupEvents \
  --StartTime "2026-05-01T00:00:00Z" \
  --EndTime "2026-05-15T23:59:59Z" \
  --MaxResults 50
```

### Search Events by Service and Event Name

```bash
aliyun actiontrail LookupEvents \
  --ServiceName Ecs \
  --EventName DeleteInstances \
  --MaxResults 20
```

### Search Console Login Events

```bash
aliyun actiontrail LookupEvents \
  --EventType ConsoleSignin \
  --MaxResults 20
```

### Audit a Specific AccessKey

```bash
aliyun actiontrail GetAccessKeyLastUsedInfo --AccessKeyId LTAI5t****
```

### Enable Insight Analysis

```bash
# Enable IP insight — detect operations from unfamiliar IPs
aliyun actiontrail EnableInsight --InsightType IpInsight

# Enable API call rate insight — detect unusual API call volume
aliyun actiontrail EnableInsight --InsightType ApiCallRateInsight

# Enable API error rate insight — detect unusual error spikes
aliyun actiontrail EnableInsight --InsightType ApiErrorRateInsight

# Enable AccessKey insight — detect unusual AK call patterns
aliyun actiontrail EnableInsight --InsightType AkInsight

# Enable policy change insight — detect permission changes
aliyun actiontrail EnableInsight --InsightType PolicyChangeInsight

# Enable password change insight — detect password changes
aliyun actiontrail EnableInsight --InsightType PasswordChangeInsight

# Enable trail concealment insight — detect trail tampering
aliyun actiontrail EnableInsight --InsightType TrailConcealmentInsight
```

### Query Insight Events

```bash
# Query IP insight events
aliyun actiontrail LookupInsightEvents --InsightType IpInsight

# Query with time range
aliyun actiontrail LookupInsightEvents \
  --InsightType ApiCallRateInsight \
  --StartTime "2026-05-01T00:00:00Z" \
  --EndTime "2026-05-15T23:59:59Z" \
  --MaxResults 50
```

### Create Compliance Trail

```bash
# Create a trail that meets compliance requirements
aliyun actiontrail CreateTrail \
  --Name compliance-trail \
  --OssBucketName my-audit-bucket \
  --OssKeyPrefix compliance \
  --EventRW All \
  --TrailRegion All

# Enable logging immediately
aliyun actiontrail StartLogging --Name compliance-trail
```

### Delete a Trail (Destructive)

```bash
# First, confirm the trail exists
aliyun actiontrail DescribeTrails --NameList '["my-audit-trail"]'

# Then delete
aliyun actiontrail DeleteTrail --Name my-audit-trail
```

## CLI Coverage Gaps

The following operations are **SDK-only** (not exposed via `aliyun` CLI):

| Operation | Description | Alternative |
|-----------|-------------|-------------|
| DescribeScenes | Query advanced query scenarios | Use SDK or console |
| DescribeSearchTemplates | Query advanced query templates | Use SDK or console |
| CreateAdvancedQueryTemplate | Create advanced query template | Use SDK or console |
| DeleteAdvancedQueryTemplate | Delete advanced query template | Use SDK or console |
| DescribeAdvancedQueryTemplate | Describe advanced query template | Use SDK or console |
| UpdateAdvancedQueryTemplate | Update advanced query template | Use SDK or console |
| GetAdvancedQueryTemplate | Get advanced query template | Use SDK or console |
| CreateAdvancedQueryHistory | Create advanced query history | Use SDK or console |
| DeleteAdvancedQueryHistory | Delete advanced query history | Use SDK or console |
| DescribeAdvancedQueryHistory | Describe advanced query history | Use SDK or console |
| DescribeResourceLifeCycleEvents | Query resource lifecycle events | Use SDK or console |
| ListDataEventServices | List data event services | Use SDK or console |
| GetGovernanceMetrics | Get governance metrics | Use SDK or console |
| DescribeUserAlertCount | Describe user alert count | Use SDK or console |
| DescribeUserLogCount | Describe user log count | Use SDK or console |

For SDK-only operations, use the JIT Go SDK fallback as documented in
[integration.md](integration.md).

## Output Format

The `aliyun` CLI outputs JSON by default. No `--output json` flag is needed.

For tabular output with specific columns:

```bash
aliyun actiontrail DescribeTrails \
  --output cols=TrailName,Status,TrailRegion rows=TrailList[]
```