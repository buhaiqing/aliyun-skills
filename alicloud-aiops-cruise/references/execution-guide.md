# CLI 命令执行指南

> 阿里云全链路巡检涉及的 aliyun CLI 命令速查。
> 所有命令均为只读（Describe/List/Get），不含任何写操作。

## [NOTE] 使用说明

> 本文件不是 SKILL.md 的替代，而是 Agent 在执行巡检时的 CLI 命令速查表。
> SKILL.md 描述"做什么"，本文件提供"How to do"——具体的参数和常见踩坑点。
>
> **关键原则**：
> 1. 所有命令先加 `--PageSize 100` 避免分页遗漏
> 2. 复杂 JSON 输出用 `jq` 过滤——不要直接输出全量 JSON（Token 爆炸）
> 3. 监控指标的时间窗口用 `date` 计算，不要硬编码

---

## 资源组（推荐扫描方式）

> 阿里云资源组（ResourceGroup）是云资源管理的**原生单位**，比标签更可靠：
> - 每个资源**一定**属于某个资源组（即使未指定也属于"默认资源组"）
> - 标签可能漏打，但资源组一定存在
> - 推荐优先使用资源组扫描，标签作为回退方案
>
> **[ALERT] 铁律：默认资源组自动禁用资源组模式**
> 自动跳过 default/空资源组，转为标签通道。除非用户明确输入 `scope=full`，
> 否则禁止按默认资源组扫描（防止意外全账号扫描，违反 Safety Gate）。

### 资源组支持度矩阵

| 产品 | `--ResourceGroupId` 参数 | 响应中包含 `ResourceGroupId` | 推荐方式 |
|---|---|---|---|
| ECS | PASS 原生支持 | PASS | `aliyun ecs DescribeInstances --ResourceGroupId` |
| RDS | PASS 原生支持 | PASS | `aliyun rds DescribeDBInstances --ResourceGroupId` |
| NAT | PASS 原生支持 | PASS | `aliyun vpc DescribeNatGateways --ResourceGroupId` |
| SLB | FAIL 不支持 | PASS | 全量拉取后 `jq --arg rg ... select(.ResourceGroupId == $rg)` |
| Redis | FAIL 不支持 | PASS | 全量拉取后 `jq` 筛选 |
| VPC | FAIL 不支持 | PASS | 全量拉取后 `jq` 筛选 |
| 安全组 | FAIL 不支持 | PASS | 全量拉取后 `jq` 筛选 |
| EIP | FAIL 不支持 | PASS | 全量拉取后 `jq` 筛选 |
| ACK | FAIL 不支持 | FAIL (无此字段) | 按其他维度过滤 |

### 从某个资源ID反查所属资源组

```bash
# 给定任意资源ID，自动判断类型并反查 ResourceGroupId
RESOURCE_ID="rm-bp180t670128318su"

case "${RESOURCE_ID:0:2}" in
  i-)
    aliyun ecs DescribeInstances --RegionId "$REGION" \
      --InstanceIds "[\"$RESOURCE_ID\"]" | jq -r '.Instances.Instance[0].ResourceGroupId' ;;
  rm-|pgm-)
    aliyun rds DescribeDBInstances --RegionId "$REGION" \
      --DBInstanceId "$RESOURCE_ID" | jq -r '.Items.DBInstance[0].ResourceGroupId' ;;
  r-)
    aliyun r-kvstore DescribeInstances --RegionId "$REGION" | jq -r \
      --arg id "$RESOURCE_ID" '.Instances.KVStoreInstance[] | select(.InstanceId==$id) | .ResourceGroupId' ;;
  lb-)
    aliyun slb DescribeLoadBalancers --RegionId "$REGION" | jq -r \
      --arg id "$RESOURCE_ID" '.LoadBalancers.LoadBalancer[] | select(.LoadBalancerId==$id) | .ResourceGroupId' ;;
  ngw-)
    aliyun vpc DescribeNatGateways --RegionId "$REGION" \
      --NatGatewayId "$RESOURCE_ID" | jq -r '.NatGateways.NatGateway[0].ResourceGroupId' ;;
  eip-)
    aliyun vpc DescribeEipAddresses --RegionId "$REGION" \
      --AllocationId "$RESOURCE_ID" | jq -r '.EipAddresses.EipAddress[0].ResourceGroupId' ;;
  vpc-)
    aliyun vpc DescribeVpcs --RegionId "$REGION" --VpcId "$RESOURCE_ID" \
      | jq -r '.Vpcs.Vpc[0].ResourceGroupId' ;;
  *)
    echo "未知资源类型" ;;
esac
```

### 按资源组批量扫描

```bash
RG_ID="rg-acfmvyfsd4znnoi"

# 支持原生过滤的产品（ECS/RDS/NAT）
aliyun ecs DescribeInstances --RegionId "$REGION" --ResourceGroupId "$RG_ID" --PageSize 100
aliyun rds DescribeDBInstances --RegionId "$REGION" --ResourceGroupId "$RG_ID" --PageSize 100
aliyun vpc DescribeNatGateways --RegionId "$REGION" --ResourceGroupId "$RG_ID"

# 不支持原生过滤的产品（SLB/Redis/VPC/EIP/安全组）—— 全量拉取后 jq 筛选
aliyun slb DescribeLoadBalancers --RegionId "$REGION" --PageSize 100 \
  | jq --arg rg "$RG_ID" '.LoadBalancers.LoadBalancer[] | select(.ResourceGroupId == $rg)'

aliyun r-kvstore DescribeInstances --RegionId "$REGION" --PageSize 100 \
  | jq --arg rg "$RG_ID" '.Instances.KVStoreInstance[] | select(.ResourceGroupId == $rg)'
```

---

## 前置准备

```bash
# 时间计算（macOS `date -v+/-` 兼容 Linux `date -d`）
# 建议优先使用 macOS 格式，Agent 可自动适配
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START_TIME_SIX_HOURS=$(date -u -v-6H +%Y-%m-%dT%H:%M:%SZ)  # 6小时前

# 昨日同期
YESTERDAY_START=$(date -u -v-30H +%Y-%m-%dT%H:%M:%SZ)
YESTERDAY_END=$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)
```

## ECS

```bash
# 列出实例
aliyun ecs DescribeInstances \
  --RegionId "$REGION" \
  --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" \
  --PageSize 100 \
  | jq '.Instances.Instance[] | {InstanceId, InstanceName, InstanceType, Status, Tags}'

# 查询实例详情
aliyun ecs DescribeInstanceAttribute \
  --RegionId "$REGION" \
  --InstanceId "i-xxx" \
  | jq '. | {InstanceId, InstanceName, InstanceType, Memory, Cpu, VpcAttributes, Tags}'
```

## SLB

```bash
# 列出 SLB
aliyun slb DescribeLoadBalancers \
  --RegionId "$REGION" \
  --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" \
  --PageSize 100 \
  | jq '.LoadBalancers.LoadBalancer[] | {LoadBalancerId, LoadBalancerName, Address, LoadBalancerSpec, Bandwidth}'

# 查询后端服务器组
aliyun slb DescribeVServerGroups \
  --RegionId "$REGION" \
  --LoadBalancerId "lb-xxx" \
  | jq '.VServerGroups.VServerGroup[] | {VServerGroupId, VServerGroupName}'

# 查询健康状态
aliyun slb DescribeHealthStatus \
  --RegionId "$REGION" \
  --LoadBalancerId "lb-xxx" \
  | jq '.BackendServers.BackendServer[] | {ServerId, Port, ServerHealthStatus}'
```

## VPC / EIP / NAT

```bash
# VPC 列表
aliyun vpc DescribeVpcs --RegionId "$REGION" --PageSize 50 \
  | jq '.Vpcs.Vpc[] | {VpcId, VpcName, CidrBlock, VSwitchIds}'

# vSwitch 列表
aliyun vpc DescribeVSwitches --RegionId "$REGION" --VpcId "vpc-xxx" \
  | jq '.VSwitches.VSwitch[] | {VSwitchId, VSwitchName, CidrBlock, ZoneId, AvailableIpAddressCount}'

# EIP 列表
aliyun vpc DescribeEipAddresses --RegionId "$REGION" --PageSize 50 \
  | jq '.EipAddresses.EipAddress[] | {AllocationId, EipAddress, Bandwidth, InstanceId, InstanceType, Status}'

# NAT 网关
aliyun vpc DescribeNatGateways --RegionId "$REGION" --PageSize 50 \
  | jq '.NatGateways.NatGateway[] | {NatGatewayId, Name, Spec, Status, SnatTableIds}'

# NAT SNAT 列表
aliyun vpc DescribeSnatTableEntries --RegionId "$REGION" --SnatTableId "stb-xxx" \
  | jq '.SnatTableEntries.SnatTableEntry[] | {SnatEntryId, SnatIp, SourceCIDR, Status}'
```

## RDS

```bash
# 列出 RDS 实例
aliyun rds DescribeDBInstances \
  --RegionId "$REGION" \
  --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" \
  --PageSize 100 \
  | jq '.Items.DBInstance[] | {DBInstanceId, DBInstanceDescription, DBInstanceClass, Engine, EngineVersion, DBInstanceStorage, DBInstanceStatus}'

# RDS 性能数据
aliyun rds DescribeDBInstancePerformance \
  --RegionId "$REGION" \
  --DBInstanceId "rm-xxx" \
  --Key "MySQL_CpuUsage,MySQL_IOPS,MySQL_Connections" \
  --StartTime "$START_TIME_SIX_HOURS" \
  --EndTime "$END_TIME"
```

## Redis

```bash
# 列出 Redis 实例
aliyun r-kvstore DescribeInstances \
  --RegionId "$REGION" \
  --Tag.1.Key "customer" --Tag.1.Value "$CUSTOMER" \
  --PageSize 100 \
  | jq '.Instances.KVStoreInstance[] | {InstanceId, InstanceName, InstanceClass, ConnectionDomain, Bandwidth, Connections}'
```

## ACK

```bash
# 列出 ACK 集群
aliyun cs DescribeClustersV1 --page_size 50 \
  | jq '.clusters[] | {cluster_id, name, cluster_type, state, node_count}'

# 查询集群详情（如果 cluster_id 已知）
aliyun cs DescribeClusterDetail --ClusterId "c-xxx" \
  | jq '. | {cluster_id, name, cluster_type, current_version, state}'
```

## CloudMonitor

```bash
# 通用格式：查询某个 Namespace 下的指标
aliyun cms DescribeMetricList \
  --Namespace "acs_ecs_dashboard" \         # ECS: acs_ecs_dashboard, SLB: acs_slb_dashboard
  --MetricName "CPUUtilization" \            # RDS: acs_rds_dashboard, Redis: acs_redis_dashboard
  --Dimensions '[{"instanceId":"i-xxx"}]' \  # NAT: acs_nat_gateway
  --Period 300 \                              # 300=5min, 60=1min, 3600=1h
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  | jq '.Datapoints | fromjson | [{"timestamp": .Timestamp, "average": .Average, "maximum": .Maximum}]'

# CloudMonitor 常用 Namespace 速查
# ECS:      acs_ecs_dashboard       (CPUUtilization, memory_usage(需agent), DiskReadIOPS, DiskWriteIOPS, InternetInRate, InternetOutRate, TcpConnection)
# SLB:      acs_slb_dashboard       (UnhealthyServerCount, ActiveConnection, NewConnection)
# RDS:      acs_rds_dashboard       (CpuUsage, ConnectionUsage, DiskUsage, IOPSUsage, SlowQueryCount)
# Redis:    acs_redis_dashboard     (memory_usage, UsedConnection, IntranetInRatio, CpuUsage)
# EIP:      acs_vpc_eip             (net_in.rate_percentage 入带宽使用率, net_out.rate_percentage 出带宽使用率)
# NAT:      acs_nat_gateway          (SnatConnection, EniSessionActiveConnection, EniPacketsDropPortAllocationFail)
```

## ActionTrail

```bash
# 查询近期操作事件（常用于故障排查：检查是否有人改过配置）
aliyun actiontrail LookupEvents \
  --StartTime "$(date -u -v-6H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --MaxResults 50 \
  | jq '.Events[] | {EventTime, EventName, EventSource, UserIdentity: .UserIdentity.UserName, ResourceName: .Resources[0].ResourceName, RequestParameters: .RequestParameters}'
```

## EIP (弹性公网 IP)

```bash
# EIP 带宽使用率（百分比）—— 注意 Datapoints 是 JSON 字符串，需 fromjson 解析
# 入方向
EIP_ID="eip-xxx"
aliyun cms DescribeMetricList \
  --Namespace acs_vpc_eip \
  --MetricName net_in.rate_percentage \
  --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
  --Period 3600 \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  | jq '.Datapoints | fromjson | [.[].Maximum] | max // "NODATA"'

# 出方向
EIP_ID="eip-xxx"
aliyun cms DescribeMetricList \
  --Namespace acs_vpc_eip \
  --MetricName net_out.rate_percentage \
  --Dimensions "[{\"instanceId\":\"$EIP_ID\"}]" \
  --Period 3600 \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  | jq '.Datapoints | fromjson | [.[].Maximum] | max // "NODATA"'
```

## NAT 网关

```bash
# SNAT 连接数（查 7 天趋势，因为 SNAT 变化慢）
NAT_ID="ngw-xxx"
aliyun cms DescribeMetricList \
  --Namespace acs_nat_gateway \
  --MetricName SnatConnection \
  --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
  --Period 3600 \
  --StartTime "$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)" --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  | jq '.Datapoints | fromjson | [.[].Maximum] | max // "NODATA"'

# 端口分配失败（关键指标：>0 说明出现过 SNAT 端口耗尽）
aliyun cms DescribeMetricList \
  --Namespace acs_nat_gateway \
  --MetricName EniPacketsDropPortAllocationFail \
  --Dimensions "[{\"instanceId\":\"$NAT_ID\"}]" \
  --Period 3600 \
  --StartTime "$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)" --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  | jq '.Datapoints | fromjson | [.[].Maximum] | max // 0'
```

## CloudAssistant

```bash
# 步骤1: 创建命令
CMD_ID=$(aliyun ecs RunCommand \
  --RegionId "$REGION" \
  --Name "cruise-diag-$(date +%s)" \
  --CommandContent "$(echo '#!/bin/bash
echo "===TOP CPU==="; ps aux --sort=-%cpu | head -5
echo "===DISK==="; df -h /
echo "===MEMORY==="; free -h
echo "===PORTS==="; ss -tlnp | head -20' | base64)" \
  --Type RunShellScript \
  --InstanceId "[\"i-xxx\"]" \
  --Timeout 30)

CMD_ID=$(echo "$CMD_ID" | jq -r '.CommandId')

# 步骤2: 轮询结果（等 5 秒）
sleep 5

# 步骤3: 获取结果
aliyun ecs DescribeInvocationResults \
  --RegionId "$REGION" \
  --InstanceId "i-xxx" \
  --CommandId "$CMD_ID" \
  | jq -r '.Invocation.InvocationResults.InvocationResult[0].Output // ""' \
  | base64 -d 2>/dev/null

# 步骤4: 清理命令（可选，保留24h自动清理）
```

## ResourceCenter

```bash
# 跨产品资源搜索（需要先安装插件：aliyun plugin install --names aliyun-cli-resourcecenter）
aliyun resourcecenter SearchResources \
  --Filter.1.Key "TagKey" --Filter.1.Value "customer" \
  --Filter.2.Key "TagValue" --Filter.2.Value "烟台振华" \
  | jq '.Resources[] | {ResourceId, ResourceType, RegionId, CreateTime, ZoneId, Tags}'
```