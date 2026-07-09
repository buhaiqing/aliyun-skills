# VPC Core Concepts

> **Purpose:** Architecture, limits, regions, quotas, and fundamental VPC resource relationships.

## Architecture

VPC is a logically isolated network in the cloud. Define your own IP range, subnets (vSwitches), route tables, and gateways.

### Resource Hierarchy

```
VPC
├── vSwitch (subnet) — hosts ECS/RDS/etc
├── RouteTable — system + custom routes
├── NAT Gateway — SNAT (outbound) + DNAT (inbound)
├── Network ACL (L3 firewall) — inbound + outbound rules
├── IPv6 Gateway
├── DHCP Options Set
└── FlowLog (traffic capture)

Region-level: EIP, VPN Gateway, Customer Gateway, HaVip, CommonBandwidthPackage
```

### Resource Relationships

- **VPC** = 1 region; **vSwitch** = 1 VPC + 1 AZ
- **NAT Gateway** = 1 VPC; Enhanced NAT requires a vSwitch
- **EIP** = region-level; bindable to ECS/NAT/SLB/HaVip/ENI
- **Route Table** = 1 VPC, multi-vSwitch
- **Network ACL** = 1 VPC, multi-vSwitch
- **VPN Gateway** = 1 VPC

## CIDR Block Constraints

| Parameter | Constraint |
|-----------|------------|
| VPC IPv4 CIDR | 10.0.0.0/8 (prefix 16-28), 172.16.0.0/12 (prefix 16-28), 192.168.0.0/16 (prefix 16-28) |
| vSwitch CIDR | Subset of VPC CIDR; mask ≥ /19 |
| Overlap | Same-region VPCs **cannot** overlap |
| Modification | **Not supported** after creation; use `AssociateVpcCidrBlock` for secondary CIDR |

## Quotas (Default Limits — verify via CLI)

```bash
# VPCs per region: 10 | vSwitches per VPC: 24 | Route tables per VPC: 20
# Routes per table: 70 | EIPs per region: 20 | NAT GWs per VPC: 10
# SNAT entries: 200 | DNAT entries: 200 | VPN GWs per VPC: 10
# Network ACLs per VPC: 50 | ACL rules: 64 | FlowLogs per VPC/vSwitch: 25

# Check actual usage
aliyun vpc DescribeVpcs --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --output cols=VpcId,VpcName rows=Vpcs.Vpc[]
aliyun vpc DescribeEipAddresses --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --output cols=AllocationId rows=EipAddresses.EipAddress[]
aliyun vpc DescribeNatGateways --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --output cols=NatGatewayId rows=NatGateways.NatGateway[]
```

## Region and AZ

- VPC products are region-scoped.
- Check available zones: `aliyun vpc DescribeZones --RegionId <region>`

## Billing Overview

| Resource | Billing | Notes |
|----------|---------|-------|
| VPC/vSwitch/SNAT/DNAT/Network ACL/FlowLog | Free | |
| NAT Gateway (Enhanced) | Instance + CU fee | PayBySpec or PayByActualUsage |
| EIP | Instance + bandwidth fee | PayByBandwidth or PayByTraffic |
| VPN Gateway | Instance + bandwidth fee | |
| Common Bandwidth Package | Instance + bandwidth fee | Cost-effective for multi-EIP |

## Lifecycle Dependencies

**Create:** VPC → vSwitch → NAT Gateway → EIP → SNAT/DNAT → Deploy resources
**Delete:** SNAT/DNAT → EIPs (unbind first) → NAT → vSwitches → VPC
