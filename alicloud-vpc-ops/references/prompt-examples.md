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

## Quick Reference (Compact)

| # | Prompt | Action |
|---|--------|--------|
| 7 | 创建 VPC，网段 192.168.0.0/16 | CreateVpc --CidrBlock 192.168.0.0/16 |
| 8 | 查看当前有多少个 VPC | DescribeVpcs |
| 9 | 删除 VPC vpc-xxx | DeleteVpc (check deps first) |
| 10 | 列出所有可用区 | DescribeZones |
| 11 | 在 VPC 里创建交换机 | CreateVSwitch |
| 12 | 查看 VPC 里有多少个交换机 | DescribeVSwitches |
| 13 | 删除交换机 vsw-xxx | DeleteVSwitch |
| 14 | 创建增强型 NAT 网关 | CreateNatGateway --NatType Enhanced |
| 15 | 查看 NAT 网关详情 | DescribeNatGateways |
| 16 | 删除 NAT 网关 | DeleteNatGateway (delete entries first) |
| 17 | 给 NAT 配置 SNAT，让 10.0.1.0/24 能上网 | CreateSnatEntry |
| 18 | 配置 DNAT，把公网 8080 映射到内网 80 | CreateForwardEntry |
| 19 | 查看 SNAT 条目 | DescribeSnatTableEntries |
| 20 | 删除 DNAT 映射 | DeleteForwardEntry |
| 21 | 申请弹性公网 IP | AllocateEipAddress |
| 22 | 绑定 EIP 到 ECS | AssociateEipAddress |
| 23 | 解绑 EIP | UnassociateEipAddress |
| 24 | 释放 EIP | ReleaseEipAddress |
| 25 | 修改 EIP 带宽 | ModifyEipAddressAttribute |
| 26 | 创建 VPN 网关 | CreateVpnGateway |
| 27 | 查看 VPN 网关状态 | DescribeVpnGateways |
| 28 | 创建网络 ACL | CreateNetworkAcl |
| 29 | 关联 ACL 到 vSwitch | AssociateNetworkAcl |
| 30 | 帮我从零创建一套网络 | VPC → vSwitch → NAT → EIP → SNAT |
| 31 | 清理整个 VPC 环境 | Delete all: SNAT/DNAT → EIPs → NAT → vSwitches → VPC |
| 32 | 收到 NAT 带宽告警，帮我诊断 | Check OutRatePercent, FlowLog, EIP usage |
| 33 | 网络不通了，帮我从 VPC 层面诊断 | Route table → NAT → ACL → FlowLog cascade |
