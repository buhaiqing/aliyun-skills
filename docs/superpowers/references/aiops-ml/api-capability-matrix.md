# API 能力矩阵 — alicloud-aiops-ml

> 本文件列出所有需要调用的阿里云 API，标注各 API 在当前 Skill 体系中的覆盖状态。
> Agent 无需外部搜索，直接使用本文件中的命令格式。

---

## 1. ECS

| 操作 | CLI 命令 | CMS 指标（--api-version 2019-05-01 必须） | 已有 Skill 覆盖 |
|------|---------|---------------------------------------------|--------------|
| 查实例列表 | `aliyun ecs DescribeInstances --RegionId $region --PageSize 100` | — | ✅ alicloud-ecs-ops |
| 查云盘 | `aliyun ecs DescribeDisks --RegionId $region --PageSize 100` | — | ✅ alicloud-ecs-ops |
| 查监控（ECS级别） | `aliyun cms DescribeMetricList --Namespace acs_ecs_dashboard --MetricName cpu.utilization --Dimensions "[{\"instanceId\":\"$i\"}]" --api-version 2019-05-01` | cpu.utilization, memory.usedutilization, disk.read.bytes, disk.write.bytes, disk.read.iops, disk.write.iops, InternetIn.rate, InternetOut.rate | ✅ alicloud-ecs-ops |

**ECS Memory 单位换算**：`DescribeInstances` 返回 `Memory = int(MB)`，需 ÷1024 转 GB。

**ECS 云盘大小**：`disk_gb` 需从 `DescribeDisks` 获取，不在 `DescribeInstances` 中。

**ECS CPU Credits（突发型实例）**：c9i/g9i/r9i 为突发型，`cpu.utilization` 无法区分 Credits 使用情况。如需分析突发，需调 `DescribeInstanceCreditSpecification`。

---

## 2. RDS

| 操作 | CLI 命令 | 已有 Skill 覆盖 |
|------|---------|--------------|
| 查实例列表 | `aliyun rds DescribeDBInstances --RegionId $region --PageSize 100` | ✅ alicloud-rds-ops |
| 查实例属性 | `aliyun rds DescribeDatabaseAttribute --DBInstanceId $id` | ✅ alicloud-rds-ops |
| 查监控 | `aliyun cms DescribeMetricList --Namespace acs_rds_dashboard --MetricName CPUUtilization --Dimensions "[{\"DBInstanceId\":\"$id\"}]" --api-version 2019-05-01` | CPUUtilization, MemoryUsage, DiskUsage, QPS, ConnectionUsage, IOPSUsage | ✅ alicloud-rds-ops |

**RDS Memory 单位换算**：`DBInstanceMemory = int(kB)`，需 ÷1024² 转 GB。

**RDS 存储**：`DiskUsed` 和 `DiskQuota` 来自 `DescribeDatabaseAttribute`（单位：GB），无需额外 API。

---

## 3. Redis

| 操作 | CLI 命令 | 已有 Skill 覆盖 |
|------|---------|--------------|
| 查实例列表 | `aliyun r-kvstore DescribeInstances --RegionId $region --PageSize 100` | ✅ alicloud-redis-ops |
| 查监控 | `aliyun cms DescribeMetricList --Namespace acs_kvstore_dashboard --MetricName MemoryUsage --Dimensions "[{\"instanceId\":\"$id\"}]" --api-version 2019-05-01` | MemoryUsage, QPS, ConnectionUsage, RejectedConnections | ✅ alicloud-redis-ops |

---

## 4. SLB

| 操作 | CLI 命令 | 已有 Skill 覆盖 |
|------|---------|--------------|
| 查实例列表 | `aliyun slb DescribeLoadBalancers --RegionId $region --PageSize 100` | ✅ alicloud-slb-ops |
| 查监控 | `aliyun cms DescribeMetricList --Namespace acs_slb_dashboard --MetricName TrafficRX --Dimensions "[{\"loadBalancerId\":\"$id\"}]" --api-version 2019-05-01` | TrafficRX, TrafficTX, Qps, ActiveConnection, BackendServerQps | ✅ alicloud-slb-ops |

**SLB 带宽字段**：`InternetBandwidth`（Mbps）来自 `DescribeLoadBalancers`。

---

## 5. OSS

| 操作 | CLI 命令 | 已有 Skill 覆盖 |
|------|---------|--------------|
| 查 bucket 列表 | `aliyun oss GetBucketInfo --Bucket $bucket` | ✅ alicloud-oss-ops |
| 查存储量 | `aliyun oss GetBucketStat --Bucket $bucket` | ✅ alicloud-oss-ops |
| **OSS 无 CloudMonitor 指标** | 存储量和流量来自 OSS API，不是 CMS | ✅ alicloud-oss-ops |

---

## 6. K8s（容器服务）

| 操作 | CLI 命令 | 已有 Skill 覆盖 |
|------|---------|--------------|
| 查集群列表 | `aliyun cs GET /clusters` | ✅ alicloud-ack-ops |
| 查集群详情 | `aliyun cs GET /clusters/{cluster_id}` | ✅ alicloud-ack-ops |
| 查节点列表 | `aliyun cs GET /clusters/{cluster_id}/nodes` | ✅ alicloud-ack-ops |
| 查 Pod 列表 | `aliyun cs GET /clusters/{cluster_id}/pods` | ✅ alicloud-ack-ops |
| **K8s 监控指标** | `aliyun cms DescribeMetricList --Namespace acs_k8s_dashboard --MetricName CpuUsage --Dimensions "[{\"clusterId\":\"$id\"}]" --api-version 2019-05-01` | CpuUsage, MemoryUsage | ✅ alicloud-ack-ops |

**K8s Node 采集注意**：
- `GET /clusters/{id}/nodes` 返回每个节点的 CPU/Memory allocatable 和 used
- **不是**从 CMS 采集，是从 CS API 采集
- 节点 `status` = "ready" 才计入可用容量

---

## 7. 标签（ResourceManager）

| 操作 | CLI 命令 | 已有 Skill 覆盖 |
|------|---------|--------------|
| 查所有资源标签 | `aliyun resourcemanager ListResources --ResourceType all --RegionId $region --PageSize 100` | ✅ alicloud-resourcemanager-ops |
| 按资源类型查标签 | `aliyun resourcemanager ListResources --ResourceType "ecs:instance" --RegionId $region` | ✅ alicloud-resourcemanager-ops |
| 查标签键列表 | `aliyun resourcemanager ListTagKeys --RegionId $region` | ✅ alicloud-resourcemanager-ops |
| 按标签过滤资源 | `aliyun resourcemanager ListTagResources --Tag "[\"product:iwms\"]" --ResourceType "ecs:instance" --RegionId $region` | ✅ alicloud-resourcemanager-ops |

**Tag 标准键（常见）**：`product`, `env`, `project`, `owner`, `cost_center`
**Tag 非标准键**：`business_line`（不存在于标准 Tag，需 fallback）
