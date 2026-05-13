# Monitoring Alibaba Cloud ECS

## Key Metrics

ECS metrics are available through CloudMonitor (`acs_ecs_dashboard` namespace):

| Metric Name | Description | Unit |
|-------------|-------------|------|
| `CPUUtilization` | CPU usage percentage | % |
| `InternetInRate` | Inbound internet traffic | bits/s |
| `InternetOutRate` | Outbound internet traffic | bits/s |
| `IntranetInRate` | Inbound intranet traffic | bits/s |
| `IntranetOutRate` | Outbound intranet traffic | bits/s |
| `DiskReadBPS` | Disk read throughput | bytes/s |
| `DiskWriteBPS` | Disk write throughput | bytes/s |
| `DiskReadIOPS` | Disk read IOPS | count/s |
| `DiskWriteIOPS` | Disk write IOPS | count/s |
| `MemoryUtilization` | Memory usage percentage | % |
| `LoadAverage` | System load average | - |
| `VPCPublicIPConnection` | Public IP connection count | count |
| `VPCPublicIPInRate` | VPC public IP inbound rate | bits/s |
| `VPCPublicIPOutRate` | VPC public IP outbound rate | bits/s |

## CloudMonitor CLI

```bash
# Describe metric list
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"i-bp67acfmxazb4ph***"}]' \
  --StartTime "2026-05-01T00:00:00Z" \
  --EndTime "2026-05-14T00:00:00Z"

# Describe metric metadata
aliyun cms DescribeMetricMetaList --Namespace acs_ecs_dashboard
```

## Alert Example (structure only)

```json
{
  "AlertName": "ecs-cpu-high",
  "Namespace": "acs_ecs_dashboard",
  "MetricName": "CPUUtilization",
  "Dimensions": [
    {
      "instanceId": "i-bp67acfmxazb4ph***"
    }
  ],
  "EvaluationCount": 3,
  "Period": 60,
  "Statistics": "Average",
  "ComparisonOperator": ">",
  "Threshold": 80,
  "ContactGroups": ["ecs-admins"]
}
```

## Log Service (SLS) Integration

ECS instances can send logs to Alibaba Cloud Log Service:

```bash
# Install Logtail on ECS instance
# Configure machine group in SLS console
# Create log collection configuration
```

## Auto Scaling

For dynamic scaling based on metrics:

```bash
# Describe scaling groups
aliyun ess DescribeScalingGroups --RegionId cn-hangzhou

# Describe scaling configurations
aliyun ess DescribeScalingConfigurations --RegionId cn-hangzhou
```
