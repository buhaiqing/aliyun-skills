# API Capability Matrix — alicloud-aiops-ml

All Alibaba Cloud APIs consumed by the AIOps/FinOps skill. **Read-only only** — no Create/Modify/Delete operations.

## Data Collection APIs

| Product | API Action | Purpose | Key Parameters | Response Fields Used |
|---------|-----------|---------|---------------|---------------------|
| ECS | `DescribeInstances` | Instance inventory + specs | `RegionId`, `Status` (filter `Running`) | `InstanceId`, `InstanceName`, `InstanceType`, `Cpu`, `Memory` (MB→GB), `Status`, `ExpiredTime`, `InstanceChargeType`, `Tags.Tag[]`, `VpcAttributes.PrivateIpAddress.IpAddress[]` |
| ECS | `DescribeDisks` | Disk/cloud disk size | `RegionId`, `InstanceId` | `Disks.Disk[].Size` (GB), `Disks.Disk[].Type`, `Disks.Disk[].Category` |
| RDS | `DescribeDBInstances` | DB instance inventory | `RegionId` | `DBInstanceId`, `DBInstanceDescription`, `DBInstanceClass`, `DBInstanceMemory` (kB→GB), `DBInstanceStorage`, `DBInstanceStatus`, `ExpireTime`, `PayType` |
| Redis | `DescribeInstances` | Redis instance inventory | `RegionId`, `Status` (filter `Normal`) | `InstanceId`, `InstanceName`, `InstanceClass`, `Capacity` (MB→GB), `Bandwidth`, `QPS`, `InstanceStatus`, `ArchitectureType` |
| SLB | `DescribeLoadBalancers` | Load balancer inventory | `RegionId` | `LoadBalancerId`, `LoadBalancerName`, `AddressType`, `LoadBalancerSpec`, `NetworkType` |
| OSS | `GetBucketStat` | Bucket storage stats | `BucketName` | `Storage`, `ObjectCount`, `MultipartUploadCount`, `LiveChannelCount`, `LastModifiedTime` |
| CS | `GET /clusters` | K8s cluster list | `RegionId` | `cluster_id`, `name`, `cluster_type`, `state`, `vpc_id` |
| CS | `GET /clusters/{id}/nodes` | K8s node details | `cluster_id` | `instance_id`, `instance_name`, `instance_type`, `cpu`, `memory`, `node_status` |

## Monitoring APIs (CMS)

| Product | API Action | Purpose | Key Parameters | Response Fields Used |
|---------|-----------|---------|---------------|---------------------|
| CMS | `DescribeMetricList` | Time-series metrics | `Namespace`, `MetricName`, `Dimensions`, `StartTime`, `EndTime`, `Period` | `Datapoints` (JSON array of `{timestamp, Average, Maximum, Minimum}`) |

### CMS Metric Namespaces and Metrics

| Product | Namespace | Metrics Collected | Period |
|---------|-----------|-------------------|--------|
| ECS | `acs_ecs_dashboard` | `cpu.utilization`, `memory.usedutilization`, `disk.read.bytes`, `disk.write.bytes`, `disk.read.iops`, `disk.write.iops`, `InternetIn.rate`, `InternetOut.rate` | 3600s (hourly avg) |
| RDS | `acs_rds_dashboard` | `CPUUtilization`, `MemoryUsage`, `DiskUsage`, `QPS`, `ConnectionUsage`, `IOPSUsage` | 3600s |
| Redis | `acs_kvstore` | `CpuUsage`, `MemoryUsage`, `UsedQPS`, `IntranetIn`, `IntranetOut`, `ConnectionUsage` | 3600s |
| SLB | `acs_slb_dashboard` | `TrafficRX`, `TrafficTX`, `Qps`, `ActiveConnection`, `MaxConnection` | 3600s |

## Resource Management APIs

| Product | API Action | Purpose | Key Parameters | Response Fields Used |
|---------|-----------|---------|---------------|---------------------|
| ResourceManager | `ListResources` | Tag discovery | `ResourceType` (e.g. `ACS::ECS::Instance`), `RegionId` | `Resources.Resource[].ResourceId`, `Resources.Resource[].Tags.Tag[]` (key-value pairs) |

### Resource Types for Tag Discovery

| Resource Type ARN | Product | Collector |
|-------------------|---------|-----------|
| `ACS::ECS::Instance` | ECS | `ecs_collector.py` |
| `ACS::RDS::DBInstance` | RDS | `db_collector.py` |
| `ACS::Redis::DBInstance` | Redis | `db_collector.py` |
| `ACS::SLB::LoadBalancer` | SLB | `net_collector.py` |
| `ACS::OSS::Bucket` | OSS | `net_collector.py` |
| `ACS::CS::Cluster` | Container Service | `net_collector.py` |

## API Call Conventions

```
aliyun <product> <Action> --RegionId <region> --output json
```

- `DescribeInstances` series: pagination via `--PageNumber` / `--PageSize`
- CMS: API version **must** be `2019-05-01` (`--api-version 2019-05-01`)
- CS: REST API via `aliyun cs GET /clusters` (not `DescribeClusters`)
- Dimensions: CMS metric queries require `--Dimensions` with format `'[{"instanceId":"i-xxx"}]'`
