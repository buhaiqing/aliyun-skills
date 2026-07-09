# Well-Architected Assessment — Alibaba Cloud GCL Runner

This document evaluates the GCL Runner skill's operations against Alibaba Cloud's
[Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).

## 安全 (Security)

### Identity & Access Management

| Requirement | Guidance |
|-------------|----------|
| **RAM Policy** | Use scoped permissions: `acs:gcl runner:*:*:trace/rubric/*`. Avoid wildcard `*` actions. |
| **Least Privilege** | Create dedicated RAM users/roles with minimum required permissions. Never use `AdministratorAccess`. |
| **STS Tokens** | Use `AssumeRole` for temporary access with 1-hour expiry for automation. |
| **AccessKey Rotation** | Rotate AccessKeys every 90 days. Use `DisableAccessKey` to revoke compromised keys. |

### Network Security

- Secret Masking
- Trace Sanitization
- No External Calls

### Data Protection

- Enable encryption at rest for sensitive data
- Use HTTPS endpoints for all API calls
- Enable audit logging for compliance

## 稳定 (Stability)

### Failure-Oriented Design

- All operations follow Pre-flight → Execute → Validate → Recover pattern
- Document idempotent behavior for retry scenarios
- Identify failure domains and blast radius

### Backup & Recovery

- Trace Archive
- Rubric Version Control

### Recovery Objectives

| Metric | Target | Measurement |
|--------|--------|-------------|
| RTO | < 4 hours | Time to restore service |
| RPO | < 1 hour | Data loss window |

## 成本 (Cost)

### Billing Model Selection

| Billing Type | Best Use Case | Savings |
|-------------|---------------|---------|
| Free (Local Execution) | All workloads | N/A |

### Cost Optimization

- Monitor resource utilization and right-size
- Use Reserved Instances for predictable workloads
- Enable auto-decommission for temporary resources

## 效率 (Efficiency)

### Automation

- Use batch APIs for operations on ≥ 3 resources
- Document concurrency limits
- Integrate with CI/CD pipelines

### Operational Integration

- Map skill errors to CMS alarm rules
- Document escalation paths
- Maintain change history via ActionTrail

## 性能 (Performance)

### Key Metrics

| Metric | Namespace | Optimization Action |
|--------|-----------|---------------------|
| PassRate | acs_alicloud_gcl_runner | Threshold |
| ExecutionTime | acs_alicloud_gcl_runner | Threshold |
| IterationCount | acs_alicloud_gcl_runner | Threshold |

### Scaling Patterns

- Horizontal scaling: add/remove instances
- Vertical scaling: modify instance specifications
- Auto-scaling: configure thresholds based on metrics

---

*This assessment follows the Well-Architected Framework five pillars: Security, Stability, Cost, Efficiency, Performance.*
