<!-- markdownlint-disable MD013 MD060 MD024 MD022 MD032 -->

# Well-Architected Assessment — CEN/CBN

## Five-Pillar Checklist

| Pillar | CEN Assessment | Evidence |
|--------|----------------|----------|
| Security | Least-privilege CBN actions; cross-account grants verified; no credential leakage | RAM policy review, command trace |
| Stability | Redundant region paths where needed; route rollback plan; VBR health checks | topology export, health checks |
| Cost | Inter-region bandwidth sized; unused attachments/packages identified | bandwidth/package inventory |
| Efficiency | Idempotent automation with `ClientToken`; batch describe; DryRun | scripts/traces |
| Performance | Bandwidth utilization and route convergence monitored | CMS metrics, flow logs |

## Security

Minimum permissions should be scoped to required CBN APIs, for example:

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cbn:Describe*",
        "cbn:List*",
        "cbn:CheckTransitRouterService"
      ],
      "Resource": "*"
    }
  ]
}
```

Add write actions only for approved automation. Cross-account attachments require explicit grants and owner/account verification.

## Stability

- Export topology before writes.
- Use maintenance windows for route/attachment changes.
- Use redundant attachments and cross-region paths for critical workloads.
- Enable VBR health checks for Express Connect paths.
- Keep rollback commands ready for route entries and propagation changes.

## Cost

- Query bandwidth packages and inter-region limits instead of assuming capacity.
- Detect idle attachments and unused bandwidth packages.
- Confirm cost impact before peer attachments and bandwidth changes.
- Prefer right-sized bandwidth with alarms at 80/95% utilization.

## Efficiency

- Use `ClientToken` for create/update idempotency.
- Use `DryRun` where supported.
- Batch read-only describes before proposing changes.
- Keep runtime outputs under `.runtime/` or `audit-results/`.

## Performance

- Monitor inter-region bandwidth and packet loss symptoms.
- Use flow logs for top talkers and unexpected drops.
- Minimize broad route propagation; prefer explicit route tables for isolation.
- Validate route convergence after changes before declaring success.

## Destructive Operation Gate

Before `DeleteCen`, `DeleteTransitRouter*`, or route deletion:

1. Explicit user confirmation with exact resource ID.
2. GCL PASS.
3. Dependency inventory exported.
4. Rollback/restore path documented.
5. Validation command prepared.
