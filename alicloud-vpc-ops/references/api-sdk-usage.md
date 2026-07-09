# API & SDK — VPC

> **Purpose:** VPC API operation map, required fields, pagination, and Go SDK usage.

## OpenAPI

- **Product:** VPC (Virtual Private Cloud)
- **API Version:** 2016-04-28
- **OpenAPI Doc:** https://help.aliyun.com/zh/vpc/developer-reference/api-vpc-2016-04-28-overview
- **Endpoint:** `vpc.aliyuncs.com`

## Go SDK Package

```
github.com/alibabacloud-go/vpc-20160428/v3/client
```

## Operations Map

### VPC Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create VPC | `CreateVpc` | RegionId | CidrBlock (optional, default 172.16.0.0/12), VpcName (optional) |
| Describe VPCs | `DescribeVpcs` | RegionId | VpcId (optional), VpcName (optional), IsDefault (optional) |
| Modify VPC | `ModifyVpcAttribute` | RegionId, VpcId | New VpcName, Description |
| Delete VPC | `DeleteVpc` | RegionId, VpcId | No vSwitches/NAT/other deps allowed |
| Create Default VPC | `CreateDefaultVpc` | — | Creates system default VPC with default vSwitches |
| Add Secondary CIDR | `AssociateVpcCidrBlock` | RegionId, VpcId | Secondary IPv4 CIDR |
| Remove Secondary CIDR | `UnassociateVpcCidrBlock` | RegionId, VpcId | |

### vSwitch Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create vSwitch | `CreateVSwitch` | RegionId, VpcId, ZoneId, CidrBlock | |
| Describe vSwitches | `DescribeVSwitches` | RegionId | VpcId (optional), VSwitchId (optional) |
| Modify vSwitch | `ModifyVSwitchAttribute` | RegionId, VSwitchId | New VSwitchName, Description |
| Delete vSwitch | `DeleteVSwitch` | RegionId, VSwitchId | No running resources in vSwitch |
| Create Default vSwitch | `CreateDefaultVSwitch` | ZoneId | Creates default vSwitch |

### Route Table Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Describe RouteTables | `DescribeRouteTables` | RegionId | VpcId (optional), RouteTableId (optional) |
| Associate RouteTable | `AssociateRouteTable` | RegionId, RouteTableId, VSwitchId | |
| Unassociate RouteTable | `UnassociateRouteTable` | RegionId, RouteTableId, VSwitchId | |

### NAT Gateway Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create NAT Gateway | `CreateNatGateway` | RegionId, VpcId | NatType (Enhanced/Normal), VSwitchId (for Enhanced) |
| Describe NAT Gateways | `DescribeNatGateways` | RegionId | NatGatewayId (optional), VpcId (optional) |
| Modify NAT Gateway | `ModifyNatGatewayAttribute` | RegionId, NatGatewayId | New Name, Description |
| Delete NAT Gateway | `DeleteNatGateway` | RegionId, NatGatewayId | Delete all SNAT/DNAT first |

### SNAT Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Describe SNAT Entries | `DescribeSnatTableEntries` | RegionId, SnatTableId | |
| Create SNAT Entry | `CreateSnatEntry` | RegionId | NatGatewayId, SourceCIDR, SnatIp |
| Delete SNAT Entry | `DeleteSnatEntry` | RegionId, SnatEntryId | |

### DNAT / Forward Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Describe Forward Entries | `DescribeForwardTableEntries` | RegionId, ForwardTableId | |
| Create Forward Entry | `CreateForwardEntry` | RegionId | NatGatewayId, IpProtocol, ExternalIp, ExternalPort, InternalIp, InternalPort |
| Delete Forward Entry | `DeleteForwardEntry` | RegionId, ForwardEntryId | |

### EIP Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Allocate EIP | `AllocateEipAddress` | RegionId | Bandwidth, ISP (optional), Name (optional) |
| Describe EIPs | `DescribeEipAddresses` | RegionId | AllocationId (optional), Status (optional) |
| Release EIP | `ReleaseEipAddress` | RegionId, AllocationId | Must be unbound first |
| Associate EIP | `AssociateEipAddress` | RegionId, AllocationId, InstanceId, InstanceType | |
| Unassociate EIP | `UnassociateEipAddress` | RegionId, AllocationId, InstanceId, InstanceType | |
| Modify EIP | `ModifyEipAddressAttribute` | RegionId, AllocationId | Bandwidth, Name, Description |
| Convert EIP | `ConvertNatPublicIpToEip` | RegionId, InstanceId | Convert NAT public IP |

### VPN Gateway Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create VPN Gateway | `CreateVpnGateway` | RegionId, VpcId | VpnType |
| Describe VPN Gateways | `DescribeVpnGateways` | RegionId | |
| Modify VPN Gateway | `ModifyVpnGatewayAttribute` | RegionId, VpnGatewayId | Name, Description, VpnType |
| Delete VPN Gateway | `DeleteVpnGateway` | RegionId, VpnGatewayId | Delete IPsec connections first |

### IPsec Server Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create IPsec Server | `CreateIpsecServer` | VpnGatewayId, LocalSubnet, IkeConfig.*, IpsecConfig.* | |
| Modify IPsec Server | `ModifyIpsecServer` | IpsecServerId | |
| Delete IPsec Server | `DeleteIpsecServer` | IpsecServerId | |
| Describe IPsec Servers | `DescribeIpsecServers` | VpnGatewayId | |

### Customer Gateway Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create Customer Gateway | `CreateCustomerGateway` | RegionId, IpAddress | |
| Describe Customer Gateways | `DescribeCustomerGateways` | RegionId | |
| Modify Customer Gateway | `ModifyCustomerGateway` | CustomerGatewayId | |
| Delete Customer Gateway | `DeleteCustomerGateway` | CustomerGatewayId | |

### Network ACL Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create Network ACL | `CreateNetworkAcl` | RegionId, VpcId | Name (optional) |
| Describe Network ACLs | `DescribeNetworkAcls` | RegionId | |
| Delete Network ACL | `DeleteNetworkAcl` | RegionId, NetworkAclId | |
| Associate Network ACL | `AssociateNetworkAcl` | RegionId, NetworkAclId | |
| Unassociate Network ACL | `UnassociateNetworkAcl` | RegionId, NetworkAclId | |
| Copy ACL Rules | `CopyNetworkAclEntries` | RegionId, NetworkAclId | |

### FlowLog Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create FlowLog | `CreateFlowLog` | RegionId, ResourceId | Resource type (VPC/VSwitch) |
| Describe FlowLogs | `DescribeFlowLogs` | RegionId | |
| Delete FlowLog | `DeleteFlowLog` | RegionId, FlowLogId | |
| Active FlowLog | `ActiveFlowLog` | RegionId, FlowLogId | Start flow log |
| Deactive FlowLog | `DeactiveFlowLog` | RegionId, FlowLogId | Pause flow log |

### DHCP Options Set Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create DHCP Options | `CreateDhcpOptionsSet` | RegionId | DhcpOptionsSetName, DomainName, DnsServers |
| Describe DHCP Options | `DescribeDhcpOptionsSets` | RegionId | |
| Associate DHCP to VPC | `AttachDhcpOptionsSetToVpc` | RegionId, VpcId, DhcpOptionsSetId | |
| Delete DHCP Options | `DeleteDhcpOptionsSet` | RegionId, DhcpOptionsSetId | |

### HaVip Operations

| Goal | OperationId | Required Params | Notes |
|------|-------------|-----------------|-------|
| Create HaVip | `CreateHaVip` | RegionId, VpcId, VSwitchId | IpAddress (optional) |
| Describe HaVips | `DescribeHaVips` | RegionId | |
| Delete HaVip | `DeleteHaVip` | RegionId, HaVipId | |
| Associate HaVip | `AssociateHaVip` | RegionId, HaVipId, InstanceId | |
| Unassociate HaVip | `UnassociateHaVip` | RegionId, HaVipId, InstanceId | |

## Pagination

All list/describe ops: `PageNumber` (int, default 1), `PageSize` (int, default 10, max 50).

```bash
aliyun vpc DescribeVpcs --RegionId cn-hangzhou --PageSize 50 --PageNumber 1
```

## Response Examples

### CreateVpc Response
```json
{"RequestId": "D3362978-0AED-4E23-8AED-9020F0D9****", "VpcId": "vpc-bp1qpo0eug5el9mrwnbmv****"}
```

### DescribeVpcs Response
```json
{"RequestId": "9D4A5B0E-1A2D-4E5F-8C3B-D1E2F3A4B5C6", "TotalCount": 2, "PageSize": 10, "PageNumber": 1, "Vpcs": {"Vpc": [{"VpcId": "vpc-xxx", "VpcName": "my-vpc", "Status": "Available", "CidrBlock": "172.16.0.0/12", "IsDefault": false, "CreationTime": "2026-05-16T06:00:00Z", "RegionId": "cn-hangzhou"}]}}
```
