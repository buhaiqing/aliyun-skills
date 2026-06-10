# VPC Troubleshooting Guide

> **Purpose:** VPC error codes, diagnostic steps, and solutions.

## Quick Diagnostic Commands

```bash
# Check resource existence and status
aliyun vpc DescribeVpcs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpcId {{user.vpc_id}}
aliyun vpc DescribeVSwitches --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VSwitchId {{user.vswitch_id}}
aliyun vpc DescribeNatGateways --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}
aliyun vpc DescribeEipAddresses --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}}
aliyun vpc DescribeRouteTables --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --RouteTableId {{user.route_table_id}}
aliyun vpc DescribeNetworkAcls --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NetworkAclId {{user.network_acl_id}}
aliyun vpc DescribeVpnGateways --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --VpnGatewayId {{user.vpn_gateway_id}}
aliyun vpc DescribeDhcpOptionsSets --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --DhcpOptionsSetId {{user.dhcp_options_set_id}}
aliyun vpc DescribeHaVips --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --HaVipId {{user.ha_vip_id}}
aliyun vpc DescribeFlowLogs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --FlowLogId {{user.flow_log_id}}
aliyun vpc DescribeSnatTableEntries --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}
aliyun vpc DescribeForwardTableEntries --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}
aliyun vpc DescribeRegions
```

## Common API Error Codes

| Error Code | Agent Action |
|------------|-------------|
| `InvalidVpcId.NotFound` (404) | Verify VpcId and region |
| `InvalidVSwitchId.NotFound` (404) | Verify VSwitchId and region |
| `InvalidCidrBlock` (400) | Use 10.0.0.0/8, 172.16.0.0/12, or 192.168.0.0/16 |
| `InvalidNatGatewayId.NotFound` (404) | Verify NatGatewayId |
| `DependencyViolation` (400) | Delete associated resources first |
| `QuotaExceeded` (400) | Delete unused resources or request increase |
| `Forbidden.RAM` (403) | Add `AliyunVPCFullAccess` policy |
| `InsufficientBalance` (400) | HALT; user recharges |
| `Throttling.User` (429) | Retry with exponential backoff |
| `InternalError` (500) | Retry 3x; escalate with RequestId |
| `InvalidEipStatus` (400) | Check current EIP status |
| `OperationDenied` (400) | Check resource lock or deletion protection |
| `VrouterEntryConflictError` | 400 | Route entry conflicts — remove conflicting route before adding |
| `RouteTableNotSupport` | 400 | Route table doesn't support operation — check type and associations |

## Dependency Violations

| Resource Being Deleted | Must First Delete/Unbind |
|------------------------|-------------------------|
| VPC | vSwitches, NAT Gateways, Network ACLs, HaVips, DHCP Options |
| vSwitch | Running ECS/instances, HaVips |
| NAT Gateway | SNAT + DNAT + FULLNAT entries, unbind EIPs |
| Network ACL | Unassociate from all vSwitches |
| EIP | Unbind from target resource |

## CIDR Conflicts

```bash
aliyun vpc DescribeVpcs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --output cols=VpcId,CidrBlock rows=Vpcs.Vpc[].{VpcId:VpcId,CidrBlock:CidrBlock}
```

## Diagnostic Order

1. **Verify resource exists:** Describe operation with resource ID
2. **Check resource status:** Must be appropriate state for the operation
3. **Verify region:** All related resources must be in the same region
4. **Check CIDR overlap:** VPCs cannot have overlapping CIDRs in the same region
5. **Check dependencies:** Many operations require child resources to be deleted first
6. **Verify quota:** List resources and compare against default limits
7. **Check RAM:** Ensure `AliyunVPCFullAccess` or equivalent policy

## Common Scenarios

### VPC Deletion Fails

Symptoms: `DeleteVpc` fails with `DependencyViolation`

1. List vSwitches: `aliyun vpc DescribeVSwitches --VpcId <id>` → delete each
2. List NAT Gateways: `aliyun vpc DescribeNatGateways --VpcId <id>` → delete each (delete SNAT/DNAT first)
3. List Network ACLs: `aliyun vpc DescribeNetworkAcls` → unassociate and delete
4. List HaVips: `aliyun vpc DescribeHaVips --VpcId <id>` → delete
5. List DHCP Options: `aliyun vpc DescribeDhcpOptionsSets` → detach
6. Retry VPC deletion

### EIP Association Fails

Symptoms: `AssociateEipAddress` returns error

1. Check EIP status — must be `Available`
2. Check target instance exists in same region
3. Check InstanceType matches resource type
4. Verify RAM permissions

### vSwitch Creation Fails

Symptoms: `CreateVSwitch` returns error

1. Verify VPC exists and is `Available`
2. Check vSwitch CIDR is subset of VPC CIDR
3. Check ZoneId is valid for the region
4. Check vSwitch quotas (24 max per VPC)
5. Verify CIDR mask length ≥ /19

### NAT Gateway Cannot Be Deleted

Symptoms: `DeleteNatGateway` returns `DependencyViolation`

1. Delete all SNAT entries first
2. Delete all DNAT entries first
3. Delete all FULLNAT entries first
4. Unbind all associated EIPs
5. Retry deletion
