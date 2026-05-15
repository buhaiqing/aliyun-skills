# Prompt Examples — VPC Operations

> **Purpose:** Natural language prompts that should trigger the VPC skill.

## VPC Lifecycle

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 1 | "创建一个VPC，网段192.168.0.0/16" | CreateVpc --CidrBlock 192.168.0.0/16 |
| 2 | "Create a VPC in cn-hangzhou" | CreateVpc --RegionId cn-hangzhou |
| 3 | "列出所有VPC" | DescribeVpcs |
| 4 | "查看VPC [vpc-id] 的详细信息" | DescribeVpcs --VpcId |
| 5 | "删除这个VPC" | DeleteVpc (with safety gate checks) |

## vSwitch Management

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 6 | "在VPC里创建一个交换机" | CreateVSwitch |
| 7 | "Create vSwitch in zone cn-hangzhou-b" | CreateVSwitch --ZoneId cn-hangzhou-b |
| 8 | "查看VPC里有多少个交换机" | DescribeVSwitches --VpcId |
| 9 | "删除这个交换机" | DeleteVSwitch |

## RouteTable

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 10 | "查看VPC的路由表" | DescribeRouteTables |
| 11 | "把自定义路由表关联到vSwitch" | AssociateRouteTable |
| 12 | "解除路由表关联" | UnassociateRouteTable |

## NAT Gateway

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 13 | "创建一个增强型NAT网关" | CreateNatGateway --NatType Enhanced |
| 14 | "给NAT配置SNAT" | CreateSnatEntry |
| 15 | "配置DNAT端口映射" | CreateForwardEntry |
| 16 | "查看NAT网关的SNAT条目" | DescribeSnatTableEntries |
| 17 | "删除NAT网关" | DeleteNatGateway (delete entries first) |

## EIP Operations

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 18 | "申请一个弹性公网IP" | AllocateEipAddress |
| 19 | "绑定EIP到ECS" | AssociateEipAddress |
| 20 | "解绑EIP" | UnassociateEipAddress |
| 21 | "查看所有EIP" | DescribeEipAddresses |
| 22 | "释放EIP" | ReleaseEipAddress |
| 23 | "给EIP加带宽" | ModifyEipAddressAttribute --Bandwidth |

## VPN & IPsec

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 24 | "创建VPN网关" | CreateVpnGateway |
| 25 | "查看VPN网关状态" | DescribeVpnGateways |
| 26 | "删除VPN网关" | DeleteVpnGateway |

## Network ACL

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 27 | "创建网络ACL" | CreateNetworkAcl |
| 28 | "关联ACL到vSwitch" | AssociateNetworkAcl |
| 29 | "查看网络ACL规则" | DescribeNetworkAcls |
| 30 | "删除网络ACL" | DeleteNetworkAcl |

## FullStack Provisioning

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 31 | "帮我把整个网络打通" | VPC → vSwitch → NAT → EIP → SNAT |
| 32 | "Create a complete VPC stack with NAT and EIP" | CreateVpc → CreateVSwitch → CreateNatGateway → AllocateEipAddress → BindEip → CreateSnatEntry |
| 33 | "查看我这个VPC下有多少资源" | DescribeVSwitches, DescribeNatGateways, DescribeEipAddresses |
| 34 | "清理整个VPC环境" | Delete SNAT → DNAT → EIPs → NAT → vSwitches → VPC |

## Negative: Should NOT Trigger

| # | User Prompt | Should Delegate To |
|---|-------------|-------------------|
| 1 | "启动ECS实例" | `alicloud-ecs-ops` |
| 2 | "创建RDS数据库" | `alicloud-rds-ops` |
| 3 | "启动Redis" | `alicloud-redis-ops` |
| 4 | "创建SLB负载均衡" | `alicloud-slb-ops` |
| 5 | "创建ACK集群" | `alicloud-ack-ops` |
| 6 | "查看账单" | `alicloud-billing-ops` |
