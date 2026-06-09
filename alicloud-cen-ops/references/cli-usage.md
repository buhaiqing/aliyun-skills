<!-- markdownlint-disable MD013 MD060 MD024 MD022 MD032 -->

# CLI Usage — CEN/CBN (`aliyun cbn`)

## Evidence

`aliyun help cbn` reports:

- Product: `Cbn (Cloud Enterprise Network)`
- Version: `2017-09-12`
- Optional plugin: `aliyun plugin install --names aliyun-cli-cbn`
- Available APIs include `CreateCen`, `DeleteCen`, `CreateTransitRouter`, `CreateTransitRouterVpcAttachment`, `CreateTransitRouterPeerAttachment`, `CreateTransitRouterRouteEntry`, `DescribeCens`, `DescribeTransitRouters`, and many more.

## CLI Conventions

- Plain command output is JSON by default; do not add `--output json`.
- Use `--output cols=...,rows=...` for JMESPath tabular extraction.
- The CLI is non-interactive for API calls; there is no `--no-interactive` flag.
- Use environment credentials when running in agent contexts.
- Do not enable verbose debug output if it may expose credentials.

## Installation / Plugin

```bash
aliyun version
aliyun help cbn
# Optional enhanced product plugin:
aliyun plugin install --names aliyun-cli-cbn
```

## Command Map

| Goal | CLI Invocation |
|------|----------------|
| List CENs | `aliyun cbn DescribeCens` |
| Create CEN | `aliyun cbn CreateCen --Name {{user.cen_name}} --ClientToken {{user.client_token}}` |
| Delete CEN | `aliyun cbn DeleteCen --CenId {{user.cen_id}}` |
| Create bandwidth package | `aliyun cbn CreateCenBandwidthPackage --GeographicRegionAId {{user.geo_a}} --GeographicRegionBId {{user.geo_b}} --Bandwidth {{user.bandwidth_mbps}}` |
| Associate bandwidth package | `aliyun cbn AssociateCenBandwidthPackage --CenId {{user.cen_id}} --CenBandwidthPackageId {{user.bandwidth_package_id}}` |
| Create transit router | `aliyun cbn CreateTransitRouter --RegionId {{user.region}} --CenId {{user.cen_id}} --TransitRouterName {{user.name}}` |
| List transit routers | `aliyun cbn DescribeTransitRouters --RegionId {{user.region}} --CenId {{user.cen_id}}` |
| Attach VPC | `aliyun cbn CreateTransitRouterVpcAttachment --RegionId {{user.region}} --TransitRouterId {{user.transit_router_id}} --VpcId {{user.vpc_id}} --ZoneMappings.1.ZoneId {{user.zone_id}} --ZoneMappings.1.VSwitchId {{user.vswitch_id}}` |
| Attach VBR | `aliyun cbn CreateTransitRouterVbrAttachment --RegionId {{user.region}} --TransitRouterId {{user.transit_router_id}} --VbrId {{user.vbr_id}}` |
| Attach VPN | `aliyun cbn CreateTransitRouterVpnAttachment --RegionId {{user.region}} --TransitRouterId {{user.transit_router_id}} --VpnId {{user.vpn_id}}` |
| Create peer attachment | `aliyun cbn CreateTransitRouterPeerAttachment --RegionId {{user.region}} --TransitRouterId {{user.transit_router_id}} --PeerTransitRouterRegionId {{user.peer_region}} --PeerTransitRouterId {{user.peer_transit_router_id}} --Bandwidth {{user.bandwidth_mbps}}` |
| Create route table | `aliyun cbn CreateTransitRouterRouteTable --TransitRouterId {{user.transit_router_id}} --TransitRouterRouteTableName {{user.name}}` |
| Create route entry | `aliyun cbn CreateTransitRouterRouteEntry --TransitRouterRouteTableId {{user.route_table_id}} --TransitRouterRouteEntryDestinationCidrBlock {{user.destination_cidr}} --TransitRouterRouteEntryNextHopType Attachment --TransitRouterRouteEntryNextHopId {{user.attachment_id}}` |
| Enable propagation | `aliyun cbn EnableTransitRouterRouteTablePropagation --TransitRouterRouteTableId {{user.route_table_id}} --TransitRouterAttachmentId {{user.attachment_id}}` |
| Associate route table | `aliyun cbn AssociateTransitRouterAttachmentWithRouteTable --TransitRouterRouteTableId {{user.route_table_id}} --TransitRouterAttachmentId {{user.attachment_id}}` |
| Diagnose route conflict | `aliyun cbn DescribeRouteConflict --CenId {{user.cen_id}} --ChildInstanceId {{user.child_instance_id}} --ChildInstanceType {{user.child_instance_type}} --ChildInstanceRegionId {{user.region}}` |
| Create flow log | `aliyun cbn CreateFlowlog --CenId {{user.cen_id}} --RegionId {{user.region}} --ProjectName {{user.sls_project}} --LogStoreName {{user.logstore}}` |

## DryRun Pattern

Some write APIs support `--DryRun true`. Treat `DryRunOperation` as success of pre-execution validation, not as an error.

```bash
aliyun cbn CreateTransitRouterVpcAttachment \
  --DryRun true \
  --RegionId "{{user.region}}" \
  --TransitRouterId "{{user.transit_router_id}}" \
  --VpcId "{{user.vpc_id}}" \
  --ZoneMappings.1.ZoneId "{{user.zone_id}}" \
  --ZoneMappings.1.VSwitchId "{{user.vswitch_id}}"
```

## Polling Pattern

```bash
for i in $(seq 1 60); do
  aliyun cbn DescribeTransitRouterAttachments \
    --RegionId "{{user.region}}" \
    --TransitRouterAttachmentId "{{output.attachment_id}}" > /tmp/cbn-attachment.json
  # Extract status with jq if available; otherwise inspect JSON.
  jq -e '.TransitRouterAttachments.TransitRouterAttachment[0]' /tmp/cbn-attachment.json >/dev/null && break
  sleep 5
done
```

## Coverage Notes

The CLI exposes broad CEN coverage. If a parameter is missing in an installed CLI version, update CLI/plugin first; use JIT Go SDK fallback only after confirming the gap with `aliyun help cbn <Operation>`.
