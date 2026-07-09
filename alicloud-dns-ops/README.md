# Alibaba Cloud DNS Operations Skill

> **Version**: 1.0.0 | **Last Updated**: 2026-07-03 | **Status**: Production Ready

## Overview

`alicloud-dns-ops` is a comprehensive DNS operations skill for Alibaba Cloud,
covering public authoritative DNS, PrivateZone internal DNS, Global Traffic
Manager (GTM), DNSSEC, and DNS security/compliance.

This skill is designed for AI agents and human operators to manage DNS
infrastructure with enterprise-grade safety, observability, and self-repair
capabilities.

## Key Features

### Core Capabilities

- **Public Authoritative DNS** — Domain management, record CRUD, line-based routing
- **PrivateZone** — Internal DNS for VPC environments, VPC binding, forwarding rules
- **GTM 3.0** — Global Traffic Manager with health checks and disaster recovery
- **DNSSEC** — Domain Name System Security Extensions
- **Query Analytics** — DNS query logs, statistics, and real-time monitoring

### Enterprise Features

- **Self-Repair** — Automatic input validation, conflict detection, error recovery
- **Observability** — Integration with Runtime Harness, Langfuse, and Prometheus
- **Safety** — Pre-flight checks, destructive operation confirmation, rollback support
- **Compliance** — Audit logging, change management, security best practices

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DNS Operations Architecture                   │
├─────────────────────────────────────────────────────────────────┤
│  AI Agent / Human Operator                                      │
│         ↓                                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  alicloud-dns-ops Skill                                  │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │  │
│  │  │   SKILL.md  │  │ references/ │  │  scripts/   │     │  │
│  │  │  (What)     │  │   (How)     │  │ (Wrapper)   │     │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │  │
│  └──────────────────────────────────────────────────────────┘  │
│         ↓                                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SkillOpt Core Library                                   │  │
│  │  • Input Validation    • Conflict Detection              │  │
│  │  • Error Recovery      • Observability                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│         ↓                                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Alibaba Cloud DNS APIs                                  │  │
│  │  • Alidns (Public DNS)    • Pvtz (PrivateZone)          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Alibaba Cloud CLI (`aliyun`) installed
- Valid API credentials configured
- Network access to Alibaba Cloud endpoints

### Basic Usage

```bash
# Add a domain to DNS service
./scripts/dns-skillopt-wrapper.sh alidns AddDomain --DomainName "example.com"

# Add an A record
./scripts/dns-skillopt-wrapper.sh alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "A" \
  --Value "1.2.3.4" \
  --TTL 600

# Add a CNAME record
./scripts/dns-skillopt-wrapper.sh alidns AddRecord \
  --DomainName "example.com" \
  --RR "app" \
  --Type "CNAME" \
  --Value "example.slb.aliyuncs.com" \
  --TTL 300

# Create a PrivateZone
./scripts/dns-skillopt-wrapper.sh pvtz CreateZone \
  --ZoneName "internal.example.com" \
  --Remark "Internal DNS zone"

# Add internal DNS record
./scripts/dns-skillopt-wrapper.sh pvtz AddZoneRecord \
  --ZoneId "zone_123" \
  --Rr "api" \
  --Type "A" \
  --Value "10.0.0.1"
```

### Health Check

```bash
# Verify wrapper and dependencies
./scripts/dns-skillopt-wrapper.sh health
```

## Skill Structure

```
alicloud-dns-ops/
├── SKILL.md                    # Main skill documentation
├── README.md                   # This file
├── TODO.md                     # Development roadmap
├── references/
│   ├── cli-usage.md           # CLI command reference
│   ├── core-concepts.md       # DNS architecture and concepts
│   ├── dns-safety.md          # Safety guidelines and validation
│   ├── integration.md         # Cross-skill integration patterns
│   ├── prompt-templates.md    # GCL prompt templates
│   ├── rubric.md              # Quality gates and validation rules
│   ├── skillopt-integration.md # SkillOpt integration guide
│   └── troubleshooting.md     # Common issues and solutions
├── scripts/
│   └── dns-skillopt-wrapper.sh # Self-repair wrapper script
└── assets/
    ├── eval_queries.json      # Evaluation queries for testing
    └── example-config.yaml    # Example configuration
```

## Supported Operations

### Public Authoritative DNS (Alidns)

| Category | Operations |
|----------|------------|
| **Domain Management** | Add, List, Get, Delete domains |
| **Record Management** | Add, List, Update, Delete, Enable, Disable records |
| **Line-Based Routing** | ISP lines, geographic routing, custom lines |
| **Weighted Routing** | Traffic distribution across multiple records |
| **Health Checks** | Active monitoring with automatic failover |
| **GTM** | Address pools, health checks, failover |
| **DNSSEC** | Enable, Disable, Status |
| **Analytics** | Query logs, statistics, real-time monitoring |

### Private DNS (PrivateZone)

| Category | Operations |
|----------|------------|
| **Zone Management** | Create, List, Get, Delete PrivateZones |
| **Record Management** | Add, List, Update, Delete internal records |
| **VPC Binding** | Bind, Unbind PrivateZones to VPCs |
| **Forwarding Rules** | Cross-VPC and hybrid cloud DNS resolution |

## Integration Patterns

### With SLB/ALB

```bash
# Configure DNS CNAME to load balancer
./scripts/dns-skillopt-wrapper.sh alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "CNAME" \
  --Value "example.slb.aliyuncs.com" \
  --TTL 300
```

### With CDN

```bash
# Configure DNS CNAME to CDN
./scripts/dns-skillopt-wrapper.sh alidns AddRecord \
  --DomainName "example.com" \
  --RR "static" \
  --Type "CNAME" \
  --Value "static.example.com.kunlun.com" \
  --TTL 300
```

### With VPC/PrivateZone

```bash
# Create internal DNS zone
ZONE_ID=$(./scripts/dns-skillopt-wrapper.sh pvtz CreateZone \
  --ZoneName "internal.example.com" | jq -r '.ZoneId')

# Add internal record
./scripts/dns-skillopt-wrapper.sh pvtz AddZoneRecord \
  --ZoneId "$ZONE_ID" \
  --Rr "api" \
  --Type "A" \
  --Value "10.0.0.1"

# Bind to VPC
./scripts/dns-skillopt-wrapper.sh pvtz BindZoneVpc \
  --ZoneId "$ZONE_ID" \
  --Vpcs '[{"VpcId":"vpc_123","RegionId":"cn-hangzhou"}]'
```

## Safety Features

### Pre-flight Checks

- Domain ownership verification
- NS record validation
- Record conflict detection
- Permission validation
- TTL and weight validation

### Destructive Operation Protection

- Domain deletion requires confirmation
- Record deletion requires confirmation
- GTM failover requires confirmation
- All changes logged in ActionTrail

### Rollback Support

- Automatic backup before changes
- Rollback procedures documented
- Recovery commands provided

## Observability

### Runtime Harness Integration

```bash
# Enable harness tracing
export HARNESS_ENABLED=true
export HARNESS_SKILL_TAG="alicloud-dns-ops"

# Execute with tracing
./scripts/dns-skillopt-wrapper.sh alidns AddRecord ...
```

### Langfuse Integration

```bash
# Enable Langfuse tracing
export LANGFUSE_ENABLED=true
export LANGFUSE_PUBLIC_KEY="pk-..."
export LANGFUSE_SECRET_KEY="sk-..."

# Execute with tracing
./scripts/dns-skillopt-wrapper.sh alidns AddRecord ...
```

### Prometheus Metrics

```bash
# View DNS operations metrics
curl http://localhost:9090/metrics | grep dns_
```

## Testing

### Backward Compatibility Tests

```bash
# Run backward compatibility tests
./scripts/test-skillopt-backward-compatibility.sh alicloud-dns-ops
```

### Integration Tests

```bash
# Test with GCL Runner
./scripts/test-gcl-integration.sh alicloud-dns-ops

# Test with Runtime Harness
./scripts/test-harness-integration.sh alicloud-dns-ops

# Test with Langfuse
./scripts/test-multi-skill-session.sh --skills "alicloud-dns-ops"
```

### Unit Tests

```bash
# Test input validation
./scripts/dns-skillopt-wrapper.sh alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "INVALID" \
  --Value "invalid"

# Expected: Input validation error
```

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Wrapper not found | Script not executable | `chmod +x scripts/dns-skillopt-wrapper.sh` |
| Core library not found | Path incorrect | Check `SKILLOPT_CORE_LIB` path |
| Validation failing | Invalid input | Check record format, TTL, weight |
| Conflict detected | Existing records | Remove conflicting records first |
| Permission denied | RAM policy missing | Request DNS permissions |

### Debug Mode

```bash
# Enable debug mode
export SKILLOPT_DEBUG=true

# Run with debug output
./scripts/dns-skillopt-wrapper.sh alidns AddRecord ...
```

### Logs

```bash
# View wrapper logs
tail -f .runtime/logs/dns-ops/wrapper.log

# View validation logs
tail -f .runtime/logs/dns-ops/validation.log

# View error logs
tail -f .runtime/logs/dns-ops/error.log
```

## Performance Benchmarks

| Operation | Target Latency | Acceptable Range |
|-----------|---------------|------------------|
| Add Record | < 1000ms | < 3000ms |
| Update Record | < 1000ms | < 3000ms |
| Delete Record | < 1000ms | < 3000ms |
| DNS Resolution | < 100ms | < 500ms |
| Propagation | < 300s | < 3600s |
| GTM Failover | < 60s | < 300s |

## Security Requirements

### Access Control

- RAM least-privilege policies
- MFA for DNS management accounts
- ActionTrail audit logging
- Change approval workflow

### Data Protection

- Credential masking in outputs
- Encrypted configuration data
- Secure backup storage
- Regular security audits

### Compliance

- 90-day audit trail retention
- Monthly DNS configuration review
- Quarterly security audit
- Annual compliance assessment

## Contributing

### Development Workflow

1. Create feature branch
2. Implement changes
3. Run tests (`./scripts/test-skillopt-backward-compatibility.sh alicloud-dns-ops`)
4. Update documentation
5. Submit pull request

### Code Standards

- Follow existing code style
- Add tests for new functionality
- Update documentation
- Pass all quality gates

## License

MIT License - see [LICENSE](../LICENSE) for details.

## Support

- **Documentation**: See `references/` directory
- **Issues**: Report at [GitHub Issues](https://github.com/your-org/aliyun-skills/issues)
- **Contact**: SRE Team