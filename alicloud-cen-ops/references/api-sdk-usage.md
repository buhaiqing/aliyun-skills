<!-- markdownlint-disable MD013 MD060 MD024 MD022 MD032 -->

# API & SDK Usage — CEN/CBN

## OpenAPI Baseline

- Product/API: Cbn 2017-09-12
- CLI product code: `cbn`
- OpenAPI overview: <https://help.aliyun.com/zh/cen/developer-reference/api-cbn-2017-09-12-overview>
- Go SDK package pattern: `github.com/alibabacloud-go/cbn-20170912/v2/client` (verify latest module before JIT execution)

## Common JSON Paths

```text
CreateCen -> $.CenId
DescribeCens -> $.Cens.Cen[].CenId
CreateCenBandwidthPackage -> $.CenBandwidthPackageId
CreateTransitRouter -> $.TransitRouterId
CreateTransitRouter*Attachment -> $.TransitRouterAttachmentId or operation-specific attachment ID field
DescribeTransitRouterAttachments -> $.TransitRouterAttachments.TransitRouterAttachment[]
CreateTransitRouterRouteTable -> $.TransitRouterRouteTableId
CreateTransitRouterRouteEntry -> $.TransitRouterRouteEntryId
Delete/Modify -> $.RequestId
```

## Operation Map

| Goal | API Operation | Required Inputs | Idempotency |
|------|---------------|-----------------|-------------|
| Create CEN | `CreateCen` | optional `Name`, `Description` | `ClientToken` |
| List CEN | `DescribeCens` | optional filters | n/a |
| Delete CEN | `DeleteCen` | `CenId` | Natural after NotFound |
| Create bandwidth package | `CreateCenBandwidthPackage` | geographic regions, bandwidth, charge type | `ClientToken` when supported |
| Associate bandwidth package | `AssociateCenBandwidthPackage` | `CenId`, `CenBandwidthPackageId` | Check existing association first |
| Create transit router | `CreateTransitRouter` | `CenId`, `RegionId` | `ClientToken` |
| Attach VPC | `CreateTransitRouterVpcAttachment` | `TransitRouterId`, `VpcId`, zone mappings | `ClientToken`, `DryRun` |
| Attach VBR | `CreateTransitRouterVbrAttachment` | `TransitRouterId`, `VbrId` | `ClientToken`, `DryRun` |
| Attach VPN | `CreateTransitRouterVpnAttachment` | `TransitRouterId`, VPN connection ID | `ClientToken`, `DryRun` |
| Peer attachment | `CreateTransitRouterPeerAttachment` | local/peer TR IDs, peer region, bandwidth | `ClientToken` |
| Route table | `CreateTransitRouterRouteTable` | `TransitRouterId` | `ClientToken` when supported |
| Route entry | `CreateTransitRouterRouteEntry` | route table, CIDR, next hop | `ClientToken` |
| Propagation | `EnableTransitRouterRouteTablePropagation` | route table, attachment | Check existing first |
| Association | `AssociateTransitRouterAttachmentWithRouteTable` | route table, attachment | Check existing first |
| Route conflict | `DescribeRouteConflict` | CEN/child instance IDs | read-only |
| Flow log | `CreateFlowlog`, `ActiveFlowLog`, `DescribeFlowlogs` | CEN/region/SLS config | Check existing first |

## Pagination

For list/describe operations, use the API's `PageNumber`/`PageSize` or token-based fields as exposed by `aliyun help cbn <Operation>`. Do not assume all describe APIs share the same pagination schema.

Example pattern:

```bash
aliyun cbn DescribeTransitRouterAttachments \
  --RegionId "{{user.region}}" \
  --TransitRouterId "{{user.transit_router_id}}" \
  --PageNumber 1 \
  --PageSize 50
```

## JIT Go SDK Skeleton

```go
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    cbn "github.com/alibabacloud-go/cbn-20170912/v2/client"
    "github.com/alibabacloud-go/tea/tea"
)

func main() {
    if os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID") == "" || os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET") == "" {
        panic("missing Alibaba Cloud credentials")
    }
    cfg := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("cbn.aliyuncs.com"),
    }
    client, err := cbn.NewClient(cfg)
    if err != nil { panic(err) }
    resp, err := client.DescribeCens(&cbn.DescribeCensRequest{})
    if err != nil { panic(err) }
    fmt.Println(tea.ToString(resp.Body))
}
```

Do not print `cfg` or environment variable values.

## Response Validation Rules

- Create operations must capture the new ID and immediately describe it.
- Delete operations validate by describe returning NotFound/empty for the exact ID.
- Route operations validate both route entry existence and next hop correctness.
- Attachment operations validate attachment state and route propagation/association state when configured.
