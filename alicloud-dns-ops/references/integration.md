# Alibaba Cloud DNS Integration Guide

## Overview

Alibaba Cloud DNS integrates with numerous other cloud services to provide
comprehensive network infrastructure management. This guide covers integration
patterns, cross-skill delegation, and best practices for DNS coordination.

## Integration Patterns

### 1. DNS + SLB/ALB Integration

**Use Case**: Configure domain resolution to load balancer endpoints

**Pattern**:
1. Create SLB/ALB instance → get DNS name (e.g., `example.slb.aliyuncs.com`)
2. Add CNAME record in DNS → point to SLB/ALB DNS name
3. Verify health checks → ensure backend servers are healthy
4. Test end-to-end → validate traffic flows through load balancer

**Example**:
```bash
# Get SLB DNS name
SLB_DNS=$(aliyun slb DescribeLoadBalancers --LoadBalancerName "web-slb" | jq -r '.LoadBalancers.LoadBalancer[0].Address')

# Add CNAME record
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "CNAME" \
  --Value "$SLB_DNS" \
  --TTL 600

# Verify resolution
dig CNAME www.example.com @ns1.alidns.com
```

**Delegation**:
- `alicloud-slb-ops`: SLB instance creation and health check configuration
- `alicloud-alb-ops`: ALB instance creation and rule management
- `alicloud-dns-ops`: DNS record management and validation

### 2. DNS + CDN Integration

**Use Case**: Configure domain for CDN acceleration

**Pattern**:
1. Create CDN domain → get CDN CNAME (e.g., `example.com.kunlun.com`)
2. Add CNAME record in DNS → point to CDN CNAME
3. Configure CDN origin → set origin server address
4. Verify CDN caching → test content delivery

**Example**:
```bash
# Add CDN CNAME record
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "static" \
  --Type "CNAME" \
  --Value "static.example.com.kunlun.com" \
  --TTL 600

# Verify CDN resolution
dig CNAME static.example.com @ns1.alidns.com
```

**Delegation**:
- CDN product: CDN domain creation and origin configuration
- `alicloud-dns-ops`: DNS CNAME record management
- `alicloud-ecs-ops`: Origin server management (if needed)

### 3. DNS + VPC/PrivateZone Integration

**Use Case**: Internal DNS resolution for VPC environments

**Pattern**:
1. Create PrivateZone → define internal domain
2. Add internal records → A/CNAME records for services
3. Bind to VPC → associate PrivateZone with VPC
4. Test internal resolution → verify VPC instances can resolve

**Example**:
```bash
# Create PrivateZone
ZONE_ID=$(aliyun pvtz CreateZone --ZoneName "internal.example.com" | jq -r '.ZoneId')

# Add internal record
aliyun pvtz AddZoneRecord \
  --ZoneId "$ZONE_ID" \
  --Rr "api" \
  --Type "A" \
  --Value "10.0.0.1"

# Bind to VPC
aliyun pvtz BindZoneVpc \
  --ZoneId "$ZONE_ID" \
  --Vpcs '[{"VpcId":"vpc_123","RegionId":"cn-hangzhou"}]'

# Test from VPC instance
nslookup api.internal.example.com 100.100.2.136
```

**Delegation**:
- `alicloud-vpc-ops`: VPC creation and network configuration
- `alicloud-dns-ops`: PrivateZone management and VPC binding
- `alicloud-ecs-ops`: VPC instance management

### 4. DNS + ECS Integration

**Use Case**: Direct domain resolution to ECS instances

**Pattern**:
1. Create ECS instance → get public/private IP
2. Add A/AAAA record → point to ECS IP
3. Verify resolution → ensure ECS is reachable
4. Configure security groups → allow traffic

**Example**:
```bash
# Get ECS public IP
ECS_IP=$(aliyun ecs DescribeInstances --InstanceIds '["i-12345678"]' | jq -r '.Instances.Instance[0].PublicIpAddress.IpAddress[0]')

# Add A record
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "app" \
  --Type "A" \
  --Value "$ECS_IP" \
  --TTL 600

# Verify resolution
dig A app.example.com @ns1.alidns.com
```

**Delegation**:
- `alicloud-ecs-ops`: ECS instance creation and management
- `alicloud-dns-ops`: DNS record management
- `alicloud-vpc-ops`: Network and security group configuration

### 5. DNS + WAF Integration

**Use Case**: Web application firewall protection for domains

**Pattern**:
1. Configure WAF protection → set domain in WAF
2. Add CNAME record → point to WAF CNAME
3. Verify WAF protection → test malicious request blocking
4. Monitor WAF logs → review blocked requests

**Example**:
```bash
# Add WAF CNAME record
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "CNAME" \
  --Value "example.com.waf.aliyuncs.com" \
  --TTL 600

# Verify WAF protection
curl -I https://www.example.com/sql-injection-test
```

**Delegation**:
- `alicloud-waf-ops`: WAF protection configuration
- `alicloud-dns-ops`: DNS CNAME record management
- `alicloud-actiontrail-ops`: WAF operation audit

## Cross-Skill Delegation Table

| Skill | Capability | Delegation Pattern |
|-------|------------|-------------------|
| `alicloud-slb-ops` | Load Balancer Configuration | DNS CNAME → SLB DNS name |
| `alicloud-alb-ops` | Application Load Balancer | DNS CNAME → ALB DNS name |
| `alicloud-ecs-ops` | Compute Instance Management | DNS A/AAAA → ECS IP |
| `alicloud-vpc-ops` | Network & PrivateZone | PrivateZone VPC binding |
| `alicloud-cdn-ops` | Content Delivery | DNS CNAME → CDN CNAME |
| `alicloud-waf-ops` | Web Application Firewall | DNS CNAME → WAF CNAME |
| `alicloud-actiontrail-ops` | Audit & Compliance | DNS operation audit trail |
| `alicloud-cms-ops` | Monitoring & Alerting | DNS health check monitoring |
| `alicloud-ram-ops` | Access Control | DNS permission management |

## Integration Workflows

### Workflow 1: New Web Application Deployment

```
1. Create ECS instances → alicloud-ecs-ops
2. Configure SLB → alicloud-slb-ops
3. Add DNS records → alicloud-dns-ops
4. Enable CDN → CDN product
5. Configure WAF → alicloud-waf-ops
6. Set up monitoring → alicloud-cms-ops
7. Verify end-to-end → all skills
```

### Workflow 2: Internal Service Migration

```
1. Create PrivateZone → alicloud-dns-ops
2. Add internal records → alicloud-dns-ops
3. Bind to VPC → alicloud-dns-ops
4. Update ECS instances → alicloud-ecs-ops
5. Test internal resolution → alicloud-dns-ops
6. Update external records → alicloud-dns-ops
7. Monitor traffic → alicloud-cms-ops
```

### Workflow 3: Disaster Recovery with GTM

```
1. Configure primary region → alicloud-ecs-ops
2. Configure DR region → alicloud-ecs-ops
3. Set up GTM pools → alicloud-dns-ops
4. Configure health checks → alicloud-dns-ops
5. Test failover → alicloud-dns-ops
6. Monitor health status → alicloud-cms-ops
7. Document runbook → documentation
```

## Best Practices

### 1. DNS Record Naming

- Use consistent naming conventions: `app`, `static`, `api`, `mail`
- Document all DNS records in central repository
- Use tags for environment identification: `prod-`, `dev-`, `staging-`

### 2. TTL Management

- Production records: 300-600 seconds
- Development records: 60-120 seconds
- Emergency changes: Reduce TTL before changes, restore after

### 3. Health Check Configuration

- Enable health checks for all critical endpoints
- Set appropriate intervals: 60-300 seconds
- Configure multiple failure thresholds
- Use HTTPS health checks when possible

### 4. GTM Best Practices

- Define clear failover conditions
- Test failover regularly (monthly)
- Monitor health check results continuously
- Document recovery procedures

### 5. Security Considerations

- Enable DNSSEC for production domains
- Use PrivateZone for internal DNS
- Audit all DNS changes via ActionTrail
- Implement least-privilege RAM policies

## Troubleshooting Integration Issues

### Common Issues

| Issue | Likely Cause | Resolution |
|-------|--------------|------------|
| DNS not resolving | NS not propagated | Wait for TTL, verify NS records |
| CNAME conflict | Existing A/AAAA record | Remove conflicting record |
| Health check failing | Backend server down | Check ECS/SLB health |
| GTM not failing over | Health check misconfigured | Verify health check endpoint |
| PrivateZone not working | VPC not bound | Bind PrivateZone to VPC |

### Diagnostic Commands

```bash
# Test DNS resolution
dig A www.example.com @ns1.alidns.com

# Check DNS propagation
dig A www.example.com @8.8.8.8

# Verify health check status
aliyun alidns DescribeGtmInstanceStatus --InstanceId "gtm_123"

# Check GTM address pool
aliyun alidns DescribeGtmAddressPool --PoolId "pool_123"

# Test PrivateZone resolution
nslookup api.internal.example.com 100.100.2.136
```