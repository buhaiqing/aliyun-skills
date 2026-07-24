---
name: alicloud-cert-ops-well-architected
description: >-
  CAS Well-Architected Framework assessment: Security, Stability,
  Cost, Efficiency, Performance. Part of alicloud-cert-ops.
license: MIT
metadata:
  type: reference
  skill: alicloud-cert-ops
  version: "1.0.0"
  last_updated: "2026-06-25"
---

# Well-Architected Assessment — CAS

## Security

### IAM Permissions (Least Privilege)

| RAM Action | Resource | Minimum Scope |
|-----------|----------|--------------|
| cas:List* | * | Read-only operations |
| cas:UploadUserCertificate | certificate name | Write — specific cert name |
| cas:CreateDeploymentJob | job type + resources | Write — specific targets |
| cas:RevokeCertificate | certificate | Write — specific cert ID |
| cas:DeleteUserCertificate | certificate | Write — specific cert ID |

**Recommended RAM Policy**:

```json
{
  "Version": "1",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "cas:List*",
      "cas:Get*",
      "cas:Describe*"
    ],
    "Resource": "*"
  }, {
    "Effect": "Allow",
    "Action": [
      "cas:UploadUserCertificate",
      "cas:CreateDeploymentJob",
      "cas:RevokeCertificate"
    ],
    "Resource": "acs:cas:*:*:/*"
  }]
}
```

### Private Key Handling

| Rule | Enforcement |
|------|-------------|
| Never log private key content | SKILL.md mandates masking |
| Pass via env var or file reference | CLI --Key accepts variable |
| SM2 dual-key separation | Sign/Encrypt keys stored separately |
| Key material never in trace | Hard rule in SKILL.md |

### HTTPS Enforcement

| Setting | Recommendation |
|---------|---------------|
| Redirect HTTP to HTTPS | Enable on ALB/SLB/CDN |
| TLS version | Minimum TLS 1.2; disable TLS 1.0/1.1 |
| Cipher suite | Enforce strong ciphers; disable weak ones |

## Stability

### Pre-Deployment Checklist

| Check | Method | Pass Criteria |
|-------|--------|--------------|
| Certificate validity | GetUserCertificateDetail | NotAfter > 30 days |
| Certificate status | GetUserCertificateDetail | Status = ISSUED |
| Target resource existence | ListCloudResources | Resources accessible |
| Contact validity | ListContact | Contact ID active |
| Quota availability | DescribePackageState | UsedCount < TotalCount |

### Rollback Plan

| Phase | Rollback Action |
|-------|----------------|
| After Phase 2 (Upload) | DeleteUserCertificate — safe if not yet deployed |
| After Phase 3 (Deploy partial) | UpdateWorkerResourceStatus with previous cert — if rollback supported |
| After Phase 3 (Deploy success) | Cannot auto-rollback — manual redeployment needed |

### Failure Handling

| Failure Point | Recovery |
|--------------|---------|
| Job pending forever | Check contact; retry with valid ContactId |
| Job partial_success | Retry failed workers; investigate failed resources |
| Job failed | Investigate per DescribeDeploymentJob; check product permissions |
| Old cert revoked too early | Cannot undo revocation — ensure new cert deployed first |

### RTO/RPO

| Metric | Target | Method |
|--------|--------|--------|
| RTO (certificate deployment) | < 30 min | Automated CreateDeploymentJob |
| RPO (certificate data) | 0 (no data loss) | Certificate replacement does not affect data |
| Deployment success rate | > 99% | Pre-deployment discovery + verification |

## Cost

### Certificate Pack Management

| Action | Frequency | Benefit |
|--------|-----------|---------|
| DescribePackageState | Monthly | Track usage vs quota |
| Monitor WILLEXPIRED certs | Weekly | Proactive renewal before expiry |
| Delete expired certs | Monthly | Clean up stale resources |

### Cost Optimization

| Pattern | Recommendation |
|---------|---------------|
| Bulk deployment | Use one CreateDeploymentJob for all targets |
| Avoid duplicate purchases | Check existing certs before buying new |
| Cert pack sizing | Choose pack based on WILLEXPIRED tracking, not peak |
| Cross-cloud deployment | Single job for multi-cloud — reduces API calls |

### Cost Anti-Patterns

| Anti-Pattern | Cost Impact |
|-------------|-----------|
| Creating new cert pack for each renewal | Wastes unused quotas |
| One job per resource | Unnecessary API calls |
| Ignoring WILLEXPIRED certs | Emergency rush purchases at higher cost |

## Efficiency

### Batch Deployment

| Scenario | Command | Efficiency |
|---------|---------|-----------|
| Deploy to multiple SLBs | Single CreateDeploymentJob | 1 API call vs N |
| Deploy to mixed products | JobType=Multiple | 1 job for all types |
| Deploy to 50+ resources | Split into multiple jobs | Max 50 ResourceIds per job |

### Automation Patterns

| Pattern | Tool | Use Case |
|---------|------|----------|
| Scheduled renewal | cron + SKILL.md workflow | Weekly cert health check |
| Deployment verification | Script loop polling DescribeDeploymentJobStatus | Automated Phase 3-4 |
| Expiry monitoring | CMS alarm on NotAfter | Proactive renewal |

### Deployment Speed

| Step | Typical Duration |
|------|----------------|
| CreateDeploymentJob | < 5s |
| SLB/ALB/NLB deployment | 30s - 2min |
| CDN/DCDN deployment | 1 - 5min |
| OSS deployment | 30s - 1min |
| WAF deployment | 1 - 3min |
| Cross-cloud deployment | 5 - 15min |

## Performance

### Key Metrics

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Deployment success rate | > 98% | 90-98% | < 90% |
| Average deployment time | < 2min | 2-5min | > 5min |
| Certificate expiry lead time | > 30 days | 7-30 days | < 7 days |
| Partial success rate | 0% | 1-5% | > 5% |

### Monitoring Recommendations

| Alert | Threshold | Action |
|-------|-----------|--------|
| WILLEXPIRED cert detected | Any | Notify ops team |
| Deployment failed | Any | Investigate immediately |
| Partial success rate | > 5% | Check target product permissions |
| Quota usage | > 80% | Plan certificate pack purchase |
