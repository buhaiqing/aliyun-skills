# DNS Operations Skill Rubric

## Overview

This rubric defines the quality gates for the `alicloud-dns-ops` skill. All
operations must pass these criteria before execution. The rubric is designed
for GCL (GCL Runner) adversarial review.

## Quality Gates

### P0 - Must Pass (Blocking)

| Gate | Criterion | Validation | Failure Action |
|------|-----------|------------|----------------|
| **P0-1** | Domain ownership verified | `DescribeDomainInfo` returns success | HALT - Verify domain is added to DNS service |
| **P0-2** | NS records pointing to Alibaba Cloud | `dig NS` shows `ns1.alidns.com` | HALT - Update NS records with domain registrar |
| **P0-3** | RAM permissions valid | `ListPoliciesForUser` includes DNS policy | HALT - Request DNS permissions from admin |
| **P0-4** | Record format valid | Regex validation for record types | HALT - Fix record format |
| **P0-5** | No CNAME conflicts | Check for existing A/AAAA records | HALT - Remove conflicting records first |
| **P0-6** | Credentials not leaked | No AK/SK in output | HALT - Mask credentials in output |
| **P0-7** | TTL within valid range | 60-86400 seconds | HALT - Adjust TTL value |
| **P0-8** | Weight within valid range | 1-100 | HALT - Adjust weight value |

### P1 - Should Pass (Warning)

| Gate | Criterion | Validation | Failure Action |
|------|-----------|------------|----------------|
| **P1-1** | Health check configured | `DescribeGtmAddressPool` shows health check | WARN - Configure health checks for production |
| **P1-2** | DNSSEC enabled | `DescribeDnssecStatus` shows enabled | WARN - Enable DNSSEC for security |
| **P1-3** | Audit logging enabled | ActionTrail integration verified | WARN - Enable audit logging |
| **P1-4** | Backup created | DNS configuration exported | WARN - Create backup before changes |
| **P1-5** | Rollback plan documented | Recovery steps defined | WARN - Document rollback procedure |
| **P1-6** | Change ticket created | Ticket number provided | WARN - Create change ticket |
| **P1-7** | Monitoring configured | CMS alarms set up | WARN - Configure monitoring alerts |

### P2 - Nice to Have (Advisory)

| Gate | Criterion | Validation | Failure Action |
|------|-----------|------------|----------------|
| **P2-1** | Performance baseline | Response time < 100ms | INFO - Optimize DNS configuration |
| **P2-2** | Security best practices | Least-privilege access | INFO - Review RAM policies |
| **P2-3** | Documentation complete | All records documented | INFO - Update DNS documentation |
| **P2-4** | Compliance requirements | Audit trail complete | INFO - Review compliance status |

## Validation Rules

### Record Type Validation

| Record Type | Format | Example | Validation |
|-------------|--------|---------|------------|
| **A** | IPv4 address | `1.2.3.4` | Regex: `^(\d{1,3}\.){3}\d{1,3}$` |
| **AAAA** | IPv6 address | `2001:db8::1` | Regex: `^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$` |
| **CNAME** | Domain name | `example.com` | Regex: `^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.$` |
| **MX** | Priority + domain | `10 mx.example.com` | Regex: `^\d{1,3}\s+[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.$` |
| **TXT** | Text string | `"v=spf1 ..."` | Max 255 characters per string |
| **NS** | Name server | `ns1.example.com` | Regex: `^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.$` |
| **SRV** | Priority + weight + port + target | `10 50 5060 sip.example.com` | Regex: `^\d{1,3}\s+\d{1,3}\s+\d{1,5}\s+[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.$` |
| **CAA** | Flags + tag + value | `0 issue "letsencrypt.org"` | Regex: `^\d{1,3}\s+[a-z]+\s+".*"$` |

### TTL Validation

| Environment | Recommended TTL | Acceptable Range |
|-------------|----------------|------------------|
| Production | 300-600 seconds | 60-86400 seconds |
| Development | 60-120 seconds | 60-86400 seconds |
| Emergency | 60 seconds | 60-300 seconds |

### Weight Validation

| Scenario | Recommended Weight | Acceptable Range |
|----------|-------------------|------------------|
| Primary | 70-80 | 1-100 |
| Secondary | 20-30 | 1-100 |
| Backup | 10-20 | 1-100 |

## Safety Rules

### High-Risk Operations (Require GCL Review)

| Operation | Risk Level | Required Approvals |
|-----------|------------|-------------------|
| Delete Domain | CRITICAL | SRE Lead + Security |
| Delete Record | HIGH | SRE Lead |
| Update NS Records | CRITICAL | SRE Lead + Security |
| Enable DNSSEC | HIGH | Security |
| GTM Failover | HIGH | SRE Lead |
| PrivateZone Delete | HIGH | VPC Owner |

### Medium-Risk Operations (Require Approval)

| Operation | Risk Level | Required Approvals |
|-----------|------------|-------------------|
| Add Record | LOW | None |
| Update Record | MEDIUM | Peer Review |
| Change TTL | LOW | None |
| Weight Changes | MEDIUM | Peer Review |
| Line Changes | MEDIUM | Peer Review |

### Low-Risk Operations (Auto-Approved)

| Operation | Risk Level | Required Approvals |
|-----------|------------|-------------------|
| List Records | READ-ONLY | None |
| Get Domain Info | READ-ONLY | None |
| Query Logs | READ-ONLY | None |
| Statistics | READ-ONLY | None |

## Error Handling Rules

### HALT Errors (Do Not Retry)

| Error Code | Description | Required Action |
|------------|-------------|-----------------|
| `InvalidParameter` | Parameter format error | Fix parameter and retry |
| `DomainNotExists` | Domain not in DNS service | Add domain first |
| `RecordNotExists` | Record ID not found | Verify record exists |
| `Forbidden.AliasRecord` | CNAME conflict | Remove conflicting record |
| `UnauthorizedOperation` | Insufficient permissions | Request permissions |

### RETRY Errors (Temporary)

| Error Code | Description | Retry Strategy |
|------------|-------------|----------------|
| `Throttling` | API rate limit | Exponential backoff (1s, 2s, 4s) |
| `ServiceUnavailable` | Service temporarily unavailable | Retry after 30s |
| `InternalError` | Internal server error | Retry after 60s |

### FALLBACK Errors (Alternative Path)

| Error Code | Description | Fallback Strategy |
|------------|-------------|-------------------|
| `IncorrectDomainStatus` | Domain in invalid state | Use SDK fallback |
| `InvalidRR.Format` | Subdomain format invalid | Validate RR format |
| `InvalidType.Record` | Record type not supported | Check supported types |

## Validation Procedures

### Pre-flight Validation

1. **Domain Check**
   ```bash
   aliyun alidns DescribeDomainInfo --DomainName "example.com"
   ```

2. **NS Check**
   ```bash
   dig NS example.com @a.gtld-servers.net
   ```

3. **Permission Check**
   ```bash
   aliyun ram ListPoliciesForUser --UserName "dns_admin"
   ```

4. **Conflict Check**
   ```bash
   aliyun alidns DescribeDomainRecords --DomainName "example.com" --RRKeyWord "www"
   ```

### Post-change Validation

1. **Record Status**
   ```bash
   aliyun alidns DescribeDomainRecords --DomainName "example.com" --RRKeyWord "www"
   ```

2. **DNS Resolution**
   ```bash
   dig A www.example.com @ns1.alidns.com
   ```

3. **Propagation Check**
   ```bash
   dig A www.example.com @8.8.8.8
   ```

4. **Health Check**
   ```bash
   curl -I http://www.example.com/health
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

### Security Requirements

- Enable DNSSEC for production domains
- Use RAM least-privilege policies
- Enable MFA for DNS management
- Audit all DNS changes via ActionTrail

## Performance Benchmarks

| Operation | Target Latency | Acceptable Range |
|-----------|---------------|------------------|
| Add Record | < 1000ms | < 3000ms |
| Update Record | < 1000ms | < 3000ms |
| Delete Record | < 1000ms | < 3000ms |
| DNS Resolution | < 100ms | < 500ms |
| Propagation | < 300s | < 3600s |
| GTM Failover | < 60s | < 300s |

## Monitoring Requirements

### Key Metrics

| Metric | Warning Threshold | Critical Threshold |
|--------|-------------------|-------------------|
| DNS Query Volume | >10x normal | >100x normal |
| DNS Response Time | >500ms | >2000ms |
| Health Check Failures | >3 consecutive | >10 consecutive |
| GTM Failover Events | Any | Any |
| DNSSEC Validation Errors | Any | Any |

### Alert Channels

| Severity | Channel | Response Time |
|----------|---------|---------------|
| Critical | SMS + Email | 15 minutes |
| Warning | Email | 1 hour |
| Info | Dashboard | Next business day