# VPC Troubleshooting Quick Reference

## Quick Diagnostic Commands

```bash
# Check if VPC exists
aliyun vpc DescribeVpcs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}}

# Check vSwitch status
aliyun vpc DescribeVSwitches --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VSwitchId {{user.vswitch_id}}

# Check NAT Gateway status
aliyun vpc DescribeNatGateways --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}

# Check EIP status
aliyun vpc DescribeEipAddresses --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}}

# Check route table
aliyun vpc DescribeRouteTables --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --RouteTableId {{user.route_table_id}}

# Check network ACL
aliyun vpc DescribeNetworkAcls --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NetworkAclId {{user.network_acl_id}}

# Check VPN Gateway
aliyun vpc DescribeVpnGateways --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpnGatewayId {{user.vpn_gateway_id}}

# Check DHCP options
aliyun vpc DescribeDhcpOptionsSets --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --DhcpOptionsSetId {{user.dhcp_options_set_id}}

# Check HaVip
aliyun vpc DescribeHaVips --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --HaVipId {{user.ha_vip_id}}

# Check FlowLog
aliyun vpc DescribeFlowLogs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --FlowLogId {{user.flow_log_id}}

# Check SNAT entries
aliyun vpc DescribeSnatTableEntries --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}

# Check DNAT entries
aliyun vpc DescribeForwardTableEntries --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}

# Check regions
aliyun vpc DescribeRegions
```

## Common Failure Patterns

### "DependencyViolation" errors

| Resource Being Deleted | Must First Delete/Unbind |
|------------------------|-------------------------|
| VPC | All vSwitches, NAT Gateways, Network ACLs, HaVips, DHCP Options |
| vSwitch | All running ECS/instances, HaVips |
| NAT Gateway | All SNAT entries, DNAT entries, FULLNAT entries, unbind EIPs |
| Network ACL | Unassociate from all vSwitches |
| EIP | Unbind from target resource |

### Region Mismatch

VPC resources are region-scoped. Verify all related resources (VPC, vSwitch, NAT Gateway, EIP) are in the same `RegionId`.

### CIDR Conflicts

```bash
# Check for overlapping CIDRs
aliyun vpc DescribeVpcs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --output cols=VpcId,CidrBlock rows=Vpcs.Vpc[].{VpcId:VpcId,CidrBlock:CidrBlock}
```
