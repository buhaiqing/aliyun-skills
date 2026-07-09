# Well-Architected Assessment — RAM

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to RAM.

## 安全 (Security) — *Primary Pillar for RAM*

| Area | Guidance |
|------|----------|
| **IAM** | RAM IS the security pillar. Scope policies to specific actions, resources, and conditions. Never use `Action: "*"` or `Resource: "*"` |
| **Credential Security** | Rotate access keys every 90 days. Enforce MFA for console access. STS for apps over long-term AK/SK |
| **Least Privilege** | Use `Allow` with explicit `Condition`. Avoid `Deny` unless explicitly blocking destructive actions |
| **No Root Access** | Root account should NEVER have access keys. All ops use RAM user with minimal permissions |

## 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | Policy versioning: create new version before deleting old one. Never leave zero active versions |
| **面向精细的运维管控** | Audit with `ListEntitiesForPolicy`. Monitor unused roles and access keys regularly |
| **面向风险的应急快恢** | Detach policy before delete. If all access lost, root account recovery available |

### DR Runbook
```
Phase 1: Verify — sts GetCallerIdentity to confirm credentials are still valid
Phase 2: Restore — If locked out, use root account to re-grant access
Phase 3: Validate — ListUsers/ListPolicies to confirm permissions are correct
```

## 成本 (Cost)

RAM is free. However, poorly managed identities can lead to:
- **Orphaned resources:** Users/roles that exist but are never used → audit and delete
- **Over-provisioned permissions:** Excessive `Action: "*"` leads to accidental resource creation → cost overruns

## 效率 (Efficiency)

- **Policy Templates:** Use predefined Alibaba Cloud system policies where appropriate
- **Groups:** Organize users into groups for bulk permission management
- **CI/CD:** STS AssumeRole for temporary pipeline credentials

## 性能 (Performance)

RAM API calls are instant (sub-second). Monitor:
| Metric | Threshold | Action |
|--------|----------|--------|
| Throttling | Any 429 | Retry with exponential backoff |
| Stale access keys | 90+ days old | Rotate or delete |