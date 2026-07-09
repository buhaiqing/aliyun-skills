# Well-Architected Assessment — Alibaba Cloud Voice Service

This document evaluates the Voice skill's operations against Alibaba Cloud's
[Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).

## 安全 (Security)

### Identity & Access Management

| Requirement | Guidance |
|-------------|----------|
| **RAM Policy** | Use scoped permissions: `acs:dyvmsapi:*:*:sms/*`. Avoid wildcard `*` actions. |
| **Least Privilege** | Create dedicated RAM users/roles with minimum required permissions. Never use `AdministratorAccess`. |
| **STS Tokens** | Use `AssumeRole` for temporary access with 1-hour expiry for automation. |
| **AccessKey Rotation** | Rotate AccessKeys every 90 days. Use `DisableAccessKey` to revoke compromised keys. |

### Network Security

- All API calls use HTTPS — verify endpoint scheme is `https://`
- Prefer VPC endpoints over public endpoints for API calls
- When using JIT Go SDK: ensure VPC NAT or egress rules allow outbound HTTPS (443)

### Data Protection

- Phone numbers may contain PII — mask in user-facing output
- Template parameters may contain sensitive data — mask in logs
- Log output: NEVER include credential values, use `***` masking

## 稳定 (Stability)

### Failure-Oriented Design

- All operations follow Pre-flight → Execute → Validate → Recover pattern
- Document idempotent behavior for retry scenarios (OutId prevents duplicates)
- Identify failure domains and blast radius

### Rate Limiting

- Per-signature: 1 Voice per 100ms
- Per-account: Check daily/monthly limits
- Backoff strategy: Exponential backoff on `isv.BUSINESS_LIMIT_CONTROL`

### Recovery Objectives

| Metric | Target | Measurement |
|--------|--------|-------------|
| RTO | < 5 minutes | Time to resume sending |
| RPO | 0 (idempotent) | No data loss with OutId tracking |

## 成本 (Cost)

### Billing Model Selection

| Billing Type | Best Use Case | Savings |
|-------------|---------------|---------|
| Pay-per-Voice | Low volume, variable | N/A |
| Voice Package | High volume, predictable | Up to 30% |
| Monthly subscription | Steady state | Up to 20% |

### Cost Optimization

- Monitor delivery rates; optimize templates to reduce rejections
- Use batch sending for >5 messages
- Track per-template cost via QuerySendStatistics
- Set daily/monthly budget alerts

## 效率 (Efficiency)

### Automation

- Use batch APIs for operations on ≥ 3 numbers
- Document concurrency limits (SendBatchSms: 1 batch/second)
- Integrate with CI/CD pipelines for automated sending

### Operational Integration

- Map skill errors to CMS alarm rules
- Document escalation paths
- Maintain change history via ActionTrail

## 性能 (Performance)

### Key Metrics

| Metric | Namespace | Optimization Action |
|--------|-----------|---------------------|
| DeliveryRate | acs_alicloud_dyvmsapi | Optimize templates, fix phone numbers |
| SendSpeed | acs_alicloud_dyvmsapi | Adjust rate limits |
| DailyUsage | acs_alicloud_dyvmsapi | Scale packages, monitor quota |

### Rate Management

- Per-signature: 1 Voice per 100ms
- Per-account: Check daily/monthly limits
- Backoff: Exponential on rate limit errors
- Pre-warming: Provision capacity before campaigns

---

*This assessment follows the Well-Architected Framework five pillars: Security, Stability, Cost, Efficiency, Performance.*
