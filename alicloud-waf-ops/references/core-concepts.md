# Core Concepts — Alibaba Cloud Web Application Firewall (WAF)

## Architecture Overview

Alibaba Cloud WAF 3.0 provides **Layer 7 (application layer)** protection for web applications. It acts as a reverse proxy, inspecting all HTTP/HTTPS traffic before forwarding legitimate requests to origin servers.

### Traffic Flow

```
Client → DNS (CNAME to WAF) → WAF Instance → Origin Server (ECS/SLB/ALB/OSS)
```

### Key Components

| Component | Description | Resource ID |
|-----------|-------------|-------------|
| **WAF Instance** | Central protection service | `InstanceId` (e.g., `waf_cdnsdf3****`) |
| **Protected Domain** | Website/domain under protection | `Domain` / `DomainId` |
| **Access Control Rules** | IP blacklist/whitelist | `RuleId` |
| **Defense Rules** | CC protection, Web core rules | `DefenseRuleId` |
| **Bot Management** | Malicious crawler detection | Configured per domain |
| **Threat Intelligence** | IP reputation feeds | Global, per instance |

## WAF Instance Types

| Edition | Features | Use Case |
|---------|----------|----------|
| **Personal (免费)** | Basic protection, limited rules | Small websites, testing |
| **Pro** | Full Web core rules, CC protection | Production web apps |
| **Enterprise** | Advanced bot management, threat intelligence | High-security applications |

## Domain Protection Model

### CNAME Configuration

After adding a domain to WAF:
1. WAF returns a CNAME (e.g., `waf123456.waf100001.com`)
2. User updates DNS: domain CNAME → WAF CNAME
3. All traffic flows through WAF before reaching origin

### Supported Origin Types

| Origin Type | Protocol | Notes |
|-------------|----------|-------|
| ECS IP | HTTP/HTTPS | Direct IP address |
| SLB | HTTP/HTTPS | Load balancer VIP |
| ALB | HTTP/HTTPS | Application Load Balancer |
| OSS Bucket | HTTPS | Object Storage for static sites |
| Custom IP | HTTP/HTTPS | Third-party server |

### Port Configuration

| Protocol | Default Ports | Custom Ports |
|----------|--------------|--------------|
| HTTP | 80 | 1-65535 |
| HTTPS | 443 | 1-65535 |

## Protection Layers

### Layer 1: Access Control (IP-based)

- **IP Blacklist:** Block specific IPs/CIDRs
- **IP Whitelist:** Bypass protection for trusted sources
- **Geo-blocking:** Block/allow by country/region

### Layer 2: CC Protection (Rate Limiting)

- **Request rate limiting:** Max requests per second/minute
- **Unique visitor limiting:** Max unique IPs per interval
- **Challenge-response:** CAPTCHA/js-challenge for suspicious traffic

### Layer 3: Web Core Protection (OWASP Top 10)

| Threat | Detection Method | Action |
|--------|-----------------|--------|
| SQL Injection | Signature matching | Block/Alert |
| XSS | Pattern analysis | Block/Alert |
| Command Injection | Keyword detection | Block/Alert |
| Path Traversal | URL normalization | Block/Alert |
| File Inclusion | Request analysis | Block/Alert |

### Layer 4: Bot Management

- **Malicious bot detection:** Behavioral analysis
- **Crawler management:** Legitimate vs malicious crawlers
- **API protection:** Rate limiting for API endpoints

## Region and Endpoint Information

| Region | Endpoint | Notes |
|--------|----------|-------|
| cn-hangzhou | waf-openapi.cn-hangzhou.aliyuncs.com | Mainland China |
| cn-shanghai | waf-openapi.cn-shanghai.aliyuncs.com | Mainland China |
| cn-beijing | waf-openapi.cn-beijing.aliyuncs.com | Mainland China |
| ap-southeast-1 | waf-openapi.ap-southeast-1.aliyuncs.com | Singapore |

## Resource Quotas

| Resource | Default Quota | Upgrade |
|----------|--------------|---------|
| Protected Domains | 50 | Contact sales |
| Access Control Rules | 200 | Upgrade edition |
| CC Defense Rules | 100 | Upgrade edition |
| Whitelist IPs | 100 | Upgrade edition |
| Blacklist IPs | 1000 | Upgrade edition |

> Use `DescribeInstanceInfo` to query current quota limits.

## WAF vs DDoS Protection

| Aspect | WAF (Layer 7) | DDoS (Layer 3/4) |
|--------|--------------|------------------|
| Protection | SQL injection, XSS, CC attacks | Volumetric attacks, SYN flood |
| Traffic | HTTP/HTTPS inspection | IP/protocol level |
| Origin | Web applications | Network infrastructure |
| Product | WAF (this skill) | DDoS Protection (separate skill) |

## Integration Points

| Service | Integration | Use Case |
|---------|-------------|----------|
| **SLB** | WAF sits in front of SLB | Web app protection |
| **ALB** | WAF protects ALB endpoints | Modern application architectures |
| **ECS** | Origin server hosting | Direct ECS origin |
| **OSS** | Static website protection | Static site + WAF |
| **CDN** | CDN + WAF layered defense | Content delivery + security |
| **SLS** | Log collection | Security audit, analysis |
| **ActionTrail** | API audit trail | Compliance, forensics |

## Security Best Practices

1. **Enable HTTPS:** Always use HTTPS listeners for encrypted traffic
2. **Regular rule review:** Audit ACL/defense rules quarterly
3. **Log collection:** Enable SLS log collection for all protected domains
4. **IP reputation:** Use threat intelligence for dynamic IP blocking
5. **Least privilege:** RAM policy should only grant required WAF actions
