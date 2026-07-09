# Prompt Examples — NAT Operations

> **Purpose:** Natural language prompts that should trigger the NAT skill.

## NAT Gateway Creation

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 1 | "帮我创建一个NAT网关" | CreateNatGateway — prompt for VPC/vSwitch |
| 2 | "Create an enhanced NAT gateway in VPC vpc-xxx" | CreateNatGateway --NatType Enhanced |
| 3 | "给VPC创建一个增强型NAT，交换机选择vsw-xxx" | CreateNatGateway --NatType Enhanced --VSwitchId |
| 4 | "Create a NAT Gateway with PayByActualUsage billing" | CreateNatGateway --BillingMethod PayByActualUsage |

## SNAT (Outbound Internet Access)

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 5 | "给NAT配置SNAT，让10.0.1.0/24的机器能上网" | CreateSnatEntry --SourceCIDR 10.0.1.0/24 |
| 6 | "Configure SNAT for the whole vSwitch" | CreateSnatEntry --VSwitchId |
| 7 | "Add another EIP to the existing SNAT" | CreateSnatEntry with new SnatIp |
| 8 | "删除SNAT条目" | DeleteSnatEntry |
| 9 | "查看所有SNAT配置" | DescribeSnatTableEntries |

## DNAT (Inbound Port Mapping)

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 10 | "配置DNAT，把公网的8080端口映射到10.0.1.5的80" | CreateForwardEntry TCP 8080→80 |
| 11 | "Create a DNAT for SSH access on port 22 to internal 10.0.1.10:22" | CreateForwardEntry TCP 22→22 |
| 12 | "把443端口映射到内网服务器" | CreateForwardEntry TCP 443→443 |
| 13 | "查看所有DNAT条目" | DescribeForwardTableEntries |
| 14 | "删除DNAT映射" | DeleteForwardEntry |

## FullNAT

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 15 | "创建FULLNAT条目" | CreateFullNatEntry |
| 16 | "查看FULLNAT配置" | DescribeFullNatEntries |
| 17 | "删除FULLNAT" | DeleteFullNatEntry |

## Listing & Discovery

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 18 | "列出所有NAT网关" | DescribeNatGateways |
| 19 | "查看NAT网关 [nat-id] 的详细信息" | DescribeNatGateways --NatGatewayId |
| 20 | "这个NAT网关有多少SNAT条目？" | DescribeSnatTableEntries + count |
| 21 | "Check how many DNAT rules are configured" | DescribeForwardTableEntries + count |

## Modification

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 22 | "修改NAT网关名称" | ModifyNatGatewayAttribute --Name |
| 23 | "升级NAT网关规格" | ModifyNatGatewaySpec |
| 24 | "Change NAT billing to PayByActualUsage" | ModifyNatGatewaySpec --BillingMethod |

## Release

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 25 | "删除NAT网关" | Delete NAT (with safety gate: delete SNAT/DNAT/FullNat first) |
| 26 | "释放这个NAT，先清理所有SNAT和DNAT" | Delete entries, then DeleteNatGateway |

## Troubleshooting

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 27 | "SNAT配置了但内网机器上不了网" | Diagnose: SNAT entry, EIP status, security group, routing |
| 28 | "DNAT端口映射不通" | Check: DNAT entry, protocol match, ECS firewall, security group |
| 29 | "NAT网关删不掉" | Check: SNAT/DNAT/FullNat entries still exist |
| 30 | "为什么NAT关联的EIP解绑不了？" | Check: EIP is SNAT/DNAT source IP |
| 31 | "NAT连接数满了怎么办？" | Explain: Add more EIPs for SNAT capacity, each EIP ≈ 30K connections |
| 32 | "SNAT能同时访问互联网的最大并发是多少？" | Explain: ~30K per EIP, scale by adding EIPs |

## Negative: Should NOT Trigger

| # | User Prompt | Should Delegate To |
|---|-------------|-------------------|
| 1 | "Allocate a new EIP" | `alicloud-eip-ops` |
| 2 | "Create a VPC" | `alicloud-vpc-ops` |
| 3 | "Start an ECS instance" | `alicloud-ecs-ops` |
| 4 | "Check account balance" | `alicloud-billing-ops` |
| 5 | "Bind EIP to ECS" | `alicloud-eip-ops` |
| 6 | "Create a load balancer" | `alicloud-slb-ops` |

## FinOps — Cost Optimization

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 33 | "检查是否有闲置的NAT网关" | Scan all NAT Gateways; flag those with 0 SNAT + 0 DNAT entries |
| 34 | "NAT网关成本太高了，帮我分析优化" | Check billing mode, spec utilization, EIP waste; generate optimization report |
| 35 | "这个NAT应该用PayBySpec还是PayByActualUsage？" | Query 7-day CU utilization; recommend billing mode per decision tree |
| 36 | "帮我做NAT网关规格右调" | Query CU trend (7d); compare against spec limits; recommend upgrade/downgrade |
| 37 | "NAT关联的EIP有没有浪费？" | List EIPs on NAT; check traffic metrics; flag orphaned/low-traffic EIPs |
| 38 | "生成NAT网关月度成本优化报告" | Full FinOps scan: idle NATs, underutilized specs, billing mode fit, EIP waste, CBWP opportunity |
| 39 | "NAT成本突然涨了30%，帮我排查" | Compare MoM cost; check CU spike, EIP additions, spec changes, billing mode switch |
| 40 | "5个EIP绑在NAT上，需要用共享带宽包吗？" | Calculate individual vs CBWP cost; recommend CBWP if 3+ EIPs |

## SecurityOps — Security Audit

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 41 | "审计所有DNAT条目，检查高危端口暴露" | List all DNAT entries; flag ports 22/3306/6379/3389/27017/445/21/23 |
| 42 | "检查SNAT源CIDR是否过于宽泛" | List SNAT entries; flag SourceCIDR = 0.0.0.0/0 |
| 43 | "NAT网关安全基线检查" | Run P0 security checklist: high-risk ports, RAM scope, credential masking, SNAT scope, security groups |
| 44 | "有DNAT把22端口映射到公网了，紧急处理" | DeleteForwardEntry for port 22 DNAT; verify removal; recommend Bastion host |
| 45 | "查看NAT网关的操作审计日志" | Delegate to `alicloud-actiontrail-ops`; query NAT-related events |
| 46 | "帮我配置NAT网关的最小权限RAM策略" | Generate scoped RAM policy per security-enhancement.md templates |
| 47 | "检查DNAT是否有对应的安全组规则" | List DNAT entries → for each internal IP, check ECS security group inbound rules |
| 48 | "执行NAT网关安全巡检" | Full security scan: DNAT exposure, SNAT scope, RAM policies, credential safety, audit trail |
