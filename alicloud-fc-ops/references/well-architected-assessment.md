# Well-Architected Assessment — FC 3.0

## 2.1 安全支柱 Security

### RAM Execution Role
- FC functions MUST use a dedicated RAM role (not account AccessKey)
- Minimum permissions principle: grant only required actions (e.g., `oss:GetObject` not `oss:*`)
- RAM policies MUST be attached to the execution role, NOT the caller

### Network Security
- Use VPC binding when accessing VPC resources (RDS, Redis)
- Configure security groups with egress rules (allow 443 for API calls)
- For public HTTP triggers, enable authentication

### Code Security
- Code package uploaded to SSE-S3 encrypted or CMK encrypted OSS bucket
- Function-level IAM prevents unauthorized invocation
- Environment variables with sensitive values should use KMS encryption

### Credential Rotation
- STS temporary credentials preferred over long-lived AccessKey
- Rotate execution role credentials per security policy

## 2.2 稳定支柱 Stability

### Provisioned Instances

| Pattern | Use Case | CLI Example |
|---------|----------|-------------|
| **Always-warm** | Latency-critical, consistent traffic | Set `target: 1` on alias `prod` |
| **Pre-warm before peak** | Predictable traffic spikes (business hours) | Set provisioned instances before peak window |
| **Graceful scale-down** | Off-peak cost reduction | Set `target: 0` during off-hours |

### Backup & Recovery

- Function code: stored in OSS (versioned bucket recommended); FC stores last N versions
- Config backup: use `GetFunction` to export config before destructive changes
- Cross-region DR: deploy identical function in backup region + traffic switch via SLB
- RTO: function invocation recovers in seconds (serverless, no infra provisioning)
- RPO: code changes can be redeployed in minutes

### Emergency Recovery

- **Phase 1: Backup Verification**: Confirm code package is accessible; verify execution role is valid
- **Phase 2: Recovery Execution**: `UpdateFunction` with code pointing to known-good OSS version
- **Phase 3: Post-Recovery Validation**: Invoke function with test payload; verify output

## 2.3 成本支柱 Cost

### Billing Model Comparison

| Billing Type | Unit | Best For |
|-------------|------|----------|
| **Invocation** | Per request | Low-traffic, sporadic workloads |
| **Resource (GB-s)** | Memory(GB) × Duration(s) | All workloads; optimize via memory tuning |
| **Provisioned** | Per instance-hour | Steady-state, latency-critical workloads |
| **Network** | Outbound data transfer | Functions returning large payloads |

### Memory Right-Sizing Optimization

FC pricing rule: **higher memory = more CPU = faster execution = potentially lower GB-s cost**

Memory → CPU mapping (Alibaba Cloud):
| Memory (MB) | vCPU |
|-------------|------|
| 128-409 | 0.01-0.3 |
| 512 | 0.33 |
| 1024 | 0.66 |
| 1536 | 1 |
| 2048 | 1.33 |
| 3072 | 2 |

**Optimization rule:** If a function at 512MB takes 10s (5.12 GB-s), try 1024MB (might take ~5s → 5.12 GB-s same cost but faster). For CPU-heavy, higher memory often reduces total GB-s.

### Idle Function Detection

| Indicator | Threshold | Action |
|-----------|-----------|--------|
| 0 invocations in 24h + provisioned instances | Any provisioned count | Remove provisioned config |
| < 100 invocations/month | Low traffic | Verify if function is still needed |
| High provisioned ratio | provisioned_invocations < total_invocations × 0.3 | Reduce provisioned instances |

## 2.4 效率支柱 Efficiency

### Batch Operations

- Use concurrent invocations when possible (stateless functions)
- For processing queues, use multiple function instances (concurrent execution)

### CI/CD Integration

- Code packages via OSS; trigger `UpdateFunction` with new code after deployment
- Use aliases for canary releases: deploy to `dev` → test → promote to `prod`
- Version pinning: `UpdateAlias` to change alias target version

### Tag-Based Operations

- Tag functions: `env:production`, `team:backend`, `version:1.0`
- Filter operations by tag for batch management

## 2.5 性能支柱 Performance

### Scaling Triggers

| Metric | Scale Up | Scale Down | Notes |
|--------|----------|------------|-------|
| Concurrent executions | > 80% of limit | < 30% for 5min | Auto-scales to account limit |
| Invocation duration | P99 approaching timeout | — | Indicates timeout risk |
| Memory utilization | > 85% sustained | — | OOM risk; increase memory |

### Performance Optimization

- **Cold start mitigation**: Use provisioned instances; increase memory; reduce package size
- **Concurrency optimization**: Set per-function limits to prevent noisy neighbor issues
- **Duration optimization**: Optimize code paths; use efficient runtimes; cache external calls
- **p99 target**: Set SLO for p99 duration; alert when exceeded
