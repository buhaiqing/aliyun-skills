<!-- markdownlint-disable MD013 MD060 MD024 MD022 MD032 -->

# Idempotency Checklist — CEN/CBN

## Create Operations

| Operation | Idempotency Rule |
|-----------|------------------|
| `CreateCen` | Check `DescribeCens --Name`; use `ClientToken` |
| `CreateTransitRouter` | Check existing TRs by `CenId` + `RegionId` + name; use `ClientToken` |
| `CreateTransitRouterVpcAttachment` | Check attachments filtered by VPC/TransitRouter; use `ClientToken` and DryRun |
| `CreateTransitRouterPeerAttachment` | Check existing peer attachment pair; confirm cost; use `ClientToken` |
| `CreateTransitRouterRouteEntry` | Check route table for destination CIDR and next hop; use `ClientToken` |
| `EnableTransitRouterRouteTablePropagation` | Check existing propagation first |
| `AssociateTransitRouterAttachmentWithRouteTable` | Check existing association first |

## Delete Operations

Delete is idempotent only when:

1. The exact resource ID was confirmed.
2. A pre-delete describe showed the resource existed.
3. A post-delete describe returns NotFound/empty for the same ID.

Do not treat arbitrary NotFound as success if the pre-delete ID was never validated.

## Retry Policy

| Error | Retry? |
|-------|--------|
| `Throttling` | Yes, max 3, exponential backoff |
| `InternalError` | Yes, max 3, preserve RequestId |
| `IncorrectStatus` | Poll if transitioning; no retry if failed/deleting |
| `InvalidParameter` | Retry once only after deterministic fix |
| `RouteConflict`, `QuotaExceeded`, `Forbidden.RAM`, `InsufficientBalance` | No; HALT |

## Automation Requirements

- Generate deterministic `ClientToken` from operation intent and request ID.
- Log RequestId and resource ID, never secrets.
- Persist GCL traces for destructive and route-changing operations.
- Re-run describe after every retry to avoid duplicate changes.
