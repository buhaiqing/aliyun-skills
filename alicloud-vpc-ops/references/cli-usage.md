# CLI — VPC (`aliyun`)

> **Purpose:** `aliyun` CLI command reference for VPC operations.

## Install and config

- Install: `brew install aliyun-cli` or `/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"`
- Credentials via env vars: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- Region via env var: `ALIBABA_CLOUD_REGION_ID`

## Conventions (agent execution)

- Output is **JSON by default** — NO `--output json` needed
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- `--no-interactive` does NOT exist — commands are non-interactive by default

## Command Map

### VPC (Virtual Private Cloud)

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List VPCs | `aliyun vpc DescribeVpcs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --output cols=VpcId,VpcName,Status,CidrBlock rows=Vpcs.Vpc[].{VpcId:VpcId,VpcName:VpcName,Status:Status,CidrBlock:CidrBlock}` | |
| Create VPC | `aliyun vpc CreateVpc --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcName "my-vpc" --CidrBlock "192.168.0.0/16"` | Returns VpcId |
| Describe VPC | `aliyun vpc DescribeVpcs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}}` | |
| Modify VPC | `aliyun vpc ModifyVpcAttribute --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}} --VpcName "new-name"` | |
| Delete VPC | `aliyun vpc DeleteVpc --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}}` | Must delete vSwitches first |
| Create Default VPC | `aliyun vpc CreateDefaultVpc` | |
| List Regions | `aliyun vpc DescribeRegions` | |

### vSwitch

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List vSwitches | `aliyun vpc DescribeVSwitches --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}} --output cols=VSwitchId,VSwitchName,Status,ZoneId rows=VSwitches.VSwitch[].{VSwitchId:VSwitchId,VSwitchName:VSwitchName,Status:Status,ZoneId:ZoneId}` | |
| Create vSwitch | `aliyun vpc CreateVSwitch --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}} --ZoneId {{user.zone_id}} --CidrBlock "192.168.1.0/24" --VSwitchName "my-vswitch"` | Returns VSwitchId |
| Describe vSwitch | `aliyun vpc DescribeVSwitches --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VSwitchId {{user.vswitch_id}}` | |
| Modify vSwitch | `aliyun vpc ModifyVSwitchAttribute --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VSwitchId {{user.vswitch_id}} --VSwitchName "new-name"` | |
| Delete vSwitch | `aliyun vpc DeleteVSwitch --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VSwitchId {{user.vswitch_id}}` | Must delete resources in vSwitch first |

### RouteTable

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List RouteTables | `aliyun vpc DescribeRouteTables --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}} --output cols=RouteTableId,RouteTableName,VpcId rows=RouteTables.RouteTable[].{RouteTableId:RouteTableId,RouteTableName:RouteTableName,VpcId:VpcId}` | |
| Associate RouteTable | `aliyun vpc AssociateRouteTable --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --RouteTableId {{user.route_table_id}} --VSwitchId {{user.vswitch_id}}` | |
| Unassociate RouteTable | `aliyun vpc UnassociateRouteTable --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --RouteTableId {{user.route_table_id}} --VSwitchId {{user.vswitch_id}}` | |

### NAT Gateway

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List NAT Gateways | `aliyun vpc DescribeNatGateways --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --output cols=NatGatewayId,Name,Status,Spec rows=NatGateways.NatGateway[].{NatGatewayId:NatGatewayId,Name:Name,Status:Status,Spec:Spec}` | |
| Create NAT Gateway | `aliyun vpc CreateNatGateway --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}} --NatType Enhanced --VSwitchId {{user.vswitch_id}} --Name "my-nat"` | Returns NatGatewayId |
| Describe NAT Gateway | `aliyun vpc DescribeNatGateways --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}` | Poll until Status=Available |
| Modify NAT Gateway | `aliyun vpc ModifyNatGatewayAttribute --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}} --Name "new-name"` | |
| Delete NAT Gateway | `aliyun vpc DeleteNatGateway --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}` | Delete SNAT/DNAT first |

### EIP (Elastic IP)

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List EIPs | `aliyun vpc DescribeEipAddresses --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --output cols=AllocationId,IpAddress,Status,InstanceId rows=EipAddresses.EipAddress[].{AllocationId:AllocationId,IpAddress:IpAddress,Status:Status,InstanceId:InstanceId}` | |
| Allocate EIP | `aliyun vpc AllocateEipAddress --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --Bandwidth 5 --Name "my-eip"` | Returns AllocationId |
| Describe EIP | `aliyun vpc DescribeEipAddresses --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}}` | |
| Associate EIP | `aliyun vpc AssociateEipAddress --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}} --InstanceId {{user.instance_id}} --InstanceType EcsInstance` | |
| Unassociate EIP | `aliyun vpc UnassociateEipAddress --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}} --InstanceId {{user.instance_id}} --InstanceType EcsInstance` | |
| Release EIP | `aliyun vpc ReleaseEipAddress --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}}` | Must unbind first |
| Modify EIP | `aliyun vpc ModifyEipAddressAttribute --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}} --Bandwidth 10` | |

### VPN Gateway

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List VPN Gateways | `aliyun vpc DescribeVpnGateways --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}` | |
| Create VPN Gateway | `aliyun vpc CreateVpnGateway --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}} --VpnType Normal` | |
| Delete VPN Gateway | `aliyun vpc DeleteVpnGateway --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpnGatewayId {{user.vpn_gateway_id}}` | Delete IPsec connections first |

### Network ACL

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List Network ACLs | `aliyun vpc DescribeNetworkAcls --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}` | |
| Create Network ACL | `aliyun vpc CreateNetworkAcl --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}} --Name "my-acl"` | |
| Delete Network ACL | `aliyun vpc DeleteNetworkAcl --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NetworkAclId {{user.network_acl_id}}` | Must unassociate from vSwitches first |
| Associate Network ACL | `aliyun vpc AssociateNetworkAcl --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NetworkAclId {{user.network_acl_id}}` | |
| Unassociate Network ACL | `aliyun vpc UnassociateNetworkAcl --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NetworkAclId {{user.network_acl_id}}` | |

### FlowLog

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List FlowLogs | `aliyun vpc DescribeFlowLogs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}` | |
| Create FlowLog | `aliyun vpc CreateFlowLog --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --ResourceId {{user.resource_id}} --ResourceType VPC --ProjectName "my-sls-project" --LogStoreName "my-logstore" --TrafficMirror "true" --Active "true"` | |
| Active FlowLog | `aliyun vpc ActiveFlowLog --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --FlowLogId {{user.flow_log_id}}` | Start |
| Deactive FlowLog | `aliyun vpc DeactiveFlowLog --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --FlowLogId {{user.flow_log_id}}` | Pause |
| Delete FlowLog | `aliyun vpc DeleteFlowLog --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --FlowLogId {{user.flow_log_id}}` | |

### HaVip

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List HaVips | `aliyun vpc DescribeHaVips --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}}` | |
| Create HaVip | `aliyun vpc CreateHaVip --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}} --VSwitchId {{user.vswitch_id}}` | |
| Associate HaVip | `aliyun vpc AssociateHaVip --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --HaVipId {{user.ha_vip_id}} --InstanceId {{user.instance_id}}` | |
| Unassociate HaVip | `aliyun vpc UnassociateHaVip --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --HaVipId {{user.ha_vip_id}} --InstanceId {{user.instance_id}}` | |
| Delete HaVip | `aliyun vpc DeleteHaVip --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --HaVipId {{user.ha_vip_id}}` | |

### DHCP Options Set

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List DHCP Options | `aliyun vpc DescribeDhcpOptionsSets --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}` | |
| Create DHCP Options | `aliyun vpc CreateDhcpOptionsSet --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --DhcpOptionsSetName "my-dhcp" --DnsServerList.1 8.8.8.8` | |
| Associate DHCP | `aliyun vpc AttachDhcpOptionsSetToVpc --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}} --DhcpOptionsSetId {{user.dhcp_options_set_id}}` | |
| Delete DHCP Options | `aliyun vpc DeleteDhcpOptionsSet --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --DhcpOptionsSetId {{user.dhcp_options_set_id}}` | |

### BGP

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List BGP Groups | `aliyun vpc DescribeBgpGroups --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}` | |
| Create BGP Group | `aliyun vpc CreateBgpGroup --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --BgpGroupId "my-group"` | |
| List BGP Peers | `aliyun vpc DescribeBgpPeers --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}` | |
| Create BGP Peer | `aliyun vpc CreateBgpPeer --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --BgpGroupId {{user.bgp_group_id}}` | |

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.Items.Item[]?`
- Use `--PageSize` to control result sets: `--PageSize 50`
- Example:
```bash
aliyun ecs DescribeInstances --PageSize 50 | jq '{total: .TotalCount, items: [.Items.Item[]? | {id: .Id, name: .Name}]}'
```

