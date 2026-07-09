# Alibaba Cloud DNS Core Concepts

## Overview

Alibaba Cloud DNS provides authoritative domain name resolution services with
enterprise-grade features. This document covers the core concepts, architecture,
and best practices for DNS operations.

## DNS Architecture

### Public Authoritative DNS (Alidns)

```
┌─────────────────────────────────────────────────────────┐
│                    DNS Resolution Flow                   │
├─────────────────────────────────────────────────────────┤
│  User Query → Recursive Resolver → Alibaba Cloud DNS   │
│                    ↓                                    │
│              Authoritative Response                     │
│                    ↓                                    │
│              Client Application                         │
└─────────────────────────────────────────────────────────┘
```

**Key Components:**
- **Domain Management** — Add, verify, and manage domains
- **Record Management** — CRUD for DNS records (A, AAAA, CNAME, MX, TXT, NS, SRV, CAA)
- **Line-Based Routing** — ISP and geographic routing
- **Weighted Routing** — Traffic distribution across multiple records
- **Health Checks** — Active monitoring with automatic failover
- **GTM 3.0** — Global Traffic Manager with disaster recovery
- **DNSSEC** — Domain Name System Security Extensions
- **Query Analytics** — DNS query logs, statistics, and monitoring

### Private DNS (PrivateZone)

```
┌─────────────────────────────────────────────────────────┐
│                  PrivateZone Architecture                │
├─────────────────────────────────────────────────────────┤
│  VPC Instance → PrivateZone → Internal DNS Resolution   │
│                    ↓                                    │
│              Internal Services                          │
│                    ↓                                    │
│              VPC Peering (Optional)                     │
└─────────────────────────────────────────────────────────┘
```

**Key Components:**
- **PrivateZone Management** — Internal DNS zones for VPC environments
- **Record Management** — Internal DNS records within PrivateZone
- **VPC Binding** — Associate PrivateZones with VPC instances
- **Forwarding Rules** — Cross-VPC and hybrid cloud DNS resolution
- **Custom Lines** — ISP-based routing for internal DNS

## DNS Record Types

### Record Type Reference

| Record Type | Purpose | Format | Example |
|-------------|---------|--------|---------|
| **A** | Maps domain to IPv4 address | IPv4 address | `1.2.3.4` |
| **AAAA** | Maps domain to IPv6 address | IPv6 address | `2001:db8::1` |
| **CNAME** | Maps domain to another domain | Domain name | `example.com` |
| **MX** | Mail server for domain | Priority + domain | `10 mx.example.com` |
| **TXT** | Text information | Text string | `"v=spf1 ..."` |
| **NS** | Name server for domain | Name server | `ns1.example.com` |
| **SRV** | Service location | Priority + weight + port + target | `10 50 5060 sip.example.com` |
| **CAA** | Certificate authority | Flags + tag + value | `0 issue "letsencrypt.org"` |

### Record Conflict Rules

| Conflict Type | Rule | Resolution |
|---------------|------|------------|
| CNAME vs A/AAAA | Cannot coexist | Remove one type |
| CNAME vs MX | Cannot coexist | Remove one type |
| CNAME vs NS | Cannot coexist | Remove one type |
| A vs AAAA | Can coexist | Different IP versions |
| Multiple A records | Can coexist | Weighted or line-based routing |

## Line-Based Routing

### ISP Lines

| Line Name | Description | Use Case |
|-----------|-------------|----------|
| `default` | Default routing | General traffic |
| `telecom` | China Telecom | ISP-specific optimization |
| `unicom` | China Unicom | ISP-specific optimization |
| `mobile` | China Mobile | ISP-specific optimization |
| `oversea` | International | Geographic routing |

### Geographic Lines

| Line Name | Description | Use Case |
|-----------|-------------|----------|
| `asia` | Asia Pacific | Regional routing |
| `europe` | Europe | Regional routing |
| `namerica` | North America | Regional routing |
| `samerica` | South America | Regional routing |
| `africa` | Africa | Regional routing |
| `oceania` | Oceania | Regional routing |

## Weighted Routing

### Weight Configuration

| Weight Range | Description | Use Case |
|--------------|-------------|----------|
| 1-100 | Traffic distribution percentage | Load balancing |
| 70/30 | Primary/secondary split | Failover scenarios |
| 50/50 | Equal distribution | A/B testing |

### Weighted Routing Rules

1. **Total Weight** — Sum of all weights for a record set
2. **Traffic Distribution** — Each record receives proportional traffic
3. **Health Checks** — Failed health checks reduce effective weight
4. **Failover** — GTM can redirect traffic on health check failure

## Health Checks

### Health Check Types

| Type | Protocol | Use Case |
|------|----------|----------|
| HTTP | TCP/HTTP | Web applications |
| HTTPS | TCP/HTTPS | Secure web applications |
| TCP | TCP | Non-HTTP services |
| ICMP | ICMP | Network connectivity |

### Health Check Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| Interval | 60s | 10-300s | Time between checks |
| Threshold | 3 | 1-10 | Consecutive failures before failover |
| Timeout | 5s | 1-30s | Response timeout |
| Port | 80 | 1-65535 | Check port |
| Path | `/` | URL path | HTTP check path |

## GTM (Global Traffic Manager)

### GTM Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    GTM Architecture                      │
├─────────────────────────────────────────────────────────┤
│  User Query → GTM → Health Check → Address Pool         │
│                    ↓                                    │
│              Primary Pool (Active)                      │
│                    ↓                                    │
│              Backup Pool (Standby)                      │
└─────────────────────────────────────────────────────────┘
```

### GTM Components

| Component | Description | Configuration |
|-----------|-------------|---------------|
| Address Pool | Collection of endpoints | IP addresses, ports |
| Health Check | Monitor endpoint health | Type, interval, threshold |
| Failover Strategy | Automatic or manual | AUTO, MANUAL |
| Recovery Strategy | Restore primary | Threshold-based |

## DNSSEC

### DNSSEC Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    DNSSEC Architecture                   │
├─────────────────────────────────────────────────────────┤
│  DNS Query → DNSSEC Validation → Signed Response        │
│                    ↓                                    │
│              Key Signing Key (KSK)                      │
│                    ↓                                    │
│              Zone Signing Key (ZSK)                     │
└─────────────────────────────────────────────────────────┘
```

### DNSSEC Components

| Component | Description | Management |
|-----------|-------------|------------|
| KSK | Key Signing Key | Long-term, manual rotation |
| ZSK | Zone Signing Key | Short-term, automatic rotation |
| DS | Delegation Signer | Registrar configuration |
| RRSIG | Resource Record Signature | Automatic signing |
| NSEC/NSEC3 | Next Secure | Zone walking prevention |

## TTL (Time-to-Live)

### TTL Guidelines

| Environment | Recommended TTL | Acceptable Range |
|-------------|----------------|------------------|
| Production | 300-600s | 60-86400s |
| Development | 60-120s | 60-86400s |
| Emergency | 60s | 60-300s |

### TTL Best Practices

1. **Before Changes** — Reduce TTL to 60s
2. **After Changes** — Wait for old TTL to expire
3. **Restore TTL** — Increase to normal after propagation
4. **Monitoring** — Check propagation across DNS servers

## DNS Resolution Process

### Resolution Flow

```
1. User Query → Recursive Resolver
2. Recursive Resolver → Root DNS Server
3. Root Server → TLD DNS Server (.com, .cn, etc.)
4. TLD Server → Authoritative DNS Server (Alibaba Cloud)
5. Authoritative Server → Response
6. Recursive Resolver → Cache & Return to User
```

### Resolution Time Factors

| Factor | Impact | Optimization |
|--------|--------|--------------|
| TTL | Cache duration | Adjust based on change frequency |
| DNS Server | Geographic distance | Use nearest DNS server |
| Network | Latency | Optimize network path |
| Query Type | Complexity | Use appropriate record types |

## Best Practices

### Domain Management

1. **Documentation** — Document all DNS records and configurations
2. **Version Control** — Track DNS changes in version control
3. **Backup** — Regular backups of DNS configurations
4. **Monitoring** — Continuous monitoring of DNS health

### Record Management

1. **Naming Conventions** — Use consistent naming patterns
2. **TTL Strategy** — Balance between performance and flexibility
3. **Conflict Prevention** — Check for conflicts before changes
4. **Validation** — Verify records after changes

### Security

1. **DNSSEC** — Enable for all production domains
2. **Access Control** — Use RAM least-privilege policies
3. **Audit Logging** — Enable ActionTrail for DNS changes
4. **Regular Reviews** — Quarterly security audits

### Performance

1. **TTL Optimization** — Adjust based on change frequency
2. **Geographic Routing** — Use line-based routing for global services
3. **Health Checks** — Enable for all critical endpoints
4. **GTM** — Use for disaster recovery and load balancing

## Common Patterns

### Pattern 1: Web Application

```
www.example.com → CNAME → example.slb.aliyuncs.com
app.example.com → A → 1.2.3.4
static.example.com → CNAME → example.com.kunlun.com
```

### Pattern 2: Internal Services

```
api.internal.example.com → A → 10.0.0.1
db.internal.example.com → A → 10.0.0.2
cache.internal.example.com → A → 10.0.0.3
```

### Pattern 3: Disaster Recovery

```
Primary: www.example.com → A → 1.2.3.4 (weight 70)
Backup: www.example.com → A → 5.6.7.8 (weight 30)
GTM: Health checks with automatic failover
```

### Pattern 4: Multi-Region

```
Asia: www.example.com → A → 1.2.3.4 (line: asia)
Europe: www.example.com → A → 2.3.4.5 (line: europe)
Americas: www.example.com → A → 3.4.5.6 (line: namerica)
```