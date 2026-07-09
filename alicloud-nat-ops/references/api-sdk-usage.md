# API & SDK — NAT

> **Purpose:** NAT API operation map, required fields, pagination, and Go SDK usage.

## OpenAPI

- **Product:** VPC (NAT operations are part of VPC API)
- **API Version:** 2016-04-28
- **OpenAPI Doc:** https://help.aliyun.com/zh/vpc/developer-reference/api-vpc-2016-04-28-overview

## Go SDK Package

```
github.com/alibabacloud-go/vpc-20160428/v3/client
```

## Operations Map

### NAT Gateway Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create NAT | `CreateNatGateway` | RegionId, VpcId | NatType (Enhanced/Normal), VSwitchId (Enhanced), Name |
| Describe NAT | `DescribeNatGateways` | RegionId | NatGatewayId, VpcId (optional) |
| Modify NAT | `ModifyNatGatewayAttribute` | RegionId, NatGatewayId | Name, Description |
| Modify NAT Spec/Billing | `ModifyNatGatewaySpec` | RegionId, NatGatewayId, NatSpec | PayBySpec/PayByActualUsage |
| Delete NAT | `DeleteNatGateway` | RegionId, NatGatewayId | Delete all SNAT/DNAT first |

### SNAT Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create SNAT | `CreateSnatEntry` | RegionId | NatGatewayId, SnatIp (EIP address), SourceCIDR or VSwitchId |
| Describe SNAT | `DescribeSnatTableEntries` | RegionId | SnatTableId, SnatEntryId (optional) |
| Delete SNAT | `DeleteSnatEntry` | RegionId, SnatEntryId | |

### DNAT / Forward Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create DNAT (Forward) | `CreateForwardEntry` | RegionId | NatGatewayId, IpProtocol, ExternalIp, ExternalPort, InternalIp, InternalPort |
| Describe DNAT | `DescribeForwardTableEntries` | RegionId | ForwardTableId, ForwardEntryId (optional) |
| Delete DNAT | `DeleteForwardEntry` | RegionId, ForwardEntryId | |

### FULLNAT Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create FULLNAT | `CreateFullNatEntry` | RegionId | NatGatewayId, IpProtocol, FullNatIp, DestinationCidrBlock, DestinationPort, InternalIp, InternalPort |
| Describe FULLNAT | `DescribeFullNatEntries` | RegionId | |
| Delete FULLNAT | `DeleteFullNatEntry` | RegionId, FullNatEntryId | |

## Key Fields

### CreateNatGateway Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| RegionId | string | Yes | Region ID |
| VpcId | string | Yes | VPC ID |
| NatType | string | Yes | "Enhanced" or "Normal" |
| VSwitchId | string | Conditional | Required for Enhanced NAT, must be in same VPC |
| Name | string | No | NAT Gateway name |
| Description | string | No | Description |
| NatSpec | string | No | Spec: Small/Medium/Large/XLarge (for PayBySpec) |
| BillingMethod | string | No | PayBySpec or PayByActualUsage |
| AutoPay | boolean | No | Auto-payment |

### DescribeNatGateways Response

| Field | Path | Type | Description |
|-------|------|------|-------------|
| NatGatewayId | `$.NatGateways.NatGateway[].NatGatewayId` | string | NAT Gateway ID |
| Name | `$.NatGateways.NatGateway[].Name` | string | NAT name |
| Status | `$.NatGateways.NatGateway[].Status` | string | Creating/Available/Modifying/Deleting |
| VpcId | `$.NatGateways.NatGateway[].VpcId` | string | VPC ID |
| VSwitchId | `$.NatGateways.NatGateway[].VSwitchId` | string | vSwitch ID (Enhanced type) |
| NatType | `$.NatGateways.NatGateway[].NatType` | string | Enhanced/Normal |
| NatSpec | `$.NatGateways.NatGateway[].NatSpec` | string | Spec (Small/Medium/Large/XLarge) |
| BillingMethod | `$.NatGateways.NatGateway[].BillingMethod` | string | PayBySpec/PayByActualUsage |
| BandwidthPackageIds | `$.NatGateways.NatGateway[].BandwidthPackageIds.BandwidthPackageId` | array | Associated bandwidth plans |

### CreateSnatEntry — Source Modes

| Mode | Parameter | Description |
|------|-----------|-------------|
| vSwitch-level | `VSwitchId` | All instances in vSwitch use this SNAT |
| CIDR-level | `SourceCIDR` | Specific CIDR range uses this SNAT |

### CreateForwardEntry — Protocol Values

| Value | Description |
|-------|-------------|
| `TCP` | TCP protocol only |
| `UDP` | UDP protocol only |
| `Any` | Both TCP and UDP (protocol field: ip) |

### CreateForwardEntry — Port Values

| Value | Description |
|-------|-------------|
| Specific port | `80`, `443`, `8080`, etc. |
| Port range | `1024-65535` |
| All ports | `AnyPort` or `-1` |
