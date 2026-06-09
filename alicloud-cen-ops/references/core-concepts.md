<!-- markdownlint-disable MD013 MD060 MD024 MD022 MD032 -->

# Core Concepts — Alibaba Cloud CEN/CBN

## Product Boundary

Cloud Enterprise Network (CEN, CLI/API product code `cbn`) connects cloud and hybrid networks. This skill covers CEN control-plane operations only: CEN instances, bandwidth packages, transit routers, attachments, route tables, route maps, QoS, flow logs, and VBR health checks.

Delegate standalone network resource lifecycle:

| Resource | Delegate |
|----------|----------|
| VPC, vSwitch, VPN gateway, route table inside VPC | `alicloud-vpc-ops` |
| EIP | `alicloud-eip-ops` |
| NAT gateway | `alicloud-nat-ops` |
| ECS/RDS/SLB endpoint checks | Product-specific skill |

## Resource Model

| Layer | Resource | Notes |
|-------|----------|-------|
| Global container | CEN instance (`CenId`) | Logical network fabric; may span regions/accounts |
| Regional routing | Transit router (`TransitRouterId`) | Enterprise Edition routing hub per region |
| Connectivity edge | Attachment (`TransitRouterAttachmentId`) | VPC, VBR, VPN, ECR, or peer attachment |
| Routing policy | Route table / route entry / propagation / association | Determines forwarding behavior |
| Cross-region capacity | Bandwidth package / inter-region bandwidth limit / peer attachment | Cost and throughput control |
| Observability | Flow log / VBR health check | Traffic and link diagnostics |

## Operation Dependencies

```text
CEN
├── BandwidthPackage associations
├── TransitRouter(region A)
│   ├── RouteTables
│   │   ├── RouteEntries
│   │   ├── Attachment associations
│   │   └── Propagation rules
│   └── Attachments: VPC / VBR / VPN / ECR / Peer
└── TransitRouter(region B)
    └── Peer attachment back to region A
```

Before deleting a parent, describe all children and clean up in reverse order.

## Safety-Critical Concepts

### Route Conflict
CEN rejects or blackholes routes when CIDRs overlap or the route target is ambiguous. Always run `DescribeRouteConflict` or equivalent inventory checks before attaching networks or adding routes.

### Propagation vs Association
- **Association**: which route table an attachment uses for forwarding.
- **Propagation**: whether routes learned from an attachment are imported into a route table.

Misconfiguring either can cause one-way connectivity or wide route leakage.

### Cross-Account Grants
For cross-account attachments, the resource owner must grant permissions to the CEN/transit router owner. Validate grants before create operations.

### Region Semantics
CEN instance is global, but transit routers, child instances, and attachments are regional. Keep local region, peer region, and child resource region explicit.

## Limits and Quotas

Do not hardcode quotas. Query current state and quotas with product APIs:

```bash
aliyun cbn DescribeCens
aliyun cbn DescribeTransitRouters --RegionId {{user.region}} --CenId {{user.cen_id}}
aliyun cbn DescribeCenBandwidthPackages
aliyun cbn DescribeCenInterRegionBandwidthLimits --CenId {{user.cen_id}}
```

If API returns `QuotaExceeded`, HALT and ask the user to clean up unused resources or request a quota increase.

## Destructive Cleanup Order

1. Export topology and route tables to trace/audit output.
2. Delete static route entries and disable unwanted propagation.
3. Disassociate attachments from route tables.
4. Delete VPC/VBR/VPN/ECR/peer attachments.
5. Delete custom route tables and QoS/route maps if unused.
6. Disassociate/delete bandwidth packages if required.
7. Delete transit routers.
8. Delete CEN instance.

Never skip dependency checks for DeleteCen or DeleteTransitRouter.
