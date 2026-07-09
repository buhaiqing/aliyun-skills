# Alibaba Cloud DNS CLI Usage Reference

## Public Authoritative DNS (Alidns)

### Domain Management

```bash
# Add a domain to DNS service
aliyun alidns AddDomain --DomainName "example.com"

# List all managed domains
aliyun alidns DescribeDomains --PageNumber 1 --PageSize 10

# Get domain details
aliyun alidns DescribeDomainInfo --DomainName "example.com"

# Delete a domain
aliyun alidns DeleteDomain --DomainName "example.com"
```

### Record Management

```bash
# Add an A record
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "A" \
  --Value "1.2.3.4" \
  --TTL 600

# Add a CNAME record
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "app" \
  --Type "CNAME" \
  --Value "example.aliyuncs.com" \
  --TTL 600

# List all records for a domain
aliyun alidns DescribeDomainRecords \
  --DomainName "example.com" \
  --PageNumber 1 \
  --PageSize 50

# Get specific record
aliyun alidns DescribeDomainRecords \
  --DomainName "example.com" \
  --RRKeyWord "www" \
  --TypeKeyWord "A"

# Update a record
aliyun alidns UpdateDomainRecord \
  --RecordId "12345678" \
  --RR "www" \
  --Type "A" \
  --Value "5.6.7.8" \
  --TTL 300

# Delete a record
aliyun alidns DeleteDomainRecord --RecordId "12345678"

# Enable a paused record
aliyun alidns EnableDomainRecord --RecordId "12345678"

# Disable a record (pause)
aliyun alidns DisableDomainRecord --RecordId "12345678"
```

### Line-Based Routing

```bash
# Add record with ISP line routing
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "A" \
  --Value "1.2.3.4" \
  --Line "telecom"

# Add record with geographic routing
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "A" \
  --Value "2.3.4.5" \
  --Line "oversea"

# List available routing lines
aliyun alidns DescribeLines --DomainName "example.com"
```

### Weighted Routing

```bash
# Add weighted records
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "A" \
  --Value "1.2.3.4" \
  --Weight 50

aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "A" \
  --Value "5.6.7.8" \
  --Weight 50
```

### Health Checks & GTM

```bash
# Add GTM address pool
aliyun alidns AddGtmAddressPool \
  --Name "primary-pool" \
  --Type "IPv4" \
  --Addr "1.2.3.4,5.6.7.8"

# Update health check configuration
aliyun alidns UpdateGtmAddressPool \
  --PoolId "pool_123" \
  --HealthCheckConfig '{"ProbeContent":"/","ProbeInterval":60,"ProbeType":"HTTP","ProbePort":80}'

# Get GTM instance status
aliyun alidns DescribeGtmInstanceStatus --InstanceId "gtm_123"

# Trigger manual failover
aliyun alidns SwitchGtmFailoverAddressPool --InstanceId "gtm_123"
```

### DNSSEC

```bash
# Enable DNSSEC
aliyun alidns EnableDnssec --DomainName "example.com"

# Disable DNSSEC
aliyun alidns DisableDnssec --DomainName "example.com"

# Get DNSSEC status
aliyun alidns DescribeDnssecStatus --DomainName "example.com"
```

### Query Analytics & Logs

```bash
# Get DNS query logs
aliyun alidns DescribeDnsLogs \
  --DomainName "example.com" \
  --StartDate "2026-07-01" \
  --EndDate "2026-07-03"

# Get query statistics
aliyun alidns DescribeDomainStatistics \
  --DomainName "example.com" \
  --StartDate "2026-07-01" \
  --EndDate "2026-07-03"

# Real-time QPS monitoring
aliyun alidns DescribeDnsRealTimeQps
```

## Private DNS (PrivateZone)

### Zone Management

```bash
# Create PrivateZone
aliyun pvtz CreateZone \
  --ZoneName "internal.example.com" \
  --Remark "Internal DNS zone"

# List PrivateZones
aliyun pvtz DescribeZones \
  --PageNumber 1 \
  --PageSize 10

# Get zone details
aliyun pvtz DescribeZoneInfo --ZoneId "zone_123"

# Delete PrivateZone
aliyun pvtz DeleteZone --ZoneId "zone_123"
```

### Record Management

```bash
# Add record to PrivateZone
aliyun pvtz AddZoneRecord \
  --ZoneId "zone_123" \
  --Rr "api" \
  --Type "A" \
  --Value "10.0.0.1"

# List records in PrivateZone
aliyun pvtz DescribeZoneRecords \
  --ZoneId "zone_123" \
  --PageNumber 1 \
  --PageSize 10

# Update PrivateZone record
aliyun pvtz UpdateZoneRecord \
  --RecordId "record_456" \
  --Rr "api" \
  --Type "A" \
  --Value "10.0.0.2"

# Delete PrivateZone record
aliyun pvtz DeleteZoneRecord --RecordId "record_456"
```

### VPC Binding

```bash
# Bind PrivateZone to VPC
aliyun pvtz BindZoneVpc \
  --ZoneId "zone_123" \
  --Vpcs '[{"VpcId":"vpc_123","RegionId":"cn-hangzhou"}]'

# Unbind PrivateZone from VPC
aliyun pvtz UnbindZoneVpc \
  --ZoneId "zone_123" \
  --Vpcs '[{"VpcId":"vpc_123","RegionId":"cn-hangzhou"}]'

# List VPCs bound to PrivateZone
aliyun pvtz DescribeZoneVpcList --ZoneId "zone_123"
```

### Forwarding Rules

```bash
# Add forwarding rule
aliyun pvtz AddForwardRule \
  --ZoneName "example.com" \
  --Vpcs '[{"VpcId":"vpc_123","RegionId":"cn-hangzhou"}]'

# List forwarding rules
aliyun pvtz DescribeForwardRules \
  --PageNumber 1 \
  --PageSize 10

# Delete forwarding rule
aliyun pvtz DeleteForwardRule --RuleId "rule_789"
```

## Common Patterns

### Pre-flight Validation

```bash
# Check if domain exists
aliyun alidns DescribeDomainInfo --DomainName "example.com"

# Check NS records
dig NS example.com @ns1.alidns.com

# Check existing records
aliyun alidns DescribeDomainRecords \
  --DomainName "example.com" \
  --RRKeyWord "www" \
  --TypeKeyWord "A"
```

### Post-change Validation

```bash
# Verify record after update
aliyun alidns DescribeDomainRecords \
  --DomainName "example.com" \
  --RRKeyWord "www" \
  --TypeKeyWord "A"

# Test DNS resolution
dig A www.example.com @ns1.alidns.com

# Check propagation
dig A www.example.com @8.8.8.8
```

### Batch Operations

```bash
# Add multiple records in sequence
for record in "www:A:1.2.3.4" "app:CNAME:example.aliyuncs.com" "mail:MX:10:mx.example.com"; do
  IFS=':' read -r rr type value <<< "$record"
  aliyun alidns AddRecord \
    --DomainName "example.com" \
    --RR "$rr" \
    --Type "$type" \
    --Value "$value"
done
```

## Error Handling

### Common Error Codes

| Error Code | Description | Resolution |
|------------|-------------|------------|
| `InvalidParameter` | Parameter format error | Check parameter format and try again |
| `DomainNotExists` | Domain not in DNS service | Add domain first with `AddDomain` |
| `RecordNotExists` | Record ID not found | Verify record exists with `DescribeDomainRecords` |
| `Forbidden.AliasRecord` | CNAME record conflict | Delete conflicting CNAME record first |
| `Throttling` | API rate limit | Wait and retry with exponential backoff |
| `UnauthorizedOperation` | Insufficient RAM permissions | Check RAM policy for DNS permissions |

### Retry Strategy

```bash
# Exponential backoff retry
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
```

## Integration Examples

### With SLB/ALB

```bash
# Configure DNS CNAME to SLB
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "CNAME" \
  --Value "example.slb.aliyuncs.com"
```

### With CDN

```bash
# Configure DNS CNAME to CDN
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "static" \
  --Type "CNAME" \
  --Value "example.com.kunlun.com"
```

### With VPC/PrivateZone

```bash
# Create PrivateZone for internal services
aliyun pvtz CreateZone --ZoneName "internal.example.com"

# Add internal DNS record
aliyun pvtz AddZoneRecord \
  --ZoneId "zone_123" \
  --Rr "api.internal" \
  --Type "A" \
  --Value "10.0.0.1"

# Bind to VPC
aliyun pvtz BindZoneVpc \
  --ZoneId "zone_123" \
  --Vpcs '[{"VpcId":"vpc_123","RegionId":"cn-hangzhou"}]'
```