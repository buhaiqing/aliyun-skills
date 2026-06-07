# Core Concepts — Alibaba Cloud ALB (Application Load Balancer)

> Version: 1.0.0 | Last Updated: 2026-06-07

## What is ALB?

Application Load Balancer (ALB) is Alibaba Cloud's Layer 7 (HTTP/HTTPS/QUIC) load balancing service. It distributes traffic to backend servers with advanced routing based on request content (host, path, header, query string, cookie, source IP).

## Product Variants Comparison

| Variant | API Version | Layer | Protocols | Use Case |
|---------|-------------|-------|-----------|----------|
| **ALB** (Application Load Balancer) | ALB 2020-06-16 | L7 | HTTP, HTTPS, QUIC, gRPC | Advanced HTTP/HTTPS routing |
| **CLB** (Classic Load Balancer / SLB) | SLB 2014-05-15 | L4/L7 | TCP, UDP, HTTP, HTTPS | Traditional load balancing |
| **NLB** (Network Load Balancer) | NLB 2022-04-30 | L4 | TCP, UDP, TCPSSL | Ultra-low latency |

> This skill covers **ALB only**. For CLB, use `alicloud-slb-ops`. For NLB, use a separate NLB skill when available.

## Key Concepts

### Load Balancer Instance

The core resource that receives and distributes traffic:

- **LoadBalancerId**: Unique identifier (e.g., `alb-bp67acfmxazb4ph***`)
- **Address**: Assigned IP address
- **AddressType**: `Internet` (public) or `Intranet` (private)
- **DNSName**: Auto-generated DNS entry
- **Status**: `Active`, `Inactive`, `Provisioning`, `Configuring`
- **Edition**: `Basic` (Basic), `Standard` (Standard), `StandardWithWaf` (Standard with WAF)
- **NetworkType**: `VPC` only (no classic network support)
- **DeletionProtectionEnabled**: `true` / `false`
- **ModificationProtectionStatus**: `ConsoleProtection` / `NonProtection`

### Editions

| Edition | Features | Max Listeners | Max Server Groups | Use Case |
|---------|----------|:-------------:|:-----------------:|----------|
| Basic | Basic HTTP/HTTPS routing | 50 | 50 | Small-scale applications |
| Standard | Full ALB features, gRPC, QUIC | 100 | 100 | Production workloads |
| StandardWithWaf | All Standard + integrated WAF | 100 | 100 | Security-sensitive apps |

### Listener

A listener checks for connection requests using a configured **protocol** and **port**:

- **Protocol**: `HTTP`, `HTTPS`, `QUIC`
- **ListenerPort**: Frontend port (1-65535)
- **Default actions**: Default forwarding rule (ForwardGroup, Redirect, etc.)
- **Certificate**: For HTTPS/QUIC listeners (server certificate)
- **SecurityPolicyId**: For HTTPS listeners (TLS version + cipher suites)

### Server Group

A logical group of backend servers serving the same application:

- **Protocol**: `HTTP`, `HTTPS`, `gRPC`
- **Scheduler**: `Wrr` (Weighted Round Robin), `Wlc` (Weighted Least Connections), `Sch` (Consistent Hash)
- **HealthCheck**: Configurable via health check templates or embedded config
- **Persistence**: Session persistence via Client IP, Cookie, or AppCookie
- **ConnectionDrain**: Graceful connection draining on server removal

### Forwarding Rule

Determines traffic distribution based on conditions:

- **Conditions**: Host, Path, Header, Query String, Cookie, Source IP, Method, Response Status Code
- **Actions**: ForwardGroup, Redirect, FixedResponse, Rewrite, InsertHeader, RemoveHeader, TrafficLimit, TrafficMirror
- **Priority**: Integer, lower = higher priority (1-10000)
- **Status**: Active / Inactive

### ACL (Access Control List)

IP-based access control for listeners:

- **ACL Type**: `Black` (deny listed IPs) or `White` (allow listed IPs only)
- **Entry**: CIDR block (IPv4 or IPv6)
- **Associable**: Can be applied to multiple listeners

### Security Policy

TLS/SSL configuration for HTTPS listeners:

- **TLSVersion**: `TLSv1.0`, `TLSv1.1`, `TLSv1.2`, `TLSv1.3`
- **Ciphers**: Selectable cipher suites
- **System policies**: `SystemSecurityPolicy`, `SystemSecurityPolicy-2020`, etc.
- **Custom policies**: User-defined TLS + cipher combinations

### Health Check Template

Reusable health check configuration:

- **Protocol**: `HTTP`, `HTTPS`, `TCP`, `gRPC`
- **Path**: Health check URL path (for HTTP/HTTPS)
- **Interval**: 1-120s, default 2s
- **Timeout**: 1-120s, default 5s
- **HealthyThreshold**: 2-10, default 3
- **UnhealthyThreshold**: 2-10, default 3
- **HttpCode**: e.g., `http_2xx`, `http_3xx`

## Key Resource Relationships

```
ALB Instance
├── Zone Mapping (1..N zones, each with VSwitch)
├── Security Group (0..N)
├── Bandwidth Package (0..1, internet type only)
├── Listener (0..N)
│   ├── Default Forwarding Rule → Server Group
│   ├── Additional Forwarding Rules (0..N)
│   ├── ACL (0..2: Black + White list)
│   ├── Additional Certificates (0..N, SNI)
│   └── Security Policy (HTTPS only)
├── Server Group (0..N)
│   ├── Backend Servers (ECS/ENI/ECI/IP/Functions)
│   ├── Health Check Template
│   └── Connection Pool Config
└── Access Log (0..1, SLS project)
```

## Regions and Zones

ALB is available in most Alibaba Cloud regions. Use `DescribeRegions` and `DescribeZones` to query available regions and zones.

## Quotas and Limits

| Resource | Default Quota | Can Increase |
|----------|:-------------:|:------------:|
| ALB instances per region | 10 | Yes |
| Listeners per ALB | 50 (Basic) / 100 (Standard+) | Yes |
| Server groups per ALB | 50 (Basic) / 100 (Standard+) | Yes |
| Servers per server group | 200 | Yes |
| Forwarding rules per listener | 100 (Basic) / 200 (Standard+) | Yes |
| Certificates per listener | 10 | Yes |
| ACLs per region | 100 | Yes |
| Entries per ACL | 500 | Yes |
| Security policies per region | 20 | No |
| Health check templates per region | 100 | Yes |

> Use `DescribeZones` and `ListLoadBalancers` to check current usage. Quota limits can be raised by submitting a ticket to Alibaba Cloud support.

## Billing

| Mode | Description |
|------|-------------|
| Pay-as-you-go | Per-hour billing based on ALB instance units (LCU) |
| Subscription | Monthly/yearly prepaid, no longer available for new purchases (2024-12-01) |

**LCU (Load Capacity Unit):** ALB is billed based on LCU consumption. Each LCU includes:
- 25 new connections per second
- 3,000 active connections per minute
- 1 GB of data transfer per hour
- 1,000 rule evaluations per second