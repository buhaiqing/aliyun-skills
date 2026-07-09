# DNS Troubleshooting Guide

## Common DNS Issues & Solutions

### 1. Domain Not Resolving

**Symptoms**:
- `dig` or `nslookup` returns no records
- Website inaccessible via domain name

**Possible Causes**:
- Domain not added to DNS service
- NS records not pointing to Alibaba Cloud
- DNS records deleted or paused
- TTL propagation delay

**Diagnostic Steps**:
```bash
# Check if domain exists in DNS
aliyun alidns DescribeDomainInfo --DomainName "example.com"

# Verify NS records
dig NS example.com @a.gtld-servers.net

# Check existing records
aliyun alidns DescribeDomainRecords --DomainName "example.com"

# Test resolution from Alibaba Cloud DNS
dig A www.example.com @ns1.alidns.com
```

**Solutions**:
```bash
# If domain not added
aliyun alidns AddDomain --DomainName "example.com"

# If NS records incorrect, update with domain registrar
# If records deleted, recreate them
aliyun alidns AddRecord --DomainName "example.com" --RR "www" --Type "A" --Value "1.2.3.4"
```

### 2. CNAME Conflicts

**Symptoms**:
- Error: `Forbidden.AliasRecord`
- Cannot add CNAME record when A/AAAA exists
- Cannot add A/AAAA when CNAME exists

**Diagnostic Steps**:
```bash
# Check for conflicting records
aliyun alidns DescribeDomainRecords \
  --DomainName "example.com" \
  --RRKeyWord "www" \
  --TypeKeyWord "A"

aliyun alidns DescribeDomainRecords \
  --DomainName "example.com" \
  --RRKeyWord "www" \
  --TypeKeyWord "CNAME"
```

**Solutions**:
```bash
# Remove conflicting A record before adding CNAME
aliyun alidns DeleteDomainRecord --RecordId "conflicting_record_id"

# Or remove conflicting CNAME before adding A
aliyun alidns DeleteDomainRecord --RecordId "conflicting_cname_id"
```

### 3. DNS Propagation Delays

**Symptoms**:
- Changes not visible immediately
- Different results from different DNS servers
- TTL not expiring as expected

**Diagnostic Steps**:
```bash
# Check TTL value
dig +ttlid A www.example.com @ns1.alidns.com

# Test multiple DNS servers
dig A www.example.com @ns1.alidns.com
dig A www.example.com @ns2.alidns.com
dig A www.example.com @8.8.8.8
dig A www.example.com @1.1.1.1

# Check record status
aliyun alidns DescribeDomainRecords \
  --DomainName "example.com" \
  --RRKeyWord "www" \
  --TypeKeyWord "A" \
  --Status "ENABLE"
```

**Solutions**:
- Wait for TTL to expire (max 24 hours for standard records)
- Reduce TTL before making changes (e.g., 60 seconds)
- Flush local DNS cache: `sudo dscacheutil -flushcache` (macOS)
- Use authoritative DNS servers for testing

### 4. Health Check Failures

**Symptoms**:
- GTM shows health check failures
- Automatic failover not working
- Manual failover required

**Diagnostic Steps**:
```bash
# Check GTM instance status
aliyun alidns DescribeGtmInstanceStatus --InstanceId "gtm_123"

# Verify health check configuration
aliyun alidns DescribeGtmAddressPool --PoolId "pool_123"

# Test health check endpoint manually
curl -I http://www.example.com/health

# Check health check logs
aliyun alidns DescribeDnsLogs --DomainName "example.com" --StartDate $(date -d "1 hour ago" +%Y-%m-%d) --EndDate $(date +%Y-%m-%d)
```

**Solutions**:
```bash
# Verify backend server is accessible
ping www.example.com

# Check security groups allow health check traffic
aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId "sg_123"

# Update health check configuration
aliyun alidns UpdateGtmAddressPool \
  --PoolId "pool_123" \
  --HealthCheckConfig '{"ProbeContent":"/health","ProbeInterval":60,"ProbeType":"HTTP","ProbePort":80}'

# Trigger manual failover if needed
aliyun alidns SwitchGtmFailoverAddressPool --InstanceId "gtm_123"
```

### 5. PrivateZone Not Working

**Symptoms**:
- Internal DNS resolution failing
- VPC instances cannot resolve internal domains
- PrivateZone records not accessible

**Diagnostic Steps**:
```bash
# Check PrivateZone exists
aliyun pvtz DescribeZoneInfo --ZoneId "zone_123"

# Verify VPC binding
aliyun pvtz DescribeZoneVpcList --ZoneId "zone_123"

# Check records in PrivateZone
aliyun pvtz DescribeZoneRecords --ZoneId "zone_123"

# Test resolution from VPC instance
nslookup api.internal.example.com 100.100.2.136
```

**Solutions**:
```bash
# If VPC not bound
aliyun pvtz BindZoneVpc \
  --ZoneId "zone_123" \
  --Vpcs '[{"VpcId":"vpc_123","RegionId":"cn-hangzhou"}]'

# If records missing
aliyun pvtz AddZoneRecord \
  --ZoneId "zone_123" \
  --Rr "api" \
  --Type "A" \
  --Value "10.0.0.1"

# Verify from VPC instance
dig A api.internal.example.com @100.100.2.136
```

### 6. DNSSEC Validation Errors

**Symptoms**:
- DNSSEC validation failures
- `SERVFAIL` responses
- DNSSEC-signed domains not resolving

**Diagnostic Steps**:
```bash
# Check DNSSEC status
aliyun alidns DescribeDnssecStatus --DomainName "example.com"

# Test DNSSEC validation
dig +dnssec A www.example.com @ns1.alidns.com

# Verify DS records with registrar
dig DS example.com @a.gtld-servers.net
```

**Solutions**:
```bash
# If DNSSEC not enabled
aliyun alidns EnableDnssec --DomainName "example.com"

# Verify DS records are set with domain registrar
# Contact registrar to add DS records if missing

# If DNSSEC causing issues, temporarily disable
aliyun alidns DisableDnssec --DomainName "example.com"
```

### 7. GTM Failover Not Working

**Symptoms**:
- Traffic not shifting to backup
- Health checks passing but failover not triggering
- Manual failover required

**Diagnostic Steps**:
```bash
# Check GTM configuration
aliyun alidns DescribeGtmInstanceStatus --InstanceId "gtm_123"

# Verify address pools
aliyun alidns DescribeGtmAddressPool --PoolId "pool_123"

# Check health check status
aliyun alidns DescribeGtmAddressPool --PoolId "pool_456"

# Test DNS resolution
dig A www.example.com @ns1.alidns.com
```

**Solutions**:
```bash
# Update GTM configuration
aliyun alidns UpdateGtmInstance \
  --InstanceId "gtm_123" \
  --Name "production-gtm" \
  --StrategyMode "AUTO"

# Trigger manual failover
aliyun alidns SwitchGtmFailoverAddressPool --InstanceId "gtm_123"

# Verify failover worked
aliyun alidns DescribeGtmInstanceStatus --InstanceId "gtm_123"
```

### 8. Rate Limiting / Throttling

**Symptoms**:
- Error: `Throttling`
- API calls being rejected
- Operations failing intermittently

**Diagnostic Steps**:
```bash
# Check API call frequency
# Review recent API logs

# Test with simple query
aliyun alidns DescribeDomains --PageNumber 1 --PageSize 1
```

**Solutions**:
```bash
# Implement exponential backoff
retry_count=0
max_retries=3
while [ $retry_count -lt $max_retries ]; do
  result=$(aliyun alidns AddRecord ...)
  if [ $? -eq 0 ]; then
    break
  fi
  sleep $((2 ** retry_count))
  retry_count=$((retry_count + 1))
done

# Reduce API call frequency
# Use batch operations when possible
```

## Performance Issues

### Slow DNS Resolution

**Symptoms**:
- High DNS response times
- Slow website loading
- Intermittent connectivity

**Diagnostic Steps**:
```bash
# Measure DNS resolution time
dig A www.example.com @ns1.alidns.com | grep "Query time"

# Check TTL values
dig +ttlid A www.example.com @ns1.alidns.com

# Test multiple DNS servers
dig A www.example.com @8.8.8.8
dig A www.example.com @1.1.1.1
```

**Solutions**:
```bash
# Reduce TTL for faster propagation
aliyun alidns UpdateDomainRecord \
  --RecordId "12345678" \
  --RR "www" \
  --Type "A" \
  --Value "1.2.3.4" \
  --TTL 60

# Use DNS caching at application level
# Configure local DNS resolver
```

### Inconsistent Resolution

**Symptoms**:
- Different results from different DNS servers
- Regional resolution differences
- ISP-specific issues

**Diagnostic Steps**:
```bash
# Test from different locations
# Use DNS propagation check tools
dig A www.example.com @ns1.alidns.com
dig A www.example.com @ns2.alidns.com

# Check line-based routing
aliyun alidns DescribeDomainRecords \
  --DomainName "example.com" \
  --RRKeyWord "www" \
  --TypeKeyWord "A"
```

**Solutions**:
```bash
# Verify line-based routing configuration
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "A" \
  --Value "1.2.3.4" \
  --Line "default"

# Check for ISP-specific routing issues
# Contact ISP if necessary
```

## Security Issues

### Unauthorized DNS Changes

**Symptoms**:
- Unexpected DNS record changes
- Domain pointing to wrong IP
- Security alert from ActionTrail

**Diagnostic Steps**:
```bash
# Check ActionTrail for DNS changes
aliyun actiontrail LookupEvents \
  --EventName "AddRecord" \
  --StartTime $(date -d "24 hours ago" +%Y-%m-%dT%H:%M:%SZ) \
  --EndTime $(date +%Y-%m-%dT%H:%M:%SZ)

# Verify DNS records
aliyun alidns DescribeDomainRecords --DomainName "example.com"

# Check RAM policies
aliyun ram ListPoliciesForUser --UserName "dns_admin"
```

**Solutions**:
```bash
# Restore from backup
cat dns-backup-20260703.json | jq -r '.DomainRecords.Record[] | 
  "aliyun alidns UpdateDomainRecord --RecordId \"\(.RecordId)\" --RR \"\(.RR)\" --Type \"\(.Type)\" --Value \"\(.Value)\" --TTL \(.TTL)"' | sh

# Update RAM policies to least privilege
# Enable MFA for DNS management accounts
# Review and revoke unnecessary access
```

### DNS Hijacking

**Symptoms**:
- Domain resolving to malicious IP
- SSL certificate warnings
- Browser security alerts

**Diagnostic Steps**:
```bash
# Check DNS resolution
dig A www.example.com @ns1.alidns.com

# Verify SSL certificate
openssl s_client -connect www.example.com:443 -servername www.example.com

# Check for unauthorized records
aliyun alidns DescribeDomainRecords --DomainName "example.com"
```

**Solutions**:
```bash
# Remove unauthorized records
aliyun alidns DeleteDomainRecord --RecordId "malicious_record_id"

# Enable DNSSEC
aliyun alidns EnableDnssec --DomainName "example.com"

# Update NS records if compromised
# Contact Alibaba Cloud support immediately
# Review all DNS records and security logs
```

## Recovery Procedures

### 1. Domain Recovery

```bash
# Re-add deleted domain
aliyun alidns AddDomain --DomainName "example.com"

# Restore records from backup
cat dns-backup-20260703.json | jq -r '.DomainRecords.Record[] | 
  "aliyun alidns AddRecord --DomainName \"example.com\" --RR \"\(.RR)\" --Type \"\(.Type)\" --Value \"\(.Value)\" --TTL \(.TTL)"' | sh
```

### 2. Record Recovery

```bash
# Update record to known good value
aliyun alidns UpdateDomainRecord \
  --RecordId "12345678" \
  --RR "www" \
  --Type "A" \
  --Value "1.2.3.4" \
  --TTL 600
```

### 3. NS Recovery

```bash
# Update NS records to original
aliyun alidns UpdateDomainRecord \
  --RecordId "ns_record_id" \
  --RR "example.com" \
  --Type "NS" \
  --Value "ns1.alidns.com,ns2.alidns.com"
```

### 4. GTM Recovery

```bash
# Revert GTM failover
aliyun alidns SwitchGtmFailoverAddressPool --InstanceId "gtm_123"

# Restore primary address pool
aliyun alidns UpdateGtmAddressPool \
  --PoolId "pool_123" \
  --Addr "1.2.3.4,5.6.7.8"
```

## Monitoring & Alerting

### Key Metrics to Monitor

| Metric | Warning Threshold | Critical Threshold |
|--------|-------------------|-------------------|
| DNS Query Volume | >10x normal | >100x normal |
| DNS Response Time | >500ms | >2000ms |
| Health Check Failures | >3 consecutive | >10 consecutive |
| GTM Failover Events | Any | Any |
| DNSSEC Validation Errors | Any | Any |

### Alert Configuration

```bash
# Create CMS alarm for DNS query volume
aliyun cms PutMetricRuleTargets \
  --RuleId "dns_query_volume" \
  --Targets '[{"Id":"target_1","ARN":"acs:ess:cn-hangzhou:*:scaling_group/scg_123"}]'
```

## Escalation Procedures

### Level 1: Self-Service
- Check DNS status and records
- Verify NS propagation
- Test health checks

### Level 2: SRE Team
- DNS hijacking suspected
- GTM failover issues
- PrivateZone connectivity problems

### Level 3: Alibaba Cloud Support
- Domain registration issues
- DNSSEC validation failures
- Service-wide outages

### Level 4: Management
- Security breaches
- Business-critical failures
- Compliance violations