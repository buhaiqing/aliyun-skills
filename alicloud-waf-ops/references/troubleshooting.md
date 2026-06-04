# Troubleshooting — Alibaba Cloud WAF

## Common API Error Codes

| Error Code | HTTP Status | Meaning | Agent Action |
|------------|-------------|---------|--------------|
| `InvalidParameter` | 400 | Parameter validation failed | Fix per OpenAPI spec |
| `InvalidParameterValue` | 400 | Value out of allowed range | HALT; check enums |
| `MissingParameter` | 400 | Required field missing | HALT; add required field |
| `Forbidden.NoPermission` | 403 | RAM permission denied | HALT; add `waf:*` policy |
| `NoPermission` | 403 | Insufficient privilege | HALT; scope RAM policy |
| `InvalidAccessKeyId` | 401 | Bad AccessKey ID | HALT; fix credentials |
| `SignatureDoesNotMatch` | 401 | Signature mismatch | HALT; check SK or clock sync |
| `Throttling` | 429 | Rate limit exceeded | Retry with backoff (1s, 2s, 4s) |
| `Throttling.User` | 429 | User-level rate limit | Retry with exponential backoff |
| `InternalError` | 500 | Server-side error | Retry; escalate with RequestId |
| `ServiceUnavailable` | 503 | Temporary outage | Backoff; check status page |
| `InstanceNotFound` | 404 | WAF instance not found | HALT; create instance in console |
| `DomainAlreadyExists` | 409 | Domain already protected | Use ModifyDomain instead |
| `DomainNotFound` | 404 | Domain not in WAF | Add domain first |
| `OriginAddressUnreachable` | 400 | Origin server unreachable | HALT; verify origin IP/port |
| `InvalidIpFormat` | 400 | IP/CIDR format error | HALT; fix IP format |
| `RuleQuotaExceeded` | 400 | Rule quota reached | HALT; delete unused rules |
| `DefenseRuleNotFound` | 404 | Defense rule not found | Re-list rules to get current IDs |
| `InvalidPort` | 400 | Port format error | Check allowed port ranges |

## Diagnostic Order

### Step 1: Verify Credentials

```bash
# Check if credentials are set
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo "✅ AK is set" || echo "❌ AK not set"
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "✅ SK is set" || echo "❌ SK not set"
```

### Step 2: Verify CLI Plugin

```bash
# Check WAF plugin installed
aliyun plugin list | grep waf

# If not installed:
aliyun plugin install --names aliyun-cli-waf-openapi
```

### Step 3: Test Basic Connectivity

```bash
# Query instance info (tests credentials + plugin + region)
aliyun waf-openapi DescribeInstanceInfo \
  --RegionId cn-hangzhou \
  --version 2021-10-01 \
  --force
```

### Step 4: Check Instance Exists

```bash
# Verify WAF instance is provisioned
aliyun waf-openapi DescribeInstanceInfo \
  --RegionId cn-hangzhou \
  --version 2021-10-01 \
  --force | jq '.InstanceInfo.InstanceId'
```

### Step 5: Verify Domain Configuration

```bash
# Check domain is added to WAF
aliyun waf-openapi DescribeDomainList \
  --RegionId cn-hangzhou \
  --InstanceId waf_xxx \
  --version 2021-10-01 \
  --force | jq '.DomainList[].Domain'
```

### Step 6: Check Origin Reachability

```bash
# Test origin server from outside WAF
curl -I http://origin_ip:port
```

## Specific Troubleshooting Scenarios

### Scenario: "DomainAlreadyExists" when adding domain

**Cause:** Domain is already protected in WAF.

**Resolution:**
```bash
# List existing domains to find the duplicate
aliyun waf-openapi DescribeDomainList \
  --RegionId cn-hangzhou \
  --InstanceId waf_xxx \
  --version 2021-10-01 \
  --force

# Option 1: Modify existing domain config
aliyun waf-openapi ModifyDomain --Domain example.com ...

# Option 2: Delete and re-add
aliyun waf-openapi DeleteDomain --Domain example.com --version 2021-10-01 --force
```

### Scenario: "OriginAddressUnreachable"

**Cause:** WAF cannot connect to origin server.

**Resolution:**
1. Verify origin server IP/hostname is correct
2. Check origin server port is open
3. Verify security groups allow WAF IP ranges
4. Test origin directly: `curl http://origin_ip:port`

### Scenario: "Throttling" errors

**Cause:** API rate limit exceeded.

**Resolution:**
```bash
# Wait and retry with backoff
sleep 2
# Retry the operation
```

### Scenario: CLI calls WAF 2.0 instead of 3.0

**Cause:** Missing `--version 2021-10-01 --force` options.

**Resolution:**
```bash
# Always include both options
aliyun waf-openapi <Operation> \
  --RegionId cn-hangzhou \
  --version 2021-10-01 \
  --force
```

### Scenario: CNAME not resolving to WAF

**Cause:** DNS not updated or propagation delay.

**Resolution:**
```bash
# Check current DNS
nslookup example.com

# Expected: Should resolve to WAF CNAME
# If not: Update DNS A/CNAME record to WAF CNAME
```

## Escalation Criteria

| Condition | Escalation Path |
|-----------|-----------------|
| Persistent `InternalError` | Contact Alibaba Cloud support with RequestId |
| Quota cannot be increased | Contact sales for edition upgrade |
| Origin unreachable after verification | Check VPC/Security Group with `alicloud-ecs-ops` |
| DNS issues | Verify with DNS provider |
