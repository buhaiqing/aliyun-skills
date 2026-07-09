# 执行命令清单 (CLI-Only)

本 Skill 仅使用 `aliyun` CLI 进行数据采集。以下为各阶段执行的标准命令：

## 1. VPC 基础网络
- `aliyun vpc DescribeVpcs --RegionId $REGION_ID`
- `aliyun vpc DescribeVSwitches --RegionId $REGION_ID --VpcId $VPC_ID`

## 2. 负载均衡与公网入口
- `aliyun slb DescribeLoadBalancers --RegionId $REGION_ID --PageSize 100`
- `aliyun vpc DescribeEipAddresses --RegionId $REGION_ID --PageSize 50`
- `aliyun vpc DescribeNatGateways --RegionId $REGION_ID --PageSize 50`

## 3. 核心组件资源 (详细模式)
- `aliyun ecs DescribeInstances --RegionId $REGION_ID --PageSize 100`
- `aliyun rds DescribeDBInstances --RegionId $REGION_ID --PageSize 100`
- `aliyun cs DescribeClustersV1 --page_size 50`
- `aliyun ecs DescribeSecurityGroups --RegionId $REGION_ID --PageSize 100`

## JSON 输出路径映射

| 资源 | JSON Path |
|------|-----------|
| VPC ID | `$.Vpcs.Vpc[0].VpcId` |
| VSwitch ID | `$.VSwitches.VSwitch[].VSwitchId` |
| SLB Name | `$.LoadBalancers.LoadBalancer[].LoadBalancerName` |
| EIP IP | `$.EipAddresses.EipAddress[].IpAddress` |
| ECS IP | `$.Instances.Instance[].VpcAttributes.PrivateIpAddress.IpAddress[0]` |
| RDS Name | `$.Items.DBInstance[].DBInstanceDescription` |
| ACK Name | `$.clusters[].name` |

> 所有命令默认输出 JSON，无需 `--output json` 参数。
