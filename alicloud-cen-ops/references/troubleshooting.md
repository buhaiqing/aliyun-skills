<!-- markdownlint-disable MD013 MD060 MD024 MD022 MD032 -->

# Troubleshooting — CEN/CBN

## Diagnostic Order

1. Verify credentials and CLI support: `aliyun version && aliyun help cbn`.
2. Describe CEN: `aliyun cbn DescribeCens --CenId {{user.cen_id}}`.
3. Describe transit router in the exact region.
4. Describe attachments and route tables.
5. Check route propagation and association.
6. Run `DescribeRouteConflict` for affected child instances.
7. Check bandwidth packages/inter-region bandwidth limits.
8. Check flow logs and VBR health checks if enabled.
9. Delegate endpoint-specific checks to VPC/ECS/RDS/SLB skills.
10. Escalate with `RequestId` if cloud-side errors persist.

## Common Error Codes

| Code / Pattern | Meaning | Agent Action |
|----------------|---------|--------------|
| `InvalidParameter` | Parameter violates API schema | FIX against `aliyun help cbn <Operation>`; retry once if safe |
| `MissingParameter` | Required field absent | FIX by collecting missing `{{user.*}}` |
| `Forbidden.RAM` / `NoPermission` | RAM policy lacks CBN action | HALT; request least-privilege CBN permissions |
| `InvalidCenId.NotFound` / `CenNotFound` | CEN does not exist or wrong account | HALT; re-list CENs and confirm ID/account |
| `InvalidTransitRouterId.NotFound` | TR ID invalid/wrong region | HALT; describe TRs in the specified region |
| `InvalidTransitRouterAttachmentId.NotFound` | Attachment absent | Treat as success only during delete validation; otherwise HALT |
| `IncorrectStatus.TransitRouter` | TR is creating/deleting/updating | Poll if transitioning; HALT if failed/deleting |
| `IncorrectStatus.Attachment` | Attachment is not stable | Poll up to 300s; then HALT with RequestId |
| `RouteConflict` | CIDR/route conflict | HALT; show conflicting routes and redesign |
| `InvalidCidrBlock.Overlapped` | CIDR overlaps with existing network | HALT; delegate CIDR planning to VPC skill |
| `ResourceAlreadyExists` / `ResourceAlreadyAssociated` | Duplicate create/association | Describe existing resource and reuse if intent matches |
| `DependencyViolation` | Parent has child resources | HALT; list dependencies and cleanup order |
| `QuotaExceeded` | Resource quota reached | HALT; request quota increase or cleanup |
| `InsufficientBalance` | Billing issue | HALT; user must resolve billing |
| `DryRunOperation` | Dry-run passed | Expected; ask explicit confirmation before real execution |
| `Throttling` / 429 | Rate limited | Retry 3 times with exponential backoff |
| `InternalError` / 5xx | Alibaba Cloud internal error | Retry 3 times; escalate with RequestId |

## Connectivity Diagnosis Patterns

### VPCs attached but cannot communicate

```bash
aliyun cbn DescribeTransitRouterAttachments --RegionId {{user.region}} --TransitRouterId {{user.transit_router_id}}
aliyun cbn DescribeTransitRouterRouteTables --TransitRouterId {{user.transit_router_id}}
aliyun cbn ListTransitRouterRouteEntries --TransitRouterRouteTableId {{user.route_table_id}}
```

Check:
- Both VPC attachments are stable.
- Each attachment is associated with the intended route table.
- Route propagation is enabled or static routes exist.
- Security groups/NACLs allow traffic (delegate to VPC/ECS skill).

### Cross-region latency or packet loss

```bash
aliyun cbn DescribeCenInterRegionBandwidthLimits --CenId {{user.cen_id}}
aliyun cbn DescribeCenBandwidthPackages
```

Check bandwidth limit, package association, QoS queues, and CloudMonitor metrics.

### VBR link intermittent

```bash
aliyun cbn DescribeCenVbrHealthCheck --CenId {{user.cen_id}} --VbrInstanceId {{user.vbr_id}}
```

Enable or adjust VBR health checks only after confirming circuit ownership and maintenance window.

## Recovery Playbooks

### Route change caused outage

1. Stop further writes.
2. Export current route table and attachment association state.
3. Compare with pre-change trace.
4. Recreate previous route entry or disable recently enabled propagation.
5. Validate traffic with endpoint-specific checks.
6. Record RequestIds and timeline.

### Delete blocked by dependencies

1. Run all `Describe*` dependency checks.
2. Delete in reverse dependency order from [core concepts](core-concepts.md).
3. Re-run GCL before each destructive step.
4. Validate parent is empty, then retry delete.

## User-Facing Error Format

Use:

```text
[ERROR] <Code>: <short summary>
What happened: <plain-language cause>
How to fix: <specific action>
Next step: <command or decision required>
RequestId: <request id if available>
```
