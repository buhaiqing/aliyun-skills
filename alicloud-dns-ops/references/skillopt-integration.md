# DNS SkillOpt Integration Guide

## Overview

This document describes how `alicloud-dns-ops` integrates with the SkillOpt
self-repair framework and dynamic optimization system.

## SkillOpt Integration

### Wrapper Integration

The `alicloud-dns-ops` skill uses the standard SkillOpt wrapper pattern:

```bash
# Primary execution path
./scripts/dns-skillopt-wrapper.sh alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "A" \
  --Value "1.2.3.4" \
  --TTL 600

# Fallback to native CLI
aliyun alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "A" \
  --Value "1.2.3.4" \
  --TTL 600
```

### Self-Repair Features

| Feature | Description | Implementation |
|---------|-------------|----------------|
| **Input Validation** | Validates record format, TTL, weight before execution | `validate_dns_record()`, `validate_ttl()`, `validate_weight()` |
| **Conflict Detection** | Checks for CNAME/A/AAAA conflicts | `check_record_conflicts()` |
| **Domain Verification** | Verifies domain exists before operations | `check_domain_exists()` |
| **Error Recovery** | Automatic retry for transient errors | Exponential backoff in wrapper |
| **Rollback Support** | Automatic rollback on failure | Backup before change pattern |

### Dynamic Optimization

| Optimization | Description | Trigger |
|--------------|-------------|---------|
| **TTL Adjustment** | Automatically adjust TTL based on change frequency | High change frequency detected |
| **Batch Operations** | Group multiple record changes for efficiency | Multiple records changed |
| **Health Check Tuning** | Optimize health check intervals | Health check failures |
| **Line Routing Optimization** | Adjust routing based on traffic patterns | Traffic pattern changes |

## Integration Points

### With GCL Runner

The skill integrates with `alicloud-gcl-runner-ops` for adversarial review:

```bash
# GCL review for write operations
./scripts/gcl_runner.py \
  --skill "alicloud-dns-ops" \
  --operation "AddRecord" \
  --params '{"domain": "example.com", "rr": "www", "type": "A", "value": "1.2.3.4"}'
```

### With Runtime Harness

The skill integrates with `alicloud-runtime-harness-ops` for observability:

```bash
# Enable harness tracing
export HARNESS_ENABLED=true
export HARNESS_SKILL_TAG="alicloud-dns-ops"

# Execute with tracing
./scripts/dns-skillopt-wrapper.sh alidns AddRecord ...
```

### With Langfuse

The skill supports Langfuse tracing for session-level observability:

```bash
# Enable Langfuse tracing
export LANGFUSE_ENABLED=true
export LANGFUSE_PUBLIC_KEY="pk-..."
export LANGFUSE_SECRET_KEY="sk-..."

# Execute with tracing
./scripts/dns-skillopt-wrapper.sh alidns AddRecord ...
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SKILLOPT_ENABLED` | Enable SkillOpt features | `true` |
| `SKILLOPT_LOG_LABEL` | Log label for this skill | `DNS-SkillOpt` |
| `HARNESS_ENABLED` | Enable harness tracing | `false` |
| `LANGFUSE_ENABLED` | Enable Langfuse tracing | `false` |

### Skill-Specific Configuration

```yaml
# dns-skillopt-config.yaml
skill:
  name: alicloud-dns-ops
  version: "1.0.0"
  
validation:
  record_types: ["A", "AAAA", "CNAME", "MX", "TXT", "NS", "SRV", "CAA"]
  ttl_range: [60, 86400]
  weight_range: [1, 100]
  
self_repair:
  max_retries: 3
  retry_delay: 1000
  exponential_backoff: true
  
optimization:
  batch_size: 10
  ttl_adjustment: true
  health_check_tuning: true
```

## Testing

### Backward Compatibility Tests

```bash
# Run backward compatibility tests
./scripts/test-skillopt-backward-compatibility.sh alicloud-dns-ops
```

### Self-Repair Tests

```bash
# Test input validation
./scripts/dns-skillopt-wrapper.sh alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "INVALID" \
  --Value "invalid"

# Expected: Input validation error

# Test conflict detection
./scripts/dns-skillopt-wrapper.sh alidns AddRecord \
  --DomainName "example.com" \
  --RR "www" \
  --Type "CNAME" \
  --Value "example.com"

# Expected: Conflict detection error (if A record exists)
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

## Monitoring

### Metrics

| Metric | Description | Source |
|--------|-------------|--------|
| `dns_operations_total` | Total DNS operations | Wrapper |
| `dns_operations_success` | Successful operations | Wrapper |
| `dns_operations_failed` | Failed operations | Wrapper |
| `dns_validation_errors` | Validation errors | Wrapper |
| `dns_conflict_errors` | Conflict errors | Wrapper |
| `dns_retry_count` | Retry attempts | Wrapper |

### Dashboards

```bash
# View DNS operations dashboard
./scripts/harness-runtime.py dashboard --skill "alicloud-dns-ops"

# View metrics in Prometheus format
curl http://localhost:9090/metrics | grep dns_
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

## Best Practices

### 1. Always Use Wrapper

```bash
# Preferred
./scripts/dns-skillopt-wrapper.sh alidns AddRecord ...

# Not preferred (bypasses self-repair)
aliyun alidns AddRecord ...
```

### 2. Enable Tracing

```bash
export HARNESS_ENABLED=true
export LANGFUSE_ENABLED=true
```

### 3. Monitor Metrics

```bash
# Check operation metrics
curl http://localhost:9090/metrics | grep dns_operations

# Check error metrics
curl http://localhost:9090/metrics | grep dns_errors
```

### 4. Regular Testing

```bash
# Run tests regularly
./scripts/test-skillopt-backward-compatibility.sh alicloud-dns-ops
./scripts/test-gcl-integration.sh alicloud-dns-ops
```

### 5. Review Logs

```bash
# Review logs weekly
find .runtime/logs/dns-ops -name "*.log" -mtime -7 -exec tail -50 {} \;
```