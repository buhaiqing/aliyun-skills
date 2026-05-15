# VPC Core Concepts

> **Purpose:** Architecture, limits, regions, quotas, and fundamental VPC resource relationships.

## Architecture

Alibaba Cloud VPC (Virtual Private Cloud) is a logically isolated network that you can create and manage in the cloud. It enables you to define your own IP address range, subnets (vSwitches), route tables, and network gateways.

### Resource Hierarchy

```
VPC (Virtual Private Cloud)
├── vSwitch (Virtual Switch / Subnet)
│   └── ECS, RDS, and other cloud resources
├── RouteTable (Route Table)
│   ├── System route (auto-created)
│   └── Custom route (user-defined, propagated to associated vSwitches)
├── NAT Gateway
│   ├── SNAT Table (outbound internet access)
│   │   └── SNAT Entry (CIDR → EIP)
│   └── Forward Table (DNAT for inbound access)
│       └── Forward Entry (port mapping: external IP:port → internal IP:port)
├── Network ACL (optional, Layer 3 firewall)
│   ├── Inbound Rules
│   └── Outbound Rules
├── IPv6 Gateway (optional)
│   └── IPv6 Egress-Only Rules
├── DHCP Options Set (optional)
└── FlowLog (optional, network traffic capture)

├── EIP (Elastic IP Address) - region-level resource
├── VPN Gateway - region-level resource
│   ├── IPsec Connections (VPN tunnels)
│   └── BGP configuration (dynamic routing)
├── Customer Gateway (on-premise)
├── HaVip (High-Availability Virtual IP)
├── CommonBandwidthPackage (shared bandwidth for EIPs)
└── IPv6Address (IPv6 addresses for ECS instances)
```

### Resource Relationships

- A **VPC** belongs to one region. Cannot span regions.
- A **vSwitch** belongs to one VPC and one **Availability Zone**.
- **NAT Gateway** belongs to one VPC. Enhanced NAT Gateway requires a vSwitch.
- **EIP** is a region-level resource. Can be associated with ECS, NAT, SLB, HaVip, ENI.
- **Route Table** belongs to one VPC. Can be associated with multiple vSwitches.
- **Network ACL** belongs to one VPC. Can be associated with multiple vSwitches.
- **VPN Gateway** belongs to one VPC.

## CIDR Block Constraints

| Parameter | Constraint |
|-----------|------------|
| VPC IPv4 CIDR | `10.0.0.0/8` (prefix 16–28), `172.16.0.0/12` (prefix 16–28), `192.168.0.0/16` (prefix 16–28) |
| vSwitch CIDR | Must be a subset of VPC CIDR; mask length ≥ /19 |
| CIDR overlap | VPCs in the same region **cannot** have overlapping CIDRs |
| VPC CIDR modification | **Not supported** after creation; can add secondary CIDR via `AssociateVpcCidrBlock` |

## Quotas (Default Limits)

| Resource | Default Limit | Notes |
|----------|---------------|-------|
| VPCs per region | 10 | Can be increased via ticket |
| vSwitches per VPC | 24 | Dependent on instance count |
| Route tables per VPC | 20 | Custom route tables only |
| Routes per route table | 70 | Including system routes |
| EIPs per region | 20 | Can be increased |
| NAT Gateways per VPC | 10 | Enhanced type |
| SNAT entries per NAT | 200 | |
| DNAT entries per NAT | 200 | |
| VPN Gateways per VPC | 10 | |
| Network ACLs per VPC | 50 | |
| Network ACL rules | 64 | Per ACL (inbound + outbound) |
| FlowLogs per VPC/vSwitch | 25 | |

## Region and Availability Zone

- VPC products are region-scoped.
- Check available zones: `aliyun vpc DescribeZones --RegionId <region>`
- VSwitch placement requires a specific Availability Zone.

## Billing Overview

| Resource | Billing Model | Notes |
|----------|---------------|-------|
| VPC | Free | |
| vSwitch | Free | |
| NAT Gateway (Enhanced) | Instance fee (PayBySpec or PayByActualUsage) + CU fee | Enhanced NAT incurs CU charges |
| EIP | Instance fee + bandwidth fee | PayByBandwidth or PayByTraffic |
| VPN Gateway | Instance fee + bandwidth fee | |
| Common Bandwidth Package | Instance fee + bandwidth fee | Cost-effective for multiple EIPs |
| SNAT/DNAT Entry | Free | Uses NAT Gateway and EIP charges |
| Network ACL | Free | |
| FlowLog | Free | Storage depends on SLS configuration |

## Lifecycle Dependencies

When **creating** a full networking stack:
1. **VPC** (or use default) → 2. **vSwitch** (in a zone) → 3. **NAT Gateway** (if public access needed) → 4. **EIP** (for SNAT/DNAT) → 5. **SNAT/DNAT entries** → 6. **Deploy resources** in vSwitch

When **deleting** a VPC:
1. Delete SNAT → DNAT entries → 2. Release EIPs (unbind first) → 3. Delete NAT Gateway → 4. Delete vSwitches → 5. Delete VPC
