# DNS Safety Guidelines

## Overview

DNS operations are critical infrastructure changes that can affect global traffic
flow. This document outlines safety protocols, validation procedures, and
recovery strategies for DNS operations in Alibaba Cloud environments.

## DNS Change Risk Assessment

### High-Risk Operations

| Operation | Risk Level | Impact Window | Mitigation |
|-----------|------------|---------------|------------|
| Delete Domain | CRITICAL | Permanent | Backup zone file, verify no dependencies |
| Delete Record | HIGH | Until TTL expires | Backup record, verify health checks |
| Update NS Records | CRITICAL | Until TTL expires | Verify new NS servers, test resolution |
| Update SOA Record | HIGH | Until TTL expires | Verify parameters, test zone transfer |
| Enable DNSSEC | HIGH | Until propagation | Test DNSSEC validation, verify DS records |
| GTM Failover | HIGH | Until manual revert | Verify primary recovery, monitor health |

### Medium-Risk Operations

| Operation | Risk Level | Impact Window | Mitigation |
|-----------|------------|---------------|------------|
| Add Record | LOW | Until TTL expires | Validate record format, test resolution |
| Update Record | MEDIUM | Until TTL expires | Verify new value, test health checks |
| Change TTL | LOW | Until new TTL | Monitor propagation, adjust caching |
| Weight Changes | MEDIUM | Until next query | Monitor traffic distribution |
| Line Changes | MEDIUM | Until next query | Test ISP-specific resolution |

## Pre-flight Safety Checks

### 1. Domain Ownership Verification

```bash
# Verify domain is in DNS service
aliyun alidns DescribeDomainInfo --DomainName "example.com"

# Verify NS records point to Alibaba Cloud
dig NS example.com @a.gtld-servers.net

# Expected NS servers
# ns1.alidns.com
# ns2.alidns.com
```

### 2. Record Conflict Detection

```bash
# Check for CNAME conflicts
aliyun alidns DescribeDomainRecords \
  --DomainName "example.com" \
  --RRKeyWord "www" \
  --TypeKeyWord "CNAME"

# Check for A/AAAA conflicts
aliyun alidns DescribeDomainRecords \
  --DomainName "example.com" \
  --RRKeyWord "www" \
  --TypeKeyWord "A"
```

### 3. Permission Validation

```bash
# Verify RAM user has DNS permissions
aliyun ram GetUserPolicy --UserName <user> --PolicyName "AliyunDNSFullAccess"

# Expected policy
{
  "PolicyName": "AliyunDNSFullAccess",
  "PolicyType": "System"
}
```

### 4. Backup Creation

```bash
# Export current DNS configuration
aliyun alidns DescribeDomainRecords \
  --DomainName "example.com" \
  --PageSize 100 > dns-backup-$(date +%Y%m%d).json

# Backup PrivateZone records
aliyun pvtz DescribeZoneRecords \
  --ZoneId "zone_123" \
  --PageSize 100 > pvtz-backup-$(date +%Y%m%d).json
```

## Change Management Procedures

### Standard Change Process

1. **Request** — User submits DNS change request
2. **Review** — Validate change against safety rules
3. **Approve** — GCL adversarial review for write operations
4. **Execute** — Apply change with rollback plan
5. **Verify** — Confirm change propagation and health
6. **Monitor** — Track DNS resolution and traffic flow
7. **Document** — Record change in audit trail

### Emergency Change Process

1. **Assess** — Determine impact and urgency
2. **Authorize** — Emergency approval from SRE lead
3. **Execute** — Apply minimal necessary change
4. **Verify** — Immediate validation of change
5. **Monitor** — Continuous health monitoring
6. **Review** — Post-incident review within 24 hours

## Validation Procedures

### 1. Record Validation

```bash
# Verify record exists and is active
aliyun alidns DescribeDomainRecords \
  --DomainName "example.com" \
  --RRKeyWord "www" \
  --TypeKeyWord "A" \
  --Status "ENABLE"

# Test DNS resolution
dig A www.example.com @ns1.alidns.com

# Expected output
;; ANSWER SECTION:
www.example.com.    600    IN    A    1.2.3.4
```

### 2. Propagation Validation

```bash
# Test multiple DNS servers
dig A www.example.com @ns1.alidns.com
dig A www.example.com @ns2.alidns.com
dig A www.example.com @8.8.8.8
dig A www.example.com @1.1.1.1

# Check TTL propagation
dig +ttlid A www.example.com @ns1.alidns.com
```

### 3. Health Check Validation

```bash
# Verify health check is configured
aliyun alidns DescribeGtmInstanceStatus --InstanceId "gtm_123"

# Test health check endpoint
curl -I http://www.example.com/health

# Check health status
aliyun alidns DescribeGtmAddressPool --PoolId "pool_123"
```

### 4. GTM Failover Validation

```bash
# Simulate failover
aliyun alidns SwitchGtmFailoverAddressPool --InstanceId "gtm_123"

# Verify failover
aliyun alidns DescribeGtmInstanceStatus --InstanceId "gtm_123"

# Monitor traffic shift
aliyun alidns DescribeDnsLogs --DomainName "example.com" --StartDate $(date -d "1 hour ago" +%Y-%m-%d) --EndDate $(date +%Y-%m-%d)
```

## Rollback Procedures

### 1. Record Rollback

```bash
# Restore from backup
aliyun alidns UpdateDomainRecord \
  --RecordId "12345678" \
  --RR "www" \
  --Type "A" \
  --Value "1.2.3.4" \
  --TTL 600
```

### 2. Domain Rollback

```bash
# Re-add deleted domain
aliyun alidns AddDomain --DomainName "example.com"

# Restore records from backup
cat dns-backup-20260703.json | jq -r '.DomainRecords.Record[] | 
  "aliyun alidns AddRecord --DomainName \"example.com\" --RR \"\(.RR)\" --Type \"\(.Type)\" --Value \"\(.Value)\" --TTL \(.TTL)"' | sh
```

### 3. NS Rollback

```bash
# Update NS records to original
aliyun alidns UpdateDomainRecord \
  --RecordId "ns_record_id" \
  --RR "example.com" \
  --Type "NS" \
  --Value "ns1.alidns.com,ns2.alidns.com"
```

### 4. GTM Rollback

```bash
# Revert GTM failover
aliyun alidns SwitchGtmFailoverAddressPool --InstanceId "gtm_123"

# Restore primary address pool
aliyun alidns UpdateGtmAddressPool \
  --PoolId "pool_123" \
  --Addr "1.2.3.4,5.6.7.8"
```

## Security Best Practices

### 1. Access Control

- Use RAM roles with least-privilege policies
- Enable MFA for DNS management accounts
- Audit DNS changes via ActionTrail
- Use VPC PrivateZone for internal DNS

### 2. DNSSEC Implementation

- Enable DNSSEC for all production domains
- Verify DS records with domain registrar
- Monitor DNSSEC validation failures
- Rotate DNSSEC keys regularly

### 3. Query Logging

- Enable DNS query logs for all domains
- Monitor for unusual query patterns
- Set up alerts for high query volumes
- Retain logs for compliance requirements

### 4. Change Control

- Implement GCL adversarial review for all changes
- Use change management tickets for production
- Require peer review for critical DNS changes
- Document all DNS modifications

## Monitoring & Alerting

### Key Metrics

| Metric | Threshold | Alert Channel |
|--------|-----------|---------------|
| DNS Query Volume | >10x normal | SMS, Email |
| DNS Response Time | >500ms | Email |
| Health Check Failures | >3 consecutive | SMS, Email |
| GTM Failover Events | Any | SMS, Email |
| DNSSEC Validation Errors | Any | Email |

### Alert Configuration

```bash
# Create CMS alarm for DNS query volume
aliyun cms PutMetricRuleTargets \
  --RuleId "dns_query_volume" \
  --Targets '[{"Id":"target_1","ARN":"acs:ess:cn-hangzhou:*:scaling_group/scg_123"}]'
```

## Compliance Requirements

### Audit Trail

- All DNS changes logged in ActionTrail
- Retain logs for 90 days minimum
- Monthly DNS configuration review
- Quarterly security audit

### Change Documentation

- Document all DNS changes in ticket system
- Include change reason and approval
- Record rollback procedures
- Note any deviations from standard process

## Emergency Contacts

| Role | Contact | Availability |
|------|---------|--------------|
| DNS Admin | SRE Team Lead | 24/7 |
| Security | Security Operations | Business Hours |
| Network | Network Engineering | Business Hours |
| Management | VP of Engineering | Escalation Only