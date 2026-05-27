# 成本可视化报告

## CLI 实现

```bash
# 获取实例信息
aliyun ecs DescribeInstances --RegionId "{{user.region}}" --output cols=InstanceId,InstanceName,InstanceType,Status rows=Instances.Instance[]

# 获取磁盘信息
aliyun ecs DescribeDisks --RegionId "{{user.region}}" --output cols=InstanceId,DiskId,Size,Category rows=Disks.Disk[]
```

## 成本优化建议

| 建议 | 节省 |
|------|------|
| 降配低利用率实例 | 60-80% |
| 预留实例(1年/3年) | 30-85% |
| 回收闲置实例 | 按实际节省 |
| 清理过期快照 | 按实际节省 |

## FinOps 详情

参见 [FinOps Cost Optimization](../alicloud-rds-ops/references/finops-analysis.md) 了解完整的成本分析方法。