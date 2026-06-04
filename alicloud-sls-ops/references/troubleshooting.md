# Troubleshooting — Alibaba Cloud Simple Log Service (SLS)

## Error Code Reference

| Code | Message | Retryable | Action |
|------|---------|-----------|--------|
| `ProjectAlreadyExists` | Project name already exists | No | HALT; choose different project name |
| `ProjectNotFound` | Project not found | No | HALT; create project first |
| `LogstoreAlreadyExists` | Logstore name already exists | No | HALT; choose different logstore name |
| `LogstoreNotFound` | Logstore not found | No | HALT; create logstore first |
| `IndexNotFound` | Index not configured | No | Create index before querying |
| `InvalidLogstoreName` | Invalid logstore name format | No | HALT; use 3-63 chars, lowercase alphanumeric + hyphens |
| `InvalidProjectName` | Invalid project name format | No | HALT; use 3-63 chars, lowercase alphanumeric + hyphens |
| `InvalidQuery` | Invalid SQL query syntax | No | Fix query syntax |
| `InvalidParameter` | Invalid parameter | No | Check request parameters |
| `ShardCountExceedsLimit` | Shard count exceeds limit | No | HALT; reduce shard count (max 256) |
| `TtlExceedsLimit` | TTL out of range | No | HALT; check TTL limits (1-3650 days) |
| `Forbidden.NoPermission` | RAM permission denied | No | HALT; delegate `alicloud-ram-ops` |
| `Throttling` | Rate limited | Yes | Exponential backoff (1s, 2s, 4s) |
| `InternalError` | Server error | Yes | Retry; escalate with RequestId |
| `ServiceUnavailable` | Temporary outage | Yes | Backoff; check status page |
| `InvalidAccessKeyId` | Invalid AK | No | HALT; fix credentials |
| `SignatureDoesNotMatch` | Invalid signature | No | HALT; fix SK or check clock skew |
| `LogSizeExceedsLimit` | Log entry too large | No | HALT; max 512 KB per log entry |
| `WriteShardExhausted` | Write shard capacity full | Yes | Backoff; increase shard count |

## Diagnostic Order

### 1. Credentials & Permissions

```bash
# Verify credentials
echo "AK: $ALIBABA_CLOUD_ACCESS_KEY_ID"
echo "Region: $ALIBABA_CLOUD_REGION_ID"

# Test basic access
aliyun sls GET / --header "x-log-apiversion=0.9.0" --project "test-project"
```

### 2. Project Existence

```bash
# Check project exists
aliyun sls GET / --header "x-log-apiversion=0.9.0" --project "{{user.project_name}}"
```

### 3. Logstore Existence

```bash
# Check logstore exists
aliyun sls GET /logstores/{{user.logstore}} --header "x-log-apiversion=0.9.0" --project "{{user.project_name}}"
```

### 4. Index Configuration

```bash
# Check index exists
aliyun sls GET /logstores/{{user.logstore}}/index --header "x-log-apiversion=0.9.0" --project "{{user.project_name}}"
```

### 5. Query Validation

```bash
# Test query
aliyun sls GET /logstores/{{user.logstore}}/logs --header "x-log-apiversion=0.9.0" --query "level:ERROR" --project "{{user.project_name}}"
```

## Common Scenarios

### Scenario: Query Returns No Results

**Symptoms:** `$.count` is 0, `$.logs` is empty

**Diagnosis:**
1. Check time range — logs may be outside query window
2. Check index configuration — fields may not be indexed
3. Check log ingestion — logs may not be collected yet
4. Check query syntax — SQL may be invalid

**Recovery:**
```bash
# Expand time range
aliyun sls GET /logstores/{{user.logstore}}/logs --header "x-log-apiversion=0.9.0" \
  --query "from * | select * limit 100" \
  --from $(date -d "1 hour ago" +%s) \
  --to $(date +%s) \
  --project "{{user.project_name}}"
```

### Scenario: Index Not Configured

**Symptoms:** `IndexNotFound` error when querying logs

**Diagnosis:**
1. Check if index exists
2. Check index configuration

**Recovery:**
```bash
# Create index
aliyun sls POST /logstores/{{user.logstore}}/index \
  --header "x-log-apiversion=0.9.0" \
  --body '{"fullTextIndex":{"caseSensitive":false,"includeChinese":true,"token":["@"," ", ","]}}' \
  --project "{{user.project_name}}"
```

### Scenario: Write Throttling

**Symptoms:** `Throttling` or `WriteShardExhausted` errors

**Diagnosis:**
1. Check shard count
2. Check write QPS

**Recovery:**
```bash
# Increase shard count
aliyun sls PUT /logstores/{{user.logstore}} \
  --header "x-log-apiversion=0.9.0" \
  --body '{"shardCount":4}' \
  --project "{{user.project_name}}"
```

### Scenario: Alert Not Firing

**Symptoms:** Alert created but no notifications

**Diagnosis:**
1. Check alert configuration
2. Check notification settings
3. Check alert schedule

**Recovery:**
```bash
# Verify alert exists
aliyun sls GET /alerts/{{user.alert_name}} --header "x-log-apiversion=0.9.0" --project "{{user.project_name}}"

# Update alert schedule
aliyun sls PUT /alerts/{{user.alert_name}} \
  --header "x-log-apiversion=0.9.0" \
  --body '{"schedule":{"type":"FixedRate","interval":"1m"}}' \
  --project "{{user.project_name}}"
```

## HALT vs Retry Decision

| Error Type | Decision | Rationale |
|------------|----------|-----------|
| `Forbidden.*` | HALT | Permission issue — delegate to `alicloud-ram-ops` |
| `NotFound.*` | HALT | Resource missing — create it first |
| `Invalid*` | HALT | Parameter error — fix input |
| `AlreadyExists` | HALT | Naming conflict — choose different name |
| `Throttling` | Retry | Rate limit — backoff and retry |
| `InternalError` | Retry | Server issue — retry with backoff |
| `ServiceUnavailable` | Retry | Temporary outage — backoff |

## Escalation Path

### For HALT Errors

1. **Permission errors** → Delegate to `alicloud-ram-ops`
2. **Resource not found** → Create resource first
3. **Invalid parameters** → Fix input and retry
4. **Naming conflicts** → Choose different name

### For Retry Errors

1. **Throttling** → Exponential backoff (1s, 2s, 4s)
2. **InternalError** → Retry up to 3 times, then escalate with RequestId
3. **ServiceUnavailable** → Check Alibaba Cloud status page

## Log Collection Issues

### Logtail Not Collecting Logs

**Diagnosis:**
1. Check Logtail agent status
2. Check log path configuration
3. Check machine group membership

**Recovery:**
```bash
# Check Logtail status (on ECS)
ps aux | grep logtail

# Check Logtail configuration
cat /etc/ilogtail/conf.d/*.conf

# Restart Logtail
sudo service logtail restart
```

### Logs Ingested but Not Queryable

**Diagnosis:**
1. Check index configuration
2. Check query syntax
3. Check time range

**Recovery:**
```bash
# Create index if missing
aliyun sls POST /logstores/{{user.logstore}}/index \
  --header "x-log-apiversion=0.9.0" \
  --body '{"fullTextIndex":{"caseSensitive":false,"includeChinese":true,"token":["@"," ", ","]}}' \
  --project "{{user.project_name}}"
```

## Performance Issues

### Slow Queries

**Diagnosis:**
1. Check query complexity
2. Check index coverage
3. Check shard count

**Recovery:**
- Simplify queries
- Add indexes for frequently queried fields
- Increase shard count for write throughput

### High Latency

**Diagnosis:**
1. Check network connectivity
2. Check endpoint selection
3. Check region proximity

**Recovery:**
- Use regional endpoint
- Check Alibaba Cloud network status
- Consider cross-region replication for global access

## Reference Documentation

- [SLS Error Codes](https://help.aliyun.com/zh/sls/developer-reference/error-codes)
- [SLS Troubleshooting](https://help.aliyun.com/zh/sls/developer-reference/troubleshooting)
- [SLS Best Practices](https://help.aliyun.com/zh/sls/developer-reference/best-practices-for-log-service)
