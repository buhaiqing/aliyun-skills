# Troubleshooting — Alibaba Cloud ActionTrail (操作审计)

## Error Code Reference

| Error Code | Description | Common Causes | Resolution |
|------------|-------------|---------------|------------|
| `TrailNotFoundException` | Trail not found | Trail name incorrect, trail deleted | Use `DescribeTrails` to list all trails and verify the name |
| `TrailAlreadyExistsException` | Trail name already exists | Duplicate trail name in the same account | Use a different trail name |
| `InvalidParameter` | Invalid parameter | Parameter value out of range or wrong format | Check parameter constraints in API docs |
| `InvalidParameterValue` | Invalid parameter value | Parameter value not in allowed set | Verify against allowed enum values |
| `Throttling` | Request throttled | Exceeded API rate limit (2 calls/sec for LookupEvents) | Implement exponential backoff; reduce request frequency |
| `AccessDenied` | Access denied | Insufficient RAM permissions | Grant `actiontrail:*` or specific action permissions |
| `InvalidAccessKeyId` | Invalid AccessKey ID | Wrong or deleted AccessKey | Verify AccessKey ID in RAM console |
| `SignatureDoesNotMatch` | Signature mismatch | Wrong secret key or clock skew | Check credential configuration and system time |
| `MissingParameter` | Missing required parameter | Required field not provided | Add the required parameter |
| `QuotaExceeded` | Quota exceeded | More than 5 trails per region | Delete unused trails or use a different region |
| `DependencyViolation` | Dependency violation | Trail has active dependencies | Check if trail has active data event selectors or delivery jobs |
| `AccessKeyNotFoundException` | AccessKey not found | AccessKey ID does not exist | Verify the AccessKey ID |
| `InvalidEventType` | Invalid event type | Wrong event type value | Use: ApiCall, ConsoleOperation, AliyunServiceEvent, PasswordReset, ConsoleSignin, ConsoleSignout |
| `TimeRangeExceeded` | Time range exceeded | LookupEvents span > 30 days or outside 90-day window | Adjust time range (max 30 days, within 90 days) |
| `ServiceUnavailable` | Service unavailable | Temporary service issue | Retry with backoff; check service health |
| `InsightTypeNotAvailable` | Insight type not available | Invalid type or not yet enabled | Use valid types: IpInsight, ApiCallRateInsight, ApiErrorRateInsight, AkInsight, PolicyChangeInsight, PasswordChangeInsight, TrailConcealmentInsight |
| `InternalError` | Internal error | Server-side error | Retry; if persists, contact support |

## Diagnostic Steps

### Step 1: Verify Credentials

```bash
# Check if credentials are set
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo "AK set" || echo "AK missing"
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "Secret set" || echo "Secret missing"
test -n "$ALIBABA_CLOUD_REGION_ID" && echo "Region set" || echo "Region missing"

# Test basic API access
aliyun actiontrail DescribeRegions
```

### Step 2: Check Trail Configuration

```bash
# List all trails
aliyun actiontrail DescribeTrails

# Check specific trail status
aliyun actiontrail GetTrailStatus --Name {{user.trail_name}}
```

### Step 3: Verify Event Delivery

```bash
# Check if logging is enabled
aliyun actiontrail GetTrailStatus --Name {{user.trail_name}}

# Look for recent events
aliyun actiontrail LookupEvents --MaxResults 10
```

### Step 4: Check Quotas

```bash
# Check trail count
aliyun actiontrail DescribeUserTrailCount
```

### Step 5: Check Insight Configuration

```bash
# List enabled insight types
aliyun actiontrail GetInsightTypes
```

## Common Issues

### Issue: Trail Created but No Events Being Delivered

**Cause:** Trails are created in disabled state by default.

**Fix:**
```bash
aliyun actiontrail StartLogging --Name {{user.trail_name}}
```

### Issue: LookupEvents Returns No Results

**Possible causes:**
1. Time range is outside the 90-day retention window
2. Time range exceeds 30 days
3. No matching events for the specified filters
4. Event type filter is too restrictive

**Fix:**
- Verify time range is within the last 90 days
- Ensure time range span ≤ 30 days
- Broaden filter criteria
- Remove filters one by one to identify the restrictive one

### Issue: Cannot Create Trail — QuotaExceeded

**Cause:** Maximum 5 trails per region.

**Fix:**
```bash
# List existing trails
aliyun actiontrail DescribeTrails

# Delete unused trails
aliyun actiontrail DeleteTrail --Name {{unused_trail_name}}
```

### Issue: AccessKey Audit Returns No Data

**Possible causes:**
1. AccessKey ID is incorrect
2. AccessKey has never been used
3. AccessKey was used more than 90 days ago

**Fix:**
- Verify the AccessKey ID
- Check if the AccessKey exists in RAM
- Use LookupEvents with the AccessKey ID filter to find historical usage

### Issue: Insight Events Not Appearing After Enabling

**Cause:** Insight events take at least 24 hours to generate after enabling.

**Fix:**
- Wait at least 24 hours after enabling the InsightType
- Verify the InsightType is enabled: `aliyun actiontrail GetInsightTypes`
- Check if there are enough historical events for analysis (requires 7 days of data)

### Issue: InsightTypeNotAvailable Error

**Cause:** The specified InsightType is invalid or not yet available.

**Fix:**
```bash
# List valid InsightType values
# Valid types: IpInsight, ApiCallRateInsight, ApiErrorRateInsight,
#              AkInsight, PolicyChangeInsight, PasswordChangeInsight,
#              TrailConcealmentInsight

# Check which types are already enabled
aliyun actiontrail GetInsightTypes
```

### Issue: Trail Deletion Fails

**Possible causes:**
1. Trail has active data event selectors
2. Trail has active delivery history jobs

**Fix:**
```bash
# List data event selectors
aliyun actiontrail ListDataEventSelectors --TrailName {{user.trail_name}}

# Delete data event selectors first if any
aliyun actiontrail DeleteDataEventSelector --TrailName {{user.trail_name}}

# Then retry deletion
aliyun actiontrail DeleteTrail --Name {{user.trail_name}}
```

## Best Practices

1. **Enable trails immediately** after creation with `StartLogging`
2. **Use descriptive trail names** for easy identification
3. **Monitor delivery metrics** with `DescribeTrailDeliveryMetricData`
4. **Set up SLS delivery** for real-time event analysis and alerting
5. **Enable insight** for anomaly detection on API call patterns
6. **Regularly audit AccessKeys** using the AccessKey audit APIs
7. **Use organization trails** for multi-account environments
8. **Configure data event selectors** for data-level audit requirements