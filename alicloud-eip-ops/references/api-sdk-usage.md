# API & SDK — EIP

> **Purpose:** EIP API operation map, required fields, pagination, and Go SDK usage.

## OpenAPI

- **Product:** VPC (EIP operations are part of VPC API)
- **API Version:** 2016-04-28
- **OpenAPI Doc:** https://help.aliyun.com/zh/vpc/developer-reference/api-vpc-2016-04-28-overview
- **Endpoint:** `vpc.aliyuncs.com`

## Go SDK Package

```
github.com/alibabacloud-go/vpc-20160428/v3/client
```

## Operations Map

### EIP Core Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Allocate EIP | `AllocateEipAddress` | RegionId | Bandwidth, InternetChargeType, ISP (optional) |
| Describe EIPs | `DescribeEipAddresses` | RegionId | AllocationId, Status, InstanceId (all optional) |
| Release EIP | `ReleaseEipAddress` | RegionId, AllocationId | Must be unbound first (Status=Available) |
| Associate EIP | `AssociateEipAddress` | RegionId, AllocationId, InstanceId, InstanceType | InstanceType: EcsInstance/Nat/SLBInstance/HaVip/NetworkInterface/Ngw |
| Unassociate EIP | `UnassociateEipAddress` | RegionId, AllocationId, InstanceId, InstanceType | |
| Modify EIP | `ModifyEipAddressAttribute` | RegionId, AllocationId | Bandwidth, InternetChargeType, Name, Description |
| Convert NAT Public IP | `ConvertNatPublicIpToEip` | RegionId, InstanceId | Convert ECS NAT public IP to EIP |

### EIP Pro Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Allocate Pro EIP | `AllocateEipAddressPro` | RegionId | Bandwidth, InternetChargeType, Name |
| Associate Batch EIP | `AssociateEipAddressBatch` | RegionId, AllocationIds, InstanceId, InstanceType | Multiple EIPs to one instance |

### EIP Bandwidth Plan Operations

| Goal | OperationId | Notes |
|------|-------------|-------|
| Create Bandwidth Plan | `CreateCommonBandwidthPackage` | Bandwidth, ChargeType, Name |
| Describe Bandwidth Plans | `DescribeCommonBandwidthPackages` | RegionId |
| Add EIP to Plan | `AddCommonBandwidthPackageIp` | BandwidthPackageId, IpInstanceId |
| Remove EIP from Plan | `RemoveCommonBandwidthPackageIp` | BandwidthPackageId, IpInstanceId |
| Delete Bandwidth Plan | `DeleteCommonBandwidthPackage` | BandwidthPackageId |

## Key Fields

### AllocateEipAddress Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| RegionId | string | Yes | Region ID |
| Bandwidth | int | Yes | Bandwidth in Mbps (1-500 for PayByBandwidth, 1-200 for PayByTraffic) |
| InternetChargeType | string | Yes | PayByBandwidth or PayByTraffic |
| ISP | string | No | BGP (default), ChinaTelecom, ChinaUnicom, ChinaMobile |
| Name | string | No | EIP name |
| DeletionProtection | boolean | No | Enable/disable deletion protection |
| AutoPay | boolean | No | Auto-payment |

### DescribeEipAddresses Response

| Field | Path | Type | Description |
|-------|------|------|-------------|
| TotalCount | `$.TotalCount` | int | Total EIPs |
| AllocationId | `$.EipAddresses.EipAddress[].AllocationId` | string | EIP ID |
| IpAddress | `$.EipAddresses.EipAddress[].IpAddress` | string | Public IP |
| Status | `$.EipAddresses.EipAddress[].Status` | string | Available/InUse/Associating/Unassociating/Releasing |
| InstanceId | `$.EipAddresses.EipAddress[].InstanceId` | string | Bound instance ID |
| InstanceType | `$.EipAddresses.EipAddress[].InstanceType` | string | Bound instance type |
| Bandwidth | `$.EipAddresses.EipAddress[].Bandwidth` | int | Current bandwidth (Mbps) |
| InternetChargeType | `$.EipAddresses.EipAddress[].InternetChargeType` | string | PayByBandwidth/PayByTraffic |
| Name | `$.EipAddresses.EipAddress[].Name` | string | EIP name |
| AvailableRegions | `$.EipAddresses.EipAddress[].AvailableRegions` | string[] | Available regions |

### AssociateEipAddress — InstanceType Values

| Value | Target Resource | CLI Example |
|-------|-----------------|-------------|
| `EcsInstance` | ECS Instance | Primary use case |
| `Nat` | NAT Gateway | NAT SNAT/DNAT source |
| `SLBInstance` | Server Load Balancer | Internet-facing SLB |
| `HaVip` | High-Availability Virtual IP | HA failover |
| `NetworkInterface` | Elastic Network Interface | Secondary ENI |
| `Ngw` | Enhanced NAT Gateway | vSwitch-level SNAT |
