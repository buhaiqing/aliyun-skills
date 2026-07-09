# Prompt Examples — EIP Operations

> **Purpose:** Natural language prompts that should trigger the EIP skill. Each example corresponds to a real user query scenario.

## Allocation & Creation

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 1 | "帮我申请一个弹性公网IP" | AllocateEipAddress with default settings |
| 2 | "Create a new EIP with 20Mbps bandwidth" | AllocateEipAddress --Bandwidth 20 |
| 3 | "给生产环境申请一个按流量计费的公网IP，带宽100M" | AllocateEipAddress --InternetChargeType PayByTraffic --Bandwidth 100 |
| 4 | "Allocate 3 EIPs for high availability setup" | AllocateEipAddress x3 |

## Binding & Unbinding

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 5 | "把EIP [eip-id] 绑定到 ECS [instance-id]" | AssociateEipAddress --InstanceType EcsInstance |
| 6 | "Bind this elastic IP to my NAT gateway" | AssociateEipAddress --InstanceType Nat |
| 7 | "解绑这台ECS的公网IP" | UnassociateEipAddress after describing current EIP |
| 8 | "把这个EIP从SLB上解下来" | UnassociateEipAddress --InstanceType SLBInstance |

## Bandwidth & Billing

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 9 | "把EIP带宽升级到100M" | ModifyEipAddressAttribute --Bandwidth 100 |
| 10 | "Switch EIP billing from PayByBandwidth to PayByTraffic" | ModifyEipAddressAttribute --InternetChargeType PayByTraffic |
| 11 | "EIP带宽降到了5M" | ModifyEipAddressAttribute --Bandwidth 5 |
| 12 | "查看EIP [eip-id] 的详细信息" | DescribeEipAddresses --AllocationId |

## Listing & Discovery

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 13 | "列出所有可用的弹性公网IP" | DescribeEipAddresses --Status Available |
| 14 | "查看当前有多少个公网IP" | DescribeEipAddresses --PageSize |
| 15 | "哪些EIP已经绑定了资源？" | DescribeEipAddresses --Status InUse |
| 16 | "Show me all EIPs with their bandwidth" | DescribeEipAddresses with JMESPath |
| 17 | "Check if EIP is bound to NAT Gateway" | DescribeEipAddresses --AllocationId |

## Release

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 18 | "释放这个不用的EIP" | ReleaseEipAddress (with safety gate confirmation) |
| 19 | "Release all unused EIPs" | DescribeEipAddresses --Status Available, then Release |
| 20 | "删除这个公网IP，先解绑再释放" | Unassociate + Release |

## Bandwidth Plans

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 21 | "创建一个共享带宽包" | CreateCommonBandwidthPackage |
| 22 | "Add this EIP to the bandwidth plan" | AddCommonBandwidthPackageIp |
| 23 | "查看带宽包里有多少EIP" | DescribeCommonBandwidthPackages |
| 24 | "从带宽包中移除EIP" | RemoveCommonBandwidthPackageIp |

## Troubleshooting

| # | User Prompt | Expected Action |
|---|-------------|-----------------|
| 25 | "EIP绑定失败，什么原因？" | Diagnose: check status, quota, region, RAM |
| 26 | "公网IP绑上了但是访问不了" | Check SecurityGroup, bandwidth, billing |
| 27 | "EIP quota exceeded怎么办" | DescribeEipAddresses, suggest unused deletions |
| 28 | "为什么EIP解绑后还是扣费？" | Explain billing for retained EIPs |
| 29 | "带宽打满了，怎么快速扩容？" | ModifyEipAddressAttribute --Bandwidth |
| 30 | "这个EIP能不能直接释放？" | Check Status; if InUse, must unbind first |

## Negative: Should NOT Trigger

| # | User Prompt | Should Delegate To |
|---|-------------|-------------------|
| 1 | "Create a NAT Gateway" | `alicloud-nat-ops` |
| 2 | "Create a new VPC" | `alicloud-vpc-ops` |
| 3 | "Start my ECS instance" | `alicloud-ecs-ops` |
| 4 | "Check my account balance" | `alicloud-billing-ops` |
| 5 | "Create a load balancer" | `alicloud-slb-ops` |
| 6 | "Configure RAM permissions" | `alicloud-ram-ops` |
